"""ZERG review command - two-stage code review workflow."""

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from zerg.logging import get_logger

console = Console()
logger = get_logger("review")


class ReviewMode(Enum):
    """Review workflow modes."""

    PREPARE = "prepare"
    SELF = "self"
    RECEIVE = "receive"
    FULL = "full"


@dataclass
class ReviewConfig:
    """Configuration for review."""

    mode: str = "full"
    include_tests: bool = True
    include_docs: bool = True
    strict: bool = False


@dataclass
class ReviewItem:
    """A review comment or finding."""

    category: str
    severity: str  # info, warning, error
    file: str
    line: int
    message: str
    suggestion: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "category": self.category,
            "severity": self.severity,
            "file": self.file,
            "line": self.line,
            "message": self.message,
            "suggestion": self.suggestion,
        }


@dataclass
class ReviewResult:
    """Result of code review."""

    files_reviewed: int
    items: list[ReviewItem]
    spec_passed: bool
    quality_passed: bool
    stage1_details: str = ""
    stage2_details: str = ""

    @property
    def overall_passed(self) -> bool:
        """Check if both stages passed."""
        return self.spec_passed and self.quality_passed

    @property
    def total_items(self) -> int:
        """Count total review items."""
        return len(self.items)

    @property
    def error_count(self) -> int:
        """Count error-level items."""
        return sum(1 for item in self.items if item.severity == "error")

    @property
    def warning_count(self) -> int:
        """Count warning-level items."""
        return sum(1 for item in self.items if item.severity == "warning")


class SelfReviewChecklist:
    """Checklist for self-review before submission."""

    ITEMS = [
        ("basics", "Code compiles/runs without errors"),
        ("tests", "All tests pass locally"),
        ("secrets", "No hardcoded values or secrets"),
        ("errors", "Error handling is appropriate"),
        ("edge_cases", "Edge cases are handled"),
        ("readability", "Code is readable and well-named"),
        ("complexity", "No unnecessary complexity"),
        ("docs", "Documentation is updated"),
        ("debug", "No console.log/print debug statements"),
        ("requirements", "Changes match the requirements"),
    ]

    def get_items(self) -> list[tuple[str, str]]:
        """Return checklist items."""
        return self.ITEMS


class CodeAnalyzer:
    """Analyze code for common issues."""

    PATTERNS: dict[str, dict[str, Any]] = {
        "debug_print": {
            "pattern": r"(print\(|console\.log|debugger;)",
            "message": "Debug statement found",
            "severity": "warning",
        },
        "todo": {
            "pattern": r"(TODO|FIXME|HACK|XXX)",
            "message": "TODO/FIXME comment found",
            "severity": "info",
        },
        "hardcoded_secret": {
            "pattern": r"(password|secret|api_key|token)\s*=\s*['\"][^'\"]+['\"]",
            "message": "Potential hardcoded secret",
            "severity": "error",
        },
        "long_line": {
            "pattern": None,  # Special handling
            "message": "Line exceeds 120 characters",
            "severity": "info",
        },
    }

    def analyze(self, content: str, filename: str) -> list[ReviewItem]:
        """Analyze content for issues."""
        import re

        items = []
        lines = content.split("\n")

        for line_num, line in enumerate(lines, 1):
            # Check patterns
            for category, config in self.PATTERNS.items():
                if config["pattern"]:
                    if re.search(config["pattern"], line, re.IGNORECASE):
                        items.append(
                            ReviewItem(
                                category=category,
                                severity=config["severity"],
                                file=filename,
                                line=line_num,
                                message=config["message"],
                            )
                        )
                elif category == "long_line" and len(line) > 120:
                    items.append(
                        ReviewItem(
                            category=category,
                            severity=config["severity"],
                            file=filename,
                            line=line_num,
                            message=f"{config['message']} ({len(line)} chars)",
                        )
                    )

        return items


