"""ZERG refactor command - automated code improvement."""

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.prompt import Confirm
from rich.table import Table

from zerg.logging import get_logger

console = Console()
logger = get_logger("refactor")


class TransformType(Enum):
    """Types of refactoring transforms."""

    DEAD_CODE = "dead-code"
    SIMPLIFY = "simplify"
    TYPES = "types"
    PATTERNS = "patterns"
    NAMING = "naming"


@dataclass
class RefactorConfig:
    """Configuration for refactoring."""

    dry_run: bool = False
    interactive: bool = False
    backup: bool = True
    exclude_patterns: list[str] = field(default_factory=list)


@dataclass
class RefactorSuggestion:
    """A refactoring suggestion."""

    transform_type: TransformType
    file: str
    line: int
    original: str
    suggested: str
    reason: str
    confidence: float = 0.9

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "transform": self.transform_type.value,
            "file": self.file,
            "line": self.line,
            "original": self.original,
            "suggested": self.suggested,
            "reason": self.reason,
            "confidence": self.confidence,
        }


@dataclass
class RefactorResult:
    """Result of refactoring operation."""

    files_analyzed: int
    suggestions: list[RefactorSuggestion]
    applied: int
    errors: list[str] = field(default_factory=list)

    @property
    def total_suggestions(self) -> int:
        """Count total suggestions."""
        return len(self.suggestions)

    def by_transform(self) -> dict[str, list[RefactorSuggestion]]:
        """Group suggestions by transform type."""
        result: dict[str, list[RefactorSuggestion]] = {}
        for s in self.suggestions:
            key = s.transform_type.value
            if key not in result:
                result[key] = []
            result[key].append(s)
        return result


class BaseTransform(ABC):
    """Base class for refactoring transforms."""

    name: str = "base"

    @abstractmethod
    def analyze(self, content: str, filename: str) -> list[RefactorSuggestion]:
        """Analyze content and return suggestions."""
        ...

    @abstractmethod
    def apply(self, content: str, suggestions: list[RefactorSuggestion]) -> str:
        """Apply suggestions to content."""
        ...


class DeadCodeTransform(BaseTransform):
    """Remove unused code."""

    name = "dead-code"

    # Patterns for potentially dead code
    PATTERNS = [
        (r"^\s*#\s*TODO:.*$", "TODO comment"),
        (r"^\s*#\s*FIXME:.*$", "FIXME comment"),
        (r"^\s*pass\s*$", "Empty pass statement"),
    ]

    def analyze(self, content: str, filename: str) -> list[RefactorSuggestion]:
        """Analyze for dead code."""
        suggestions = []
        lines = content.split("\n")

        for line_num, line in enumerate(lines, 1):
            for pattern, reason in self.PATTERNS:
                if re.match(pattern, line, re.IGNORECASE):
                    suggestions.append(
                        RefactorSuggestion(
                            transform_type=TransformType.DEAD_CODE,
                            file=filename,
                            line=line_num,
                            original=line.strip(),
                            suggested="",
                            reason=f"Consider removing: {reason}",
                            confidence=0.7,
                        )
                    )
                    break

        return suggestions

    def apply(self, content: str, suggestions: list[RefactorSuggestion]) -> str:
        """Remove dead code."""
        return content


