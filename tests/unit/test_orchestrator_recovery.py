"""Tests for Orchestrator error recovery paths.

This module covers:
1. _set_recoverable_error setting pause state
2. _set_recoverable_error setting error message
3. Resume from recoverable error
4. Worker respawn after crash
5. Worktree cleanup on recovery
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zerg.constants import WorkerStatus
from zerg.orchestrator import Orchestrator


@pytest.fixture
def mock_orchestrator_deps():
    """Mock all orchestrator dependencies for recovery testing."""
    with (
        patch("zerg.orchestrator.StateManager") as state_mock,
        patch("zerg.orchestrator.LevelController") as levels_mock,
        patch("zerg.orchestrator.TaskParser") as parser_mock,
        patch("zerg.orchestrator.GateRunner") as gates_mock,
        patch("zerg.orchestrator.WorktreeManager") as worktree_mock,
        patch("zerg.orchestrator.ContainerManager") as container_mock,
        patch("zerg.orchestrator.PortAllocator") as ports_mock,
        patch("zerg.orchestrator.MergeCoordinator") as merge_mock,
        patch("zerg.orchestrator.TaskSyncBridge") as task_sync_mock,
        patch("zerg.orchestrator.SubprocessLauncher") as subprocess_launcher_mock,
        patch("zerg.orchestrator.ContainerLauncher") as container_launcher_mock,
    ):
        state = MagicMock()
        state.load.return_value = {}
        state.get_task_status.return_value = None
        state.get_task_retry_count.return_value = 0
        state.get_failed_tasks.return_value = []
        state.generate_state_md.return_value = None
        state._state = {"tasks": {}}
        state_mock.return_value = state

        levels = MagicMock()
        levels.current_level = 1
        levels.is_level_complete.return_value = False
        levels.is_level_resolved.return_value = False
        levels.can_advance.return_value = False
        levels.advance_level.return_value = 2
        levels.start_level.return_value = ["TASK-001"]
        levels.get_pending_tasks_for_level.return_value = []
        levels.get_status.return_value = {
            "current_level": 1,
            "total_tasks": 10,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "in_progress_tasks": 0,
            "progress_percent": 0,
            "is_complete": False,
            "levels": {},
        }
        levels_mock.return_value = levels

        parser = MagicMock()
        parser.get_all_tasks.return_value = []
        parser.get_task.return_value = None
        parser.get_tasks_for_level.return_value = []
        parser.total_tasks = 0
        parser.levels = [1, 2]
        parser_mock.return_value = parser

        gates = MagicMock()
        gates.run_all_gates.return_value = (True, [])
        gates_mock.return_value = gates

        worktree = MagicMock()
        worktree_info = MagicMock()
        worktree_info.path = Path("/tmp/worktree")
        worktree_info.branch = "zerg/test/worker-0"
        worktree.create.return_value = worktree_info
        worktree.get_worktree_path.return_value = Path("/tmp/worktree")
        worktree_mock.return_value = worktree

        container = MagicMock()
        container.get_status.return_value = WorkerStatus.RUNNING
        container_mock.return_value = container

        ports = MagicMock()
        ports.allocate_one.return_value = 49152
        ports_mock.return_value = ports

        merge = MagicMock()
        merge_result = MagicMock()
        merge_result.success = True
        merge_result.merge_commit = "abc123"
        merge_result.error = None
        merge.full_merge_flow.return_value = merge_result
        merge_mock.return_value = merge

        task_sync = MagicMock()
        task_sync.create_level_tasks.return_value = None
        task_sync.sync_state.return_value = None
        task_sync_mock.return_value = task_sync

        # Subprocess launcher mock
        subprocess_launcher = MagicMock()
        spawn_result = MagicMock()
        spawn_result.success = True
        spawn_result.handle = MagicMock()
        spawn_result.handle.container_id = None
        spawn_result.error = None
        subprocess_launcher.spawn.return_value = spawn_result
        subprocess_launcher.monitor.return_value = WorkerStatus.RUNNING
        subprocess_launcher.terminate.return_value = True
        subprocess_launcher.sync_state.return_value = None
        subprocess_launcher_mock.return_value = subprocess_launcher

        # Container launcher mock
        container_launcher = MagicMock()
        container_launcher.spawn.return_value = spawn_result
        container_launcher.monitor.return_value = WorkerStatus.RUNNING
        container_launcher.terminate.return_value = True
        container_launcher.ensure_network.return_value = None
        container_launcher.sync_state.return_value = None
        container_launcher_mock.return_value = container_launcher

        yield {
            "state": state,
            "levels": levels,
            "parser": parser,
            "gates": gates,
            "worktree": worktree,
            "container": container,
            "ports": ports,
            "merge": merge,
            "task_sync": task_sync,
            "subprocess_launcher": subprocess_launcher,
            "container_launcher": container_launcher,
            "subprocess_launcher_mock": subprocess_launcher_mock,
            "container_launcher_mock": container_launcher_mock,
            "worktree_mock": worktree_mock,
        }


class TestSetRecoverableErrorPauseState:
    """Tests for _set_recoverable_error setting pause state."""

    def test_set_recoverable_error_sets_paused_true(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test _set_recoverable_error sets _paused to True."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")
        assert orch._paused is False

        orch._set_recoverable_error("Test error message")

        assert orch._paused is True

    def test_set_recoverable_error_calls_state_set_paused(
        self, mock_orchestrator_deps, tmp_path: Path, monkeypatch
    ) -> None:
        """Test _set_recoverable_error calls state.set_paused(True)."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")

        orch._set_recoverable_error("Test error message")

        mock_orchestrator_deps["state"].set_paused.assert_called_once_with(True)

    def test_set_recoverable_error_preserves_running_state(
        self, mock_orchestrator_deps, tmp_path: Path, monkeypatch
    ) -> None:
        """Test _set_recoverable_error does not modify _running flag."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")
        orch._running = True

        orch._set_recoverable_error("Test error")

        # _running should remain True (paused, not stopped)
        assert orch._running is True
        assert orch._paused is True


class TestSetRecoverableErrorMessage:
    """Tests for _set_recoverable_error setting error message."""

    def test_set_recoverable_error_calls_set_error(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test _set_recoverable_error calls state.set_error with message."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")

        error_message = "Merge failed after 3 attempts"
        orch._set_recoverable_error(error_message)

        mock_orchestrator_deps["state"].set_error.assert_called_once_with(error_message)

    def test_set_recoverable_error_appends_event(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test _set_recoverable_error appends recoverable_error event."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")

        error_message = "Level 2 merge failed"
        orch._set_recoverable_error(error_message)

        mock_orchestrator_deps["state"].append_event.assert_called_with("recoverable_error", {"error": error_message})

    def test_set_recoverable_error_handles_complex_message(
        self, mock_orchestrator_deps, tmp_path: Path, monkeypatch
    ) -> None:
        """Test _set_recoverable_error handles complex error messages."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")

        complex_error = "Level 1 merge failed after 3 attempts: git error: fatal conflict in src/file.py"
        orch._set_recoverable_error(complex_error)

        mock_orchestrator_deps["state"].set_error.assert_called_once_with(complex_error)
        mock_orchestrator_deps["state"].append_event.assert_called_with("recoverable_error", {"error": complex_error})


