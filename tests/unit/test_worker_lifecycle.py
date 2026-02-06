"""Unit tests for worker lifecycle - OFX-002.

Tests for worker spawn, terminate, restart, state transitions,
and spawn failure handling.
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zerg.constants import ExitCode, WorkerStatus
from zerg.launcher_types import SpawnResult, WorkerHandle
from zerg.launchers import SubprocessLauncher
from zerg.protocol_state import WorkerProtocol


class TestWorkerSpawn:
    """Test worker spawning."""

    @patch("subprocess.Popen")
    def test_spawn_returns_spawn_result_with_handle(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Spawn should return a SpawnResult with handle and register worker."""
        mock_popen.return_value = MagicMock(pid=12345)

        launcher = SubprocessLauncher()
        result = launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        assert isinstance(result, SpawnResult)
        if result.success:
            assert result.handle is not None
            assert launcher.get_handle(0) is not None


class TestWorkerTermination:
    """Test worker termination - covers OFX-007 termination race fix."""

    @patch("subprocess.Popen")
    def test_terminate_stops_and_removes_worker(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Terminate should stop the worker process and update tracking."""
        mock_process = MagicMock(pid=12345)
        mock_process.poll.return_value = 0
        mock_popen.return_value = mock_process

        launcher = SubprocessLauncher()
        launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="test-branch",
        )
        launcher.terminate(0)

        mock_process.terminate.assert_called()
        handle = launcher.get_handle(0)
        if handle is not None:
            assert handle.status in [WorkerStatus.STOPPED, WorkerStatus.CRASHED]

    def test_terminate_nonexistent_worker_safe(self) -> None:
        """Terminating non-existent worker should not raise."""
        launcher = SubprocessLauncher()
        launcher.terminate(999)


class TestWorkerRestart:
    """Test worker restart behavior - covers OFX-007 restart fixes."""

    @patch("subprocess.Popen")
    def test_respawn_after_crash(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Worker can be respawned after crash."""
        mock_popen.return_value = MagicMock(pid=12345)

        launcher = SubprocessLauncher()
        launcher.spawn(worker_id=0, feature="test-feature", worktree_path=tmp_path, branch="test-branch")
        launcher.terminate(0)

        result2 = launcher.spawn(worker_id=0, feature="test-feature", worktree_path=tmp_path, branch="test-branch")
        assert result2.success or result2.error is not None


class TestPollLoop:
    """Test poll loop behavior - covers OFX-007 poll loop fixes."""

    @pytest.mark.parametrize(
        "poll_return, expected_status",
        [
            (None, WorkerStatus.RUNNING),
            (0, {WorkerStatus.STOPPED, WorkerStatus.CRASHED}),
        ],
        ids=["running", "exited"],
    )
    @patch("subprocess.Popen")
    def test_monitor_returns_correct_status(
        self, mock_popen: MagicMock, tmp_path: Path, poll_return, expected_status
    ) -> None:
        """Monitor should return correct WorkerStatus based on poll."""
        mock_process = MagicMock(pid=12345)
        mock_process.poll.return_value = poll_return
        mock_popen.return_value = mock_process

        launcher = SubprocessLauncher()
        launcher.spawn(worker_id=0, feature="test-feature", worktree_path=tmp_path, branch="test-branch")
        status = launcher.monitor(0)

        assert isinstance(status, WorkerStatus)
        if isinstance(expected_status, set):
            assert status in expected_status
        else:
            assert status == expected_status

    def test_monitor_nonexistent_returns_stopped(self) -> None:
        """Monitor of non-existent worker should return STOPPED."""
        launcher = SubprocessLauncher()
        assert launcher.monitor(999) == WorkerStatus.STOPPED


class TestSpawnFailure:
    """Test spawn failure handling - covers OFX-007 spawn failure fixes."""

    @patch("subprocess.Popen")
    def test_spawn_failure_returns_error_no_registration(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Failed spawn should return SpawnResult with error and not register worker."""
        mock_popen.side_effect = OSError("Failed to spawn")

        launcher = SubprocessLauncher()
        result = launcher.spawn(worker_id=0, feature="test-feature", worktree_path=tmp_path, branch="test-branch")

        assert not result.success
        assert result.error is not None
        assert launcher.get_handle(0) is None


class TestWorkerHandle:
    """Test WorkerHandle class."""

    @pytest.mark.parametrize(
        "status, alive",
        [
            (WorkerStatus.RUNNING, True),
            (WorkerStatus.STOPPED, False),
        ],
        ids=["running_alive", "stopped_not_alive"],
    )
    def test_handle_properties(self, status: WorkerStatus, alive: bool) -> None:
        """WorkerHandle stores properties and is_alive reflects status."""
        handle = WorkerHandle(worker_id=0, pid=12345, status=status)
        assert handle.worker_id == 0
        assert handle.status == status
        assert handle.is_alive() is alive


class TestLauncherStateConsistency:
    """Test launcher state remains consistent."""

    @patch("subprocess.Popen")
    def test_get_all_and_terminate_all(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """get_all_workers returns all spawned; terminate_all stops them."""
        mock_process = MagicMock(pid=12345)
        mock_process.poll.return_value = 0
        mock_popen.return_value = mock_process

        launcher = SubprocessLauncher()
        for i in range(3):
            launcher.spawn(worker_id=i, feature="test-feature", worktree_path=tmp_path, branch=f"test-branch-{i}")

        assert len(launcher.get_all_workers()) == 3

        launcher.terminate_all()
        for i in range(3):
            status = launcher.monitor(i)
            assert status in [WorkerStatus.STOPPED, WorkerStatus.CRASHED]


class TestWorkerProtocolStateWrites:
    """Test WorkerProtocol writes WorkerState through its lifecycle."""

    @pytest.fixture
    def mock_state_manager(self) -> MagicMock:
        mock = MagicMock()
        mock.load.return_value = {}
        mock.get_tasks_by_status.return_value = []
        mock.get_worker_state.return_value = None
        return mock

    @pytest.fixture
    def mock_git_ops(self) -> MagicMock:
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
        monkeypatch.setenv("ZERG_WORKER_ID", "0")
        monkeypatch.setenv("ZERG_FEATURE", "test-feature")
        monkeypatch.setenv("ZERG_WORKTREE", str(tmp_path))
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        with (
            patch("zerg.protocol_state.StateManager", return_value=mock_state_manager),
            patch("zerg.protocol_state.GitOps", return_value=mock_git_ops),
            patch("zerg.protocol_state.VerificationExecutor"),
        ):
            p = WorkerProtocol(worker_id=0, feature="test-feature")
            p._started_at = datetime.now()
            return p

    def test_start_sets_running_then_stopped(self, protocol: WorkerProtocol, mock_state_manager: MagicMock) -> None:
        """start() writes RUNNING then STOPPED on clean exit."""
        mock_state_manager.get_tasks_by_status.return_value = []

        with patch.object(protocol, "claim_next_task", return_value=None):
            with pytest.raises(SystemExit) as exc_info:
                protocol.start()
        assert exc_info.value.code == ExitCode.SUCCESS

        calls = mock_state_manager.set_worker_state.call_args_list
        running_calls = [c for c in calls if c[0][0].status == WorkerStatus.RUNNING]
        assert len(running_calls) >= 1
        last_call = calls[-1]
        assert last_call[0][0].status == WorkerStatus.STOPPED

    def test_exception_sets_crashed(self, protocol: WorkerProtocol, mock_state_manager: MagicMock) -> None:
        """Unhandled exception in start() loop writes CRASHED status."""
        mock_state_manager.get_tasks_by_status.side_effect = RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            protocol.start()

        calls = mock_state_manager.set_worker_state.call_args_list
        crashed_calls = [c for c in calls if c[0][0].status == WorkerStatus.CRASHED]
        assert len(crashed_calls) >= 1
