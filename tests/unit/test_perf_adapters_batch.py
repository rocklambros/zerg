"""Batch tests for performance tool adapters: pipdeptree, jscpd, cloc, deptry.

Each adapter follows the same pattern: subprocess call -> JSON parse -> findings.
Tests use parametrize with mock subprocess output to cover all code paths.
"""

from __future__ import annotations

import json
import subprocess
from unittest.mock import patch

import pytest

from zerg.performance.adapters.cloc_adapter import ClocAdapter
from zerg.performance.adapters.deptry_adapter import DeptryAdapter
from zerg.performance.adapters.jscpd_adapter import JscpdAdapter
from zerg.performance.adapters.pipdeptree_adapter import PipdeptreeAdapter
from zerg.performance.types import DetectedStack, Severity

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def python_stack():
    return DetectedStack(languages=["python"], frameworks=["flask"])


@pytest.fixture()
def js_stack():
    return DetectedStack(languages=["javascript"], frameworks=["react"])


@pytest.fixture()
def empty_stack():
    return DetectedStack(languages=[], frameworks=[])


def _make_completed_process(stdout: str = "", stderr: str = "", returncode: int = 0):
    """Helper to build a subprocess.CompletedProcess."""
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


# ===========================================================================
# PipdeptreeAdapter tests
# ===========================================================================


