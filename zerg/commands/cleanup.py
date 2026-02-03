"""ZERG cleanup command - remove ZERG artifacts."""

import fnmatch
import shutil
import time
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.table import Table

from zerg.config import ZergConfig
from zerg.constants import GSD_DIR, SPECS_DIR
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
@click.option(
    "--logs",
    "logs_only",
    is_flag=True,
    help="Clean only structured logs (task artifacts and rotated worker logs)",
)
@click.pass_context
def cleanup(
    ctx: click.Context,
    feature: str | None,
    all_features: bool,
    keep_logs: bool,
    keep_branches: bool,
    dry_run: bool,
    logs_only: bool,
) -> None:
    """Remove ZERG artifacts.

    Cleans worktrees, branches, containers, and logs.

    Examples:

        zerg cleanup --feature user-auth

        zerg cleanup --all

        zerg cleanup --all --keep-logs --dry-run

        zerg cleanup --logs
    """
    try:
        # Handle --logs mode (standalone log cleanup)
        if logs_only:
            config = ZergConfig.load()
            cleanup_structured_logs(config, dry_run)
            return

        # Validate arguments
        if not feature and not all_features:
            console.print("[red]Error:[/red] Specify --feature or --all")
            raise SystemExit(1)

        console.print("\n[bold cyan]ZERG Cleanup[/bold cyan]\n")

        # Load config
        config = ZergConfig.load()

        # Get features to clean
        features = discover_features() if all_features else [feature] if feature else []

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
        raise SystemExit(1) from None


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
            if branch.name.startswith("zerg/"):
                parts = branch.name.split("/")
                if len(parts) >= 2:
                    features.add(parts[1])
    except Exception as e:
        logger.debug(f"Branch listing failed: {e}")

    return sorted(features)


def create_cleanup_plan(
    features: list[str],
    keep_logs: bool,
    keep_branches: bool,
    config: ZergConfig,
) -> dict[str, Any]:
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
                    if branch.name.startswith(f"zerg/{feature}/"):
                        plan["branches"].append(branch.name)
            except Exception as e:
                logger.debug(f"Container listing failed: {e}")

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


def show_cleanup_plan(plan: dict[str, Any], dry_run: bool) -> None:
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
        wt_preview = "\n".join(plan["worktrees"][:3])
        wt_suffix = "..." if len(plan["worktrees"]) > 3 else ""
        table.add_row(
            "Worktrees",
            wt_preview + wt_suffix,
            str(len(plan["worktrees"])),
        )
    else:
        table.add_row("Worktrees", "-", "0")

    # Branches
    if plan["branches"]:
        br_preview = "\n".join(plan["branches"][:3])
        br_suffix = "..." if len(plan["branches"]) > 3 else ""
        table.add_row(
            "Branches",
            br_preview + br_suffix,
            str(len(plan["branches"])),
        )
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


def execute_cleanup(plan: dict[str, Any], config: ZergConfig) -> None:
    """Execute cleanup plan.

    Args:
        plan: Cleanup plan
        config: Configuration
    """
    errors = []

    # Remove worktrees
    console.print("\n[bold]Removing worktrees...[/bold]")
    worktree_mgr = WorktreeManager()
    for wt_path in plan["worktrees"]:
        try:
            wt_path_obj = Path(wt_path)
            if wt_path_obj.exists():
                worktree_mgr.delete(wt_path_obj)
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
            all_containers = container_mgr.get_all_containers()
            stopped = 0
            for worker_id, info in all_containers.items():
                if fnmatch.fnmatch(info.name, pattern):
                    container_mgr.stop_worker(worker_id)
                    stopped += 1
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

    # Remove spec directories for cleaned features
    for feature in plan["features"]:
        spec_dir = Path(SPECS_DIR) / feature
        if spec_dir.exists():
            try:
                shutil.rmtree(spec_dir)
                console.print(f"  [green]✓[/green] Removed spec dir {spec_dir}")
            except Exception as e:
                console.print(f"  [red]✗[/red] {spec_dir}: {e}")
                errors.append(str(e))

    # Clear .current-feature if it points to a cleaned feature
    current_feature_file = Path(GSD_DIR) / ".current-feature"
    if current_feature_file.exists():
        try:
            current = current_feature_file.read_text().strip()
            if current in plan["features"]:
                current_feature_file.unlink()
                console.print("  [green]✓[/green] Cleared active feature pointer")
        except Exception as e:
            console.print(f"  [red]✗[/red] .current-feature: {e}")
            errors.append(str(e))

    if errors:
        console.print(f"\n[yellow]Completed with {len(errors)} error(s)[/yellow]")


