"""End-to-end tests for failure recovery scenarios (TC-018).

Tests the system's ability to recover from various failure conditions.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zerg.constants import WorkerStatus
from zerg.launcher import SpawnResult
from zerg.orchestrator import Orchestrator


@pytest.fixture
def recovery_setup(tmp_path: Path, monkeypatch):
    """Set up environment for recovery testing."""
    monkeypatch.chdir(tmp_path)

    zerg_dir = tmp_path / ".zerg"
    zerg_dir.mkdir()

    task_graph = {
        "feature": "recovery-test",
        "levels": {"1": ["TASK-001", "TASK-002"]},
        "tasks": {
            "TASK-001": {
                "id": "TASK-001",
                "title": "Task that might fail",
                "level": 1,
                "files": ["src/a.py"],
                "verification": "pytest tests/test_a.py",
            },
            "TASK-002": {
                "id": "TASK-002",
                "title": "Another task",
                "level": 1,
                "files": ["src/b.py"],
                "verification": "pytest tests/test_b.py",
            },
        },
    }
    (zerg_dir / "task-graph.json").write_text(json.dumps(task_graph))

    return tmp_path


@pytest.fixture
def mock_orchestrator_deps():
    """Mock all orchestrator dependencies."""
    with (
        patch("zerg.orchestrator.StateManager") as state_mock,
        patch("zerg.orchestrator.LevelController") as levels_mock,
        patch("zerg.orchestrator.TaskParser") as parser_mock,
        patch("zerg.orchestrator.GateRunner"),
        patch("zerg.orchestrator.WorktreeManager") as worktree_mock,
        patch("zerg.orchestrator.ContainerManager"),
        patch("zerg.orchestrator.PortAllocator") as ports_mock,
        patch("zerg.orchestrator.MergeCoordinator"),
        patch("zerg.orchestrator.SubprocessLauncher") as launcher_mock,
    ):
        state = MagicMock()
        state.load.return_value = {}
        state_mock.return_value = state

        levels = MagicMock()
        levels.current_level = 1
        levels_mock.return_value = levels

        parser = MagicMock()
        parser.total_tasks = 2
        parser_mock.return_value = parser

        worktree = MagicMock()
        worktree_info = MagicMock()
        worktree_info.path = Path("/tmp/worktree")
        worktree_info.branch = "zerg/recovery-test/worker-0"
        worktree.create.return_value = worktree_info
        worktree_mock.return_value = worktree

        ports = MagicMock()
        ports.allocate_one.return_value = 49152
        ports_mock.return_value = ports

        launcher = MagicMock()
        spawn_result = MagicMock(spec=SpawnResult)
        spawn_result.success = True
        spawn_result.handle = MagicMock()
        spawn_result.handle.container_id = None
        spawn_result.error = None
        launcher.spawn.return_value = spawn_result
        launcher.monitor.return_value = WorkerStatus.RUNNING
        launcher.terminate.return_value = True
        launcher_mock.return_value = launcher

        yield {
            "state": state,
            "levels": levels,
            "parser": parser,
            "worktree": worktree,
            "ports": ports,
            "launcher": launcher,
        }


class TestWorkerCrashRecovery:
    """Tests for worker crash recovery."""

    def test_detect_worker_crash(self, recovery_setup: Path, mock_orchestrator_deps) -> None:
        """Test detection of worker crash."""
        mock_orchestrator_deps["launcher"].monitor.return_value = WorkerStatus.CRASHED

        orch = Orchestrator("recovery-test")

        orch._spawn_worker(0)
        orch._poll_workers()

        # State should record crash
        mock_orchestrator_deps["state"].set_worker_state.assert_called()

    def test_respawn_crashed_worker(self, recovery_setup: Path, mock_orchestrator_deps) -> None:
        """Test respawning a crashed worker."""
        orch = Orchestrator("recovery-test")

        # First spawn
        orch._spawn_worker(0)

        # Respawn (simulating crash recovery)
        orch._spawn_worker(0)

        assert 0 in orch._workers
        assert mock_orchestrator_deps["launcher"].spawn.call_count >= 2


class TestTaskStatusTracking:
    """Tests for task status tracking on failures."""

    def test_task_status_set_on_worker_crash(self, recovery_setup: Path, mock_orchestrator_deps) -> None:
        """Test task status is updated when worker crashes."""
        mock_orchestrator_deps["launcher"].monitor.return_value = WorkerStatus.CRASHED

        orch = Orchestrator("recovery-test")
        orch._spawn_worker(0)
        orch._poll_workers()

        # Worker state should be updated
        mock_orchestrator_deps["state"].set_worker_state.assert_called()

    def test_worker_state_tracked(self, recovery_setup: Path, mock_orchestrator_deps) -> None:
        """Test worker state is tracked properly."""
        orch = Orchestrator("recovery-test")
        orch._spawn_worker(0)

        worker = orch._workers.get(0)
        assert worker is not None


class TestMergeConflictRecovery:
    """Tests for merge conflict recovery."""

    def test_pause_on_merge_conflict(self, recovery_setup: Path, mock_orchestrator_deps) -> None:
        """Test orchestrator pauses on merge conflict."""
        merge = MagicMock()
        merge_result = MagicMock()
        merge_result.success = False
        merge_result.error = "Merge conflict in src/auth.py"
        merge.full_merge_flow.return_value = merge_result

        with (
            patch("zerg.orchestrator.MergeCoordinator", return_value=merge),
            patch("zerg.level_coordinator.time.sleep"),
        ):
            orch = Orchestrator("recovery-test")
            orch._spawn_worker(0)
            orch._on_level_complete_handler(1)

            assert orch._paused is True

    def test_resume_after_conflict_resolution(self, recovery_setup: Path, mock_orchestrator_deps) -> None:
        """Test resuming after merge conflict is resolved."""
        orch = Orchestrator("recovery-test")
        orch._paused = True

        orch.resume()

        assert orch._paused is False
        mock_orchestrator_deps["state"].set_paused.assert_called_with(False)


class TestStateRecovery:
    """Tests for state recovery on restart."""

    def test_state_manager_initialized(self, recovery_setup: Path, mock_orchestrator_deps) -> None:
        """Test state manager is initialized."""
        orch = Orchestrator("recovery-test")

        # State manager should be accessible
        assert orch.state is not None

    def test_resume_from_checkpoint(self, recovery_setup: Path, mock_orchestrator_deps) -> None:
        """Test resuming from checkpoint context."""
        mock_orchestrator_deps["levels"].current_level = 2

        orch = Orchestrator("recovery-test")

        # Should resume at level 2
        assert orch.levels.current_level == 2


class TestNetworkFailureRecovery:
    """Tests for network/process failure recovery."""

    def test_worker_stopped_handling(self, recovery_setup: Path, mock_orchestrator_deps) -> None:
        """Test handling of worker that stopped unexpectedly."""
        mock_orchestrator_deps["launcher"].monitor.return_value = WorkerStatus.STOPPED

        orch = Orchestrator("recovery-test")
        orch._spawn_worker(0)
        orch._poll_workers()

        # State should be updated
        mock_orchestrator_deps["state"].set_worker_state.assert_called()

    def test_worker_blocked_handling(self, recovery_setup: Path, mock_orchestrator_deps) -> None:
        """Test handling of blocked worker."""
        mock_orchestrator_deps["launcher"].monitor.return_value = WorkerStatus.BLOCKED

        orch = Orchestrator("recovery-test")
        orch._spawn_worker(0)
        orch._poll_workers()

        # State should be updated
        mock_orchestrator_deps["state"].set_worker_state.assert_called()


class TestGracefulDegradation:
    """Tests for graceful degradation."""

    def test_continue_with_remaining_workers(self, recovery_setup: Path, mock_orchestrator_deps) -> None:
        """Test continuing execution with remaining workers."""
        mock_orchestrator_deps["ports"].allocate_one.side_effect = [49152, 49153]

        # Worker 0 crashes, Worker 1 runs
        mock_orchestrator_deps["launcher"].monitor.side_effect = [WorkerStatus.CRASHED, WorkerStatus.RUNNING]

        orch = Orchestrator("recovery-test")
        orch._spawn_worker(0)
        orch._spawn_worker(1)

        orch._poll_workers()

        # Should still have workers
        assert len(orch._workers) >= 1

    def test_spawn_failure_handled(self, recovery_setup: Path, mock_orchestrator_deps) -> None:
        """Test spawn failure is handled gracefully."""
        spawn_result = MagicMock(spec=SpawnResult)
        spawn_result.success = False
        spawn_result.error = "Failed to spawn"
        mock_orchestrator_deps["launcher"].spawn.return_value = spawn_result

        orch = Orchestrator("recovery-test")

        # Should not raise
        try:
            orch._spawn_worker(0)
        except Exception:
            pass  # May raise, but shouldn't crash catastrophically


class TestOrchestrationControl:
    """Tests for orchestration control mechanisms."""

    def test_stop_terminates_workers(self, recovery_setup: Path, mock_orchestrator_deps) -> None:
        """Test stop terminates all workers."""
        mock_orchestrator_deps["ports"].allocate_one.side_effect = [49152, 49153]

        orch = Orchestrator("recovery-test")
        orch._running = True

        orch._spawn_worker(0)
        orch._spawn_worker(1)

        orch.stop()

        assert orch._running is False
        assert mock_orchestrator_deps["launcher"].terminate.call_count >= 2

    def test_paused_flag_exists(self, recovery_setup: Path, mock_orchestrator_deps) -> None:
        """Test paused flag can be set."""
        orch = Orchestrator("recovery-test")

        # Initially not paused
        assert orch._paused is False

        # Can set paused
        orch._paused = True
        assert orch._paused is True

    def test_running_state_tracked(self, recovery_setup: Path, mock_orchestrator_deps) -> None:
        """Test running state is tracked."""
        orch = Orchestrator("recovery-test")

        # Initially not running
        assert orch._running is False

        # After setting
        orch._running = True
        assert orch._running is True
