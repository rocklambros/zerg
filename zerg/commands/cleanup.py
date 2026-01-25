"""ZERG cleanup command - remove ZERG artifacts."""

import shutil
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from zerg.config import ZergConfig
from zerg.containers import ContainerManager
from zerg.git_ops import GitOps
from zerg.logging import get_logger
from zerg.worktree import WorktreeManager

console = Console()
logger = get_logger("cleanup")


@click.command()
@click.option("--feature", "-f", help="Feature to clean")
@click.option("--all", "all_features", is_flag=True, help="Clean all features")
@click.option("--keep-logs", is_flag=True, help="Preserve log files")
@click.option("--keep-branches", is_flag=True, help="Preserve git branches")
@click.option("--dry-run", is_flag=True, help="Show cleanup plan only")
@click.pass_context
def cleanup(
    ctx: click.Context,
    feature: str | None,
    all_features: bool,
    keep_logs: bool,
    keep_branches: bool,
    dry_run: bool,
) -> None:
    """Remove ZERG artifacts.

    Cleans worktrees, branches, containers, and logs.

    Examples:

        zerg cleanup --feature user-auth

        zerg cleanup --all

        zerg cleanup --all --keep-logs --dry-run
    """
    try:
        # Validate arguments
        if not feature and not all_features:
            console.print("[red]Error:[/red] Specify --feature or --all")
            raise SystemExit(1)

        console.print("\n[bold cyan]ZERG Cleanup[/bold cyan]\n")

        # Load config
        config = ZergConfig.load()

        # Get features to clean
        if all_features:
            features = discover_features()
        else:
            features = [feature] if feature else []

        if not features:
            console.print("[yellow]No features found to clean[/yellow]")
            return

        # Plan cleanup
        plan = create_cleanup_plan(features, keep_logs, keep_branches, config)

        # Show plan
        show_cleanup_plan(plan, dry_run)

        if dry_run:
            console.print("\n[dim]Dry run - no changes made[/dim]")
            return

        # Confirm
        if not click.confirm("\nProceed with cleanup?", default=False):
            console.print("[yellow]Aborted[/yellow]")
            return

        # Execute cleanup
        execute_cleanup(plan, config)

        console.print("\n[green]✓[/green] Cleanup complete")

    except Exception as e:
        console.print(f"\n[red]Error:[/red] {e}")
        raise SystemExit(1)


def discover_features() -> list[str]:
    """Discover all features with ZERG artifacts.

    Returns:
        List of feature names
    """
    features = set()

    # Check state files
    state_dir = Path(".zerg/state")
    if state_dir.exists():
        for state_file in state_dir.glob("*.json"):
            features.add(state_file.stem)

    # Check worktree directories
    worktree_dir = Path(".zerg/worktrees")
    if worktree_dir.exists():
        for wt_dir in worktree_dir.iterdir():
            if wt_dir.is_dir():
                # Extract feature from worktree name
                name = wt_dir.name
                if "-worker-" in name:
                    feature = name.rsplit("-worker-", 1)[0]
                    features.add(feature)

    # Check branches
    try:
        git = GitOps()
        branches = git.list_branches()
        for branch in branches:
            if branch.startswith("zerg/"):
                parts = branch.split("/")
                if len(parts) >= 2:
                    features.add(parts[1])
    except Exception:
        pass

    return sorted(features)


def create_cleanup_plan(
    features: list[str],
    keep_logs: bool,
    keep_branches: bool,
    config: ZergConfig,
) -> dict:
    """Create cleanup plan.

    Args:
        features: Features to clean
        keep_logs: Whether to keep logs
        keep_branches: Whether to keep branches
        config: Configuration

    Returns:
        Cleanup plan dict
    """
    plan = {
        "features": features,
        "worktrees": [],
        "branches": [],
        "containers": [],
        "state_files": [],
        "log_files": [],
        "dirs_to_remove": [],
    }

    for feature in features:
        # Find worktrees
        worktree_dir = Path(".zerg/worktrees")
        if worktree_dir.exists():
            for wt_dir in worktree_dir.glob(f"{feature}-worker-*"):
                plan["worktrees"].append(str(wt_dir))

        # Find branches
        if not keep_branches:
            try:
                git = GitOps()
                branches = git.list_branches()
                for branch in branches:
                    if branch.startswith(f"zerg/{feature}/"):
                        plan["branches"].append(branch)
            except Exception:
                pass

        # Find containers
        plan["containers"].append(f"zerg-worker-{feature}-*")

        # Find state files
        state_file = Path(f".zerg/state/{feature}.json")
        if state_file.exists():
            plan["state_files"].append(str(state_file))

        # Find log files
        if not keep_logs:
            log_dir = Path(".zerg/logs")
            if log_dir.exists():
                for log_file in log_dir.glob("*.log"):
                    plan["log_files"].append(str(log_file))

    return plan


