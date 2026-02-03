"""Comprehensive unit tests for ZERG debug command - 100% coverage target.

Tests cover:
- DebugPhase enum
- DebugConfig dataclass
- Hypothesis dataclass
- ParsedError dataclass
- DiagnosticResult dataclass with properties
- ErrorParser for error message parsing
- StackTraceAnalyzer for pattern detection
- HypothesisGenerator for hypothesis generation
- DebugCommand orchestration
- _load_stacktrace_file helper function
- CLI command with all options
- Deep diagnostics integration (--feature, --deep, --auto-fix, --worker)
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

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

    def test_symptom_value(self) -> None:
        """Test symptom enum value."""
        assert DebugPhase.SYMPTOM.value == "symptom"

    def test_hypothesis_value(self) -> None:
        """Test hypothesis enum value."""
        assert DebugPhase.HYPOTHESIS.value == "hypothesis"

    def test_test_value(self) -> None:
        """Test test enum value."""
        assert DebugPhase.TEST.value == "test"

    def test_root_cause_value(self) -> None:
        """Test root_cause enum value."""
        assert DebugPhase.ROOT_CAUSE.value == "root_cause"

    def test_all_phases_exist(self) -> None:
        """Test all expected phases are defined."""
        expected = {"symptom", "hypothesis", "test", "root_cause"}
        actual = {p.value for p in DebugPhase}
        assert actual == expected


# =============================================================================
# DebugConfig Dataclass Tests
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
        config = DebugConfig(
            verbose=True,
            max_hypotheses=5,
            auto_test=True,
        )

        assert config.verbose is True
        assert config.max_hypotheses == 5
        assert config.auto_test is True


# =============================================================================
# Hypothesis Dataclass Tests
# =============================================================================


class TestHypothesis:
    """Tests for Hypothesis dataclass."""

    def test_default_values(self) -> None:
        """Test default Hypothesis values."""
        hypothesis = Hypothesis(
            description="Test hypothesis",
            likelihood="high",
        )

        assert hypothesis.test_command == ""
        assert hypothesis.tested is False
        assert hypothesis.confirmed is False

    def test_custom_values(self) -> None:
        """Test custom Hypothesis values."""
        hypothesis = Hypothesis(
            description="Test hypothesis",
            likelihood="medium",
            test_command="run test",
            tested=True,
            confirmed=True,
        )

        assert hypothesis.test_command == "run test"
        assert hypothesis.tested is True
        assert hypothesis.confirmed is True

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


# =============================================================================
# ParsedError Dataclass Tests
# =============================================================================


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

    def test_custom_values(self) -> None:
        """Test custom ParsedError values."""
        parsed = ParsedError(
            error_type="ValueError",
            message="invalid literal",
            file="module.py",
            line=42,
            stack_trace=["File 'module.py', line 42"],
        )

        assert parsed.error_type == "ValueError"
        assert parsed.message == "invalid literal"
        assert parsed.file == "module.py"
        assert parsed.line == 42
        assert len(parsed.stack_trace) == 1

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

        assert result == {
            "error_type": "TypeError",
            "message": "expected str",
            "file": "app.py",
            "line": 10,
            "stack_trace": ["at app.py:10"],
        }


# =============================================================================
# DiagnosticResult Dataclass Tests
# =============================================================================


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

    def test_default_values(self) -> None:
        """Test default DiagnosticResult values."""
        result = DiagnosticResult(
            symptom="Error",
            hypotheses=[],
            root_cause="Cause",
            recommendation="Fix it",
        )

        assert result.phase == DebugPhase.ROOT_CAUSE
        assert result.confidence == 0.8
        assert result.parsed_error is None

    def test_to_dict_with_parsed_error(self) -> None:
        """Test to_dict with parsed error."""
        parsed = ParsedError(
            error_type="ValueError",
            message="bad value",
            file="test.py",
            line=5,
        )
        hypothesis = Hypothesis(
            description="Invalid input",
            likelihood="high",
        )
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
        assert d["root_cause"] == "Invalid input data"
        assert d["recommendation"] == "Validate input"
        assert d["confidence"] == 0.9
        assert d["phase"] == "root_cause"
        assert len(d["hypotheses"]) == 1
        assert d["parsed_error"]["error_type"] == "ValueError"

    def test_to_dict_without_parsed_error(self) -> None:
        """Test to_dict without parsed error."""
        result = DiagnosticResult(
            symptom="Unknown error",
            hypotheses=[],
            root_cause="Unknown",
            recommendation="Debug",
        )

        d = result.to_dict()

        assert d["parsed_error"] is None


# =============================================================================
# ErrorParser Tests
# =============================================================================


class TestErrorParser:
    """Tests for ErrorParser class."""

    def test_parse_python_error(self) -> None:
        """Test parsing Python error."""
        parser = ErrorParser()
        error = "ValueError: invalid literal for int()"

        parsed = parser.parse(error)

        assert parsed.error_type == "ValueError"
        assert "invalid literal" in parsed.message

    def test_parse_python_exception(self) -> None:
        """Test parsing Python exception."""
        parser = ErrorParser()
        error = "KeyError: 'missing_key'"

        parsed = parser.parse(error)

        assert parsed.error_type == "KeyError"
        assert "missing_key" in parsed.message

    def test_parse_python_file_line(self) -> None:
        """Test parsing Python file and line."""
        parser = ErrorParser()
        error = 'File "module.py", line 42\n    x = 1/0'

        parsed = parser.parse(error)

        assert parsed.file == "module.py"
        assert parsed.line == 42

    def test_parse_javascript_error(self) -> None:
        """Test parsing JavaScript error."""
        parser = ErrorParser()
        error = "TypeError: undefined is not a function"

        parsed = parser.parse(error)

        assert parsed.error_type == "TypeError"
        assert "undefined" in parsed.message

    def test_parse_javascript_reference_error(self) -> None:
        """Test parsing JavaScript ReferenceError."""
        parser = ErrorParser()
        error = "ReferenceError: x is not defined"

        parsed = parser.parse(error)

        assert parsed.error_type == "ReferenceError"

    def test_parse_javascript_syntax_error(self) -> None:
        """Test parsing JavaScript SyntaxError."""
        parser = ErrorParser()
        error = "SyntaxError: Unexpected token"

        parsed = parser.parse(error)

        assert parsed.error_type == "SyntaxError"

    def test_parse_javascript_file_line(self) -> None:
        """Test parsing JavaScript file and line."""
        parser = ErrorParser()
        error = "    at Object.<anonymous> (app.js:10:5)"

        parsed = parser.parse(error)

        assert parsed.file == "app.js"
        assert parsed.line == 10

    def test_parse_go_file_line(self) -> None:
        """Test parsing Go file and line."""
        parser = ErrorParser()
        error = "panic: runtime error\nmain.go:25"

        parsed = parser.parse(error)

        assert parsed.file == "main.go"
        assert parsed.line == 25

    def test_parse_rust_error(self) -> None:
        """Test parsing Rust error."""
        parser = ErrorParser()
        error = "error[E0382]: use of moved value"

        parsed = parser.parse(error)

        assert parsed.error_type == "RustError"
        assert "moved value" in parsed.message

    def test_parse_rust_file_line(self) -> None:
        """Test parsing Rust file and line."""
        parser = ErrorParser()
        error = "--> src/main.rs:15:5"

        parsed = parser.parse(error)

        assert parsed.file == "src/main.rs"
        assert parsed.line == 15

    def test_parse_extracts_stack_trace(self) -> None:
        """Test parsing extracts stack trace lines."""
        parser = ErrorParser()
        error = """Traceback (most recent call last):
  File "app.py", line 10
    x = 1/0
