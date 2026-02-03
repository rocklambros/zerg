"""Comprehensive unit tests for ZERG review command - 100% coverage target.

Tests cover:
- ReviewMode enum
- ReviewConfig dataclass
- ReviewItem dataclass
- ReviewResult dataclass with properties
- SelfReviewChecklist class
- CodeAnalyzer for code issue detection
- ReviewCommand orchestration
- _collect_files helper function
- CLI command with all options
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from zerg.commands.review import (
    CodeAnalyzer,
    ReviewCommand,
    ReviewConfig,
    ReviewItem,
    ReviewMode,
    ReviewResult,
    SelfReviewChecklist,
    _collect_files,
    review,
)

# =============================================================================
# ReviewMode Enum Tests
# =============================================================================


class TestReviewModeEnum:
    """Tests for ReviewMode enum."""

    def test_prepare_value(self) -> None:
        """Test prepare enum value."""
        assert ReviewMode.PREPARE.value == "prepare"

    def test_self_value(self) -> None:
        """Test self enum value."""
        assert ReviewMode.SELF.value == "self"

    def test_receive_value(self) -> None:
        """Test receive enum value."""
        assert ReviewMode.RECEIVE.value == "receive"

    def test_full_value(self) -> None:
        """Test full enum value."""
        assert ReviewMode.FULL.value == "full"

    def test_all_modes_exist(self) -> None:
        """Test all expected modes are defined."""
        expected = {"prepare", "self", "receive", "full"}
        actual = {m.value for m in ReviewMode}
        assert actual == expected


# =============================================================================
# ReviewConfig Dataclass Tests
# =============================================================================


class TestReviewConfig:
    """Tests for ReviewConfig dataclass."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = ReviewConfig()

        assert config.mode == "full"
        assert config.include_tests is True
        assert config.include_docs is True
        assert config.strict is False

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        config = ReviewConfig(
            mode="prepare",
            include_tests=False,
            include_docs=False,
            strict=True,
        )

        assert config.mode == "prepare"
        assert config.include_tests is False
        assert config.include_docs is False
        assert config.strict is True


# =============================================================================
# ReviewItem Dataclass Tests
# =============================================================================


class TestReviewItem:
    """Tests for ReviewItem dataclass."""

    def test_default_suggestion(self) -> None:
        """Test default suggestion value."""
        item = ReviewItem(
            category="debug_print",
            severity="warning",
            file="test.py",
            line=10,
            message="Debug statement found",
        )

        assert item.suggestion == ""

    def test_custom_suggestion(self) -> None:
        """Test custom suggestion value."""
        item = ReviewItem(
            category="complexity",
            severity="warning",
            file="test.py",
            line=1,
            message="High complexity",
            suggestion="Break into smaller functions",
        )

        assert item.suggestion == "Break into smaller functions"

    def test_to_dict(self) -> None:
        """Test to_dict method."""
        item = ReviewItem(
            category="hardcoded_secret",
            severity="error",
            file="config.py",
            line=5,
            message="Potential hardcoded secret",
            suggestion="Use environment variables",
        )

        result = item.to_dict()

        assert result == {
            "category": "hardcoded_secret",
            "severity": "error",
            "file": "config.py",
            "line": 5,
            "message": "Potential hardcoded secret",
            "suggestion": "Use environment variables",
        }


# =============================================================================
# ReviewResult Dataclass Tests
# =============================================================================


