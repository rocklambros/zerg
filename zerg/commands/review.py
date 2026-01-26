"""ZERG review command - two-stage code review workflow."""

import click
from rich.console import Console

from zerg.logging import get_logger

console = Console()
logger = get_logger("review")


@click.command()
@click.option(
    "--mode",
    "-m",
    type=click.Choice(["prepare", "self", "receive", "full"]),
    default="full",
    help="Review mode",
)
@click.option("--files", "-f", help="Specific files to review")
@click.option("--output", "-o", help="Output file for review results")
@click.pass_context
def review(
    ctx: click.Context,
    mode: str,
    files: str | None,
    output: str | None,
) -> None:
    """Two-stage code review workflow.

    Modes:
    - prepare: Generate change summary and review checklist
    - self: Self-review checklist
    - receive: Process review feedback
    - full: Complete two-stage review (spec + quality)

    Examples:

        zerg review

        zerg review --mode prepare

        zerg review --mode self
    """
    console.print("[yellow]review command not yet implemented[/yellow]")
    raise SystemExit(1)
