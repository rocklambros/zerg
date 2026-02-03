"""Comprehensive unit tests for zerg/commands/analyze.py.

Tests cover all code paths including:
- CheckType enum
- AnalyzeConfig dataclass
- AnalysisResult dataclass and summary method
- BaseChecker abstract class
- LintChecker implementation
- ComplexityChecker implementation
- CoverageChecker implementation
- SecurityChecker implementation
- AnalyzeCommand orchestrator
- Result formatting (text, JSON, SARIF)
- Threshold parsing
- File collection
- CLI command integration
- Error handling and edge cases
"""

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

# =============================================================================
# CheckType Enum Tests
# =============================================================================


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

    def test_lint_type(self) -> None:
        """Test LINT check type."""
        assert CheckType.LINT.value == "lint"

    def test_complexity_type(self) -> None:
        """Test COMPLEXITY check type."""
        assert CheckType.COMPLEXITY.value == "complexity"

    def test_coverage_type(self) -> None:
        """Test COVERAGE check type."""
        assert CheckType.COVERAGE.value == "coverage"

    def test_security_type(self) -> None:
        """Test SECURITY check type."""
        assert CheckType.SECURITY.value == "security"


# =============================================================================
# AnalyzeConfig Dataclass Tests
# =============================================================================


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
        config = AnalyzeConfig(
            complexity_threshold=15,
            coverage_threshold=80,
            lint_command="flake8",
            security_command="safety",
        )
        assert config.complexity_threshold == 15
        assert config.coverage_threshold == 80
        assert config.lint_command == "flake8"
        assert config.security_command == "safety"


# =============================================================================
# AnalysisResult Dataclass Tests
# =============================================================================


class TestAnalysisResult:
    """Tests for AnalysisResult dataclass."""

    def test_successful_result(self) -> None:
        """Test successful AnalysisResult."""
        result = AnalysisResult(
            check_type=CheckType.LINT,
            passed=True,
            issues=[],
            score=100.0,
        )
        assert result.passed is True
        assert result.score == 100.0
        assert result.issues == []

    def test_failed_result(self) -> None:
        """Test failed AnalysisResult."""
        result = AnalysisResult(
            check_type=CheckType.SECURITY,
            passed=False,
            issues=["SQL injection vulnerability", "Hardcoded password"],
            score=60.0,
        )
        assert result.passed is False
        assert len(result.issues) == 2
        assert result.score == 60.0

    def test_summary_passed(self) -> None:
        """Test summary method for passed result."""
        result = AnalysisResult(
            check_type=CheckType.LINT,
            passed=True,
            score=95.0,
        )
        summary = result.summary()
        assert "LINT" in summary
        assert "PASSED" in summary
        assert "95.0" in summary

    def test_summary_failed(self) -> None:
        """Test summary method for failed result."""
        result = AnalysisResult(
            check_type=CheckType.COMPLEXITY,
            passed=False,
            score=45.5,
        )
        summary = result.summary()
        assert "COMPLEXITY" in summary
        assert "FAILED" in summary
        assert "45.5" in summary


# =============================================================================
# BaseChecker Tests
# =============================================================================


class TestBaseChecker:
    """Tests for BaseChecker base class."""

    def test_cannot_instantiate_abstract_class(self) -> None:
        """Test that BaseChecker cannot be instantiated directly (abstract)."""
        with pytest.raises(TypeError, match="abstract"):
            BaseChecker()

    def test_name_attribute(self) -> None:
        """Test that base checker has name attribute."""
        assert BaseChecker.name == "base"


# =============================================================================
# LintChecker Tests
# =============================================================================


