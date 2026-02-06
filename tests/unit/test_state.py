"""Comprehensive tests for ZERG state management module.

Targets 100% coverage for zerg/state.py including:
- JSON parsing errors
- Edge cases in task/worker/level management
- Paused/error state handling
- STATE.md generation
"""

import json
from datetime import datetime
from pathlib import Path

import pytest

from zerg.constants import LevelMergeStatus, TaskStatus, WorkerStatus
from zerg.exceptions import StateError
from zerg.state import StateManager
from zerg.types import WorkerState


class TestStateManagerInit:
    """Tests for StateManager initialization."""

    def test_init_with_default_state_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test initialization with default state directory."""
        # Monkeypatch the STATE_DIR constant
        monkeypatch.setattr("zerg.state.STATE_DIR", str(tmp_path / "default_state"))

        manager = StateManager("test-feature")

        assert manager.feature == "test-feature"
        assert manager.state_dir == tmp_path / "default_state"
        assert manager._state_file == tmp_path / "default_state" / "test-feature.json"

    def test_init_with_custom_state_dir_string(self, tmp_path: Path) -> None:
        """Test initialization with custom state directory as string."""
        custom_dir = str(tmp_path / "custom")

        manager = StateManager("test-feature", state_dir=custom_dir)

        assert manager.state_dir == Path(custom_dir)

    def test_init_with_custom_state_dir_path(self, tmp_path: Path) -> None:
        """Test initialization with custom state directory as Path."""
        custom_dir = tmp_path / "custom"

        manager = StateManager("test-feature", state_dir=custom_dir)

        assert manager.state_dir == custom_dir

    def test_init_creates_state_directory(self, tmp_path: Path) -> None:
        """Test that initialization creates state directory if needed."""
        custom_dir = tmp_path / "nested" / "state" / "dir"

        StateManager("test-feature", state_dir=custom_dir)

        assert custom_dir.exists()


class TestStateLoading:
    """Tests for state loading and JSON parsing."""

    def test_load_creates_initial_state_when_no_file(self, tmp_path: Path) -> None:
        """Test loading when no state file exists creates initial state."""
        manager = StateManager("test-feature", state_dir=tmp_path)

        state = manager.load()

        assert state["feature"] == "test-feature"
        assert state["current_level"] == 0
        assert state["tasks"] == {}
        assert state["workers"] == {}
        assert state["levels"] == {}
        assert state["execution_log"] == []
        assert state["paused"] is False
        assert state["error"] is None
        assert "started_at" in state

    def test_load_parses_existing_valid_file(self, tmp_path: Path) -> None:
        """Test loading an existing valid state file."""
        state_data = {
            "feature": "existing-feature",
            "current_level": 2,
            "tasks": {"TASK-001": {"status": "complete"}},
            "workers": {},
            "levels": {},
            "execution_log": [],
            "paused": False,
            "error": None,
        }
        state_file = tmp_path / "existing-feature.json"
        state_file.write_text(json.dumps(state_data))

        manager = StateManager("existing-feature", state_dir=tmp_path)
        state = manager.load()

        assert state["feature"] == "existing-feature"
        assert state["current_level"] == 2
        assert state["tasks"]["TASK-001"]["status"] == "complete"

    def test_load_raises_state_error_on_invalid_json(self, tmp_path: Path) -> None:
        """Test loading raises StateError on invalid JSON."""
        state_file = tmp_path / "bad-feature.json"
        state_file.write_text("{ invalid json }")

        manager = StateManager("bad-feature", state_dir=tmp_path)

        with pytest.raises(StateError) as exc_info:
            manager.load()

        assert "Failed to parse state file" in str(exc_info.value)

    def test_load_returns_copy_of_state(self, tmp_path: Path) -> None:
        """Test that load returns a copy, not the internal state."""
        manager = StateManager("test-feature", state_dir=tmp_path)

        state1 = manager.load()
        state1["current_level"] = 999
        state2 = manager.load()

        # Modifying returned state should not affect internal state
        assert state2["current_level"] == 0


class TestStateSaving:
    """Tests for state saving."""

    def test_save_persists_state(self, tmp_path: Path) -> None:
        """Test saving persists state to file."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager._state["current_level"] = 5

        manager.save()

        # Read raw file to verify
        state_file = tmp_path / "test-feature.json"
        saved = json.loads(state_file.read_text())
        assert saved["current_level"] == 5

    def test_save_handles_datetime_serialization(self, tmp_path: Path) -> None:
        """Test save handles datetime objects via default=str."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager._state["custom_datetime"] = datetime.now()

        # Should not raise
        manager.save()

        state_file = tmp_path / "test-feature.json"
        saved = json.loads(state_file.read_text())
        assert "custom_datetime" in saved


class TestTaskStatus:
    """Tests for task status management."""

    def test_get_task_status_returns_none_for_missing_task(self, tmp_path: Path) -> None:
        """Test getting status of nonexistent task returns None."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        status = manager.get_task_status("NONEXISTENT")

        assert status is None

    def test_get_task_status_returns_status_string(self, tmp_path: Path) -> None:
        """Test getting status of existing task returns status string."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager.set_task_status("TASK-001", TaskStatus.IN_PROGRESS)

        status = manager.get_task_status("TASK-001")

        assert status == "in_progress"

    def test_set_task_status_with_enum(self, tmp_path: Path) -> None:
        """Test setting task status with TaskStatus enum."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_task_status("TASK-001", TaskStatus.COMPLETE)

        assert manager.get_task_status("TASK-001") == "complete"

    def test_set_task_status_with_string(self, tmp_path: Path) -> None:
        """Test setting task status with string."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_task_status("TASK-001", "custom_status")

        assert manager.get_task_status("TASK-001") == "custom_status"

    def test_set_task_status_creates_tasks_dict_if_missing(self, tmp_path: Path) -> None:
        """Test set_task_status creates tasks dict if not present."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        # Remove tasks dict to test creation
        del manager._state["tasks"]

        manager.set_task_status("TASK-001", TaskStatus.PENDING)

        assert "tasks" in manager._state
        assert manager.get_task_status("TASK-001") == "pending"

    def test_set_task_status_with_worker_id(self, tmp_path: Path) -> None:
        """Test setting task status with worker ID."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_task_status("TASK-001", TaskStatus.CLAIMED, worker_id=3)

        task = manager._state["tasks"]["TASK-001"]
        assert task["worker_id"] == 3

    def test_set_task_status_with_error(self, tmp_path: Path) -> None:
        """Test setting task status with error message."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_task_status("TASK-001", TaskStatus.FAILED, error="Test error")

        task = manager._state["tasks"]["TASK-001"]
        assert task["error"] == "Test error"

    def test_set_task_status_complete_sets_completed_at(self, tmp_path: Path) -> None:
        """Test COMPLETE status sets completed_at timestamp."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_task_status("TASK-001", TaskStatus.COMPLETE)

        task = manager._state["tasks"]["TASK-001"]
        assert "completed_at" in task

    def test_set_task_status_in_progress_sets_started_at(self, tmp_path: Path) -> None:
        """Test IN_PROGRESS status sets started_at timestamp."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_task_status("TASK-001", TaskStatus.IN_PROGRESS)

        task = manager._state["tasks"]["TASK-001"]
        assert "started_at" in task

    def test_set_task_status_updates_existing_task(self, tmp_path: Path) -> None:
        """Test setting status on existing task updates it."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager.set_task_status("TASK-001", TaskStatus.PENDING)

        manager.set_task_status("TASK-001", TaskStatus.IN_PROGRESS, worker_id=1)

        task = manager._state["tasks"]["TASK-001"]
        assert task["status"] == "in_progress"
        assert task["worker_id"] == 1


class TestWorkerState:
    """Tests for worker state management."""

    def test_set_worker_state_creates_workers_dict_if_missing(self, tmp_path: Path) -> None:
        """Test set_worker_state creates workers dict if not present."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        del manager._state["workers"]

        worker = WorkerState(worker_id=0, status=WorkerStatus.READY)
        manager.set_worker_state(worker)

        assert "workers" in manager._state
        assert "0" in manager._state["workers"]

    def test_get_all_workers_empty(self, tmp_path: Path) -> None:
        """Test get_all_workers returns empty dict when no workers."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        workers = manager.get_all_workers()

        assert workers == {}

    def test_set_worker_ready_does_nothing_for_nonexistent_worker(self, tmp_path: Path) -> None:
        """Test set_worker_ready does nothing if worker doesn't exist."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_worker_ready(999)  # Nonexistent worker

        # Should not raise, and should not create worker
        assert "999" not in manager._state.get("workers", {})


