"""Tests for ZERG state management level and event tracking.

Covers:
- Level status transitions (set_level_status)
- Event retrieval with limit filtering (get_events)
- Event appending and structure (append_event)
- Level completion timestamp tracking
- Event history behavior
"""

import time
from datetime import datetime
from pathlib import Path

from zerg.state import StateManager


class TestSetLevelStatusTransitions:
    """Tests for set_level_status state transitions."""

    def test_set_level_status_basic(self, tmp_path: Path) -> None:
        """Test basic level status setting."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_level_status(1, "pending")

        status = manager.get_level_status(1)
        assert status is not None
        assert status["status"] == "pending"

    def test_set_level_status_updates_updated_at(self, tmp_path: Path) -> None:
        """Test that setting status always updates updated_at timestamp."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        before = datetime.now().isoformat()
        manager.set_level_status(1, "running")
        after = datetime.now().isoformat()

        status = manager.get_level_status(1)
        assert "updated_at" in status
        assert before <= status["updated_at"] <= after

    def test_level_status_transition_pending_to_running(self, tmp_path: Path) -> None:
        """Test transition from pending to running status."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_level_status(1, "pending")
        manager.set_level_status(1, "running")

        status = manager.get_level_status(1)
        assert status["status"] == "running"

    def test_level_status_transition_running_to_complete(self, tmp_path: Path) -> None:
        """Test transition from running to complete status."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_level_status(1, "running")
        manager.set_level_status(1, "complete")

        status = manager.get_level_status(1)
        assert status["status"] == "complete"

    def test_level_status_transition_to_failed(self, tmp_path: Path) -> None:
        """Test transition to failed status."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_level_status(1, "running")
        manager.set_level_status(1, "failed")

        status = manager.get_level_status(1)
        assert status["status"] == "failed"

    def test_level_status_full_lifecycle(self, tmp_path: Path) -> None:
        """Test full level status lifecycle: pending -> running -> complete."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        statuses = ["pending", "running", "complete"]
        for expected_status in statuses:
            manager.set_level_status(1, expected_status)
            status = manager.get_level_status(1)
            assert status["status"] == expected_status

    def test_level_status_with_merge_commit(self, tmp_path: Path) -> None:
        """Test setting level status with merge commit SHA."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_level_status(1, "complete", merge_commit="abc123def456")

        status = manager.get_level_status(1)
        assert status["merge_commit"] == "abc123def456"

    def test_level_status_merge_commit_optional(self, tmp_path: Path) -> None:
        """Test that merge_commit is optional and not set by default."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_level_status(1, "complete")

        status = manager.get_level_status(1)
        assert "merge_commit" not in status

    def test_multiple_levels_independent_status(self, tmp_path: Path) -> None:
        """Test that multiple levels maintain independent status."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_level_status(1, "complete")
        manager.set_level_status(2, "running")
        manager.set_level_status(3, "pending")

        assert manager.get_level_status(1)["status"] == "complete"
        assert manager.get_level_status(2)["status"] == "running"
        assert manager.get_level_status(3)["status"] == "pending"

    def test_get_level_status_nonexistent(self, tmp_path: Path) -> None:
        """Test getting status for nonexistent level returns None."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        status = manager.get_level_status(999)

        assert status is None


class TestGetEventsWithTypeFilter:
    """Tests for get_events with event type considerations.

    Note: The current implementation does not support type filtering,
    but these tests verify the event structure and type field presence.
    """

    def test_events_have_event_type_field(self, tmp_path: Path) -> None:
        """Test that all events have an event type field."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.append_event("task_started", {"task_id": "TASK-001"})
        manager.append_event("task_complete", {"task_id": "TASK-001"})

        events = manager.get_events()
        for event in events:
            assert "event" in event

    def test_events_preserve_event_type(self, tmp_path: Path) -> None:
        """Test that event types are preserved correctly."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        event_types = ["level_started", "task_claimed", "task_complete", "level_complete"]
        for event_type in event_types:
            manager.append_event(event_type, {"test": True})

        events = manager.get_events()
        retrieved_types = [e["event"] for e in events]
        assert retrieved_types == event_types

    def test_events_can_be_filtered_manually_by_type(self, tmp_path: Path) -> None:
        """Test that events can be manually filtered by type."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.append_event("task_started", {"task_id": "TASK-001"})
        manager.append_event("task_complete", {"task_id": "TASK-001"})
        manager.append_event("task_started", {"task_id": "TASK-002"})
        manager.append_event("level_complete", {"level": 1})

        events = manager.get_events()
        task_started_events = [e for e in events if e["event"] == "task_started"]

        assert len(task_started_events) == 2

    def test_different_event_types_coexist(self, tmp_path: Path) -> None:
        """Test multiple different event types in same log."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        types_to_add = [
            "worker_started",
            "task_claimed",
            "task_started",
            "task_complete",
            "task_failed",
            "level_started",
            "level_complete",
        ]
        for event_type in types_to_add:
            manager.append_event(event_type, {})

        events = manager.get_events()
        assert len(events) == len(types_to_add)


