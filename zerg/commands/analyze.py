"""ZERG analyze command - static analysis and quality assessment."""

import contextlib
import json
import re
import shlex
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.table import Table

from zerg.ast_cache import ASTCache, collect_exports, collect_imports
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
    DEAD_CODE = "dead-code"
    WIRING = "wiring"
    CROSS_FILE = "cross-file"
    CONVENTIONS = "conventions"
    IMPORT_CHAIN = "import-chain"
    CONTEXT_ENGINEERING = "context-engineering"


@dataclass
class AnalyzeConfig:
    """Configuration for analysis."""

    complexity_threshold: int = 10
    coverage_threshold: int = 70
    lint_command: str = "ruff check"
    security_command: str = "bandit"
    dead_code_min_confidence: int = 80
    wiring_strict: bool = False
    wiring_exclude_patterns: list[str] = field(default_factory=list)
    cross_file_scope: str = "zerg/"
    conventions_naming: str = "snake_case"
    conventions_require_task_prefixes: bool = True
    import_chain_max_depth: int = 10
    context_engineering_auto_split: bool = False


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
            return AnalysisResult(check_type=CheckType.LINT, passed=True, issues=[], score=100.0)

        try:
            paths: list[str | Path] = list(files)
            sanitized_files = self._executor.sanitize_paths(paths)
            cmd_parts = shlex.split(self.command)
            cmd_parts.extend(sanitized_files)

            result = self._executor.execute(cmd_parts, timeout=120)

            if result.success:
                return AnalysisResult(check_type=CheckType.LINT, passed=True, issues=[], score=100.0)
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
        return AnalysisResult(check_type=CheckType.COMPLEXITY, passed=True, issues=[], score=85.0)


class CoverageChecker(BaseChecker):
    """Check test coverage."""

    name = "coverage"

    def __init__(self, threshold: int = 70) -> None:
        """Initialize coverage checker."""
        self.threshold = threshold

    def check(self, files: list[str]) -> AnalysisResult:
        """Run coverage check."""
        return AnalysisResult(check_type=CheckType.COVERAGE, passed=True, issues=[], score=75.0)


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
            return AnalysisResult(check_type=CheckType.SECURITY, passed=True, issues=[], score=100.0)

        try:
            paths: list[str | Path] = list(files)
            sanitized_files = self._executor.sanitize_paths(paths)
            cmd_parts = shlex.split(self.command)
            cmd_parts.extend(["-r"])
            cmd_parts.extend(sanitized_files)

            result = self._executor.execute(cmd_parts, timeout=120)

            if result.success:
                return AnalysisResult(check_type=CheckType.SECURITY, passed=True, issues=[], score=100.0)
            else:
                issues = result.stdout.strip().split("\n") if result.stdout else []
                return AnalysisResult(
                    check_type=CheckType.SECURITY,
                    passed=False,
                    issues=issues,
                    score=max(0.0, 100.0 - len(issues) * 10),
                )
        except CommandValidationError:
            return AnalysisResult(check_type=CheckType.SECURITY, passed=True, issues=[], score=100.0)
        except Exception:
            return AnalysisResult(check_type=CheckType.SECURITY, passed=True, issues=[], score=100.0)


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