class TestTaskClaiming:
    """Tests for task claiming functionality."""

    def test_claim_task_with_todo_status(self, tmp_path: Path) -> None:
        """Test claiming a task with TODO status."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager.set_task_status("TASK-001", TaskStatus.TODO)

        result = manager.claim_task("TASK-001", worker_id=0)

        assert result is True
        assert manager.get_task_status("TASK-001") == TaskStatus.CLAIMED.value

    def test_claim_task_fails_for_claimed_status(self, tmp_path: Path) -> None:
        """Test claiming fails for already claimed task."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager.set_task_status("TASK-001", TaskStatus.CLAIMED, worker_id=0)

        result = manager.claim_task("TASK-001", worker_id=1)

        assert result is False

    def test_claim_task_fails_for_complete_status(self, tmp_path: Path) -> None:
        """Test claiming fails for completed task."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager.set_task_status("TASK-001", TaskStatus.COMPLETE)

        result = manager.claim_task("TASK-001", worker_id=0)

        assert result is False

    def test_claim_task_fails_when_task_has_worker_assigned(self, tmp_path: Path) -> None:
        """Test claiming fails when task is pending but already has worker_id.

        This is an edge case where a task has PENDING status but already has
        a worker_id assigned (unusual state, but possible via manual state
        manipulation or recovery scenarios).
        """
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        # Manually create a task in an unusual state: PENDING but with worker_id set
        manager._state["tasks"] = {
            "TASK-001": {
                "status": TaskStatus.PENDING.value,
                "worker_id": 5,  # Already has a worker assigned
            }
        }
        manager.save()

        result = manager.claim_task("TASK-001", worker_id=1)

        # Should fail because task already has a worker_id
        assert result is False

    def test_release_task_for_nonexistent_task(self, tmp_path: Path) -> None:
        """Test releasing nonexistent task does nothing."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        # Should not raise
        manager.release_task("NONEXISTENT", worker_id=0)