class TestGetEventsWithTimeRangeFilter:
    """Tests for get_events with timestamp considerations.

    Note: The current implementation does not support time range filtering,
    but these tests verify timestamp presence and ordering.
    """

    def test_events_have_timestamp(self, tmp_path: Path) -> None:
        """Test that all events have a timestamp field."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.append_event("test_event", {"data": "value"})

        events = manager.get_events()
        assert len(events) == 1
        assert "timestamp" in events[0]

    def test_events_timestamps_are_iso_format(self, tmp_path: Path) -> None:
        """Test that event timestamps are in ISO format."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.append_event("test_event", {})

        events = manager.get_events()
        timestamp = events[0]["timestamp"]
        # Should parse without error
        parsed = datetime.fromisoformat(timestamp)
        assert isinstance(parsed, datetime)

    def test_events_timestamps_are_chronological(self, tmp_path: Path) -> None:
        """Test that events are stored in chronological order."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        for i in range(5):
            manager.append_event(f"event_{i}", {"index": i})
            time.sleep(0.01)  # Small delay to ensure different timestamps

        events = manager.get_events()
        timestamps = [e["timestamp"] for e in events]

        # Timestamps should be in ascending order
        assert timestamps == sorted(timestamps)

    def test_events_can_be_filtered_manually_by_time(self, tmp_path: Path) -> None:
        """Test that events can be manually filtered by timestamp."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        # Add events with small delays
        manager.append_event("early_event", {})
        time.sleep(0.05)
        cutoff = datetime.now().isoformat()
        time.sleep(0.05)
        manager.append_event("late_event", {})

        events = manager.get_events()
        late_events = [e for e in events if e["timestamp"] > cutoff]

        assert len(late_events) == 1
        assert late_events[0]["event"] == "late_event"


