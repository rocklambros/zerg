"""ZERG v2 Test Runner - Test generation, execution, and coverage analysis."""

import json
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

# Import secure command executor
sys.path.insert(0, str(Path(__file__).parent.parent))
from zerg.command_executor import CommandExecutor, CommandValidationError


class TestFramework(Enum):
    """Supported test frameworks."""

    PYTEST = "pytest"
    JEST = "jest"
    CARGO = "cargo"
    GO = "go"
    MOCHA = "mocha"
    VITEST = "vitest"


@dataclass
class TestConfig:
    """Configuration for test execution."""

    parallel: bool = True
    coverage: bool = False
    watch: bool = False
    workers: int = 4
    timeout_seconds: int = 300
    verbose: bool = False
    filter: str = ""


@dataclass
class TestResult:
    """Result of test execution."""

    total: int
    passed: int
    failed: int
    skipped: int
    duration_seconds: float = 0.0
    coverage_percentage: float | None = None
    errors: list[str] = field(default_factory=list)

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


@dataclass
class CoverageReport:
    """Coverage analysis report."""

    total_lines: int
    covered_lines: int
    percentage: float
    files: dict[str, float] = field(default_factory=dict)

    def meets_threshold(self, threshold: int) -> bool:
        """Check if coverage meets threshold."""
        return self.percentage >= threshold


class FrameworkDetector:
    """Detect test frameworks from project structure."""

    FRAMEWORK_MARKERS = {
        TestFramework.PYTEST: ["pytest.ini", "pyproject.toml", "conftest.py"],
        TestFramework.JEST: ["jest.config.js", "jest.config.ts", "package.json"],
        TestFramework.CARGO: ["Cargo.toml"],
        TestFramework.GO: ["go.mod"],
        TestFramework.MOCHA: [".mocharc.js", ".mocharc.json"],
        TestFramework.VITEST: ["vitest.config.ts", "vitest.config.js"],
    }

    def detect(self, project_path: Path) -> list[TestFramework]:
        """Detect test frameworks in project.

        Args:
            project_path: Path to project root

        Returns:
            List of detected frameworks
        """
        detected = []

        for framework, markers in self.FRAMEWORK_MARKERS.items():
            for marker in markers:
                if (project_path / marker).exists():
                    if framework not in detected:
                        detected.append(framework)
                    break

        # Check package.json for JS frameworks
        package_json = project_path / "package.json"
        if package_json.exists():
            try:
                with open(package_json) as f:
                    pkg = json.load(f)
                    deps = {
                        **pkg.get("dependencies", {}),
                        **pkg.get("devDependencies", {}),
                    }
                    if "jest" in deps and TestFramework.JEST not in detected:
                        detected.append(TestFramework.JEST)
                    if "vitest" in deps and TestFramework.VITEST not in detected:
                        detected.append(TestFramework.VITEST)
                    if "mocha" in deps and TestFramework.MOCHA not in detected:
                        detected.append(TestFramework.MOCHA)
            except (json.JSONDecodeError, OSError):
                pass

        return detected


