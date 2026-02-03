"""ZERG Worker Metrics Collection.

Provides comprehensive metrics collection and tracking for worker instances,
including task execution timing, context usage, resource consumption, and
aggregated statistics.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class TaskExecutionMetrics:
    """Metrics for a single task execution."""

    task_id: str
    worker_id: int
    started_at: datetime
    completed_at: datetime | None = None
    status: str = "running"
    duration_seconds: float | None = None
    context_usage_before: float = 0.0
    context_usage_after: float = 0.0
    retry_count: int = 0
    verification_passed: bool | None = None
    verification_duration_ms: int | None = None
    error_message: str | None = None

    def complete(
        self,
        status: str = "completed",
        context_usage: float | None = None,
        verification_passed: bool | None = None,
        verification_duration_ms: int | None = None,
        error_message: str | None = None,
    ) -> None:
        """Mark task as completed with final metrics.

        Args:
            status: Final status (completed, failed, skipped)
            context_usage: Context usage after completion
            verification_passed: Whether verification command passed
            verification_duration_ms: Time spent on verification
            error_message: Error message if failed
        """
        self.completed_at = datetime.now()
        self.status = status
        self.duration_seconds = (self.completed_at - self.started_at).total_seconds()
        if context_usage is not None:
            self.context_usage_after = context_usage
        if verification_passed is not None:
            self.verification_passed = verification_passed
        if verification_duration_ms is not None:
            self.verification_duration_ms = verification_duration_ms
        if error_message is not None:
            self.error_message = error_message

    @property
    def context_delta(self) -> float:
        """Calculate change in context usage during task."""
        return self.context_usage_after - self.context_usage_before

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "task_id": self.task_id,
            "worker_id": self.worker_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": (self.completed_at.isoformat() if self.completed_at else None),
            "status": self.status,
            "duration_seconds": self.duration_seconds,
            "context_usage_before": self.context_usage_before,
            "context_usage_after": self.context_usage_after,
            "context_delta": self.context_delta,
            "retry_count": self.retry_count,
            "verification_passed": self.verification_passed,
            "verification_duration_ms": self.verification_duration_ms,
            "error_message": self.error_message,
        }


@dataclass
class WorkerMetrics:
    """Comprehensive metrics for a single worker instance."""

    worker_id: int
    started_at: datetime = field(default_factory=datetime.now)
    stopped_at: datetime | None = None

    # Task tracking
    tasks_completed: int = 0
    tasks_failed: int = 0
    tasks_skipped: int = 0
    current_task: str | None = None

    # Context tracking
    context_usage: float = 0.0
    peak_context_usage: float = 0.0
    context_resets: int = 0

    # Timing
    total_task_duration_seconds: float = 0.0
    total_idle_seconds: float = 0.0
    last_task_completed_at: datetime | None = None

    # Health
    health_check_failures: int = 0
    last_health_check_at: datetime | None = None
    last_health_check_ok: bool = True

    # Task execution history
    task_history: list[TaskExecutionMetrics] = field(default_factory=list)

    @property
    def total_tasks(self) -> int:
        """Total tasks attempted."""
        return self.tasks_completed + self.tasks_failed + self.tasks_skipped

    @property
    def success_rate(self) -> float:
        """Calculate task success rate (0.0-1.0)."""
        if self.total_tasks == 0:
            return 0.0
        return self.tasks_completed / self.total_tasks

    @property
    def uptime_seconds(self) -> float:
        """Calculate total uptime."""
        end = self.stopped_at or datetime.now()
        return (end - self.started_at).total_seconds()

    @property
    def utilization(self) -> float:
        """Calculate worker utilization (task time / uptime)."""
        if self.uptime_seconds == 0:
            return 0.0
        return self.total_task_duration_seconds / self.uptime_seconds

    @property
    def avg_task_duration(self) -> float:
        """Calculate average task duration."""
        if self.total_tasks == 0:
            return 0.0
        return self.total_task_duration_seconds / self.total_tasks

    def start_task(self, task_id: str, context_usage: float | None = None) -> TaskExecutionMetrics:
        """Record task start and return metrics object.

        Args:
            task_id: Task identifier
            context_usage: Current context usage

        Returns:
            TaskExecutionMetrics for tracking
        """
        self.current_task = task_id

        # Update idle time
        if self.last_task_completed_at:
            idle = (datetime.now() - self.last_task_completed_at).total_seconds()
            self.total_idle_seconds += idle

        metrics = TaskExecutionMetrics(
            task_id=task_id,
            worker_id=self.worker_id,
            started_at=datetime.now(),
            context_usage_before=context_usage or self.context_usage,
        )
        self.task_history.append(metrics)
        return metrics

    def complete_task(
        self,
        task_id: str,
        status: str = "completed",
        context_usage: float | None = None,
        verification_passed: bool | None = None,
        verification_duration_ms: int | None = None,
        error_message: str | None = None,
    ) -> None:
        """Record task completion.

        Args:
            task_id: Task identifier
            status: Final status
            context_usage: Context usage after completion
            verification_passed: Whether verification passed
            verification_duration_ms: Verification duration
            error_message: Error message if failed
        """
        # Find the task metrics
        for metrics in reversed(self.task_history):
            if metrics.task_id == task_id and metrics.status == "running":
                metrics.complete(
                    status=status,
                    context_usage=context_usage,
                    verification_passed=verification_passed,
                    verification_duration_ms=verification_duration_ms,
                    error_message=error_message,
                )
                break

        # Update worker stats
        if status == "completed":
            self.tasks_completed += 1
        elif status == "failed":
            self.tasks_failed += 1
        elif status == "skipped":
            self.tasks_skipped += 1

        # Update timing
        for metrics in reversed(self.task_history):
            if metrics.task_id == task_id and metrics.duration_seconds:
                self.total_task_duration_seconds += metrics.duration_seconds
                break

        self.current_task = None
        self.last_task_completed_at = datetime.now()

        # Update context tracking
        if context_usage is not None:
            self.context_usage = context_usage
            if context_usage > self.peak_context_usage:
                self.peak_context_usage = context_usage

    def record_context_reset(self) -> None:
        """Record a context checkpoint/reset."""
        self.context_resets += 1
        self.context_usage = 0.0

    def record_health_check(self, success: bool) -> None:
        """Record health check result.

        Args:
            success: Whether health check passed
        """
        self.last_health_check_at = datetime.now()
        self.last_health_check_ok = success
        if not success:
            self.health_check_failures += 1

    def stop(self) -> None:
        """Mark worker as stopped."""
        self.stopped_at = datetime.now()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "worker_id": self.worker_id,
            "started_at": self.started_at.isoformat(),
            "stopped_at": self.stopped_at.isoformat() if self.stopped_at else None,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "tasks_skipped": self.tasks_skipped,
            "total_tasks": self.total_tasks,
            "current_task": self.current_task,
            "success_rate": round(self.success_rate, 3),
            "context_usage": round(self.context_usage, 3),
            "peak_context_usage": round(self.peak_context_usage, 3),
            "context_resets": self.context_resets,
            "total_task_duration_seconds": round(self.total_task_duration_seconds, 2),
            "total_idle_seconds": round(self.total_idle_seconds, 2),
            "uptime_seconds": round(self.uptime_seconds, 2),
            "utilization": round(self.utilization, 3),
            "avg_task_duration": round(self.avg_task_duration, 2),
            "health_check_failures": self.health_check_failures,
            "last_health_check_at": (self.last_health_check_at.isoformat() if self.last_health_check_at else None),
            "last_health_check_ok": self.last_health_check_ok,
            "task_history": [t.to_dict() for t in self.task_history],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkerMetrics":
        """Create from dictionary.

        Args:
            data: Dictionary representation

        Returns:
            WorkerMetrics instance
        """
        metrics = cls(
            worker_id=data["worker_id"],
            started_at=datetime.fromisoformat(data["started_at"]),
            tasks_completed=data.get("tasks_completed", 0),
            tasks_failed=data.get("tasks_failed", 0),
            tasks_skipped=data.get("tasks_skipped", 0),
            current_task=data.get("current_task"),
            context_usage=data.get("context_usage", 0.0),
            peak_context_usage=data.get("peak_context_usage", 0.0),
            context_resets=data.get("context_resets", 0),
            total_task_duration_seconds=data.get("total_task_duration_seconds", 0.0),
            total_idle_seconds=data.get("total_idle_seconds", 0.0),
            health_check_failures=data.get("health_check_failures", 0),
            last_health_check_ok=data.get("last_health_check_ok", True),
        )

        if data.get("stopped_at"):
            metrics.stopped_at = datetime.fromisoformat(data["stopped_at"])
        if data.get("last_task_completed_at"):
            metrics.last_task_completed_at = datetime.fromisoformat(data["last_task_completed_at"])
        if data.get("last_health_check_at"):
            metrics.last_health_check_at = datetime.fromisoformat(data["last_health_check_at"])

        return metrics


@dataclass
class LevelMetrics:
    """Aggregated metrics for a level execution."""

    level: int
    started_at: datetime | None = None
    completed_at: datetime | None = None
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    total_duration_seconds: float = 0.0
    worker_count: int = 0

    @property
    def duration_seconds(self) -> float:
        """Calculate level duration."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        elif self.started_at:
            return (datetime.now() - self.started_at).total_seconds()
        return 0.0

    @property
    def success_rate(self) -> float:
        """Calculate success rate for level."""
        attempted = self.completed_tasks + self.failed_tasks
        if attempted == 0:
            return 0.0
        return self.completed_tasks / attempted

    @property
    def is_complete(self) -> bool:
        """Check if level is complete."""
        return self.completed_tasks + self.failed_tasks == self.total_tasks and self.total_tasks > 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "level": self.level,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": (self.completed_at.isoformat() if self.completed_at else None),
            "total_tasks": self.total_tasks,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "success_rate": round(self.success_rate, 3),
            "duration_seconds": round(self.duration_seconds, 2),
            "total_duration_seconds": round(self.total_duration_seconds, 2),
            "worker_count": self.worker_count,
            "is_complete": self.is_complete,
        }


