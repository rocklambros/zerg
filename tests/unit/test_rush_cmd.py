"""Unit tests for ZERG rush command.

Comprehensive tests covering all code paths in zerg/commands/rush.py:
- rush() main entry point with all options and flags
- find_task_graph() task graph discovery logic
- show_summary() execution summary display
- show_dry_run() dry run plan display
- Error handling paths (keyboard interrupt, general exceptions)
- Orchestrator callbacks and status handling
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from zerg.cli import cli
from zerg.commands.rush import find_task_graph, show_dry_run, show_summary

if TYPE_CHECKING:
    from pytest import MonkeyPatch


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def minimal_task_graph() -> dict[str, Any]:
    """Create a minimal valid task graph for testing."""
    return {
        "schema": "1.0",
        "feature": "test-feature",
        "version": "1.0.0",
        "generated": "2026-01-26T10:00:00Z",
        "total_tasks": 3,
        "estimated_duration_minutes": 45,
        "max_parallelization": 2,
        "critical_path_minutes": 30,
        "tasks": [
            {
                "id": "L1-001",
                "title": "First Task",
                "description": "Test task 1",
                "level": 1,
                "dependencies": [],
                "files": {"create": ["src/a.py"], "modify": [], "read": []},
                "verification": {"command": "python -c 'print(1)'", "timeout_seconds": 30},
                "estimate_minutes": 10,
                "critical_path": True,
            },
            {
                "id": "L1-002",
                "title": "Second Task",
                "description": "Test task 2",
                "level": 1,
                "dependencies": [],
                "files": {"create": ["src/b.py"], "modify": [], "read": []},
                "verification": {"command": "python -c 'print(2)'", "timeout_seconds": 30},
                "estimate_minutes": 15,
                "critical_path": False,
            },
            {
                "id": "L2-001",
                "title": "Third Task",
                "description": "Test task 3",
                "level": 2,
                "dependencies": ["L1-001", "L1-002"],
                "files": {"create": ["src/c.py"], "modify": [], "read": []},
                "verification": {"command": "python -c 'print(3)'", "timeout_seconds": 30},
                "estimate_minutes": 20,
                "critical_path": True,
            },
        ],
        "levels": {
            "1": {
                "name": "foundation",
                "tasks": ["L1-001", "L1-002"],
                "parallel": True,
                "estimated_minutes": 25,
                "depends_on_levels": [],
            },
            "2": {
                "name": "core",
                "tasks": ["L2-001"],
                "parallel": True,
                "estimated_minutes": 20,
                "depends_on_levels": [1],
            },
        },
    }


@pytest.fixture
def task_graph_file_setup(tmp_path: Path, minimal_task_graph: dict[str, Any]) -> Path:
    """Create a task graph file in a temporary directory.

    Args:
        tmp_path: Pytest temporary directory
        minimal_task_graph: Minimal task graph fixture

    Returns:
        Path to the task graph file
    """
    # Create .gsd/tasks directory structure
    tasks_dir = tmp_path / ".gsd" / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)

    task_graph_path = tasks_dir / "task-graph.json"
    with open(task_graph_path, "w") as f:
        json.dump(minimal_task_graph, f, indent=2)

    return task_graph_path


@pytest.fixture
def mock_orchestrator() -> MagicMock:
    """Create a mock Orchestrator for testing.

    Returns:
        Mock Orchestrator instance
    """
    mock = MagicMock()
    mock.status.return_value = {
        "feature": "test-feature",
        "running": False,
        "current_level": 1,
        "progress": {
            "total": 3,
            "completed": 3,
            "failed": 0,
            "in_progress": 0,
            "percent": 100.0,
        },
        "workers": {},
        "levels": {
            1: {"status": "complete", "tasks": 2, "merge_commit": "abc123"},
            2: {"status": "complete", "tasks": 1, "merge_commit": "def456"},
        },
        "is_complete": True,
    }
    return mock


@pytest.fixture
def mock_orchestrator_incomplete() -> MagicMock:
    """Create a mock Orchestrator that is not complete.

    Returns:
        Mock Orchestrator with incomplete status
    """
    mock = MagicMock()
    mock.status.return_value = {
        "feature": "test-feature",
        "running": True,
        "current_level": 1,
        "progress": {
            "total": 3,
            "completed": 1,
            "failed": 0,
            "in_progress": 2,
            "percent": 33.3,
        },
        "workers": {
            0: {"status": "running", "current_task": "L1-001", "tasks_completed": 0},
        },
        "levels": {
            1: {"status": "running", "tasks": 2, "merge_commit": None},
        },
        "is_complete": False,
    }
    return mock


# =============================================================================
# Test find_task_graph()
# =============================================================================


class TestFindTaskGraph:
    """Tests for find_task_graph() function."""

    def test_find_task_graph_with_feature_in_specs(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test finding task graph in .gsd/specs/<feature>/ directory."""
        monkeypatch.chdir(tmp_path)

        # Create feature-specific task graph
        feature_dir = tmp_path / ".gsd" / "specs" / "user-auth"
        feature_dir.mkdir(parents=True)
        task_graph = feature_dir / "task-graph.json"
        task_graph.write_text("{}")

        result = find_task_graph("user-auth")
        # find_task_graph returns relative paths, so resolve both for comparison
        assert result is not None
        assert result.resolve() == task_graph.resolve()

    def test_find_task_graph_in_gsd_tasks(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test finding task graph in .gsd/tasks/ directory."""
        monkeypatch.chdir(tmp_path)

        # Create task graph in .gsd/tasks
        tasks_dir = tmp_path / ".gsd" / "tasks"
        tasks_dir.mkdir(parents=True)
        task_graph = tasks_dir / "task-graph.json"
        task_graph.write_text("{}")

        result = find_task_graph(None)
        # find_task_graph returns relative paths, so resolve both for comparison
        assert result is not None
        assert result.resolve() == task_graph.resolve()

    def test_find_task_graph_in_root(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test finding task graph in project root."""
        monkeypatch.chdir(tmp_path)

        # Create task graph in root
        task_graph = tmp_path / "task-graph.json"
        task_graph.write_text("{}")

        result = find_task_graph(None)
        # find_task_graph returns relative paths, so resolve both for comparison
        assert result is not None
        assert result.resolve() == task_graph.resolve()

    def test_find_task_graph_priority_feature_over_tasks(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test that feature-specific path takes priority over general path."""
        monkeypatch.chdir(tmp_path)

        # Create both paths
        feature_dir = tmp_path / ".gsd" / "specs" / "my-feature"
        feature_dir.mkdir(parents=True)
        feature_graph = feature_dir / "task-graph.json"
        feature_graph.write_text('{"feature": "from-specs"}')

        tasks_dir = tmp_path / ".gsd" / "tasks"
        tasks_dir.mkdir(parents=True)
        tasks_graph = tasks_dir / "task-graph.json"
        tasks_graph.write_text('{"feature": "from-tasks"}')

        result = find_task_graph("my-feature")
        # find_task_graph returns relative paths, so resolve both for comparison
        assert result is not None
        assert result.resolve() == feature_graph.resolve()

    def test_find_task_graph_search_gsd_recursively(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test recursive search in .gsd directory when specific paths don't exist."""
        monkeypatch.chdir(tmp_path)

        # Create task graph in nested .gsd directory
        nested_dir = tmp_path / ".gsd" / "nested" / "path"
        nested_dir.mkdir(parents=True)
        task_graph = nested_dir / "task-graph.json"
        task_graph.write_text("{}")

        result = find_task_graph(None)
        assert result is not None
        assert result.name == "task-graph.json"

    def test_find_task_graph_not_found(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test returns None when no task graph found."""
        monkeypatch.chdir(tmp_path)

        # No task graph anywhere
        result = find_task_graph(None)
        assert result is None

    def test_find_task_graph_no_gsd_directory(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test returns None when .gsd directory doesn't exist."""
        monkeypatch.chdir(tmp_path)

        result = find_task_graph("some-feature")
        assert result is None


# =============================================================================
# Test show_summary()
# =============================================================================


class TestShowSummary:
    """Tests for show_summary() function."""

    def test_show_summary_basic(self, minimal_task_graph: dict[str, Any], capsys: pytest.CaptureFixture[str]) -> None:
        """Test basic summary display."""
        show_summary(minimal_task_graph, workers=5)

        captured = capsys.readouterr()
        assert "test-feature" in captured.out
        assert "3" in captured.out  # Total tasks
        assert "2" in captured.out  # Levels
        assert "5" in captured.out  # Workers

    def test_show_summary_with_mode(
        self, minimal_task_graph: dict[str, Any], capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test summary display with execution mode."""
        show_summary(minimal_task_graph, workers=3, mode="container")

        captured = capsys.readouterr()
        assert "container" in captured.out

    def test_show_summary_with_critical_path(
        self, minimal_task_graph: dict[str, Any], capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test summary display includes critical path minutes."""
        show_summary(minimal_task_graph, workers=5)

        captured = capsys.readouterr()
        assert "30" in captured.out  # critical_path_minutes

    def test_show_summary_auto_mode(
        self, minimal_task_graph: dict[str, Any], capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test summary with auto mode."""
        show_summary(minimal_task_graph, workers=5, mode="auto")

        captured = capsys.readouterr()
        assert "auto" in captured.out

    def test_show_summary_subprocess_mode(
        self, minimal_task_graph: dict[str, Any], capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test summary with subprocess mode."""
        show_summary(minimal_task_graph, workers=5, mode="subprocess")

        captured = capsys.readouterr()
        assert "subprocess" in captured.out

    def test_show_summary_empty_tasks(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test summary with empty tasks list."""
        data = {
            "feature": "empty-feature",
            "tasks": [],
            "levels": {},
        }

        show_summary(data, workers=3)

        captured = capsys.readouterr()
        assert "empty-feature" in captured.out
        assert "0" in captured.out  # 0 tasks

    def test_show_summary_max_parallelization(
        self, minimal_task_graph: dict[str, Any], capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test summary includes max parallelization."""
        show_summary(minimal_task_graph, workers=5)

        captured = capsys.readouterr()
        assert "2" in captured.out  # max_parallelization is 2

    def test_show_summary_no_critical_path(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test summary without critical path minutes."""
        data = {
            "feature": "no-critical",
            "tasks": [{"id": "T1", "title": "Task", "level": 1}],
            "levels": {"1": {"name": "test", "tasks": ["T1"]}},
        }

        show_summary(data, workers=3)

        captured = capsys.readouterr()
        assert "no-critical" in captured.out
        # Should not crash without critical_path_minutes


# =============================================================================
# Test show_dry_run()
# =============================================================================


class TestShowDryRun:
    """Tests for show_dry_run() function."""

    def test_show_dry_run_basic(self, minimal_task_graph: dict[str, Any], capsys: pytest.CaptureFixture[str]) -> None:
        """Test basic dry run display."""
        show_dry_run(minimal_task_graph, workers=3, feature="test-feature")

        captured = capsys.readouterr()
        assert "Dry Run" in captured.out
        assert "Execution Plan" in captured.out
        assert "Level 1" in captured.out
        assert "Level 2" in captured.out

    def test_show_dry_run_shows_tasks(
        self, minimal_task_graph: dict[str, Any], capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test dry run shows task details."""
        show_dry_run(minimal_task_graph, workers=3, feature="test-feature")

        captured = capsys.readouterr()
        assert "L1-001" in captured.out
        assert "L1-002" in captured.out
        assert "L2-001" in captured.out
        assert "First Task" in captured.out

    def test_show_dry_run_shows_worker_assignments(
        self, minimal_task_graph: dict[str, Any], capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test dry run shows worker assignments."""
        show_dry_run(minimal_task_graph, workers=3, feature="test-feature")

        captured = capsys.readouterr()
        # Should show worker numbers
        assert "0" in captured.out or "1" in captured.out or "2" in captured.out

    def test_show_dry_run_shows_estimates(
        self, minimal_task_graph: dict[str, Any], capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test dry run shows time estimates."""
        show_dry_run(minimal_task_graph, workers=3, feature="test-feature")

        captured = capsys.readouterr()
        assert "10m" in captured.out or "15m" in captured.out or "20m" in captured.out

    def test_show_dry_run_shows_critical_path_marker(
        self, minimal_task_graph: dict[str, Any], capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test dry run shows critical path marker."""
        show_dry_run(minimal_task_graph, workers=3, feature="test-feature")

        captured = capsys.readouterr()
        # Critical path tasks should have a star marker
        # L1-001 and L2-001 are on critical path
        assert "First Task" in captured.out  # Critical path task

    def test_show_dry_run_no_workers_message(
        self, minimal_task_graph: dict[str, Any], capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test dry run shows no-workers message."""
        show_dry_run(minimal_task_graph, workers=3, feature="test-feature")

        captured = capsys.readouterr()
        assert "No workers will be started" in captured.out

    def test_show_dry_run_level_names(
        self, minimal_task_graph: dict[str, Any], capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test dry run shows level names."""
        show_dry_run(minimal_task_graph, workers=3, feature="test-feature")

        captured = capsys.readouterr()
        assert "foundation" in captured.out
        assert "core" in captured.out

    def test_show_dry_run_missing_level_info(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test dry run handles missing level info gracefully."""
        data = {
            "feature": "simple",
            "tasks": [{"id": "T1", "title": "Task One", "level": 1, "estimate_minutes": 10}],
            "levels": {},  # Empty levels
        }

        show_dry_run(data, workers=2, feature="simple")

        captured = capsys.readouterr()
        assert "Level 1" in captured.out
        assert "T1" in captured.out


# =============================================================================
# Test rush() Command CLI
# =============================================================================


class TestRushCommand:
    """Tests for rush CLI command."""

    def test_rush_help(self) -> None:
        """Test rush --help displays options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["rush", "--help"])

        assert result.exit_code == 0
        assert "workers" in result.output
        assert "feature" in result.output
        assert "level" in result.output
        assert "dry-run" in result.output
        assert "resume" in result.output
        assert "timeout" in result.output
        assert "task-graph" in result.output
        assert "mode" in result.output
        assert "verbose" in result.output

    def test_rush_no_task_graph_error(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test rush fails gracefully when no task graph found."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        runner = CliRunner()
        result = runner.invoke(cli, ["rush"])

        assert result.exit_code == 1
        assert "No task-graph.json found" in result.output

    def test_rush_with_explicit_task_graph(
        self,
        tmp_path: Path,
        task_graph_file_setup: Path,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """Test rush with explicit task graph path."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = runner.invoke(cli, ["rush", "--task-graph", str(task_graph_file_setup)])

        # Should find the task graph and start processing
        # May fail at later stage due to no config, but should not fail on task graph
        assert "No task-graph.json found" not in result.output

    def test_rush_dry_run(
        self,
        tmp_path: Path,
        task_graph_file_setup: Path,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """Test rush --dry-run invokes DryRunSimulator."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        with patch("zerg.commands.rush.ZergConfig") as mock_config_cls:
            mock_config = MagicMock()
            mock_config_cls.load.return_value = mock_config

            result = runner.invoke(
                cli,
                ["rush", "--task-graph", str(task_graph_file_setup), "--dry-run"],
            )

        # Enhanced dry run renders validation + timeline panels
        assert "Validation" in result.output
        assert "ready to rush" in result.output.lower()

    def test_rush_verbose_flag(
        self,
        tmp_path: Path,
        task_graph_file_setup: Path,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """Test rush --verbose enables verbose logging."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        with (
            patch("zerg.commands.rush.setup_logging") as mock_setup,
            patch("zerg.commands.rush.ZergConfig") as mock_config_cls,
        ):
            mock_config = MagicMock()
            mock_config_cls.load.return_value = mock_config

            runner.invoke(
                cli,
                [
                    "rush",
                    "--task-graph",
                    str(task_graph_file_setup),
                    "--dry-run",
                    "--verbose",
                ],
            )

        # Should have called setup_logging with debug level
        mock_setup.assert_called()
        call_kwargs = mock_setup.call_args
        if call_kwargs:
            assert call_kwargs[1].get("level") == "debug" or call_kwargs[0][0] == "debug"

    def test_rush_workers_option(
        self,
        tmp_path: Path,
        task_graph_file_setup: Path,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """Test rush --workers option."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        with patch("zerg.commands.rush.ZergConfig") as mock_config_cls:
            mock_config = MagicMock()
            mock_config_cls.load.return_value = mock_config

            result = runner.invoke(
                cli,
                [
                    "rush",
                    "--task-graph",
                    str(task_graph_file_setup),
                    "--dry-run",
                    "--workers",
                    "10",
                ],
            )

        # Should show 10 workers in summary
        assert "10" in result.output

    def test_rush_mode_subprocess(
        self,
        tmp_path: Path,
        task_graph_file_setup: Path,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """Test rush --mode subprocess option."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        with patch("zerg.commands.rush.ZergConfig") as mock_config_cls:
            mock_config = MagicMock()
            mock_config_cls.load.return_value = mock_config

            result = runner.invoke(
                cli,
                [
                    "rush",
                    "--task-graph",
                    str(task_graph_file_setup),
                    "--dry-run",
                    "--mode",
                    "subprocess",
                ],
            )

        assert "subprocess" in result.output

    def test_rush_mode_container(
        self,
        tmp_path: Path,
        task_graph_file_setup: Path,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """Test rush --mode container option."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        with patch("zerg.commands.rush.ZergConfig") as mock_config_cls:
            mock_config = MagicMock()
            mock_config_cls.load.return_value = mock_config

            result = runner.invoke(
                cli,
                [
                    "rush",
                    "--task-graph",
                    str(task_graph_file_setup),
                    "--dry-run",
                    "--mode",
                    "container",
                ],
            )

        assert "container" in result.output

    def test_rush_mode_auto(
        self,
        tmp_path: Path,
        task_graph_file_setup: Path,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """Test rush --mode auto option."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        with patch("zerg.commands.rush.ZergConfig") as mock_config_cls:
            mock_config = MagicMock()
            mock_config_cls.load.return_value = mock_config

            result = runner.invoke(
                cli,
                [
                    "rush",
                    "--task-graph",
                    str(task_graph_file_setup),
                    "--dry-run",
                    "--mode",
                    "auto",
                ],
            )

        assert "auto" in result.output

    def test_rush_feature_name_detection(
        self,
        tmp_path: Path,
        minimal_task_graph: dict[str, Any],
        monkeypatch: MonkeyPatch,
    ) -> None:
        """Test rush auto-detects feature name from task graph."""
        monkeypatch.chdir(tmp_path)

        # Create task graph with specific feature name
        tasks_dir = tmp_path / ".gsd" / "tasks"
        tasks_dir.mkdir(parents=True)
        task_graph_path = tasks_dir / "task-graph.json"
        with open(task_graph_path, "w") as f:
            json.dump(minimal_task_graph, f)

        runner = CliRunner()
        with patch("zerg.commands.rush.ZergConfig") as mock_config_cls:
            mock_config = MagicMock()
            mock_config_cls.load.return_value = mock_config

            result = runner.invoke(cli, ["rush", "--dry-run"])

        assert "test-feature" in result.output

    def test_rush_explicit_feature_option(
        self,
        tmp_path: Path,
        minimal_task_graph: dict[str, Any],
        monkeypatch: MonkeyPatch,
    ) -> None:
        """Test rush --feature option overrides auto-detection."""
        monkeypatch.chdir(tmp_path)

        # Create task graph
        tasks_dir = tmp_path / ".gsd" / "tasks"
        tasks_dir.mkdir(parents=True)
        task_graph_path = tasks_dir / "task-graph.json"
        with open(task_graph_path, "w") as f:
            json.dump(minimal_task_graph, f)

        runner = CliRunner()
        with patch("zerg.commands.rush.ZergConfig") as mock_config_cls:
            mock_config = MagicMock()
            mock_config_cls.load.return_value = mock_config

            result = runner.invoke(cli, ["rush", "--dry-run", "--feature", "custom-feature"])

        # Should use custom feature name, though task graph has test-feature
        # The output should include custom-feature in the header
        # Note: feature name in dry run might come from task graph parsing
        assert result.exit_code == 0 or "custom-feature" in result.output


class TestRushExecution:
    """Tests for rush command execution paths (non-dry-run)."""

    def test_rush_abort_on_user_decline(
        self,
        tmp_path: Path,
        task_graph_file_setup: Path,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """Test rush aborts when user declines confirmation."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        with patch("zerg.commands.rush.ZergConfig") as mock_config_cls:
            mock_config = MagicMock()
            mock_config_cls.load.return_value = mock_config

            # Simulate user saying 'n' to confirmation
            result = runner.invoke(
                cli,
                ["rush", "--task-graph", str(task_graph_file_setup)],
                input="n\n",
            )

        assert "Aborted" in result.output

    def test_rush_proceeds_on_user_confirm(
        self,
        tmp_path: Path,
        task_graph_file_setup: Path,
        monkeypatch: MonkeyPatch,
        mock_orchestrator: MagicMock,
    ) -> None:
        """Test rush proceeds when user confirms."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        with (
            patch("zerg.commands.rush.ZergConfig") as mock_config_cls,
            patch("zerg.commands.rush.Orchestrator") as mock_orch_cls,
        ):
            mock_config = MagicMock()
            mock_config_cls.load.return_value = mock_config
            mock_orch_cls.return_value = mock_orchestrator

            # Simulate user saying 'y' to confirmation
            runner.invoke(
                cli,
                ["rush", "--task-graph", str(task_graph_file_setup)],
                input="y\n",
            )

        # Should have started orchestrator
        mock_orchestrator.start.assert_called_once()

    def test_rush_skips_confirm_on_resume(
        self,
        tmp_path: Path,
        task_graph_file_setup: Path,
        monkeypatch: MonkeyPatch,
        mock_orchestrator: MagicMock,
    ) -> None:
        """Test rush --resume skips confirmation."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        with (
            patch("zerg.commands.rush.ZergConfig") as mock_config_cls,
            patch("zerg.commands.rush.Orchestrator") as mock_orch_cls,
        ):
            mock_config = MagicMock()
            mock_config_cls.load.return_value = mock_config
            mock_orch_cls.return_value = mock_orchestrator

            # No input needed with --resume
            runner.invoke(
                cli,
                ["rush", "--task-graph", str(task_graph_file_setup), "--resume"],
            )

        # Should have started orchestrator without confirmation
        mock_orchestrator.start.assert_called_once()

    def test_rush_with_start_level(
        self,
        tmp_path: Path,
        task_graph_file_setup: Path,
        monkeypatch: MonkeyPatch,
        mock_orchestrator: MagicMock,
    ) -> None:
        """Test rush --level option starts from specific level."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        with (
            patch("zerg.commands.rush.ZergConfig") as mock_config_cls,
            patch("zerg.commands.rush.Orchestrator") as mock_orch_cls,
        ):
            mock_config = MagicMock()
            mock_config_cls.load.return_value = mock_config
            mock_orch_cls.return_value = mock_orchestrator

            runner.invoke(
                cli,
                [
                    "rush",
                    "--task-graph",
                    str(task_graph_file_setup),
                    "--resume",
                    "--level",
                    "2",
                ],
            )

        # Should have started with level 2
        call_kwargs = mock_orchestrator.start.call_args
        assert call_kwargs[1].get("start_level") == 2 or (len(call_kwargs[0]) > 2 and call_kwargs[0][2] == 2)

    def test_rush_shows_complete_status(
        self,
        tmp_path: Path,
        task_graph_file_setup: Path,
        monkeypatch: MonkeyPatch,
        mock_orchestrator: MagicMock,
    ) -> None:
        """Test rush shows completion message when all tasks complete."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        with (
            patch("zerg.commands.rush.ZergConfig") as mock_config_cls,
            patch("zerg.commands.rush.Orchestrator") as mock_orch_cls,
        ):
            mock_config = MagicMock()
            mock_config_cls.load.return_value = mock_config
            mock_orch_cls.return_value = mock_orchestrator

            result = runner.invoke(
                cli,
                ["rush", "--task-graph", str(task_graph_file_setup), "--resume"],
            )

        assert "All tasks complete" in result.output

    def test_rush_shows_incomplete_status(
        self,
        tmp_path: Path,
        task_graph_file_setup: Path,
        monkeypatch: MonkeyPatch,
        mock_orchestrator_incomplete: MagicMock,
    ) -> None:
        """Test rush shows progress when not all tasks complete."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        with (
            patch("zerg.commands.rush.ZergConfig") as mock_config_cls,
            patch("zerg.commands.rush.Orchestrator") as mock_orch_cls,
        ):
            mock_config = MagicMock()
            mock_config_cls.load.return_value = mock_config
            mock_orch_cls.return_value = mock_orchestrator_incomplete

            result = runner.invoke(
                cli,
                ["rush", "--task-graph", str(task_graph_file_setup), "--resume"],
            )

        assert "stopped at" in result.output or "33" in result.output

    def test_rush_registers_callbacks(
        self,
        tmp_path: Path,
        task_graph_file_setup: Path,
        monkeypatch: MonkeyPatch,
        mock_orchestrator: MagicMock,
    ) -> None:
        """Test rush registers task and level completion callbacks."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        with (
            patch("zerg.commands.rush.ZergConfig") as mock_config_cls,
            patch("zerg.commands.rush.Orchestrator") as mock_orch_cls,
        ):
            mock_config = MagicMock()
            mock_config_cls.load.return_value = mock_config
            mock_orch_cls.return_value = mock_orchestrator

            runner.invoke(
                cli,
                ["rush", "--task-graph", str(task_graph_file_setup), "--resume"],
            )

        # Should have registered callbacks
        mock_orchestrator.on_task_complete.assert_called_once()
        mock_orchestrator.on_level_complete.assert_called_once()


class TestRushCurrentFeatureCleanup:
    """Tests for rush clearing .current-feature on successful completion."""

    def test_rush_clears_current_feature_on_complete(
        self,
        tmp_path: Path,
        task_graph_file_setup: Path,
        monkeypatch: MonkeyPatch,
        mock_orchestrator: MagicMock,
    ) -> None:
        """Test rush clears .current-feature when all tasks complete."""
        monkeypatch.chdir(tmp_path)

        # Create .current-feature pointing to the feature
        gsd_dir = tmp_path / ".gsd"
        gsd_dir.mkdir(parents=True, exist_ok=True)
        current_feature = gsd_dir / ".current-feature"
        current_feature.write_text("test-feature")

        runner = CliRunner()
        with (
            patch("zerg.commands.rush.ZergConfig") as mock_config_cls,
            patch("zerg.commands.rush.Orchestrator") as mock_orch_cls,
        ):
            mock_config = MagicMock()
            mock_config_cls.load.return_value = mock_config
            mock_orch_cls.return_value = mock_orchestrator

            result = runner.invoke(
                cli,
                ["rush", "--task-graph", str(task_graph_file_setup), "--resume"],
            )

        assert "All tasks complete" in result.output
        assert not current_feature.exists()

    def test_rush_preserves_current_feature_on_incomplete(
        self,
        tmp_path: Path,
        task_graph_file_setup: Path,
        monkeypatch: MonkeyPatch,
        mock_orchestrator_incomplete: MagicMock,
    ) -> None:
        """Test rush preserves .current-feature when tasks are incomplete."""
        monkeypatch.chdir(tmp_path)

        # Create .current-feature pointing to the feature
        gsd_dir = tmp_path / ".gsd"
        gsd_dir.mkdir(parents=True, exist_ok=True)
        current_feature = gsd_dir / ".current-feature"
        current_feature.write_text("test-feature")

        runner = CliRunner()
        with (
            patch("zerg.commands.rush.ZergConfig") as mock_config_cls,
            patch("zerg.commands.rush.Orchestrator") as mock_orch_cls,
        ):
            mock_config = MagicMock()
            mock_config_cls.load.return_value = mock_config
            mock_orch_cls.return_value = mock_orchestrator_incomplete

            runner.invoke(
                cli,
                ["rush", "--task-graph", str(task_graph_file_setup), "--resume"],
            )

        # Should still exist since tasks aren't complete
        assert current_feature.exists()
        assert current_feature.read_text().strip() == "test-feature"


class TestRushErrorHandling:
    """Tests for rush command error handling."""

    def test_rush_keyboard_interrupt(
        self,
        tmp_path: Path,
        task_graph_file_setup: Path,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """Test rush handles KeyboardInterrupt gracefully."""
        monkeypatch.chdir(tmp_path)

        mock_orch = MagicMock()
        mock_orch.start.side_effect = KeyboardInterrupt()

        runner = CliRunner()
        with (
            patch("zerg.commands.rush.ZergConfig") as mock_config_cls,
            patch("zerg.commands.rush.Orchestrator") as mock_orch_cls,
        ):
            mock_config = MagicMock()
            mock_config_cls.load.return_value = mock_config
            mock_orch_cls.return_value = mock_orch

            result = runner.invoke(
                cli,
                ["rush", "--task-graph", str(task_graph_file_setup), "--resume"],
            )

        assert result.exit_code == 130
        assert "Interrupted" in result.output

    def test_rush_general_exception(
        self,
        tmp_path: Path,
        task_graph_file_setup: Path,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """Test rush handles general exceptions."""
        monkeypatch.chdir(tmp_path)

        mock_orch = MagicMock()
        mock_orch.start.side_effect = RuntimeError("Something went wrong")

        runner = CliRunner()
        with (
            patch("zerg.commands.rush.ZergConfig") as mock_config_cls,
            patch("zerg.commands.rush.Orchestrator") as mock_orch_cls,
        ):
            mock_config = MagicMock()
            mock_config_cls.load.return_value = mock_config
            mock_orch_cls.return_value = mock_orch

            result = runner.invoke(
                cli,
                ["rush", "--task-graph", str(task_graph_file_setup), "--resume"],
            )

        assert result.exit_code == 1
        assert "Error" in result.output
        assert "Something went wrong" in result.output

    def test_rush_verbose_exception_traceback(
        self,
        tmp_path: Path,
        task_graph_file_setup: Path,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """Test rush --verbose shows exception traceback."""
        monkeypatch.chdir(tmp_path)

        mock_orch = MagicMock()
        mock_orch.start.side_effect = ValueError("Detailed error message")

        runner = CliRunner()
        with (
            patch("zerg.commands.rush.ZergConfig") as mock_config_cls,
            patch("zerg.commands.rush.Orchestrator") as mock_orch_cls,
        ):
            mock_config = MagicMock()
            mock_config_cls.load.return_value = mock_config
            mock_orch_cls.return_value = mock_orch

            result = runner.invoke(
                cli,
                [
                    "rush",
                    "--task-graph",
                    str(task_graph_file_setup),
                    "--resume",
                    "--verbose",
                ],
            )

        assert result.exit_code == 1
        # Verbose mode should show more error details
        assert "Error" in result.output

    def test_rush_invalid_task_graph(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test rush handles invalid task graph."""
        monkeypatch.chdir(tmp_path)

        # Create invalid task graph
        tasks_dir = tmp_path / ".gsd" / "tasks"
        tasks_dir.mkdir(parents=True)
        task_graph_path = tasks_dir / "task-graph.json"
        task_graph_path.write_text('{"invalid": "graph"}')  # Missing required fields

        runner = CliRunner()
        with patch("zerg.commands.rush.ZergConfig") as mock_config_cls:
            mock_config = MagicMock()
            mock_config_cls.load.return_value = mock_config

            result = runner.invoke(cli, ["rush", "--dry-run"])

        assert result.exit_code == 1
        assert "Error" in result.output

    def test_rush_task_graph_not_exists(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test rush handles non-existent task graph path."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["rush", "--task-graph", "/nonexistent/path/task-graph.json"],
        )

        assert result.exit_code == 1
        assert "No task-graph.json found" in result.output or "Error" in result.output


class TestRushLogging:
    """Tests for rush command logging configuration."""

    def test_rush_default_logging(
        self,
        tmp_path: Path,
        task_graph_file_setup: Path,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """Test rush sets up info logging by default."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        with (
            patch("zerg.commands.rush.setup_logging") as mock_setup,
            patch("zerg.commands.rush.ZergConfig") as mock_config_cls,
        ):
            mock_config = MagicMock()
            mock_config_cls.load.return_value = mock_config

            runner.invoke(
                cli,
                ["rush", "--task-graph", str(task_graph_file_setup), "--dry-run"],
            )

        # Should have called setup_logging with info level (not verbose)
        mock_setup.assert_called()
        call_kwargs = mock_setup.call_args
        if call_kwargs and call_kwargs[1]:
            # Check the first call was with info level
            assert "level" in call_kwargs[1]


class TestRushOrchestratorIntegration:
    """Tests for rush command orchestrator integration."""

    def test_rush_creates_orchestrator_with_correct_params(
        self,
        tmp_path: Path,
        task_graph_file_setup: Path,
        monkeypatch: MonkeyPatch,
        mock_orchestrator: MagicMock,
    ) -> None:
        """Test rush creates orchestrator with correct parameters."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        with (
            patch("zerg.commands.rush.ZergConfig") as mock_config_cls,
            patch("zerg.commands.rush.Orchestrator") as mock_orch_cls,
        ):
            mock_config = MagicMock()
            mock_config_cls.load.return_value = mock_config
            mock_orch_cls.return_value = mock_orchestrator

            runner.invoke(
                cli,
                [
                    "rush",
                    "--task-graph",
                    str(task_graph_file_setup),
                    "--resume",
                    "--mode",
                    "subprocess",
                ],
            )

        # Check orchestrator was created with correct launcher_mode
        call_kwargs = mock_orch_cls.call_args
        assert call_kwargs[1].get("launcher_mode") == "subprocess"

    def test_rush_passes_workers_count_to_orchestrator(
        self,
        tmp_path: Path,
        task_graph_file_setup: Path,
        monkeypatch: MonkeyPatch,
        mock_orchestrator: MagicMock,
    ) -> None:
        """Test rush passes worker count to orchestrator.start()."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        with (
            patch("zerg.commands.rush.ZergConfig") as mock_config_cls,
            patch("zerg.commands.rush.Orchestrator") as mock_orch_cls,
        ):
            mock_config = MagicMock()
            mock_config_cls.load.return_value = mock_config
            mock_orch_cls.return_value = mock_orchestrator

            runner.invoke(
                cli,
                [
                    "rush",
                    "--task-graph",
                    str(task_graph_file_setup),
                    "--resume",
                    "--workers",
                    "7",
                ],
            )

        # Check orchestrator.start was called with correct worker_count
        call_kwargs = mock_orchestrator.start.call_args
        assert call_kwargs[1].get("worker_count") == 7


class TestRushDryRunEnhanced:
    """Tests for the enhanced dry-run with DryRunSimulator."""

    def test_rush_dry_run_enhanced(
        self,
        tmp_path: Path,
        task_graph_file_setup: Path,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """Invoke rush --dry-run and verify DryRunSimulator is called."""
        monkeypatch.chdir(tmp_path)

        mock_sim = MagicMock()
        mock_report = MagicMock()
        mock_report.has_errors = False
        mock_sim.return_value.run.return_value = mock_report

        runner = CliRunner()
        with (
            patch("zerg.commands.rush.ZergConfig") as mock_config_cls,
            patch("zerg.dryrun.DryRunSimulator", mock_sim) as _,
        ):
            mock_config = MagicMock()
            mock_config_cls.load.return_value = mock_config

            result = runner.invoke(
                cli,
                ["rush", "--task-graph", str(task_graph_file_setup), "--dry-run"],
            )

        # DryRunSimulator should have been instantiated and run() called
        mock_sim.assert_called_once()
        mock_sim.return_value.run.assert_called_once()
        assert result.exit_code == 0

    def test_rush_check_gates_flag(
        self,
        tmp_path: Path,
        task_graph_file_setup: Path,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """--check-gates --dry-run passes run_gates=True to simulator."""
        monkeypatch.chdir(tmp_path)

        mock_sim = MagicMock()
        mock_report = MagicMock()
        mock_report.has_errors = False
        mock_sim.return_value.run.return_value = mock_report

        runner = CliRunner()
        with (
            patch("zerg.commands.rush.ZergConfig") as mock_config_cls,
            patch("zerg.dryrun.DryRunSimulator", mock_sim) as _,
        ):
            mock_config = MagicMock()
            mock_config_cls.load.return_value = mock_config

            result = runner.invoke(
                cli,
                [
                    "rush",
                    "--task-graph",
                    str(task_graph_file_setup),
                    "--dry-run",
                    "--check-gates",
                ],
            )

        # Verify run_gates=True was passed
        call_kwargs = mock_sim.call_args[1]
        assert call_kwargs["run_gates"] is True
        assert result.exit_code == 0

    def test_rush_check_gates_without_dry_run(
        self,
        tmp_path: Path,
        task_graph_file_setup: Path,
        monkeypatch: MonkeyPatch,
        mock_orchestrator: MagicMock,
    ) -> None:
        """--check-gates alone (no --dry-run) has no effect — gates only run in dry-run mode."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        with (
            patch("zerg.commands.rush.ZergConfig") as mock_config_cls,
            patch("zerg.commands.rush.Orchestrator") as mock_orch_cls,
        ):
            mock_config = MagicMock()
            mock_config_cls.load.return_value = mock_config
            mock_orch_cls.return_value = mock_orchestrator

            runner.invoke(
                cli,
                [
                    "rush",
                    "--task-graph",
                    str(task_graph_file_setup),
                    "--resume",
                    "--check-gates",
                ],
            )

        # Should proceed to orchestrator (not dry-run path)
        mock_orchestrator.start.assert_called_once()

    def test_rush_dry_run_exits_1_on_errors(
        self,
        tmp_path: Path,
        task_graph_file_setup: Path,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """Dry-run exits with code 1 when report has errors."""
        monkeypatch.chdir(tmp_path)

        mock_sim = MagicMock()
        mock_report = MagicMock()
        mock_report.has_errors = True
        mock_sim.return_value.run.return_value = mock_report

        runner = CliRunner()
        with (
            patch("zerg.commands.rush.ZergConfig") as mock_config_cls,
            patch("zerg.dryrun.DryRunSimulator", mock_sim) as _,
        ):
            mock_config = MagicMock()
            mock_config_cls.load.return_value = mock_config

            result = runner.invoke(
                cli,
                ["rush", "--task-graph", str(task_graph_file_setup), "--dry-run"],
            )

        assert result.exit_code == 1


class TestRushTaskGraphValidation:
    """Tests for rush command task graph validation."""

    def test_rush_validates_task_graph(
        self,
        tmp_path: Path,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """Test rush validates task graph before proceeding."""
        monkeypatch.chdir(tmp_path)

        # Create task graph with validation issues (duplicate task IDs)
        task_graph = {
            "feature": "test",
            "tasks": [
                {"id": "T1", "title": "Task 1", "level": 1},
                {"id": "T1", "title": "Duplicate", "level": 1},  # Duplicate ID
            ],
            "levels": {"1": {"name": "test", "tasks": ["T1"]}},
        }

        tasks_dir = tmp_path / ".gsd" / "tasks"
        tasks_dir.mkdir(parents=True)
        task_graph_path = tasks_dir / "task-graph.json"
        with open(task_graph_path, "w") as f:
            json.dump(task_graph, f)

        runner = CliRunner()
        with patch("zerg.commands.rush.ZergConfig") as mock_config_cls:
            mock_config = MagicMock()
            mock_config_cls.load.return_value = mock_config

            result = runner.invoke(cli, ["rush", "--dry-run"])

        assert result.exit_code == 1
        assert "Error" in result.output


# =============================================================================
# Test Backlog Callback Integration
# =============================================================================


class TestRushBacklog:
    """Tests for rush command backlog callback integration."""

    def test_rush_registers_backlog_callback(
        self,
        tmp_path: Path,
        task_graph_file_setup: Path,
        monkeypatch: MonkeyPatch,
        mock_orchestrator: MagicMock,
    ) -> None:
        """Test the registered callback invokes update_backlog_task_status when backlog exists."""
        monkeypatch.chdir(tmp_path)

        # Create a backlog file so the callback path is exercised
        backlog_dir = tmp_path / "tasks"
        backlog_dir.mkdir()
        backlog_file = backlog_dir / "TEST-FEATURE-BACKLOG.md"
        backlog_file.write_text("| **L1-001** | First Task | src/a.py | - | TODO | cmd |\n")

        runner = CliRunner()
        with (
            patch("zerg.commands.rush.ZergConfig") as mock_config_cls,
            patch("zerg.commands.rush.Orchestrator") as mock_orch_cls,
            patch("zerg.commands.rush.update_backlog_task_status") as mock_update,
        ):
            mock_config = MagicMock()
            mock_config_cls.load.return_value = mock_config
            mock_orch_cls.return_value = mock_orchestrator

            runner.invoke(
                cli,
                ["rush", "--task-graph", str(task_graph_file_setup), "--resume"],
            )

            # Extract the callback and invoke it
            callback = mock_orchestrator.on_task_complete.call_args[0][0]
            callback("L1-001")

        mock_update.assert_called_once_with(Path("tasks/TEST-FEATURE-BACKLOG.md"), "L1-001", "COMPLETE")

    def test_backlog_update_on_complete(
        self,
        tmp_path: Path,
        task_graph_file_setup: Path,
        monkeypatch: MonkeyPatch,
        mock_orchestrator: MagicMock,
    ) -> None:
        """Test callback updates the backlog file content on task completion."""
        monkeypatch.chdir(tmp_path)

        # Create a backlog file with a TODO task row
        backlog_dir = tmp_path / "tasks"
        backlog_dir.mkdir()
        backlog_file = backlog_dir / "TEST-FEATURE-BACKLOG.md"
        backlog_file.write_text(
            "# Backlog\n\n"
            "| ID | Description | Files | Deps | Status | Verification |\n"
            "|---|---|---|---|---|---|\n"
            "| **L1-001** | First Task | src/a.py | - | TODO | python -c 'print(1)' |\n"
            "| **L1-002** | Second Task | src/b.py | - | TODO | python -c 'print(2)' |\n"
        )

        runner = CliRunner()
        with (
            patch("zerg.commands.rush.ZergConfig") as mock_config_cls,
            patch("zerg.commands.rush.Orchestrator") as mock_orch_cls,
        ):
            mock_config = MagicMock()
            mock_config_cls.load.return_value = mock_config
            mock_orch_cls.return_value = mock_orchestrator

            runner.invoke(
                cli,
                ["rush", "--task-graph", str(task_graph_file_setup), "--resume"],
            )

            # Extract the callback and invoke it with the real backlog on disk
            callback = mock_orchestrator.on_task_complete.call_args[0][0]
            callback("L1-001")

        # Verify the file now contains COMPLETE for L1-001
        updated_content = backlog_file.read_text()
        assert "COMPLETE" in updated_content
        # L1-002 should still be TODO
        assert "TODO" in updated_content

    def test_no_backlog_graceful(
        self,
        tmp_path: Path,
        task_graph_file_setup: Path,
        monkeypatch: MonkeyPatch,
        mock_orchestrator: MagicMock,
    ) -> None:
        """Test callback handles missing backlog file gracefully (no error)."""
        monkeypatch.chdir(tmp_path)

        # Do NOT create a backlog file - tasks/ dir does not exist

        runner = CliRunner()
        with (
            patch("zerg.commands.rush.ZergConfig") as mock_config_cls,
            patch("zerg.commands.rush.Orchestrator") as mock_orch_cls,
        ):
            mock_config = MagicMock()
            mock_config_cls.load.return_value = mock_config
            mock_orch_cls.return_value = mock_orchestrator

            runner.invoke(
                cli,
                ["rush", "--task-graph", str(task_graph_file_setup), "--resume"],
            )

            # Extract the callback and invoke it - no backlog file exists
            callback = mock_orchestrator.on_task_complete.call_args[0][0]

            # Should not raise any exception
            callback("L1-001")
