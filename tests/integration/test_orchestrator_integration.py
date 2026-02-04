"""Integration tests for Orchestrator failure handling.

Tests cover:
1. Orchestrator recovery from worker crash
2. Orchestrator pause on merge failure
3. Orchestrator resume after fix
4. Level advancement after recovery
5. Metrics collection through failures
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from tests.mocks import MockContainerLauncher, MockMergeCoordinator, MockStateManager
from zerg.constants import TaskStatus, WorkerStatus
from zerg.orchestrator import Orchestrator


class OrchestratorTestFixture:
    """Test fixture providing orchestrator with mocked dependencies."""

    def __init__(self, tmp_path: Path, feature: str = "test-feature") -> None:
        """Initialize test fixture.

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

        # Create orchestrator with mocked dependencies
        self.orchestrator: Orchestrator | None = None

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
                    "verification": {"command": "echo ok"},
                },
                {
                    "id": "TASK-002",
                    "title": "Task 2",
                    "level": 1,
                    "dependencies": [],
                    "files": {"create": ["file2.py"], "modify": [], "read": []},
                    "verification": {"command": "echo ok"},
                },
                {
                    "id": "TASK-003",
                    "title": "Task 3",
                    "level": 2,
                    "dependencies": ["TASK-001", "TASK-002"],
                    "files": {"create": ["file3.py"], "modify": [], "read": []},
                    "verification": {"command": "echo ok"},
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


@pytest.fixture
def test_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> OrchestratorTestFixture:
    """Create test fixture with mocked dependencies.

    Args:
        tmp_path: Pytest temporary path fixture
        monkeypatch: Pytest monkeypatch fixture

    Returns:
        OrchestratorTestFixture instance
    """
    monkeypatch.chdir(tmp_path)
    return OrchestratorTestFixture(tmp_path)


class TestOrchestratorWorkerCrashRecovery:
    """Test orchestrator recovery from worker crashes."""

    def test_worker_crash_marks_task_for_retry(self, test_fixture: OrchestratorTestFixture) -> None:
        """Worker crash should mark current task for retry."""
        with (
            patch("zerg.orchestrator.StateManager") as state_cls,
            patch("zerg.orchestrator.LevelController") as levels_cls,
            patch("zerg.orchestrator.TaskParser") as parser_cls,
            patch("zerg.orchestrator.WorktreeManager") as worktree_cls,
            patch("zerg.orchestrator.PortAllocator") as ports_cls,
            patch("zerg.orchestrator.MergeCoordinator") as merge_cls,
            patch("zerg.orchestrator.SubprocessLauncher") as launcher_cls,
            patch("zerg.orchestrator.GateRunner"),
            patch("zerg.orchestrator.ContainerManager"),
            patch("zerg.orchestrator.TaskSyncBridge"),
        ):
            # Configure mocks
            state_mock = MagicMock()
            state_mock.load.return_value = {}
            state_mock.get_task_retry_count.return_value = 0
            state_mock.increment_task_retry.return_value = 1
            state_mock.get_tasks_ready_for_retry.return_value = []
            state_cls.return_value = state_mock

            levels_mock = MagicMock()
            levels_mock.current_level = 1
            levels_cls.return_value = levels_mock

            parser_mock = MagicMock()
            parser_mock.get_task.return_value = {"id": "TASK-001", "verification": {"command": "echo ok"}}
            parser_cls.return_value = parser_mock

            worktree_mock = MagicMock()
            wt_info = MagicMock()
            wt_info.path = test_fixture.tmp_path / "worktree"
            wt_info.branch = "test-branch"
            worktree_mock.create.return_value = wt_info
            worktree_cls.return_value = worktree_mock

            ports_mock = MagicMock()
            ports_mock.allocate_one.return_value = 50000
            ports_cls.return_value = ports_mock

            merge_cls.return_value = MagicMock()

            # Configure launcher to simulate crash
            launcher_mock = MagicMock()
            spawn_result = MagicMock()
            spawn_result.success = True
            spawn_result.handle = MagicMock()
            spawn_result.handle.container_id = None
            launcher_mock.spawn.return_value = spawn_result
            launcher_mock.monitor.return_value = WorkerStatus.CRASHED
            launcher_mock.sync_state.return_value = None
            launcher_cls.return_value = launcher_mock

            # Create orchestrator
            orch = Orchestrator(test_fixture.feature)

            # Spawn a worker
            worker_state = orch._spawn_worker(0)
            worker_state.current_task = "TASK-001"
            orch._workers[0] = worker_state

            # Poll should detect crash
            orch._poll_workers()

            # Verify crash handling: task marked FAILED then reset to PENDING
            # Worker crashes do NOT increment retry count (infrastructure failure)
            state_mock.increment_task_retry.assert_not_called()

            # Verify task was marked failed then reset to pending
            # Filter to only TASK-001 status changes
            task_status_calls = [c for c in state_mock.set_task_status.call_args_list if c[0][0] == "TASK-001"]
            # Should have FAILED then PENDING (crash handling pattern)
            failed_calls = [c for c in task_status_calls if c[0][1] == TaskStatus.FAILED]
            pending_calls = [c for c in task_status_calls if c[0][1] == TaskStatus.PENDING]
            assert len(failed_calls) >= 1, "Task should be marked FAILED on crash"
            assert len(pending_calls) >= 1, "Task should be reset to PENDING after crash"
            # FAILED should include the crash error
            assert "Worker crashed" in failed_calls[0][1].get("error", "")

            # Verify crash event was recorded
            state_mock.append_event.assert_called()
            event_calls = [c for c in state_mock.append_event.call_args_list if c[0][0] == "task_crash_reassign"]
            assert len(event_calls) == 1
            assert event_calls[0][0][1]["task_id"] == "TASK-001"
            assert event_calls[0][0][1]["retry_count_incremented"] is False

    def test_worker_crash_respawns_worker(self, test_fixture: OrchestratorTestFixture) -> None:
        """Worker crash should trigger respawn if tasks remain."""
        with (
            patch("zerg.orchestrator.StateManager") as state_cls,
            patch("zerg.orchestrator.LevelController") as levels_cls,
            patch("zerg.orchestrator.TaskParser") as parser_cls,
            patch("zerg.orchestrator.WorktreeManager") as worktree_cls,
            patch("zerg.orchestrator.PortAllocator") as ports_cls,
            patch("zerg.orchestrator.MergeCoordinator") as merge_cls,
            patch("zerg.orchestrator.SubprocessLauncher") as launcher_cls,
            patch("zerg.orchestrator.GateRunner"),
            patch("zerg.orchestrator.ContainerManager"),
            patch("zerg.orchestrator.TaskSyncBridge"),
        ):
            # Configure mocks
            state_mock = MagicMock()
            state_mock.load.return_value = {}
            state_mock.get_task_retry_count.return_value = 0
            state_mock._state = {"tasks": {}}
            state_cls.return_value = state_mock

            levels_mock = MagicMock()
            levels_mock.current_level = 1
            levels_mock.get_pending_tasks_for_level.return_value = ["TASK-002"]
            levels_cls.return_value = levels_mock

            parser_mock = MagicMock()
            parser_mock.get_task.return_value = None
            parser_cls.return_value = parser_mock

            worktree_mock = MagicMock()
            wt_info = MagicMock()
            wt_info.path = test_fixture.tmp_path / "worktree"
            wt_info.branch = "test-branch"
            worktree_mock.create.return_value = wt_info
            worktree_mock.get_worktree_path.return_value = test_fixture.tmp_path / "worktree"
            worktree_cls.return_value = worktree_mock

            ports_mock = MagicMock()
            ports_mock.allocate_one.return_value = 50000
            ports_cls.return_value = ports_mock

            merge_cls.return_value = MagicMock()

            # Configure launcher
            launcher_mock = MagicMock()
            spawn_result = MagicMock()
            spawn_result.success = True
            spawn_result.handle = MagicMock()
            spawn_result.handle.container_id = None
            launcher_mock.spawn.return_value = spawn_result
            # First call returns CRASHED, subsequent returns RUNNING
            launcher_mock.monitor.side_effect = [WorkerStatus.CRASHED, WorkerStatus.RUNNING]
            launcher_mock.sync_state.return_value = None
            launcher_cls.return_value = launcher_mock

            # Create orchestrator
            orch = Orchestrator(test_fixture.feature)
            orch._running = True
            orch._worker_manager.running = True

            # Spawn initial worker
            worker_state = orch._spawn_worker(0)
            worker_state.current_task = None  # No current task
            orch._workers[0] = worker_state

            # Poll should detect crash and handle exit
            orch._poll_workers()

            # Verify respawn was attempted (spawn called again after initial)
            assert launcher_mock.spawn.call_count >= 2


class TestOrchestratorResumeAfterFix:
    """Test orchestrator resume functionality."""

    def test_resume_clears_paused_state(self, test_fixture: OrchestratorTestFixture) -> None:
        """Resume should clear paused state."""
        with (
            patch("zerg.orchestrator.StateManager") as state_cls,
            patch("zerg.orchestrator.LevelController"),
            patch("zerg.orchestrator.TaskParser"),
            patch("zerg.orchestrator.WorktreeManager"),
            patch("zerg.orchestrator.PortAllocator"),
            patch("zerg.orchestrator.MergeCoordinator"),
            patch("zerg.orchestrator.SubprocessLauncher"),
            patch("zerg.orchestrator.GateRunner"),
            patch("zerg.orchestrator.ContainerManager"),
            patch("zerg.orchestrator.TaskSyncBridge"),
        ):
            state_mock = MagicMock()
            state_mock.load.return_value = {}
            state_cls.return_value = state_mock

            orch = Orchestrator(test_fixture.feature)
            orch._paused = True

            orch.resume()

            assert orch._paused is False
            state_mock.set_paused.assert_called_with(False)
            state_mock.append_event.assert_called_with("resumed", {})

    def test_resume_does_nothing_if_not_paused(self, test_fixture: OrchestratorTestFixture) -> None:
        """Resume should do nothing if not paused."""
        with (
            patch("zerg.orchestrator.StateManager") as state_cls,
            patch("zerg.orchestrator.LevelController"),
            patch("zerg.orchestrator.TaskParser"),
            patch("zerg.orchestrator.WorktreeManager"),
            patch("zerg.orchestrator.PortAllocator"),
            patch("zerg.orchestrator.MergeCoordinator"),
            patch("zerg.orchestrator.SubprocessLauncher"),
            patch("zerg.orchestrator.GateRunner"),
            patch("zerg.orchestrator.ContainerManager"),
            patch("zerg.orchestrator.TaskSyncBridge"),
        ):
            state_mock = MagicMock()
            state_mock.load.return_value = {}
            state_cls.return_value = state_mock

            orch = Orchestrator(test_fixture.feature)
            orch._paused = False

            orch.resume()

            # set_paused should not be called since we weren't paused
            state_mock.set_paused.assert_not_called()

    def test_retry_failed_task_after_pause(self, test_fixture: OrchestratorTestFixture) -> None:
        """Can retry failed tasks after resuming from pause."""
        with (
            patch("zerg.orchestrator.StateManager") as state_cls,
            patch("zerg.orchestrator.LevelController"),
            patch("zerg.orchestrator.TaskParser"),
            patch("zerg.orchestrator.WorktreeManager"),
            patch("zerg.orchestrator.PortAllocator"),
            patch("zerg.orchestrator.MergeCoordinator"),
            patch("zerg.orchestrator.SubprocessLauncher"),
            patch("zerg.orchestrator.GateRunner"),
            patch("zerg.orchestrator.ContainerManager"),
            patch("zerg.orchestrator.TaskSyncBridge"),
        ):
            state_mock = MagicMock()
            state_mock.load.return_value = {}
            state_mock.get_task_status.return_value = "failed"
            state_mock.get_failed_tasks.return_value = [
                {"task_id": "TASK-001", "retry_count": 1, "error": "test error"},
            ]
            state_cls.return_value = state_mock

            orch = Orchestrator(test_fixture.feature)
            orch._paused = True

            # Resume first
            orch.resume()

            # Retry failed task
            result = orch.retry_task("TASK-001")

            assert result is True
            state_mock.reset_task_retry.assert_called_with("TASK-001")
            state_mock.set_task_status.assert_called_with("TASK-001", TaskStatus.PENDING)


class TestMetricsCollectionThroughFailures:
    """Test metrics collection during failure scenarios."""

    def test_metrics_available_in_status_during_failure(self, test_fixture: OrchestratorTestFixture) -> None:
        """Metrics should be available in status even during failures."""
        with (
            patch("zerg.orchestrator.StateManager") as state_cls,
            patch("zerg.orchestrator.LevelController") as levels_cls,
            patch("zerg.orchestrator.TaskParser"),
            patch("zerg.orchestrator.WorktreeManager"),
            patch("zerg.orchestrator.PortAllocator"),
            patch("zerg.orchestrator.MergeCoordinator"),
            patch("zerg.orchestrator.SubprocessLauncher"),
            patch("zerg.orchestrator.GateRunner"),
            patch("zerg.orchestrator.ContainerManager"),
            patch("zerg.orchestrator.TaskSyncBridge"),
            patch("zerg.orchestrator.MetricsCollector") as metrics_cls,
        ):
            state_mock = MagicMock()
            state_mock.load.return_value = {}
            state_cls.return_value = state_mock

            levels_mock = MagicMock()
            levels_mock.current_level = 1
            levels_mock.get_status.return_value = {
                "current_level": 1,
                "total_tasks": 3,
                "completed_tasks": 1,
                "failed_tasks": 1,
                "in_progress_tasks": 0,
                "progress_percent": 33,
                "is_complete": False,
                "levels": {},
            }
            levels_cls.return_value = levels_mock

            # Configure metrics for failed state
            metrics_mock = MagicMock()
            feature_metrics = MagicMock()
            feature_metrics.tasks_completed = 1
            feature_metrics.tasks_total = 3
            feature_metrics.tasks_failed = 1
            feature_metrics.total_duration_ms = 3000
            feature_metrics.to_dict.return_value = {
                "tasks_completed": 1,
                "tasks_total": 3,
                "tasks_failed": 1,
                "total_duration_ms": 3000,
            }
            metrics_mock.compute_feature_metrics.return_value = feature_metrics
            metrics_cls.return_value = metrics_mock

            orch = Orchestrator(test_fixture.feature)
            orch._paused = True  # Simulate paused due to failure

            status = orch.status()

            assert status["metrics"] is not None
            assert status["metrics"]["tasks_completed"] == 1
            assert status["metrics"]["tasks_failed"] == 1

    def test_metrics_track_failed_tasks(self, test_fixture: OrchestratorTestFixture) -> None:
        """Metrics should track failed tasks correctly."""
        with (
            patch("zerg.orchestrator.StateManager") as state_cls,
            patch("zerg.orchestrator.LevelController") as levels_cls,
            patch("zerg.orchestrator.TaskParser"),
            patch("zerg.orchestrator.WorktreeManager"),
            patch("zerg.orchestrator.PortAllocator"),
            patch("zerg.orchestrator.MergeCoordinator"),
            patch("zerg.orchestrator.SubprocessLauncher"),
            patch("zerg.orchestrator.GateRunner"),
            patch("zerg.orchestrator.ContainerManager"),
            patch("zerg.orchestrator.TaskSyncBridge"),
        ):
            state_mock = MagicMock()
            state_mock.load.return_value = {}
            state_mock.get_task_retry_count.return_value = 3  # At max retries
            state_cls.return_value = state_mock

            levels_mock = MagicMock()
            levels_mock.current_level = 1
            levels_cls.return_value = levels_mock

            orch = Orchestrator(test_fixture.feature)

            # Handle task failure that exceeds retry limit
            will_retry = orch._handle_task_failure("TASK-001", 0, "Final failure")

            assert will_retry is False

            # Verify permanent failure was recorded
            state_mock.set_task_status.assert_called()
            call_args = state_mock.set_task_status.call_args
            assert call_args[0][0] == "TASK-001"
            assert call_args[0][1] == TaskStatus.FAILED
            levels_mock.mark_task_failed.assert_called_with("TASK-001", "Final failure")


class TestOrchestratorIntegrationWithMocks:
    """Integration tests using full mock objects."""

    def test_full_failure_recovery_flow(self, test_fixture: OrchestratorTestFixture) -> None:
        """Test complete failure and recovery flow using mocks."""
        # Create launcher mock that simulates crash then recovery
        launcher = MockContainerLauncher()
        launcher.configure(container_crash_workers={0})

        # Create merger mock that fails first, succeeds on retry
        merger = MockMergeCoordinator(test_fixture.feature)
        merger.configure(fail_at_attempt=1, always_succeed=True)

        with (
            patch("zerg.orchestrator.StateManager") as state_cls,
            patch("zerg.orchestrator.LevelController") as levels_cls,
            patch("zerg.orchestrator.TaskParser"),
            patch("zerg.orchestrator.WorktreeManager") as worktree_cls,
            patch("zerg.orchestrator.PortAllocator") as ports_cls,
            patch("zerg.orchestrator.MergeCoordinator") as merge_cls,
            patch("zerg.orchestrator.SubprocessLauncher"),
            patch("zerg.orchestrator.GateRunner"),
            patch("zerg.orchestrator.ContainerManager"),
            patch("zerg.orchestrator.TaskSyncBridge"),
        ):
            state_mock = MockStateManager(test_fixture.feature)
            state_cls.return_value = state_mock

            levels_mock = MagicMock()
            levels_mock.current_level = 1
            levels_mock.get_pending_tasks_for_level.return_value = ["TASK-001"]
            levels_cls.return_value = levels_mock

            worktree_mock = MagicMock()
            wt_info = MagicMock()
            wt_info.path = test_fixture.tmp_path / "worktree"
            wt_info.branch = "test-branch"
            worktree_mock.create.return_value = wt_info
            worktree_cls.return_value = worktree_mock

            ports_mock = MagicMock()
            ports_mock.allocate_one.return_value = 50000
            ports_cls.return_value = ports_mock

            merge_cls.return_value = merger

            orch = Orchestrator(test_fixture.feature)
            orch.launcher = launcher
            orch.merger = merger

            # Spawn worker
            result = launcher.spawn(
                worker_id=0,
                feature=test_fixture.feature,
                worktree_path=test_fixture.tmp_path / "worktree",
                branch="test-branch",
            )
            assert result.success

            # Worker crashes
            status = launcher.monitor(0)
            assert status == WorkerStatus.CRASHED

            # Clear crash configuration to allow recovery
            launcher.configure(container_crash_workers=set())

            # First merge attempt fails
            merge_result1 = merger.full_merge_flow(level=1, worker_branches=["branch-1"])
            assert not merge_result1.success

            # Second merge attempt succeeds
            merge_result2 = merger.full_merge_flow(level=1, worker_branches=["branch-1"])
            assert merge_result2.success
            assert merge_result2.merge_commit is not None


class TestRecoverableErrorState:
    """Test recoverable error state handling."""

    def test_set_recoverable_error_pauses(self, test_fixture: OrchestratorTestFixture) -> None:
        """Setting recoverable error should pause orchestrator."""
        with (
            patch("zerg.orchestrator.StateManager") as state_cls,
            patch("zerg.orchestrator.LevelController"),
            patch("zerg.orchestrator.TaskParser"),
            patch("zerg.orchestrator.WorktreeManager"),
            patch("zerg.orchestrator.PortAllocator"),
            patch("zerg.orchestrator.MergeCoordinator"),
            patch("zerg.orchestrator.SubprocessLauncher"),
            patch("zerg.orchestrator.GateRunner"),
            patch("zerg.orchestrator.ContainerManager"),
            patch("zerg.orchestrator.TaskSyncBridge"),
        ):
            state_mock = MagicMock()
            state_mock.load.return_value = {}
            state_cls.return_value = state_mock

            orch = Orchestrator(test_fixture.feature)

            orch._set_recoverable_error("Test recoverable error")

            assert orch._paused is True
            state_mock.set_error.assert_called_with("Test recoverable error")
            state_mock.set_paused.assert_called_with(True)
            state_mock.append_event.assert_called_with("recoverable_error", {"error": "Test recoverable error"})