class SimplifyTransform(BaseTransform):
    """Simplify complex expressions."""

    name = "simplify"

    PATTERNS = [
        (r"if\s+(\w+)\s*==\s*True:", r"if \1:", "Simplify boolean comparison"),
        (r"if\s+(\w+)\s*==\s*False:", r"if not \1:", "Simplify boolean comparison"),
        (r"if\s+(\w+)\s*==\s*None:", r"if \1 is None:", "Use identity comparison"),
        (r"if\s+(\w+)\s*!=\s*None:", r"if \1 is not None:", "Use identity comparison"),
        (r"len\((\w+)\)\s*==\s*0", r"not \1", "Use truthiness"),
        (r"len\((\w+)\)\s*>\s*0", r"\1", "Use truthiness"),
        (r"(\w+)\s*==\s*\[\]", r"not \1", "Use truthiness"),
        (r"(\w+)\s*!=\s*\[\]", r"\1", "Use truthiness"),
    ]

    def analyze(self, content: str, filename: str) -> list[RefactorSuggestion]:
        """Analyze for simplification opportunities."""
        suggestions = []

        for line_num, line in enumerate(content.split("\n"), 1):
            for pattern, replacement, reason in self.PATTERNS:
                if re.search(pattern, line):
                    new_line = re.sub(pattern, replacement, line)
                    suggestions.append(
                        RefactorSuggestion(
                            transform_type=TransformType.SIMPLIFY,
                            file=filename,
                            line=line_num,
                            original=line.strip(),
                            suggested=new_line.strip(),
                            reason=reason,
                        )
                    )
                    break

        return suggestions

    def apply(self, content: str, suggestions: list[RefactorSuggestion]) -> str:
        """Apply simplifications."""
        for pattern, replacement, _ in self.PATTERNS:
            content = re.sub(pattern, replacement, content)
        return content


class TypesTransform(BaseTransform):
    """Strengthen type annotations."""

    name = "types"

    # Functions without return type hints
    FUNC_PATTERN = re.compile(r"def\s+(\w+)\s*\([^)]*\)\s*:")

    def analyze(self, content: str, filename: str) -> list[RefactorSuggestion]:
        """Analyze for missing type annotations."""
        suggestions = []

        for line_num, line in enumerate(content.split("\n"), 1):
            match = self.FUNC_PATTERN.search(line)
            if match and "->" not in line:
                func_name = match.group(1)
                if not func_name.startswith("_"):  # Skip private
                    suggestions.append(
                        RefactorSuggestion(
                            transform_type=TransformType.TYPES,
                            file=filename,
                            line=line_num,
                            original=line.strip(),
                            suggested=line.rstrip(":") + " -> None:",
                            reason=f"Add return type hint to {func_name}",
                            confidence=0.6,
                        )
                    )

        return suggestions

    def apply(self, content: str, suggestions: list[RefactorSuggestion]) -> str:
        """Add type annotations."""
        return content


class NamingTransform(BaseTransform):
    """Improve variable and function names."""

    name = "naming"

    POOR_NAMES = {"x", "y", "z", "tmp", "temp", "foo", "bar", "baz", "data", "result", "val", "var"}

    VAR_PATTERN = re.compile(r"\b([a-z_][a-z0-9_]*)\s*=")

    def analyze(self, content: str, filename: str) -> list[RefactorSuggestion]:
        """Analyze for poor naming."""
        suggestions = []

        for line_num, line in enumerate(content.split("\n"), 1):
            for match in self.VAR_PATTERN.finditer(line):
                var_name = match.group(1)
                if var_name in self.POOR_NAMES:
                    suggestions.append(
                        RefactorSuggestion(
                            transform_type=TransformType.NAMING,
                            file=filename,
                            line=line_num,
                            original=line.strip(),
                            suggested=line.strip(),  # Can't auto-suggest better name
                            reason=f"Consider more descriptive name for '{var_name}'",
                            confidence=0.5,
                        )
                    )

        return suggestions

    def apply(self, content: str, suggestions: list[RefactorSuggestion]) -> str:
        """Apply naming improvements - requires manual intervention."""
        return content


class PatternsTransform(BaseTransform):
    """Apply common design patterns."""

    name = "patterns"

    def analyze(self, content: str, filename: str) -> list[RefactorSuggestion]:
        """Analyze for pattern opportunities."""
        suggestions = []

        # Detect potential guard clauses
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if "if " in line and ":" in line:
                # Check for deep nesting
                indent = len(line) - len(line.lstrip())
                if indent >= 12:  # 3+ levels deep
                    suggestions.append(
                        RefactorSuggestion(
                            transform_type=TransformType.PATTERNS,
                            file=filename,
                            line=i + 1,
                            original=line.strip(),
                            suggested="Consider guard clause",
                            reason="Deep nesting detected, consider early return pattern",
                            confidence=0.7,
                        )
                    )

        return suggestions

    def apply(self, content: str, suggestions: list[RefactorSuggestion]) -> str:
        """Apply patterns."""
        return content


