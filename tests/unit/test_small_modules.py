"""Tests for small modules: render_utils, json_utils, retry_backoff, trivy_adapter.

Covers:
- zerg/render_utils.py (re-export shim)
- zerg/json_utils.py (JSON encoding/decoding with optional orjson)
- zerg/retry_backoff.py (exponential backoff calculator)
- zerg/performance/adapters/trivy_adapter.py (Trivy output parser)
"""

from __future__ import annotations

import io
import json
import sys
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from zerg.performance.adapters.trivy_adapter import (
    _MISCONFIG_SEVERITY,
    _VULN_SEVERITY,
    TrivyAdapter,
)
from zerg.performance.types import DetectedStack, Severity
from zerg.retry_backoff import RetryBackoffCalculator

# ────────────────────────────────────────────────────────────────
# render_utils  (backward-compatibility shim)
# ────────────────────────────────────────────────────────────────


class TestRenderUtilsReExports:
    """Verify render_utils re-exports all expected symbols from rendering.shared."""

    def test_format_elapsed_compact_reexported(self) -> None:
        from zerg.render_utils import format_elapsed_compact
        from zerg.rendering.shared import (
            format_elapsed_compact as original,
        )

        assert format_elapsed_compact is original

    def test_render_gantt_chart_reexported(self) -> None:
        from zerg.render_utils import render_gantt_chart
        from zerg.rendering.shared import render_gantt_chart as original

        assert render_gantt_chart is original

    def test_render_progress_bar_reexported(self) -> None:
        from zerg.render_utils import render_progress_bar
        from zerg.rendering.shared import render_progress_bar as original

        assert render_progress_bar is original

    def test_render_progress_bar_str_reexported(self) -> None:
        from zerg.render_utils import render_progress_bar_str
        from zerg.rendering.shared import (
            render_progress_bar_str as original,
        )

        assert render_progress_bar_str is original

    def test_all_exports_match(self) -> None:
        import zerg.render_utils as mod

        assert set(mod.__all__) == {
            "format_elapsed_compact",
            "render_gantt_chart",
            "render_progress_bar",
            "render_progress_bar_str",
        }


# ────────────────────────────────────────────────────────────────
# json_utils  (stdlib fallback path)
# ────────────────────────────────────────────────────────────────


class TestJsonUtilsStdlib:
    """Test json_utils when using stdlib json (orjson not available)."""

    def _reload_without_orjson(self) -> Any:
        """Force-reload json_utils with orjson import blocked."""
        saved = sys.modules.get("orjson")
        sys.modules["orjson"] = None  # type: ignore[assignment]
        try:
            # Remove cached module to force re-import
            sys.modules.pop("zerg.json_utils", None)
            import zerg.json_utils as mod

            return mod
        finally:
            if saved is not None:
                sys.modules["orjson"] = saved
            else:
                sys.modules.pop("orjson", None)
            # Restore original module
            sys.modules.pop("zerg.json_utils", None)

    def test_has_orjson_false(self) -> None:
        mod = self._reload_without_orjson()
        assert mod.HAS_ORJSON is False

    def test_loads_parses_string(self) -> None:
        mod = self._reload_without_orjson()
        result = mod.loads('{"a": 1}')
        assert result == {"a": 1}

    def test_loads_parses_bytes(self) -> None:
        mod = self._reload_without_orjson()
        result = mod.loads(b'{"b": 2}')
        assert result == {"b": 2}

    def test_dumps_returns_str(self) -> None:
        mod = self._reload_without_orjson()
        result = mod.dumps({"x": 42})
        assert isinstance(result, str)
        assert json.loads(result) == {"x": 42}

    def test_dumps_with_indent(self) -> None:
        mod = self._reload_without_orjson()
        result = mod.dumps({"k": "v"}, indent=True)
        assert isinstance(result, str)
        # Indented output contains newlines
        assert "\n" in result
        assert json.loads(result) == {"k": "v"}

    def test_load_from_file(self) -> None:
        mod = self._reload_without_orjson()
        fp = io.StringIO('{"file": true}')
        result = mod.load(fp)
        assert result == {"file": True}

    def test_dump_to_file(self) -> None:
        mod = self._reload_without_orjson()
        fp = io.StringIO()
        mod.dump({"out": 1}, fp)
        fp.seek(0)
        assert json.loads(fp.read()) == {"out": 1}

    def test_dump_to_file_with_indent(self) -> None:
        mod = self._reload_without_orjson()
        fp = io.StringIO()
        mod.dump({"out": 2}, fp, indent=True)
        fp.seek(0)
        content = fp.read()
        assert "\n" in content
        assert json.loads(content) == {"out": 2}

    def test_all_exports(self) -> None:
        mod = self._reload_without_orjson()
        assert set(mod.__all__) == {"HAS_ORJSON", "dump", "dumps", "load", "loads"}