class WorkerMetricsCollector:
    """Collects and aggregates metrics across all workers.

    Provides centralized metrics collection for the orchestrator,
    including real-time statistics and historical data export.
    """

    DEFAULT_METRICS_DIR = Path(".zerg/metrics")

    def __init__(
        self,
        feature: str,
        metrics_dir: Path | None = None,
    ) -> None:
        """Initialize the metrics collector.

        Args:
            feature: Feature name being executed
            metrics_dir: Directory for metrics output
        """
        self.feature = feature
        self.metrics_dir = metrics_dir or self.DEFAULT_METRICS_DIR
        self.execution_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.started_at = datetime.now()
        self.completed_at: datetime | None = None

        # Worker metrics
        self._workers: dict[int, WorkerMetrics] = {}

        # Level metrics
        self._levels: dict[int, LevelMetrics] = {}

        # Ensure directory exists
        self.metrics_dir.mkdir(parents=True, exist_ok=True)

    def register_worker(self, worker_id: int) -> WorkerMetrics:
        """Register a new worker and return its metrics.

        Args:
            worker_id: Worker identifier

        Returns:
            WorkerMetrics for the worker
        """
        if worker_id not in self._workers:
            self._workers[worker_id] = WorkerMetrics(worker_id=worker_id)
        return self._workers[worker_id]

    def get_worker(self, worker_id: int) -> WorkerMetrics | None:
        """Get metrics for a specific worker.

        Args:
            worker_id: Worker identifier

        Returns:
            WorkerMetrics or None if not found
        """
        return self._workers.get(worker_id)

    def start_level(self, level: int, total_tasks: int, worker_count: int) -> None:
        """Record level start.

        Args:
            level: Level number
            total_tasks: Total tasks in level
            worker_count: Number of workers for this level
        """
        self._levels[level] = LevelMetrics(
            level=level,
            started_at=datetime.now(),
            total_tasks=total_tasks,
            worker_count=worker_count,
        )

    def complete_level(self, level: int) -> None:
        """Record level completion.

        Args:
            level: Level number
        """
        if level in self._levels:
            lvl = self._levels[level]
            lvl.completed_at = datetime.now()

            # Calculate aggregate task duration
            for worker in self._workers.values():
                for task in worker.task_history:
                    if task.duration_seconds:
                        lvl.total_duration_seconds += task.duration_seconds

    def record_task_completion(self, level: int, success: bool) -> None:
        """Record task completion at level.

        Args:
            level: Level number
            success: Whether task succeeded
        """
        if level not in self._levels:
            self._levels[level] = LevelMetrics(level=level)

        if success:
            self._levels[level].completed_tasks += 1
        else:
            self._levels[level].failed_tasks += 1

    def get_summary(self) -> dict[str, Any]:
        """Get execution summary across all workers.

        Returns:
            Summary dictionary with aggregate statistics
        """
        # Aggregate worker stats
        total_tasks = sum(w.total_tasks for w in self._workers.values())
        completed_tasks = sum(w.tasks_completed for w in self._workers.values())
        failed_tasks = sum(w.tasks_failed for w in self._workers.values())
        total_task_duration = sum(w.total_task_duration_seconds for w in self._workers.values())
        total_idle = sum(w.total_idle_seconds for w in self._workers.values())

        # Calculate averages
        worker_count = len(self._workers)
        avg_utilization = sum(w.utilization for w in self._workers.values()) / worker_count if worker_count > 0 else 0.0
        avg_context = sum(w.context_usage for w in self._workers.values()) / worker_count if worker_count > 0 else 0.0
        peak_context = max(w.peak_context_usage for w in self._workers.values()) if worker_count > 0 else 0.0

        # Calculate overall duration
        duration = ((self.completed_at or datetime.now()) - self.started_at).total_seconds()

        return {
            "execution_id": self.execution_id,
            "feature": self.feature,
            "started_at": self.started_at.isoformat(),
            "completed_at": (self.completed_at.isoformat() if self.completed_at else None),
            "duration_seconds": round(duration, 2),
            "worker_count": worker_count,
            "levels_completed": sum(1 for lvl in self._levels.values() if lvl.is_complete),
            "total_levels": len(self._levels),
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "failed_tasks": failed_tasks,
            "success_rate": (round(completed_tasks / total_tasks, 3) if total_tasks > 0 else 0.0),
            "total_task_duration_seconds": round(total_task_duration, 2),
            "total_idle_seconds": round(total_idle, 2),
            "avg_worker_utilization": round(avg_utilization, 3),
            "avg_context_usage": round(avg_context, 3),
            "peak_context_usage": round(peak_context, 3),
            "parallel_efficiency": (
                round(total_task_duration / (duration * worker_count), 3) if duration > 0 and worker_count > 0 else 0.0
            ),
        }

    def get_worker_summary(self, worker_id: int) -> dict[str, Any] | None:
        """Get summary for a specific worker.

        Args:
            worker_id: Worker identifier

        Returns:
            Worker summary or None
        """
        worker = self._workers.get(worker_id)
        if worker:
            return worker.to_dict()
        return None

    def get_level_summary(self, level: int) -> dict[str, Any] | None:
        """Get summary for a specific level.

        Args:
            level: Level number

        Returns:
            Level summary or None
        """
        lvl = self._levels.get(level)
        if lvl:
            return lvl.to_dict()
        return None

    def complete(self) -> None:
        """Mark the execution as complete."""
        self.completed_at = datetime.now()
        for worker in self._workers.values():
            if not worker.stopped_at:
                worker.stop()

    def export(self, path: Path | None = None) -> Path:
        """Export all metrics to JSON.

        Args:
            path: Output path (defaults to metrics_dir/metrics_{id}.json)

        Returns:
            Path to exported file
        """
        path = path or self.metrics_dir / f"metrics_{self.execution_id}.json"

        data = {
            "summary": self.get_summary(),
            "workers": {str(wid): w.to_dict() for wid, w in self._workers.items()},
            "levels": {str(lvl): lm.to_dict() for lvl, lm in self._levels.items()},
        }

        path.write_text(json.dumps(data, indent=2))
        return path

    def export_summary(self, path: Path | None = None) -> Path:
        """Export summary only (smaller file).

        Args:
            path: Output path

        Returns:
            Path to exported file
        """
        path = path or self.metrics_dir / f"summary_{self.execution_id}.json"
        path.write_text(json.dumps(self.get_summary(), indent=2))
        return path


def estimate_execution_cost(
    total_tokens: int,
    input_ratio: float = 0.4,
    model: str = "sonnet",
) -> float:
    """Estimate API cost based on token usage.

    Args:
        total_tokens: Total tokens used
        input_ratio: Ratio of input to output tokens (default 40% input)
        model: Model name for pricing

    Returns:
        Estimated cost in USD
    """
    # Pricing per 1M tokens (as of 2024)
    pricing = {
        "sonnet": {"input": 3.0, "output": 15.0},
        "opus": {"input": 15.0, "output": 75.0},
        "haiku": {"input": 0.25, "output": 1.25},
    }

    rates = pricing.get(model, pricing["sonnet"])
    input_tokens = int(total_tokens * input_ratio)
    output_tokens = total_tokens - input_tokens

    input_cost = (input_tokens / 1_000_000) * rates["input"]
    output_cost = (output_tokens / 1_000_000) * rates["output"]

    return round(input_cost + output_cost, 4)
