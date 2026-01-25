"""ZERG command-line interface."""

import click
from rich.console import Console

from zerg import __version__
from zerg.commands import cleanup, init, logs, merge_cmd, retry, rush, status, stop

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


# Register implemented commands
cli.add_command(cleanup)
cli.add_command(init)
cli.add_command(logs)
cli.add_command(merge_cmd)
cli.add_command(retry)
cli.add_command(rush)
cli.add_command(status)
cli.add_command(stop)


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


if __name__ == "__main__":
    cli()