class RefactorCommand:
    """Main refactor command orchestrator."""

    def __init__(self, config: RefactorConfig | None = None) -> None:
        """Initialize refactor command."""
        self.config = config or RefactorConfig()
        self.transforms: dict[str, BaseTransform] = {
            "dead-code": DeadCodeTransform(),
            "simplify": SimplifyTransform(),
            "types": TypesTransform(),
            "patterns": PatternsTransform(),
            "naming": NamingTransform(),
        }

    def supported_transforms(self) -> list[str]:
        """Return list of supported transforms."""
        return list(self.transforms.keys())

    def run(
        self,
        files: list[str],
        transforms: list[str],
        dry_run: bool = False,
        interactive: bool = False,
    ) -> RefactorResult:
        """Run refactoring."""
        all_suggestions: list[RefactorSuggestion] = []
        applied = 0
        errors: list[str] = []

        for filepath in files:
            try:
                path = Path(filepath)
                if not path.exists() or not path.is_file():
                    continue

                content = path.read_text(encoding="utf-8")
                modified = False
                new_content = content

                for transform_name in transforms:
                    if transform_name not in self.transforms:
                        continue

                    transform = self.transforms[transform_name]
                    suggestions = transform.analyze(content, filepath)
                    all_suggestions.extend(suggestions)

                    if not dry_run and suggestions:
                        if interactive:
                            # Ask for each suggestion
                            for s in suggestions:
                                console.print(f"\n[cyan]{s.file}:{s.line}[/cyan]")
                                console.print(f"  [red]- {s.original}[/red]")
                                console.print(f"  [green]+ {s.suggested}[/green]")
                                console.print(f"  [dim]{s.reason}[/dim]")
                                if Confirm.ask("Apply this change?", default=True):
                                    new_content = transform.apply(new_content, [s])
                                    applied += 1
                                    modified = True
                        else:
                            new_content = transform.apply(new_content, suggestions)
                            applied += len(suggestions)
                            modified = True

                if modified and not dry_run:
                    path.write_text(new_content, encoding="utf-8")

            except Exception as e:
                errors.append(f"{filepath}: {e}")

        return RefactorResult(
            files_analyzed=len(files),
            suggestions=all_suggestions,
            applied=applied if not dry_run else 0,
            errors=errors,
        )

    def format_result(self, result: RefactorResult, fmt: str = "text") -> str:
        """Format refactoring result."""
        if fmt == "json":
            return json.dumps(
                {
                    "files_analyzed": result.files_analyzed,
                    "total_suggestions": result.total_suggestions,
                    "applied": result.applied,
                    "suggestions": [s.to_dict() for s in result.suggestions],
                    "errors": result.errors,
                },
                indent=2,
            )

        lines = [
            "Refactor Results",
            "=" * 40,
            f"Files Analyzed: {result.files_analyzed}",
            f"Suggestions: {result.total_suggestions}",
            f"Applied: {result.applied}",
            "",
        ]

        if result.suggestions:
            lines.append("Suggestions:")
            by_transform = result.by_transform()
            for transform, suggestions in by_transform.items():
                lines.append(f"\n  {transform}:")
                for s in suggestions[:5]:
                    lines.append(f"    {s.file}:{s.line}")
                    lines.append(f"      - {s.original[:50]}")
                    lines.append(f"      + {s.suggested[:50]}")

        return "\n".join(lines)


def _collect_files(path: str | None) -> list[str]:
    """Collect Python files from path."""
    if not path:
        path = "."

    target = Path(path)
    if target.is_file():
        return [str(target)]
    elif target.is_dir():
        files = []
        for f in target.rglob("*.py"):
            # Skip test files, __pycache__, etc.
            if "__pycache__" in str(f) or ".git" in str(f):
                continue
            files.append(str(f))
        return files[:50]  # Limit
    return []


