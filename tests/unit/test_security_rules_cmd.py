"""Unit tests for ZERG security-rules command.

Thinned from 50 tests to cover unique code paths:
- security_rules_group (help)
- detect subcommand (text output, JSON output, empty project, with path)
- list subcommand (shows rules, empty project)
- fetch subcommand (runs, with no-cache, shows fetched)
- integrate subcommand (runs, no-update-claude-md, with output)
- Edge cases (nonexistent path, default output dir)
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


class TestSecurityRulesGroup:
    """Tests for the security-rules command group."""

    def test_security_rules_group_help(self) -> None:
        """Test security-rules --help shows subcommands."""
        runner = CliRunner()
        result = runner.invoke(cli, ["security-rules", "--help"])
        assert result.exit_code == 0
        assert "Usage:" in result.output
        for subcmd in ["detect", "list", "fetch", "integrate"]:
            assert subcmd in result.output


class TestDetectCommand:
    """Tests for security-rules detect subcommand."""

    def test_detect_text_output_with_languages(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test detect shows detected languages in text format."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "app.py").write_text("print('hello')")
        runner = CliRunner()
        result = runner.invoke(cli, ["security-rules", "detect"])
        assert result.exit_code == 0
        assert "Detected Project Stack:" in result.output
        assert "python" in result.output.lower()

    def test_detect_json_output(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test detect --json-output produces valid JSON."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "app.py").write_text("print('hello')")
        runner = CliRunner()
        result = runner.invoke(cli, ["security-rules", "detect", "--json-output"])
        assert result.exit_code == 0
        import json

        data = json.loads(result.output)
        assert "languages" in data
        assert "python" in data["languages"]

    def test_detect_empty_project(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test detect handles empty project (no languages detected)."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["security-rules", "detect"])
        assert result.exit_code == 0
        assert "none" in result.output.lower()

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
        assert data["ai_ml"] is True
        assert data["rag"] is True


class TestListCommand:
    """Tests for security-rules list subcommand."""

    def test_list_shows_rules(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test list shows rules for detected stack."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "app.py").write_text("print('hello')")
        runner = CliRunner()
        result = runner.invoke(cli, ["security-rules", "list"])
        assert result.exit_code == 0
        assert "Security rules for detected stack" in result.output
        assert "owasp" in result.output.lower()

    def test_list_empty_project(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test list on empty project still shows core rules."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["security-rules", "list"])
        assert result.exit_code == 0
        assert "Security rules" in result.output


class TestFetchCommand:
    """Tests for security-rules fetch subcommand."""

    def test_fetch_runs(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test fetch runs and reports progress."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "app.py").write_text("print('hello')")
        with patch("zerg.commands.security_rules_cmd.fetch_rules") as mock_fetch:
            mock_fetch.return_value = {"rules/python.md": tmp_path / "python.md"}
            runner = CliRunner()
            result = runner.invoke(cli, ["security-rules", "fetch"])
        assert result.exit_code == 0
        assert "Fetched" in result.output

    def test_fetch_with_no_cache(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test fetch --no-cache option."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "app.py").write_text("print('hello')")
        with patch("zerg.commands.security_rules_cmd.fetch_rules") as mock_fetch:
            mock_fetch.return_value = {}
            runner = CliRunner()
            result = runner.invoke(cli, ["security-rules", "fetch", "--no-cache"])
        assert result.exit_code == 0
        assert mock_fetch.call_args[1]["use_cache"] is False

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
        assert mock_fetch.call_args[0][1] == output_dir


class TestIntegrateCommand:
    """Tests for security-rules integrate subcommand."""

    def _mock_integrate_result(self, tmp_path: Path, **extra_stack):
        """Helper to create a mock integrate result."""
        stack = {"languages": ["python"], "frameworks": [], "databases": []}
        stack.update(extra_stack)
        return {
            "stack": stack,
            "rules_fetched": 2,
            "rules_dir": str(tmp_path / ".claude" / "rules" / "security"),
        }

    def test_integrate_runs(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test integrate runs full integration."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "app.py").write_text("print('hello')")
        with patch("zerg.commands.security_rules_cmd.integrate_security_rules") as mock_integrate:
            mock_integrate.return_value = self._mock_integrate_result(tmp_path)
            runner = CliRunner()
            result = runner.invoke(cli, ["security-rules", "integrate"])
        assert result.exit_code == 0
        assert "Integrating secure coding rules" in result.output
        assert "Done!" in result.output

    def test_integrate_no_update_claude_md(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test integrate --no-update-claude-md option."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "app.py").write_text("print('hello')")
        with patch("zerg.commands.security_rules_cmd.integrate_security_rules") as mock_integrate:
            mock_integrate.return_value = self._mock_integrate_result(tmp_path)
            runner = CliRunner()
            result = runner.invoke(cli, ["security-rules", "integrate", "--no-update-claude-md"])
        assert result.exit_code == 0
        assert "Updated:" not in result.output
        assert mock_integrate.call_args[1]["update_claude_md"] is False

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
        assert mock_integrate.call_args[1]["output_dir"] == output_dir


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_detect_nonexistent_path(self) -> None:
        """Test detect with nonexistent path shows error."""
        runner = CliRunner()
        result = runner.invoke(cli, ["security-rules", "detect", "--path", "/nonexistent/path"])
        assert result.exit_code != 0
