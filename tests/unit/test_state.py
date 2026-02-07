"""Tests for ZERG state management module.

Covers core StateManager functionality: init, load, save, task/worker/level
management, events, paused/error state, delete/exists, merge status, retry
tracking, STATE.md generation, worker state edge cases, and StateSyncService.
"""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from zerg.constants import LevelMergeStatus, TaskStatus, WorkerStatus
from zerg.exceptions import StateError
from zerg.levels import LevelController
from zerg.state import StateManager
from zerg.state_sync_service import StateSyncService
from zerg.types import WorkerState


class TestStateManagerInit:
    """Tests for StateManager initialization."""

    @pytest.mark.smoke
    def test_init_with_default_state_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test initialization with default state directory."""
        monkeypatch.setattr("zerg.state.persistence.STATE_DIR", str(tmp_path / "default_state"))
        manager = StateManager("test-feature")
        assert manager.feature == "test-feature"
        assert manager._persistence._state_file == tmp_path / "default_state" / "test-feature.json"

    @pytest.mark.smoke
    def test_init_creates_nested_state_directory(self, tmp_path: Path) -> None:
        """Test that initialization creates nested state directory."""
        custom_dir = tmp_path / "nested" / "state" / "dir"
        StateManager("test-feature", state_dir=custom_dir)
        assert custom_dir.exists()


class TestStateLoading:
    """Tests for state loading and JSON parsing."""

    @pytest.mark.smoke
    def test_load_creates_initial_state_when_no_file(self, tmp_path: Path) -> None:
        """Test loading when no state file exists creates initial state."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        state = manager.load()
        assert state["feature"] == "test-feature"
        assert state["current_level"] == 0
        assert state["tasks"] == {}
        assert state["paused"] is False
        assert state["error"] is None

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
        (tmp_path / "existing-feature.json").write_text(json.dumps(state_data))
        manager = StateManager("existing-feature", state_dir=tmp_path)
        state = manager.load()
        assert state["current_level"] == 2

    def test_load_raises_state_error_on_invalid_json(self, tmp_path: Path) -> None:
        """Test loading raises StateError on invalid JSON."""
        (tmp_path / "bad-feature.json").write_text("{ invalid json }")
        manager = StateManager("bad-feature", state_dir=tmp_path)
        with pytest.raises(StateError, match="Failed to parse state file"):
            manager.load()

    def test_load_returns_copy_of_state(self, tmp_path: Path) -> None:
        """Test that load returns a copy, not the internal state."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        state1 = manager.load()
        state1["current_level"] = 999
        assert manager.load()["current_level"] == 0


class TestStateSaving:
    """Tests for state saving."""

    def test_save_persists_state_and_handles_datetime(self, tmp_path: Path) -> None:
        """Test saving persists state to file including datetime serialization."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager._persistence._state["current_level"] = 5
        manager._persistence._state["custom_datetime"] = datetime.now()
        manager.save()
        saved = json.loads((tmp_path / "test-feature.json").read_text())
        assert saved["current_level"] == 5
        assert "custom_datetime" in saved


class TestTaskStatus:
    """Tests for task status management."""

    def test_get_task_status_returns_none_for_missing_task(self, tmp_path: Path) -> None:
        """Test getting status of nonexistent task returns None."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        assert manager.get_task_status("NONEXISTENT") is None

    def test_set_task_status_enum_and_string(self, tmp_path: Path) -> None:
        """Test setting task status with enum and string values."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager.set_task_status("TASK-001", TaskStatus.COMPLETE)
        assert manager.get_task_status("TASK-001") == "complete"
        manager.set_task_status("TASK-002", "custom_status")
        assert manager.get_task_status("TASK-002") == "custom_status"

    def test_set_task_status_creates_tasks_dict_if_missing(self, tmp_path: Path) -> None:
        """Test set_task_status creates tasks dict if not present."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        del manager._persistence._state["tasks"]
        manager.set_task_status("TASK-001", TaskStatus.PENDING)
        assert manager.get_task_status("TASK-001") == "pending"

    def test_set_task_status_with_worker_id_error_and_timestamps(self, tmp_path: Path) -> None:
        """Test setting task status with worker ID, error, and timestamp behavior."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager.set_task_status("TASK-001", TaskStatus.FAILED, worker_id=3, error="Test error")
        task = manager._persistence._state["tasks"]["TASK-001"]
        assert task["worker_id"] == 3
        assert task["error"] == "Test error"
        # Verify COMPLETE sets completed_at, IN_PROGRESS sets started_at
        manager.set_task_status("TASK-002", TaskStatus.COMPLETE)
        assert "completed_at" in manager._persistence._state["tasks"]["TASK-002"]
        manager.set_task_status("TASK-003", TaskStatus.IN_PROGRESS)
        assert "started_at" in manager._persistence._state["tasks"]["TASK-003"]


