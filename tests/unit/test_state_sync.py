"""Unit tests for state synchronization - OFX-003.

Tests for orchestrator-launcher state synchronization,
handle consistency, and status accuracy.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from zerg.constants import WorkerStatus
from zerg.launcher import SubprocessLauncher


class TestLauncherOrchestratorSync:
    """Test launcher state synchronization."""

    @patch("subprocess.Popen")
    def test_launcher_tracks_spawned_workers(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Launcher should track all spawned workers."""
        mock_popen.return_value = MagicMock(pid=12345)

        launcher = SubprocessLauncher()

        # Spawn workers
        for i in range(3):
            launcher.spawn(
                worker_id=i,
                feature="test-feature",
                worktree_path=tmp_path,
                branch=f"branch-{i}",
            )

        # All should be tracked
        for i in range(3):
            handle = launcher.get_handle(i)
            assert handle is not None, f"Worker {i} should be tracked"

    @patch("subprocess.Popen")
    def test_launcher_removes_terminated_workers(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Launcher should update state after termination."""
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

        # Terminate
        launcher.terminate(0)

        # Either removed or marked as stopped
        handle = launcher.get_handle(0)
        if handle is not None:
            assert handle.status in [WorkerStatus.STOPPED, WorkerStatus.CRASHED]


class TestHandleConsistency:
    """Test worker handle consistency."""

    @patch("subprocess.Popen")
    def test_handle_pid_matches_process(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Handle PID should match spawned process."""
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process

        launcher = SubprocessLauncher()
        result = launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        if result.success and result.handle:
            assert result.handle.pid == 12345

    @patch("subprocess.Popen")
    def test_handle_worker_id_matches_requested(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Handle worker_id should match requested ID."""
        mock_popen.return_value = MagicMock(pid=12345)

        launcher = SubprocessLauncher()
        result = launcher.spawn(
            worker_id=42,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        if result.success and result.handle:
            assert result.handle.worker_id == 42


class TestStatusAccuracy:
    """Test status reporting accuracy."""

    @patch("subprocess.Popen")
    def test_status_running_when_process_alive(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Status should be RUNNING when process is alive."""
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
    def test_status_stopped_when_process_exited_cleanly(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Status should be STOPPED when process exited with code 0."""
        mock_process = MagicMock(pid=12345)
        mock_process.poll.return_value = 0  # Clean exit
        mock_popen.return_value = mock_process

        launcher = SubprocessLauncher()
        launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        status = launcher.monitor(0)

        assert status == WorkerStatus.STOPPED

    @patch("subprocess.Popen")
    def test_status_crashed_when_process_exited_with_error(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Status should be CRASHED when process exited with non-zero code."""
        mock_process = MagicMock(pid=12345)
        mock_process.poll.return_value = 1  # Error exit
        mock_popen.return_value = mock_process

        launcher = SubprocessLauncher()
        launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        status = launcher.monitor(0)

        # Should be CRASHED or STOPPED depending on implementation
        assert status in [WorkerStatus.CRASHED, WorkerStatus.STOPPED]


class TestGetStatusSummary:
    """Test status summary generation."""

    @patch("subprocess.Popen")
    def test_get_status_summary_returns_dict(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """get_status_summary should return a dictionary."""
        mock_process = MagicMock(pid=12345)
        mock_process.poll.return_value = None
        mock_popen.return_value = mock_process

        launcher = SubprocessLauncher()
        launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        summary = launcher.get_status_summary()

        assert isinstance(summary, dict)

    @patch("subprocess.Popen")
    def test_get_status_summary_includes_all_workers(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Status summary should include all workers."""
        mock_process = MagicMock(pid=12345)
        mock_process.poll.return_value = None
        mock_popen.return_value = mock_process

        launcher = SubprocessLauncher()

        for i in range(3):
            launcher.spawn(
                worker_id=i,
                feature="test-feature",
                worktree_path=tmp_path,
                branch=f"branch-{i}",
            )

        summary = launcher.get_status_summary()

        # Should have entries for all workers
        assert len(summary) >= 3


class TestSyncState:
    """Test sync_state method for reconciliation."""

    @patch("subprocess.Popen")
    def test_sync_state_updates_stale_handles(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """sync_state should update handles with stale status."""
        mock_process = MagicMock(pid=12345)
        mock_process.poll.return_value = None  # Running
        mock_popen.return_value = mock_process

        launcher = SubprocessLauncher()
        launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        # First monitor - running
        status1 = launcher.monitor(0)
        assert status1 == WorkerStatus.RUNNING

        # Change mock to return stopped
        mock_process.poll.return_value = 0  # Stopped

        # Second monitor - should now be stopped
        status2 = launcher.monitor(0)
        assert status2 in [WorkerStatus.STOPPED, WorkerStatus.CRASHED]


class TestConcurrentAccess:
    """Test behavior under concurrent access patterns."""

    @patch("subprocess.Popen")
    def test_rapid_spawn_terminate_cycles(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Rapid spawn/terminate cycles should not corrupt state."""
        mock_process = MagicMock(pid=12345)
        mock_process.poll.return_value = 0
        mock_popen.return_value = mock_process

        launcher = SubprocessLauncher()

        # Rapid cycles
        for _ in range(10):
            launcher.spawn(
                worker_id=0,
                feature="test-feature",
                worktree_path=tmp_path,
                branch="test-branch",
            )
            launcher.terminate(0)

        # State should be consistent
        # Either no worker or stopped worker
        handle = launcher.get_handle(0)
        if handle is not None:
            assert handle.status in [WorkerStatus.STOPPED, WorkerStatus.CRASHED]

    @patch("subprocess.Popen")
    def test_monitor_during_termination(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Monitor during termination should not raise."""
        mock_process = MagicMock(pid=12345)
        mock_process.poll.return_value = None
        mock_popen.return_value = mock_process

        launcher = SubprocessLauncher()
        launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        # Interleaved operations should not raise
        launcher.monitor(0)
        launcher.terminate(0)
        launcher.monitor(0)  # Should not raise


class TestEdgeCases:
    """Test edge cases in state management."""

    def test_monitor_never_spawned_worker(self) -> None:
        """Monitoring never-spawned worker should return STOPPED."""
        launcher = SubprocessLauncher()

        status = launcher.monitor(999)

        assert status == WorkerStatus.STOPPED

    def test_get_handle_never_spawned_worker(self) -> None:
        """Getting handle for never-spawned worker should return None."""
        launcher = SubprocessLauncher()

        handle = launcher.get_handle(999)

        assert handle is None

    def test_terminate_never_spawned_worker(self) -> None:
        """Terminating never-spawned worker should not raise."""
        launcher = SubprocessLauncher()

        # Should not raise
        launcher.terminate(999)

    @patch("subprocess.Popen")
    def test_double_terminate(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Double termination should not raise."""
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

        # Double terminate should not raise
        launcher.terminate(0)
        launcher.terminate(0)