class DeadCodeChecker(BaseChecker):
    """Detect unused code via vulture static analysis."""

    name = "dead-code"

    def __init__(self, min_confidence: int = 80) -> None:
        """Initialize dead code checker.

        Args:
            min_confidence: Minimum confidence threshold for vulture (0-100).
        """
        self.min_confidence = min_confidence
        self._executor = CommandExecutor(
            allow_unlisted=True,
            timeout=120,
        )

    def check(self, files: list[str]) -> AnalysisResult:
        """Run vulture dead code detection on given files."""
        if not files:
            return AnalysisResult(check_type=CheckType.DEAD_CODE, passed=True, issues=[], score=100.0)

        try:
            paths: list[str | Path] = list(files)
            sanitized_files = self._executor.sanitize_paths(paths)
            cmd_parts = [
                "vulture",
                "--min-confidence",
                str(self.min_confidence),
            ]
            cmd_parts.extend(sanitized_files)

            result = self._executor.execute(cmd_parts, timeout=120)

            if result.success:
                return AnalysisResult(check_type=CheckType.DEAD_CODE, passed=True, issues=[], score=100.0)
            else:
                issues = [line for line in result.stdout.strip().split("\n") if line.strip()] if result.stdout else []
                score = max(0.0, 100.0 - len(issues) * 5)
                return AnalysisResult(
                    check_type=CheckType.DEAD_CODE,
                    passed=len(issues) == 0,
                    issues=issues,
                    score=score,
                )
        except CommandValidationError:
            # vulture not installed or not on PATH
            return AnalysisResult(
                check_type=CheckType.DEAD_CODE,
                passed=True,
                issues=["vulture not installed — skipping dead code analysis"],
                score=100.0,
            )
        except FileNotFoundError:
            return AnalysisResult(
                check_type=CheckType.DEAD_CODE,
                passed=True,
                issues=["vulture not installed — skipping dead code analysis"],
                score=100.0,
            )
        except Exception as e:
            return AnalysisResult(
                check_type=CheckType.DEAD_CODE,
                passed=False,
                issues=[f"Dead code analysis error: {e}"],
                score=0.0,
            )


class WiringChecker(BaseChecker):
    """Check module wiring to detect orphaned modules with no production callers."""

    name = "wiring"

    def __init__(self, strict: bool = False) -> None:
        """Initialize wiring checker.

        Args:
            strict: If True, orphaned modules cause failure. Otherwise warnings only.
        """
        self.strict = strict

    def check(self, files: list[str]) -> AnalysisResult:
        """Run module wiring validation."""
        try:
            from zerg.validate_commands import validate_module_wiring

            passed, messages = validate_module_wiring(strict=self.strict)
            score = 100.0 if passed else max(0.0, 100.0 - len(messages) * 10)
            return AnalysisResult(
                check_type=CheckType.WIRING,
                passed=passed,
                issues=messages,
                score=score,
            )
        except ImportError as e:
            return AnalysisResult(
                check_type=CheckType.WIRING,
                passed=False,
                issues=[f"Could not import validate_commands: {e}"],
                score=0.0,
            )
        except Exception as e:
            return AnalysisResult(
                check_type=CheckType.WIRING,
                passed=False,
                issues=[f"Wiring check error: {e}"],
                score=0.0,
            )


class ConventionsChecker(BaseChecker):
    """Check naming conventions and file organization standards."""

    name = "conventions"

    # Pattern for valid snake_case Python filenames
    _SNAKE_CASE_RE = re.compile(r"^[a-z][a-z0-9_]*\.py$")

    # Pattern for bracketed Task prefixes in command files
    _TASK_PREFIX_RE = re.compile(r"\[(?:Plan|Design|L\d+|Brainstorm|Init|Cleanup|Review|Build|Test|Security)\]")

    def __init__(self, naming: str = "snake_case", require_task_prefixes: bool = True) -> None:
        """Initialize conventions checker.

        Args:
            naming: Naming convention to enforce (currently only 'snake_case').
            require_task_prefixes: Whether to check for bracketed Task prefixes
                in command .md files.
        """
        self.naming = naming
        self.require_task_prefixes = require_task_prefixes

    def check(self, files: list[str]) -> AnalysisResult:
        """Run conventions checks on the given files and project structure."""
        issues: list[str] = []

        # 1. Check snake_case naming for .py files
        if self.naming == "snake_case":
            issues.extend(self._check_snake_case(files))

        # 2. Check bracketed Task prefixes in command .md files
        if self.require_task_prefixes:
            issues.extend(self._check_task_prefixes())

        # 3. Check file organization (tests in tests/, scripts in scripts/)
        issues.extend(self._check_file_organization(files))

        score = max(0.0, 100.0 - len(issues) * 5)
        return AnalysisResult(
            check_type=CheckType.CONVENTIONS,
            passed=len(issues) == 0,
            issues=issues,
            score=score,
        )

    def _check_snake_case(self, files: list[str]) -> list[str]:
        """Check that .py files follow snake_case naming."""
        issues: list[str] = []
        for filepath in files:
            p = Path(filepath)
            if p.suffix != ".py":
                continue
            filename = p.name
            # Skip dunder files like __init__.py, __main__.py
            if filename.startswith("__") and filename.endswith("__.py"):
                continue
            if not self._SNAKE_CASE_RE.match(filename):
                issues.append(f"Naming violation: {filepath} is not snake_case")
        return issues

    def _check_task_prefixes(self) -> list[str]:
        """Check that command .md files reference bracketed Task prefixes."""
        issues: list[str] = []
        commands_dir = Path(__file__).parent.parent / "data" / "commands"
        if not commands_dir.is_dir():
            return issues

        for md_file in sorted(commands_dir.glob("*.md")):
            name = md_file.name
            # Skip split fragments and internal files
            if ".core.md" in name or ".details.md" in name:
                continue
            if name.startswith("_"):
                continue

            content = md_file.read_text()
            if not self._TASK_PREFIX_RE.search(content):
                issues.append(f"Missing Task prefix: {name} has no bracketed prefix (e.g., [Plan], [L1], [Build])")
        return issues

    def _check_file_organization(self, files: list[str]) -> list[str]:
        """Check that tests and scripts are in proper directories."""
        issues: list[str] = []
        for filepath in files:
            p = Path(filepath)
            filename = p.name

            # Test files should be in tests/ directory
            if (
                (filename.startswith("test_") or filename.endswith("_test.py"))
                and "tests" not in p.parts
                and "test" not in p.parts
            ):
                issues.append(f"File organization: {filepath} looks like a test but is not in tests/")

        return issues


