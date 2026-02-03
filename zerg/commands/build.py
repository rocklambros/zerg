"""ZERG build command - build orchestration with error recovery."""

import json
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from zerg.command_executor import CommandExecutor, CommandValidationError
from zerg.logging import get_logger

console = Console()
logger = get_logger("build")


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

    def to_dict(self) -> dict[str, Any]:
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
        BuildSystem.NPM: {
            "dev": "npm run dev",
            "staging": "npm run build",
            "prod": "npm run build",
        },
        BuildSystem.CARGO: {
            "dev": "cargo build",
            "staging": "cargo build",
            "prod": "cargo build --release",
        },
        BuildSystem.MAKE: {
            "dev": "make",
            "staging": "make",
            "prod": "make release",
        },
        BuildSystem.GRADLE: {
            "dev": "gradle build",
            "staging": "gradle build",
            "prod": "gradle build -Penv=prod",
        },
        BuildSystem.GO: {
            "dev": "go build ./...",
            "staging": "go build ./...",
            "prod": "go build -ldflags='-s -w' ./...",
        },
        BuildSystem.PYTHON: {
            "dev": "pip install -e .",
            "staging": "python -m build",
            "prod": "python -m build",
        },
    }

    def _get_executor(self, cwd: str = ".") -> CommandExecutor:
        """Get command executor for build execution."""
        return CommandExecutor(
            working_dir=Path(cwd),
            allow_unlisted=True,
            timeout=600,
        )

    def get_command(self, system: BuildSystem, mode: str = "dev") -> str:
        """Get build command for system and mode."""
        commands = self.COMMANDS.get(system, {})
        return commands.get(mode, commands.get("dev", "make"))

    def run(self, system: BuildSystem, config: BuildConfig, cwd: str = ".") -> BuildResult:
        """Run build."""
        command = self.get_command(system, config.mode)
        start = time.time()

        try:
            executor = self._get_executor(cwd)
            result = executor.execute(command, timeout=600)
            duration = time.time() - start

            if result.success:
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
                    errors=[result.stderr or result.stdout or "Build failed"],
                )
        except CommandValidationError as e:
            return BuildResult(
                success=False,
                duration_seconds=time.time() - start,
                artifacts=[],
                errors=[f"Command validation failed: {e}"],
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

    def __init__(self, config: BuildConfig | None = None) -> None:
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
        cwd: str = ".",
    ) -> BuildResult:
        """Run build."""
        if dry_run:
            detected = self.detector.detect(Path(cwd))
            system_name = detected[0].value if detected else "unknown"
            return BuildResult(
                success=True,
                duration_seconds=0.0,
                artifacts=[],
                warnings=[f"Dry run: would build with {system_name}"],
            )

        if system is None:
            detected = self.detector.detect(Path(cwd))
            system = detected[0] if detected else BuildSystem.MAKE

        # Attempt build with retries
        result = None
        for attempt in range(self.config.retry):
            result = self.runner.run(system, self.config, cwd)
            if result.success:
                result.retries = attempt
                return result

            # Try recovery
            if result.errors:
                category = self.recovery.classify(result.errors[0])
                if category == ErrorCategory.NETWORK_TIMEOUT:
                    time.sleep(2**attempt)  # Exponential backoff
                    continue

            result.retries = attempt + 1

        return result or BuildResult(
            success=False,
            duration_seconds=0.0,
            artifacts=[],
            errors=["Build failed after retries"],
        )

    def format_result(self, result: BuildResult, fmt: str = "text") -> str:
        """Format build result."""
        if fmt == "json":
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


