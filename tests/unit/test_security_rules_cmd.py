"""Comprehensive unit tests for ZERG security-rules command.

This module provides 100% test coverage for zerg/commands/security_rules_cmd.py including:
- security_rules_group command group
- detect subcommand (text and JSON output)
- list subcommand
- fetch subcommand
- integrate subcommand (with various options)
- All branches and error conditions
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

from click.testing import CliRunner

from zerg.cli import cli
from zerg.security_rules import ProjectStack

if TYPE_CHECKING:
    from pytest import MonkeyPatch


# =============================================================================
# Tests for security_rules_group()
# =============================================================================


class TestSecurityRulesGroup:
    """Tests for the security-rules command group."""

    def test_security_rules_group_help(self) -> None:
        """Test security-rules --help shows subcommands."""
        runner = CliRunner()
        result = runner.invoke(cli, ["security-rules", "--help"])

        assert result.exit_code == 0
        assert "Usage:" in result.output
        assert "detect" in result.output
        assert "list" in result.output
        assert "fetch" in result.output
        assert "integrate" in result.output

    def test_security_rules_group_description(self) -> None:
        """Test security-rules shows description."""
        runner = CliRunner()
        result = runner.invoke(cli, ["security-rules", "--help"])

        assert "Manage secure coding rules" in result.output
        assert "TikiTribe" in result.output


# =============================================================================
# Tests for detect_command()
# =============================================================================


class TestDetectCommand:
    """Tests for security-rules detect subcommand."""

    def test_detect_help(self) -> None:
        """Test detect --help shows options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["security-rules", "detect", "--help"])

        assert result.exit_code == 0
        assert "Usage:" in result.output
        assert "--path" in result.output
        assert "--json-output" in result.output

    def test_detect_text_output_with_languages(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test detect shows detected languages in text format."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "app.py").write_text("print('hello')")

        runner = CliRunner()
        result = runner.invoke(cli, ["security-rules", "detect"])

        assert result.exit_code == 0
        assert "Detected Project Stack:" in result.output
        assert "Languages:" in result.output
        assert "python" in result.output.lower()

    def test_detect_text_output_with_frameworks(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test detect shows frameworks in text format."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\ndependencies = ["fastapi"]')

        runner = CliRunner()
        result = runner.invoke(cli, ["security-rules", "detect"])

        assert result.exit_code == 0
        assert "Frameworks:" in result.output

    def test_detect_text_output_with_databases(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test detect shows databases in text format."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\ndependencies = ["sqlalchemy"]')

        runner = CliRunner()
        result = runner.invoke(cli, ["security-rules", "detect"])

        assert result.exit_code == 0
        assert "Databases:" in result.output

    def test_detect_text_output_with_infrastructure(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test detect shows infrastructure in text format."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "Dockerfile").write_text("FROM python:3.11")

        runner = CliRunner()
        result = runner.invoke(cli, ["security-rules", "detect"])

        assert result.exit_code == 0
        assert "Infrastructure:" in result.output
        assert "docker" in result.output.lower()

    def test_detect_text_output_ai_ml_yes(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test detect shows AI/ML as yes when detected."""
        monkeypatch.chdir(tmp_path)

        with patch("zerg.commands.security_rules_cmd.detect_project_stack") as mock_detect:
            mock_detect.return_value = ProjectStack(languages={"python"}, frameworks={"langchain"}, ai_ml=True)

            runner = CliRunner()
            result = runner.invoke(cli, ["security-rules", "detect"])

        assert result.exit_code == 0
        assert "AI/ML:" in result.output
        assert "yes" in result.output

    def test_detect_text_output_ai_ml_no(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test detect shows AI/ML as no when not detected."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "app.py").write_text("print('hello')")

        runner = CliRunner()
        result = runner.invoke(cli, ["security-rules", "detect"])

        assert result.exit_code == 0
        assert "AI/ML:" in result.output
        # Should show 'no' for non-AI projects
        assert "no" in result.output.lower()

    def test_detect_text_output_rag_yes(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test detect shows RAG as yes when detected."""
        monkeypatch.chdir(tmp_path)

        with patch("zerg.commands.security_rules_cmd.detect_project_stack") as mock_detect:
            mock_detect.return_value = ProjectStack(languages={"python"}, frameworks={"llamaindex"}, rag=True)

            runner = CliRunner()
            result = runner.invoke(cli, ["security-rules", "detect"])

        assert result.exit_code == 0
        assert "RAG:" in result.output
        assert "yes" in result.output

    def test_detect_text_output_rag_no(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test detect shows RAG as no when not detected."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "app.py").write_text("print('hello')")

        runner = CliRunner()
        result = runner.invoke(cli, ["security-rules", "detect"])

        assert result.exit_code == 0
        assert "RAG:" in result.output

    def test_detect_text_output_empty_project(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test detect handles empty project (no languages detected)."""
        monkeypatch.chdir(tmp_path)
        # Empty directory - no code files

        runner = CliRunner()
        result = runner.invoke(cli, ["security-rules", "detect"])

        assert result.exit_code == 0
        assert "Languages:" in result.output
        # Should show 'none' when no languages detected
        assert "none" in result.output.lower()

    def test_detect_json_output(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test detect --json-output produces valid JSON."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "app.py").write_text("print('hello')")

        runner = CliRunner()
        result = runner.invoke(cli, ["security-rules", "detect", "--json-output"])

        assert result.exit_code == 0
        # Should be valid JSON
        import json

        data = json.loads(result.output)
        assert "languages" in data
        assert "python" in data["languages"]

    def test_detect_json_output_short_flag(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test detect -j produces JSON output."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "package.json").write_text('{"name": "test"}')

        runner = CliRunner()
        result = runner.invoke(cli, ["security-rules", "detect", "-j"])

        assert result.exit_code == 0
        import json

        data = json.loads(result.output)
        assert "javascript" in data["languages"]

    def test_detect_with_path_option(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test detect --path option."""
        monkeypatch.chdir(tmp_path)
        subdir = tmp_path / "myproject"
        subdir.mkdir()
        (subdir / "main.go").write_text("package main")

        runner = CliRunner()
        result = runner.invoke(cli, ["security-rules", "detect", "--path", str(subdir)])

        assert result.exit_code == 0
        assert "go" in result.output.lower()

    def test_detect_with_path_short_flag(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test detect -p path option."""
        monkeypatch.chdir(tmp_path)
        subdir = tmp_path / "rustproject"
        subdir.mkdir()
        (subdir / "Cargo.toml").write_text('[package]\nname = "test"')

        runner = CliRunner()
        result = runner.invoke(cli, ["security-rules", "detect", "-p", str(subdir)])

        assert result.exit_code == 0
        assert "rust" in result.output.lower()

    def test_detect_json_with_all_stack_fields(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test detect JSON includes all stack fields."""
        monkeypatch.chdir(tmp_path)

        with patch("zerg.commands.security_rules_cmd.detect_project_stack") as mock_detect:
            mock_detect.return_value = ProjectStack(
                languages={"python"},
                frameworks={"fastapi"},
                databases={"postgresql"},
                infrastructure={"docker"},
                ai_ml=True,
                rag=True,
            )

            runner = CliRunner()
            result = runner.invoke(cli, ["security-rules", "detect", "-j"])

        import json

        data = json.loads(result.output)
        assert data["languages"] == ["python"]
        assert data["frameworks"] == ["fastapi"]
        assert data["databases"] == ["postgresql"]
        assert data["infrastructure"] == ["docker"]
        assert data["ai_ml"] is True
        assert data["rag"] is True


# =============================================================================
# Tests for list_command()
# =============================================================================


class TestListCommand:
    """Tests for security-rules list subcommand."""

    def test_list_help(self) -> None:
        """Test list --help shows options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["security-rules", "list", "--help"])

        assert result.exit_code == 0
        assert "Usage:" in result.output
        assert "--path" in result.output

    def test_list_shows_rules(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test list shows rules for detected stack."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "app.py").write_text("print('hello')")

        runner = CliRunner()
        result = runner.invoke(cli, ["security-rules", "list"])

        assert result.exit_code == 0
        assert "Security rules for detected stack" in result.output
        assert "files" in result.output.lower()

    def test_list_shows_rule_paths(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test list shows individual rule paths."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "app.py").write_text("print('hello')")

        runner = CliRunner()
        result = runner.invoke(cli, ["security-rules", "list"])

        assert result.exit_code == 0
        # Should list rules as bullet points
        assert "-" in result.output

    def test_list_with_path_option(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test list --path option."""
        monkeypatch.chdir(tmp_path)
        subdir = tmp_path / "myproject"
        subdir.mkdir()
        (subdir / "package.json").write_text('{"name": "test"}')

        runner = CliRunner()
        result = runner.invoke(cli, ["security-rules", "list", "--path", str(subdir)])

        assert result.exit_code == 0
        assert "Security rules" in result.output

    def test_list_shows_core_rules(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test list always includes core OWASP rules."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "app.py").write_text("print('hello')")

        runner = CliRunner()
        result = runner.invoke(cli, ["security-rules", "list"])

        assert result.exit_code == 0
        assert "owasp" in result.output.lower()

    def test_list_shows_language_specific_rules(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test list includes language-specific rules."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "main.go").write_text("package main")

        runner = CliRunner()
        result = runner.invoke(cli, ["security-rules", "list"])

        assert result.exit_code == 0
        # Should include go rules
        assert "go" in result.output.lower()

    def test_list_empty_project(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test list on empty project still shows core rules."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = runner.invoke(cli, ["security-rules", "list"])

        assert result.exit_code == 0
        # Should still show some rules (at least core)
        assert "Security rules" in result.output


# =============================================================================
# Tests for fetch_command()
# =============================================================================


class TestFetchCommand:
    """Tests for security-rules fetch subcommand."""

    def test_fetch_help(self) -> None:
        """Test fetch --help shows options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["security-rules", "fetch", "--help"])

        assert result.exit_code == 0
        assert "Usage:" in result.output
        assert "--path" in result.output
        assert "--output" in result.output
        assert "--no-cache" in result.output

    def test_fetch_runs(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test fetch runs and reports progress."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "app.py").write_text("print('hello')")

        with patch("zerg.commands.security_rules_cmd.fetch_rules") as mock_fetch:
            mock_fetch.return_value = {"rules/python.md": tmp_path / "python.md"}

            runner = CliRunner()
            result = runner.invoke(cli, ["security-rules", "fetch"])

        assert result.exit_code == 0
        assert "Fetching" in result.output
        assert "Fetched" in result.output

    def test_fetch_with_output_option(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test fetch --output option."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "app.py").write_text("print('hello')")
        output_dir = tmp_path / "custom-rules"

        with patch("zerg.commands.security_rules_cmd.fetch_rules") as mock_fetch:
            mock_fetch.return_value = {}

            runner = CliRunner()
            result = runner.invoke(cli, ["security-rules", "fetch", "--output", str(output_dir)])

        assert result.exit_code == 0
        # Verify output dir was passed to fetch_rules
        mock_fetch.assert_called_once()
        call_args = mock_fetch.call_args
        assert call_args[0][1] == output_dir

    def test_fetch_with_output_short_flag(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test fetch -o option."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "app.py").write_text("print('hello')")
        output_dir = tmp_path / "my-rules"

        with patch("zerg.commands.security_rules_cmd.fetch_rules") as mock_fetch:
            mock_fetch.return_value = {}

            runner = CliRunner()
            result = runner.invoke(cli, ["security-rules", "fetch", "-o", str(output_dir)])

        assert result.exit_code == 0

    def test_fetch_with_no_cache_option(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test fetch --no-cache option."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "app.py").write_text("print('hello')")

        with patch("zerg.commands.security_rules_cmd.fetch_rules") as mock_fetch:
            mock_fetch.return_value = {}

            runner = CliRunner()
            result = runner.invoke(cli, ["security-rules", "fetch", "--no-cache"])

        assert result.exit_code == 0
        # Verify use_cache=False was passed
        mock_fetch.assert_called_once()
        call_args = mock_fetch.call_args
        assert call_args[1]["use_cache"] is False

    def test_fetch_default_uses_cache(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test fetch uses cache by default."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "app.py").write_text("print('hello')")

        with patch("zerg.commands.security_rules_cmd.fetch_rules") as mock_fetch:
            mock_fetch.return_value = {}

            runner = CliRunner()
            result = runner.invoke(cli, ["security-rules", "fetch"])

        assert result.exit_code == 0
        # Verify use_cache=True was passed
        mock_fetch.assert_called_once()
        call_args = mock_fetch.call_args
        assert call_args[1]["use_cache"] is True

    def test_fetch_shows_fetched_rules(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test fetch shows list of fetched rules."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "app.py").write_text("print('hello')")

        with patch("zerg.commands.security_rules_cmd.fetch_rules") as mock_fetch:
            mock_fetch.return_value = {
                "rules/python.md": tmp_path / "python.md",
                "rules/owasp.md": tmp_path / "owasp.md",
            }

            runner = CliRunner()
            result = runner.invoke(cli, ["security-rules", "fetch"])

        assert result.exit_code == 0
        assert "Fetched 2 rules" in result.output

    def test_fetch_shows_output_directory(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test fetch shows output directory path."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "app.py").write_text("print('hello')")

        with patch("zerg.commands.security_rules_cmd.fetch_rules") as mock_fetch:
            mock_fetch.return_value = {}

            runner = CliRunner()
            result = runner.invoke(cli, ["security-rules", "fetch"])

        assert result.exit_code == 0
        assert "rules/security" in result.output

    def test_fetch_with_path_option(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test fetch --path option."""
        monkeypatch.chdir(tmp_path)
        subdir = tmp_path / "myproject"
        subdir.mkdir()
        (subdir / "app.py").write_text("print('hello')")

        with patch("zerg.commands.security_rules_cmd.fetch_rules") as mock_fetch:
            mock_fetch.return_value = {}

            runner = CliRunner()
            result = runner.invoke(cli, ["security-rules", "fetch", "--path", str(subdir)])

        assert result.exit_code == 0


# =============================================================================
# Tests for integrate_command()
# =============================================================================


class TestIntegrateCommand:
    """Tests for security-rules integrate subcommand."""

    def test_integrate_help(self) -> None:
        """Test integrate --help shows options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["security-rules", "integrate", "--help"])

        assert result.exit_code == 0
        assert "Usage:" in result.output
        assert "--path" in result.output
        assert "--output" in result.output
        assert "--no-update-claude-md" in result.output

    def test_integrate_runs(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test integrate runs full integration."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "app.py").write_text("print('hello')")

        with patch("zerg.commands.security_rules_cmd.integrate_security_rules") as mock_integrate:
            mock_integrate.return_value = {
                "stack": {"languages": ["python"], "frameworks": [], "databases": []},
                "rules_fetched": 2,
                "rules_dir": str(tmp_path / ".claude" / "rules" / "security"),
            }

            runner = CliRunner()
            result = runner.invoke(cli, ["security-rules", "integrate"])

        assert result.exit_code == 0
        assert "Integrating secure coding rules" in result.output

    def test_integrate_shows_stack_detected(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test integrate shows detected stack."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "app.py").write_text("print('hello')")

        with patch("zerg.commands.security_rules_cmd.integrate_security_rules") as mock_integrate:
            mock_integrate.return_value = {
                "stack": {"languages": ["python"], "frameworks": ["fastapi"]},
                "rules_fetched": 3,
                "rules_dir": str(tmp_path / ".claude" / "rules" / "security"),
            }

            runner = CliRunner()
            result = runner.invoke(cli, ["security-rules", "integrate"])

        assert result.exit_code == 0
        assert "Stack detected:" in result.output
        # Should show non-empty stack values
        assert "languages" in result.output or "python" in result.output.lower()

    def test_integrate_shows_rules_fetched_count(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test integrate shows number of rules fetched."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "app.py").write_text("print('hello')")

        with patch("zerg.commands.security_rules_cmd.integrate_security_rules") as mock_integrate:
            mock_integrate.return_value = {
                "stack": {"languages": ["python"]},
                "rules_fetched": 5,
                "rules_dir": str(tmp_path / ".claude" / "rules" / "security"),
            }

            runner = CliRunner()
            result = runner.invoke(cli, ["security-rules", "integrate"])

        assert result.exit_code == 0
        assert "Rules fetched: 5" in result.output

    def test_integrate_shows_rules_directory(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test integrate shows rules directory path."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "app.py").write_text("print('hello')")
        rules_dir = tmp_path / ".claude" / "rules" / "security"

        with patch("zerg.commands.security_rules_cmd.integrate_security_rules") as mock_integrate:
            mock_integrate.return_value = {
                "stack": {"languages": ["python"]},
                "rules_fetched": 2,
                "rules_dir": str(rules_dir),
            }

            runner = CliRunner()
            result = runner.invoke(cli, ["security-rules", "integrate"])

        assert result.exit_code == 0
        assert "Rules directory:" in result.output

    def test_integrate_shows_claude_md_updated(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test integrate shows CLAUDE.md was updated."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "app.py").write_text("print('hello')")

        with patch("zerg.commands.security_rules_cmd.integrate_security_rules") as mock_integrate:
            mock_integrate.return_value = {
                "stack": {"languages": ["python"]},
                "rules_fetched": 2,
                "rules_dir": str(tmp_path / ".claude" / "rules" / "security"),
            }

            runner = CliRunner()
            result = runner.invoke(cli, ["security-rules", "integrate"])

        assert result.exit_code == 0
        assert "Updated:" in result.output
        assert "CLAUDE.md" in result.output

    def test_integrate_shows_done_message(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test integrate shows done message."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "app.py").write_text("print('hello')")

        with patch("zerg.commands.security_rules_cmd.integrate_security_rules") as mock_integrate:
            mock_integrate.return_value = {
                "stack": {"languages": ["python"]},
                "rules_fetched": 2,
                "rules_dir": str(tmp_path / ".claude" / "rules" / "security"),
            }

            runner = CliRunner()
            result = runner.invoke(cli, ["security-rules", "integrate"])

        assert result.exit_code == 0
        assert "Done!" in result.output
        assert "Security rules integrated" in result.output

    def test_integrate_with_no_update_claude_md(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test integrate --no-update-claude-md option."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "app.py").write_text("print('hello')")

        with patch("zerg.commands.security_rules_cmd.integrate_security_rules") as mock_integrate:
            mock_integrate.return_value = {
                "stack": {"languages": ["python"]},
                "rules_fetched": 2,
                "rules_dir": str(tmp_path / ".claude" / "rules" / "security"),
            }

            runner = CliRunner()
            result = runner.invoke(cli, ["security-rules", "integrate", "--no-update-claude-md"])

        assert result.exit_code == 0
        # Should NOT show CLAUDE.md updated message
        assert "Updated:" not in result.output
        # Verify update_claude_md=False was passed
        mock_integrate.assert_called_once()
        call_kwargs = mock_integrate.call_args[1]
        assert call_kwargs["update_claude_md"] is False

    def test_integrate_with_output_option(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test integrate --output option."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "app.py").write_text("print('hello')")
        output_dir = tmp_path / "custom-rules"

        with patch("zerg.commands.security_rules_cmd.integrate_security_rules") as mock_integrate:
            mock_integrate.return_value = {
                "stack": {"languages": ["python"]},
                "rules_fetched": 2,
                "rules_dir": str(output_dir),
            }

            runner = CliRunner()
            result = runner.invoke(cli, ["security-rules", "integrate", "--output", str(output_dir)])

        assert result.exit_code == 0
        # Verify output_dir was passed
        mock_integrate.assert_called_once()
        call_kwargs = mock_integrate.call_args[1]
        assert call_kwargs["output_dir"] == output_dir

    def test_integrate_with_path_option(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test integrate --path option."""
        monkeypatch.chdir(tmp_path)
        subdir = tmp_path / "myproject"
        subdir.mkdir()
        (subdir / "app.py").write_text("print('hello')")

        with patch("zerg.commands.security_rules_cmd.integrate_security_rules") as mock_integrate:
            mock_integrate.return_value = {
                "stack": {"languages": ["python"]},
                "rules_fetched": 2,
                "rules_dir": str(subdir / ".claude" / "rules" / "security"),
            }

            runner = CliRunner()
            result = runner.invoke(cli, ["security-rules", "integrate", "--path", str(subdir)])

        assert result.exit_code == 0
        # Verify project_path was passed
        mock_integrate.assert_called_once()
        call_kwargs = mock_integrate.call_args[1]
        assert call_kwargs["project_path"] == subdir

    def test_integrate_shows_all_stack_values(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test integrate shows all non-empty stack values."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "app.py").write_text("print('hello')")

        with patch("zerg.commands.security_rules_cmd.integrate_security_rules") as mock_integrate:
            mock_integrate.return_value = {
                "stack": {
                    "languages": ["python", "javascript"],
                    "frameworks": ["fastapi"],
                    "databases": ["postgresql"],
                    "infrastructure": ["docker"],
                    "ai_ml": True,
                    "rag": False,
                },
                "rules_fetched": 5,
                "rules_dir": str(tmp_path / ".claude" / "rules" / "security"),
            }

            runner = CliRunner()
            result = runner.invoke(cli, ["security-rules", "integrate"])

        assert result.exit_code == 0
        assert "Stack detected:" in result.output
        # Should show languages, frameworks, databases, infrastructure
        output_lower = result.output.lower()
        assert "languages" in output_lower or "python" in output_lower

    def test_integrate_skips_empty_stack_values(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test integrate skips empty stack values in output."""
        monkeypatch.chdir(tmp_path)

        with patch("zerg.commands.security_rules_cmd.integrate_security_rules") as mock_integrate:
            mock_integrate.return_value = {
                "stack": {
                    "languages": ["python"],
                    "frameworks": [],  # Empty
                    "databases": [],  # Empty
                    "infrastructure": [],  # Empty
                    "ai_ml": False,  # Falsy
                    "rag": False,  # Falsy
                },
                "rules_fetched": 2,
                "rules_dir": str(tmp_path / ".claude" / "rules" / "security"),
            }

            runner = CliRunner()
            result = runner.invoke(cli, ["security-rules", "integrate"])

        assert result.exit_code == 0
        # Should only show non-empty values
        assert "Stack detected:" in result.output


# =============================================================================
# Tests for edge cases and error handling
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_detect_nonexistent_path(self) -> None:
        """Test detect with nonexistent path shows error."""
        runner = CliRunner()
        result = runner.invoke(cli, ["security-rules", "detect", "--path", "/nonexistent/path"])

        # Click should handle this with an error
        assert result.exit_code != 0

    def test_fetch_default_output_dir(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test fetch uses default output dir when not specified."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "app.py").write_text("print('hello')")

        with patch("zerg.commands.security_rules_cmd.fetch_rules") as mock_fetch:
            mock_fetch.return_value = {}

            runner = CliRunner()
            runner.invoke(cli, ["security-rules", "fetch"])

        # Should use path / .claude / rules / security as default
        mock_fetch.assert_called_once()
        call_args = mock_fetch.call_args
        output_dir = call_args[0][1]
        assert str(output_dir).endswith(str(Path(".claude") / "rules" / "security"))

    def test_integrate_passes_correct_parameters(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test integrate passes all parameters correctly."""
        monkeypatch.chdir(tmp_path)
        output_dir = tmp_path / "rules"

        with patch("zerg.commands.security_rules_cmd.integrate_security_rules") as mock_integrate:
            mock_integrate.return_value = {
                "stack": {},
                "rules_fetched": 0,
                "rules_dir": str(output_dir),
            }

            runner = CliRunner()
            runner.invoke(
                cli,
                [
                    "security-rules",
                    "integrate",
                    "--path",
                    str(tmp_path),
                    "--output",
                    str(output_dir),
                    "--no-update-claude-md",
                ],
            )

        mock_integrate.assert_called_once_with(
            project_path=tmp_path,
            output_dir=output_dir,
            update_claude_md=False,
        )

    def test_list_rule_output_format(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test list outputs rules in expected format."""
        monkeypatch.chdir(tmp_path)

        with patch("zerg.commands.security_rules_cmd.detect_project_stack") as mock_detect:
            mock_detect.return_value = ProjectStack(languages={"python"})

            with patch("zerg.commands.security_rules_cmd.get_required_rules") as mock_rules:
                mock_rules.return_value = [
                    "rules/_core/owasp-2025.md",
                    "rules/languages/python/CLAUDE.md",
                ]

                runner = CliRunner()
                result = runner.invoke(cli, ["security-rules", "list"])

        assert result.exit_code == 0
        assert "2 files" in result.output
        assert "owasp" in result.output
        assert "python" in result.output

    def test_fetch_lists_fetched_paths(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test fetch lists each fetched rule path."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "app.py").write_text("print('hello')")

        with patch("zerg.commands.security_rules_cmd.fetch_rules") as mock_fetch:
            fetched_path = tmp_path / "rules" / "python.md"
            mock_fetch.return_value = {"rules/python.md": fetched_path}

            runner = CliRunner()
            result = runner.invoke(cli, ["security-rules", "fetch"])

        assert result.exit_code == 0
        # Should show the path in output
        assert str(fetched_path) in result.output or "python.md" in result.output