class TestWorkerState:
    """Tests for worker state management."""

    def test_set_worker_state_creates_workers_dict_if_missing(self, tmp_path: Path) -> None:
        """Test set_worker_state creates workers dict if not present."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        del manager._persistence._state["workers"]
        manager.set_worker_state(WorkerState(worker_id=0, status=WorkerStatus.READY))
        assert "0" in manager._persistence._state["workers"]

    def test_set_worker_ready_does_nothing_for_nonexistent_worker(self, tmp_path: Path) -> None:
        """Test set_worker_ready does nothing if worker doesn't exist."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager.set_worker_ready(999)
        assert "999" not in manager._persistence._state.get("workers", {})


class TestTaskClaiming:
    """Tests for task claiming functionality."""

    def test_claim_task_with_todo_status(self, tmp_path: Path) -> None:
        """Test claiming a task with TODO status succeeds."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager.set_task_status("TASK-001", TaskStatus.TODO)
        assert manager.claim_task("TASK-001", worker_id=0) is True
        assert manager.get_task_status("TASK-001") == TaskStatus.CLAIMED.value

    def test_claim_task_fails_for_non_claimable(self, tmp_path: Path) -> None:
        """Test claiming fails for already claimed or completed tasks."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager.set_task_status("TASK-001", TaskStatus.CLAIMED, worker_id=0)
        assert manager.claim_task("TASK-001", worker_id=1) is False
        manager.set_task_status("TASK-002", TaskStatus.COMPLETE)
        assert manager.claim_task("TASK-002", worker_id=1) is False

    def test_release_task_for_nonexistent_task(self, tmp_path: Path) -> None:
        """Test releasing nonexistent task does nothing."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager.release_task("NONEXISTENT", worker_id=0)


class TestEvents:
    """Tests for execution event logging."""

    def test_append_event_creates_log_and_stores_data(self, tmp_path: Path) -> None:
        """Test append_event creates execution_log if missing and stores event data."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        del manager._persistence._state["execution_log"]
        manager.append_event("test_event", {"key": "value"})
        assert len(manager._persistence._state["execution_log"]) == 1
        # Also test no-data path
        manager.append_event("no_data_event")
        assert manager._persistence._state["execution_log"][1]["data"] == {}

    def test_get_events_with_and_without_limit(self, tmp_path: Path) -> None:
        """Test get_events with and without limit."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        for i in range(10):
            manager.append_event(f"event_{i}")
        assert len(manager.get_events()) == 10
        limited = manager.get_events(limit=3)
        assert len(limited) == 3
        assert limited[0]["event"] == "event_7"


class TestLevelAndPausedErrorState:
    """Tests for level management, paused, and error state."""

    def test_set_and_get_current_level(self, tmp_path: Path) -> None:
        """Test setting and getting current level, including default."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager.set_current_level(3)
        assert manager._persistence._state["current_level"] == 3
        del manager._persistence._state["current_level"]
        assert manager.get_current_level() == 0

    def test_set_level_status_creates_levels_dict(self, tmp_path: Path) -> None:
        """Test set_level_status creates levels dict if missing."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        del manager._persistence._state["levels"]
        manager.set_level_status(1, "running")
        assert manager._persistence._state["levels"]["1"]["status"] == "running"

    def test_get_level_status_returns_none_for_missing(self, tmp_path: Path) -> None:
        """Test get_level_status returns None for nonexistent level."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        assert manager.get_level_status(999) is None

    def test_set_paused_and_error(self, tmp_path: Path) -> None:
        """Test paused and error state management."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        # Paused
        manager.set_paused(True)
        assert manager._persistence._state["paused"] is True
        manager.set_paused(False)
        assert manager._persistence._state["paused"] is False
        # Error
        manager.set_error("Test error")
        assert manager.get_error() == "Test error"
        manager.set_error(None)
        assert manager.get_error() is None


class TestTasksByStatus:
    """Tests for getting tasks by status."""

    def test_get_tasks_by_status_filters_correctly(self, tmp_path: Path) -> None:
        """Test get_tasks_by_status returns correct tasks."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager.set_task_status("TASK-001", TaskStatus.PENDING)
        manager.set_task_status("TASK-002", TaskStatus.PENDING)
        manager.set_task_status("TASK-003", TaskStatus.COMPLETE)
        assert set(manager.get_tasks_by_status(TaskStatus.PENDING)) == {"TASK-001", "TASK-002"}
        assert manager.get_tasks_by_status(TaskStatus.FAILED) == []


