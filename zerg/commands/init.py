"""ZERG init command - initialize ZERG for a project."""

import json
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.table import Table

from zerg.devcontainer_features import DynamicDevcontainerGenerator
from zerg.logging import get_logger
from zerg.security_rules import ProjectStack, detect_project_stack, integrate_security_rules

console = Console()
logger = get_logger("init")


# Files/directories that indicate an existing project (not empty)
PROJECT_INDICATORS = {
    # Version control
    ".git",
    # Python
    "pyproject.toml",
    "setup.py",
    "requirements.txt",
    "Pipfile",
    # JavaScript/TypeScript
    "package.json",
    "tsconfig.json",
    # Go
    "go.mod",
    # Rust
    "Cargo.toml",
    # Java
    "pom.xml",
    "build.gradle",
    # Ruby
    "Gemfile",
    # C#
    "*.csproj",
    "*.sln",
    # Source directories
    "src",
    "lib",
    "app",
}


def is_empty_project(path: Path | None = None) -> bool:
    """Check if the current directory is an empty project (no code/config files).

    An "empty project" means no recognizable project structure exists yet.
    This determines whether to run Inception Mode (create from scratch) vs
    Discovery Mode (analyze existing project).

    Args:
        path: Directory to check. Defaults to current working directory.

    Returns:
        True if the directory is empty or has no project indicators.
    """
    path = path or Path(".")

    # Check if directory exists
    if not path.exists():
        return True

    # Check if directory is completely empty
    entries = list(path.iterdir())
    if not entries:
        return True

    # Check for project indicators
    for indicator in PROJECT_INDICATORS:
        if "*" in indicator:
            # Glob pattern (e.g., "*.csproj")
            if list(path.glob(indicator)):
                return False
        else:
            # Direct path check
            if (path / indicator).exists():
                return False

    # Check for any source code files
    code_extensions = {".py", ".js", ".ts", ".go", ".rs", ".java", ".rb", ".cs", ".cpp", ".c"}
    return all(not (entry.is_file() and entry.suffix in code_extensions) for entry in entries)


