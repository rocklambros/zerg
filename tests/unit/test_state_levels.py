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

    def test_level_status_full_lifecycle(self, tmp_path: Path) -> None:
        """Test full level status lifecycle: pending -> running -> complete."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        for expected_status in ["pending", "running", "complete"]:
            manager.set_level_status(1, expected_status)
            status = manager.get_level_status(1)
            assert status["status"] == expected_status
            assert "updated_at" in status

    def test_level_status_with_merge_commit(self, tmp_path: Path) -> None:
        """Test setting level status with and without merge commit SHA."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_level_status(1, "complete", merge_commit="abc123def456")
        assert manager.get_level_status(1)["merge_commit"] == "abc123def456"

        manager.set_level_status(2, "complete")
        assert "merge_commit" not in manager.get_level_status(2)

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
        assert manager.get_level_status(999) is None


class TestEventStructureAndTypes:
    """Tests for event structure, types, and timestamps."""

    def test_event_has_required_fields_and_preserves_types(self, tmp_path: Path) -> None:
        """Test events have required fields and preserve event types in order."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        event_types = ["task_started", "task_complete", "level_complete"]
        for event_type in event_types:
            manager.append_event(event_type, {"test": True})

        events = manager.get_events()
        assert len(events) == 3
        for event in events:
            assert "timestamp" in event
            assert "event" in event
            assert "data" in event
        assert [e["event"] for e in events] == event_types

    def test_event_timestamps_are_iso_and_chronological(self, tmp_path: Path) -> None:
        """Test timestamps are ISO format and chronologically ordered."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        for i in range(3):
            manager.append_event(f"event_{i}", {"index": i})
            time.sleep(0.01)

        events = manager.get_events()
        timestamps = [e["timestamp"] for e in events]
        # Verify ISO parseable
        for ts in timestamps:
            datetime.fromisoformat(ts)
        assert timestamps == sorted(timestamps)

    def test_event_data_preserved_including_complex_and_none(self, tmp_path: Path) -> None:
        """Test event data preservation: complex data and None -> empty dict."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        data = {"task_id": "TASK-001", "files": ["a.py"], "metrics": {"ms": 1500}}
        manager.append_event("task_complete", data)
        manager.append_event("empty_event", None)

        events = manager.get_events()
        assert events[0]["data"]["metrics"]["ms"] == 1500
        assert events[1]["data"] == {}

    def test_get_events_returns_copy(self, tmp_path: Path) -> None:
        """Test that get_events returns a copy, not the internal list."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager.append_event("event_1", {})

        events1 = manager.get_events()
        events1.append({"fake": "event"})

        assert len(manager.get_events()) == 1


class TestEventHistoryLimits:
    """Tests for event history limit behavior."""

    def test_get_events_limit_returns_most_recent(self, tmp_path: Path) -> None:
        """Test limit returns most recent events, no limit returns all."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        for i in range(20):
            manager.append_event(f"event_{i}", {"index": i})

        assert len(manager.get_events()) == 20

        events = manager.get_events(limit=5)
        indices = [e["data"]["index"] for e in events]
        assert indices == [15, 16, 17, 18, 19]

    def test_get_events_limit_boundary_cases(self, tmp_path: Path) -> None:
        """Test limit=1, limit > total, and limit=0 (no limit)."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        for i in range(5):
            manager.append_event(f"event_{i}", {"index": i})

        # limit=1 returns most recent
        events = manager.get_events(limit=1)
        assert len(events) == 1
        assert events[0]["event"] == "event_4"

        # limit > total returns all
        assert len(manager.get_events(limit=100)) == 5

        # limit=0 treated as no limit
        assert len(manager.get_events(limit=0)) == 5


class TestLevelCompletionTimestampTracking:
    """Tests for level completion timestamp tracking."""

    def test_running_and_complete_set_timestamps(self, tmp_path: Path) -> None:
        """Test running sets started_at, complete sets completed_at, pending sets neither."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        # Pending: no special timestamps
        manager.set_level_status(1, "pending")
        status = manager.get_level_status(1)
        assert "started_at" not in status
        assert "completed_at" not in status
        assert "updated_at" in status

        # Running: sets started_at
        manager.set_level_status(2, "running")
        status = manager.get_level_status(2)
        assert "started_at" in status

        # Complete: sets completed_at
        manager.set_level_status(3, "complete")
        status = manager.get_level_status(3)
        assert "completed_at" in status

    def test_running_then_complete_preserves_started_at(self, tmp_path: Path) -> None:
        """Test started_at preserved when transitioning running -> complete."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_level_status(1, "running")
        started_at = manager.get_level_status(1)["started_at"]

        time.sleep(0.01)
        manager.set_level_status(1, "complete")

        status = manager.get_level_status(1)
        assert status["started_at"] == started_at
        assert status["completed_at"] > status["started_at"]

    def test_failed_status_no_completed_at(self, tmp_path: Path) -> None:
        """Test failed status does not set completed_at."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_level_status(1, "running")
        manager.set_level_status(1, "failed")

        status = manager.get_level_status(1)
        assert "started_at" in status
        assert "completed_at" not in status

    def test_rerunning_level_updates_started_at(self, tmp_path: Path) -> None:
        """Test rerunning a level updates started_at timestamp."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_level_status(1, "running")
        first_started = manager.get_level_status(1)["started_at"]

        time.sleep(0.01)
        manager.set_level_status(1, "failed")
        time.sleep(0.01)
        manager.set_level_status(1, "running")
        second_started = manager.get_level_status(1)["started_at"]

        assert second_started > first_started