class TestPipdeptreeAdapter:
    """Tests for PipdeptreeAdapter covering is_applicable, run, and _analyze_tree."""

    def test_is_applicable_python(self, python_stack):
        adapter = PipdeptreeAdapter()
        assert adapter.is_applicable(python_stack) is True

    def test_is_applicable_non_python(self, js_stack):
        adapter = PipdeptreeAdapter()
        assert adapter.is_applicable(js_stack) is False

    def test_attributes(self):
        adapter = PipdeptreeAdapter()
        assert adapter.name == "pipdeptree"
        assert adapter.tool_name == "pipdeptree"
        assert 80 in adapter.factors_covered

    @patch("zerg.performance.adapters.pipdeptree_adapter.subprocess.run")
    def test_run_subprocess_failure_returns_empty(self, mock_run, python_stack):
        mock_run.side_effect = subprocess.SubprocessError("boom")
        adapter = PipdeptreeAdapter()
        result = adapter.run([], "/project", python_stack)
        assert result == []

    @patch("zerg.performance.adapters.pipdeptree_adapter.subprocess.run")
    def test_run_invalid_json_returns_empty(self, mock_run, python_stack):
        mock_run.return_value = _make_completed_process(stdout="not-json")
        adapter = PipdeptreeAdapter()
        result = adapter.run([], "/project", python_stack)
        assert result == []

    @patch("zerg.performance.adapters.pipdeptree_adapter.subprocess.run")
    def test_run_non_list_json_returns_empty(self, mock_run, python_stack):
        mock_run.return_value = _make_completed_process(stdout='{"key": "value"}')
        adapter = PipdeptreeAdapter()
        result = adapter.run([], "/project", python_stack)
        assert result == []

    @patch("zerg.performance.adapters.pipdeptree_adapter.subprocess.run")
    def test_run_os_error_returns_empty(self, mock_run, python_stack):
        mock_run.side_effect = OSError("no binary")
        adapter = PipdeptreeAdapter()
        result = adapter.run([], "/project", python_stack)
        assert result == []

    @patch("zerg.performance.adapters.pipdeptree_adapter.subprocess.run")
    def test_run_empty_tree_no_findings(self, mock_run, python_stack):
        mock_run.return_value = _make_completed_process(stdout="[]")
        adapter = PipdeptreeAdapter()
        result = adapter.run([], "/project", python_stack)
        assert result == []

    @pytest.mark.parametrize(
        "transitive_count,expected_severity,expected_rule",
        [
            (201, Severity.HIGH, "transitive-count-high"),
            (150, Severity.MEDIUM, "transitive-count-medium"),
            (50, None, None),  # below threshold
        ],
        ids=["high-transitive", "medium-transitive", "below-threshold"],
    )
    @patch("zerg.performance.adapters.pipdeptree_adapter.subprocess.run")
    def test_transitive_count_thresholds(
        self, mock_run, python_stack, transitive_count, expected_severity, expected_rule
    ):
        """Test transitive dependency count triggers correct severity."""
        # Build packages with a flat list of N transitive deps
        deps = [{"package_name": f"dep-{i}", "dependencies": []} for i in range(transitive_count)]
        packages = [{"package_name": "root", "dependencies": deps}]
        mock_run.return_value = _make_completed_process(stdout=json.dumps(packages))

        adapter = PipdeptreeAdapter()
        findings = adapter.run([], "/project", python_stack)

        transitive_findings = [f for f in findings if f.rule_id.startswith("transitive-count")]
        if expected_severity is None:
            assert transitive_findings == []
        else:
            assert len(transitive_findings) == 1
            assert transitive_findings[0].severity == expected_severity
            assert transitive_findings[0].rule_id == expected_rule

    @pytest.mark.parametrize(
        "depth,expected_severity,expected_rule",
        [
            (11, Severity.HIGH, "depth-high"),
            (7, Severity.MEDIUM, "depth-medium"),
            (3, None, None),
        ],
        ids=["high-depth", "medium-depth", "below-depth-threshold"],
    )
    @patch("zerg.performance.adapters.pipdeptree_adapter.subprocess.run")
    def test_depth_thresholds(self, mock_run, python_stack, depth, expected_severity, expected_rule):
        """Test dependency chain depth triggers correct severity."""
        # Build a linear chain of the given depth
        innermost = {"package_name": "leaf", "dependencies": []}
        current = innermost
        for i in range(depth - 1):
            current = {"package_name": f"mid-{i}", "dependencies": [current]}
        packages = [{"package_name": "root", "dependencies": [current]}]
        mock_run.return_value = _make_completed_process(stdout=json.dumps(packages))

        adapter = PipdeptreeAdapter()
        findings = adapter.run([], "/project", python_stack)

        depth_findings = [f for f in findings if f.rule_id.startswith("depth")]
        if expected_severity is None:
            assert depth_findings == []
        else:
            assert len(depth_findings) == 1
            assert depth_findings[0].severity == expected_severity
            assert depth_findings[0].rule_id == expected_rule

    @patch("zerg.performance.adapters.pipdeptree_adapter.subprocess.run")
    def test_conflict_in_stderr(self, mock_run, python_stack):
        """stderr containing 'conflict' should produce a finding."""
        mock_run.return_value = _make_completed_process(stdout="[]", stderr="Warning: version conflict detected")
        adapter = PipdeptreeAdapter()
        findings = adapter.run([], "/project", python_stack)
        assert len(findings) == 1
        assert findings[0].rule_id == "version-conflict"
        assert findings[0].severity == Severity.HIGH

    @patch("zerg.performance.adapters.pipdeptree_adapter.subprocess.run")
    def test_non_dict_packages_ignored(self, mock_run, python_stack):
        """Non-dict entries in the package list should be skipped."""
        packages = ["not-a-dict", 42, None, {"package_name": "valid", "dependencies": []}]
        mock_run.return_value = _make_completed_process(stdout=json.dumps(packages))
        adapter = PipdeptreeAdapter()
        findings = adapter.run([], "/project", python_stack)
        # No crash, should produce no findings (only 0 transitive deps)
        assert isinstance(findings, list)

    @patch("zerg.performance.adapters.pipdeptree_adapter.subprocess.run")
    def test_non_dict_deps_in_measure_deps(self, mock_run, python_stack):
        """Non-dict entries in dependencies list should be skipped."""
        packages = [
            {"package_name": "root", "dependencies": ["not-a-dict", 123, {"package_name": "real", "dependencies": []}]}
        ]
        mock_run.return_value = _make_completed_process(stdout=json.dumps(packages))
        adapter = PipdeptreeAdapter()
        findings = adapter.run([], "/project", python_stack)
        assert isinstance(findings, list)

    @patch("zerg.performance.adapters.pipdeptree_adapter.subprocess.run")
    def test_non_list_dependencies_field(self, mock_run, python_stack):
        """If dependencies field is not a list, it should be skipped."""
        packages = [{"package_name": "root", "dependencies": "not-a-list"}]
        mock_run.return_value = _make_completed_process(stdout=json.dumps(packages))
        adapter = PipdeptreeAdapter()
        findings = adapter.run([], "/project", python_stack)
        assert isinstance(findings, list)