class TestEvents:
    """Tests for execution event logging."""

    def test_append_event_creates_execution_log_if_missing(self, tmp_path: Path) -> None:
        """Test append_event creates execution_log if not present."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        del manager._state["execution_log"]

        manager.append_event("test_event", {"key": "value"})

        assert "execution_log" in manager._state
        assert len(manager._state["execution_log"]) == 1

    def test_append_event_without_data(self, tmp_path: Path) -> None:
        """Test append_event with no data uses empty dict."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.append_event("test_event")

        event = manager._state["execution_log"][0]
        assert event["data"] == {}

    def test_get_events_without_limit(self, tmp_path: Path) -> None:
        """Test get_events returns all events when no limit specified."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        for i in range(5):
            manager.append_event(f"event_{i}")

        events = manager.get_events()

        assert len(events) == 5

    def test_get_events_with_limit(self, tmp_path: Path) -> None:
        """Test get_events respects limit parameter."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        for i in range(10):
            manager.append_event(f"event_{i}")

        events = manager.get_events(limit=3)

        assert len(events) == 3
        # Should be the last 3 events
        assert events[0]["event"] == "event_7"
        assert events[2]["event"] == "event_9"

    def test_get_events_returns_copy(self, tmp_path: Path) -> None:
        """Test get_events returns a copy of events list."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager.append_event("test_event")

        events1 = manager.get_events()
        events1.append({"fake": "event"})
        events2 = manager.get_events()

        assert len(events2) == 1


class TestLevelManagement:
    """Tests for current level management."""

    def test_set_current_level(self, tmp_path: Path) -> None:
        """Test setting current level."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_current_level(3)

        assert manager._state["current_level"] == 3

    def test_get_current_level_default(self, tmp_path: Path) -> None:
        """Test get_current_level returns 0 when not set."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        del manager._state["current_level"]

        level = manager.get_current_level()

        assert level == 0


class TestLevelStatus:
    """Tests for level status management."""

    def test_set_level_status_creates_levels_dict_if_missing(self, tmp_path: Path) -> None:
        """Test set_level_status creates levels dict if not present."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        del manager._state["levels"]

        manager.set_level_status(1, "running")

        assert "levels" in manager._state
        assert "1" in manager._state["levels"]

    def test_set_level_status_creates_level_if_missing(self, tmp_path: Path) -> None:
        """Test set_level_status creates level entry if not present."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_level_status(5, "pending")

        assert "5" in manager._state["levels"]
        assert manager._state["levels"]["5"]["status"] == "pending"

    def test_get_level_status_returns_none_for_missing_level(self, tmp_path: Path) -> None:
        """Test get_level_status returns None for nonexistent level."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        status = manager.get_level_status(999)

        assert status is None


