"""ZERG test command - test execution with coverage analysis."""

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from zerg.command_executor import CommandExecutor, CommandValidationError
from zerg.logging import get_logger

console = Console()
logger = get_logger("test")


class Framework(Enum):
    """Supported test frameworks."""

    PYTEST = "pytest"
    JEST = "jest"
    CARGO = "cargo"
    GO = "go"
    MOCHA = "mocha"
    VITEST = "vitest"


# Backward compat aliases (will be removed in v3)
TestFramework = Framework


@dataclass
class RunConfig:
    """Configuration for test execution."""

    parallel: bool = True
    coverage: bool = False
    watch: bool = False
    workers: int = 4
    timeout_seconds: int = 300
    verbose: bool = False
    filter: str = ""


# Backward compat aliases (will be removed in v3)
TestConfig = RunConfig


@dataclass
class RunResult:
    """Result of test execution."""

    total: int
    passed: int
    failed: int
    skipped: int
    duration_seconds: float = 0.0
    coverage_percentage: float | None = None
    errors: list[str] = field(default_factory=list)
    output: str = ""

    @property
    def success(self) -> bool:
        """Check if all tests passed."""
        return self.failed == 0

    @property
    def pass_percentage(self) -> float:
        """Calculate pass percentage."""
        if self.total == 0:
            return 0.0
        return (self.passed / self.total) * 100


# Backward compat aliases (will be removed in v3)
TestResult = RunResult


class FrameworkDetector:
    """Detect test frameworks from project structure."""

    FRAMEWORK_MARKERS = {
        Framework.PYTEST: ["pytest.ini", "pyproject.toml", "conftest.py", "tests/"],
        Framework.JEST: ["jest.config.js", "jest.config.ts"],
        Framework.CARGO: ["Cargo.toml"],
        Framework.GO: ["go.mod"],
        Framework.MOCHA: [".mocharc.js", ".mocharc.json"],
        Framework.VITEST: ["vitest.config.ts", "vitest.config.js"],
    }

    def detect(self, project_path: Path) -> list[TestFramework]:
        """Detect test frameworks in project."""
        detected = []

        for framework, markers in self.FRAMEWORK_MARKERS.items():
            for marker in markers:
                marker_path = project_path / marker
                if marker_path.exists():
                    if framework not in detected:
                        detected.append(framework)
                    break

        # Check package.json for JS frameworks
        package_json = project_path / "package.json"
        if package_json.exists():
            try:
                import json as json_module

                pkg = json_module.loads(package_json.read_text())
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                if "jest" in deps and Framework.JEST not in detected:
                    detected.append(Framework.JEST)
                if "vitest" in deps and Framework.VITEST not in detected:
                    detected.append(Framework.VITEST)
                if "mocha" in deps and Framework.MOCHA not in detected:
                    detected.append(Framework.MOCHA)
            except Exception as e:
                logger.debug(f"Config loading failed: {e}")

        return detected


