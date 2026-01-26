"""ZERG command-line interface."""

import click
from rich.console import Console

from zerg import __version__
from zerg.commands import (
    analyze,
    build,
    cleanup,
    design,
    git_cmd,
    init,
    logs,
    merge_cmd,
    plan,
    refactor,
    retry,
    review,
    rush,
    security_rules_group,
    status,
    stop,
    test_cmd,
    troubleshoot,
)

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
cli.add_command(analyze)
cli.add_command(build)
cli.add_command(cleanup)
cli.add_command(design)
cli.add_command(git_cmd, name="git")
cli.add_command(init)
cli.add_command(logs)
cli.add_command(merge_cmd)
cli.add_command(plan)
cli.add_command(refactor)
cli.add_command(retry)
cli.add_command(review)
cli.add_command(rush)
cli.add_command(security_rules_group)
cli.add_command(status)
cli.add_command(stop)
cli.add_command(test_cmd, name="test")
cli.add_command(troubleshoot)


if __name__ == "__main__":
    cli()
