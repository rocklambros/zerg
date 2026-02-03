"""Integration tests for ContainerLauncher lifecycle.

Tests cover the full lifecycle of container workers including spawn,
status transitions, multi-worker management, cleanup, and resource tracking.
Uses MockContainerLauncher to avoid real Docker dependencies.
"""

from pathlib import Path

from tests.mocks.mock_launcher import MockContainerLauncher
from zerg.constants import WorkerStatus
from zerg.launcher import LauncherConfig, WorkerHandle


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

    def test_lifecycle_with_env_vars(self, tmp_path: Path) -> None:
        """Test lifecycle with custom environment variables."""
        config = LauncherConfig(
            env_vars={"ZERG_TEST_VAR": "test_value"},
        )
        launcher = MockContainerLauncher(config=config)
        worktree = tmp_path / "worktree"
        worktree.mkdir()

        result = launcher.spawn(
            worker_id=1,
            feature="env-test",
            worktree_path=worktree,
            branch="zerg/test/worker-1",
            env={"ZERG_CUSTOM": "custom_value"},
        )

        assert result.success is True

        # Verify spawn was recorded
        attempts = launcher.get_spawn_attempts()
        assert len(attempts) == 1
        assert attempts[0].success is True

        launcher.terminate(1)

    def test_lifecycle_exec_verification(self, tmp_path: Path) -> None:
        """Test that exec verification happens during spawn."""
        launcher = MockContainerLauncher()
        worktree = tmp_path / "worktree"
        worktree.mkdir()

        result = launcher.spawn(
            worker_id=0,
            feature="exec-test",
            worktree_path=worktree,
            branch="zerg/test/worker-0",
        )

        assert result.success is True

        # Verify exec was recorded
        exec_attempts = launcher.get_exec_attempts()
        assert len(exec_attempts) == 1
        assert exec_attempts[0].success is True
        assert exec_attempts[0].process_started is True

        launcher.terminate(0)

    def test_lifecycle_process_verification(self, tmp_path: Path) -> None:
        """Test that process verification happens after exec."""
        launcher = MockContainerLauncher()
        worktree = tmp_path / "worktree"
        worktree.mkdir()

        result = launcher.spawn(
            worker_id=0,
            feature="process-test",
            worktree_path=worktree,
            branch="zerg/test/worker-0",
        )

        assert result.success is True

        # Verify process is running
        spawn_attempts = launcher.get_spawn_attempts()
        assert len(spawn_attempts) == 1
        assert spawn_attempts[0].process_verified is True

        # Container should have process running
        container_id = spawn_attempts[0].container_id
        assert container_id is not None
        assert launcher.is_process_running(container_id) is True

        launcher.terminate(0)


class TestMultipleWorkerManagement:
    """Test managing multiple concurrent workers."""

    def test_spawn_multiple_workers(self, tmp_path: Path) -> None:
        """Test spawning multiple workers concurrently."""
        launcher = MockContainerLauncher()
        num_workers = 5

        # Spawn multiple workers
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

        # Verify all workers are tracked
        all_workers = launcher.get_all_workers()
        assert len(all_workers) == num_workers

        # Verify all workers are running
        for worker_id in range(num_workers):
            status = launcher.monitor(worker_id)
            assert status == WorkerStatus.RUNNING

        # Clean up
        results = launcher.terminate_all()
        assert all(results.values())
        assert len(results) == num_workers

    def test_mixed_worker_outcomes(self, tmp_path: Path) -> None:
        """Test managing workers with mixed success/failure outcomes."""
        launcher = MockContainerLauncher()

        # Configure some workers to fail
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

        # Workers 0, 2, 4 should succeed
        assert results[0] is True
        assert results[2] is True
        assert results[4] is True

        # Workers 1, 3, 5 should fail
        assert results[1] is False  # spawn failure
        assert results[3] is False  # exec failure
        assert results[5] is False  # process failure

        # Only successful workers should be tracked
        all_workers = launcher.get_all_workers()
        assert len(all_workers) == 3
        assert 0 in all_workers
        assert 2 in all_workers
        assert 4 in all_workers

    def test_partial_termination(self, tmp_path: Path) -> None:
        """Test terminating some workers while others continue."""
        launcher = MockContainerLauncher()

        # Spawn 4 workers
        for worker_id in range(4):
            worktree = tmp_path / f"worktree-{worker_id}"
            worktree.mkdir()
            launcher.spawn(
                worker_id=worker_id,
                feature="partial-term",
                worktree_path=worktree,
                branch=f"zerg/test/worker-{worker_id}",
            )

        # Terminate workers 0 and 2
        launcher.terminate(0)
        launcher.terminate(2)

        # Verify remaining workers
        all_workers = launcher.get_all_workers()
        assert len(all_workers) == 2
        assert 1 in all_workers
        assert 3 in all_workers

        # Remaining should still be running
        assert launcher.monitor(1) == WorkerStatus.RUNNING
        assert launcher.monitor(3) == WorkerStatus.RUNNING

        launcher.terminate_all()


