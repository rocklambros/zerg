"""ZERG troubleshoot command - systematic debugging with root cause analysis."""

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from zerg.logging import get_logger

console = Console()
logger = get_logger("troubleshoot")


class TroubleshootPhase(Enum):
    """Phases of troubleshooting process."""

    SYMPTOM = "symptom"
    HYPOTHESIS = "hypothesis"
    TEST = "test"
    ROOT_CAUSE = "root_cause"


@dataclass
class TroubleshootConfig:
    """Configuration for troubleshooting."""

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

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "error_type": self.error_type,
            "message": self.message,
            "file": self.file,
            "line": self.line,
            "stack_trace": self.stack_trace,
        }


@dataclass
class DiagnosticResult:
    """Result of diagnostic analysis."""

    symptom: str
    hypotheses: list[Hypothesis]
    root_cause: str
    recommendation: str
    phase: TroubleshootPhase = TroubleshootPhase.ROOT_CAUSE
    confidence: float = 0.8
    parsed_error: ParsedError | None = None

    @property
    def has_root_cause(self) -> bool:
        """Check if root cause was found."""
        return bool(self.root_cause)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "symptom": self.symptom,
            "root_cause": self.root_cause,
            "recommendation": self.recommendation,
            "confidence": self.confidence,
            "phase": self.phase.value,
            "hypotheses": [h.to_dict() for h in self.hypotheses],
            "parsed_error": self.parsed_error.to_dict() if self.parsed_error else None,
        }


class ErrorParser:
    """Parse error messages and stack traces."""

    # Python error patterns
    PYTHON_ERROR = re.compile(r"(\w+Error|\w+Exception):\s*(.+)")
    PYTHON_FILE_LINE = re.compile(r'File "([^"]+)", line (\d+)')

    # JavaScript error patterns
    JS_ERROR = re.compile(r"(TypeError|ReferenceError|SyntaxError|Error):\s*(.+)")
    JS_FILE_LINE = re.compile(r"at\s+.+\(([^:]+):(\d+):\d+\)")

    # Go error patterns
    GO_FILE_LINE = re.compile(r"([^\s]+\.go):(\d+)")

    # Rust error patterns
    RUST_ERROR = re.compile(r"error\[E\d+\]:\s*(.+)")
    RUST_FILE_LINE = re.compile(r"-->\s*([^:]+):(\d+):\d+")

    def parse(self, error: str) -> ParsedError:
        """Parse error string."""
        result = ParsedError()

        # Try Python patterns first
        match = self.PYTHON_ERROR.search(error)
        if match:
            result.error_type = match.group(1)
            result.message = match.group(2)

        match = self.PYTHON_FILE_LINE.search(error)
        if match:
            result.file = match.group(1)
            result.line = int(match.group(2))

        # Try JavaScript patterns
        if not result.error_type:
            match = self.JS_ERROR.search(error)
            if match:
                result.error_type = match.group(1)
                result.message = match.group(2)

            match = self.JS_FILE_LINE.search(error)
            if match:
                result.file = match.group(1)
                result.line = int(match.group(2))

        # Try Go patterns
        if not result.file:
            match = self.GO_FILE_LINE.search(error)
            if match:
                result.file = match.group(1)
                result.line = int(match.group(2))

        # Try Rust patterns
        if not result.error_type:
            match = self.RUST_ERROR.search(error)
            if match:
                result.error_type = "RustError"
                result.message = match.group(1)

            match = self.RUST_FILE_LINE.search(error)
            if match:
                result.file = match.group(1)
                result.line = int(match.group(2))

        # Extract stack trace lines
        lines = error.strip().split("\n")
        for line in lines:
            stripped = line.strip()
            if (
                stripped.startswith("File ")
                or stripped.startswith("at ")
                or stripped.startswith("-->")
                or re.match(r"^\s*\d+:", stripped)
            ):
                result.stack_trace.append(stripped)

        return result