class TestEventHistoryTruncation:
    """Tests for event history behavior (max events handling).

    Note: The current implementation does not truncate event history automatically.
    These tests document the current behavior and test the limit parameter.
    """

    def test_get_events_no_limit_returns_all(self, tmp_path: Path) -> None:
        """Test that get_events without limit returns all events."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        for i in range(100):
            manager.append_event(f"event_{i}", {"index": i})

        events = manager.get_events()
        assert len(events) == 100

    def test_get_events_with_limit(self, tmp_path: Path) -> None:
        """Test get_events respects limit parameter."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        for i in range(50):
            manager.append_event(f"event_{i}", {"index": i})

        events = manager.get_events(limit=10)
        assert len(events) == 10

    def test_get_events_limit_returns_most_recent(self, tmp_path: Path) -> None:
        """Test that limit returns the most recent events."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        for i in range(20):
            manager.append_event(f"event_{i}", {"index": i})

        events = manager.get_events(limit=5)

        # Should return events 15-19 (last 5)
        indices = [e["data"]["index"] for e in events]
        assert indices == [15, 16, 17, 18, 19]

    def test_get_events_limit_larger_than_total(self, tmp_path: Path) -> None:
        """Test limit larger than total events returns all events."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        for i in range(5):
            manager.append_event(f"event_{i}", {"index": i})

        events = manager.get_events(limit=100)
        assert len(events) == 5

    def test_get_events_limit_zero_treated_as_no_limit(self, tmp_path: Path) -> None:
        """Test that limit=0 is treated as no limit (falsy value)."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        for i in range(10):
            manager.append_event(f"event_{i}", {"index": i})

        # limit=0 is falsy, so should return all events
        events = manager.get_events(limit=0)
        assert len(events) == 10

    def test_get_events_limit_one(self, tmp_path: Path) -> None:
        """Test limit=1 returns only the most recent event."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.append_event("first", {"order": 1})
        manager.append_event("second", {"order": 2})
        manager.append_event("third", {"order": 3})

        events = manager.get_events(limit=1)
        assert len(events) == 1
        assert events[0]["event"] == "third"

    def test_large_event_log_performance(self, tmp_path: Path) -> None:
        """Test that large event logs are handled without issues."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        # Add many events
        for i in range(500):
            manager.append_event(f"event_{i}", {"index": i})

        # Should return all without error
        events = manager.get_events()
        assert len(events) == 500

        # Limited query should be fast
        limited = manager.get_events(limit=10)
        assert len(limited) == 10


class TestLevelCompletionTimestampTracking:
    """Tests for level completion timestamp tracking."""

    def test_running_status_sets_started_at(self, tmp_path: Path) -> None:
        """Test that 'running' status sets started_at timestamp."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        before = datetime.now().isoformat()
        manager.set_level_status(1, "running")
        after = datetime.now().isoformat()

        status = manager.get_level_status(1)
        assert "started_at" in status
        assert before <= status["started_at"] <= after

    def test_complete_status_sets_completed_at(self, tmp_path: Path) -> None:
        """Test that 'complete' status sets completed_at timestamp."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        before = datetime.now().isoformat()
        manager.set_level_status(1, "complete")
        after = datetime.now().isoformat()

        status = manager.get_level_status(1)
        assert "completed_at" in status
        assert before <= status["completed_at"] <= after

    def test_running_then_complete_preserves_started_at(self, tmp_path: Path) -> None:
        """Test that started_at is preserved when transitioning to complete."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_level_status(1, "running")
        started_at = manager.get_level_status(1)["started_at"]

        time.sleep(0.01)  # Small delay
        manager.set_level_status(1, "complete")

        status = manager.get_level_status(1)
        assert status["started_at"] == started_at
        assert "completed_at" in status
        assert status["completed_at"] > status["started_at"]

    def test_pending_status_no_special_timestamps(self, tmp_path: Path) -> None:
        """Test that 'pending' status does not set special timestamps."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_level_status(1, "pending")

        status = manager.get_level_status(1)
        assert "started_at" not in status
        assert "completed_at" not in status
        assert "updated_at" in status  # updated_at is always set

    def test_failed_status_no_completed_at(self, tmp_path: Path) -> None:
        """Test that 'failed' status does not set completed_at."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_level_status(1, "running")
        manager.set_level_status(1, "failed")

        status = manager.get_level_status(1)
        assert "started_at" in status  # From running
        assert "completed_at" not in status

    def test_multiple_levels_independent_timestamps(self, tmp_path: Path) -> None:
        """Test that multiple levels have independent timestamps."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_level_status(1, "running")
        level1_started = manager.get_level_status(1)["started_at"]

        time.sleep(0.01)
        manager.set_level_status(2, "running")
        level2_started = manager.get_level_status(2)["started_at"]

        assert level1_started < level2_started

    def test_rerunning_level_updates_started_at(self, tmp_path: Path) -> None:
        """Test that rerunning a level updates started_at timestamp."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_level_status(1, "running")
        first_started = manager.get_level_status(1)["started_at"]

        time.sleep(0.01)
        manager.set_level_status(1, "failed")

        time.sleep(0.01)
        manager.set_level_status(1, "running")  # Rerun
        second_started = manager.get_level_status(1)["started_at"]

        assert second_started > first_started

    def test_timestamp_persistence(self, tmp_path: Path) -> None:
        """Test that timestamps persist across manager instances."""
        manager1 = StateManager("test-feature", state_dir=tmp_path)
        manager1.load()

        manager1.set_level_status(1, "running")
        manager1.set_level_status(1, "complete")

        # Load with new manager
        manager2 = StateManager("test-feature", state_dir=tmp_path)
        manager2.load()

        status = manager2.get_level_status(1)
        assert "started_at" in status
        assert "completed_at" in status
        assert status["started_at"] < status["completed_at"]


class TestEventDataStructure:
    """Tests for event data structure and content."""

    def test_event_has_required_fields(self, tmp_path: Path) -> None:
        """Test that events have all required fields."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.append_event("test_event", {"key": "value"})

        events = manager.get_events()
        event = events[0]

        assert "timestamp" in event
        assert "event" in event
        assert "data" in event

    def test_event_data_is_preserved(self, tmp_path: Path) -> None:
        """Test that event data is preserved correctly."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        data = {"task_id": "TASK-001", "worker_id": 0, "level": 1}
        manager.append_event("task_complete", data)

        events = manager.get_events()
        assert events[0]["data"] == data

    def test_event_empty_data(self, tmp_path: Path) -> None:
        """Test event with None data uses empty dict."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.append_event("test_event", None)

        events = manager.get_events()
        assert events[0]["data"] == {}

    def test_event_complex_data(self, tmp_path: Path) -> None:
        """Test event with complex nested data."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        data = {
            "task_id": "TASK-001",
            "files": ["src/main.py", "tests/test_main.py"],
            "metrics": {"duration_ms": 1500, "lines_changed": 42},
        }
        manager.append_event("task_complete", data)

        events = manager.get_events()
        assert events[0]["data"]["files"] == ["src/main.py", "tests/test_main.py"]
        assert events[0]["data"]["metrics"]["duration_ms"] == 1500

    def test_get_events_returns_copy(self, tmp_path: Path) -> None:
        """Test that get_events returns a copy, not the internal list."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.append_event("event_1", {})

        events1 = manager.get_events()
        events1.append({"timestamp": "fake", "event": "fake", "data": {}})

        events2 = manager.get_events()
        assert len(events2) == 1  # Original should be unchanged
