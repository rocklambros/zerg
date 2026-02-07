"""Integration tests for ContainerLauncher lifecycle.

Tests cover the full lifecycle of container workers including spawn,
status transitions, multi-worker management, cleanup, and resource tracking.
Uses MockContainerLauncher to avoid real Docker dependencies.
"""

from pathlib import Path

import pytest

from tests.mocks.mock_launcher import MockContainerLauncher
from zerg.constants import WorkerStatus
from zerg.launcher_types import WorkerHandle


class TestSpawnToTerminateLifecycle:
    """Test spawn to terminate lifecycle for container workers."""

    def test_basic_lifecycle(self, tmp_path: Path) -> None:
        """Test basic spawn, monitor, terminate lifecycle."""
        launcher = MockContainerLauncher()
        worktree = tmp_path / "worktree"
        worktree.mkdir()

        # Spawn worker
        result = launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=worktree,
            branch="zerg/test/worker-0",
        )

        assert result.success is True
        assert result.worker_id == 0
        assert result.handle is not None
        assert result.handle.status == WorkerStatus.RUNNING

        # Monitor worker
        status = launcher.monitor(0)
        assert status == WorkerStatus.RUNNING

        # Terminate worker
        terminated = launcher.terminate(0)
        assert terminated is True

        # Verify worker is stopped
        status = launcher.monitor(0)
        assert status == WorkerStatus.STOPPED


class TestMultipleWorkerManagement:
    """Test managing multiple concurrent workers."""

    def test_spawn_multiple_workers(self, tmp_path: Path) -> None:
        """Test spawning multiple workers concurrently."""
        launcher = MockContainerLauncher()
        num_workers = 5

        for worker_id in range(num_workers):
            worktree = tmp_path / f"worktree-{worker_id}"
            worktree.mkdir()

            result = launcher.spawn(
                worker_id=worker_id,
                feature="multi-worker",
                worktree_path=worktree,
                branch=f"zerg/test/worker-{worker_id}",
            )

            assert result.success is True, f"Worker {worker_id} failed to spawn"

        all_workers = launcher.get_all_workers()
        assert len(all_workers) == num_workers

        for worker_id in range(num_workers):
            status = launcher.monitor(worker_id)
            assert status == WorkerStatus.RUNNING

        results = launcher.terminate_all()
        assert all(results.values())
        assert len(results) == num_workers

    def test_mixed_worker_outcomes(self, tmp_path: Path) -> None:
        """Test managing workers with mixed success/failure outcomes."""
        launcher = MockContainerLauncher()

        launcher.configure(
            spawn_fail_workers={1},
            exec_fail_workers={3},
            process_fail_workers={5},
        )

        results = {}
        for worker_id in range(6):
            worktree = tmp_path / f"worktree-{worker_id}"
            worktree.mkdir()

            result = launcher.spawn(
                worker_id=worker_id,
                feature="mixed-outcomes",
                worktree_path=worktree,
                branch=f"zerg/test/worker-{worker_id}",
            )
            results[worker_id] = result.success

        assert results[0] is True
        assert results[2] is True
        assert results[4] is True

        assert results[1] is False
        assert results[3] is False
        assert results[5] is False

        all_workers = launcher.get_all_workers()
        assert len(all_workers) == 3
        assert 0 in all_workers
        assert 2 in all_workers
        assert 4 in all_workers