class Runner:
    """Execute tests with various frameworks."""

    COMMANDS = {
        Framework.PYTEST: "python -m pytest",
        Framework.JEST: "npx jest",
        Framework.CARGO: "cargo test",
        Framework.GO: "go test ./...",
        Framework.MOCHA: "npx mocha",
        Framework.VITEST: "npx vitest run",
    }

    def __init__(self, config: RunConfig | None = None) -> None:
        """Initialize test runner."""
        self.config = config or RunConfig()

    def _get_executor(self, cwd: str = ".") -> CommandExecutor:
        """Get command executor for test execution."""
        return CommandExecutor(
            working_dir=Path(cwd),
            allow_unlisted=True,
            timeout=self.config.timeout_seconds,
        )

    def get_command(self, framework: Framework, path: str = "") -> str:
        """Get test command for framework."""
        base_cmd = self.COMMANDS.get(framework, "pytest")

        if framework == Framework.PYTEST:
            args = []
            if self.config.coverage:
                args.append("--cov")
            if self.config.parallel and self.config.workers > 1:
                args.append(f"-n {self.config.workers}")
            if self.config.verbose:
                args.append("-v")
            if self.config.filter:
                args.append(f"-k '{self.config.filter}'")
            if path:
                args.append(path)
            return f"{base_cmd} {' '.join(args)}".strip()

        elif framework == Framework.JEST:
            args = []
            if self.config.coverage:
                args.append("--coverage")
            if self.config.parallel:
                args.append(f"--maxWorkers={self.config.workers}")
            if path:
                args.append(path)
            return f"{base_cmd} {' '.join(args)}".strip()

        elif framework == Framework.CARGO:
            args = []
            if self.config.parallel:
                args.append(f"-- --test-threads={self.config.workers}")
            return f"{base_cmd} {' '.join(args)}".strip()

        elif framework == Framework.GO:
            args = []
            if self.config.coverage:
                args.append("-cover")
            if self.config.verbose:
                args.append("-v")
            if path:
                return f"go test {' '.join(args)} {path}".strip()
            return f"{base_cmd} {' '.join(args)}".strip()

        return base_cmd

    def run(self, framework: Framework, path: str = ".") -> RunResult:
        """Run tests and return results."""
        cmd = self.get_command(framework, path if path != "." else "")
        start = time.time()

        try:
            executor = self._get_executor(path)
            result = executor.execute(cmd, timeout=self.config.timeout_seconds)
            duration = time.time() - start

            return self._parse_output(
                framework,
                result.stdout + result.stderr,
                result.exit_code,
                duration,
            )

        except CommandValidationError as e:
            return RunResult(
                total=0,
                passed=0,
                failed=0,
                skipped=0,
                errors=[f"Command validation failed: {e}"],
            )
        except Exception as e:
            return RunResult(
                total=0,
                passed=0,
                failed=0,
                skipped=0,
                errors=[f"Test execution error: {e}"],
            )

    def _parse_output(self, framework: Framework, output: str, returncode: int, duration: float) -> RunResult:
        """Parse test output to extract results."""
        import re

        total = passed = failed = skipped = 0
        coverage = None

        if framework == Framework.PYTEST:
            # Parse pytest output: "5 passed, 2 failed, 1 skipped"
            match = re.search(r"(\d+) passed", output)
            if match:
                passed = int(match.group(1))
            match = re.search(r"(\d+) failed", output)
            if match:
                failed = int(match.group(1))
            match = re.search(r"(\d+) skipped", output)
            if match:
                skipped = int(match.group(1))
            match = re.search(r"(\d+) error", output)
            if match:
                failed += int(match.group(1))

            # Coverage
            match = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", output)
            if match:
                coverage = float(match.group(1))

            total = passed + failed + skipped

        elif framework in (Framework.JEST, Framework.VITEST):
            # Parse jest output: "Tests: 5 passed, 2 failed, 7 total"
            match = re.search(r"(\d+) passed", output)
            if match:
                passed = int(match.group(1))
            match = re.search(r"(\d+) failed", output)
            if match:
                failed = int(match.group(1))
            match = re.search(r"(\d+) skipped", output)
            if match:
                skipped = int(match.group(1))
            match = re.search(r"(\d+) total", output)
            if match:
                total = int(match.group(1))

        elif framework == Framework.GO:
            # Parse go test output
            passed = output.count("--- PASS:")
            failed = output.count("--- FAIL:")
            skipped = output.count("--- SKIP:")
            total = passed + failed + skipped

            # Coverage
            match = re.search(r"coverage:\s+(\d+\.?\d*)%", output)
            if match:
                coverage = float(match.group(1))

        elif framework == Framework.CARGO:
            # Parse cargo test output
            match = re.search(r"(\d+) passed", output)
            if match:
                passed = int(match.group(1))
            match = re.search(r"(\d+) failed", output)
            if match:
                failed = int(match.group(1))
            match = re.search(r"(\d+) ignored", output)
            if match:
                skipped = int(match.group(1))
            total = passed + failed + skipped

        # Fallback
        if total == 0:
            if returncode == 0:
                total = passed = 1
            else:
                total = failed = 1

        return RunResult(
            total=total,
            passed=passed,
            failed=failed,
            skipped=skipped,
            duration_seconds=duration,
            coverage_percentage=coverage,
            errors=[output[:1000]] if returncode != 0 else [],
            output=output,
        )


# Backward compat alias (will be removed in v3)
TestRunner = Runner


class StubGenerator:
    """Generate test stubs for uncovered code."""

    TEMPLATES = {
        "python_function": '''def test_{name}():
    """Test {name} function."""
    # Arrange
    # TODO: Set up test data

    # Act
    result = {name}()

    # Assert
    assert result is not None
''',
        "python_class": '''class Test{name}:
    """Tests for {name} class."""

    def test_{name}_creation(self):
        """Test {name} can be instantiated."""
        instance = {name}()
        assert instance is not None

    def test_{name}_basic_operation(self):
        """Test basic operation of {name}."""
        instance = {name}()
        # TODO: Add meaningful test
        pass
''',
    }

    def generate_stub(self, name: str, kind: str = "function") -> str:
        """Generate test stub."""
        template_key = f"python_{kind}"
        template = self.TEMPLATES.get(template_key, self.TEMPLATES["python_function"])
        return template.format(name=name)


