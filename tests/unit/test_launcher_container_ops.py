"""Unit tests for ContainerLauncher operations.

Consolidated from:
- test_launcher_process.py (run_worker_entry, verify, cleanup, spawn flow)
- test_launcher_network.py (network config, cleanup, terminate)
- test_launcher_exec.py (mock-based verification)
- test_launcher_errors.py (docker errors, resource limits, monitor/terminate errors)

Organized by method under test with duplicates removed.
"""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from tests.mocks.mock_launcher import MockContainerLauncher
from zerg.constants import WorkerStatus
from zerg.launcher_types import LauncherConfig, WorkerHandle
from zerg.launchers import ContainerLauncher

# =============================================================================
# Network Configuration
# =============================================================================


class TestNetworkConfiguration:
    """Tests for ContainerLauncher network configuration."""

    def test_default_bridge_network(self) -> None:
        """Test that default network is 'bridge' for internet access."""
        launcher = ContainerLauncher()
        assert launcher.network == "bridge"
        assert launcher.network == ContainerLauncher.DEFAULT_NETWORK

    def test_custom_network_configuration(self) -> None:
        """Test custom network can be specified at initialization."""
        custom_network = "zerg-internal"
        launcher = ContainerLauncher(network=custom_network)
        assert launcher.network == custom_network

    def test_custom_network_with_config(self) -> None:
        """Test custom network with LauncherConfig."""
        config = LauncherConfig(timeout_seconds=1800)
        launcher = ContainerLauncher(config=config, network="custom-net")
        assert launcher.network == "custom-net"
        assert launcher.config.timeout_seconds == 1800

    def test_none_network_uses_default(self) -> None:
        """Test that None network falls back to default bridge."""
        launcher = ContainerLauncher(network=None)
        assert launcher.network == "bridge"

    def test_empty_string_network_falls_back_to_default(self) -> None:
        """Test that empty string network falls back to default bridge.

        The implementation uses 'network or DEFAULT_NETWORK' which treats
        empty string as falsy, thus falling back to the default.
        """
        launcher = ContainerLauncher(network="")
        assert launcher.network == "bridge"

    @patch("subprocess.run")
    def test_network_used_in_docker_run_command(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test that configured network is passed to docker run."""
        mock_run.return_value = MagicMock(returncode=0, stdout="container-id-abc123\n", stderr="")

        launcher = ContainerLauncher(network="custom-network")
        launcher._start_container(
            container_name="zerg-worker-0",
            worktree_path=tmp_path,
            env={"ZERG_WORKER_ID": "0"},
        )

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "--network" in call_args
        network_idx = call_args.index("--network")
        assert call_args[network_idx + 1] == "custom-network"

    @patch("subprocess.run")
    def test_default_bridge_network_in_docker_command(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test that default bridge network is used in docker run."""
        mock_run.return_value = MagicMock(returncode=0, stdout="container-id-abc123\n", stderr="")

        launcher = ContainerLauncher()
        launcher._start_container(
            container_name="zerg-worker-0",
            worktree_path=tmp_path,
            env={"ZERG_WORKER_ID": "0"},
        )

        call_args = mock_run.call_args[0][0]
        network_idx = call_args.index("--network")
        assert call_args[network_idx + 1] == "bridge"

    @patch("subprocess.run")
    def test_custom_network_in_ensure_network(self, mock_run: MagicMock) -> None:
        """Test ensure_network uses the configured custom network."""
        mock_run.return_value = MagicMock(returncode=0)

        launcher = ContainerLauncher(network="my-custom-network")
        result = launcher.ensure_network()

        assert result is True
        call_args = mock_run.call_args[0][0]
        assert "docker" in call_args
        assert "network" in call_args
        assert "inspect" in call_args
        assert "my-custom-network" in call_args

    @patch("subprocess.run")
    def test_custom_network_creation_on_missing(self, mock_run: MagicMock) -> None:
        """Test custom network is created when it does not exist."""
        mock_run.side_effect = [
            MagicMock(returncode=1),  # network inspect fails (not found)
            MagicMock(returncode=0),  # network create succeeds
        ]

        launcher = ContainerLauncher(network="new-custom-network")
        result = launcher.ensure_network()

        assert result is True
        create_call = mock_run.call_args_list[1]
        call_args = create_call[0][0]
        assert "docker" in call_args
        assert "network" in call_args
        assert "create" in call_args
        assert "new-custom-network" in call_args


# =============================================================================
# _run_worker_entry Tests (Success + Failure + Errors)
# =============================================================================


class TestRunWorkerEntrySuccess:
    """Tests for _run_worker_entry success path."""

    def test_run_worker_entry_success_returns_true(self) -> None:
        """Successful docker-exec command should return True."""
        launcher = ContainerLauncher()
        container_id = "test-container-abc123"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            result = launcher._run_worker_entry(container_id)
            assert result is True

    def test_run_worker_entry_calls_docker_correctly(self) -> None:
        """_run_worker_entry should call docker with correct arguments."""
        launcher = ContainerLauncher()
        container_id = "test-container-abc123"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            launcher._run_worker_entry(container_id)

            mock_run.assert_called_once()
            call_args = mock_run.call_args
            cmd = call_args[0][0]

            assert cmd[0] == "docker"
            assert "-d" in cmd
            assert container_id in cmd
            assert "/bin/bash" in cmd
            assert f"/workspace/{launcher.WORKER_ENTRY_SCRIPT}" in cmd

    def test_run_worker_entry_sets_working_directory(self) -> None:
        """_run_worker_entry should set working directory to /workspace."""
        launcher = ContainerLauncher()
        container_id = "test-container-abc123"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            launcher._run_worker_entry(container_id)

            cmd = mock_run.call_args[0][0]
            assert "-w" in cmd
            w_index = cmd.index("-w")
            assert cmd[w_index + 1] == "/workspace"

    def test_run_worker_entry_uses_timeout(self) -> None:
        """_run_worker_entry should use 30 second timeout."""
        launcher = ContainerLauncher()
        container_id = "test-container-abc123"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            launcher._run_worker_entry(container_id)

            call_kwargs = mock_run.call_args[1]
            assert call_kwargs.get("timeout") == 30


class TestRunWorkerEntryFailure:
    """Tests for _run_worker_entry with various failure modes."""

    def test_failure_returns_false(self) -> None:
        """Failed command should return False."""
        launcher = ContainerLauncher()
        container_id = "test-container-abc123"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="container not found",
            )
            result = launcher._run_worker_entry(container_id)
            assert result is False

    def test_nonzero_exit_returns_false(self) -> None:
        """Non-zero exit code from docker should return False."""
        launcher = ContainerLauncher()
        container_id = "test-container-abc123"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=125)
            result = launcher._run_worker_entry(container_id)
            assert result is False

    def test_timeout_returns_false(self) -> None:
        """Timeout during command should return False."""
        launcher = ContainerLauncher()
        container_id = "test-container-abc123"

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="docker", timeout=30)
            result = launcher._run_worker_entry(container_id)
            assert result is False

    def test_os_error_returns_false(self) -> None:
        """OSError during command should return False."""
        launcher = ContainerLauncher()
        container_id = "test-container-abc123"

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = OSError("Docker not available")
            result = launcher._run_worker_entry(container_id)
            assert result is False

    def test_file_not_found_returns_false(self) -> None:
        """FileNotFoundError should return False."""
        launcher = ContainerLauncher()
        container_id = "test-container-abc123"

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("docker command not found")
            result = launcher._run_worker_entry(container_id)
            assert result is False

    @patch("subprocess.run")
    def test_container_not_running(self, mock_run: MagicMock) -> None:
        """Fails when container stopped."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Error response from daemon: Container is not running",
        )

        launcher = ContainerLauncher()
        result = launcher._run_worker_entry("container-abc123")
        assert result is False

    @patch("subprocess.run")
    def test_script_not_found(self, mock_run: MagicMock) -> None:
        """Fails when entry script missing."""
        mock_run.return_value = MagicMock(
            returncode=126,
            stdout="",
            stderr="/workspace/.zerg/worker_entry.sh: No such file or directory",
        )

        launcher = ContainerLauncher()
        result = launcher._run_worker_entry("container-abc123")
        assert result is False

    @patch("subprocess.run")
    def test_permission_denied(self, mock_run: MagicMock) -> None:
        """Fails when script not executable."""
        mock_run.return_value = MagicMock(
            returncode=126,
            stdout="",
            stderr="/workspace/.zerg/worker_entry.sh: Permission denied",
        )

        launcher = ContainerLauncher()
        result = launcher._run_worker_entry("container-abc123")
        assert result is False


# =============================================================================
# _verify_worker_process Tests (Success + Timeout + NotFound + Errors)
# =============================================================================


class TestVerifyWorkerProcessSuccess:
    """Tests for _verify_worker_process success scenarios."""

    def test_process_found_returns_true(self) -> None:
        """If pgrep finds worker_main process, return True."""
        launcher = ContainerLauncher()
        container_id = "test-container-abc123"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=b"12345")
            result = launcher._verify_worker_process(container_id, timeout=1.0)
            assert result is True

    def test_process_found_on_first_try(self) -> None:
        """Process found immediately should return True quickly."""
        launcher = ContainerLauncher()
        container_id = "test-container-abc123"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = launcher._verify_worker_process(container_id, timeout=5.0)
            assert result is True
            assert mock_run.call_count == 1

    def test_verify_calls_pgrep_correctly(self) -> None:
        """_verify_worker_process should call pgrep with worker_main pattern."""
        launcher = ContainerLauncher()
        container_id = "test-container-abc123"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            launcher._verify_worker_process(container_id, timeout=1.0)

            mock_run.assert_called()
            call_args = mock_run.call_args
            cmd = call_args[0][0]

            assert cmd[0] == "docker"
            assert container_id in cmd
            assert "pgrep" in cmd
            assert "-f" in cmd
            assert "worker_main" in cmd


class TestVerifyWorkerProcessTimeout:
    """Tests for _verify_worker_process timeout handling."""

    def test_timeout_after_multiple_retries(self) -> None:
        """Process not found should retry until timeout."""
        launcher = ContainerLauncher()
        container_id = "test-container-abc123"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            result = launcher._verify_worker_process(container_id, timeout=1.5)
            assert result is False
            assert mock_run.call_count >= 2

    def test_zero_timeout_returns_false_when_process_not_found(self) -> None:
        """Zero timeout should return False since no retries can occur.

        The implementation uses `while time < timeout` which means with
        timeout=0, the loop condition is false immediately and no checks occur.
        """
        launcher = ContainerLauncher()
        container_id = "test-container-abc123"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            result = launcher._verify_worker_process(container_id, timeout=0)
            assert result is False

    def test_very_small_timeout_allows_one_check(self) -> None:
        """Very small (but non-zero) timeout should allow at least one check."""
        launcher = ContainerLauncher()
        container_id = "test-container-abc123"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = launcher._verify_worker_process(container_id, timeout=0.1)
            assert result is True
            assert mock_run.call_count >= 1

    def test_eventual_success_within_timeout(self) -> None:
        """Process appearing during timeout window should return True."""
        launcher = ContainerLauncher()
        container_id = "test-container-abc123"
        call_count = [0]

        def mock_subprocess_run(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] < 2:
                return MagicMock(returncode=1)
            return MagicMock(returncode=0)

        with patch("subprocess.run", side_effect=mock_subprocess_run):
            result = launcher._verify_worker_process(container_id, timeout=5.0)
            assert result is True
            assert call_count[0] >= 2

    def test_subprocess_timeout_continues_retrying(self) -> None:
        """Subprocess timeout during pgrep should continue retrying."""
        launcher = ContainerLauncher()
        container_id = "test-container-abc123"
        call_count = [0]

        def mock_subprocess_run(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] < 2:
                raise subprocess.TimeoutExpired(cmd="docker", timeout=2)
            return MagicMock(returncode=0)

        with patch("subprocess.run", side_effect=mock_subprocess_run):
            result = launcher._verify_worker_process(container_id, timeout=5.0)
            assert result is True
            assert call_count[0] >= 2


class TestVerifyWorkerProcessNotFound:
    """Tests for _verify_worker_process when process not found."""

    def test_process_not_found_returns_false(self) -> None:
        """If pgrep never finds process, return False after timeout."""
        launcher = ContainerLauncher()
        container_id = "test-container-abc123"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            result = launcher._verify_worker_process(container_id, timeout=0.5)
            assert result is False

    def test_container_not_running_returns_false(self) -> None:
        """If container stops during verification, return False."""
        launcher = ContainerLauncher()
        container_id = "test-container-abc123"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stderr=b"Error: No such container",
            )
            result = launcher._verify_worker_process(container_id, timeout=0.5)
            assert result is False

    def test_generic_exception_continues_retrying(self) -> None:
        """Generic exception during check should continue retrying."""
        launcher = ContainerLauncher()
        container_id = "test-container-abc123"
        call_count = [0]

        def mock_subprocess_run(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] < 2:
                raise Exception("Docker daemon unavailable")
            return MagicMock(returncode=0)

        with patch("subprocess.run", side_effect=mock_subprocess_run):
            result = launcher._verify_worker_process(container_id, timeout=5.0)
            assert result is True
            assert call_count[0] >= 2

    def test_all_retries_fail_returns_false(self) -> None:
        """If all retry attempts fail with exceptions, return False."""
        launcher = ContainerLauncher()
        container_id = "test-container-abc123"

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = Exception("Permanent failure")
            result = launcher._verify_worker_process(container_id, timeout=1.0)
            assert result is False


class TestVerifyWorkerProcessErrors:
    """Tests for _verify_worker_process error handling with time mocking."""

    @patch("subprocess.run")
    @patch("time.time")
    @patch("time.sleep")
    def test_verify_worker_process_timeout_with_mocked_time(
        self,
        mock_sleep: MagicMock,
        mock_time: MagicMock,
        mock_run: MagicMock,
    ) -> None:
        """Test _verify_worker_process returns False on timeout."""
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
    def test_verify_worker_process_generic_exception_with_mocked_time(
        self,
        mock_sleep: MagicMock,
        mock_time: MagicMock,
        mock_run: MagicMock,
    ) -> None:
        """Test _verify_worker_process handles generic exceptions."""
        mock_run.side_effect = Exception("Docker failed unexpectedly")
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
    def test_verify_worker_process_success_after_retry_with_mocked_time(
        self,
        mock_sleep: MagicMock,
        mock_time: MagicMock,
        mock_run: MagicMock,
    ) -> None:
        """Test _verify_worker_process succeeds after initial failures."""
        mock_run.side_effect = [
            MagicMock(returncode=1, stdout="", stderr=""),
            MagicMock(returncode=0, stdout="12345\n", stderr=""),
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


# =============================================================================
# _cleanup_failed_container Tests (consolidated from process + network + errors)
# =============================================================================


class TestCleanupFailedContainer:
    """Tests for _cleanup_failed_container (consolidated from process, network, errors)."""

    def test_cleanup_removes_container(self) -> None:
        """_cleanup_failed_container should run docker rm -f."""
        launcher = ContainerLauncher()
        container_id = "test-container-abc123"
        worker_id = 42

        launcher._container_ids[worker_id] = container_id
        launcher._workers[worker_id] = WorkerHandle(
            worker_id=worker_id,
            container_id=container_id,
            status=WorkerStatus.INITIALIZING,
        )

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            launcher._cleanup_failed_container(container_id, worker_id)

            mock_run.assert_called_once()
            cmd = mock_run.call_args[0][0]
            assert cmd == ["docker", "rm", "-f", container_id]

    def test_cleanup_removes_container_id_tracking(self) -> None:
        """Cleanup should remove worker from _container_ids dict."""
        launcher = ContainerLauncher()
        container_id = "test-container-abc123"
        worker_id = 42

        launcher._container_ids[worker_id] = container_id
        launcher._workers[worker_id] = WorkerHandle(
            worker_id=worker_id,
            container_id=container_id,
        )

        with patch("subprocess.run"):
            launcher._cleanup_failed_container(container_id, worker_id)

        assert worker_id not in launcher._container_ids

    def test_cleanup_removes_worker_handle(self) -> None:
        """Cleanup should remove worker from _workers dict."""
        launcher = ContainerLauncher()
        container_id = "test-container-abc123"
        worker_id = 42

        launcher._container_ids[worker_id] = container_id
        launcher._workers[worker_id] = WorkerHandle(
            worker_id=worker_id,
            container_id=container_id,
        )

        with patch("subprocess.run"):
            launcher._cleanup_failed_container(container_id, worker_id)

        assert worker_id not in launcher._workers

    def test_cleanup_handles_docker_failure_gracefully(self) -> None:
        """Cleanup should not raise if docker rm times out."""
        launcher = ContainerLauncher()
        container_id = "test-container-abc123"
        worker_id = 42

        launcher._container_ids[worker_id] = container_id
        launcher._workers[worker_id] = WorkerHandle(
            worker_id=worker_id,
            container_id=container_id,
        )

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="docker rm", timeout=10)
            launcher._cleanup_failed_container(container_id, worker_id)

        assert worker_id not in launcher._container_ids
        assert worker_id not in launcher._workers

    def test_cleanup_handles_exception_gracefully(self) -> None:
        """Cleanup should not raise on generic exceptions."""
        launcher = ContainerLauncher()
        container_id = "test-container-abc123"
        worker_id = 42

        launcher._container_ids[worker_id] = container_id
        launcher._workers[worker_id] = WorkerHandle(
            worker_id=worker_id,
            container_id=container_id,
        )

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = Exception("Docker daemon not responding")
            launcher._cleanup_failed_container(container_id, worker_id)

        assert worker_id not in launcher._container_ids
        assert worker_id not in launcher._workers

    def test_cleanup_with_nonexistent_worker_id(self) -> None:
        """Cleanup should handle worker_id not in tracking dicts."""
        launcher = ContainerLauncher()
        container_id = "test-container-abc123"
        worker_id = 999

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            launcher._cleanup_failed_container(container_id, worker_id)

        mock_run.assert_called_once()

    def test_cleanup_uses_timeout(self) -> None:
        """Cleanup should use 10 second timeout for docker rm."""
        launcher = ContainerLauncher()
        container_id = "test-container-abc123"
        worker_id = 42

        launcher._container_ids[worker_id] = container_id

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            launcher._cleanup_failed_container(container_id, worker_id)

            call_kwargs = mock_run.call_args[1]
            assert call_kwargs.get("timeout") == 10

    @patch("subprocess.run")
    def test_cleanup_handles_docker_rm_nonzero_returncode(self, mock_run: MagicMock) -> None:
        """Test cleanup handles docker rm failure (nonzero return) gracefully."""
        mock_run.return_value = MagicMock(returncode=1, stderr="No such container")

        launcher = ContainerLauncher()
        launcher._workers[0] = WorkerHandle(worker_id=0, container_id="container-abc")
        launcher._container_ids[0] = "container-abc"

        launcher._cleanup_failed_container("container-abc", 0)

        assert 0 not in launcher._workers
        assert 0 not in launcher._container_ids

    @patch("subprocess.run")
    def test_cleanup_only_removes_specified_worker(self, mock_run: MagicMock) -> None:
        """Test cleanup only removes the specified worker, not others."""
        mock_run.return_value = MagicMock(returncode=0)

        launcher = ContainerLauncher()
        for i in range(5):
            launcher._workers[i] = WorkerHandle(worker_id=i, container_id=f"container-{i}")
            launcher._container_ids[i] = f"container-{i}"

        launcher._cleanup_failed_container("container-2", 2)

        assert 2 not in launcher._workers
        assert 2 not in launcher._container_ids
        for i in [0, 1, 3, 4]:
            assert i in launcher._workers
            assert i in launcher._container_ids

    @patch("subprocess.run")
    def test_cleanup_removes_from_tracking_with_multiple_workers(self, mock_run: MagicMock) -> None:
        """Test cleanup removes container from tracking while others remain."""
        mock_run.return_value = MagicMock(returncode=0)

        launcher = ContainerLauncher()
        launcher._workers[0] = WorkerHandle(worker_id=0, container_id="container-abc")
        launcher._workers[1] = WorkerHandle(worker_id=1, container_id="container-def")
        launcher._container_ids[0] = "container-abc"
        launcher._container_ids[1] = "container-def"

        launcher._cleanup_failed_container("container-abc", 0)

        assert 0 not in launcher._workers
        assert 0 not in launcher._container_ids
        assert 1 in launcher._workers
        assert 1 in launcher._container_ids


# =============================================================================
# Docker Daemon / Image / Resource Errors
# =============================================================================


class TestDockerDaemonNotRunning:
    """Tests for spawn behavior when Docker daemon is not running."""

    @patch("subprocess.run")
    def test_spawn_docker_daemon_connection_refused(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test spawn fails gracefully when Docker daemon connection is refused."""
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
        """Test spawn fails when Docker socket permission denied."""
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
        """Test spawn fails when docker command not found."""
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
        assert "Failed to start container" in result.error


