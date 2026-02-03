"""ZERG command-line interface."""

import click
from rich.console import Console

from zerg import __version__
from zerg.commands import (
    analyze,
    build,
    cleanup,
    debug,
    design,
    document,
    git_cmd,
    init,
    install_commands,
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
    uninstall_commands,
    wiki,
)

console = Console()


@click.group()
@click.version_option(version=__version__, prog_name="zerg")
@click.option("--quick", is_flag=True, help="Quick surface-level analysis")
@click.option("--think", is_flag=True, help="Structured multi-step analysis")
@click.option("--think-hard", is_flag=True, help="Deep architectural analysis")
@click.option("--ultrathink", is_flag=True, help="Maximum depth analysis")
@click.option("--no-compact", is_flag=True, default=False, help="Disable compact output (compact is ON by default)")
@click.option(
    "--mode",
    type=click.Choice(["precision", "speed", "exploration", "refactor", "debug"]),
    default=None,
    help="Behavioral execution mode",
)
@click.option("--mcp/--no-mcp", default=None, help="Enable/disable MCP auto-routing")
@click.option("--tdd", is_flag=True, help="Enable TDD enforcement mode")
@click.option("--no-loop", is_flag=True, default=False, help="Disable improvement loops (loops are ON by default)")
@click.option("--iterations", type=int, default=None, help="Override max loop iterations")
@click.pass_context
def cli(
    ctx: click.Context,
    quick: bool,
    think: bool,
    think_hard: bool,
    ultrathink: bool,
    no_compact: bool,
    mode: str | None,
    mcp: bool | None,
    tdd: bool,
    no_loop: bool,
    iterations: int | None,
) -> None:
    """ZERG - Parallel Claude Code execution system.

    Overwhelm features with coordinated worker instances.
    """
    ctx.ensure_object(dict)

    # Determine analysis depth (mutually exclusive flags)
    depth_flags = {
        "quick": quick,
        "think": think,
        "think_hard": think_hard,
        "ultrathink": ultrathink,
    }
    active = [k for k, v in depth_flags.items() if v]
    if len(active) > 1:
        raise click.UsageError("Depth flags are mutually exclusive: --quick, --think, --think-hard, --ultrathink")
    ctx.obj["depth"] = active[0] if active else "standard"

    # Compact: ON by default, --no-compact to disable
    ctx.obj["compact"] = not no_compact

    ctx.obj["mode"] = mode
    ctx.obj["mcp"] = mcp
    ctx.obj["tdd"] = tdd

    # Loops: ON by default, --no-loop to disable
    ctx.obj["loop"] = not no_loop
    ctx.obj["iterations"] = iterations


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
cli.add_command(debug)
cli.add_command(document)
cli.add_command(wiki)
cli.add_command(install_commands)
cli.add_command(uninstall_commands)


if __name__ == "__main__":
    cli()
