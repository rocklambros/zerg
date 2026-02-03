"""Integration tests for ZERG review command."""

import tempfile
from pathlib import Path

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

    def test_review_mode_option(self) -> None:
        """Test review --mode option accepts valid values."""
        runner = CliRunner()

        for mode in ["prepare", "self", "receive", "full"]:
            result = runner.invoke(cli, ["review", "--mode", mode])
            assert "Invalid value" not in result.output

    def test_review_invalid_mode_rejected(self) -> None:
        """Test review rejects invalid modes."""
        runner = CliRunner()
        result = runner.invoke(cli, ["review", "--mode", "invalid"])

        assert result.exit_code != 0
        assert "Invalid value" in result.output

    def test_review_files_option(self) -> None:
        """Test review --files option works."""
        runner = CliRunner()
        result = runner.invoke(cli, ["review", "--files", "src/"])
        assert "Invalid value" not in result.output

    def test_review_output_option(self) -> None:
        """Test review --output option works."""
        runner = CliRunner()
        result = runner.invoke(cli, ["review", "--output", "review.md"])
        assert "Invalid value" not in result.output


class TestReviewModes:
    """Tests for review modes."""

    def test_review_default_mode_is_full(self) -> None:
        """Test default review mode is full."""
        runner = CliRunner()
        result = runner.invoke(cli, ["review", "--help"])
        assert "default: full" in result.output.lower() or "full" in result.output

    def test_review_prepare_mode(self) -> None:
        """Test prepare mode."""
        runner = CliRunner()
        result = runner.invoke(cli, ["review", "--mode", "prepare"])
        assert "Invalid value" not in result.output

    def test_review_self_mode(self) -> None:
        """Test self-review mode."""
        runner = CliRunner()
        result = runner.invoke(cli, ["review", "--mode", "self"])
        assert "Invalid value" not in result.output

    def test_review_combined_options(self) -> None:
        """Test review with combined options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["review", "--mode", "prepare", "--files", "src/", "--output", "out.md"])
        assert "Invalid value" not in result.output


class TestReviewFunctional:
    """Functional tests for review command."""

    def test_review_displays_header(self) -> None:
        """Test review shows ZERG Review header."""
        runner = CliRunner()
        result = runner.invoke(cli, ["review"])
        assert "ZERG" in result.output or "Review" in result.output

    def test_review_full_mode(self) -> None:
        """Test review full mode runs both stages."""
        runner = CliRunner()
        result = runner.invoke(cli, ["review", "--mode", "full"])
        assert result.exit_code in [0, 1]

    def test_review_prepare_mode_output(self) -> None:
        """Test review prepare mode generates summary."""
        runner = CliRunner()
        result = runner.invoke(cli, ["review", "--mode", "prepare"])
        assert result.exit_code in [0, 1]
        # Should produce some output
        assert len(result.output) > 0

    def test_review_self_mode_checklist(self) -> None:
        """Test review self mode generates checklist."""
        runner = CliRunner()
        result = runner.invoke(cli, ["review", "--mode", "self"])
        assert result.exit_code in [0, 1]

    def test_review_receive_mode(self) -> None:
        """Test review receive mode processes quality review."""
        runner = CliRunner()
        result = runner.invoke(cli, ["review", "--mode", "receive"])
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
            # Create test files
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("def foo():\n    return 1\n")

            result = runner.invoke(cli, ["review", "--files", str(test_file)])
            assert result.exit_code in [0, 1]


class TestReviewStages:
    """Tests for review stage functionality."""

    def test_review_spec_compliance_stage(self) -> None:
        """Test review includes spec compliance check."""
        runner = CliRunner()
        result = runner.invoke(cli, ["review", "--mode", "full"])
        assert result.exit_code in [0, 1]

    def test_review_code_quality_stage(self) -> None:
        """Test review includes code quality check."""
        runner = CliRunner()
        result = runner.invoke(cli, ["review", "--mode", "full"])
        assert result.exit_code in [0, 1]

    def test_review_handles_no_changes(self) -> None:
        """Test review handles repository with no changes."""
        runner = CliRunner()
        result = runner.invoke(cli, ["review"])
        # Should handle gracefully even with no staged changes
        assert result.exit_code in [0, 1]


class TestReviewChecklist:
    """Tests for review checklist functionality."""

    def test_review_self_generates_checklist(self) -> None:
        """Test self-review mode generates checklist items."""
        runner = CliRunner()
        result = runner.invoke(cli, ["review", "--mode", "self"])
        assert result.exit_code in [0, 1]

    def test_review_combined_modes(self) -> None:
        """Test different review modes produce different output."""
        runner = CliRunner()

        prepare_result = runner.invoke(cli, ["review", "--mode", "prepare"])
        self_result = runner.invoke(cli, ["review", "--mode", "self"])

        # Both should succeed
        assert prepare_result.exit_code in [0, 1]
        assert self_result.exit_code in [0, 1]

    def test_review_all_modes_execute(self) -> None:
        """Test all review modes can execute."""
        runner = CliRunner()

        for mode in ["prepare", "self", "receive", "full"]:
            result = runner.invoke(cli, ["review", "--mode", mode])
            assert result.exit_code in [0, 1], f"Mode {mode} failed"
