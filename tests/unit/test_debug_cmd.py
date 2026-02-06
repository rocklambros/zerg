"""Unit tests for ZERG debug command.

Thinned from 139 tests to ~30 tests. Retained:
- 1 enum test (all values), removed per-value tests
- 1 happy-path + 1 error-path per dataclass
- 1 per language for ErrorParser (Python, JS, Rust, Go, unknown)
- Parametrized StackTraceAnalyzer (kept as-is, already parametrized)
- 1 happy-path + 1 error-path for HypothesisGenerator
- 1 happy-path + 1 error-path for DebugCommand
- 1 happy-path + 1 error-path for format_result
- 1 happy-path + 1 error-path for _load_stacktrace_file
- 1 help + 1 basic execution for CLI
- 1 per error handler (KeyboardInterrupt, generic exception)
- Deep diagnostics: 1 per subsystem + 1 to_dict + 1 design escalation
"""

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

# =============================================================================
# DebugPhase Enum Tests
# =============================================================================


class TestDebugPhaseEnum:
    """Tests for DebugPhase enum."""

    def test_all_phases_exist(self) -> None:
        """Test all expected phases are defined."""
        expected = {"symptom", "hypothesis", "test", "root_cause"}
        actual = {p.value for p in DebugPhase}
        assert actual == expected


# =============================================================================
# Dataclass Tests (1 happy-path + 1 edge per class)
# =============================================================================


class TestDebugConfig:
    """Tests for DebugConfig dataclass."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = DebugConfig()
        assert config.verbose is False
        assert config.max_hypotheses == 3
        assert config.auto_test is False

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        config = DebugConfig(verbose=True, max_hypotheses=5, auto_test=True)
        assert config.verbose is True
        assert config.max_hypotheses == 5
        assert config.auto_test is True


class TestHypothesis:
    """Tests for Hypothesis dataclass."""

    def test_default_values(self) -> None:
        """Test default Hypothesis values."""
        hypothesis = Hypothesis(description="Test hypothesis", likelihood="high")
        assert hypothesis.test_command == ""
        assert hypothesis.tested is False
        assert hypothesis.confirmed is False

    def test_to_dict(self) -> None:
        """Test to_dict method."""
        hypothesis = Hypothesis(
            description="Memory leak detected",
            likelihood="high",
            test_command="valgrind ./app",
            tested=True,
            confirmed=False,
        )
        result = hypothesis.to_dict()
        assert result == {
            "description": "Memory leak detected",
            "likelihood": "high",
            "test_command": "valgrind ./app",
            "tested": True,
            "confirmed": False,
        }


class TestParsedError:
    """Tests for ParsedError dataclass."""

    def test_default_values(self) -> None:
        """Test default ParsedError values."""
        parsed = ParsedError()
        assert parsed.error_type == ""
        assert parsed.message == ""
        assert parsed.file == ""
        assert parsed.line == 0
        assert parsed.stack_trace == []

    def test_to_dict(self) -> None:
        """Test to_dict method."""
        parsed = ParsedError(
            error_type="TypeError",
            message="expected str",
            file="app.py",
            line=10,
            stack_trace=["at app.py:10"],
        )
        result = parsed.to_dict()
        assert result["error_type"] == "TypeError"
        assert result["file"] == "app.py"


class TestDiagnosticResult:
    """Tests for DiagnosticResult dataclass."""

    def test_has_root_cause_true(self) -> None:
        """Test has_root_cause when root cause exists."""
        result = DiagnosticResult(
            symptom="Error occurred",
            hypotheses=[],
            root_cause="Memory exhaustion",
            recommendation="Add more RAM",
        )
        assert result.has_root_cause is True

    def test_has_root_cause_false(self) -> None:
        """Test has_root_cause when root cause is empty."""
        result = DiagnosticResult(
            symptom="Error occurred",
            hypotheses=[],
            root_cause="",
            recommendation="Collect more data",
        )
        assert result.has_root_cause is False

    def test_to_dict_with_parsed_error(self) -> None:
        """Test to_dict with parsed error."""
        parsed = ParsedError(error_type="ValueError", message="bad value", file="test.py", line=5)
        hypothesis = Hypothesis(description="Invalid input", likelihood="high")
        result = DiagnosticResult(
            symptom="ValueError: bad value",
            hypotheses=[hypothesis],
            root_cause="Invalid input data",
            recommendation="Validate input",
            phase=DebugPhase.ROOT_CAUSE,
            confidence=0.9,
            parsed_error=parsed,
        )
        d = result.to_dict()
        assert d["symptom"] == "ValueError: bad value"
        assert d["parsed_error"]["error_type"] == "ValueError"
        assert len(d["hypotheses"]) == 1


# =============================================================================
# ErrorParser Tests (1 per language + unknown)
# =============================================================================


class TestErrorParser:
    """Tests for ErrorParser class."""

    @pytest.mark.parametrize(
        "error_input,expected_type,expected_in_msg",
        [
            ("ValueError: invalid literal for int()", "ValueError", "invalid literal"),
            ("TypeError: undefined is not a function", "TypeError", "undefined"),
            ("error[E0382]: use of moved value", "RustError", "moved value"),
            ("Something went wrong", "", ""),
        ],
    )
    def test_parse_error_types(self, error_input: str, expected_type: str, expected_in_msg: str) -> None:
        """Test parsing error types across languages."""
        parser = ErrorParser()
        parsed = parser.parse(error_input)
        assert parsed.error_type == expected_type
        if expected_in_msg:
            assert expected_in_msg in parsed.message

    @pytest.mark.parametrize(
        "error_input,expected_file,expected_line",
        [
            ('File "module.py", line 42\n    x = 1/0', "module.py", 42),
            ("    at Object.<anonymous> (app.js:10:5)", "app.js", 10),
            ("panic: runtime error\nmain.go:25", "main.go", 25),
            ("--> src/main.rs:15:5", "src/main.rs", 15),
        ],
    )
    def test_parse_file_line(self, error_input: str, expected_file: str, expected_line: int) -> None:
        """Test parsing file and line from various languages."""
        parser = ErrorParser()
        parsed = parser.parse(error_input)
        assert parsed.file == expected_file
        assert parsed.line == expected_line

    def test_parse_extracts_stack_trace(self) -> None:
        """Test parsing extracts stack trace lines."""
        parser = ErrorParser()
        error = """Traceback (most recent call last):
  File "app.py", line 10
    x = 1/0