class TestResumeFromRecoverableError:
    """Tests for resume from recoverable error state."""

    def test_resume_clears_paused_flag(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test resume clears the _paused flag."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")
        orch._paused = True

        orch.resume()

        assert orch._paused is False

    def test_resume_calls_state_set_paused_false(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test resume calls state.set_paused(False)."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")
        orch._paused = True

        orch.resume()

        mock_orchestrator_deps["state"].set_paused.assert_called_once_with(False)

    def test_resume_appends_resumed_event(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test resume appends resumed event to state."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")
        orch._paused = True

        orch.resume()

        mock_orchestrator_deps["state"].append_event.assert_called_with("resumed", {})

    def test_resume_when_not_paused_does_nothing(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test resume does nothing when not paused."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")
        orch._paused = False

        orch.resume()

        mock_orchestrator_deps["state"].set_paused.assert_not_called()
        mock_orchestrator_deps["state"].append_event.assert_not_called()

    def test_resume_after_recoverable_error_workflow(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test full workflow: recoverable error then resume."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")
        orch._running = True

        # Set recoverable error
        orch._set_recoverable_error("Test error")
        assert orch._paused is True
        assert orch._running is True

        # Resume
        orch.resume()
        assert orch._paused is False
        assert orch._running is True


class TestWorkerRespawnAfterCrash:
    """Tests for worker respawn after crash."""

    def test_crashed_worker_triggers_respawn(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test crashed worker triggers respawn when tasks remain."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        # Make launcher report crash, then success on respawn
        mock_orchestrator_deps["subprocess_launcher"].monitor.side_effect = [
            WorkerStatus.CRASHED,
            WorkerStatus.RUNNING,
        ]

        # Remaining tasks exist
        mock_orchestrator_deps["levels"].get_pending_tasks_for_level.return_value = ["TASK-002"]

        orch = Orchestrator("test-feature")
        orch._spawn_worker(0)
        orch._workers[0].current_task = "TASK-001"
        orch._running = True
        orch._worker_manager.running = True

        # Reset spawn call count after initial spawn
        mock_orchestrator_deps["subprocess_launcher"].spawn.reset_mock()

        orch._poll_workers()

        # Worker should be respawned
        assert mock_orchestrator_deps["subprocess_launcher"].spawn.call_count == 1

    def test_crashed_worker_marks_task_failed(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test crashed worker marks current task as failed."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        mock_orchestrator_deps["subprocess_launcher"].monitor.return_value = WorkerStatus.CRASHED

        orch = Orchestrator("test-feature")
        orch._spawn_worker(0)
        orch._workers[0].current_task = "TASK-001"
        orch._running = True

        with patch.object(orch, "_handle_task_failure") as failure_mock:
            orch._poll_workers()

        failure_mock.assert_called_with("TASK-001", 0, "Worker crashed")

    def test_crashed_worker_no_respawn_when_stopped(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test crashed worker does not respawn when orchestrator stopped."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        mock_orchestrator_deps["subprocess_launcher"].monitor.return_value = WorkerStatus.CRASHED
        mock_orchestrator_deps["levels"].get_pending_tasks_for_level.return_value = ["TASK-002"]

        orch = Orchestrator("test-feature")
        orch._spawn_worker(0)
        orch._running = False  # Stopped

        # Reset spawn call count
        mock_orchestrator_deps["subprocess_launcher"].spawn.reset_mock()

        orch._poll_workers()

        # Should not respawn since not running
        mock_orchestrator_deps["subprocess_launcher"].spawn.assert_not_called()

    def test_crashed_worker_no_respawn_when_no_remaining_tasks(
        self, mock_orchestrator_deps, tmp_path: Path, monkeypatch
    ) -> None:
        """Test crashed worker does not respawn when no tasks remain."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        mock_orchestrator_deps["subprocess_launcher"].monitor.return_value = WorkerStatus.CRASHED
        mock_orchestrator_deps["levels"].get_pending_tasks_for_level.return_value = []

        orch = Orchestrator("test-feature")
        orch._spawn_worker(0)
        orch._running = True

        # Reset spawn call count
        mock_orchestrator_deps["subprocess_launcher"].spawn.reset_mock()

        orch._poll_workers()

        # Should not respawn since no remaining tasks
        mock_orchestrator_deps["subprocess_launcher"].spawn.assert_not_called()

    def test_respawn_failure_handled_gracefully(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test respawn failure is handled gracefully."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        # First spawn succeeds, second (respawn) fails
        spawn_success = MagicMock()
        spawn_success.success = True
        spawn_success.handle = MagicMock()
        spawn_success.handle.container_id = None
        spawn_success.error = None

        spawn_fail = MagicMock()
        spawn_fail.success = False
        spawn_fail.error = "Failed to respawn"

        mock_orchestrator_deps["subprocess_launcher"].spawn.side_effect = [
            spawn_success,
            spawn_fail,
        ]
        mock_orchestrator_deps["subprocess_launcher"].monitor.return_value = WorkerStatus.STOPPED
        mock_orchestrator_deps["levels"].get_pending_tasks_for_level.return_value = ["TASK-002"]

        orch = Orchestrator("test-feature")
        orch._spawn_worker(0)
        orch._running = True

        # Should not raise
        orch._poll_workers()

        # Worker should be removed
        assert 0 not in orch._workers


class TestWorktreeCleanupOnRecovery:
    """Tests for worktree cleanup on recovery."""

    def test_terminate_worker_deletes_worktree(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test terminate worker deletes worktree."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")
        orch._spawn_worker(0)

        orch._terminate_worker(0)

        mock_orchestrator_deps["worktree"].delete.assert_called_once()

    def test_worktree_cleanup_on_failed_respawn(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test worktree cleanup when respawn fails."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        # First spawn succeeds, second fails
        spawn_success = MagicMock()
        spawn_success.success = True
        spawn_success.handle = MagicMock()
        spawn_success.handle.container_id = None
        spawn_success.error = None

        spawn_fail = MagicMock()
        spawn_fail.success = False
        spawn_fail.error = "Failed to respawn"

        mock_orchestrator_deps["subprocess_launcher"].spawn.side_effect = [
            spawn_success,
            spawn_fail,
        ]
        mock_orchestrator_deps["subprocess_launcher"].monitor.return_value = WorkerStatus.STOPPED
        mock_orchestrator_deps["levels"].get_pending_tasks_for_level.return_value = ["TASK-002"]

        orch = Orchestrator("test-feature")
        orch._spawn_worker(0)
        orch._running = True
        orch._worker_manager.running = True

        # Reset delete call count after initial spawn
        mock_orchestrator_deps["worktree"].delete.reset_mock()

        orch._poll_workers()

        # Worktree should be cleaned up after failed respawn
        mock_orchestrator_deps["worktree"].delete.assert_called()

    def test_worktree_cleanup_failure_handled_gracefully(
        self, mock_orchestrator_deps, tmp_path: Path, monkeypatch
    ) -> None:
        """Test worktree cleanup failure is handled gracefully."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        mock_orchestrator_deps["worktree"].delete.side_effect = Exception("Delete failed")

        orch = Orchestrator("test-feature")
        orch._spawn_worker(0)

        # Should not raise
        orch._terminate_worker(0)

        # Worker should still be removed
        assert 0 not in orch._workers

    def test_worktree_cleanup_with_force_flag(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test worktree deletion uses force flag."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")
        orch._spawn_worker(0)

        orch._terminate_worker(0, force=True)

        # Check delete was called with force=True
        mock_orchestrator_deps["worktree"].delete.assert_called_once()
        call_args = mock_orchestrator_deps["worktree"].delete.call_args
        assert call_args[1].get("force") is True

    def test_port_released_on_worker_exit(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test port is released when worker exits."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        mock_orchestrator_deps["subprocess_launcher"].monitor.return_value = WorkerStatus.STOPPED

        orch = Orchestrator("test-feature")
        orch._spawn_worker(0)
        worker_port = orch._workers[0].port
        orch._running = False  # Don't respawn

        orch._poll_workers()

        mock_orchestrator_deps["ports"].release.assert_called_with(worker_port)


class TestRecoveryIntegration:
    """Integration tests for recovery scenarios."""

    def test_error_pause_resume_continue_workflow(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test complete workflow: error -> pause -> resume -> continue."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")
        orch._running = True

        # Step 1: Error occurs, set recoverable error
        orch._set_recoverable_error("Level 1 merge failed")

        assert orch._paused is True
        assert orch._running is True  # Not stopped, just paused
        mock_orchestrator_deps["state"].set_error.assert_called_with("Level 1 merge failed")
        mock_orchestrator_deps["state"].set_paused.assert_called_with(True)

        # Step 2: Admin fixes issue externally

        # Step 3: Resume execution
        mock_orchestrator_deps["state"].reset_mock()
        orch.resume()

        assert orch._paused is False
        assert orch._running is True  # Still running
        mock_orchestrator_deps["state"].set_paused.assert_called_with(False)
        mock_orchestrator_deps["state"].append_event.assert_called_with("resumed", {})

    def test_multiple_recoverable_errors(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test handling multiple recoverable errors in sequence."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")

        # First error
        orch._set_recoverable_error("Error 1")
        assert orch._paused is True

        # Resume
        orch.resume()
        assert orch._paused is False

        # Second error
        orch._set_recoverable_error("Error 2")
        assert orch._paused is True

        # Verify both errors were logged
        calls = mock_orchestrator_deps["state"].set_error.call_args_list
        assert len(calls) == 2
        assert calls[0][0][0] == "Error 1"
        assert calls[1][0][0] == "Error 2"

    def test_worker_crash_during_paused_state(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test worker crash handling when orchestrator is paused."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        mock_orchestrator_deps["subprocess_launcher"].monitor.return_value = WorkerStatus.CRASHED
        mock_orchestrator_deps["levels"].get_pending_tasks_for_level.return_value = ["TASK-002"]

        orch = Orchestrator("test-feature")
        orch._spawn_worker(0)
        orch._running = True
        orch._worker_manager.running = True
        orch._paused = True  # Paused state

        # Reset spawn call count
        mock_orchestrator_deps["subprocess_launcher"].spawn.reset_mock()

        orch._poll_workers()

        # Worker should still be respawned even when paused
        # (paused affects level progression, not worker management)
        assert mock_orchestrator_deps["subprocess_launcher"].spawn.call_count == 1