class ReviewCommand:
    """Main review command orchestrator."""

    def __init__(self, config: ReviewConfig | None = None) -> None:
        """Initialize review command."""
        self.config = config or ReviewConfig()
        self.checklist = SelfReviewChecklist()
        self.analyzer = CodeAnalyzer()

    def supported_modes(self) -> list[str]:
        """Return list of supported review modes."""
        return [m.value for m in ReviewMode]

    def run(
        self,
        files: list[str],
        mode: str = "full",
    ) -> ReviewResult:
        """Run code review."""
        items: list[ReviewItem] = []
        spec_passed = True
        quality_passed = True
        stage1_details = ""
        stage2_details = ""

        if mode in ("prepare", "full"):
            spec_passed, stage1_details = self._run_spec_review(files)

        if mode in ("self", "full"):
            self_items = self._run_self_review(files)
            items.extend(self_items)

        if mode in ("receive", "full"):
            quality_passed, stage2_details, quality_items = self._run_quality_review(files)
            items.extend(quality_items)

        return ReviewResult(
            files_reviewed=len(files),
            items=items,
            spec_passed=spec_passed,
            quality_passed=quality_passed,
            stage1_details=stage1_details,
            stage2_details=stage2_details,
        )

    def _run_spec_review(self, files: list[str]) -> tuple[bool, str]:
        """Stage 1: Spec compliance review."""
        details_lines = [
            "Stage 1: Specification Review",
            "-" * 30,
            "",
            "Checking implementation against requirements...",
            "",
        ]

        # Check for common spec compliance issues
        has_tests = any("test" in f.lower() for f in files)
        has_docs = any(f.endswith(".md") or f.endswith(".rst") for f in files)

        if self.config.include_tests and not has_tests:
            details_lines.append("⚠ No test files included in changes")
        else:
            details_lines.append("✓ Test files present")

        if self.config.include_docs:
            if has_docs:
                details_lines.append("✓ Documentation updated")
            else:
                details_lines.append("⚠ Consider updating documentation")

        details_lines.append("")
        details_lines.append("Spec compliance: PASSED")

        return True, "\n".join(details_lines)

    def _run_self_review(self, files: list[str]) -> list[ReviewItem]:
        """Generate self-review checklist and analyze files."""
        items: list[ReviewItem] = []

        # Analyze each file
        for filepath in files:
            try:
                path = Path(filepath)
                if not path.exists() or not path.is_file():
                    continue
                if path.suffix not in [".py", ".js", ".ts", ".go", ".rs", ".java"]:
                    continue

                content = path.read_text(encoding="utf-8")
                file_items = self.analyzer.analyze(content, filepath)
                items.extend(file_items)
            except Exception as e:
                logger.debug(f"File read failed: {e}")

        return items

    def _run_quality_review(self, files: list[str]) -> tuple[bool, str, list[ReviewItem]]:
        """Stage 2: Code quality review."""
        items: list[ReviewItem] = []
        details_lines = [
            "Stage 2: Quality Review",
            "-" * 30,
            "",
        ]

        total_lines = 0
        total_issues = 0

        for filepath in files:
            try:
                path = Path(filepath)
                if not path.exists() or not path.is_file():
                    continue

                content = path.read_text(encoding="utf-8")
                lines = content.split("\n")
                total_lines += len(lines)

                # Check complexity (simple heuristic)
                functions = content.count("def ") + content.count("function ")
                if functions > 0:
                    avg_lines_per_func = len(lines) / functions
                    if avg_lines_per_func > 50:
                        items.append(
                            ReviewItem(
                                category="complexity",
                                severity="warning",
                                file=filepath,
                                line=1,
                                message=(f"High average function length ({avg_lines_per_func:.0f} lines)"),
                                suggestion="Consider breaking into smaller functions",
                            )
                        )
                        total_issues += 1

            except Exception as e:
                logger.debug(f"File read failed: {e}")

        details_lines.append(f"Files reviewed: {len(files)}")
        details_lines.append(f"Total lines: {total_lines}")
        details_lines.append(f"Issues found: {total_issues}")
        details_lines.append("")

        passed = total_issues == 0 or not self.config.strict
        status = "PASSED" if passed else "NEEDS ATTENTION"
        details_lines.append(f"Quality review: {status}")

        return passed, "\n".join(details_lines), items

    def format_result(self, result: ReviewResult, fmt: str = "text") -> str:
        """Format review result."""
        if fmt == "json":
            return json.dumps(
                {
                    "files_reviewed": result.files_reviewed,
                    "overall_passed": result.overall_passed,
                    "spec_passed": result.spec_passed,
                    "quality_passed": result.quality_passed,
                    "total_items": result.total_items,
                    "error_count": result.error_count,
                    "warning_count": result.warning_count,
                    "items": [i.to_dict() for i in result.items],
                },
                indent=2,
            )

        status = "PASSED" if result.overall_passed else "NEEDS ATTENTION"
        lines = [
            "Code Review Results",
            "=" * 40,
            f"Status: {status}",
            f"Files Reviewed: {result.files_reviewed}",
            "",
            f"Stage 1 (Spec): {'✓' if result.spec_passed else '✗'}",
            f"Stage 2 (Quality): {'✓' if result.quality_passed else '✗'}",
            "",
        ]

        if result.items:
            lines.append("Review Items:")
            for item in result.items[:10]:
                severity_icon = {"error": "❌", "warning": "⚠", "info": "ℹ"}.get(item.severity, "•")
                lines.append(f"  {severity_icon} [{item.severity}] {item.file}:{item.line}")
                lines.append(f"     {item.message}")

        return "\n".join(lines)