class TestWorkerStatusTransitions:
    """Test worker status transitions through lifecycle."""

    def test_initializing_to_running(self, tmp_path: Path) -> None:
        """Test transition from INITIALIZING to RUNNING on spawn."""
        launcher = MockContainerLauncher()
        worktree = tmp_path / "worktree"
        worktree.mkdir()

        result = launcher.spawn(
            worker_id=0,
            feature="status-test",
            worktree_path=worktree,
            branch="zerg/test/worker-0",
        )

        # After successful spawn, should be RUNNING
        assert result.handle is not None
        assert result.handle.status == WorkerStatus.RUNNING

        launcher.terminate(0)

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

        # Before termination
        status = launcher.monitor(0)
        assert status == WorkerStatus.RUNNING

        # Terminate
        launcher.terminate(0)

        # After termination
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

        # Simulate crash
        launcher.configure(container_crash_workers={0})

        # Monitor should detect crash
        status = launcher.monitor(0)
        assert status == WorkerStatus.CRASHED

        # Handle should have exit code set
        handle = launcher.get_handle(0)
        assert handle is not None
        assert handle.exit_code == 1

    def test_status_summary(self, tmp_path: Path) -> None:
        """Test get_status_summary with various worker states."""
        launcher = MockContainerLauncher()

        # Spawn 3 workers
        for worker_id in range(3):
            worktree = tmp_path / f"worktree-{worker_id}"
            worktree.mkdir()
            launcher.spawn(
                worker_id=worker_id,
                feature="summary-test",
                worktree_path=worktree,
                branch=f"zerg/test/worker-{worker_id}",
            )

        # Configure one to crash
        launcher.configure(container_crash_workers={1})

        # Trigger status update for crashed worker
        launcher.monitor(1)

        # Get summary
        summary = launcher.get_status_summary()

        assert summary["total"] == 3
        assert summary["by_status"]["running"] == 2
        assert summary["by_status"]["crashed"] == 1
        # Alive count: RUNNING is alive, CRASHED is not
        assert summary["alive"] == 2

    def test_sync_state_removes_stopped_workers(self, tmp_path: Path) -> None:
        """Test that sync_state removes stopped and crashed workers."""
        launcher = MockContainerLauncher()

        # Spawn workers
        for worker_id in range(3):
            worktree = tmp_path / f"worktree-{worker_id}"
            worktree.mkdir()
            launcher.spawn(
                worker_id=worker_id,
                feature="sync-test",
                worktree_path=worktree,
                branch=f"zerg/test/worker-{worker_id}",
            )

        # Manually stop one worker's process to simulate stopped state
        container_id = launcher._container_ids.get(1)
        if container_id:
            launcher._process_running[container_id] = False

        # Sync state
        results = launcher.sync_state()

        assert len(results) == 3
        assert results[0] == WorkerStatus.RUNNING
        assert results[1] == WorkerStatus.STOPPED
        assert results[2] == WorkerStatus.RUNNING

        # Stopped worker should be removed from tracking
        all_workers = launcher.get_all_workers()
        assert 1 not in all_workers


