"""Unit tests for ContainerLauncher operations — thinned to essentials.

Covers: network config, _run_worker_entry, _verify_worker_process,
_cleanup_failed_container, docker errors, spawn flow, mock-based verification.
"""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tests.mocks.mock_launcher import MockContainerLauncher
from zerg.constants import WorkerStatus
from zerg.launcher_types import WorkerHandle
from zerg.launchers import ContainerLauncher

# =============================================================================
# Network Configuration
# =============================================================================


class TestNetworkConfiguration:
    """Tests for ContainerLauncher network configuration."""

    def test_default_and_custom_network(self) -> None:
        assert ContainerLauncher().network == "bridge"
        assert ContainerLauncher(network="custom").network == "custom"
        assert ContainerLauncher(network=None).network == "bridge"
        assert ContainerLauncher(network="").network == "bridge"

    @patch("subprocess.run")
    def test_network_used_in_docker_run(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="cid\n", stderr="")
        launcher = ContainerLauncher(network="custom-net")
        launcher._start_container("zerg-worker-0", tmp_path, {"ZERG_WORKER_ID": "0"})
        call_args = mock_run.call_args[0][0]
        idx = call_args.index("--network")
        assert call_args[idx + 1] == "custom-net"

    @patch("subprocess.run")
    def test_custom_network_creation(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = [MagicMock(returncode=1), MagicMock(returncode=0)]
        launcher = ContainerLauncher(network="new-net")
        assert launcher.ensure_network() is True
        create_args = mock_run.call_args_list[1][0][0]
        assert "create" in create_args
        assert "new-net" in create_args


# =============================================================================
# _run_worker_entry
# =============================================================================


class TestRunWorkerEntry:
    """Tests for _run_worker_entry success and failure paths."""

    def test_success_returns_true(self) -> None:
        launcher = ContainerLauncher()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            assert launcher._run_worker_entry("container-abc") is True

    def test_calls_docker_correctly(self) -> None:
        launcher = ContainerLauncher()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            launcher._run_worker_entry("container-abc")
            cmd = mock_run.call_args[0][0]
            assert cmd[0] == "docker"
            assert "container-abc" in cmd
            assert "-d" in cmd
            assert mock_run.call_args[1].get("timeout") == 30

    @pytest.mark.parametrize(
        "side_effect",
        [
            MagicMock(returncode=1, stdout="", stderr="container not found"),
            MagicMock(returncode=126, stdout="", stderr="Permission denied"),
            subprocess.TimeoutExpired(cmd="docker", timeout=30),
            OSError("Docker not available"),
        ],
    )
    def test_failure_returns_false(self, side_effect) -> None:
        launcher = ContainerLauncher()
        with patch("subprocess.run") as mock_run:
            if isinstance(side_effect, MagicMock):
                mock_run.return_value = side_effect
            else:
                mock_run.side_effect = side_effect
            assert launcher._run_worker_entry("container-abc") is False


# =============================================================================
# _verify_worker_process
# =============================================================================


class TestVerifyWorkerProcess:
    """Tests for _verify_worker_process."""

    def test_process_found_returns_true(self) -> None:
        launcher = ContainerLauncher()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            assert launcher._verify_worker_process("cid", timeout=1.0) is True
            cmd = mock_run.call_args[0][0]
            assert "pgrep" in cmd
            assert "worker_main" in cmd

    def test_process_not_found_returns_false(self) -> None:
        launcher = ContainerLauncher()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            assert launcher._verify_worker_process("cid", timeout=0.5) is False

    def test_eventual_success(self) -> None:
        launcher = ContainerLauncher()
        call_count = [0]

        def mock_run(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] < 2:
                return MagicMock(returncode=1)
            return MagicMock(returncode=0)

        with patch("subprocess.run", side_effect=mock_run):
            assert launcher._verify_worker_process("cid", timeout=5.0) is True

    @patch("subprocess.run")
    @patch("time.time")
    @patch("time.sleep")
    def test_timeout_with_mocked_time(self, mock_sleep, mock_time, mock_run) -> None:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="")
        call_count = 0
        timeline = [0, 1, 2, 3, 4, 6]

        def advancing_time():
            nonlocal call_count
            idx = min(call_count, len(timeline) - 1)
            call_count += 1
            return timeline[idx]

        mock_time.side_effect = advancing_time
        launcher = ContainerLauncher()
        assert launcher._verify_worker_process("cid", timeout=5.0) is False


# =============================================================================
# _cleanup_failed_container
# =============================================================================


