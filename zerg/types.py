"""ZERG type definitions using TypedDict and dataclass."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, TypedDict

from zerg.constants import GateResult, Level, MergeStatus, WorkerStatus

# ============================================================================
# Task-related types
# ============================================================================


class FileSpec(TypedDict):
    """Files associated with a task."""

    create: list[str]
    modify: list[str]
    read: list[str]


class VerificationSpec(TypedDict):
    """Task verification configuration."""

    command: str
    timeout_seconds: int


class VerificationResult(TypedDict, total=False):
    """Result of a verification command."""

    success: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timestamp: str


class TaskExecution(TypedDict, total=False):
    """Task execution metadata."""

    started_at: str
    completed_at: str
    claimed_at: str
    paused_at: str
    pause_reason: str
    retry_count: int
    error_message: str
    worker_id: int
    duration_ms: int


class Task(TypedDict, total=False):
    """A single task in the task graph."""

    id: str
    title: str
    description: str
    level: int
    dependencies: list[str]
    files: FileSpec
    verification: VerificationSpec
    estimate_minutes: int
    status: str
    critical_path: bool
    assigned_worker: int
    execution: TaskExecution
    context: str


class LevelSpec(TypedDict, total=False):
    """Level specification in task graph."""

    name: str
    tasks: list[str]
    parallel: bool
    estimated_minutes: int
    depends_on_levels: list[int]


class TaskGraph(TypedDict, total=False):
    """Complete task graph for a feature."""

    schema: str
    feature: str
    version: str
    generated: str
    total_tasks: int
    estimated_duration_minutes: int
    max_parallelization: int
    critical_path: list[str]
    critical_path_minutes: int
    tasks: list[Task]
    levels: dict[str, LevelSpec]


# ============================================================================
# Worker-related types
# ============================================================================


@dataclass
class WorkerState:
    """Current state of a worker instance."""

    worker_id: int
    status: WorkerStatus
    current_task: str | None = None
    port: int | None = None
    container_id: str | None = None
    worktree_path: str | None = None
    branch: str | None = None
    health_check_at: datetime | None = None
    started_at: datetime | None = None
    ready_at: datetime | None = None
    last_task_completed_at: datetime | None = None
    tasks_completed: int = 0
    context_usage: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "worker_id": self.worker_id,
            "status": self.status.value,
            "current_task": self.current_task,
            "port": self.port,
            "container_id": self.container_id,
            "worktree_path": self.worktree_path,
            "branch": self.branch,
            "health_check_at": self.health_check_at.isoformat() if self.health_check_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ready_at": self.ready_at.isoformat() if self.ready_at else None,
            "last_task_completed_at": (
                self.last_task_completed_at.isoformat()
                if self.last_task_completed_at
                else None
            ),
            "tasks_completed": self.tasks_completed,
            "context_usage": self.context_usage,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkerState":
        """Create from dictionary."""
        return cls(
            worker_id=data["worker_id"],
            status=WorkerStatus(data["status"]),
            current_task=data.get("current_task"),
            port=data.get("port"),
            container_id=data.get("container_id"),
            worktree_path=data.get("worktree_path"),
            branch=data.get("branch"),
            health_check_at=(
                datetime.fromisoformat(data["health_check_at"])
                if data.get("health_check_at")
                else None
            ),
            started_at=(
                datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None
            ),
            ready_at=(
                datetime.fromisoformat(data["ready_at"]) if data.get("ready_at") else None
            ),
            last_task_completed_at=(
                datetime.fromisoformat(data["last_task_completed_at"])
                if data.get("last_task_completed_at")
                else None
            ),
            tasks_completed=data.get("tasks_completed", 0),
            context_usage=data.get("context_usage", 0.0),
        )


# ============================================================================
# Level-related types
# ============================================================================


@dataclass
class LevelStatus:
    """Status of a single level in execution."""

    level: Level
    name: str
    total_tasks: int
    completed_tasks: int = 0
    failed_tasks: int = 0
    in_progress_tasks: int = 0
    status: str = "pending"
    started_at: datetime | None = None
    completed_at: datetime | None = None
    merge_commit: str | None = None

    @property
    def is_complete(self) -> bool:
        """Check if level is complete (all tasks resolved: completed or failed)."""
        resolved = self.completed_tasks + self.failed_tasks
        return resolved == self.total_tasks

    @property
    def progress_percent(self) -> float:
        """Calculate completion percentage."""
        if self.total_tasks == 0:
            return 100.0
        return (self.completed_tasks / self.total_tasks) * 100

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "level": self.level.value,
            "name": self.name,
            "total_tasks": self.total_tasks,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "in_progress_tasks": self.in_progress_tasks,
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "merge_commit": self.merge_commit,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LevelStatus":
        """Create from dictionary."""
        return cls(
            level=Level(data["level"]),
            name=data["name"],
            total_tasks=data["total_tasks"],
            completed_tasks=data.get("completed_tasks", 0),
            failed_tasks=data.get("failed_tasks", 0),
            in_progress_tasks=data.get("in_progress_tasks", 0),
            status=data.get("status", "pending"),
            started_at=(
                datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None
            ),
            completed_at=(
                datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None
            ),
            merge_commit=data.get("merge_commit"),
        )


# ============================================================================
# Gate-related types
# ============================================================================


class GateConfig(TypedDict, total=False):
    """Quality gate configuration."""

    name: str
    command: str
    timeout: int
    required: bool
    coverage_threshold: int


@dataclass
class GateRunResult:
    """Result of a quality gate execution."""

    gate_name: str
    result: GateResult
    command: str
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = 0
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "gate_name": self.gate_name,
            "result": self.result.value,
            "command": self.command,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp.isoformat(),
        }


# ============================================================================
# Merge-related types
# ============================================================================


@dataclass
class MergeResult:
    """Result of a branch merge operation."""

    source_branch: str
    target_branch: str
    status: MergeStatus
    commit_sha: str | None = None
    conflicting_files: list[str] = field(default_factory=list)
    error_message: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "source_branch": self.source_branch,
            "target_branch": self.target_branch,
            "status": self.status.value,
            "commit_sha": self.commit_sha,
            "conflicting_files": self.conflicting_files,
            "error_message": self.error_message,
            "timestamp": self.timestamp.isoformat(),
        }


# ============================================================================
# Orchestrator state types
# ============================================================================


@dataclass
class LevelCompleteResult:
    """Result of level completion handling."""

    success: bool
    level: int
    merge_commit: str | None = None
    error: str | None = None


class ExecutionEvent(TypedDict, total=False):
    """Event in execution log."""

    timestamp: str
    event: str
    data: dict[str, Any]


@dataclass
class OrchestratorState:
    """Complete orchestrator state."""

    feature: str
    started_at: datetime
    current_level: int = 1
    workers: dict[int, WorkerState] = field(default_factory=dict)
    levels: dict[int, LevelStatus] = field(default_factory=dict)
    execution_log: list[ExecutionEvent] = field(default_factory=list)
    paused: bool = False
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "feature": self.feature,
            "started_at": self.started_at.isoformat(),
            "current_level": self.current_level,
            "workers": {wid: w.to_dict() for wid, w in self.workers.items()},
            "levels": {lid: lvl.to_dict() for lid, lvl in self.levels.items()},
            "execution_log": self.execution_log,
            "paused": self.paused,
            "error": self.error,
        }


# ============================================================================
# Assignment types
# ============================================================================


@dataclass
class WorkerAssignmentEntry:
    """Task assignment to a worker."""

    task_id: str
    worker_id: int
    level: int
    estimated_minutes: int

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "task_id": self.task_id,
            "worker_id": self.worker_id,
            "level": self.level,
            "estimated_minutes": self.estimated_minutes,
        }


@dataclass
class WorkerAssignments:
    """Complete worker assignment mapping."""

    feature: str
    worker_count: int
    assignments: list[WorkerAssignmentEntry] = field(default_factory=list)
    generated_at: datetime = field(default_factory=datetime.now)

    def get_worker_tasks(self, worker_id: int) -> list[str]:
        """Get all task IDs assigned to a worker."""
        return [a.task_id for a in self.assignments if a.worker_id == worker_id]

    def get_task_worker(self, task_id: str) -> int | None:
        """Get worker assigned to a task."""
        for a in self.assignments:
            if a.task_id == task_id:
                return a.worker_id
        return None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "feature": self.feature,
            "worker_count": self.worker_count,
            "assignments": [a.to_dict() for a in self.assignments],
            "generated_at": self.generated_at.isoformat(),
        }


# ============================================================================
# Metrics types
# ============================================================================


@dataclass
class WorkerMetrics:
    """Aggregated metrics for a single worker."""

    worker_id: int
    initialization_ms: int | None = None
    uptime_ms: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0
    total_task_duration_ms: int = 0
    avg_task_duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "worker_id": self.worker_id,
            "initialization_ms": self.initialization_ms,
            "uptime_ms": self.uptime_ms,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "total_task_duration_ms": self.total_task_duration_ms,
            "avg_task_duration_ms": self.avg_task_duration_ms,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkerMetrics":
        """Create from dictionary."""
        return cls(
            worker_id=data["worker_id"],
            initialization_ms=data.get("initialization_ms"),
            uptime_ms=data.get("uptime_ms", 0),
            tasks_completed=data.get("tasks_completed", 0),
            tasks_failed=data.get("tasks_failed", 0),
            total_task_duration_ms=data.get("total_task_duration_ms", 0),
            avg_task_duration_ms=data.get("avg_task_duration_ms", 0.0),
        )


@dataclass
class TaskMetrics:
    """Metrics for a single task execution."""

    task_id: str
    queue_wait_ms: int | None = None
    execution_duration_ms: int | None = None
    verification_duration_ms: int | None = None
    total_duration_ms: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "task_id": self.task_id,
            "queue_wait_ms": self.queue_wait_ms,
            "execution_duration_ms": self.execution_duration_ms,
            "verification_duration_ms": self.verification_duration_ms,
            "total_duration_ms": self.total_duration_ms,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskMetrics":
        """Create from dictionary."""
        return cls(
            task_id=data["task_id"],
            queue_wait_ms=data.get("queue_wait_ms"),
            execution_duration_ms=data.get("execution_duration_ms"),
            verification_duration_ms=data.get("verification_duration_ms"),
            total_duration_ms=data.get("total_duration_ms"),
        )


@dataclass
class LevelMetrics:
    """Metrics for a level execution."""

    level: int
    duration_ms: int | None = None
    task_count: int = 0
    completed_count: int = 0
    failed_count: int = 0
    avg_task_duration_ms: float = 0.0
    p50_duration_ms: int = 0
    p95_duration_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "level": self.level,
            "duration_ms": self.duration_ms,
            "task_count": self.task_count,
            "completed_count": self.completed_count,
            "failed_count": self.failed_count,
            "avg_task_duration_ms": self.avg_task_duration_ms,
            "p50_duration_ms": self.p50_duration_ms,
            "p95_duration_ms": self.p95_duration_ms,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LevelMetrics":
        """Create from dictionary."""
        return cls(
            level=data["level"],
            duration_ms=data.get("duration_ms"),
            task_count=data.get("task_count", 0),
            completed_count=data.get("completed_count", 0),
            failed_count=data.get("failed_count", 0),
            avg_task_duration_ms=data.get("avg_task_duration_ms", 0.0),
            p50_duration_ms=data.get("p50_duration_ms", 0),
            p95_duration_ms=data.get("p95_duration_ms", 0),
        )


@dataclass
class FeatureMetrics:
    """Aggregated metrics for entire feature execution."""

    computed_at: datetime
    total_duration_ms: int | None = None
    workers_used: int = 0
    tasks_total: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0
    levels_completed: int = 0
    worker_metrics: list[WorkerMetrics] = field(default_factory=list)
    level_metrics: list[LevelMetrics] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "computed_at": self.computed_at.isoformat(),
            "total_duration_ms": self.total_duration_ms,
            "workers_used": self.workers_used,
            "tasks_total": self.tasks_total,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "levels_completed": self.levels_completed,
            "worker_metrics": [wm.to_dict() for wm in self.worker_metrics],
            "level_metrics": [lm.to_dict() for lm in self.level_metrics],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FeatureMetrics":
        """Create from dictionary."""
        return cls(
            computed_at=datetime.fromisoformat(data["computed_at"]),
            total_duration_ms=data.get("total_duration_ms"),
            workers_used=data.get("workers_used", 0),
            tasks_total=data.get("tasks_total", 0),
            tasks_completed=data.get("tasks_completed", 0),
            tasks_failed=data.get("tasks_failed", 0),
            levels_completed=data.get("levels_completed", 0),
            worker_metrics=[
                WorkerMetrics.from_dict(wm) for wm in data.get("worker_metrics", [])
            ],
            level_metrics=[
                LevelMetrics.from_dict(lm) for lm in data.get("level_metrics", [])
            ],
        )