def cleanup_structured_logs(config: ZergConfig, dry_run: bool = False) -> None:
    """Clean up structured log artifacts based on retention policy.

    Prunes task artifact directories based on config.logging retention settings.
    Rotates/removes old worker JSONL files based on retain_days.

    Args:
        config: ZergConfig with logging settings
        dry_run: If True, only show what would be cleaned
    """
    console.print("\n[bold cyan]ZERG Log Cleanup[/bold cyan]\n")

    log_dir = Path(config.logging.directory)
    tasks_dir = log_dir / "tasks"
    workers_dir = log_dir / "workers"
    retain_days = config.logging.retain_days

    cleaned_tasks = 0
    cleaned_workers = 0
    errors = []

    # Clean task artifact directories
    if tasks_dir.exists():
        console.print("[bold]Task artifacts:[/bold]")
        cutoff_time = time.time() - (retain_days * 86400)

        for task_dir in sorted(tasks_dir.iterdir()):
            if not task_dir.is_dir():
                continue

            # Check modification time
            dir_mtime = task_dir.stat().st_mtime
            if dir_mtime < cutoff_time:
                if dry_run:
                    console.print(f"  [dim]Would remove:[/dim] {task_dir.name}")
                else:
                    try:
                        shutil.rmtree(task_dir)
                        console.print(f"  [green]Removed:[/green] {task_dir.name}")
                    except OSError as e:
                        console.print(f"  [red]Error:[/red] {task_dir.name}: {e}")
                        errors.append(str(e))
                cleaned_tasks += 1

        if cleaned_tasks == 0:
            console.print("  [dim]No task artifacts to clean[/dim]")

    # Clean/rotate worker JSONL files
    if workers_dir.exists():
        console.print("\n[bold]Worker JSONL files:[/bold]")
        cutoff_time = time.time() - (retain_days * 86400)

        for jsonl_file in sorted(workers_dir.glob("*.jsonl*")):
            file_mtime = jsonl_file.stat().st_mtime

            should_clean = False
            reason = ""

            if file_mtime < cutoff_time:
                should_clean = True
                reason = f"older than {retain_days} days"
            elif jsonl_file.suffix == ".1":
                # Rotated files older than retain_days
                if file_mtime < cutoff_time:
                    should_clean = True
                    reason = "rotated file, expired"

            if should_clean:
                if dry_run:
                    console.print(f"  [dim]Would remove:[/dim] {jsonl_file.name} ({reason})")
                else:
                    try:
                        jsonl_file.unlink()
                        console.print(f"  [green]Removed:[/green] {jsonl_file.name} ({reason})")
                    except OSError as e:
                        console.print(f"  [red]Error:[/red] {jsonl_file.name}: {e}")
                        errors.append(str(e))
                cleaned_workers += 1

        if cleaned_workers == 0:
            console.print("  [dim]No worker logs to clean[/dim]")

    # Also clean orchestrator.jsonl if old
    orchestrator_file = log_dir / "orchestrator.jsonl"
    if orchestrator_file.exists():
        cutoff_time = time.time() - (retain_days * 86400)
        if orchestrator_file.stat().st_mtime < cutoff_time:
            if dry_run:
                console.print("\n  [dim]Would remove:[/dim] orchestrator.jsonl")
            else:
                try:
                    orchestrator_file.unlink()
                    console.print("\n  [green]Removed:[/green] orchestrator.jsonl")
                except OSError as e:
                    errors.append(str(e))

    if dry_run:
        console.print(
            f"\n[dim]Dry run: {cleaned_tasks} task dirs, {cleaned_workers} worker files would be cleaned[/dim]"
        )
    else:
        console.print(
            f"\n[green]Log cleanup complete:[/green] {cleaned_tasks} task dirs, {cleaned_workers} worker files"
        )

    if errors:
        console.print(f"[yellow]{len(errors)} error(s) during cleanup[/yellow]")
