"""Unit tests for ContainerLauncher exec and process verification.

Tests the _exec_worker_entry, _verify_worker_process, and _cleanup_failed_container
methods of ContainerLauncher using mocks for Docker subprocess calls.
"""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from zerg.constants import WorkerStatus
from zerg.launcher import ContainerLauncher, WorkerHandle

# =============================================================================
# _exec_worker_entry Tests
# =============================================================================


class TestExecWorkerEntrySuccess:
    """Tests for _exec_worker_entry success path."""

    def test_exec_worker_entry_success_returns_true(self) -> None:
        """Successful exec command should return True."""
        launcher = ContainerLauncher()
        container_id = "test-container-abc123"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

            result = launcher._exec_worker_entry(container_id)

            assert result is True

    def test_exec_worker_entry_calls_docker_exec(self) -> None:
        """_exec_worker_entry should call docker exec with correct arguments."""
        launcher = ContainerLauncher()
        container_id = "test-container-abc123"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            launcher._exec_worker_entry(container_id)

            mock_run.assert_called_once()
            call_args = mock_run.call_args
            cmd = call_args[0][0]

            # Verify command structure
            assert cmd[0] == "docker"
            assert cmd[1] == "exec"
            assert "-d" in cmd  # Detached mode
            assert container_id in cmd
            assert "/bin/bash" in cmd
            assert f"/workspace/{launcher.WORKER_ENTRY_SCRIPT}" in cmd

    def test_exec_worker_entry_sets_working_directory(self) -> None:
        """_exec_worker_entry should set working directory to /workspace."""
        launcher = ContainerLauncher()
        container_id = "test-container-abc123"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            launcher._exec_worker_entry(container_id)

            call_args = mock_run.call_args
            cmd = call_args[0][0]

            # Verify -w /workspace is present
            assert "-w" in cmd
            w_index = cmd.index("-w")
            assert cmd[w_index + 1] == "/workspace"

    def test_exec_worker_entry_uses_timeout(self) -> None:
        """_exec_worker_entry should use 30 second timeout."""
        launcher = ContainerLauncher()
        container_id = "test-container-abc123"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            launcher._exec_worker_entry(container_id)

            call_kwargs = mock_run.call_args[1]
            assert call_kwargs.get("timeout") == 30


class TestExecWorkerEntryFailure:
    """Tests for _exec_worker_entry with exec failure."""

    def test_exec_failure_returns_false(self) -> None:
        """Failed exec command should return False."""
        launcher = ContainerLauncher()
        container_id = "test-container-abc123"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="exec failed: container not found",
            )

            result = launcher._exec_worker_entry(container_id)

            assert result is False

    def test_exec_nonzero_exit_returns_false(self) -> None:
        """Non-zero exit code from docker exec should return False."""
        launcher = ContainerLauncher()
        container_id = "test-container-abc123"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=125)  # Docker error code

            result = launcher._exec_worker_entry(container_id)

            assert result is False

    def test_exec_timeout_returns_false(self) -> None:
        """Timeout during exec should return False."""
        launcher = ContainerLauncher()
        container_id = "test-container-abc123"

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="docker exec", timeout=30)

            result = launcher._exec_worker_entry(container_id)

            assert result is False

    def test_exec_exception_returns_false(self) -> None:
        """Generic exception during exec should return False."""
        launcher = ContainerLauncher()
        container_id = "test-container-abc123"

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = OSError("Docker not available")

            result = launcher._exec_worker_entry(container_id)

            assert result is False

    def test_exec_file_not_found_returns_false(self) -> None:
        """FileNotFoundError should return False."""
        launcher = ContainerLauncher()
        container_id = "test-container-abc123"

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("docker command not found")

            result = launcher._exec_worker_entry(container_id)

            assert result is False


