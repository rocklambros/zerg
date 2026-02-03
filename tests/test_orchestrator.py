"""Tests for ZERG orchestrator."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zerg.constants import TaskStatus, WorkerStatus
from zerg.orchestrator import Orchestrator


@pytest.fixture
def mock_deps():
    """Mock orchestrator dependencies."""
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
        state.increment_task_retry.return_value = 1
        state.get_failed_tasks.return_value = []
        state.get_tasks_ready_for_retry.return_value = []
        state_mock.return_value = state

        levels = MagicMock()
        levels.current_level = 1
        levels.is_level_complete.return_value = False
        levels.is_level_resolved.return_value = False
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

        launcher = MagicMock()
        spawn_result = MagicMock()
        spawn_result.success = True
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


class TestOrchestrator:
    """Tests for Orchestrator class."""

    def test_init(self, mock_deps, tmp_path: Path, monkeypatch) -> None:
        """Test orchestrator initialization."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")

        assert orch.feature == "test-feature"
        assert orch.launcher is not None
        assert orch.merger is not None

    def test_create_launcher(self, mock_deps, tmp_path: Path, monkeypatch) -> None:
        """Test launcher creation."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")

        # Default should be subprocess launcher
        assert orch.launcher is not None


class TestExecute:
    """Tests for worker execution (L2-001)."""

    def test_spawn_worker_subprocess(self, mock_deps, tmp_path: Path, monkeypatch) -> None:
        """Test spawning worker with subprocess launcher."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")

        worker_state = orch._spawn_worker(0)

        assert worker_state.worker_id == 0
        assert worker_state.status == WorkerStatus.RUNNING
        mock_deps["launcher"].spawn.assert_called_once()

    def test_poll_workers_uses_launcher(self, mock_deps, tmp_path: Path, monkeypatch) -> None:
        """Test polling uses launcher for status."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")
        orch._spawn_worker(0)

        orch._poll_workers()

        mock_deps["launcher"].monitor.assert_called()

    def test_terminate_worker_uses_launcher(self, mock_deps, tmp_path: Path, monkeypatch) -> None:
        """Test terminating uses launcher."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")
        orch._spawn_worker(0)

        orch._terminate_worker(0)

        mock_deps["launcher"].terminate.assert_called_with(0, force=False)


class TestMerge:
    """Tests for merge protocol (L2-002)."""

    def test_merge_level_success(self, mock_deps, tmp_path: Path, monkeypatch) -> None:
        """Test successful level merge."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")
        orch._spawn_worker(0)

        result = orch._merge_level(1)

        assert result.success is True
        mock_deps["merge"].full_merge_flow.assert_called_once()

    def test_on_level_complete_triggers_merge(self, mock_deps, tmp_path: Path, monkeypatch) -> None:
        """Test level completion triggers merge."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")

        orch._on_level_complete_handler(1)

        mock_deps["state"].set_level_merge_status.assert_called()

    def test_pause_for_intervention(self, mock_deps, tmp_path: Path, monkeypatch) -> None:
        """Test pausing for intervention."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")

        orch._pause_for_intervention("Test reason")

        assert orch._paused is True
        mock_deps["state"].set_paused.assert_called_with(True)

    def test_resume(self, mock_deps, tmp_path: Path, monkeypatch) -> None:
        """Test resuming from pause."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")
        orch._paused = True

        orch.resume()

        assert orch._paused is False
        mock_deps["state"].set_paused.assert_called_with(False)


class TestRetry:
    """Tests for retry logic (L2-003)."""

    def test_handle_task_failure_retries(self, mock_deps, tmp_path: Path, monkeypatch) -> None:
        """Test task failure triggers retry when under limit."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        mock_deps["state"].get_task_retry_count.return_value = 0

        orch = Orchestrator("test-feature")

        will_retry = orch._handle_task_failure("TASK-001", 0, "Test error")

        assert will_retry is True
        mock_deps["state"].increment_task_retry.assert_called_once()
        assert mock_deps["state"].increment_task_retry.call_args[0][0] == "TASK-001"
        mock_deps["state"].set_task_status.assert_called_with("TASK-001", "waiting_retry")

    def test_handle_task_failure_exceeds_limit(self, mock_deps, tmp_path: Path, monkeypatch) -> None:
        """Test task failure fails permanently when over limit."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        mock_deps["state"].get_task_retry_count.return_value = 3  # At limit

        orch = Orchestrator("test-feature")

        will_retry = orch._handle_task_failure("TASK-001", 0, "Test error")

        assert will_retry is False
        mock_deps["levels"].mark_task_failed.assert_called()

    def test_retry_task(self, mock_deps, tmp_path: Path, monkeypatch) -> None:
        """Test manual task retry."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        mock_deps["state"].get_task_status.return_value = "failed"

        orch = Orchestrator("test-feature")

        result = orch.retry_task("TASK-001")

        assert result is True
        mock_deps["state"].reset_task_retry.assert_called_with("TASK-001")
        mock_deps["state"].set_task_status.assert_called_with("TASK-001", TaskStatus.PENDING)

    def test_retry_task_not_failed(self, mock_deps, tmp_path: Path, monkeypatch) -> None:
        """Test retry fails for non-failed task."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        mock_deps["state"].get_task_status.return_value = "complete"

        orch = Orchestrator("test-feature")

        result = orch.retry_task("TASK-001")

        assert result is False

    def test_retry_all_failed(self, mock_deps, tmp_path: Path, monkeypatch) -> None:
        """Test retrying all failed tasks."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        mock_deps["state"].get_failed_tasks.return_value = [
            {"task_id": "TASK-001", "retry_count": 1},
            {"task_id": "TASK-002", "retry_count": 2},
        ]
        mock_deps["state"].get_task_status.return_value = "failed"

        orch = Orchestrator("test-feature")

        retried = orch.retry_all_failed()

        assert len(retried) == 2
        assert "TASK-001" in retried
        assert "TASK-002" in retried

    def test_verify_with_retry_success(self, mock_deps, tmp_path: Path, monkeypatch) -> None:
        """Test verification with retry succeeds on first try."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        with patch("zerg.verify.VerificationExecutor") as verify_mock:
            result = MagicMock()
            result.success = True
            verify_mock.return_value.verify.return_value = result

            orch = Orchestrator("test-feature")

            success = orch.verify_with_retry("TASK-001", "echo test")

            assert success is True

    def test_verify_with_retry_fails_then_succeeds(self, mock_deps, tmp_path: Path, monkeypatch) -> None:
        """Test verification retries and succeeds."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        with patch("zerg.verify.VerificationExecutor") as verify_mock:
            fail_result = MagicMock()
            fail_result.success = False
            success_result = MagicMock()
            success_result.success = True

            verifier = MagicMock()
            verifier.verify.side_effect = [fail_result, success_result]
            verify_mock.return_value = verifier

            orch = Orchestrator("test-feature")

            success = orch.verify_with_retry("TASK-001", "echo test", max_retries=1)

            assert success is True
            assert verifier.verify.call_count == 2
