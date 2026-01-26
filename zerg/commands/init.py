"""ZERG init command - initialize ZERG for a project."""

import json
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from zerg.logging import get_logger
from zerg.security_rules import integrate_security_rules

console = Console()
logger = get_logger("init")

# Project type detection patterns
PROJECT_PATTERNS = {
    "python": ["pyproject.toml", "setup.py", "requirements.txt", "Pipfile"],
    "node": ["package.json", "yarn.lock", "pnpm-lock.yaml"],
    "rust": ["Cargo.toml"],
    "go": ["go.mod"],
    "java": ["pom.xml", "build.gradle", "build.gradle.kts"],
    "ruby": ["Gemfile"],
    "php": ["composer.json"],
    "dotnet": ["*.csproj", "*.fsproj", "*.sln"],
}


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
@click.option("--force", is_flag=True, help="Overwrite existing configuration")
@click.pass_context
def init(
    ctx: click.Context,
    detect: bool,
    workers: int,
    security: str,
    with_security_rules: bool,
    force: bool,
) -> None:
    """Initialize ZERG for the current project.

    Creates .zerg/ configuration and .devcontainer/ setup.

    Examples:

        zerg init

        zerg init --workers 3 --security strict

        zerg init --no-detect
    """
    try:
        console.print("\n[bold cyan]ZERG Init[/bold cyan]\n")

        # Check existing config
        zerg_dir = Path(".zerg")
        if zerg_dir.exists() and not force:
            console.print("[yellow]ZERG already initialized.[/yellow]")
            console.print("Use [cyan]--force[/cyan] to reinitialize.")
            return

        # Detect project type
        project_type = None
        if detect:
            project_type = detect_project_type()
            if project_type:
                console.print(f"Detected project type: [cyan]{project_type}[/cyan]")
            else:
                console.print("[dim]Could not detect project type[/dim]")

        # Create directory structure
        create_directory_structure()

        # Create configuration
        config = create_config(workers, security, project_type)
        save_config(config)

        # Create devcontainer if needed
        create_devcontainer(project_type, security)

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

        # Show summary
        show_summary(workers, security, project_type, security_rules_result)

        console.print("\n[green]✓[/green] ZERG initialized successfully!")
        console.print("\nNext steps:")
        console.print("  1. Run [cyan]zerg plan <feature>[/cyan] to capture requirements")
        console.print("  2. Run [cyan]zerg design[/cyan] to create task graph")
        console.print("  3. Run [cyan]zerg rush[/cyan] to start execution")

    except Exception as e:
        console.print(f"\n[red]Error:[/red] {e}")
        raise SystemExit(1) from e


def detect_project_type() -> str | None:
    """Detect project type from files.

    Returns:
        Project type string or None
    """
    cwd = Path(".")

    for project_type, patterns in PROJECT_PATTERNS.items():
        for pattern in patterns:
            if "*" in pattern:
                # Glob pattern
                if list(cwd.glob(pattern)):
                    return project_type
            else:
                # Exact file
                if (cwd / pattern).exists():
                    return project_type

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


def create_config(workers: int, security: str, project_type: str | None) -> dict:
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


def get_quality_gates(project_type: str | None) -> dict:
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


def get_default_mcp_servers() -> list[dict]:
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


def save_config(config: dict) -> None:
    """Save configuration to file.

    Args:
        config: Configuration dict
    """
    config_path = Path(".zerg/config.yaml")

    # Convert to YAML-like format
    import yaml

    try:
        with open(config_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    except ImportError:
        # Fallback to JSON if yaml not available
        config_path = Path(".zerg/config.json")
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)

    console.print(f"  [green]✓[/green] Created {config_path}")


def create_devcontainer(project_type: str | None, security: str) -> None:
    """Create devcontainer configuration.

    Args:
        project_type: Project type
        security: Security level
    """
    devcontainer_dir = Path(".devcontainer")
    devcontainer_dir.mkdir(exist_ok=True)

    # Base image based on project type
    images = {
        "python": "mcr.microsoft.com/devcontainers/python:3.12",
        "node": "mcr.microsoft.com/devcontainers/javascript-node:20",
        "rust": "mcr.microsoft.com/devcontainers/rust:latest",
        "go": "mcr.microsoft.com/devcontainers/go:latest",
    }

    base_image = images.get(project_type, "mcr.microsoft.com/devcontainers/base:ubuntu")

    # Devcontainer config
    devcontainer_config = {
        "name": "ZERG Worker",
        "image": base_image,
        "features": {
            "ghcr.io/devcontainers/features/git:1": {},
            "ghcr.io/devcontainers/features/github-cli:1": {},
        },
        "customizations": {
            "vscode": {
                "extensions": [
                    "anthropic.claude-code",
                ],
            },
        },
        "mounts": [
            "source=${localWorkspaceFolder},target=/workspace,type=bind",
        ],
        "workspaceFolder": "/workspace",
        "postCreateCommand": "echo 'ZERG worker ready'",
    }

    # Add security settings for strict mode
    if security == "strict":
        devcontainer_config["runArgs"] = [
            "--read-only",
            "--security-opt=no-new-privileges:true",
        ]

    # Write devcontainer.json
    devcontainer_path = devcontainer_dir / "devcontainer.json"
    with open(devcontainer_path, "w") as f:
        json.dump(devcontainer_config, f, indent=2)

    console.print(f"  [green]✓[/green] Created {devcontainer_path}")


def show_summary(
    workers: int,
    security: str,
    project_type: str | None,
    security_rules_result: dict | None = None,
) -> None:
    """Show initialization summary.

    Args:
        workers: Worker count
        security: Security level
        project_type: Project type
        security_rules_result: Results from security rules integration
    """
    table = Table(title="ZERG Configuration", show_header=False)
    table.add_column("Setting", style="cyan")
    table.add_column("Value")

    table.add_row("Project Type", project_type or "unknown")
    table.add_row("Default Workers", str(workers))
    table.add_row("Security Level", security)
    table.add_row("Config Location", ".zerg/config.yaml")
    table.add_row("Devcontainer", ".devcontainer/devcontainer.json")

    if security_rules_result:
        stack = security_rules_result.get("stack", {})
        languages = ", ".join(stack.get("languages", [])) or "none"
        frameworks = ", ".join(stack.get("frameworks", [])) or "none"
        table.add_row("Security Rules", f"{security_rules_result['rules_fetched']} files")
        table.add_row("Detected Languages", languages)
        table.add_row("Detected Frameworks", frameworks)

    console.print()
    console.print(table)