class TestImagePullFailure:
    """Tests for spawn behavior when image pull fails."""

    @patch("subprocess.run")
    def test_spawn_image_not_found(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test spawn fails when Docker image does not exist."""
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
            stderr="Error response from daemon: net/http: request canceled while waiting for connection",
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
        mock_run.return_value = MagicMock(returncode=0, stdout="false\n", stderr="")
        mock_time.side_effect = [0, 5, 10, 15, 20, 25, 35]

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


# =============================================================================
# _start_container Errors
# =============================================================================


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
        """Test _start_container behavior with invalid env var format."""
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


# =============================================================================
# Monitor Errors
# =============================================================================


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

        assert status == WorkerStatus.RUNNING


# =============================================================================
# Terminate Errors and Cleanup
# =============================================================================


class TestTerminateCleanup:
    """Tests for cleanup behavior in ContainerLauncher.terminate method."""

    @patch("subprocess.run")
    def test_terminate_removes_from_container_ids(self, mock_run: MagicMock) -> None:
        """Test terminate removes worker from _container_ids tracking."""
        mock_run.return_value = MagicMock(returncode=0)

        launcher = ContainerLauncher()
        handle = WorkerHandle(worker_id=0, container_id="container-abc")
        launcher._workers[0] = handle
        launcher._container_ids[0] = "container-abc"

        result = launcher.terminate(0)

        assert result is True
        assert 0 not in launcher._container_ids

    @patch("subprocess.run")
    def test_terminate_removes_from_workers(self, mock_run: MagicMock) -> None:
        """Test terminate removes worker from _workers tracking."""
        mock_run.return_value = MagicMock(returncode=0)

        launcher = ContainerLauncher()
        handle = WorkerHandle(worker_id=0, container_id="container-abc")
        launcher._workers[0] = handle
        launcher._container_ids[0] = "container-abc"

        launcher.terminate(0)

        assert 0 not in launcher._workers

    @patch("subprocess.run")
    def test_terminate_cleans_up_even_on_docker_stop_failure(self, mock_run: MagicMock) -> None:
        """Test terminate cleans up tracking even when docker stop fails."""
        mock_run.return_value = MagicMock(returncode=1, stderr="Container already stopped")

        launcher = ContainerLauncher()
        handle = WorkerHandle(worker_id=0, container_id="container-abc")
        launcher._workers[0] = handle
        launcher._container_ids[0] = "container-abc"

        result = launcher.terminate(0)

        assert result is False
        assert 0 not in launcher._container_ids
        assert 0 not in launcher._workers

    @patch("subprocess.run")
    def test_terminate_cleans_up_on_exception(self, mock_run: MagicMock) -> None:
        """Test terminate cleans up tracking even on exception."""
        mock_run.side_effect = Exception("Docker daemon not available")

        launcher = ContainerLauncher()
        handle = WorkerHandle(worker_id=0, container_id="container-abc")
        launcher._workers[0] = handle
        launcher._container_ids[0] = "container-abc"

        result = launcher.terminate(0)

        assert result is False
        assert 0 not in launcher._container_ids
        assert 0 not in launcher._workers

    @patch("subprocess.run")
    def test_terminate_cleans_up_on_timeout(self, mock_run: MagicMock) -> None:
        """Test terminate cleans up on timeout with force kill."""
        mock_run.side_effect = [
            subprocess.TimeoutExpired("docker stop", 30),
            MagicMock(returncode=0),  # docker kill succeeds
        ]

        launcher = ContainerLauncher()
        handle = WorkerHandle(worker_id=0, container_id="container-abc")
        launcher._workers[0] = handle
        launcher._container_ids[0] = "container-abc"

        result = launcher.terminate(0)

        assert result is True
        assert 0 not in launcher._container_ids
        assert 0 not in launcher._workers

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
        assert 0 not in launcher._container_ids

    @patch("subprocess.run")
    def test_terminate_cleanup_after_double_failure(self, mock_run: MagicMock) -> None:
        """Test terminate cleans up even when both stop and remove fail."""
        mock_run.side_effect = [
            MagicMock(returncode=1, stdout="", stderr="stop failed"),
        ]

        launcher = ContainerLauncher()
        handle = WorkerHandle(worker_id=0, container_id="container-abc123")
        launcher._workers[0] = handle
        launcher._container_ids[0] = "container-abc123"

        result = launcher.terminate(0)

        assert result is False
        assert 0 not in launcher._container_ids
        assert 0 not in launcher._workers


# =============================================================================
# Spawn Flow Integration (consolidated: real + mock-based)
# =============================================================================


class TestSpawnFlowCleanup:
    """Tests for spawn flow cleanup when steps fail (consolidated from
    process, network, errors)."""

    def test_spawn_fails_when_verify_fails(self) -> None:
        """Spawn should fail and cleanup when _verify_worker_process fails."""
        launcher = ContainerLauncher()

        with (
            patch.object(launcher, "_start_container", return_value="container-123"),
            patch.object(launcher, "_wait_ready", return_value=True),
            patch.object(launcher, "_verify_worker_process", return_value=False),
            patch.object(launcher, "_cleanup_failed_container") as mock_cleanup,
        ):
            result = launcher.spawn(
                worker_id=0,
                feature="test",
                worktree_path=Path("/workspace"),
                branch="test-branch",
            )

            assert not result.success
            assert "process" in result.error.lower() or "start" in result.error.lower()
            mock_cleanup.assert_called_once_with("container-123", 0)

    def test_spawn_fails_when_process_verification_fails_with_entry(self) -> None:
        """Spawn should fail and cleanup when _verify_worker_process fails after entry."""
        launcher = ContainerLauncher()

        with (
            patch.object(launcher, "_start_container", return_value="container-123"),
            patch.object(launcher, "_wait_ready", return_value=True),
            patch.object(launcher, "_run_worker_entry", return_value=True),
            patch.object(launcher, "_verify_worker_process", return_value=False),
            patch.object(launcher, "_cleanup_failed_container") as mock_cleanup,
        ):
            result = launcher.spawn(
                worker_id=0,
                feature="test",
                worktree_path=Path("/workspace"),
                branch="test-branch",
            )

            assert not result.success
            assert "process" in result.error.lower() or "start" in result.error.lower()
            mock_cleanup.assert_called_once_with("container-123", 0)

    def test_spawn_succeeds_when_all_steps_pass(self) -> None:
        """Spawn should succeed when all verification steps pass."""
        launcher = ContainerLauncher()

        with (
            patch.object(launcher, "_start_container", return_value="container-123"),
            patch.object(launcher, "_wait_ready", return_value=True),
            patch.object(launcher, "_run_worker_entry", return_value=True),
            patch.object(launcher, "_verify_worker_process", return_value=True),
        ):
            result = launcher.spawn(
                worker_id=0,
                feature="test",
                worktree_path=Path("/workspace"),
                branch="test-branch",
            )

            assert result.success
            assert result.handle is not None
            assert result.handle.status == WorkerStatus.RUNNING
            assert result.handle.container_id == "container-123"

    def test_spawn_no_cleanup_when_container_start_fails(self) -> None:
        """No cleanup should happen if container fails to start."""
        launcher = ContainerLauncher()

        with (
            patch.object(launcher, "_start_container", return_value=None),
            patch.object(launcher, "_cleanup_failed_container") as mock_cleanup,
        ):
            result = launcher.spawn(
                worker_id=0,
                feature="test",
                worktree_path=Path("/workspace"),
                branch="test-branch",
            )

            assert not result.success
            mock_cleanup.assert_not_called()

    def test_spawn_worker_cleaned_up_on_failure_real_cleanup(self) -> None:
        """Worker should be cleaned up when process verification fails (using real cleanup)."""
        launcher = ContainerLauncher()

        with (
            patch.object(launcher, "_start_container", return_value="container-123"),
            patch.object(launcher, "_wait_ready", return_value=True),
            patch.object(launcher, "_verify_worker_process", return_value=False),
            patch("subprocess.run") as mock_docker_run,
        ):
            mock_docker_run.return_value = MagicMock(returncode=0)

            result = launcher.spawn(
                worker_id=0,
                feature="test",
                worktree_path=Path("/workspace"),
                branch="test-branch",
            )

            assert not result.success
            assert launcher.get_handle(0) is None
            assert len(launcher.get_all_workers()) == 0

    @patch.object(ContainerLauncher, "_cleanup_failed_container")
    @patch.object(ContainerLauncher, "_verify_worker_process")
    @patch.object(ContainerLauncher, "_wait_ready")
    @patch.object(ContainerLauncher, "_start_container")
    def test_cleanup_called_on_failure_class_patches(
        self,
        mock_start: MagicMock,
        mock_wait: MagicMock,
        mock_verify: MagicMock,
        mock_cleanup: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test cleanup is called when worker process fails to start (class-level patches)."""
        mock_start.return_value = "container-abc123"
        mock_wait.return_value = True
        mock_verify.return_value = False

        launcher = ContainerLauncher()
        result = launcher.spawn(
            worker_id=0,
            feature="test",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        assert result.success is False
        assert "Worker process failed to start" in result.error
        mock_cleanup.assert_called_once_with("container-abc123", 0)

    @patch.object(ContainerLauncher, "_cleanup_failed_container")
    @patch.object(ContainerLauncher, "_verify_worker_process")
    @patch.object(ContainerLauncher, "_run_worker_entry")
    @patch.object(ContainerLauncher, "_wait_ready")
    @patch.object(ContainerLauncher, "_start_container")
    def test_cleanup_called_on_verify_failure_class_patches(
        self,
        mock_start: MagicMock,
        mock_wait: MagicMock,
        mock_entry: MagicMock,
        mock_verify: MagicMock,
        mock_cleanup: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test cleanup is called when process verification fails (class-level patches)."""
        mock_start.return_value = "container-abc123"
        mock_wait.return_value = True
        mock_entry.return_value = True
        mock_verify.return_value = False

        launcher = ContainerLauncher()
        result = launcher.spawn(
            worker_id=0,
            feature="test",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        assert result.success is False
        assert "Worker process failed to start" in result.error
        mock_cleanup.assert_called_once_with("container-abc123", 0)

    @patch.object(ContainerLauncher, "_start_container")
    def test_no_cleanup_on_container_start_failure_class_patch(self, mock_start: MagicMock, tmp_path: Path) -> None:
        """Test no cleanup needed when container start fails (nothing to clean)."""
        mock_start.return_value = None

        launcher = ContainerLauncher()
        result = launcher.spawn(
            worker_id=0,
            feature="test",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        assert result.success is False
        assert "Failed to start container" in result.error
        assert 0 not in launcher._container_ids
        assert 0 not in launcher._workers

    @patch.object(ContainerLauncher, "_cleanup_failed_container")
    @patch.object(ContainerLauncher, "_verify_worker_process")
    @patch.object(ContainerLauncher, "_wait_ready")
    @patch.object(ContainerLauncher, "_start_container")
    def test_spawn_cleanup_preserves_other_workers(
        self,
        mock_start: MagicMock,
        mock_wait: MagicMock,
        mock_verify: MagicMock,
        mock_cleanup: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test that cleanup after spawn failure does not affect other workers."""
        mock_start.return_value = "container-0"
        mock_wait.return_value = True
        mock_verify.return_value = True

        launcher = ContainerLauncher()

        # Manually track a pre-existing worker
        launcher._workers[1] = WorkerHandle(worker_id=1, container_id="container-1")
        launcher._container_ids[1] = "container-1"

        # Now simulate spawn of worker 2 that fails at process verification
        mock_start.return_value = "container-2"
        mock_verify.return_value = False

        def real_cleanup(container_id: str, worker_id: int) -> None:
            if worker_id in launcher._container_ids:
                del launcher._container_ids[worker_id]
            if worker_id in launcher._workers:
                del launcher._workers[worker_id]

        mock_cleanup.side_effect = real_cleanup

        result = launcher.spawn(
            worker_id=2,
            feature="test",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        assert result.success is False
        assert 1 in launcher._workers
        assert 1 in launcher._container_ids
        mock_cleanup.assert_called_with("container-2", 2)


# =============================================================================
# Mock-Based Verification (from test_launcher_exec.py)
# =============================================================================


class TestMockExecReturnValue:
    """Tests for return value using MockContainerLauncher."""

    def test_success_returns_true(self):
        """Successful operation should return True."""
        launcher = MockContainerLauncher()
        launcher.configure()

        result = launcher.spawn(
            worker_id=0,
            feature="test",
            worktree_path=Path("/workspace"),
            branch="test-branch",
        )

        assert result.success
        exec_attempts = launcher.get_exec_attempts()
        assert len(exec_attempts) == 1
        assert exec_attempts[0].success

    def test_failure_returns_false(self):
        """Failed operation should return False and fail spawn."""
        launcher = MockContainerLauncher()
        launcher.configure(exec_fail_workers={0})

        result = launcher.spawn(
            worker_id=0,
            feature="test",
            worktree_path=Path("/workspace"),
            branch="test-branch",
        )

        assert not result.success
        assert "execute" in result.error.lower() or "entry" in result.error.lower()
        exec_attempts = launcher.get_exec_attempts()
        assert len(exec_attempts) == 1
        assert not exec_attempts[0].success

    def test_failure_prevents_worker_registration(self):
        """Failed operation should not register worker."""
        launcher = MockContainerLauncher()
        launcher.configure(exec_fail_workers={0})

        result = launcher.spawn(
            worker_id=0,
            feature="test",
            worktree_path=Path("/workspace"),
            branch="test-branch",
        )

        assert not result.success
        assert launcher.get_handle(0) is None
        assert len(launcher.get_all_workers()) == 0


class TestMockProcessVerification:
    """Tests for verifying worker process using MockContainerLauncher."""

    def test_process_running_after_spawn(self):
        """Process should be verified running after spawn."""
        launcher = MockContainerLauncher()
        launcher.configure()

        result = launcher.spawn(
            worker_id=0,
            feature="test",
            worktree_path=Path("/workspace"),
            branch="test-branch",
        )

        assert result.success
        handle = launcher.get_handle(0)
        assert handle is not None
        assert handle.status == WorkerStatus.RUNNING

        container_id = handle.container_id
        assert launcher.is_process_running(container_id)

    def test_process_not_running_fails_spawn(self):
        """If process doesn't start, spawn should fail."""
        launcher = MockContainerLauncher()
        launcher.configure(process_fail_workers={0})

        result = launcher.spawn(
            worker_id=0,
            feature="test",
            worktree_path=Path("/workspace"),
            branch="test-branch",
        )

        assert not result.success
        assert "process" in result.error.lower() or "start" in result.error.lower()
        assert launcher.get_handle(0) is None

    def test_process_verification_with_timeout(self):
        """Process verification should respect timeout."""
        launcher = MockContainerLauncher()
        launcher.configure(process_verify_timeout=1.0)

        result = launcher.spawn(
            worker_id=0,
            feature="test",
            worktree_path=Path("/workspace"),
            branch="test-branch",
        )

        assert result.success


class TestMockSpawnFlowIntegration:
    """Integration tests for spawn flow using MockContainerLauncher."""

    def test_full_spawn_flow_success(self):
        """Test complete spawn flow with all checks passing."""
        launcher = MockContainerLauncher()
        launcher.configure()

        result = launcher.spawn(
            worker_id=0,
            feature="test",
            worktree_path=Path("/workspace"),
            branch="test-branch",
        )

        assert result.success
        assert result.handle is not None
        assert result.handle.container_id is not None

        spawn_attempts = launcher.get_spawn_attempts()
        assert len(spawn_attempts) == 1
        assert spawn_attempts[0].success
        assert spawn_attempts[0].exec_success
        assert spawn_attempts[0].process_verified

    def test_spawn_failure_at_container_start(self):
        """Test failure at container start stage."""
        launcher = MockContainerLauncher()
        launcher.configure(spawn_fail_workers={0})

        result = launcher.spawn(
            worker_id=0,
            feature="test",
            worktree_path=Path("/workspace"),
            branch="test-branch",
        )

        assert not result.success
        spawn_attempts = launcher.get_spawn_attempts()
        assert len(spawn_attempts) == 1
        assert spawn_attempts[0].container_id is None

    def test_spawn_failure_at_exec_stage(self):
        """Test failure at exec stage."""
        launcher = MockContainerLauncher()
        launcher.configure(exec_fail_workers={0})

        result = launcher.spawn(
            worker_id=0,
            feature="test",
            worktree_path=Path("/workspace"),
            branch="test-branch",
        )

        assert not result.success
        spawn_attempts = launcher.get_spawn_attempts()
        assert len(spawn_attempts) == 1
        assert spawn_attempts[0].container_id is not None
        assert not spawn_attempts[0].exec_success

    def test_spawn_failure_at_process_stage(self):
        """Test failure at process verification stage."""
        launcher = MockContainerLauncher()
        launcher.configure(process_fail_workers={0})

        result = launcher.spawn(
            worker_id=0,
            feature="test",
            worktree_path=Path("/workspace"),
            branch="test-branch",
        )

        assert not result.success
        spawn_attempts = launcher.get_spawn_attempts()
        assert len(spawn_attempts) == 1
        assert spawn_attempts[0].exec_success
        assert not spawn_attempts[0].process_verified


class TestMockMultipleWorkers:
    """Tests for spawning multiple workers with MockContainerLauncher."""

    def test_multiple_workers_spawn_independently(self):
        """Multiple workers should spawn independently."""
        launcher = MockContainerLauncher()
        launcher.configure()

        results = []
        for worker_id in range(3):
            result = launcher.spawn(
                worker_id=worker_id,
                feature="test",
                worktree_path=Path(f"/workspace-{worker_id}"),
                branch=f"branch-{worker_id}",
            )
            results.append(result)

        assert all(r.success for r in results)
        assert len(launcher.get_all_workers()) == 3

    def test_some_workers_fail_others_succeed(self):
        """Some workers can fail while others succeed."""
        launcher = MockContainerLauncher()
        launcher.configure(exec_fail_workers={1})

        results = []
        for worker_id in range(3):
            result = launcher.spawn(
                worker_id=worker_id,
                feature="test",
                worktree_path=Path(f"/workspace-{worker_id}"),
                branch=f"branch-{worker_id}",
            )
            results.append(result)

        assert results[0].success
        assert not results[1].success
        assert results[2].success
        assert len(launcher.get_all_workers()) == 2


class TestMockMonitorAfterSpawn:
    """Tests for monitoring workers after spawn with MockContainerLauncher."""

    def test_monitor_running_worker(self):
        """Monitor should return RUNNING for active worker."""
        launcher = MockContainerLauncher()
        launcher.configure()

        launcher.spawn(
            worker_id=0,
            feature="test",
            worktree_path=Path("/workspace"),
            branch="test-branch",
        )

        status = launcher.monitor(0)
        assert status == WorkerStatus.RUNNING

    def test_monitor_crashed_worker(self):
        """Monitor should return CRASHED for crashed worker."""
        launcher = MockContainerLauncher()
        launcher.configure(container_crash_workers={0})

        launcher.spawn(
            worker_id=0,
            feature="test",
            worktree_path=Path("/workspace"),
            branch="test-branch",
        )

        status = launcher.monitor(0)
        assert status == WorkerStatus.CRASHED

    def test_monitor_nonexistent_worker(self):
        """Monitor should return STOPPED for unknown worker."""
        launcher = MockContainerLauncher()

        status = launcher.monitor(999)
        assert status == WorkerStatus.STOPPED


class TestMockCleanupOnFailure:
    """Tests for cleanup behavior on spawn failure with MockContainerLauncher."""

    def test_container_cleaned_up_on_exec_failure(self):
        """Container should be cleaned up if operation fails."""
        launcher = MockContainerLauncher()
        launcher.configure(exec_fail_workers={0})

        result = launcher.spawn(
            worker_id=0,
            feature="test",
            worktree_path=Path("/workspace"),
            branch="test-branch",
        )

        assert not result.success
        assert launcher.get_handle(0) is None
        assert 0 not in launcher._container_ids

    def test_container_cleaned_up_on_process_failure(self):
        """Container should be cleaned up if process doesn't start."""
        launcher = MockContainerLauncher()
        launcher.configure(process_fail_workers={0})

        result = launcher.spawn(
            worker_id=0,
            feature="test",
            worktree_path=Path("/workspace"),
            branch="test-branch",
        )

        assert not result.success
        assert launcher.get_handle(0) is None
