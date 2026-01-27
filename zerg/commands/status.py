"""ZERG status command - show execution progress."""

import json
import time
from pathlib import Path

import click
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from zerg.constants import TaskStatus, WorkerStatus
from zerg.logging import get_logger
from zerg.metrics import MetricsCollector
from zerg.state import StateManager
from zerg.types import FeatureMetrics, LevelMetrics, WorkerMetrics

console = Console()
logger = get_logger("status")


@click.command()
@click.option("--feature", "-f", help="Feature to show status for")
@click.option("--watch", "-w", is_flag=True, help="Continuous update mode")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.option("--level", "-l", type=int, help="Filter to specific level")
@click.option("--interval", default=5, type=int, help="Watch interval (seconds)")
@click.pass_context
def status(
    ctx: click.Context,
    feature: str | None,
    watch: bool,
    json_output: bool,
    level: int | None,
    interval: int,
) -> None:
    """Show execution progress.

    Displays worker status, level progress, and recent events.

    Examples:

        zerg status

        zerg status --watch

        zerg status --feature user-auth --json
    """
    try:
        # Auto-detect feature
        if not feature:
            feature = detect_feature()

        if not feature:
            console.print("[red]Error:[/red] No active feature found")
            console.print("Specify a feature with [cyan]--feature[/cyan] or run from a feature directory")
            raise SystemExit(1)

        # Load state
        state = StateManager(feature)
        if not state.exists():
            console.print(f"[red]Error:[/red] No state found for feature '{feature}'")
            raise SystemExit(1)

        state.load()

        if json_output:
            show_json_status(state, level)
        elif watch:
            show_watch_status(state, feature, level, interval)
        else:
            show_status(state, feature, level)

    except KeyboardInterrupt:
        console.print("\n[dim]Stopped watching[/dim]")
    except Exception as e:
        console.print(f"\n[red]Error:[/red] {e}")
        raise SystemExit(1)


def detect_feature() -> str | None:
    """Detect active feature from state files.

    Returns:
        Feature name or None
    """
    state_dir = Path(".zerg/state")
    if not state_dir.exists():
        return None

    # Find most recent state file
    state_files = list(state_dir.glob("*.json"))
    if not state_files:
        return None

    # Sort by modification time
    state_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return state_files[0].stem


def show_status(state: StateManager, feature: str, level_filter: int | None) -> None:
    """Show current status.

    Args:
        state: State manager
        feature: Feature name
        level_filter: Level to filter to
    """
    # Header
    console.print()
    console.print(Panel(f"[bold cyan]ZERG Status: {feature}[/bold cyan]"))
    console.print()

    # Get task stats
    all_tasks = state._state.get("tasks", {})
    completed = len(state.get_tasks_by_status(TaskStatus.COMPLETE))
    failed = len(state.get_tasks_by_status(TaskStatus.FAILED))
    in_progress = len(state.get_tasks_by_status(TaskStatus.IN_PROGRESS))
    total = len(all_tasks) if all_tasks else 42  # Fallback estimate

    # Progress bar
    progress_pct = (completed / total * 100) if total > 0 else 0
    progress_bar = create_progress_bar(progress_pct)
    console.print(f"Progress: {progress_bar} {progress_pct:.0f}% ({completed}/{total} tasks)")
    console.print()

    # Level status
    show_level_status(state, level_filter)

    # Worker status
    show_worker_status(state)

    # Worker metrics (timing, throughput)
    show_worker_metrics(state)

    # Level metrics (duration, percentiles)
    show_level_metrics(state)

    # Recent events
    show_recent_events(state, limit=5)

    # Error state
    error = state.get_error()
    if error:
        console.print(f"\n[red]Error:[/red] {error}")


def show_level_status(state: StateManager, level_filter: int | None) -> None:
    """Show level status table.

    Args:
        state: State manager
        level_filter: Level to filter to
    """
    console.print("[bold]Level Status:[/bold]")

    table = Table(show_header=True)
    table.add_column("Level", justify="center")
    table.add_column("Name")
    table.add_column("Tasks", justify="center")
    table.add_column("Complete", justify="center")
    table.add_column("Status")

    levels = state._state.get("levels", {})

    # If no level data, show placeholder
    if not levels:
        for i in range(1, 6):
            if level_filter and i != level_filter:
                continue
            status = "PENDING"
            if i == state.get_current_level():
                status = "[yellow]RUNNING[/yellow]"
            table.add_row(str(i), f"Level {i}", "-", "-", status)
    else:
        for level_str, level_data in sorted(levels.items(), key=lambda x: int(x[0])):
            level_num = int(level_str)
            if level_filter and level_num != level_filter:
                continue

            name = level_data.get("name", f"Level {level_num}")
            status_str = level_data.get("status", "pending")

            if status_str == "complete":
                status_display = "[green]✓ DONE[/green]"
            elif status_str == "running":
                status_display = "[yellow]RUNNING[/yellow]"
            else:
                status_display = "PENDING"

            table.add_row(
                level_str,
                name,
                "-",  # Would need task data
                "-",  # Would need completion data
                status_display,
            )

    console.print(table)
    console.print()


