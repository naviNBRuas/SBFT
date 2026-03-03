"""
SBFT Monitoring and Metrics System

Advanced monitoring system for tracking performance, detecting anomalies,
and providing real-time insights into the brute-force operation.

Author: Navin B. Ruas (NBR. Company LTD)
License: MIT
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from collections import defaultdict, deque
from datetime import datetime, timedelta
import threading
from pathlib import Path

logger = logging.getLogger("SBFT.Monitoring")


@dataclass
class PerformanceMetrics:
    """Comprehensive performance metrics"""

    start_time: float = field(default_factory=time.time)
    total_keys_processed: int = 0
    total_addresses_checked: int = 0
    keys_per_second: float = 0.0
    addresses_per_second: float = 0.0
    current_batch_size: int = 0
    batch_processing_times: deque = field(default_factory=lambda: deque(maxlen=100))
    provider_stats: Dict[str, Dict] = field(default_factory=dict)
    error_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    checkpoint_stats: Dict = field(default_factory=dict)

    def get_runtime(self) -> float:
        """Get total runtime in seconds"""
        return time.time() - self.start_time

    def get_formatted_runtime(self) -> str:
        """Get human-readable runtime"""
        runtime = self.get_runtime()
        hours = int(runtime // 3600)
        minutes = int((runtime % 3600) // 60)
        seconds = int(runtime % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


class AnomalyDetector:
    """Detects performance anomalies and system issues"""

    def __init__(self, window_size: int = 50):
        self.window_size = window_size
        self.processing_rates = deque(maxlen=window_size)
        self.error_rates = deque(maxlen=window_size)
        self.last_alert_time = 0
        self.alert_cooldown = 300  # 5 minutes between alerts

    def record_processing_rate(self, rate: float):
        """Record processing rate sample"""
        self.processing_rates.append(rate)

    def record_errors(self, error_count: int, total_requests: int):
        """Record error rate"""
        if total_requests > 0:
            error_rate = error_count / total_requests
            self.error_rates.append(error_rate)

    def detect_performance_drop(self) -> Optional[float]:
        """Detect significant performance drops"""
        if len(self.processing_rates) < 10:
            return None

        recent_avg = sum(list(self.processing_rates)[-5:]) / 5
        historical_avg = sum(self.processing_rates) / len(self.processing_rates)

        if historical_avg > 0:
            drop_percentage = (historical_avg - recent_avg) / historical_avg * 100
            if drop_percentage > 30:  # 30% drop threshold
                return drop_percentage
        return None

    def detect_high_error_rate(self) -> Optional[float]:
        """Detect high error rates"""
        if len(self.error_rates) < 10:
            return None

        recent_error_rate = sum(list(self.error_rates)[-5:]) / 5
        if recent_error_rate > 0.5:  # 50% error rate threshold
            return recent_error_rate
        return None

    def should_alert(self) -> bool:
        """Check if alert cooldown has passed"""
        return time.time() - self.last_alert_time > self.alert_cooldown

    def record_alert(self):
        """Record that an alert was sent"""
        self.last_alert_time = time.time()


class SystemHealthMonitor:
    """Monitors overall system health and resource usage"""

    def __init__(self):
        self.metrics = PerformanceMetrics()
        self.anomaly_detector = AnomalyDetector()
        self.providers_health: Dict[str, Dict] = {}
        self.system_stats: Dict = {}
        self.checkpoint_history: List[Dict] = []

    def update_processing_metrics(
        self,
        keys_processed: int,
        addresses_checked: int,
        batch_time: float,
        batch_size: int,
    ):
        """Update processing performance metrics"""
        self.metrics.total_keys_processed += keys_processed
        self.metrics.total_addresses_checked += addresses_checked
        self.metrics.current_batch_size = batch_size

        # Calculate rates
        runtime = self.metrics.get_runtime()
        self.metrics.keys_per_second = (
            self.metrics.total_keys_processed / runtime if runtime > 0 else 0
        )
        self.metrics.addresses_per_second = (
            self.metrics.total_addresses_checked / runtime if runtime > 0 else 0
        )

        # Record batch processing time
        self.metrics.batch_processing_times.append(batch_time)

        # Update anomaly detector
        self.anomaly_detector.record_processing_rate(self.metrics.keys_per_second)

    def update_provider_stats(self, provider_name: str, stats: Dict):
        """Update provider-specific statistics"""
        self.metrics.provider_stats[provider_name] = stats
        self.providers_health[provider_name] = stats

        # Track provider errors
        if "failed_requests" in stats and "requests_sent" in stats:
            failed = stats["failed_requests"]
            total = stats["requests_sent"]
            self.anomaly_detector.record_errors(failed, total)

    def update_system_stats(
        self,
        cpu_percent: Optional[float] = None,
        memory_mb: Optional[float] = None,
        disk_io: Optional[Dict] = None,
    ):
        """Update system resource statistics"""
        if cpu_percent is not None:
            self.system_stats["cpu_percent"] = cpu_percent
        if memory_mb is not None:
            self.system_stats["memory_mb"] = memory_mb
        if disk_io is not None:
            self.system_stats["disk_io"] = disk_io

    def record_checkpoint(self, checkpoint_data: Dict):
        """Record checkpoint statistics"""
        checkpoint_info = {
            "timestamp": datetime.now().isoformat(),
            "checkpoint_data": checkpoint_data,
            "performance": {
                "keys_per_second": self.metrics.keys_per_second,
                "addresses_per_second": self.metrics.addresses_per_second,
                "runtime": self.metrics.get_formatted_runtime(),
            },
        }
        self.checkpoint_history.append(checkpoint_info)

        # Keep only last 100 checkpoints
        if len(self.checkpoint_history) > 100:
            self.checkpoint_history.pop(0)

    def get_health_report(self) -> Dict:
        """Generate comprehensive health report"""
        runtime = self.metrics.get_runtime()

        # Detect anomalies
        perf_drop = self.anomaly_detector.detect_performance_drop()
        high_errors = self.anomaly_detector.detect_high_error_rate()

        report = {
            "timestamp": datetime.now().isoformat(),
            "runtime": self.metrics.get_formatted_runtime(),
            "performance": {
                "total_keys_processed": self.metrics.total_keys_processed,
                "total_addresses_checked": self.metrics.total_addresses_checked,
                "keys_per_second": round(self.metrics.keys_per_second, 2),
                "addresses_per_second": round(self.metrics.addresses_per_second, 2),
                "average_batch_time": (
                    sum(self.metrics.batch_processing_times)
                    / len(self.metrics.batch_processing_times)
                    if self.metrics.batch_processing_times
                    else 0
                ),
                "current_batch_size": self.metrics.current_batch_size,
            },
            "providers": self.providers_health,
            "system": self.system_stats,
            "anomalies": {
                "performance_drop": perf_drop,
                "high_error_rate": high_errors,
                "should_alert": self.anomaly_detector.should_alert(),
            },
            "checkpoints_recorded": len(self.checkpoint_history),
        }

        # Send alert if needed
        if (perf_drop or high_errors) and self.anomaly_detector.should_alert():
            self._send_alert(report)
            self.anomaly_detector.record_alert()

        return report

    def _send_alert(self, report: Dict):
        """Send alert about detected anomalies"""
        alerts = []
        if report["anomalies"]["performance_drop"]:
            alerts.append(
                f"Performance dropped by {report['anomalies']['performance_drop']:.1f}%"
            )
        if report["anomalies"]["high_error_rate"]:
            alerts.append(
                f"High error rate: {report['anomalies']['high_error_rate']:.1%}"
            )

        alert_msg = " | ".join(alerts)
        logger.warning(f"⚠️  SYSTEM ALERT: {alert_msg}")

    def save_metrics_snapshot(self, filepath: str):
        """Save current metrics to file"""
        try:
            report = self.get_health_report()
            with open(filepath, "w") as f:
                json.dump(report, f, indent=2)
            logger.info(f"📊 Metrics saved to {filepath}")
        except Exception as e:
            logger.error(f"Failed to save metrics: {e}")


class ProgressTracker:
    """Tracks overall progress through the key space"""

    def __init__(self, total_key_space: int = 2**128):
        self.total_key_space = total_key_space
        self.processed_indices: Set[int] = set()
        self.current_range_start = 0
        self.current_range_end = 0
        self.progress_history: List[Dict] = []

    def update_range(self, start: int, end: int):
        """Update current working range"""
        self.current_range_start = start
        self.current_range_end = end

    def mark_processed(self, indices: List[int]):
        """Mark indices as processed"""
        self.processed_indices.update(indices)

    def get_progress_percentage(self) -> float:
        """Get percentage of key space searched"""
        if self.total_key_space > 0:
            return len(self.processed_indices) / self.total_key_space * 100
        return 0.0

    def get_eta_seconds(self, keys_per_second: float) -> float:
        """Calculate estimated time remaining"""
        remaining_keys = self.total_key_space - len(self.processed_indices)
        if keys_per_second > 0:
            return remaining_keys / keys_per_second
        return float("inf")

    def get_formatted_eta(self, keys_per_second: float) -> str:
        """Get human-readable ETA"""
        eta_seconds = self.get_eta_seconds(keys_per_second)
        if eta_seconds == float("inf"):
            return "Unknown"

        days = int(eta_seconds // 86400)
        hours = int((eta_seconds % 86400) // 3600)
        minutes = int((eta_seconds % 3600) // 60)

        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"


# Global monitoring instance
monitor = SystemHealthMonitor()
progress_tracker = ProgressTracker()


# Periodic monitoring task
class MonitoringService:
    """Background service for periodic monitoring"""

    def __init__(self, interval_seconds: int = 30):
        self.interval = interval_seconds
        self.running = False
        self.task: Optional[asyncio.Task] = None

    async def start(self):
        """Start monitoring service"""
        self.running = True
        self.task = asyncio.create_task(self._monitor_loop())
        logger.info("🔍 Monitoring service started")

    async def stop(self):
        """Stop monitoring service"""
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("🔍 Monitoring service stopped")

    async def _monitor_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                # Generate and log health report
                report = monitor.get_health_report()

                # Log summary
                perf = report["performance"]
                logger.info(
                    f"📈 Progress: {perf['keys_per_second']:.0f} keys/s | "
                    f"{perf['addresses_per_second']:.0f} addresses/s | "
                    f"Runtime: {report['runtime']}"
                )

                # Check for anomalies
                anomalies = report["anomalies"]
                if anomalies["performance_drop"]:
                    logger.warning(
                        f"📉 Performance drop detected: {anomalies['performance_drop']:.1f}%"
                    )
                if anomalies["high_error_rate"]:
                    logger.warning(
                        f"⚠️  High error rate: {anomalies['high_error_rate']:.1%}"
                    )

                await asyncio.sleep(self.interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitoring error: {e}")
                await asyncio.sleep(self.interval)


# Global monitoring service instance
monitoring_service = MonitoringService()