class StackTraceAnalyzer:
    """Analyze stack traces for patterns."""

    COMMON_PATTERNS = {
        "recursion": [r"maximum recursion", r"RecursionError", r"stack overflow"],
        "memory": [r"MemoryError", r"out of memory", r"OOM", r"heap"],
        "timeout": [r"TimeoutError", r"timed out", r"deadline exceeded"],
        "connection": [r"ConnectionError", r"connection refused", r"ECONNREFUSED"],
        "permission": [r"PermissionError", r"permission denied", r"EACCES"],
        "import": [r"ImportError", r"ModuleNotFoundError", r"cannot find module"],
        "type": [r"TypeError", r"type error", r"incompatible types"],
        "value": [r"ValueError", r"invalid value", r"invalid argument"],
        "key": [r"KeyError", r"undefined key", r"missing key"],
        "attribute": [r"AttributeError", r"has no attribute", r"undefined property"],
        "index": [r"IndexError", r"index out of range", r"out of bounds"],
        "file": [r"FileNotFoundError", r"no such file", r"ENOENT"],
        "syntax": [r"SyntaxError", r"unexpected token", r"parse error"],
        "assertion": [r"AssertionError", r"assertion failed"],
    }

    def analyze(self, stack_trace: str) -> list[str]:
        """Analyze stack trace for patterns."""
        patterns = []
        trace_lower = stack_trace.lower()

        for name, pattern_list in self.COMMON_PATTERNS.items():
            for pattern in pattern_list:
                if re.search(pattern, trace_lower, re.IGNORECASE):
                    if name not in patterns:
                        patterns.append(name)
                    break

        return patterns


class HypothesisGenerator:
    """Generate hypotheses based on error patterns."""

    HYPOTHESIS_TEMPLATES = {
        "recursion": Hypothesis(
            description="Infinite recursion or circular reference",
            likelihood="high",
            test_command="Check for circular imports or recursive calls",
        ),
        "memory": Hypothesis(
            description="Memory exhaustion from large data or leak",
            likelihood="high",
            test_command="Monitor memory usage, check for unbounded collections",
        ),
        "timeout": Hypothesis(
            description="Operation taking too long or blocked",
            likelihood="medium",
            test_command="Check network calls, database queries, or long computations",
        ),
        "connection": Hypothesis(
            description="Network or service connection failure",
            likelihood="high",
            test_command="Verify service is running and accessible",
        ),
        "permission": Hypothesis(
            description="Insufficient permissions for file or resource",
            likelihood="high",
            test_command="Check file permissions and user access rights",
        ),
        "import": Hypothesis(
            description="Missing module or incorrect import path",
            likelihood="high",
            test_command="Verify package is installed and import path is correct",
        ),
        "type": Hypothesis(
            description="Type mismatch or invalid operation on type",
            likelihood="medium",
            test_command="Check argument types and function signatures",
        ),
        "value": Hypothesis(
            description="Invalid value passed to function",
            likelihood="medium",
            test_command="Validate input data and constraints",
        ),
        "key": Hypothesis(
            description="Missing key in dictionary or mapping",
            likelihood="high",
            test_command="Verify key exists before access, use .get() with default",
        ),
        "attribute": Hypothesis(
            description="Accessing non-existent attribute or method",
            likelihood="high",
            test_command="Check object type and available attributes",
        ),
        "index": Hypothesis(
            description="Array/list index out of bounds",
            likelihood="high",
            test_command="Verify collection length before index access",
        ),
        "file": Hypothesis(
            description="File or directory does not exist",
            likelihood="high",
            test_command="Verify path exists and is accessible",
        ),
        "syntax": Hypothesis(
            description="Syntax error in source code",
            likelihood="high",
            test_command="Check for missing brackets, quotes, or keywords",
        ),
        "assertion": Hypothesis(
            description="Assertion condition failed",
            likelihood="medium",
            test_command="Review assertion condition and input values",
        ),
    }

    def generate(self, patterns: list[str], parsed: ParsedError) -> list[Hypothesis]:
        """Generate hypotheses from patterns."""
        hypotheses = []

        for pattern in patterns:
            if pattern in self.HYPOTHESIS_TEMPLATES:
                template = self.HYPOTHESIS_TEMPLATES[pattern]
                hypotheses.append(
                    Hypothesis(
                        description=template.description,
                        likelihood=template.likelihood,
                        test_command=template.test_command,
                    )
                )

        # Add location-specific hypothesis if we have file info
        if parsed.file and parsed.line:
            hypotheses.insert(
                0,
                Hypothesis(
                    description=f"Error at {parsed.file}:{parsed.line}",
                    likelihood="high",
                    test_command=f"Review code at {parsed.file} line {parsed.line}",
                ),
            )

        return hypotheses