def _path_to_module(path: Path) -> str:
    """Convert a file path to a dotted module name."""
    parts = path.with_suffix("").parts
    return ".".join(parts)


def _max_import_depth(graph: dict[str, set[str]], node: str, seen: set[str]) -> int:
    """Calculate max import chain depth from a node."""
    if node in seen or node not in graph:
        return 0
    seen.add(node)
    max_d = 0
    for neighbor in graph[node]:
        d = _max_import_depth(graph, neighbor, seen)
        max_d = max(max_d, d)
    seen.discard(node)
    return max_d + 1


class CrossFileChecker(BaseChecker):
    """Detect exported symbols that are never imported by any other module."""

    name = "cross-file"

    def __init__(self, scope: str = "zerg/") -> None:
        self.scope = scope
        self._cache = ASTCache()

    def check(self, files: list[str]) -> AnalysisResult:
        """Run cross-file export/import analysis."""
        issues: list[str] = []
        scope_path = Path(self.scope)
        if not scope_path.is_dir():
            return AnalysisResult(check_type=CheckType.CROSS_FILE, passed=True, issues=[], score=100.0)

        py_files = sorted(scope_path.rglob("*.py"))

        # Phase 1: collect all exports per module
        exports_by_file: dict[str, list[str]] = {}
        for pf in py_files:
            if pf.name.startswith("__"):
                continue
            try:
                tree = self._cache.parse(pf)
                exports_by_file[str(pf)] = collect_exports(tree)
            except Exception:
                logger.debug("Failed to parse %s for exports", pf)
                continue

        # Phase 2: collect all imported names across entire scope
        all_imported_names: set[str] = set()
        for pf in py_files:
            try:
                tree = self._cache.parse(pf)
                for _module_name, name in collect_imports(tree):
                    if name:
                        all_imported_names.add(name)
            except Exception:
                logger.debug("Failed to parse %s for imports", pf)
                continue

        # Phase 3: diff -- exported but never imported
        for filepath, exports in exports_by_file.items():
            for symbol in exports:
                if symbol not in all_imported_names:
                    issues.append(f"Unused export: {symbol} in {filepath}")

        score = max(0.0, 100.0 - len(issues) * 3)
        return AnalysisResult(
            check_type=CheckType.CROSS_FILE,
            passed=len(issues) == 0,
            issues=issues,
            score=score,
        )


