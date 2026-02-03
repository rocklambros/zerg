"""Unit tests for ZERG CLI module."""

from click.testing import CliRunner

from zerg.cli import cli


class TestCliGroup:
    """Tests for main CLI group."""

    def test_cli_help(self) -> None:
        """Test CLI shows help with all commands."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "ZERG" in result.output
        assert "Parallel Claude Code" in result.output

    def test_cli_version(self) -> None:
        """Test CLI shows version."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])

        assert result.exit_code == 0
        assert "zerg" in result.output.lower()

    def test_cli_verbose_flag_removed(self) -> None:
        """Test that removed --verbose flag is rejected."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--verbose", "--help"])

        assert result.exit_code == 2  # Click rejects unknown option

    def test_cli_quiet_flag_removed(self) -> None:
        """Test that removed --quiet flag is rejected."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--quiet", "--help"])

        assert result.exit_code == 2  # Click rejects unknown option


class TestCommandRegistration:
    """Tests for command registration."""

    def test_all_commands_registered(self) -> None:
        """Test all expected commands are registered."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        expected_commands = [
            "analyze",
            "build",
            "cleanup",
            "design",
            "git",
            "init",
            "logs",
            "merge",
            "plan",
            "refactor",
            "retry",
            "review",
            "rush",
            "security-rules",
            "status",
            "stop",
            "test",
            "debug",
        ]

        for cmd in expected_commands:
            assert cmd in result.output, f"Command {cmd} not found in CLI help"

    def test_command_help_available(self) -> None:
        """Test each command has help available."""
        runner = CliRunner()

        commands = ["analyze", "build", "git", "refactor", "review", "test", "debug"]

        for cmd in commands:
            result = runner.invoke(cli, [cmd, "--help"])
            assert result.exit_code == 0, f"Command {cmd} --help failed"
            assert "Usage:" in result.output, f"Command {cmd} missing usage info"


class TestCliContext:
    """Tests for CLI context handling."""

    def test_context_created(self) -> None:
        """Test CLI creates context object."""
        runner = CliRunner()
        # Context is created when any command runs
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0

    def test_verbose_removed_from_context(self) -> None:
        """Test verbose flag no longer accepted."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--verbose", "--help"])
        assert result.exit_code == 2

    def test_quiet_removed_from_context(self) -> None:
        """Test quiet flag no longer accepted."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--quiet", "--help"])
        assert result.exit_code == 2