@click.command()
@click.option("--detect/--no-detect", default=True, help="Auto-detect project type")
@click.option("--workers", "-w", default=5, type=int, help="Default worker count")
@click.option(
    "--security",
    type=click.Choice(["minimal", "standard", "strict"]),
    default="standard",
    help="Security level",
)
@click.option(
    "--with-security-rules/--no-security-rules",
    default=True,
    help="Fetch secure coding rules from TikiTribe/claude-secure-coding-rules",
)
@click.option(
    "--with-containers/--no-containers",
    default=False,
    help="Build devcontainer image after creating files",
)
@click.option("--force", is_flag=True, help="Overwrite existing configuration")
@click.pass_context
def init(
    ctx: click.Context,
    detect: bool,
    workers: int,
    security: str,
    with_security_rules: bool,
    with_containers: bool,
    force: bool,
) -> None:
    """Initialize ZERG for the current project.

    Creates .zerg/ configuration and .devcontainer/ setup.

    Operates in two modes:
    - **Inception Mode**: For empty directories - creates project from scratch
    - **Discovery Mode**: For existing projects - analyzes and configures ZERG

    Examples:

        zerg init

        zerg init --workers 3 --security strict

        zerg init --no-detect
    """
    try:
        # Check if this is an empty directory (Inception Mode)
        if is_empty_project():
            console.print("\n[bold cyan]ZERG Init - Inception Mode[/bold cyan]")
            console.print("[dim]Empty directory detected. Starting new project wizard...[/dim]\n")

            # Import and run inception mode
            from zerg.inception import run_inception_mode

            success = run_inception_mode(security_level=security)
            if not success:
                raise SystemExit(1)

            # After inception, continue with ZERG setup
            console.print("\n[bold]Configuring ZERG infrastructure...[/bold]")

        console.print("\n[bold cyan]ZERG Init - Discovery Mode[/bold cyan]\n")

        # Check existing config
        zerg_dir = Path(".zerg")
        if zerg_dir.exists() and not force:
            console.print("[yellow]ZERG already initialized.[/yellow]")
            console.print("Use [cyan]--force[/cyan] to reinitialize.")
            return

        # Detect project stack (multi-language)
        stack: ProjectStack | None = None
        if detect:
            stack = detect_project_type()
            if stack:
                langs = ", ".join(sorted(stack.languages))
                console.print(f"Detected languages: [cyan]{langs}[/cyan]")
                if stack.frameworks:
                    frameworks = ", ".join(sorted(stack.frameworks))
                    console.print(f"Detected frameworks: [cyan]{frameworks}[/cyan]")
            else:
                console.print("[dim]Could not detect project type[/dim]")

        # Create directory structure
        create_directory_structure()

        # Get primary language for config (backwards compatibility)
        primary_lang = get_primary_language(stack) if stack else None

        # Create configuration
        config = create_config(workers, security, primary_lang)
        save_config(config)

        # Create devcontainer with multi-language support
        create_devcontainer(stack, security)

        # Integrate secure coding rules if requested
        security_rules_result = None
        if with_security_rules:
            console.print("\n[bold]Integrating secure coding rules...[/bold]")
            try:
                security_rules_result = integrate_security_rules(
                    project_path=Path("."),
                    update_claude_md=True,
                )
                console.print(
                    f"  [green]✓[/green] Fetched {security_rules_result['rules_fetched']} "
                    f"security rules for detected stack"
                )
            except Exception as e:
                console.print(f"  [yellow]⚠[/yellow] Could not fetch security rules: {e}")

        # Build devcontainer if requested
        container_built = False
        if with_containers:
            console.print("\n[bold]Building devcontainer...[/bold]")
            container_built = build_devcontainer()

        # Show summary
        show_summary(
            workers,
            security,
            stack,
            security_rules_result,
            container_built=container_built,
        )

        # Auto-install slash commands globally if not present
        from zerg.commands.install_commands import auto_install_commands

        auto_install_commands()

        console.print("\n[green]✓[/green] ZERG initialized successfully!")
        console.print("\nNext steps:")
        console.print("  1. Run [cyan]zerg plan <feature>[/cyan] to capture requirements")
        console.print("  2. Run [cyan]zerg design[/cyan] to create task graph")
        console.print("  3. Run [cyan]zerg rush[/cyan] to start execution")

    except Exception as e:
        console.print(f"\n[red]Error:[/red] {e}")
        raise SystemExit(1) from e


def detect_project_type() -> ProjectStack | None:
    """Detect project type from files using comprehensive stack detection.

    Returns:
        ProjectStack with detected languages, frameworks, etc.
    """
    cwd = Path(".")
    stack = detect_project_stack(cwd)

    # Return None if no languages detected
    if not stack.languages:
        return None

    return stack


def get_primary_language(stack: ProjectStack) -> str | None:
    """Get the primary language from a ProjectStack for config purposes.

    Args:
        stack: Detected project stack

    Returns:
        Primary language string or None
    """
    # Priority order for primary language
    priority = ["python", "typescript", "javascript", "go", "rust", "java", "ruby", "csharp"]

    for lang in priority:
        if lang in stack.languages:
            return lang

    # Return first detected if not in priority list
    if stack.languages:
        return next(iter(stack.languages))

    return None


def create_directory_structure() -> None:
    """Create ZERG directory structure."""
    dirs = [
        ".zerg",
        ".zerg/state",
        ".zerg/logs",
        ".zerg/worktrees",
        ".zerg/hooks",
        ".gsd",
        ".gsd/specs",
        ".gsd/tasks",
    ]

    for dir_path in dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
        console.print(f"  [green]✓[/green] Created {dir_path}/")