ValueError: division by zero"""

        parsed = parser.parse(error)

        assert len(parsed.stack_trace) >= 1
        assert any("File" in line for line in parsed.stack_trace)

    def test_parse_extracts_js_stack_trace(self) -> None:
        """Test parsing extracts JavaScript stack trace."""
        parser = ErrorParser()
        error = """Error: Something went wrong
    at doSomething (app.js:10:5)
    at main (index.js:5:3)"""

        parsed = parser.parse(error)

        assert len(parsed.stack_trace) >= 2

    def test_parse_extracts_rust_stack_trace(self) -> None:
        """Test parsing extracts Rust stack trace."""
        parser = ErrorParser()
        error = """--> src/main.rs:15:5
   |
15 |     let x = y;
   |     ^^^^^^^^^"""

        parsed = parser.parse(error)

        assert len(parsed.stack_trace) >= 1

    def test_parse_unknown_format(self) -> None:
        """Test parsing unknown error format."""
        parser = ErrorParser()
        error = "Something went wrong"

        parsed = parser.parse(error)

        assert parsed.error_type == ""
        assert parsed.message == ""

    def test_parse_numbered_stack_trace(self) -> None:
        """Test parsing numbered stack trace lines."""
        parser = ErrorParser()
        error = """   1: main
   2: runtime"""

        parsed = parser.parse(error)

        assert len(parsed.stack_trace) >= 1


# =============================================================================
# StackTraceAnalyzer Tests
# =============================================================================


class TestStackTraceAnalyzer:
    """Tests for StackTraceAnalyzer class."""

    def test_analyze_detects_recursion(self) -> None:
        """Test analyze detects recursion patterns."""
        analyzer = StackTraceAnalyzer()

        patterns = analyzer.analyze("RecursionError: maximum recursion depth")

        assert "recursion" in patterns

    def test_analyze_detects_stack_overflow(self) -> None:
        """Test analyze detects stack overflow."""
        analyzer = StackTraceAnalyzer()

        patterns = analyzer.analyze("stack overflow in thread")

        assert "recursion" in patterns

    def test_analyze_detects_memory(self) -> None:
        """Test analyze detects memory patterns."""
        analyzer = StackTraceAnalyzer()

        patterns = analyzer.analyze("MemoryError: unable to allocate")

        assert "memory" in patterns

    def test_analyze_detects_oom(self) -> None:
        """Test analyze detects OOM."""
        analyzer = StackTraceAnalyzer()

        patterns = analyzer.analyze("out of memory error")

        assert "memory" in patterns

    def test_analyze_detects_heap(self) -> None:
        """Test analyze detects heap issues."""
        analyzer = StackTraceAnalyzer()

        patterns = analyzer.analyze("JavaScript heap out of memory")

        assert "memory" in patterns

    def test_analyze_detects_timeout(self) -> None:
        """Test analyze detects timeout patterns."""
        analyzer = StackTraceAnalyzer()

        patterns = analyzer.analyze("TimeoutError: operation timed out")

        assert "timeout" in patterns

    def test_analyze_detects_deadline_exceeded(self) -> None:
        """Test analyze detects deadline exceeded."""
        analyzer = StackTraceAnalyzer()

        patterns = analyzer.analyze("deadline exceeded")

        assert "timeout" in patterns

    def test_analyze_detects_connection(self) -> None:
        """Test analyze detects connection patterns."""
        analyzer = StackTraceAnalyzer()

        patterns = analyzer.analyze("ConnectionError: connection refused")

        assert "connection" in patterns

    def test_analyze_detects_econnrefused(self) -> None:
        """Test analyze detects ECONNREFUSED."""
        analyzer = StackTraceAnalyzer()

        patterns = analyzer.analyze("Error: connect ECONNREFUSED")

        assert "connection" in patterns

    def test_analyze_detects_permission(self) -> None:
        """Test analyze detects permission patterns."""
        analyzer = StackTraceAnalyzer()

        patterns = analyzer.analyze("PermissionError: permission denied")

        assert "permission" in patterns

    def test_analyze_detects_eacces(self) -> None:
        """Test analyze detects EACCES."""
        analyzer = StackTraceAnalyzer()

        patterns = analyzer.analyze("Error: EACCES, permission denied")

        assert "permission" in patterns

    def test_analyze_detects_import(self) -> None:
        """Test analyze detects import patterns."""
        analyzer = StackTraceAnalyzer()

        patterns = analyzer.analyze("ImportError: No module named 'foo'")

        assert "import" in patterns

    def test_analyze_detects_module_not_found(self) -> None:
        """Test analyze detects ModuleNotFoundError."""
        analyzer = StackTraceAnalyzer()

        patterns = analyzer.analyze("ModuleNotFoundError: No module named 'bar'")

        assert "import" in patterns

    def test_analyze_detects_cannot_find_module(self) -> None:
        """Test analyze detects cannot find module."""
        analyzer = StackTraceAnalyzer()

        patterns = analyzer.analyze("Error: Cannot find module 'express'")

        assert "import" in patterns

    def test_analyze_detects_type_error(self) -> None:
        """Test analyze detects type error patterns."""
        analyzer = StackTraceAnalyzer()

        patterns = analyzer.analyze("TypeError: expected str, got int")

        assert "type" in patterns

    def test_analyze_detects_incompatible_types(self) -> None:
        """Test analyze detects incompatible types."""
        analyzer = StackTraceAnalyzer()

        patterns = analyzer.analyze("incompatible types: String vs Integer")

        assert "type" in patterns

    def test_analyze_detects_value_error(self) -> None:
        """Test analyze detects value error patterns."""
        analyzer = StackTraceAnalyzer()

        patterns = analyzer.analyze("ValueError: invalid value")

        assert "value" in patterns

    def test_analyze_detects_invalid_argument(self) -> None:
        """Test analyze detects invalid argument."""
        analyzer = StackTraceAnalyzer()

        patterns = analyzer.analyze("Error: invalid argument provided")

        assert "value" in patterns

    def test_analyze_detects_key_error(self) -> None:
        """Test analyze detects key error patterns."""
        analyzer = StackTraceAnalyzer()

        patterns = analyzer.analyze("KeyError: 'missing_key'")

        assert "key" in patterns

    def test_analyze_detects_undefined_key(self) -> None:
        """Test analyze detects undefined key."""
        analyzer = StackTraceAnalyzer()

        patterns = analyzer.analyze("undefined key in dictionary")

        assert "key" in patterns

    def test_analyze_detects_attribute_error(self) -> None:
        """Test analyze detects attribute error patterns."""
        analyzer = StackTraceAnalyzer()

        patterns = analyzer.analyze("AttributeError: 'NoneType' has no attribute 'x'")

        assert "attribute" in patterns

    def test_analyze_detects_undefined_property(self) -> None:
        """Test analyze detects undefined property."""
        analyzer = StackTraceAnalyzer()

        patterns = analyzer.analyze("Cannot read undefined property 'foo'")

        assert "attribute" in patterns

    def test_analyze_detects_index_error(self) -> None:
        """Test analyze detects index error patterns."""
        analyzer = StackTraceAnalyzer()

        patterns = analyzer.analyze("IndexError: list index out of range")

        assert "index" in patterns

    def test_analyze_detects_out_of_bounds(self) -> None:
        """Test analyze detects out of bounds."""
        analyzer = StackTraceAnalyzer()

        patterns = analyzer.analyze("array index out of bounds")

        assert "index" in patterns

    def test_analyze_detects_file_error(self) -> None:
        """Test analyze detects file error patterns."""
        analyzer = StackTraceAnalyzer()

        patterns = analyzer.analyze("FileNotFoundError: no such file")

        assert "file" in patterns

    def test_analyze_detects_enoent(self) -> None:
        """Test analyze detects ENOENT."""
        analyzer = StackTraceAnalyzer()

        patterns = analyzer.analyze("Error: ENOENT, no such file or directory")

        assert "file" in patterns

    def test_analyze_detects_syntax_error(self) -> None:
        """Test analyze detects syntax error patterns."""
        analyzer = StackTraceAnalyzer()

        patterns = analyzer.analyze("SyntaxError: invalid syntax")

        assert "syntax" in patterns

    def test_analyze_detects_unexpected_token(self) -> None:
        """Test analyze detects unexpected token."""
        analyzer = StackTraceAnalyzer()

        patterns = analyzer.analyze("unexpected token at line 10")

        assert "syntax" in patterns

    def test_analyze_detects_parse_error(self) -> None:
        """Test analyze detects parse error."""
        analyzer = StackTraceAnalyzer()

        patterns = analyzer.analyze("parse error near keyword")

        assert "syntax" in patterns

    def test_analyze_detects_assertion(self) -> None:
        """Test analyze detects assertion patterns."""
        analyzer = StackTraceAnalyzer()

        patterns = analyzer.analyze("AssertionError: expected True")

        assert "assertion" in patterns

    def test_analyze_detects_assertion_failed(self) -> None:
        """Test analyze detects assertion failed."""
        analyzer = StackTraceAnalyzer()

        patterns = analyzer.analyze("assertion failed: x > 0")

        assert "assertion" in patterns

    def test_analyze_no_patterns(self) -> None:
        """Test analyze with no matching patterns."""
        analyzer = StackTraceAnalyzer()

        patterns = analyzer.analyze("Everything is fine")

        assert patterns == []

    def test_analyze_multiple_patterns(self) -> None:
        """Test analyze detects multiple patterns."""
        analyzer = StackTraceAnalyzer()

        patterns = analyzer.analyze("TypeError: invalid value, KeyError: missing")

        assert "type" in patterns
        assert "key" in patterns

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
        assert any("Type mismatch" in h.description for h in hypotheses)
        assert any("Invalid value" in h.description for h in hypotheses)

    def test_generate_with_file_info(self) -> None:
        """Test generate adds location hypothesis with file info."""
        generator = HypothesisGenerator()
        parsed = ParsedError(file="module.py", line=42)

        hypotheses = generator.generate(["type"], parsed)

        # First hypothesis should be location-specific
        assert hypotheses[0].description == "Error at module.py:42"
        assert "42" in hypotheses[0].test_command

    def test_generate_without_file_info(self) -> None:
        """Test generate without file info."""
        generator = HypothesisGenerator()
        parsed = ParsedError()

        hypotheses = generator.generate(["import"], parsed)

        # Should not have location hypothesis
        assert not any("Error at" in h.description for h in hypotheses)

    def test_generate_all_patterns(self) -> None:
        """Test generate handles all known patterns."""
        generator = HypothesisGenerator()
        parsed = ParsedError()

        all_patterns = [
            "recursion",
            "memory",
            "timeout",
            "connection",
            "permission",
            "import",
            "type",
            "value",
            "key",
            "attribute",
            "index",
            "file",
            "syntax",
            "assertion",
        ]

        hypotheses = generator.generate(all_patterns, parsed)

        assert len(hypotheses) == len(all_patterns)

    def test_generate_unknown_pattern(self) -> None:
        """Test generate ignores unknown patterns."""
        generator = HypothesisGenerator()
        parsed = ParsedError()

        hypotheses = generator.generate(["unknown_pattern"], parsed)

        assert hypotheses == []

    def test_generate_hypothesis_has_likelihood(self) -> None:
        """Test generated hypotheses have likelihood."""
        generator = HypothesisGenerator()
        parsed = ParsedError()

        hypotheses = generator.generate(["memory"], parsed)

        assert hypotheses[0].likelihood in ["high", "medium", "low"]

    def test_generate_hypothesis_has_test_command(self) -> None:
        """Test generated hypotheses have test commands."""
        generator = HypothesisGenerator()
        parsed = ParsedError()

        hypotheses = generator.generate(["connection"], parsed)

        assert hypotheses[0].test_command != ""


# =============================================================================
# DebugCommand Tests
# =============================================================================


class TestDebugCommand:
    """Tests for DebugCommand class."""

    def test_init_default_config(self) -> None:
        """Test initialization with default config."""
        debugger = DebugCommand()

        assert debugger.config.verbose is False
        assert debugger.config.max_hypotheses == 3

    def test_init_custom_config(self) -> None:
        """Test initialization with custom config."""
        config = DebugConfig(verbose=True, max_hypotheses=5)
        debugger = DebugCommand(config)

        assert debugger.config.verbose is True
        assert debugger.config.max_hypotheses == 5

    def test_run_with_error(self) -> None:
        """Test run with error message."""
        debugger = DebugCommand()

        result = debugger.run(error="ValueError: invalid literal")

        assert result.symptom == "ValueError: invalid literal"
        assert result.has_root_cause is True

    def test_run_with_stack_trace(self) -> None:
        """Test run with stack trace."""
        debugger = DebugCommand()
        stack_trace = """Traceback (most recent call last):
  File "test.py", line 10
    x = int('abc')