# ===========================================================================
# JscpdAdapter tests
# ===========================================================================


class TestJscpdAdapter:
    """Tests for JscpdAdapter covering is_applicable, run, and _parse_duplicates."""

    def test_is_applicable_always_true(self, python_stack, js_stack, empty_stack):
        adapter = JscpdAdapter()
        assert adapter.is_applicable(python_stack) is True
        assert adapter.is_applicable(js_stack) is True
        assert adapter.is_applicable(empty_stack) is True

    def test_attributes(self):
        adapter = JscpdAdapter()
        assert adapter.name == "jscpd"
        assert adapter.tool_name == "jscpd"
        assert 84 in adapter.factors_covered

    @patch("zerg.performance.adapters.jscpd_adapter.subprocess.run")
    def test_run_subprocess_failure(self, mock_run, python_stack):
        mock_run.side_effect = subprocess.SubprocessError("boom")
        adapter = JscpdAdapter()
        result = adapter.run([], "/project", python_stack)
        assert result == []

    @patch("zerg.performance.adapters.jscpd_adapter.subprocess.run")
    def test_run_os_error(self, mock_run, python_stack):
        mock_run.side_effect = OSError("no binary")
        adapter = JscpdAdapter()
        result = adapter.run([], "/project", python_stack)
        assert result == []

    @patch("zerg.performance.adapters.jscpd_adapter.subprocess.run")
    def test_run_no_report_file(self, mock_run, python_stack):
        """When jscpd succeeds but produces no report file."""
        mock_run.return_value = _make_completed_process(stdout="")
        adapter = JscpdAdapter()
        result = adapter.run([], "/project", python_stack)
        assert result == []

    @patch("zerg.performance.adapters.jscpd_adapter.Path.exists", return_value=True)
    @patch("zerg.performance.adapters.jscpd_adapter.Path.read_text")
    @patch("zerg.performance.adapters.jscpd_adapter.subprocess.run")
    def test_run_invalid_json_in_report(self, mock_run, mock_read, mock_exists, python_stack):
        mock_run.return_value = _make_completed_process()
        mock_read.return_value = "not-json"
        adapter = JscpdAdapter()
        result = adapter.run([], "/project", python_stack)
        assert result == []

    def test_parse_duplicates_non_list_duplicates(self):
        adapter = JscpdAdapter()
        result = adapter._parse_duplicates({"duplicates": "not-a-list"})
        assert result == []

    def test_parse_duplicates_empty(self):
        adapter = JscpdAdapter()
        result = adapter._parse_duplicates({"duplicates": []})
        assert result == []

    def test_parse_duplicates_skips_small_blocks(self):
        """Blocks with < 10 lines should be skipped."""
        adapter = JscpdAdapter()
        data = {
            "duplicates": [
                {
                    "lines": 5,
                    "tokens": 20,
                    "firstFile": {"name": "a.py", "startLoc": {"line": 1}},
                    "secondFile": {"name": "b.py"},
                }
            ]
        }
        result = adapter._parse_duplicates(data)
        assert result == []

    def test_parse_duplicates_non_dict_entry(self):
        """Non-dict entries in duplicates should be skipped."""
        adapter = JscpdAdapter()
        data = {"duplicates": ["not-a-dict", 42]}
        result = adapter._parse_duplicates(data)
        assert result == []

    def test_parse_duplicates_non_int_lines(self):
        """Non-int lines value should be skipped."""
        adapter = JscpdAdapter()
        data = {
            "duplicates": [
                {
                    "lines": "many",
                    "tokens": 50,
                    "firstFile": {"name": "a.py", "startLoc": {"line": 1}},
                    "secondFile": {"name": "b.py"},
                }
            ]
        }
        result = adapter._parse_duplicates(data)
        assert result == []

    @pytest.mark.parametrize(
        "lines,expected_severity",
        [
            (55, Severity.HIGH),
            (30, Severity.MEDIUM),
            (15, Severity.LOW),
        ],
        ids=["high-dup", "medium-dup", "low-dup"],
    )
    def test_severity_for_lines(self, lines, expected_severity):
        adapter = JscpdAdapter()
        data = {
            "duplicates": [
                {
                    "lines": lines,
                    "tokens": 100,
                    "firstFile": {"name": "foo.py", "startLoc": {"line": 10}},
                    "secondFile": {"name": "bar.py"},
                }
            ]
        }
        findings = adapter._parse_duplicates(data)
        assert len(findings) == 1
        assert findings[0].severity == expected_severity
        assert findings[0].factor_id == 84
        assert findings[0].rule_id == "duplication"
        assert "foo.py" in findings[0].message
        assert "bar.py" in findings[0].message

    def test_parse_duplicates_non_dict_firstFile(self):
        """When firstFile is not a dict, should default to <unknown>."""
        adapter = JscpdAdapter()
        data = {
            "duplicates": [
                {
                    "lines": 20,
                    "tokens": 50,
                    "firstFile": "not-dict",
                    "secondFile": "also-not-dict",
                }
            ]
        }
        findings = adapter._parse_duplicates(data)
        assert len(findings) == 1
        assert "<unknown>" in findings[0].message

    def test_parse_duplicates_non_int_startLoc(self):
        """When startLoc line is not int, should default to 0."""
        adapter = JscpdAdapter()
        data = {
            "duplicates": [
                {
                    "lines": 20,
                    "tokens": 50,
                    "firstFile": {"name": "a.py", "startLoc": {"line": "bad"}},
                    "secondFile": {"name": "b.py"},
                }
            ]
        }
        findings = adapter._parse_duplicates(data)
        assert len(findings) == 1
        assert findings[0].line == 0


