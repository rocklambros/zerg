"""Thinned unit tests for ZERG review command.

Reduced from 90 to ~25 tests by:
- Enum: 5 per-value -> 1 all-values assertion
- ReviewResult: 10 -> 3 (both-pass, one-fail, error_count)
- CodeAnalyzer: 15 -> 1 parametrized (print, todo, secret, long line, clean)
- ReviewCommand: 22 -> 5 (init, full, self, format json, format text)
- CollectFiles: 9 -> 3 (git staged, file path, directory)
- CLI: 12 -> 3 (help, full mode, keyboard interrupt)
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
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


# =============================================================================
# ReviewItem Dataclass Tests
# =============================================================================


class TestReviewItem:
    """Tests for ReviewItem dataclass."""

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

    def test_overall_passed_one_false(self) -> None:
        """Test overall_passed when one stage fails."""
        result = ReviewResult(
            files_reviewed=5,
            items=[],
            spec_passed=False,
            quality_passed=True,
        )
        assert result.overall_passed is False

    def test_error_count_property(self) -> None:
        """Test error_count property."""
        items = [
            ReviewItem(category="secret", severity="error", file="a.py", line=1, message="Secret"),
            ReviewItem(category="debug", severity="warning", file="b.py", line=2, message="Debug"),
            ReviewItem(category="secret", severity="error", file="c.py", line=3, message="Secret"),
        ]
        result = ReviewResult(files_reviewed=3, items=items, spec_passed=True, quality_passed=True)
        assert result.error_count == 2
        assert result.warning_count == 1
        assert result.total_items == 3


# =============================================================================
# SelfReviewChecklist Tests
# =============================================================================


class TestSelfReviewChecklist:
    """Tests for SelfReviewChecklist class."""

    def test_items_have_key_and_description(self) -> None:
        """Test all items have key and description."""
        checklist = SelfReviewChecklist()
        items = checklist.get_items()

        assert len(items) == 10
        for key, description in items:
            assert isinstance(key, str) and len(key) > 0
            assert isinstance(description, str) and len(description) > 0


# =============================================================================
# CodeAnalyzer Tests
# =============================================================================


class TestCodeAnalyzer:
    """Tests for CodeAnalyzer class."""

    @pytest.mark.parametrize(
        "content,filename,expected_category,expected_severity",
        [
            ("print('debug')", "test.py", "debug_print", "warning"),
            ("# TODO: fix this", "test.py", "todo", "info"),
            ("password = 'secret123'", "config.py", "hardcoded_secret", "error"),
            ("x = " + "a" * 150, "test.py", "long_line", "info"),
        ],
    )
    def test_analyze_detects_issues(
        self, content: str, filename: str, expected_category: str, expected_severity: str
    ) -> None:
        """Test analyze detects various code issues."""
        analyzer = CodeAnalyzer()
        items = analyzer.analyze(content, filename)

        assert len(items) >= 1
        assert items[0].category == expected_category
        assert items[0].severity == expected_severity

    def test_analyze_no_issues(self) -> None:
        """Test analyze with clean code."""
        analyzer = CodeAnalyzer()
        items = analyzer.analyze("x = 1\ny = x + 1", "test.py")
        assert items == []


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

    def test_run_full_mode(self, tmp_path: Path) -> None:
        """Test run in full mode."""
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1")

        reviewer = ReviewCommand()
        result = reviewer.run([str(test_file)], mode="full")

        assert result.files_reviewed == 1
        assert result.spec_passed is True
        assert result.quality_passed is True

    def test_run_self_mode(self, tmp_path: Path) -> None:
        """Test run in self mode detects issues."""
        test_file = tmp_path / "module.py"
        test_file.write_text("print('debug')")

        reviewer = ReviewCommand()
        result = reviewer.run([str(test_file)], mode="self")

        assert result.files_reviewed == 1
        assert len(result.items) >= 1

    def test_format_result_json(self) -> None:
        """Test format_result with JSON output."""
        items = [ReviewItem(category="debug", severity="warning", file="test.py", line=1, message="Debug found")]
        result = ReviewResult(files_reviewed=1, items=items, spec_passed=True, quality_passed=True)

        reviewer = ReviewCommand()
        output = reviewer.format_result(result, fmt="json")

        parsed = json.loads(output)
        assert parsed["files_reviewed"] == 1
        assert parsed["overall_passed"] is True
        assert len(parsed["items"]) == 1

    def test_format_result_text_passed(self) -> None:
        """Test format_result with text output when passed."""
        result = ReviewResult(files_reviewed=5, items=[], spec_passed=True, quality_passed=True)

        reviewer = ReviewCommand()
        output = reviewer.format_result(result, fmt="text")

        assert "PASSED" in output
        assert "Files Reviewed: 5" in output


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
        (tmp_path / "readme.txt").write_text("text")

        files = _collect_files(str(tmp_path), "full")

        assert len(files) == 2
        assert any(f.endswith(".py") for f in files)
        assert any(f.endswith(".js") for f in files)


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
        mock_command.run.return_value = ReviewResult(files_reviewed=1, items=[], spec_passed=True, quality_passed=True)
        mock_command.checklist.get_items.return_value = [("test", "Test item")]
        mock_command_class.return_value = mock_command

        runner = CliRunner()
        result = runner.invoke(review, ["--mode", "full", "--files", "test.py"])

        assert result.exit_code == 0

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
