"""Unit tests for ContainerLauncher network configuration and cleanup logic.

Tests cover:
1. Custom network configuration
2. Default bridge network
3. Container cleanup on failure
4. Cleanup removes container from tracking
5. Cleanup handles already-removed containers
"""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from zerg.launcher import (
    ContainerLauncher,
    LauncherConfig,
    WorkerHandle,
)

# =============================================================================
# Network Configuration Tests
# =============================================================================


class TestContainerLauncherNetworkConfiguration:
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

        # Verify docker run was called with --network flag
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "--network" in call_args
        network_idx = call_args.index("--network")
        assert call_args[network_idx + 1] == "custom-network"

    @patch("subprocess.run")
    def test_default_bridge_network_in_docker_command(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test that default bridge network is used in docker run."""
        mock_run.return_value = MagicMock(returncode=0, stdout="container-id-abc123\n", stderr="")

        launcher = ContainerLauncher()  # Uses default bridge network
        launcher._start_container(
            container_name="zerg-worker-0",
            worktree_path=tmp_path,
            env={"ZERG_WORKER_ID": "0"},
        )

        call_args = mock_run.call_args[0][0]
        network_idx = call_args.index("--network")
        assert call_args[network_idx + 1] == "bridge"


# =============================================================================
# Container Cleanup on Failure Tests
# =============================================================================


class TestContainerLauncherCleanupOnFailure:
    """Tests for ContainerLauncher cleanup behavior on spawn failure."""

    @patch.object(ContainerLauncher, "_cleanup_failed_container")
    @patch.object(ContainerLauncher, "_verify_worker_process")
    @patch.object(ContainerLauncher, "_wait_ready")
    @patch.object(ContainerLauncher, "_start_container")
    def test_cleanup_called_on_exec_failure(
        self,
        mock_start: MagicMock,
        mock_wait: MagicMock,
        mock_verify: MagicMock,
        mock_cleanup: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test cleanup is called when worker process fails to start."""
        mock_start.return_value = "container-abc123"
        mock_wait.return_value = True
        mock_verify.return_value = False  # Process verification fails

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
    @patch.object(ContainerLauncher, "_exec_worker_entry")
    @patch.object(ContainerLauncher, "_wait_ready")
    @patch.object(ContainerLauncher, "_start_container")
    def test_cleanup_called_on_verify_failure(
        self,
        mock_start: MagicMock,
        mock_wait: MagicMock,
        mock_exec: MagicMock,
        mock_verify: MagicMock,
        mock_cleanup: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test cleanup is called when worker process verification fails."""
        mock_start.return_value = "container-abc123"
        mock_wait.return_value = True
        mock_exec.return_value = True
        mock_verify.return_value = False  # Process verification fails

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
    def test_no_cleanup_on_container_start_failure(self, mock_start: MagicMock, tmp_path: Path) -> None:
        """Test no cleanup needed when container start fails (nothing to clean)."""
        mock_start.return_value = None  # Container start fails

        launcher = ContainerLauncher()
        result = launcher.spawn(
            worker_id=0,
            feature="test",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        assert result.success is False
        assert "Failed to start container" in result.error
        # No container ID stored since start failed
        assert 0 not in launcher._container_ids
        assert 0 not in launcher._workers


# =============================================================================
# _cleanup_failed_container Tests
# =============================================================================


class TestCleanupFailedContainer:
    """Tests for ContainerLauncher._cleanup_failed_container method."""

    @patch("subprocess.run")
    def test_cleanup_removes_container_with_docker_rm(self, mock_run: MagicMock) -> None:
        """Test cleanup runs docker rm -f on the container."""
        mock_run.return_value = MagicMock(returncode=0)

        launcher = ContainerLauncher()
        # Set up tracking as if container was partially started
        launcher._workers[0] = WorkerHandle(worker_id=0, container_id="container-abc")
        launcher._container_ids[0] = "container-abc"

        launcher._cleanup_failed_container("container-abc", 0)

        # Verify docker rm -f was called
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert call_args == ["docker", "rm", "-f", "container-abc"]

    @patch("subprocess.run")
    def test_cleanup_removes_from_tracking(self, mock_run: MagicMock) -> None:
        """Test cleanup removes container from internal tracking dictionaries."""
        mock_run.return_value = MagicMock(returncode=0)

        launcher = ContainerLauncher()
        # Set up tracking
        launcher._workers[0] = WorkerHandle(worker_id=0, container_id="container-abc")
        launcher._workers[1] = WorkerHandle(worker_id=1, container_id="container-def")
        launcher._container_ids[0] = "container-abc"
        launcher._container_ids[1] = "container-def"

        launcher._cleanup_failed_container("container-abc", 0)

        # Worker 0 should be removed, worker 1 should remain
        assert 0 not in launcher._workers
        assert 0 not in launcher._container_ids
        assert 1 in launcher._workers
        assert 1 in launcher._container_ids

    @patch("subprocess.run")
    def test_cleanup_handles_docker_rm_failure(self, mock_run: MagicMock) -> None:
        """Test cleanup handles docker rm failure gracefully."""
        mock_run.return_value = MagicMock(returncode=1, stderr="No such container")

        launcher = ContainerLauncher()
        launcher._workers[0] = WorkerHandle(worker_id=0, container_id="container-abc")
        launcher._container_ids[0] = "container-abc"

        # Should not raise exception
        launcher._cleanup_failed_container("container-abc", 0)

        # Tracking should still be cleaned up
        assert 0 not in launcher._workers
        assert 0 not in launcher._container_ids

    @patch("subprocess.run")
    def test_cleanup_handles_already_removed_container(self, mock_run: MagicMock) -> None:
        """Test cleanup handles container that was already removed."""
        mock_run.side_effect = subprocess.TimeoutExpired("docker", 10)

        launcher = ContainerLauncher()
        launcher._workers[0] = WorkerHandle(worker_id=0, container_id="container-abc")
        launcher._container_ids[0] = "container-abc"

        # Should not raise exception even with timeout
        launcher._cleanup_failed_container("container-abc", 0)

        # Tracking should still be cleaned up
        assert 0 not in launcher._workers
        assert 0 not in launcher._container_ids

    @patch("subprocess.run")
    def test_cleanup_handles_generic_exception(self, mock_run: MagicMock) -> None:
        """Test cleanup handles generic exceptions gracefully."""
        mock_run.side_effect = Exception("Docker daemon not responding")

        launcher = ContainerLauncher()
        launcher._workers[0] = WorkerHandle(worker_id=0, container_id="container-abc")
        launcher._container_ids[0] = "container-abc"

        # Should not raise exception
        launcher._cleanup_failed_container("container-abc", 0)

        # Tracking should still be cleaned up despite docker failure
        assert 0 not in launcher._workers
        assert 0 not in launcher._container_ids

    @patch("subprocess.run")
    def test_cleanup_with_nonexistent_worker_id(self, mock_run: MagicMock) -> None:
        """Test cleanup handles worker_id not in tracking."""
        mock_run.return_value = MagicMock(returncode=0)

        launcher = ContainerLauncher()
        # Worker 99 is not tracked

        # Should not raise exception
        launcher._cleanup_failed_container("container-xyz", 99)

        # Docker rm should still be attempted
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_cleanup_only_removes_specified_worker(self, mock_run: MagicMock) -> None:
        """Test cleanup only removes the specified worker, not others."""
        mock_run.return_value = MagicMock(returncode=0)

        launcher = ContainerLauncher()
        # Set up multiple workers
        for i in range(5):
            launcher._workers[i] = WorkerHandle(worker_id=i, container_id=f"container-{i}")
            launcher._container_ids[i] = f"container-{i}"

        # Clean up worker 2
        launcher._cleanup_failed_container("container-2", 2)

        # Only worker 2 should be removed
        assert 2 not in launcher._workers
        assert 2 not in launcher._container_ids
        # Others should remain
        for i in [0, 1, 3, 4]:
            assert i in launcher._workers
            assert i in launcher._container_ids


# =============================================================================
# Terminate Cleanup Tests
# =============================================================================


class TestContainerLauncherTerminateCleanup:
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
        # docker stop fails, but cleanup should still happen in finally block
        mock_run.return_value = MagicMock(returncode=1, stderr="Container already stopped")

        launcher = ContainerLauncher()
        handle = WorkerHandle(worker_id=0, container_id="container-abc")
        launcher._workers[0] = handle
        launcher._container_ids[0] = "container-abc"

        result = launcher.terminate(0)

        # Even though docker stop failed, tracking should be cleaned
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

        # Exception should be caught and tracking cleaned up
        assert result is False
        assert 0 not in launcher._container_ids
        assert 0 not in launcher._workers

    @patch("subprocess.run")
    def test_terminate_cleans_up_on_timeout(self, mock_run: MagicMock) -> None:
        """Test terminate cleans up on timeout with force kill."""
        # First call times out, second (kill) succeeds
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


# =============================================================================
# Integration Tests for Network and Cleanup
# =============================================================================


class TestNetworkAndCleanupIntegration:
    """Integration tests for network configuration and cleanup interactions."""

    @patch("subprocess.run")
    def test_custom_network_in_ensure_network(self, mock_run: MagicMock) -> None:
        """Test ensure_network uses the configured custom network."""
        mock_run.return_value = MagicMock(returncode=0)

        launcher = ContainerLauncher(network="my-custom-network")
        result = launcher.ensure_network()

        assert result is True
        # Check that docker network inspect was called with custom network
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
        # Verify second call was network create with custom name
        create_call = mock_run.call_args_list[1]
        call_args = create_call[0][0]
        assert "docker" in call_args
        assert "network" in call_args
        assert "create" in call_args
        assert "new-custom-network" in call_args

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
        # First spawn succeeds
        mock_start.return_value = "container-0"
        mock_wait.return_value = True
        mock_verify.return_value = True

        launcher = ContainerLauncher()

        # Manually track a pre-existing worker
        launcher._workers[1] = WorkerHandle(worker_id=1, container_id="container-1")
        launcher._container_ids[1] = "container-1"

        # Now simulate spawn of worker 2 that fails at process verification
        mock_start.return_value = "container-2"
        mock_verify.return_value = False  # This one fails

        # Make cleanup actually remove from tracking (simulating real behavior)
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
        # Worker 1 should still be tracked
        assert 1 in launcher._workers
        assert 1 in launcher._container_ids
        # Worker 2 should have been cleaned up
        mock_cleanup.assert_called_with("container-2", 2)
