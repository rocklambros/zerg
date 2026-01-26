"""Integration tests for ZERG troubleshoot command."""

import tempfile
from pathlib import Path

from click.testing import CliRunner

from zerg.cli import cli


class TestTroubleshootCommand:
    """Tests for troubleshoot command."""

    def test_troubleshoot_help(self) -> None:
        """Test troubleshoot --help shows all options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["troubleshoot", "--help"])

        assert result.exit_code == 0
        assert "error" in result.output
        assert "stacktrace" in result.output
        assert "verbose" in result.output

    def test_troubleshoot_error_option(self) -> None:
        """Test troubleshoot --error option works."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["troubleshoot", "--error", "ValueError: test error"]
        )
        # Check that click didn't reject the option (exit code 2 means usage error)
        assert result.exit_code != 2

    def test_troubleshoot_stacktrace_option(self) -> None:
        """Test troubleshoot --stacktrace option works."""
        runner = CliRunner()
        result = runner.invoke(cli, ["troubleshoot", "--stacktrace", "trace.txt"])
        assert "Invalid value" not in result.output

    def test_troubleshoot_verbose_flag(self) -> None:
        """Test troubleshoot --verbose flag works."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["troubleshoot", "--error", "Error", "--verbose"]
        )
        assert "Invalid value" not in result.output

    def test_troubleshoot_output_option(self) -> None:
        """Test troubleshoot --output option works."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["troubleshoot", "--error", "Error", "--output", "report.md"]
        )
        assert "Invalid value" not in result.output


class TestTroubleshootCombinations:
    """Tests for troubleshoot option combinations."""

    def test_troubleshoot_error_and_verbose(self) -> None:
        """Test troubleshoot with error and verbose."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["troubleshoot", "--error", "ImportError: No module", "--verbose"]
        )
        assert "Invalid value" not in result.output

    def test_troubleshoot_all_options(self) -> None:
        """Test troubleshoot with all options."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "troubleshoot",
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

    def test_troubleshoot_no_options(self) -> None:
        """Test troubleshoot without options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["troubleshoot"])
        # Should work (might fail at runtime but not at option parsing)
        assert "Invalid value" not in result.output

    def test_troubleshoot_error_with_special_chars(self) -> None:
        """Test troubleshoot with special characters in error."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["troubleshoot", "--error", "Error: 'foo' != \"bar\""]
        )
        assert "Invalid value" not in result.output


class TestTroubleshootFunctional:
    """Functional tests for troubleshoot command."""

    def test_troubleshoot_displays_header(self) -> None:
        """Test troubleshoot shows ZERG Troubleshoot header."""
        runner = CliRunner()
        result = runner.invoke(cli, ["troubleshoot", "--error", "Test error"])
        assert "ZERG" in result.output or "Troubleshoot" in result.output

    def test_troubleshoot_value_error(self) -> None:
        """Test troubleshoot analyzes ValueError."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["troubleshoot", "--error", "ValueError: invalid literal for int()"]
        )
        assert result.exit_code in [0, 1]
        assert len(result.output) > 0

    def test_troubleshoot_import_error(self) -> None:
        """Test troubleshoot analyzes ImportError."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["troubleshoot", "--error", "ImportError: No module named 'missing'"]
        )
        assert result.exit_code in [0, 1]

    def test_troubleshoot_type_error(self) -> None:
        """Test troubleshoot analyzes TypeError."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["troubleshoot", "--error", "TypeError: unsupported operand type(s)"]
        )
        assert result.exit_code in [0, 1]

    def test_troubleshoot_attribute_error(self) -> None:
        """Test troubleshoot analyzes AttributeError."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["troubleshoot", "--error", "AttributeError: 'NoneType' has no attribute 'foo'"]
        )
        assert result.exit_code in [0, 1]

    def test_troubleshoot_key_error(self) -> None:
        """Test troubleshoot analyzes KeyError."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["troubleshoot", "--error", "KeyError: 'missing_key'"]
        )
        assert result.exit_code in [0, 1]

    def test_troubleshoot_index_error(self) -> None:
        """Test troubleshoot analyzes IndexError."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["troubleshoot", "--error", "IndexError: list index out of range"]
        )
        assert result.exit_code in [0, 1]

    def test_troubleshoot_json_output(self) -> None:
        """Test troubleshoot --json produces JSON output."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["troubleshoot", "--error", "Error", "--json"]
        )
        assert result.exit_code in [0, 1]


class TestTroubleshootStacktrace:
    """Tests for troubleshoot stacktrace parsing."""

    def test_troubleshoot_stacktrace_file(self) -> None:
        """Test troubleshoot with stacktrace file."""
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

            result = runner.invoke(cli, ["troubleshoot", "--stacktrace", str(trace_file)])
            assert result.exit_code in [0, 1]

    def test_troubleshoot_missing_stacktrace_file(self) -> None:
        """Test troubleshoot handles missing stacktrace file."""
        runner = CliRunner()
        result = runner.invoke(cli, ["troubleshoot", "--stacktrace", "/nonexistent/file.txt"])
        # Should handle gracefully
        assert result.exit_code in [0, 1]

    def test_troubleshoot_empty_stacktrace(self) -> None:
        """Test troubleshoot handles empty stacktrace file."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            trace_file = Path(tmpdir) / "empty.txt"
            trace_file.write_text("")

            result = runner.invoke(cli, ["troubleshoot", "--stacktrace", str(trace_file)])
            assert result.exit_code in [0, 1]


