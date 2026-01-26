"""ZERG v2 State Persistence - JSON-based state management."""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

import jsonschema


class TaskStatus(Enum):
    """Task execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass
class TaskState:
    """State of a single task."""

    id: str
    status: TaskStatus = TaskStatus.PENDING
    worker_id: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "status": self.status.value,
            "worker_id": self.worker_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TaskState":
        """Deserialize from dictionary."""
        return cls(
            id=data["id"],
            status=TaskStatus(data["status"]),
            worker_id=data.get("worker_id"),
            started_at=(
                datetime.fromisoformat(data["started_at"])
                if data.get("started_at")
                else None
            ),
            completed_at=(
                datetime.fromisoformat(data["completed_at"])
                if data.get("completed_at")
                else None
            ),
            error=data.get("error"),
        )


@dataclass
class WorkerState:
    """State of a worker."""

    id: str
    status: str = "idle"
    current_task: str | None = None
    tasks_completed: int = 0

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "status": self.status,
            "current_task": self.current_task,
            "tasks_completed": self.tasks_completed,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WorkerState":
        """Deserialize from dictionary."""
        return cls(
            id=data["id"],
            status=data.get("status", "idle"),
            current_task=data.get("current_task"),
            tasks_completed=data.get("tasks_completed", 0),
        )


@dataclass
class Checkpoint:
    """Worker checkpoint for context threshold recovery."""

    task_id: str
    worker_id: str
    timestamp: datetime | None
    files_created: list[str]
    files_modified: list[str]
    current_step: int
    state_data: dict

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "task_id": self.task_id,
            "worker_id": self.worker_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "files_created": self.files_created,
            "files_modified": self.files_modified,
            "current_step": self.current_step,
            "state_data": self.state_data,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Checkpoint":
        """Deserialize from dictionary."""
        return cls(
            task_id=data["task_id"],
            worker_id=data["worker_id"],
            timestamp=(
                datetime.fromisoformat(data["timestamp"])
                if data.get("timestamp")
                else None
            ),
            files_created=data.get("files_created", []),
            files_modified=data.get("files_modified", []),
            current_step=data.get("current_step", 0),
            state_data=data.get("state_data", {}),
        )


@dataclass
class ExecutionState:
    """Persistent execution state."""

    feature: str
    started_at: datetime
    current_level: int
    tasks: dict[str, TaskState] = field(default_factory=dict)
    workers: dict[str, WorkerState] = field(default_factory=dict)
    checkpoints: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "feature": self.feature,
            "started_at": self.started_at.isoformat(),
            "current_level": self.current_level,
            "tasks": {k: v.to_dict() for k, v in self.tasks.items()},
            "workers": {k: v.to_dict() for k, v in self.workers.items()},
            "checkpoints": self.checkpoints,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ExecutionState":
        """Deserialize from dictionary."""
        return cls(
            feature=data["feature"],
            started_at=datetime.fromisoformat(data["started_at"]),
            current_level=data["current_level"],
            tasks={k: TaskState.from_dict(v) for k, v in data.get("tasks", {}).items()},
            workers={
                k: WorkerState.from_dict(v) for k, v in data.get("workers", {}).items()
            },
            checkpoints=data.get("checkpoints", []),
        )

    def save(self, path: str = ".zerg/state.json") -> None:
        """Atomically save state to disk."""
        data = self.to_dict()

        # Validate against schema
        schema = load_schema("state.schema.json")
        if schema:
            jsonschema.validate(instance=data, schema=schema)

        # Ensure parent directory exists
        path_obj = Path(path)
        path_obj.parent.mkdir(parents=True, exist_ok=True)

        # Atomic write
        atomic_write(path, json.dumps(data, indent=2))

    @classmethod
    def load(cls, path: str = ".zerg/state.json") -> "ExecutionState | None":
        """Load state from disk, validate against schema."""
        path_obj = Path(path)
        if not path_obj.exists():
            return None

        with open(path_obj) as f:
            data = json.load(f)

        # Validate against schema
        schema = load_schema("state.schema.json")
        if schema:
            jsonschema.validate(instance=data, schema=schema)

        return cls.from_dict(data)

    @classmethod
    def create(cls, feature: str) -> "ExecutionState":
        """Create new execution state for feature."""
        return cls(
            feature=feature,
            started_at=datetime.now(),
            current_level=0,
            tasks={},
            workers={},
            checkpoints=[],
        )


def atomic_write(path: str, data: str) -> None:
    """Write atomically using temp file + rename."""
    temp_path = f"{path}.tmp.{os.getpid()}"
    with open(temp_path, "w") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.rename(temp_path, path)


def load_schema(name: str) -> dict | None:
    """Load JSON schema from schemas directory."""
    schema_path = Path(__file__).parent / "schemas" / name
    if not schema_path.exists():
        return None
    with open(schema_path) as f:
        return json.load(f)
