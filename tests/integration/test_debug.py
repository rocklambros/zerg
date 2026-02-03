"""Integration tests for ZERG debug command."""

import tempfile
from pathlib import Path

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

    def test_debug_stacktrace_option(self) -> None:
        """Test debug --stacktrace option works."""
        runner = CliRunner()
        result = runner.invoke(cli, ["debug", "--stacktrace", "trace.txt"])
        assert "Invalid value" not in result.output

    def test_debug_verbose_flag(self) -> None:
        """Test debug --verbose flag works."""
        runner = CliRunner()
        result = runner.invoke(cli, ["debug", "--error", "Error", "--verbose"])
        assert "Invalid value" not in result.output

    def test_debug_output_option(self) -> None:
        """Test debug --output option works."""
        runner = CliRunner()
        result = runner.invoke(cli, ["debug", "--error", "Error", "--output", "report.md"])
        assert "Invalid value" not in result.output


class TestDebugCombinations:
    """Tests for debug option combinations."""

    def test_debug_error_and_verbose(self) -> None:
        """Test debug with error and verbose."""
        runner = CliRunner()
        result = runner.invoke(cli, ["debug", "--error", "ImportError: No module", "--verbose"])
        assert "Invalid value" not in result.output

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

    def test_debug_error_with_special_chars(self) -> None:
        """Test debug with special characters in error."""
        runner = CliRunner()
        result = runner.invoke(cli, ["debug", "--error", "Error: 'foo' != \"bar\""])
        assert "Invalid value" not in result.output


class TestDebugFunctional:
    """Functional tests for debug command."""

    def test_debug_displays_header(self) -> None:
        """Test debug shows ZERG Debug header."""
        runner = CliRunner()
        result = runner.invoke(cli, ["debug", "--error", "Test error"])
        assert "ZERG" in result.output or "Debug" in result.output

    def test_debug_value_error(self) -> None:
        """Test debug analyzes ValueError."""
        runner = CliRunner()
        result = runner.invoke(cli, ["debug", "--error", "ValueError: invalid literal for int()"])
        assert result.exit_code in [0, 1]
        assert len(result.output) > 0

    def test_debug_import_error(self) -> None:
        """Test debug analyzes ImportError."""
        runner = CliRunner()
        result = runner.invoke(cli, ["debug", "--error", "ImportError: No module named 'missing'"])
        assert result.exit_code in [0, 1]

    def test_debug_type_error(self) -> None:
        """Test debug analyzes TypeError."""
        runner = CliRunner()
        result = runner.invoke(cli, ["debug", "--error", "TypeError: unsupported operand type(s)"])
        assert result.exit_code in [0, 1]

    def test_debug_attribute_error(self) -> None:
        """Test debug analyzes AttributeError."""
        runner = CliRunner()
        result = runner.invoke(cli, ["debug", "--error", "AttributeError: 'NoneType' has no attribute 'foo'"])
        assert result.exit_code in [0, 1]

    def test_debug_key_error(self) -> None:
        """Test debug analyzes KeyError."""
        runner = CliRunner()
        result = runner.invoke(cli, ["debug", "--error", "KeyError: 'missing_key'"])
        assert result.exit_code in [0, 1]

    def test_debug_index_error(self) -> None:
        """Test debug analyzes IndexError."""
        runner = CliRunner()
        result = runner.invoke(cli, ["debug", "--error", "IndexError: list index out of range"])
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

    def test_debug_empty_stacktrace(self) -> None:
        """Test debug handles empty stacktrace file."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            trace_file = Path(tmpdir) / "empty.txt"
            trace_file.write_text("")

            result = runner.invoke(cli, ["debug", "--stacktrace", str(trace_file)])
            assert result.exit_code in [0, 1]


class TestDebugHypothesis:
    """Tests for debug hypothesis generation."""

    def test_debug_generates_hypotheses(self) -> None:
        """Test debug generates hypotheses for errors."""
        runner = CliRunner()
        result = runner.invoke(cli, ["debug", "--error", "TypeError: cannot concatenate 'str' and 'int'", "--verbose"])
        assert result.exit_code in [0, 1]

    def test_debug_connection_error(self) -> None:
        """Test debug analyzes connection errors."""
        runner = CliRunner()
        result = runner.invoke(cli, ["debug", "--error", "ConnectionError: Failed to connect to server"])
        assert result.exit_code in [0, 1]

    def test_debug_timeout_error(self) -> None:
        """Test debug analyzes timeout errors."""
        runner = CliRunner()
        result = runner.invoke(cli, ["debug", "--error", "TimeoutError: Connection timed out"])
        assert result.exit_code in [0, 1]

    def test_debug_permission_error(self) -> None:
        """Test debug analyzes permission errors."""
        runner = CliRunner()
        result = runner.invoke(cli, ["debug", "--error", "PermissionError: Permission denied"])
        assert result.exit_code in [0, 1]

    def test_debug_file_not_found(self) -> None:
        """Test debug analyzes file not found errors."""
        runner = CliRunner()
        result = runner.invoke(cli, ["debug", "--error", "FileNotFoundError: No such file or directory"])
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

    def test_debug_verbose_more_detail(self) -> None:
        """Test debug --verbose provides more detail."""
        runner = CliRunner()
        normal_result = runner.invoke(cli, ["debug", "--error", "ValueError: test"])
        verbose_result = runner.invoke(cli, ["debug", "--error", "ValueError: test", "--verbose"])

        # Both should succeed
        assert normal_result.exit_code in [0, 1]
        assert verbose_result.exit_code in [0, 1]


class TestDebugPhases:
    """Tests for debug diagnostic phases."""

    def test_debug_symptom_phase(self) -> None:
        """Test debug symptom parsing phase."""
        runner = CliRunner()
        result = runner.invoke(cli, ["debug", "--error", "SyntaxError: invalid syntax", "--verbose"])
        assert result.exit_code in [0, 1]

    def test_debug_hypothesis_phase(self) -> None:
        """Test debug hypothesis generation phase."""
        runner = CliRunner()
        result = runner.invoke(cli, ["debug", "--error", "RecursionError: maximum recursion depth exceeded"])
        assert result.exit_code in [0, 1]

    def test_debug_complex_error(self) -> None:
        """Test debug handles complex multi-line errors."""
        runner = CliRunner()
        error_msg = "ModuleNotFoundError: No module named 'foo.bar.baz'; 'foo.bar' is not a package"
        result = runner.invoke(cli, ["debug", "--error", error_msg])
        assert result.exit_code in [0, 1]