# Backward compat alias (will be removed in v3)
TestStubGenerator = StubGenerator


class Command:
    """Main test command orchestrator."""

    def __init__(self, config: RunConfig | None = None) -> None:
        """Initialize test command."""
        self.config = config or RunConfig()
        self.detector = FrameworkDetector()
        self.runner = Runner(config=self.config)
        self.stub_generator = StubGenerator()

    def supported_frameworks(self) -> list[str]:
        """Return list of supported frameworks."""
        return [f.value for f in Framework]

    def run(
        self,
        framework: Framework | None = None,
        path: str = ".",
        dry_run: bool = False,
    ) -> RunResult:
        """Run tests."""
        if dry_run:
            detected = self.detector.detect(Path(path))
            framework_name = detected[0].value if detected else "unknown"
            cmd = self.runner.get_command(detected[0] if detected else Framework.PYTEST)
            return RunResult(
                total=0,
                passed=0,
                failed=0,
                skipped=0,
                output=f"Would run: {cmd}",
                errors=[f"Dry run: detected framework {framework_name}"],
            )

        if framework is None:
            detected = self.detector.detect(Path(path))
            framework = detected[0] if detected else Framework.PYTEST

        return self.runner.run(framework, path)

    def format_result(self, result: RunResult, fmt: str = "text") -> str:
        """Format test result."""
        if fmt == "json":
            return json.dumps(
                {
                    "total": result.total,
                    "passed": result.passed,
                    "failed": result.failed,
                    "skipped": result.skipped,
                    "success": result.success,
                    "pass_percentage": result.pass_percentage,
                    "duration_seconds": result.duration_seconds,
                    "coverage_percentage": result.coverage_percentage,
                    "errors": result.errors,
                },
                indent=2,
            )

        lines = [
            "Test Results",
            "=" * 40,
            f"Total: {result.total}",
            f"Passed: {result.passed}",
            f"Failed: {result.failed}",
            f"Skipped: {result.skipped}",
            "",
            f"Pass Rate: {result.pass_percentage:.1f}%",
        ]
        if result.duration_seconds:
            lines.append(f"Duration: {result.duration_seconds:.2f}s")
        if result.coverage_percentage is not None:
            lines.append(f"Coverage: {result.coverage_percentage:.1f}%")
        if result.errors:
            lines.append("")
            lines.append("Errors:")
            for error in result.errors[:5]:
                lines.append(f"  - {error[:100]}")

        return "\n".join(lines)


# Backward compat alias (will be removed in v3)
TestCommand = Command


def _watch_loop(tester: Command, framework: Framework | None, path: str) -> None:
    """Simple watch loop using polling."""
    import hashlib

    def get_file_hashes(target: Path) -> dict[str, str]:
        """Get hashes of test-related files."""
        hashes = {}
        for ext in ["*.py", "*.js", "*.ts", "*.go", "*.rs"]:
            for f in target.rglob(ext):
                if "__pycache__" in str(f):
                    continue
                try:
                    content = f.read_bytes()
                    hashes[str(f)] = hashlib.md5(content).hexdigest()
                except OSError:
                    pass
        return hashes

    console.print("[cyan]Watch mode enabled. Press Ctrl+C to stop.[/cyan]\n")

    last_hashes = get_file_hashes(Path(path))
    last_run_time = 0.0

    while True:
        try:
            time.sleep(1)
            current_hashes = get_file_hashes(Path(path))

            if current_hashes != last_hashes and time.time() - last_run_time > 2:
                changed = [f for f in current_hashes if f not in last_hashes or current_hashes[f] != last_hashes[f]]
                console.print(f"\n[yellow]Changes detected in {len(changed)} files[/yellow]")

                result = tester.run(framework=framework, path=path)
                if result.success:
                    console.print(f"[green]✓ {result.passed}/{result.total} tests passed[/green]")
                else:
                    console.print(f"[red]✗ {result.failed}/{result.total} tests failed[/red]")

                last_hashes = current_hashes
                last_run_time = time.time()

        except KeyboardInterrupt:
            console.print("\n[yellow]Watch mode stopped[/yellow]")
            break