class TestJsonUtilsOrjson:
    """Test json_utils when orjson IS available (the try-branch)."""

    def _reload_with_orjson(self) -> Any:
        """Force-reload json_utils ensuring orjson is importable."""
        # Remove cached module to force re-import through the try branch
        sys.modules.pop("zerg.json_utils", None)
        import zerg.json_utils as mod

        return mod

    def test_has_orjson_true(self) -> None:
        mod = self._reload_with_orjson()
        assert mod.HAS_ORJSON is True

    def test_loads_parses_string(self) -> None:
        mod = self._reload_with_orjson()
        result = mod.loads('{"a": 1}')
        assert result == {"a": 1}

    def test_loads_parses_bytes(self) -> None:
        mod = self._reload_with_orjson()
        result = mod.loads(b'{"b": 2}')
        assert result == {"b": 2}

    def test_dumps_returns_str_not_bytes(self) -> None:
        mod = self._reload_with_orjson()
        result = mod.dumps({"x": 42})
        assert isinstance(result, str)
        assert json.loads(result) == {"x": 42}

    def test_dumps_with_indent(self) -> None:
        mod = self._reload_with_orjson()
        result = mod.dumps({"k": "v"}, indent=True)
        assert isinstance(result, str)
        assert "\n" in result
        assert json.loads(result) == {"k": "v"}

    def test_load_from_file(self) -> None:
        mod = self._reload_with_orjson()
        fp = io.BytesIO(b'{"file": true}')
        result = mod.load(fp)
        assert result == {"file": True}

    def test_dump_to_file(self) -> None:
        mod = self._reload_with_orjson()
        fp = io.StringIO()
        mod.dump({"out": 1}, fp)
        fp.seek(0)
        assert json.loads(fp.read()) == {"out": 1}

    def test_dump_to_file_with_indent(self) -> None:
        mod = self._reload_with_orjson()
        fp = io.StringIO()
        mod.dump({"out": 2}, fp, indent=True)
        fp.seek(0)
        content = fp.read()
        assert "\n" in content
        assert json.loads(content) == {"out": 2}


# ────────────────────────────────────────────────────────────────
# retry_backoff
# ────────────────────────────────────────────────────────────────


class TestRetryBackoffCalculator:
    """Test RetryBackoffCalculator.calculate_delay for all strategies."""

    def test_exponential_strategy(self) -> None:
        delay = RetryBackoffCalculator.calculate_delay(
            attempt=2, strategy="exponential", base_seconds=10, max_seconds=300
        )
        # 10 * 2^2 = 40, ±10% jitter -> 36..44
        assert 36.0 <= delay <= 44.0

    def test_linear_strategy(self) -> None:
        delay = RetryBackoffCalculator.calculate_delay(attempt=3, strategy="linear", base_seconds=5, max_seconds=300)
        # 5 * 3 = 15, ±10% jitter -> 13.5..16.5
        assert 13.5 <= delay <= 16.5

    def test_fixed_strategy(self) -> None:
        delay = RetryBackoffCalculator.calculate_delay(attempt=5, strategy="fixed", base_seconds=10, max_seconds=300)
        # 10, ±10% jitter -> 9..11
        assert 9.0 <= delay <= 11.0

    def test_unknown_strategy_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown backoff strategy"):
            RetryBackoffCalculator.calculate_delay(attempt=1, strategy="quadratic", base_seconds=1, max_seconds=10)

    def test_max_seconds_cap(self) -> None:
        delay = RetryBackoffCalculator.calculate_delay(
            attempt=20, strategy="exponential", base_seconds=10, max_seconds=60
        )
        # 10 * 2^20 is huge, but capped at 60 with ±10% jitter -> 54..66
        assert 54.0 <= delay <= 66.0

    def test_returns_float(self) -> None:
        delay = RetryBackoffCalculator.calculate_delay(attempt=1, strategy="fixed", base_seconds=5, max_seconds=100)
        assert isinstance(delay, float)

    def test_never_negative(self) -> None:
        # With base_seconds=0, delay=0, jitter=0 -> result >= 0
        delay = RetryBackoffCalculator.calculate_delay(attempt=1, strategy="fixed", base_seconds=0, max_seconds=100)
        assert delay >= 0.0


