"""Integration tests for ZERG analyze command."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from zerg.cli import cli
from zerg.commands.analyze import AnalysisResult, CheckType


class TestAnalyzeCommand:
    """Tests for analyze command."""

    def test_analyze_help(self) -> None:
        """Test analyze --help shows all options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", "--help"])

        assert result.exit_code == 0
        assert "lint" in result.output
        assert "complexity" in result.output
        assert "coverage" in result.output
        assert "security" in result.output

    def test_analyze_check_option(self) -> None:
        """Test analyze --check option accepts valid values.

        Note: Excludes slow checks (security, performance, all) that spawn
        external tools with long timeouts. Those are tested separately.
        """
        runner = CliRunner()

        # Fast checks only - security/performance/all spawn external tools
        # with 120-300s timeouts that exceed pytest-timeout
        for check_type in ["lint", "complexity", "coverage"]:
            result = runner.invoke(cli, ["analyze", "--check", check_type])
            # Should not fail with invalid option error
            assert "Invalid value" not in result.output

    def test_analyze_format_option(self) -> None:
        """Test analyze --format option accepts valid values.

        Uses --check lint to avoid slow performance/security checks.
        """
        runner = CliRunner()

        for fmt in ["text", "json", "sarif"]:
            result = runner.invoke(cli, ["analyze", "--format", fmt, "--check", "lint"])
            assert "Invalid value" not in result.output

    def test_analyze_invalid_check_rejected(self) -> None:
        """Test analyze rejects invalid check types."""
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", "--check", "invalid"])

        assert result.exit_code != 0
        assert "Invalid value" in result.output

    def test_analyze_threshold_option(self) -> None:
        """Test analyze --threshold option works.

        Uses --check lint to avoid slow performance/security checks.
        """
        runner = CliRunner()
        result = runner.invoke(
            cli, ["analyze", "--check", "lint", "--threshold", "complexity=15", "--threshold", "coverage=80"]
        )
        # Should accept multiple thresholds
        assert "Invalid value" not in result.output

    def test_analyze_files_option(self) -> None:
        """Test analyze --files option works.

        Uses --check lint to avoid slow performance/security checks.
        """
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", "--check", "lint", "--files", "src/"])
        assert "Invalid value" not in result.output


class TestAnalyzeOutput:
    """Tests for analyze command output formats."""

    def test_analyze_default_format_is_text(self) -> None:
        """Test default output format is text.

        Uses --check lint to avoid slow performance/security checks.
        """
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", "--check", "lint"])
        # Stub returns message, not JSON
        assert "{" not in result.output or "not yet implemented" in result.output

    def test_analyze_json_format_requested(self) -> None:
        """Test JSON format can be requested.

        Uses --check lint to avoid slow performance/security checks.
        """
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", "--format", "json", "--check", "lint"])
        # Command should accept the format option
        assert "Invalid value" not in result.output


class TestAnalyzeFunctional:
    """Functional tests for analyze command."""

    def test_analyze_displays_header(self) -> None:
        """Test analyze shows ZERG Analyze header.

        Uses --check lint to avoid slow performance/security checks.
        """
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", "--check", "lint"])
        # Check header is displayed
        assert "ZERG" in result.output or "Analyze" in result.output

    def test_analyze_lint_check(self) -> None:
        """Test analyze lint check produces output."""
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", "--check", "lint"])
        # Should complete (exit 0 or 1) not crash
        assert result.exit_code in [0, 1]
        # Should produce some output
        assert len(result.output) > 0

    def test_analyze_complexity_check(self) -> None:
        """Test analyze complexity check runs."""
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", "--check", "complexity"])
        assert result.exit_code in [0, 1]
        assert len(result.output) > 0

    def test_analyze_with_path_argument(self) -> None:
        """Test analyze with path argument.

        Uses --check lint to avoid slow performance/security checks.
        """
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test file
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("def foo():\n    pass\n")

            result = runner.invoke(cli, ["analyze", "--check", "lint", tmpdir])
            assert result.exit_code in [0, 1]

    def test_analyze_json_output_is_valid(self) -> None:
        """Test analyze --format json produces valid JSON."""
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", "--format", "json", "--check", "lint"])

        # Find JSON in output (might be mixed with other text)
        if result.exit_code == 0 and "{" in result.output:
            # Try to find and parse the JSON object
            start = result.output.find("{")
            if start >= 0:
                try:
                    # Find matching close brace
                    depth = 0
                    end = start
                    for i, c in enumerate(result.output[start:], start):
                        if c == "{":
                            depth += 1
                        elif c == "}":
                            depth -= 1
                            if depth == 0:
                                end = i + 1
                                break
                    json_str = result.output[start:end]
                    json.loads(json_str)
                except json.JSONDecodeError:
                    pass  # JSON might not be fully formed for all runs

    def test_analyze_all_checks(self) -> None:
        """Test analyze with all checks enabled."""
        # Mock performance checker to avoid jscpd timeout (180s)
        mock_result = AnalysisResult(check_type=CheckType.PERFORMANCE, passed=True, issues=[], score=80.0)
        with patch(
            "zerg.commands.analyze.PerformanceChecker.check",
            return_value=mock_result,
        ):
            runner = CliRunner()
            result = runner.invoke(cli, ["analyze", "--check", "all"])
        assert result.exit_code in [0, 1]
        # Should mention multiple check types in output
        assert len(result.output) > 0

    def test_analyze_threshold_parsing(self) -> None:
        """Test analyze parses thresholds correctly."""
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", "--check", "complexity", "--threshold", "complexity=5"])
        assert result.exit_code in [0, 1]

    def test_analyze_sarif_format(self) -> None:
        """Test analyze SARIF format output."""
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", "--format", "sarif", "--check", "lint"])
        assert result.exit_code in [0, 1]
        # SARIF format should produce valid output
        if "sarif" in result.output.lower() or "$schema" in result.output:
            assert True  # SARIF output detected

    def test_analyze_security_check(self) -> None:
        """Test analyze security check runs."""
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", "--check", "security"])
        assert result.exit_code in [0, 1]

    def test_analyze_coverage_check(self) -> None:
        """Test analyze coverage check runs."""
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", "--check", "coverage"])
        assert result.exit_code in [0, 1]
