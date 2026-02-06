"""ZERG launcher data types.

Pure data types extracted from launcher.py: LauncherType enum, LauncherConfig,
SpawnResult, and WorkerHandle dataclasses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

from zerg.constants import WorkerStatus

__all__ = [
    "LauncherType",
    "LauncherConfig",
    "SpawnResult",
    "WorkerHandle",
]


class LauncherType(Enum):
    """Worker launcher backend types."""

    SUBPROCESS = "subprocess"
    CONTAINER = "container"


@dataclass
class LauncherConfig:
    """Configuration for worker launcher."""

    launcher_type: LauncherType = LauncherType.SUBPROCESS
    timeout_seconds: int = 3600
    env_vars: dict[str, str] = field(default_factory=dict)
    working_dir: Path | None = None
    log_dir: Path | None = None


@dataclass
class SpawnResult:
    """Result of spawning a worker."""

    success: bool
    worker_id: int
    handle: WorkerHandle | None = None
    error: str | None = None


@dataclass
class WorkerHandle:
    """Handle to a running worker process."""

    worker_id: int
    pid: int | None = None
    container_id: str | None = None
    status: WorkerStatus = WorkerStatus.INITIALIZING
    started_at: datetime = field(default_factory=datetime.now)
    exit_code: int | None = None
    # FR-1: Track last health check for cooldown caching
    health_check_at: datetime | None = None

    def is_alive(self) -> bool:
        """Check if worker is still running."""
        return self.status in (
            WorkerStatus.INITIALIZING,
            WorkerStatus.READY,
            WorkerStatus.RUNNING,
            WorkerStatus.IDLE,
            WorkerStatus.CHECKPOINTING,
        )