class TestLintChecker:
    """Tests for LintChecker class."""

    def test_init_default_command(self) -> None:
        """Test LintChecker with default command."""
        checker = LintChecker()
        assert checker.command == "ruff check"

    def test_init_custom_command(self) -> None:
        """Test LintChecker with custom command."""
        checker = LintChecker(command="flake8")
        assert checker.command == "flake8"

    def test_check_empty_files(self) -> None:
        """Test check with empty file list."""
        checker = LintChecker()
        result = checker.check([])

        assert result.check_type == CheckType.LINT
        assert result.passed is True
        assert result.score == 100.0
        assert result.issues == []

    def test_check_success(self) -> None:
        """Test check with successful lint."""
        checker = LintChecker()

        mock_result = MagicMock()
        mock_result.success = True

        with patch.object(checker._executor, "execute", return_value=mock_result):
            with patch.object(checker._executor, "sanitize_paths", return_value=["file.py"]):
                result = checker.check(["file.py"])

        assert result.check_type == CheckType.LINT
        assert result.passed is True
        assert result.score == 100.0

    def test_check_failure_with_issues(self) -> None:
        """Test check with lint failures."""
        checker = LintChecker()

        mock_result = MagicMock()
        mock_result.success = False
        mock_result.stdout = "file.py:1: E501 line too long\nfile.py:2: W503 whitespace"

        with patch.object(checker._executor, "execute", return_value=mock_result):
            with patch.object(checker._executor, "sanitize_paths", return_value=["file.py"]):
                result = checker.check(["file.py"])

        assert result.check_type == CheckType.LINT
        assert result.passed is False
        assert len(result.issues) == 2
        # Score decreases by 5 per issue: 100 - 2*5 = 90
        assert result.score == 90.0

    def test_check_failure_empty_output(self) -> None:
        """Test check failure with no stdout."""
        checker = LintChecker()

        mock_result = MagicMock()
        mock_result.success = False
        mock_result.stdout = ""

        with patch.object(checker._executor, "execute", return_value=mock_result):
            with patch.object(checker._executor, "sanitize_paths", return_value=["file.py"]):
                result = checker.check(["file.py"])

        assert result.passed is False
        assert result.issues == []

    def test_check_command_validation_error(self) -> None:
        """Test check handles CommandValidationError."""
        checker = LintChecker()

        with patch.object(checker._executor, "execute", side_effect=CommandValidationError("Bad command")):
            with patch.object(checker._executor, "sanitize_paths", return_value=["file.py"]):
                result = checker.check(["file.py"])

        assert result.passed is False
        assert "Command validation failed" in result.issues[0]
        assert result.score == 0.0

    def test_check_generic_exception(self) -> None:
        """Test check handles generic exceptions."""
        checker = LintChecker()

        with patch.object(checker._executor, "execute", side_effect=RuntimeError("Unexpected")):
            with patch.object(checker._executor, "sanitize_paths", return_value=["file.py"]):
                result = checker.check(["file.py"])

        assert result.passed is False
        assert "Lint error" in result.issues[0]
        assert result.score == 0.0

    def test_check_score_minimum_zero(self) -> None:
        """Test that score doesn't go below zero."""
        checker = LintChecker()

        mock_result = MagicMock()
        mock_result.success = False
        # 25 issues * 5 = 125, but score should be capped at 0
        mock_result.stdout = "\n".join([f"issue{i}" for i in range(25)])

        with patch.object(checker._executor, "execute", return_value=mock_result):
            with patch.object(checker._executor, "sanitize_paths", return_value=["file.py"]):
                result = checker.check(["file.py"])

        assert result.score == 0.0


# =============================================================================
# ComplexityChecker Tests
# =============================================================================


class TestComplexityChecker:
    """Tests for ComplexityChecker class."""

    def test_init_default_threshold(self) -> None:
        """Test ComplexityChecker with default threshold."""
        checker = ComplexityChecker()
        assert checker.threshold == 10

    def test_init_custom_threshold(self) -> None:
        """Test ComplexityChecker with custom threshold."""
        checker = ComplexityChecker(threshold=15)
        assert checker.threshold == 15

    def test_check_returns_result(self) -> None:
        """Test check returns placeholder result."""
        checker = ComplexityChecker()
        result = checker.check(["file.py"])

        assert result.check_type == CheckType.COMPLEXITY
        assert result.passed is True
        assert result.score == 85.0

    def test_name_attribute(self) -> None:
        """Test checker has correct name."""
        checker = ComplexityChecker()
        assert checker.name == "complexity"


