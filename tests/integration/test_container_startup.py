"""Integration test: container worker startup (mocked).

Tests BF-011: Verifies container launcher exec verification and
process startup using mocked launcher.
"""

from pathlib import Path

from tests.mocks.mock_launcher import MockContainerLauncher
from zerg.constants import WorkerStatus


class TestContainerStartupFlow:
    """Integration tests for container startup flow."""

    def test_successful_startup_flow(self):
        """Test complete successful container startup."""
        launcher = MockContainerLauncher()
        launcher.configure()

        # Spawn worker
        result = launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=Path("/workspace/worktree-0"),
            branch="zerg/test-feature/worker-0",
            env={"ZERG_FEATURE": "test-feature"},
        )

        # Verify success
        assert result.success
        assert result.handle is not None
        assert result.handle.status == WorkerStatus.RUNNING

        # Verify spawn flow
        attempts = launcher.get_spawn_attempts()
        assert len(attempts) == 1
        assert attempts[0].success
        assert attempts[0].exec_success
        assert attempts[0].process_verified

    def test_exec_failure_prevents_startup(self):
        """Container should fail if exec returns failure."""
        launcher = MockContainerLauncher()
        launcher.configure(exec_fail_workers={0})

        result = launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=Path("/workspace/worktree-0"),
            branch="zerg/test-feature/worker-0",
        )

        # Verify failure
        assert not result.success
        assert "exec" in result.error.lower() or "entry" in result.error.lower()

        # Verify flow stopped at exec
        attempts = launcher.get_spawn_attempts()
        assert len(attempts) == 1
        assert not attempts[0].exec_success

    def test_process_verification_failure(self):
        """Container should fail if process doesn't start."""
        launcher = MockContainerLauncher()
        launcher.configure(process_fail_workers={0})

        result = launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=Path("/workspace/worktree-0"),
            branch="zerg/test-feature/worker-0",
        )

        # Verify failure
        assert not result.success
        assert "process" in result.error.lower() or "start" in result.error.lower()

        # Verify exec succeeded but process failed
        attempts = launcher.get_spawn_attempts()
        assert len(attempts) == 1
        assert attempts[0].exec_success
        assert not attempts[0].process_verified


class TestMultipleWorkerStartup:
    """Tests for starting multiple workers."""

    def test_multiple_workers_start_independently(self):
        """Multiple workers should start without affecting each other."""
        launcher = MockContainerLauncher()
        launcher.configure()

        results = []
        for i in range(5):
            result = launcher.spawn(
                worker_id=i,
                feature="test-feature",
                worktree_path=Path(f"/workspace/worktree-{i}"),
                branch=f"zerg/test-feature/worker-{i}",
            )
            results.append(result)

        # All should succeed
        assert all(r.success for r in results)
        assert len(launcher.get_all_workers()) == 5

        # Each should have unique container
        container_ids = [r.handle.container_id for r in results]
        assert len(set(container_ids)) == 5

    def test_partial_failure_doesnt_affect_others(self):
        """Failure of one worker shouldn't affect others."""
        launcher = MockContainerLauncher()
        # Worker 2 has exec failure
        launcher.configure(exec_fail_workers={2})

        results = []
        for i in range(5):
            result = launcher.spawn(
                worker_id=i,
                feature="test-feature",
                worktree_path=Path(f"/workspace/worktree-{i}"),
                branch=f"zerg/test-feature/worker-{i}",
            )
            results.append(result)

        # Workers 0, 1, 3, 4 succeed; worker 2 fails
        successes = [i for i, r in enumerate(results) if r.success]
        failures = [i for i, r in enumerate(results) if not r.success]

        assert successes == [0, 1, 3, 4]
        assert failures == [2]

        # 4 workers should be registered
        assert len(launcher.get_all_workers()) == 4


class TestWorkerMonitoring:
    """Tests for worker monitoring after startup."""

    def test_monitor_healthy_worker(self):
        """Healthy worker should report RUNNING."""
        launcher = MockContainerLauncher()
        launcher.configure()

        launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=Path("/workspace/worktree-0"),
            branch="zerg/test-feature/worker-0",
        )

        status = launcher.monitor(0)
        assert status == WorkerStatus.RUNNING

    def test_monitor_crashed_worker(self):
        """Crashed worker should report CRASHED."""
        launcher = MockContainerLauncher()
        # Configure crash after spawn
        launcher.configure(container_crash_workers={0})

        launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=Path("/workspace/worktree-0"),
            branch="zerg/test-feature/worker-0",
        )

        # First call detects crash
        status = launcher.monitor(0)
        assert status == WorkerStatus.CRASHED

    def test_monitor_unknown_worker(self):
        """Unknown worker should report STOPPED."""
        launcher = MockContainerLauncher()

        status = launcher.monitor(999)
        assert status == WorkerStatus.STOPPED


