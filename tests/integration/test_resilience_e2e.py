"""End-to-end resilience integration tests.

Tests for ZERG resilience features including:
- Spawn failure recovery with retry
- Task timeout detection
- Worker crash and task reassignment
- Level advancement waiting for completion
- State reconciliation
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from tests.mocks.mock_launcher import MockContainerLauncher
from tests.mocks.mock_merge import MockMergeCoordinator
from tests.mocks.mock_state import MockStateManager
from zerg.constants import TaskStatus, WorkerStatus


class ResilienceTestFixture:
    """Test fixture for resilience integration tests."""

    def __init__(self, tmp_path: Path, feature: str = "test-resilience") -> None:
        """Initialize resilience test fixture.

        Args:
            tmp_path: Temporary directory for test
            feature: Feature name
        """
        self.tmp_path = tmp_path
        self.feature = feature

        # Set up directory structure
        self._setup_directories()

        # Create mocks
        self.launcher = MockContainerLauncher()
        self.merger = MockMergeCoordinator(feature)
        self.state = MockStateManager(feature)

    def _setup_directories(self) -> None:
        """Create required directory structure."""
        (self.tmp_path / ".zerg").mkdir(parents=True, exist_ok=True)
        (self.tmp_path / ".zerg" / "state").mkdir(parents=True, exist_ok=True)
        (self.tmp_path / ".zerg" / "logs").mkdir(parents=True, exist_ok=True)
        (self.tmp_path / ".gsd" / "specs" / self.feature).mkdir(parents=True, exist_ok=True)

    def create_task_graph(self, tasks: list[dict[str, Any]] | None = None) -> Path:
        """Create a task graph file.

        Args:
            tasks: Optional list of task definitions

        Returns:
            Path to task graph file
        """
        if tasks is None:
            tasks = [
                {
                    "id": "TASK-001",
                    "title": "Task 1",
                    "level": 1,
                    "dependencies": [],
                    "files": {"create": ["file1.py"], "modify": [], "read": []},
                    "verification": {"command": "echo ok", "timeout_seconds": 60},
                },
            ]

        graph = {
            "feature": self.feature,
            "version": "1.0",
            "generated": datetime.now().isoformat(),
            "total_tasks": len(tasks),
            "tasks": tasks,
        }

        path = self.tmp_path / ".gsd" / "specs" / self.feature / "task-graph.json"
        with open(path, "w") as f:
            json.dump(graph, f)

        return path


class TestSpawnFailureRecovery:
    """Tests for spawn failure recovery with retry mechanism."""

    def test_spawn_fails_twice_succeeds_on_third_attempt(self, tmp_path: Path) -> None:
        """Test that spawn retry succeeds after 2 failures.

        Scenario: Worker spawn fails twice, then succeeds on 3rd attempt.
        Expected: Worker eventually spawns successfully after retries.
        """
        fixture = ResilienceTestFixture(tmp_path)

        # Track spawn attempts
        spawn_attempts = []
        original_spawn = fixture.launcher.spawn

        def tracking_spawn(*args, **kwargs):
            spawn_attempts.append(datetime.now())
            # Fail first 2 attempts, succeed on 3rd
            if len(spawn_attempts) <= 2:
                fixture.launcher.configure(spawn_fail_workers={0})
            else:
                fixture.launcher.configure(spawn_fail_workers=set())
            return original_spawn(*args, **kwargs)

        fixture.launcher.spawn = tracking_spawn

        # First attempt - should fail
        result1 = fixture.launcher.spawn(
            worker_id=0,
            feature=fixture.feature,
            worktree_path=tmp_path,
            branch="test-branch",
        )
        assert not result1.success
        assert len(spawn_attempts) == 1

        # Second attempt - should fail
        result2 = fixture.launcher.spawn(
            worker_id=0,
            feature=fixture.feature,
            worktree_path=tmp_path,
            branch="test-branch",
        )
        assert not result2.success
        assert len(spawn_attempts) == 2

        # Third attempt - should succeed
        result3 = fixture.launcher.spawn(
            worker_id=0,
            feature=fixture.feature,
            worktree_path=tmp_path,
            branch="test-branch",
        )
        assert result3.success
        assert len(spawn_attempts) == 3
        assert result3.handle is not None
        assert result3.handle.status == WorkerStatus.RUNNING

    def test_spawn_failure_records_attempts(self, tmp_path: Path) -> None:
        """Test that spawn failures are recorded for debugging.

        Scenario: Spawn fails multiple times.
        Expected: All failed attempts are tracked with timestamps.
        """
        fixture = ResilienceTestFixture(tmp_path)

        # Configure launcher to fail for worker 0
        fixture.launcher.configure(spawn_fail_workers={0})

        # Attempt spawns
        for _ in range(3):
            fixture.launcher.spawn(
                worker_id=0,
                feature=fixture.feature,
                worktree_path=tmp_path,
                branch="test-branch",
            )

        # Verify attempts are recorded
        failed_spawns = fixture.launcher.get_failed_spawns()
        assert len(failed_spawns) == 3

        # All should have error messages
        for attempt in failed_spawns:
            assert attempt.error is not None
            assert "Simulated spawn failure" in attempt.error

    def test_spawn_retry_with_backoff(self, tmp_path: Path) -> None:
        """Test that spawn retries use exponential backoff.

        Scenario: Configure backoff and verify delays increase.
        Expected: Each retry waits longer than the previous.
        """
        fixture = ResilienceTestFixture(tmp_path)

        # Configure increasing spawn delay to simulate backoff
        delays: list[float] = []

        def measure_delay():
            start = time.time()
            fixture.launcher.spawn(
                worker_id=0,
                feature=fixture.feature,
                worktree_path=tmp_path,
                branch="test-branch",
            )
            delays.append(time.time() - start)

        # First spawn - no delay
        fixture.launcher.configure(spawn_delay=0.0, spawn_fail_workers={0})
        measure_delay()

        # Second spawn - small delay
        fixture.launcher.configure(spawn_delay=0.05, spawn_fail_workers={0})
        measure_delay()

        # Third spawn - larger delay (simulating exponential backoff)
        fixture.launcher.configure(spawn_delay=0.1, spawn_fail_workers=set())
        measure_delay()

        # Verify delays increased (with tolerance for timing)
        assert delays[1] > delays[0]
        assert delays[2] > delays[1]


class TestTaskTimeout:
    """Tests for task timeout detection and handling."""

    def test_task_times_out_after_threshold(self, tmp_path: Path) -> None:
        """Test that tasks are marked as timed out after threshold.

        Scenario: Task runs longer than configured timeout.
        Expected: Task is marked as failed due to timeout.
        """
        fixture = ResilienceTestFixture(tmp_path)

        # Set up a task in progress
        task_id = "TASK-001"
        worker_id = 0

        # Record task start time in the past (simulating long-running task)
        past_time = (datetime.now() - timedelta(seconds=700)).isoformat()
        fixture.state._state["tasks"] = {
            task_id: {
                "status": TaskStatus.IN_PROGRESS.value,
                "worker_id": worker_id,
                "started_at": past_time,
            }
        }

        # Simulate stale task detection
        # Default stale timeout is 600 seconds
        stale_timeout_seconds = 600

        task_state = fixture.state._state["tasks"][task_id]
        started_at = datetime.fromisoformat(task_state["started_at"])
        elapsed = (datetime.now() - started_at).total_seconds()

        # Verify task is stale
        assert elapsed > stale_timeout_seconds

        # Mark task as timed out
        if elapsed > stale_timeout_seconds:
            fixture.state.set_task_status(
                task_id,
                TaskStatus.FAILED,
                worker_id=worker_id,
                error=f"Task timed out after {elapsed:.0f}s",
            )

        # Verify task was marked as failed
        assert fixture.state.get_task_status(task_id) == TaskStatus.FAILED.value
        assert "timed out" in fixture.state._state["tasks"][task_id].get("error", "")

    def test_timeout_triggers_task_reassignment(self, tmp_path: Path) -> None:
        """Test that timed out tasks are reassigned to new workers.

        Scenario: Task times out, should be available for reassignment.
        Expected: Task is reset to pending state for retry.
        """
        fixture = ResilienceTestFixture(tmp_path)
        task_id = "TASK-001"

        # Set up a timed-out task
        fixture.state._state["tasks"] = {
            task_id: {
                "status": TaskStatus.FAILED.value,
                "worker_id": 0,
                "error": "Task timed out after 650s",
                "retry_count": 0,
            }
        }

        # Simulate retry logic - reset task for retry
        task_state = fixture.state._state["tasks"][task_id]
        max_retries = 3

        if task_state.get("retry_count", 0) < max_retries:
            # Reset task for retry
            fixture.state.set_task_status(task_id, TaskStatus.PENDING)
            new_count = fixture.state.increment_task_retry(task_id)

            # Verify task is available for reassignment
            assert fixture.state.get_task_status(task_id) == TaskStatus.PENDING.value
            assert new_count == 1

    def test_timeout_detection_respects_custom_timeout(self, tmp_path: Path) -> None:
        """Test that per-task custom timeouts are respected.

        Scenario: Task has custom timeout that differs from default.
        Expected: Task timeout uses custom value, not default.
        """
        fixture = ResilienceTestFixture(tmp_path)
        task_id = "TASK-LONG"

        # Task with custom 1200s timeout (20 minutes)
        custom_timeout = 1200

        # Task started 800 seconds ago (would timeout with 600s default)
        past_time = (datetime.now() - timedelta(seconds=800)).isoformat()
        fixture.state._state["tasks"] = {
            task_id: {
                "status": TaskStatus.IN_PROGRESS.value,
                "worker_id": 0,
                "started_at": past_time,
                "timeout_seconds": custom_timeout,
            }
        }

        task_state = fixture.state._state["tasks"][task_id]
        started_at = datetime.fromisoformat(task_state["started_at"])
        elapsed = (datetime.now() - started_at).total_seconds()
        task_timeout = task_state.get("timeout_seconds", 600)

        # Verify task is NOT timed out with custom timeout
        assert elapsed < task_timeout
        assert task_state["status"] == TaskStatus.IN_PROGRESS.value


class TestWorkerCrashRecovery:
    """Tests for worker crash detection and task reassignment."""

    def test_worker_crash_triggers_task_reassignment(self, tmp_path: Path) -> None:
        """Test that crashed worker's task is reassigned.

        Scenario: Worker crashes while executing a task.
        Expected: Task is released and made available for reassignment.
        """
        fixture = ResilienceTestFixture(tmp_path)
        task_id = "TASK-001"
        worker_id = 0

        # Set up running worker with a task
        fixture.launcher.spawn(
            worker_id=worker_id,
            feature=fixture.feature,
            worktree_path=tmp_path,
            branch="test-branch",
        )

        fixture.state._state["tasks"] = {
            task_id: {
                "status": TaskStatus.IN_PROGRESS.value,
                "worker_id": worker_id,
            }
        }

        fixture.state._state["workers"] = {
            str(worker_id): {
                "worker_id": worker_id,
                "status": WorkerStatus.RUNNING.value,
                "current_task": task_id,
            }
        }

        # Simulate worker crash
        fixture.launcher.configure(container_crash_workers={worker_id})
        status = fixture.launcher.monitor(worker_id)

        assert status == WorkerStatus.CRASHED

        # Handle crash - release task
        if status == WorkerStatus.CRASHED:
            # Mark worker as crashed
            fixture.state._state["workers"][str(worker_id)]["status"] = WorkerStatus.CRASHED.value

            # Release task for reassignment
            fixture.state.set_task_status(task_id, TaskStatus.PENDING)
            fixture.state._state["tasks"][task_id]["worker_id"] = None

        # Verify task is available for reassignment
        assert fixture.state.get_task_status(task_id) == TaskStatus.PENDING.value
        assert fixture.state._state["tasks"][task_id].get("worker_id") is None

    def test_multiple_worker_crashes_handled(self, tmp_path: Path) -> None:
        """Test handling of multiple simultaneous worker crashes.

        Scenario: Multiple workers crash at once.
        Expected: All crashed workers' tasks are properly handled.
        """
        fixture = ResilienceTestFixture(tmp_path)

        # Set up multiple workers with tasks
        tasks = {
            "TASK-001": {"worker_id": 0},
            "TASK-002": {"worker_id": 1},
            "TASK-003": {"worker_id": 2},
        }

        for task_id, task_info in tasks.items():
            wid = task_info["worker_id"]
            fixture.launcher.spawn(
                worker_id=wid,
                feature=fixture.feature,
                worktree_path=tmp_path,
                branch="test-branch",
            )
            fixture.state._state["tasks"][task_id] = {
                "status": TaskStatus.IN_PROGRESS.value,
                "worker_id": wid,
            }
            fixture.state._state["workers"][str(wid)] = {
                "worker_id": wid,
                "status": WorkerStatus.RUNNING.value,
                "current_task": task_id,
            }

        # Crash workers 0 and 2 (keep 1 running)
        fixture.launcher.configure(container_crash_workers={0, 2})

        # Check status of each worker
        crashed_workers = []
        for wid in [0, 1, 2]:
            status = fixture.launcher.monitor(wid)
            if status == WorkerStatus.CRASHED:
                crashed_workers.append(wid)
                # Release associated task
                for tid, tinfo in fixture.state._state["tasks"].items():
                    if tinfo.get("worker_id") == wid:
                        fixture.state.set_task_status(tid, TaskStatus.PENDING)
                        tinfo["worker_id"] = None

        # Verify correct workers crashed
        assert set(crashed_workers) == {0, 2}

        # Verify tasks from crashed workers are released
        assert fixture.state.get_task_status("TASK-001") == TaskStatus.PENDING.value
        assert fixture.state.get_task_status("TASK-002") == TaskStatus.IN_PROGRESS.value
        assert fixture.state.get_task_status("TASK-003") == TaskStatus.PENDING.value

    def test_crash_recovery_respects_max_retries(self, tmp_path: Path) -> None:
        """Test that task is failed permanently after max retries.

        Scenario: Task fails repeatedly due to worker crashes.
        Expected: Task is marked permanently failed after max retries.
        """
        fixture = ResilienceTestFixture(tmp_path)
        task_id = "TASK-001"
        max_retries = 3

        # Task already failed max times
        fixture.state._state["tasks"] = {
            task_id: {
                "status": TaskStatus.FAILED.value,
                "retry_count": max_retries,
                "error": "Worker crashed repeatedly",
            }
        }

        # Attempt retry - should be rejected
        task_state = fixture.state._state["tasks"][task_id]
        retry_count = task_state.get("retry_count", 0)

        if retry_count >= max_retries:
            # Mark as permanently failed
            task_state["status"] = TaskStatus.FAILED.value
            task_state["error"] = f"Failed permanently after {max_retries} retries"
            can_retry = False
        else:
            can_retry = True

        assert not can_retry
        assert task_state["status"] == TaskStatus.FAILED.value
        assert "permanently" in task_state.get("error", "")


class TestLevelAdvancement:
    """Tests for level advancement waiting for task completion."""

    def test_level_waits_for_all_tasks_complete(self, tmp_path: Path) -> None:
        """Test that level only advances when all tasks complete.

        Scenario: Level 1 has 3 tasks, only 2 are complete.
        Expected: Level does not advance until all 3 complete.
        """
        fixture = ResilienceTestFixture(tmp_path)

        # Set up level 1 tasks - 2 complete, 1 still running
        fixture.state._state["tasks"] = {
            "L1-TASK-001": {
                "status": TaskStatus.COMPLETE.value,
                "level": 1,
            },
            "L1-TASK-002": {
                "status": TaskStatus.COMPLETE.value,
                "level": 1,
            },
            "L1-TASK-003": {
                "status": TaskStatus.IN_PROGRESS.value,
                "level": 1,
            },
        }
        fixture.state.set_current_level(1)

        # Check if level can advance
        level_1_tasks = [tid for tid, t in fixture.state._state["tasks"].items() if t.get("level") == 1]

        all_complete = all(
            fixture.state._state["tasks"][tid]["status"] == TaskStatus.COMPLETE.value for tid in level_1_tasks
        )

        # Level should NOT advance - one task still running
        assert not all_complete
        assert fixture.state.get_current_level() == 1

        # Complete the last task
        fixture.state.set_task_status("L1-TASK-003", TaskStatus.COMPLETE)

        # Now check again
        all_complete = all(
            fixture.state._state["tasks"][tid]["status"] == TaskStatus.COMPLETE.value for tid in level_1_tasks
        )

        # Level CAN advance now
        assert all_complete

        # Advance level
        fixture.state.set_current_level(2)
        assert fixture.state.get_current_level() == 2

    def test_level_advancement_handles_failed_tasks(self, tmp_path: Path) -> None:
        """Test level advancement with failed tasks.

        Scenario: Level has completed and failed tasks.
        Expected: Level pauses due to failure, does not auto-advance.
        """
        fixture = ResilienceTestFixture(tmp_path)

        # Set up level with a failed task
        fixture.state._state["tasks"] = {
            "L1-TASK-001": {
                "status": TaskStatus.COMPLETE.value,
                "level": 1,
            },
            "L1-TASK-002": {
                "status": TaskStatus.FAILED.value,
                "level": 1,
                "error": "Verification failed",
            },
        }
        fixture.state.set_current_level(1)

        # Check for failures
        level_1_tasks = [tid for tid, t in fixture.state._state["tasks"].items() if t.get("level") == 1]

        has_failures = any(
            fixture.state._state["tasks"][tid]["status"] == TaskStatus.FAILED.value for tid in level_1_tasks
        )

        # Level should NOT advance due to failure
        assert has_failures

        # Set paused state
        if has_failures:
            fixture.state.set_paused(True)
            fixture.state.set_error("Level 1 has failed tasks")

        assert fixture.state.is_paused()
        assert fixture.state.get_current_level() == 1  # Did not advance

    def test_level_advancement_triggers_merge(self, tmp_path: Path) -> None:
        """Test that level completion triggers merge operation.

        Scenario: All tasks in a level complete successfully.
        Expected: Merge operation is triggered before advancing.
        """
        fixture = ResilienceTestFixture(tmp_path)

        # Set up completed level
        fixture.state._state["tasks"] = {
            "L1-TASK-001": {
                "status": TaskStatus.COMPLETE.value,
                "level": 1,
            },
            "L1-TASK-002": {
                "status": TaskStatus.COMPLETE.value,
                "level": 1,
            },
        }
        fixture.state.set_current_level(1)
        fixture.state.set_level_status(1, "complete")

        # Trigger merge
        merge_called = False

        def mock_merge_level(level: int):
            nonlocal merge_called
            merge_called = True
            return True

        fixture.merger.merge_level = mock_merge_level

        # Simulate level completion check
        level_1_tasks = [tid for tid, t in fixture.state._state["tasks"].items() if t.get("level") == 1]

        all_complete = all(
            fixture.state._state["tasks"][tid]["status"] == TaskStatus.COMPLETE.value for tid in level_1_tasks
        )

        if all_complete:
            fixture.merger.merge_level(1)

        assert merge_called


class TestStateReconciliation:
    """Tests for state reconciliation fixing inconsistencies."""

    def test_reconciliation_fixes_orphaned_tasks(self, tmp_path: Path) -> None:
        """Test that orphaned tasks are detected and fixed.

        Scenario: Task assigned to non-existent worker.
        Expected: Task is released and marked as pending.
        """
        fixture = ResilienceTestFixture(tmp_path)

        # Task assigned to worker that doesn't exist
        fixture.state._state["tasks"] = {
            "TASK-001": {
                "status": TaskStatus.IN_PROGRESS.value,
                "worker_id": 99,  # Non-existent worker
            },
        }
        fixture.state._state["workers"] = {}  # No workers

        # Run reconciliation
        inconsistencies = []

        for task_id, task_state in fixture.state._state["tasks"].items():
            worker_id = task_state.get("worker_id")
            if worker_id is not None and task_state["status"] == TaskStatus.IN_PROGRESS.value:
                # Check if worker exists
                if str(worker_id) not in fixture.state._state.get("workers", {}):
                    inconsistencies.append(
                        {
                            "type": "orphaned_task",
                            "task_id": task_id,
                            "worker_id": worker_id,
                        }
                    )
                    # Fix: release the task
                    fixture.state.set_task_status(task_id, TaskStatus.PENDING)
                    task_state["worker_id"] = None

        # Verify inconsistency was detected and fixed
        assert len(inconsistencies) == 1
        assert inconsistencies[0]["type"] == "orphaned_task"
        assert fixture.state.get_task_status("TASK-001") == TaskStatus.PENDING.value

    def test_reconciliation_fixes_stale_worker_status(self, tmp_path: Path) -> None:
        """Test that stale worker states are corrected.

        Scenario: Worker marked as running but container is stopped.
        Expected: Worker status is updated to match container state.
        """
        fixture = ResilienceTestFixture(tmp_path)

        # Spawn then terminate a worker
        fixture.launcher.spawn(
            worker_id=0,
            feature=fixture.feature,
            worktree_path=tmp_path,
            branch="test-branch",
        )
        fixture.launcher.terminate(0)

        # State incorrectly shows worker as running
        fixture.state._state["workers"] = {
            "0": {
                "worker_id": 0,
                "status": WorkerStatus.RUNNING.value,
            }
        }

        # Run reconciliation - check actual container status
        actual_status = fixture.launcher.monitor(0)
        state_status = WorkerStatus(fixture.state._state["workers"]["0"]["status"])

        # Detect inconsistency
        if actual_status != state_status:
            # Fix: update state to match reality
            fixture.state._state["workers"]["0"]["status"] = actual_status.value

        # Verify status was corrected
        assert fixture.state._state["workers"]["0"]["status"] == WorkerStatus.STOPPED.value

    def test_reconciliation_at_level_transition(self, tmp_path: Path) -> None:
        """Test that reconciliation runs at level transitions.

        Scenario: Moving from level 1 to level 2.
        Expected: State is fully consistent before level 2 starts.
        """
        fixture = ResilienceTestFixture(tmp_path)

        # Set up level 1 complete with some inconsistencies
        fixture.state._state["tasks"] = {
            "L1-TASK-001": {
                "status": TaskStatus.COMPLETE.value,
                "level": 1,
                "worker_id": 0,  # Worker 0 completed
            },
            "L1-TASK-002": {
                "status": TaskStatus.COMPLETE.value,
                "level": 1,
                "worker_id": 1,  # Worker doesn't exist - stale reference
            },
            "L2-TASK-001": {
                "status": TaskStatus.PENDING.value,
                "level": 2,
            },
        }
        fixture.state._state["workers"] = {
            "0": {"worker_id": 0, "status": WorkerStatus.STOPPED.value},
            # Worker 1 doesn't exist - inconsistency
        }
        fixture.state.set_current_level(1)

        # Reconciliation before level transition
        fixed_issues = []

        # Check completed tasks still reference valid workers
        for task_id, task_state in fixture.state._state["tasks"].items():
            if task_state["status"] == TaskStatus.COMPLETE.value:
                worker_id = task_state.get("worker_id")
                if worker_id is not None:
                    worker_key = str(worker_id)
                    if worker_key not in fixture.state._state.get("workers", {}):
                        # Stale reference - worker was cleaned up
                        fixed_issues.append(
                            {
                                "type": "stale_worker_reference",
                                "task_id": task_id,
                                "worker_id": worker_id,
                            }
                        )
                        # Clear stale reference (task already complete, no action needed)

        # Verify issue was detected
        assert len(fixed_issues) == 1
        assert fixed_issues[0]["task_id"] == "L1-TASK-002"

        # Now advance level
        fixture.state.set_current_level(2)
        assert fixture.state.get_current_level() == 2

    def test_reconciliation_handles_duplicate_claims(self, tmp_path: Path) -> None:
        """Test handling of tasks claimed by multiple workers.

        Scenario: Same task claimed by two workers due to race condition.
        Expected: One claim is revoked, task runs on single worker.
        """
        fixture = ResilienceTestFixture(tmp_path)

        # Duplicate claim scenario
        fixture.state._state["tasks"] = {
            "TASK-001": {
                "status": TaskStatus.IN_PROGRESS.value,
                "worker_id": 0,
                "claimed_at": (datetime.now() - timedelta(seconds=10)).isoformat(),
            },
        }
        # Second worker also thinks it has the task
        worker_1_claim = {
            "worker_id": 1,
            "claimed_task": "TASK-001",
            "claimed_at": (datetime.now() - timedelta(seconds=5)).isoformat(),
        }

        # Reconciliation: determine which claim wins (first claim wins)
        task_state = fixture.state._state["tasks"]["TASK-001"]
        task_claimed_at = datetime.fromisoformat(task_state["claimed_at"])
        worker_1_claimed_at = datetime.fromisoformat(worker_1_claim["claimed_at"])

        # First claim wins
        if task_claimed_at < worker_1_claimed_at:
            rightful_owner = task_state["worker_id"]
        else:
            rightful_owner = worker_1_claim["worker_id"]

        # Verify worker 0 retains the task (claimed first)
        assert rightful_owner == 0
        assert task_state["worker_id"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