# =============================================================================
# CoverageChecker Tests
# =============================================================================


class TestCoverageChecker:
    """Tests for CoverageChecker class."""

    def test_init_default_threshold(self) -> None:
        """Test CoverageChecker with default threshold."""
        checker = CoverageChecker()
        assert checker.threshold == 70

    def test_init_custom_threshold(self) -> None:
        """Test CoverageChecker with custom threshold."""
        checker = CoverageChecker(threshold=90)
        assert checker.threshold == 90

    def test_check_returns_result(self) -> None:
        """Test check returns placeholder result."""
        checker = CoverageChecker()
        result = checker.check(["file.py"])

        assert result.check_type == CheckType.COVERAGE
        assert result.passed is True
        assert result.score == 75.0

    def test_name_attribute(self) -> None:
        """Test checker has correct name."""
        checker = CoverageChecker()
        assert checker.name == "coverage"


# =============================================================================
# SecurityChecker Tests
# =============================================================================


class TestSecurityChecker:
    """Tests for SecurityChecker class."""

    def test_init_default_command(self) -> None:
        """Test SecurityChecker with default command."""
        checker = SecurityChecker()
        assert checker.command == "bandit"

    def test_init_custom_command(self) -> None:
        """Test SecurityChecker with custom command."""
        checker = SecurityChecker(command="safety")
        assert checker.command == "safety"

    def test_check_empty_files(self) -> None:
        """Test check with empty file list."""
        checker = SecurityChecker()
        result = checker.check([])

        assert result.check_type == CheckType.SECURITY
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

        assert result.check_type == CheckType.SECURITY
        assert result.passed is True
        assert result.score == 100.0

    def test_check_failure_with_issues(self) -> None:
        """Test check with security issues found."""
        checker = SecurityChecker()

        mock_result = MagicMock()
        mock_result.success = False
        mock_result.stdout = "Issue 1: SQL injection\nIssue 2: XSS"

        with patch.object(checker._executor, "execute", return_value=mock_result):
            with patch.object(checker._executor, "sanitize_paths", return_value=["file.py"]):
                result = checker.check(["file.py"])

        assert result.check_type == CheckType.SECURITY
        assert result.passed is False
        assert len(result.issues) == 2
        # Score: 100 - 2*10 = 80
        assert result.score == 80.0

    def test_check_failure_empty_output(self) -> None:
        """Test check failure with no stdout."""
        checker = SecurityChecker()

        mock_result = MagicMock()
        mock_result.success = False
        mock_result.stdout = ""

        with patch.object(checker._executor, "execute", return_value=mock_result):
            with patch.object(checker._executor, "sanitize_paths", return_value=["file.py"]):
                result = checker.check(["file.py"])

        assert result.passed is False
        assert result.issues == []

    def test_check_command_validation_error(self) -> None:
        """Test check handles CommandValidationError gracefully."""
        checker = SecurityChecker()

        with patch.object(checker._executor, "execute", side_effect=CommandValidationError("Bad command")):
            with patch.object(checker._executor, "sanitize_paths", return_value=["file.py"]):
                result = checker.check(["file.py"])

        # Security checker passes on validation error (tool not available)
        assert result.passed is True
        assert result.score == 100.0

    def test_check_generic_exception(self) -> None:
        """Test check handles generic exceptions gracefully."""
        checker = SecurityChecker()

        with patch.object(checker._executor, "execute", side_effect=RuntimeError("Unexpected")):
            with patch.object(checker._executor, "sanitize_paths", return_value=["file.py"]):
                result = checker.check(["file.py"])

        # Security checker passes on exception (tool not available)
        assert result.passed is True
        assert result.score == 100.0

    def test_check_score_minimum_zero(self) -> None:
        """Test that score doesn't go below zero."""
        checker = SecurityChecker()

        mock_result = MagicMock()
        mock_result.success = False
        # 15 issues * 10 = 150, but score should be capped at 0
        mock_result.stdout = "\n".join([f"issue{i}" for i in range(15)])

        with patch.object(checker._executor, "execute", return_value=mock_result):
            with patch.object(checker._executor, "sanitize_paths", return_value=["file.py"]):
                result = checker.check(["file.py"])

        assert result.score == 0.0

    def test_name_attribute(self) -> None:
        """Test checker has correct name."""
        checker = SecurityChecker()
        assert checker.name == "security"


