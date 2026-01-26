"""Tests for ZERG state management."""

from pathlib import Path

from zerg.constants import LevelMergeStatus, TaskStatus, WorkerStatus
from zerg.state import StateManager
from zerg.types import WorkerState


class TestStateManager:
    """Tests for StateManager."""

    def test_init(self, tmp_path: Path) -> None:
        """Test state manager initialization."""
        state_dir = tmp_path / "state"
        manager = StateManager("test-feature", state_dir=state_dir)

        assert manager.feature == "test-feature"
        assert state_dir.exists()

    def test_load_creates_initial(self, tmp_path: Path) -> None:
        """Test loading creates initial state when file doesn't exist."""
        state_dir = tmp_path / "state"
        manager = StateManager("test-feature", state_dir=state_dir)

        state = manager.load()

        assert state["feature"] == "test-feature"
        assert state["current_level"] == 0
        assert state["tasks"] == {}
        assert state["paused"] is False

    def test_save_and_load(self, tmp_path: Path) -> None:
        """Test saving and loading state."""
        state_dir = tmp_path / "state"
        manager = StateManager("test-feature", state_dir=state_dir)

        manager.load()
        manager.set_current_level(2)
        manager.save()

        # Create new manager and load
        manager2 = StateManager("test-feature", state_dir=state_dir)
        state = manager2.load()

        assert state["current_level"] == 2

    def test_set_task_status(self, tmp_path: Path) -> None:
        """Test setting task status."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_task_status("TASK-001", TaskStatus.IN_PROGRESS, worker_id=0)

        status = manager.get_task_status("TASK-001")
        assert status == TaskStatus.IN_PROGRESS.value

    def test_claim_task(self, tmp_path: Path) -> None:
        """Test claiming a task."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        # Set up pending task
        manager.set_task_status("TASK-001", TaskStatus.PENDING)

        # Claim it
        result = manager.claim_task("TASK-001", worker_id=0)

        assert result is True
        assert manager.get_task_status("TASK-001") == TaskStatus.CLAIMED.value

    def test_claim_task_already_claimed(self, tmp_path: Path) -> None:
        """Test claiming already claimed task fails."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        # Set up and claim task
        manager.set_task_status("TASK-001", TaskStatus.PENDING)
        manager.claim_task("TASK-001", worker_id=0)

        # Try to claim again
        result = manager.claim_task("TASK-001", worker_id=1)

        assert result is False

    def test_get_tasks_by_status(self, tmp_path: Path) -> None:
        """Test getting tasks by status."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_task_status("TASK-001", TaskStatus.PENDING)
        manager.set_task_status("TASK-002", TaskStatus.PENDING)
        manager.set_task_status("TASK-003", TaskStatus.COMPLETE)

        pending = manager.get_tasks_by_status(TaskStatus.PENDING)

        assert len(pending) == 2
        assert "TASK-001" in pending
        assert "TASK-002" in pending

    def test_append_event(self, tmp_path: Path) -> None:
        """Test appending events."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.append_event("test_event", {"key": "value"})

        events = manager.get_events()
        assert len(events) == 1
        assert events[0]["event"] == "test_event"
        assert events[0]["data"]["key"] == "value"


class TestMergeStatus:
    """Tests for merge status tracking."""

    def test_set_level_merge_status(self, tmp_path: Path) -> None:
        """Test setting level merge status."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_level_merge_status(1, LevelMergeStatus.MERGING)

        status = manager.get_level_merge_status(1)
        assert status == LevelMergeStatus.MERGING

    def test_get_level_merge_status_not_set(self, tmp_path: Path) -> None:
        """Test getting merge status when not set."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        status = manager.get_level_merge_status(1)
        assert status is None

    def test_set_level_merge_status_with_details(self, tmp_path: Path) -> None:
        """Test setting merge status with details."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_level_merge_status(
            1,
            LevelMergeStatus.CONFLICT,
            details={"conflicting_files": ["src/auth.py"]},
        )

        # Verify details saved
        manager.load()
        level_data = manager._state["levels"]["1"]
        assert level_data["merge_status"] == "conflict"
        assert level_data["merge_details"]["conflicting_files"] == ["src/auth.py"]

    def test_merge_status_complete_timestamp(self, tmp_path: Path) -> None:
        """Test that COMPLETE status sets timestamp."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_level_merge_status(1, LevelMergeStatus.COMPLETE)

        manager.load()
        level_data = manager._state["levels"]["1"]
        assert "merge_completed_at" in level_data


class TestRetryTracking:
    """Tests for retry count tracking."""

    def test_get_retry_count_default(self, tmp_path: Path) -> None:
        """Test default retry count is 0."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        count = manager.get_task_retry_count("TASK-001")
        assert count == 0

    def test_increment_retry(self, tmp_path: Path) -> None:
        """Test incrementing retry count."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        count1 = manager.increment_task_retry("TASK-001")
        count2 = manager.increment_task_retry("TASK-001")
        count3 = manager.increment_task_retry("TASK-001")

        assert count1 == 1
        assert count2 == 2
        assert count3 == 3

    def test_reset_retry(self, tmp_path: Path) -> None:
        """Test resetting retry count."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.increment_task_retry("TASK-001")
        manager.increment_task_retry("TASK-001")
        manager.reset_task_retry("TASK-001")

        count = manager.get_task_retry_count("TASK-001")
        assert count == 0

    def test_get_failed_tasks(self, tmp_path: Path) -> None:
        """Test getting failed tasks with retry info."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        # Set up failed tasks
        manager.set_task_status("TASK-001", TaskStatus.FAILED, error="Test error")
        manager.increment_task_retry("TASK-001")
        manager.set_task_status("TASK-002", TaskStatus.COMPLETE)
        manager.set_task_status("TASK-003", TaskStatus.FAILED, error="Another error")

        failed = manager.get_failed_tasks()

        assert len(failed) == 2
        task_ids = [t["task_id"] for t in failed]
        assert "TASK-001" in task_ids
        assert "TASK-003" in task_ids

        # Check retry info
        task_001 = next(t for t in failed if t["task_id"] == "TASK-001")
        assert task_001["retry_count"] == 1
        assert task_001["error"] == "Test error"


class TestWorkerReadyStatus:
    """Tests for worker ready status tracking."""

    def test_set_worker_ready(self, tmp_path: Path) -> None:
        """Test marking worker as ready."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        # First set up the worker
        worker_state = WorkerState(
            worker_id=0,
            status=WorkerStatus.INITIALIZING,
            port=49152,
        )
        manager.set_worker_state(worker_state)

        # Mark ready
        manager.set_worker_ready(0)

        # Verify
        manager.load()
        worker_data = manager._state["workers"]["0"]
        assert worker_data["status"] == "ready"
        assert "ready_at" in worker_data

    def test_get_ready_workers(self, tmp_path: Path) -> None:
        """Test getting ready workers."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        # Set up workers
        for i in range(3):
            worker = WorkerState(
                worker_id=i,
                status=WorkerStatus.READY if i < 2 else WorkerStatus.RUNNING,
                port=49152 + i,
            )
            manager.set_worker_state(worker)

        ready = manager.get_ready_workers()

        assert len(ready) == 2
        assert 0 in ready
        assert 1 in ready
        assert 2 not in ready
