"""
SBFT Providers Module - Advanced Multi-Chain Blockchain API Integration

This module implements a robust, extensible provider system for checking cryptocurrency
balances across multiple networks and services. Features advanced error handling,
rate limiting, circuit breakers, and adaptive retry strategies.

Author: Navin B. Ruas (NBR. Company LTD)
License: MIT
"""

import asyncio
import hashlib
import json
import logging
import time
from typing import Dict, List, Optional, Set, Tuple, Union
from dataclasses import dataclass, field
from collections import defaultdict, deque
from datetime import datetime, timedelta
import aiohttp
from aiohttp import ClientTimeout, ClientError, ContentTypeError
import ssl

logger = logging.getLogger("SBFT.Providers")


@dataclass
class ProviderMetrics:
    """Tracks performance metrics for each provider"""

    requests_sent: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_response_time: float = 0.0
    errors_by_type: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    last_request_time: float = 0.0
    circuit_open: bool = False
    failure_streak: int = 0
    success_streak: int = 0


class CircuitBreaker:
    """
    Implements circuit breaker pattern to prevent cascading failures
    """

    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection"""
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.timeout:
                self.state = "HALF_OPEN"
            else:
                raise Exception("Circuit breaker is OPEN")

        try:
            result = func(*args, **kwargs)
            self.on_success()
            return result
        except Exception as e:
            self.on_failure()
            raise e

    async def async_call(self, coro):
        """Execute async coroutine with circuit breaker protection"""
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.timeout:
                self.state = "HALF_OPEN"
            else:
                raise Exception("Circuit breaker is OPEN")

        try:
            result = await coro
            self.on_success()
            return result
        except Exception as e:
            self.on_failure()
            raise e

    def on_success(self):
        """Handle successful request"""
        self.failure_count = 0
        if self.state == "HALF_OPEN":
            self.state = "CLOSED"

    def on_failure(self):
        """Handle failed request"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"


class RateLimiter:
    """
    Token bucket rate limiter for API rate control
    """

    def __init__(self, requests_per_second: float = 10.0, burst_size: int = 20):
        self.tokens = burst_size
        self.max_tokens = burst_size
        self.refill_rate = requests_per_second
        self.last_refill = time.time()

    def _refill_tokens(self):
        """Refill tokens based on elapsed time"""
        now = time.time()
        elapsed = now - self.last_refill
        new_tokens = elapsed * self.refill_rate
        self.tokens = min(self.max_tokens, self.tokens + new_tokens)
        self.last_refill = now

    async def acquire(self):
        """Acquire token for request"""
        while True:
            self._refill_tokens()
            if self.tokens >= 1:
                self.tokens -= 1
                return
            # Calculate sleep time needed
            sleep_time = (1 - self.tokens) / self.refill_rate
            await asyncio.sleep(sleep_time)


class AwaitableDict(dict):
    """Dictionary that can also be awaited (returns itself)."""

    def __await__(self):
        async def _inner():
            return self

        return _inner().__await__()


def _run_async(coro):
    """Run coroutine in sync contexts."""
    return asyncio.run(coro)


