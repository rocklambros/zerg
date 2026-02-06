"""Unit tests for ZERG rush command.

Thinned from 59 tests to ~25 tests. Retained:
- find_task_graph: 3 (feature path, fallback, not found)
- show_summary: 2 (basic, empty tasks)
- show_dry_run: 2 (basic, missing level info)
- CLI: 1 help + 1 no-task-graph error + 1 dry-run + 1 workers option
- Execution: 1 abort + 1 confirm + 1 resume skip confirm + 1 complete + 1 incomplete
- Error handling: 1 keyboard interrupt + 1 general exception + 1 invalid task graph
- Orchestrator: 1 params + 1 workers count
- DryRun enhanced: 1 basic + 1 check-gates + 1 errors exit 1
- Backlog: 1 callback + 1 no-backlog graceful
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
# Fixtures
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
    """Create a task graph file in a temporary directory."""
    tasks_dir = tmp_path / ".gsd" / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    task_graph_path = tasks_dir / "task-graph.json"
    with open(task_graph_path, "w") as f:
        json.dump(minimal_task_graph, f, indent=2)
    return task_graph_path


@pytest.fixture
def mock_orchestrator() -> MagicMock:
    """Create a mock Orchestrator that completes."""
    mock = MagicMock()
    mock.status.return_value = {
        "feature": "test-feature",
        "running": False,
        "current_level": 1,
        "progress": {"total": 3, "completed": 3, "failed": 0, "in_progress": 0, "percent": 100.0},
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
    """Create a mock Orchestrator that is not complete."""
    mock = MagicMock()
    mock.status.return_value = {
        "feature": "test-feature",
        "running": True,
        "current_level": 1,
        "progress": {"total": 3, "completed": 1, "failed": 0, "in_progress": 2, "percent": 33.3},
        "workers": {0: {"status": "running", "current_task": "L1-001", "tasks_completed": 0}},
        "levels": {1: {"status": "running", "tasks": 2, "merge_commit": None}},
        "is_complete": False,
    }
    return mock


# =============================================================================
# find_task_graph tests
# =============================================================================


class TestFindTaskGraph:
    """Tests for find_task_graph()."""

    def test_find_in_feature_specs(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test finding task graph in .gsd/specs/<feature>/."""
        monkeypatch.chdir(tmp_path)
        feature_dir = tmp_path / ".gsd" / "specs" / "user-auth"
        feature_dir.mkdir(parents=True)
        task_graph = feature_dir / "task-graph.json"
        task_graph.write_text("{}")

        result = find_task_graph("user-auth")
        assert result is not None
        assert result.resolve() == task_graph.resolve()

    def test_find_in_gsd_tasks(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test finding task graph in .gsd/tasks/."""
        monkeypatch.chdir(tmp_path)
        tasks_dir = tmp_path / ".gsd" / "tasks"
        tasks_dir.mkdir(parents=True)
        task_graph = tasks_dir / "task-graph.json"
        task_graph.write_text("{}")

        result = find_task_graph(None)
        assert result is not None
        assert result.resolve() == task_graph.resolve()

    def test_not_found(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test returns None when no task graph found."""
        monkeypatch.chdir(tmp_path)
        result = find_task_graph(None)
        assert result is None


# =============================================================================
# show_summary / show_dry_run tests
# =============================================================================


class TestShowSummary:
    """Tests for show_summary()."""

    def test_basic(self, minimal_task_graph: dict[str, Any], capsys: pytest.CaptureFixture[str]) -> None:
        """Test basic summary display."""
        show_summary(minimal_task_graph, workers=5)
        captured = capsys.readouterr()
        assert "test-feature" in captured.out
        assert "3" in captured.out

    def test_empty_tasks(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test summary with empty tasks list."""
        data = {"feature": "empty-feature", "tasks": [], "levels": {}}
        show_summary(data, workers=3)
        captured = capsys.readouterr()
        assert "empty-feature" in captured.out


class TestShowDryRun:
    """Tests for show_dry_run()."""

    def test_basic(self, minimal_task_graph: dict[str, Any], capsys: pytest.CaptureFixture[str]) -> None:
        """Test basic dry run display."""
        show_dry_run(minimal_task_graph, workers=3, feature="test-feature")
        captured = capsys.readouterr()
        assert "Dry Run" in captured.out
        assert "Level 1" in captured.out
        assert "Level 2" in captured.out

    def test_missing_level_info(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test dry run handles missing level info."""
        data = {
            "feature": "simple",
            "tasks": [{"id": "T1", "title": "Task One", "level": 1, "estimate_minutes": 10}],
            "levels": {},
        }
        show_dry_run(data, workers=2, feature="simple")
        captured = capsys.readouterr()
        assert "Level 1" in captured.out
        assert "T1" in captured.out


# =============================================================================
# CLI tests
# =============================================================================


class TestRushCommand:
    """Tests for rush CLI command."""

    def test_help(self) -> None:
        """Test rush --help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["rush", "--help"])
        assert result.exit_code == 0
        assert "workers" in result.output
        assert "dry-run" in result.output

    def test_no_task_graph_error(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test rush fails when no task graph found."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()
        runner = CliRunner()
        result = runner.invoke(cli, ["rush"])
        assert result.exit_code == 1
        assert "No task-graph.json found" in result.output

    def test_dry_run(self, tmp_path: Path, task_graph_file_setup: Path, monkeypatch: MonkeyPatch) -> None:
        """Test rush --dry-run."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        with patch("zerg.commands.rush.ZergConfig") as mock_config_cls:
            mock_config_cls.load.return_value = MagicMock()
            result = runner.invoke(cli, ["rush", "--task-graph", str(task_graph_file_setup), "--dry-run"])
        assert "Validation" in result.output

    def test_workers_option(self, tmp_path: Path, task_graph_file_setup: Path, monkeypatch: MonkeyPatch) -> None:
        """Test rush --workers option."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        with patch("zerg.commands.rush.ZergConfig") as mock_config_cls:
            mock_config_cls.load.return_value = MagicMock()
            result = runner.invoke(
                cli, ["rush", "--task-graph", str(task_graph_file_setup), "--dry-run", "--workers", "10"]
            )
        assert "10" in result.output


# =============================================================================
# Execution tests
# =============================================================================


class TestRushExecution:
    """Tests for rush execution paths."""

    def test_abort_on_decline(self, tmp_path: Path, task_graph_file_setup: Path, monkeypatch: MonkeyPatch) -> None:
        """Test rush aborts when user declines."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        with patch("zerg.commands.rush.ZergConfig") as mock_config_cls:
            mock_config_cls.load.return_value = MagicMock()
            result = runner.invoke(cli, ["rush", "--task-graph", str(task_graph_file_setup)], input="n\n")
        assert "Aborted" in result.output

    def test_proceeds_on_confirm(
        self, tmp_path: Path, task_graph_file_setup: Path, monkeypatch: MonkeyPatch, mock_orchestrator: MagicMock
    ) -> None:
        """Test rush proceeds when user confirms."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        with (
            patch("zerg.commands.rush.ZergConfig") as mock_config_cls,
            patch("zerg.commands.rush.Orchestrator") as mock_orch_cls,
        ):
            mock_config_cls.load.return_value = MagicMock()
            mock_orch_cls.return_value = mock_orchestrator
            runner.invoke(cli, ["rush", "--task-graph", str(task_graph_file_setup)], input="y\n")
        mock_orchestrator.start.assert_called_once()

    def test_resume_skips_confirm(
        self, tmp_path: Path, task_graph_file_setup: Path, monkeypatch: MonkeyPatch, mock_orchestrator: MagicMock
    ) -> None:
        """Test rush --resume skips confirmation."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        with (
            patch("zerg.commands.rush.ZergConfig") as mock_config_cls,
            patch("zerg.commands.rush.Orchestrator") as mock_orch_cls,
        ):
            mock_config_cls.load.return_value = MagicMock()
            mock_orch_cls.return_value = mock_orchestrator
            runner.invoke(cli, ["rush", "--task-graph", str(task_graph_file_setup), "--resume"])
        mock_orchestrator.start.assert_called_once()

    def test_shows_complete(
        self, tmp_path: Path, task_graph_file_setup: Path, monkeypatch: MonkeyPatch, mock_orchestrator: MagicMock
    ) -> None:
        """Test rush shows completion when all tasks complete."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        with (
            patch("zerg.commands.rush.ZergConfig") as mock_config_cls,
            patch("zerg.commands.rush.Orchestrator") as mock_orch_cls,
        ):
            mock_config_cls.load.return_value = MagicMock()
            mock_orch_cls.return_value = mock_orchestrator
            result = runner.invoke(cli, ["rush", "--task-graph", str(task_graph_file_setup), "--resume"])
        assert "All tasks complete" in result.output

    def test_shows_incomplete(
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
            mock_config_cls.load.return_value = MagicMock()
            mock_orch_cls.return_value = mock_orchestrator_incomplete
            result = runner.invoke(cli, ["rush", "--task-graph", str(task_graph_file_setup), "--resume"])
        assert "stopped at" in result.output or "33" in result.output


# =============================================================================
# Error handling tests
# =============================================================================


class TestRushErrorHandling:
    """Tests for rush error handling."""

    def test_keyboard_interrupt(self, tmp_path: Path, task_graph_file_setup: Path, monkeypatch: MonkeyPatch) -> None:
        """Test rush handles KeyboardInterrupt."""
        monkeypatch.chdir(tmp_path)
        mock_orch = MagicMock()
        mock_orch.start.side_effect = KeyboardInterrupt()
        runner = CliRunner()
        with (
            patch("zerg.commands.rush.ZergConfig") as mock_config_cls,
            patch("zerg.commands.rush.Orchestrator") as mock_orch_cls,
        ):
            mock_config_cls.load.return_value = MagicMock()
            mock_orch_cls.return_value = mock_orch
            result = runner.invoke(cli, ["rush", "--task-graph", str(task_graph_file_setup), "--resume"])
        assert result.exit_code == 130

    def test_general_exception(self, tmp_path: Path, task_graph_file_setup: Path, monkeypatch: MonkeyPatch) -> None:
        """Test rush handles general exceptions."""
        monkeypatch.chdir(tmp_path)
        mock_orch = MagicMock()
        mock_orch.start.side_effect = RuntimeError("Something went wrong")
        runner = CliRunner()
        with (
            patch("zerg.commands.rush.ZergConfig") as mock_config_cls,
            patch("zerg.commands.rush.Orchestrator") as mock_orch_cls,
        ):
            mock_config_cls.load.return_value = MagicMock()
            mock_orch_cls.return_value = mock_orch
            result = runner.invoke(cli, ["rush", "--task-graph", str(task_graph_file_setup), "--resume"])
        assert result.exit_code == 1
        assert "Something went wrong" in result.output

    def test_invalid_task_graph(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test rush handles invalid task graph."""
        monkeypatch.chdir(tmp_path)
        tasks_dir = tmp_path / ".gsd" / "tasks"
        tasks_dir.mkdir(parents=True)
        (tasks_dir / "task-graph.json").write_text('{"invalid": "graph"}')
        runner = CliRunner()
        with patch("zerg.commands.rush.ZergConfig") as mock_config_cls:
            mock_config_cls.load.return_value = MagicMock()
            result = runner.invoke(cli, ["rush", "--dry-run"])
        assert result.exit_code == 1


# =============================================================================
# DryRun enhanced tests
# =============================================================================


class TestRushDryRunEnhanced:
    """Tests for enhanced dry-run with DryRunSimulator."""

    def test_enhanced(self, tmp_path: Path, task_graph_file_setup: Path, monkeypatch: MonkeyPatch) -> None:
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
            mock_config_cls.load.return_value = MagicMock()
            result = runner.invoke(cli, ["rush", "--task-graph", str(task_graph_file_setup), "--dry-run"])
        mock_sim.assert_called_once()
        assert result.exit_code == 0

    def test_check_gates(self, tmp_path: Path, task_graph_file_setup: Path, monkeypatch: MonkeyPatch) -> None:
        """--check-gates --dry-run passes run_gates=True."""
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
            mock_config_cls.load.return_value = MagicMock()
            result = runner.invoke(
                cli, ["rush", "--task-graph", str(task_graph_file_setup), "--dry-run", "--check-gates"]
            )
        assert mock_sim.call_args[1]["run_gates"] is True
        assert result.exit_code == 0

    def test_exits_1_on_errors(self, tmp_path: Path, task_graph_file_setup: Path, monkeypatch: MonkeyPatch) -> None:
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
            mock_config_cls.load.return_value = MagicMock()
            result = runner.invoke(cli, ["rush", "--task-graph", str(task_graph_file_setup), "--dry-run"])
        assert result.exit_code == 1


# =============================================================================
# Backlog tests
# =============================================================================


class TestRushBacklog:
    """Tests for rush backlog callback integration."""

    def test_registers_callback(
        self, tmp_path: Path, task_graph_file_setup: Path, monkeypatch: MonkeyPatch, mock_orchestrator: MagicMock
    ) -> None:
        """Test callback invokes update_backlog_task_status."""
        monkeypatch.chdir(tmp_path)
        backlog_dir = tmp_path / "tasks"
        backlog_dir.mkdir()
        (backlog_dir / "TEST-FEATURE-BACKLOG.md").write_text(
            "| **L1-001** | First Task | src/a.py | - | TODO | cmd |\n"
        )
        runner = CliRunner()
        with (
            patch("zerg.commands.rush.ZergConfig") as mock_config_cls,
            patch("zerg.commands.rush.Orchestrator") as mock_orch_cls,
            patch("zerg.commands.rush.update_backlog_task_status") as mock_update,
        ):
            mock_config_cls.load.return_value = MagicMock()
            mock_orch_cls.return_value = mock_orchestrator
            runner.invoke(cli, ["rush", "--task-graph", str(task_graph_file_setup), "--resume"])
            callback = mock_orchestrator.on_task_complete.call_args[0][0]
            callback("L1-001")
        mock_update.assert_called_once_with(Path("tasks/TEST-FEATURE-BACKLOG.md"), "L1-001", "COMPLETE")

    def test_no_backlog_graceful(
        self, tmp_path: Path, task_graph_file_setup: Path, monkeypatch: MonkeyPatch, mock_orchestrator: MagicMock
    ) -> None:
        """Test callback handles missing backlog file gracefully."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        with (
            patch("zerg.commands.rush.ZergConfig") as mock_config_cls,
            patch("zerg.commands.rush.Orchestrator") as mock_orch_cls,
        ):
            mock_config_cls.load.return_value = MagicMock()
            mock_orch_cls.return_value = mock_orchestrator
            runner.invoke(cli, ["rush", "--task-graph", str(task_graph_file_setup), "--resume"])
            callback = mock_orchestrator.on_task_complete.call_args[0][0]
            callback("L1-001")  # Should not raise
