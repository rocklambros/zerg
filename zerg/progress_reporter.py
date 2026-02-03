"""Structured progress reporting for ZERG workers."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from zerg.constants import STATE_DIR
from zerg.logging import get_logger

logger = get_logger("progress")


@dataclass
class TierProgress:
    """Progress of a single verification tier."""

    tier: int
    name: str
    success: bool
    retry: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class WorkerProgress:
    """Structured progress for a single worker."""

    worker_id: int
    tasks_completed: int = 0
    tasks_total: int = 0
    current_task: str | None = None
    current_step: str = "idle"
    tier_results: list[TierProgress] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "tasks_completed": self.tasks_completed,
            "tasks_total": self.tasks_total,
            "current_task": self.current_task,
            "current_step": self.current_step,
            "tier_results": [t.to_dict() for t in self.tier_results],
        }

    @classmethod
    def from_dict(cls, data: dict) -> WorkerProgress:
        tiers = [TierProgress(**t) for t in data.get("tier_results", [])]
        return cls(
            worker_id=data["worker_id"],
            tasks_completed=data.get("tasks_completed", 0),
            tasks_total=data.get("tasks_total", 0),
            current_task=data.get("current_task"),
            current_step=data.get("current_step", "idle"),
            tier_results=tiers,
        )


class ProgressReporter:
    """Worker-side progress writer and orchestrator-side reader."""

    def __init__(self, worker_id: int, state_dir: str | Path | None = None) -> None:
        self._worker_id = worker_id
        self._state_dir = Path(state_dir) if state_dir else Path(STATE_DIR)
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self._progress = WorkerProgress(worker_id=worker_id)

    @property
    def progress_path(self) -> Path:
        return self._state_dir / f"progress-{self._worker_id}.json"

    @property
    def progress(self) -> WorkerProgress:
        return self._progress

    def update(
        self,
        current_task: str | None = None,
        current_step: str | None = None,
        tasks_completed: int | None = None,
        tasks_total: int | None = None,
    ) -> None:
        """Update progress fields and write to disk."""
        if current_task is not None:
            self._progress.current_task = current_task
        if current_step is not None:
            self._progress.current_step = current_step
        if tasks_completed is not None:
            self._progress.tasks_completed = tasks_completed
        if tasks_total is not None:
            self._progress.tasks_total = tasks_total
        self._write()

    def add_tier_result(self, tier: int, name: str, success: bool, retry: int = 0) -> None:
        """Record a verification tier result and write."""
        self._progress.tier_results.append(TierProgress(tier=tier, name=name, success=success, retry=retry))
        self._write()

    def clear_tier_results(self) -> None:
        """Clear tier results for a new task."""
        self._progress.tier_results.clear()

    def _write(self) -> None:
        """Write progress file atomically."""
        target = self.progress_path
        try:
            fd, tmp_path = tempfile.mkstemp(dir=str(self._state_dir), suffix=".tmp")
            with os.fdopen(fd, "w") as f:
                json.dump(self._progress.to_dict(), f)
            os.replace(tmp_path, str(target))
        except OSError:
            logger.debug(
                "Failed to write progress for worker %d",
                self._worker_id,
                exc_info=True,
            )

    def cleanup(self) -> None:
        """Remove progress file on clean shutdown."""
        try:
            self.progress_path.unlink(missing_ok=True)
        except OSError:
            pass

    @staticmethod
    def read(worker_id: int, state_dir: str | Path | None = None) -> WorkerProgress | None:
        """Read progress file for a worker (orchestrator-side)."""
        sd = Path(state_dir) if state_dir else Path(STATE_DIR)
        path = sd / f"progress-{worker_id}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            return WorkerProgress.from_dict(data)
        except (json.JSONDecodeError, KeyError, OSError):
            return None

    @staticmethod
    def read_all(state_dir: str | Path | None = None) -> dict[int, WorkerProgress]:
        """Read all progress files (orchestrator-side)."""
        sd = Path(state_dir) if state_dir else Path(STATE_DIR)
        result: dict[int, WorkerProgress] = {}
        if not sd.exists():
            return result
        for path in sd.glob("progress-*.json"):
            try:
                data = json.loads(path.read_text())
                wp = WorkerProgress.from_dict(data)
                result[wp.worker_id] = wp
            except (json.JSONDecodeError, KeyError, OSError):
                continue
        return result
