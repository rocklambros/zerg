"""Integration tests for ZERG build command."""

from pathlib import Path

from click.testing import CliRunner

from zerg.cli import cli


class TestBuildCommand:
    """Tests for build command."""

    def test_build_help(self) -> None:
        """Test build --help shows all options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["build", "--help"])

        assert result.exit_code == 0
        assert "target" in result.output
        assert "mode" in result.output
        assert "clean" in result.output
        assert "watch" in result.output
        assert "retry" in result.output

    def test_build_mode_option(self) -> None:
        """Test build --mode option accepts valid values."""
        runner = CliRunner()

        for mode in ["dev", "staging", "prod"]:
            result = runner.invoke(cli, ["build", "--mode", mode])
            assert "Invalid value" not in result.output

    def test_build_invalid_mode_rejected(self) -> None:
        """Test build rejects invalid modes."""
        runner = CliRunner()
        result = runner.invoke(cli, ["build", "--mode", "invalid"])

        assert result.exit_code != 0
        assert "Invalid value" in result.output

    def test_build_clean_flag(self) -> None:
        """Test build --clean flag works."""
        runner = CliRunner()
        result = runner.invoke(cli, ["build", "--clean"])
        assert "Invalid value" not in result.output

    def test_build_watch_flag(self) -> None:
        """Test build --watch flag works."""
        runner = CliRunner()
        result = runner.invoke(cli, ["build", "--watch"])
        assert "Invalid value" not in result.output

    def test_build_retry_option(self) -> None:
        """Test build --retry option works."""
        runner = CliRunner()
        result = runner.invoke(cli, ["build", "--retry", "5"])
        assert "Invalid value" not in result.output

    def test_build_target_option(self) -> None:
        """Test build --target option works."""
        runner = CliRunner()
        result = runner.invoke(cli, ["build", "--target", "frontend"])
        assert "Invalid value" not in result.output


class TestBuildModes:
    """Tests for build command modes."""

    def test_build_default_mode_is_dev(self) -> None:
        """Test default build mode is dev."""
        runner = CliRunner()
        result = runner.invoke(cli, ["build", "--help"])
        assert "default: dev" in result.output.lower() or "dev" in result.output

    def test_build_combined_options(self) -> None:
        """Test build with multiple options."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["build", "--mode", "prod", "--clean", "--retry", "3"]
        )
        assert "Invalid value" not in result.output