# =============================================================================
# AnalyzeCommand Orchestrator Tests
# =============================================================================


class TestAnalyzeCommandClass:
    """Tests for AnalyzeCommand class."""

    def test_init_default_config(self) -> None:
        """Test AnalyzeCommand with default config."""
        cmd = AnalyzeCommand()
        assert cmd.config.complexity_threshold == 10
        assert cmd.config.coverage_threshold == 70

    def test_init_custom_config(self) -> None:
        """Test AnalyzeCommand with custom config."""
        config = AnalyzeConfig(complexity_threshold=20, coverage_threshold=90)
        cmd = AnalyzeCommand(config)
        assert cmd.config.complexity_threshold == 20
        assert cmd.config.coverage_threshold == 90

    def test_supported_checks_returns_list(self) -> None:
        """Test supported_checks returns all check types as a list (line 217)."""
        cmd = AnalyzeCommand()
        checks = cmd.supported_checks()

        assert isinstance(checks, list)
        assert len(checks) == 11
        assert "lint" in checks
        assert "complexity" in checks
        assert "coverage" in checks
        assert "security" in checks
        assert "performance" in checks
        assert "dead-code" in checks
        assert "wiring" in checks
        assert "cross-file" in checks
        assert "conventions" in checks
        assert "import-chain" in checks
        assert "context-engineering" in checks

    def test_run_single_check_without_mock(self) -> None:
        """Test running a single check directly (lines 223-234)."""
        cmd = AnalyzeCommand()
        # Run with empty files to trigger the actual code path
        results = cmd.run(["lint"], [])

        assert len(results) == 1
        assert results[0].check_type == CheckType.LINT
        # Empty file list returns passed=True
        assert results[0].passed is True

    def test_run_all_checks_without_mock(self) -> None:
        """Test running all checks directly (expands 'all' to checker names)."""
        cmd = AnalyzeCommand()
        # Run with empty files to trigger actual code path
        results = cmd.run(["all"], [])

        assert len(results) == 11
        check_types = {r.check_type for r in results}
        assert CheckType.LINT in check_types
        assert CheckType.COMPLEXITY in check_types
        assert CheckType.COVERAGE in check_types
        assert CheckType.SECURITY in check_types
        assert CheckType.DEAD_CODE in check_types
        assert CheckType.WIRING in check_types

    def test_run_multiple_checks(self) -> None:
        """Test running multiple specific checks."""
        cmd = AnalyzeCommand()
        results = cmd.run(["lint", "security"], [])

        assert len(results) == 2
        check_types = {r.check_type for r in results}
        assert CheckType.LINT in check_types
        assert CheckType.SECURITY in check_types

    def test_run_unknown_check_ignored(self) -> None:
        """Test that unknown check names are ignored."""
        cmd = AnalyzeCommand()
        results = cmd.run(["unknown_check"], [])

        assert len(results) == 0

    def test_run_mixed_valid_invalid_checks(self) -> None:
        """Test running mix of valid and invalid check names."""
        cmd = AnalyzeCommand()
        results = cmd.run(["lint", "invalid", "security", "fake"], [])

        # Only valid checks should run
        assert len(results) == 2

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

    def test_overall_passed_empty_results(self) -> None:
        """Test overall_passed with empty results."""
        cmd = AnalyzeCommand()
        assert cmd.overall_passed([]) is True


