"""Tests for ZERG orchestrator level management (TC-010)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zerg.constants import LevelMergeStatus, WorkerStatus
from zerg.orchestrator import Orchestrator


@pytest.fixture
def mock_orchestrator_deps():
    """Mock orchestrator dependencies for level tests."""
    with (
        patch("zerg.orchestrator.StateManager") as state_mock,
        patch("zerg.orchestrator.LevelController") as levels_mock,
        patch("zerg.orchestrator.TaskParser") as parser_mock,
        patch("zerg.orchestrator.GateRunner") as gates_mock,
        patch("zerg.orchestrator.WorktreeManager") as worktree_mock,
        patch("zerg.orchestrator.ContainerManager") as container_mock,
        patch("zerg.orchestrator.PortAllocator") as ports_mock,
        patch("zerg.orchestrator.MergeCoordinator") as merge_mock,
        patch("zerg.orchestrator.SubprocessLauncher") as launcher_mock,
    ):
        state = MagicMock()
        state.load.return_value = {}
        state.get_task_status.return_value = None
        state.get_task_retry_count.return_value = 0
        state.get_failed_tasks.return_value = []
        state_mock.return_value = state

        levels = MagicMock()
        levels.current_level = 1
        levels.is_level_complete.return_value = False
        levels.is_level_resolved.return_value = False
        levels.can_advance.return_value = True
        levels.advance_level.return_value = 2
        levels.start_level.return_value = ["TASK-001"]
        levels.get_pending_tasks_for_level.return_value = []
        levels.get_status.return_value = {
            "current_level": 1,
            "total_tasks": 10,
            "completed_tasks": 5,
            "failed_tasks": 0,
            "in_progress_tasks": 0,
            "progress_percent": 50,
            "is_complete": False,
            "levels": {
                "1": {"status": "complete", "tasks": 5},
                "2": {"status": "running", "tasks": 5},
            },
        }
        levels_mock.return_value = levels

        parser = MagicMock()
        parser.get_all_tasks.return_value = []
        parser.get_task.return_value = None
        parser.total_tasks = 10
        parser.levels = [1, 2, 3]
        parser_mock.return_value = parser

        gates = MagicMock()
        gates.run_all_gates.return_value = (True, [])
        gates_mock.return_value = gates

        worktree = MagicMock()
        worktree_info = MagicMock()
        worktree_info.path = Path("/tmp/worktree")
        worktree_info.branch = "zerg/test/worker-0"
        worktree.create.return_value = worktree_info
        worktree_mock.return_value = worktree

        container = MagicMock()
        container_mock.return_value = container

        ports = MagicMock()
        ports.allocate_one.return_value = 49152
        ports_mock.return_value = ports

        merge = MagicMock()
        merge_result = MagicMock()
        merge_result.success = True
        merge_result.merge_commit = "abc123def"
        merge_result.error = None
        merge.full_merge_flow.return_value = merge_result
        merge_mock.return_value = merge

        launcher = MagicMock()
        spawn_result = MagicMock()
        spawn_result.success = True
        spawn_result.handle = MagicMock()
        spawn_result.handle.container_id = None
        spawn_result.error = None
        launcher.spawn.return_value = spawn_result
        launcher.monitor.return_value = WorkerStatus.RUNNING
        launcher_mock.return_value = launcher

        yield {
            "state": state,
            "levels": levels,
            "parser": parser,
            "gates": gates,
            "worktree": worktree,
            "container": container,
            "ports": ports,
            "merge": merge,
            "launcher": launcher,
        }


class TestLevelStarting:
    """Tests for starting levels."""

    def test_start_level_sets_state(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test starting a level sets correct state."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")
        orch._start_level(1)

        mock_orchestrator_deps["state"].set_current_level.assert_called_with(1)
        mock_orchestrator_deps["state"].set_level_status.assert_called_with(1, "running")

    def test_start_level_emits_event(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test starting a level emits an event."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        mock_orchestrator_deps["levels"].start_level.return_value = ["TASK-001", "TASK-002"]

        orch = Orchestrator("test-feature")
        orch._start_level(1)

        mock_orchestrator_deps["state"].append_event.assert_called_with("level_started", {"level": 1, "tasks": 2})

    def test_start_level_assigns_to_workers(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test starting a level assigns tasks."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        mock_orchestrator_deps["levels"].start_level.return_value = ["TASK-001", "TASK-002"]

        orch = Orchestrator("test-feature")
        orch.assigner = MagicMock()
        orch.assigner.get_task_worker.return_value = 0

        orch._start_level(1)

        # Should call get_task_worker for each task
        assert orch.assigner.get_task_worker.call_count == 2


class TestLevelCompletion:
    """Tests for level completion handling."""

    def test_on_level_complete_triggers_merge(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test level completion triggers merge."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")
        # Spawn a worker so there are branches to merge
        orch._spawn_worker(0)

        orch._on_level_complete_handler(1)

        mock_orchestrator_deps["merge"].full_merge_flow.assert_called()

    def test_on_level_complete_sets_merge_status(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test level completion sets merge status."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")
        # Spawn a worker so there are branches to merge
        orch._spawn_worker(0)

        orch._on_level_complete_handler(1)

        # Should set MERGING first, then COMPLETE
        calls = mock_orchestrator_deps["state"].set_level_merge_status.call_args_list
        assert any(str(LevelMergeStatus.MERGING.value) in str(c) for c in calls)

    def test_on_level_complete_success_records_commit(
        self, mock_orchestrator_deps, tmp_path: Path, monkeypatch
    ) -> None:
        """Test successful level completion records merge commit."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")
        # Spawn a worker so there are branches to merge
        orch._spawn_worker(0)

        orch._on_level_complete_handler(1)

        mock_orchestrator_deps["state"].set_level_status.assert_called_with(1, "complete", merge_commit="abc123def")

    def test_on_level_complete_emits_event(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test level completion emits event."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")
        # Spawn a worker so there are branches to merge
        orch._spawn_worker(0)

        orch._on_level_complete_handler(1)

        mock_orchestrator_deps["state"].append_event.assert_called_with(
            "level_complete", {"level": 1, "merge_commit": "abc123def"}
        )

    def test_on_level_complete_invokes_callbacks(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test level completion invokes registered callbacks."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        callback = MagicMock()

        orch = Orchestrator("test-feature")
        orch.on_level_complete(callback)
        orch._on_level_complete_handler(1)

        callback.assert_called_once_with(1)


class TestMergeFailure:
    """Tests for merge failure handling."""

    @patch("time.sleep")
    def test_merge_conflict_pauses_execution(
        self, mock_sleep, mock_orchestrator_deps, tmp_path: Path, monkeypatch
    ) -> None:
        """Test merge conflict pauses execution."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        merge_result = MagicMock()
        merge_result.success = False
        merge_result.error = "Merge conflict in src/auth.py"
        mock_orchestrator_deps["merge"].full_merge_flow.return_value = merge_result

        orch = Orchestrator("test-feature")
        # Spawn a worker so there are branches to merge
        orch._spawn_worker(0)

        orch._on_level_complete_handler(1)

        assert orch._paused is True
        mock_orchestrator_deps["state"].set_level_merge_status.assert_any_call(
            1, LevelMergeStatus.CONFLICT, details={"error": "Merge conflict in src/auth.py"}
        )

    @patch("time.sleep")
    def test_merge_failure_pauses_orchestration(
        self, mock_sleep, mock_orchestrator_deps, tmp_path: Path, monkeypatch
    ) -> None:
        """Test non-conflict merge failure pauses orchestration (BF-007: recoverable error).

        BF-007 changed behavior from stop() to _set_recoverable_error() which
        pauses execution instead of stopping, allowing manual intervention.
        """
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        merge_result = MagicMock()
        merge_result.success = False
        merge_result.error = "Pre-merge gates failed"
        mock_orchestrator_deps["merge"].full_merge_flow.return_value = merge_result

        orch = Orchestrator("test-feature")
        # Spawn a worker so there are branches to merge
        orch._spawn_worker(0)
        orch._running = True

        orch._on_level_complete_handler(1)

        # BF-007: Now pauses instead of stopping
        assert orch._paused is True
        mock_orchestrator_deps["state"].set_error.assert_called()
        mock_orchestrator_deps["state"].set_paused.assert_called_with(True)


class TestLevelAdvancement:
    """Tests for level advancement."""

    def test_can_advance_check(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test checking if level can advance."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        Orchestrator("test-feature")

        # levels.can_advance is mocked to return True
        assert mock_orchestrator_deps["levels"].can_advance() is True

    def test_advance_level_returns_next(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test advancing level returns next level."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        Orchestrator("test-feature")

        next_level = mock_orchestrator_deps["levels"].advance_level()

        assert next_level == 2


class TestStatus:
    """Tests for status reporting."""

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

    def test_status_includes_progress(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test status includes progress info."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")

        status = orch.status()

        assert status["progress"]["total"] == 10
        assert status["progress"]["completed"] == 5
        assert status["progress"]["percent"] == 50

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


class TestRebase:
    """Tests for worker branch rebasing."""

    def test_rebase_all_workers_sets_status(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test rebasing sets correct status."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")
        orch._spawn_worker(0)

        orch._rebase_all_workers(1)

        mock_orchestrator_deps["state"].set_level_merge_status.assert_called_with(1, LevelMergeStatus.REBASING)


class TestPauseResume:
    """Tests for pause/resume functionality."""

    def test_pause_for_intervention(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test pausing for intervention."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")
        orch._pause_for_intervention("Test reason")

        assert orch._paused is True
        mock_orchestrator_deps["state"].set_paused.assert_called_with(True)

    def test_pause_emits_event(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test pause emits event."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")
        orch._pause_for_intervention("Test reason")

        mock_orchestrator_deps["state"].append_event.assert_called_with(
            "paused_for_intervention", {"reason": "Test reason"}
        )

    def test_resume_from_pause(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test resuming from pause."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")
        orch._paused = True

        orch.resume()

        assert orch._paused is False
        mock_orchestrator_deps["state"].set_paused.assert_called_with(False)

    def test_resume_when_not_paused(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test resume when not paused does nothing."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")
        orch._paused = False

        orch.resume()

        # set_paused should not be called
        mock_orchestrator_deps["state"].set_paused.assert_not_called()

    def test_resume_emits_event(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test resume emits event."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")
        orch._paused = True

        orch.resume()

        mock_orchestrator_deps["state"].append_event.assert_called_with("resumed", {})