def show_worker_status(state: StateManager) -> None:
    """Show worker status table.

    Args:
        state: State manager
    """
    console.print("[bold]Worker Status:[/bold]")

    table = Table(show_header=True)
    table.add_column("Worker", justify="center")
    table.add_column("Port", justify="center")
    table.add_column("Task")
    table.add_column("Progress")
    table.add_column("Status")

    workers = state.get_all_workers()

    if not workers:
        table.add_row("-", "-", "-", "-", "[dim]No workers[/dim]")
    else:
        for worker_id, worker in sorted(workers.items()):
            status_str = worker.status.value

            if worker.status == WorkerStatus.RUNNING:
                status_display = "[green]RUNNING[/green]"
            elif worker.status == WorkerStatus.IDLE:
                status_display = "[dim]IDLE[/dim]"
            elif worker.status == WorkerStatus.CRASHED:
                status_display = "[red]CRASHED[/red]"
            else:
                status_display = status_str.upper()

            # Progress bar for context usage
            ctx_bar = create_progress_bar(worker.context_usage * 100, width=10)

            table.add_row(
                f"worker-{worker_id}",
                str(worker.port) if worker.port else "-",
                worker.current_task or "-",
                ctx_bar,
                status_display,
            )

    console.print(table)
    console.print()


def show_recent_events(state: StateManager, limit: int = 5) -> None:
    """Show recent events.

    Args:
        state: State manager
        limit: Number of events to show
    """
    events = state.get_events(limit=limit)

    if not events:
        return

    console.print("[bold]Recent Events:[/bold]")

    for event in events[-limit:]:
        ts = event.get("timestamp", "")[:8]  # Just time portion
        event_type = event.get("event", "unknown")
        data = event.get("data", {})

        # Format event
        if event_type == "task_complete":
            console.print(f"  [{ts}] [green]✓[/green] {data.get('task_id')} completed by worker-{data.get('worker_id')}")
        elif event_type == "task_failed":
            console.print(f"  [{ts}] [red]✗[/red] {data.get('task_id')} failed: {data.get('error', 'unknown')}")
        elif event_type == "level_started":
            console.print(f"  [{ts}] [cyan]▶[/cyan] Level {data.get('level')} started with {data.get('tasks')} tasks")
        elif event_type == "level_complete":
            console.print(f"  [{ts}] [green]✓[/green] Level {data.get('level')} complete")
        elif event_type == "worker_started":
            console.print(f"  [{ts}] [cyan]+[/cyan] Worker {data.get('worker_id')} started on port {data.get('port')}")
        else:
            console.print(f"  [{ts}] {event_type}")

    console.print()


def show_watch_status(state: StateManager, feature: str, level_filter: int | None, interval: int) -> None:
    """Show continuously updating status.

    Args:
        state: State manager
        feature: Feature name
        level_filter: Level to filter to
        interval: Update interval
    """
    with Live(console=console, refresh_per_second=1) as live:
        while True:
            # Reload state
            state.load()

            # Build output
            output = build_status_output(state, feature, level_filter)
            live.update(output)

            time.sleep(interval)


def build_status_output(state: StateManager, feature: str, level_filter: int | None) -> Panel:
    """Build status output for live display.

    Args:
        state: State manager
        feature: Feature name
        level_filter: Level filter

    Returns:
        Panel with status
    """

    lines = []

    # Progress
    all_tasks = state._state.get("tasks", {})
    completed = len(state.get_tasks_by_status(TaskStatus.COMPLETE))
    total = len(all_tasks) if all_tasks else 42
    progress_pct = (completed / total * 100) if total > 0 else 0

    lines.append(f"Progress: {create_progress_bar(progress_pct)} {progress_pct:.0f}%")
    lines.append("")
    lines.append(f"Level: {state.get_current_level()}")
    lines.append(f"Workers: {len(state.get_all_workers())}")
    lines.append("")
    lines.append("[dim]Press Ctrl+C to stop watching[/dim]")

    return Panel("\n".join(lines), title=f"[bold]ZERG: {feature}[/bold]")


