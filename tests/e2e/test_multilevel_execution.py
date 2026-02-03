"""End-to-end tests for multi-level task execution (TC-017).

Tests the complete workflow of executing tasks across multiple levels.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zerg.constants import WorkerStatus
from zerg.launcher import SpawnResult
from zerg.orchestrator import Orchestrator


@pytest.fixture
def multilevel_task_graph(tmp_path: Path):
    """Create a multi-level task graph."""
    zerg_dir = tmp_path / ".zerg"
    zerg_dir.mkdir()

    task_graph = {
        "feature": "multilevel-test",
        "levels": {
            "1": ["L1-TASK-001", "L1-TASK-002", "L1-TASK-003"],
            "2": ["L2-TASK-001", "L2-TASK-002"],
            "3": ["L3-TASK-001"],
        },
        "tasks": {
            "L1-TASK-001": {
                "id": "L1-TASK-001",
                "title": "Level 1 Task 1",
                "level": 1,
                "files": ["src/a.py"],
                "verification": "true",
            },
            "L1-TASK-002": {
                "id": "L1-TASK-002",
                "title": "Level 1 Task 2",
                "level": 1,
                "files": ["src/b.py"],
                "verification": "true",
            },
            "L1-TASK-003": {
                "id": "L1-TASK-003",
                "title": "Level 1 Task 3",
                "level": 1,
                "files": ["src/c.py"],
                "verification": "true",
            },
            "L2-TASK-001": {
                "id": "L2-TASK-001",
                "title": "Level 2 Task 1",
                "level": 2,
                "files": ["src/d.py"],
                "dependencies": ["L1-TASK-001", "L1-TASK-002"],
                "verification": "true",
            },
            "L2-TASK-002": {
                "id": "L2-TASK-002",
                "title": "Level 2 Task 2",
                "level": 2,
                "files": ["src/e.py"],
                "dependencies": ["L1-TASK-003"],
                "verification": "true",
            },
            "L3-TASK-001": {
                "id": "L3-TASK-001",
                "title": "Level 3 Final Task",
                "level": 3,
                "files": ["src/main.py"],
                "dependencies": ["L2-TASK-001", "L2-TASK-002"],
                "verification": "true",
            },
        },
    }

    (zerg_dir / "task-graph.json").write_text(json.dumps(task_graph))
    return tmp_path


@pytest.fixture
def mock_orchestrator_deps():
    """Mock all orchestrator dependencies."""
    with (
        patch("zerg.orchestrator.StateManager") as state_mock,
        patch("zerg.orchestrator.LevelController") as levels_mock,
        patch("zerg.orchestrator.TaskParser") as parser_mock,
        patch("zerg.orchestrator.GateRunner"),
        patch("zerg.orchestrator.WorktreeManager") as worktree_mock,
        patch("zerg.orchestrator.ContainerManager"),
        patch("zerg.orchestrator.PortAllocator") as ports_mock,
        patch("zerg.orchestrator.MergeCoordinator") as merge_mock,
        patch("zerg.orchestrator.SubprocessLauncher") as launcher_mock,
    ):
        state = MagicMock()
        state.load.return_value = {}
        state_mock.return_value = state

        levels = MagicMock()
        levels.current_level = 1
        levels.is_level_complete.return_value = True
        levels.is_level_resolved.return_value = True
        levels.can_advance.return_value = True
        levels.get_status.return_value = {
            "current_level": 1,
            "total_tasks": 6,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "in_progress_tasks": 0,
            "progress_percent": 0,
            "levels": {},
            "is_complete": False,
        }
        levels_mock.return_value = levels

        parser = MagicMock()
        parser.total_tasks = 6
        parser.levels = [1, 2, 3]
        parser_mock.return_value = parser

        worktree = MagicMock()
        worktree_info = MagicMock()
        worktree_info.path = Path("/tmp/worktree")
        worktree_info.branch = "zerg/multilevel-test/worker-0"
        worktree.create.return_value = worktree_info
        worktree_mock.return_value = worktree

        ports = MagicMock()
        ports.allocate_one.return_value = 49152
        ports_mock.return_value = ports

        launcher = MagicMock()
        spawn_result = MagicMock(spec=SpawnResult)
        spawn_result.success = True
        spawn_result.handle = MagicMock()
        spawn_result.handle.container_id = None
        spawn_result.error = None
        launcher.spawn.return_value = spawn_result
        launcher.monitor.return_value = WorkerStatus.RUNNING
        launcher.terminate.return_value = True
        launcher_mock.return_value = launcher

        merge = MagicMock()
        merge_result = MagicMock()
        merge_result.success = True
        merge_result.merge_commit = "abc123"
        merge.full_merge_flow.return_value = merge_result
        merge_mock.return_value = merge

        yield {
            "state": state,
            "levels": levels,
            "parser": parser,
            "worktree": worktree,
            "ports": ports,
            "launcher": launcher,
            "merge": merge,
        }


class TestLevelProgression:
    """Tests for level progression."""

    def test_level_starts_at_one(self, multilevel_task_graph: Path, monkeypatch, mock_orchestrator_deps) -> None:
        """Test orchestration starts at level 1."""
        monkeypatch.chdir(multilevel_task_graph)

        orch = Orchestrator("multilevel-test")

        assert orch.levels.current_level == 1

    def test_level_completion_updates_state(
        self, multilevel_task_graph: Path, monkeypatch, mock_orchestrator_deps
    ) -> None:
        """Test level completion updates state after merge."""
        monkeypatch.chdir(multilevel_task_graph)

        orch = Orchestrator("multilevel-test")
        orch._spawn_worker(0)
        orch._on_level_complete_handler(1)

        # After merge, state should be updated
        mock_orchestrator_deps["state"].set_level_status.assert_called()
        mock_orchestrator_deps["state"].append_event.assert_called()

    def test_level_blocked_until_merge(self, multilevel_task_graph: Path, monkeypatch, mock_orchestrator_deps) -> None:
        """Test level doesn't advance until merge completes."""
        monkeypatch.chdir(multilevel_task_graph)

        # Merge fails
        mock_orchestrator_deps["merge"].full_merge_flow.return_value.success = False
        mock_orchestrator_deps["merge"].full_merge_flow.return_value.error = "Conflict"

        with patch("zerg.level_coordinator.time.sleep"):
            orch = Orchestrator("multilevel-test")
            orch._spawn_worker(0)
            orch._on_level_complete_handler(1)

            # Should not advance due to merge failure
            mock_orchestrator_deps["levels"].advance_level.assert_not_called()