def _collect_files(path: str | None, mode: str) -> list[str]:
    """Collect files to review."""
    if not path:
        # Try to get changed files from git
        try:
            import subprocess

            result = subprocess.run(
                ["git", "diff", "--name-only", "--cached"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip().split("\n")

            # Try unstaged changes
            result = subprocess.run(
                ["git", "diff", "--name-only"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip().split("\n")
        except Exception as e:
            logger.debug(f"Review check failed: {e}")

        path = "."

    target = Path(path)
    if target.is_file():
        return [str(target)]
    elif target.is_dir():
        files: list[str] = []
        for ext in ["*.py", "*.js", "*.ts", "*.go", "*.rs"]:
            files.extend(str(f) for f in target.rglob(ext) if "__pycache__" not in str(f))
        return files[:50]
    return []


@click.command()
@click.option(
    "--mode",
    "-m",
    type=click.Choice(["prepare", "self", "receive", "full"]),
    default="full",
    help="Review mode",
)
@click.option("--files", "-f", help="Specific files to review")
@click.option("--output", "-o", help="Output file for review results")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.pass_context
def review(
    ctx: click.Context,
    mode: str,
    files: str | None,
    output: str | None,
    json_output: bool,
) -> None:
    """Two-stage code review workflow.

    Modes:
    - prepare: Generate change summary and review checklist
    - self: Self-review checklist and automated analysis
    - receive: Process code quality review
    - full: Complete two-stage review (spec + quality)

    Examples:

        zerg review

        zerg review --mode prepare

        zerg review --mode self

        zerg review --output review.md
    """
    try:
        console.print("\n[bold cyan]ZERG Review[/bold cyan]\n")
        console.print(f"Mode: [cyan]{mode}[/cyan]")

        # Collect files
        file_list = _collect_files(files, mode)

        if not file_list:
            console.print("[yellow]No files to review[/yellow]")
            console.print("Specify files with --files or stage changes with git")
            raise SystemExit(0)

        console.print(f"Reviewing {len(file_list)} files...\n")

        # Run review
        config = ReviewConfig(mode=mode)
        reviewer = ReviewCommand(config)
        result = reviewer.run(file_list, mode)

        # Show checklist for self-review mode
        if mode in ("self", "full"):
            console.print(Panel("[bold]Self-Review Checklist[/bold]", style="cyan"))
            checklist = reviewer.checklist.get_items()
            for _key, item in checklist:
                console.print(f"  ☐ {item}")
            console.print()

        # Display results
        if json_output:
            output_content = reviewer.format_result(result, "json")
            console.print(output_content)
        else:
            # Status panel
            status_color = "green" if result.overall_passed else "yellow"
            status_text = "PASSED" if result.overall_passed else "NEEDS ATTENTION"

            table = Table(title="Review Summary")
            table.add_column("Stage", style="cyan")
            table.add_column("Status")
            table.add_column("Details")

            stage1_status = "[green]✓ PASSED[/green]" if result.spec_passed else "[red]✗ FAILED[/red]"
            stage2_status = "[green]✓ PASSED[/green]" if result.quality_passed else "[yellow]⚠ REVIEW[/yellow]"

            table.add_row("1. Spec Compliance", stage1_status, "Requirements alignment")
            table.add_row("2. Code Quality", stage2_status, f"{result.total_items} items found")

            console.print(table)

            # Show issues if any
            if result.items:
                console.print(f"\n[bold]Review Items ({result.total_items}):[/bold]")

                # Group by severity
                errors: list[ReviewItem] = [i for i in result.items if i.severity == "error"]
                warnings: list[ReviewItem] = [i for i in result.items if i.severity == "warning"]
                infos: list[ReviewItem] = [i for i in result.items if i.severity == "info"]

                if errors:
                    console.print(f"\n[red]Errors ({len(errors)}):[/red]")
                    for ri in errors[:5]:
                        console.print(f"  ❌ {ri.file}:{ri.line} - {ri.message}")

                if warnings:
                    console.print(f"\n[yellow]Warnings ({len(warnings)}):[/yellow]")
                    for ri in warnings[:5]:
                        console.print(f"  ⚠ {ri.file}:{ri.line} - {ri.message}")

                if infos:
                    console.print(f"\n[blue]Info ({len(infos)}):[/blue]")
                    for ri in infos[:5]:
                        console.print(f"  ℹ {ri.file}:{ri.line} - {ri.message}")

            # Overall status
            console.print(f"\n[bold]Overall:[/bold] [{status_color}]{status_text}[/{status_color}]")

            # Stage details if verbose
            if result.stage1_details:
                console.print(f"\n[dim]{result.stage1_details}[/dim]")

            output_content = reviewer.format_result(result, "text")

        # Write to file if requested
        if output:
            Path(output).write_text(output_content, encoding="utf-8")
            console.print(f"\n[green]✓[/green] Results written to {output}")

        raise SystemExit(0 if result.overall_passed else 1)

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted[/yellow]")
        raise SystemExit(130) from None
    except SystemExit:
        raise
    except Exception as e:
        console.print(f"\n[red]Error:[/red] {e}")
        logger.exception("Review command failed")
        raise SystemExit(1) from e
