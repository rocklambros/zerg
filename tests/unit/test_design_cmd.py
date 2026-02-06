"""Unit tests for zerg/commands/design.py.

Thinned from 53 tests to cover unique code paths:
- get_current_feature (exists + missing)
- Design template creation (content + sections)
- Task graph template (structure + feature prefix)
- Task graph validation (valid, invalid JSON, missing fields, conflicts)
- CLI command (help, no feature, approved flow, validate-only, errors)
- Backlog and manifest (1 happy path each)
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from zerg.cli import cli
from zerg.commands.design import (
    create_design_template,
    create_task_graph_template,
    get_current_feature,
    validate_task_graph,
)


class TestGetCurrentFeature:
    """Tests for get_current_feature function."""

    def test_returns_feature_when_file_exists(self) -> None:
        """Test returning feature name when .current-feature file exists."""
        with patch("zerg.commands.design.Path") as mock_path:
            mock_path_instance = MagicMock()
            mock_path_instance.exists.return_value = True
            mock_path_instance.read_text.return_value = "my-feature\n"
            mock_path.return_value = mock_path_instance
            result = get_current_feature()
            assert result == "my-feature"

    def test_returns_none_when_file_missing(self) -> None:
        """Test returning None when .current-feature file does not exist."""
        with patch("zerg.commands.design.Path") as mock_path:
            mock_path_instance = MagicMock()
            mock_path_instance.exists.return_value = False
            mock_path.return_value = mock_path_instance
            result = get_current_feature()
            assert result is None


class TestCreateDesignTemplate:
    """Tests for create_design_template function."""

    def test_creates_design_file_with_required_sections(self, tmp_path: Path) -> None:
        """Test that design.md file is created with correct content and sections."""
        design_path = tmp_path / "design.md"
        create_design_template(design_path, "test-feature")
        assert design_path.exists()
        content = design_path.read_text()
        assert "# Technical Design: test-feature" in content
        assert "**Status**: DRAFT" in content
        for section in ["Overview", "Architecture", "Detailed Design", "Key Decisions", "Risk Assessment"]:
            assert section in content, f"Missing section: {section}"


class TestCreateTaskGraphTemplate:
    """Tests for create_task_graph_template function."""

    def test_task_graph_structure_and_prefix(self, tmp_path: Path) -> None:
        """Test task graph has required fields and uses feature prefix."""
        graph_path = tmp_path / "task-graph.json"
        create_task_graph_template(graph_path, "user-management")
        assert graph_path.exists()
        with open(graph_path) as f:
            data = json.load(f)
        assert data["feature"] == "user-management"
        assert data["version"] == "2.0"
        assert "tasks" in data
        assert "levels" in data
        assert len(data["tasks"]) == 6
        assert data["tasks"][0]["id"].startswith("USER-")


class TestValidateTaskGraph:
    """Tests for validate_task_graph function."""

    def test_validates_correct_task_graph(self, tmp_path: Path) -> None:
        """Test that valid task graph passes validation."""
        graph_path = tmp_path / "task-graph.json"
        create_task_graph_template(graph_path, "test")
        with patch("zerg.commands.design.console"):
            validate_task_graph(graph_path)

    @pytest.mark.parametrize(
        "content,description",
        [
            ("{ invalid json }", "invalid JSON"),
            ('{"feature": "test"}', "missing tasks field"),
            (json.dumps({"tasks": [{"id": "T-001"}]}), "missing task fields"),
        ],
    )
    def test_fails_on_invalid_graph(self, tmp_path: Path, content: str, description: str) -> None:
        """Test that invalid task graphs fail validation."""
        graph_path = tmp_path / "task-graph.json"
        graph_path.write_text(content)
        with patch("zerg.commands.design.console"):
            with pytest.raises(SystemExit) as exc_info:
                validate_task_graph(graph_path)
            assert exc_info.value.code == 1

    def test_fails_on_file_create_conflict(self, tmp_path: Path) -> None:
        """Test that file creation conflicts fail validation."""
        graph_path = tmp_path / "task-graph.json"
        data = {
            "tasks": [
                {
                    "id": "T-001",
                    "title": "Task 1",
                    "level": 1,
                    "dependencies": [],
                    "files": {"create": ["src/file.py"], "modify": [], "read": []},
                },
                {
                    "id": "T-002",
                    "title": "Task 2",
                    "level": 1,
                    "dependencies": [],
                    "files": {"create": ["src/file.py"], "modify": [], "read": []},
                },
            ]
        }
        graph_path.write_text(json.dumps(data))
        with patch("zerg.commands.design.console"):
            with pytest.raises(SystemExit) as exc_info:
                validate_task_graph(graph_path)
            assert exc_info.value.code == 1


class TestDesignCommand:
    """Tests for the design CLI command."""

    def test_design_help(self) -> None:
        """Test design --help shows usage information."""
        runner = CliRunner()
        result = runner.invoke(cli, ["design", "--help"])
        assert result.exit_code == 0
        assert "Usage:" in result.output
        assert "--validate-only" in result.output

    def test_design_no_feature_no_current(self, tmp_path: Path, monkeypatch) -> None:
        """Test design fails when no feature specified and no current feature."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".gsd").mkdir()
        runner = CliRunner()
        result = runner.invoke(cli, ["design"])
        assert result.exit_code == 1
        assert "No active feature" in result.output

    def test_design_requirements_approved(self, tmp_path: Path, monkeypatch) -> None:
        """Test design proceeds when requirements are approved."""
        monkeypatch.chdir(tmp_path)
        spec_dir = tmp_path / ".gsd" / "specs" / "test"
        spec_dir.mkdir(parents=True)
        (spec_dir / "requirements.md").write_text("# Requirements\n- **Status**: APPROVED")
        (tmp_path / ".gsd" / ".current-feature").write_text("test")
        runner = CliRunner()
        result = runner.invoke(cli, ["design"])
        assert result.exit_code == 0
        assert "Design artifacts created" in result.output
        assert (spec_dir / "design.md").exists()
        assert (spec_dir / "task-graph.json").exists()

    def test_design_validate_only_success(self, tmp_path: Path, monkeypatch) -> None:
        """Test design --validate-only with valid task graph."""
        monkeypatch.chdir(tmp_path)
        spec_dir = tmp_path / ".gsd" / "specs" / "test"
        spec_dir.mkdir(parents=True)
        (spec_dir / "requirements.md").write_text("# Req\n- **Status**: APPROVED")
        (tmp_path / ".gsd" / ".current-feature").write_text("test")
        create_task_graph_template(spec_dir / "task-graph.json", "test")
        runner = CliRunner()
        result = runner.invoke(cli, ["design", "--validate-only"])
        assert result.exit_code == 0
        assert "valid" in result.output.lower()

    def test_design_keyboard_interrupt(self, tmp_path: Path, monkeypatch) -> None:
        """Test design handles KeyboardInterrupt gracefully."""
        monkeypatch.chdir(tmp_path)
        with patch("zerg.commands.design.get_current_feature", side_effect=KeyboardInterrupt()):
            runner = CliRunner()
            result = runner.invoke(cli, ["design"])
            assert result.exit_code == 130

    def test_design_general_exception(self, tmp_path: Path, monkeypatch) -> None:
        """Test design handles general exceptions."""
        monkeypatch.chdir(tmp_path)
        spec_dir = tmp_path / ".gsd" / "specs" / "test"
        spec_dir.mkdir(parents=True)
        (spec_dir / "requirements.md").write_text("# Req\n- **Status**: APPROVED")
        (tmp_path / ".gsd" / ".current-feature").write_text("test")
        with patch("zerg.commands.design.create_design_template", side_effect=OSError("Disk full")):
            runner = CliRunner()
            result = runner.invoke(cli, ["design"])
            assert result.exit_code == 1
            assert "Error" in result.output


