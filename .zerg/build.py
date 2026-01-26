"""ZERG v2 Build Command - Build orchestration with error recovery."""

import json
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class BuildSystem(Enum):
    """Supported build systems."""

    NPM = "npm"
    CARGO = "cargo"
    MAKE = "make"
    GRADLE = "gradle"
    GO = "go"
    PYTHON = "python"


class ErrorCategory(Enum):
    """Build error categories."""

    MISSING_DEPENDENCY = "missing_dependency"
    TYPE_ERROR = "type_error"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    NETWORK_TIMEOUT = "network_timeout"
    SYNTAX_ERROR = "syntax_error"
    UNKNOWN = "unknown"


@dataclass
class BuildConfig:
    """Configuration for build."""

    mode: str = "dev"
    clean: bool = False
    watch: bool = False
    retry: int = 3
    target: str = "all"


@dataclass
class BuildResult:
    """Result of build operation."""

    success: bool
    duration_seconds: float
    artifacts: list[str]
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    retries: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "duration_seconds": self.duration_seconds,
            "artifacts": self.artifacts,
            "errors": self.errors,
            "warnings": self.warnings,
            "retries": self.retries,
        }


class BuildDetector:
    """Detect build systems from project structure."""

    MARKERS = {
        BuildSystem.NPM: ["package.json"],
        BuildSystem.CARGO: ["Cargo.toml"],
        BuildSystem.MAKE: ["Makefile", "makefile"],
        BuildSystem.GRADLE: ["build.gradle", "build.gradle.kts"],
        BuildSystem.GO: ["go.mod"],
        BuildSystem.PYTHON: ["setup.py", "pyproject.toml"],
    }

    def detect(self, project_path: Path) -> list[BuildSystem]:
        """Detect build systems in project."""
        detected = []
        for system, markers in self.MARKERS.items():
            for marker in markers:
                if (project_path / marker).exists():
                    detected.append(system)
                    break
        return detected


class ErrorRecovery:
    """Classify and recover from build errors."""

    PATTERNS = {
        ErrorCategory.MISSING_DEPENDENCY: [
            "ModuleNotFoundError",
            "Cannot find module",
            "package not found",
            "dependency",
        ],
        ErrorCategory.TYPE_ERROR: [
            "TypeError",
            "type error",
            "incompatible types",
        ],
        ErrorCategory.RESOURCE_EXHAUSTION: [
            "out of memory",
            "heap",
            "ENOMEM",
        ],
        ErrorCategory.NETWORK_TIMEOUT: [
            "timeout",
            "ETIMEDOUT",
            "connection refused",
        ],
        ErrorCategory.SYNTAX_ERROR: [
            "SyntaxError",
            "parse error",
            "unexpected token",
        ],
    }

    def classify(self, error: str) -> ErrorCategory:
        """Classify error by category."""
        error_lower = error.lower()
        for category, patterns in self.PATTERNS.items():
            for pattern in patterns:
                if pattern.lower() in error_lower:
                    return category
        return ErrorCategory.UNKNOWN

    def get_recovery_action(self, category: ErrorCategory) -> str:
        """Get recovery action for error category."""
        actions = {
            ErrorCategory.MISSING_DEPENDENCY: "Install missing dependencies",
            ErrorCategory.TYPE_ERROR: "Fix type errors",
            ErrorCategory.RESOURCE_EXHAUSTION: "Reduce parallelism",
            ErrorCategory.NETWORK_TIMEOUT: "Retry with backoff",
            ErrorCategory.SYNTAX_ERROR: "Fix syntax errors",
            ErrorCategory.UNKNOWN: "Review error manually",
        }
        return actions.get(category, "Unknown action")


