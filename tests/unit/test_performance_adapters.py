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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def python_stack() -> DetectedStack:
    return DetectedStack(
        languages=["python"],
        frameworks=[],
        has_docker=False,
    )


@pytest.fixture()
def go_stack() -> DetectedStack:
    return DetectedStack(
        languages=["go"],
        frameworks=[],
        has_docker=False,
    )


@pytest.fixture()
def docker_stack() -> DetectedStack:
    return DetectedStack(
        languages=["python"],
        frameworks=[],
        has_docker=True,
    )


@pytest.fixture()
def empty_stack() -> DetectedStack:
    return DetectedStack(languages=[], frameworks=[], has_docker=False)


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
        assert f.severity == Severity.MEDIUM  # WARNING -> MEDIUM
        assert f.message == "Issue found"
        assert f.tool == "semgrep"
        # "sqli" substring matches SQL injection factor
        assert f.factor_id == 127
        assert f.category == "Security Patterns"

    def test_empty_results(self, python_stack: DetectedStack) -> None:
        """Empty results list produces no findings."""
        mock_result = MagicMock()
        mock_result.stdout = json.dumps(
            {"results": [], "errors": []},
        )

        adapter = SemgrepAdapter()
        with patch(_SEMGREP_RUN, return_value=mock_result):
            findings = adapter.run([], ".", python_stack)

        assert findings == []

    def test_config_selection_python(self) -> None:
        """Python stack includes 'p/python' in config."""
        adapter = SemgrepAdapter()
        stack = DetectedStack(
            languages=["python"],
            frameworks=[],
            has_docker=True,
        )
        configs = adapter._build_configs(stack)
        assert "p/python" in configs
        assert "p/python-best-practices" in configs
        # Docker infra config
        assert "p/dockerfile" in configs

    def test_is_applicable_always_true(
        self,
        python_stack: DetectedStack,
    ) -> None:
        """SemgrepAdapter inherits default is_applicable."""
        adapter = SemgrepAdapter()
        assert adapter.is_applicable(python_stack) is True

    def test_subprocess_timeout(
        self,
        python_stack: DetectedStack,
    ) -> None:
        """Timeout should return empty list."""
        adapter = SemgrepAdapter()
        with patch(
            _SEMGREP_RUN,
            side_effect=subprocess.TimeoutExpired(
                cmd="semgrep",
                timeout=300,
            ),
        ):
            findings = adapter.run([], ".", python_stack)
        assert findings == []

    def test_subprocess_os_error(
        self,
        python_stack: DetectedStack,
    ) -> None:
        """OSError should return empty list."""
        adapter = SemgrepAdapter()
        with patch(
            _SEMGREP_RUN,
            side_effect=OSError("not found"),
        ):
            findings = adapter.run([], ".", python_stack)
        assert findings == []

    def test_empty_stdout(
        self,
        python_stack: DetectedStack,
    ) -> None:
        """Empty stdout should return empty findings."""
        mock_result = MagicMock()
        mock_result.stdout = ""
        adapter = SemgrepAdapter()
        with patch(_SEMGREP_RUN, return_value=mock_result):
            findings = adapter.run([], ".", python_stack)
        assert findings == []

    def test_no_configs_for_empty_stack(
        self,
        empty_stack: DetectedStack,
    ) -> None:
        """Empty stack produces no configs."""
        adapter = SemgrepAdapter()
        configs = adapter._build_configs(empty_stack)
        assert configs == []


# ===================================================================
# RadonAdapter
# ===================================================================


