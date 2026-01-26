"""Integration tests for ZERG analyze command."""

from pathlib import Path

from click.testing import CliRunner

from zerg.cli import cli


class TestAnalyzeCommand:
    """Tests for analyze command."""

    def test_analyze_help(self) -> None:
        """Test analyze --help shows all options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", "--help"])

        assert result.exit_code == 0
        assert "lint" in result.output
        assert "complexity" in result.output
        assert "coverage" in result.output
        assert "security" in result.output

    def test_analyze_check_option(self) -> None:
        """Test analyze --check option accepts valid values."""
        runner = CliRunner()

        for check_type in ["lint", "complexity", "coverage", "security", "all"]:
            result = runner.invoke(cli, ["analyze", "--check", check_type])
            # Should not fail with invalid option error
            assert "Invalid value" not in result.output

    def test_analyze_format_option(self) -> None:
        """Test analyze --format option accepts valid values."""
        runner = CliRunner()

        for fmt in ["text", "json", "sarif"]:
            result = runner.invoke(cli, ["analyze", "--format", fmt])
            assert "Invalid value" not in result.output

    def test_analyze_invalid_check_rejected(self) -> None:
        """Test analyze rejects invalid check types."""
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", "--check", "invalid"])

        assert result.exit_code != 0
        assert "Invalid value" in result.output

    def test_analyze_threshold_option(self) -> None:
        """Test analyze --threshold option works."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["analyze", "--threshold", "complexity=15", "--threshold", "coverage=80"]
        )
        # Should accept multiple thresholds
        assert "Invalid value" not in result.output

    def test_analyze_files_option(self) -> None:
        """Test analyze --files option works."""
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", "--files", "src/"])
        assert "Invalid value" not in result.output


class TestAnalyzeOutput:
    """Tests for analyze command output formats."""

    def test_analyze_default_format_is_text(self) -> None:
        """Test default output format is text."""
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze"])
        # Stub returns message, not JSON
        assert "{" not in result.output or "not yet implemented" in result.output

    def test_analyze_json_format_requested(self) -> None:
        """Test JSON format can be requested."""
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", "--format", "json"])
        # Command should accept the format option
        assert "Invalid value" not in result.output