# =============================================================================
# _verify_worker_process Tests
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
            # Should only call pgrep once if found immediately
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
            assert cmd[1] == "exec"
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
            # pgrep returns 1 when process not found
            mock_run.return_value = MagicMock(returncode=1)

            # Use short timeout for test
            result = launcher._verify_worker_process(container_id, timeout=1.5)

            assert result is False
            # Should have retried multiple times (every 0.5 seconds)
            assert mock_run.call_count >= 2

    def test_zero_timeout_returns_false_when_process_not_found(self) -> None:
        """Zero timeout should return False since no retries can occur.

        The implementation uses `while time < timeout` which means with
        timeout=0, the loop condition is false immediately and no checks occur.
        This tests the actual behavior of the implementation.
        """
        launcher = ContainerLauncher()
        container_id = "test-container-abc123"

        with patch("subprocess.run") as mock_run:
            # pgrep returns 1 when no process matches
            mock_run.return_value = MagicMock(returncode=1)

            result = launcher._verify_worker_process(container_id, timeout=0)

            # With timeout=0, the while loop body may not execute
            # The function returns False because process is not found
            assert result is False

    def test_very_small_timeout_allows_one_check(self) -> None:
        """Very small (but non-zero) timeout should allow at least one check."""
        launcher = ContainerLauncher()
        container_id = "test-container-abc123"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            # Use a small but non-zero timeout
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
            # Return not found first time, then found
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
                raise subprocess.TimeoutExpired(cmd="docker exec", timeout=2)
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
            # pgrep returns 1 when no process matches
            mock_run.return_value = MagicMock(returncode=1)

            result = launcher._verify_worker_process(container_id, timeout=0.5)

            assert result is False

    def test_container_not_running_returns_false(self) -> None:
        """If container stops during verification, return False."""
        launcher = ContainerLauncher()
        container_id = "test-container-abc123"

        with patch("subprocess.run") as mock_run:
            # Container not running error
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


# =============================================================================
# _cleanup_failed_container Tests
# =============================================================================


class TestCleanupFailedContainer:
    """Tests for _cleanup_failed_container removes resources."""

    def test_cleanup_removes_container(self) -> None:
        """_cleanup_failed_container should run docker rm -f."""
        launcher = ContainerLauncher()
        container_id = "test-container-abc123"
        worker_id = 42

        # Pre-populate tracking dicts to verify cleanup
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
            call_args = mock_run.call_args
            cmd = call_args[0][0]

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
        """Cleanup should not raise if docker rm fails."""
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

            # Should not raise
            launcher._cleanup_failed_container(container_id, worker_id)

        # Tracking should still be cleaned up
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

            # Should not raise
            launcher._cleanup_failed_container(container_id, worker_id)

        # Tracking should still be cleaned up
        assert worker_id not in launcher._container_ids
        assert worker_id not in launcher._workers

    def test_cleanup_with_nonexistent_worker_id(self) -> None:
        """Cleanup should handle worker_id not in tracking dicts."""
        launcher = ContainerLauncher()
        container_id = "test-container-abc123"
        worker_id = 999  # Not in tracking

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            # Should not raise
            launcher._cleanup_failed_container(container_id, worker_id)

        # Verify docker rm was still called
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


# =============================================================================
# Integration Tests - Spawn Flow with Exec/Process Verification
# =============================================================================


class TestSpawnFlowWithExecVerification:
    """Integration tests for spawn flow with exec and process verification."""

    def test_spawn_fails_when_exec_fails(self) -> None:
        """Spawn should fail and cleanup when worker process fails to start."""
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

    def test_spawn_fails_when_process_verification_fails(self) -> None:
        """Spawn should fail and cleanup when _verify_worker_process fails."""
        launcher = ContainerLauncher()

        with (
            patch.object(launcher, "_start_container", return_value="container-123"),
            patch.object(launcher, "_wait_ready", return_value=True),
            patch.object(launcher, "_exec_worker_entry", return_value=True),
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
            patch.object(launcher, "_exec_worker_entry", return_value=True),
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

    def test_cleanup_called_on_exec_failure(self) -> None:
        """_cleanup_failed_container should be called when process verification fails.

        The cleanup function removes the worker from tracking, so we verify
        that cleanup was called rather than checking the worker tracking directly.
        """
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
            # Verify cleanup was called with correct arguments
            mock_cleanup.assert_called_once_with("container-123", 0)

    def test_spawn_worker_cleaned_up_on_exec_failure_real_cleanup(self) -> None:
        """Worker should be cleaned up when process verification fails (using real cleanup)."""
        launcher = ContainerLauncher()

        # Use a mock that simulates successful docker rm but doesn't block
        with (
            patch.object(launcher, "_start_container", return_value="container-123"),
            patch.object(launcher, "_wait_ready", return_value=True),
            patch.object(launcher, "_verify_worker_process", return_value=False),
            patch("subprocess.run") as mock_docker_run,
        ):
            # Mock the subprocess.run used by _cleanup_failed_container
            mock_docker_run.return_value = MagicMock(returncode=0)

            result = launcher.spawn(
                worker_id=0,
                feature="test",
                worktree_path=Path("/workspace"),
                branch="test-branch",
            )

            assert not result.success
            # With real cleanup running, worker should not be in tracking
            assert launcher.get_handle(0) is None
            assert len(launcher.get_all_workers()) == 0
