"""Tests for task state edge cases (TC-012).

Tests covering task status retrieval, transitions, timestamps, duration, and filtering.
"""

from datetime import datetime
from pathlib import Path

from zerg.constants import TaskStatus
from zerg.state import StateManager


class TestGetTaskStatusEdgeCases:
    """Tests for get_task_status edge cases."""

    def test_get_task_status_nonexistent_and_missing_key(self, tmp_path: Path) -> None:
        """Test get_task_status returns None for missing tasks and missing status keys."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        assert manager.get_task_status("NONEXISTENT") is None

        # Task exists but no status key
        manager._state["tasks"] = {"TASK-001": {"worker_id": 1}}
        manager.save()
        assert manager.get_task_status("TASK-001") is None

    def test_get_task_status_persists_across_reload(self, tmp_path: Path) -> None:
        """Test get_task_status works correctly after manager reload."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager.set_task_status("TASK-001", TaskStatus.PENDING)

        manager2 = StateManager("test-feature", state_dir=tmp_path)
        manager2.load()
        assert manager2.get_task_status("TASK-001") == TaskStatus.PENDING.value


class TestSetTaskStatusTransitions:
    """Tests for task status transitions."""

    def test_set_task_status_accepts_all_enum_values(self, tmp_path: Path) -> None:
        """Test set_task_status accepts all valid TaskStatus values."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        for status in TaskStatus:
            task_id = f"TASK-{status.name}"
            manager.set_task_status(task_id, status)
            assert manager.get_task_status(task_id) == status.value

    def test_set_task_status_allows_backward_transition(self, tmp_path: Path) -> None:
        """Test backward transition (complete -> pending) is allowed."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager.set_task_status("TASK-001", TaskStatus.COMPLETE)
        manager.set_task_status("TASK-001", TaskStatus.PENDING)
        assert manager.get_task_status("TASK-001") == TaskStatus.PENDING.value


class TestTaskTimestamps:
    """Tests for task timestamps: claimed_at, started_at, completed_at."""

    def test_claim_sets_claimed_at_and_preserves_on_status_change(self, tmp_path: Path) -> None:
        """Test claim_task sets claimed_at, preserved across status changes."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager.set_task_status("TASK-001", TaskStatus.PENDING)
        manager.claim_task("TASK-001", worker_id=0)

        task = manager._state["tasks"]["TASK-001"]
        assert "claimed_at" in task
        datetime.fromisoformat(task["claimed_at"])

        original_claimed = task["claimed_at"]
        manager.set_task_status("TASK-001", TaskStatus.IN_PROGRESS, worker_id=0)
        assert manager._state["tasks"]["TASK-001"]["claimed_at"] == original_claimed

    def test_in_progress_and_complete_set_timestamps(self, tmp_path: Path) -> None:
        """Test IN_PROGRESS sets started_at and COMPLETE sets completed_at."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager.set_task_status("TASK-001", TaskStatus.IN_PROGRESS, worker_id=0)
        assert "started_at" in manager._state["tasks"]["TASK-001"]

        manager.set_task_status("TASK-002", TaskStatus.COMPLETE)
        assert "completed_at" in manager._state["tasks"]["TASK-002"]


class TestTaskDurationRecording:
    """Tests for task duration_ms recording."""

    def test_record_task_duration_basic_and_overwrite(self, tmp_path: Path) -> None:
        """Test basic duration recording and overwrite behavior."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager.set_task_status("TASK-001", TaskStatus.PENDING)
        manager.record_task_duration("TASK-001", duration_ms=5432)
        assert manager._state["tasks"]["TASK-001"]["duration_ms"] == 5432

        manager.record_task_duration("TASK-001", duration_ms=2000)
        assert manager._state["tasks"]["TASK-001"]["duration_ms"] == 2000

    def test_record_task_duration_nonexistent_task_ignored(self, tmp_path: Path) -> None:
        """Test recording duration for non-existent task is silently ignored."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager.record_task_duration("NONEXISTENT-TASK", duration_ms=1000)
        assert "NONEXISTENT-TASK" not in manager._state.get("tasks", {})


class TestGetTasksByStatus:
    """Tests for get_tasks_by_status filtering."""

    def test_get_tasks_by_status_filters_and_reflects_changes(self, tmp_path: Path) -> None:
        """Test filtering by status and that status changes are reflected."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        # Empty result
        assert manager.get_tasks_by_status(TaskStatus.PENDING) == []

        # Multiple matches
        manager.set_task_status("TASK-001", TaskStatus.PENDING)
        manager.set_task_status("TASK-002", TaskStatus.COMPLETE)
        manager.set_task_status("TASK-003", TaskStatus.PENDING)
        assert set(manager.get_tasks_by_status(TaskStatus.PENDING)) == {"TASK-001", "TASK-003"}

        # Status change reflected
        manager.set_task_status("TASK-001", TaskStatus.COMPLETE)
        assert "TASK-001" not in manager.get_tasks_by_status(TaskStatus.PENDING)
        assert "TASK-001" in manager.get_tasks_by_status(TaskStatus.COMPLETE)