def create_config(workers: int, security: str, project_type: str | None) -> dict[str, Any]:
    """Create configuration dictionary.

    Args:
        workers: Default worker count
        security: Security level
        project_type: Detected project type

    Returns:
        Configuration dict
    """
    # Security settings
    security_settings = {
        "minimal": {
            "network_isolation": False,
            "filesystem_sandbox": False,
            "secrets_scanning": False,
        },
        "standard": {
            "network_isolation": True,
            "filesystem_sandbox": True,
            "secrets_scanning": True,
        },
        "strict": {
            "network_isolation": True,
            "filesystem_sandbox": True,
            "secrets_scanning": True,
            "read_only_root": True,
            "no_new_privileges": True,
        },
    }

    # Quality gates based on project type
    quality_gates = get_quality_gates(project_type)

    return {
        "version": "1.0",
        "project_type": project_type or "unknown",
        "workers": {
            "default_count": workers,
            "max_count": 10,
            "context_threshold": 0.7,
            "timeout_seconds": 3600,
        },
        "security": security_settings.get(security, security_settings["standard"]),
        "quality_gates": quality_gates,
        "mcp_servers": get_default_mcp_servers(),
    }


def get_quality_gates(project_type: str | None) -> dict[str, Any]:
    """Get quality gates for project type.

    Args:
        project_type: Project type

    Returns:
        Quality gates config
    """
    # Default gates
    gates = {
        "lint": {"command": "echo 'No lint configured'", "required": False},
        "test": {"command": "echo 'No tests configured'", "required": False},
        "build": {"command": "echo 'No build configured'", "required": False},
    }

    if project_type == "python":
        gates = {
            "lint": {"command": "ruff check .", "required": True},
            "typecheck": {"command": "mypy .", "required": False},
            "test": {"command": "pytest", "required": True},
        }
    elif project_type == "node":
        gates = {
            "lint": {"command": "npm run lint", "required": True},
            "test": {"command": "npm test", "required": True},
            "build": {"command": "npm run build", "required": False},
        }
    elif project_type == "rust":
        gates = {
            "lint": {"command": "cargo clippy", "required": True},
            "test": {"command": "cargo test", "required": True},
            "build": {"command": "cargo build", "required": True},
        }
    elif project_type == "go":
        gates = {
            "lint": {"command": "golangci-lint run", "required": True},
            "test": {"command": "go test ./...", "required": True},
            "build": {"command": "go build ./...", "required": True},
        }

    return gates


def get_default_mcp_servers() -> list[dict[str, Any]]:
    """Get default MCP server configuration.

    Returns:
        List of MCP server configs
    """
    return [
        {
            "name": "filesystem",
            "command": "npx",
            "args": ["-y", "@anthropic/mcp-filesystem"],
            "env": {},
        },
    ]


def save_config(config: dict[str, Any]) -> None:
    """Save configuration to file.

    Args:
        config: Configuration dict
    """
    config_path = Path(".zerg/config.yaml")

    # Convert to YAML-like format
    import yaml  # type: ignore[import-untyped]

    try:
        with open(config_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    except ImportError:
        # Fallback to JSON if yaml not available
        config_path = Path(".zerg/config.json")
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)

    console.print(f"  [green]✓[/green] Created {config_path}")


def create_devcontainer(stack: ProjectStack | None, security: str) -> None:
    """Create devcontainer configuration with multi-language support.

    Args:
        stack: Detected project stack (or None for generic container)
        security: Security level (minimal, standard, strict)
    """
    # Get languages from stack or use empty set
    languages = stack.languages if stack else set()

    # Use dynamic generator for multi-language support
    generator = DynamicDevcontainerGenerator(
        name="ZERG Worker",
        install_claude=True,
    )

    # Generate devcontainer.json
    devcontainer_path = generator.write_devcontainer(
        languages=languages,
        security_level=security,
    )

    # Also generate worker entry script
    generator.generate_worker_entry_script()

    console.print(f"  [green]✓[/green] Created {devcontainer_path}")
    console.print("  [green]✓[/green] Created .zerg/worker_entry.sh")


