"""Metrics collection and computation for ZERG workers and tasks."""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from zerg.constants import TaskStatus
from zerg.logging import get_logger
from zerg.types import (
    FeatureMetrics,
    LevelMetrics,
    TaskMetrics,
    WorkerMetrics,
)

if TYPE_CHECKING:
    from zerg.state import StateManager

logger = get_logger("metrics")


def duration_ms(
    start: datetime | str | None,
    end: datetime | str | None,
) -> int | None:
    """Calculate duration in milliseconds between two timestamps.

    Args:
        start: Start timestamp (datetime or ISO string)
        end: End timestamp (datetime or ISO string)

    Returns:
        Duration in milliseconds, or None if either timestamp is None
    """
    if start is None or end is None:
        return None

    # Convert strings to datetime if needed
    if isinstance(start, str):
        start = datetime.fromisoformat(start)
    if isinstance(end, str):
        end = datetime.fromisoformat(end)

    delta = end - start
    return int(delta.total_seconds() * 1000)


def calculate_percentile(values: Sequence[int | float], percentile: float) -> int:
    """Calculate percentile value from a list.

    Args:
        values: List of numeric values
        percentile: Percentile to calculate (0-100)

    Returns:
        Percentile value as integer, or 0 if list is empty
    """
    if not values:
        return 0

    sorted_values = sorted(values)
    n = len(sorted_values)

    # Calculate index
    index = (percentile / 100) * (n - 1)

    # Handle edge cases
    if index <= 0:
        return int(sorted_values[0])
    if index >= n - 1:
        return int(sorted_values[-1])

    # Linear interpolation for non-integer indices
    lower_idx = int(index)
    upper_idx = lower_idx + 1
    fraction = index - lower_idx

    lower_val = sorted_values[lower_idx]
    upper_val = sorted_values[upper_idx]

    return int(lower_val + fraction * (upper_val - lower_val))