class TroubleshootCommand:
    """Main troubleshoot command orchestrator."""

    def __init__(self, config: TroubleshootConfig | None = None) -> None:
        """Initialize troubleshoot command."""
        self.config = config or TroubleshootConfig()
        self.parser = ErrorParser()
        self.analyzer = StackTraceAnalyzer()
        self.hypothesis_generator = HypothesisGenerator()

    def run(
        self,
        error: str = "",
        stack_trace: str = "",
    ) -> DiagnosticResult:
        """Run troubleshooting."""
        full_error = f"{error}\n{stack_trace}".strip()

        # Phase 1: Parse symptom
        symptom = error or "Unknown error"
        parsed = self.parser.parse(full_error)

        # Phase 2: Analyze patterns
        patterns = self.analyzer.analyze(full_error)

        # Phase 3: Generate hypotheses
        hypotheses = self.hypothesis_generator.generate(patterns, parsed)
        hypotheses = hypotheses[: self.config.max_hypotheses]

        # Phase 4: Determine root cause
        root_cause, recommendation, confidence = self._determine_root_cause(
            parsed, hypotheses
        )

        return DiagnosticResult(
            symptom=symptom,
            hypotheses=hypotheses,
            root_cause=root_cause,
            recommendation=recommendation,
            confidence=confidence,
            parsed_error=parsed,
        )

    def _determine_root_cause(
        self, parsed: ParsedError, hypotheses: list[Hypothesis]
    ) -> tuple[str, str, float]:
        """Determine most likely root cause."""
        confidence = 0.5

        if parsed.error_type and parsed.file:
            confidence = 0.9
            return (
                f"{parsed.error_type} at {parsed.file}:{parsed.line}",
                f"Review code at {parsed.file} line {parsed.line}. Error: {parsed.message}",
                confidence,
            )

        if parsed.error_type:
            confidence = 0.7
            return (
                f"{parsed.error_type}: {parsed.message}",
                f"Investigate {parsed.error_type} - {parsed.message}",
                confidence,
            )

        if hypotheses:
            top = hypotheses[0]
            confidence = {"high": 0.8, "medium": 0.6, "low": 0.4}.get(
                top.likelihood, 0.5
            )
            return (
                top.description,
                top.test_command or f"Investigate: {top.description}",
                confidence,
            )

        return "Unknown cause", "Collect more diagnostic information", 0.3

    def format_result(self, result: DiagnosticResult, fmt: str = "text") -> str:
        """Format diagnostic result."""
        if fmt == "json":
            return json.dumps(result.to_dict(), indent=2)

        lines = [
            "Diagnostic Report",
            "=" * 50,
            "",
            f"Symptom: {result.symptom[:100]}",
            "",
        ]

        if result.parsed_error and result.parsed_error.error_type:
            lines.append("Parsed Error:")
            lines.append(f"  Type: {result.parsed_error.error_type}")
            if result.parsed_error.message:
                lines.append(f"  Message: {result.parsed_error.message[:80]}")
            if result.parsed_error.file:
                lines.append(
                    f"  Location: {result.parsed_error.file}:{result.parsed_error.line}"
                )
            lines.append("")

        if result.hypotheses:
            lines.append("Hypotheses:")
            for i, h in enumerate(result.hypotheses, 1):
                icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(
                    h.likelihood, "⚪"
                )
                lines.append(f"  {i}. {icon} [{h.likelihood}] {h.description}")
                if h.test_command and self.config.verbose:
                    lines.append(f"     Test: {h.test_command}")
            lines.append("")

        lines.extend(
            [
                f"Root Cause: {result.root_cause}",
                f"Confidence: {result.confidence:.0%}",
                "",
                f"Recommendation: {result.recommendation}",
            ]
        )

        return "\n".join(lines)


def _load_stacktrace_file(filepath: str) -> str:
    """Load stack trace from file."""
    try:
        path = Path(filepath)
        if path.exists():
            return path.read_text(encoding="utf-8")
    except Exception:
        pass
    return ""


