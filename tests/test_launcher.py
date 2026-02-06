"""Tests for ZERG launcher module."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from zerg.constants import WorkerStatus
from zerg.launcher_types import LauncherConfig, LauncherType, SpawnResult, WorkerHandle
from zerg.launchers import SubprocessLauncher


class TestLauncherConfig:
    """Tests for LauncherConfig."""

    def test_defaults(self) -> None:
        """Test default configuration."""
        config = LauncherConfig()

        assert config.launcher_type == LauncherType.SUBPROCESS
        assert config.timeout_seconds == 3600
        assert config.env_vars == {}
        assert config.working_dir is None
        assert config.log_dir is None

    def test_custom_config(self, tmp_path: Path) -> None:
        """Test custom configuration."""
        config = LauncherConfig(
            launcher_type=LauncherType.CONTAINER,
            timeout_seconds=1800,
            env_vars={"FOO": "bar"},
            working_dir=tmp_path,
            log_dir=tmp_path / "logs",
        )

        assert config.launcher_type == LauncherType.CONTAINER
        assert config.timeout_seconds == 1800
        assert config.env_vars["FOO"] == "bar"
        assert config.working_dir == tmp_path


class TestWorkerHandle:
    """Tests for WorkerHandle."""

    def test_is_alive_initializing(self) -> None:
        """Test handle is alive when initializing."""
        handle = WorkerHandle(worker_id=0, status=WorkerStatus.INITIALIZING)
        assert handle.is_alive() is True

    def test_is_alive_running(self) -> None:
        """Test handle is alive when running."""
        handle = WorkerHandle(worker_id=0, status=WorkerStatus.RUNNING)
        assert handle.is_alive() is True

    def test_is_alive_stopped(self) -> None:
        """Test handle is not alive when stopped."""
        handle = WorkerHandle(worker_id=0, status=WorkerStatus.STOPPED)
        assert handle.is_alive() is False

    def test_is_alive_crashed(self) -> None:
        """Test handle is not alive when crashed."""
        handle = WorkerHandle(worker_id=0, status=WorkerStatus.CRASHED)
        assert handle.is_alive() is False


class TestSpawnResult:
    """Tests for SpawnResult."""

    def test_success_result(self) -> None:
        """Test successful spawn result."""
        handle = WorkerHandle(worker_id=0, pid=12345)
        result = SpawnResult(success=True, worker_id=0, handle=handle)

        assert result.success is True
        assert result.worker_id == 0
        assert result.handle is not None
        assert result.error is None

    def test_failure_result(self) -> None:
        """Test failed spawn result."""
        result = SpawnResult(success=False, worker_id=0, error="Failed to spawn")

        assert result.success is False
        assert result.handle is None
        assert result.error == "Failed to spawn"


class TestSubprocessLauncher:
    """Tests for SubprocessLauncher."""

    def test_init(self) -> None:
        """Test launcher initialization."""
        launcher = SubprocessLauncher()

        assert launcher.config is not None
        assert launcher._workers == {}
        assert launcher._processes == {}

    def test_init_with_config(self, tmp_path: Path) -> None:
        """Test launcher with custom config."""
        config = LauncherConfig(log_dir=tmp_path / "logs")
        launcher = SubprocessLauncher(config)

        assert launcher.config.log_dir == tmp_path / "logs"

    @patch("subprocess.Popen")
    def test_spawn_success(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Test successful worker spawn."""
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process

        launcher = SubprocessLauncher()
        result = launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="zerg/test/worker-0",
        )

        assert result.success is True
        assert result.worker_id == 0
        assert result.handle is not None
        assert result.handle.pid == 12345
        assert result.handle.status == WorkerStatus.INITIALIZING

        # Verify process was spawned
        mock_popen.assert_called_once()
        call_args = mock_popen.call_args

        # Check command
        cmd = call_args[0][0]
        assert sys.executable in cmd[0]
        assert "-m" in cmd
        assert "zerg.worker_main" in cmd
        assert "--worker-id" in cmd
        assert "0" in cmd

        # Check environment
        env = call_args[1]["env"]
        assert env["ZERG_WORKER_ID"] == "0"
        assert env["ZERG_FEATURE"] == "test-feature"

    @patch("subprocess.Popen")
    def test_spawn_failure(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Test spawn failure handling."""
        mock_popen.side_effect = OSError("Failed to spawn")

        launcher = SubprocessLauncher()
        result = launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="zerg/test/worker-0",
        )

        assert result.success is False
        assert result.error is not None
        assert "Failed to spawn" in result.error

    @patch("subprocess.Popen")
    def test_monitor_running(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Test monitoring running worker."""
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None  # Still running
        mock_popen.return_value = mock_process

        launcher = SubprocessLauncher()
        launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="zerg/test/worker-0",
        )

        status = launcher.monitor(0)
        assert status == WorkerStatus.RUNNING

    @patch("subprocess.Popen")
    def test_monitor_exited_success(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Test monitoring worker that exited successfully."""
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll.return_value = 0  # Success exit
        mock_popen.return_value = mock_process

        launcher = SubprocessLauncher()
        launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="zerg/test/worker-0",
        )

        status = launcher.monitor(0)
        assert status == WorkerStatus.STOPPED

    @patch("subprocess.Popen")
    def test_monitor_crashed(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Test monitoring crashed worker."""
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll.return_value = 1  # Error exit
        mock_popen.return_value = mock_process

        launcher = SubprocessLauncher()
        launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="zerg/test/worker-0",
        )

        status = launcher.monitor(0)
        assert status == WorkerStatus.CRASHED

    @patch("subprocess.Popen")
    def test_monitor_checkpoint(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Test monitoring worker that checkpointed."""
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll.return_value = 2  # Checkpoint exit code
        mock_popen.return_value = mock_process

        launcher = SubprocessLauncher()
        launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="zerg/test/worker-0",
        )

        status = launcher.monitor(0)
        assert status == WorkerStatus.CHECKPOINTING

    def test_monitor_unknown_worker(self) -> None:
        """Test monitoring unknown worker."""
        launcher = SubprocessLauncher()
        status = launcher.monitor(999)
        assert status == WorkerStatus.STOPPED

    @patch("subprocess.Popen")
    def test_terminate(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Test worker termination."""
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        launcher = SubprocessLauncher()
        launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="zerg/test/worker-0",
        )

        result = launcher.terminate(0)

        assert result is True
        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called()

    @patch("subprocess.Popen")
    def test_terminate_force(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Test forced worker termination."""
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        launcher = SubprocessLauncher()
        launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="zerg/test/worker-0",
        )

        result = launcher.terminate(0, force=True)

        assert result is True
        mock_process.kill.assert_called_once()

    def test_terminate_unknown_worker(self) -> None:
        """Test terminating unknown worker."""
        launcher = SubprocessLauncher()
        result = launcher.terminate(999)
        assert result is False

    def test_get_handle(self) -> None:
        """Test getting worker handle."""
        launcher = SubprocessLauncher()

        # No worker yet
        assert launcher.get_handle(0) is None

        # Add a worker
        handle = WorkerHandle(worker_id=0, pid=12345)
        launcher._workers[0] = handle

        assert launcher.get_handle(0) is handle

    def test_get_all_workers(self) -> None:
        """Test getting all worker handles."""
        launcher = SubprocessLauncher()

        # Add workers
        launcher._workers[0] = WorkerHandle(worker_id=0, pid=12345)
        launcher._workers[1] = WorkerHandle(worker_id=1, pid=12346)

        workers = launcher.get_all_workers()

        assert len(workers) == 2
        assert 0 in workers
        assert 1 in workers

    @patch("subprocess.Popen")
    def test_terminate_all(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Test terminating all workers."""
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        launcher = SubprocessLauncher()

        # Spawn multiple workers
        for i in range(3):
            launcher.spawn(
                worker_id=i,
                feature="test-feature",
                worktree_path=tmp_path,
                branch=f"zerg/test/worker-{i}",
            )

        results = launcher.terminate_all()

        assert len(results) == 3
        assert all(r is True for r in results.values())

    def test_get_status_summary(self) -> None:
        """Test getting status summary."""
        launcher = SubprocessLauncher()

        # Add workers with different statuses
        launcher._workers[0] = WorkerHandle(worker_id=0, status=WorkerStatus.RUNNING)
        launcher._workers[1] = WorkerHandle(worker_id=1, status=WorkerStatus.RUNNING)
        launcher._workers[2] = WorkerHandle(worker_id=2, status=WorkerStatus.STOPPED)

        summary = launcher.get_status_summary()

        assert summary["total"] == 3
        assert summary["alive"] == 2
        assert summary["by_status"]["running"] == 2
        assert summary["by_status"]["stopped"] == 1

    def test_get_output_from_log(self, tmp_path: Path) -> None:
        """Test getting output from log file."""
        # Create log file
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        log_file = log_dir / "worker-0.stdout.log"
        log_file.write_text("line1\nline2\nline3\n")

        config = LauncherConfig(log_dir=log_dir)
        launcher = SubprocessLauncher(config)

        output = launcher.get_output(0, tail=2)

        assert "line2" in output
        assert "line3" in output

    def test_get_output_no_log(self) -> None:
        """Test getting output when no log exists."""
        launcher = SubprocessLauncher()
        launcher._output_buffers[0] = ["line1", "line2"]

        output = launcher.get_output(0)

        assert "line1" in output
        assert "line2" in output