ValueError: division by zero"""
        parsed = parser.parse(error)
        assert len(parsed.stack_trace) >= 1


# =============================================================================
# StackTraceAnalyzer Tests (already parametrized - kept as-is)
# =============================================================================


class TestStackTraceAnalyzer:
    """Tests for StackTraceAnalyzer class."""

    @pytest.mark.parametrize(
        "error_input,expected_pattern",
        [
            ("RecursionError: maximum recursion depth", "recursion"),
            ("MemoryError: unable to allocate", "memory"),
            ("TimeoutError: operation timed out", "timeout"),
            ("ConnectionError: connection refused", "connection"),
            ("PermissionError: permission denied", "permission"),
            ("ImportError: No module named 'foo'", "import"),
            ("TypeError: expected str, got int", "type"),
            ("ValueError: invalid value", "value"),
            ("KeyError: 'missing_key'", "key"),
            ("AttributeError: 'NoneType' has no attribute 'x'", "attribute"),
            ("IndexError: list index out of range", "index"),
            ("FileNotFoundError: no such file", "file"),
            ("SyntaxError: invalid syntax", "syntax"),
            ("AssertionError: expected True", "assertion"),
        ],
    )
    def test_analyze_detects_pattern(self, error_input: str, expected_pattern: str) -> None:
        """Test analyze detects various error patterns."""
        analyzer = StackTraceAnalyzer()
        patterns = analyzer.analyze(error_input)
        assert expected_pattern in patterns

    def test_analyze_no_patterns(self) -> None:
        """Test analyze with no matching patterns."""
        analyzer = StackTraceAnalyzer()
        patterns = analyzer.analyze("Everything is fine")
        assert patterns == []

    def test_analyze_no_duplicates(self) -> None:
        """Test analyze does not duplicate patterns."""
        analyzer = StackTraceAnalyzer()
        patterns = analyzer.analyze("TypeError TypeError type error")
        assert patterns.count("type") == 1


# =============================================================================
# HypothesisGenerator Tests
# =============================================================================


class TestHypothesisGenerator:
    """Tests for HypothesisGenerator class."""

    def test_generate_from_patterns(self) -> None:
        """Test generate creates hypotheses from patterns."""
        generator = HypothesisGenerator()
        parsed = ParsedError()
        hypotheses = generator.generate(["type", "value"], parsed)
        assert len(hypotheses) == 2

    def test_generate_with_file_info(self) -> None:
        """Test generate adds location hypothesis with file info."""
        generator = HypothesisGenerator()
        parsed = ParsedError(file="module.py", line=42)
        hypotheses = generator.generate(["type"], parsed)
        assert hypotheses[0].description == "Error at module.py:42"

    def test_generate_unknown_pattern(self) -> None:
        """Test generate ignores unknown patterns."""
        generator = HypothesisGenerator()
        parsed = ParsedError()
        hypotheses = generator.generate(["unknown_pattern"], parsed)
        assert hypotheses == []


# =============================================================================
# DebugCommand Tests
# =============================================================================


class TestDebugCommand:
    """Tests for DebugCommand class."""

    def test_run_with_error(self) -> None:
        """Test run with error message."""
        debugger = DebugCommand()
        result = debugger.run(error="ValueError: invalid literal")
        assert result.symptom == "ValueError: invalid literal"
        assert result.has_root_cause is True

    def test_run_limits_hypotheses(self) -> None:
        """Test run limits hypotheses to max_hypotheses."""
        config = DebugConfig(max_hypotheses=2)
        debugger = DebugCommand(config)
        error = "TypeError: invalid value, KeyError: missing, IndexError: out of range"
        result = debugger.run(error=error)
        assert len(result.hypotheses) <= 2

    def test_run_unknown_cause(self) -> None:
        """Test run with unknown cause."""
        debugger = DebugCommand()
        result = debugger.run(error="Something happened")
        assert "Unknown" in result.root_cause
        assert result.confidence == 0.3

    def test_format_result_json(self) -> None:
        """Test format_result with JSON output."""
        debugger = DebugCommand()
        result = debugger.run(error="ValueError: test")
        output = debugger.format_result(result, fmt="json")
        parsed = json.loads(output)
        assert "symptom" in parsed
        assert "root_cause" in parsed

    def test_format_result_text(self) -> None:
        """Test format_result with text output."""
        debugger = DebugCommand()
        result = debugger.run(error="KeyError: missing")
        output = debugger.format_result(result, fmt="text")
        assert "Diagnostic Report" in output
        assert "Symptom:" in output


# =============================================================================
# _load_stacktrace_file Tests
# =============================================================================


class TestLoadStacktraceFile:
    """Tests for _load_stacktrace_file helper function."""

    def test_load_existing_file(self, tmp_path: Path) -> None:
        """Test loading existing stack trace file."""
        trace_file = tmp_path / "trace.txt"
        trace_file.write_text("Error: Something failed\n  at line 10")
        content = _load_stacktrace_file(str(trace_file))
        assert "Error: Something failed" in content

    def test_load_nonexistent_file(self) -> None:
        """Test loading nonexistent file returns empty string."""
        content = _load_stacktrace_file("/nonexistent/trace.txt")
        assert content == ""


# =============================================================================
# CLI Command Tests
# =============================================================================


class TestDebugCLI:
    """Tests for debug CLI command."""

    def test_debug_help(self) -> None:
        """Test debug --help."""
        runner = CliRunner()
        result = runner.invoke(debug, ["--help"])
        assert result.exit_code == 0
        assert "error" in result.output
        assert "stacktrace" in result.output

    @patch("zerg.commands.debug.DebugCommand")
    @patch("zerg.commands.debug.console")
    def test_debug_with_error(self, mock_console: MagicMock, mock_command_class: MagicMock) -> None:
        """Test debug with --error."""
        mock_command = MagicMock()
        mock_command.run.return_value = DiagnosticResult(
            symptom="ValueError: test",
            hypotheses=[],
            root_cause="Test error",
            recommendation="Fix it",
            confidence=0.9,
            parsed_error=ParsedError(error_type="ValueError", message="test"),
        )
        mock_command.config = DebugConfig()
        mock_command_class.return_value = mock_command
        runner = CliRunner()
        result = runner.invoke(debug, ["--error", "ValueError: test"])
        assert result.exit_code == 0

    @patch("zerg.commands.debug.console")
    def test_debug_keyboard_interrupt(self, mock_console: MagicMock) -> None:
        """Test debug handles KeyboardInterrupt."""
        with patch("zerg.commands.debug.DebugCommand", side_effect=KeyboardInterrupt):
            runner = CliRunner()
            result = runner.invoke(debug, ["--error", "Error"])
            assert result.exit_code == 130

    @patch("zerg.commands.debug.console")
    def test_debug_generic_exception(self, mock_console: MagicMock) -> None:
        """Test debug handles generic exception."""
        with patch("zerg.commands.debug.DebugCommand", side_effect=RuntimeError("Unexpected error")):
            runner = CliRunner()
            result = runner.invoke(debug, ["--error", "Error"])
            assert result.exit_code == 1


# =============================================================================
# Extended DiagnosticResult Tests (deep diagnostics fields)
# =============================================================================


class TestDiagnosticResultExtended:
    """Tests for DiagnosticResult with deep diagnostics fields."""

    def test_new_fields_default_none(self) -> None:
        """Test new optional fields default to None/empty."""
        result = DiagnosticResult(symptom="Error", hypotheses=[], root_cause="Cause", recommendation="Fix")
        assert result.zerg_health is None
        assert result.system_health is None
        assert result.recovery_plan is None
        assert result.evidence == []
        assert result.log_patterns == []

    def test_to_dict_includes_all_deep_fields(self) -> None:
        """Test to_dict includes deep diagnostic fields when set."""
        health = ZergHealthReport(feature="test", state_exists=True, total_tasks=5)
        sys_h = SystemHealthReport(git_clean=False, git_branch="main")
        plan = RecoveryPlan(problem="P", root_cause="C", steps=[RecoveryStep(description="S", command="cmd")])
        pat = LogPattern(pattern="RuntimeError", count=3, first_seen="1", last_seen="10", worker_ids=[1, 2])
        result = DiagnosticResult(
            symptom="Error",
            hypotheses=[],
            root_cause="Cause",
            recommendation="Fix",
            zerg_health=health,
            system_health=sys_h,
            recovery_plan=plan,
            evidence=["finding 1"],
            log_patterns=[pat],
        )
        d = result.to_dict()
        assert d["zerg_health"]["feature"] == "test"
        assert d["system_health"]["git_clean"] is False
        assert len(d["recovery_plan"]["steps"]) == 1
        assert d["evidence"] == ["finding 1"]
        assert d["log_patterns"][0]["count"] == 3

    def test_to_dict_omits_none_fields(self) -> None:
        """Test to_dict omits None deep diagnostic fields."""
        result = DiagnosticResult(symptom="Error", hypotheses=[], root_cause="Cause", recommendation="Fix")
        d = result.to_dict()
        assert "zerg_health" not in d
        assert "system_health" not in d
        assert "recovery_plan" not in d


# =============================================================================
# DebugCommand Deep Diagnostics Tests
# =============================================================================


class TestDebugCommandDeep:
    """Tests for DebugCommand with deep diagnostics."""

    def test_run_with_feature(self) -> None:
        """Test run with feature param triggers ZERG diagnostics."""
        debugger = DebugCommand()
        with patch.object(debugger, "_run_zerg_diagnostics") as mock_zerg:
            mock_zerg.side_effect = lambda r, f, w: r
            with patch.object(debugger, "_plan_recovery") as mock_plan:
                mock_plan.side_effect = lambda r: r
                debugger.run(error="test error", feature="my-feat")
        mock_zerg.assert_called_once()
        mock_plan.assert_called_once()

    def test_run_without_feature_or_deep(self) -> None:
        """Test run without feature/deep doesn't trigger deep diagnostics."""
        debugger = DebugCommand()
        result = debugger.run(error="ValueError: test")
        assert result.zerg_health is None
        assert result.system_health is None

    def test_plan_recovery(self) -> None:
        """Test _plan_recovery integration."""
        debugger = DebugCommand()
        result = DiagnosticResult(symptom="test", hypotheses=[], root_cause="unknown", recommendation="fix")
        with patch("zerg.diagnostics.recovery.RecoveryPlanner") as mock_plan_cls:
            mock_plan_cls.return_value.plan.return_value = RecoveryPlan(
                problem="test", root_cause="cause", steps=[RecoveryStep(description="step", command="cmd")]
            )
            result = debugger._plan_recovery(result)
        assert result.recovery_plan is not None
        assert len(result.recovery_plan.steps) == 1


# =============================================================================
# Design Escalation Tests
# =============================================================================


class TestDesignEscalationPropagation:
    """Tests for design escalation propagation from RecoveryPlan to DiagnosticResult."""

    def test_propagation_from_recovery_plan(self) -> None:
        """_plan_recovery propagates needs_design to DiagnosticResult."""
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
        assert diag.design_escalation is True
        assert diag.design_escalation_reason == "task graph flaw"

    def test_diagnostic_result_to_dict_omits_when_false(self) -> None:
        """DiagnosticResult.to_dict() omits design escalation when False."""
        diag = DiagnosticResult(symptom="err", hypotheses=[], root_cause="cause", recommendation="fix")
        d = diag.to_dict()
        assert "design_escalation" not in d