# ────────────────────────────────────────────────────────────────
# trivy_adapter
# ────────────────────────────────────────────────────────────────


def _make_stack() -> DetectedStack:
    return DetectedStack(languages=["python"], frameworks=["flask"])


class TestTrivyAdapterMetadata:
    """Test TrivyAdapter class attributes and is_applicable."""

    def test_name(self) -> None:
        adapter = TrivyAdapter()
        assert adapter.name == "trivy"

    def test_tool_name(self) -> None:
        adapter = TrivyAdapter()
        assert adapter.tool_name == "trivy"

    def test_factors_covered(self) -> None:
        adapter = TrivyAdapter()
        assert adapter.factors_covered == [22, 23, 24]

    def test_is_applicable_always_true(self) -> None:
        adapter = TrivyAdapter()
        assert adapter.is_applicable(_make_stack()) is True


class TestTrivySeverityMappings:
    """Test the module-level severity lookup dicts."""

    def test_vuln_severity_critical(self) -> None:
        assert _VULN_SEVERITY["CRITICAL"] == Severity.CRITICAL

    def test_vuln_severity_unknown(self) -> None:
        assert _VULN_SEVERITY["UNKNOWN"] == Severity.INFO

    def test_misconfig_severity_low(self) -> None:
        assert _MISCONFIG_SEVERITY["LOW"] == Severity.LOW


class TestTrivyAdapterRun:
    """Test TrivyAdapter.run with mocked subprocess."""

    def _run_with_stdout(self, stdout: str) -> list:
        adapter = TrivyAdapter()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout=stdout)
            return adapter.run(
                files=["requirements.txt"],
                project_path="/tmp/project",
                stack=_make_stack(),
            )

    def test_run_returns_empty_on_subprocess_error(self) -> None:
        adapter = TrivyAdapter()
        with patch("subprocess.run", side_effect=OSError("not found")):
            findings = adapter.run([], "/tmp/project", _make_stack())
        assert findings == []

    def test_run_returns_empty_on_json_decode_error(self) -> None:
        adapter = TrivyAdapter()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="NOT JSON")
            findings = adapter.run([], "/tmp/project", _make_stack())
        assert findings == []

    def test_run_returns_empty_on_no_results(self) -> None:
        findings = self._run_with_stdout(json.dumps({}))
        assert findings == []

    def test_run_returns_empty_on_non_list_results(self) -> None:
        findings = self._run_with_stdout(json.dumps({"Results": "not a list"}))
        assert findings == []

    def test_run_skips_non_dict_entries(self) -> None:
        findings = self._run_with_stdout(json.dumps({"Results": ["string", 42]}))
        assert findings == []


