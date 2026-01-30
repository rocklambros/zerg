"""ZERG v2 Debug Command - Systematic debugging with root cause analysis."""

import json
import re
from dataclasses import dataclass, field
from enum import Enum


class DebugPhase(Enum):
    """Phases of debugging process."""

    SYMPTOM = "symptom"
    HYPOTHESIS = "hypothesis"
    TEST = "test"
    ROOT_CAUSE = "root_cause"


@dataclass
class DebugConfig:
    """Configuration for debugging."""

    verbose: bool = False
    max_hypotheses: int = 3
    auto_test: bool = False


@dataclass
class Hypothesis:
    """A hypothesis about the problem cause."""

    description: str
    likelihood: str  # high, medium, low
    test_command: str = ""
    tested: bool = False
    confirmed: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "description": self.description,
            "likelihood": self.likelihood,
            "test_command": self.test_command,
            "tested": self.tested,
            "confirmed": self.confirmed,
        }


@dataclass
class ParsedError:
    """Parsed error information."""

    error_type: str = ""
    message: str = ""
    file: str = ""
    line: int = 0
    stack_trace: list[str] = field(default_factory=list)


@dataclass
class DiagnosticResult:
    """Result of diagnostic analysis."""

    symptom: str
    hypotheses: list[Hypothesis]
    root_cause: str
    recommendation: str
    phase: DebugPhase = DebugPhase.ROOT_CAUSE
    confidence: float = 0.8

    @property
    def has_root_cause(self) -> bool:
        """Check if root cause was found."""
        return bool(self.root_cause)


class ErrorParser:
    """Parse error messages and stack traces."""

    PYTHON_ERROR = re.compile(r"(\w+Error|\w+Exception):\s*(.+)")
    FILE_LINE = re.compile(r'File "([^"]+)", line (\d+)')

    def parse(self, error: str) -> ParsedError:
        """Parse error string.

        Args:
            error: Error message or stack trace

        Returns:
            ParsedError with extracted information
        """
        result = ParsedError()

        # Extract error type
        match = self.PYTHON_ERROR.search(error)
        if match:
            result.error_type = match.group(1)
            result.message = match.group(2)

        # Extract file and line
        match = self.FILE_LINE.search(error)
        if match:
            result.file = match.group(1)
            result.line = int(match.group(2))

        # Extract stack trace lines
        lines = error.strip().split("\n")
        for line in lines:
            if line.strip().startswith("File ") or line.strip().startswith("at "):
                result.stack_trace.append(line.strip())

        return result


class StackTraceAnalyzer:
    """Analyze stack traces for patterns."""

    COMMON_PATTERNS = {
        "recursion": r"maximum recursion|RecursionError",
        "memory": r"MemoryError|out of memory",
        "timeout": r"TimeoutError|timed out",
        "connection": r"ConnectionError|connection refused",
        "permission": r"PermissionError|permission denied",
        "import": r"ImportError|ModuleNotFoundError",
        "type": r"TypeError",
        "value": r"ValueError",
        "key": r"KeyError",
        "attribute": r"AttributeError",
    }

    def analyze(self, stack_trace: str) -> list[str]:
        """Analyze stack trace for patterns.

        Args:
            stack_trace: Stack trace text

        Returns:
            List of detected patterns
        """
        patterns = []
        for name, pattern in self.COMMON_PATTERNS.items():
            if re.search(pattern, stack_trace, re.IGNORECASE):
                patterns.append(name)
        return patterns


class DebugCommand:
    """Main debug command orchestrator."""

    def __init__(self, config: DebugConfig | None = None):
        """Initialize debug command."""
        self.config = config or DebugConfig()
        self.parser = ErrorParser()
        self.analyzer = StackTraceAnalyzer()

    def run(
        self,
        error: str = "",
        stack_trace: str = "",
        dry_run: bool = False,
    ) -> DiagnosticResult:
        """Run debugging.

        Args:
            error: Error message
            stack_trace: Stack trace if available
            dry_run: If True, don't run tests

        Returns:
            DiagnosticResult with analysis
        """
        # Phase 1: Parse symptom
        symptom = error or "Unknown error"
        parsed = self.parser.parse(error)

        # Phase 2: Generate hypotheses
        hypotheses = self._generate_hypotheses(parsed, stack_trace)

        # Phase 3: Test hypotheses (if not dry_run)
        if not dry_run and self.config.auto_test:
            hypotheses = self._test_hypotheses(hypotheses)

        # Phase 4: Determine root cause
        root_cause, recommendation = self._determine_root_cause(
            parsed, hypotheses
        )

        return DiagnosticResult(
            symptom=symptom,
            hypotheses=hypotheses,
            root_cause=root_cause,
            recommendation=recommendation,
        )

    def _generate_hypotheses(
        self, parsed: ParsedError, stack_trace: str
    ) -> list[Hypothesis]:
        """Generate hypotheses based on error."""
        hypotheses = []

        # Based on error type
        if parsed.error_type:
            hypotheses.append(
                Hypothesis(
                    description=f"{parsed.error_type} in {parsed.file}:{parsed.line}",
                    likelihood="high",
                    test_command=f"python -c 'import {parsed.file.replace('.py', '')}'",
                )
            )

        # Based on patterns
        patterns = self.analyzer.analyze(stack_trace or parsed.message)
        for pattern in patterns[:self.config.max_hypotheses]:
            hypotheses.append(
                Hypothesis(
                    description=f"Possible {pattern} issue",
                    likelihood="medium",
                )
            )

        return hypotheses[:self.config.max_hypotheses]

    def _test_hypotheses(
        self, hypotheses: list[Hypothesis]
    ) -> list[Hypothesis]:
        """Test hypotheses with commands."""
        # Would run test_command for each hypothesis
        return hypotheses

    def _determine_root_cause(
        self, parsed: ParsedError, hypotheses: list[Hypothesis]
    ) -> tuple[str, str]:
        """Determine most likely root cause."""
        if parsed.error_type and parsed.file:
            return (
                f"{parsed.error_type} at {parsed.file}:{parsed.line}",
                f"Check the code at {parsed.file} line {parsed.line} for {parsed.message}",
            )

        if hypotheses:
            top = hypotheses[0]
            return top.description, f"Investigate: {top.description}"

        return "Unknown", "Collect more diagnostic information"

    def format_result(
        self, result: DiagnosticResult, format: str = "text"
    ) -> str:
        """Format diagnostic result.

        Args:
            result: Diagnostic result to format
            format: Output format (text or json)

        Returns:
            Formatted string
        """
        if format == "json":
            return json.dumps(
                {
                    "symptom": result.symptom,
                    "root_cause": result.root_cause,
                    "recommendation": result.recommendation,
                    "confidence": result.confidence,
                    "hypotheses": [h.to_dict() for h in result.hypotheses],
                },
                indent=2,
            )

        lines = [
            "Diagnostic Report",
            "=" * 40,
            "",
            f"Symptom: {result.symptom}",
            "",
        ]

        if result.hypotheses:
            lines.append("Hypotheses:")
            for h in result.hypotheses:
                lines.append(f"  [{h.likelihood}] {h.description}")

        lines.extend(
            [
                "",
                f"Root Cause: {result.root_cause}",
                "",
                f"Recommendation: {result.recommendation}",
            ]
        )

        return "\n".join(lines)


__all__ = [
    "DebugPhase",
    "DebugConfig",
    "Hypothesis",
    "ParsedError",
    "DiagnosticResult",
    "ErrorParser",
    "StackTraceAnalyzer",
    "DebugCommand",
]