class TestTasksByStatus:
    """Tests for getting tasks by status."""

    def test_get_tasks_by_status_with_enum(self, tmp_path: Path) -> None:
        """Test get_tasks_by_status with TaskStatus enum."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager.set_task_status("TASK-001", TaskStatus.PENDING)
        manager.set_task_status("TASK-002", TaskStatus.PENDING)
        manager.set_task_status("TASK-003", TaskStatus.COMPLETE)

        pending = manager.get_tasks_by_status(TaskStatus.PENDING)

        assert set(pending) == {"TASK-001", "TASK-002"}

    def test_get_tasks_by_status_with_string(self, tmp_path: Path) -> None:
        """Test get_tasks_by_status with string."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager.set_task_status("TASK-001", "custom")
        manager.set_task_status("TASK-002", "custom")

        custom = manager.get_tasks_by_status("custom")

        assert set(custom) == {"TASK-001", "TASK-002"}

    def test_get_tasks_by_status_empty_result(self, tmp_path: Path) -> None:
        """Test get_tasks_by_status returns empty list when no matches."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        result = manager.get_tasks_by_status(TaskStatus.FAILED)

        assert result == []


class TestPausedState:
    """Tests for paused state management."""

    def test_set_paused_true(self, tmp_path: Path) -> None:
        """Test setting paused state to True."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_paused(True)

        assert manager._state["paused"] is True

    def test_set_paused_false(self, tmp_path: Path) -> None:
        """Test setting paused state to False."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager._state["paused"] = True

        manager.set_paused(False)

        assert manager._state["paused"] is False

    def test_is_paused_default_false(self, tmp_path: Path) -> None:
        """Test is_paused returns False by default."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        del manager._state["paused"]

        assert manager.is_paused() is False

    def test_is_paused_true(self, tmp_path: Path) -> None:
        """Test is_paused returns True when paused."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager.set_paused(True)

        assert manager.is_paused() is True


class TestErrorState:
    """Tests for error state management."""

    def test_set_error(self, tmp_path: Path) -> None:
        """Test setting error state."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_error("Test error message")

        assert manager._state["error"] == "Test error message"

    def test_set_error_none_clears_error(self, tmp_path: Path) -> None:
        """Test setting error to None clears it."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager._state["error"] = "Previous error"

        manager.set_error(None)

        assert manager._state["error"] is None

    def test_get_error_default_none(self, tmp_path: Path) -> None:
        """Test get_error returns None by default."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        del manager._state["error"]

        assert manager.get_error() is None

    def test_get_error_returns_error(self, tmp_path: Path) -> None:
        """Test get_error returns error message."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager.set_error("Some error")

        error = manager.get_error()

        assert error == "Some error"


class TestDeleteAndExists:
    """Tests for delete and exists methods."""

    def test_delete_removes_state_file(self, tmp_path: Path) -> None:
        """Test delete removes the state file."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager.save()

        manager.delete()

        assert not (tmp_path / "test-feature.json").exists()

    def test_delete_does_nothing_if_no_file(self, tmp_path: Path) -> None:
        """Test delete does nothing if file doesn't exist."""
        manager = StateManager("test-feature", state_dir=tmp_path)

        # Should not raise
        manager.delete()

    def test_exists_returns_false_for_missing_file(self, tmp_path: Path) -> None:
        """Test exists returns False when file doesn't exist."""
        manager = StateManager("test-feature", state_dir=tmp_path)

        assert manager.exists() is False

    def test_exists_returns_true_for_existing_file(self, tmp_path: Path) -> None:
        """Test exists returns True when file exists."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager.save()

        assert manager.exists() is True


class TestLevelMergeStatus:
    """Tests for level merge status."""

    def test_get_level_merge_status_returns_none_when_not_set(self, tmp_path: Path) -> None:
        """Test get_level_merge_status returns None when not set."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        status = manager.get_level_merge_status(1)

        assert status is None

    def test_get_level_merge_status_returns_none_for_missing_level(self, tmp_path: Path) -> None:
        """Test get_level_merge_status returns None for nonexistent level."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        status = manager.get_level_merge_status(999)

        assert status is None

    def test_set_level_merge_status_creates_levels_dict(self, tmp_path: Path) -> None:
        """Test set_level_merge_status creates levels dict if missing."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        del manager._state["levels"]

        manager.set_level_merge_status(1, LevelMergeStatus.PENDING)

        assert "levels" in manager._state


