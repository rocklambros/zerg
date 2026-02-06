"""Unit tests for ZERG debug command — thinned Phase 4/5."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from zerg.commands.debug import (
    DebugCommand,
    DebugConfig,
    DebugPhase,
    DiagnosticResult,
    ErrorParser,
    Hypothesis,
    HypothesisGenerator,
    ParsedError,
    StackTraceAnalyzer,
    _load_stacktrace_file,
    debug,
)
from zerg.diagnostics.log_analyzer import LogPattern
from zerg.diagnostics.recovery import RecoveryPlan, RecoveryStep
from zerg.diagnostics.state_introspector import ZergHealthReport
from zerg.diagnostics.system_diagnostics import SystemHealthReport


class TestDebugPhaseEnum:
    def test_all_phases_exist(self) -> None:
        assert {p.value for p in DebugPhase} == {"symptom", "hypothesis", "test", "root_cause"}


class TestDataclasses:
    def test_debug_config_defaults(self) -> None:
        config = DebugConfig()
        assert config.verbose is False
        assert config.max_hypotheses == 3

    def test_hypothesis_to_dict(self) -> None:
        d = Hypothesis(description="Leak", likelihood="high", tested=True, confirmed=False).to_dict()
        assert d["description"] == "Leak" and d["tested"] is True

    def test_diagnostic_result_has_root_cause(self) -> None:
        def mk(rc: str) -> DiagnosticResult:
            return DiagnosticResult(symptom="E", hypotheses=[], root_cause=rc, recommendation="f")

        assert mk("OOM").has_root_cause is True
        assert mk("").has_root_cause is False


class TestErrorParser:
    @pytest.mark.parametrize(
        "error_input,expected_type",
        [
            ("ValueError: invalid literal for int()", "ValueError"),
            ("TypeError: undefined is not a function", "TypeError"),
            ("error[E0382]: use of moved value", "RustError"),
            ("Something went wrong", ""),
        ],
    )
    def test_parse_error_types(self, error_input: str, expected_type: str) -> None:
        assert ErrorParser().parse(error_input).error_type == expected_type

    @pytest.mark.parametrize(
        "error_input,expected_file,expected_line",
        [
            ('File "module.py", line 42\n    x = 1/0', "module.py", 42),
            ("    at Object.<anonymous> (app.js:10:5)", "app.js", 10),
        ],
    )
    def test_parse_file_line(self, error_input: str, expected_file: str, expected_line: int) -> None:
        parsed = ErrorParser().parse(error_input)
        assert parsed.file == expected_file and parsed.line == expected_line


class TestStackTraceAnalyzer:
    @pytest.mark.parametrize(
        "error_input,expected_pattern",
        [
            ("RecursionError: maximum recursion depth", "recursion"),
            ("MemoryError: unable to allocate", "memory"),
            ("TimeoutError: operation timed out", "timeout"),
            ("ImportError: No module named 'foo'", "import"),
        ],
    )
    def test_analyze_detects_pattern(self, error_input: str, expected_pattern: str) -> None:
        assert expected_pattern in StackTraceAnalyzer().analyze(error_input)

    def test_analyze_no_patterns(self) -> None:
        assert StackTraceAnalyzer().analyze("Everything is fine") == []


class TestHypothesisGenerator:
    def test_generate_from_patterns(self) -> None:
        assert len(HypothesisGenerator().generate(["type", "value"], ParsedError())) == 2

    def test_generate_unknown_pattern(self) -> None:
        assert HypothesisGenerator().generate(["unknown_pattern"], ParsedError()) == []


class TestDebugCommand:
    def test_run_with_error(self) -> None:
        result = DebugCommand().run(error="ValueError: invalid literal")
        assert result.has_root_cause is True

    def test_run_unknown_cause(self) -> None:
        result = DebugCommand().run(error="Something happened")
        assert "Unknown" in result.root_cause

    def test_format_result_json(self) -> None:
        debugger = DebugCommand()
        parsed = json.loads(debugger.format_result(debugger.run(error="ValueError: test"), fmt="json"))
        assert "symptom" in parsed


class TestLoadStacktraceFile:
    def test_load_existing_file(self, tmp_path: Path) -> None:
        f = tmp_path / "trace.txt"
        f.write_text("Error: Something failed")
        assert "Error: Something failed" in _load_stacktrace_file(str(f))

    def test_load_nonexistent_file(self) -> None:
        assert _load_stacktrace_file("/nonexistent/trace.txt") == ""


class TestDebugCLI:
    def test_debug_help(self) -> None:
        assert CliRunner().invoke(debug, ["--help"]).exit_code == 0

    @patch("zerg.commands.debug.console")
    def test_debug_keyboard_interrupt(self, mock_console: MagicMock) -> None:
        with patch("zerg.commands.debug.DebugCommand", side_effect=KeyboardInterrupt):
            assert CliRunner().invoke(debug, ["--error", "Error"]).exit_code == 130


class TestDiagnosticResultExtended:
    def test_to_dict_includes_deep_fields(self) -> None:
        result = DiagnosticResult(
            symptom="E",
            hypotheses=[],
            root_cause="C",
            recommendation="F",
            zerg_health=ZergHealthReport(feature="test", state_exists=True, total_tasks=5),
            system_health=SystemHealthReport(git_clean=False, git_branch="main"),
            recovery_plan=RecoveryPlan(
                problem="P", root_cause="C", steps=[RecoveryStep(description="S", command="cmd")]
            ),
            evidence=["finding 1"],
            log_patterns=[
                LogPattern(pattern="RuntimeError", count=3, first_seen="1", last_seen="10", worker_ids=[1, 2])
            ],
        )
        d = result.to_dict()
        assert d["zerg_health"]["feature"] == "test"
        assert d["system_health"]["git_clean"] is False
        assert len(d["recovery_plan"]["steps"]) == 1


class TestDebugCommandDeep:
    def test_run_with_feature(self) -> None:
        debugger = DebugCommand()
        with patch.object(debugger, "_run_zerg_diagnostics", side_effect=lambda r, f, w: r):
            with patch.object(debugger, "_plan_recovery", side_effect=lambda r: r):
                debugger.run(error="test error", feature="my-feat")

    def test_plan_recovery_with_design_escalation(self) -> None:
        debugger = DebugCommand()
        diag = DiagnosticResult(symptom="test", hypotheses=[], root_cause="unknown", recommendation="fix")
        with patch("zerg.diagnostics.recovery.RecoveryPlanner") as mock_cls:
            mock_cls.return_value.plan.return_value = RecoveryPlan(
                problem="test",
                root_cause="cause",
                steps=[RecoveryStep(description="s", command="c")],
                needs_design=True,
                design_reason="task graph flaw",
            )
            diag = debugger._plan_recovery(diag)
        assert diag.recovery_plan is not None
        assert diag.design_escalation is True