class TestReviewResult:
    """Tests for ReviewResult dataclass."""

    def test_overall_passed_both_true(self) -> None:
        """Test overall_passed when both stages pass."""
        result = ReviewResult(
            files_reviewed=5,
            items=[],
            spec_passed=True,
            quality_passed=True,
        )

        assert result.overall_passed is True

    def test_overall_passed_spec_false(self) -> None:
        """Test overall_passed when spec fails."""
        result = ReviewResult(
            files_reviewed=5,
            items=[],
            spec_passed=False,
            quality_passed=True,
        )

        assert result.overall_passed is False

    def test_overall_passed_quality_false(self) -> None:
        """Test overall_passed when quality fails."""
        result = ReviewResult(
            files_reviewed=5,
            items=[],
            spec_passed=True,
            quality_passed=False,
        )

        assert result.overall_passed is False

    def test_overall_passed_both_false(self) -> None:
        """Test overall_passed when both fail."""
        result = ReviewResult(
            files_reviewed=5,
            items=[],
            spec_passed=False,
            quality_passed=False,
        )

        assert result.overall_passed is False

    def test_total_items_property(self) -> None:
        """Test total_items property."""
        items = [
            ReviewItem(
                category="debug",
                severity="warning",
                file="a.py",
                line=1,
                message="Debug",
            ),
            ReviewItem(
                category="todo",
                severity="info",
                file="b.py",
                line=2,
                message="TODO",
            ),
        ]
        result = ReviewResult(
            files_reviewed=2,
            items=items,
            spec_passed=True,
            quality_passed=True,
        )

        assert result.total_items == 2

    def test_total_items_empty(self) -> None:
        """Test total_items with no items."""
        result = ReviewResult(
            files_reviewed=2,
            items=[],
            spec_passed=True,
            quality_passed=True,
        )

        assert result.total_items == 0

    def test_error_count_property(self) -> None:
        """Test error_count property."""
        items = [
            ReviewItem(
                category="secret",
                severity="error",
                file="a.py",
                line=1,
                message="Secret",
            ),
            ReviewItem(
                category="debug",
                severity="warning",
                file="b.py",
                line=2,
                message="Debug",
            ),
            ReviewItem(
                category="secret",
                severity="error",
                file="c.py",
                line=3,
                message="Secret",
            ),
        ]
        result = ReviewResult(
            files_reviewed=3,
            items=items,
            spec_passed=True,
            quality_passed=True,
        )

        assert result.error_count == 2

    def test_error_count_zero(self) -> None:
        """Test error_count with no errors."""
        items = [
            ReviewItem(
                category="debug",
                severity="warning",
                file="a.py",
                line=1,
                message="Debug",
            ),
        ]
        result = ReviewResult(
            files_reviewed=1,
            items=items,
            spec_passed=True,
            quality_passed=True,
        )

        assert result.error_count == 0

    def test_warning_count_property(self) -> None:
        """Test warning_count property."""
        items = [
            ReviewItem(
                category="debug",
                severity="warning",
                file="a.py",
                line=1,
                message="Debug",
            ),
            ReviewItem(
                category="secret",
                severity="error",
                file="b.py",
                line=2,
                message="Secret",
            ),
            ReviewItem(
                category="debug",
                severity="warning",
                file="c.py",
                line=3,
                message="Debug",
            ),
        ]
        result = ReviewResult(
            files_reviewed=3,
            items=items,
            spec_passed=True,
            quality_passed=True,
        )

        assert result.warning_count == 2

    def test_warning_count_zero(self) -> None:
        """Test warning_count with no warnings."""
        items = [
            ReviewItem(
                category="secret",
                severity="error",
                file="a.py",
                line=1,
                message="Secret",
            ),
        ]
        result = ReviewResult(
            files_reviewed=1,
            items=items,
            spec_passed=True,
            quality_passed=True,
        )

        assert result.warning_count == 0

    def test_default_stage_details(self) -> None:
        """Test default stage details."""
        result = ReviewResult(
            files_reviewed=1,
            items=[],
            spec_passed=True,
            quality_passed=True,
        )

        assert result.stage1_details == ""
        assert result.stage2_details == ""


# =============================================================================
# SelfReviewChecklist Tests
# =============================================================================


class TestSelfReviewChecklist:
    """Tests for SelfReviewChecklist class."""

    def test_items_exist(self) -> None:
        """Test checklist items exist."""
        checklist = SelfReviewChecklist()
        items = checklist.get_items()

        assert len(items) == 10

    def test_items_have_key_and_description(self) -> None:
        """Test all items have key and description."""
        checklist = SelfReviewChecklist()
        items = checklist.get_items()

        for key, description in items:
            assert isinstance(key, str)
            assert isinstance(description, str)
            assert len(key) > 0
            assert len(description) > 0

    def test_specific_items_exist(self) -> None:
        """Test specific checklist items exist."""
        checklist = SelfReviewChecklist()
        items = checklist.get_items()
        keys = [key for key, _ in items]

        assert "basics" in keys
        assert "tests" in keys
        assert "secrets" in keys
        assert "errors" in keys
        assert "edge_cases" in keys
        assert "readability" in keys


# =============================================================================
# CodeAnalyzer Tests
# =============================================================================