def build_devcontainer() -> bool:
    """Build the devcontainer image.

    Returns:
        True if build succeeded
    """
    import subprocess

    devcontainer_dir = Path(".devcontainer")
    if not devcontainer_dir.exists():
        console.print("  [red]✗[/red] No .devcontainer directory found")
        return False

    # Check if Docker is available
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            console.print("  [red]✗[/red] Docker is not running")
            console.print("  [dim]Start Docker and try again[/dim]")
            return False
    except FileNotFoundError:
        console.print("  [red]✗[/red] Docker not found")
        console.print("  [dim]Install Docker to use container mode[/dim]")
        return False
    except subprocess.TimeoutExpired:
        console.print("  [red]✗[/red] Docker not responding")
        return False

    # Check for devcontainer CLI
    devcontainer_cli = None
    try:
        result = subprocess.run(
            ["devcontainer", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            devcontainer_cli = "devcontainer"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Build using devcontainer CLI if available
    if devcontainer_cli:
        console.print("  [dim]Using devcontainer CLI...[/dim]")
        try:
            result = subprocess.run(
                ["devcontainer", "build", "--workspace-folder", "."],
                capture_output=True,
                text=True,
                timeout=600,  # 10 minutes
            )
            if result.returncode == 0:
                console.print("  [green]✓[/green] Devcontainer built successfully")
                return True
            else:
                console.print(f"  [red]✗[/red] Build failed: {result.stderr[:200]}")
                return False
        except subprocess.TimeoutExpired:
            console.print("  [red]✗[/red] Build timed out (10 min)")
            return False

    # Fall back to docker-compose if available
    compose_file = devcontainer_dir / "docker-compose.yaml"
    if compose_file.exists():
        console.print("  [dim]Using docker-compose...[/dim]")
        try:
            result = subprocess.run(
                ["docker", "compose", "-f", str(compose_file), "build"],
                capture_output=True,
                text=True,
                timeout=600,
            )
            if result.returncode == 0:
                console.print("  [green]✓[/green] Container image built successfully")
                return True
            else:
                console.print(f"  [red]✗[/red] Build failed: {result.stderr[:200]}")
                return False
        except subprocess.TimeoutExpired:
            console.print("  [red]✗[/red] Build timed out (10 min)")
            return False

    # Fall back to plain docker build
    dockerfile = devcontainer_dir / "Dockerfile"
    if dockerfile.exists():
        console.print("  [dim]Using docker build...[/dim]")
        try:
            result = subprocess.run(
                ["docker", "build", "-t", "zerg-worker", "-f", str(dockerfile), "."],
                capture_output=True,
                text=True,
                timeout=600,
            )
            if result.returncode == 0:
                console.print("  [green]✓[/green] Docker image built successfully")
                return True
            else:
                console.print(f"  [red]✗[/red] Build failed: {result.stderr[:200]}")
                return False
        except subprocess.TimeoutExpired:
            console.print("  [red]✗[/red] Build timed out (10 min)")
            return False

    console.print("  [yellow]⚠[/yellow] No Dockerfile found to build")
    return False


def show_summary(
    workers: int,
    security: str,
    stack: ProjectStack | None,
    security_rules_result: dict[str, Any] | None = None,
    container_built: bool = False,
) -> None:
    """Show initialization summary.

    Args:
        workers: Worker count
        security: Security level
        stack: Detected project stack
        security_rules_result: Results from security rules integration
        container_built: Whether container was built
    """
    table = Table(title="ZERG Configuration", show_header=False)
    table.add_column("Setting", style="cyan")
    table.add_column("Value")

    # Show detected languages
    if stack and stack.languages:
        languages = ", ".join(sorted(stack.languages))
        table.add_row("Languages", languages)
    else:
        table.add_row("Languages", "unknown")

    # Show detected frameworks
    if stack and stack.frameworks:
        frameworks = ", ".join(sorted(stack.frameworks))
        table.add_row("Frameworks", frameworks)

    table.add_row("Default Workers", str(workers))
    table.add_row("Security Level", security)
    table.add_row("Config Location", ".zerg/config.yaml")
    table.add_row("Devcontainer", ".devcontainer/devcontainer.json")
    if container_built:
        table.add_row("Container Image", "[green]Built[/green]")

    if security_rules_result:
        table.add_row("Security Rules", f"{security_rules_result['rules_fetched']} files")

    console.print()
    console.print(table)