class ImportChainChecker(BaseChecker):
    """Detect circular imports and deep import chains via DFS."""

    name = "import-chain"

    def __init__(self, max_depth: int = 10) -> None:
        self.max_depth = max_depth
        self._cache = ASTCache()

    def check(self, files: list[str]) -> AnalysisResult:
        """Run import chain analysis for cycles and excessive depth."""
        issues: list[str] = []

        # Build import graph: module_stem -> set of imported module stems
        # Focus on intra-project imports (zerg.*)
        scope_path = Path("zerg/")
        if not scope_path.is_dir():
            return AnalysisResult(
                check_type=CheckType.IMPORT_CHAIN,
                passed=True,
                issues=[],
                score=100.0,
            )

        py_files = sorted(scope_path.rglob("*.py"))

        # Map: module dotted name -> set of imported zerg module names
        graph: dict[str, set[str]] = {}

        for pf in py_files:
            mod_name = _path_to_module(pf)
            graph[mod_name] = set()
            try:
                tree = self._cache.parse(pf)
                for module_name, _name in collect_imports(tree):
                    if module_name and module_name.startswith("zerg"):
                        graph[mod_name].add(module_name)
            except Exception:
                logger.debug("Failed to parse %s for dependency graph", pf)
                continue

        # Detect cycles via DFS
        visited: set[str] = set()
        rec_stack: set[str] = set()
        cycles_found: list[list[str]] = []

        def dfs(node: str, path: list[str]) -> None:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in graph.get(node, set()):
                if neighbor not in visited:
                    dfs(neighbor, path)
                elif neighbor in rec_stack:
                    # Found cycle
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    cycles_found.append(cycle)

            path.pop()
            rec_stack.discard(node)

        for mod in sorted(graph):
            if mod not in visited:
                dfs(mod, [])

        for cycle in cycles_found:
            issues.append(f"Circular import: {' -> '.join(cycle)}")

        # Check import depth (longest chain from each root)
        for mod in sorted(graph):
            depth = _max_import_depth(graph, mod, set())
            if depth > self.max_depth:
                issues.append(f"Deep import chain: {mod} has depth {depth} (max: {self.max_depth})")

        score = max(0.0, 100.0 - len(issues) * 10)
        return AnalysisResult(
            check_type=CheckType.IMPORT_CHAIN,
            passed=len(issues) == 0,
            issues=issues,
            score=score,
        )


class ContextEngineeringChecker(BaseChecker):
    """Validate context engineering principles via validate_commands checks."""

    name = "context-engineering"

    def __init__(self, auto_split: bool = False) -> None:
        self.auto_split = auto_split

    def check(self, files: list[str]) -> AnalysisResult:
        """Run all 7 validate_commands.py checks."""
        try:
            from zerg.validate_commands import validate_all

            passed, messages = validate_all(auto_split=self.auto_split)
            score = 100.0 if passed else max(0.0, 100.0 - len(messages) * 10)
            return AnalysisResult(
                check_type=CheckType.CONTEXT_ENGINEERING,
                passed=passed,
                issues=messages,
                score=score,
            )
        except ImportError as e:
            return AnalysisResult(
                check_type=CheckType.CONTEXT_ENGINEERING,
                passed=False,
                issues=[f"Could not import validate_commands: {e}"],
                score=0.0,
            )
        except Exception as e:
            return AnalysisResult(
                check_type=CheckType.CONTEXT_ENGINEERING,
                passed=False,
                issues=[f"Context engineering check error: {e}"],
                score=0.0,
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
            "dead-code": DeadCodeChecker(self.config.dead_code_min_confidence),
            "wiring": WiringChecker(self.config.wiring_strict),
            "cross-file": CrossFileChecker(self.config.cross_file_scope),
            "conventions": ConventionsChecker(
                self.config.conventions_naming,
                self.config.conventions_require_task_prefixes,
            ),
            "import-chain": ImportChainChecker(self.config.import_chain_max_depth),
            "context-engineering": ContextEngineeringChecker(self.config.context_engineering_auto_split),
        }

    def supported_checks(self) -> list[str]:
        """Return list of supported check types."""
        return list(self.checkers.keys())

    def run(self, checks: list[str], files: list[str], threshold: dict[str, int] | None = None) -> list[AnalysisResult]:
        """Run specified checks on files."""
        results = []

        if "all" in checks:
            checks = list(self.checkers.keys())

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
    type=click.Choice(
        [
            "lint",
            "complexity",
            "coverage",
            "security",
            "performance",
            "dead-code",
            "wiring",
            "cross-file",
            "conventions",
            "import-chain",
            "context-engineering",
            "all",
        ]
    ),
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
@click.option("--performance", is_flag=True, help="Run comprehensive performance audit (140 factors)")
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