class TestCodeAnalyzer:
    """Tests for CodeAnalyzer class."""

    def test_analyze_detects_print(self) -> None:
        """Test analyze detects print statements."""
        analyzer = CodeAnalyzer()
        content = "print('debug')"

        items = analyzer.analyze(content, "test.py")

        assert len(items) == 1
        assert items[0].category == "debug_print"
        assert items[0].severity == "warning"

    def test_analyze_detects_console_log(self) -> None:
        """Test analyze detects console.log."""
        analyzer = CodeAnalyzer()
        content = "console.log('debug');"

        items = analyzer.analyze(content, "test.js")

        assert len(items) == 1
        assert items[0].category == "debug_print"

    def test_analyze_detects_debugger(self) -> None:
        """Test analyze detects debugger statement."""
        analyzer = CodeAnalyzer()
        content = "debugger;"

        items = analyzer.analyze(content, "test.js")

        assert len(items) == 1
        assert items[0].category == "debug_print"

    def test_analyze_detects_todo(self) -> None:
        """Test analyze detects TODO comments."""
        analyzer = CodeAnalyzer()
        content = "# TODO: fix this"

        items = analyzer.analyze(content, "test.py")

        assert len(items) == 1
        assert items[0].category == "todo"
        assert items[0].severity == "info"

    def test_analyze_detects_fixme(self) -> None:
        """Test analyze detects FIXME comments."""
        analyzer = CodeAnalyzer()
        content = "// FIXME: broken"

        items = analyzer.analyze(content, "test.js")

        assert len(items) == 1
        assert items[0].category == "todo"

    def test_analyze_detects_hack(self) -> None:
        """Test analyze detects HACK comments."""
        analyzer = CodeAnalyzer()
        content = "# HACK: workaround"

        items = analyzer.analyze(content, "test.py")

        assert len(items) == 1
        assert items[0].category == "todo"

    def test_analyze_detects_xxx(self) -> None:
        """Test analyze detects XXX comments."""
        analyzer = CodeAnalyzer()
        content = "# XXX: bad code"

        items = analyzer.analyze(content, "test.py")

        assert len(items) == 1
        assert items[0].category == "todo"

    def test_analyze_detects_hardcoded_password(self) -> None:
        """Test analyze detects hardcoded password."""
        analyzer = CodeAnalyzer()
        content = "password = 'secret123'"

        items = analyzer.analyze(content, "config.py")

        assert len(items) == 1
        assert items[0].category == "hardcoded_secret"
        assert items[0].severity == "error"

    def test_analyze_detects_hardcoded_api_key(self) -> None:
        """Test analyze detects hardcoded API key."""
        analyzer = CodeAnalyzer()
        content = "api_key = 'abc123def456'"

        items = analyzer.analyze(content, "config.py")

        assert len(items) == 1
        assert items[0].category == "hardcoded_secret"

    def test_analyze_detects_hardcoded_token(self) -> None:
        """Test analyze detects hardcoded token."""
        analyzer = CodeAnalyzer()
        content = "token = 'xyz789'"

        items = analyzer.analyze(content, "auth.py")

        assert len(items) == 1
        assert items[0].category == "hardcoded_secret"

    def test_analyze_detects_long_lines(self) -> None:
        """Test analyze detects lines over 120 characters."""
        analyzer = CodeAnalyzer()
        content = "x = " + "a" * 150

        items = analyzer.analyze(content, "test.py")

        assert len(items) == 1
        assert items[0].category == "long_line"
        assert items[0].severity == "info"
        assert "chars" in items[0].message

    def test_analyze_accepts_normal_lines(self) -> None:
        """Test analyze accepts lines under 120 characters."""
        analyzer = CodeAnalyzer()
        content = "x = 1\ny = 2"

        items = analyzer.analyze(content, "test.py")

        assert all(i.category != "long_line" for i in items)

    def test_analyze_multiple_issues(self) -> None:
        """Test analyze finds multiple issues."""
        analyzer = CodeAnalyzer()
        content = "print('debug')\n# TODO: fix\npassword = 'secret'"

        items = analyzer.analyze(content, "test.py")

        assert len(items) == 3

    def test_analyze_no_issues(self) -> None:
        """Test analyze with clean code."""
        analyzer = CodeAnalyzer()
        content = "x = 1\ny = x + 1"

        items = analyzer.analyze(content, "test.py")

        assert items == []

    def test_analyze_case_insensitive(self) -> None:
        """Test analyze is case insensitive."""
        analyzer = CodeAnalyzer()
        content = "# todo: something"

        items = analyzer.analyze(content, "test.py")

        assert len(items) == 1


# =============================================================================
# ReviewCommand Tests
# =============================================================================


