"""ZERG status command - show execution progress."""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click
from rich.console import Console, Group, RenderableType
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from zerg.claude_tasks_reader import ClaudeTasksReader
from zerg.constants import SPECS_DIR, TaskStatus, WorkerStatus
from zerg.logging import get_logger
from zerg.metrics import MetricsCollector
from zerg.state import StateManager

if TYPE_CHECKING:
    from zerg.state import StateManager

console = Console()
logger = get_logger("status")

# Dashboard status symbols
LEVEL_SYMBOLS = {
    "complete": "[green]✓[/green]",
    "running": "[yellow]●[/yellow]",
    "pending": "[dim]○[/dim]",
    "merging": "[cyan]⟳[/cyan]",
    "conflict": "[red]✗[/red]",
}

WORKER_COLORS = {
    WorkerStatus.RUNNING: "green",
    WorkerStatus.IDLE: "dim",
    WorkerStatus.CRASHED: "red",
    WorkerStatus.CHECKPOINTING: "yellow",
    WorkerStatus.INITIALIZING: "cyan",
    WorkerStatus.READY: "blue",
    WorkerStatus.STOPPING: "yellow",
    WorkerStatus.STOPPED: "dim",
    WorkerStatus.BLOCKED: "red",
}


@click.command()
@click.option("--feature", "-f", help="Feature to show status for")
@click.option("--watch", "-w", is_flag=True, help="Continuous update mode")
@click.option("--dashboard", "-d", is_flag=True, help="Real-time dashboard view")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.option("--level", "-l", type=int, help="Filter to specific level")
@click.option("--interval", default=1, type=int, help="Refresh interval in seconds (default: 1)")
@click.option("--tasks", "tasks_view", is_flag=True, help="Show all tasks with status, level, and worker")
@click.option("--workers", "workers_view", is_flag=True, help="Show detailed per-worker info")
@click.option("--commits", "commits_view", is_flag=True, help="Show recent commits per worker branch")
@click.pass_context
def status(
    ctx: click.Context,
    feature: str | None,
    watch: bool,
    dashboard: bool,
    json_output: bool,
    level: int | None,
    interval: int,
    tasks_view: bool,
    workers_view: bool,
    commits_view: bool,
) -> None:
    """Show execution progress.

    Displays worker status, level progress, and recent events.

    Examples:

        zerg status

        zerg status --dashboard

        zerg status -d --interval 2

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
            # Try Claude Code Tasks as fallback before declaring "not executing"
            _injected = False
            try:
                reader = ClaudeTasksReader()
                task_list_dir = reader.find_feature_task_list(feature)
                if task_list_dir:
                    task_state = reader.read_tasks(task_list_dir)
                    if task_state.get("tasks"):
                        state.inject_state(task_state)
                        _injected = True
            except Exception:
                logger.debug("Claude Tasks reader fallback failed", exc_info=True)

            if _injected:
                pass  # Fall through to normal display path
            else:
                # No Claude Code Tasks found — show spec-based messages
                spec_dir = Path(SPECS_DIR) / feature
                if spec_dir.exists():
                    task_graph_path = spec_dir / "task-graph.json"
                    started = spec_dir / ".started"
                    if task_graph_path.exists():
                        console.print(f"[yellow]Feature '{feature}' is designed but not yet executing.[/yellow]")
                        try:
                            tg = json.loads(task_graph_path.read_text())
                            total = tg.get("total_tasks", "?")
                            levels = tg.get("levels", {})
                            max_par = tg.get("max_parallelization", "?")
                            console.print("\n[bold]Task Graph Summary[/bold]")
                            console.print(f"  Tasks: {total}  |  Levels: {len(levels)}  |  Max parallel: {max_par}")
                            for lvl_num, lvl_data in sorted(levels.items(), key=lambda x: int(x[0])):
                                name = lvl_data.get("name", "")
                                task_ids = lvl_data.get("tasks", [])
                                console.print(f"  L{lvl_num} ({name}): {len(task_ids)} tasks")
                        except Exception:
                            pass
                        console.print(
                            f"\nRun [cyan]zerg rush[/cyan] to start execution,"
                            f" or [cyan]zerg cleanup -f {feature}[/cyan] to remove."
                        )
                    elif started.exists():
                        console.print(f"[yellow]Feature '{feature}' design is in progress.[/yellow]")
                    else:
                        console.print(f"[yellow]Feature '{feature}' is planned but not yet designed.[/yellow]")
                        console.print(
                            f"Run [cyan]zerg design[/cyan] to create task graph,"
                            f" or [cyan]zerg cleanup -f {feature}[/cyan] to remove."
                        )
                else:
                    console.print(f"[red]Error:[/red] No state found for feature '{feature}'")
                raise SystemExit(1)

        if not state._state:
            state.load()

        if tasks_view:
            show_tasks_view(state, level)
        elif workers_view:
            show_workers_view(state)
        elif commits_view:
            show_commits_view(state, feature)
        elif json_output:
            show_json_status(state, level)
        elif dashboard:
            show_dashboard(state, feature, interval)
        elif watch:
            show_watch_status(state, feature, level, interval)
        else:
            show_status(state, feature, level)

    except KeyboardInterrupt:
        console.print("\n[dim]Stopped watching[/dim]")
    except Exception as e:
        console.print(f"\n[red]Error:[/red] {e}")
        raise SystemExit(1) from None


def detect_feature() -> str | None:
    """Detect active feature. Re-exported from shared utility.

    See :func:`zerg.commands._utils.detect_feature` for details.
    """
    from zerg.commands._utils import detect_feature as _detect

    return _detect()


def format_elapsed(start: datetime) -> str:
    """Format elapsed time as '5m 32s' or '1h 23m'.

    Args:
        start: Start datetime

    Returns:
        Formatted elapsed string
    """
    delta = datetime.now() - start
    total_seconds = int(delta.total_seconds())

    if total_seconds < 60:
        return f"{total_seconds}s"

    minutes = total_seconds // 60
    seconds = total_seconds % 60

    if minutes < 60:
        return f"{minutes}m {seconds}s"

    hours = minutes // 60
    remaining_minutes = minutes % 60
    return f"{hours}h {remaining_minutes}m"


def compact_progress_bar(percent: float, width: int = 20) -> str:
    """Create a compact Unicode block progress bar.

    Args:
        percent: Percentage complete (0-100)
        width: Bar width in characters

    Returns:
        Progress bar string without Rich markup
    """
    filled = int(width * percent / 100)
    empty = width - filled
    return "█" * filled + "░" * empty


class DashboardRenderer:
    """Compact real-time dashboard renderer."""

    def __init__(self, state: StateManager, feature: str, data_source: str = "state"):
        """Initialize the dashboard renderer.

        Args:
            state: State manager instance
            feature: Feature name
            data_source: Data source label ("state" or "tasks")
        """
        self.state = state
        self.feature = feature
        self.data_source = data_source
        self.start_time = datetime.now()

    def render(self) -> RenderableType:
        """Build full dashboard.

        Returns:
            Renderable dashboard content
        """
        return Group(
            self._render_header(),
            self._render_progress(),
            self._render_levels(),
            self._render_workers(),
            self._render_retry_info(),
            self._render_events(),
        )

    def _render_header(self) -> Panel:
        """Render header with feature name and elapsed time."""
        elapsed = format_elapsed(self.start_time)
        header_text = Text()
        header_text.append("ZERG Dashboard: ", style="bold cyan")
        header_text.append(self.feature, style="bold white")
        header_text.append(" " * 10)
        source_label = "Tasks" if self.data_source == "tasks" else "State"
        header_text.append(f"[{source_label}]", style="dim cyan")
        header_text.append(" " * 10)
        header_text.append(f"Elapsed: {elapsed}", style="dim")
        from rich import box as rich_box

        return Panel(header_text, box=rich_box.SIMPLE, padding=(0, 1))

    def _render_progress(self) -> Text:
        """Render overall progress bar."""
        tasks = self.state._state.get("tasks", {})
        total = len(tasks)
        complete = sum(1 for t in tasks.values() if t.get("status") == TaskStatus.COMPLETE.value)
        percent = (complete / total * 100) if total > 0 else 0

        bar = compact_progress_bar(percent)
        progress_text = Text()
        progress_text.append("Progress: ")
        progress_text.append(bar[: int(20 * percent / 100)], style="green")
        progress_text.append(bar[int(20 * percent / 100) :], style="dim")
        progress_text.append(f" {percent:.0f}% ({complete}/{total} tasks)")
        progress_text.append("\n")
        return progress_text

    def _render_levels(self) -> Panel:
        """Render level status section."""
        tasks = self.state._state.get("tasks", {})
        levels_data = self.state._state.get("levels", {})

        # Group tasks by level
        level_tasks: dict[int, list[Any]] = {}
        for task in tasks.values():
            level_num = task.get("level", 1)
            if level_num not in level_tasks:
                level_tasks[level_num] = []
            level_tasks[level_num].append(task)

        lines = []
        for level_num in sorted(level_tasks.keys()):
            level_task_list = level_tasks[level_num]
            total = len(level_task_list)
            complete = sum(1 for t in level_task_list if t.get("status") == TaskStatus.COMPLETE.value)
            running = sum(
                1
                for t in level_task_list
                if t.get("status") in (TaskStatus.CLAIMED.value, TaskStatus.IN_PROGRESS.value)
            )

            # Determine level status
            if complete == total:
                status = "complete"
                status_text = "COMPLETE"
            elif running > 0 or complete > 0:
                status = "running"
                status_text = "RUNNING"
            else:
                status = "pending"
                status_text = "PENDING"

            # Check for merge status
            level_info = levels_data.get(str(level_num), {})
            merge_status = level_info.get("merge_status")
            if merge_status in ("merging", "rebasing", "validating"):
                status = "merging"
                status_text = "MERGING"
            elif merge_status == "conflict":
                status = "conflict"
                status_text = "CONFLICT"

            percent = (complete / total * 100) if total > 0 else 0
            bar = compact_progress_bar(percent)
            symbol = LEVEL_SYMBOLS.get(status, "○")

            line = Text()
            line.append(f"L{level_num} [")
            line.append(bar[: int(20 * percent / 100)], style="green")
            line.append(bar[int(20 * percent / 100) :], style="dim")
            line.append(f"] {percent:3.0f}% {complete:2}/{total:2} {symbol} {status_text}")
            lines.append(line)

        content = Text("\n").join(lines) if lines else Text("[dim]No levels[/dim]")
        return Panel(content, title="[bold]LEVELS[/bold]", title_align="left", padding=(0, 1))

    def _render_workers(self) -> Panel:
        """Render worker status section."""
        workers = self.state.get_all_workers()

        lines = []
        for worker_id, worker in sorted(workers.items()):
            color = WORKER_COLORS.get(worker.status, "white")
            status_str = worker.status.value.upper()

            # Context usage bar
            ctx = worker.context_usage
            ctx_bar = compact_progress_bar(ctx * 100, width=20)
            ctx_percent = int(ctx * 100)

            line = Text()
            line.append(f"W{worker_id} ", style="bold")
            line.append(f"{status_str:12}", style=color)
            line.append(f"{worker.current_task or '-':16}")
            line.append(" [")

            # Color context bar based on usage
            bar_filled = int(20 * ctx)
            if ctx > 0.85:
                line.append(ctx_bar[:bar_filled], style="red")
            elif ctx > 0.70:
                line.append(ctx_bar[:bar_filled], style="yellow")
            else:
                line.append(ctx_bar[:bar_filled], style="green")
            line.append(ctx_bar[bar_filled:], style="dim")
            line.append("] ")

            ctx_str = f"ctx:{ctx_percent:2}%"
            if ctx > 0.85:
                line.append(ctx_str, style="red")
                line.append(" ⚠", style="yellow")
            else:
                line.append(ctx_str)

            lines.append(line)

        if not lines:
            if self.data_source == "tasks":
                content = Text("N/A (task-based execution)", style="dim")
            else:
                content = Text("[dim]No workers active[/dim]")
        else:
            content = Text("\n").join(lines)
        return Panel(content, title="[bold]WORKERS[/bold]", title_align="left", padding=(0, 1))

    def _render_retry_info(self) -> Panel:
        """Render retry status section showing tasks awaiting or scheduled for retry."""
        tasks = self.state._state.get("tasks", {})
        now = datetime.now()

        lines = []
        awaiting_count = 0

        for task_id, task_state in sorted(tasks.items()):
            retry_count = task_state.get("retry_count", 0)
            if retry_count == 0:
                continue

            max_retries = task_state.get("max_retries", 3)  # fallback
            next_retry = task_state.get("next_retry_at")
            status = task_state.get("status")

            line = Text()
            line.append(f"{task_id:16}", style="bold")
            line.append(f"{retry_count}/{max_retries} ", style="yellow")

            if status == "waiting_retry" and next_retry:
                awaiting_count += 1
                try:
                    retry_dt = datetime.fromisoformat(next_retry)
                    remaining = (retry_dt - now).total_seconds()
                    if remaining > 0:
                        line.append(f"in {int(remaining)}s", style="cyan")
                    else:
                        line.append("ready", style="green")
                except (ValueError, TypeError):
                    line.append("scheduled", style="dim")
            elif status == TaskStatus.FAILED.value:
                line.append("exhausted", style="red")
            elif status == TaskStatus.COMPLETE.value:
                line.append("recovered", style="green")
            else:
                line.append(status or "?", style="dim")

            lines.append(line)

        if not lines:
            content = Text("[dim]No retries[/dim]")
        else:
            summary = Text()
            if awaiting_count > 0:
                summary.append(f"{awaiting_count} task(s) awaiting retry", style="yellow")
                summary.append("\n")
            summary.append(Text("\n").join(lines))
            content = summary

        return Panel(content, title="[bold]RETRIES[/bold]", title_align="left", padding=(0, 1))

    def _render_events(self, limit: int = 4) -> Panel:
        """Render recent events section.

        Args:
            limit: Maximum number of events to display
        """
        events = self.state.get_events(limit=limit)

        lines = []
        for event in events[-limit:]:
            ts = event.get("timestamp", "")
            # Extract time portion (HH:MM:SS)
            ts_display = (ts[11:19] if len(ts) > 11 else ts[:8]) if len(ts) >= 8 else ts

            event_type = event.get("event", "unknown")
            data = event.get("data", {})

            line = Text()
            line.append(f"{ts_display} ", style="dim")

            if event_type == "task_complete":
                duration = data.get("duration", "")
                duration_str = f", {duration}" if duration else ""
                task_id = data.get("task_id", "?")
                worker_id = data.get("worker_id", "?")
                line.append("✓ ", style="green")
                line.append(f"{task_id} complete (worker-{worker_id}{duration_str})")
            elif event_type == "task_claimed":
                task_id = data.get("task_id", "?")
                worker_id = data.get("worker_id", "?")
                line.append("→ ", style="cyan")
                line.append(f"{task_id} claimed by worker-{worker_id}")
            elif event_type == "task_failed":
                task_id = data.get("task_id", "?")
                error_msg = data.get("error", "unknown")[:30]
                line.append("✗ ", style="red")
                line.append(f"{task_id} failed: {error_msg}")
            elif event_type == "level_started":
                lvl = data.get("level", "?")
                task_count = data.get("tasks", "?")
                line.append("▶ ", style="cyan")
                line.append(f"Level {lvl} started with {task_count} tasks")
            elif event_type == "level_complete":
                line.append("✓ ", style="green")
                line.append(f"Level {data.get('level', '?')} complete")
            elif event_type == "worker_started":
                line.append("+ ", style="cyan")
                line.append(f"Worker {data.get('worker_id', '?')} started")
            elif event_type == "merge_started":
                line.append("⟳ ", style="cyan")
                line.append(f"Level {data.get('level', '?')} merge started")
            elif event_type == "merge_complete":
                line.append("✓ ", style="green")
                line.append(f"Level {data.get('level', '?')} merge complete")
            elif event_type == "task_retry_scheduled":
                task_id = data.get("task_id", "?")
                backoff = data.get("backoff_seconds", "?")
                retry_num = data.get("retry_count", "?")
                line.append("↻ ", style="yellow")
                line.append(f"{task_id} retry #{retry_num} in {backoff}s")
            elif event_type == "task_retry_ready":
                line.append("↻ ", style="green")
                line.append(f"{data.get('task_id', '?')} retry ready")
            else:
                line.append(f"  {event_type}")

            lines.append(line)

        content = Text("[dim]No events yet[/dim]") if not lines else Text("\n").join(lines)
        return Panel(content, title="[bold]EVENTS[/bold]", title_align="left", padding=(0, 1))


def show_dashboard(state: StateManager, feature: str, interval: int = 1) -> None:
    """Real-time dashboard view.

    Falls back to reading Claude Code Tasks from disk when the state JSON
    has no task data (e.g., when workers were launched via slash commands).

    Args:
        state: State manager
        feature: Feature name
        interval: Refresh interval in seconds
    """
    # Determine data source: state JSON or Claude Code Tasks
    reader = None
    task_list_dir = None
    data_source = "state"

    state.load()
    if not state._state.get("tasks"):
        from zerg.claude_tasks_reader import ClaudeTasksReader

        reader = ClaudeTasksReader()
        task_list_dir = reader.find_feature_task_list(feature)
        if task_list_dir:
            state.inject_state(reader.read_tasks(task_list_dir))
            data_source = "tasks"
            logger.info("Dashboard using Claude Tasks from %s", task_list_dir.name)

    renderer = DashboardRenderer(state, feature, data_source=data_source)

    with Live(console=console, refresh_per_second=1, screen=True) as live:
        try:
            while True:
                if reader and task_list_dir:
                    state.inject_state(reader.read_tasks(task_list_dir))
                else:
                    state.load()
                live.update(renderer.render())
                time.sleep(interval)
        except KeyboardInterrupt:
            pass


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
            task_id = data.get("task_id")
            worker_id = data.get("worker_id")
            console.print(f"  [{ts}] [green]✓[/green] {task_id} completed by worker-{worker_id}")
        elif event_type == "task_failed":
            task_id = data.get("task_id")
            error = data.get("error", "unknown")
            console.print(f"  [{ts}] [red]✗[/red] {task_id} failed: {error}")
        elif event_type == "level_started":
            level = data.get("level")
            tasks = data.get("tasks")
            console.print(f"  [{ts}] [cyan]▶[/cyan] Level {level} started with {tasks} tasks")
        elif event_type == "level_complete":
            console.print(f"  [{ts}] [green]✓[/green] Level {data.get('level')} complete")
        elif event_type == "worker_started":
            wid = data.get("worker_id")
            port = data.get("port")
            console.print(f"  [{ts}] [cyan]+[/cyan] Worker {wid} started on port {port}")
        else:
            console.print(f"  [{ts}] {event_type}")

    console.print()


def show_tasks_view(state: StateManager, level_filter: int | None) -> None:
    """Show detailed task table.

    Args:
        state: State manager
        level_filter: Level to filter to
    """
    console.print()
    console.print(Panel("[bold cyan]Task Details[/bold cyan]"))
    console.print()

    table = Table(show_header=True)
    table.add_column("Task ID")
    table.add_column("Status")
    table.add_column("Level", justify="center")
    table.add_column("Worker", justify="center")
    table.add_column("Description")

    all_tasks = state._state.get("tasks", {})

    if not all_tasks:
        console.print("[dim]No tasks found[/dim]")
        return

    for task_id, task in sorted(all_tasks.items()):
        task_level = task.get("level", 1)
        if level_filter and task_level != level_filter:
            continue

        status = task.get("status", "pending")
        if status == TaskStatus.COMPLETE.value:
            status_display = "[green]complete[/green]"
        elif status == TaskStatus.IN_PROGRESS.value:
            status_display = "[yellow]in_progress[/yellow]"
        elif status == TaskStatus.FAILED.value:
            status_display = "[red]failed[/red]"
        else:
            status_display = f"[dim]{status}[/dim]"

        worker_id = task.get("worker_id")
        worker_display = f"W{worker_id}" if worker_id is not None else "-"

        desc = task.get("description", task.get("title", ""))[:50]

        table.add_row(task_id, status_display, str(task_level), worker_display, desc)

    console.print(table)


def show_workers_view(state: StateManager) -> None:
    """Show detailed per-worker info.

    Args:
        state: State manager
    """
    console.print()
    console.print(Panel("[bold cyan]Worker Details[/bold cyan]"))
    console.print()

    table = Table(show_header=True)
    table.add_column("Worker")
    table.add_column("Status")
    table.add_column("Container")
    table.add_column("Port", justify="center")
    table.add_column("Branch")
    table.add_column("Current Task")
    table.add_column("Progress")

    workers = state.get_all_workers()
    workers_data = state._state.get("workers", {})

    if not workers:
        console.print("[dim]No workers active[/dim]")
        return

    for worker_id, worker in sorted(workers.items()):
        color = WORKER_COLORS.get(worker.status, "white")
        status_display = f"[{color}]{worker.status.value}[/{color}]"

        worker_info = workers_data.get(str(worker_id), {})
        container = worker_info.get("container", f"zerg-worker-{worker_id}")
        branch = worker_info.get("branch", f"zerg/{state.feature}/worker-{worker_id}")

        ctx_pct = int(worker.context_usage * 100)
        progress = f"{ctx_pct}% ctx"

        table.add_row(
            f"worker-{worker_id}",
            status_display,
            container,
            str(worker.port) if worker.port else "-",
            branch,
            worker.current_task or "-",
            progress,
        )

    console.print(table)


def show_commits_view(state: StateManager, feature: str) -> None:
    """Show recent commits per worker branch.

    Args:
        state: State manager
        feature: Feature name
    """
    import subprocess

    console.print()
    console.print(Panel("[bold cyan]Worker Commits[/bold cyan]"))
    console.print()

    table = Table(show_header=True)
    table.add_column("Worker")
    table.add_column("Branch")
    table.add_column("Commits", justify="center")
    table.add_column("Latest Commit")

    workers = state.get_all_workers()
    workers_data = state._state.get("workers", {})

    if not workers:
        console.print("[dim]No workers active[/dim]")
        return

    for worker_id, worker in sorted(workers.items()):
        worker_info = workers_data.get(str(worker_id), {})
        branch = worker_info.get("branch", f"zerg/{feature}/worker-{worker_id}")

        try:
            result = subprocess.run(
                ["git", "log", "--oneline", "-5", branch],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                commit_count = len([line for line in lines if line])
                latest = lines[0][:60] if lines and lines[0] else "-"
            else:
                commit_count = 0
                latest = "[dim]branch not found[/dim]"
        except Exception:
            commit_count = 0
            latest = "[dim]error[/dim]"

        table.add_row(
            f"worker-{worker_id}",
            branch,
            str(commit_count),
            latest,
        )

    console.print(table)


def show_watch_status(
    state: StateManager,
    feature: str,
    level_filter: int | None,
    interval: int,
) -> None:
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
        "workers": {str(wid): w.to_dict() for wid, w in state.get_all_workers().items()},
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


def get_metrics_dict(state: StateManager) -> dict[str, Any] | None:
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
