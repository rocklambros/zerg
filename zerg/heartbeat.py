"""Heartbeat-based worker health monitoring for ZERG."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from zerg.constants import STATE_DIR
from zerg.logging import get_logger

logger = get_logger("heartbeat")


@dataclass
class Heartbeat:
    """Single heartbeat record from a worker."""

    worker_id: int
    timestamp: str  # ISO 8601
    task_id: str | None
    step: str  # "implementing", "verifying_tier1", etc.
    progress_pct: int  # 0-100

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> Heartbeat:
        return cls(
            worker_id=data["worker_id"],
            timestamp=data["timestamp"],
            task_id=data.get("task_id"),
            step=data.get("step", "unknown"),
            progress_pct=data.get("progress_pct", 0),
        )

    def is_stale(self, timeout_seconds: int) -> bool:
        """Check if this heartbeat is older than timeout_seconds."""
        try:
            ts = datetime.fromisoformat(self.timestamp)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            return (now - ts).total_seconds() > timeout_seconds
        except (ValueError, TypeError):
            return True


class HeartbeatWriter:
    """Worker-side heartbeat writer. Writes periodic heartbeat JSON files."""

    def __init__(self, worker_id: int, state_dir: str | Path | None = None) -> None:
        self._worker_id = worker_id
        self._state_dir = Path(state_dir) if state_dir else Path(STATE_DIR)
        self._state_dir.mkdir(parents=True, exist_ok=True)

    @property
    def heartbeat_path(self) -> Path:
        return self._state_dir / f"heartbeat-{self._worker_id}.json"

    def write(
        self,
        task_id: str | None = None,
        step: str = "idle",
        progress_pct: int = 0,
    ) -> Heartbeat:
        """Write a heartbeat file atomically (temp+rename)."""
        heartbeat = Heartbeat(
            worker_id=self._worker_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            task_id=task_id,
            step=step,
            progress_pct=max(0, min(100, progress_pct)),
        )

        target = self.heartbeat_path
        try:
            fd, tmp_path = tempfile.mkstemp(
                dir=str(self._state_dir), suffix=".tmp"
            )
            with os.fdopen(fd, "w") as f:
                json.dump(heartbeat.to_dict(), f)
            os.replace(tmp_path, str(target))
        except OSError:
            logger.debug(
                "Failed to write heartbeat for worker %d", self._worker_id,
                exc_info=True,
            )
        return heartbeat

    def cleanup(self) -> None:
        """Remove heartbeat file on clean shutdown."""
        try:
            self.heartbeat_path.unlink(missing_ok=True)
        except OSError:
            pass


class HeartbeatMonitor:
    """Orchestrator-side heartbeat reader. Detects stalled workers."""

    def __init__(self, state_dir: str | Path | None = None) -> None:
        self._state_dir = Path(state_dir) if state_dir else Path(STATE_DIR)

    def read(self, worker_id: int) -> Heartbeat | None:
        """Read heartbeat file for a given worker."""
        path = self._state_dir / f"heartbeat-{worker_id}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            return Heartbeat.from_dict(data)
        except (json.JSONDecodeError, KeyError, OSError):
            logger.debug(
                "Failed to read heartbeat for worker %d", worker_id,
                exc_info=True,
            )
            return None

    def read_all(self) -> dict[int, Heartbeat]:
        """Read all heartbeat files in the state directory."""
        result: dict[int, Heartbeat] = {}
        if not self._state_dir.exists():
            return result
        for path in self._state_dir.glob("heartbeat-*.json"):
            try:
                data = json.loads(path.read_text())
                hb = Heartbeat.from_dict(data)
                result[hb.worker_id] = hb
            except (json.JSONDecodeError, KeyError, OSError):
                continue
        return result

    def check_stale(
        self, worker_id: int, timeout_seconds: int
    ) -> bool:
        """Return True if worker's heartbeat is stale or missing."""
        hb = self.read(worker_id)
        if hb is None:
            return True
        return hb.is_stale(timeout_seconds)

    def get_stalled_workers(
        self, worker_ids: list[int], timeout_seconds: int
    ) -> list[int]:
        """Return worker IDs whose heartbeats are stale."""
        stalled = []
        for wid in worker_ids:
            if self.check_stale(wid, timeout_seconds):
                stalled.append(wid)
        return stalled