class ProviderBase:
    """
    Abstract base class for all blockchain providers
    """

    def __init__(self, api_key: Optional[str] = None, network: str = "bitcoin"):
        self.api_key = api_key
        self.network = network
        self.metrics = ProviderMetrics()
        self.circuit_breaker = CircuitBreaker()
        self.rate_limiter = RateLimiter()
        self.session: Optional[aiohttp.ClientSession] = None
        self.timeout = ClientTimeout(total=30, connect=10)

    @property
    def name(self) -> str:
        """Provider name"""
        return self.__class__.__name__.lower()

    @property
    def base_url(self) -> str:
        """Base API URL"""
        return ""

    def get_balances(self, addresses: List[str]) -> Dict[str, int]:
        """
        Get balances for multiple addresses

        Args:
            addresses: List of cryptocurrency addresses

        Returns:
            Dictionary mapping addresses to balances (in satoshis/wei)
        """
        raise NotImplementedError("Provider subclasses must implement get_balances")

    def _record_metrics(
        self, success: bool, response_time: float, error_type: Optional[str] = None
    ):
        """Record request metrics"""
        self.metrics.requests_sent += 1
        self.metrics.total_response_time += response_time
        self.metrics.last_request_time = time.time()

        if success:
            self.metrics.successful_requests += 1
            self.metrics.success_streak += 1
            self.metrics.failure_streak = 0
        else:
            self.metrics.failed_requests += 1
            self.metrics.errors_by_type[error_type or "unknown"] += 1
            self.metrics.failure_streak += 1
            self.metrics.success_streak = 0

    def get_health_stats(self) -> Dict:
        """Get provider health statistics"""
        avg_response_time = (
            self.metrics.total_response_time / self.metrics.requests_sent
            if self.metrics.requests_sent > 0
            else 0
        )

        success_rate = (
            self.metrics.successful_requests / self.metrics.requests_sent * 100
            if self.metrics.requests_sent > 0
            else 0
        )

        return {
            "provider": self.name,
            "requests_sent": self.metrics.requests_sent,
            "successful_requests": self.metrics.successful_requests,
            "failed_requests": self.metrics.failed_requests,
            "success_rate": round(success_rate, 2),
            "avg_response_time": round(avg_response_time, 3),
            "circuit_open": self.metrics.circuit_open,
            "failure_streak": self.metrics.failure_streak,
            "errors": dict(self.metrics.errors_by_type),
        }

    async def __aenter__(self):
        """Async context manager entry"""
        connector = aiohttp.TCPConnector(
            limit=100,
            limit_per_host=20,
            ttl_dns_cache=300,
            use_dns_cache=True,
            ssl=ssl.create_default_context(),
        )
        self.session = aiohttp.ClientSession(
            timeout=self.timeout,
            connector=connector,
            headers={
                "User-Agent": "SBFT/1.0 (Educational Research Tool)",
                "Accept": "application/json",
            },
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
            self.session = None


class BlockcypherProvider(ProviderBase):
    """BlockCypher API provider with enhanced error handling"""

    @property
    def name(self) -> str:
        return "blockcypher"

    @property
    def base_url(self) -> str:
        return "https://api.blockcypher.com/v1/btc/main"

    def get_balances(self, addresses: List[str]) -> Dict[str, int]:
        return AwaitableDict(_run_async(self._get_balances_async(addresses)))

    async def _get_balances_async(self, addresses: List[str]) -> Dict[str, int]:
        start_time = time.time()
        try:
            await self.rate_limiter.acquire()

            # BlockCypher supports batch requests for up to 200 addresses
            batch_size = 200
            results = {}

            for i in range(0, len(addresses), batch_size):
                batch = addresses[i : i + batch_size]
                batch_results = await self._get_batch_balances(batch)
                results.update(batch_results)

            self._record_metrics(True, time.time() - start_time)
            return results

        except Exception as e:
            error_type = type(e).__name__
            self._record_metrics(False, time.time() - start_time, error_type)
            logger.warning(f"{self.name} failed to get balances: {error_type}")
            # Return zero balances for failed addresses
            return {addr: 0 for addr in addresses}

    async def _get_batch_balances(self, addresses: List[str]) -> Dict[str, int]:
        """Get balances for a batch of addresses"""
        url = f"{self.base_url}/addrs/{';'.join(addresses)}/balance"

        params = {}
        if self.api_key:
            params["token"] = self.api_key

        if self.session is None:
            async with self:
                return await self._get_batch_balances(addresses)

        async with self.session.get(url, params=params) as response:
            if response.status == 429:
                # Rate limited - exponential backoff
                retry_after = int(response.headers.get("Retry-After", 1))
                await asyncio.sleep(min(retry_after, 60))
                raise Exception("Rate limited")

            response.raise_for_status()
            data = await response.json()

            if isinstance(data, dict) and "address" in data:
                # Single address response
                return {data["address"]: data.get("final_balance", 0)}
            elif isinstance(data, list):
                # Multiple addresses response
                return {item["address"]: item.get("final_balance", 0) for item in data}
            else:
                return {addr: 0 for addr in addresses}


class BlockstreamProvider(ProviderBase):
    """Blockstream API provider with enhanced capabilities"""

    @property
    def name(self) -> str:
        return "blockstream"

    @property
    def base_url(self) -> str:
        return "https://blockstream.info/api"

    def get_balances(self, addresses: List[str]) -> Dict[str, int]:
        return AwaitableDict(_run_async(self._get_balances_async(addresses)))

    async def _get_balances_async(self, addresses: List[str]) -> Dict[str, int]:
        start_time = time.time()
        try:
            await self.rate_limiter.acquire()

            # Blockstream allows individual address queries
            # We'll make concurrent requests for better performance
            tasks = [self._get_single_balance(addr) for addr in addresses]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            balances = {}
            for addr, result in zip(addresses, results):
                if isinstance(result, Exception):
                    logger.debug(f"Failed to get balance for {addr}: {result}")
                    balances[addr] = 0
                else:
                    balances[addr] = result

            self._record_metrics(True, time.time() - start_time)
            return balances

        except Exception as e:
            error_type = type(e).__name__
            self._record_metrics(False, time.time() - start_time, error_type)
            logger.warning(f"{self.name} failed to get balances: {error_type}")
            return {addr: 0 for addr in addresses}

    async def _get_single_balance(self, address: str) -> int:
        """Get balance for a single address"""
        url = f"{self.base_url}/address/{address}"

        if self.session is None:
            async with self:
                return await self._get_single_balance(address)

        async with self.session.get(url) as response:
            if response.status == 429:
                await asyncio.sleep(1)  # Blockstream rate limits aggressively
                raise Exception("Rate limited")

            response.raise_for_status()
            data = await response.json()

            # Chain stats contains confirmed balance
            chain_stats = data.get("chain_stats", {})
            return chain_stats.get("funded_txo_sum", 0) - chain_stats.get(
                "spent_txo_sum", 0
            )


class AlchemyProvider(ProviderBase):
    """Alchemy API provider for Ethereum and other EVM chains"""

    def __init__(self, api_key: str, network: str = "ethereum"):
        super().__init__(api_key, network)
        self.rate_limiter = RateLimiter(requests_per_second=15.0, burst_size=30)

    @property
    def name(self) -> str:
        return "alchemy"

    @property
    def base_url(self) -> str:
        network_map = {
            "ethereum": "eth-mainnet",
            "polygon": "polygon-mainnet",
            "arbitrum": "arb-mainnet",
            "optimism": "opt-mainnet",
        }
        network_id = network_map.get(self.network, "eth-mainnet")
        return f"https://{network_id}.g.alchemy.com/v2/{self.api_key}"

    def get_balances(self, addresses: List[str]) -> Dict[str, int]:
        return AwaitableDict(_run_async(self._get_balances_async(addresses)))

    async def _get_balances_async(self, addresses: List[str]) -> Dict[str, int]:
        start_time = time.time()
        try:
            await self.rate_limiter.acquire()

            # Alchemy supports batch requests via JSON-RPC
            batch_requests = []
            for i, address in enumerate(addresses):
                batch_requests.append(
                    {
                        "jsonrpc": "2.0",
                        "id": i,
                        "method": "eth_getBalance",
                        "params": [address, "latest"],
                    }
                )

            if self.session is None:
                async with self:
                    return await self._get_balances_async(addresses)

            async with self.session.post(
                self.base_url, json=batch_requests
            ) as response:
                response.raise_for_status()
                results = await response.json()

                balances = {}
                if isinstance(results, list):
                    for i, result in enumerate(results):
                        if "result" in result:
                            # Convert hex balance to wei (int)
                            hex_balance = result["result"]
                            balances[addresses[i]] = (
                                int(hex_balance, 16)
                                if hex_balance.startswith("0x")
                                else 0
                            )
                        else:
                            balances[addresses[i]] = 0
                else:
                    # Single result
                    if "result" in results:
                        balances = {addresses[0]: int(results["result"], 16)}
                    else:
                        balances = {addr: 0 for addr in addresses}

            self._record_metrics(True, time.time() - start_time)
            return balances

        except Exception as e:
            error_type = type(e).__name__
            self._record_metrics(False, time.time() - start_time, error_type)
            logger.warning(f"{self.name} failed to get balances: {error_type}")
            return {addr: 0 for addr in addresses}


class InfuraProvider(ProviderBase):
    """Infura API provider for Ethereum"""

    def __init__(
        self,
        project_id: str,
        project_secret: Optional[str] = None,
        network: str = "ethereum",
    ):
        super().__init__(None, network)
        self.project_id = project_id
        self.project_secret = project_secret
        self.rate_limiter = RateLimiter(requests_per_second=10.0, burst_size=20)

    @property
    def name(self) -> str:
        return "infura"

    @property
    def base_url(self) -> str:
        network_map = {
            "ethereum": "mainnet",
            "polygon": "polygon-mainnet",
            "arbitrum": "arbitrum-mainnet",
            "optimism": "optimism-mainnet",
        }
        network_name = network_map.get(self.network, "mainnet")
        auth = (
            f"{self.project_id}:{self.project_secret}@" if self.project_secret else ""
        )
        return f"https://{auth}{network_name}.infura.io/v3/{self.project_id}"

    def get_balances(self, addresses: List[str]) -> Dict[str, int]:
        return AwaitableDict(_run_async(self._get_balances_async(addresses)))

    async def _get_balances_async(self, addresses: List[str]) -> Dict[str, int]:
        start_time = time.time()
        try:
            await self.rate_limiter.acquire()

            # Similar to Alchemy, use batch JSON-RPC
            batch_requests = []
            for i, address in enumerate(addresses):
                batch_requests.append(
                    {
                        "jsonrpc": "2.0",
                        "id": i,
                        "method": "eth_getBalance",
                        "params": [address, "latest"],
                    }
                )

            auth = (
                aiohttp.BasicAuth(self.project_id, self.project_secret)
                if self.project_secret
                else None
            )

            if self.session is None:
                async with self:
                    return await self._get_balances_async(addresses)

            async with self.session.post(
                f"https://{self.network}.infura.io/v3/{self.project_id}",
                json=batch_requests,
                auth=auth,
            ) as response:
                response.raise_for_status()
                results = await response.json()

                balances = {}
                if isinstance(results, list):
                    for i, result in enumerate(results):
                        if "result" in result:
                            hex_balance = result["result"]
                            balances[addresses[i]] = (
                                int(hex_balance, 16)
                                if hex_balance.startswith("0x")
                                else 0
                            )
                        else:
                            balances[addresses[i]] = 0
                else:
                    if "result" in results:
                        balances = {addresses[0]: int(results["result"], 16)}
                    else:
                        balances = {addr: 0 for addr in addresses}

            self._record_metrics(True, time.time() - start_time)
            return balances

        except Exception as e:
            error_type = type(e).__name__
            self._record_metrics(False, time.time() - start_time, error_type)
            logger.warning(f"{self.name} failed to get balances: {error_type}")
            return {addr: 0 for addr in addresses}


class DummyProvider(ProviderBase):
    """Dummy provider for testing - always returns zero balances"""

    @property
    def name(self) -> str:
        return "dummy"

    @property
    def base_url(self) -> str:
        return "http://localhost/dummy"

    def get_balances(self, addresses: List[str]) -> Dict[str, int]:
        return AwaitableDict({addr: 0 for addr in addresses})


# Provider factory mapping
PROVIDER_CLASSES = {
    "blockcypher": BlockcypherProvider,
    "blockstream": BlockstreamProvider,
    "alchemy": AlchemyProvider,
    "infura": InfuraProvider,
    "dummy": DummyProvider,
}


def create_provider(provider_name: str, **kwargs) -> ProviderBase:
    """
    Factory function to create provider instances

    Args:
        provider_name: Name of the provider (blockcypher, blockstream, etc.)
        **kwargs: Provider-specific configuration (api_key, network, etc.)

    Returns:
        Provider instance

    Raises:
        ValueError: If provider name is not supported
    """
    if provider_name not in PROVIDER_CLASSES:
        raise ValueError(f"Unsupported provider: {provider_name}")

    return PROVIDER_CLASSES[provider_name](**kwargs)


def get_available_providers() -> List[str]:
    """Get list of available provider names"""
    return list(PROVIDER_CLASSES.keys())