@click.command()
@click.option("--error", "-e", help="Error message to analyze")
@click.option("--stacktrace", "-s", help="Path to stack trace file")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.option("--output", "-o", help="Output file for diagnostic report")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.pass_context
def troubleshoot(
    ctx: click.Context,
    error: str | None,
    stacktrace: str | None,
    verbose: bool,
    output: str | None,
    json_output: bool,
) -> None:
    """Systematic debugging with root cause analysis.

    Four-phase process:
    1. Symptom: Parse and identify the error
    2. Hypothesis: Generate possible causes
    3. Test: Verify hypotheses with diagnostics
    4. Root Cause: Determine actual cause with confidence score

    Examples:

        zerg troubleshoot --error "ValueError: invalid literal"

        zerg troubleshoot --stacktrace trace.txt

        zerg troubleshoot --error "Error" --verbose

        zerg troubleshoot --error "ImportError" --json
    """
    try:
        console.print("\n[bold cyan]ZERG Troubleshoot[/bold cyan]\n")

        # Load stack trace from file if provided
        stack_trace_content = ""
        if stacktrace:
            stack_trace_content = _load_stacktrace_file(stacktrace)
            if not stack_trace_content:
                console.print(f"[yellow]Warning: Could not load {stacktrace}[/yellow]")

        # Need at least error or stack trace
        error_message = error or ""
        if not error_message and not stack_trace_content:
            console.print("[yellow]No error provided[/yellow]")
            console.print("Use --error to specify an error message")
            console.print("Use --stacktrace to provide a stack trace file")
            raise SystemExit(0)

        # Create config
        config = TroubleshootConfig(
            verbose=verbose,
            max_hypotheses=5 if verbose else 3,
        )

        # Run diagnostics
        troubleshooter = TroubleshootCommand(config)
        result = troubleshooter.run(
            error=error_message,
            stack_trace=stack_trace_content,
        )

        # Output
        if json_output:
            output_content = troubleshooter.format_result(result, "json")
            console.print(output_content)
        else:
            # Display diagnostic panel
            console.print(Panel("[bold]Phase 1: Symptom Analysis[/bold]", style="cyan"))
            console.print(f"  Error: {result.symptom[:100]}")

            if result.parsed_error and result.parsed_error.error_type:
                console.print(f"  Type: [yellow]{result.parsed_error.error_type}[/yellow]")
                if result.parsed_error.file:
                    console.print(
                        f"  Location: [cyan]{result.parsed_error.file}:{result.parsed_error.line}[/cyan]"
                    )
            console.print()

            # Hypotheses
            if result.hypotheses:
                console.print(
                    Panel("[bold]Phase 2: Hypothesis Generation[/bold]", style="cyan")
                )
                table = Table()
                table.add_column("#", style="dim")
                table.add_column("Likelihood")
                table.add_column("Hypothesis")

                for i, h in enumerate(result.hypotheses, 1):
                    likelihood_color = {
                        "high": "red",
                        "medium": "yellow",
                        "low": "green",
                    }.get(h.likelihood, "white")
                    table.add_row(
                        str(i),
                        f"[{likelihood_color}]{h.likelihood}[/{likelihood_color}]",
                        h.description,
                    )

                console.print(table)

                if verbose:
                    console.print("\n[dim]Test commands:[/dim]")
                    for i, h in enumerate(result.hypotheses, 1):
                        if h.test_command:
                            console.print(f"  {i}. {h.test_command}")
                console.print()

            # Root cause
            console.print(Panel("[bold]Phase 4: Root Cause[/bold]", style="cyan"))
            confidence_color = (
                "green" if result.confidence >= 0.7 else "yellow" if result.confidence >= 0.5 else "red"
            )
            console.print(f"  Root Cause: [bold]{result.root_cause}[/bold]")
            console.print(
                f"  Confidence: [{confidence_color}]{result.confidence:.0%}[/{confidence_color}]"
            )
            console.print()
            console.print(
                Panel(f"[bold]Recommendation:[/bold] {result.recommendation}", style="green")
            )

            output_content = troubleshooter.format_result(result, "text")

        # Write to file if requested
        if output:
            Path(output).write_text(output_content, encoding="utf-8")
            console.print(f"\n[green]✓[/green] Report written to {output}")

        raise SystemExit(0)

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted[/yellow]")
        raise SystemExit(130) from None
    except SystemExit:
        raise
    except Exception as e:
        console.print(f"\n[red]Error:[/red] {e}")
        logger.exception("Troubleshoot command failed")
        raise SystemExit(1) from e