def show_cleanup_plan(plan: dict, dry_run: bool) -> None:
    """Show cleanup plan.

    Args:
        plan: Cleanup plan
        dry_run: Whether dry run
    """
    title = "Cleanup Plan (DRY RUN)" if dry_run else "Cleanup Plan"
    table = Table(title=title)
    table.add_column("Category", style="cyan")
    table.add_column("Items")
    table.add_column("Count", justify="right")

    # Features
    table.add_row("Features", ", ".join(plan["features"]), str(len(plan["features"])))

    # Worktrees
    if plan["worktrees"]:
        table.add_row("Worktrees", "\n".join(plan["worktrees"][:3]) + ("..." if len(plan["worktrees"]) > 3 else ""), str(len(plan["worktrees"])))
    else:
        table.add_row("Worktrees", "-", "0")

    # Branches
    if plan["branches"]:
        table.add_row("Branches", "\n".join(plan["branches"][:3]) + ("..." if len(plan["branches"]) > 3 else ""), str(len(plan["branches"])))
    else:
        table.add_row("Branches", "-", "0")

    # Containers
    table.add_row("Container patterns", "\n".join(plan["containers"]), str(len(plan["containers"])))

    # State files
    if plan["state_files"]:
        table.add_row("State files", "\n".join(plan["state_files"]), str(len(plan["state_files"])))
    else:
        table.add_row("State files", "-", "0")

    # Log files
    if plan["log_files"]:
        table.add_row("Log files", f"{len(plan['log_files'])} files", str(len(plan["log_files"])))
    else:
        table.add_row("Log files", "[dim]keeping[/dim]", "-")

    console.print(table)


def execute_cleanup(plan: dict, config: ZergConfig) -> None:
    """Execute cleanup plan.

    Args:
        plan: Cleanup plan
        config: Configuration
    """
    errors = []

    # Remove worktrees
    console.print("\n[bold]Removing worktrees...[/bold]")
    worktree_mgr = WorktreeManager(config)
    for wt_path in plan["worktrees"]:
        try:
            wt_path_obj = Path(wt_path)
            if wt_path_obj.exists():
                worktree_mgr.remove(wt_path_obj)
                console.print(f"  [green]✓[/green] {wt_path}")
            else:
                console.print(f"  [dim]-[/dim] {wt_path} (not found)")
        except Exception as e:
            console.print(f"  [red]✗[/red] {wt_path}: {e}")
            errors.append(str(e))

    # Remove branches
    if plan["branches"]:
        console.print("\n[bold]Removing branches...[/bold]")
        git = GitOps()
        for branch in plan["branches"]:
            try:
                git.delete_branch(branch, force=True)
                console.print(f"  [green]✓[/green] {branch}")
            except Exception as e:
                console.print(f"  [red]✗[/red] {branch}: {e}")
                errors.append(str(e))

    # Stop containers
    console.print("\n[bold]Stopping containers...[/bold]")
    container_mgr = ContainerManager(config)
    for pattern in plan["containers"]:
        try:
            stopped = container_mgr.stop_matching(pattern)
            if stopped:
                console.print(f"  [green]✓[/green] Stopped {stopped} container(s) matching {pattern}")
            else:
                console.print(f"  [dim]-[/dim] No containers matching {pattern}")
        except Exception as e:
            console.print(f"  [yellow]![/yellow] {pattern}: {e}")

    # Remove state files
    if plan["state_files"]:
        console.print("\n[bold]Removing state files...[/bold]")
        for state_file in plan["state_files"]:
            try:
                Path(state_file).unlink()
                console.print(f"  [green]✓[/green] {state_file}")
            except Exception as e:
                console.print(f"  [red]✗[/red] {state_file}: {e}")
                errors.append(str(e))

    # Remove log files
    if plan["log_files"]:
        console.print("\n[bold]Removing log files...[/bold]")
        for log_file in plan["log_files"]:
            try:
                Path(log_file).unlink()
                console.print(f"  [green]✓[/green] {log_file}")
            except Exception as e:
                console.print(f"  [red]✗[/red] {log_file}: {e}")
                errors.append(str(e))

    if errors:
        console.print(f"\n[yellow]Completed with {len(errors)} error(s)[/yellow]")
