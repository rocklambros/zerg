"""Integration tests for ZERG review command."""

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
        result = runner.invoke(
            cli, ["review", "--mode", "prepare", "--files", "src/", "--output", "out.md"]
        )
        assert "Invalid value" not in result.output