class TestReviewCommand:
    """Tests for ReviewCommand class."""

    def test_init_default_config(self) -> None:
        """Test initialization with default config."""
        reviewer = ReviewCommand()

        assert reviewer.config.mode == "full"
        assert reviewer.config.strict is False

    def test_init_custom_config(self) -> None:
        """Test initialization with custom config."""
        config = ReviewConfig(mode="prepare", strict=True)
        reviewer = ReviewCommand(config)

        assert reviewer.config.mode == "prepare"
        assert reviewer.config.strict is True

    def test_supported_modes(self) -> None:
        """Test supported_modes returns all modes."""
        reviewer = ReviewCommand()

        modes = reviewer.supported_modes()

        assert "prepare" in modes
        assert "self" in modes
        assert "receive" in modes
        assert "full" in modes

    def test_run_full_mode(self, tmp_path: Path) -> None:
        """Test run in full mode."""
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1")

        reviewer = ReviewCommand()
        result = reviewer.run([str(test_file)], mode="full")

        assert result.files_reviewed == 1
        assert result.spec_passed is True
        assert result.quality_passed is True

    def test_run_prepare_mode(self, tmp_path: Path) -> None:
        """Test run in prepare mode."""
        test_file = tmp_path / "test_module.py"
        test_file.write_text("x = 1")

        reviewer = ReviewCommand()
        result = reviewer.run([str(test_file)], mode="prepare")

        assert result.spec_passed is True
        assert result.stage1_details != ""

    def test_run_self_mode(self, tmp_path: Path) -> None:
        """Test run in self mode."""
        test_file = tmp_path / "module.py"
        test_file.write_text("print('debug')")

        reviewer = ReviewCommand()
        result = reviewer.run([str(test_file)], mode="self")

        assert result.files_reviewed == 1
        assert len(result.items) >= 1

    def test_run_receive_mode(self, tmp_path: Path) -> None:
        """Test run in receive mode."""
        test_file = tmp_path / "module.py"
        test_file.write_text("x = 1")

        reviewer = ReviewCommand()
        result = reviewer.run([str(test_file)], mode="receive")

        assert result.quality_passed is True
        assert result.stage2_details != ""

    def test_run_spec_review_with_tests(self, tmp_path: Path) -> None:
        """Test spec review passes with test files."""
        test_file = tmp_path / "test_module.py"
        test_file.write_text("def test_x(): pass")

        config = ReviewConfig(include_tests=True)
        reviewer = ReviewCommand(config)
        result = reviewer.run([str(test_file)], mode="prepare")

        assert result.spec_passed is True
        assert "Test files present" in result.stage1_details

    def test_run_spec_review_without_tests(self) -> None:
        """Test spec review warns without test files.

        Note: We use explicit file paths without 'test' to avoid tmpdir
        path containing 'test' (e.g., /tmp/pytest-...).
        """
        # Use file paths that explicitly don't contain 'test'
        config = ReviewConfig(include_tests=True)
        reviewer = ReviewCommand(config)
        result = reviewer.run(["module.py", "app.py"], mode="prepare")

        # These file paths don't contain 'test', so warning should be present
        assert "No test files" in result.stage1_details

    def test_run_spec_review_with_docs(self, tmp_path: Path) -> None:
        """Test spec review passes with doc files."""
        doc_file = tmp_path / "README.md"
        doc_file.write_text("# Documentation")

        config = ReviewConfig(include_docs=True)
        reviewer = ReviewCommand(config)
        result = reviewer.run([str(doc_file)], mode="prepare")

        assert "Documentation updated" in result.stage1_details

    def test_run_spec_review_without_docs(self, tmp_path: Path) -> None:
        """Test spec review warns without doc files."""
        test_file = tmp_path / "module.py"
        test_file.write_text("x = 1")

        config = ReviewConfig(include_docs=True)
        reviewer = ReviewCommand(config)
        result = reviewer.run([str(test_file)], mode="prepare")

        assert "Consider updating documentation" in result.stage1_details

    def test_run_spec_review_with_rst_docs(self, tmp_path: Path) -> None:
        """Test spec review passes with .rst files."""
        doc_file = tmp_path / "docs.rst"
        doc_file.write_text("Documentation\n=============")

        config = ReviewConfig(include_docs=True)
        reviewer = ReviewCommand(config)
        result = reviewer.run([str(doc_file)], mode="prepare")

        assert "Documentation updated" in result.stage1_details

    def test_run_self_review_nonexistent_file(self) -> None:
        """Test self review with nonexistent file."""
        reviewer = ReviewCommand()
        result = reviewer.run(["/nonexistent/path.py"], mode="self")

        assert result.files_reviewed == 1
        assert result.items == []

    def test_run_self_review_directory(self, tmp_path: Path) -> None:
        """Test self review skips directories."""
        reviewer = ReviewCommand()
        result = reviewer.run([str(tmp_path)], mode="self")

        assert result.items == []

    def test_run_self_review_unsupported_extension(self, tmp_path: Path) -> None:
        """Test self review skips unsupported file types."""
        text_file = tmp_path / "readme.txt"
        text_file.write_text("Some text")

        reviewer = ReviewCommand()
        result = reviewer.run([str(text_file)], mode="self")

        assert result.items == []

    def test_run_self_review_supported_extensions(self, tmp_path: Path) -> None:
        """Test self review handles various supported extensions."""
        extensions = [".py", ".js", ".ts", ".go", ".rs", ".java"]
        for ext in extensions:
            test_file = tmp_path / f"file{ext}"
            test_file.write_text("// TODO: fix")

        reviewer = ReviewCommand()
        files = [str(tmp_path / f"file{ext}") for ext in extensions]
        result = reviewer.run(files, mode="self")

        assert len(result.items) > 0

    def test_run_self_review_handles_read_error(self, tmp_path: Path) -> None:
        """Test self review handles file read errors."""
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1")

        reviewer = ReviewCommand()

        with patch.object(Path, "read_text", side_effect=PermissionError):
            result = reviewer.run([str(test_file)], mode="self")

        assert result.items == []

    def test_run_quality_review_high_complexity(self, tmp_path: Path) -> None:
        """Test quality review detects high complexity."""
        # Create a file with long functions
        content = "def foo():\n" + "    x = 1\n" * 100
        test_file = tmp_path / "module.py"
        test_file.write_text(content)

        reviewer = ReviewCommand()
        result = reviewer.run([str(test_file)], mode="receive")

        assert any(i.category == "complexity" for i in result.items)

    def test_run_quality_review_normal_complexity(self, tmp_path: Path) -> None:
        """Test quality review passes with normal complexity."""
        content = "def foo():\n    x = 1\n\ndef bar():\n    y = 2\n"
        test_file = tmp_path / "module.py"
        test_file.write_text(content)

        reviewer = ReviewCommand()
        result = reviewer.run([str(test_file)], mode="receive")

        assert all(i.category != "complexity" for i in result.items)

    def test_run_quality_review_nonexistent_file(self) -> None:
        """Test quality review with nonexistent file."""
        reviewer = ReviewCommand()
        result = reviewer.run(["/nonexistent/path.py"], mode="receive")

        assert result.quality_passed is True

    def test_run_quality_review_directory(self, tmp_path: Path) -> None:
        """Test quality review skips directories."""
        reviewer = ReviewCommand()
        result = reviewer.run([str(tmp_path)], mode="receive")

        assert result.quality_passed is True

    def test_run_quality_review_handles_read_error(self, tmp_path: Path) -> None:
        """Test quality review handles file read errors."""
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1")

        reviewer = ReviewCommand()

        with patch.object(Path, "read_text", side_effect=PermissionError):
            result = reviewer.run([str(test_file)], mode="receive")

        assert result.quality_passed is True

    def test_run_quality_review_strict_mode_fail(self, tmp_path: Path) -> None:
        """Test quality review fails in strict mode with issues."""
        content = "def foo():\n" + "    x = 1\n" * 100
        test_file = tmp_path / "module.py"
        test_file.write_text(content)

        config = ReviewConfig(strict=True)
        reviewer = ReviewCommand(config)
        result = reviewer.run([str(test_file)], mode="receive")

        assert result.quality_passed is False

    def test_run_quality_review_strict_mode_pass(self, tmp_path: Path) -> None:
        """Test quality review passes in strict mode without issues."""
        test_file = tmp_path / "module.py"
        test_file.write_text("def foo():\n    x = 1\n\ndef bar():\n    y = 2\n")

        config = ReviewConfig(strict=True)
        reviewer = ReviewCommand(config)
        result = reviewer.run([str(test_file)], mode="receive")

        assert result.quality_passed is True

    def test_format_result_json(self) -> None:
        """Test format_result with JSON output."""
        items = [
            ReviewItem(
                category="debug",
                severity="warning",
                file="test.py",
                line=1,
                message="Debug found",
            )
        ]
        result = ReviewResult(
            files_reviewed=1,
            items=items,
            spec_passed=True,
            quality_passed=True,
        )

        reviewer = ReviewCommand()
        output = reviewer.format_result(result, fmt="json")

        parsed = json.loads(output)
        assert parsed["files_reviewed"] == 1
        assert parsed["overall_passed"] is True
        assert len(parsed["items"]) == 1

    def test_format_result_text_passed(self) -> None:
        """Test format_result with text output when passed."""
        result = ReviewResult(
            files_reviewed=5,
            items=[],
            spec_passed=True,
            quality_passed=True,
        )

        reviewer = ReviewCommand()
        output = reviewer.format_result(result, fmt="text")

        assert "PASSED" in output
        assert "Files Reviewed: 5" in output

    def test_format_result_text_needs_attention(self) -> None:
        """Test format_result with text output when needs attention."""
        result = ReviewResult(
            files_reviewed=5,
            items=[],
            spec_passed=False,
            quality_passed=True,
        )

        reviewer = ReviewCommand()
        output = reviewer.format_result(result, fmt="text")

        assert "NEEDS ATTENTION" in output

    def test_format_result_text_with_items(self) -> None:
        """Test format_result text includes review items."""
        items = [
            ReviewItem(
                category="error",
                severity="error",
                file="test.py",
                line=1,
                message="Error message",
            ),
            ReviewItem(
                category="warning",
                severity="warning",
                file="test.py",
                line=2,
                message="Warning message",
            ),
            ReviewItem(
                category="info",
                severity="info",
                file="test.py",
                line=3,
                message="Info message",
            ),
        ]
        result = ReviewResult(
            files_reviewed=1,
            items=items,
            spec_passed=True,
            quality_passed=True,
        )

        reviewer = ReviewCommand()
        output = reviewer.format_result(result, fmt="text")

        assert "Review Items:" in output
        assert "[error]" in output
        assert "[warning]" in output
        assert "[info]" in output

    def test_format_result_text_unknown_severity(self) -> None:
        """Test format_result handles unknown severity."""
        items = [
            ReviewItem(
                category="unknown",
                severity="unknown",
                file="test.py",
                line=1,
                message="Unknown item",
            )
        ]
        result = ReviewResult(
            files_reviewed=1,
            items=items,
            spec_passed=True,
            quality_passed=True,
        )

        reviewer = ReviewCommand()
        output = reviewer.format_result(result, fmt="text")

        assert "[unknown]" in output