class BuildRunner:
    """Execute builds for different systems."""

    COMMANDS = {
        BuildSystem.NPM: {"dev": "npm run dev", "prod": "npm run build"},
        BuildSystem.CARGO: {"dev": "cargo build", "prod": "cargo build --release"},
        BuildSystem.MAKE: {"dev": "make", "prod": "make release"},
        BuildSystem.GRADLE: {"dev": "gradle build", "prod": "gradle build -Penv=prod"},
        BuildSystem.GO: {"dev": "go build ./...", "prod": "go build -ldflags='-s -w' ./..."},
        BuildSystem.PYTHON: {"dev": "pip install -e .", "prod": "python -m build"},
    }

    def get_command(self, system: BuildSystem, mode: str = "dev") -> str:
        """Get build command for system and mode."""
        commands = self.COMMANDS.get(system, {})
        return commands.get(mode, commands.get("dev", "make"))

    def run(
        self, system: BuildSystem, config: BuildConfig, cwd: str = "."
    ) -> BuildResult:
        """Run build."""
        command = self.get_command(system, config.mode)
        start = time.time()

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=600,
            )
            duration = time.time() - start

            if result.returncode == 0:
                return BuildResult(
                    success=True,
                    duration_seconds=duration,
                    artifacts=[],
                )
            else:
                return BuildResult(
                    success=False,
                    duration_seconds=duration,
                    artifacts=[],
                    errors=[result.stderr or result.stdout],
                )
        except subprocess.TimeoutExpired:
            return BuildResult(
                success=False,
                duration_seconds=600,
                artifacts=[],
                errors=["Build timed out"],
            )
        except Exception as e:
            return BuildResult(
                success=False,
                duration_seconds=time.time() - start,
                artifacts=[],
                errors=[str(e)],
            )


class BuildCommand:
    """Main build command orchestrator."""

    def __init__(self, config: BuildConfig | None = None):
        """Initialize build command."""
        self.config = config or BuildConfig()
        self.detector = BuildDetector()
        self.runner = BuildRunner()
        self.recovery = ErrorRecovery()

    def supported_systems(self) -> list[str]:
        """Return list of supported build systems."""
        return [s.value for s in BuildSystem]

    def run(
        self,
        system: BuildSystem | None = None,
        dry_run: bool = False,
    ) -> BuildResult:
        """Run build.

        Args:
            system: Build system to use (auto-detect if None)
            dry_run: If True, don't actually build

        Returns:
            BuildResult with build details
        """
        if dry_run:
            return BuildResult(
                success=True,
                duration_seconds=0.0,
                artifacts=[],
            )

        if system is None:
            detected = self.detector.detect(Path("."))
            system = detected[0] if detected else BuildSystem.MAKE

        # Attempt build with retries
        for attempt in range(self.config.retry):
            result = self.runner.run(system, self.config)
            if result.success:
                result.retries = attempt
                return result

            # Try recovery
            if result.errors:
                category = self.recovery.classify(result.errors[0])
                if category == ErrorCategory.NETWORK_TIMEOUT:
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue

            result.retries = attempt + 1

        return result

    def format_result(self, result: BuildResult, format: str = "text") -> str:
        """Format build result.

        Args:
            result: Build result to format
            format: Output format (text or json)

        Returns:
            Formatted string
        """
        if format == "json":
            return json.dumps(result.to_dict(), indent=2)

        status = "✓ SUCCESS" if result.success else "✗ FAILED"
        lines = [
            "Build Result",
            "=" * 40,
            f"Status: {status}",
            f"Duration: {result.duration_seconds:.2f}s",
            f"Retries: {result.retries}",
        ]

        if result.artifacts:
            lines.append(f"Artifacts: {len(result.artifacts)}")
            for artifact in result.artifacts[:5]:
                lines.append(f"  - {artifact}")

        if result.errors:
            lines.append("Errors:")
            for error in result.errors[:3]:
                lines.append(f"  - {error[:100]}")

        return "\n".join(lines)


__all__ = [
    "BuildSystem",
    "ErrorCategory",
    "BuildConfig",
    "BuildResult",
    "BuildDetector",
    "ErrorRecovery",
    "BuildRunner",
    "BuildCommand",
]
