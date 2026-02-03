"""Extended tests for ZERG state management (TC-011).

Tests worker tracking, merge status, and retry functionality.
"""

import threading
from pathlib import Path

from zerg.constants import LevelMergeStatus, TaskStatus, WorkerStatus
from zerg.state import StateManager
from zerg.types import WorkerState


class TestWorkerStateTracking:
    """Tests for worker state tracking."""

    def test_set_worker_state(self, tmp_path: Path) -> None:
        """Test setting worker state."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        worker = WorkerState(
            worker_id=0,
            status=WorkerStatus.RUNNING,
            port=49152,
            worktree_path="/tmp/worktree-0",
            branch="zerg/test/worker-0",
        )
        manager.set_worker_state(worker)

        retrieved = manager.get_worker_state(0)

        assert retrieved is not None
        assert retrieved.worker_id == 0
        assert retrieved.status == WorkerStatus.RUNNING
        assert retrieved.port == 49152

    def test_get_worker_state_not_found(self, tmp_path: Path) -> None:
        """Test getting nonexistent worker state."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        retrieved = manager.get_worker_state(999)

        assert retrieved is None

    def test_get_all_workers(self, tmp_path: Path) -> None:
        """Test getting all worker states."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        for i in range(3):
            worker = WorkerState(
                worker_id=i,
                status=WorkerStatus.RUNNING,
                port=49152 + i,
            )
            manager.set_worker_state(worker)

        workers = manager.get_all_workers()

        assert len(workers) == 3
        assert 0 in workers
        assert 1 in workers
        assert 2 in workers

    def test_worker_state_persistence(self, tmp_path: Path) -> None:
        """Test worker state persists across manager instances."""
        manager1 = StateManager("test-feature", state_dir=tmp_path)
        manager1.load()

        worker = WorkerState(
            worker_id=0,
            status=WorkerStatus.RUNNING,
            port=49152,
        )
        manager1.set_worker_state(worker)

        # Create new manager
        manager2 = StateManager("test-feature", state_dir=tmp_path)
        manager2.load()

        retrieved = manager2.get_worker_state(0)

        assert retrieved is not None
        assert retrieved.worker_id == 0


class TestWorkerReadyTracking:
    """Tests for worker ready status tracking."""

    def test_set_worker_ready(self, tmp_path: Path) -> None:
        """Test marking worker as ready."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        # First create worker
        worker = WorkerState(
            worker_id=0,
            status=WorkerStatus.INITIALIZING,
            port=49152,
        )
        manager.set_worker_state(worker)

        # Mark ready
        manager.set_worker_ready(0)

        # Reload and check
        manager.load()
        worker_data = manager._state["workers"]["0"]
        assert worker_data["status"] == "ready"
        assert "ready_at" in worker_data

    def test_get_ready_workers(self, tmp_path: Path) -> None:
        """Test getting list of ready workers."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        # Create workers with different statuses
        statuses = [WorkerStatus.READY, WorkerStatus.READY, WorkerStatus.RUNNING]
        for i, status in enumerate(statuses):
            worker = WorkerState(worker_id=i, status=status, port=49152 + i)
            manager.set_worker_state(worker)

        ready = manager.get_ready_workers()

        assert len(ready) == 2
        assert 0 in ready
        assert 1 in ready
        assert 2 not in ready

    def test_wait_for_workers_ready_success(self, tmp_path: Path) -> None:
        """Test waiting for workers to become ready - success case."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        # Set up workers as ready
        for i in range(2):
            worker = WorkerState(worker_id=i, status=WorkerStatus.READY, port=49152 + i)
            manager.set_worker_state(worker)

        result = manager.wait_for_workers_ready([0, 1], timeout=1.0)

        assert result is True

    def test_wait_for_workers_ready_timeout(self, tmp_path: Path) -> None:
        """Test waiting for workers to become ready - timeout case."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        # Set up workers NOT ready
        for i in range(2):
            worker = WorkerState(worker_id=i, status=WorkerStatus.INITIALIZING, port=49152 + i)
            manager.set_worker_state(worker)

        result = manager.wait_for_workers_ready([0, 1], timeout=0.5)

        assert result is False


class TestMergeStatusTracking:
    """Tests for merge status tracking."""

    def test_set_level_merge_status(self, tmp_path: Path) -> None:
        """Test setting merge status for a level."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_level_merge_status(1, LevelMergeStatus.MERGING)

        status = manager.get_level_merge_status(1)
        assert status == LevelMergeStatus.MERGING

    def test_merge_status_progression(self, tmp_path: Path) -> None:
        """Test merge status can progress through states."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        # Progress through states
        for status in [
            LevelMergeStatus.PENDING,
            LevelMergeStatus.MERGING,
            LevelMergeStatus.REBASING,
            LevelMergeStatus.COMPLETE,
        ]:
            manager.set_level_merge_status(1, status)
            assert manager.get_level_merge_status(1) == status

    def test_merge_status_with_details(self, tmp_path: Path) -> None:
        """Test setting merge status with additional details."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        details = {
            "conflicting_files": ["src/auth.py", "src/config.py"],
            "error": "Merge conflict detected",
        }
        manager.set_level_merge_status(1, LevelMergeStatus.CONFLICT, details=details)

        manager.load()
        level_data = manager._state["levels"]["1"]
        assert level_data["merge_status"] == "conflict"
        assert level_data["merge_details"]["conflicting_files"] == ["src/auth.py", "src/config.py"]

    def test_merge_complete_sets_timestamp(self, tmp_path: Path) -> None:
        """Test that COMPLETE status sets completion timestamp."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_level_merge_status(1, LevelMergeStatus.COMPLETE)

        manager.load()
        level_data = manager._state["levels"]["1"]
        assert "merge_completed_at" in level_data

    def test_multiple_levels_independent(self, tmp_path: Path) -> None:
        """Test merge status is independent per level."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_level_merge_status(1, LevelMergeStatus.COMPLETE)
        manager.set_level_merge_status(2, LevelMergeStatus.MERGING)

        assert manager.get_level_merge_status(1) == LevelMergeStatus.COMPLETE
        assert manager.get_level_merge_status(2) == LevelMergeStatus.MERGING


