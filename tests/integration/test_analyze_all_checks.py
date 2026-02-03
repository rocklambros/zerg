"""Integration tests for analyze --check all running all check types."""

import json
from unittest.mock import MagicMock

from zerg.commands.analyze import AnalysisResult, AnalyzeCommand, CheckType


def _stub_performance_checker(cmd: AnalyzeCommand) -> None:
    """Replace the performance checker with a fast stub to avoid tool timeouts."""
    cmd.checkers["performance"].check = MagicMock(
        return_value=AnalysisResult(check_type=CheckType.PERFORMANCE, passed=True, issues=[], score=80.0)
    )


class TestAnalyzeAllChecks:
    def test_all_check_types_present(self):
        """Verify all 11 check types are registered."""
        cmd = AnalyzeCommand()
        assert len(cmd.checkers) == 11

    def test_check_all_returns_results_for_all(self):
        """Running 'all' should return results from every checker."""
        cmd = AnalyzeCommand()
        _stub_performance_checker(cmd)
        results = cmd.run(["all"], [])
        assert len(results) == 11

    def test_each_result_has_check_type(self):
        """Every result should carry a valid CheckType."""
        cmd = AnalyzeCommand()
        _stub_performance_checker(cmd)
        results = cmd.run(["all"], [])
        check_values = {r.check_type.value for r in results}
        expected = {
            "lint",
            "complexity",
            "coverage",
            "security",
            "performance",
            "dead-code",
            "wiring",
            "cross-file",
            "conventions",
            "import-chain",
            "context-engineering",
        }
        assert check_values == expected

    def test_individual_wiring_check(self):
        """--check wiring should run standalone."""
        cmd = AnalyzeCommand()
        results = cmd.run(["wiring"], [])
        assert len(results) == 1
        assert results[0].check_type.value == "wiring"

    def test_individual_dead_code_check(self):
        """--check dead-code should run standalone."""
        cmd = AnalyzeCommand()
        results = cmd.run(["dead-code"], [])
        assert len(results) == 1
        assert results[0].check_type.value == "dead-code"

    def test_individual_conventions_check(self):
        """--check conventions should run standalone."""
        cmd = AnalyzeCommand()
        results = cmd.run(["conventions"], [])
        assert len(results) == 1
        assert results[0].check_type.value == "conventions"

    def test_individual_cross_file_check(self):
        """--check cross-file should run standalone."""
        cmd = AnalyzeCommand()
        results = cmd.run(["cross-file"], [])
        assert len(results) == 1
        assert results[0].check_type.value == "cross-file"

    def test_individual_import_chain_check(self):
        """--check import-chain should run standalone."""
        cmd = AnalyzeCommand()
        results = cmd.run(["import-chain"], [])
        assert len(results) == 1
        assert results[0].check_type.value == "import-chain"

    def test_individual_context_engineering_check(self):
        """--check context-engineering should run standalone."""
        cmd = AnalyzeCommand()
        results = cmd.run(["context-engineering"], [])
        assert len(results) == 1
        assert results[0].check_type.value == "context-engineering"

    def test_format_json(self):
        """JSON output should be valid."""
        cmd = AnalyzeCommand()
        results = cmd.run(["lint"], [])
        output = cmd.format_results(results, "json")
        data = json.loads(output)
        assert "results" in data
        assert "overall_passed" in data
        assert isinstance(data["results"], list)
        assert len(data["results"]) == 1

    def test_format_sarif(self):
        """SARIF output should have correct schema."""
        cmd = AnalyzeCommand()
        results = cmd.run(["lint"], [])
        output = cmd.format_results(results, "sarif")
        data = json.loads(output)
        assert data["version"] == "2.1.0"
        assert "runs" in data
        assert len(data["runs"]) == 1
        assert data["runs"][0]["tool"]["driver"]["name"] == "zerg-analyze"

    def test_format_text(self):
        """Text output should contain analysis header."""
        cmd = AnalyzeCommand()
        results = cmd.run(["lint"], [])
        output = cmd.format_results(results, "text")
        assert "Analysis Results" in output
        assert "Overall:" in output

    def test_overall_passed_all_pass(self):
        """overall_passed returns True when all checks pass."""
        cmd = AnalyzeCommand()
        # With empty file list, lint/security/dead-code return passed
        results = cmd.run(["lint", "dead-code"], [])
        # Both should pass with no files
        assert all(r.passed for r in results)
        assert cmd.overall_passed(results) is True

    def test_supported_checks_matches_checkers(self):
        """supported_checks() should return all checker names."""
        cmd = AnalyzeCommand()
        supported = cmd.supported_checks()
        assert set(supported) == set(cmd.checkers.keys())
        assert len(supported) == 11