class MetricsCollector:
    """Collect and compute metrics from ZERG execution state."""

    def __init__(self, state: StateManager) -> None:
        """Initialize metrics collector.

        Args:
            state: StateManager instance to read state from
        """
        self.state = state
        self._state_data: dict[str, Any] = {}

    def _refresh_state(self) -> None:
        """Refresh internal state data from StateManager."""
        self._state_data = self.state.load()

    def compute_worker_metrics(self, worker_id: int) -> WorkerMetrics:
        """Compute metrics for a single worker.

        Args:
            worker_id: Worker identifier

        Returns:
            WorkerMetrics for the worker
        """
        self._refresh_state()

        worker_data = self._state_data.get("workers", {}).get(str(worker_id), {})

        # Calculate initialization time (ready_at - started_at)
        started_at = worker_data.get("started_at")
        ready_at = worker_data.get("ready_at")
        initialization_ms = duration_ms(started_at, ready_at)

        # Calculate uptime (now - started_at)
        uptime_ms = 0
        if started_at:
            uptime_ms = duration_ms(started_at, datetime.now()) or 0

        # Count completed and failed tasks for this worker
        tasks_completed = 0
        tasks_failed = 0
        total_task_duration_ms = 0
        task_durations: list[int] = []

        for _task_id, task_data in self._state_data.get("tasks", {}).items():
            if task_data.get("worker_id") != worker_id:
                continue

            status = task_data.get("status")
            if status == TaskStatus.COMPLETE.value:
                tasks_completed += 1
                # Get task duration
                task_duration = task_data.get("duration_ms")
                if task_duration:
                    task_durations.append(task_duration)
                    total_task_duration_ms += task_duration
            elif status == TaskStatus.FAILED.value:
                tasks_failed += 1

        # Calculate average
        avg_task_duration_ms = 0.0
        if task_durations:
            avg_task_duration_ms = total_task_duration_ms / len(task_durations)

        return WorkerMetrics(
            worker_id=worker_id,
            initialization_ms=initialization_ms,
            uptime_ms=uptime_ms,
            tasks_completed=tasks_completed,
            tasks_failed=tasks_failed,
            total_task_duration_ms=total_task_duration_ms,
            avg_task_duration_ms=avg_task_duration_ms,
        )

    def compute_task_metrics(self, task_id: str) -> TaskMetrics:
        """Compute metrics for a single task.

        Args:
            task_id: Task identifier

        Returns:
            TaskMetrics for the task
        """
        self._refresh_state()

        task_data = self._state_data.get("tasks", {}).get(task_id, {})

        # Queue wait time (claimed_at - created_at)
        # Note: created_at may not exist in state, use started_at of feature as fallback
        created_at = task_data.get("created_at") or self._state_data.get("started_at")
        claimed_at = task_data.get("claimed_at")
        queue_wait_ms = duration_ms(created_at, claimed_at)

        # Execution duration (completed_at - started_at)
        started_at = task_data.get("started_at")
        completed_at = task_data.get("completed_at")
        execution_duration_ms = duration_ms(started_at, completed_at)

        # Verification duration (from stored duration_ms or VerificationResult)
        verification_duration_ms = task_data.get("verification_duration_ms")

        # Total duration (completed_at - created_at OR claimed_at)
        total_start = claimed_at or created_at
        total_duration_ms = duration_ms(total_start, completed_at)

        return TaskMetrics(
            task_id=task_id,
            queue_wait_ms=queue_wait_ms,
            execution_duration_ms=execution_duration_ms,
            verification_duration_ms=verification_duration_ms,
            total_duration_ms=total_duration_ms,
        )

    def compute_level_metrics(self, level: int) -> LevelMetrics:
        """Compute metrics for a level.

        Args:
            level: Level number

        Returns:
            LevelMetrics for the level
        """
        self._refresh_state()

        level_data = self._state_data.get("levels", {}).get(str(level), {})

        # Level duration (completed_at - started_at)
        started_at = level_data.get("started_at")
        completed_at = level_data.get("completed_at")
        level_duration_ms = duration_ms(started_at, completed_at)

        # Count tasks and gather durations for this level
        task_count = 0
        completed_count = 0
        failed_count = 0
        task_durations: list[int] = []

        # Find tasks for this level by checking task data
        for _task_id, task_data in self._state_data.get("tasks", {}).items():
            task_level = task_data.get("level")
            if task_level != level:
                continue

            task_count += 1
            status = task_data.get("status")

            if status == TaskStatus.COMPLETE.value:
                completed_count += 1
                duration = task_data.get("duration_ms")
                if duration:
                    task_durations.append(duration)
            elif status == TaskStatus.FAILED.value:
                failed_count += 1

        # Calculate statistics
        avg_task_duration_ms = 0.0
        if task_durations:
            avg_task_duration_ms = sum(task_durations) / len(task_durations)

        p50_duration_ms = calculate_percentile(task_durations, 50)
        p95_duration_ms = calculate_percentile(task_durations, 95)

        return LevelMetrics(
            level=level,
            duration_ms=level_duration_ms,
            task_count=task_count,
            completed_count=completed_count,
            failed_count=failed_count,
            avg_task_duration_ms=avg_task_duration_ms,
            p50_duration_ms=p50_duration_ms,
            p95_duration_ms=p95_duration_ms,
        )

    def compute_feature_metrics(self) -> FeatureMetrics:
        """Compute aggregated metrics for the entire feature.

        Returns:
            FeatureMetrics with all aggregations
        """
        self._refresh_state()

        now = datetime.now()

        # Total duration (now - started_at OR completed_at - started_at)
        started_at = self._state_data.get("started_at")
        # Check if feature is complete
        all_levels = self._state_data.get("levels", {})
        feature_completed_at = None
        for level_data in all_levels.values():
            if level_data.get("status") == "complete":
                lvl_completed = level_data.get("completed_at")
                if lvl_completed and (feature_completed_at is None or lvl_completed > feature_completed_at):
                    feature_completed_at = lvl_completed

        end_time = feature_completed_at or now.isoformat()
        total_duration_ms = duration_ms(started_at, end_time)

        # Count workers
        workers_data = self._state_data.get("workers", {})
        workers_used = len(workers_data)

        # Count tasks
        tasks_data = self._state_data.get("tasks", {})
        tasks_total = len(tasks_data)
        tasks_completed = sum(1 for t in tasks_data.values() if t.get("status") == TaskStatus.COMPLETE.value)
        tasks_failed = sum(1 for t in tasks_data.values() if t.get("status") == TaskStatus.FAILED.value)

        # Count completed levels
        levels_completed = sum(1 for lvl in all_levels.values() if lvl.get("status") == "complete")

        # Compute per-worker metrics
        worker_metrics = [self.compute_worker_metrics(int(wid)) for wid in workers_data]

        # Compute per-level metrics
        level_metrics = [self.compute_level_metrics(int(lvl)) for lvl in all_levels]

        return FeatureMetrics(
            computed_at=now,
            total_duration_ms=total_duration_ms,
            workers_used=workers_used,
            tasks_total=tasks_total,
            tasks_completed=tasks_completed,
            tasks_failed=tasks_failed,
            levels_completed=levels_completed,
            worker_metrics=worker_metrics,
            level_metrics=level_metrics,
        )

    def export_json(self, path: str | Path) -> None:
        """Export metrics to a JSON file.

        Args:
            path: Path to write JSON file
        """
        metrics = self.compute_feature_metrics()
        output_path = Path(path)

        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(metrics.to_dict(), f, indent=2, default=str)

        logger.info(f"Exported metrics to {output_path}")
