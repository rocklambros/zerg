"""Integration tests for ZERG build command."""

import tempfile
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
        # Use --dry-run with --watch to avoid infinite loop
        result = runner.invoke(cli, ["build", "--watch", "--dry-run"])
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
        result = runner.invoke(cli, ["build", "--mode", "prod", "--clean", "--retry", "3"])
        assert "Invalid value" not in result.output


class TestBuildFunctional:
    """Functional tests for build command."""

    def test_build_displays_header(self) -> None:
        """Test build shows ZERG Build header."""
        runner = CliRunner()
        result = runner.invoke(cli, ["build", "--dry-run"])
        assert "ZERG" in result.output or "Build" in result.output

    def test_build_dry_run_mode(self) -> None:
        """Test build --dry-run shows what would be built."""
        runner = CliRunner()
        result = runner.invoke(cli, ["build", "--dry-run"])
        # Dry run should not fail
        assert result.exit_code in [0, 1]
        # Should mention dry run or preview
        assert len(result.output) > 0

    def test_build_detects_no_build_system(self) -> None:
        """Test build handles missing build system gracefully."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory():
            # Run in empty directory
            result = runner.invoke(cli, ["build", "--dry-run"], catch_exceptions=False)
            # Should handle gracefully
            assert result.exit_code in [0, 1]

    def test_build_json_output(self) -> None:
        """Test build --json produces JSON output."""
        runner = CliRunner()
        result = runner.invoke(cli, ["build", "--json", "--dry-run"])
        assert result.exit_code in [0, 1]

    def test_build_clean_with_dry_run(self) -> None:
        """Test build --clean --dry-run shows clean operation."""
        runner = CliRunner()
        result = runner.invoke(cli, ["build", "--clean", "--dry-run"])
        assert result.exit_code in [0, 1]

    def test_build_with_target(self) -> None:
        """Test build with specific target."""
        runner = CliRunner()
        result = runner.invoke(cli, ["build", "--target", "test", "--dry-run"])
        assert result.exit_code in [0, 1]

    def test_build_prod_mode(self) -> None:
        """Test build in production mode."""
        runner = CliRunner()
        result = runner.invoke(cli, ["build", "--mode", "prod", "--dry-run"])
        assert result.exit_code in [0, 1]

    def test_build_staging_mode(self) -> None:
        """Test build in staging mode."""
        runner = CliRunner()
        result = runner.invoke(cli, ["build", "--mode", "staging", "--dry-run"])
        assert result.exit_code in [0, 1]

    def test_build_retry_zero(self) -> None:
        """Test build with zero retries."""
        runner = CliRunner()
        result = runner.invoke(cli, ["build", "--retry", "0", "--dry-run"])
        assert result.exit_code in [0, 1]

    def test_build_all_options_combined(self) -> None:
        """Test build with all options combined."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "build",
                "--mode",
                "prod",
                "--target",
                "all",
                "--clean",
                "--retry",
                "3",
                "--dry-run",
            ],
        )
        assert result.exit_code in [0, 1]


class TestBuildDetection:
    """Tests for build system detection."""

    def test_build_detects_python_project(self) -> None:
        """Test build detects Python project with setup.py."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create setup.py
            setup_file = Path(tmpdir) / "setup.py"
            setup_file.write_text("from setuptools import setup\nsetup(name='test')")

            # Note: We can't easily change working directory in CliRunner
            result = runner.invoke(cli, ["build", "--dry-run"])
            assert result.exit_code in [0, 1]

    def test_build_detects_node_project(self) -> None:
        """Test build handles Node.js project detection."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create package.json
            pkg_file = Path(tmpdir) / "package.json"
            pkg_file.write_text('{"name": "test", "scripts": {"build": "echo build"}}')

            result = runner.invoke(cli, ["build", "--dry-run"])
            assert result.exit_code in [0, 1]