class TestDeleteAndExists:
    """Tests for delete and exists methods."""

    def test_delete_and_exists_lifecycle(self, tmp_path: Path) -> None:
        """Test delete removes file and exists reflects file state."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        assert manager.exists() is False
        manager.load()
        manager.save()
        assert manager.exists() is True
        manager.delete()
        assert not (tmp_path / "test-feature.json").exists()
        # delete on missing file is no-op
        manager.delete()


class TestLevelMergeAndRetry:
    """Tests for level merge status and retry tracking."""

    def test_get_level_merge_status_returns_none_when_unset(self, tmp_path: Path) -> None:
        """Test get_level_merge_status returns None when not set."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        assert manager.get_level_merge_status(1) is None
        assert manager.get_level_merge_status(999) is None

    def test_set_level_merge_status_creates_levels_dict(self, tmp_path: Path) -> None:
        """Test set_level_merge_status creates levels dict if missing."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        del manager._persistence._state["levels"]
        manager.set_level_merge_status(1, LevelMergeStatus.PENDING)
        assert "levels" in manager._persistence._state

    def test_increment_retry_creates_tasks_dict(self, tmp_path: Path) -> None:
        """Test increment_task_retry creates tasks dict if missing."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        del manager._persistence._state["tasks"]
        assert manager.increment_task_retry("TASK-001") == 1

    def test_reset_retry_nonexistent_task(self, tmp_path: Path) -> None:
        """Test reset_task_retry does nothing for nonexistent task."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager.reset_task_retry("NONEXISTENT")


class TestStateMdGeneration:
    """Tests for STATE.md generation."""

    def test_generate_state_md_creates_file(self, tmp_path: Path) -> None:
        """Test generate_state_md creates STATE.md file."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        result = manager.generate_state_md(gsd_dir=tmp_path / "gsd")
        assert result.exists()
        assert result.name == "STATE.md"

    def test_generate_state_md_includes_all_sections(self, tmp_path: Path) -> None:
        """Test STATE.md includes header, phase, tasks, workers, levels, blockers, events."""
        manager = StateManager("my-feature", state_dir=tmp_path)
        manager.load()
        manager.set_current_level(3)
        manager.set_paused(True)
        manager.set_error("Test error message")
        manager.set_task_status("TASK-001", TaskStatus.COMPLETE, worker_id=1)
        manager.set_task_status("TASK-002", TaskStatus.FAILED, error="Verification failed")
        manager.increment_task_retry("TASK-002")
        manager.set_worker_state(
            WorkerState(
                worker_id=0,
                status=WorkerStatus.RUNNING,
                branch="zerg/test/worker-0",
                tasks_completed=5,
            )
        )
        manager.set_level_status(1, "complete", merge_commit="abc123def456")
        manager.set_level_merge_status(1, LevelMergeStatus.COMPLETE)
        manager.append_event("task_started", {"task_id": "TASK-001"})
        gsd_dir = tmp_path / "gsd"
        content = manager.generate_state_md(gsd_dir=gsd_dir).read_text()

        for expected in [
            "# ZERG State: my-feature",
            "**Level:** 3",
            "**Status:** PAUSED",
            "**Error:** Test error message",
            "## Tasks",
            "TASK-001",
            "## Workers",
            "## Levels",
            "Commit: abc123de",
            "## Blockers",
            "**TASK-002** (retries: 1)",
            "## Recent Events",
        ]:
            assert expected in content

    def test_generate_state_md_omits_empty_sections(self, tmp_path: Path) -> None:
        """Test STATE.md omits optional sections when empty."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        content = manager.generate_state_md(gsd_dir=tmp_path / "gsd").read_text()
        for section in ["## Workers", "## Levels", "## Blockers", "## Recent Events"]:
            assert section not in content

    def test_generate_state_md_limits_events_to_10(self, tmp_path: Path) -> None:
        """Test STATE.md only shows last 10 events."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        for i in range(15):
            manager.append_event(f"event_{i}")
        content = manager.generate_state_md(gsd_dir=tmp_path / "gsd").read_text()
        assert "event_14" in content
        assert "event_4" not in content