class TestWorkerStatusTransitions:
    """Test worker status transitions through lifecycle."""

    def test_running_to_stopped_on_terminate(self, tmp_path: Path) -> None:
        """Test transition from RUNNING to STOPPED on terminate."""
        launcher = MockContainerLauncher()
        worktree = tmp_path / "worktree"
        worktree.mkdir()

        launcher.spawn(
            worker_id=0,
            feature="status-test",
            worktree_path=worktree,
            branch="zerg/test/worker-0",
        )

        status = launcher.monitor(0)
        assert status == WorkerStatus.RUNNING

        launcher.terminate(0)

        status = launcher.monitor(0)
        assert status == WorkerStatus.STOPPED

    def test_running_to_crashed(self, tmp_path: Path) -> None:
        """Test transition from RUNNING to CRASHED on container crash."""
        launcher = MockContainerLauncher()
        worktree = tmp_path / "worktree"
        worktree.mkdir()

        launcher.spawn(
            worker_id=0,
            feature="crash-test",
            worktree_path=worktree,
            branch="zerg/test/worker-0",
        )

        launcher.configure(container_crash_workers={0})

        status = launcher.monitor(0)
        assert status == WorkerStatus.CRASHED

        handle = launcher.get_handle(0)
        assert handle is not None
        assert handle.exit_code == 1

    def test_status_summary(self, tmp_path: Path) -> None:
        """Test get_status_summary with various worker states."""
        launcher = MockContainerLauncher()

        for worker_id in range(3):
            worktree = tmp_path / f"worktree-{worker_id}"
            worktree.mkdir()
            launcher.spawn(
                worker_id=worker_id,
                feature="summary-test",
                worktree_path=worktree,
                branch=f"zerg/test/worker-{worker_id}",
            )

        launcher.configure(container_crash_workers={1})
        launcher.monitor(1)

        summary = launcher.get_status_summary()

        assert summary["total"] == 3
        assert summary["by_status"]["running"] == 2
        assert summary["by_status"]["crashed"] == 1
        assert summary["alive"] == 2


class TestCleanupOnOrchestratorStop:
    """Test cleanup behavior when orchestrator stops."""

    def test_terminate_all_workers(self, tmp_path: Path) -> None:
        """Test terminate_all terminates all running workers."""
        launcher = MockContainerLauncher()

        for worker_id in range(5):
            worktree = tmp_path / f"worktree-{worker_id}"
            worktree.mkdir()
            launcher.spawn(
                worker_id=worker_id,
                feature="cleanup-test",
                worktree_path=worktree,
                branch=f"zerg/test/worker-{worker_id}",
            )

        assert len(launcher.get_all_workers()) == 5

        results = launcher.terminate_all()

        assert len(results) == 5
        assert all(results.values())
        assert len(launcher.get_all_workers()) == 0

    def test_cleanup_with_mixed_states(self, tmp_path: Path) -> None:
        """Test cleanup when workers are in different states."""
        launcher = MockContainerLauncher()

        for worker_id in range(4):
            worktree = tmp_path / f"worktree-{worker_id}"
            worktree.mkdir()
            launcher.spawn(
                worker_id=worker_id,
                feature="mixed-cleanup",
                worktree_path=worktree,
                branch=f"zerg/test/worker-{worker_id}",
            )

        launcher.configure(container_crash_workers={2})
        launcher.monitor(2)

        results = launcher.terminate_all()

        for worker_id, success in results.items():
            if worker_id != 2:
                assert success is True


class TestResourceTrackingAccuracy:
    """Test accuracy of resource tracking during worker lifecycle."""

    def test_worker_handle_tracking(self, tmp_path: Path) -> None:
        """Test that worker handles are accurately tracked."""
        launcher = MockContainerLauncher()

        for worker_id in range(3):
            worktree = tmp_path / f"worktree-{worker_id}"
            worktree.mkdir()
            launcher.spawn(
                worker_id=worker_id,
                feature="handle-track",
                worktree_path=worktree,
                branch=f"zerg/test/worker-{worker_id}",
            )

        all_workers = launcher.get_all_workers()

        for worker_id in range(3):
            assert worker_id in all_workers
            handle = all_workers[worker_id]
            assert isinstance(handle, WorkerHandle)
            assert handle.worker_id == worker_id
            assert handle.container_id is not None
            assert handle.status == WorkerStatus.RUNNING

    def test_spawn_attempt_tracking(self, tmp_path: Path) -> None:
        """Test that spawn attempts are accurately recorded."""
        launcher = MockContainerLauncher()
        launcher.configure(exec_fail_workers={1})

        for worker_id in range(3):
            worktree = tmp_path / f"worktree-{worker_id}"
            worktree.mkdir()
            launcher.spawn(
                worker_id=worker_id,
                feature="spawn-track",
                worktree_path=worktree,
                branch=f"zerg/test/worker-{worker_id}",
            )

        all_attempts = launcher.get_spawn_attempts()
        successful = launcher.get_successful_spawns()
        failed = launcher.get_failed_spawns()

        assert len(all_attempts) == 3
        assert len(successful) == 2
        assert len(failed) == 1

        failed_attempt = failed[0]
        assert failed_attempt.worker_id == 1
        assert failed_attempt.exec_success is False