class TestRetryTracking:
    """Tests for task retry tracking."""

    def test_get_retry_count_default(self, tmp_path: Path) -> None:
        """Test default retry count is zero."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        count = manager.get_task_retry_count("TASK-001")

        assert count == 0

    def test_increment_retry(self, tmp_path: Path) -> None:
        """Test incrementing retry count."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        counts = [manager.increment_task_retry("TASK-001") for _ in range(3)]

        assert counts == [1, 2, 3]

    def test_increment_retry_sets_timestamp(self, tmp_path: Path) -> None:
        """Test increment sets last_retry_at timestamp."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.increment_task_retry("TASK-001")

        manager.load()
        task_data = manager._state["tasks"]["TASK-001"]
        assert "last_retry_at" in task_data

    def test_reset_retry(self, tmp_path: Path) -> None:
        """Test resetting retry count."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.increment_task_retry("TASK-001")
        manager.increment_task_retry("TASK-001")
        manager.reset_task_retry("TASK-001")

        count = manager.get_task_retry_count("TASK-001")
        assert count == 0

    def test_reset_retry_removes_timestamp(self, tmp_path: Path) -> None:
        """Test reset removes last_retry_at timestamp."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.increment_task_retry("TASK-001")
        manager.reset_task_retry("TASK-001")

        manager.load()
        task_data = manager._state["tasks"]["TASK-001"]
        assert "last_retry_at" not in task_data

    def test_get_failed_tasks(self, tmp_path: Path) -> None:
        """Test getting all failed tasks."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        # Set up mixed task statuses
        manager.set_task_status("TASK-001", TaskStatus.FAILED, error="Error 1")
        manager.increment_task_retry("TASK-001")
        manager.set_task_status("TASK-002", TaskStatus.COMPLETE)
        manager.set_task_status("TASK-003", TaskStatus.FAILED, error="Error 3")

        failed = manager.get_failed_tasks()

        assert len(failed) == 2
        task_ids = {t["task_id"] for t in failed}
        assert task_ids == {"TASK-001", "TASK-003"}

    def test_failed_tasks_include_retry_info(self, tmp_path: Path) -> None:
        """Test failed tasks include retry information."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_task_status("TASK-001", TaskStatus.FAILED, error="Test error")
        manager.increment_task_retry("TASK-001")
        manager.increment_task_retry("TASK-001")

        failed = manager.get_failed_tasks()

        task_001 = next(t for t in failed if t["task_id"] == "TASK-001")
        assert task_001["retry_count"] == 2
        assert task_001["error"] == "Test error"
        assert "last_retry_at" in task_001


class TestLevelStatus:
    """Tests for level status tracking."""

    def test_set_level_status(self, tmp_path: Path) -> None:
        """Test setting level status."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_level_status(1, "running")

        status = manager.get_level_status(1)
        assert status["status"] == "running"

    def test_level_status_with_merge_commit(self, tmp_path: Path) -> None:
        """Test setting level status with merge commit."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_level_status(1, "complete", merge_commit="abc123")

        status = manager.get_level_status(1)
        assert status["status"] == "complete"
        assert status["merge_commit"] == "abc123"

    def test_level_running_sets_started_at(self, tmp_path: Path) -> None:
        """Test running status sets started_at."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_level_status(1, "running")

        status = manager.get_level_status(1)
        assert "started_at" in status

    def test_level_complete_sets_completed_at(self, tmp_path: Path) -> None:
        """Test complete status sets completed_at."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_level_status(1, "complete")

        status = manager.get_level_status(1)
        assert "completed_at" in status


class TestTaskClaiming:
    """Tests for task claiming with locking."""

    def test_claim_task_success(self, tmp_path: Path) -> None:
        """Test successfully claiming a task."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_task_status("TASK-001", TaskStatus.PENDING)

        result = manager.claim_task("TASK-001", worker_id=0)

        assert result is True
        assert manager.get_task_status("TASK-001") == TaskStatus.CLAIMED.value

    def test_claim_task_already_claimed(self, tmp_path: Path) -> None:
        """Test claiming already claimed task fails."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_task_status("TASK-001", TaskStatus.PENDING)
        manager.claim_task("TASK-001", worker_id=0)

        result = manager.claim_task("TASK-001", worker_id=1)

        assert result is False

    def test_claim_task_in_progress(self, tmp_path: Path) -> None:
        """Test claiming in-progress task fails."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_task_status("TASK-001", TaskStatus.IN_PROGRESS, worker_id=0)

        result = manager.claim_task("TASK-001", worker_id=1)

        assert result is False

    def test_release_task(self, tmp_path: Path) -> None:
        """Test releasing a claimed task."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_task_status("TASK-001", TaskStatus.PENDING)
        manager.claim_task("TASK-001", worker_id=0)

        manager.release_task("TASK-001", worker_id=0)

        assert manager.get_task_status("TASK-001") == TaskStatus.PENDING.value

    def test_release_task_wrong_worker(self, tmp_path: Path) -> None:
        """Test releasing task from wrong worker does nothing."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        manager.set_task_status("TASK-001", TaskStatus.PENDING)
        manager.claim_task("TASK-001", worker_id=0)

        manager.release_task("TASK-001", worker_id=1)  # Wrong worker

        # Should still be claimed
        assert manager.get_task_status("TASK-001") == TaskStatus.CLAIMED.value


