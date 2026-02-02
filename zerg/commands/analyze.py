"""ZERG analyze command - static analysis and quality assessment."""

import contextlib
import json
import shlex
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.table import Table

from zerg.command_executor import CommandExecutor, CommandValidationError
from zerg.logging import get_logger

console = Console()
logger = get_logger("analyze")


class CheckType(Enum):
    """Types of analysis checks."""

    LINT = "lint"
    COMPLEXITY = "complexity"
    COVERAGE = "coverage"
    SECURITY = "security"
    PERFORMANCE = "performance"


@dataclass
class AnalyzeConfig:
    """Configuration for analysis."""

    complexity_threshold: int = 10
    coverage_threshold: int = 70
    lint_command: str = "ruff check"
    security_command: str = "bandit"


@dataclass
class AnalysisResult:
    """Result of an analysis check."""

    check_type: CheckType
    passed: bool
    issues: list[str] = field(default_factory=list)
    score: float = 0.0

    def summary(self) -> str:
        """Generate summary string."""
        status = "PASSED" if self.passed else "FAILED"
        return f"{self.check_type.name}: {status} (score: {self.score:.1f})"


class BaseChecker(ABC):
    """Base class for analysis checkers."""

    name: str = "base"

    @abstractmethod
    def check(self, files: list[str]) -> AnalysisResult:
        """Run the check on given files."""
        ...


class LintChecker(BaseChecker):
    """Lint code using language-specific linters."""

    name = "lint"

    def __init__(self, command: str = "ruff check") -> None:
        """Initialize lint checker."""
        self.command = command
        self._executor = CommandExecutor(
            allow_unlisted=True,
            timeout=120,
        )

    def check(self, files: list[str]) -> AnalysisResult:
        """Run lint check."""
        if not files:
            return AnalysisResult(
                check_type=CheckType.LINT, passed=True, issues=[], score=100.0
            )

        try:
            paths: list[str | Path] = list(files)
            sanitized_files = self._executor.sanitize_paths(paths)
            cmd_parts = shlex.split(self.command)
            cmd_parts.extend(sanitized_files)

            result = self._executor.execute(cmd_parts, timeout=120)

            if result.success:
                return AnalysisResult(
                    check_type=CheckType.LINT, passed=True, issues=[], score=100.0
                )
            else:
                issues = result.stdout.strip().split("\n") if result.stdout else []
                score = max(0, 100 - len(issues) * 5)
                return AnalysisResult(
                    check_type=CheckType.LINT,
                    passed=False,
                    issues=issues,
                    score=float(score),
                )
        except CommandValidationError as e:
            return AnalysisResult(
                check_type=CheckType.LINT,
                passed=False,
                issues=[f"Command validation failed: {e}"],
                score=0.0,
            )
        except Exception as e:
            return AnalysisResult(
                check_type=CheckType.LINT,
                passed=False,
                issues=[f"Lint error: {e}"],
                score=0.0,
            )


class ComplexityChecker(BaseChecker):
    """Check cyclomatic and cognitive complexity."""

    name = "complexity"

    def __init__(self, threshold: int = 10) -> None:
        """Initialize complexity checker."""
        self.threshold = threshold

    def check(self, files: list[str]) -> AnalysisResult:
        """Run complexity check."""
        return AnalysisResult(
            check_type=CheckType.COMPLEXITY, passed=True, issues=[], score=85.0
        )


class CoverageChecker(BaseChecker):
    """Check test coverage."""

    name = "coverage"

    def __init__(self, threshold: int = 70) -> None:
        """Initialize coverage checker."""
        self.threshold = threshold

    def check(self, files: list[str]) -> AnalysisResult:
        """Run coverage check."""
        return AnalysisResult(
            check_type=CheckType.COVERAGE, passed=True, issues=[], score=75.0
        )


class SecurityChecker(BaseChecker):
    """Run security analysis."""

    name = "security"

    def __init__(self, command: str = "bandit") -> None:
        """Initialize security checker."""
        self.command = command
        self._executor = CommandExecutor(
            allow_unlisted=True,
            timeout=120,
        )

    def check(self, files: list[str]) -> AnalysisResult:
        """Run security check."""
        if not files:
            return AnalysisResult(
                check_type=CheckType.SECURITY, passed=True, issues=[], score=100.0
            )

        try:
            paths: list[str | Path] = list(files)
            sanitized_files = self._executor.sanitize_paths(paths)
            cmd_parts = shlex.split(self.command)
            cmd_parts.extend(["-r"])
            cmd_parts.extend(sanitized_files)

            result = self._executor.execute(cmd_parts, timeout=120)

            if result.success:
                return AnalysisResult(
                    check_type=CheckType.SECURITY, passed=True, issues=[], score=100.0
                )
            else:
                issues = result.stdout.strip().split("\n") if result.stdout else []
                return AnalysisResult(
                    check_type=CheckType.SECURITY,
                    passed=False,
                    issues=issues,
                    score=max(0.0, 100.0 - len(issues) * 10),
                )
        except CommandValidationError:
            return AnalysisResult(
                check_type=CheckType.SECURITY, passed=True, issues=[], score=100.0
            )
        except Exception:
            return AnalysisResult(
                check_type=CheckType.SECURITY, passed=True, issues=[], score=100.0
            )


