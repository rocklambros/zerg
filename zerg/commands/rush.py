"""ZERG rush command - launch parallel execution."""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from zerg.risk_scoring import RiskReport

import click
from rich.console import Console
from rich.table import Table

from zerg.backlog import update_backlog_task_status
from zerg.capability_resolver import CapabilityResolver
from zerg.config import ZergConfig
from zerg.logging import get_logger, setup_logging
from zerg.orchestrator import Orchestrator
from zerg.parser import TaskParser
from zerg.validation import load_and_validate_task_graph

console = Console()
logger = get_logger("rush")


@click.command()
@click.option("--workers", "-w", default=5, type=int, help="Number of workers to launch")
@click.option("--feature", "-f", help="Feature name (auto-detected if not provided)")
@click.option("--level", "-l", type=int, help="Start from specific level")
@click.option("--dry-run", is_flag=True, help="Show plan without executing")
@click.option("--resume", is_flag=True, help="Continue from previous run")
@click.option("--timeout", default=3600, type=int, help="Max execution time (seconds)")
@click.option("--task-graph", "-g", help="Path to task-graph.json")
@click.option(
    "--mode",
    "-m",
    type=click.Choice(["subprocess", "container", "auto"]),
    default="auto",
    help="Worker execution mode (default: auto-detect)",
)
@click.option("--check-gates", is_flag=True, help="Pre-run quality gates during dry-run")
@click.option("--what-if", is_flag=True, help="Compare different worker counts and modes")
@click.option("--risk", is_flag=True, help="Show risk assessment for the task graph")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.pass_context
def rush(
    ctx: click.Context,
    workers: int,
    feature: str | None,
    level: int | None,
    dry_run: bool,
    resume: bool,
    timeout: int,
    task_graph: str | None,
    mode: str,
    check_gates: bool,
    what_if: bool,
    risk: bool,
    verbose: bool,
) -> None:
    """Launch parallel worker execution.

    Spawns workers, assigns tasks, and monitors progress until completion.

    Examples:

        zerg rush --workers 5

        zerg rush --feature user-auth --dry-run

        zerg rush --resume --workers 3

        zerg rush --mode container --workers 5

        zerg rush --dry-run --what-if

        zerg rush --dry-run --risk
    """
    # Setup logging
    if verbose:
        setup_logging(level="debug", console_output=True)
    else:
        setup_logging(level="info", console_output=True)

    try:
        # Load configuration
        config = ZergConfig.load()

        # Auto-detect feature and task graph
        task_graph_path = Path(task_graph) if task_graph else find_task_graph(feature)

        if not task_graph_path or not task_graph_path.exists():
            console.print("[red]Error:[/red] No task-graph.json found")
            console.print("Run [cyan]zerg design[/cyan] first to create a task graph")
            raise SystemExit(1)

        # Auto-detect feature from task graph
        if not feature:
            parser = TaskParser()
            parser.parse(task_graph_path)
            feature = parser.feature_name

        console.print(f"\n[bold cyan]ZERG Rush[/bold cyan] - {feature}\n")

        # Print task list ID for coordination visibility
        import os

        task_list_id = os.environ.get("CLAUDE_CODE_TASK_LIST_ID")
        if task_list_id:
            console.print(f"Task List ID: {task_list_id}")
        else:
            console.print("Task List ID: (default)")

        # Validate task graph
        with console.status("Validating task graph..."):
            task_data = load_and_validate_task_graph(task_graph_path)

        # Show summary
        show_summary(task_data, workers, mode)

        # Pre-flight checks (always run before rush or dry-run)
        if not _run_preflight(config, mode, workers):
            raise SystemExit(1)

        # What-if analysis
        if what_if:
            from zerg.whatif import WhatIfEngine

            engine = WhatIfEngine(task_data, feature)
            report = engine.compare_all()
            engine.render(report)
            if not dry_run:
                console.print()  # spacer before continuing

        # Risk assessment (standalone)
        if risk and not dry_run:
            from zerg.risk_scoring import RiskScorer

            scorer = RiskScorer(task_data, workers)
            risk_report = scorer.score()
            _render_standalone_risk(risk_report)

        if dry_run:
            from zerg.dryrun import DryRunSimulator

            simulator = DryRunSimulator(
                task_data=task_data,
                workers=workers,
                feature=feature,
                config=config,
                mode=mode,
                run_gates=check_gates,
            )
            dry_report = simulator.run()
            raise SystemExit(1 if dry_report.has_errors else 0)

        # If only what-if or risk was requested (without dry-run), exit
        if what_if or risk:
            return

        # Confirm before starting
        if not resume and not click.confirm("\nStart execution?", default=True):
            console.print("[yellow]Aborted[/yellow]")
            return

        # Resolve cross-cutting capabilities from CLI flags + config + task graph
        resolver = CapabilityResolver()
        capabilities = resolver.resolve(
            cli_flags=ctx.obj,
            config=config,
            task_graph=task_data,
            command="rush",
        )

        # Create orchestrator and start
        orchestrator = Orchestrator(feature, config, launcher_mode=mode, capabilities=capabilities)
        launcher_name = type(orchestrator.launcher).__name__
        mode_label = "container (Docker)" if "Container" in launcher_name else "subprocess"
        console.print(f"Launcher mode: [bold]{mode_label}[/bold]")
        console.print(f"Workers: [bold]{workers}[/bold]")

        # Register task completion callback with backlog update
        backlog_path = Path(f"tasks/{feature.upper()}-BACKLOG.md")

        def _on_task_done(tid: str) -> None:
            console.print(f"[green]✓[/green] Task {tid} complete")
            if backlog_path.exists():
                with contextlib.suppress(Exception):
                    update_backlog_task_status(backlog_path, tid, "COMPLETE")

        orchestrator.on_task_complete(_on_task_done)
        orchestrator.on_level_complete(lambda lvl: console.print(f"\n[bold green]Level {lvl} complete![/bold green]\n"))

        # Start execution
        console.print(f"\n[bold]Starting {workers} workers...[/bold]\n")

        orchestrator.start(
            task_graph_path=task_graph_path,
            worker_count=workers,
            start_level=level,
            dry_run=False,
        )

        # Show final status
        status = orchestrator.status()
        if status["is_complete"]:
            console.print(f"\n[bold green]✓ All tasks complete![/bold green] (mode: {mode_label})")
            # Clear .current-feature so stale pointers don't persist
            current_feature_file = Path(".gsd/.current-feature")
            if current_feature_file.exists():
                try:
                    current = current_feature_file.read_text().strip()
                    if current == feature:
                        current_feature_file.unlink()
                except Exception:
                    pass  # Non-critical cleanup
        else:
            pct = status["progress"]["percent"]
            console.print(f"\n[yellow]Execution stopped at {pct:.0f}%[/yellow]")

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted[/yellow]")
        raise SystemExit(130) from None
    except Exception as e:
        console.print(f"\n[red]Error:[/red] {e}")
        if verbose:
            console.print_exception()
        raise SystemExit(1) from None