class TestRetryTracking:
    """Tests for retry tracking edge cases."""

    def test_increment_retry_creates_tasks_dict(self, tmp_path: Path) -> None:
        """Test increment_task_retry creates tasks dict if missing."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        del manager._state["tasks"]

        count = manager.increment_task_retry("TASK-001")

        assert count == 1
        assert "tasks" in manager._state

    def test_reset_retry_nonexistent_task(self, tmp_path: Path) -> None:
        """Test reset_task_retry does nothing for nonexistent task."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        # Should not raise
        manager.reset_task_retry("NONEXISTENT")


class TestStateMdGeneration:
    """Tests for STATE.md generation."""

    def test_generate_state_md_creates_file(self, tmp_path: Path) -> None:
        """Test generate_state_md creates STATE.md file."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        gsd_dir = tmp_path / "gsd"

        result = manager.generate_state_md(gsd_dir=gsd_dir)

        assert result.exists()
        assert result.name == "STATE.md"

    def test_generate_state_md_creates_gsd_directory(self, tmp_path: Path) -> None:
        """Test generate_state_md creates GSD directory if missing."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        gsd_dir = tmp_path / "nested" / "gsd"

        manager.generate_state_md(gsd_dir=gsd_dir)

        assert gsd_dir.exists()

    def test_generate_state_md_uses_default_gsd_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test generate_state_md uses default GSD_DIR when not specified."""
        monkeypatch.setattr("zerg.state.GSD_DIR", str(tmp_path / "default_gsd"))

        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        result = manager.generate_state_md()

        assert str(result).startswith(str(tmp_path / "default_gsd"))

    def test_generate_state_md_includes_header(self, tmp_path: Path) -> None:
        """Test STATE.md includes feature name in header."""
        manager = StateManager("my-feature", state_dir=tmp_path)
        manager.load()
        gsd_dir = tmp_path / "gsd"

        result = manager.generate_state_md(gsd_dir=gsd_dir)
        content = result.read_text()

        assert "# ZERG State: my-feature" in content

    def test_generate_state_md_includes_current_phase(self, tmp_path: Path) -> None:
        """Test STATE.md includes current phase information."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager.set_current_level(3)
        gsd_dir = tmp_path / "gsd"

        result = manager.generate_state_md(gsd_dir=gsd_dir)
        content = result.read_text()

        assert "## Current Phase" in content
        assert "**Level:** 3" in content

    def test_generate_state_md_includes_paused_status(self, tmp_path: Path) -> None:
        """Test STATE.md includes paused status when paused."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager.set_paused(True)
        gsd_dir = tmp_path / "gsd"

        result = manager.generate_state_md(gsd_dir=gsd_dir)
        content = result.read_text()

        assert "**Status:** PAUSED" in content

    def test_generate_state_md_includes_error(self, tmp_path: Path) -> None:
        """Test STATE.md includes error when set."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager.set_error("Test error message")
        gsd_dir = tmp_path / "gsd"

        result = manager.generate_state_md(gsd_dir=gsd_dir)
        content = result.read_text()

        assert "**Error:** Test error message" in content

    def test_generate_state_md_includes_tasks_table(self, tmp_path: Path) -> None:
        """Test STATE.md includes tasks table."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager.set_task_status("TASK-001", TaskStatus.COMPLETE, worker_id=1)
        manager.set_task_status("TASK-002", TaskStatus.IN_PROGRESS, worker_id=2)
        gsd_dir = tmp_path / "gsd"

        result = manager.generate_state_md(gsd_dir=gsd_dir)
        content = result.read_text()

        assert "## Tasks" in content
        assert "| ID | Status | Worker | Updated |" in content
        assert "TASK-001" in content
        assert "complete" in content

    def test_generate_state_md_includes_workers_section(self, tmp_path: Path) -> None:
        """Test STATE.md includes workers section when workers exist."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        worker = WorkerState(
            worker_id=0,
            status=WorkerStatus.RUNNING,
            branch="zerg/test/worker-0",
            tasks_completed=5,
        )
        manager.set_worker_state(worker)
        gsd_dir = tmp_path / "gsd"

        result = manager.generate_state_md(gsd_dir=gsd_dir)
        content = result.read_text()

        assert "## Workers" in content
        assert "| ID | Status | Tasks Done | Branch |" in content

    def test_generate_state_md_truncates_long_branch_names(self, tmp_path: Path) -> None:
        """Test STATE.md truncates very long branch names."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        worker = WorkerState(
            worker_id=0,
            status=WorkerStatus.RUNNING,
            branch="zerg/very-long-feature-name/with-extra-details/worker-0-branch",
        )
        manager.set_worker_state(worker)
        gsd_dir = tmp_path / "gsd"

        result = manager.generate_state_md(gsd_dir=gsd_dir)
        content = result.read_text()

        assert "..." in content

    def test_generate_state_md_includes_levels_section(self, tmp_path: Path) -> None:
        """Test STATE.md includes levels section."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager.set_level_status(1, "complete", merge_commit="abc123def456")
        manager.set_level_merge_status(1, LevelMergeStatus.COMPLETE)
        gsd_dir = tmp_path / "gsd"

        result = manager.generate_state_md(gsd_dir=gsd_dir)
        content = result.read_text()

        assert "## Levels" in content
        assert "**Level 1:** complete" in content
        assert "Merge: complete" in content
        assert "Commit: abc123de" in content  # First 8 chars

    def test_generate_state_md_includes_blockers_section(self, tmp_path: Path) -> None:
        """Test STATE.md includes blockers section for failed tasks."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager.set_task_status("TASK-001", TaskStatus.FAILED, error="Verification failed")
        manager.increment_task_retry("TASK-001")
        gsd_dir = tmp_path / "gsd"

        result = manager.generate_state_md(gsd_dir=gsd_dir)
        content = result.read_text()

        assert "## Blockers" in content
        assert "**TASK-001** (retries: 1)" in content
        assert "Verification failed" in content

    def test_generate_state_md_includes_recent_events(self, tmp_path: Path) -> None:
        """Test STATE.md includes recent events section."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager.append_event("task_started", {"task_id": "TASK-001"})
        manager.append_event("task_completed", {"task_id": "TASK-001"})
        gsd_dir = tmp_path / "gsd"

        result = manager.generate_state_md(gsd_dir=gsd_dir)
        content = result.read_text()

        assert "## Recent Events" in content
        assert "task_started" in content
        assert "task_completed" in content

    def test_generate_state_md_limits_events_to_10(self, tmp_path: Path) -> None:
        """Test STATE.md only shows last 10 events."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        for i in range(15):
            manager.append_event(f"event_{i}")
        gsd_dir = tmp_path / "gsd"

        result = manager.generate_state_md(gsd_dir=gsd_dir)
        content = result.read_text()

        # Should have events 5-14, not 0-4
        assert "event_14" in content
        assert "event_5" in content
        assert "event_4" not in content

    def test_generate_state_md_no_workers_section_when_empty(self, tmp_path: Path) -> None:
        """Test STATE.md omits workers section when no workers."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        gsd_dir = tmp_path / "gsd"

        result = manager.generate_state_md(gsd_dir=gsd_dir)
        content = result.read_text()

        assert "## Workers" not in content

    def test_generate_state_md_no_levels_section_when_empty(self, tmp_path: Path) -> None:
        """Test STATE.md omits levels section when no levels."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        gsd_dir = tmp_path / "gsd"

        result = manager.generate_state_md(gsd_dir=gsd_dir)
        content = result.read_text()

        assert "## Levels" not in content

    def test_generate_state_md_no_blockers_section_when_empty(self, tmp_path: Path) -> None:
        """Test STATE.md omits blockers section when no failed tasks."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        gsd_dir = tmp_path / "gsd"

        result = manager.generate_state_md(gsd_dir=gsd_dir)
        content = result.read_text()

        assert "## Blockers" not in content

    def test_generate_state_md_no_events_section_when_empty(self, tmp_path: Path) -> None:
        """Test STATE.md omits events section when no events."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        gsd_dir = tmp_path / "gsd"

        result = manager.generate_state_md(gsd_dir=gsd_dir)
        content = result.read_text()

        assert "## Recent Events" not in content

    def test_generate_state_md_handles_task_without_timestamp(self, tmp_path: Path) -> None:
        """Test STATE.md handles tasks without updated_at timestamp."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        # Manually add task without updated_at
        manager._state["tasks"]["TASK-001"] = {"status": "pending"}
        gsd_dir = tmp_path / "gsd"

        result = manager.generate_state_md(gsd_dir=gsd_dir)
        content = result.read_text()

        assert "TASK-001" in content
        assert "pending" in content

    def test_generate_state_md_handles_levels_without_merge_commit(self, tmp_path: Path) -> None:
        """Test STATE.md handles levels without merge_commit."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager.set_level_status(1, "running")
        gsd_dir = tmp_path / "gsd"

        result = manager.generate_state_md(gsd_dir=gsd_dir)
        content = result.read_text()

        assert "**Level 1:** running" in content
        # Should not have commit line
        lines = content.split("\n")
        level_line_idx = next(i for i, line in enumerate(lines) if "Level 1:" in line)
        # Next line should not be about commit
        if level_line_idx + 1 < len(lines):
            assert "Commit:" not in lines[level_line_idx + 1]
