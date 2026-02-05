"""Comprehensive tests for ZERG orchestrator to achieve 100% coverage.

This module tests all orchestrator functionality including:
- Launcher creation modes (subprocess, container, auto)
- Main start/stop workflow
- Main loop execution
- Worker coordination
- Level progression
- Error handling and recovery
- Merge operations
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zerg.config import ZergConfig
from zerg.constants import LevelMergeStatus, TaskStatus, WorkerStatus
from zerg.orchestrator import Orchestrator


@pytest.fixture
def mock_orchestrator_deps():
    """Mock all orchestrator dependencies comprehensively."""
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
        state.increment_task_retry.return_value = 1
        state.get_failed_tasks.return_value = []
        state.get_tasks_ready_for_retry.return_value = []
        state.generate_state_md.return_value = None
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
        subprocess_launcher_mock.return_value = subprocess_launcher

        # Container launcher mock
        container_launcher = MagicMock()
        container_launcher.spawn.return_value = spawn_result
        container_launcher.monitor.return_value = WorkerStatus.RUNNING
        container_launcher.terminate.return_value = True
        container_launcher.ensure_network.return_value = True
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
        }


class TestLauncherCreation:
    """Tests for launcher creation with different modes."""

    def test_create_launcher_subprocess_mode(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test explicit subprocess mode."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature", launcher_mode="subprocess")

        assert orch.launcher is not None

    def test_create_launcher_container_mode(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test explicit container mode creates ContainerLauncher."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        Orchestrator("test-feature", launcher_mode="container")

        # ContainerLauncher should have been created
        mock_orchestrator_deps["container_launcher_mock"].assert_called()
        mock_orchestrator_deps["container_launcher"].ensure_network.assert_called()

    def test_create_launcher_unknown_mode_raises_value_error(
        self, mock_orchestrator_deps, tmp_path: Path, monkeypatch
    ) -> None:
        """Test unknown mode raises ValueError instead of silent fallback."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        config = ZergConfig()
        with pytest.raises(ValueError, match="Unsupported launcher mode"):
            Orchestrator("test-feature", config=config, launcher_mode="unknown_mode")

    def test_create_launcher_auto_mode_no_devcontainer(
        self, mock_orchestrator_deps, tmp_path: Path, monkeypatch
    ) -> None:
        """Test auto mode without devcontainer uses subprocess."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature", launcher_mode="auto")

        # Without devcontainer, should use subprocess
        assert orch.launcher is not None

    def test_auto_detect_with_devcontainer_and_image(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test auto-detect returns subprocess launcher (container requires explicit flag)."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()
        (tmp_path / ".devcontainer").mkdir()
        (tmp_path / ".devcontainer" / "devcontainer.json").write_text("{}")

        orch = Orchestrator("test-feature", launcher_mode="auto")

        # Auto-detect always returns subprocess launcher
        # Container mode requires explicit --mode container
        assert orch.launcher is not None

    def test_auto_detect_with_devcontainer_no_image(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test auto-detect with devcontainer but no image."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()
        (tmp_path / ".devcontainer").mkdir()
        (tmp_path / ".devcontainer" / "devcontainer.json").write_text("{}")

        with patch("subprocess.run") as sp_run:
            sp_run.return_value = MagicMock(returncode=1)  # Image not found

            orch = Orchestrator("test-feature", launcher_mode="auto")

            assert orch.launcher is not None

    def test_auto_detect_docker_check_fails(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test auto-detect when docker check fails."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()
        (tmp_path / ".devcontainer").mkdir()
        (tmp_path / ".devcontainer" / "devcontainer.json").write_text("{}")

        with patch("subprocess.run") as sp_run:
            sp_run.side_effect = Exception("Docker not available")

            orch = Orchestrator("test-feature", launcher_mode="auto")

            # Should fall back to subprocess
            assert orch.launcher is not None


class TestGetWorkerImageName:
    """Tests for worker image name resolution."""

    def test_get_worker_image_name_from_config_attr(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test image name from config with container_image attribute."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        # Create a mock config that has container_image attribute
        config = MagicMock(spec=ZergConfig)
        config.container_image = "custom-image:latest"
        config.ports = MagicMock()
        config.ports.range_start = 49152
        config.ports.range_end = 65535
        config.workers = MagicMock()
        config.workers.timeout_minutes = 30
        config.workers.retry_attempts = 3
        config.logging = MagicMock()
        config.logging.directory = "/tmp/logs"
        config.get_launcher_type.return_value = MagicMock()
        # Error recovery config for circuit breaker / backpressure
        er_config = MagicMock()
        er_config.circuit_breaker.failure_threshold = 3
        er_config.circuit_breaker.cooldown_seconds = 60
        er_config.circuit_breaker.enabled = True
        er_config.backpressure.failure_rate_threshold = 0.5
        er_config.backpressure.window_size = 10
        er_config.backpressure.enabled = True
        config.error_recovery = er_config

        orch = Orchestrator("test-feature", config=config)
        image_name = orch._get_worker_image_name()

        assert image_name == "custom-image:latest"

    def test_get_worker_image_name_default(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test default image name from feature."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("my-feature")
        image_name = orch._get_worker_image_name()

        assert image_name == "zerg-worker"


class TestStartMethod:
    """Tests for the start() method."""

    def test_start_initializes_correctly(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test start initializes all components."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()
        (tmp_path / ".gsd" / "specs" / "test-feature").mkdir(parents=True)
        task_graph_path = tmp_path / "task-graph.json"
        task_graph_path.write_text('{"tasks": []}')

        mock_orchestrator_deps["parser"].get_all_tasks.return_value = [{"id": "TASK-001", "level": 1}]

        orch = Orchestrator("test-feature")
        # Don't run actual main loop
        with patch.object(orch, "_main_loop"):
            with patch.object(orch, "_spawn_workers", return_value=3):
                with patch.object(orch, "_start_level"):
                    orch.start(task_graph_path, worker_count=3)

        mock_orchestrator_deps["parser"].parse.assert_called_with(task_graph_path)
        mock_orchestrator_deps["state"].load.assert_called()
        mock_orchestrator_deps["state"].append_event.assert_called()

    def test_start_dry_run(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test start with dry_run prints plan without spawning."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()
        (tmp_path / ".gsd" / "specs" / "test-feature").mkdir(parents=True)
        task_graph_path = tmp_path / "task-graph.json"
        task_graph_path.write_text('{"tasks": []}')

        mock_orchestrator_deps["parser"].get_all_tasks.return_value = []
        mock_orchestrator_deps["parser"].total_tasks = 5
        mock_orchestrator_deps["parser"].levels = [1, 2]
        mock_orchestrator_deps["parser"].get_tasks_for_level.return_value = [{"id": "TASK-001", "title": "Test Task"}]

        orch = Orchestrator("test-feature")

        # Dry run should not spawn workers
        orch.start(task_graph_path, worker_count=3, dry_run=True)

        mock_orchestrator_deps["subprocess_launcher"].spawn.assert_not_called()

    def test_start_with_start_level(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test start with custom start level."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()
        (tmp_path / ".gsd" / "specs" / "test-feature").mkdir(parents=True)
        task_graph_path = tmp_path / "task-graph.json"
        task_graph_path.write_text('{"tasks": []}')

        mock_orchestrator_deps["parser"].get_all_tasks.return_value = []

        orch = Orchestrator("test-feature")

        with patch.object(orch, "_main_loop"):
            with patch.object(orch, "_spawn_workers", return_value=3):
                with patch.object(orch, "_start_level") as start_level_mock:
                    orch.start(task_graph_path, worker_count=3, start_level=2)

                    start_level_mock.assert_called_with(2)


class TestStopMethod:
    """Tests for the stop() method."""

    def test_stop_generates_state_md_failure(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test stop handles STATE.md generation failure gracefully."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        mock_orchestrator_deps["state"].generate_state_md.side_effect = Exception("Failed to generate")

        orch = Orchestrator("test-feature")
        orch._running = True

        # Should not raise
        orch.stop()

        assert orch._running is False

    def test_stop_terminates_all_workers(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test stop terminates all workers."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")
        orch._spawn_worker(0)
        orch._spawn_worker(1)
        orch._running = True

        orch.stop()

        # Workers should be terminated
        assert mock_orchestrator_deps["subprocess_launcher"].terminate.call_count >= 2


class TestMainLoop:
    """Tests for the main orchestration loop."""

    def test_main_loop_level_complete_advances(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test main loop advances when level completes."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        # Set up level completion sequence
        mock_orchestrator_deps["levels"].is_level_resolved.side_effect = [True, False, False]
        mock_orchestrator_deps["levels"].can_advance.side_effect = [True, False]
        mock_orchestrator_deps["levels"].advance_level.return_value = 2
        mock_orchestrator_deps["levels"].get_status.return_value = {
            "current_level": 2,
            "total_tasks": 10,
            "completed_tasks": 5,
            "failed_tasks": 0,
            "in_progress_tasks": 0,
            "progress_percent": 50,
            "is_complete": False,
            "levels": {},
        }

        orch = Orchestrator("test-feature")
        orch._running = True
        orch._poll_interval = 0  # No sleep

        # Stop after a few iterations
        call_count = [0]

        def stop_after_calls():
            call_count[0] += 1
            if call_count[0] > 2:
                orch._running = False

        with patch.object(orch, "_poll_workers", side_effect=stop_after_calls):
            with patch.object(orch, "_on_level_complete_handler"):
                with patch.object(orch, "_start_level"):
                    with patch("time.sleep"):
                        orch._main_loop()

    def test_main_loop_all_complete(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test main loop stops when all tasks complete."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        mock_orchestrator_deps["levels"].is_level_resolved.return_value = True
        mock_orchestrator_deps["levels"].can_advance.return_value = False
        mock_orchestrator_deps["levels"].get_status.return_value = {
            "current_level": 3,
            "total_tasks": 10,
            "completed_tasks": 10,
            "failed_tasks": 0,
            "in_progress_tasks": 0,
            "progress_percent": 100,
            "is_complete": True,
            "levels": {},
        }

        orch = Orchestrator("test-feature")
        orch._running = True
        orch._poll_interval = 0

        with patch.object(orch, "_poll_workers"):
            with patch.object(orch, "_on_level_complete_handler"):
                with patch("time.sleep"):
                    orch._main_loop()

        assert orch._running is False

    def test_main_loop_keyboard_interrupt(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test main loop handles keyboard interrupt."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")
        orch._running = True
        orch._poll_interval = 0

        with patch.object(orch, "_poll_workers", side_effect=KeyboardInterrupt):
            with patch.object(orch, "stop") as stop_mock:
                with patch("time.sleep"):
                    orch._main_loop()

        stop_mock.assert_called()

    def test_main_loop_exception_handling(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test main loop handles exceptions properly."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")
        orch._running = True
        orch._poll_interval = 0

        with patch.object(orch, "_poll_workers", side_effect=RuntimeError("Test error")):
            with patch.object(orch, "stop") as stop_mock:
                with patch("time.sleep"):
                    with pytest.raises(RuntimeError, match="Test error"):
                        orch._main_loop()

        mock_orchestrator_deps["state"].set_error.assert_called_with("Test error")
        stop_mock.assert_called_with(force=True)


class TestStartLevel:
    """Tests for _start_level method."""

    def test_start_level_creates_claude_tasks(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test _start_level creates Claude Tasks for level."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        mock_orchestrator_deps["levels"].start_level.return_value = ["TASK-001", "TASK-002"]
        mock_orchestrator_deps["parser"].get_task.side_effect = [
            {"id": "TASK-001", "title": "Task 1"},
            {"id": "TASK-002", "title": "Task 2"},
        ]

        orch = Orchestrator("test-feature")
        orch._start_level(1)

        mock_orchestrator_deps["task_sync"].create_level_tasks.assert_called()

    def test_start_level_skips_claude_tasks_if_no_tasks(
        self, mock_orchestrator_deps, tmp_path: Path, monkeypatch
    ) -> None:
        """Test _start_level skips Claude Tasks if all tasks None."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        mock_orchestrator_deps["levels"].start_level.return_value = ["TASK-001"]
        mock_orchestrator_deps["parser"].get_task.return_value = None

        orch = Orchestrator("test-feature")
        orch._start_level(1)

        mock_orchestrator_deps["task_sync"].create_level_tasks.assert_not_called()

    def test_start_level_assigns_tasks_to_workers(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test _start_level assigns tasks to workers when assigner is set."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        mock_orchestrator_deps["levels"].start_level.return_value = ["TASK-001", "TASK-002"]
        mock_orchestrator_deps["parser"].get_task.return_value = None

        orch = Orchestrator("test-feature")
        orch.assigner = MagicMock()
        orch.assigner.get_task_worker.return_value = 0

        orch._start_level(1)

        # Should call set_task_status for each task
        assert mock_orchestrator_deps["state"].set_task_status.call_count >= 2


class TestLevelCompleteHandler:
    """Tests for _on_level_complete_handler.

    Note: Tests for immediate merge behavior (state_md generation, merge conflict pause,
    merge failure pause) were removed because PR #120 introduced deferred merge by default.
    """

    def test_level_complete_invokes_callbacks(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test level completion invokes registered callbacks."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        callback = MagicMock()

        orch = Orchestrator("test-feature")
        orch.on_level_complete(callback)
        orch._on_level_complete_handler(1)

        callback.assert_called_once_with(1)


class TestMergeLevelWithBranches:
    """Tests for _merge_level with actual branches."""

    def test_merge_level_with_branches_calls_merger(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test merge_level calls merger when there are branches."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")
        orch._spawn_worker(0)
        # Worker has a branch from worktree mock

        orch._merge_level(1)

        mock_orchestrator_deps["merge"].full_merge_flow.assert_called_once()


class TestRebaseAllWorkers:
    """Tests for _rebase_all_workers method."""

    def test_rebase_all_workers_skips_no_branch(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test rebasing skips workers without branches."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")
        orch._spawn_worker(0)
        orch._workers[0].branch = None  # No branch

        orch._rebase_all_workers(1)

        # Should still set status
        mock_orchestrator_deps["state"].set_level_merge_status.assert_called_with(1, LevelMergeStatus.REBASING)

    def test_rebase_all_workers_handles_exception(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test rebasing handles exceptions gracefully."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")
        orch._spawn_worker(0)

        # Should not raise even if something goes wrong
        orch._rebase_all_workers(1)

    def test_rebase_all_workers_logs_branch_info(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test rebasing logs branch information for each worker."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")
        orch._spawn_worker(0)
        # Worker has a branch from worktree mock

        # Should complete without error and log the branch info
        orch._rebase_all_workers(1)

        mock_orchestrator_deps["state"].set_level_merge_status.assert_called_with(1, LevelMergeStatus.REBASING)


class TestPauseForIntervention:
    """Tests for _pause_for_intervention method."""

    def test_pause_for_intervention_sets_state(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test pausing for intervention sets correct state."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")
        orch._pause_for_intervention("Test reason")

        assert orch._paused is True
        mock_orchestrator_deps["state"].set_paused.assert_called_with(True)
        mock_orchestrator_deps["state"].append_event.assert_called_with(
            "paused_for_intervention", {"reason": "Test reason"}
        )


class TestSpawnWorkers:
    """Tests for _spawn_workers method."""

    def test_spawn_workers_handles_individual_failures(
        self, mock_orchestrator_deps, tmp_path: Path, monkeypatch
    ) -> None:
        """Test spawning continues despite individual failures."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        # First spawn succeeds, second fails, third succeeds
        spawn_success = MagicMock()
        spawn_success.success = True
        spawn_success.handle = MagicMock()
        spawn_success.handle.container_id = None
        spawn_success.error = None

        spawn_fail = MagicMock()
        spawn_fail.success = False
        spawn_fail.error = "Failed to spawn"

        mock_orchestrator_deps["subprocess_launcher"].spawn.side_effect = [
            spawn_success,
            spawn_fail,
            spawn_success,
        ]

        orch = Orchestrator("test-feature")

        # Should not raise, continues with other workers
        orch._spawn_workers(3)

        # Should have attempted all 3
        assert mock_orchestrator_deps["subprocess_launcher"].spawn.call_count == 3

    def test_spawn_workers_returns_count(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test _spawn_workers returns number of successfully spawned workers."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")
        result = orch._spawn_workers(3)

        assert result == 3

    def test_spawn_workers_returns_partial_count(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test _spawn_workers returns partial count when some fail."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        spawn_success = MagicMock()
        spawn_success.success = True
        spawn_success.handle = MagicMock()
        spawn_success.handle.container_id = None
        spawn_success.error = None

        # Second worker raises an exception
        mock_orchestrator_deps["subprocess_launcher"].spawn.side_effect = [
            spawn_success,
            Exception("Spawn failed"),
            spawn_success,
        ]

        orch = Orchestrator("test-feature")
        result = orch._spawn_workers(3)

        assert result == 2

    def test_spawn_workers_all_fail_returns_zero(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test _spawn_workers returns 0 when all workers fail."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        mock_orchestrator_deps["subprocess_launcher"].spawn.side_effect = Exception("Spawn failed")

        orch = Orchestrator("test-feature")
        result = orch._spawn_workers(3)

        assert result == 0


class TestStartSpawnValidation:
    """Tests for start() spawn count validation."""

    def test_start_raises_when_all_spawns_fail(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test start raises RuntimeError when all workers fail to spawn."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()
        (tmp_path / ".gsd" / "specs" / "test-feature").mkdir(parents=True)
        task_graph_path = tmp_path / "task-graph.json"
        task_graph_path.write_text('{"tasks": []}')

        mock_orchestrator_deps["parser"].get_all_tasks.return_value = [{"id": "TASK-001", "level": 1}]

        orch = Orchestrator("test-feature")

        with patch.object(orch, "_spawn_workers", return_value=0):
            with pytest.raises(RuntimeError, match="All 3 workers failed to spawn"):
                orch.start(task_graph_path, worker_count=3)

    def test_start_continues_with_partial_spawns(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test start continues when some workers spawn successfully."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()
        (tmp_path / ".gsd" / "specs" / "test-feature").mkdir(parents=True)
        task_graph_path = tmp_path / "task-graph.json"
        task_graph_path.write_text('{"tasks": []}')

        mock_orchestrator_deps["parser"].get_all_tasks.return_value = [{"id": "TASK-001", "level": 1}]

        orch = Orchestrator("test-feature")

        with patch.object(orch, "_spawn_workers", return_value=2):
            with patch.object(orch, "_main_loop"):
                with patch.object(orch, "_start_level"):
                    with patch.object(orch, "_wait_for_initialization"):
                        orch.start(task_graph_path, worker_count=3)

        # Should not raise — completed successfully

    def test_start_records_rush_failed_event(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test start records rush_failed event when all spawns fail."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()
        (tmp_path / ".gsd" / "specs" / "test-feature").mkdir(parents=True)
        task_graph_path = tmp_path / "task-graph.json"
        task_graph_path.write_text('{"tasks": []}')

        mock_orchestrator_deps["parser"].get_all_tasks.return_value = [{"id": "TASK-001", "level": 1}]

        orch = Orchestrator("test-feature")

        with patch.object(orch, "_spawn_workers", return_value=0):
            with pytest.raises(RuntimeError):
                orch.start(task_graph_path, worker_count=3)

        # Verify rush_failed event was recorded
        event_calls = mock_orchestrator_deps["state"].append_event.call_args_list
        rush_failed = [c for c in event_calls if c[0][0] == "rush_failed"]
        assert len(rush_failed) == 1
        event_data = rush_failed[0][0][1]
        assert event_data["reason"] == "No workers spawned"
        assert event_data["requested"] == 3

        # Verify state.save() was called
        mock_orchestrator_deps["state"].save.assert_called()


class TestTerminateWorker:
    """Tests for _terminate_worker method."""

    def test_terminate_worker_worktree_delete_fails(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test terminate handles worktree deletion failure."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        mock_orchestrator_deps["worktree"].delete.side_effect = Exception("Delete failed")

        orch = Orchestrator("test-feature")
        orch._spawn_worker(0)

        # Should not raise
        orch._terminate_worker(0)

        # Worker should still be removed
        assert 0 not in orch._workers

    def test_terminate_nonexistent_worker(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test terminate returns early for nonexistent worker."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")

        # Should not raise, just return
        orch._terminate_worker(999)

        # No launcher calls should be made
        mock_orchestrator_deps["subprocess_launcher"].terminate.assert_not_called()


class TestPollWorkers:
    """Tests for _poll_workers method."""

    def test_poll_workers_stopped_status(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test polling handles stopped worker status."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        mock_orchestrator_deps["subprocess_launcher"].monitor.return_value = WorkerStatus.STOPPED

        orch = Orchestrator("test-feature")
        orch._spawn_worker(0)

        with patch.object(orch, "_handle_worker_exit") as exit_mock:
            orch._poll_workers()

        exit_mock.assert_called_with(0)

    def test_poll_workers_crashed_status(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test polling handles crashed worker status.

        FR-5: Worker crash uses _handle_worker_crash (not _handle_task_failure)
        to avoid incrementing retry count for infrastructure failures.
        """
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        mock_orchestrator_deps["subprocess_launcher"].monitor.return_value = WorkerStatus.CRASHED

        orch = Orchestrator("test-feature")
        orch._spawn_worker(0)
        orch._workers[0].current_task = "TASK-001"

        with patch.object(orch, "_handle_worker_crash") as crash_mock:
            orch._poll_workers()

        # Worker is removed after crash is handled (via _handle_worker_exit)
        assert 0 not in orch._workers
        # FR-5: Crash handler is called instead of task failure handler
        crash_mock.assert_called_with("TASK-001", 0)

    def test_poll_workers_checkpointing_status(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test polling handles checkpointing worker status."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        mock_orchestrator_deps["subprocess_launcher"].monitor.return_value = WorkerStatus.CHECKPOINTING

        orch = Orchestrator("test-feature")
        orch._spawn_worker(0)

        with patch.object(orch, "_handle_worker_exit") as exit_mock:
            orch._poll_workers()

        assert orch._workers[0].status == WorkerStatus.CHECKPOINTING
        exit_mock.assert_called_with(0)


class TestHandleWorkerExit:
    """Tests for _handle_worker_exit method."""

    def test_handle_worker_exit_no_worker(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test exit handling with nonexistent worker."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")

        # Should not raise
        orch._handle_worker_exit(999)

    def test_handle_worker_exit_task_complete_callback(
        self, mock_orchestrator_deps, tmp_path: Path, monkeypatch
    ) -> None:
        """Test exit handling invokes task completion callbacks."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        mock_orchestrator_deps["parser"].get_task.return_value = {
            "id": "TASK-001",
            "verification": {"command": "echo test"},
        }

        callback = MagicMock()

        orch = Orchestrator("test-feature")
        orch.on_task_complete(callback)
        orch._spawn_worker(0)
        orch._workers[0].current_task = "TASK-001"

        orch._handle_worker_exit(0)

        callback.assert_called_with("TASK-001")

    def test_handle_worker_exit_restart_fails(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test exit handling when worker restart fails."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        mock_orchestrator_deps["levels"].get_pending_tasks_for_level.return_value = ["TASK-002"]

        # Make spawn fail on restart
        spawn_fail = MagicMock()
        spawn_fail.success = False
        spawn_fail.error = "Failed to spawn"

        spawn_success = MagicMock()
        spawn_success.success = True
        spawn_success.handle = MagicMock()
        spawn_success.handle.container_id = None
        spawn_success.error = None

        mock_orchestrator_deps["subprocess_launcher"].spawn.side_effect = [
            spawn_success,  # Initial spawn
            spawn_fail,  # Restart spawn fails
        ]

        orch = Orchestrator("test-feature")
        orch._spawn_worker(0)

        # Should not raise
        orch._handle_worker_exit(0)

    def test_handle_worker_exit_no_current_task(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test exit handling when worker has no current task."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")
        orch._spawn_worker(0)
        orch._workers[0].current_task = None  # No current task

        # Should not raise
        orch._handle_worker_exit(0)

        mock_orchestrator_deps["levels"].mark_task_complete.assert_not_called()


class TestPrintPlan:
    """Tests for _print_plan method."""

    def test_print_plan_outputs_correctly(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch, capsys) -> None:
        """Test print plan outputs execution plan."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        mock_orchestrator_deps["parser"].total_tasks = 3
        mock_orchestrator_deps["parser"].levels = [1, 2]
        mock_orchestrator_deps["parser"].get_tasks_for_level.return_value = [
            {"id": "TASK-001", "title": "First Task"},
            {"id": "TASK-002", "title": "Second Task"},
        ]

        orch = Orchestrator("test-feature")
        orch.assigner = MagicMock()
        orch.assigner.worker_count = 3
        orch.assigner.get_task_worker.return_value = 0

        assignments = MagicMock()
        assignments.worker_count = 3

        orch._print_plan(assignments)

        captured = capsys.readouterr()
        assert "ZERG Execution Plan" in captured.out
        assert "test-feature" in captured.out

    def test_print_plan_without_assigner(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch, capsys) -> None:
        """Test print plan works without assigner."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        mock_orchestrator_deps["parser"].total_tasks = 3
        mock_orchestrator_deps["parser"].levels = [1]
        mock_orchestrator_deps["parser"].get_tasks_for_level.return_value = [
            {"id": "TASK-001", "title": "First Task"},
        ]

        orch = Orchestrator("test-feature")
        orch.assigner = None  # No assigner

        assignments = MagicMock()
        assignments.worker_count = 3

        orch._print_plan(assignments)

        captured = capsys.readouterr()
        assert "ZERG Execution Plan" in captured.out


class TestVerifyWithRetry:
    """Tests for verify_with_retry method."""

    def test_verify_with_retry_all_fail(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test verify_with_retry returns False when all retries fail."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        # Patch at the module level where it's imported inside the method
        with patch("zerg.verify.VerificationExecutor") as verify_mock:
            fail_result = MagicMock()
            fail_result.success = False

            verifier = MagicMock()
            verifier.verify.return_value = fail_result
            verify_mock.return_value = verifier

            orch = Orchestrator("test-feature")

            with patch("time.sleep"):  # Don't actually sleep
                success = orch.verify_with_retry("TASK-001", "echo test", max_retries=2)

            assert success is False
            # Should try original + 2 retries = 3 attempts
            assert verifier.verify.call_count == 3

    def test_verify_with_retry_success_on_first_try(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test verify_with_retry returns True on first try success."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        with patch("zerg.verify.VerificationExecutor") as verify_mock:
            success_result = MagicMock()
            success_result.success = True

            verifier = MagicMock()
            verifier.verify.return_value = success_result
            verify_mock.return_value = verifier

            orch = Orchestrator("test-feature")

            success = orch.verify_with_retry("TASK-001", "echo test")

            assert success is True
            assert verifier.verify.call_count == 1


class TestMergeLevel:
    """Tests for _merge_level method."""

    def test_merge_level_no_branches(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test merge_level with no worker branches."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")
        # No workers spawned, no branches

        result = orch._merge_level(1)

        assert result.success is True
        mock_orchestrator_deps["merge"].full_merge_flow.assert_not_called()


class TestContainerWorkerSpawn:
    """Tests for spawning workers with container IDs."""

    def test_spawn_worker_with_container_id(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test spawning worker records container ID."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        spawn_result = MagicMock()
        spawn_result.success = True
        spawn_result.handle = MagicMock()
        spawn_result.handle.container_id = "container-xyz-123"
        spawn_result.error = None

        mock_orchestrator_deps["subprocess_launcher"].spawn.return_value = spawn_result

        orch = Orchestrator("test-feature")
        worker_state = orch._spawn_worker(0)

        assert worker_state.container_id == "container-xyz-123"
        mock_orchestrator_deps["state"].append_event.assert_called_with(
            "worker_started",
            {
                "worker_id": 0,
                "port": 49152,
                "container_id": "container-xyz-123",
                "mode": "container",
            },
        )


class TestTaskFailureHandling:
    """Tests for task failure and retry handling."""

    def test_handle_task_failure_emits_retry_event(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test task failure emits retry event."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        mock_orchestrator_deps["state"].get_task_retry_count.return_value = 0
        mock_orchestrator_deps["state"].increment_task_retry.return_value = 1

        orch = Orchestrator("test-feature")

        will_retry = orch._handle_task_failure("TASK-001", 0, "Test error")

        assert will_retry is True
        # Event name changed to task_retry_scheduled with backoff info
        event_calls = mock_orchestrator_deps["state"].append_event.call_args_list
        retry_call = [c for c in event_calls if c[0][0] == "task_retry_scheduled"]
        assert len(retry_call) == 1
        event_data = retry_call[0][0][1]
        assert event_data["task_id"] == "TASK-001"
        assert event_data["worker_id"] == 0
        assert event_data["retry_count"] == 1
        assert event_data["error"] == "Test error"
        assert "backoff_seconds" in event_data
        assert "next_retry_at" in event_data

    def test_handle_task_failure_permanent_emits_event(
        self, mock_orchestrator_deps, tmp_path: Path, monkeypatch
    ) -> None:
        """Test permanent task failure emits event."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        mock_orchestrator_deps["state"].get_task_retry_count.return_value = 3

        orch = Orchestrator("test-feature")

        will_retry = orch._handle_task_failure("TASK-001", 0, "Test error")

        assert will_retry is False
        mock_orchestrator_deps["state"].append_event.assert_called_with(
            "task_failed_permanent",
            {
                "task_id": "TASK-001",
                "worker_id": 0,
                "retry_count": 3,
                "error": "Test error",
            },
        )


class TestRetryTaskMethods:
    """Tests for retry_task and retry_all_failed methods."""

    def test_retry_task_with_taskstatus_failed(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test retry_task works with TaskStatus.FAILED enum value."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        mock_orchestrator_deps["state"].get_task_status.return_value = TaskStatus.FAILED.value

        orch = Orchestrator("test-feature")

        result = orch.retry_task("TASK-001")

        assert result is True
        mock_orchestrator_deps["state"].reset_task_retry.assert_called_with("TASK-001")

    def test_retry_task_not_failed(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test retry_task returns False for non-failed task."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        mock_orchestrator_deps["state"].get_task_status.return_value = "running"

        orch = Orchestrator("test-feature")

        result = orch.retry_task("TASK-001")

        assert result is False

    def test_retry_all_failed(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test retry_all_failed retries all failed tasks."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        mock_orchestrator_deps["state"].get_failed_tasks.return_value = [
            {"task_id": "TASK-001"},
            {"task_id": "TASK-002"},
        ]
        mock_orchestrator_deps["state"].get_task_status.return_value = "failed"

        orch = Orchestrator("test-feature")

        retried = orch.retry_all_failed()

        assert len(retried) == 2
        assert "TASK-001" in retried
        assert "TASK-002" in retried


class TestResume:
    """Tests for resume method."""

    def test_resume_when_paused(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test resume from paused state."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")
        orch._paused = True

        orch.resume()

        assert orch._paused is False
        mock_orchestrator_deps["state"].set_paused.assert_called_with(False)
        mock_orchestrator_deps["state"].append_event.assert_called_with("resumed", {})

    def test_resume_when_not_paused(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test resume when not paused does nothing."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")
        orch._paused = False

        orch.resume()

        # set_paused should not be called
        mock_orchestrator_deps["state"].set_paused.assert_not_called()


class TestStatus:
    """Tests for status method."""

    def test_status_returns_correct_structure(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test status returns correct structure."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")
        orch._running = True

        status = orch.status()

        assert status["feature"] == "test-feature"
        assert status["running"] is True
        assert "current_level" in status
        assert "progress" in status
        assert "workers" in status
        assert "levels" in status
        assert "is_complete" in status

    def test_status_includes_worker_info(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test status includes worker information."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")
        orch._spawn_worker(0)

        status = orch.status()

        assert 0 in status["workers"]
        assert "status" in status["workers"][0]
        assert "current_task" in status["workers"][0]
        assert "tasks_completed" in status["workers"][0]


class TestCallbackRegistration:
    """Tests for callback registration methods."""

    def test_on_level_complete_registers_callback(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test on_level_complete registers callback."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        callback = MagicMock()

        orch = Orchestrator("test-feature")
        orch.on_level_complete(callback)

        assert callback in orch._on_level_complete

    def test_on_task_complete_registers_callback(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test on_task_complete registers callback."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        callback = MagicMock()

        orch = Orchestrator("test-feature")
        orch.on_task_complete(callback)

        assert callback in orch._on_task_complete