ValueError: invalid literal"""

        result = debugger.run(error="", stack_trace=stack_trace)

        assert result.parsed_error is not None

    def test_run_combines_error_and_trace(self) -> None:
        """Test run combines error and stack trace."""
        debugger = DebugCommand()

        result = debugger.run(
            error="ValueError: bad value",
            stack_trace='File "test.py", line 5',
        )

        assert "ValueError" in result.symptom
        assert result.parsed_error.file == "test.py"

    def test_run_limits_hypotheses(self) -> None:
        """Test run limits hypotheses to max_hypotheses."""
        config = DebugConfig(max_hypotheses=2)
        debugger = DebugCommand(config)

        # Generate error that would produce many hypotheses
        error = "TypeError: invalid value, KeyError: missing, IndexError: out of range"
        result = debugger.run(error=error)

        assert len(result.hypotheses) <= 2

    def test_run_determines_root_cause_with_type_and_file(self) -> None:
        """Test run determines root cause with error type and file."""
        debugger = DebugCommand()
        error = """ValueError: invalid literal
File "module.py", line 42"""

        result = debugger.run(error=error)

        assert "ValueError" in result.root_cause
        assert "module.py" in result.root_cause
        assert result.confidence == 0.9

    def test_run_determines_root_cause_with_type_only(self) -> None:
        """Test run determines root cause with error type only."""
        debugger = DebugCommand()
        error = "KeyError: missing_key"

        result = debugger.run(error=error)

        assert "KeyError" in result.root_cause
        assert result.confidence == 0.7

    def test_run_determines_root_cause_from_hypothesis(self) -> None:
        """Test run determines root cause from hypothesis."""
        debugger = DebugCommand()
        error = "connection refused"

        result = debugger.run(error=error)

        assert len(result.hypotheses) > 0
        assert result.confidence >= 0.5

    def test_run_unknown_cause(self) -> None:
        """Test run with unknown cause."""
        debugger = DebugCommand()

        result = debugger.run(error="Something happened")

        assert "Unknown" in result.root_cause
        assert result.confidence == 0.3

    def test_run_hypothesis_likelihood_confidence(self) -> None:
        """Test run sets confidence based on hypothesis likelihood."""
        debugger = DebugCommand()

        # Memory errors have high likelihood
        result = debugger.run(error="heap out of memory")

        assert result.confidence >= 0.5

    def test_format_result_json(self) -> None:
        """Test format_result with JSON output."""
        debugger = DebugCommand()
        result = debugger.run(error="ValueError: test")

        output = debugger.format_result(result, fmt="json")

        parsed = json.loads(output)
        assert "symptom" in parsed
        assert "root_cause" in parsed
        assert "hypotheses" in parsed

    def test_format_result_text(self) -> None:
        """Test format_result with text output."""
        debugger = DebugCommand()
        result = debugger.run(error="KeyError: missing")

        output = debugger.format_result(result, fmt="text")

        assert "Diagnostic Report" in output
        assert "Symptom:" in output
        assert "Root Cause:" in output
        assert "Recommendation:" in output

    def test_format_result_text_with_parsed_error(self) -> None:
        """Test format_result text includes parsed error."""
        debugger = DebugCommand()
        error = """ValueError: bad input
