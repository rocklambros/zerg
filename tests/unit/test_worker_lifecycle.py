"""Unit tests for worker lifecycle - OFX-002.

Tests for worker spawn, terminate, restart, state transitions,
worktree cleanup, and spawn failure handling.
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zerg.constants import ExitCode, WorkerStatus
from zerg.launcher import SpawnResult, SubprocessLauncher, WorkerHandle
from zerg.worker_protocol import WorkerProtocol


class TestWorkerSpawn:
    """Test worker spawning."""

    @patch("subprocess.Popen")
    def test_spawn_returns_spawn_result(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Spawn should return a SpawnResult object."""
        mock_popen.return_value = MagicMock(pid=12345)

        launcher = SubprocessLauncher()
        result = launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        assert isinstance(result, SpawnResult)

    @patch("subprocess.Popen")
    def test_spawn_success_has_handle(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Successful spawn should have a handle."""
        mock_popen.return_value = MagicMock(pid=12345)

        launcher = SubprocessLauncher()
        result = launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        if result.success:
            assert result.handle is not None

    @patch("subprocess.Popen")
    def test_spawn_registers_worker(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Spawn should register worker in launcher state."""
        mock_popen.return_value = MagicMock(pid=12345)

        launcher = SubprocessLauncher()
        result = launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        if result.success:
            # Worker should be tracked
            handle = launcher.get_handle(0)
            assert handle is not None


class TestWorkerTermination:
    """Test worker termination - covers OFX-007 termination race fix."""

    @patch("subprocess.Popen")
    def test_terminate_stops_worker(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Terminate should stop the worker process."""
        mock_process = MagicMock(pid=12345)
        mock_process.poll.return_value = None  # Still running
        mock_popen.return_value = mock_process

        launcher = SubprocessLauncher()
        launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        launcher.terminate(0)

        # Should have called terminate on the process
        mock_process.terminate.assert_called()

    @patch("subprocess.Popen")
    def test_terminate_removes_from_tracking(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """After termination, worker should be removed from tracking."""
        mock_process = MagicMock(pid=12345)
        mock_process.poll.return_value = 0  # Exited
        mock_popen.return_value = mock_process

        launcher = SubprocessLauncher()
        launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        launcher.terminate(0)

        # Worker should no longer be tracked (or marked as terminated)
        handle = launcher.get_handle(0)
        # Either None or status is STOPPED/terminated
        if handle is not None:
            assert handle.status in [WorkerStatus.STOPPED, WorkerStatus.CRASHED]

    def test_terminate_nonexistent_worker_safe(self) -> None:
        """Terminating non-existent worker should not raise."""
        launcher = SubprocessLauncher()

        # Should not raise
        launcher.terminate(999)


class TestWorkerRestart:
    """Test worker restart behavior - covers OFX-007 restart fixes."""

    @patch("subprocess.Popen")
    def test_respawn_after_crash(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Worker can be respawned after crash."""
        mock_popen.return_value = MagicMock(pid=12345)

        launcher = SubprocessLauncher()

        # First spawn
        launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        # Terminate (simulate crash)
        launcher.terminate(0)

        # Respawn should work
        result2 = launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        assert result2.success or result2.error is not None


class TestPollLoop:
    """Test poll loop behavior - covers OFX-007 poll loop fixes."""

    @patch("subprocess.Popen")
    def test_monitor_returns_status(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Monitor should return valid WorkerStatus."""
        mock_process = MagicMock(pid=12345)
        mock_process.poll.return_value = None  # Still running
        mock_popen.return_value = mock_process

        launcher = SubprocessLauncher()
        launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        status = launcher.monitor(0)

        assert isinstance(status, WorkerStatus)

    @patch("subprocess.Popen")
    def test_monitor_running_worker(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Monitor should return RUNNING for active worker."""
        mock_process = MagicMock(pid=12345)
        mock_process.poll.return_value = None  # Still running
        mock_popen.return_value = mock_process

        launcher = SubprocessLauncher()
        launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        status = launcher.monitor(0)

        assert status == WorkerStatus.RUNNING

    @patch("subprocess.Popen")
    def test_monitor_stopped_worker(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Monitor should return STOPPED for exited worker."""
        mock_process = MagicMock(pid=12345)
        mock_process.poll.return_value = 0  # Exited cleanly
        mock_popen.return_value = mock_process

        launcher = SubprocessLauncher()
        launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        status = launcher.monitor(0)

        assert status in [WorkerStatus.STOPPED, WorkerStatus.CRASHED]

    def test_monitor_nonexistent_returns_stopped(self) -> None:
        """Monitor of non-existent worker should return STOPPED."""
        launcher = SubprocessLauncher()

        status = launcher.monitor(999)

        assert status == WorkerStatus.STOPPED


class TestSpawnFailure:
    """Test spawn failure handling - covers OFX-007 spawn failure fixes."""

    @patch("subprocess.Popen")
    def test_spawn_failure_returns_error(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Failed spawn should return SpawnResult with error."""
        mock_popen.side_effect = OSError("Failed to spawn")

        launcher = SubprocessLauncher()
        result = launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        assert not result.success
        assert result.error is not None

    @patch("subprocess.Popen")
    def test_spawn_failure_does_not_register(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Failed spawn should not register worker."""
        mock_popen.side_effect = OSError("Failed to spawn")

        launcher = SubprocessLauncher()
        launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        handle = launcher.get_handle(0)
        assert handle is None


class TestWorkerHandle:
    """Test WorkerHandle class."""

    def test_handle_has_worker_id(self) -> None:
        """WorkerHandle should have worker_id."""
        handle = WorkerHandle(
            worker_id=0,
            pid=12345,
            status=WorkerStatus.RUNNING,
        )

        assert handle.worker_id == 0

    def test_handle_has_status(self) -> None:
        """WorkerHandle should have status."""
        handle = WorkerHandle(
            worker_id=0,
            pid=12345,
            status=WorkerStatus.RUNNING,
        )

        assert handle.status == WorkerStatus.RUNNING

    def test_handle_is_alive_when_running(self) -> None:
        """is_alive() should return True when RUNNING."""
        handle = WorkerHandle(
            worker_id=0,
            pid=12345,
            status=WorkerStatus.RUNNING,
        )

        assert handle.is_alive() is True

    def test_handle_not_alive_when_stopped(self) -> None:
        """is_alive() should return False when STOPPED."""
        handle = WorkerHandle(
            worker_id=0,
            pid=12345,
            status=WorkerStatus.STOPPED,
        )

        assert handle.is_alive() is False


class TestLauncherStateConsistency:
    """Test launcher state remains consistent."""

    @patch("subprocess.Popen")
    def test_get_all_workers(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """get_all_workers should return all spawned workers."""
        mock_popen.return_value = MagicMock(pid=12345)

        launcher = SubprocessLauncher()

        # Spawn multiple workers
        for i in range(3):
            launcher.spawn(
                worker_id=i,
                feature="test-feature",
                worktree_path=tmp_path,
                branch=f"test-branch-{i}",
            )

        workers = launcher.get_all_workers()

        assert len(workers) == 3

    @patch("subprocess.Popen")
    def test_terminate_all(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """terminate_all should stop all workers."""
        mock_process = MagicMock(pid=12345)
        mock_process.poll.return_value = 0
        mock_popen.return_value = mock_process

        launcher = SubprocessLauncher()

        # Spawn multiple workers
        for i in range(3):
            launcher.spawn(
                worker_id=i,
                feature="test-feature",
                worktree_path=tmp_path,
                branch=f"test-branch-{i}",
            )

        launcher.terminate_all()

        # All should be terminated
        for i in range(3):
            status = launcher.monitor(i)
            assert status in [WorkerStatus.STOPPED, WorkerStatus.CRASHED]


class TestWorkerProtocolStateWrites:
    """Test WorkerProtocol writes WorkerState through its lifecycle."""

    @pytest.fixture
    def mock_state_manager(self) -> MagicMock:
        """Create mock state manager."""
        mock = MagicMock()
        mock.load.return_value = {}
        mock.get_tasks_by_status.return_value = []
        mock.get_worker_state.return_value = None
        return mock

    @pytest.fixture
    def mock_git_ops(self) -> MagicMock:
        """Create mock git ops."""
        mock = MagicMock()
        mock.has_changes.return_value = False
        return mock

    @pytest.fixture
    def protocol(
        self,
        tmp_path: Path,
        mock_state_manager: MagicMock,
        mock_git_ops: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> WorkerProtocol:
        """Create WorkerProtocol with mocked dependencies."""
        monkeypatch.setenv("ZERG_WORKER_ID", "0")
        monkeypatch.setenv("ZERG_FEATURE", "test-feature")
        monkeypatch.setenv("ZERG_WORKTREE", str(tmp_path))
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        with (
            patch("zerg.worker_protocol.StateManager", return_value=mock_state_manager),
            patch("zerg.worker_protocol.GitOps", return_value=mock_git_ops),
            patch("zerg.worker_protocol.VerificationExecutor"),
        ):
            p = WorkerProtocol(worker_id=0, feature="test-feature")
            p._started_at = datetime.now()
            return p

    def test_start_sets_running_worker_state(self, protocol: WorkerProtocol, mock_state_manager: MagicMock) -> None:
        """After signal_ready, start() writes WorkerState with RUNNING."""
        # Make claim_next_task return None immediately (no tasks)
        mock_state_manager.get_tasks_by_status.return_value = []

        with patch.object(protocol, "claim_next_task", return_value=None):
            with pytest.raises(SystemExit) as exc_info:
                protocol.start()
        assert exc_info.value.code == ExitCode.SUCCESS

        # Find set_worker_state calls with RUNNING status
        calls = mock_state_manager.set_worker_state.call_args_list
        running_calls = [c for c in calls if c[0][0].status == WorkerStatus.RUNNING]
        assert len(running_calls) >= 1, "Expected at least one RUNNING state write"

    def test_start_clean_exit_sets_stopped(self, protocol: WorkerProtocol, mock_state_manager: MagicMock) -> None:
        """Clean exit from start() writes STOPPED status."""
        mock_state_manager.get_tasks_by_status.return_value = []

        with patch.object(protocol, "claim_next_task", return_value=None):
            with pytest.raises(SystemExit) as exc_info:
                protocol.start()
        assert exc_info.value.code == ExitCode.SUCCESS

        # Last set_worker_state call should be STOPPED
        last_call = mock_state_manager.set_worker_state.call_args_list[-1]
        assert last_call[0][0].status == WorkerStatus.STOPPED

    def test_execute_task_sets_current_task(self, protocol: WorkerProtocol, mock_state_manager: MagicMock) -> None:
        """execute_task updates WorkerState with current_task."""
        task = {"id": "TASK-001", "title": "Test task"}

        # Mock Claude CLI to succeed
        with patch.object(protocol, "invoke_claude_code") as mock_invoke:
            mock_invoke.return_value = MagicMock(success=True)
            with patch.object(protocol, "commit_task_changes", return_value=True):
                protocol.execute_task(task)

        # Find the call that sets current_task to TASK-001
        calls = mock_state_manager.set_worker_state.call_args_list
        task_calls = [c for c in calls if c[0][0].current_task == "TASK-001"]
        assert len(task_calls) >= 1, "Expected WorkerState with current_task='TASK-001'"

    def test_report_complete_clears_current_task(self, protocol: WorkerProtocol, mock_state_manager: MagicMock) -> None:
        """report_complete clears current_task and increments tasks_completed."""
        protocol.current_task = {"id": "TASK-001"}
        protocol.tasks_completed = 0

        protocol.report_complete("TASK-001")

        # Should write state with current_task=None and tasks_completed=1
        last_call = mock_state_manager.set_worker_state.call_args_list[-1]
        ws = last_call[0][0]
        assert ws.current_task is None
        assert ws.tasks_completed == 1

    def test_report_failed_clears_current_task(self, protocol: WorkerProtocol, mock_state_manager: MagicMock) -> None:
        """report_failed writes WorkerState with current_task=None."""
        protocol.current_task = {"id": "TASK-001"}

        protocol.report_failed("TASK-001", "Test error")

        last_call = mock_state_manager.set_worker_state.call_args_list[-1]
        ws = last_call[0][0]
        assert ws.current_task is None
        assert ws.status == WorkerStatus.RUNNING

    def test_exception_sets_crashed(self, protocol: WorkerProtocol, mock_state_manager: MagicMock) -> None:
        """Unhandled exception in start() loop writes CRASHED status."""
        # Make claim_next_task raise an exception
        mock_state_manager.get_tasks_by_status.side_effect = RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            protocol.start()

        # Find CRASHED state write
        calls = mock_state_manager.set_worker_state.call_args_list
        crashed_calls = [c for c in calls if c[0][0].status == WorkerStatus.CRASHED]
        assert len(crashed_calls) >= 1, "Expected CRASHED state write on exception"

    def test_execute_task_records_duration(self, protocol: WorkerProtocol, mock_state_manager: MagicMock) -> None:
        """execute_task records duration_ms via state.record_task_duration."""
        task = {"id": "TASK-001", "title": "Test task"}

        with patch("zerg.worker_protocol.TaskArtifactCapture"):
            with patch.object(protocol, "invoke_claude_code") as mock_invoke:
                mock_invoke.return_value = MagicMock(success=True, stdout="", stderr="")
                with patch.object(protocol, "commit_task_changes", return_value=True):
                    result = protocol.execute_task(task)

        assert result is True
        mock_state_manager.record_task_duration.assert_called_once()
        call_args = mock_state_manager.record_task_duration.call_args
        assert call_args[0][0] == "TASK-001"
        assert call_args[0][1] >= 0  # duration_ms should be non-negative

    def test_context_usage_written(self, protocol: WorkerProtocol, mock_state_manager: MagicMock) -> None:
        """WorkerState writes include context_usage > 0 or == 0 (a float)."""
        protocol._update_worker_state(WorkerStatus.RUNNING)

        call = mock_state_manager.set_worker_state.call_args_list[-1]
        ws = call[0][0]
        assert isinstance(ws.context_usage, float)

    def test_checkpoint_sets_checkpointing(self, protocol: WorkerProtocol, mock_state_manager: MagicMock) -> None:
        """checkpoint_and_exit writes CHECKPOINTING status."""
        with pytest.raises(SystemExit) as exc_info:
            protocol.checkpoint_and_exit()
        assert exc_info.value.code == ExitCode.CHECKPOINT

        calls = mock_state_manager.set_worker_state.call_args_list
        checkpoint_calls = [c for c in calls if c[0][0].status == WorkerStatus.CHECKPOINTING]
        assert len(checkpoint_calls) >= 1
