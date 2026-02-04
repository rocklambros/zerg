"""Unit tests for EventEmitter."""

from __future__ import annotations

import json
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

from zerg.event_emitter import EventEmitter


class TestEventEmitter:
    """Tests for EventEmitter."""

    def test_init_creates_state_dir(self, tmp_path: Path) -> None:
        """EventEmitter should create state directory if it doesn't exist."""
        state_dir = tmp_path / "nonexistent" / "state"
        emitter = EventEmitter("test-feature", state_dir=state_dir)

        assert state_dir.exists()
        assert emitter.event_file == state_dir / "test-feature-events.jsonl"

    def test_emit_creates_event_file(self, tmp_path: Path) -> None:
        """emit() should create event file on first event."""
        emitter = EventEmitter("test-feature", state_dir=tmp_path)

        assert not emitter.event_file.exists()
        emitter.emit("test_event", {"key": "value"})
        assert emitter.event_file.exists()

    def test_emit_writes_valid_jsonl(self, tmp_path: Path) -> None:
        """emit() should write valid JSONL format."""
        emitter = EventEmitter("test-feature", state_dir=tmp_path)

        emitter.emit("task_complete", {"task_id": "TASK-001"})

        with open(emitter.event_file) as f:
            line = f.readline()
            event = json.loads(line)

        assert event["type"] == "task_complete"
        assert event["feature"] == "test-feature"
        assert event["data"]["task_id"] == "TASK-001"
        assert "timestamp" in event

    def test_emit_appends_multiple_events(self, tmp_path: Path) -> None:
        """emit() should append events, not overwrite."""
        emitter = EventEmitter("test-feature", state_dir=tmp_path)

        emitter.emit("event1", {"n": 1})
        emitter.emit("event2", {"n": 2})
        emitter.emit("event3", {"n": 3})

        with open(emitter.event_file) as f:
            lines = f.readlines()

        assert len(lines) == 3
        assert json.loads(lines[0])["type"] == "event1"
        assert json.loads(lines[1])["type"] == "event2"
        assert json.loads(lines[2])["type"] == "event3"

    def test_emit_with_empty_data(self, tmp_path: Path) -> None:
        """emit() should handle empty data dict."""
        emitter = EventEmitter("test-feature", state_dir=tmp_path)

        emitter.emit("simple_event")

        with open(emitter.event_file) as f:
            event = json.loads(f.readline())

        assert event["type"] == "simple_event"
        assert event["data"] == {}

    def test_emit_timestamp_is_utc_iso(self, tmp_path: Path) -> None:
        """emit() should use UTC ISO format timestamp."""
        emitter = EventEmitter("test-feature", state_dir=tmp_path)

        before = datetime.now(UTC)
        emitter.emit("test")
        after = datetime.now(UTC)

        with open(emitter.event_file) as f:
            event = json.loads(f.readline())

        event_time = datetime.fromisoformat(event["timestamp"])
        assert before <= event_time <= after

    def test_subscribe_receives_events(self, tmp_path: Path) -> None:
        """subscribe() callback should receive emitted events."""
        emitter = EventEmitter("test-feature", state_dir=tmp_path)
        received: list[tuple[str, dict]] = []

        def callback(event_type: str, data: dict) -> None:
            received.append((event_type, data))

        emitter.subscribe(callback)
        emitter.emit("event1", {"key": "val1"})
        emitter.emit("event2", {"key": "val2"})

        assert len(received) == 2
        assert received[0] == ("event1", {"key": "val1"})
        assert received[1] == ("event2", {"key": "val2"})

    def test_multiple_subscribers(self, tmp_path: Path) -> None:
        """Multiple subscribers should all receive events."""
        emitter = EventEmitter("test-feature", state_dir=tmp_path)
        received1: list[str] = []
        received2: list[str] = []

        emitter.subscribe(lambda t, d: received1.append(t))
        emitter.subscribe(lambda t, d: received2.append(t))
        emitter.emit("test_event")

        assert received1 == ["test_event"]
        assert received2 == ["test_event"]

    def test_unsubscribe_stops_events(self, tmp_path: Path) -> None:
        """unsubscribe() should stop callback from receiving events."""
        emitter = EventEmitter("test-feature", state_dir=tmp_path)
        received: list[str] = []

        def callback(event_type: str, data: dict) -> None:
            received.append(event_type)

        emitter.subscribe(callback)
        emitter.emit("event1")
        emitter.unsubscribe(callback)
        emitter.emit("event2")

        assert received == ["event1"]

    def test_get_events_returns_all_events(self, tmp_path: Path) -> None:
        """get_events() should return all events."""
        emitter = EventEmitter("test-feature", state_dir=tmp_path)

        emitter.emit("event1", {"n": 1})
        emitter.emit("event2", {"n": 2})
        emitter.emit("event3", {"n": 3})

        events = emitter.get_events()

        assert len(events) == 3
        assert events[0]["type"] == "event1"
        assert events[1]["type"] == "event2"
        assert events[2]["type"] == "event3"

    def test_get_events_with_since_filter(self, tmp_path: Path) -> None:
        """get_events(since=) should filter by timestamp."""
        emitter = EventEmitter("test-feature", state_dir=tmp_path)

        emitter.emit("event1")
        time.sleep(0.01)
        cutoff = datetime.now(UTC)
        time.sleep(0.01)
        emitter.emit("event2")
        emitter.emit("event3")

        events = emitter.get_events(since=cutoff)

        assert len(events) == 2
        assert events[0]["type"] == "event2"
        assert events[1]["type"] == "event3"

    def test_get_events_empty_file(self, tmp_path: Path) -> None:
        """get_events() should return empty list if no events."""
        emitter = EventEmitter("test-feature", state_dir=tmp_path)

        events = emitter.get_events()

        assert events == []

    def test_clear_removes_event_file(self, tmp_path: Path) -> None:
        """clear() should delete the event file."""
        emitter = EventEmitter("test-feature", state_dir=tmp_path)

        emitter.emit("test")
        assert emitter.event_file.exists()

        emitter.clear()
        assert not emitter.event_file.exists()

    def test_clear_handles_missing_file(self, tmp_path: Path) -> None:
        """clear() should handle case when file doesn't exist."""
        emitter = EventEmitter("test-feature", state_dir=tmp_path)

        # Should not raise
        emitter.clear()

    def test_cleanup_stops_watching(self, tmp_path: Path) -> None:
        """cleanup() should stop watching and clear subscribers."""
        emitter = EventEmitter("test-feature", state_dir=tmp_path)
        received: list[str] = []

        emitter.subscribe(lambda t, d: received.append(t))
        emitter.cleanup()

        # Internal subscribers list should be cleared
        assert len(emitter._subscribers) == 0

    def test_emit_thread_safe(self, tmp_path: Path) -> None:
        """emit() should be thread-safe."""
        emitter = EventEmitter("test-feature", state_dir=tmp_path)
        errors: list[Exception] = []

        def emit_events(n: int) -> None:
            try:
                for i in range(10):
                    emitter.emit(f"event_{n}_{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=emit_events, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []

        # All 50 events should be written
        events = emitter.get_events()
        assert len(events) == 50

    def test_subscriber_exception_does_not_break_emit(self, tmp_path: Path) -> None:
        """A failing subscriber should not prevent other subscribers."""
        emitter = EventEmitter("test-feature", state_dir=tmp_path)
        received: list[str] = []

        def failing_callback(event_type: str, data: dict) -> None:
            raise RuntimeError("Subscriber error")

        def working_callback(event_type: str, data: dict) -> None:
            received.append(event_type)

        emitter.subscribe(failing_callback)
        emitter.subscribe(working_callback)

        # Should not raise
        emitter.emit("test")

        # Working callback should still receive event
        assert received == ["test"]