class TestRadonAdapter:
    """Tests for the RadonAdapter."""

    def test_cyclomatic_complexity_high_rank(
        self,
        python_stack: DetectedStack,
    ) -> None:
        """Rank D finding should produce HIGH severity."""
        cc_output = json.dumps(
            {
                "test.py": [
                    {
                        "type": "function",
                        "name": "foo",
                        "complexity": 25,
                        "rank": "D",
                        "lineno": 5,
                    }
                ]
            }
        )
        mi_output = json.dumps({})

        adapter = RadonAdapter()
        with patch(_RADON_RUN) as mock_run:
            mock_run.side_effect = [
                MagicMock(stdout=cc_output),
                MagicMock(stdout=mi_output),
            ]
            findings = adapter.run([], ".", python_stack)

        assert len(findings) == 1
        f = findings[0]
        assert f.severity == Severity.HIGH
        assert f.factor_id == 1
        assert f.file == "test.py"
        assert f.line == 5
        assert "foo" in f.message
        assert "25" in f.message

    def test_is_applicable_python(
        self,
        python_stack: DetectedStack,
    ) -> None:
        """Radon is applicable for Python stacks."""
        adapter = RadonAdapter()
        assert adapter.is_applicable(python_stack) is True

    def test_is_applicable_go(self, go_stack: DetectedStack) -> None:
        """Radon is not applicable for Go-only stacks."""
        adapter = RadonAdapter()
        assert adapter.is_applicable(go_stack) is False

    def test_subprocess_failure(
        self,
        python_stack: DetectedStack,
    ) -> None:
        """Subprocess failure should return empty list."""
        adapter = RadonAdapter()
        with patch(
            _RADON_RUN,
            side_effect=OSError("not found"),
        ):
            findings = adapter.run([], ".", python_stack)
        assert findings == []

    def test_skip_rank_a_b(
        self,
        python_stack: DetectedStack,
    ) -> None:
        """Rank A and B findings should be skipped."""
        cc_output = json.dumps(
            {
                "test.py": [
                    {
                        "type": "function",
                        "name": "simple",
                        "complexity": 3,
                        "rank": "A",
                        "lineno": 1,
                    },
                    {
                        "type": "function",
                        "name": "moderate",
                        "complexity": 8,
                        "rank": "B",
                        "lineno": 10,
                    },
                ]
            }
        )
        mi_output = json.dumps({})

        adapter = RadonAdapter()
        with patch(_RADON_RUN) as mock_run:
            mock_run.side_effect = [
                MagicMock(stdout=cc_output),
                MagicMock(stdout=mi_output),
            ]
            findings = adapter.run([], ".", python_stack)

        assert findings == []

    def test_maintainability_index(
        self,
        python_stack: DetectedStack,
    ) -> None:
        """MI rank D should produce a finding."""
        cc_output = json.dumps({})
        mi_output = json.dumps(
            {
                "bad_file.py": {"rank": "D", "mi": 5.2},
            }
        )

        adapter = RadonAdapter()
        with patch(_RADON_RUN) as mock_run:
            mock_run.side_effect = [
                MagicMock(stdout=cc_output),
                MagicMock(stdout=mi_output),
            ]
            findings = adapter.run([], ".", python_stack)

        assert len(findings) == 1
        assert findings[0].factor_id == 28
        assert findings[0].severity == Severity.HIGH


# ===================================================================
# LizardAdapter
# ===================================================================


class TestLizardAdapter:
    """Tests for the LizardAdapter."""

    def test_high_ccn_finding(
        self,
        python_stack: DetectedStack,
    ) -> None:
        """High CCN value should produce a finding."""
        # CSV: NLOC, CCN, token, PARAM, length, location, name
        csv_output = "50,30,200,3,60,test.py@5,complex_func\n"

        mock_result = MagicMock()
        mock_result.stdout = csv_output

        adapter = LizardAdapter()
        with patch(_LIZARD_RUN, return_value=mock_result):
            findings = adapter.run([], ".", python_stack)

        # CCN=30 (>25) -> HIGH severity
        ccn = [f for f in findings if "cyclomatic" in f.message]
        assert len(ccn) == 1
        assert ccn[0].severity == Severity.HIGH
        assert ccn[0].file == "test.py"
        assert ccn[0].line == 5

    def test_critical_ccn(
        self,
        python_stack: DetectedStack,
    ) -> None:
        """CCN > 40 should be CRITICAL."""
        csv_output = "50,45,300,3,60,test.py@1,very_complex\n"
        mock_result = MagicMock()
        mock_result.stdout = csv_output

        adapter = LizardAdapter()
        with patch(_LIZARD_RUN, return_value=mock_result):
            findings = adapter.run([], ".", python_stack)

        ccn = [f for f in findings if "cyclomatic" in f.message]
        assert len(ccn) == 1
        assert ccn[0].severity == Severity.CRITICAL

    def test_large_function(
        self,
        python_stack: DetectedStack,
    ) -> None:
        """NLOC > 200 should produce HIGH severity finding."""
        csv_output = "250,5,500,2,260,test.py@10,big_func\n"
        mock_result = MagicMock()
        mock_result.stdout = csv_output

        adapter = LizardAdapter()
        with patch(_LIZARD_RUN, return_value=mock_result):
            findings = adapter.run([], ".", python_stack)

        nloc = [f for f in findings if "lines of code" in f.message]
        assert len(nloc) == 1
        assert nloc[0].severity == Severity.HIGH

    def test_excessive_params(
        self,
        python_stack: DetectedStack,
    ) -> None:
        """More than 5 params should produce LOW finding."""
        csv_output = "20,3,50,8,25,test.py@1,many_params\n"
        mock_result = MagicMock()
        mock_result.stdout = csv_output

        adapter = LizardAdapter()
        with patch(_LIZARD_RUN, return_value=mock_result):
            findings = adapter.run([], ".", python_stack)

        params = [f for f in findings if "parameters" in f.message]
        assert len(params) == 1
        assert params[0].severity == Severity.LOW

    def test_is_applicable_always(
        self,
        python_stack: DetectedStack,
        go_stack: DetectedStack,
    ) -> None:
        """Lizard is always applicable."""
        adapter = LizardAdapter()
        assert adapter.is_applicable(python_stack) is True
        assert adapter.is_applicable(go_stack) is True

    def test_subprocess_failure(
        self,
        python_stack: DetectedStack,
    ) -> None:
        """Subprocess failure returns empty list."""
        adapter = LizardAdapter()
        with patch(
            _LIZARD_RUN,
            side_effect=OSError("not found"),
        ):
            findings = adapter.run([], ".", python_stack)
        assert findings == []


