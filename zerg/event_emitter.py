"""Event emitter for ZERG live streaming.

This module provides the EventEmitter class for JSONL-based event
streaming between orchestrator and status monitors.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from zerg.logging import get_logger

logger = get_logger(__name__)

EventCallback = Callable[[str, dict[str, Any]], None]


class EventEmitter:
    """JSONL file-based event emitter for live streaming.

    Events are written to .zerg/state/{feature}-events.jsonl and can
    be subscribed to for real-time updates.
    """

    def __init__(self, feature: str, state_dir: Path | str | None = None) -> None:
        """Initialize event emitter.

        Args:
            feature: Feature name for event file naming
            state_dir: Directory for event files (default: .zerg/state)
        """
        self._feature = feature
        self._state_dir = Path(state_dir) if state_dir else Path(".zerg/state")
        self._event_file = self._state_dir / f"{feature}-events.jsonl"
        self._subscribers: list[EventCallback] = []
        self._lock = threading.Lock()
        self._running = False
        self._watch_thread: threading.Thread | None = None

        # Ensure state directory exists
        self._state_dir.mkdir(parents=True, exist_ok=True)

    @property
    def event_file(self) -> Path:
        """Get the event file path."""
        return self._event_file

    def emit(self, event_type: str, data: dict[str, Any] | None = None) -> None:
        """Emit an event to the JSONL file.

        Args:
            event_type: Type of event (e.g., 'task_claim', 'level_complete')
            data: Event data dictionary
        """
        event = {
            "timestamp": datetime.now(UTC).isoformat(),
            "type": event_type,
            "feature": self._feature,
            "data": data or {},
        }

        with self._lock:
            try:
                with open(self._event_file, "a") as f:
                    f.write(json.dumps(event) + "\n")
                    f.flush()
                logger.debug(f"Emitted event: {event_type}")
            except OSError as e:
                logger.error(f"Failed to write event: {e}")

        # Notify in-process subscribers
        for callback in self._subscribers:
            try:
                callback(event_type, event.get("data", {}))
            except Exception as e:
                logger.warning(f"Subscriber callback error: {e}")

    def subscribe(self, callback: EventCallback) -> None:
        """Subscribe to events with a callback.

        Args:
            callback: Function called with (event_type, data) for each event
        """
        self._subscribers.append(callback)
        logger.debug(f"Added subscriber, total: {len(self._subscribers)}")

    def unsubscribe(self, callback: EventCallback) -> None:
        """Unsubscribe a callback from events.

        Args:
            callback: Previously registered callback function
        """
        if callback in self._subscribers:
            self._subscribers.remove(callback)
            logger.debug(f"Removed subscriber, total: {len(self._subscribers)}")

    def start_watching(self, callback: EventCallback) -> None:
        """Start watching the event file for new events.

        This is useful for status monitors that need to read events
        from a separate process.

        Args:
            callback: Function called with (event_type, data) for each new event
        """
        if self._running:
            logger.warning("Already watching events")
            return

        self._running = True
        self._watch_thread = threading.Thread(target=self._watch_loop, args=(callback,), daemon=True)
        self._watch_thread.start()
        logger.info(f"Started watching {self._event_file}")

    def stop_watching(self) -> None:
        """Stop watching the event file."""
        self._running = False
        if self._watch_thread:
            self._watch_thread.join(timeout=2.0)
            self._watch_thread = None
        logger.info("Stopped watching events")

    def _watch_loop(self, callback: EventCallback) -> None:
        """Internal loop for watching event file.

        Args:
            callback: Function to call for new events
        """
        last_position = 0

        # Start from end of file if it exists
        if self._event_file.exists():
            last_position = self._event_file.stat().st_size

        while self._running:
            try:
                if not self._event_file.exists():
                    time.sleep(0.5)
                    continue

                current_size = self._event_file.stat().st_size
                if current_size > last_position:
                    with open(self._event_file) as f:
                        f.seek(last_position)
                        for line in f:
                            line = line.strip()
                            if line:
                                try:
                                    event = json.loads(line)
                                    callback(event.get("type", "unknown"), event.get("data", {}))
                                except json.JSONDecodeError as e:
                                    logger.warning(f"Malformed event line: {e}")
                        last_position = f.tell()

                time.sleep(0.1)  # Poll interval

            except OSError as e:
                logger.error(f"Error watching events: {e}")
                time.sleep(1.0)

    def get_events(self, since: datetime | None = None) -> list[dict[str, Any]]:
        """Get all events, optionally filtered by timestamp.

        Args:
            since: Only return events after this timestamp

        Returns:
            List of event dictionaries
        """
        events = []

        if not self._event_file.exists():
            return events

        with open(self._event_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    if since:
                        event_time = datetime.fromisoformat(event.get("timestamp", ""))
                        if event_time <= since:
                            continue
                    events.append(event)
                except (json.JSONDecodeError, ValueError):
                    continue

        return events

    def clear(self) -> None:
        """Clear all events from the file."""
        with self._lock:
            if self._event_file.exists():
                self._event_file.unlink()
                logger.info(f"Cleared events: {self._event_file}")

    def cleanup(self) -> None:
        """Clean up resources and stop watching."""
        self.stop_watching()
        self._subscribers.clear()
