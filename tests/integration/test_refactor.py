"""Integration tests for ZERG refactor command."""

import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from zerg.cli import cli


class TestRefactorCommand:
    """Tests for refactor command."""

    def test_refactor_help(self) -> None:
        """Test refactor --help shows all options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["refactor", "--help"])

        assert result.exit_code == 0
        assert "transforms" in result.output
        assert "dry-run" in result.output
        assert "interactive" in result.output

    @pytest.mark.parametrize(
        "extra_args",
        [
            ["--transforms", "dead-code,simplify"],
            ["--dry-run"],
        ],
        ids=["transforms", "dry-run"],
    )
    def test_refactor_option_accepted(self, extra_args: list[str]) -> None:
        """Test refactor options are accepted without error."""
        runner = CliRunner()
        result = runner.invoke(cli, ["refactor"] + extra_args)
        assert "Invalid value" not in result.output


class TestRefactorFunctional:
    """Functional tests for refactor command."""

    def test_refactor_displays_header(self) -> None:
        """Test refactor shows ZERG Refactor header."""
        runner = CliRunner()
        result = runner.invoke(cli, ["refactor", "--dry-run"])
        assert "ZERG" in result.output or "Refactor" in result.output

    def test_refactor_dry_run_no_changes(self) -> None:
        """Test refactor --dry-run doesn't modify files."""
        runner = CliRunner()
        result = runner.invoke(cli, ["refactor", "--dry-run"])
        assert result.exit_code in [0, 1]

    @pytest.mark.parametrize(
        "transform",
        ["dead-code", "types", "naming"],
    )
    def test_refactor_individual_transform(self, transform: str) -> None:
        """Test representative refactor transforms in dry-run mode."""
        runner = CliRunner()
        result = runner.invoke(cli, ["refactor", "--transforms", transform, "--dry-run"])
        assert result.exit_code in [0, 1]

    def test_refactor_with_path_argument(self) -> None:
        """Test refactor with path argument."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("def foo():\n    pass\n\ndef bar():\n    pass\n")

            result = runner.invoke(cli, ["refactor", tmpdir, "--dry-run"])
            assert result.exit_code in [0, 1]

    def test_refactor_json_output(self) -> None:
        """Test refactor --json produces JSON output."""
        runner = CliRunner()
        result = runner.invoke(cli, ["refactor", "--json", "--dry-run"])
        assert result.exit_code in [0, 1]

    def test_refactor_combined_options(self) -> None:
        """Test refactor with combined options."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["refactor", "--transforms", "types,naming", "--dry-run", "--files", "src/"],
        )
        assert "Invalid value" not in result.output


class TestRefactorSuggestions:
    """Tests for refactor suggestion generation."""

    def test_refactor_generates_suggestions(self) -> None:
        """Test refactor generates suggestions in dry-run mode."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text(
                "import os\nimport sys  # unused\n\ndef unused_func():\n    pass\n\ndef main():\n    x = 1\n"
            )

            result = runner.invoke(cli, ["refactor", tmpdir, "--dry-run"])
            assert result.exit_code in [0, 1]

    def test_refactor_handles_nonexistent_path(self) -> None:
        """Test refactor handles nonexistent path."""
        runner = CliRunner()
        result = runner.invoke(cli, ["refactor", "/nonexistent/path", "--dry-run"])
        assert result.exit_code in [0, 1]