@click.command("test")
@click.option("--generate", "-g", is_flag=True, help="Generate test stubs")
@click.option("--coverage", "-c", is_flag=True, help="Report coverage")
@click.option("--watch", "-w", is_flag=True, help="Watch mode")
@click.option("--parallel", "-p", type=int, help="Number of parallel workers")
@click.option(
    "--framework",
    "-f",
    type=click.Choice(["pytest", "jest", "cargo", "go", "mocha", "vitest"]),
    help="Test framework (auto-detected if not specified)",
)
@click.option("--path", help="Path to test files")
@click.option("--dry-run", is_flag=True, help="Show what would be run without running")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.pass_context
def test_cmd(
    ctx: click.Context,
    generate: bool,
    coverage: bool,
    watch: bool,
    parallel: int | None,
    framework: str | None,
    path: str | None,
    dry_run: bool,
    json_output: bool,
) -> None:
    """Execute tests with coverage analysis and test generation.

    Auto-detects test framework (pytest, jest, cargo, go, mocha, vitest)
    and runs tests with optional coverage reporting.

    Examples:

        zerg test

        zerg test --coverage

        zerg test --watch --parallel 8

        zerg test --generate

        zerg test --dry-run
    """
    try:
        console.print("\n[bold cyan]ZERG Test[/bold cyan]\n")

        test_path = path or "."

        # Create config
        config = TestConfig(
            coverage=coverage,
            watch=watch,
            workers=parallel or 4,
            parallel=parallel is not None and parallel > 1,
        )

        tester = TestCommand(config)

        # Detect framework
        detected = tester.detector.detect(Path(test_path))
        fw: TestFramework | None = None

        if framework:
            fw = TestFramework(framework)
        elif detected:
            fw = detected[0]
        else:
            fw = Framework.PYTEST

        console.print(f"Framework: [cyan]{fw.value}[/cyan]")

        # Generate stubs mode
        if generate:
            console.print("\n[bold]Generating test stubs...[/bold]")

            # Find Python files without tests
            source_dir = Path(test_path)
            if source_dir.is_dir():
                for py_file in source_dir.rglob("*.py"):
                    if "test" in str(py_file) or "__pycache__" in str(py_file):
                        continue

                    # Check if test file exists
                    test_file = py_file.parent / f"test_{py_file.name}"
                    if not test_file.exists():
                        console.print(f"  Would create: {test_file}")

            console.print("\n[yellow]Stub generation is a preview - files not created[/yellow]")
            raise SystemExit(0)

        # Watch mode (skip in dry-run)
        if watch and not dry_run:
            _watch_loop(tester, fw, test_path)
            return
        elif watch and dry_run:
            console.print("[cyan]Watch mode would be enabled (dry-run)[/cyan]")

        # Run tests
        if not dry_run:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                progress.add_task(description="Running tests...", total=None)
                result = tester.run(framework=fw, path=test_path)
        else:
            result = tester.run(framework=fw, path=test_path, dry_run=True)

        # Output
        if json_output:
            console.print(tester.format_result(result, "json"))
        else:
            # Display results
            table = Table(title="Test Results")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", justify="right")

            table.add_row("Total", str(result.total))
            table.add_row("Passed", f"[green]{result.passed}[/green]")
            table.add_row("Failed", f"[red]{result.failed}[/red]" if result.failed else "0")
            table.add_row("Skipped", str(result.skipped))
            table.add_row("Duration", f"{result.duration_seconds:.2f}s")
            if result.coverage_percentage is not None:
                table.add_row("Coverage", f"{result.coverage_percentage:.1f}%")

            console.print(table)

            # Status
            if result.success:
                console.print(
                    Panel(
                        f"[green]All {result.passed} tests passed[/green]",
                        title="Result",
                    )
                )
            else:
                console.print(
                    Panel(
                        f"[red]{result.failed} tests failed[/red]",
                        title="Result",
                    )
                )
                if result.errors:
                    console.print("\n[red]Errors:[/red]")
                    for error in result.errors[:3]:
                        # Truncate long output
                        console.print(f"  {error[:500]}")

            if dry_run and result.output:
                console.print(f"\n[dim]{result.output}[/dim]")

        raise SystemExit(0 if result.success else 1)

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted[/yellow]")
        raise SystemExit(130) from None
    except SystemExit:
        raise
    except Exception as e:
        console.print(f"\n[red]Error:[/red] {e}")
        logger.exception("Test command failed")
        raise SystemExit(1) from e