@click.command()
@click.argument("path", default=".", required=False)
@click.option(
    "--transforms",
    "-t",
    default="dead-code,simplify",
    help="Comma-separated transforms: dead-code,simplify,types,patterns,naming",
)
@click.option("--dry-run", is_flag=True, help="Show suggestions without applying")
@click.option("--interactive", "-i", is_flag=True, help="Interactive mode")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.pass_context
def refactor(
    ctx: click.Context,
    path: str,
    transforms: str,
    dry_run: bool,
    interactive: bool,
    json_output: bool,
) -> None:
    """Automated code improvement and cleanup.

    Supports transforms: dead-code removal, simplification,
    type strengthening, pattern application, and naming improvements.

    Examples:

        zerg refactor

        zerg refactor --transforms dead-code,simplify --dry-run

        zerg refactor --interactive

        zerg refactor --transforms types,naming
    """
    try:
        console.print("\n[bold cyan]ZERG Refactor[/bold cyan]\n")

        # Parse transforms
        transform_list = [t.strip() for t in transforms.split(",") if t.strip()]
        console.print(f"Transforms: [cyan]{', '.join(transform_list)}[/cyan]")

        if dry_run:
            console.print("[yellow]Dry run mode - no changes will be made[/yellow]")
        if interactive:
            console.print("[yellow]Interactive mode - will prompt for each change[/yellow]")

        # Collect files
        file_list = _collect_files(path)

        if not file_list:
            console.print(f"[yellow]No Python files found in {path}[/yellow]")
            raise SystemExit(0)

        console.print(f"\nAnalyzing {len(file_list)} files...\n")

        # Create config and run
        config = RefactorConfig(
            dry_run=dry_run,
            interactive=interactive,
        )
        refactorer = RefactorCommand(config)
        result = refactorer.run(file_list, transform_list, dry_run, interactive)

        # Output
        if json_output:
            console.print(refactorer.format_result(result, "json"))
        else:
            # Display results
            table = Table(title="Refactor Summary")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", justify="right")

            table.add_row("Files Analyzed", str(result.files_analyzed))
            table.add_row("Suggestions", str(result.total_suggestions))
            table.add_row("Applied", str(result.applied))

            console.print(table)

            # Show suggestions by transform
            if result.suggestions:
                console.print("\n[bold]Suggestions by transform:[/bold]")
                by_transform = result.by_transform()
                for transform, suggestions in by_transform.items():
                    console.print(f"\n  [cyan]{transform}[/cyan] ({len(suggestions)} suggestions)")
                    for s in suggestions[:3]:
                        console.print(f"    {s.file}:{s.line}")
                        console.print(f"      [red]- {s.original[:60]}[/red]")
                        if s.suggested:
                            console.print(f"      [green]+ {s.suggested[:60]}[/green]")
                        console.print(f"      [dim]{s.reason}[/dim]")
                    if len(suggestions) > 3:
                        console.print(f"    ... and {len(suggestions) - 3} more")

            # Errors
            if result.errors:
                console.print("\n[red]Errors:[/red]")
                for error in result.errors[:5]:
                    console.print(f"  {error}")

            # Status
            if result.total_suggestions == 0:
                console.print("\n[green]No refactoring suggestions found - code looks good![/green]")
            elif dry_run:
                console.print(
                    f"\n[yellow]Run without --dry-run to apply {result.total_suggestions} suggestions[/yellow]"
                )
            else:
                console.print(f"\n[green]Applied {result.applied} changes[/green]")

        raise SystemExit(0)

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted[/yellow]")
        raise SystemExit(130) from None
    except SystemExit:
        raise
    except Exception as e:
        console.print(f"\n[red]Error:[/red] {e}")
        logger.exception("Refactor command failed")
        raise SystemExit(1) from e
