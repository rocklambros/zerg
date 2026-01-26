"""Integration tests for ZERG refactor command."""

from pathlib import Path

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

    def test_refactor_transforms_option(self) -> None:
        """Test refactor --transforms option works."""
        runner = CliRunner()
        result = runner.invoke(cli, ["refactor", "--transforms", "dead-code,simplify"])
        assert "Invalid value" not in result.output

    def test_refactor_all_transforms(self) -> None:
        """Test refactor with all transforms."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["refactor", "--transforms", "dead-code,simplify,types,patterns,naming"]
        )
        assert "Invalid value" not in result.output

    def test_refactor_dry_run_flag(self) -> None:
        """Test refactor --dry-run flag works."""
        runner = CliRunner()
        result = runner.invoke(cli, ["refactor", "--dry-run"])
        assert "Invalid value" not in result.output

    def test_refactor_interactive_flag(self) -> None:
        """Test refactor --interactive flag works."""
        runner = CliRunner()
        result = runner.invoke(cli, ["refactor", "--interactive"])
        assert "Invalid value" not in result.output

    def test_refactor_files_option(self) -> None:
        """Test refactor --files option works."""
        runner = CliRunner()
        result = runner.invoke(cli, ["refactor", "--files", "src/"])
        assert "Invalid value" not in result.output


class TestRefactorTransforms:
    """Tests for refactor transforms."""

    def test_refactor_default_transforms(self) -> None:
        """Test default transforms are dead-code,simplify."""
        runner = CliRunner()
        result = runner.invoke(cli, ["refactor", "--help"])
        assert "dead-code" in result.output and "simplify" in result.output

    def test_refactor_combined_options(self) -> None:
        """Test refactor with combined options."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["refactor", "--transforms", "types,naming", "--dry-run", "--files", "src/"],
        )
        assert "Invalid value" not in result.output

    def test_refactor_single_transform(self) -> None:
        """Test refactor with single transform."""
        runner = CliRunner()
        result = runner.invoke(cli, ["refactor", "--transforms", "dead-code"])
        assert "Invalid value" not in result.output