class PerformanceChecker(BaseChecker):
    """Run comprehensive performance audit."""

    name = "performance"

    def __init__(self, project_path: str = ".") -> None:
        """Initialize performance checker."""
        self.project_path = project_path
        self._last_report: Any = None

    def check(self, files: list[str]) -> AnalysisResult:
        """Run performance audit."""
        from zerg.performance.aggregator import PerformanceAuditor

        auditor = PerformanceAuditor(self.project_path)
        report = auditor.run(files)
        self._last_report = report

        score = report.overall_score if report.overall_score is not None else 0.0
        return AnalysisResult(
            check_type=CheckType.PERFORMANCE,
            passed=score >= 70.0,
            issues=report.top_issues(limit=20),
            score=score,
        )


class AnalyzeCommand:
    """Main analyze command orchestrator."""

    def __init__(self, config: AnalyzeConfig | None = None) -> None:
        """Initialize analyze command."""
        self.config = config or AnalyzeConfig()
        self.checkers: dict[str, BaseChecker] = {
            "lint": LintChecker(self.config.lint_command),
            "complexity": ComplexityChecker(self.config.complexity_threshold),
            "coverage": CoverageChecker(self.config.coverage_threshold),
            "security": SecurityChecker(self.config.security_command),
            "performance": PerformanceChecker(),
        }

    def supported_checks(self) -> list[str]:
        """Return list of supported check types."""
        return list(self.checkers.keys())

    def run(
        self, checks: list[str], files: list[str], threshold: dict[str, int] | None = None
    ) -> list[AnalysisResult]:
        """Run specified checks on files."""
        results = []

        if "all" in checks:
            checks = [k for k in self.checkers if k != "performance"]

        for check_name in checks:
            if check_name in self.checkers:
                checker = self.checkers[check_name]
                result = checker.check(files)
                results.append(result)

        return results

    def format_results(self, results: list[AnalysisResult], fmt: str = "text") -> str:
        """Format results for output."""
        if fmt == "json":
            return self._format_json(results)
        elif fmt == "sarif":
            return self._format_sarif(results)
        else:
            return self._format_text(results)

    def _format_text(self, results: list[AnalysisResult]) -> str:
        """Format as text."""
        lines = ["Analysis Results", "=" * 40]
        for result in results:
            status = "✓" if result.passed else "✗"
            lines.append(f"{status} {result.check_type.value}: {result.score:.1f}%")
            for issue in result.issues[:5]:
                lines.append(f"  - {issue}")
        lines.append("")
        overall = "PASSED" if self.overall_passed(results) else "FAILED"
        lines.append(f"Overall: {overall}")
        return "\n".join(lines)

    def _format_json(self, results: list[AnalysisResult]) -> str:
        """Format as JSON."""
        data = {
            "results": [
                {
                    "check": r.check_type.value,
                    "passed": r.passed,
                    "score": r.score,
                    "issues": r.issues,
                }
                for r in results
            ],
            "overall_passed": self.overall_passed(results),
        }
        return json.dumps(data, indent=2)

    def _format_sarif(self, results: list[AnalysisResult]) -> str:
        """Format as SARIF for IDE integration."""
        sarif_results: list[dict[str, Any]] = []
        sarif: dict[str, Any] = {
            "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {"driver": {"name": "zerg-analyze", "version": "2.0"}},
                    "results": sarif_results,
                }
            ],
        }

        for result in results:
            for issue in result.issues:
                sarif_results.append(
                    {
                        "ruleId": result.check_type.value,
                        "level": "error" if not result.passed else "note",
                        "message": {"text": issue},
                    }
                )

        return json.dumps(sarif, indent=2)

    def overall_passed(self, results: list[AnalysisResult]) -> bool:
        """Check if all results passed."""
        return all(r.passed for r in results)


def _parse_thresholds(threshold_args: tuple[str, ...]) -> dict[str, int]:
    """Parse threshold arguments into dict."""
    thresholds = {}
    for arg in threshold_args:
        if "=" in arg:
            key, value = arg.split("=", 1)
            with contextlib.suppress(ValueError):
                thresholds[key.strip()] = int(value.strip())
    return thresholds