class TestWorkerTermination:
    """Tests for worker termination."""

    def test_terminate_running_worker(self):
        """Should be able to terminate running worker."""
        launcher = MockContainerLauncher()
        launcher.configure()

        launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=Path("/workspace/worktree-0"),
            branch="zerg/test-feature/worker-0",
        )

        result = launcher.terminate(0)
        assert result is True

        # Worker should be gone
        status = launcher.monitor(0)
        assert status == WorkerStatus.STOPPED

    def test_terminate_all_workers(self):
        """Should be able to terminate all workers."""
        launcher = MockContainerLauncher()
        launcher.configure()

        for i in range(3):
            launcher.spawn(
                worker_id=i,
                feature="test-feature",
                worktree_path=Path(f"/workspace/worktree-{i}"),
                branch=f"zerg/test-feature/worker-{i}",
            )

        results = launcher.terminate_all()

        assert all(results.values())
        assert len(launcher.get_all_workers()) == 0


class TestStartupAttemptTracking:
    """Tests for tracking startup attempts."""

    def test_successful_attempts_tracked(self):
        """Successful startups should be tracked."""
        launcher = MockContainerLauncher()
        launcher.configure()

        for i in range(3):
            launcher.spawn(
                worker_id=i,
                feature="test-feature",
                worktree_path=Path(f"/workspace/worktree-{i}"),
                branch=f"zerg/test-feature/worker-{i}",
            )

        successful = launcher.get_successful_spawns()
        assert len(successful) == 3

    def test_failed_attempts_tracked(self):
        """Failed startups should be tracked."""
        launcher = MockContainerLauncher()
        launcher.configure(spawn_fail_workers={0, 1, 2})

        for i in range(3):
            launcher.spawn(
                worker_id=i,
                feature="test-feature",
                worktree_path=Path(f"/workspace/worktree-{i}"),
                branch=f"zerg/test-feature/worker-{i}",
            )

        failed = launcher.get_failed_spawns()
        assert len(failed) == 3

    def test_exec_failures_tracked_separately(self):
        """Exec failures should be tracked distinctly."""
        launcher = MockContainerLauncher()
        launcher.configure(exec_fail_workers={0})

        launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=Path("/workspace/worktree-0"),
            branch="zerg/test-feature/worker-0",
        )

        exec_failed = launcher.get_exec_failed_spawns()
        assert len(exec_failed) == 1
        assert exec_failed[0].worker_id == 0

    def test_process_failures_tracked_separately(self):
        """Process failures should be tracked distinctly."""
        launcher = MockContainerLauncher()
        launcher.configure(process_fail_workers={0})

        launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=Path("/workspace/worktree-0"),
            branch="zerg/test-feature/worker-0",
        )

        process_failed = launcher.get_process_failed_spawns()
        assert len(process_failed) == 1
        assert process_failed[0].worker_id == 0


class TestCleanupOnFailure:
    """Tests for cleanup behavior on startup failure."""

    def test_cleanup_on_exec_failure(self):
        """Resources should be cleaned up on exec failure."""
        launcher = MockContainerLauncher()
        launcher.configure(exec_fail_workers={0})

        result = launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=Path("/workspace/worktree-0"),
            branch="zerg/test-feature/worker-0",
        )

        assert not result.success
        # Worker should not be tracked
        assert launcher.get_handle(0) is None
        assert 0 not in launcher._container_ids

    def test_cleanup_on_process_failure(self):
        """Resources should be cleaned up on process failure."""
        launcher = MockContainerLauncher()
        launcher.configure(process_fail_workers={0})

        result = launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=Path("/workspace/worktree-0"),
            branch="zerg/test-feature/worker-0",
        )

        assert not result.success
        # Worker should not be tracked
        assert launcher.get_handle(0) is None
        assert 0 not in launcher._container_ids


class TestWorkerOutput:
    """Tests for worker output retrieval."""

    def test_get_output_from_running_worker(self):
        """Should be able to get output from running worker."""
        launcher = MockContainerLauncher()
        launcher.configure()

        launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=Path("/workspace/worktree-0"),
            branch="zerg/test-feature/worker-0",
        )

        output = launcher.get_output(0)
        assert len(output) > 0
        assert "worker" in output.lower() or "container" in output.lower()

    def test_get_output_from_unknown_worker(self):
        """Output from unknown worker should be empty."""
        launcher = MockContainerLauncher()

        output = launcher.get_output(999)
        assert output == ""