File "app.py", line 20"""

        result = debugger.run(error=error)
        output = debugger.format_result(result, fmt="text")

        assert "Parsed Error:" in output
        assert "Type:" in output
        assert "Location:" in output

    def test_format_result_text_with_hypotheses(self) -> None:
        """Test format_result text includes hypotheses."""
        debugger = DebugCommand()
        result = debugger.run(error="connection refused")

        output = debugger.format_result(result, fmt="text")

        assert "Hypotheses:" in output

    def test_format_result_text_verbose(self) -> None:
        """Test format_result text with verbose config shows test commands."""
        config = DebugConfig(verbose=True)
        debugger = DebugCommand(config)
        result = debugger.run(error="ImportError: no module")

        output = debugger.format_result(result, fmt="text")

        assert "Test:" in output

    def test_format_result_text_likelihood_icons(self) -> None:
        """Test format_result text shows likelihood icons."""
        debugger = DebugCommand()
        result = debugger.run(error="MemoryError: heap")

        output = debugger.format_result(result, fmt="text")

        # Should contain one of the likelihood icons
        assert any(icon in output for icon in ["high", "medium", "low"])


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
        assert "at line 10" in content

    def test_load_nonexistent_file(self) -> None:
        """Test loading nonexistent file returns empty string."""
        content = _load_stacktrace_file("/nonexistent/trace.txt")

        assert content == ""

    def test_load_file_with_exception(self, tmp_path: Path) -> None:
        """Test loading file handles exceptions."""
        # Create a directory with the name to cause an error
        dir_path = tmp_path / "not_a_file"
        dir_path.mkdir()

        content = _load_stacktrace_file(str(dir_path))

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
        assert "verbose" in result.output
        assert "output" in result.output
        assert "json" in result.output

    @patch("zerg.commands.debug.console")
    def test_debug_no_input(self, mock_console: MagicMock) -> None:
        """Test debug with no error or stack trace."""
        runner = CliRunner()
        result = runner.invoke(debug, [])

        assert result.exit_code == 0

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

    @patch("zerg.commands.debug.DebugCommand")
    @patch("zerg.commands.debug._load_stacktrace_file")
    @patch("zerg.commands.debug.console")
    def test_debug_with_stacktrace_file(
        self,
        mock_console: MagicMock,
        mock_load: MagicMock,
        mock_command_class: MagicMock,
    ) -> None:
        """Test debug with --stacktrace file."""
        mock_load.return_value = "Error: test\n  at line 10"
        mock_command = MagicMock()
        mock_command.run.return_value = DiagnosticResult(
            symptom="Error: test",
            hypotheses=[],
            root_cause="Test error",
            recommendation="Fix it",
            confidence=0.8,
            parsed_error=None,
        )
        mock_command.config = DebugConfig()
        mock_command_class.return_value = mock_command

        runner = CliRunner()
        result = runner.invoke(debug, ["--stacktrace", "trace.txt"])

        assert result.exit_code == 0

    @patch("zerg.commands.debug._load_stacktrace_file")
    @patch("zerg.commands.debug.console")
    def test_debug_stacktrace_not_found(self, mock_console: MagicMock, mock_load: MagicMock) -> None:
        """Test debug warns when stacktrace file not found."""
        mock_load.return_value = ""

        runner = CliRunner()
        result = runner.invoke(debug, ["--stacktrace", "nonexistent.txt"])

        # Should exit 0 since we have no error either
        assert result.exit_code == 0

    @patch("zerg.commands.debug.DebugCommand")
    @patch("zerg.commands.debug.console")
    def test_debug_json_output(self, mock_console: MagicMock, mock_command_class: MagicMock) -> None:
        """Test debug --json."""
        mock_command = MagicMock()
        mock_command.run.return_value = DiagnosticResult(
            symptom="Error",
            hypotheses=[],
            root_cause="Cause",
            recommendation="Fix",
            confidence=0.8,
            parsed_error=None,
        )
        mock_command.format_result.return_value = '{"test": 1}'
        mock_command.config = DebugConfig()
        mock_command_class.return_value = mock_command

        runner = CliRunner()
        result = runner.invoke(debug, ["--error", "Error", "--json"])

        assert result.exit_code == 0

    @patch("zerg.commands.debug.DebugCommand")
    @patch("zerg.commands.debug.console")
    def test_debug_verbose(self, mock_console: MagicMock, mock_command_class: MagicMock) -> None:
        """Test debug --verbose."""
        hypothesis = Hypothesis(
            description="Test hypothesis",
            likelihood="high",
            test_command="run test",
        )
        mock_command = MagicMock()
        mock_command.run.return_value = DiagnosticResult(
            symptom="Error",
            hypotheses=[hypothesis],
            root_cause="Cause",
            recommendation="Fix",
            confidence=0.8,
            parsed_error=None,
        )
        mock_command.config = DebugConfig(verbose=True)
        mock_command_class.return_value = mock_command

        runner = CliRunner()
        result = runner.invoke(debug, ["--error", "Error", "--verbose"])

        assert result.exit_code == 0

    @patch("zerg.commands.debug.DebugCommand")
    @patch("zerg.commands.debug.console")
    def test_debug_with_hypotheses(self, mock_console: MagicMock, mock_command_class: MagicMock) -> None:
        """Test debug displays hypotheses."""
        hypotheses = [
            Hypothesis(description="Hyp 1", likelihood="high"),
            Hypothesis(description="Hyp 2", likelihood="medium"),
            Hypothesis(description="Hyp 3", likelihood="low"),
        ]
        mock_command = MagicMock()
        mock_command.run.return_value = DiagnosticResult(
            symptom="Error",
            hypotheses=hypotheses,
            root_cause="Cause",
            recommendation="Fix",
            confidence=0.8,
            parsed_error=None,
        )
        mock_command.config = DebugConfig()
        mock_command_class.return_value = mock_command

        runner = CliRunner()
        result = runner.invoke(debug, ["--error", "Error"])

        assert result.exit_code == 0

    @patch("zerg.commands.debug.DebugCommand")
    @patch("zerg.commands.debug.console")
    def test_debug_with_parsed_error_location(self, mock_console: MagicMock, mock_command_class: MagicMock) -> None:
        """Test debug displays parsed error with location."""
        mock_command = MagicMock()
        mock_command.run.return_value = DiagnosticResult(
            symptom="ValueError: test",
            hypotheses=[],
            root_cause="Test error",
            recommendation="Fix it",
            confidence=0.9,
            parsed_error=ParsedError(
                error_type="ValueError",
                message="test",
                file="module.py",
                line=42,
            ),
        )
        mock_command.config = DebugConfig()
        mock_command_class.return_value = mock_command

        runner = CliRunner()
        result = runner.invoke(debug, ["--error", "ValueError: test"])

        assert result.exit_code == 0

    @patch("zerg.commands.debug.DebugCommand")
    @patch("zerg.commands.debug.console")
    def test_debug_writes_output_file(
        self, mock_console: MagicMock, mock_command_class: MagicMock, tmp_path: Path
    ) -> None:
        """Test debug writes to output file."""
        mock_command = MagicMock()
        mock_command.run.return_value = DiagnosticResult(
            symptom="Error",
            hypotheses=[],
            root_cause="Cause",
            recommendation="Fix",
            confidence=0.8,
            parsed_error=None,
        )
        mock_command.format_result.return_value = "Diagnostic report"
        mock_command.config = DebugConfig()
        mock_command_class.return_value = mock_command

        output_file = tmp_path / "report.txt"

        runner = CliRunner()
        result = runner.invoke(debug, ["--error", "Error", "--output", str(output_file)])

        assert result.exit_code == 0
        assert output_file.exists()
        assert output_file.read_text() == "Diagnostic report"

    @patch("zerg.commands.debug.console")
    def test_debug_keyboard_interrupt(self, mock_console: MagicMock) -> None:
        """Test debug handles KeyboardInterrupt."""
        with patch(
            "zerg.commands.debug.DebugCommand",
            side_effect=KeyboardInterrupt,
        ):
            runner = CliRunner()
            result = runner.invoke(debug, ["--error", "Error"])

            assert result.exit_code == 130

    @patch("zerg.commands.debug.console")
    def test_debug_generic_exception(self, mock_console: MagicMock) -> None:
        """Test debug handles generic exception."""
        with patch(
            "zerg.commands.debug.DebugCommand",
            side_effect=RuntimeError("Unexpected error"),
        ):
            runner = CliRunner()
            result = runner.invoke(debug, ["--error", "Error"])

            assert result.exit_code == 1

    @patch("zerg.commands.debug.DebugCommand")
    @patch("zerg.commands.debug.console")
    def test_debug_confidence_colors(self, mock_console: MagicMock, mock_command_class: MagicMock) -> None:
        """Test debug displays confidence with appropriate colors."""
        # High confidence (green)
        mock_command = MagicMock()
        mock_command.run.return_value = DiagnosticResult(
            symptom="Error",
            hypotheses=[],
            root_cause="Cause",
            recommendation="Fix",
            confidence=0.8,
            parsed_error=None,
        )
        mock_command.config = DebugConfig()
        mock_command_class.return_value = mock_command

        runner = CliRunner()
        result = runner.invoke(debug, ["--error", "Error"])

        assert result.exit_code == 0

        # Low confidence (red)
        mock_command.run.return_value = DiagnosticResult(
            symptom="Error",
            hypotheses=[],
            root_cause="Unknown",
            recommendation="Debug",
            confidence=0.3,
            parsed_error=None,
        )

        result = runner.invoke(debug, ["--error", "Something"])

        assert result.exit_code == 0

    @patch("zerg.commands.debug.DebugCommand")
    @patch("zerg.commands.debug.console")
    def test_debug_no_hypotheses(self, mock_console: MagicMock, mock_command_class: MagicMock) -> None:
        """Test debug with no hypotheses generated."""
        mock_command = MagicMock()
        mock_command.run.return_value = DiagnosticResult(
            symptom="Unknown error",
            hypotheses=[],
            root_cause="Unknown",
            recommendation="Collect more data",
            confidence=0.3,
            parsed_error=None,
        )
        mock_command.config = DebugConfig()
        mock_command_class.return_value = mock_command

        runner = CliRunner()
        result = runner.invoke(debug, ["--error", "Something random"])

        assert result.exit_code == 0


# =============================================================================
# Extended DiagnosticResult Tests (new fields)
# =============================================================================


class TestDiagnosticResultExtended:
    """Tests for DiagnosticResult with deep diagnostics fields."""

    def test_new_fields_default_none(self) -> None:
        """Test new optional fields default to None/empty."""
        result = DiagnosticResult(
            symptom="Error",
            hypotheses=[],
            root_cause="Cause",
            recommendation="Fix",
        )
        assert result.zerg_health is None
        assert result.system_health is None
        assert result.recovery_plan is None
        assert result.evidence == []
        assert result.log_patterns == []

    def test_to_dict_includes_zerg_health(self) -> None:
        """Test to_dict includes zerg_health when set."""
        health = ZergHealthReport(feature="test", state_exists=True, total_tasks=5)
        result = DiagnosticResult(
            symptom="Error",
            hypotheses=[],
            root_cause="Cause",
            recommendation="Fix",
            zerg_health=health,
        )
        d = result.to_dict()
        assert "zerg_health" in d
        assert d["zerg_health"]["feature"] == "test"

    def test_to_dict_includes_system_health(self) -> None:
        """Test to_dict includes system_health when set."""
        sys_h = SystemHealthReport(git_clean=False, git_branch="main")
        result = DiagnosticResult(
            symptom="Error",
            hypotheses=[],
            root_cause="Cause",
            recommendation="Fix",
            system_health=sys_h,
        )
        d = result.to_dict()
        assert "system_health" in d
        assert d["system_health"]["git_clean"] is False

    def test_to_dict_includes_recovery_plan(self) -> None:
        """Test to_dict includes recovery_plan when set."""
        plan = RecoveryPlan(
            problem="P",
            root_cause="C",
            steps=[RecoveryStep(description="S", command="cmd")],
        )
        result = DiagnosticResult(
            symptom="Error",
            hypotheses=[],
            root_cause="Cause",
            recommendation="Fix",
            recovery_plan=plan,
        )
        d = result.to_dict()
        assert "recovery_plan" in d
        assert len(d["recovery_plan"]["steps"]) == 1

    def test_to_dict_includes_evidence(self) -> None:
        """Test to_dict includes evidence when non-empty."""
        result = DiagnosticResult(
            symptom="Error",
            hypotheses=[],
            root_cause="Cause",
            recommendation="Fix",
            evidence=["finding 1", "finding 2"],
        )
        d = result.to_dict()
        assert d["evidence"] == ["finding 1", "finding 2"]

    def test_to_dict_includes_log_patterns(self) -> None:
        """Test to_dict includes log_patterns when non-empty."""
        pat = LogPattern(
            pattern="RuntimeError",
            count=3,
            first_seen="1",
            last_seen="10",
            worker_ids=[1, 2],
        )
        result = DiagnosticResult(
            symptom="Error",
            hypotheses=[],
            root_cause="Cause",
            recommendation="Fix",
            log_patterns=[pat],
        )
        d = result.to_dict()
        assert len(d["log_patterns"]) == 1
        assert d["log_patterns"][0]["count"] == 3

    def test_to_dict_omits_none_fields(self) -> None:
        """Test to_dict omits None deep diagnostic fields."""
        result = DiagnosticResult(
            symptom="Error",
            hypotheses=[],
            root_cause="Cause",
            recommendation="Fix",
        )
        d = result.to_dict()
        assert "zerg_health" not in d
        assert "system_health" not in d
        assert "recovery_plan" not in d
        assert "evidence" not in d
        assert "log_patterns" not in d


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

    def test_run_with_deep(self) -> None:
        """Test run with deep=True triggers system diagnostics."""
        debugger = DebugCommand()
        with patch.object(debugger, "_run_system_diagnostics") as mock_sys:
            mock_sys.side_effect = lambda r: r
            with patch.object(debugger, "_plan_recovery") as mock_plan:
                mock_plan.side_effect = lambda r: r
                debugger.run(error="test error", deep=True, auto_fix=True)
        mock_sys.assert_called_once()

    def test_run_without_feature_or_deep(self) -> None:
        """Test run without feature/deep doesn't trigger deep diagnostics."""
        debugger = DebugCommand()
        result = debugger.run(error="ValueError: test")
        assert result.zerg_health is None
        assert result.system_health is None
        assert result.recovery_plan is None

    def test_run_zerg_diagnostics(self, tmp_path: Path) -> None:
        """Test _run_zerg_diagnostics integration."""
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        import json

        state = {
            "tasks": {"T1": {"status": "failed", "error": "err"}},
            "workers": {},
        }
        (state_dir / "feat.json").write_text(json.dumps(state))

        debugger = DebugCommand()
        result = DiagnosticResult(
            symptom="test",
            hypotheses=[],
            root_cause="unknown",
            recommendation="fix",
        )
        with patch("zerg.diagnostics.state_introspector.ZergStateIntrospector") as mock_intr_cls:
            mock_intr = mock_intr_cls.return_value
            mock_intr.get_health_report.return_value = ZergHealthReport(
                feature="feat",
                state_exists=True,
                total_tasks=1,
                failed_tasks=[{"task_id": "T1", "error": "err"}],
            )
            with patch("zerg.diagnostics.log_analyzer.LogAnalyzer") as mock_log_cls:
                mock_log_cls.return_value.scan_worker_logs.return_value = []
                result = debugger._run_zerg_diagnostics(result, "feat", None)

        assert result.zerg_health is not None
        assert "1 failed task" in result.evidence[0]

    def test_run_system_diagnostics(self) -> None:
        """Test _run_system_diagnostics integration."""
        debugger = DebugCommand()
        result = DiagnosticResult(
            symptom="test",
            hypotheses=[],
            root_cause="unknown",
            recommendation="fix",
        )
        with patch("zerg.diagnostics.system_diagnostics.SystemDiagnostics") as mock_sys_cls:
            mock_sys_cls.return_value.run_all.return_value = SystemHealthReport(
                git_clean=False,
                git_uncommitted_files=5,
                port_conflicts=[9500],
                disk_free_gb=0.5,
            )
            result = debugger._run_system_diagnostics(result)

        assert result.system_health is not None
        assert any("uncommitted" in e for e in result.evidence)
        assert any("Port" in e for e in result.evidence)
        assert any("disk" in e.lower() for e in result.evidence)

    def test_plan_recovery(self) -> None:
        """Test _plan_recovery integration."""
        debugger = DebugCommand()
        result = DiagnosticResult(
            symptom="test",
            hypotheses=[],
            root_cause="unknown",
            recommendation="fix",
        )
        with patch("zerg.diagnostics.recovery.RecoveryPlanner") as mock_plan_cls:
            mock_plan_cls.return_value.plan.return_value = RecoveryPlan(
                problem="test",
                root_cause="cause",
                steps=[RecoveryStep(description="step", command="cmd")],
            )
            result = debugger._plan_recovery(result)

        assert result.recovery_plan is not None
        assert len(result.recovery_plan.steps) == 1

    def test_format_result_text_with_zerg_health(self) -> None:
        """Test format_result text includes ZERG health section."""
        debugger = DebugCommand(DebugConfig(verbose=True))
        result = DiagnosticResult(
            symptom="Error",
            hypotheses=[],
            root_cause="Cause",
            recommendation="Fix",
            zerg_health=ZergHealthReport(
                feature="auth",
                state_exists=True,
                total_tasks=10,
                task_summary={"complete": 7, "failed": 3},
            ),
        )
        output = debugger.format_result(result)
        assert "ZERG Health:" in output
        assert "auth" in output
        assert "10" in output

    def test_format_result_text_with_system_health(self) -> None:
        """Test format_result text includes system health section."""
        debugger = DebugCommand(DebugConfig(verbose=True))
        result = DiagnosticResult(
            symptom="Error",
            hypotheses=[],
            root_cause="Cause",
            recommendation="Fix",
            system_health=SystemHealthReport(
                git_clean=False,
                git_branch="main",
                disk_free_gb=50.0,
            ),
        )
        output = debugger.format_result(result)
        assert "System Health:" in output
        assert "dirty" in output
        assert "main" in output

    def test_format_result_text_with_log_patterns(self) -> None:
        """Test format_result text includes log patterns section."""
        debugger = DebugCommand(DebugConfig(verbose=True))
        result = DiagnosticResult(
            symptom="Error",
            hypotheses=[],
            root_cause="Cause",
            recommendation="Fix",
            log_patterns=[
                LogPattern(
                    pattern="RuntimeError: crash",
                    count=5,
                    first_seen="1",
                    last_seen="10",
                    worker_ids=[1, 2],
                )
            ],
        )
        output = debugger.format_result(result)
        assert "Log Patterns:" in output
        assert "5x" in output

    def test_format_result_text_with_evidence(self) -> None:
        """Test format_result text includes evidence section."""
        debugger = DebugCommand(DebugConfig(verbose=True))
        result = DiagnosticResult(
            symptom="Error",
            hypotheses=[],
            root_cause="Cause",
            recommendation="Fix",
            evidence=["3 failed tasks", "Low disk space"],
        )
        output = debugger.format_result(result)
        assert "Evidence:" in output
        assert "3 failed tasks" in output

    def test_format_result_text_with_recovery_plan(self) -> None:
        """Test format_result text includes recovery plan section."""
        debugger = DebugCommand(DebugConfig(verbose=True))
        result = DiagnosticResult(
            symptom="Error",
            hypotheses=[],
            root_cause="Cause",
            recommendation="Fix",
            recovery_plan=RecoveryPlan(
                problem="issue",
                root_cause="root",
                steps=[
                    RecoveryStep(
                        description="Restart workers",
                        command="zerg rush",
                        risk="safe",
                    ),
                    RecoveryStep(
                        description="Clean worktrees",
                        command="git worktree prune",
                        risk="moderate",
                    ),
                ],
                verification_command="zerg status",
                prevention="Monitor workers",
            ),
        )
        output = debugger.format_result(result)
        assert "Recovery Plan:" in output
        assert "Restart workers" in output
        assert "zerg rush" in output
        assert "Verify:" in output
        assert "Prevent:" in output

    def test_format_result_json_with_deep_fields(self) -> None:
        """Test format_result JSON includes deep diagnostic fields."""
        debugger = DebugCommand()
        result = DiagnosticResult(
            symptom="Error",
            hypotheses=[],
            root_cause="Cause",
            recommendation="Fix",
            zerg_health=ZergHealthReport(feature="test", state_exists=True, total_tasks=1),
            evidence=["ev1"],
        )
        output = debugger.format_result(result, fmt="json")
        parsed = json.loads(output)
        assert "zerg_health" in parsed
        assert "evidence" in parsed