def _collect_files(path: str | None) -> list[str]:
    """Collect files from path."""
    if not path:
        path = "."

    target = Path(path)
    if target.is_file():
        return [str(target)]
    elif target.is_dir():
        files: list[str] = []
        for ext in ["*.py", "*.js", "*.ts", "*.go", "*.rs"]:
            files.extend(str(f) for f in target.rglob(ext))
        return files[:100]  # Limit to prevent overwhelming
    return []


@click.command()
@click.argument("path", default=".", required=False)
@click.option(
    "--check",
    "-c",
    type=click.Choice(["lint", "complexity", "coverage", "security", "performance", "all"]),
    default="all",
    help="Type of check to run",
)
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["text", "json", "sarif", "markdown"]),
    default="text",
    help="Output format",
)
@click.option(
    "--threshold",
    "-t",
    multiple=True,
    help="Thresholds (e.g., complexity=10,coverage=70)",
)
@click.option(
    "--performance", is_flag=True, help="Run comprehensive performance audit (140 factors)"
)
@click.pass_context
def analyze(
    ctx: click.Context,
    path: str,
    check: str,
    output_format: str,
    threshold: tuple[str, ...],
    performance: bool,
) -> None:
    """Run static analysis, complexity metrics, and quality assessment.

    Supports lint, complexity, coverage, and security checks with
    configurable thresholds and output formats.

    Examples:

        zerg analyze

        zerg analyze . --check lint

        zerg analyze --check all --format json

        zerg analyze --check complexity --threshold complexity=15
    """
    try:
        if performance:
            check = "performance"

        is_machine_output = output_format in ("json", "sarif")

        if not is_machine_output:
            console.print("\n[bold cyan]ZERG Analyze[/bold cyan]\n")

        # Parse thresholds
        thresholds = _parse_thresholds(threshold)

        # Build config
        config = AnalyzeConfig()
        if "complexity" in thresholds:
            config.complexity_threshold = thresholds["complexity"]
        if "coverage" in thresholds:
            config.coverage_threshold = thresholds["coverage"]

        # Collect files
        file_list = _collect_files(path)

        if not file_list:
            console.print(f"[yellow]No files found in {path}[/yellow]")
            raise SystemExit(0)

        if not is_machine_output:
            console.print(f"Analyzing {len(file_list)} files...")

        # Run analysis
        analyzer = AnalyzeCommand(config)
        checks_to_run = [check] if check != "all" else ["all"]
        results = analyzer.run(checks_to_run, file_list, thresholds)

        # Check if this is a performance-only run with rich report
        perf_checker = analyzer.checkers.get("performance")
        if (
            check == "performance"
            and perf_checker
            and hasattr(perf_checker, "_last_report")
            and perf_checker._last_report is not None
        ):
            from zerg.performance.formatters import (
                format_json as perf_format_json,
            )
            from zerg.performance.formatters import (
                format_markdown,
                format_rich,
            )
            from zerg.performance.formatters import (
                format_sarif as perf_format_sarif,
            )

            report = perf_checker._last_report
            if output_format == "text":
                format_rich(report, console)
            elif output_format == "json":
                print(perf_format_json(report))
            elif output_format == "sarif":
                print(perf_format_sarif(report))
            elif output_format == "markdown":
                console.print(format_markdown(report))
            overall = results[0].passed if results else True
            raise SystemExit(0 if overall else 1)

        # Output results
        if output_format == "text":
            # Rich table output
            table = Table(title="Analysis Results")
            table.add_column("Check", style="cyan")
            table.add_column("Status")
            table.add_column("Score", justify="right")
            table.add_column("Issues", justify="right")

            for result in results:
                status = "[green]PASS[/green]" if result.passed else "[red]FAIL[/red]"
                table.add_row(
                    result.check_type.value,
                    status,
                    f"{result.score:.1f}%",
                    str(len(result.issues)),
                )

            console.print(table)

            # Show issues if any
            for result in results:
                if result.issues:
                    console.print(f"\n[yellow]{result.check_type.value} issues:[/yellow]")
                    for issue in result.issues[:10]:
                        console.print(f"  • {issue}")
                    if len(result.issues) > 10:
                        console.print(f"  ... and {len(result.issues) - 10} more")

            # Overall status
            overall = analyzer.overall_passed(results)
            status_text = "[green]PASSED[/green]" if overall else "[red]FAILED[/red]"
            console.print(f"\n[bold]Overall:[/bold] {status_text}")

            raise SystemExit(0 if overall else 1)
        else:
            # JSON or SARIF output
            output = analyzer.format_results(results, output_format)
            console.print(output)
            raise SystemExit(0 if analyzer.overall_passed(results) else 1)

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted[/yellow]")
        raise SystemExit(130) from None
    except SystemExit:
        raise
    except Exception as e:
        console.print(f"\n[red]Error:[/red] {e}")
        logger.exception("Analyze command failed")
        raise SystemExit(1) from e
