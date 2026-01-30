"""Tests for ZERG v2 Debug Command."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestDebugPhase:
    """Tests for debug phase enumeration."""

    def test_phases_exist(self):
        """Test debug phases are defined."""
        from debug import DebugPhase

        assert hasattr(DebugPhase, "SYMPTOM")
        assert hasattr(DebugPhase, "HYPOTHESIS")
        assert hasattr(DebugPhase, "TEST")
        assert hasattr(DebugPhase, "ROOT_CAUSE")


class TestDebugConfig:
    """Tests for debug configuration."""

    def test_config_defaults(self):
        """Test DebugConfig has sensible defaults."""
        from debug import DebugConfig

        config = DebugConfig()
        assert config.verbose is False

    def test_config_custom(self):
        """Test DebugConfig with custom values."""
        from debug import DebugConfig

        config = DebugConfig(verbose=True, max_hypotheses=5)
        assert config.verbose is True
        assert config.max_hypotheses == 5


class TestHypothesis:
    """Tests for hypothesis model."""

    def test_hypothesis_creation(self):
        """Test Hypothesis can be created."""
        from debug import Hypothesis

        hyp = Hypothesis(
            description="Database connection timeout",
            likelihood="high",
            test_command="ping db.local",
        )
        assert hyp.description == "Database connection timeout"

    def test_hypothesis_to_dict(self):
        """Test Hypothesis serialization."""
        from debug import Hypothesis

        hyp = Hypothesis(
            description="Memory leak",
            likelihood="medium",
            test_command="top -l 1",
        )
        data = hyp.to_dict()
        assert data["likelihood"] == "medium"


class TestDiagnosticResult:
    """Tests for diagnostic results."""

    def test_result_creation(self):
        """Test DiagnosticResult can be created."""
        from debug import DiagnosticResult

        result = DiagnosticResult(
            symptom="Application crash",
            hypotheses=[],
            root_cause="Memory exhaustion",
            recommendation="Increase memory limit",
        )
        assert result.symptom == "Application crash"

    def test_result_has_root_cause(self):
        """Test DiagnosticResult root cause detection."""
        from debug import DiagnosticResult

        with_cause = DiagnosticResult(
            symptom="Error",
            hypotheses=[],
            root_cause="Found it",
            recommendation="Fix it",
        )
        assert with_cause.has_root_cause is True

        without = DiagnosticResult(
            symptom="Error",
            hypotheses=[],
            root_cause="",
            recommendation="",
        )
        assert without.has_root_cause is False


class TestErrorParser:
    """Tests for error message parsing."""

    def test_parser_creation(self):
        """Test ErrorParser can be created."""
        from debug import ErrorParser

        parser = ErrorParser()
        assert parser is not None

    def test_parser_python_error(self):
        """Test parsing Python error."""
        from debug import ErrorParser

        parser = ErrorParser()
        error = """Traceback (most recent call last):
  File "test.py", line 10, in <module>
    raise ValueError("test error")
ValueError: test error"""
        result = parser.parse(error)
        assert result.error_type == "ValueError"

    def test_parser_extract_file_line(self):
        """Test extracting file and line from error."""
        from debug import ErrorParser

        parser = ErrorParser()
        error = 'File "test.py", line 10'
        result = parser.parse(error)
        assert result.file == "test.py"
        assert result.line == 10


class TestStackTraceAnalyzer:
    """Tests for stack trace analysis."""

    def test_analyzer_creation(self):
        """Test StackTraceAnalyzer can be created."""
        from debug import StackTraceAnalyzer

        analyzer = StackTraceAnalyzer()
        assert analyzer is not None


class TestDebugCommand:
    """Tests for DebugCommand class."""

    def test_command_creation(self):
        """Test DebugCommand can be created."""
        from debug import DebugCommand

        cmd = DebugCommand()
        assert cmd is not None

    def test_command_run_returns_result(self):
        """Test run returns DiagnosticResult."""
        from debug import DiagnosticResult, DebugCommand

        cmd = DebugCommand()
        result = cmd.run(error="test error", dry_run=True)
        assert isinstance(result, DiagnosticResult)

    def test_command_format_text(self):
        """Test text output format."""
        from debug import DiagnosticResult, DebugCommand

        cmd = DebugCommand()
        result = DiagnosticResult(
            symptom="App crash",
            hypotheses=[],
            root_cause="Memory issue",
            recommendation="Add more RAM",
        )
        output = cmd.format_result(result, format="text")
        assert "Debug" in output or "Diagnostic" in output

    def test_command_format_json(self):
        """Test JSON output format."""
        import json

        from debug import DiagnosticResult, DebugCommand

        cmd = DebugCommand()
        result = DiagnosticResult(
            symptom="Error",
            hypotheses=[],
            root_cause="Bug",
            recommendation="Fix",
        )
        output = cmd.format_result(result, format="json")
        data = json.loads(output)
        assert "symptom" in data