class TestCleanupOnOrchestratorStop:
    """Test cleanup behavior when orchestrator stops."""

    def test_terminate_all_workers(self, tmp_path: Path) -> None:
        """Test terminate_all terminates all running workers."""
        launcher = MockContainerLauncher()

        # Spawn workers
        for worker_id in range(5):
            worktree = tmp_path / f"worktree-{worker_id}"
            worktree.mkdir()
            launcher.spawn(
                worker_id=worker_id,
                feature="cleanup-test",
                worktree_path=worktree,
                branch=f"zerg/test/worker-{worker_id}",
            )

        # All should be running
        all_workers = launcher.get_all_workers()
        assert len(all_workers) == 5

        # Terminate all
        results = launcher.terminate_all()

        # All should have terminated successfully
        assert len(results) == 5
        assert all(results.values())

        # No workers should remain
        all_workers = launcher.get_all_workers()
        assert len(all_workers) == 0

    def test_terminate_all_force(self, tmp_path: Path) -> None:
        """Test force termination of all workers."""
        launcher = MockContainerLauncher()

        # Spawn workers
        for worker_id in range(3):
            worktree = tmp_path / f"worktree-{worker_id}"
            worktree.mkdir()
            launcher.spawn(
                worker_id=worker_id,
                feature="force-cleanup",
                worktree_path=worktree,
                branch=f"zerg/test/worker-{worker_id}",
            )

        # Force terminate all
        results = launcher.terminate_all(force=True)

        assert all(results.values())
        assert len(launcher.get_all_workers()) == 0

    def test_cleanup_with_mixed_states(self, tmp_path: Path) -> None:
        """Test cleanup when workers are in different states."""
        launcher = MockContainerLauncher()

        # Spawn workers
        for worker_id in range(4):
            worktree = tmp_path / f"worktree-{worker_id}"
            worktree.mkdir()
            launcher.spawn(
                worker_id=worker_id,
                feature="mixed-cleanup",
                worktree_path=worktree,
                branch=f"zerg/test/worker-{worker_id}",
            )

        # Configure one to be crashed
        launcher.configure(container_crash_workers={2})

        # Trigger crash detection
        launcher.monitor(2)

        # Terminate remaining (non-crashed workers)
        results = launcher.terminate_all()

        # All terminations should succeed
        for worker_id, success in results.items():
            if worker_id != 2:  # Crashed workers might have different behavior
                assert success is True

    def test_cleanup_handles_already_stopped(self, tmp_path: Path) -> None:
        """Test cleanup handles workers that already stopped."""
        launcher = MockContainerLauncher()

        # Spawn workers
        for worker_id in range(3):
            worktree = tmp_path / f"worktree-{worker_id}"
            worktree.mkdir()
            launcher.spawn(
                worker_id=worker_id,
                feature="already-stopped",
                worktree_path=worktree,
                branch=f"zerg/test/worker-{worker_id}",
            )

        # Manually terminate one
        launcher.terminate(1)

        # Now terminate_all should handle the remaining
        results = launcher.terminate_all()

        # Should only have results for remaining workers (0 and 2)
        assert len(results) == 2
        assert 0 in results
        assert 2 in results


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

        # Get all handles
        all_workers = launcher.get_all_workers()

        # Verify each handle
        for worker_id in range(3):
            assert worker_id in all_workers
            handle = all_workers[worker_id]
            assert isinstance(handle, WorkerHandle)
            assert handle.worker_id == worker_id
            assert handle.container_id is not None
            assert handle.status == WorkerStatus.RUNNING

    def test_container_id_tracking(self, tmp_path: Path) -> None:
        """Test that container IDs are accurately tracked."""
        launcher = MockContainerLauncher()

        container_ids = []
        for worker_id in range(3):
            worktree = tmp_path / f"worktree-{worker_id}"
            worktree.mkdir()
            result = launcher.spawn(
                worker_id=worker_id,
                feature="container-track",
                worktree_path=worktree,
                branch=f"zerg/test/worker-{worker_id}",
            )
            assert result.handle is not None
            container_ids.append(result.handle.container_id)

        # All container IDs should be unique
        assert len(set(container_ids)) == 3

        # Container IDs should match internal tracking
        for worker_id in range(3):
            handle = launcher.get_handle(worker_id)
            assert handle is not None
            assert handle.container_id == launcher._container_ids[worker_id]

    def test_spawn_attempt_tracking(self, tmp_path: Path) -> None:
        """Test that spawn attempts are accurately recorded."""
        launcher = MockContainerLauncher()
        launcher.configure(exec_fail_workers={1})

        # Attempt spawns
        for worker_id in range(3):
            worktree = tmp_path / f"worktree-{worker_id}"
            worktree.mkdir()
            launcher.spawn(
                worker_id=worker_id,
                feature="spawn-track",
                worktree_path=worktree,
                branch=f"zerg/test/worker-{worker_id}",
            )

        # Get all attempts
        all_attempts = launcher.get_spawn_attempts()
        successful = launcher.get_successful_spawns()
        failed = launcher.get_failed_spawns()

        assert len(all_attempts) == 3
        assert len(successful) == 2  # Workers 0 and 2
        assert len(failed) == 1  # Worker 1

        # Verify failed spawn details
        failed_attempt = failed[0]
        assert failed_attempt.worker_id == 1
        assert failed_attempt.exec_success is False

    def test_exec_attempt_tracking(self, tmp_path: Path) -> None:
        """Test that exec attempts are accurately recorded."""
        launcher = MockContainerLauncher()

        for worker_id in range(2):
            worktree = tmp_path / f"worktree-{worker_id}"
            worktree.mkdir()
            launcher.spawn(
                worker_id=worker_id,
                feature="exec-track",
                worktree_path=worktree,
                branch=f"zerg/test/worker-{worker_id}",
            )

        exec_attempts = launcher.get_exec_attempts()

        assert len(exec_attempts) == 2
        for attempt in exec_attempts:
            assert attempt.success is True
            assert attempt.command == "worker_entry.sh"

    def test_process_running_state_tracking(self, tmp_path: Path) -> None:
        """Test that process running state is accurately tracked."""
        launcher = MockContainerLauncher()

        worktree = tmp_path / "worktree"
        worktree.mkdir()
        result = launcher.spawn(
            worker_id=0,
            feature="process-track",
            worktree_path=worktree,
            branch="zerg/test/worker-0",
        )

        assert result.handle is not None
        container_id = result.handle.container_id
        assert container_id is not None

        # Process should be running
        assert launcher.is_process_running(container_id) is True

        # After termination
        launcher.terminate(0)
        assert launcher.is_process_running(container_id) is False

    def test_reset_clears_all_tracking(self, tmp_path: Path) -> None:
        """Test that reset clears all tracked state."""
        launcher = MockContainerLauncher()

        # Spawn some workers
        for worker_id in range(3):
            worktree = tmp_path / f"worktree-{worker_id}"
            worktree.mkdir()
            launcher.spawn(
                worker_id=worker_id,
                feature="reset-test",
                worktree_path=worktree,
                branch=f"zerg/test/worker-{worker_id}",
            )

        # Verify tracking has data
        assert len(launcher.get_all_workers()) > 0
        assert len(launcher.get_spawn_attempts()) > 0
        assert len(launcher.get_exec_attempts()) > 0

        # Reset
        launcher.reset()

        # All tracking should be cleared
        assert len(launcher.get_all_workers()) == 0
        assert len(launcher.get_spawn_attempts()) == 0
        assert len(launcher.get_exec_attempts()) == 0
        assert len(launcher._container_ids) == 0
        assert len(launcher._process_running) == 0