# =============================================================================
# _collect_files Tests
# =============================================================================


class TestCollectFiles:
    """Tests for _collect_files helper function."""

    def test_collect_files_from_git_staged(self) -> None:
        """Test collect_files from git staged changes."""
        with patch.object(
            subprocess,
            "run",
            return_value=MagicMock(returncode=0, stdout="file1.py\nfile2.py\n"),
        ):
            files = _collect_files(None, "full")

        assert files == ["file1.py", "file2.py"]

    def test_collect_files_from_git_unstaged(self) -> None:
        """Test collect_files from git unstaged changes."""
        # First call (staged) returns empty, second call (unstaged) returns files
        with patch.object(
            subprocess,
            "run",
            side_effect=[
                MagicMock(returncode=0, stdout=""),
                MagicMock(returncode=0, stdout="file1.py\nfile2.py\n"),
            ],
        ):
            files = _collect_files(None, "full")

        assert files == ["file1.py", "file2.py"]

    def test_collect_files_git_fails(self, tmp_path: Path) -> None:
        """Test collect_files when git fails."""
        # Create some files in tmp_path for fallback
        (tmp_path / "test.py").write_text("x = 1")

        with patch.object(
            subprocess,
            "run",
            side_effect=[
                MagicMock(returncode=1, stdout=""),
                MagicMock(returncode=1, stdout=""),
            ],
        ):
            import os

            original_cwd = os.getcwd()
            try:
                os.chdir(tmp_path)
                files = _collect_files(None, "full")
                # Should fall back to directory scan
                assert isinstance(files, list)
            finally:
                os.chdir(original_cwd)

    def test_collect_files_git_exception(self) -> None:
        """Test collect_files handles git exception."""
        with patch.object(subprocess, "run", side_effect=Exception("Git not installed")):
            files = _collect_files(None, "full")

        # Should return files from current directory scan
        assert isinstance(files, list)

    def test_collect_files_file_path(self, tmp_path: Path) -> None:
        """Test collect_files with file path."""
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1")

        files = _collect_files(str(test_file), "full")

        assert files == [str(test_file)]

    def test_collect_files_directory(self, tmp_path: Path) -> None:
        """Test collect_files with directory path."""
        (tmp_path / "a.py").write_text("x = 1")
        (tmp_path / "b.js").write_text("let y = 2")
        (tmp_path / "c.ts").write_text("const z: number = 3")
        (tmp_path / "readme.txt").write_text("text")

        files = _collect_files(str(tmp_path), "full")

        assert len(files) == 3
        assert any(f.endswith(".py") for f in files)
        assert any(f.endswith(".js") for f in files)
        assert any(f.endswith(".ts") for f in files)

    def test_collect_files_excludes_pycache(self, tmp_path: Path) -> None:
        """Test collect_files excludes __pycache__."""
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "cached.py").write_text("x = 1")
        (tmp_path / "main.py").write_text("y = 2")

        files = _collect_files(str(tmp_path), "full")

        assert len(files) == 1
        assert "__pycache__" not in files[0]

    def test_collect_files_limits_results(self, tmp_path: Path) -> None:
        """Test collect_files limits to 50 files."""
        for i in range(60):
            (tmp_path / f"file{i}.py").write_text(f"x = {i}")

        files = _collect_files(str(tmp_path), "full")

        assert len(files) <= 50

    def test_collect_files_nonexistent_path(self) -> None:
        """Test collect_files with nonexistent path."""
        files = _collect_files("/nonexistent/path", "full")

        assert files == []

    def test_collect_files_supports_go_and_rust(self, tmp_path: Path) -> None:
        """Test collect_files includes Go and Rust files."""
        (tmp_path / "main.go").write_text("package main")
        (tmp_path / "lib.rs").write_text("fn main() {}")

        files = _collect_files(str(tmp_path), "full")

        assert len(files) == 2