class TestTrivyParseVulnerabilities:
    """Test _parse_vulnerabilities method."""

    def test_no_vulnerabilities_key(self) -> None:
        adapter = TrivyAdapter()
        result = adapter._parse_vulnerabilities({}, "target.txt")
        assert result == []

    def test_vulnerabilities_not_list(self) -> None:
        adapter = TrivyAdapter()
        result = adapter._parse_vulnerabilities({"Vulnerabilities": "bad"}, "t")
        assert result == []

    def test_skips_non_dict_vuln(self) -> None:
        adapter = TrivyAdapter()
        result = adapter._parse_vulnerabilities({"Vulnerabilities": ["string"]}, "t")
        assert result == []

    def test_parses_full_vulnerability(self) -> None:
        adapter = TrivyAdapter()
        entry = {
            "Vulnerabilities": [
                {
                    "Severity": "HIGH",
                    "VulnerabilityID": "CVE-2024-1234",
                    "PkgName": "requests",
                    "InstalledVersion": "2.28.0",
                    "FixedVersion": "2.31.0",
                    "Title": "SSRF in requests",
                }
            ]
        }
        findings = adapter._parse_vulnerabilities(entry, "requirements.txt")
        assert len(findings) == 1
        f = findings[0]
        assert f.severity == Severity.HIGH
        assert f.factor_id == 22
        assert f.rule_id == "CVE-2024-1234"
        assert "requests" in f.message
        assert "2.31.0" in f.suggestion
        assert f.file == "requirements.txt"

    def test_vuln_without_fixed_version(self) -> None:
        adapter = TrivyAdapter()
        entry = {
            "Vulnerabilities": [
                {
                    "Severity": "LOW",
                    "VulnerabilityID": "CVE-2024-9999",
                    "PkgName": "urllib3",
                    "InstalledVersion": "1.26.0",
                }
            ]
        }
        findings = adapter._parse_vulnerabilities(entry, "req.txt")
        assert len(findings) == 1
        assert "to " not in findings[0].suggestion  # no fixed version appended

    def test_vuln_without_pkg_name(self) -> None:
        adapter = TrivyAdapter()
        entry = {
            "Vulnerabilities": [
                {
                    "Severity": "MEDIUM",
                    "VulnerabilityID": "CVE-2024-0001",
                    "Title": "General vuln",
                }
            ]
        }
        findings = adapter._parse_vulnerabilities(entry, "t")
        assert len(findings) == 1
        assert findings[0].suggestion == ""
        assert findings[0].message == "General vuln"

    def test_unknown_severity_defaults_to_info(self) -> None:
        adapter = TrivyAdapter()
        entry = {
            "Vulnerabilities": [
                {
                    "Severity": "ALIEN_LEVEL",
                    "VulnerabilityID": "CVE-X",
                    "Title": "weird",
                }
            ]
        }
        findings = adapter._parse_vulnerabilities(entry, "t")
        assert findings[0].severity == Severity.INFO


class TestTrivyParseSecrets:
    """Test _parse_secrets method."""

    def test_no_secrets_key(self) -> None:
        adapter = TrivyAdapter()
        result = adapter._parse_secrets({}, "target")
        assert result == []

    def test_secrets_not_list(self) -> None:
        adapter = TrivyAdapter()
        result = adapter._parse_secrets({"Secrets": 123}, "target")
        assert result == []

    def test_skips_non_dict_secret(self) -> None:
        adapter = TrivyAdapter()
        result = adapter._parse_secrets({"Secrets": [None]}, "target")
        assert result == []

    def test_parses_full_secret(self) -> None:
        adapter = TrivyAdapter()
        entry = {
            "Secrets": [
                {
                    "RuleID": "aws-access-key",
                    "Title": "AWS Access Key",
                    "Match": "AKIA***",
                    "StartLine": 10,
                }
            ]
        }
        findings = adapter._parse_secrets(entry, ".env")
        assert len(findings) == 1
        f = findings[0]
        assert f.severity == Severity.HIGH
        assert f.factor_id == 23
        assert f.line == 10
        assert f.rule_id == "aws-access-key"
        assert "AKIA***" in f.message
        assert f.file == ".env"

    def test_secret_without_match(self) -> None:
        adapter = TrivyAdapter()
        entry = {
            "Secrets": [
                {
                    "RuleID": "generic",
                    "Title": "Secret found",
                }
            ]
        }
        findings = adapter._parse_secrets(entry, "f")
        assert len(findings) == 1
        assert findings[0].message == "Secret found"


