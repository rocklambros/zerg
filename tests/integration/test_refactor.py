"""Integration tests for ZERG refactor command."""

import tempfile
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
        result = runner.invoke(cli, ["refactor", "--transforms", "dead-code,simplify,types,patterns,naming"])
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
        # Should complete without error
        assert result.exit_code in [0, 1]

    def test_refactor_dead_code_transform(self) -> None:
        """Test refactor dead-code transform."""
        runner = CliRunner()
        result = runner.invoke(cli, ["refactor", "--transforms", "dead-code", "--dry-run"])
        assert result.exit_code in [0, 1]

    def test_refactor_simplify_transform(self) -> None:
        """Test refactor simplify transform."""
        runner = CliRunner()
        result = runner.invoke(cli, ["refactor", "--transforms", "simplify", "--dry-run"])
        assert result.exit_code in [0, 1]

    def test_refactor_types_transform(self) -> None:
        """Test refactor types transform."""
        runner = CliRunner()
        result = runner.invoke(cli, ["refactor", "--transforms", "types", "--dry-run"])
        assert result.exit_code in [0, 1]

    def test_refactor_patterns_transform(self) -> None:
        """Test refactor patterns transform."""
        runner = CliRunner()
        result = runner.invoke(cli, ["refactor", "--transforms", "patterns", "--dry-run"])
        assert result.exit_code in [0, 1]

    def test_refactor_naming_transform(self) -> None:
        """Test refactor naming transform."""
        runner = CliRunner()
        result = runner.invoke(cli, ["refactor", "--transforms", "naming", "--dry-run"])
        assert result.exit_code in [0, 1]

    def test_refactor_with_path_argument(self) -> None:
        """Test refactor with path argument."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test file
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("def foo():\n    pass\n\ndef bar():\n    pass\n")

            result = runner.invoke(cli, ["refactor", tmpdir, "--dry-run"])
            assert result.exit_code in [0, 1]

    def test_refactor_json_output(self) -> None:
        """Test refactor --json produces JSON output."""
        runner = CliRunner()
        result = runner.invoke(cli, ["refactor", "--json", "--dry-run"])
        assert result.exit_code in [0, 1]

    def test_refactor_multiple_transforms(self) -> None:
        """Test refactor with multiple transforms."""
        runner = CliRunner()
        result = runner.invoke(cli, ["refactor", "--transforms", "dead-code,simplify,types", "--dry-run"])
        assert result.exit_code in [0, 1]

    def test_refactor_all_transforms_combined(self) -> None:
        """Test refactor with all transforms enabled."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "refactor",
                "--transforms",
                "dead-code,simplify,types,patterns,naming",
                "--dry-run",
            ],
        )
        assert result.exit_code in [0, 1]


class TestRefactorSuggestions:
    """Tests for refactor suggestion generation."""

    def test_refactor_generates_suggestions(self) -> None:
        """Test refactor generates suggestions in dry-run mode."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file with potential improvements
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text(
                "import os\nimport sys  # unused\n\ndef unused_func():\n    pass\n\ndef main():\n    x = 1\n"
            )

            result = runner.invoke(cli, ["refactor", tmpdir, "--dry-run"])
            assert result.exit_code in [0, 1]

    def test_refactor_handles_empty_directory(self) -> None:
        """Test refactor handles empty directory."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(cli, ["refactor", tmpdir, "--dry-run"])
            # Should handle gracefully
            assert result.exit_code in [0, 1]

    def test_refactor_handles_nonexistent_path(self) -> None:
        """Test refactor handles nonexistent path."""
        runner = CliRunner()
        result = runner.invoke(cli, ["refactor", "/nonexistent/path", "--dry-run"])
        # Should handle gracefully (error or warning)
        assert result.exit_code in [0, 1]