def _run_preflight(config: ZergConfig, mode: str, workers: int) -> bool:
    """Run pre-flight checks before rush. Returns True if passed."""
    from zerg.preflight import PreflightChecker

    with console.status("Running pre-flight checks..."):
        checker = PreflightChecker(
            mode=mode,
            worker_count=workers,
            port_range_start=config.ports.range_start,
            port_range_end=config.ports.range_end,
        )
        report = checker.run_all()

    if report.errors:
        console.print("[bold red]Pre-flight failed:[/bold red]")
        for check in report.errors:
            console.print(f"  [red]✗[/red] {check.name}: {check.message}")
        return False

    if report.warnings:
        for check in report.warnings:
            console.print(f"  [yellow]⚠[/yellow] {check.name}: {check.message}")

    return True


def _render_standalone_risk(risk_report: RiskReport) -> None:
    """Render risk assessment as standalone output."""
    from rich.panel import Panel
    from rich.text import Text

    lines: list[Text] = []
    grade_colors = {"A": "green", "B": "yellow", "C": "red", "D": "bold red"}

    grade_line = Text()
    grade_line.append("Grade: ", style="dim")
    grade_line.append(
        risk_report.grade,
        style=grade_colors.get(risk_report.grade, "white"),
    )
    grade_line.append(f" (score: {risk_report.overall_score:.2f})")
    lines.append(grade_line)

    if risk_report.critical_path:
        cp_line = Text()
        cp_line.append("Critical path: ", style="dim")
        cp_line.append(" → ".join(risk_report.critical_path))
        lines.append(cp_line)

    for factor in risk_report.risk_factors:
        fl = Text()
        fl.append("⚠ ", style="yellow")
        fl.append(factor)
        lines.append(fl)

    content = Text("\n").join(lines)
    console.print(Panel(content, title="[bold]Risk Assessment[/bold]", title_align="left"))