# ============================================================================
# Merged from test_state_workers.py -- unique worker state code paths
# ============================================================================


class TestGetWorkerStateEdgeCases:
    """Tests for get_worker_state edge cases (merged from test_state_workers.py)."""

    def test_get_worker_state_non_existent_returns_none(self, tmp_path: Path) -> None:
        """get_worker_state returns None for non-existent worker ID."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        assert manager.get_worker_state(worker_id=999) is None

    def test_get_worker_state_string_key_conversion(self, tmp_path: Path) -> None:
        """get_worker_state handles string-to-int key conversion correctly."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager._persistence._state["workers"] = {
            "1": {
                "worker_id": 1,
                "status": WorkerStatus.READY.value,
                "current_task": None,
                "port": 8080,
                "container_id": None,
                "worktree_path": None,
                "branch": None,
                "health_check_at": None,
                "started_at": None,
                "ready_at": None,
                "last_task_completed_at": None,
                "tasks_completed": 0,
                "context_usage": 0.0,
            }
        }
        manager.save()
        result = manager.get_worker_state(worker_id=1)
        assert result is not None and result.worker_id == 1
        assert manager.get_worker_state(worker_id=2) is None

    def test_set_worker_state_overwrites_completely(self, tmp_path: Path) -> None:
        """set_worker_state does full replacement, not merge."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager.set_worker_state(
            WorkerState(
                worker_id=1,
                status=WorkerStatus.RUNNING,
                current_task="TASK-001",
                port=8080,
                tasks_completed=10,
            )
        )
        manager.set_worker_state(
            WorkerState(
                worker_id=1,
                status=WorkerStatus.IDLE,
                current_task=None,
                port=None,
                tasks_completed=0,
            )
        )
        retrieved = manager.get_worker_state(worker_id=1)
        assert retrieved.status == WorkerStatus.IDLE
        assert retrieved.tasks_completed == 0

    def test_get_all_workers_returns_correct_states(self, tmp_path: Path) -> None:
        """get_all_workers returns all registered workers with int keys."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        for i in range(3):
            manager.set_worker_state(WorkerState(worker_id=i, status=WorkerStatus.READY, port=8080 + i))
        result = manager.get_all_workers()
        assert len(result) == 3
        assert all(isinstance(k, int) for k in result.keys())


# ============================================================================
# Merged from test_state_sync_service.py -- unique StateSyncService code paths
# ============================================================================


class TestStateSyncServiceEssentials:
    """Essential StateSyncService tests (merged from test_state_sync_service.py)."""

    def test_sync_from_disk_syncs_completed_tasks(self) -> None:
        """sync_from_disk propagates completed task status to LevelController."""
        mock_state = MagicMock(spec=StateManager)
        mock_state._state = {"tasks": {"TASK-001": {"status": TaskStatus.COMPLETE.value}}}
        mock_levels = MagicMock(spec=LevelController)
        mock_levels.get_task_status.return_value = TaskStatus.PENDING.value
        service = StateSyncService(state=mock_state, levels=mock_levels)
        service.sync_from_disk()
        mock_levels.mark_task_complete.assert_called_once_with("TASK-001")

    def test_reassign_stranded_tasks_clears_dead_worker(self) -> None:
        """reassign_stranded_tasks unassigns tasks on dead workers."""
        mock_state = MagicMock(spec=StateManager)
        mock_state._state = {"tasks": {"TASK-001": {"status": "pending", "worker_id": 5}}}
        mock_levels = MagicMock(spec=LevelController)
        service = StateSyncService(state=mock_state, levels=mock_levels)
        service.reassign_stranded_tasks({1, 2, 3})
        assert mock_state._state["tasks"]["TASK-001"]["worker_id"] is None
        mock_state.save.assert_called_once()