class TestCleanupFailedContainer:
    """Tests for _cleanup_failed_container."""

    def test_cleanup_removes_container_and_tracking(self) -> None:
        launcher = ContainerLauncher()
        launcher._container_ids[0] = "cid"
        launcher._workers[0] = WorkerHandle(worker_id=0, container_id="cid")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            launcher._cleanup_failed_container("cid", 0)
            assert mock_run.call_args[0][0] == ["docker", "rm", "-f", "cid"]
        assert 0 not in launcher._container_ids
        assert 0 not in launcher._workers

    def test_cleanup_handles_exception_gracefully(self) -> None:
        launcher = ContainerLauncher()
        launcher._container_ids[0] = "cid"
        launcher._workers[0] = WorkerHandle(worker_id=0, container_id="cid")
        with patch("subprocess.run", side_effect=Exception("Docker error")):
            launcher._cleanup_failed_container("cid", 0)
        assert 0 not in launcher._container_ids

    def test_cleanup_only_removes_specified_worker(self) -> None:
        launcher = ContainerLauncher()
        for i in range(3):
            launcher._workers[i] = WorkerHandle(worker_id=i, container_id=f"c-{i}")
            launcher._container_ids[i] = f"c-{i}"
        with patch("subprocess.run", return_value=MagicMock(returncode=0)):
            launcher._cleanup_failed_container("c-1", 1)
        assert 1 not in launcher._workers
        assert 0 in launcher._workers and 2 in launcher._workers


# =============================================================================
# Docker Daemon / Image / Resource Errors
# =============================================================================


class TestDockerErrors:
    """Tests for spawn behavior under various Docker error conditions."""

    @pytest.mark.parametrize(
        "side_effect",
        [
            subprocess.CalledProcessError(1, ["docker"], stderr="Cannot connect to Docker daemon"),
            PermissionError("Permission denied: /var/run/docker.sock"),
            FileNotFoundError("docker: command not found"),
        ],
    )
    @patch("subprocess.run")
    def test_spawn_docker_errors(self, mock_run, tmp_path, side_effect) -> None:
        mock_run.side_effect = side_effect
        launcher = ContainerLauncher()
        result = launcher.spawn(worker_id=0, feature="test", worktree_path=tmp_path, branch="b")
        assert result.success is False

    @pytest.mark.parametrize(
        "stderr_msg",
        [
            "Cannot allocate memory",
            "no space left on device",
            "pull access denied for zerg-worker",
        ],
    )
    @patch("subprocess.run")
    def test_spawn_resource_errors(self, mock_run, tmp_path, stderr_msg) -> None:
        mock_run.return_value = MagicMock(returncode=125, stdout="", stderr=f"Error: {stderr_msg}")
        launcher = ContainerLauncher()
        result = launcher.spawn(worker_id=0, feature="test", worktree_path=tmp_path, branch="b")
        assert result.success is False


class TestHealthCheckTimeout:
    """Tests for health check timeout during container startup."""

    @patch.object(ContainerLauncher, "_start_container")
    @patch("subprocess.run")
    @patch("time.time")
    @patch("time.sleep")
    def test_wait_ready_times_out(self, mock_sleep, mock_time, mock_run, mock_start, tmp_path) -> None:
        mock_start.return_value = "container-abc123"
        mock_run.return_value = MagicMock(returncode=0, stdout="false\n", stderr="")
        mock_time.side_effect = [0, 5, 10, 15, 20, 25, 35]
        launcher = ContainerLauncher()
        result = launcher.spawn(worker_id=0, feature="test", worktree_path=tmp_path, branch="b")
        assert result.success is False


class TestStartContainerErrors:
    """Tests for _start_container error scenarios."""

    @pytest.mark.parametrize(
        "stderr_msg",
        [
            'Conflict. The container name "/zerg-worker-0" is already in use',
            "source path does not exist",
            "network custom-network not found",
        ],
    )
    @patch("subprocess.run")
    def test_start_container_errors(self, mock_run, tmp_path, stderr_msg) -> None:
        mock_run.return_value = MagicMock(returncode=125, stdout="", stderr=stderr_msg)
        launcher = ContainerLauncher()
        assert launcher._start_container("zerg-worker-0", tmp_path, {}) is None


class TestMonitorErrors:
    """Tests for monitor error handling."""

    @patch("subprocess.run")
    def test_monitor_container_removed(self, mock_run) -> None:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="No such object")
        launcher = ContainerLauncher()
        launcher._workers[0] = WorkerHandle(worker_id=0, container_id="c")
        launcher._container_ids[0] = "c"
        assert launcher.monitor(0) == WorkerStatus.STOPPED

    @patch("subprocess.run")
    def test_monitor_malformed_output(self, mock_run) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="invalid\n", stderr="")
        launcher = ContainerLauncher()
        launcher._workers[0] = WorkerHandle(worker_id=0, container_id="c", status=WorkerStatus.RUNNING)
        launcher._container_ids[0] = "c"
        assert launcher.monitor(0) == WorkerStatus.RUNNING