def find_task_graph(feature: str | None) -> Path | None:
    """Find task-graph.json for a feature.

    Args:
        feature: Feature name or None

    Returns:
        Path to task graph or None
    """
    # Check common locations
    candidates = [
        Path(".gsd/tasks/task-graph.json"),
        Path("task-graph.json"),
    ]

    if feature:
        candidates.insert(0, Path(f".gsd/specs/{feature}/task-graph.json"))

    for path in candidates:
        if path.exists():
            return path

    # Search for any task-graph.json
    for path in Path(".gsd").rglob("task-graph.json"):
        return path

    return None


def show_summary(task_data: dict[str, Any], workers: int, mode: str = "auto") -> None:
    """Show execution summary.

    Args:
        task_data: Task graph data
        workers: Worker count
        mode: Execution mode (subprocess, container, task, auto)
    """
    tasks = task_data.get("tasks", [])
    levels = task_data.get("levels", {})

    table = Table(title="Execution Summary", show_header=False, box=None)
    table.add_column("Metric", style="cyan")
    table.add_column("Value")

    table.add_row("Feature", task_data.get("feature", "unknown"))
    table.add_row("Total Tasks", str(len(tasks)))
    table.add_row("Levels", str(len(levels)))
    table.add_row("Workers", str(workers))
    table.add_row("Mode", mode)
    table.add_row("Max Parallelization", str(task_data.get("max_parallelization", workers)))

    if "critical_path_minutes" in task_data:
        table.add_row("Critical Path", f"{task_data['critical_path_minutes']} min")

    console.print(table)


def show_dry_run(task_data: dict[str, Any], workers: int, feature: str) -> None:
    """Show dry run plan.

    Args:
        task_data: Task graph data
        workers: Worker count
        feature: Feature name
    """
    console.print("\n[bold]Dry Run - Execution Plan[/bold]\n")

    tasks = task_data.get("tasks", [])
    levels = task_data.get("levels", {})

    # Group tasks by level
    level_tasks: dict[int, list[dict[str, Any]]] = {}
    for task in tasks:
        lvl = task.get("level", 1)
        if lvl not in level_tasks:
            level_tasks[lvl] = []
        level_tasks[lvl].append(task)

    # Show each level
    from zerg.assign import WorkerAssignment

    assigner = WorkerAssignment(workers)
    assigner.assign(tasks, feature)

    for level_num in sorted(level_tasks.keys()):
        level_info = levels.get(str(level_num), {})
        level_name = level_info.get("name", "unnamed")
        console.print(f"[bold cyan]Level {level_num}[/bold cyan] - {level_name}")

        table = Table(show_header=True)
        table.add_column("Task", style="cyan", width=15)
        table.add_column("Title", width=40)
        table.add_column("Worker", justify="center", width=8)
        table.add_column("Est.", justify="right", width=6)

        for task in level_tasks[level_num]:
            worker = assigner.get_task_worker(task["id"])
            critical = "⭐ " if task.get("critical_path") else ""
            table.add_row(
                task["id"],
                critical + task.get("title", ""),
                str(worker) if worker is not None else "-",
                f"{task.get('estimate_minutes', '?')}m",
            )

        console.print(table)
        console.print()

    console.print("[dim]No workers will be started in dry-run mode[/dim]")
