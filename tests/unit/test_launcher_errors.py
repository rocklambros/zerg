"""Unit tests for ContainerLauncher error paths.

Tests cover:
1. Docker daemon not running
2. Image pull failure
3. Health check timeout handling
4. Container start failure cleanup
5. Resource limit errors
"""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from zerg.constants import WorkerStatus
from zerg.launcher import (
    ContainerLauncher,
    WorkerHandle,
)


class TestDockerDaemonNotRunning:
    """Tests for spawn behavior when Docker daemon is not running."""

    @patch("subprocess.run")
    def test_spawn_docker_daemon_connection_refused(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test spawn fails gracefully when Docker daemon connection is refused."""
        # Simulate Docker daemon not running - connection refused error
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=["docker", "run"],
            stderr=(
                "Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?"
            ),
        )

        launcher = ContainerLauncher()
        result = launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        assert result.success is False
        assert result.error is not None
        assert 0 not in launcher._workers
        assert 0 not in launcher._container_ids

    @patch("subprocess.run")
    def test_spawn_docker_socket_permission_denied(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test spawn fails when Docker socket permission denied.

        Note: PermissionError is caught by spawn's outer exception handler
        and the actual error message is returned in the result.
        """
        mock_run.side_effect = PermissionError("Permission denied: /var/run/docker.sock")

        launcher = ContainerLauncher()
        result = launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        assert result.success is False
        assert result.error is not None
        assert 0 not in launcher._workers

    @patch("subprocess.run")
    def test_spawn_docker_daemon_not_found(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test spawn fails when docker command not found.

        Note: FileNotFoundError is caught by spawn's outer exception handler
        and the actual error message is returned in the result.
        """
        mock_run.side_effect = FileNotFoundError("docker: command not found")

        launcher = ContainerLauncher()
        result = launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        assert result.success is False
        assert result.error is not None

    @patch("subprocess.run")
    def test_spawn_docker_daemon_error_return_code(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test spawn fails when docker returns error code indicating daemon issues."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?",
        )

        launcher = ContainerLauncher()
        result = launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        assert result.success is False
        assert "Failed to start container" in result.error


class TestImagePullFailure:
    """Tests for spawn behavior when image pull fails."""

    @patch("subprocess.run")
    def test_spawn_image_not_found(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test spawn fails when Docker image does not exist."""
        # Docker run returns error when image not found
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Unable to find image 'zerg-worker:latest' locally\n"
            "Error response from daemon: pull access denied for zerg-worker",
        )

        launcher = ContainerLauncher()
        result = launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        assert result.success is False
        assert "Failed to start container" in result.error

    @patch("subprocess.run")
    def test_spawn_image_pull_timeout(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test spawn fails when image pull times out."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="docker run", timeout=60)

        launcher = ContainerLauncher()
        result = launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        assert result.success is False
        # _start_container returns None on timeout

    @patch("subprocess.run")
    def test_spawn_registry_authentication_error(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test spawn fails when registry authentication fails."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Error response from daemon: unauthorized: authentication required",
        )

        launcher = ContainerLauncher()
        result = launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        assert result.success is False
        assert "Failed to start container" in result.error

    @patch("subprocess.run")
    def test_spawn_network_error_during_pull(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test spawn fails when network error occurs during image pull."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr=("Error response from daemon: net/http: request canceled while waiting for connection"),
        )

        launcher = ContainerLauncher()
        result = launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        assert result.success is False


class TestHealthCheckTimeoutHandling:
    """Tests for health check timeout scenarios during container startup."""

    @patch.object(ContainerLauncher, "_start_container")
    @patch("subprocess.run")
    @patch("time.time")
    @patch("time.sleep")
    def test_wait_ready_times_out_on_slow_container(
        self,
        mock_sleep: MagicMock,
        mock_time: MagicMock,
        mock_run: MagicMock,
        mock_start: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test spawn fails when container health check times out."""
        mock_start.return_value = "container-abc123"
        # docker inspect keeps returning false (container not ready)
        mock_run.return_value = MagicMock(returncode=0, stdout="false\n", stderr="")
        # Time progresses past timeout
        mock_time.side_effect = [0, 5, 10, 15, 20, 25, 35]  # Exceeds 30 second timeout

        launcher = ContainerLauncher()
        result = launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        assert result.success is False
        assert "failed to become ready" in result.error

    @patch.object(ContainerLauncher, "_start_container")
    @patch("subprocess.run")
    @patch("time.time")
    @patch("time.sleep")
    def test_wait_ready_container_exits_during_health_check(
        self,
        mock_sleep: MagicMock,
        mock_time: MagicMock,
        mock_run: MagicMock,
        mock_start: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test spawn fails when container exits during health check."""
        mock_start.return_value = "container-abc123"
        # First inspect returns timeout error, then container not found
        mock_run.side_effect = [
            subprocess.TimeoutExpired(cmd="docker inspect", timeout=10),
            MagicMock(returncode=1, stdout="", stderr="No such container"),
        ]
        mock_time.side_effect = [0, 5, 35]

        launcher = ContainerLauncher()
        result = launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        assert result.success is False

    @patch.object(ContainerLauncher, "_start_container")
    @patch("subprocess.run")
    @patch("time.time")
    @patch("time.sleep")
    def test_wait_ready_handles_generic_exception(
        self,
        mock_sleep: MagicMock,
        mock_time: MagicMock,
        mock_run: MagicMock,
        mock_start: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test wait_ready handles generic exceptions during health check."""
        mock_start.return_value = "container-abc123"
        # docker inspect raises unexpected exception
        mock_run.side_effect = [
            Exception("Unexpected Docker error"),
            Exception("Unexpected Docker error"),
        ]
        mock_time.side_effect = [0, 5, 35]

        launcher = ContainerLauncher()
        result = launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        assert result.success is False


class TestContainerStartFailureCleanup:
    """Tests for cleanup behavior when container start fails at various stages."""

    @patch.object(ContainerLauncher, "_cleanup_failed_container")
    @patch.object(ContainerLauncher, "_verify_worker_process")
    @patch.object(ContainerLauncher, "_wait_ready")
    @patch.object(ContainerLauncher, "_start_container")
    def test_spawn_cleans_up_on_exec_failure(
        self,
        mock_start: MagicMock,
        mock_wait: MagicMock,
        mock_verify: MagicMock,
        mock_cleanup: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test spawn cleans up container when worker process fails to start."""
        mock_start.return_value = "container-abc123"
        mock_wait.return_value = True
        mock_verify.return_value = False  # Worker process fails to start

        launcher = ContainerLauncher()
        result = launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        assert result.success is False
        assert "Worker process failed to start" in result.error
        mock_cleanup.assert_called_once_with("container-abc123", 0)

    @patch.object(ContainerLauncher, "_cleanup_failed_container")
    @patch.object(ContainerLauncher, "_verify_worker_process")
    @patch.object(ContainerLauncher, "_exec_worker_entry")
    @patch.object(ContainerLauncher, "_wait_ready")
    @patch.object(ContainerLauncher, "_start_container")
    def test_spawn_cleans_up_on_verify_failure(
        self,
        mock_start: MagicMock,
        mock_wait: MagicMock,
        mock_exec: MagicMock,
        mock_verify: MagicMock,
        mock_cleanup: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test spawn cleans up container when worker process verification fails."""
        mock_start.return_value = "container-abc123"
        mock_wait.return_value = True
        mock_exec.return_value = True
        mock_verify.return_value = False  # Worker process not running

        launcher = ContainerLauncher()
        result = launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        assert result.success is False
        assert "Worker process failed to start" in result.error
        mock_cleanup.assert_called_once_with("container-abc123", 0)

    @patch("subprocess.run")
    def test_cleanup_failed_container_removes_tracking(self, mock_run: MagicMock) -> None:
        """Test _cleanup_failed_container removes worker from tracking."""
        mock_run.return_value = MagicMock(returncode=0)

        launcher = ContainerLauncher()
        # Simulate partially set up worker
        launcher._container_ids[0] = "container-abc123"
        launcher._workers[0] = WorkerHandle(worker_id=0, container_id="container-abc123")

        launcher._cleanup_failed_container("container-abc123", 0)

        assert 0 not in launcher._container_ids
        assert 0 not in launcher._workers
        mock_run.assert_called_once()
        # Verify docker rm -f was called
        call_args = mock_run.call_args[0][0]
        assert "docker" in call_args
        assert "rm" in call_args
        assert "-f" in call_args

    @patch("subprocess.run")
    def test_cleanup_failed_container_handles_docker_error(self, mock_run: MagicMock) -> None:
        """Test _cleanup_failed_container handles docker rm failure gracefully."""
        mock_run.side_effect = Exception("Docker error during cleanup")

        launcher = ContainerLauncher()
        launcher._container_ids[0] = "container-abc123"
        launcher._workers[0] = WorkerHandle(worker_id=0, container_id="container-abc123")

        # Should not raise, should clean up tracking anyway
        launcher._cleanup_failed_container("container-abc123", 0)

        assert 0 not in launcher._container_ids
        assert 0 not in launcher._workers

    @patch("subprocess.run")
    def test_cleanup_failed_container_timeout(self, mock_run: MagicMock) -> None:
        """Test _cleanup_failed_container handles timeout during cleanup."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="docker rm", timeout=10)

        launcher = ContainerLauncher()
        launcher._container_ids[0] = "container-abc123"
        launcher._workers[0] = WorkerHandle(worker_id=0, container_id="container-abc123")

        # Should not raise, should still clean up tracking
        launcher._cleanup_failed_container("container-abc123", 0)

        assert 0 not in launcher._container_ids
        assert 0 not in launcher._workers


class TestResourceLimitErrors:
    """Tests for resource limit related errors during container spawn."""

    @patch("subprocess.run")
    def test_spawn_out_of_memory_error(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test spawn fails when system is out of memory."""
        mock_run.return_value = MagicMock(
            returncode=125,
            stdout="",
            stderr="Error response from daemon: Cannot allocate memory",
        )

        launcher = ContainerLauncher()
        result = launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        assert result.success is False
        assert "Failed to start container" in result.error

    @patch("subprocess.run")
    def test_spawn_disk_quota_exceeded(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test spawn fails when disk quota is exceeded."""
        mock_run.return_value = MagicMock(
            returncode=125,
            stdout="",
            stderr="Error response from daemon: no space left on device",
        )

        launcher = ContainerLauncher()
        result = launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        assert result.success is False
        assert "Failed to start container" in result.error

    @patch("subprocess.run")
    def test_spawn_container_limit_reached(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test spawn fails when container limit is reached."""
        mock_run.return_value = MagicMock(
            returncode=125,
            stdout="",
            stderr="Error response from daemon: max containers reached on this node",
        )

        launcher = ContainerLauncher()
        result = launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        assert result.success is False

    @patch("subprocess.run")
    def test_spawn_port_already_in_use(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test spawn fails when required port is already in use."""
        mock_run.return_value = MagicMock(
            returncode=125,
            stdout="",
            stderr="Error response from daemon: driver failed programming external connectivity: "
            "Bind for 0.0.0.0:8080 failed: port is already allocated",
        )

        launcher = ContainerLauncher()
        result = launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        assert result.success is False

    @patch("subprocess.run")
    def test_spawn_cgroup_limit_error(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test spawn fails when cgroup resource limit is hit."""
        mock_run.return_value = MagicMock(
            returncode=125,
            stdout="",
            stderr="Error response from daemon: cgroup error: unable to create cgroup memory path",
        )

        launcher = ContainerLauncher()
        result = launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        assert result.success is False


class TestVerifyWorkerProcessErrors:
    """Tests for _verify_worker_process error handling."""

    @patch("subprocess.run")
    @patch("time.time")
    @patch("time.sleep")
    def test_verify_worker_process_timeout(
        self,
        mock_sleep: MagicMock,
        mock_time: MagicMock,
        mock_run: MagicMock,
    ) -> None:
        """Test _verify_worker_process returns False on timeout."""
        # pgrep keeps returning "not found"
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="")
        # Use a counter so logging's internal time.time() calls don't
        # exhaust the mock (StopIteration in CI).
        call_count = 0
        timeline = [0, 1, 2, 3, 4, 6]

        def advancing_time():
            nonlocal call_count
            idx = min(call_count, len(timeline) - 1)
            call_count += 1
            return timeline[idx]

        mock_time.side_effect = advancing_time

        launcher = ContainerLauncher()
        result = launcher._verify_worker_process("container-abc123", timeout=5.0)

        assert result is False

    @patch("subprocess.run")
    @patch("time.time")
    @patch("time.sleep")
    def test_verify_worker_process_pgrep_timeout(
        self,
        mock_sleep: MagicMock,
        mock_time: MagicMock,
        mock_run: MagicMock,
    ) -> None:
        """Test _verify_worker_process handles pgrep command timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="pgrep", timeout=2)
        call_count = 0
        timeline = [0, 1, 6]

        def advancing_time():
            nonlocal call_count
            idx = min(call_count, len(timeline) - 1)
            call_count += 1
            return timeline[idx]

        mock_time.side_effect = advancing_time

        launcher = ContainerLauncher()
        result = launcher._verify_worker_process("container-abc123", timeout=5.0)

        assert result is False

    @patch("subprocess.run")
    @patch("time.time")
    @patch("time.sleep")
    def test_verify_worker_process_generic_exception(
        self,
        mock_sleep: MagicMock,
        mock_time: MagicMock,
        mock_run: MagicMock,
    ) -> None:
        """Test _verify_worker_process handles generic exceptions."""
        mock_run.side_effect = Exception("Docker exec failed unexpectedly")
        call_count = 0
        timeline = [0, 1, 6]

        def advancing_time():
            nonlocal call_count
            idx = min(call_count, len(timeline) - 1)
            call_count += 1
            return timeline[idx]

        mock_time.side_effect = advancing_time

        launcher = ContainerLauncher()
        result = launcher._verify_worker_process("container-abc123", timeout=5.0)

        assert result is False

    @patch("subprocess.run")
    @patch("time.time")
    @patch("time.sleep")
    def test_verify_worker_process_success_after_retry(
        self,
        mock_sleep: MagicMock,
        mock_time: MagicMock,
        mock_run: MagicMock,
    ) -> None:
        """Test _verify_worker_process succeeds after initial failures."""
        # First attempt fails, second succeeds
        mock_run.side_effect = [
            MagicMock(returncode=1, stdout="", stderr=""),  # Not found
            MagicMock(returncode=0, stdout="12345\n", stderr=""),  # Found
        ]
        call_count = 0
        timeline = [0, 1, 2]

        def advancing_time():
            nonlocal call_count
            idx = min(call_count, len(timeline) - 1)
            call_count += 1
            return timeline[idx]

        mock_time.side_effect = advancing_time

        launcher = ContainerLauncher()
        result = launcher._verify_worker_process("container-abc123", timeout=5.0)

        assert result is True


class TestExecWorkerEntryErrors:
    """Tests for _exec_worker_entry error handling."""

    @patch("subprocess.run")
    def test_exec_worker_entry_timeout(self, mock_run: MagicMock) -> None:
        """Test _exec_worker_entry handles command timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="docker exec", timeout=30)

        launcher = ContainerLauncher()
        result = launcher._exec_worker_entry("container-abc123")

        assert result is False

    @patch("subprocess.run")
    def test_exec_worker_entry_container_not_running(self, mock_run: MagicMock) -> None:
        """Test _exec_worker_entry fails when container stopped."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Error response from daemon: Container is not running",
        )

        launcher = ContainerLauncher()
        result = launcher._exec_worker_entry("container-abc123")

        assert result is False

    @patch("subprocess.run")
    def test_exec_worker_entry_script_not_found(self, mock_run: MagicMock) -> None:
        """Test _exec_worker_entry fails when entry script missing."""
        mock_run.return_value = MagicMock(
            returncode=126,
            stdout="",
            stderr="/workspace/.zerg/worker_entry.sh: No such file or directory",
        )

        launcher = ContainerLauncher()
        result = launcher._exec_worker_entry("container-abc123")

        assert result is False

    @patch("subprocess.run")
    def test_exec_worker_entry_permission_denied(self, mock_run: MagicMock) -> None:
        """Test _exec_worker_entry fails when script not executable."""
        mock_run.return_value = MagicMock(
            returncode=126,
            stdout="",
            stderr="/workspace/.zerg/worker_entry.sh: Permission denied",
        )

        launcher = ContainerLauncher()
        result = launcher._exec_worker_entry("container-abc123")

        assert result is False


class TestStartContainerErrors:
    """Tests for _start_container error handling."""

    @patch("subprocess.run")
    def test_start_container_name_conflict(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test _start_container fails when container name already exists."""
        mock_run.return_value = MagicMock(
            returncode=125,
            stdout="",
            stderr='Error response from daemon: Conflict. The container name "/zerg-worker-0" '
            "is already in use by container",
        )

        launcher = ContainerLauncher()
        result = launcher._start_container(
            container_name="zerg-worker-0",
            worktree_path=tmp_path,
            env={"ZERG_WORKER_ID": "0"},
        )

        assert result is None

    @patch("subprocess.run")
    def test_start_container_mount_path_not_found(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test _start_container fails when mount path doesn't exist."""
        mock_run.return_value = MagicMock(
            returncode=125,
            stdout="",
            stderr="Error response from daemon: invalid mount config: source path does not exist",
        )

        launcher = ContainerLauncher()
        result = launcher._start_container(
            container_name="zerg-worker-0",
            worktree_path=tmp_path / "nonexistent",
            env={},
        )

        assert result is None

    @patch("subprocess.run")
    def test_start_container_network_not_found(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test _start_container fails when network doesn't exist."""
        mock_run.return_value = MagicMock(
            returncode=125,
            stdout="",
            stderr="Error response from daemon: network custom-network not found",
        )

        launcher = ContainerLauncher(network="custom-network")
        result = launcher._start_container(
            container_name="zerg-worker-0",
            worktree_path=tmp_path,
            env={},
        )

        assert result is None

    @patch("subprocess.run")
    def test_start_container_invalid_env_var(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test _start_container behavior with invalid env var format (Docker handles)."""
        # Docker would reject invalid env var syntax
        mock_run.return_value = MagicMock(
            returncode=125,
            stdout="",
            stderr="Error response from daemon: invalid environment variable",
        )

        launcher = ContainerLauncher()
        result = launcher._start_container(
            container_name="zerg-worker-0",
            worktree_path=tmp_path,
            env={"INVALID=VAR=NAME": "value"},
        )

        assert result is None


class TestMonitorErrors:
    """Tests for monitor method error handling."""

    @patch("subprocess.run")
    def test_monitor_container_removed(self, mock_run: MagicMock) -> None:
        """Test monitor handles container that was removed externally."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Error: No such object: container-abc123",
        )

        launcher = ContainerLauncher()
        handle = WorkerHandle(worker_id=0, container_id="container-abc123")
        launcher._workers[0] = handle
        launcher._container_ids[0] = "container-abc123"

        status = launcher.monitor(0)

        assert status == WorkerStatus.STOPPED
        assert handle.status == WorkerStatus.STOPPED

    @patch("subprocess.run")
    def test_monitor_docker_inspect_timeout(self, mock_run: MagicMock) -> None:
        """Test monitor handles docker inspect timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="docker inspect", timeout=10)

        launcher = ContainerLauncher()
        handle = WorkerHandle(
            worker_id=0,
            container_id="container-abc123",
            status=WorkerStatus.RUNNING,
        )
        launcher._workers[0] = handle
        launcher._container_ids[0] = "container-abc123"

        status = launcher.monitor(0)

        # Should return current status on error
        assert status == WorkerStatus.RUNNING

    @patch("subprocess.run")
    def test_monitor_malformed_output(self, mock_run: MagicMock) -> None:
        """Test monitor handles malformed docker inspect output."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="invalid-output-format\n",
            stderr="",
        )

        launcher = ContainerLauncher()
        handle = WorkerHandle(
            worker_id=0,
            container_id="container-abc123",
            status=WorkerStatus.RUNNING,
        )
        launcher._workers[0] = handle
        launcher._container_ids[0] = "container-abc123"

        status = launcher.monitor(0)

        # Exception should be caught, returns current status
        assert status == WorkerStatus.RUNNING


class TestTerminateErrors:
    """Tests for terminate method error handling."""

    @patch("subprocess.run")
    def test_terminate_already_stopped_container(self, mock_run: MagicMock) -> None:
        """Test terminate handles already stopped container."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Error response from daemon: Container is not running",
        )

        launcher = ContainerLauncher()
        handle = WorkerHandle(worker_id=0, container_id="container-abc123")
        launcher._workers[0] = handle
        launcher._container_ids[0] = "container-abc123"

        result = launcher.terminate(0)

        assert result is False
        # Container ID should still be cleaned up in finally block
        assert 0 not in launcher._container_ids

    @patch("subprocess.run")
    def test_terminate_cleanup_after_double_failure(self, mock_run: MagicMock) -> None:
        """Test terminate cleans up even when both stop and remove fail."""
        mock_run.side_effect = [
            MagicMock(returncode=1, stdout="", stderr="stop failed"),  # docker stop
        ]

        launcher = ContainerLauncher()
        handle = WorkerHandle(worker_id=0, container_id="container-abc123")
        launcher._workers[0] = handle
        launcher._container_ids[0] = "container-abc123"

        result = launcher.terminate(0)

        assert result is False
        # Cleanup should still happen in finally block
        assert 0 not in launcher._container_ids
        assert 0 not in launcher._workers
