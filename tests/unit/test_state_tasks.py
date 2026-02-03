"""Tests for task state edge cases (TC-012).

Tests covering task status retrieval, invalid transitions, timestamps, and filtering.
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from zerg.constants import TaskStatus
from zerg.state import StateManager


class TestGetTaskStatusEdgeCases:
    """Tests for get_task_status edge cases."""

    def test_get_task_status_nonexistent_task(self, tmp_path: Path) -> None:
        """Test get_task_status returns None for non-existent task."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        result = manager.get_task_status("NONEXISTENT-TASK-999")

        assert result is None

    def test_get_task_status_empty_tasks_dict(self, tmp_path: Path) -> None:
        """Test get_task_status when tasks dict is empty."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        # Verify tasks dict is empty initially
        assert manager._state.get("tasks", {}) == {}

        result = manager.get_task_status("ANY-TASK")

        assert result is None

    def test_get_task_status_missing_status_key(self, tmp_path: Path) -> None:
        """Test get_task_status when task exists but status key is missing."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        # Manually create task without status key
        manager._state["tasks"] = {"TASK-001": {"worker_id": 1}}
        manager.save()

        result = manager.get_task_status("TASK-001")

        assert result is None

    def test_get_task_status_after_reload(self, tmp_path: Path) -> None:
        """Test get_task_status works correctly after manager reload."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager.set_task_status("TASK-001", TaskStatus.PENDING)

        # Create new manager instance
        manager2 = StateManager("test-feature", state_dir=tmp_path)
        manager2.load()

        result = manager2.get_task_status("TASK-001")

        assert result == TaskStatus.PENDING.value


class TestSetTaskStatusTransitions:
    """Tests for task status transitions and validation."""

    def test_set_task_status_all_valid_statuses(self, tmp_path: Path) -> None:
        """Test set_task_status accepts all valid TaskStatus values."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        for status in TaskStatus:
            task_id = f"TASK-{status.name}"
            manager.set_task_status(task_id, status)

            result = manager.get_task_status(task_id)
            assert result == status.value, f"Failed for status {status}"

    def test_set_task_status_with_string_value(self, tmp_path: Path) -> None:
        """Test set_task_status accepts string status values."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_task_status("TASK-001", "pending")

        result = manager.get_task_status("TASK-001")
        assert result == "pending"

    def test_set_task_status_invalid_string_not_rejected(self, tmp_path: Path) -> None:
        """Test that invalid string status values are stored (no validation).

        Note: The current implementation does not validate status transitions.
        This test documents the actual behavior - invalid strings are accepted.
        """
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        # Current implementation accepts any string
        manager.set_task_status("TASK-001", "invalid_status_value")

        result = manager.get_task_status("TASK-001")
        assert result == "invalid_status_value"

    def test_set_task_status_backward_transition(self, tmp_path: Path) -> None:
        """Test backward status transition (complete -> pending).

        Note: The current implementation allows any transition.
        This documents the behavior for potential future validation.
        """
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_task_status("TASK-001", TaskStatus.COMPLETE)
        manager.set_task_status("TASK-001", TaskStatus.PENDING)

        result = manager.get_task_status("TASK-001")
        assert result == TaskStatus.PENDING.value

    def test_set_task_status_same_status(self, tmp_path: Path) -> None:
        """Test setting same status updates timestamp."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_task_status("TASK-001", TaskStatus.PENDING)
        first_update = manager._state["tasks"]["TASK-001"]["updated_at"]

        # Small delay to ensure different timestamp
        with patch("zerg.state.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 1, 27, 12, 0, 1)
            manager.set_task_status("TASK-001", TaskStatus.PENDING)

        second_update = manager._state["tasks"]["TASK-001"]["updated_at"]
        assert first_update != second_update

    def test_set_task_status_creates_task_if_not_exists(self, tmp_path: Path) -> None:
        """Test set_task_status creates task entry if it does not exist."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_task_status("NEW-TASK", TaskStatus.PENDING)

        assert "NEW-TASK" in manager._state["tasks"]
        assert manager._state["tasks"]["NEW-TASK"]["status"] == TaskStatus.PENDING.value

    def test_set_task_status_with_error_message(self, tmp_path: Path) -> None:
        """Test set_task_status stores error message for failed status."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        error_msg = "Verification command failed with exit code 1"
        manager.set_task_status("TASK-001", TaskStatus.FAILED, error=error_msg)

        task = manager._state["tasks"]["TASK-001"]
        assert task["status"] == TaskStatus.FAILED.value
        assert task["error"] == error_msg


class TestTaskClaimedAtTimestamp:
    """Tests for task claimed_at timestamp handling."""

    def test_claim_task_sets_claimed_at(self, tmp_path: Path) -> None:
        """Test claim_task sets claimed_at timestamp."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_task_status("TASK-001", TaskStatus.PENDING)
        manager.claim_task("TASK-001", worker_id=0)

        task = manager._state["tasks"]["TASK-001"]
        assert "claimed_at" in task
        # Verify it's a valid ISO timestamp
        datetime.fromisoformat(task["claimed_at"])

    def test_record_task_claimed_standalone(self, tmp_path: Path) -> None:
        """Test record_task_claimed can be called independently."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.record_task_claimed("TASK-001", worker_id=5)

        task = manager._state["tasks"]["TASK-001"]
        assert "claimed_at" in task
        assert task["worker_id"] == 5

    def test_claimed_at_preserved_on_status_change(self, tmp_path: Path) -> None:
        """Test claimed_at is preserved when status changes."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_task_status("TASK-001", TaskStatus.PENDING)
        manager.claim_task("TASK-001", worker_id=0)

        original_claimed_at = manager._state["tasks"]["TASK-001"]["claimed_at"]

        # Change status to in_progress
        manager.set_task_status("TASK-001", TaskStatus.IN_PROGRESS, worker_id=0)

        assert manager._state["tasks"]["TASK-001"]["claimed_at"] == original_claimed_at

    def test_in_progress_sets_started_at(self, tmp_path: Path) -> None:
        """Test IN_PROGRESS status sets started_at timestamp."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_task_status("TASK-001", TaskStatus.IN_PROGRESS, worker_id=0)

        task = manager._state["tasks"]["TASK-001"]
        assert "started_at" in task
        datetime.fromisoformat(task["started_at"])

    def test_complete_sets_completed_at(self, tmp_path: Path) -> None:
        """Test COMPLETE status sets completed_at timestamp."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_task_status("TASK-001", TaskStatus.COMPLETE)

        task = manager._state["tasks"]["TASK-001"]
        assert "completed_at" in task
        datetime.fromisoformat(task["completed_at"])


class TestTaskDurationRecording:
    """Tests for task duration_ms recording."""

    def test_record_task_duration_basic(self, tmp_path: Path) -> None:
        """Test basic duration recording."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_task_status("TASK-001", TaskStatus.PENDING)
        manager.record_task_duration("TASK-001", duration_ms=5432)

        task = manager._state["tasks"]["TASK-001"]
        assert task["duration_ms"] == 5432

    def test_record_task_duration_overwrites(self, tmp_path: Path) -> None:
        """Test duration recording overwrites previous value."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_task_status("TASK-001", TaskStatus.PENDING)
        manager.record_task_duration("TASK-001", duration_ms=1000)
        manager.record_task_duration("TASK-001", duration_ms=2000)

        task = manager._state["tasks"]["TASK-001"]
        assert task["duration_ms"] == 2000

    def test_record_task_duration_zero(self, tmp_path: Path) -> None:
        """Test recording zero duration."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_task_status("TASK-001", TaskStatus.PENDING)
        manager.record_task_duration("TASK-001", duration_ms=0)

        task = manager._state["tasks"]["TASK-001"]
        assert task["duration_ms"] == 0

    def test_record_task_duration_large_value(self, tmp_path: Path) -> None:
        """Test recording large duration value (e.g., 30 minute task)."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        # 30 minutes in milliseconds
        duration_30min = 30 * 60 * 1000

        manager.set_task_status("TASK-001", TaskStatus.PENDING)
        manager.record_task_duration("TASK-001", duration_ms=duration_30min)

        task = manager._state["tasks"]["TASK-001"]
        assert task["duration_ms"] == duration_30min

    def test_record_task_duration_nonexistent_task(self, tmp_path: Path) -> None:
        """Test recording duration for non-existent task is silently ignored."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        # Should not raise - silently ignored
        manager.record_task_duration("NONEXISTENT-TASK", duration_ms=1000)

        # Task should not be created
        assert "NONEXISTENT-TASK" not in manager._state.get("tasks", {})

    def test_record_task_duration_persisted(self, tmp_path: Path) -> None:
        """Test duration is persisted across manager instances."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager.set_task_status("TASK-001", TaskStatus.COMPLETE)
        manager.record_task_duration("TASK-001", duration_ms=12345)

        # Create new manager
        manager2 = StateManager("test-feature", state_dir=tmp_path)
        manager2.load()

        task = manager2._state["tasks"]["TASK-001"]
        assert task["duration_ms"] == 12345


class TestGetTasksByStatus:
    """Tests for get_tasks_by_status filtering."""

    def test_get_tasks_by_status_empty(self, tmp_path: Path) -> None:
        """Test get_tasks_by_status returns empty list when no tasks exist."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        result = manager.get_tasks_by_status(TaskStatus.PENDING)

        assert result == []

    def test_get_tasks_by_status_no_matches(self, tmp_path: Path) -> None:
        """Test get_tasks_by_status returns empty list when no tasks match."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_task_status("TASK-001", TaskStatus.COMPLETE)
        manager.set_task_status("TASK-002", TaskStatus.COMPLETE)

        result = manager.get_tasks_by_status(TaskStatus.PENDING)

        assert result == []

    def test_get_tasks_by_status_single_match(self, tmp_path: Path) -> None:
        """Test get_tasks_by_status returns single matching task."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_task_status("TASK-001", TaskStatus.PENDING)
        manager.set_task_status("TASK-002", TaskStatus.COMPLETE)

        result = manager.get_tasks_by_status(TaskStatus.PENDING)

        assert result == ["TASK-001"]

    def test_get_tasks_by_status_multiple_matches(self, tmp_path: Path) -> None:
        """Test get_tasks_by_status returns all matching tasks."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_task_status("TASK-001", TaskStatus.PENDING)
        manager.set_task_status("TASK-002", TaskStatus.COMPLETE)
        manager.set_task_status("TASK-003", TaskStatus.PENDING)
        manager.set_task_status("TASK-004", TaskStatus.FAILED)
        manager.set_task_status("TASK-005", TaskStatus.PENDING)

        result = manager.get_tasks_by_status(TaskStatus.PENDING)

        assert set(result) == {"TASK-001", "TASK-003", "TASK-005"}

    def test_get_tasks_by_status_with_string(self, tmp_path: Path) -> None:
        """Test get_tasks_by_status accepts string status value."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_task_status("TASK-001", TaskStatus.PENDING)
        manager.set_task_status("TASK-002", TaskStatus.PENDING)

        result = manager.get_tasks_by_status("pending")

        assert set(result) == {"TASK-001", "TASK-002"}

    def test_get_tasks_by_status_all_statuses(self, tmp_path: Path) -> None:
        """Test get_tasks_by_status works for all TaskStatus values."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        # Create one task for each status
        for i, status in enumerate(TaskStatus):
            manager.set_task_status(f"TASK-{i:03d}", status)

        # Verify each status returns correct task
        for i, status in enumerate(TaskStatus):
            result = manager.get_tasks_by_status(status)
            assert f"TASK-{i:03d}" in result, f"Failed for status {status}"

    def test_get_tasks_by_status_mixed_case_sensitivity(self, tmp_path: Path) -> None:
        """Test get_tasks_by_status is case-sensitive for string matching."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_task_status("TASK-001", TaskStatus.PENDING)

        # Uppercase should not match lowercase status
        result = manager.get_tasks_by_status("PENDING")

        assert result == []  # No match because stored as lowercase "pending"

    def test_get_tasks_by_status_after_status_change(self, tmp_path: Path) -> None:
        """Test get_tasks_by_status reflects status changes."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_task_status("TASK-001", TaskStatus.PENDING)

        pending_before = manager.get_tasks_by_status(TaskStatus.PENDING)
        complete_before = manager.get_tasks_by_status(TaskStatus.COMPLETE)

        assert "TASK-001" in pending_before
        assert "TASK-001" not in complete_before

        # Change status
        manager.set_task_status("TASK-001", TaskStatus.COMPLETE)

        pending_after = manager.get_tasks_by_status(TaskStatus.PENDING)
        complete_after = manager.get_tasks_by_status(TaskStatus.COMPLETE)

        assert "TASK-001" not in pending_after
        assert "TASK-001" in complete_after
