"""Per-worker token usage tracking with atomic file writes."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from zerg.constants import STATE_DIR

logger = logging.getLogger(__name__)


class TokenTracker:
    """Track token usage per worker with per-task breakdowns.

    Each worker gets a separate JSON file: tokens-{worker_id}.json
    All writes are atomic (tempfile + os.replace).
    """

    def __init__(self, state_dir: str | Path | None = None) -> None:
        self._state_dir = Path(state_dir) if state_dir else Path(STATE_DIR)
        self._state_dir.mkdir(parents=True, exist_ok=True)

    def _worker_path(self, worker_id: str) -> Path:
        return self._state_dir / f"tokens-{worker_id}.json"

    def record_task(
        self,
        worker_id: str,
        task_id: str,
        breakdown: dict,
        mode: str = "estimated",
    ) -> None:
        """Record token usage for a single task.

        Args:
            worker_id: Worker identifier.
            task_id: Task identifier (e.g. "TASK-001").
            breakdown: Dict with keys like command_template, task_context,
                repo_map, security_rules, spec_excerpt — each an int count.
            mode: Counting mode, default "estimated".
        """
        try:
            data = self.read(worker_id)
            if data is None:
                data = {
                    "worker_id": worker_id,
                    "tasks": {},
                    "cumulative": {"total_tokens": 0, "tasks_completed": 0},
                }

            total = sum(int(v) for v in breakdown.values())

            data["tasks"][task_id] = {
                "breakdown": breakdown,
                "total": total,
                "mode": mode,
                "timestamp": datetime.now(UTC).isoformat(),
            }

            # Recompute cumulative from all tasks
            cumulative_total = sum(t.get("total", 0) for t in data["tasks"].values())
            data["cumulative"] = {
                "total_tokens": cumulative_total,
                "tasks_completed": len(data["tasks"]),
            }

            self._atomic_write(worker_id, data)
        except Exception:
            logger.warning(
                "Failed to record task %s for worker %s",
                task_id,
                worker_id,
                exc_info=True,
            )

    def read(self, worker_id: str) -> dict | None:
        """Read a single worker's token data. Returns None if not found."""
        try:
            path = self._worker_path(worker_id)
            if not path.exists():
                return None
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            logger.warning(
                "Failed to read token data for worker %s",
                worker_id,
                exc_info=True,
            )
            return None

    def read_all(self) -> dict:
        """Read all worker token files. Returns {worker_id: data}."""
        result: dict = {}
        try:
            if not self._state_dir.exists():
                return result
            for path in self._state_dir.glob("tokens-*.json"):
                try:
                    data = json.loads(path.read_text())
                    wid = data.get("worker_id", path.stem.split("-", 1)[-1])
                    result[wid] = data
                except (json.JSONDecodeError, OSError):
                    continue
        except Exception:
            logger.warning("Failed to read all token data", exc_info=True)
        return result

    def _atomic_write(self, worker_id: str, data: dict) -> None:
        """Write worker token file atomically via tempfile + os.replace."""
        target = self._worker_path(worker_id)
        fd, tmp_path = tempfile.mkstemp(dir=str(self._state_dir), suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_path, str(target))
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
