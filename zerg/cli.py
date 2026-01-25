"""ZERG command-line interface."""

import click
from rich.console import Console

from zerg import __version__

console = Console()


@click.group()
@click.version_option(version=__version__, prog_name="zerg")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option("--quiet", "-q", is_flag=True, help="Suppress non-essential output")
@click.pass_context
def cli(ctx: click.Context, verbose: bool, quiet: bool) -> None:
    """ZERG - Parallel Claude Code execution system.

    Overwhelm features with coordinated worker instances.
    """
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["quiet"] = quiet


@cli.command()
@click.option("--detect/--no-detect", default=True, help="Auto-detect project type")
@click.option("--workers", "-w", default=5, type=int, help="Default worker count")
@click.option(
    "--security",
    type=click.Choice(["minimal", "standard", "strict"]),
    default="standard",
    help="Security level",
)
@click.pass_context
def init(ctx: click.Context, detect: bool, workers: int, security: str) -> None:
    """Initialize ZERG for the current project.

    Creates .zerg/ configuration and .devcontainer/ setup.
    """
    console.print("[yellow]Init command not yet implemented[/yellow]")


@cli.command()
@click.argument("feature", required=False)
@click.option("--template", "-t", default="default", help="Requirements template")
@click.option("--interactive/--no-interactive", default=True, help="Interactive mode")
@click.option("--from-issue", help="Import from GitHub issue URL")
@click.pass_context
def plan(
    ctx: click.Context,
    feature: str | None,
    template: str,
    interactive: bool,
    from_issue: str | None,
) -> None:
    """Capture feature requirements.

    Creates .gsd/specs/{feature}/requirements.md
    """
    console.print("[yellow]Plan command not yet implemented[/yellow]")


@cli.command()
@click.option("--max-task-minutes", default=30, type=int, help="Maximum minutes per task")
@click.option("--min-task-minutes", default=5, type=int, help="Minimum minutes per task")
@click.option("--validate-only", is_flag=True, help="Validate existing graph only")
@click.pass_context
def design(
    ctx: click.Context,
    max_task_minutes: int,
    min_task_minutes: int,
    validate_only: bool,
) -> None:
    """Generate architecture and task graph.

    Creates .gsd/specs/{feature}/design.md and task-graph.json
    """
    console.print("[yellow]Design command not yet implemented[/yellow]")


@cli.command()
@click.option("--workers", "-w", default=5, type=int, help="Number of workers")
@click.option("--feature", "-f", help="Feature to execute")
@click.option("--level", "-l", type=int, help="Start from specific level")
@click.option("--dry-run", is_flag=True, help="Show plan without executing")
@click.option("--resume", is_flag=True, help="Continue from previous run")
@click.option("--timeout", default=3600, type=int, help="Max execution time (seconds)")
@click.pass_context
def rush(
    ctx: click.Context,
    workers: int,
    feature: str | None,
    level: int | None,
    dry_run: bool,
    resume: bool,
    timeout: int,
) -> None:
    """Launch parallel worker execution.

    Spawns workers, assigns tasks, and monitors progress.
    """
    console.print("[yellow]Rush command not yet implemented[/yellow]")


@cli.command()
@click.option("--feature", "-f", help="Feature to show status for")
@click.option("--watch", "-w", is_flag=True, help="Continuous update mode")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.option("--level", "-l", type=int, help="Filter to specific level")
@click.pass_context
def status(
    ctx: click.Context,
    feature: str | None,
    watch: bool,
    json_output: bool,
    level: int | None,
) -> None:
    """Show execution progress.

    Displays worker status, level progress, and recent events.
    """
    console.print("[yellow]Status command not yet implemented[/yellow]")


@cli.command()
@click.option("--feature", "-f", help="Feature to stop")
@click.option("--worker", "-w", type=int, help="Specific worker ID")
@click.option("--force", is_flag=True, help="Kill without cleanup")
@click.option("--no-checkpoint", is_flag=True, help="Skip WIP commit")
@click.pass_context
def stop(
    ctx: click.Context,
    feature: str | None,
    worker: int | None,
    force: bool,
    no_checkpoint: bool,
) -> None:
    """Stop workers gracefully.

    Checkpoints in-progress work and stops containers.
    """
    console.print("[yellow]Stop command not yet implemented[/yellow]")


@cli.command()
@click.argument("task_id", required=False)
@click.option("--feature", "-f", help="Feature name")
@click.option("--all-failed", is_flag=True, help="Retry all failed tasks")
@click.option("--reset", is_flag=True, help="Reset task to fresh state")
@click.option("--worker", "-w", type=int, help="Assign to specific worker")
@click.pass_context
def retry(
    ctx: click.Context,
    task_id: str | None,
    feature: str | None,
    all_failed: bool,
    reset: bool,
    worker: int | None,
) -> None:
    """Retry failed or blocked tasks.

    Re-queues tasks for execution.
    """
    console.print("[yellow]Retry command not yet implemented[/yellow]")


@cli.command()
@click.argument("worker_id", required=False, type=int)
@click.option("--feature", "-f", help="Feature name")
@click.option("--tail", "-n", default=100, type=int, help="Lines to show")
@click.option("--follow", is_flag=True, help="Stream new logs")
@click.option(
    "--level",
    type=click.Choice(["debug", "info", "warn", "error"]),
    default="info",
    help="Log level filter",
)
@click.pass_context
def logs(
    ctx: click.Context,
    worker_id: int | None,
    feature: str | None,
    tail: int,
    follow: bool,
    level: str,
) -> None:
    """Stream worker logs.

    Shows logs from workers with optional filtering.
    """
    console.print("[yellow]Logs command not yet implemented[/yellow]")


@cli.command()
@click.option("--feature", "-f", help="Feature to merge")
@click.option("--level", "-l", type=int, help="Level to merge")
@click.option("--target", "-t", help="Target branch")
@click.option("--skip-gates", is_flag=True, help="Skip quality gates")
@click.option("--dry-run", is_flag=True, help="Show merge plan only")
@click.pass_context
def merge(
    ctx: click.Context,
    feature: str | None,
    level: int | None,
    target: str | None,
    skip_gates: bool,
    dry_run: bool,
) -> None:
    """Trigger merge gate execution.

    Merges worker branches after quality gates pass.
    """
    console.print("[yellow]Merge command not yet implemented[/yellow]")


@cli.command()
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
    """
    console.print("[yellow]Cleanup command not yet implemented[/yellow]")


if __name__ == "__main__":
    cli()