# ===================================================================
# VultureAdapter
# ===================================================================


class TestVultureAdapter:
    """Tests for the VultureAdapter."""

    def test_parse_output(
        self,
        python_stack: DetectedStack,
    ) -> None:
        """Vulture output should be parsed into findings."""
        vulture_output = "test.py:10: unused function 'foo' (90% confidence)\n"
        mock_result = MagicMock()
        mock_result.stdout = vulture_output

        adapter = VultureAdapter()
        with patch(_VULTURE_RUN, return_value=mock_result):
            findings = adapter.run([], ".", python_stack)

        assert len(findings) == 1
        f = findings[0]
        assert f.severity == Severity.MEDIUM  # 90% -> MEDIUM
        assert f.file == "test.py"
        assert f.line == 10
        assert "foo" in f.message
        assert f.tool == "vulture"

    def test_high_confidence(
        self,
        python_stack: DetectedStack,
    ) -> None:
        """100% confidence should map to HIGH severity."""
        vulture_output = "app.py:5: unused variable 'x' (100% confidence)\n"
        mock_result = MagicMock()
        mock_result.stdout = vulture_output

        adapter = VultureAdapter()
        with patch(_VULTURE_RUN, return_value=mock_result):
            findings = adapter.run([], ".", python_stack)

        assert len(findings) == 1
        assert findings[0].severity == Severity.HIGH

    def test_low_confidence(
        self,
        python_stack: DetectedStack,
    ) -> None:
        """80% confidence should map to LOW severity."""
        vulture_output = "lib.py:20: unused import 'os' (80% confidence)\n"
        mock_result = MagicMock()
        mock_result.stdout = vulture_output

        adapter = VultureAdapter()
        with patch(_VULTURE_RUN, return_value=mock_result):
            findings = adapter.run([], ".", python_stack)

        assert len(findings) == 1
        assert findings[0].severity == Severity.LOW

    def test_is_applicable_python_only(
        self,
        python_stack: DetectedStack,
        go_stack: DetectedStack,
    ) -> None:
        """Vulture only applicable for Python."""
        adapter = VultureAdapter()
        assert adapter.is_applicable(python_stack) is True
        assert adapter.is_applicable(go_stack) is False

    def test_subprocess_failure(
        self,
        python_stack: DetectedStack,
    ) -> None:
        """Subprocess failure returns empty list."""
        adapter = VultureAdapter()
        with patch(
            _VULTURE_RUN,
            side_effect=OSError("not found"),
        ):
            findings = adapter.run([], ".", python_stack)
        assert findings == []

    def test_empty_output(
        self,
        python_stack: DetectedStack,
    ) -> None:
        """Empty output produces no findings."""
        mock_result = MagicMock()
        mock_result.stdout = ""

        adapter = VultureAdapter()
        with patch(_VULTURE_RUN, return_value=mock_result):
            findings = adapter.run([], ".", python_stack)
        assert findings == []


