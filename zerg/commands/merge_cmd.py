"""ZERG merge command - trigger merge gate execution."""

from typing import Any

import click
from rich.console import Console
from rich.table import Table

from zerg.config import ZergConfig
from zerg.constants import GateResult
from zerg.gates import GateRunner
from zerg.logging import get_logger
from zerg.merge import MergeCoordinator
from zerg.orchestrator import Orchestrator
from zerg.state import StateManager

console = Console()
logger = get_logger("merge")


@click.command("merge")
@click.option("--feature", "-f", help="Feature to merge")
@click.option("--level", "-l", type=int, help="Level to merge")
@click.option("--target", "-t", help="Target branch (default: main)")
@click.option("--skip-gates", is_flag=True, help="Skip quality gates")
@click.option("--dry-run", is_flag=True, help="Show merge plan only")
@click.pass_context
def merge_cmd(
    ctx: click.Context,
    feature: str | None,
    level: int | None,
    target: str | None,
    skip_gates: bool,
    dry_run: bool,
) -> None:
    """Trigger merge gate execution.

    Merges worker branches after quality gates pass.

    Examples:

        zerg merge

        zerg merge --level 2

        zerg merge --target develop --skip-gates

        zerg merge --dry-run
    """
    try:
        # Auto-detect feature
        if not feature:
            feature = detect_feature()

        if not feature:
            console.print("[red]Error:[/red] No active feature found")
            console.print("Specify a feature with [cyan]--feature[/cyan]")
            raise SystemExit(1)

        # Default target branch
        if not target:
            target = "main"

        console.print(f"\n[bold cyan]ZERG Merge[/bold cyan] - {feature}\n")

        # Load state and config
        state = StateManager(feature)
        if not state.exists():
            console.print(f"[red]Error:[/red] No state found for feature '{feature}'")
            raise SystemExit(1)

        state.load()
        config = ZergConfig.load()

        # Determine level to merge
        if not level:
            level = state.get_current_level()

        # Create merge coordinator
        merge_coordinator = MergeCoordinator(feature, config)

        # Show merge plan
        plan = create_merge_plan(state, feature, level, target, skip_gates)
        show_merge_plan(plan, dry_run)

        if dry_run:
            console.print("\n[dim]Dry run - no changes made[/dim]")
            return

        # Run quality gates if not skipped
        if not skip_gates:
            console.print("\n[bold]Running quality gates...[/bold]")
            gate_result = run_quality_gates(config, feature, level)

            if gate_result != GateResult.PASS:
                console.print("\n[red]Quality gates failed[/red]")
                console.print("Use [cyan]--skip-gates[/cyan] to merge anyway (not recommended)")
                raise SystemExit(1)

            console.print("[green]✓ Quality gates passed[/green]")

        # Confirm
        if not click.confirm("\nProceed with merge?", default=True):
            console.print("[yellow]Aborted[/yellow]")
            return

        # Execute merge using orchestrator for proper state tracking
        console.print("\n[bold]Merging branches...[/bold]")

        try:
            # Use orchestrator for merge with proper state management
            orchestrator = Orchestrator(feature)
            result = orchestrator._merge_level(level)

            if result.success:
                console.print(f"\n[green]✓ Level {level} merged successfully[/green]")
                if result.merge_commit:
                    console.print(f"  Merge commit: {result.merge_commit[:8]}")
                console.print(f"  Target: {target}")

                # Show merge status
                merge_status = state.get_level_merge_status(level)
                if merge_status:
                    console.print(f"  Status: {merge_status.value}")
            else:
                console.print("\n[red]Merge failed[/red]")
                if result.error:
                    console.print(f"  Error: {result.error}")
                conflicts = getattr(result, "conflicts", None)
                if conflicts:
                    console.print("\nConflicts in:")
                    for conflict in conflicts:
                        console.print(f"  - {conflict}")
                console.print("\nResolve conflicts manually or use [cyan]zerg retry[/cyan]")
                raise SystemExit(1)

        except Exception as e:
            # Fall back to direct merge coordinator
            logger.warning(f"Orchestrator merge failed, using direct coordinator: {e}")
            result = merge_coordinator.full_merge_flow(level)

            if result.success:
                console.print(f"\n[green]✓ Level {level} merged successfully[/green]")
                console.print(f"  Target: {target}")
            else:
                console.print("\n[red]Merge failed[/red]")
                if hasattr(result, "conflicts") and result.conflicts:
                    console.print("\nConflicts in:")
                    for conflict in result.conflicts:
                        console.print(f"  - {conflict}")
                console.print("\nResolve conflicts manually or use [cyan]zerg retry[/cyan]")
                raise SystemExit(1) from None

    except Exception as e:
        console.print(f"\n[red]Error:[/red] {e}")
        raise SystemExit(1) from e