# =============================================================================
# CLI Command Tests
# =============================================================================


class TestReviewCLI:
    """Tests for review CLI command."""

    def test_review_help(self) -> None:
        """Test review --help."""
        runner = CliRunner()
        result = runner.invoke(review, ["--help"])

        assert result.exit_code == 0
        assert "mode" in result.output
        assert "files" in result.output
        assert "output" in result.output
        assert "json" in result.output

    @patch("zerg.commands.review._collect_files")
    @patch("zerg.commands.review.console")
    def test_review_no_files(self, mock_console: MagicMock, mock_collect: MagicMock) -> None:
        """Test review with no files found."""
        mock_collect.return_value = []

        runner = CliRunner()
        result = runner.invoke(review, [])

        assert result.exit_code == 0

    @patch("zerg.commands.review._collect_files")
    @patch("zerg.commands.review.ReviewCommand")
    @patch("zerg.commands.review.console")
    def test_review_full_mode(
        self,
        mock_console: MagicMock,
        mock_command_class: MagicMock,
        mock_collect: MagicMock,
    ) -> None:
        """Test review in full mode."""
        mock_collect.return_value = ["test.py"]
        mock_command = MagicMock()
        mock_command.run.return_value = ReviewResult(
            files_reviewed=1,
            items=[],
            spec_passed=True,
            quality_passed=True,
        )
        mock_command.checklist.get_items.return_value = [("test", "Test item")]
        mock_command_class.return_value = mock_command

        runner = CliRunner()
        result = runner.invoke(review, ["--mode", "full", "--files", "test.py"])

        assert result.exit_code == 0

    @patch("zerg.commands.review._collect_files")
    @patch("zerg.commands.review.ReviewCommand")
    @patch("zerg.commands.review.console")
    def test_review_self_mode_shows_checklist(
        self,
        mock_console: MagicMock,
        mock_command_class: MagicMock,
        mock_collect: MagicMock,
    ) -> None:
        """Test review self mode shows checklist."""
        mock_collect.return_value = ["test.py"]
        mock_command = MagicMock()
        mock_command.run.return_value = ReviewResult(
            files_reviewed=1,
            items=[],
            spec_passed=True,
            quality_passed=True,
        )
        mock_command.checklist.get_items.return_value = [
            ("basics", "Code runs"),
            ("tests", "Tests pass"),
        ]
        mock_command_class.return_value = mock_command

        runner = CliRunner()
        result = runner.invoke(review, ["--mode", "self", "--files", "test.py"])

        assert result.exit_code == 0

    @patch("zerg.commands.review._collect_files")
    @patch("zerg.commands.review.ReviewCommand")
    @patch("zerg.commands.review.console")
    def test_review_json_output(
        self,
        mock_console: MagicMock,
        mock_command_class: MagicMock,
        mock_collect: MagicMock,
    ) -> None:
        """Test review --json."""
        mock_collect.return_value = ["test.py"]
        mock_command = MagicMock()
        mock_command.run.return_value = ReviewResult(
            files_reviewed=1,
            items=[],
            spec_passed=True,
            quality_passed=True,
        )
        mock_command.format_result.return_value = '{"test": 1}'
        mock_command_class.return_value = mock_command

        runner = CliRunner()
        result = runner.invoke(review, ["--json", "--files", "test.py"])

        assert result.exit_code == 0

    @patch("zerg.commands.review._collect_files")
    @patch("zerg.commands.review.ReviewCommand")
    @patch("zerg.commands.review.console")
    def test_review_with_issues(
        self,
        mock_console: MagicMock,
        mock_command_class: MagicMock,
        mock_collect: MagicMock,
    ) -> None:
        """Test review with issues found but overall_passed is False."""
        mock_collect.return_value = ["test.py"]
        items = [
            ReviewItem(
                category="secret",
                severity="error",
                file="test.py",
                line=1,
                message="Secret found",
            ),
        ]
        mock_result = ReviewResult(
            files_reviewed=1,
            items=items,
            spec_passed=True,
            quality_passed=False,
            stage1_details="Stage 1 details",
        )
        mock_command = MagicMock()
        mock_command.run.return_value = mock_result
        mock_command.checklist.get_items.return_value = []
        mock_command.format_result.return_value = "text output"
        mock_command_class.return_value = mock_command

        runner = CliRunner()
        result = runner.invoke(review, ["--files", "test.py"])

        # Exit code 1 because overall_passed is False (quality_passed=False)
        assert result.exit_code == 1

    @patch("zerg.commands.review._collect_files")
    @patch("zerg.commands.review.ReviewCommand")
    @patch("zerg.commands.review.console")
    def test_review_with_many_issues(
        self,
        mock_console: MagicMock,
        mock_command_class: MagicMock,
        mock_collect: MagicMock,
    ) -> None:
        """Test review with many issues shows limited."""
        mock_collect.return_value = ["test.py"]
        items = [
            ReviewItem(
                category="debug",
                severity="warning",
                file=f"test{i}.py",
                line=i,
                message=f"Debug {i}",
            )
            for i in range(10)
        ]
        mock_command = MagicMock()
        mock_command.run.return_value = ReviewResult(
            files_reviewed=10,
            items=items,
            spec_passed=True,
            quality_passed=True,
        )
        mock_command.checklist.get_items.return_value = []
        mock_command_class.return_value = mock_command

        runner = CliRunner()
        result = runner.invoke(review, ["--files", "test.py"])

        assert result.exit_code == 0

    @patch("zerg.commands.review._collect_files")
    @patch("zerg.commands.review.ReviewCommand")
    @patch("zerg.commands.review.console")
    @patch("zerg.commands.review.Path")
    def test_review_writes_output_file(
        self,
        mock_path_class: MagicMock,
        mock_console: MagicMock,
        mock_command_class: MagicMock,
        mock_collect: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test review writes to output file."""
        mock_collect.return_value = ["test.py"]
        mock_command = MagicMock()
        mock_command.run.return_value = ReviewResult(
            files_reviewed=1,
            items=[],
            spec_passed=True,
            quality_passed=True,
        )
        mock_command.format_result.return_value = "Review results"
        mock_command.checklist.get_items.return_value = []
        mock_command_class.return_value = mock_command

        # Set up mock path for output file write
        mock_output_path = MagicMock()
        mock_path_class.return_value = mock_output_path

        runner = CliRunner()
        result = runner.invoke(review, ["--files", "test.py", "--output", "/tmp/review.txt"])

        assert result.exit_code == 0
        mock_output_path.write_text.assert_called_once()

    @patch("zerg.commands.review.console")
    def test_review_keyboard_interrupt(self, mock_console: MagicMock) -> None:
        """Test review handles KeyboardInterrupt."""
        with patch(
            "zerg.commands.review._collect_files",
            side_effect=KeyboardInterrupt,
        ):
            runner = CliRunner()
            result = runner.invoke(review, [])

            assert result.exit_code == 130

    @patch("zerg.commands.review.console")
    def test_review_generic_exception(self, mock_console: MagicMock) -> None:
        """Test review handles generic exception."""
        with patch(
            "zerg.commands.review._collect_files",
            side_effect=RuntimeError("Unexpected error"),
        ):
            runner = CliRunner()
            result = runner.invoke(review, [])

            assert result.exit_code == 1

    @patch("zerg.commands.review._collect_files")
    @patch("zerg.commands.review.ReviewCommand")
    @patch("zerg.commands.review.console")
    def test_review_prepare_mode(
        self,
        mock_console: MagicMock,
        mock_command_class: MagicMock,
        mock_collect: MagicMock,
    ) -> None:
        """Test review in prepare mode."""
        mock_collect.return_value = ["test.py"]
        mock_command = MagicMock()
        mock_command.run.return_value = ReviewResult(
            files_reviewed=1,
            items=[],
            spec_passed=True,
            quality_passed=True,
        )
        mock_command.checklist.get_items.return_value = []
        mock_command_class.return_value = mock_command

        runner = CliRunner()
        result = runner.invoke(review, ["--mode", "prepare", "--files", "test.py"])

        assert result.exit_code == 0

    @patch("zerg.commands.review._collect_files")
    @patch("zerg.commands.review.ReviewCommand")
    @patch("zerg.commands.review.console")
    def test_review_receive_mode(
        self,
        mock_console: MagicMock,
        mock_command_class: MagicMock,
        mock_collect: MagicMock,
    ) -> None:
        """Test review in receive mode."""
        mock_collect.return_value = ["test.py"]
        mock_command = MagicMock()
        mock_command.run.return_value = ReviewResult(
            files_reviewed=1,
            items=[],
            spec_passed=True,
            quality_passed=True,
        )
        mock_command.checklist.get_items.return_value = []
        mock_command_class.return_value = mock_command

        runner = CliRunner()
        result = runner.invoke(review, ["--mode", "receive", "--files", "test.py"])

        assert result.exit_code == 0
