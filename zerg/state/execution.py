"""Execution log — events, pause/resume, and error tracking.

Manages the execution event log, pause/resume state, and global error state.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

from zerg.logging import get_logger
from zerg.types import ExecutionEvent

if TYPE_CHECKING:
    from zerg.state.persistence import PersistenceLayer

logger = get_logger("state.execution")


class ExecutionLog:
    """Execution event log and pause/error state management.

    Appends events to the execution log, manages pause/resume state,
    and tracks global error state. All operations delegate file I/O
    to the PersistenceLayer.
    """

    def __init__(self, persistence: PersistenceLayer) -> None:
        """Initialize execution log.

        Args:
            persistence: PersistenceLayer instance for data access
        """
        self._persistence = persistence

    def append_event(self, event_type: str, data: dict[str, Any] | None = None) -> None:
        """Append an event to the execution log.

        Args:
            event_type: Type of event
            data: Event data
        """
        event: ExecutionEvent = {
            "timestamp": datetime.now().isoformat(),
            "event": event_type,
            "data": data or {},
        }

        with self._persistence.atomic_update():
            if "execution_log" not in self._persistence.state:
                self._persistence.state["execution_log"] = []
            self._persistence.state["execution_log"].append(event)

        logger.debug(f"Event: {event_type}")

    def get_events(self, limit: int | None = None) -> list[ExecutionEvent]:
        """Get execution events.

        Args:
            limit: Maximum number of events to return

        Returns:
            List of events (most recent last)
        """
        with self._persistence.lock:
            events = cast(
                list[ExecutionEvent],
                self._persistence.state.get("execution_log", []),
            )
            if limit:
                return events[-limit:]
            return events.copy()

    def set_paused(self, paused: bool) -> None:
        """Set paused state.

        Args:
            paused: Whether execution is paused
        """
        with self._persistence.atomic_update():
            self._persistence.state["paused"] = paused

    def is_paused(self) -> bool:
        """Check if execution is paused.

        Returns:
            True if paused
        """
        with self._persistence.lock:
            return bool(self._persistence.state.get("paused", False))

    def set_error(self, error: str | None) -> None:
        """Set error state.

        Args:
            error: Error message or None to clear
        """
        with self._persistence.atomic_update():
            self._persistence.state["error"] = error

    def get_error(self) -> str | None:
        """Get current error.

        Returns:
            Error message or None
        """
        with self._persistence.lock:
            return cast(str | None, self._persistence.state.get("error"))