class TestFailureScenarios:
    """Test various failure scenarios in launcher lifecycle."""

    def test_spawn_failure_no_cleanup_needed(self, tmp_path: Path) -> None:
        """Test that spawn failure doesn't leave orphan resources."""
        launcher = MockContainerLauncher()
        launcher.configure(spawn_fail_workers={0})

        worktree = tmp_path / "worktree"
        worktree.mkdir()
        result = launcher.spawn(
            worker_id=0,
            feature="spawn-fail",
            worktree_path=worktree,
            branch="zerg/test/worker-0",
        )

        assert result.success is False

        # No workers should be tracked
        assert len(launcher.get_all_workers()) == 0
        assert len(launcher._container_ids) == 0

    def test_exec_failure_cleans_up_container(self, tmp_path: Path) -> None:
        """Test that exec failure properly cleans up container."""
        launcher = MockContainerLauncher()
        launcher.configure(exec_fail_workers={0})

        worktree = tmp_path / "worktree"
        worktree.mkdir()
        result = launcher.spawn(
            worker_id=0,
            feature="exec-fail",
            worktree_path=worktree,
            branch="zerg/test/worker-0",
        )

        assert result.success is False
        assert "Failed to execute worker entry script" in (result.error or "")

        # Container should be cleaned up
        assert 0 not in launcher._container_ids
        assert 0 not in launcher._workers

        # Spawn attempt should record the failure
        failed = launcher.get_exec_failed_spawns()
        assert len(failed) == 1

    def test_process_verification_failure_cleans_up(self, tmp_path: Path) -> None:
        """Test that process verification failure cleans up properly."""
        launcher = MockContainerLauncher()
        launcher.configure(process_fail_workers={0})

        worktree = tmp_path / "worktree"
        worktree.mkdir()
        result = launcher.spawn(
            worker_id=0,
            feature="process-fail",
            worktree_path=worktree,
            branch="zerg/test/worker-0",
        )

        assert result.success is False
        assert "Worker process failed to start" in (result.error or "")

        # Container should be cleaned up
        assert 0 not in launcher._container_ids
        assert 0 not in launcher._workers

        # Spawn attempt should record the failure
        failed = launcher.get_process_failed_spawns()
        assert len(failed) == 1

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

    def test_get_handle_nonexistent_worker(self) -> None:
        """Test getting handle for nonexistent worker."""
        launcher = MockContainerLauncher()

        handle = launcher.get_handle(999)
        assert handle is None

    def test_get_output_nonexistent_worker(self) -> None:
        """Test getting output for nonexistent worker."""
        launcher = MockContainerLauncher()

        output = launcher.get_output(999)
        assert output == ""


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

        # Both should succeed but second overwrites first
        assert result1.success is True
        assert result2.success is True

        # Only one worker should be tracked
        all_workers = launcher.get_all_workers()
        assert len(all_workers) == 1

        # Should be the second spawn
        handle = launcher.get_handle(0)
        assert handle is not None
        assert handle.container_id == result2.handle.container_id

    def test_spawn_with_empty_feature_name(self, tmp_path: Path) -> None:
        """Test spawning with empty feature name."""
        launcher = MockContainerLauncher()

        worktree = tmp_path / "worktree"
        worktree.mkdir()
        result = launcher.spawn(
            worker_id=0,
            feature="",
            worktree_path=worktree,
            branch="zerg/test/worker-0",
        )

        # Should still succeed (empty string is valid)
        assert result.success is True

        launcher.terminate(0)

    def test_spawn_with_special_chars_in_feature(self, tmp_path: Path) -> None:
        """Test spawning with special characters in feature name."""
        launcher = MockContainerLauncher()

        worktree = tmp_path / "worktree"
        worktree.mkdir()
        result = launcher.spawn(
            worker_id=0,
            feature="test-feature_v2.0",
            worktree_path=worktree,
            branch="zerg/test/worker-0",
        )

        assert result.success is True
        launcher.terminate(0)

    def test_configure_returns_self_for_chaining(self, tmp_path: Path) -> None:
        """Test that configure returns self for method chaining."""
        launcher = MockContainerLauncher().configure(exec_fail_workers={1}).configure(spawn_fail_workers={2})

        # Last configure should win
        assert 2 in launcher._spawn_fail_workers

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

        # Get workers and modify the returned dict
        workers1 = launcher.get_all_workers()
        workers1.clear()

        # Original should be unchanged
        workers2 = launcher.get_all_workers()
        assert len(workers2) == 1

        # Same for spawn attempts
        attempts1 = launcher.get_spawn_attempts()
        attempts1.clear()

        attempts2 = launcher.get_spawn_attempts()
        assert len(attempts2) == 1