class TestConcurrency:
    """Tests for thread-safe operations."""

    def test_concurrent_claims(self, tmp_path: Path) -> None:
        """Test concurrent task claims from multiple workers with shared manager."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager.set_task_status("TASK-001", TaskStatus.PENDING)
        manager.save()

        results = {}
        errors = []

        def claim_task(worker_id: int) -> None:
            try:
                # Use shared manager - threading.Lock protects same instance
                result = manager.claim_task("TASK-001", worker_id)
                results[worker_id] = result
            except Exception as e:
                errors.append((worker_id, e))

        threads = [threading.Thread(target=claim_task, args=(i,)) for i in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)  # Add timeout to prevent hanging

        # Only one should succeed
        successful = [wid for wid, success in results.items() if success]
        assert len(successful) == 1
        assert len(errors) == 0

    def test_concurrent_event_appending(self, tmp_path: Path) -> None:
        """Test concurrent event appending."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        events_added = []

        def append_event(event_id: int) -> None:
            manager.append_event(f"event_{event_id}", {"id": event_id})
            events_added.append(event_id)

        threads = [threading.Thread(target=append_event, args=(i,)) for i in range(10)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        events = manager.get_events()
        assert len(events) == 10


class TestPersistence:
    """Tests for state persistence."""

    def test_state_persists_across_instances(self, tmp_path: Path) -> None:
        """Test state persists across manager instances."""
        manager1 = StateManager("test-feature", state_dir=tmp_path)
        manager1.load()
        manager1.set_current_level(3)
        manager1.set_task_status("TASK-001", TaskStatus.COMPLETE)
        manager1.save()

        manager2 = StateManager("test-feature", state_dir=tmp_path)
        state = manager2.load()

        assert state["current_level"] == 3
        assert manager2.get_task_status("TASK-001") == TaskStatus.COMPLETE.value

    def test_delete_state(self, tmp_path: Path) -> None:
        """Test deleting state file."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager.save()

        assert manager.exists()

        manager.delete()

        assert not manager.exists()

    def test_exists_check(self, tmp_path: Path) -> None:
        """Test checking if state exists."""
        manager = StateManager("test-feature", state_dir=tmp_path)

        assert not manager.exists()

        manager.load()
        manager.save()

        assert manager.exists()
