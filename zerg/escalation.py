"""Escalation subsystem for ZERG workers — ambiguous failure reporting."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from zerg.constants import STATE_DIR
from zerg.logging import get_logger

logger = get_logger("escalation")

ESCALATION_FILE = "escalations.json"


@dataclass
class Escalation:
    """Single escalation record from a worker."""

    worker_id: int
    task_id: str
    timestamp: str  # ISO 8601
    category: str  # "ambiguous_spec", "dependency_missing", "verification_unclear"
    message: str
    context: dict[str, Any] = field(default_factory=dict)
    resolved: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> Escalation:
        return cls(
            worker_id=data["worker_id"],
            task_id=data["task_id"],
            timestamp=data.get("timestamp", ""),
            category=data.get("category", "unknown"),
            message=data.get("message", ""),
            context=data.get("context", {}),
            resolved=data.get("resolved", False),
        )


class EscalationWriter:
    """Worker-side escalation writer. Appends to shared escalations file."""

    def __init__(self, worker_id: int, state_dir: str | Path | None = None) -> None:
        self._worker_id = worker_id
        self._state_dir = Path(state_dir) if state_dir else Path(STATE_DIR)
        self._state_dir.mkdir(parents=True, exist_ok=True)

    @property
    def escalation_path(self) -> Path:
        return self._state_dir / ESCALATION_FILE

    def escalate(
        self,
        task_id: str,
        category: str,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> Escalation:
        """Write an escalation to the shared escalations file."""
        esc = Escalation(
            worker_id=self._worker_id,
            task_id=task_id,
            timestamp=datetime.now(UTC).isoformat(),
            category=category,
            message=message,
            context=context or {},
        )

        # Read existing escalations, append, write atomically
        existing = self._read_existing()
        existing.append(esc.to_dict())
        self._atomic_write(existing)

        logger.info(
            "Worker %d escalated task %s: %s",
            self._worker_id,
            task_id,
            category,
        )
        return esc

    def _read_existing(self) -> list[dict]:
        path = self.escalation_path
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text())
            return data.get("escalations", [])
        except (json.JSONDecodeError, OSError):
            return []

    def _atomic_write(self, escalations: list[dict]) -> None:
        target = self.escalation_path
        try:
            fd, tmp_path = tempfile.mkstemp(dir=str(self._state_dir), suffix=".tmp")
            with os.fdopen(fd, "w") as f:
                json.dump({"escalations": escalations}, f, indent=2)
            os.replace(tmp_path, str(target))
        except OSError:
            logger.debug("Failed to write escalation file", exc_info=True)


class EscalationMonitor:
    """Orchestrator-side escalation reader and resolver."""

    def __init__(self, state_dir: str | Path | None = None) -> None:
        self._state_dir = Path(state_dir) if state_dir else Path(STATE_DIR)

    @property
    def escalation_path(self) -> Path:
        return self._state_dir / ESCALATION_FILE

    def read_all(self) -> list[Escalation]:
        """Read all escalations from disk."""
        path = self.escalation_path
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text())
            return [Escalation.from_dict(e) for e in data.get("escalations", [])]
        except (json.JSONDecodeError, OSError):
            return []

    def get_unresolved(self) -> list[Escalation]:
        """Return only unresolved escalations."""
        return [e for e in self.read_all() if not e.resolved]

    def resolve(self, task_id: str, worker_id: int) -> bool:
        """Mark a specific escalation as resolved."""
        all_esc = self.read_all()
        changed = False
        for e in all_esc:
            if e.task_id == task_id and e.worker_id == worker_id and not e.resolved:
                e.resolved = True
                changed = True
        if changed:
            self._write_all(all_esc)
        return changed

    def resolve_all(self) -> int:
        """Resolve all unresolved escalations. Returns count resolved."""
        all_esc = self.read_all()
        count = 0
        for e in all_esc:
            if not e.resolved:
                e.resolved = True
                count += 1
        if count:
            self._write_all(all_esc)
        return count

    def alert_terminal(self, escalation: Escalation) -> None:
        """Print an escalation alert to stderr for terminal visibility."""
        msg = (
            f"\n{'=' * 60}\n"
            f"ESCALATION from Worker {escalation.worker_id}\n"
            f"Task: {escalation.task_id} | Category: {escalation.category}\n"
            f"{escalation.message}\n"
            f"{'=' * 60}\n"
        )
        print(msg, file=sys.stderr, flush=True)

    def _write_all(self, escalations: list[Escalation]) -> None:
        target = self.escalation_path
        try:
            fd, tmp_path = tempfile.mkstemp(dir=str(self._state_dir), suffix=".tmp")
            with os.fdopen(fd, "w") as f:
                json.dump(
                    {"escalations": [e.to_dict() for e in escalations]},
                    f,
                    indent=2,
                )
            os.replace(tmp_path, str(target))
        except OSError:
            logger.debug("Failed to write escalation file", exc_info=True)