class TestTrivyParseMisconfigurations:
    """Test _parse_misconfigurations method."""

    def test_no_misconfigurations_key(self) -> None:
        adapter = TrivyAdapter()
        result = adapter._parse_misconfigurations({}, "target")
        assert result == []

    def test_misconfigurations_not_list(self) -> None:
        adapter = TrivyAdapter()
        result = adapter._parse_misconfigurations({"Misconfigurations": False}, "t")
        assert result == []

    def test_skips_non_dict_misconfig(self) -> None:
        adapter = TrivyAdapter()
        result = adapter._parse_misconfigurations({"Misconfigurations": [42]}, "t")
        assert result == []

    def test_parses_full_misconfiguration(self) -> None:
        adapter = TrivyAdapter()
        entry = {
            "Misconfigurations": [
                {
                    "Severity": "CRITICAL",
                    "ID": "DS002",
                    "Title": "Root user in Dockerfile",
                    "Description": "Running as root is dangerous",
                    "Resolution": "Add USER directive",
                }
            ]
        }
        findings = adapter._parse_misconfigurations(entry, "Dockerfile")
        assert len(findings) == 1
        f = findings[0]
        assert f.severity == Severity.CRITICAL
        assert f.factor_id == 24
        assert f.rule_id == "DS002"
        assert "DS002" in f.message
        assert f.suggestion == "Add USER directive"
        assert f.file == "Dockerfile"

    def test_misconfig_without_resolution_uses_description(self) -> None:
        adapter = TrivyAdapter()
        entry = {
            "Misconfigurations": [
                {
                    "ID": "MC001",
                    "Title": "Some issue",
                    "Description": "Detailed explanation",
                }
            ]
        }
        findings = adapter._parse_misconfigurations(entry, "t")
        assert findings[0].suggestion == "Detailed explanation"

    def test_misconfig_without_id(self) -> None:
        adapter = TrivyAdapter()
        entry = {
            "Misconfigurations": [
                {
                    "Title": "No ID misconfig",
                }
            ]
        }
        findings = adapter._parse_misconfigurations(entry, "t")
        assert findings[0].message == "No ID misconfig"

    def test_unknown_severity_defaults_to_medium(self) -> None:
        adapter = TrivyAdapter()
        entry = {
            "Misconfigurations": [
                {
                    "Severity": "UNKNOWN_LEVEL",
                    "Title": "test",
                }
            ]
        }
        findings = adapter._parse_misconfigurations(entry, "t")
        assert findings[0].severity == Severity.MEDIUM


class TestTrivyRunIntegration:
    """Test TrivyAdapter.run end-to-end with trivy output fixture."""

    def test_run_parses_mixed_results(self) -> None:
        """Verify run() dispatches to all three parsers and aggregates."""
        trivy_output = {
            "Results": [
                {
                    "Target": "requirements.txt",
                    "Vulnerabilities": [
                        {
                            "Severity": "HIGH",
                            "VulnerabilityID": "CVE-1",
                            "PkgName": "pkg",
                            "InstalledVersion": "1.0",
                            "Title": "vuln",
                        }
                    ],
                    "Secrets": [
                        {
                            "RuleID": "secret-1",
                            "Title": "Leaked key",
                            "Match": "AKIA",
                            "StartLine": 5,
                        }
                    ],
                    "Misconfigurations": [
                        {
                            "Severity": "LOW",
                            "ID": "MC1",
                            "Title": "Minor issue",
                        }
                    ],
                }
            ]
        }
        adapter = TrivyAdapter()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout=json.dumps(trivy_output))
            findings = adapter.run([], "/tmp/proj", _make_stack())

        assert len(findings) == 3
        factor_ids = {f.factor_id for f in findings}
        assert factor_ids == {22, 23, 24}

    def test_run_handles_subprocess_timeout(self) -> None:
        import subprocess as sp

        adapter = TrivyAdapter()
        with patch("subprocess.run", side_effect=sp.TimeoutExpired("trivy", 300)):
            findings = adapter.run([], "/tmp/proj", _make_stack())
        assert findings == []