def show_json_status(state: StateManager, level_filter: int | None) -> None:
    """Output status as JSON.

    Args:
        state: State manager
        level_filter: Level to filter to
    """
    output = {
        "feature": state.feature,
        "current_level": state.get_current_level(),
        "paused": state.is_paused(),
        "error": state.get_error(),
        "tasks": state._state.get("tasks", {}),
        "workers": {
            str(wid): w.to_dict() for wid, w in state.get_all_workers().items()
        },
        "levels": state._state.get("levels", {}),
        "events": state.get_events(limit=10),
        "metrics": get_metrics_dict(state),
    }

    console.print(json.dumps(output, indent=2, default=str))


def create_progress_bar(percent: float, width: int = 20) -> str:
    """Create a text progress bar.

    Args:
        percent: Percentage complete
        width: Bar width in characters

    Returns:
        Progress bar string
    """
    filled = int(width * percent / 100)
    empty = width - filled
    return f"[green]{'█' * filled}[/green][dim]{'░' * empty}[/dim]"


def format_duration(ms: int | None) -> str:
    """Format duration in milliseconds to human-readable string.

    Args:
        ms: Duration in milliseconds, or None

    Returns:
        Formatted string like "1.2s", "4m30s", "2h15m", or "-"
    """
    if ms is None:
        return "-"

    if ms < 1000:
        return f"{ms}ms"

    seconds = ms / 1000

    if seconds < 60:
        return f"{seconds:.1f}s"

    minutes = int(seconds // 60)
    remaining_seconds = int(seconds % 60)

    if minutes < 60:
        if remaining_seconds > 0:
            return f"{minutes}m{remaining_seconds}s"
        return f"{minutes}m"

    hours = int(minutes // 60)
    remaining_minutes = int(minutes % 60)

    if remaining_minutes > 0:
        return f"{hours}h{remaining_minutes}m"
    return f"{hours}h"


def show_worker_metrics(state: StateManager) -> None:
    """Show worker metrics table with timing information.

    Args:
        state: State manager
    """
    try:
        collector = MetricsCollector(state)
        feature_metrics = collector.compute_feature_metrics()
    except Exception as e:
        logger.debug(f"Could not compute metrics: {e}")
        return

    if not feature_metrics.worker_metrics:
        return

    console.print("[bold]Worker Metrics:[/bold]")

    table = Table(show_header=True)
    table.add_column("Worker", justify="center")
    table.add_column("Init Time", justify="right")
    table.add_column("Tasks", justify="center")
    table.add_column("Avg Duration", justify="right")
    table.add_column("Uptime", justify="right")

    for wm in feature_metrics.worker_metrics:
        tasks_display = f"{wm.tasks_completed}"
        if wm.tasks_failed > 0:
            tasks_display += f" [red]({wm.tasks_failed} failed)[/red]"

        table.add_row(
            f"worker-{wm.worker_id}",
            format_duration(wm.initialization_ms),
            tasks_display,
            format_duration(int(wm.avg_task_duration_ms)) if wm.avg_task_duration_ms > 0 else "-",
            format_duration(wm.uptime_ms),
        )

    console.print(table)
    console.print()


def show_level_metrics(state: StateManager) -> None:
    """Show level metrics table with timing and percentiles.

    Args:
        state: State manager
    """
    try:
        collector = MetricsCollector(state)
        feature_metrics = collector.compute_feature_metrics()
    except Exception as e:
        logger.debug(f"Could not compute metrics: {e}")
        return

    if not feature_metrics.level_metrics:
        return

    console.print("[bold]Level Metrics:[/bold]")

    table = Table(show_header=True)
    table.add_column("Level", justify="center")
    table.add_column("Duration", justify="right")
    table.add_column("Tasks", justify="center")
    table.add_column("p50", justify="right")
    table.add_column("p95", justify="right")

    for lm in sorted(feature_metrics.level_metrics, key=lambda x: x.level):
        tasks_display = f"{lm.completed_count}/{lm.task_count}"
        if lm.failed_count > 0:
            tasks_display += f" [red]({lm.failed_count} failed)[/red]"

        table.add_row(
            str(lm.level),
            format_duration(lm.duration_ms),
            tasks_display,
            format_duration(lm.p50_duration_ms) if lm.p50_duration_ms > 0 else "-",
            format_duration(lm.p95_duration_ms) if lm.p95_duration_ms > 0 else "-",
        )

    console.print(table)
    console.print()


def get_metrics_dict(state: StateManager) -> dict | None:
    """Get metrics as a dictionary for JSON output.

    Args:
        state: State manager

    Returns:
        Metrics dictionary or None if unavailable
    """
    try:
        collector = MetricsCollector(state)
        feature_metrics = collector.compute_feature_metrics()
        return feature_metrics.to_dict()
    except Exception as e:
        logger.debug(f"Could not compute metrics: {e}")
        return None
