"""Unit tests for low-coverage performance adapters: jscpd, pipdeptree, cloc, deptry."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zerg.performance.adapters.cloc_adapter import ClocAdapter
from zerg.performance.adapters.deptry_adapter import _ERROR_MAP, DeptryAdapter
from zerg.performance.adapters.jscpd_adapter import JscpdAdapter
from zerg.performance.adapters.pipdeptree_adapter import PipdeptreeAdapter
from zerg.performance.types import DetectedStack, Severity

# Patch targets for subprocess.run in each adapter module
_JSCPD_RUN = "zerg.performance.adapters.jscpd_adapter.subprocess.run"
_PIPDEPTREE_RUN = "zerg.performance.adapters.pipdeptree_adapter.subprocess.run"
_CLOC_RUN = "zerg.performance.adapters.cloc_adapter.subprocess.run"
_DEPTRY_RUN = "zerg.performance.adapters.deptry_adapter.subprocess.run"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def python_stack() -> DetectedStack:
    return DetectedStack(languages=["python"], frameworks=[], has_docker=False)


@pytest.fixture()
def go_stack() -> DetectedStack:
    return DetectedStack(languages=["go"], frameworks=[], has_docker=False)


@pytest.fixture()
def empty_stack() -> DetectedStack:
    return DetectedStack(languages=[], frameworks=[], has_docker=False)


# ===================================================================
# JscpdAdapter
# ===================================================================


class TestJscpdAdapter:
    """Tests for the JscpdAdapter."""

    def test_attributes(self) -> None:
        adapter = JscpdAdapter()
        assert adapter.name == "jscpd"
        assert adapter.tool_name == "jscpd"
        assert adapter.factors_covered == [84]

    def test_is_applicable_always_true(self, python_stack: DetectedStack, go_stack: DetectedStack) -> None:
        adapter = JscpdAdapter()
        assert adapter.is_applicable(python_stack) is True
        assert adapter.is_applicable(go_stack) is True

    def test_run_success_with_duplicates(self, python_stack: DetectedStack) -> None:
        """Full run through _execute with a jscpd report containing duplicates."""
        report_data = {
            "duplicates": [
                {
                    "lines": 30,
                    "tokens": 150,
                    "firstFile": {
                        "name": "src/foo.py",
                        "startLoc": {"line": 10},
                    },
                    "secondFile": {
                        "name": "src/bar.py",
                    },
                },
            ]
        }

        adapter = JscpdAdapter()
        # Test through _execute directly to avoid tmpdir/shutil complexity
        with (
            patch(_JSCPD_RUN, return_value=MagicMock()),
            patch("zerg.performance.adapters.jscpd_adapter.Path") as mock_path_cls,
        ):
            mock_report = MagicMock()
            mock_report.exists.return_value = True
            mock_report.read_text.return_value = json.dumps(report_data)
            mock_path_cls.return_value.__truediv__ = MagicMock(return_value=mock_report)
            findings = adapter._execute("/project", "/tmp/out")

        assert len(findings) == 1
        f = findings[0]
        assert f.factor_id == 84
        assert f.severity == Severity.MEDIUM  # 30 lines -> MEDIUM
        assert "src/foo.py" in f.message
        assert "src/bar.py" in f.message
        assert f.file == "src/foo.py"
        assert f.line == 10
        assert f.tool == "jscpd"
        assert f.rule_id == "duplication"

    def test_run_subprocess_failure(self, python_stack: DetectedStack) -> None:
        """Subprocess error returns empty findings."""
        adapter = JscpdAdapter()
        with patch(
            _JSCPD_RUN,
            side_effect=subprocess.TimeoutExpired("jscpd", 180),
        ):
            findings = adapter._execute("/project", "/tmp/out")
        assert findings == []

    def test_run_os_error(self, python_stack: DetectedStack) -> None:
        """OSError returns empty findings."""
        adapter = JscpdAdapter()
        with patch(_JSCPD_RUN, side_effect=OSError("not found")):
            findings = adapter._execute("/project", "/tmp/out")
        assert findings == []

    def test_execute_report_not_found(self, python_stack: DetectedStack) -> None:
        """Missing report file returns empty findings."""
        adapter = JscpdAdapter()
        with (
            patch(_JSCPD_RUN, return_value=MagicMock()),
            patch("zerg.performance.adapters.jscpd_adapter.Path") as mock_path_cls,
        ):
            mock_report = MagicMock()
            mock_report.exists.return_value = False
            mock_path_cls.return_value.__truediv__ = MagicMock(return_value=mock_report)
            findings = adapter._execute("/project", "/tmp/out")
        assert findings == []

    def test_execute_json_decode_error(self, python_stack: DetectedStack) -> None:
        """Corrupted JSON report returns empty findings."""
        adapter = JscpdAdapter()
        with (
            patch(_JSCPD_RUN, return_value=MagicMock()),
            patch("zerg.performance.adapters.jscpd_adapter.Path") as mock_path_cls,
        ):
            mock_report = MagicMock()
            mock_report.exists.return_value = True
            mock_report.read_text.return_value = "NOT JSON"
            mock_path_cls.return_value.__truediv__ = MagicMock(return_value=mock_report)
            findings = adapter._execute("/project", "/tmp/out")
        assert findings == []

    def test_parse_duplicates_empty(self) -> None:
        """Empty duplicates list produces no findings."""
        adapter = JscpdAdapter()
        assert adapter._parse_duplicates({"duplicates": []}) == []

    def test_parse_duplicates_not_a_list(self) -> None:
        """Non-list duplicates value returns empty."""
        adapter = JscpdAdapter()
        assert adapter._parse_duplicates({"duplicates": "bad"}) == []

    def test_parse_duplicates_no_key(self) -> None:
        """Missing duplicates key returns empty."""
        adapter = JscpdAdapter()
        assert adapter._parse_duplicates({}) == []

    def test_parse_duplicates_skips_non_dict(self) -> None:
        """Non-dict entries in duplicates are skipped."""
        adapter = JscpdAdapter()
        findings = adapter._parse_duplicates({"duplicates": ["not a dict", 42]})
        assert findings == []

    def test_parse_duplicates_skips_small_blocks(self) -> None:
        """Blocks with fewer than 10 lines are skipped."""
        adapter = JscpdAdapter()
        data = {
            "duplicates": [
                {"lines": 5, "tokens": 20, "firstFile": {"name": "a.py"}, "secondFile": {"name": "b.py"}},
            ]
        }
        assert adapter._parse_duplicates(data) == []

    def test_parse_duplicates_lines_not_int(self) -> None:
        """Non-integer lines value is skipped."""
        adapter = JscpdAdapter()
        data = {
            "duplicates": [
                {"lines": "many", "tokens": 20, "firstFile": {"name": "a.py"}, "secondFile": {"name": "b.py"}},
            ]
        }
        assert adapter._parse_duplicates(data) == []

    def test_parse_duplicates_non_dict_file_entries(self) -> None:
        """Non-dict firstFile/secondFile produce <unknown> names."""
        adapter = JscpdAdapter()
        data = {
            "duplicates": [
                {
                    "lines": 25,
                    "tokens": 100,
                    "firstFile": "not a dict",
                    "secondFile": None,
                },
            ]
        }
        findings = adapter._parse_duplicates(data)
        assert len(findings) == 1
        assert "<unknown>" in findings[0].message
        assert findings[0].line == 0

    def test_parse_duplicates_start_line_not_int(self) -> None:
        """Non-integer startLoc line defaults to 0."""
        adapter = JscpdAdapter()
        data = {
            "duplicates": [
                {
                    "lines": 15,
                    "tokens": 60,
                    "firstFile": {"name": "a.py", "startLoc": {"line": "bad"}},
                    "secondFile": {"name": "b.py"},
                },
            ]
        }
        findings = adapter._parse_duplicates(data)
        assert len(findings) == 1
        assert findings[0].line == 0

    def test_severity_for_lines_low(self) -> None:
        assert JscpdAdapter._severity_for_lines(10) == Severity.LOW

    def test_severity_for_lines_medium(self) -> None:
        assert JscpdAdapter._severity_for_lines(25) == Severity.MEDIUM

    def test_severity_for_lines_high(self) -> None:
        assert JscpdAdapter._severity_for_lines(60) == Severity.HIGH

    def test_severity_for_lines_boundaries(self) -> None:
        assert JscpdAdapter._severity_for_lines(20) == Severity.LOW
        assert JscpdAdapter._severity_for_lines(21) == Severity.MEDIUM
        assert JscpdAdapter._severity_for_lines(50) == Severity.MEDIUM
        assert JscpdAdapter._severity_for_lines(51) == Severity.HIGH

    def test_run_cleans_up_tmpdir_on_success(self, python_stack: DetectedStack) -> None:
        """Temp directory is cleaned up after successful run."""
        adapter = JscpdAdapter()
        with (
            patch(
                "zerg.performance.adapters.jscpd_adapter.tempfile.mkdtemp",
                return_value="/tmp/jscpd-test",
            ),
            patch("shutil.rmtree") as mock_rmtree,
            patch.object(adapter, "_execute", return_value=[]),
        ):
            adapter.run([], "/project", python_stack)
        mock_rmtree.assert_called_once_with("/tmp/jscpd-test", ignore_errors=True)

    def test_run_cleans_up_tmpdir_on_exception(self, python_stack: DetectedStack) -> None:
        """Temp directory is cleaned up even when _execute raises."""
        adapter = JscpdAdapter()
        with (
            patch(
                "zerg.performance.adapters.jscpd_adapter.tempfile.mkdtemp",
                return_value="/tmp/jscpd-test",
            ),
            patch("shutil.rmtree") as mock_rmtree,
            patch.object(adapter, "_execute", side_effect=RuntimeError("boom")),
        ):
            with pytest.raises(RuntimeError, match="boom"):
                adapter.run([], "/project", python_stack)
        mock_rmtree.assert_called_once_with("/tmp/jscpd-test", ignore_errors=True)

    def test_run_end_to_end_via_run_method(self, python_stack: DetectedStack, tmp_path: Path) -> None:
        """Test the full run() method including tmpdir creation and cleanup."""
        report_data = {
            "duplicates": [
                {
                    "lines": 55,
                    "tokens": 300,
                    "firstFile": {"name": "x.py", "startLoc": {"line": 1}},
                    "secondFile": {"name": "y.py"},
                },
            ]
        }
        adapter = JscpdAdapter()
        # Use a real tmpdir via tmp_path to avoid mocking shutil
        tmpdir = str(tmp_path / "jscpd-out")

        with (
            patch(
                "zerg.performance.adapters.jscpd_adapter.tempfile.mkdtemp",
                return_value=tmpdir,
            ),
            patch(_JSCPD_RUN, return_value=MagicMock()),
        ):
            # Create the report file where _execute expects it
            import os

            os.makedirs(tmpdir, exist_ok=True)
            report_path = Path(tmpdir) / "jscpd-report.json"
            report_path.write_text(json.dumps(report_data))

            findings = adapter.run([], "/project", python_stack)

        assert len(findings) == 1
        assert findings[0].severity == Severity.HIGH  # 55 lines -> HIGH


# ===================================================================
# PipdeptreeAdapter
# ===================================================================


class TestPipdeptreeAdapter:
    """Tests for the PipdeptreeAdapter."""

    def test_attributes(self) -> None:
        adapter = PipdeptreeAdapter()
        assert adapter.name == "pipdeptree"
        assert adapter.tool_name == "pipdeptree"
        assert adapter.factors_covered == [80]

    def test_is_applicable_python(self, python_stack: DetectedStack) -> None:
        adapter = PipdeptreeAdapter()
        assert adapter.is_applicable(python_stack) is True

    def test_is_applicable_non_python(self, go_stack: DetectedStack) -> None:
        adapter = PipdeptreeAdapter()
        assert adapter.is_applicable(go_stack) is False

    def test_run_subprocess_failure(self, python_stack: DetectedStack) -> None:
        adapter = PipdeptreeAdapter()
        with patch(_PIPDEPTREE_RUN, side_effect=OSError("not found")):
            findings = adapter.run([], ".", python_stack)
        assert findings == []

    def test_run_timeout(self, python_stack: DetectedStack) -> None:
        adapter = PipdeptreeAdapter()
        with patch(
            _PIPDEPTREE_RUN,
            side_effect=subprocess.TimeoutExpired("pipdeptree", 120),
        ):
            findings = adapter.run([], ".", python_stack)
        assert findings == []

    def test_run_invalid_json(self, python_stack: DetectedStack) -> None:
        mock_result = MagicMock()
        mock_result.stdout = "NOT JSON"
        adapter = PipdeptreeAdapter()
        with patch(_PIPDEPTREE_RUN, return_value=mock_result):
            findings = adapter.run([], ".", python_stack)
        assert findings == []

    def test_run_non_list_output(self, python_stack: DetectedStack) -> None:
        """Output that is valid JSON but not a list returns empty."""
        mock_result = MagicMock()
        mock_result.stdout = json.dumps({"key": "value"})
        mock_result.stderr = ""
        adapter = PipdeptreeAdapter()
        with patch(_PIPDEPTREE_RUN, return_value=mock_result):
            findings = adapter.run([], ".", python_stack)
        assert findings == []

    def test_run_small_tree_no_findings(self, python_stack: DetectedStack) -> None:
        """Small dependency tree with shallow depth produces no findings."""
        data = [
            {
                "package": {"key": "flask"},
                "dependencies": [
                    {"package_name": "click", "dependencies": []},
                ],
            },
        ]
        mock_result = MagicMock()
        mock_result.stdout = json.dumps(data)
        mock_result.stderr = ""
        adapter = PipdeptreeAdapter()
        with patch(_PIPDEPTREE_RUN, return_value=mock_result):
            findings = adapter.run([], ".", python_stack)
        assert findings == []

    def test_run_high_transitive_count(self, python_stack: DetectedStack) -> None:
        """More than 200 transitive deps triggers HIGH severity."""
        deps = [{"package_name": f"pkg{i}", "dependencies": []} for i in range(250)]
        data = [{"package": {"key": "big"}, "dependencies": deps}]
        mock_result = MagicMock()
        mock_result.stdout = json.dumps(data)
        mock_result.stderr = ""
        adapter = PipdeptreeAdapter()
        with patch(_PIPDEPTREE_RUN, return_value=mock_result):
            findings = adapter.run([], ".", python_stack)

        count_findings = [f for f in findings if f.rule_id == "transitive-count-high"]
        assert len(count_findings) == 1
        assert count_findings[0].severity == Severity.HIGH

    def test_run_medium_transitive_count(self, python_stack: DetectedStack) -> None:
        """Between 101 and 200 transitive deps triggers MEDIUM severity."""
        deps = [{"package_name": f"pkg{i}", "dependencies": []} for i in range(150)]
        data = [{"package": {"key": "med"}, "dependencies": deps}]
        mock_result = MagicMock()
        mock_result.stdout = json.dumps(data)
        mock_result.stderr = ""
        adapter = PipdeptreeAdapter()
        with patch(_PIPDEPTREE_RUN, return_value=mock_result):
            findings = adapter.run([], ".", python_stack)

        count_findings = [f for f in findings if f.rule_id == "transitive-count-medium"]
        assert len(count_findings) == 1
        assert count_findings[0].severity == Severity.MEDIUM

    def test_run_deep_dependency_chain_high(self, python_stack: DetectedStack) -> None:
        """Depth > 10 triggers HIGH severity depth finding."""
        inner = {"package_name": "leaf", "dependencies": []}
        for i in range(11):
            inner = {"package_name": f"level_{i}", "dependencies": [inner]}
        data = [{"package": {"key": "root"}, "dependencies": [inner]}]
        mock_result = MagicMock()
        mock_result.stdout = json.dumps(data)
        mock_result.stderr = ""
        adapter = PipdeptreeAdapter()
        with patch(_PIPDEPTREE_RUN, return_value=mock_result):
            findings = adapter.run([], ".", python_stack)

        depth_findings = [f for f in findings if f.rule_id == "depth-high"]
        assert len(depth_findings) == 1
        assert depth_findings[0].severity == Severity.HIGH

    def test_run_deep_dependency_chain_medium(self, python_stack: DetectedStack) -> None:
        """Depth between 6 and 10 triggers MEDIUM severity depth finding."""
        inner = {"package_name": "leaf", "dependencies": []}
        for i in range(6):
            inner = {"package_name": f"level_{i}", "dependencies": [inner]}
        data = [{"package": {"key": "root"}, "dependencies": [inner]}]
        mock_result = MagicMock()
        mock_result.stdout = json.dumps(data)
        mock_result.stderr = ""
        adapter = PipdeptreeAdapter()
        with patch(_PIPDEPTREE_RUN, return_value=mock_result):
            findings = adapter.run([], ".", python_stack)

        depth_findings = [f for f in findings if f.rule_id == "depth-medium"]
        assert len(depth_findings) == 1
        assert depth_findings[0].severity == Severity.MEDIUM

    def test_run_version_conflict_in_stderr(self, python_stack: DetectedStack) -> None:
        """Conflict keyword in stderr triggers version-conflict finding."""
        data = [{"package": {"key": "a"}, "dependencies": []}]
        mock_result = MagicMock()
        mock_result.stdout = json.dumps(data)
        mock_result.stderr = "Warning: version conflict detected for package X"
        adapter = PipdeptreeAdapter()
        with patch(_PIPDEPTREE_RUN, return_value=mock_result):
            findings = adapter.run([], ".", python_stack)

        conflict_findings = [f for f in findings if f.rule_id == "version-conflict"]
        assert len(conflict_findings) == 1
        assert conflict_findings[0].severity == Severity.HIGH

    def test_analyze_tree_skips_non_dict_packages(self) -> None:
        """Non-dict entries in packages list are skipped."""
        adapter = PipdeptreeAdapter()
        findings = adapter._analyze_tree(["not a dict", 42], "")
        assert findings == []

    def test_analyze_tree_non_list_dependencies(self) -> None:
        """Non-list dependencies field is handled gracefully."""
        adapter = PipdeptreeAdapter()
        packages = [{"package": {"key": "x"}, "dependencies": "bad"}]
        findings = adapter._analyze_tree(packages, "")
        assert findings == []

    def test_measure_deps_skips_non_dict(self) -> None:
        """Non-dict entries in deps list are skipped."""
        adapter = PipdeptreeAdapter()
        depth, count = adapter._measure_deps(["not a dict", 42])
        assert count == 0
        assert depth == 1

    def test_measure_deps_recursive(self) -> None:
        """Recursive measurement counts depth and total correctly."""
        adapter = PipdeptreeAdapter()
        deps = [
            {
                "package_name": "a",
                "dependencies": [
                    {
                        "package_name": "b",
                        "dependencies": [
                            {"package_name": "c", "dependencies": []},
                        ],
                    },
                ],
            },
        ]
        depth, count = adapter._measure_deps(deps)
        assert depth == 3
        assert count == 3  # a, b, c

    def test_measure_deps_non_list_children(self) -> None:
        """Non-list children field is handled."""
        adapter = PipdeptreeAdapter()
        deps = [{"package_name": "a", "dependencies": "not a list"}]
        depth, count = adapter._measure_deps(deps)
        assert count == 1
        assert depth == 1

    def test_run_no_stderr(self, python_stack: DetectedStack) -> None:
        """When stderr is None, it should fallback to empty string."""
        data = [{"package": {"key": "a"}, "dependencies": []}]
        mock_result = MagicMock()
        mock_result.stdout = json.dumps(data)
        mock_result.stderr = None
        adapter = PipdeptreeAdapter()
        with patch(_PIPDEPTREE_RUN, return_value=mock_result):
            findings = adapter.run([], ".", python_stack)
        # Should not raise; no conflict findings
        conflict_findings = [f for f in findings if f.rule_id == "version-conflict"]
        assert conflict_findings == []


# ===================================================================
# ClocAdapter
# ===================================================================


class TestClocAdapter:
    """Tests for the ClocAdapter."""

    def test_attributes(self) -> None:
        adapter = ClocAdapter()
        assert adapter.name == "cloc"
        assert adapter.tool_name == "cloc"
        assert adapter.factors_covered == [115]

    def test_is_applicable_always_true(self, python_stack: DetectedStack, go_stack: DetectedStack) -> None:
        adapter = ClocAdapter()
        assert adapter.is_applicable(python_stack) is True
        assert adapter.is_applicable(go_stack) is True

    def test_run_subprocess_failure(self, python_stack: DetectedStack) -> None:
        adapter = ClocAdapter()
        with patch(_CLOC_RUN, side_effect=OSError("not found")):
            findings = adapter.run([], ".", python_stack)
        assert findings == []

    def test_run_timeout(self, python_stack: DetectedStack) -> None:
        adapter = ClocAdapter()
        with patch(
            _CLOC_RUN,
            side_effect=subprocess.TimeoutExpired("cloc", 180),
        ):
            findings = adapter.run([], ".", python_stack)
        assert findings == []

    def test_run_invalid_json(self, python_stack: DetectedStack) -> None:
        mock_result = MagicMock()
        mock_result.stdout = "NOT VALID JSON"
        adapter = ClocAdapter()
        with patch(_CLOC_RUN, return_value=mock_result):
            findings = adapter.run([], ".", python_stack)
        assert findings == []

    def test_run_non_dict_output(self, python_stack: DetectedStack) -> None:
        """Valid JSON that is not a dict returns empty."""
        mock_result = MagicMock()
        mock_result.stdout = json.dumps([1, 2, 3])
        adapter = ClocAdapter()
        with patch(_CLOC_RUN, return_value=mock_result):
            findings = adapter.run([], ".", python_stack)
        assert findings == []

    def test_analyze_missing_sum(self) -> None:
        """Missing SUM section returns empty findings."""
        adapter = ClocAdapter()
        findings = adapter._analyze({"Python": {"code": 100}})
        assert findings == []

    def test_analyze_sum_not_dict(self) -> None:
        """SUM that is not a dict returns empty."""
        adapter = ClocAdapter()
        findings = adapter._analyze({"SUM": "bad"})
        assert findings == []

    def test_analyze_low_comment_ratio(self) -> None:
        """Comment ratio below 5% triggers MEDIUM finding."""
        adapter = ClocAdapter()
        data = {"SUM": {"code": 1000, "comment": 10, "nFiles": 20}}
        findings = adapter._analyze(data)

        low_comment = [f for f in findings if f.rule_id == "low-comment-ratio"]
        assert len(low_comment) == 1
        assert low_comment[0].severity == Severity.MEDIUM
        assert "documentation ratio" in low_comment[0].message.lower()

    def test_analyze_good_comment_ratio(self) -> None:
        """Comment ratio above 5% does not trigger finding."""
        adapter = ClocAdapter()
        data = {"SUM": {"code": 1000, "comment": 200, "nFiles": 20}}
        findings = adapter._analyze(data)
        low_comment = [f for f in findings if f.rule_id == "low-comment-ratio"]
        assert low_comment == []

    def test_analyze_large_codebase(self) -> None:
        """Codebase with >100k lines triggers INFO finding."""
        adapter = ClocAdapter()
        data = {"SUM": {"code": 150000, "comment": 30000, "nFiles": 500}}
        findings = adapter._analyze(data)

        large = [f for f in findings if f.rule_id == "large-codebase"]
        assert len(large) == 1
        assert large[0].severity == Severity.INFO
        assert "150,000" in large[0].message

    def test_analyze_small_codebase_no_large_finding(self) -> None:
        """Codebase under 100k lines does not trigger large-codebase."""
        adapter = ClocAdapter()
        data = {"SUM": {"code": 5000, "comment": 1000, "nFiles": 30}}
        findings = adapter._analyze(data)
        large = [f for f in findings if f.rule_id == "large-codebase"]
        assert large == []

    def test_analyze_zero_code_lines(self) -> None:
        """Zero code and comment lines => no comment ratio finding."""
        adapter = ClocAdapter()
        data = {"SUM": {"code": 0, "comment": 0, "nFiles": 0}}
        findings = adapter._analyze(data)
        assert findings == []

    def test_analyze_non_numeric_fields(self) -> None:
        """Non-numeric code/comment/nFiles default to 0."""
        adapter = ClocAdapter()
        data = {"SUM": {"code": "bad", "comment": None, "nFiles": "x"}}
        findings = adapter._analyze(data)
        # All default to 0, total_meaningful=0, no findings
        assert findings == []

    def test_run_full_pipeline(self, python_stack: DetectedStack) -> None:
        """End-to-end run with low comment ratio."""
        cloc_output = json.dumps({"SUM": {"code": 2000, "comment": 50, "nFiles": 10}})
        mock_result = MagicMock()
        mock_result.stdout = cloc_output
        adapter = ClocAdapter()
        with patch(_CLOC_RUN, return_value=mock_result):
            findings = adapter.run([], "/project", python_stack)
        assert len(findings) == 1
        assert findings[0].rule_id == "low-comment-ratio"

    def test_analyze_both_low_comment_and_large_codebase(self) -> None:
        """Large codebase with low comments triggers both findings."""
        adapter = ClocAdapter()
        data = {"SUM": {"code": 200000, "comment": 100, "nFiles": 800}}
        findings = adapter._analyze(data)
        rule_ids = {f.rule_id for f in findings}
        assert "low-comment-ratio" in rule_ids
        assert "large-codebase" in rule_ids


# ===================================================================
# DeptryAdapter
# ===================================================================


class TestDeptryAdapter:
    """Tests for the DeptryAdapter."""

    def test_attributes(self) -> None:
        adapter = DeptryAdapter()
        assert adapter.name == "deptry"
        assert adapter.tool_name == "deptry"
        assert adapter.factors_covered == [79, 120]

    def test_is_applicable_python(self, python_stack: DetectedStack) -> None:
        adapter = DeptryAdapter()
        assert adapter.is_applicable(python_stack) is True

    def test_is_applicable_non_python(self, go_stack: DetectedStack) -> None:
        adapter = DeptryAdapter()
        assert adapter.is_applicable(go_stack) is False

    def test_run_subprocess_failure(self, python_stack: DetectedStack) -> None:
        adapter = DeptryAdapter()
        with patch(_DEPTRY_RUN, side_effect=OSError("not found")):
            findings = adapter.run([], ".", python_stack)
        assert findings == []

    def test_run_timeout(self, python_stack: DetectedStack) -> None:
        adapter = DeptryAdapter()
        with patch(
            _DEPTRY_RUN,
            side_effect=subprocess.TimeoutExpired("deptry", 120),
        ):
            findings = adapter.run([], ".", python_stack)
        assert findings == []

    def test_run_invalid_json(self, python_stack: DetectedStack) -> None:
        mock_result = MagicMock()
        mock_result.stdout = "NOT JSON"
        adapter = DeptryAdapter()
        with patch(_DEPTRY_RUN, return_value=mock_result):
            findings = adapter.run([], ".", python_stack)
        assert findings == []

    def test_run_non_list_output(self, python_stack: DetectedStack) -> None:
        mock_result = MagicMock()
        mock_result.stdout = json.dumps({"key": "value"})
        adapter = DeptryAdapter()
        with patch(_DEPTRY_RUN, return_value=mock_result):
            findings = adapter.run([], ".", python_stack)
        assert findings == []

    def test_run_dep001_missing_dependency(self, python_stack: DetectedStack) -> None:
        """DEP001 (missing dependency) maps to HIGH severity."""
        data = [
            {
                "error_code": "DEP001",
                "module": "requests",
                "message": "requests is not in dependencies",
            }
        ]
        mock_result = MagicMock()
        mock_result.stdout = json.dumps(data)
        adapter = DeptryAdapter()
        with patch(_DEPTRY_RUN, return_value=mock_result):
            findings = adapter.run([], "/project", python_stack)

        assert len(findings) == 1
        f = findings[0]
        assert f.severity == Severity.HIGH
        assert f.factor_id == 79
        assert f.rule_id == "DEP001"
        assert "Missing dependency" in f.message
        assert "requests" in f.message
        assert f.tool == "deptry"
        assert "Add 'requests'" in f.suggestion

    def test_run_dep002_unused_dependency(self, python_stack: DetectedStack) -> None:
        """DEP002 (unused dependency) maps to MEDIUM severity."""
        data = [
            {
                "error_code": "DEP002",
                "module": "flask",
                "message": "flask is not used",
            }
        ]
        mock_result = MagicMock()
        mock_result.stdout = json.dumps(data)
        adapter = DeptryAdapter()
        with patch(_DEPTRY_RUN, return_value=mock_result):
            findings = adapter.run([], "/project", python_stack)

        assert len(findings) == 1
        assert findings[0].severity == Severity.MEDIUM
        assert findings[0].rule_id == "DEP002"
        assert "Remove unused dependency" in findings[0].suggestion

    def test_run_dep003_transitive_dependency(self, python_stack: DetectedStack) -> None:
        """DEP003 (transitive dependency) maps to LOW severity."""
        data = [
            {
                "error_code": "DEP003",
                "module": "six",
                "message": "six is a transitive dependency",
            }
        ]
        mock_result = MagicMock()
        mock_result.stdout = json.dumps(data)
        adapter = DeptryAdapter()
        with patch(_DEPTRY_RUN, return_value=mock_result):
            findings = adapter.run([], "/project", python_stack)

        assert len(findings) == 1
        assert findings[0].severity == Severity.LOW
        assert findings[0].rule_id == "DEP003"
        assert "direct dependency" in findings[0].suggestion

    def test_run_dep004_misplaced_dev_dependency(self, python_stack: DetectedStack) -> None:
        """DEP004 (misplaced dev dependency) maps to LOW severity."""
        data = [
            {
                "error_code": "DEP004",
                "module": "pytest",
                "message": "pytest is a dev dependency used in prod",
            }
        ]
        mock_result = MagicMock()
        mock_result.stdout = json.dumps(data)
        adapter = DeptryAdapter()
        with patch(_DEPTRY_RUN, return_value=mock_result):
            findings = adapter.run([], "/project", python_stack)

        assert len(findings) == 1
        assert findings[0].severity == Severity.LOW
        assert findings[0].rule_id == "DEP004"
        assert "Move" in findings[0].suggestion

    def test_run_unknown_error_code(self, python_stack: DetectedStack) -> None:
        """Unknown error code defaults to LOW severity."""
        data = [
            {
                "error_code": "DEP999",
                "module": "something",
                "message": "Unknown issue",
            }
        ]
        mock_result = MagicMock()
        mock_result.stdout = json.dumps(data)
        adapter = DeptryAdapter()
        with patch(_DEPTRY_RUN, return_value=mock_result):
            findings = adapter.run([], "/project", python_stack)

        assert len(findings) == 1
        assert findings[0].severity == Severity.LOW
        assert "Dependency issue" in findings[0].message
        assert "Review dependency" in findings[0].suggestion

    def test_run_violation_no_message(self, python_stack: DetectedStack) -> None:
        """Violation without message uses desc only."""
        data = [
            {
                "error_code": "DEP001",
                "module": "numpy",
                "message": "",
            }
        ]
        mock_result = MagicMock()
        mock_result.stdout = json.dumps(data)
        adapter = DeptryAdapter()
        with patch(_DEPTRY_RUN, return_value=mock_result):
            findings = adapter.run([], "/project", python_stack)

        assert len(findings) == 1
        # When message is empty, format is "desc: module"
        assert findings[0].message == "Missing dependency: numpy"

    def test_run_skips_non_dict_violations(self, python_stack: DetectedStack) -> None:
        """Non-dict entries in violations list are skipped."""
        data = [
            "not a dict",
            42,
            {"error_code": "DEP002", "module": "flask", "message": "unused"},
        ]
        mock_result = MagicMock()
        mock_result.stdout = json.dumps(data)
        adapter = DeptryAdapter()
        with patch(_DEPTRY_RUN, return_value=mock_result):
            findings = adapter.run([], "/project", python_stack)

        assert len(findings) == 1
        assert findings[0].rule_id == "DEP002"

    def test_run_multiple_violations(self, python_stack: DetectedStack) -> None:
        """Multiple violations are all returned."""
        data = [
            {"error_code": "DEP001", "module": "a", "message": "missing"},
            {"error_code": "DEP002", "module": "b", "message": "unused"},
            {"error_code": "DEP003", "module": "c", "message": "transitive"},
        ]
        mock_result = MagicMock()
        mock_result.stdout = json.dumps(data)
        adapter = DeptryAdapter()
        with patch(_DEPTRY_RUN, return_value=mock_result):
            findings = adapter.run([], "/project", python_stack)

        assert len(findings) == 3
        assert {f.rule_id for f in findings} == {"DEP001", "DEP002", "DEP003"}

    def test_suggestion_for_all_known_codes(self) -> None:
        """All known error codes produce specific suggestions."""
        for code in ("DEP001", "DEP002", "DEP003", "DEP004"):
            suggestion = DeptryAdapter._suggestion_for(code, "mymod")
            assert "mymod" in suggestion
            assert suggestion != "Review dependency 'mymod'"

    def test_suggestion_for_unknown_code(self) -> None:
        """Unknown error code produces generic suggestion."""
        suggestion = DeptryAdapter._suggestion_for("UNKNOWN", "mymod")
        assert suggestion == "Review dependency 'mymod'"

    def test_error_map_completeness(self) -> None:
        """Verify _ERROR_MAP contains expected entries."""
        assert "DEP001" in _ERROR_MAP
        assert "DEP002" in _ERROR_MAP
        assert "DEP003" in _ERROR_MAP
        assert "DEP004" in _ERROR_MAP
        assert _ERROR_MAP["DEP001"][0] == Severity.HIGH
        assert _ERROR_MAP["DEP002"][0] == Severity.MEDIUM
        assert _ERROR_MAP["DEP003"][0] == Severity.LOW
        assert _ERROR_MAP["DEP004"][0] == Severity.LOW

    def test_run_empty_list(self, python_stack: DetectedStack) -> None:
        """Empty violations list returns no findings."""
        mock_result = MagicMock()
        mock_result.stdout = json.dumps([])
        adapter = DeptryAdapter()
        with patch(_DEPTRY_RUN, return_value=mock_result):
            findings = adapter.run([], "/project", python_stack)
        assert findings == []