def detect_feature() -> str | None:
    """Detect active feature. Re-exported from shared utility.

    See :func:`zerg.commands._utils.detect_feature` for details.
    """
    from zerg.commands._utils import detect_feature as _detect

    return _detect()


def create_merge_plan(
    state: StateManager,
    feature: str,
    level: int,
    target: str,
    skip_gates: bool,
) -> dict[str, Any]:
    """Create merge plan.

    Args:
        state: State manager
        feature: Feature name
        level: Level to merge
        target: Target branch
        skip_gates: Whether to skip gates

    Returns:
        Merge plan dict
    """
    workers = state.get_all_workers()

    branches = []
    for worker_id, worker in workers.items():
        branch = f"zerg/{feature}/worker-{worker_id}"
        branches.append(
            {
                "branch": branch,
                "worker_id": worker_id,
                "status": worker.status.value,
            }
        )

    return {
        "feature": feature,
        "level": level,
        "target": target,
        "staging_branch": f"zerg/{feature}/staging",
        "branches": branches,
        "skip_gates": skip_gates,
        "gates": [] if skip_gates else ["lint", "typecheck", "test"],
    }


def show_merge_plan(plan: dict[str, Any], dry_run: bool) -> None:
    """Show merge plan.

    Args:
        plan: Merge plan
        dry_run: Whether dry run
    """
    title = "Merge Plan (DRY RUN)" if dry_run else "Merge Plan"

    table = Table(title=title)
    table.add_column("Setting", style="cyan")
    table.add_column("Value")

    table.add_row("Feature", plan["feature"])
    table.add_row("Level", str(plan["level"]))
    table.add_row("Target Branch", plan["target"])
    table.add_row("Staging Branch", plan["staging_branch"])
    table.add_row("Branches to Merge", str(len(plan["branches"])))
    gates_display = ", ".join(plan["gates"]) if plan["gates"] else "[dim]skipped[/dim]"
    table.add_row("Quality Gates", gates_display)

    console.print(table)

    # Show branches
    console.print("\n[bold]Branches:[/bold]")
    for branch_info in plan["branches"]:
        status = branch_info["status"]
        icon = "🟢" if status == "running" else "⬜"
        console.print(f"  {icon} {branch_info['branch']}")


def run_quality_gates(config: ZergConfig, feature: str, level: int) -> GateResult:
    """Run quality gates.

    Args:
        config: Configuration
        feature: Feature name
        level: Level number

    Returns:
        Gate result
    """
    gate_runner = GateRunner(config)

    # Get gate commands from config
    gates = config.quality_gates

    all_passed = True
    for gate in gates:
        if not gate.required:
            continue

        if not gate.command:
            continue

        console.print(f"  Running {gate.name}...")
        result = gate_runner.run_gate(gate)

        if result.result == GateResult.PASS:
            console.print(f"    [green]✓[/green] {gate.name}")
        else:
            console.print(f"    [red]✗[/red] {gate.name}")
            all_passed = False

    return GateResult.PASS if all_passed else GateResult.FAIL
