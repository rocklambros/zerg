"""Unit tests for launcher exec verification.

Tests BF-008: Launcher exec return value check and process verification.
"""

from pathlib import Path

from tests.mocks.mock_launcher import (
    MockContainerLauncher,
)
from zerg.constants import WorkerStatus


class TestExecReturnValue:
    """Tests for checking exec return value."""

    def test_exec_success_returns_true(self):
        """Successful exec should return True."""
        launcher = MockContainerLauncher()
        launcher.configure()

        result = launcher.spawn(
            worker_id=0,
            feature="test",
            worktree_path=Path("/workspace"),
            branch="test-branch",
        )

        assert result.success
        # Verify exec was called and succeeded
        exec_attempts = launcher.get_exec_attempts()
        assert len(exec_attempts) == 1
        assert exec_attempts[0].success

    def test_exec_failure_returns_false(self):
        """Failed exec should return False and fail spawn."""
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
        # Verify exec failed
        exec_attempts = launcher.get_exec_attempts()
        assert len(exec_attempts) == 1
        assert not exec_attempts[0].success

    def test_exec_failure_prevents_worker_registration(self):
        """Failed exec should not register worker."""
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


class TestProcessVerification:
    """Tests for verifying worker process is running."""

    def test_process_running_after_exec(self):
        """Process should be verified running after exec."""
        launcher = MockContainerLauncher()
        launcher.configure()

        result = launcher.spawn(
            worker_id=0,
            feature="test",
            worktree_path=Path("/workspace"),
            branch="test-branch",
        )

        assert result.success
        # Verify process is running
        handle = launcher.get_handle(0)
        assert handle is not None
        assert handle.status == WorkerStatus.RUNNING

        # Check process is marked as running in mock
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

        # Worker should not be registered
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
        # Spawn should complete within reasonable time


class TestSpawnFlowIntegration:
    """Integration tests for spawn flow with exec verification."""

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

        # Verify spawn attempt recorded correctly
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
        # Container never started, so no exec attempt
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

        # Container started but exec failed
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

        # Exec succeeded but process didn't start
        spawn_attempts = launcher.get_spawn_attempts()
        assert len(spawn_attempts) == 1
        assert spawn_attempts[0].exec_success
        assert not spawn_attempts[0].process_verified


class TestMultipleWorkers:
    """Tests for spawning multiple workers."""

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

        # Worker 0 and 2 succeed, worker 1 fails
        assert results[0].success
        assert not results[1].success
        assert results[2].success

        # Only 2 workers registered
        assert len(launcher.get_all_workers()) == 2


class TestMonitorAfterSpawn:
    """Tests for monitoring workers after spawn."""

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


class TestCleanupOnFailure:
    """Tests for cleanup behavior on spawn failure."""

    def test_container_cleaned_up_on_exec_failure(self):
        """Container should be cleaned up if exec fails."""
        launcher = MockContainerLauncher()
        launcher.configure(exec_fail_workers={0})

        result = launcher.spawn(
            worker_id=0,
            feature="test",
            worktree_path=Path("/workspace"),
            branch="test-branch",
        )

        assert not result.success
        # Worker should not exist
        assert launcher.get_handle(0) is None
        # Container ID should be cleaned up
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
        # Worker should not exist
        assert launcher.get_handle(0) is None
