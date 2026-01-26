"""Integration tests for ZERG test command."""

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
        result = runner.invoke(cli, ["test", "--coverage"])
        assert "Invalid value" not in result.output

    def test_test_watch_flag(self) -> None:
        """Test test --watch flag works."""
        runner = CliRunner()
        result = runner.invoke(cli, ["test", "--watch"])
        assert "Invalid value" not in result.output

    def test_test_parallel_option(self) -> None:
        """Test test --parallel option works."""
        runner = CliRunner()
        result = runner.invoke(cli, ["test", "--parallel", "8"])
        assert "Invalid value" not in result.output

    def test_test_framework_option(self) -> None:
        """Test test --framework option accepts valid values."""
        runner = CliRunner()

        for framework in ["pytest", "jest", "cargo", "go", "mocha", "vitest"]:
            result = runner.invoke(cli, ["test", "--framework", framework])
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
        result = runner.invoke(cli, ["test", "--path", "tests/"])
        assert "Invalid value" not in result.output


class TestTestOptions:
    """Tests for test command options."""

    def test_test_combined_options(self) -> None:
        """Test test with combined options."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["test", "--coverage", "--parallel", "4", "--framework", "pytest"]
        )
        assert "Invalid value" not in result.output

    def test_test_watch_and_coverage(self) -> None:
        """Test test with watch and coverage."""
        runner = CliRunner()
        result = runner.invoke(cli, ["test", "--watch", "--coverage"])
        assert "Invalid value" not in result.output

    def test_test_generate_with_path(self) -> None:
        """Test test generate with path."""
        runner = CliRunner()
        result = runner.invoke(cli, ["test", "--generate", "--path", "src/"])
        assert "Invalid value" not in result.output