class TestTerminateCleanup:
    """Tests for cleanup in terminate."""

    @patch("subprocess.run")
    def test_terminate_cleans_up_on_failure(self, mock_run) -> None:
        mock_run.return_value = MagicMock(returncode=1, stderr="already stopped")
        launcher = ContainerLauncher()
        launcher._workers[0] = WorkerHandle(worker_id=0, container_id="c")
        launcher._container_ids[0] = "c"
        launcher.terminate(0)
        assert 0 not in launcher._container_ids
        assert 0 not in launcher._workers

    @patch("subprocess.run")
    def test_terminate_timeout_then_kill(self, mock_run) -> None:
        mock_run.side_effect = [subprocess.TimeoutExpired("docker stop", 30), MagicMock(returncode=0)]
        launcher = ContainerLauncher()
        launcher._workers[0] = WorkerHandle(worker_id=0, container_id="c")
        launcher._container_ids[0] = "c"
        assert launcher.terminate(0) is True


# =============================================================================
# Spawn Flow
# =============================================================================


class TestSpawnFlow:
    """Tests for spawn flow cleanup when steps fail."""

    def test_spawn_cleanup_on_verify_failure(self) -> None:
        launcher = ContainerLauncher()
        with (
            patch.object(launcher, "_start_container", return_value="c-123"),
            patch.object(launcher, "_wait_ready", return_value=True),
            patch.object(launcher, "_verify_worker_process", return_value=False),
            patch.object(launcher, "_cleanup_failed_container") as mock_cleanup,
        ):
            result = launcher.spawn(worker_id=0, feature="test", worktree_path=Path("/ws"), branch="b")
            assert not result.success
            mock_cleanup.assert_called_once_with("c-123", 0)

    def test_spawn_no_cleanup_when_start_fails(self) -> None:
        launcher = ContainerLauncher()
        with (
            patch.object(launcher, "_start_container", return_value=None),
            patch.object(launcher, "_cleanup_failed_container") as mock_cleanup,
        ):
            result = launcher.spawn(worker_id=0, feature="test", worktree_path=Path("/ws"), branch="b")
            assert not result.success
            mock_cleanup.assert_not_called()

    def test_spawn_all_steps_pass(self) -> None:
        launcher = ContainerLauncher()
        with (
            patch.object(launcher, "_start_container", return_value="c-123"),
            patch.object(launcher, "_wait_ready", return_value=True),
            patch.object(launcher, "_run_worker_entry", return_value=True),
            patch.object(launcher, "_verify_worker_process", return_value=True),
        ):
            result = launcher.spawn(worker_id=0, feature="test", worktree_path=Path("/ws"), branch="b")
            assert result.success
            assert result.handle.status == WorkerStatus.RUNNING


# =============================================================================
# Mock-Based Verification
# =============================================================================


class TestMockLauncher:
    """Tests using MockContainerLauncher for spawn flow verification."""

    def test_full_spawn_success(self) -> None:
        launcher = MockContainerLauncher()
        launcher.configure()
        result = launcher.spawn(worker_id=0, feature="test", worktree_path=Path("/ws"), branch="b")
        assert result.success
        assert launcher.get_handle(0) is not None

    def test_exec_failure_cleans_up(self) -> None:
        launcher = MockContainerLauncher()
        launcher.configure(exec_fail_workers={0})
        result = launcher.spawn(worker_id=0, feature="test", worktree_path=Path("/ws"), branch="b")
        assert not result.success
        assert launcher.get_handle(0) is None

    def test_process_failure_cleans_up(self) -> None:
        launcher = MockContainerLauncher()
        launcher.configure(process_fail_workers={0})
        result = launcher.spawn(worker_id=0, feature="test", worktree_path=Path("/ws"), branch="b")
        assert not result.success
        assert launcher.get_handle(0) is None

    def test_multiple_workers_independent(self) -> None:
        launcher = MockContainerLauncher()
        launcher.configure(exec_fail_workers={1})
        results = [
            launcher.spawn(worker_id=i, feature="test", worktree_path=Path(f"/ws-{i}"), branch=f"b-{i}")
            for i in range(3)
        ]
        assert results[0].success and not results[1].success and results[2].success
        assert len(launcher.get_all_workers()) == 2

    def test_monitor_states(self) -> None:
        launcher = MockContainerLauncher()
        launcher.configure(container_crash_workers={0})
        launcher.spawn(worker_id=0, feature="test", worktree_path=Path("/ws"), branch="b")
        assert launcher.monitor(0) == WorkerStatus.CRASHED
        assert launcher.monitor(999) == WorkerStatus.STOPPED