# ===========================================================================
# ClocAdapter tests
# ===========================================================================


class TestClocAdapter:
    """Tests for ClocAdapter covering is_applicable, run, and _analyze."""

    def test_is_applicable_always_true(self, python_stack, js_stack, empty_stack):
        adapter = ClocAdapter()
        assert adapter.is_applicable(python_stack) is True
        assert adapter.is_applicable(js_stack) is True
        assert adapter.is_applicable(empty_stack) is True

    def test_attributes(self):
        adapter = ClocAdapter()
        assert adapter.name == "cloc"
        assert adapter.tool_name == "cloc"
        assert 115 in adapter.factors_covered

    @patch("zerg.performance.adapters.cloc_adapter.subprocess.run")
    def test_run_subprocess_failure(self, mock_run, python_stack):
        mock_run.side_effect = subprocess.SubprocessError("boom")
        adapter = ClocAdapter()
        result = adapter.run([], "/project", python_stack)
        assert result == []

    @patch("zerg.performance.adapters.cloc_adapter.subprocess.run")
    def test_run_os_error(self, mock_run, python_stack):
        mock_run.side_effect = OSError("no cloc")
        adapter = ClocAdapter()
        result = adapter.run([], "/project", python_stack)
        assert result == []

    @patch("zerg.performance.adapters.cloc_adapter.subprocess.run")
    def test_run_invalid_json(self, mock_run, python_stack):
        mock_run.return_value = _make_completed_process(stdout="not json")
        adapter = ClocAdapter()
        result = adapter.run([], "/project", python_stack)
        assert result == []

    @patch("zerg.performance.adapters.cloc_adapter.subprocess.run")
    def test_run_non_dict_output(self, mock_run, python_stack):
        mock_run.return_value = _make_completed_process(stdout="[1,2,3]")
        adapter = ClocAdapter()
        result = adapter.run([], "/project", python_stack)
        assert result == []

    @patch("zerg.performance.adapters.cloc_adapter.subprocess.run")
    def test_analyze_no_sum_section(self, mock_run, python_stack):
        """Missing SUM section produces no findings."""
        data = {"Python": {"code": 100, "comment": 10, "nFiles": 5}}
        mock_run.return_value = _make_completed_process(stdout=json.dumps(data))
        adapter = ClocAdapter()
        result = adapter.run([], "/project", python_stack)
        assert result == []

    @patch("zerg.performance.adapters.cloc_adapter.subprocess.run")
    def test_analyze_non_dict_sum(self, mock_run, python_stack):
        """Non-dict SUM section produces no findings."""
        data = {"SUM": "not-a-dict"}
        mock_run.return_value = _make_completed_process(stdout=json.dumps(data))
        adapter = ClocAdapter()
        result = adapter.run([], "/project", python_stack)
        assert result == []

    @pytest.mark.parametrize(
        "code,comment,n_files,expect_low_comment,expect_large_codebase",
        [
            (1000, 10, 5, True, False),  # low comment ratio (< 5%)
            (1000, 200, 10, False, False),  # healthy ratio, small codebase
            (200000, 50000, 500, False, True),  # large codebase
            (200000, 100, 500, True, True),  # low ratio AND large
            (0, 0, 0, False, False),  # zero lines
        ],
        ids=[
            "low-comment-ratio",
            "healthy-codebase",
            "large-codebase",
            "low-ratio-and-large",
            "zero-lines",
        ],
    )
    @patch("zerg.performance.adapters.cloc_adapter.subprocess.run")
    def test_analyze_thresholds(
        self,
        mock_run,
        python_stack,
        code,
        comment,
        n_files,
        expect_low_comment,
        expect_large_codebase,
    ):
        data = {"SUM": {"code": code, "comment": comment, "nFiles": n_files}}
        mock_run.return_value = _make_completed_process(stdout=json.dumps(data))
        adapter = ClocAdapter()
        findings = adapter.run([], "/project", python_stack)

        low_comment = [f for f in findings if f.rule_id == "low-comment-ratio"]
        large = [f for f in findings if f.rule_id == "large-codebase"]

        if expect_low_comment:
            assert len(low_comment) == 1
            assert low_comment[0].severity == Severity.MEDIUM
        else:
            assert len(low_comment) == 0

        if expect_large_codebase:
            assert len(large) == 1
            assert large[0].severity == Severity.INFO
        else:
            assert len(large) == 0

    @patch("zerg.performance.adapters.cloc_adapter.subprocess.run")
    def test_analyze_non_numeric_values(self, mock_run, python_stack):
        """Non-numeric values for code/comment/nFiles should default to 0."""
        data = {"SUM": {"code": "many", "comment": None, "nFiles": "lots"}}
        mock_run.return_value = _make_completed_process(stdout=json.dumps(data))
        adapter = ClocAdapter()
        findings = adapter.run([], "/project", python_stack)
        # All defaulted to 0, total_meaningful == 0 -> no findings
        assert findings == []