# =============================================================================
# CLI Extended Options Tests
# =============================================================================


class TestDebugCLIExtended:
    """Tests for new CLI options."""

    def test_help_shows_new_options(self) -> None:
        """Test --help shows new options."""
        runner = CliRunner()
        result = runner.invoke(debug, ["--help"])
        assert result.exit_code == 0
        assert "--feature" in result.output
        assert "--worker" in result.output
        assert "--deep" in result.output
        assert "--auto-fix" in result.output

    @patch("zerg.commands.debug.DebugCommand")
    @patch("zerg.commands.debug.console")
    def test_feature_only_no_error(self, mock_console: MagicMock, mock_command_class: MagicMock) -> None:
        """Test --feature without --error sets default symptom."""
        mock_command = MagicMock()
        mock_command.run.return_value = DiagnosticResult(
            symptom="Investigating feature: test",
            hypotheses=[],
            root_cause="Unknown",
            recommendation="Check state",
            confidence=0.5,
            parsed_error=None,
        )
        mock_command.config = DebugConfig()
        mock_command_class.return_value = mock_command

        runner = CliRunner()
        result = runner.invoke(debug, ["--feature", "test"])

        assert result.exit_code == 0
        mock_command.run.assert_called_once()
        call_kwargs = mock_command.run.call_args
        assert call_kwargs.kwargs.get("feature") == "test"

    @patch("zerg.commands.debug.DebugCommand")
    @patch("zerg.commands.debug.console")
    def test_feature_with_worker(self, mock_console: MagicMock, mock_command_class: MagicMock) -> None:
        """Test --feature with --worker passes worker_id."""
        mock_command = MagicMock()
        mock_command.run.return_value = DiagnosticResult(
            symptom="test",
            hypotheses=[],
            root_cause="cause",
            recommendation="fix",
            confidence=0.5,
            parsed_error=None,
        )
        mock_command.config = DebugConfig()
        mock_command_class.return_value = mock_command

        runner = CliRunner()
        result = runner.invoke(debug, ["--feature", "test", "--worker", "3"])

        assert result.exit_code == 0
        call_kwargs = mock_command.run.call_args
        assert call_kwargs.kwargs.get("worker_id") == 3

    @patch("zerg.commands.debug.DebugCommand")
    @patch("zerg.commands.debug.console")
    def test_deep_flag(self, mock_console: MagicMock, mock_command_class: MagicMock) -> None:
        """Test --deep triggers system diagnostics."""
        mock_command = MagicMock()
        mock_command.run.return_value = DiagnosticResult(
            symptom="test",
            hypotheses=[],
            root_cause="cause",
            recommendation="fix",
            confidence=0.5,
            parsed_error=None,
        )
        mock_command.config = DebugConfig()
        mock_command_class.return_value = mock_command

        runner = CliRunner()
        with patch("zerg.diagnostics.state_introspector.ZergStateIntrospector") as mock_intr_cls:
            mock_intr_cls.return_value.find_latest_feature.return_value = None
            result = runner.invoke(debug, ["--error", "test", "--deep"])

        assert result.exit_code == 0
        call_kwargs = mock_command.run.call_args
        assert call_kwargs.kwargs.get("deep") is True

    @patch("zerg.commands.debug.DebugCommand")
    @patch("zerg.commands.debug.console")
    def test_auto_fix_flag(self, mock_console: MagicMock, mock_command_class: MagicMock) -> None:
        """Test --auto-fix triggers recovery."""
        mock_command = MagicMock()
        mock_command.run.return_value = DiagnosticResult(
            symptom="test",
            hypotheses=[],
            root_cause="cause",
            recommendation="fix",
            confidence=0.5,
            parsed_error=None,
        )
        mock_command.config = DebugConfig()
        mock_command_class.return_value = mock_command

        runner = CliRunner()
        with patch("zerg.diagnostics.state_introspector.ZergStateIntrospector") as mock_intr_cls:
            mock_intr_cls.return_value.find_latest_feature.return_value = "auto-feat"
            result = runner.invoke(debug, ["--error", "test", "--auto-fix"])

        assert result.exit_code == 0
        call_kwargs = mock_command.run.call_args
        assert call_kwargs.kwargs.get("auto_fix") is True

    @patch("zerg.commands.debug.console")
    def test_no_input_shows_feature_hint(self, mock_console: MagicMock) -> None:
        """Test no input shows --feature hint."""
        runner = CliRunner()
        result = runner.invoke(debug, [])
        assert result.exit_code == 0

    @patch("zerg.commands.debug.DebugCommand")
    @patch("zerg.commands.debug.console")
    def test_cli_displays_zerg_health(self, mock_console: MagicMock, mock_command_class: MagicMock) -> None:
        """Test CLI displays ZERG health section."""
        mock_command = MagicMock()
        mock_command.run.return_value = DiagnosticResult(
            symptom="test",
            hypotheses=[],
            root_cause="cause",
            recommendation="fix",
            confidence=0.5,
            parsed_error=None,
            zerg_health=ZergHealthReport(
                feature="auth",
                state_exists=True,
                total_tasks=10,
                task_summary={"complete": 8, "failed": 2},
                failed_tasks=[{"task_id": "T1"}],
            ),
        )
        mock_command.config = DebugConfig()
        mock_command_class.return_value = mock_command

        runner = CliRunner()
        result = runner.invoke(debug, ["--feature", "auth"])
        assert result.exit_code == 0

    @patch("zerg.commands.debug.DebugCommand")
    @patch("zerg.commands.debug.console")
    def test_cli_displays_system_health(self, mock_console: MagicMock, mock_command_class: MagicMock) -> None:
        """Test CLI displays system health section."""
        mock_command = MagicMock()
        mock_command.run.return_value = DiagnosticResult(
            symptom="test",
            hypotheses=[],
            root_cause="cause",
            recommendation="fix",
            confidence=0.5,
            parsed_error=None,
            system_health=SystemHealthReport(
                git_clean=False,
                git_branch="main",
                git_uncommitted_files=3,
                disk_free_gb=50.0,
            ),
        )
        mock_command.config = DebugConfig()
        mock_command_class.return_value = mock_command

        runner = CliRunner()
        result = runner.invoke(debug, ["--error", "test", "--deep"])
        assert result.exit_code == 0

    @patch("zerg.commands.debug.DebugCommand")
    @patch("zerg.commands.debug.console")
    def test_cli_displays_recovery_plan(self, mock_console: MagicMock, mock_command_class: MagicMock) -> None:
        """Test CLI displays recovery plan section."""
        mock_command = MagicMock()
        mock_command.run.return_value = DiagnosticResult(
            symptom="test",
            hypotheses=[],
            root_cause="cause",
            recommendation="fix",
            confidence=0.5,
            parsed_error=None,
            recovery_plan=RecoveryPlan(
                problem="issue",
                root_cause="root",
                steps=[
                    RecoveryStep(
                        description="Fix it",
                        command="do fix",
                        risk="safe",
                    )
                ],
                prevention="Be careful",
            ),
        )
        mock_command.config = DebugConfig()
        mock_command_class.return_value = mock_command

        runner = CliRunner()
        result = runner.invoke(debug, ["--feature", "test"])
        assert result.exit_code == 0


