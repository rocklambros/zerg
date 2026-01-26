"""Integration tests for ZERG troubleshoot command."""

from pathlib import Path

from click.testing import CliRunner

from zerg.cli import cli


class TestTroubleshootCommand:
    """Tests for troubleshoot command."""

    def test_troubleshoot_help(self) -> None:
        """Test troubleshoot --help shows all options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["troubleshoot", "--help"])

        assert result.exit_code == 0
        assert "error" in result.output
        assert "stacktrace" in result.output
        assert "verbose" in result.output

    def test_troubleshoot_error_option(self) -> None:
        """Test troubleshoot --error option works."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["troubleshoot", "--error", "ValueError: invalid literal"]
        )
        assert "Invalid value" not in result.output

    def test_troubleshoot_stacktrace_option(self) -> None:
        """Test troubleshoot --stacktrace option works."""
        runner = CliRunner()
        result = runner.invoke(cli, ["troubleshoot", "--stacktrace", "trace.txt"])
        assert "Invalid value" not in result.output

    def test_troubleshoot_verbose_flag(self) -> None:
        """Test troubleshoot --verbose flag works."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["troubleshoot", "--error", "Error", "--verbose"]
        )
        assert "Invalid value" not in result.output

    def test_troubleshoot_output_option(self) -> None:
        """Test troubleshoot --output option works."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["troubleshoot", "--error", "Error", "--output", "report.md"]
        )
        assert "Invalid value" not in result.output


class TestTroubleshootCombinations:
    """Tests for troubleshoot option combinations."""

    def test_troubleshoot_error_and_verbose(self) -> None:
        """Test troubleshoot with error and verbose."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["troubleshoot", "--error", "ImportError: No module", "--verbose"]
        )
        assert "Invalid value" not in result.output

    def test_troubleshoot_all_options(self) -> None:
        """Test troubleshoot with all options."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "troubleshoot",
                "--error",
                "Error message",
                "--stacktrace",
                "trace.txt",
                "--verbose",
                "--output",
                "report.md",
            ],
        )
        assert "Invalid value" not in result.output

    def test_troubleshoot_no_options(self) -> None:
        """Test troubleshoot without options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["troubleshoot"])
        # Should work (might fail at runtime but not at option parsing)
        assert "Invalid value" not in result.output

    def test_troubleshoot_error_with_special_chars(self) -> None:
        """Test troubleshoot with special characters in error."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["troubleshoot", "--error", "Error: 'foo' != \"bar\""]
        )
        assert "Invalid value" not in result.output