class TestDesignBacklog:
    """Tests for backlog generation in the design command."""

    def test_design_auto_generates_backlog(self, tmp_path: Path, monkeypatch) -> None:
        """Test that running a full design flow creates the backlog file."""
        monkeypatch.chdir(tmp_path)
        spec_dir = tmp_path / ".gsd" / "specs" / "test"
        spec_dir.mkdir(parents=True)
        (spec_dir / "requirements.md").write_text("# Requirements\n- **Status**: APPROVED")
        (tmp_path / ".gsd" / ".current-feature").write_text("test")
        runner = CliRunner()
        result = runner.invoke(cli, ["design", "--feature", "test"])
        assert result.exit_code == 0
        backlog_path = tmp_path / "tasks" / "TEST-BACKLOG.md"
        assert backlog_path.exists()

    def test_update_backlog_no_graph_fails(self, tmp_path: Path, monkeypatch) -> None:
        """Test that --update-backlog fails when no task graph exists."""
        monkeypatch.chdir(tmp_path)
        spec_dir = tmp_path / ".gsd" / "specs" / "test"
        spec_dir.mkdir(parents=True)
        (spec_dir / "requirements.md").write_text("# Requirements\n- **Status**: APPROVED")
        (tmp_path / ".gsd" / ".current-feature").write_text("test")
        runner = CliRunner()
        result = runner.invoke(cli, ["design", "--update-backlog"])
        assert result.exit_code == 1
        assert "No task graph found" in result.output


class TestDesignManifest:
    """Tests for design-tasks-manifest.json creation."""

    def test_design_creates_manifest_with_structure(self, tmp_path: Path, monkeypatch) -> None:
        """Test that full design generation writes valid design-tasks-manifest.json."""
        monkeypatch.chdir(tmp_path)
        spec_dir = tmp_path / ".gsd" / "specs" / "test"
        spec_dir.mkdir(parents=True)
        (spec_dir / "requirements.md").write_text("# Requirements\n- **Status**: APPROVED")
        (tmp_path / ".gsd" / ".current-feature").write_text("test")
        runner = CliRunner()
        result = runner.invoke(cli, ["design", "--feature", "test"])
        assert result.exit_code == 0
        manifest_path = spec_dir / "design-tasks-manifest.json"
        assert manifest_path.exists()
        with open(manifest_path) as f:
            manifest = json.load(f)
        assert manifest["feature"] == "test"
        assert "tasks" in manifest
        assert len(manifest["tasks"]) > 0
        for task in manifest["tasks"]:
            assert "subject" in task
            assert "description" in task