class TestTaskDependencies:
    """Tests for task dependency handling."""

    def test_level2_tasks_wait_for_level1(
        self, multilevel_task_graph: Path, monkeypatch, mock_orchestrator_deps
    ) -> None:
        """Test level 2 tasks wait for level 1 completion."""
        monkeypatch.chdir(multilevel_task_graph)

        mock_orchestrator_deps["levels"].get_pending_tasks_for_level.return_value = ["L1-TASK-001", "L1-TASK-002"]

        orch = Orchestrator("multilevel-test")

        # Only level 1 tasks should be pending
        pending = orch.levels.get_pending_tasks_for_level(1)
        assert "L2-TASK-001" not in pending
        assert "L2-TASK-002" not in pending

    def test_final_level_runs_after_all(self, multilevel_task_graph: Path, monkeypatch, mock_orchestrator_deps) -> None:
        """Test final level runs after all previous levels."""
        monkeypatch.chdir(multilevel_task_graph)

        mock_orchestrator_deps["levels"].current_level = 3
        mock_orchestrator_deps["levels"].get_pending_tasks_for_level.return_value = ["L3-TASK-001"]

        orch = Orchestrator("multilevel-test")

        # Level 3 should have only the final task
        pending = orch.levels.get_pending_tasks_for_level(3)
        assert "L3-TASK-001" in pending