# ===================================================================
# DiveAdapter
# ===================================================================


class TestDiveAdapter:
    """Tests for the DiveAdapter."""

    def test_mergeable_runs(
        self,
        tmp_path: Path,
        docker_stack: DetectedStack,
    ) -> None:
        """Multiple consecutive RUN -> LOW finding."""
        dockerfile = tmp_path / "Dockerfile"
        dockerfile.write_text(
            "FROM python:3.11\nRUN apt-get update\nRUN apt-get install -y curl\nRUN pip install flask\nCOPY . /app\n"
        )

        adapter = DiveAdapter()
        findings = adapter.run([], str(tmp_path), docker_stack)

        mergeable = [f for f in findings if f.rule_id == "dive-mergeable-runs"]
        assert len(mergeable) == 1
        assert mergeable[0].severity == Severity.LOW

    def test_no_multistage(
        self,
        tmp_path: Path,
        docker_stack: DetectedStack,
    ) -> None:
        """Single FROM -> MEDIUM finding for no multi-stage."""
        dockerfile = tmp_path / "Dockerfile"
        dockerfile.write_text("FROM python:3.11\nCOPY . /app\n")

        adapter = DiveAdapter()
        findings = adapter.run([], str(tmp_path), docker_stack)

        ms = [f for f in findings if f.rule_id == "dive-no-multistage"]
        assert len(ms) == 1
        assert ms[0].severity == Severity.MEDIUM

    def test_multistage_no_finding(
        self,
        tmp_path: Path,
        docker_stack: DetectedStack,
    ) -> None:
        """Multi-stage build -> no multistage finding."""
        dockerfile = tmp_path / "Dockerfile"
        dockerfile.write_text(
            "FROM python:3.11 AS builder\nRUN pip install build\nFROM python:3.11-slim\nCOPY --from=builder /app /app\n"
        )

        adapter = DiveAdapter()
        findings = adapter.run([], str(tmp_path), docker_stack)

        ms = [f for f in findings if f.rule_id == "dive-no-multistage"]
        assert len(ms) == 0

    def test_is_applicable_docker_only(
        self,
        docker_stack: DetectedStack,
        python_stack: DetectedStack,
    ) -> None:
        """Dive only applicable when Docker is present."""
        adapter = DiveAdapter()
        assert adapter.is_applicable(docker_stack) is True
        assert adapter.is_applicable(python_stack) is False

    def test_no_dockerfile(
        self,
        tmp_path: Path,
        docker_stack: DetectedStack,
    ) -> None:
        """No Dockerfile should produce no findings."""
        adapter = DiveAdapter()
        findings = adapter.run([], str(tmp_path), docker_stack)
        assert findings == []


# ===================================================================
# HadolintAdapter
# ===================================================================


class TestHadolintAdapter:
    """Tests for the HadolintAdapter."""

    def test_parse_json_output(
        self,
        tmp_path: Path,
        docker_stack: DetectedStack,
    ) -> None:
        """Hadolint JSON output parsed into findings."""
        dockerfile = tmp_path / "Dockerfile"
        dockerfile.write_text("FROM python:3.11\n")

        hadolint_output = json.dumps(
            [
                {
                    "line": 1,
                    "code": "DL3008",
                    "message": "Pin versions in apt get install",
                    "level": "warning",
                }
            ]
        )

        mock_result = MagicMock()
        mock_result.stdout = hadolint_output

        adapter = HadolintAdapter()
        with patch(_HADOLINT_RUN, return_value=mock_result):
            findings = adapter.run(
                [],
                str(tmp_path),
                docker_stack,
            )

        assert len(findings) == 1
        f = findings[0]
        assert f.severity == Severity.MEDIUM
        assert f.line == 1
        assert f.rule_id == "DL3008"
        assert "Pin versions" in f.message

    def test_is_applicable_docker_only(
        self,
        docker_stack: DetectedStack,
        python_stack: DetectedStack,
    ) -> None:
        """Hadolint only applicable when Docker is present."""
        adapter = HadolintAdapter()
        assert adapter.is_applicable(docker_stack) is True
        assert adapter.is_applicable(python_stack) is False

    def test_subprocess_failure(
        self,
        tmp_path: Path,
        docker_stack: DetectedStack,
    ) -> None:
        """Subprocess failure returns empty list."""
        dockerfile = tmp_path / "Dockerfile"
        dockerfile.write_text("FROM python:3.11\n")

        adapter = HadolintAdapter()
        with patch(
            _HADOLINT_RUN,
            side_effect=OSError("not found"),
        ):
            findings = adapter.run(
                [],
                str(tmp_path),
                docker_stack,
            )
        assert findings == []

    def test_empty_output(
        self,
        tmp_path: Path,
        docker_stack: DetectedStack,
    ) -> None:
        """Empty JSON array returns no findings."""
        dockerfile = tmp_path / "Dockerfile"
        dockerfile.write_text("FROM python:3.11\n")

        mock_result = MagicMock()
        mock_result.stdout = "[]"

        adapter = HadolintAdapter()
        with patch(_HADOLINT_RUN, return_value=mock_result):
            findings = adapter.run(
                [],
                str(tmp_path),
                docker_stack,
            )
        assert findings == []