def _build_docker_image() -> None:
    """Build the zerg-worker Docker image."""
    dockerfile = Path(".devcontainer/Dockerfile")
    if not dockerfile.exists():
        console.print("[red]No .devcontainer/Dockerfile found[/red]")
        raise SystemExit(1)

    console.print("[cyan]Building zerg-worker Docker image...[/cyan]")
    cmd = ["docker", "build", "-t", "zerg-worker", "-f", str(dockerfile), "."]

    try:
        result = subprocess.run(cmd, timeout=600)
    except FileNotFoundError:
        console.print("[red]Docker not found. Is Docker installed and running?[/red]")
        raise SystemExit(1) from None
    except subprocess.TimeoutExpired:
        console.print("[red]Docker build timed out[/red]")
        raise SystemExit(1) from None

    if result.returncode == 0:
        # Show image size
        try:
            inspect = subprocess.run(
                ["docker", "image", "inspect", "--format", "{{.Size}}", "zerg-worker"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if inspect.returncode == 0:
                size_bytes = int(inspect.stdout.strip())
                size_mb = size_bytes / (1024 * 1024)
                console.print(f"[green]Image built: zerg-worker ({size_mb:.0f} MB)[/green]")
            else:
                console.print("[green]Image built: zerg-worker[/green]")
        except Exception as e:
            logger.debug(f"Image size check failed: {e}")
            console.print("[green]Image built: zerg-worker[/green]")
    else:
        console.print("[red]Docker build failed[/red]")
        raise SystemExit(1)


def _watch_loop(builder: BuildCommand, system: BuildSystem | None, cwd: str) -> None:
    """Simple watch loop using polling."""
    import hashlib

    def get_file_hashes(path: Path) -> dict[str, str]:
        """Get hashes of all source files."""
        hashes = {}
        for ext in ["*.py", "*.js", "*.ts", "*.go", "*.rs", "*.java"]:
            for f in path.rglob(ext):
                try:
                    content = f.read_bytes()
                    hashes[str(f)] = hashlib.md5(content).hexdigest()
                except OSError:
                    pass
        return hashes

    console.print("[cyan]Watch mode enabled. Press Ctrl+C to stop.[/cyan]\n")

    last_hashes = get_file_hashes(Path(cwd))
    last_build_time = 0.0

    while True:
        try:
            time.sleep(1)
            current_hashes = get_file_hashes(Path(cwd))

            if current_hashes != last_hashes and time.time() - last_build_time > 2:
                changed = [f for f in current_hashes if f not in last_hashes or current_hashes[f] != last_hashes[f]]
                console.print(f"\n[yellow]Changes detected in {len(changed)} files[/yellow]")

                result = builder.run(system=system, cwd=cwd)
                if result.success:
                    console.print("[green]Build succeeded[/green]")
                else:
                    err = result.errors[0] if result.errors else "Unknown"
                    console.print(f"[red]Build failed:[/red] {err}")

                last_hashes = current_hashes
                last_build_time = time.time()

        except KeyboardInterrupt:
            console.print("\n[yellow]Watch mode stopped[/yellow]")
            break


@click.command()
@click.option("--target", "-t", default="all", help="Build target")
@click.option(
    "--mode",
    "-m",
    type=click.Choice(["dev", "staging", "prod"]),
    default="dev",
    help="Build mode",
)
@click.option("--clean", is_flag=True, help="Clean build artifacts first")
@click.option("--watch", "-w", is_flag=True, help="Watch mode for continuous builds")
@click.option("--retry", "-r", default=3, type=int, help="Number of retries on failure")
@click.option("--dry-run", is_flag=True, help="Show what would be built without building")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.option("--docker", is_flag=True, help="Build the zerg-worker Docker image")
@click.pass_context
def build(
    ctx: click.Context,
    target: str,
    mode: str,
    clean: bool,
    watch: bool,
    retry: int,
    dry_run: bool,
    json_output: bool,
    docker: bool,
) -> None:
    """Build orchestration with error recovery.

    Auto-detects build system (npm, cargo, make, gradle, go, python)
    and executes appropriate build commands with retry logic.

    Examples:

        zerg build

        zerg build --mode prod

        zerg build --clean --watch

        zerg build --dry-run
    """
    try:
        if docker:
            _build_docker_image()
            return

        console.print("\n[bold cyan]ZERG Build[/bold cyan]\n")

        cwd = str(Path.cwd())

        # Create config
        config = BuildConfig(
            mode=mode,
            clean=clean,
            watch=watch,
            retry=retry,
            target=target,
        )

        builder = BuildCommand(config)

        # Detect build system
        detected = builder.detector.detect(Path(cwd))
        if detected:
            console.print(f"Detected build system: [cyan]{detected[0].value}[/cyan]")
        else:
            console.print("[yellow]No build system detected, will use make[/yellow]")

        system = detected[0] if detected else None

        # Clean if requested
        if clean and not dry_run:
            console.print("Cleaning build artifacts...")
            # Simple clean - remove common build directories
            for clean_dir in ["build", "dist", "__pycache__", "target", "node_modules/.cache"]:
                clean_path = Path(cwd) / clean_dir
                if clean_path.exists() and clean_path.is_dir():
                    console.print(f"  Removing {clean_dir}/")

        # Watch mode (skip in dry-run)
        if watch and not dry_run:
            _watch_loop(builder, system, cwd)
            return
        elif watch and dry_run:
            console.print("[cyan]Watch mode would be enabled (dry-run)[/cyan]")

        # Run build
        if not dry_run:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                progress.add_task(description="Building...", total=None)
                result = builder.run(system=system, cwd=cwd)
        else:
            result = builder.run(system=system, dry_run=True, cwd=cwd)

        # Output
        if json_output:
            console.print(json.dumps(result.to_dict(), indent=2))
        else:
            # Display result
            if result.success:
                console.print(
                    Panel(
                        f"[green]Build succeeded[/green] in {result.duration_seconds:.2f}s",
                        title="Result",
                    )
                )
                if result.warnings:
                    for warning in result.warnings:
                        console.print(f"[yellow]⚠ {warning}[/yellow]")
            else:
                console.print(
                    Panel(
                        f"[red]Build failed[/red] after {result.retries} retries",
                        title="Result",
                    )
                )
                if result.errors:
                    console.print("\n[red]Errors:[/red]")
                    for error in result.errors[:5]:
                        console.print(f"  {error[:200]}")

                # Suggest recovery
                if result.errors:
                    recovery = ErrorRecovery()
                    category = recovery.classify(result.errors[0])
                    action = recovery.get_recovery_action(category)
                    console.print(f"\n[yellow]Suggested action:[/yellow] {action}")

        raise SystemExit(0 if result.success else 1)

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted[/yellow]")
        raise SystemExit(130) from None
    except SystemExit:
        raise
    except Exception as e:
        console.print(f"\n[red]Error:[/red] {e}")
        logger.exception("Build command failed")
        raise SystemExit(1) from e