class TestFailureScenarios:
    """Test various failure scenarios in launcher lifecycle."""

    @pytest.mark.parametrize(
        "config_key,worker_set,expected_error_fragment",
        [
            ("spawn_fail_workers", {0}, None),
            ("exec_fail_workers", {0}, "Failed to execute worker entry script"),
            ("process_fail_workers", {0}, "Worker process failed to start"),
        ],
        ids=["spawn_fail", "exec_fail", "process_fail"],
    )
    def test_failure_types(
        self, tmp_path: Path, config_key: str, worker_set: set, expected_error_fragment: str | None
    ) -> None:
        """Test that different failure types are handled correctly."""
        launcher = MockContainerLauncher()
        launcher.configure(**{config_key: worker_set})

        worktree = tmp_path / "worktree"
        worktree.mkdir()
        result = launcher.spawn(
            worker_id=0,
            feature="fail-test",
            worktree_path=worktree,
            branch="zerg/test/worker-0",
        )

        assert result.success is False
        if expected_error_fragment:
            assert expected_error_fragment in (result.error or "")

        assert len(launcher.get_all_workers()) == 0

    def test_terminate_nonexistent_worker(self) -> None:
        """Test terminating a worker that doesn't exist."""
        launcher = MockContainerLauncher()

        result = launcher.terminate(999)
        assert result is False

    def test_monitor_nonexistent_worker(self) -> None:
        """Test monitoring a worker that doesn't exist."""
        launcher = MockContainerLauncher()

        status = launcher.monitor(999)
        assert status == WorkerStatus.STOPPED


class TestEdgeCases:
    """Test edge cases in launcher behavior."""

    def test_spawn_same_worker_id_twice(self, tmp_path: Path) -> None:
        """Test spawning with same worker ID (should overwrite)."""
        launcher = MockContainerLauncher()

        worktree1 = tmp_path / "worktree1"
        worktree1.mkdir()
        result1 = launcher.spawn(
            worker_id=0,
            feature="duplicate-test",
            worktree_path=worktree1,
            branch="zerg/test/worker-0",
        )

        worktree2 = tmp_path / "worktree2"
        worktree2.mkdir()
        result2 = launcher.spawn(
            worker_id=0,
            feature="duplicate-test",
            worktree_path=worktree2,
            branch="zerg/test/worker-0-v2",
        )

        assert result1.success is True
        assert result2.success is True

        all_workers = launcher.get_all_workers()
        assert len(all_workers) == 1

        handle = launcher.get_handle(0)
        assert handle is not None
        assert handle.container_id == result2.handle.container_id

    def test_helper_methods_return_copies(self, tmp_path: Path) -> None:
        """Test that helper methods return copies, not references."""
        launcher = MockContainerLauncher()

        worktree = tmp_path / "worktree"
        worktree.mkdir()
        launcher.spawn(
            worker_id=0,
            feature="copy-test",
            worktree_path=worktree,
            branch="zerg/test/worker-0",
        )

        workers1 = launcher.get_all_workers()
        workers1.clear()

        workers2 = launcher.get_all_workers()
        assert len(workers2) == 1

        attempts1 = launcher.get_spawn_attempts()
        attempts1.clear()

        attempts2 = launcher.get_spawn_attempts()
        assert len(attempts2) == 1
