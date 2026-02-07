"""Unit tests for zerg/commands/analyze.py - thinned per TSR2-L3-002."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from zerg.cli import cli
from zerg.command_executor import CommandValidationError
from zerg.commands.analyze import (
    AnalysisResult,
    AnalyzeCommand,
    AnalyzeConfig,
    BaseChecker,
    CheckType,
    ComplexityChecker,
    CoverageChecker,
    LintChecker,
    SecurityChecker,
    _collect_files,
    _parse_thresholds,
)


class TestCheckType:
    """Tests for CheckType enum."""

    def test_all_check_types_have_values(self) -> None:
        """Test that all check types have string values."""
        expected = {
            "lint",
            "complexity",
            "coverage",
            "security",
            "performance",
            "dead-code",
            "wiring",
            "cross-file",
            "conventions",
            "import-chain",
            "context-engineering",
        }
        actual = {ct.value for ct in CheckType}
        assert actual == expected


class TestAnalyzeConfig:
    """Tests for AnalyzeConfig dataclass."""

    def test_default_values(self) -> None:
        """Test AnalyzeConfig default values."""
        config = AnalyzeConfig()
        assert config.complexity_threshold == 10
        assert config.coverage_threshold == 70
        assert config.lint_command == "ruff check"
        assert config.security_command == "bandit"

    def test_custom_values(self) -> None:
        """Test AnalyzeConfig with custom values."""
        config = AnalyzeConfig(complexity_threshold=15, coverage_threshold=80)
        assert config.complexity_threshold == 15
        assert config.coverage_threshold == 80


class TestAnalysisResult:
    """Tests for AnalysisResult dataclass."""

    def test_successful_result(self) -> None:
        """Test successful AnalysisResult."""
        result = AnalysisResult(check_type=CheckType.LINT, passed=True, issues=[], score=100.0)
        assert result.passed is True
        assert result.score == 100.0

    def test_summary_passed(self) -> None:
        """Test summary method for passed result."""
        result = AnalysisResult(check_type=CheckType.LINT, passed=True, score=95.0)
        summary = result.summary()
        assert "PASSED" in summary

    def test_summary_failed(self) -> None:
        """Test summary method for failed result."""
        result = AnalysisResult(check_type=CheckType.COMPLEXITY, passed=False, score=45.5)
        summary = result.summary()
        assert "FAILED" in summary


class TestBaseChecker:
    """Tests for BaseChecker base class."""

    def test_cannot_instantiate_abstract_class(self) -> None:
        """Test that BaseChecker cannot be instantiated directly (abstract)."""
        with pytest.raises(TypeError, match="abstract"):
            BaseChecker()


class TestLintChecker:
    """Tests for LintChecker class."""

    def test_init_default_command(self) -> None:
        """Test LintChecker with default command."""
        checker = LintChecker()
        assert checker.command == "ruff check"

    def test_check_empty_files(self) -> None:
        """Test check with empty file list."""
        checker = LintChecker()
        result = checker.check([])
        assert result.passed is True
        assert result.score == 100.0

    def test_check_success(self) -> None:
        """Test check with successful lint."""
        checker = LintChecker()
        mock_result = MagicMock()
        mock_result.success = True
        with patch.object(checker._executor, "execute", return_value=mock_result):
            with patch.object(checker._executor, "sanitize_paths", return_value=["file.py"]):
                result = checker.check(["file.py"])
        assert result.passed is True

    def test_check_failure_with_issues(self) -> None:
        """Test check with lint failures."""
        checker = LintChecker()
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.stdout = "file.py:1: E501 line too long\nfile.py:2: W503 whitespace"
        with patch.object(checker._executor, "execute", return_value=mock_result):
            with patch.object(checker._executor, "sanitize_paths", return_value=["file.py"]):
                result = checker.check(["file.py"])
        assert result.passed is False
        assert len(result.issues) == 2

    def test_check_command_validation_error(self) -> None:
        """Test check handles CommandValidationError."""
        checker = LintChecker()
        with patch.object(checker._executor, "execute", side_effect=CommandValidationError("Bad command")):
            with patch.object(checker._executor, "sanitize_paths", return_value=["file.py"]):
                result = checker.check(["file.py"])
        assert result.passed is False
        assert result.score == 0.0


class TestComplexityChecker:
    """Tests for ComplexityChecker class."""

    def test_check_returns_result(self) -> None:
        """Test check returns placeholder result."""
        checker = ComplexityChecker()
        result = checker.check(["file.py"])
        assert result.check_type == CheckType.COMPLEXITY
        assert result.passed is True


class TestCoverageChecker:
    """Tests for CoverageChecker class."""

    def test_check_returns_result(self) -> None:
        """Test check returns placeholder result."""
        checker = CoverageChecker()
        result = checker.check(["file.py"])
        assert result.check_type == CheckType.COVERAGE
        assert result.passed is True


class TestSecurityChecker:
    """Tests for SecurityChecker class."""

    def test_check_empty_files(self) -> None:
        """Test check with empty file list."""
        checker = SecurityChecker()
        result = checker.check([])
        assert result.passed is True
        assert result.score == 100.0

    def test_check_success(self) -> None:
        """Test check with successful security scan."""
        checker = SecurityChecker()
        mock_result = MagicMock()
        mock_result.success = True
        with patch.object(checker._executor, "execute", return_value=mock_result):
            with patch.object(checker._executor, "sanitize_paths", return_value=["file.py"]):
                result = checker.check(["file.py"])
        assert result.passed is True

    def test_check_failure_with_issues(self) -> None:
        """Test check with security issues found."""
        checker = SecurityChecker()
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.stdout = "Issue 1: SQL injection\nIssue 2: XSS"
        with patch.object(checker._executor, "execute", return_value=mock_result):
            with patch.object(checker._executor, "sanitize_paths", return_value=["file.py"]):
                result = checker.check(["file.py"])
        assert result.passed is False
        assert len(result.issues) == 2

    def test_check_command_validation_error(self) -> None:
        """Test check handles CommandValidationError as skip (tool not installed)."""
        checker = SecurityChecker()
        with patch.object(checker._executor, "execute", side_effect=CommandValidationError("Bad command")):
            with patch.object(checker._executor, "sanitize_paths", return_value=["file.py"]):
                result = checker.check(["file.py"])
        assert result.passed is True
        assert result.score == 0.0
        assert any("Security tool not installed" in i for i in result.issues)

    def test_check_exception_fails_closed(self) -> None:
        """Test check returns passed=False on unexpected Exception (fail-closed)."""
        checker = SecurityChecker()
        with patch.object(checker._executor, "execute", side_effect=RuntimeError("Unexpected")):
            with patch.object(checker._executor, "sanitize_paths", return_value=["file.py"]):
                result = checker.check(["file.py"])
        assert result.passed is False
        assert result.score == 0.0
        assert any("Security check error" in i for i in result.issues)


class TestAnalyzeCommandClass:
    """Tests for AnalyzeCommand class."""

    def test_init_default_config(self) -> None:
        """Test AnalyzeCommand with default config."""
        cmd = AnalyzeCommand()
        assert cmd.config.complexity_threshold == 10

    def test_supported_checks_returns_list(self) -> None:
        """Test supported_checks returns all check types as a list."""
        cmd = AnalyzeCommand()
        checks = cmd.supported_checks()
        assert isinstance(checks, list)
        assert "lint" in checks
        assert "security" in checks

    def test_run_single_check(self) -> None:
        """Test running a single check."""
        cmd = AnalyzeCommand()
        results = cmd.run(["lint"], [])
        assert len(results) == 1
        assert results[0].check_type == CheckType.LINT

    def test_run_unknown_check_ignored(self) -> None:
        """Test that unknown check names are ignored."""
        cmd = AnalyzeCommand()
        results = cmd.run(["unknown_check"], [])
        assert len(results) == 0

    def test_overall_passed_all_pass(self) -> None:
        """Test overall_passed when all checks pass."""
        cmd = AnalyzeCommand()
        results = [
            AnalysisResult(CheckType.LINT, True, [], 100.0),
            AnalysisResult(CheckType.SECURITY, True, [], 100.0),
        ]
        assert cmd.overall_passed(results) is True

    def test_overall_passed_one_fails(self) -> None:
        """Test overall_passed when one check fails."""
        cmd = AnalyzeCommand()
        results = [
            AnalysisResult(CheckType.LINT, True, [], 100.0),
            AnalysisResult(CheckType.SECURITY, False, ["Issue"], 50.0),
        ]
        assert cmd.overall_passed(results) is False


class TestFormatResults:
    """Tests for result formatting methods."""

    def test_format_text(self) -> None:
        """Test text format output."""
        cmd = AnalyzeCommand()
        results = [
            AnalysisResult(CheckType.LINT, True, [], 100.0),
            AnalysisResult(CheckType.SECURITY, False, ["SQL injection"], 80.0),
        ]
        output = cmd.format_results(results, "text")
        assert "Analysis Results" in output
        assert "FAILED" in output

    def test_format_json(self) -> None:
        """Test JSON format output."""
        cmd = AnalyzeCommand()
        results = [AnalysisResult(CheckType.LINT, True, [], 100.0)]
        output = cmd.format_results(results, "json")
        data = json.loads(output)
        assert data["overall_passed"] is True

    def test_format_sarif(self) -> None:
        """Test SARIF format output."""
        cmd = AnalyzeCommand()
        results = [AnalysisResult(CheckType.SECURITY, False, ["SQL injection", "XSS"], 70.0)]
        output = cmd.format_results(results, "sarif")
        data = json.loads(output)
        assert data["version"] == "2.1.0"
        assert len(data["runs"][0]["results"]) == 2


class TestParseThresholds:
    """Tests for _parse_thresholds function."""

    def test_parse_single_threshold(self) -> None:
        """Test parsing single threshold."""
        result = _parse_thresholds(("complexity=15",))
        assert result == {"complexity": 15}

    def test_parse_empty_tuple(self) -> None:
        """Test parsing empty tuple."""
        result = _parse_thresholds(())
        assert result == {}

    def test_parse_invalid_value(self) -> None:
        """Test parsing with non-integer value."""
        result = _parse_thresholds(("complexity=high",))
        assert result == {}


class TestCollectFiles:
    """Tests for _collect_files function."""

    def test_collect_from_file(self, tmp_path: Path) -> None:
        """Test collecting when path is a file."""
        test_file = tmp_path / "test.py"
        test_file.write_text("# test")
        files = _collect_files(str(test_file))
        assert files == [str(test_file)]

    def test_collect_from_directory(self, tmp_path: Path) -> None:
        """Test collecting Python files from directory."""
        (tmp_path / "file1.py").write_text("# test")
        (tmp_path / "file2.txt").write_text("not python")
        files = _collect_files(str(tmp_path))
        assert any("file1.py" in f for f in files)
        assert not any("file2.txt" in f for f in files)

    def test_collect_nonexistent_path(self) -> None:
        """Test collecting from nonexistent path."""
        files = _collect_files("/nonexistent/path")
        assert files == []


class TestAnalyzeCLI:
    """Integration tests for the analyze CLI command."""

    def test_analyze_help(self) -> None:
        """Test analyze --help shows usage information."""
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", "--help"])
        assert result.exit_code == 0
        assert "--check" in result.output

    def test_analyze_failure_exit_code(self, tmp_path: Path, monkeypatch) -> None:
        """Test analyze returns exit code 1 on failure."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "test.py").write_text("# test")
        with patch("zerg.commands.analyze.AnalyzeCommand") as mock_cmd_class:
            mock_cmd = MagicMock()
            mock_cmd.run.return_value = [AnalysisResult(CheckType.SECURITY, False, ["Issue"], 50.0)]
            mock_cmd.overall_passed.return_value = False
            mock_cmd_class.return_value = mock_cmd
            runner = CliRunner()
            result = runner.invoke(cli, ["analyze"])
            assert result.exit_code == 1

    def test_keyboard_interrupt(self, tmp_path: Path, monkeypatch) -> None:
        """Test analyze handles KeyboardInterrupt gracefully."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "test.py").write_text("# test")
        with patch("zerg.commands.analyze.AnalyzeCommand", side_effect=KeyboardInterrupt()):
            runner = CliRunner()
            result = runner.invoke(cli, ["analyze"])
            assert result.exit_code == 130

    def test_general_exception(self, tmp_path: Path, monkeypatch) -> None:
        """Test analyze handles general exceptions."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "test.py").write_text("# test")
        with patch("zerg.commands.analyze.AnalyzeCommand", side_effect=RuntimeError("Unexpected error")):
            runner = CliRunner()
            result = runner.invoke(cli, ["analyze"])
            assert result.exit_code == 1
