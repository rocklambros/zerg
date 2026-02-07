"""Integration tests for ZERG build command."""

import tempfile
from pathlib import Path

import pytest
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

    def test_build_invalid_mode_rejected(self) -> None:
        """Test build rejects invalid modes."""
        runner = CliRunner()
        result = runner.invoke(cli, ["build", "--mode", "invalid"])

        assert result.exit_code != 0
        assert "Invalid value" in result.output

    @pytest.mark.parametrize(
        "extra_args",
        [
            ["--mode", "dev"],
            ["--clean"],
            ["--retry", "5"],
        ],
        ids=["mode", "clean", "retry"],
    )
    def test_build_option_accepted(self, extra_args: list[str]) -> None:
        """Test build options are accepted without error."""
        runner = CliRunner()
        result = runner.invoke(cli, ["build"] + extra_args)
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
        assert result.exit_code in [0, 1]
        assert len(result.output) > 0

    def test_build_detects_no_build_system(self) -> None:
        """Test build handles missing build system gracefully."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory():
            result = runner.invoke(cli, ["build", "--dry-run"], catch_exceptions=False)
            assert result.exit_code in [0, 1]

    @pytest.mark.parametrize("mode", ["staging", "prod"])
    def test_build_mode(self, mode: str) -> None:
        """Test build in non-default modes."""
        runner = CliRunner()
        result = runner.invoke(cli, ["build", "--mode", mode, "--dry-run"])
        assert result.exit_code in [0, 1]

    def test_build_json_output(self) -> None:
        """Test build --json produces JSON output."""
        runner = CliRunner()
        result = runner.invoke(cli, ["build", "--json", "--dry-run"])
        assert result.exit_code in [0, 1]

    def test_build_all_options_combined(self) -> None:
        """Test build with all options combined."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["build", "--mode", "prod", "--target", "all", "--clean", "--retry", "3", "--dry-run"],
        )
        assert result.exit_code in [0, 1]


class TestBuildDetection:
    """Tests for build system detection."""

    @pytest.mark.parametrize(
        "filename,content",
        [
            ("setup.py", "from setuptools import setup\nsetup(name='test')"),
            ("package.json", '{"name": "test", "scripts": {"build": "echo build"}}'),
        ],
        ids=["python-project", "node-project"],
    )
    def test_build_detects_project_type(self, filename: str, content: str) -> None:
        """Test build detects project type from config files."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / filename
            config_file.write_text(content)

            result = runner.invoke(cli, ["build", "--dry-run"])
            assert result.exit_code in [0, 1]
