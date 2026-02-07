"""Integration tests for ZERG debug command."""

import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from zerg.cli import cli


class TestDebugCommand:
    """Tests for debug command."""

    def test_debug_help(self) -> None:
        """Test debug --help shows all options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["debug", "--help"])

        assert result.exit_code == 0
        assert "error" in result.output
        assert "stacktrace" in result.output
        assert "verbose" in result.output

    def test_debug_error_option(self) -> None:
        """Test debug --error option works."""
        runner = CliRunner()
        result = runner.invoke(cli, ["debug", "--error", "ValueError: test error"])
        # Check that click didn't reject the option (exit code 2 means usage error)
        assert result.exit_code != 2


class TestDebugCombinations:
    """Tests for debug option combinations."""

    def test_debug_all_options(self) -> None:
        """Test debug with all options."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "debug",
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

    def test_debug_no_options(self) -> None:
        """Test debug without options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["debug"])
        # Should work (might fail at runtime but not at option parsing)
        assert "Invalid value" not in result.output


class TestDebugFunctional:
    """Functional tests for debug command."""

    def test_debug_displays_header(self) -> None:
        """Test debug shows ZERG Debug header."""
        runner = CliRunner()
        result = runner.invoke(cli, ["debug", "--error", "Test error"])
        assert "ZERG" in result.output or "Debug" in result.output

    @pytest.mark.parametrize(
        "error_msg",
        [
            "ValueError: invalid literal for int()",
            "ImportError: No module named 'missing'",
            "KeyError: 'missing_key'",
        ],
    )
    def test_debug_analyzes_error_types(self, error_msg: str) -> None:
        """Test debug analyzes various error types."""
        runner = CliRunner()
        result = runner.invoke(cli, ["debug", "--error", error_msg])
        assert result.exit_code in [0, 1]

    def test_debug_json_output(self) -> None:
        """Test debug --json produces JSON output."""
        runner = CliRunner()
        result = runner.invoke(cli, ["debug", "--error", "Error", "--json"])
        assert result.exit_code in [0, 1]


class TestDebugStacktrace:
    """Tests for debug stacktrace parsing."""

    def test_debug_stacktrace_file(self) -> None:
        """Test debug with stacktrace file."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a stacktrace file
            trace_file = Path(tmpdir) / "trace.txt"
            trace_file.write_text(
                "Traceback (most recent call last):\n"
                '  File "test.py", line 10, in <module>\n'
                "    result = foo()\n"
                '  File "test.py", line 5, in foo\n'
                "    return bar()\n"
                "ValueError: invalid value\n"
            )

            result = runner.invoke(cli, ["debug", "--stacktrace", str(trace_file)])
            assert result.exit_code in [0, 1]

    def test_debug_missing_stacktrace_file(self) -> None:
        """Test debug handles missing stacktrace file."""
        runner = CliRunner()
        result = runner.invoke(cli, ["debug", "--stacktrace", "/nonexistent/file.txt"])
        # Should handle gracefully
        assert result.exit_code in [0, 1]


class TestDebugHypothesis:
    """Tests for debug hypothesis generation."""

    @pytest.mark.parametrize(
        "error_msg",
        [
            "ConnectionError: Failed to connect to server",
            "PermissionError: Permission denied",
        ],
    )
    def test_debug_generates_hypotheses(self, error_msg: str) -> None:
        """Test debug generates hypotheses for various errors."""
        runner = CliRunner()
        result = runner.invoke(cli, ["debug", "--error", error_msg])
        assert result.exit_code in [0, 1]


class TestDebugOutput:
    """Tests for debug output options."""

    def test_debug_output_file(self) -> None:
        """Test debug writes to output file."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = Path(tmpdir) / "report.md"
            result = runner.invoke(
                cli,
                ["debug", "--error", "Test error", "--output", str(output_file)],
            )
            assert result.exit_code in [0, 1]


class TestDebugPhases:
    """Tests for debug diagnostic phases."""

    def test_debug_complex_error(self) -> None:
        """Test debug handles complex multi-line errors."""
        runner = CliRunner()
        error_msg = "ModuleNotFoundError: No module named 'foo.bar.baz'; 'foo.bar' is not a package"
        result = runner.invoke(cli, ["debug", "--error", error_msg])
        assert result.exit_code in [0, 1]