# ===========================================================================
# DeptryAdapter tests
# ===========================================================================


class TestDeptryAdapter:
    """Tests for DeptryAdapter covering is_applicable, run, and _suggestion_for."""

    def test_is_applicable_python(self, python_stack):
        adapter = DeptryAdapter()
        assert adapter.is_applicable(python_stack) is True

    def test_is_applicable_non_python(self, js_stack):
        adapter = DeptryAdapter()
        assert adapter.is_applicable(js_stack) is False

    def test_attributes(self):
        adapter = DeptryAdapter()
        assert adapter.name == "deptry"
        assert adapter.tool_name == "deptry"
        assert 79 in adapter.factors_covered
        assert 120 in adapter.factors_covered

    @patch("zerg.performance.adapters.deptry_adapter.subprocess.run")
    def test_run_subprocess_failure(self, mock_run, python_stack):
        mock_run.side_effect = subprocess.SubprocessError("boom")
        adapter = DeptryAdapter()
        result = adapter.run([], "/project", python_stack)
        assert result == []

    @patch("zerg.performance.adapters.deptry_adapter.subprocess.run")
    def test_run_os_error(self, mock_run, python_stack):
        mock_run.side_effect = OSError("no deptry")
        adapter = DeptryAdapter()
        result = adapter.run([], "/project", python_stack)
        assert result == []

    @patch("zerg.performance.adapters.deptry_adapter.subprocess.run")
    def test_run_invalid_json(self, mock_run, python_stack):
        mock_run.return_value = _make_completed_process(stdout="not-json")
        adapter = DeptryAdapter()
        result = adapter.run([], "/project", python_stack)
        assert result == []

    @patch("zerg.performance.adapters.deptry_adapter.subprocess.run")
    def test_run_non_list_output(self, mock_run, python_stack):
        mock_run.return_value = _make_completed_process(stdout='{"key": "val"}')
        adapter = DeptryAdapter()
        result = adapter.run([], "/project", python_stack)
        assert result == []

    @patch("zerg.performance.adapters.deptry_adapter.subprocess.run")
    def test_run_empty_violations(self, mock_run, python_stack):
        mock_run.return_value = _make_completed_process(stdout="[]")
        adapter = DeptryAdapter()
        result = adapter.run([], "/project", python_stack)
        assert result == []

    @pytest.mark.parametrize(
        "error_code,expected_severity,expected_desc",
        [
            ("DEP001", Severity.HIGH, "Missing dependency"),
            ("DEP002", Severity.MEDIUM, "Unused dependency"),
            ("DEP003", Severity.LOW, "Transitive dependency used directly"),
            ("DEP004", Severity.LOW, "Misplaced dev dependency"),
            ("UNKNOWN", Severity.LOW, "Dependency issue"),
        ],
        ids=["DEP001", "DEP002", "DEP003", "DEP004", "unknown-code"],
    )
    @patch("zerg.performance.adapters.deptry_adapter.subprocess.run")
    def test_violation_error_codes(self, mock_run, python_stack, error_code, expected_severity, expected_desc):
        violations = [{"error_code": error_code, "module": "requests", "message": "issue detail"}]
        mock_run.return_value = _make_completed_process(stdout=json.dumps(violations))
        adapter = DeptryAdapter()
        findings = adapter.run([], "/project", python_stack)
        assert len(findings) == 1
        assert findings[0].severity == expected_severity
        assert expected_desc in findings[0].message
        assert findings[0].factor_id == 79
        assert findings[0].tool == "deptry"
        assert findings[0].rule_id == error_code

    @patch("zerg.performance.adapters.deptry_adapter.subprocess.run")
    def test_violation_without_message(self, mock_run, python_stack):
        """Violation with empty message uses shorter format."""
        violations = [{"error_code": "DEP001", "module": "flask", "message": ""}]
        mock_run.return_value = _make_completed_process(stdout=json.dumps(violations))
        adapter = DeptryAdapter()
        findings = adapter.run([], "/project", python_stack)
        assert len(findings) == 1
        assert findings[0].message == "Missing dependency: flask"

    @patch("zerg.performance.adapters.deptry_adapter.subprocess.run")
    def test_non_dict_violation_skipped(self, mock_run, python_stack):
        """Non-dict entries in violations list should be skipped."""
        violations = ["not-a-dict", 42, None]
        mock_run.return_value = _make_completed_process(stdout=json.dumps(violations))
        adapter = DeptryAdapter()
        findings = adapter.run([], "/project", python_stack)
        assert findings == []

    @pytest.mark.parametrize(
        "error_code,module,expected_snippet",
        [
            ("DEP001", "flask", "Add 'flask'"),
            ("DEP002", "requests", "Remove unused dependency 'requests'"),
            ("DEP003", "six", "Add 'six' as a direct dependency"),
            ("DEP004", "pytest", "Move 'pytest'"),
            ("UNKNOWN", "mystery", "Review dependency 'mystery'"),
        ],
        ids=["suggest-dep001", "suggest-dep002", "suggest-dep003", "suggest-dep004", "suggest-unknown"],
    )
    def test_suggestion_for(self, error_code, module, expected_snippet):
        result = DeptryAdapter._suggestion_for(error_code, module)
        assert expected_snippet in result

    @patch("zerg.performance.adapters.deptry_adapter.subprocess.run")
    def test_multiple_violations(self, mock_run, python_stack):
        """Multiple violations should produce multiple findings."""
        violations = [
            {"error_code": "DEP001", "module": "flask", "message": "missing"},
            {"error_code": "DEP002", "module": "unused-pkg", "message": "not used"},
            {"error_code": "DEP003", "module": "six", "message": "transitive"},
        ]
        mock_run.return_value = _make_completed_process(stdout=json.dumps(violations))
        adapter = DeptryAdapter()
        findings = adapter.run([], "/project", python_stack)
        assert len(findings) == 3
        rule_ids = {f.rule_id for f in findings}
        assert rule_ids == {"DEP001", "DEP002", "DEP003"}