# ===================================================================
# TrivyAdapter
# ===================================================================


class TestTrivyAdapter:
    """Tests for the TrivyAdapter."""

    def test_parse_vulnerabilities(
        self,
        python_stack: DetectedStack,
    ) -> None:
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
        f = findings[0]
        assert f.severity == Severity.HIGH
        assert f.factor_id == 22
        assert "CVE-2023-1234" in f.message
        assert f.file == "requirements.txt"

    def test_severity_mapping(
        self,
        python_stack: DetectedStack,
    ) -> None:
        """Trivy severities should map correctly."""
        trivy_output = json.dumps(
            {
                "Results": [
                    {
                        "Target": "go.sum",
                        "Vulnerabilities": [
                            {
                                "VulnerabilityID": "CVE-2023-0001",
                                "Severity": "CRITICAL",
                                "Title": "RCE",
                                "PkgName": "pkg",
                                "InstalledVersion": "1.0",
                            },
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

        assert findings[0].severity == Severity.CRITICAL

    def test_misconfigurations(
        self,
        python_stack: DetectedStack,
    ) -> None:
        """Trivy misconfigurations should be parsed."""
        trivy_output = json.dumps(
            {
                "Results": [
                    {
                        "Target": "Dockerfile",
                        "Misconfigurations": [
                            {
                                "ID": "DS002",
                                "Title": "Root user",
                                "Severity": "HIGH",
                                "Description": "Running as root",
                                "Resolution": "Add USER instruction",
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
        assert findings[0].factor_id == 24
        assert findings[0].severity == Severity.HIGH

    def test_secrets(
        self,
        python_stack: DetectedStack,
    ) -> None:
        """Trivy secrets should be parsed."""
        trivy_output = json.dumps(
            {
                "Results": [
                    {
                        "Target": "config.py",
                        "Secrets": [
                            {
                                "RuleID": "aws-access-key",
                                "Title": "AWS Access Key",
                                "Match": "AKIA***",
                                "StartLine": 5,
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
        assert findings[0].factor_id == 23
        assert findings[0].line == 5

    def test_is_applicable_always(
        self,
        python_stack: DetectedStack,
        go_stack: DetectedStack,
    ) -> None:
        """Trivy is always applicable."""
        adapter = TrivyAdapter()
        assert adapter.is_applicable(python_stack) is True
        assert adapter.is_applicable(go_stack) is True

    def test_subprocess_failure(
        self,
        python_stack: DetectedStack,
    ) -> None:
        """Subprocess failure returns empty list."""
        adapter = TrivyAdapter()
        with patch(
            _TRIVY_RUN,
            side_effect=OSError("not found"),
        ):
            findings = adapter.run([], ".", python_stack)
        assert findings == []

    def test_empty_results(
        self,
        python_stack: DetectedStack,
    ) -> None:
        """Empty Results array returns no findings."""
        mock_result = MagicMock()
        mock_result.stdout = json.dumps({"Results": []})

        adapter = TrivyAdapter()
        with patch(_TRIVY_RUN, return_value=mock_result):
            findings = adapter.run([], ".", python_stack)
        assert findings == []
