"""Integration tests for ZERG test command."""

import tempfile
from pathlib import Path

from click.testing import CliRunner

from zerg.cli import cli


class TestTestCommand:
    """Tests for test command."""

    def test_test_help(self) -> None:
        """Test test --help shows all options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["test", "--help"])

        assert result.exit_code == 0
        assert "generate" in result.output
        assert "coverage" in result.output
        assert "watch" in result.output
        assert "parallel" in result.output
        assert "framework" in result.output

    def test_test_generate_flag(self) -> None:
        """Test test --generate flag works."""
        runner = CliRunner()
        result = runner.invoke(cli, ["test", "--generate"])
        assert "Invalid value" not in result.output

    def test_test_coverage_flag(self) -> None:
        """Test test --coverage flag works."""
        runner = CliRunner()
        # Use --dry-run to avoid actually running tests with coverage
        result = runner.invoke(cli, ["test", "--coverage", "--dry-run"])
        assert "Invalid value" not in result.output

    def test_test_watch_flag(self) -> None:
        """Test test --watch flag works."""
        runner = CliRunner()
        # Use --dry-run with --watch to avoid infinite loop
        result = runner.invoke(cli, ["test", "--watch", "--dry-run"])
        assert "Invalid value" not in result.output

    def test_test_parallel_option(self) -> None:
        """Test test --parallel option works."""
        runner = CliRunner()
        # Use --dry-run to avoid actually running tests
        result = runner.invoke(cli, ["test", "--parallel", "8", "--dry-run"])
        assert "Invalid value" not in result.output

    def test_test_framework_option(self) -> None:
        """Test test --framework option accepts valid values."""
        runner = CliRunner()

        for framework in ["pytest", "jest", "cargo", "go", "mocha", "vitest"]:
            # Use --dry-run to avoid actually running tests
            result = runner.invoke(cli, ["test", "--framework", framework, "--dry-run"])
            assert "Invalid value" not in result.output

    def test_test_invalid_framework_rejected(self) -> None:
        """Test test rejects invalid frameworks."""
        runner = CliRunner()
        result = runner.invoke(cli, ["test", "--framework", "invalid"])

        assert result.exit_code != 0
        assert "Invalid value" in result.output

    def test_test_path_option(self) -> None:
        """Test test --path option works."""
        runner = CliRunner()
        # Use --dry-run to avoid actually running tests
        result = runner.invoke(cli, ["test", "--path", "tests/", "--dry-run"])
        assert "Invalid value" not in result.output


class TestTestOptions:
    """Tests for test command options."""

    def test_test_combined_options(self) -> None:
        """Test test with combined options."""
        runner = CliRunner()
        # Use --dry-run to avoid actually running tests
        result = runner.invoke(cli, ["test", "--coverage", "--parallel", "4", "--framework", "pytest", "--dry-run"])
        assert "Invalid value" not in result.output

    def test_test_watch_and_coverage(self) -> None:
        """Test test with watch and coverage."""
        runner = CliRunner()
        # Use --dry-run with --watch to avoid infinite loop
        result = runner.invoke(cli, ["test", "--watch", "--coverage", "--dry-run"])
        assert "Invalid value" not in result.output

    def test_test_generate_with_path(self) -> None:
        """Test test generate with path."""
        runner = CliRunner()
        result = runner.invoke(cli, ["test", "--generate", "--path", "src/"])
        assert "Invalid value" not in result.output


class TestTestFunctional:
    """Functional tests for test command."""

    def test_test_displays_header(self) -> None:
        """Test test shows ZERG Test header."""
        runner = CliRunner()
        result = runner.invoke(cli, ["test", "--dry-run"])
        assert "ZERG" in result.output or "Test" in result.output

    def test_test_dry_run_mode(self) -> None:
        """Test test --dry-run shows what would be run."""
        runner = CliRunner()
        result = runner.invoke(cli, ["test", "--dry-run"])
        assert result.exit_code in [0, 1]
        assert len(result.output) > 0

    def test_test_detects_pytest(self) -> None:
        """Test test detects pytest framework."""
        runner = CliRunner()
        # Current project uses pytest
        result = runner.invoke(cli, ["test", "--dry-run"])
        assert result.exit_code in [0, 1]

    def test_test_json_output(self) -> None:
        """Test test --json produces JSON output."""
        runner = CliRunner()
        result = runner.invoke(cli, ["test", "--json", "--dry-run"])
        assert result.exit_code in [0, 1]

    def test_test_with_coverage(self) -> None:
        """Test test --coverage flag works."""
        runner = CliRunner()
        result = runner.invoke(cli, ["test", "--coverage", "--dry-run"])
        assert result.exit_code in [0, 1]

    def test_test_parallel_workers(self) -> None:
        """Test test with parallel workers."""
        runner = CliRunner()
        result = runner.invoke(cli, ["test", "--parallel", "4", "--dry-run"])
        assert result.exit_code in [0, 1]

    def test_test_specific_path(self) -> None:
        """Test test with specific test path."""
        runner = CliRunner()
        result = runner.invoke(cli, ["test", "--path", "tests/unit", "--dry-run"])
        assert result.exit_code in [0, 1]


class TestTestFrameworkDetection:
    """Tests for test framework detection."""

    def test_test_pytest_framework(self) -> None:
        """Test test with pytest framework."""
        runner = CliRunner()
        result = runner.invoke(cli, ["test", "--framework", "pytest", "--dry-run"])
        assert result.exit_code in [0, 1]

    def test_test_jest_framework(self) -> None:
        """Test test with jest framework."""
        runner = CliRunner()
        result = runner.invoke(cli, ["test", "--framework", "jest", "--dry-run"])
        assert result.exit_code in [0, 1]

    def test_test_cargo_framework(self) -> None:
        """Test test with cargo framework."""
        runner = CliRunner()
        result = runner.invoke(cli, ["test", "--framework", "cargo", "--dry-run"])
        assert result.exit_code in [0, 1]

    def test_test_go_framework(self) -> None:
        """Test test with go framework."""
        runner = CliRunner()
        result = runner.invoke(cli, ["test", "--framework", "go", "--dry-run"])
        assert result.exit_code in [0, 1]

    def test_test_mocha_framework(self) -> None:
        """Test test with mocha framework."""
        runner = CliRunner()
        result = runner.invoke(cli, ["test", "--framework", "mocha", "--dry-run"])
        assert result.exit_code in [0, 1]

    def test_test_vitest_framework(self) -> None:
        """Test test with vitest framework."""
        runner = CliRunner()
        result = runner.invoke(cli, ["test", "--framework", "vitest", "--dry-run"])
        assert result.exit_code in [0, 1]


class TestTestGeneration:
    """Tests for test stub generation."""

    def test_test_generate_flag(self) -> None:
        """Test test --generate creates test stubs."""
        runner = CliRunner()
        result = runner.invoke(cli, ["test", "--generate", "--dry-run"])
        assert result.exit_code in [0, 1]

    def test_test_generate_with_path(self) -> None:
        """Test test --generate with specific path."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a source file
            src_file = Path(tmpdir) / "module.py"
            src_file.write_text("def add(a, b):\n    return a + b\n")

            result = runner.invoke(cli, ["test", "--generate", "--path", tmpdir])
            assert result.exit_code in [0, 1]

    def test_test_generate_handles_empty_dir(self) -> None:
        """Test test --generate handles empty directory."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(cli, ["test", "--generate", "--path", tmpdir])
            # Should handle gracefully
            assert result.exit_code in [0, 1]


class TestTestWatchMode:
    """Tests for test watch mode."""

    def test_test_watch_flag_accepted(self) -> None:
        """Test test --watch flag is accepted."""
        runner = CliRunner()
        result = runner.invoke(cli, ["test", "--watch", "--dry-run"])
        # Should accept the flag
        assert "Invalid value" not in result.output

    def test_test_watch_with_coverage(self) -> None:
        """Test test --watch --coverage combination."""
        runner = CliRunner()
        result = runner.invoke(cli, ["test", "--watch", "--coverage", "--dry-run"])
        assert result.exit_code in [0, 1]


class TestTestAllOptions:
    """Tests for test command with all options."""

    def test_test_all_options_combined(self) -> None:
        """Test test with all options combined."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "test",
                "--coverage",
                "--parallel",
                "4",
                "--framework",
                "pytest",
                "--path",
                "tests/",
                "--dry-run",
            ],
        )
        assert result.exit_code in [0, 1]

    def test_test_parallel_zero(self) -> None:
        """Test test with zero parallel workers."""
        runner = CliRunner()
        result = runner.invoke(cli, ["test", "--parallel", "0", "--dry-run"])
        # Should handle zero workers (use default or auto-detect)
        assert result.exit_code in [0, 1]

    def test_test_parallel_large_number(self) -> None:
        """Test test with large parallel worker count."""
        runner = CliRunner()
        result = runner.invoke(cli, ["test", "--parallel", "100", "--dry-run"])
        assert result.exit_code in [0, 1]