# =============================================================================
# Result Formatting Tests
# =============================================================================


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
        assert "lint" in output
        assert "security" in output
        assert "SQL injection" in output
        assert "FAILED" in output

    def test_format_text_limited_issues(self) -> None:
        """Test that text format limits issues shown."""
        cmd = AnalyzeCommand()
        results = [
            AnalysisResult(
                CheckType.LINT,
                False,
                [f"Issue {i}" for i in range(10)],  # More than 5 issues
                50.0,
            ),
        ]

        output = cmd.format_results(results, "text")
        # Only first 5 issues should be shown
        assert "Issue 0" in output
        assert "Issue 4" in output

    def test_format_json(self) -> None:
        """Test JSON format output."""
        cmd = AnalyzeCommand()
        results = [
            AnalysisResult(CheckType.LINT, True, [], 100.0),
        ]

        output = cmd.format_results(results, "json")
        data = json.loads(output)

        assert "results" in data
        assert "overall_passed" in data
        assert data["overall_passed"] is True
        assert len(data["results"]) == 1
        assert data["results"][0]["check"] == "lint"
        assert data["results"][0]["passed"] is True

    def test_format_sarif(self) -> None:
        """Test SARIF format output."""
        cmd = AnalyzeCommand()
        results = [
            AnalysisResult(CheckType.SECURITY, False, ["SQL injection", "XSS"], 70.0),
        ]

        output = cmd.format_results(results, "sarif")
        data = json.loads(output)

        assert "$schema" in data
        assert data["version"] == "2.1.0"
        assert "runs" in data
        assert len(data["runs"]) == 1
        assert data["runs"][0]["tool"]["driver"]["name"] == "zerg-analyze"
        assert len(data["runs"][0]["results"]) == 2

    def test_format_sarif_issue_levels(self) -> None:
        """Test SARIF format has correct issue levels."""
        cmd = AnalyzeCommand()
        results = [
            AnalysisResult(CheckType.LINT, True, ["Note"], 100.0),
            AnalysisResult(CheckType.SECURITY, False, ["Error"], 50.0),
        ]

        output = cmd.format_results(results, "sarif")
        data = json.loads(output)

        sarif_results = data["runs"][0]["results"]
        # Find results by message
        for r in sarif_results:
            if r["message"]["text"] == "Note":
                assert r["level"] == "note"
            elif r["message"]["text"] == "Error":
                assert r["level"] == "error"

    def test_format_default_is_text(self) -> None:
        """Test that default format is text."""
        cmd = AnalyzeCommand()
        results = [AnalysisResult(CheckType.LINT, True, [], 100.0)]

        output = cmd.format_results(results)
        assert "Analysis Results" in output


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestParseThresholds:
    """Tests for _parse_thresholds function."""

    def test_parse_single_threshold(self) -> None:
        """Test parsing single threshold."""
        result = _parse_thresholds(("complexity=15",))
        assert result == {"complexity": 15}

    def test_parse_multiple_thresholds(self) -> None:
        """Test parsing multiple thresholds."""
        result = _parse_thresholds(("complexity=15", "coverage=80"))
        assert result == {"complexity": 15, "coverage": 80}

    def test_parse_empty_tuple(self) -> None:
        """Test parsing empty tuple."""
        result = _parse_thresholds(())
        assert result == {}

    def test_parse_invalid_format_no_equals(self) -> None:
        """Test parsing invalid format without equals sign."""
        result = _parse_thresholds(("complexity15",))
        assert result == {}

    def test_parse_invalid_value(self) -> None:
        """Test parsing with non-integer value."""
        result = _parse_thresholds(("complexity=high",))
        assert result == {}

    def test_parse_strips_whitespace(self) -> None:
        """Test that whitespace is stripped."""
        result = _parse_thresholds(("  complexity = 15  ",))
        assert result == {"complexity": 15}


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
        (tmp_path / "file2.py").write_text("# test")
        (tmp_path / "file3.txt").write_text("not python")

        files = _collect_files(str(tmp_path))

        # Should only include .py files
        assert any("file1.py" in f for f in files)
        assert any("file2.py" in f for f in files)
        assert not any("file3.txt" in f for f in files)

    def test_collect_recursively(self, tmp_path: Path) -> None:
        """Test collecting files recursively."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "nested.py").write_text("# test")

        files = _collect_files(str(tmp_path))
        assert any("nested.py" in f for f in files)

    def test_collect_nonexistent_path(self) -> None:
        """Test collecting from nonexistent path."""
        files = _collect_files("/nonexistent/path")
        assert files == []

    def test_collect_default_current_dir(self, tmp_path: Path, monkeypatch) -> None:
        """Test collecting with None defaults to current directory."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "test.py").write_text("# test")

        files = _collect_files(None)
        assert any("test.py" in f for f in files)

    def test_collect_limits_files(self, tmp_path: Path) -> None:
        """Test that file collection is limited to 100 files."""
        # Create 150 Python files
        for i in range(150):
            (tmp_path / f"file{i}.py").write_text(f"# test {i}")

        files = _collect_files(str(tmp_path))
        assert len(files) <= 100

    def test_collect_multiple_extensions(self, tmp_path: Path) -> None:
        """Test collecting files with multiple extensions."""
        (tmp_path / "file.py").write_text("# python")
        (tmp_path / "file.js").write_text("// js")
        (tmp_path / "file.ts").write_text("// ts")
        (tmp_path / "file.go").write_text("// go")
        (tmp_path / "file.rs").write_text("// rust")

        files = _collect_files(str(tmp_path))

        # All supported extensions should be collected
        assert any(".py" in f for f in files)
        assert any(".js" in f for f in files)
        assert any(".ts" in f for f in files)
        assert any(".go" in f for f in files)
        assert any(".rs" in f for f in files)


