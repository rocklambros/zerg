"""CLI command for security rules integration."""

import json
from pathlib import Path

import click

from zerg.logging import get_logger
from zerg.security_rules import (
    detect_project_stack,
    fetch_rules,
    get_required_rules,
    integrate_security_rules,
)

logger = get_logger(__name__)


@click.group(name="security-rules")
def security_rules_group() -> None:
    """Manage secure coding rules from TikiTribe/claude-secure-coding-rules."""
    pass


@security_rules_group.command(name="detect")
@click.option(
    "--path",
    "-p",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    help="Project path to analyze",
)
@click.option("--json-output", "-j", is_flag=True, help="Output as JSON")
def detect_command(path: Path, json_output: bool) -> None:
    """Detect project technology stack."""
    import logging

    # Suppress log output when JSON output is requested for clean machine-readable output
    if json_output:
        logging.getLogger("zerg").setLevel(logging.CRITICAL + 1)

    stack = detect_project_stack(path)

    if json_output:
        click.echo(json.dumps(stack.to_dict(), indent=2))
    else:
        click.echo("Detected Project Stack:")
        click.echo(f"  Languages:      {', '.join(sorted(stack.languages)) or 'none'}")
        click.echo(f"  Frameworks:     {', '.join(sorted(stack.frameworks)) or 'none'}")
        click.echo(f"  Databases:      {', '.join(sorted(stack.databases)) or 'none'}")
        click.echo(f"  Infrastructure: {', '.join(sorted(stack.infrastructure)) or 'none'}")
        click.echo(f"  AI/ML:          {'yes' if stack.ai_ml else 'no'}")
        click.echo(f"  RAG:            {'yes' if stack.rag else 'no'}")


@security_rules_group.command(name="list")
@click.option(
    "--path",
    "-p",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    help="Project path to analyze",
)
def list_command(path: Path) -> None:
    """List security rules that would be fetched for this project."""
    stack = detect_project_stack(path)
    rules = get_required_rules(stack)

    click.echo(f"Security rules for detected stack ({len(rules)} files):\n")
    for rule in rules:
        click.echo(f"  - {rule}")


@security_rules_group.command(name="fetch")
@click.option(
    "--path",
    "-p",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    help="Project path to analyze",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default=None,
    help="Output directory for rules (default: .claude/security-rules/)",
)
@click.option("--no-cache", is_flag=True, help="Force re-fetch even if cached")
def fetch_command(path: Path, output: Path | None, no_cache: bool) -> None:
    """Fetch security rules for this project's stack."""
    stack = detect_project_stack(path)
    rules = get_required_rules(stack)

    output_dir = output or (path / ".claude" / "security-rules")

    click.echo(f"Fetching {len(rules)} security rule files...")
    fetched = fetch_rules(rules, output_dir, use_cache=not no_cache)

    click.echo(f"\nFetched {len(fetched)} rules to {output_dir}")
    for rule_path in fetched:
        click.echo(f"  - {rule_path}")


@security_rules_group.command(name="integrate")
@click.option(
    "--path",
    "-p",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    help="Project path to analyze",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default=None,
    help="Output directory for rules (default: .claude/security-rules/)",
)
@click.option(
    "--no-update-claude-md",
    is_flag=True,
    help="Don't update CLAUDE.md",
)
def integrate_command(
    path: Path,
    output: Path | None,
    no_update_claude_md: bool,
) -> None:
    """Full integration: detect stack, fetch rules, update CLAUDE.md."""
    click.echo("Integrating secure coding rules...\n")

    result = integrate_security_rules(
        project_path=path,
        output_dir=output,
        update_claude_md=not no_update_claude_md,
    )

    click.echo("Stack detected:")
    for key, value in result["stack"].items():
        if value:
            click.echo(f"  {key}: {value}")

    click.echo(f"\nRules fetched: {result['rules_fetched']}")
    click.echo(f"Rules directory: {result['rules_dir']}")

    if not no_update_claude_md:
        click.echo(f"Updated: {path}/CLAUDE.md")

    click.echo("\nDone! Security rules integrated.")