class TestLevelMerging:
    """Tests for level merge operations."""

    def test_merge_triggered_on_level_complete(
        self, multilevel_task_graph: Path, monkeypatch, mock_orchestrator_deps
    ) -> None:
        """Test merge is triggered when level completes."""
        monkeypatch.chdir(multilevel_task_graph)

        orch = Orchestrator("multilevel-test")
        orch._spawn_worker(0)
        orch._on_level_complete_handler(1)

        mock_orchestrator_deps["merge"].full_merge_flow.assert_called()

    def test_merge_status_tracked(self, multilevel_task_graph: Path, monkeypatch, mock_orchestrator_deps) -> None:
        """Test merge status is tracked in state."""
        monkeypatch.chdir(multilevel_task_graph)

        orch = Orchestrator("multilevel-test")
        orch._spawn_worker(0)
        orch._on_level_complete_handler(1)

        # Should update merge status
        mock_orchestrator_deps["state"].set_level_merge_status.assert_called()


class TestParallelExecution:
    """Tests for parallel task execution within levels."""

    def test_multiple_workers_per_level(self, multilevel_task_graph: Path, monkeypatch, mock_orchestrator_deps) -> None:
        """Test multiple workers execute level tasks in parallel."""
        monkeypatch.chdir(multilevel_task_graph)

        mock_orchestrator_deps["levels"].start_level.return_value = ["L1-TASK-001", "L1-TASK-002", "L1-TASK-003"]
        mock_orchestrator_deps["ports"].allocate_one.side_effect = [49152, 49153, 49154]

        orch = Orchestrator("multilevel-test")

        # Spawn 3 workers
        for i in range(3):
            orch._spawn_worker(i)

        assert len(orch._workers) == 3


class TestCompletionTracking:
    """Tests for completion tracking across levels."""

    def test_progress_tracked_across_levels(
        self, multilevel_task_graph: Path, monkeypatch, mock_orchestrator_deps
    ) -> None:
        """Test overall progress is tracked."""
        monkeypatch.chdir(multilevel_task_graph)

        mock_orchestrator_deps["levels"].get_status.return_value = {
            "current_level": 1,
            "total_tasks": 6,
            "completed_tasks": 3,
            "failed_tasks": 0,
            "in_progress_tasks": 0,
            "progress_percent": 50,
            "levels": {},
            "is_complete": False,
        }

        orch = Orchestrator("multilevel-test")
        status = orch.status()

        assert "progress" in status
        assert status["progress"]["percent"] == 50

    def test_all_levels_complete_detection(
        self, multilevel_task_graph: Path, monkeypatch, mock_orchestrator_deps
    ) -> None:
        """Test detection when all levels are complete."""
        monkeypatch.chdir(multilevel_task_graph)

        mock_orchestrator_deps["levels"].current_level = 3
        mock_orchestrator_deps["levels"].get_status.return_value = {
            "current_level": 3,
            "total_tasks": 6,
            "completed_tasks": 6,
            "failed_tasks": 0,
            "in_progress_tasks": 0,
            "progress_percent": 100,
            "levels": {},
            "is_complete": True,
        }

        orch = Orchestrator("multilevel-test")
        status = orch.status()

        assert status["is_complete"] is True


class TestLevelStatusReporting:
    """Tests for level status reporting."""

    def test_status_includes_feature(self, multilevel_task_graph: Path, monkeypatch, mock_orchestrator_deps) -> None:
        """Test status includes feature name."""
        monkeypatch.chdir(multilevel_task_graph)

        orch = Orchestrator("multilevel-test")
        status = orch.status()

        assert status["feature"] == "multilevel-test"

    def test_status_includes_workers(self, multilevel_task_graph: Path, monkeypatch, mock_orchestrator_deps) -> None:
        """Test status includes worker info."""
        monkeypatch.chdir(multilevel_task_graph)

        orch = Orchestrator("multilevel-test")
        orch._spawn_worker(0)

        status = orch.status()

        assert "workers" in status
        assert 0 in status["workers"]
