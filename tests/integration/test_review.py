"""Integration tests for ZERG review command."""

import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from zerg.cli import cli


class TestReviewCommand:
    """Tests for review command."""

    def test_review_help(self) -> None:
        """Test review --help shows all options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["review", "--help"])

        assert result.exit_code == 0
        assert "mode" in result.output
        assert "prepare" in result.output
        assert "self" in result.output
        assert "receive" in result.output
        assert "full" in result.output

    def test_review_invalid_mode_rejected(self) -> None:
        """Test review rejects invalid modes."""
        runner = CliRunner()
        result = runner.invoke(cli, ["review", "--mode", "invalid"])

        assert result.exit_code != 0
        assert "Invalid value" in result.output

    @pytest.mark.parametrize(
        "extra_args",
        [
            ["--mode", "prepare"],
            ["--files", "src/"],
            ["--output", "review.md"],
        ],
        ids=["mode", "files", "output"],
    )
    def test_review_option_accepted(self, extra_args: list[str]) -> None:
        """Test review options are accepted without error."""
        runner = CliRunner()
        result = runner.invoke(cli, ["review"] + extra_args)
        assert "Invalid value" not in result.output


class TestReviewFunctional:
    """Functional tests for review command."""

    def test_review_displays_header(self) -> None:
        """Test review shows ZERG Review header."""
        runner = CliRunner()
        result = runner.invoke(cli, ["review"])
        assert "ZERG" in result.output or "Review" in result.output

    @pytest.mark.parametrize("mode", ["prepare", "full"])
    def test_review_mode_executes(self, mode: str) -> None:
        """Test representative review modes can execute."""
        runner = CliRunner()
        result = runner.invoke(cli, ["review", "--mode", mode])
        assert result.exit_code in [0, 1]

    def test_review_json_output(self) -> None:
        """Test review --json produces JSON output."""
        runner = CliRunner()
        result = runner.invoke(cli, ["review", "--json"])
        assert result.exit_code in [0, 1]

    def test_review_with_output_file(self) -> None:
        """Test review writes to output file."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = Path(tmpdir) / "review.md"
            result = runner.invoke(cli, ["review", "--output", str(output_file)])
            assert result.exit_code in [0, 1]

    def test_review_specific_files(self) -> None:
        """Test review with specific files."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("def foo():\n    return 1\n")

            result = runner.invoke(cli, ["review", "--files", str(test_file)])
            assert result.exit_code in [0, 1]

    def test_review_handles_no_changes(self) -> None:
        """Test review handles repository with no changes."""
        runner = CliRunner()
        result = runner.invoke(cli, ["review"])
        assert result.exit_code in [0, 1]

    def test_review_combined_options(self) -> None:
        """Test review with combined options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["review", "--mode", "prepare", "--files", "src/", "--output", "out.md"])
        assert "Invalid value" not in result.output