# =============================================================================
# Design Escalation Tests
# =============================================================================


class TestDesignEscalationPropagation:
    """Tests for design escalation propagation from RecoveryPlan to DiagnosticResult."""

    def test_propagation_from_recovery_plan(self) -> None:
        """_plan_recovery propagates needs_design to DiagnosticResult."""
        from zerg.diagnostics.recovery import RecoveryPlan, RecoveryStep

        debugger = DebugCommand()
        diag = DiagnosticResult(
            symptom="test",
            hypotheses=[],
            root_cause="unknown",
            recommendation="fix",
        )
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

    def test_diagnostic_result_to_dict_with_escalation(self) -> None:
        """DiagnosticResult.to_dict() includes design escalation fields."""
        diag = DiagnosticResult(
            symptom="err",
            hypotheses=[],
            root_cause="cause",
            recommendation="fix",
            design_escalation=True,
            design_escalation_reason="wide blast radius",
        )
        d = diag.to_dict()
        assert d["design_escalation"] is True
        assert d["design_escalation_reason"] == "wide blast radius"

    def test_diagnostic_result_to_dict_omits_when_false(self) -> None:
        """DiagnosticResult.to_dict() omits design escalation when False."""
        diag = DiagnosticResult(
            symptom="err",
            hypotheses=[],
            root_cause="cause",
            recommendation="fix",
        )
        d = diag.to_dict()
        assert "design_escalation" not in d
