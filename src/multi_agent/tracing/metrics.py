"""Performance metrics tracking for multi-agent framework.

This module provides metrics collection and reporting for framework operations.
"""

import time
from collections import defaultdict
from contextlib import contextmanager
from typing import Any, Optional

from ..utils import get_logger

logger = get_logger(__name__)


class Metrics:
    """Performance metrics for a single operation.

    Attributes:
        name: Operation name
        duration_ms: Duration in milliseconds
        success: Whether operation succeeded
        error: Error message if failed
        metadata: Additional metadata
    """

    def __init__(
        self,
        name: str,
        duration_ms: float,
        success: bool = True,
        error: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """Initialize metrics.

        Args:
            name: Operation name
            duration_ms: Duration in milliseconds
            success: Whether operation succeeded
            error: Error message if failed
            metadata: Additional metadata
        """
        self.name = name
        self.duration_ms = duration_ms
        self.success = success
        self.error = error
        self.metadata = metadata or {}

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "name": self.name,
            "duration_ms": self.duration_ms,
            "success": self.success,
            "error": self.error,
            "metadata": self.metadata,
        }


class MetricsTracker:
    """Tracks performance metrics for framework operations.

    Provides collection, aggregation, and reporting of metrics.
    """

    def __init__(self) -> None:
        """Initialize the metrics tracker."""
        self._metrics: list[Metrics] = []
        self._counters: dict[str, int] = defaultdict(int)
        self._gauges: dict[str, float] = {}
        self._start_times: dict[str, float] = {}

    def record_metric(self, metric: Metrics) -> None:
        """Record a metric.

        Args:
            metric: Metric to record
        """
        self._metrics.append(metric)
        logger.debug(f"Recorded metric: {metric.name} ({metric.duration_ms}ms)")

    def increment_counter(self, name: str, value: int = 1) -> None:
        """Increment a counter.

        Args:
            name: Counter name
            value: Value to increment by
        """
        self._counters[name] += value

    def set_gauge(self, name: str, value: float) -> None:
        """Set a gauge value.

        Args:
            name: Gauge name
            value: Gauge value
        """
        self._gauges[name] = value

    def get_counter(self, name: str) -> int:
        """Get counter value.

        Args:
            name: Counter name

        Returns:
            Counter value
        """
        return self._counters.get(name, 0)

    def get_gauge(self, name: str) -> Optional[float]:
        """Get gauge value.

        Args:
            name: Gauge name

        Returns:
            Gauge value or None
        """
        return self._gauges.get(name)

    def get_metrics_by_name(self, name: str) -> list[Metrics]:
        """Get all metrics with a specific name.

        Args:
            name: Metric name

        Returns:
            List of matching metrics
        """
        return [m for m in self._metrics if m.name == name]

    def get_average_duration(self, name: str) -> Optional[float]:
        """Get average duration for a metric name.

        Args:
            name: Metric name

        Returns:
            Average duration in milliseconds or None
        """
        matching = self.get_metrics_by_name(name)
        if not matching:
            return None

        total = sum(m.duration_ms for m in matching)
        return total / len(matching)

    def get_success_rate(self, name: str) -> Optional[float]:
        """Get success rate for a metric name.

        Args:
            name: Metric name

        Returns:
            Success rate (0-1) or None
        """
        matching = self.get_metrics_by_name(name)
        if not matching:
            return None

        successful = sum(1 for m in matching if m.success)
        return successful / len(matching)

    def get_percentile(self, name: str, percentile: float) -> Optional[float]:
        """Get percentile duration for a metric name.

        Args:
            name: Metric name
            percentile: Percentile to calculate (0-100)

        Returns:
            Percentile value or None
        """
        matching = self.get_metrics_by_name(name)
        if not matching:
            return None

        durations = sorted(m.duration_ms for m in matching)
        index = int(len(durations) * percentile / 100)
        return durations[min(index, len(durations) - 1)]

    def get_summary(self) -> dict[str, Any]:
        """Get metrics summary.

        Returns:
            Summary of all metrics
        """
        summary: dict[str, Any] = {}

        # Group by metric name
        by_name: dict[str, list[Metrics]] = defaultdict(list)
        for metric in self._metrics:
            by_name[metric.name].append(metric)

        # Calculate statistics for each name
        for name, metrics_list in by_name.items():
            durations = [m.duration_ms for m in metrics_list]
            successes = sum(1 for m in metrics_list if m.success)

            summary[name] = {
                "count": len(metrics_list),
                "total_duration_ms": sum(durations),
                "avg_duration_ms": sum(durations) / len(durations),
                "min_duration_ms": min(durations),
                "max_duration_ms": max(durations),
                "success_rate": successes / len(metrics_list),
            }

        # Add counters and gauges
        summary["counters"] = dict(self._counters)
        summary["gauges"] = self._gauges

        return summary

    def reset(self) -> None:
        """Reset all metrics."""
        self._metrics.clear()
        self._counters.clear()
        self._gauges.clear()
        self._start_times.clear()

    @contextmanager
    def track_operation(self, name: str, metadata: Optional[dict[str, Any]] = None):
        """Context manager for tracking an operation.

        Args:
            name: Operation name
            metadata: Optional metadata

        Yields:
            None
        """
        start_time = time.time()
        error = None

        try:
            yield
        except Exception as e:
            error = str(e)
            raise
        finally:
            duration_ms = (time.time() - start_time) * 1000
            self.record_metric(Metrics(
                name=name,
                duration_ms=duration_ms,
                success=error is None,
                error=error,
                metadata=metadata or {},
            ))


# Global metrics tracker
_global_tracker: Optional[MetricsTracker] = None


def get_metrics_tracker() -> MetricsTracker:
    """Get the global metrics tracker.

    Returns:
        Global metrics tracker
    """
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = MetricsTracker()
    return _global_tracker


def reset_metrics() -> None:
    """Reset the global metrics tracker."""
    global _global_tracker
    if _global_tracker:
        _global_tracker.reset()