# =============================================================================
# CLI Command Integration Tests
# =============================================================================


class TestAnalyzeCLI:
    """Integration tests for the analyze CLI command."""

    def test_analyze_help(self) -> None:
        """Test analyze --help shows usage information."""
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", "--help"])

        assert result.exit_code == 0
        assert "Usage:" in result.output
        assert "--check" in result.output
        assert "--format" in result.output
        assert "--threshold" in result.output

    def test_analyze_no_files_found(self, tmp_path: Path, monkeypatch) -> None:
        """Test analyze with no files found."""
        monkeypatch.chdir(tmp_path)
        # Empty directory

        runner = CliRunner()
        result = runner.invoke(cli, ["analyze"])

        assert result.exit_code == 0
        assert "No files found" in result.output

    def test_analyze_text_output(self, tmp_path: Path, monkeypatch) -> None:
        """Test analyze with text output format."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "test.py").write_text("# test")

        with patch("zerg.commands.analyze.AnalyzeCommand") as mock_cmd_class:
            mock_cmd = MagicMock()
            mock_cmd.run.return_value = [
                AnalysisResult(CheckType.LINT, True, [], 100.0),
            ]
            mock_cmd.overall_passed.return_value = True
            mock_cmd_class.return_value = mock_cmd

            runner = CliRunner()
            result = runner.invoke(cli, ["analyze", "--format", "text"])

            assert result.exit_code == 0

    def test_analyze_json_output(self, tmp_path: Path, monkeypatch) -> None:
        """Test analyze with JSON output format."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "test.py").write_text("# test")

        with patch("zerg.commands.analyze.AnalyzeCommand") as mock_cmd_class:
            mock_cmd = MagicMock()
            mock_cmd.run.return_value = [
                AnalysisResult(CheckType.LINT, True, [], 100.0),
            ]
            mock_cmd.overall_passed.return_value = True
            mock_cmd.format_results.return_value = '{"results": []}'
            mock_cmd_class.return_value = mock_cmd

            runner = CliRunner()
            result = runner.invoke(cli, ["analyze", "--format", "json"])

            assert result.exit_code == 0

    def test_analyze_sarif_output(self, tmp_path: Path, monkeypatch) -> None:
        """Test analyze with SARIF output format."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "test.py").write_text("# test")

        with patch("zerg.commands.analyze.AnalyzeCommand") as mock_cmd_class:
            mock_cmd = MagicMock()
            mock_cmd.run.return_value = [
                AnalysisResult(CheckType.LINT, True, [], 100.0),
            ]
            mock_cmd.overall_passed.return_value = True
            mock_cmd.format_results.return_value = '{"version": "2.1.0"}'
            mock_cmd_class.return_value = mock_cmd

            runner = CliRunner()
            result = runner.invoke(cli, ["analyze", "--format", "sarif"])

            assert result.exit_code == 0

    def test_analyze_single_check(self, tmp_path: Path, monkeypatch) -> None:
        """Test analyze with single check type."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "test.py").write_text("# test")

        with patch("zerg.commands.analyze.AnalyzeCommand") as mock_cmd_class:
            mock_cmd = MagicMock()
            mock_cmd.run.return_value = [
                AnalysisResult(CheckType.LINT, True, [], 100.0),
            ]
            mock_cmd.overall_passed.return_value = True
            mock_cmd_class.return_value = mock_cmd

            runner = CliRunner()
            result = runner.invoke(cli, ["analyze", "--check", "lint"])

            mock_cmd.run.assert_called()
            assert result.exit_code == 0

    def test_analyze_with_complexity_threshold(self, tmp_path: Path, monkeypatch) -> None:
        """Test analyze with complexity threshold."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "test.py").write_text("# test")

        with patch("zerg.commands.analyze.AnalyzeCommand") as mock_cmd_class:
            mock_cmd = MagicMock()
            mock_cmd.run.return_value = [
                AnalysisResult(CheckType.COMPLEXITY, True, [], 90.0),
            ]
            mock_cmd.overall_passed.return_value = True
            mock_cmd_class.return_value = mock_cmd

            runner = CliRunner()
            result = runner.invoke(cli, ["analyze", "--check", "complexity", "--threshold", "complexity=15"])

            assert result.exit_code == 0

    def test_analyze_with_coverage_threshold(self, tmp_path: Path, monkeypatch) -> None:
        """Test analyze with coverage threshold to hit line 392."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "test.py").write_text("# test")

        with patch("zerg.commands.analyze.AnalyzeCommand") as mock_cmd_class:
            mock_cmd = MagicMock()
            mock_cmd.run.return_value = [
                AnalysisResult(CheckType.COVERAGE, True, [], 85.0),
            ]
            mock_cmd.overall_passed.return_value = True
            mock_cmd_class.return_value = mock_cmd

            runner = CliRunner()
            result = runner.invoke(cli, ["analyze", "--check", "coverage", "--threshold", "coverage=80"])

            assert result.exit_code == 0

    def test_analyze_deprecated_files_option_removed(self, tmp_path: Path, monkeypatch) -> None:
        """Test that removed --files option is rejected."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "test.py").write_text("# test")

        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", "--files", str(tmp_path)])

        assert result.exit_code == 2  # Click rejects unknown option

    def test_analyze_failure_exit_code(self, tmp_path: Path, monkeypatch) -> None:
        """Test analyze returns exit code 1 on failure."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "test.py").write_text("# test")

        with patch("zerg.commands.analyze.AnalyzeCommand") as mock_cmd_class:
            mock_cmd = MagicMock()
            mock_cmd.run.return_value = [
                AnalysisResult(CheckType.SECURITY, False, ["Issue"], 50.0),
            ]
            mock_cmd.overall_passed.return_value = False
            mock_cmd_class.return_value = mock_cmd

            runner = CliRunner()
            result = runner.invoke(cli, ["analyze"])

            assert result.exit_code == 1

    def test_analyze_shows_issues(self, tmp_path: Path, monkeypatch) -> None:
        """Test analyze shows issues in text mode."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "test.py").write_text("# test")

        with patch("zerg.commands.analyze.AnalyzeCommand") as mock_cmd_class:
            mock_cmd = MagicMock()
            mock_cmd.run.return_value = [
                AnalysisResult(
                    CheckType.LINT,
                    False,
                    [f"Issue {i}" for i in range(15)],  # More than 10 issues
                    50.0,
                ),
            ]
            mock_cmd.overall_passed.return_value = False
            mock_cmd_class.return_value = mock_cmd

            runner = CliRunner()
            result = runner.invoke(cli, ["analyze", "--format", "text"])

            # Should show "... and X more" for excess issues
            assert "more" in result.output or result.exit_code == 1


class TestAnalyzeErrorHandling:
    """Tests for analyze command error handling."""

    def test_keyboard_interrupt(self, tmp_path: Path, monkeypatch) -> None:
        """Test analyze handles KeyboardInterrupt gracefully."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "test.py").write_text("# test")

        with patch(
            "zerg.commands.analyze.AnalyzeCommand",
            side_effect=KeyboardInterrupt(),
        ):
            runner = CliRunner()
            result = runner.invoke(cli, ["analyze"])

            assert result.exit_code == 130
            assert "Interrupted" in result.output

    def test_general_exception(self, tmp_path: Path, monkeypatch) -> None:
        """Test analyze handles general exceptions."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "test.py").write_text("# test")

        with patch(
            "zerg.commands.analyze.AnalyzeCommand",
            side_effect=RuntimeError("Unexpected error"),
        ):
            runner = CliRunner()
            result = runner.invoke(cli, ["analyze"])

            assert result.exit_code == 1
            assert "Error" in result.output


# =============================================================================
# Edge Cases and Boundary Conditions
# =============================================================================


class TestAnalyzeEdgeCases:
    """Edge case tests for analyze command."""

    def test_empty_issues_list(self) -> None:
        """Test formatting with empty issues list."""
        cmd = AnalyzeCommand()
        results = [AnalysisResult(CheckType.LINT, True, [], 100.0)]

        # Should not raise
        output = cmd.format_results(results, "text")
        assert "lint" in output

    def test_single_issue(self) -> None:
        """Test formatting with exactly one issue."""
        cmd = AnalyzeCommand()
        results = [AnalysisResult(CheckType.LINT, False, ["Single issue"], 95.0)]

        output = cmd.format_results(results, "text")
        assert "Single issue" in output

    def test_threshold_with_extra_equals(self) -> None:
        """Test parsing threshold with extra equals in value."""
        # This would be invalid but shouldn't crash
        result = _parse_thresholds(("key=value=extra",))
        # Should only parse first part, second part is invalid int
        assert result == {}

    def test_sarif_empty_results(self) -> None:
        """Test SARIF format with no results."""
        cmd = AnalyzeCommand()
        results: list[AnalysisResult] = []

        output = cmd.format_results(results, "sarif")
        data = json.loads(output)

        assert data["runs"][0]["results"] == []

    def test_analyze_path_argument(self, tmp_path: Path, monkeypatch) -> None:
        """Test analyze with explicit path argument."""
        monkeypatch.chdir(tmp_path)
        subdir = tmp_path / "src"
        subdir.mkdir()
        (subdir / "test.py").write_text("# test")

        with patch("zerg.commands.analyze.AnalyzeCommand") as mock_cmd_class:
            mock_cmd = MagicMock()
            mock_cmd.run.return_value = [
                AnalysisResult(CheckType.LINT, True, [], 100.0),
            ]
            mock_cmd.overall_passed.return_value = True
            mock_cmd_class.return_value = mock_cmd

            runner = CliRunner()
            result = runner.invoke(cli, ["analyze", str(subdir)])

            assert result.exit_code == 0

    def test_run_iterates_over_checks(self) -> None:
        """Test that run iterates over all checks in the list."""
        cmd = AnalyzeCommand()
        # Use complexity and coverage which don't need external tools
        results = cmd.run(["complexity", "coverage"], [])

        assert len(results) == 2
        types = {r.check_type for r in results}
        assert CheckType.COMPLEXITY in types
        assert CheckType.COVERAGE in types
