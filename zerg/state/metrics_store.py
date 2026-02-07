"""Metrics store — timing, counts, and feature metrics persistence.

Records task execution timings, durations, and stores computed
feature-level metrics for reporting.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from zerg.logging import get_logger

if TYPE_CHECKING:
    from zerg.state.persistence import PersistenceLayer
    from zerg.types import FeatureMetrics

logger = get_logger("state.metrics_store")


class MetricsStore:
    """Metrics storage and retrieval.

    Records task timing data and stores/retrieves computed feature metrics.
    All operations delegate file I/O to the PersistenceLayer.
    """

    def __init__(self, persistence: PersistenceLayer) -> None:
        """Initialize metrics store.

        Args:
            persistence: PersistenceLayer instance for data access
        """
        self._persistence = persistence

    def record_task_duration(self, task_id: str, duration_ms: int) -> None:
        """Record task execution duration.

        Args:
            task_id: Task identifier
            duration_ms: Execution duration in milliseconds
        """
        with self._persistence.atomic_update():
            if task_id in self._persistence.state.get("tasks", {}):
                self._persistence.state["tasks"][task_id]["duration_ms"] = duration_ms

        logger.debug(f"Task {task_id} duration: {duration_ms}ms")

    def store_metrics(self, metrics: FeatureMetrics) -> None:
        """Store computed metrics to state.

        Args:
            metrics: FeatureMetrics to persist
        """
        with self._persistence.atomic_update():
            self._persistence.state["metrics"] = metrics.to_dict()

        logger.debug("Stored feature metrics")

    def get_metrics(self) -> FeatureMetrics | None:
        """Retrieve stored metrics.

        Returns:
            FeatureMetrics if available, None otherwise
        """
        with self._persistence.lock:
            metrics_data = self._persistence.state.get("metrics")
            if not metrics_data:
                return None

            # Import here to avoid circular import
            from zerg.types import FeatureMetrics

            return FeatureMetrics.from_dict(metrics_data)