class TestRunner:
    """Execute tests with various frameworks."""

    COMMANDS = {
        TestFramework.PYTEST: "python -m pytest",
        TestFramework.JEST: "npx jest",
        TestFramework.CARGO: "cargo test",
        TestFramework.GO: "go test ./...",
        TestFramework.MOCHA: "npx mocha",
        TestFramework.VITEST: "npx vitest run",
    }

    def __init__(self, config: TestConfig | None = None):
        """Initialize test runner."""
        self.config = config or TestConfig()

    def _get_executor(self, cwd: str = ".") -> CommandExecutor:
        """Get command executor for test execution."""
        return CommandExecutor(
            working_dir=Path(cwd),
            allow_unlisted=True,  # Allow test commands
            timeout=self.config.timeout_seconds,
        )

    def get_command(self, framework: TestFramework) -> str:
        """Get test command for framework.

        Args:
            framework: Test framework to use

        Returns:
            Command string
        """
        base_cmd = self.COMMANDS.get(framework, "pytest")

        if framework == TestFramework.PYTEST:
            args = []
            if self.config.coverage:
                args.append("--cov")
            if self.config.parallel and self.config.workers > 1:
                args.append(f"-n {self.config.workers}")
            if self.config.verbose:
                args.append("-v")
            if self.config.filter:
                args.append(f"-k '{self.config.filter}'")
            return f"{base_cmd} {' '.join(args)}".strip()

        elif framework == TestFramework.JEST:
            args = []
            if self.config.coverage:
                args.append("--coverage")
            if self.config.parallel:
                args.append(f"--maxWorkers={self.config.workers}")
            if self.config.watch:
                args.append("--watch")
            return f"{base_cmd} {' '.join(args)}".strip()

        elif framework == TestFramework.CARGO:
            args = []
            if self.config.parallel:
                args.append(f"-- --test-threads={self.config.workers}")
            return f"{base_cmd} {' '.join(args)}".strip()

        return base_cmd

    def run(
        self, framework: TestFramework, path: str = "."
    ) -> TestResult:
        """Run tests and return results.

        Args:
            framework: Test framework to use
            path: Path to test directory

        Returns:
            TestResult with execution details
        """
        cmd = self.get_command(framework)

        try:
            # Use secure command executor - no shell=True
            executor = self._get_executor(path)
            result = executor.execute(cmd, timeout=self.config.timeout_seconds)

            # Parse output based on framework
            return self._parse_output(framework, result.stdout, result.exit_code)

        except CommandValidationError as e:
            return TestResult(
                total=0,
                passed=0,
                failed=0,
                skipped=0,
                errors=[f"Command validation failed: {e}"],
            )
        except Exception as e:
            return TestResult(
                total=0,
                passed=0,
                failed=0,
                skipped=0,
                errors=[f"Test execution error: {e}"],
            )

    def _parse_output(
        self, framework: TestFramework, output: str, returncode: int
    ) -> TestResult:
        """Parse test output to extract results."""
        # Basic parsing - real implementation would be framework-specific
        if returncode == 0:
            return TestResult(total=1, passed=1, failed=0, skipped=0)
        else:
            return TestResult(
                total=1, passed=0, failed=1, skipped=0, errors=[output[:500]]
            )


class TestCommand:
    """Main test command orchestrator."""

    def __init__(self, config: TestConfig | None = None):
        """Initialize test command."""
        self.config = config or TestConfig()
        self.detector = FrameworkDetector()
        self.runner = TestRunner(config=self.config)

    def supported_frameworks(self) -> list[str]:
        """Return list of supported frameworks."""
        return [f.value for f in TestFramework]

    def run(
        self,
        framework: TestFramework | None = None,
        path: str = ".",
        dry_run: bool = False,
    ) -> TestResult:
        """Run tests.

        Args:
            framework: Framework to use (auto-detect if None)
            path: Path to test directory
            dry_run: If True, don't actually run tests

        Returns:
            TestResult with execution details
        """
        if dry_run:
            return TestResult(total=0, passed=0, failed=0, skipped=0)

        if framework is None:
            detected = self.detector.detect(Path(path))
            framework = detected[0] if detected else TestFramework.PYTEST

        return self.runner.run(framework, path)

    def format_result(self, result: TestResult, format: str = "text") -> str:
        """Format test result.

        Args:
            result: Test result to format
            format: Output format (text or json)

        Returns:
            Formatted string
        """
        if format == "json":
            return json.dumps(
                {
                    "total": result.total,
                    "passed": result.passed,
                    "failed": result.failed,
                    "skipped": result.skipped,
                    "success": result.success,
                    "pass_percentage": result.pass_percentage,
                    "duration_seconds": result.duration_seconds,
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
        if result.errors:
            lines.append("")
            lines.append("Errors:")
            for error in result.errors[:5]:
                lines.append(f"  - {error[:100]}")

        return "\n".join(lines)


class TestStubGenerator:
    """Generate test stubs for uncovered code."""

    TEMPLATES = {
        "function": '''def test_{name}():
    """Test {name} function."""
    # TODO: Implement test
    result = {name}()
    assert result is not None
''',
        "class": '''class Test{name}:
    """Tests for {name} class."""

    def test_{name}_creation(self):
        """Test {name} can be created."""
        instance = {name}()
        assert instance is not None
''',
        "method": '''def test_{class_name}_{name}(self):
    """Test {class_name}.{name} method."""
    # TODO: Implement test
    instance = {class_name}()
    result = instance.{name}()
    assert result is not None
''',
    }

    def generate_stub(
        self, name: str, kind: str = "function", class_name: str = ""
    ) -> str:
        """Generate test stub.

        Args:
            name: Name of function/class/method
            kind: Type of code element
            class_name: Parent class name for methods

        Returns:
            Test stub code
        """
        template = self.TEMPLATES.get(kind, self.TEMPLATES["function"])
        return template.format(name=name, class_name=class_name)


__all__ = [
    "TestFramework",
    "TestConfig",
    "TestResult",
    "CoverageReport",
    "FrameworkDetector",
    "TestRunner",
    "TestCommand",
    "TestStubGenerator",
]