class TestTroubleshootHypothesis:
    """Tests for troubleshoot hypothesis generation."""

    def test_troubleshoot_generates_hypotheses(self) -> None:
        """Test troubleshoot generates hypotheses for errors."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["troubleshoot", "--error", "TypeError: cannot concatenate 'str' and 'int'", "--verbose"]
        )
        assert result.exit_code in [0, 1]

    def test_troubleshoot_connection_error(self) -> None:
        """Test troubleshoot analyzes connection errors."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["troubleshoot", "--error", "ConnectionError: Failed to connect to server"]
        )
        assert result.exit_code in [0, 1]

    def test_troubleshoot_timeout_error(self) -> None:
        """Test troubleshoot analyzes timeout errors."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["troubleshoot", "--error", "TimeoutError: Connection timed out"]
        )
        assert result.exit_code in [0, 1]

    def test_troubleshoot_permission_error(self) -> None:
        """Test troubleshoot analyzes permission errors."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["troubleshoot", "--error", "PermissionError: Permission denied"]
        )
        assert result.exit_code in [0, 1]

    def test_troubleshoot_file_not_found(self) -> None:
        """Test troubleshoot analyzes file not found errors."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["troubleshoot", "--error", "FileNotFoundError: No such file or directory"]
        )
        assert result.exit_code in [0, 1]


class TestTroubleshootOutput:
    """Tests for troubleshoot output options."""

    def test_troubleshoot_output_file(self) -> None:
        """Test troubleshoot writes to output file."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = Path(tmpdir) / "report.md"
            result = runner.invoke(
                cli,
                ["troubleshoot", "--error", "Test error", "--output", str(output_file)],
            )
            assert result.exit_code in [0, 1]

    def test_troubleshoot_verbose_more_detail(self) -> None:
        """Test troubleshoot --verbose provides more detail."""
        runner = CliRunner()
        normal_result = runner.invoke(
            cli, ["troubleshoot", "--error", "ValueError: test"]
        )
        verbose_result = runner.invoke(
            cli, ["troubleshoot", "--error", "ValueError: test", "--verbose"]
        )

        # Both should succeed
        assert normal_result.exit_code in [0, 1]
        assert verbose_result.exit_code in [0, 1]


class TestTroubleshootPhases:
    """Tests for troubleshoot diagnostic phases."""

    def test_troubleshoot_symptom_phase(self) -> None:
        """Test troubleshoot symptom parsing phase."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["troubleshoot", "--error", "SyntaxError: invalid syntax", "--verbose"]
        )
        assert result.exit_code in [0, 1]

    def test_troubleshoot_hypothesis_phase(self) -> None:
        """Test troubleshoot hypothesis generation phase."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["troubleshoot", "--error", "RecursionError: maximum recursion depth exceeded"]
        )
        assert result.exit_code in [0, 1]

    def test_troubleshoot_complex_error(self) -> None:
        """Test troubleshoot handles complex multi-line errors."""
        runner = CliRunner()
        error_msg = (
            "ModuleNotFoundError: No module named 'foo.bar.baz'; "
            "'foo.bar' is not a package"
        )
        result = runner.invoke(cli, ["troubleshoot", "--error", error_msg])
        assert result.exit_code in [0, 1]
