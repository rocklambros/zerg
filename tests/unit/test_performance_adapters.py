"""Unit tests for performance analysis tool adapters."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zerg.performance.adapters.dive_adapter import DiveAdapter
from zerg.performance.adapters.hadolint_adapter import HadolintAdapter
from zerg.performance.adapters.lizard_adapter import LizardAdapter
from zerg.performance.adapters.radon_adapter import RadonAdapter
from zerg.performance.adapters.semgrep_adapter import SemgrepAdapter
from zerg.performance.adapters.trivy_adapter import TrivyAdapter
from zerg.performance.adapters.vulture_adapter import VultureAdapter
from zerg.performance.types import DetectedStack, Severity

# Patch targets for subprocess.run in each adapter module
_SEMGREP_RUN = "zerg.performance.adapters.semgrep_adapter.subprocess.run"
_RADON_RUN = "zerg.performance.adapters.radon_adapter.subprocess.run"
_LIZARD_RUN = "zerg.performance.adapters.lizard_adapter.subprocess.run"
_VULTURE_RUN = "zerg.performance.adapters.vulture_adapter.subprocess.run"
_HADOLINT_RUN = "zerg.performance.adapters.hadolint_adapter.subprocess.run"
_TRIVY_RUN = "zerg.performance.adapters.trivy_adapter.subprocess.run"


@pytest.fixture()
def python_stack() -> DetectedStack:
    return DetectedStack(languages=["python"], frameworks=[], has_docker=False)


@pytest.fixture()
def docker_stack() -> DetectedStack:
    return DetectedStack(languages=["python"], frameworks=[], has_docker=True)


# ===================================================================
# SemgrepAdapter
# ===================================================================


class TestSemgrepAdapter:
    """Tests for the SemgrepAdapter."""

    def test_parse_results(self, python_stack: DetectedStack) -> None:
        """Verify PerformanceFinding from mocked semgrep JSON."""
        sample_output = json.dumps(
            {
                "results": [
                    {
                        "check_id": "python.lang.security.audit.sqli",
                        "path": "test.py",
                        "start": {"line": 10},
                        "extra": {
                            "message": "Issue found",
                            "severity": "WARNING",
                        },
                    }
                ],
                "errors": [],
            }
        )

        mock_result = MagicMock()
        mock_result.stdout = sample_output

        adapter = SemgrepAdapter()
        with patch(_SEMGREP_RUN, return_value=mock_result):
            findings = adapter.run([], ".", python_stack)

        assert len(findings) == 1
        f = findings[0]
        assert f.file == "test.py"
        assert f.line == 10
        assert f.severity == Severity.MEDIUM
        assert f.tool == "semgrep"
        assert f.factor_id == 127

    @pytest.mark.parametrize(
        "side_effect",
        [
            subprocess.TimeoutExpired(cmd="semgrep", timeout=300),
            OSError("not found"),
        ],
        ids=["timeout", "os_error"],
    )
    def test_subprocess_errors_return_empty(self, python_stack: DetectedStack, side_effect: Exception) -> None:
        """Timeout and OSError should return empty list."""
        adapter = SemgrepAdapter()
        with patch(_SEMGREP_RUN, side_effect=side_effect):
            findings = adapter.run([], ".", python_stack)
        assert findings == []


# ===================================================================
# RadonAdapter
# ===================================================================


class TestRadonAdapter:
    """Tests for the RadonAdapter."""

    def test_cyclomatic_complexity_high_rank(self, python_stack: DetectedStack) -> None:
        """Rank D finding should produce HIGH severity."""
        cc_output = json.dumps(
            {"test.py": [{"type": "function", "name": "foo", "complexity": 25, "rank": "D", "lineno": 5}]}
        )
        mi_output = json.dumps({})

        adapter = RadonAdapter()
        with patch(_RADON_RUN) as mock_run:
            mock_run.side_effect = [MagicMock(stdout=cc_output), MagicMock(stdout=mi_output)]
            findings = adapter.run([], ".", python_stack)

        assert len(findings) == 1
        assert findings[0].severity == Severity.HIGH
        assert findings[0].file == "test.py"

    def test_is_applicable_python_only(self) -> None:
        """Radon is applicable for Python, not Go."""
        adapter = RadonAdapter()
        py = DetectedStack(languages=["python"], frameworks=[], has_docker=False)
        go = DetectedStack(languages=["go"], frameworks=[], has_docker=False)
        assert adapter.is_applicable(py) is True
        assert adapter.is_applicable(go) is False

    def test_subprocess_failure(self, python_stack: DetectedStack) -> None:
        """Subprocess failure should return empty list."""
        adapter = RadonAdapter()
        with patch(_RADON_RUN, side_effect=OSError("not found")):
            findings = adapter.run([], ".", python_stack)
        assert findings == []


# ===================================================================
# LizardAdapter
# ===================================================================


class TestLizardAdapter:
    """Tests for the LizardAdapter."""

    @pytest.mark.parametrize(
        "csv_output,expected_severity,message_substr",
        [
            ("50,30,200,3,60,test.py@5,complex_func\n", Severity.HIGH, "cyclomatic"),
            ("50,45,300,3,60,test.py@1,very_complex\n", Severity.CRITICAL, "cyclomatic"),
        ],
        ids=["high_ccn", "critical_ccn"],
    )
    def test_ccn_severity(
        self, python_stack: DetectedStack, csv_output: str, expected_severity: Severity, message_substr: str
    ) -> None:
        """CCN thresholds map to correct severity."""
        mock_result = MagicMock()
        mock_result.stdout = csv_output
        adapter = LizardAdapter()
        with patch(_LIZARD_RUN, return_value=mock_result):
            findings = adapter.run([], ".", python_stack)
        ccn = [f for f in findings if message_substr in f.message]
        assert len(ccn) == 1
        assert ccn[0].severity == expected_severity

    def test_subprocess_failure(self, python_stack: DetectedStack) -> None:
        """Subprocess failure returns empty list."""
        adapter = LizardAdapter()
        with patch(_LIZARD_RUN, side_effect=OSError("not found")):
            findings = adapter.run([], ".", python_stack)
        assert findings == []


# ===================================================================
# VultureAdapter
# ===================================================================


class TestVultureAdapter:
    """Tests for the VultureAdapter."""

    @pytest.mark.parametrize(
        "vulture_output,expected_severity",
        [
            ("test.py:10: unused function 'foo' (90% confidence)\n", Severity.MEDIUM),
            ("app.py:5: unused variable 'x' (100% confidence)\n", Severity.HIGH),
            ("lib.py:20: unused import 'os' (80% confidence)\n", Severity.LOW),
        ],
        ids=["90pct_medium", "100pct_high", "80pct_low"],
    )
    def test_confidence_to_severity(
        self, python_stack: DetectedStack, vulture_output: str, expected_severity: Severity
    ) -> None:
        """Vulture confidence levels map to correct severity."""
        mock_result = MagicMock()
        mock_result.stdout = vulture_output
        adapter = VultureAdapter()
        with patch(_VULTURE_RUN, return_value=mock_result):
            findings = adapter.run([], ".", python_stack)
        assert len(findings) == 1
        assert findings[0].severity == expected_severity

    def test_subprocess_failure(self, python_stack: DetectedStack) -> None:
        """Subprocess failure returns empty list."""
        adapter = VultureAdapter()
        with patch(_VULTURE_RUN, side_effect=OSError("not found")):
            findings = adapter.run([], ".", python_stack)
        assert findings == []


# ===================================================================
# DiveAdapter
# ===================================================================


class TestDiveAdapter:
    """Tests for the DiveAdapter."""

    def test_mergeable_runs(self, tmp_path: Path, docker_stack: DetectedStack) -> None:
        """Multiple consecutive RUN -> LOW finding."""
        (tmp_path / "Dockerfile").write_text(
            "FROM python:3.11\nRUN apt-get update\nRUN apt-get install -y curl\nRUN pip install flask\nCOPY . /app\n"
        )
        adapter = DiveAdapter()
        findings = adapter.run([], str(tmp_path), docker_stack)
        mergeable = [f for f in findings if f.rule_id == "dive-mergeable-runs"]
        assert len(mergeable) == 1
        assert mergeable[0].severity == Severity.LOW

    def test_is_applicable_docker_only(self, docker_stack: DetectedStack) -> None:
        """Dive only applicable when Docker is present."""
        adapter = DiveAdapter()
        py = DetectedStack(languages=["python"], frameworks=[], has_docker=False)
        assert adapter.is_applicable(docker_stack) is True
        assert adapter.is_applicable(py) is False

    def test_no_dockerfile(self, tmp_path: Path, docker_stack: DetectedStack) -> None:
        """No Dockerfile should produce no findings."""
        adapter = DiveAdapter()
        findings = adapter.run([], str(tmp_path), docker_stack)
        assert findings == []


# ===================================================================
# HadolintAdapter
# ===================================================================


class TestHadolintAdapter:
    """Tests for the HadolintAdapter."""

    def test_parse_json_output(self, tmp_path: Path, docker_stack: DetectedStack) -> None:
        """Hadolint JSON output parsed into findings."""
        (tmp_path / "Dockerfile").write_text("FROM python:3.11\n")
        hadolint_output = json.dumps(
            [{"line": 1, "code": "DL3008", "message": "Pin versions in apt get install", "level": "warning"}]
        )
        mock_result = MagicMock()
        mock_result.stdout = hadolint_output
        adapter = HadolintAdapter()
        with patch(_HADOLINT_RUN, return_value=mock_result):
            findings = adapter.run([], str(tmp_path), docker_stack)
        assert len(findings) == 1
        assert findings[0].severity == Severity.MEDIUM
        assert findings[0].rule_id == "DL3008"

    def test_subprocess_failure(self, tmp_path: Path, docker_stack: DetectedStack) -> None:
        """Subprocess failure returns empty list."""
        (tmp_path / "Dockerfile").write_text("FROM python:3.11\n")
        adapter = HadolintAdapter()
        with patch(_HADOLINT_RUN, side_effect=OSError("not found")):
            findings = adapter.run([], str(tmp_path), docker_stack)
        assert findings == []


# ===================================================================
# TrivyAdapter
# ===================================================================


class TestTrivyAdapter:
    """Tests for the TrivyAdapter."""

    def test_parse_vulnerabilities(self, python_stack: DetectedStack) -> None:
        """Trivy vulnerability results parsed correctly."""
        trivy_output = json.dumps(
            {
                "Results": [
                    {
                        "Target": "requirements.txt",
                        "Vulnerabilities": [
                            {
                                "VulnerabilityID": "CVE-2023-1234",
                                "PkgName": "flask",
                                "InstalledVersion": "2.0.0",
                                "FixedVersion": "2.3.0",
                                "Severity": "HIGH",
                                "Title": "XSS vulnerability",
                            }
                        ],
                    }
                ]
            }
        )
        mock_result = MagicMock()
        mock_result.stdout = trivy_output
        adapter = TrivyAdapter()
        with patch(_TRIVY_RUN, return_value=mock_result):
            findings = adapter.run([], ".", python_stack)
        assert len(findings) == 1
        assert findings[0].severity == Severity.HIGH
        assert "CVE-2023-1234" in findings[0].message

    def test_subprocess_failure(self, python_stack: DetectedStack) -> None:
        """Subprocess failure returns empty list."""
        adapter = TrivyAdapter()
        with patch(_TRIVY_RUN, side_effect=OSError("not found")):
            findings = adapter.run([], ".", python_stack)
        assert findings == []
