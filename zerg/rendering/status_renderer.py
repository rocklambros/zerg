"""Status display renderer.

Extracts Rich rendering logic from ``zerg.commands.status`` into a
dedicated renderer class and standalone helper functions for clean SRP
separation.

Moved from ``zerg.commands.status`` by TASK-013.

Functions that produce terminal output accept an optional ``_console``
parameter.  When called directly, they use the module-level default.
When called via the thin wrappers in ``zerg.commands.status``, the
wrapper forwards the patchable ``status.console`` object so that
existing tests (which patch ``zerg.commands.status.console``) continue
to work.
"""

from __future__ import annotations

import json
import subprocess
import time as _time_mod
from datetime import datetime
from typing import TYPE_CHECKING, Any

from rich.console import Console, Group, RenderableType
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from zerg.constants import STATE_DIR, TaskStatus, WorkerStatus
from zerg.heartbeat import HeartbeatMonitor
from zerg.metrics import MetricsCollector

if TYPE_CHECKING:
    from zerg.state import StateManager

console = Console()

# Dashboard status symbols
LEVEL_SYMBOLS = {
    "complete": "[green]\u2713[/green]",
    "running": "[yellow]\u25cf[/yellow]",
    "pending": "[dim]\u25cb[/dim]",
    "merging": "[cyan]\u27f3[/cyan]",
    "conflict": "[red]\u2717[/red]",
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

# Step progress emoji indicators
STEP_INDICATORS = {
    "completed": "\u2705",
    "in_progress": "\U0001f504",
    "pending": "\u23f3",
    "failed": "\u274c",
}


# ---------------------------------------------------------------------------
# Standalone helper functions
# ---------------------------------------------------------------------------


def format_step_progress(
    current_step: int | None,
    total_steps: int | None,
    step_states: list[str] | None = None,
) -> str | None:
    """Format step progress as a visual indicator.

    Args:
        current_step: Current step number (1-indexed).
        total_steps: Total number of steps.
        step_states: List of states per step ("completed", "in_progress", "pending", "failed").

    Returns:
        Formatted string like "[Step 3/5: checkmarks]" or None if no steps.
    """
    if current_step is None or total_steps is None or total_steps == 0:
        return None

    # Build emoji indicators
    indicators = []
    if step_states:
        for state in step_states:
            indicators.append(STEP_INDICATORS.get(state, "\u23f3"))
    else:
        # Fallback: derive states from current_step
        for i in range(1, total_steps + 1):
            if i < current_step:
                indicators.append(STEP_INDICATORS["completed"])
            elif i == current_step:
                indicators.append(STEP_INDICATORS["in_progress"])
            else:
                indicators.append(STEP_INDICATORS["pending"])

    return f"[Step {current_step}/{total_steps}: {''.join(indicators)}]"


def get_step_progress_for_task(
    task_id: str,
    worker_id: int | None,
    heartbeat_monitor: HeartbeatMonitor | None,
) -> str | None:
    """Get step progress display for a task from heartbeat data.

    Args:
        task_id: The task ID.
        worker_id: The worker ID executing the task.
        heartbeat_monitor: HeartbeatMonitor instance for reading heartbeats.

    Returns:
        Formatted step progress string or None.
    """
    if worker_id is None or heartbeat_monitor is None:
        return None

    heartbeat = heartbeat_monitor.read(worker_id)
    if heartbeat is None:
        return None

    # Only show step progress if this heartbeat is for the requested task
    if heartbeat.task_id != task_id:
        return None

    return heartbeat.get_step_progress_display()


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
    return "\u2588" * filled + "\u2591" * empty


def create_progress_bar(percent: float, width: int = 20) -> str:
    """Create a text progress bar with Rich markup.

    Args:
        percent: Percentage complete
        width: Bar width in characters

    Returns:
        Progress bar string
    """
    filled = int(width * percent / 100)
    empty = width - filled
    return f"[green]{'\u2588' * filled}[/green][dim]{'\u2591' * empty}[/dim]"


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


# ---------------------------------------------------------------------------
# DashboardRenderer
# ---------------------------------------------------------------------------


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
            symbol = LEVEL_SYMBOLS.get(status, "\u25cb")

            line = Text()
            line.append(f"L{level_num} [")
            line.append(bar[: int(20 * percent / 100)], style="green")
            line.append(bar[int(20 * percent / 100) :], style="dim")
            line.append(f"] {percent:3.0f}% {complete:2}/{total:2} {symbol} {status_text}")
            lines.append(line)

        content = Text("\n").join(lines) if lines else Text("[dim]No levels[/dim]")
        return Panel(content, title="[bold]LEVELS[/bold]", title_align="left", padding=(0, 1))

    def _render_workers(self) -> Panel:
        """Render worker status section with step progress."""
        workers = self.state.get_all_workers()

        # Initialize heartbeat monitor for reading step progress
        heartbeat_monitor = HeartbeatMonitor(state_dir=STATE_DIR)

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

            # Get step progress from heartbeat
            step_progress = None
            if worker.current_task:
                heartbeat = heartbeat_monitor.read(worker_id)
                if heartbeat and heartbeat.task_id == worker.current_task:
                    step_progress = heartbeat.get_step_progress_display()

            # Show step progress or context bar
            if step_progress:
                line.append(f" {step_progress}")
            else:
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
                    line.append(" \u26a0", style="yellow")
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
                line.append("\u2713 ", style="green")
                line.append(f"{task_id} complete (worker-{worker_id}{duration_str})")
            elif event_type == "task_claimed":
                task_id = data.get("task_id", "?")
                worker_id = data.get("worker_id", "?")
                line.append("\u2192 ", style="cyan")
                line.append(f"{task_id} claimed by worker-{worker_id}")
            elif event_type == "task_failed":
                task_id = data.get("task_id", "?")
                error_msg = data.get("error", "unknown")[:30]
                line.append("\u2717 ", style="red")
                line.append(f"{task_id} failed: {error_msg}")
            elif event_type == "level_started":
                lvl = data.get("level", "?")
                task_count = data.get("tasks", "?")
                line.append("\u25b6 ", style="cyan")
                line.append(f"Level {lvl} started with {task_count} tasks")
            elif event_type == "level_complete":
                line.append("\u2713 ", style="green")
                line.append(f"Level {data.get('level', '?')} complete")
            elif event_type == "worker_started":
                line.append("+ ", style="cyan")
                line.append(f"Worker {data.get('worker_id', '?')} started")
            elif event_type == "merge_started":
                line.append("\u27f3 ", style="cyan")
                line.append(f"Level {data.get('level', '?')} merge started")
            elif event_type == "merge_complete":
                line.append("\u2713 ", style="green")
                line.append(f"Level {data.get('level', '?')} merge complete")
            elif event_type == "task_retry_scheduled":
                task_id = data.get("task_id", "?")
                backoff = data.get("backoff_seconds", "?")
                retry_num = data.get("retry_count", "?")
                line.append("\u21bb ", style="yellow")
                line.append(f"{task_id} retry #{retry_num} in {backoff}s")
            elif event_type == "task_retry_ready":
                line.append("\u21bb ", style="green")
                line.append(f"{data.get('task_id', '?')} retry ready")
            else:
                line.append(f"  {event_type}")

            lines.append(line)

        content = Text("[dim]No events yet[/dim]") if not lines else Text("\n").join(lines)
        return Panel(content, title="[bold]EVENTS[/bold]", title_align="left", padding=(0, 1))


# ---------------------------------------------------------------------------
# Standalone render functions
#
# Each function that produces console output accepts an optional ``_console``
# keyword argument.  This allows ``zerg.commands.status`` to forward its own
# (patchable) console instance while still providing a usable default for
# direct callers.
# ---------------------------------------------------------------------------


def show_level_status(state: StateManager, level_filter: int | None, *, _console: Console | None = None) -> None:
    """Show level status table.

    Args:
        state: State manager
        level_filter: Level to filter to
    """
    c = _console or console
    c.print("[bold]Level Status:[/bold]")

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
                status_display = "[green]\u2713 DONE[/green]"
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

    c.print(table)
    c.print()


def show_worker_status(state: StateManager, *, _console: Console | None = None) -> None:
    """Show worker status table.

    Args:
        state: State manager
    """
    c = _console or console
    c.print("[bold]Worker Status:[/bold]")

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

    c.print(table)
    c.print()


def show_recent_events(state: StateManager, limit: int = 5, *, _console: Console | None = None) -> None:
    """Show recent events.

    Args:
        state: State manager
        limit: Number of events to show
    """
    c = _console or console
    events = state.get_events(limit=limit)

    if not events:
        return

    c.print("[bold]Recent Events:[/bold]")

    for event in events[-limit:]:
        ts = event.get("timestamp", "")[:8]  # Just time portion
        event_type = event.get("event", "unknown")
        data = event.get("data", {})

        # Format event
        if event_type == "task_complete":
            task_id = data.get("task_id")
            worker_id = data.get("worker_id")
            c.print(f"  [{ts}] [green]\u2713[/green] {task_id} completed by worker-{worker_id}")
        elif event_type == "task_failed":
            task_id = data.get("task_id")
            error = data.get("error", "unknown")
            c.print(f"  [{ts}] [red]\u2717[/red] {task_id} failed: {error}")
        elif event_type == "level_started":
            level = data.get("level")
            tasks = data.get("tasks")
            c.print(f"  [{ts}] [cyan]\u25b6[/cyan] Level {level} started with {tasks} tasks")
        elif event_type == "level_complete":
            c.print(f"  [{ts}] [green]\u2713[/green] Level {data.get('level')} complete")
        elif event_type == "worker_started":
            wid = data.get("worker_id")
            port = data.get("port")
            c.print(f"  [{ts}] [cyan]+[/cyan] Worker {wid} started on port {port}")
        else:
            c.print(f"  [{ts}] {event_type}")

    c.print()


def show_tasks_view(state: StateManager, level_filter: int | None, *, _console: Console | None = None) -> None:
    """Show detailed task table with step progress.

    Args:
        state: State manager
        level_filter: Level to filter to
    """
    c = _console or console
    c.print()
    c.print(Panel("[bold cyan]Task Details[/bold cyan]"))
    c.print()

    table = Table(show_header=True)
    table.add_column("Task ID")
    table.add_column("Status")
    table.add_column("Level", justify="center")
    table.add_column("Worker", justify="center")
    table.add_column("Step Progress")
    table.add_column("Description")

    all_tasks = state._state.get("tasks", {})

    if not all_tasks:
        c.print("[dim]No tasks found[/dim]")
        return

    # Initialize heartbeat monitor for reading step progress
    heartbeat_monitor = HeartbeatMonitor(state_dir=STATE_DIR)

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

        # Get step progress from heartbeat if task is in progress
        step_progress = "-"
        if status == TaskStatus.IN_PROGRESS.value and worker_id is not None:
            progress = get_step_progress_for_task(task_id, worker_id, heartbeat_monitor)
            if progress:
                step_progress = progress

        desc = task.get("description", task.get("title", ""))[:40]

        table.add_row(task_id, status_display, str(task_level), worker_display, step_progress, desc)

    c.print(table)


def show_workers_view(state: StateManager, *, _console: Console | None = None) -> None:
    """Show detailed per-worker info with step progress.

    Args:
        state: State manager
    """
    c = _console or console
    c.print()
    c.print(Panel("[bold cyan]Worker Details[/bold cyan]"))
    c.print()

    table = Table(show_header=True)
    table.add_column("Worker")
    table.add_column("Status")
    table.add_column("Container")
    table.add_column("Port", justify="center")
    table.add_column("Current Task")
    table.add_column("Step Progress")
    table.add_column("Context")

    workers = state.get_all_workers()
    workers_data = state._state.get("workers", {})

    if not workers:
        c.print("[dim]No workers active[/dim]")
        return

    # Initialize heartbeat monitor for reading step progress
    heartbeat_monitor = HeartbeatMonitor(state_dir=STATE_DIR)

    for worker_id, worker in sorted(workers.items()):
        color = WORKER_COLORS.get(worker.status, "white")
        status_display = f"[{color}]{worker.status.value}[/{color}]"

        worker_info = workers_data.get(str(worker_id), {})
        container = worker_info.get("container", f"zerg-worker-{worker_id}")

        ctx_pct = int(worker.context_usage * 100)
        ctx_display = f"{ctx_pct}% ctx"

        # Get step progress from heartbeat
        step_progress = "-"
        if worker.current_task:
            heartbeat = heartbeat_monitor.read(worker_id)
            if heartbeat and heartbeat.task_id == worker.current_task:
                progress = heartbeat.get_step_progress_display()
                if progress:
                    step_progress = progress

        table.add_row(
            f"worker-{worker_id}",
            status_display,
            container,
            str(worker.port) if worker.port else "-",
            worker.current_task or "-",
            step_progress,
            ctx_display,
        )

    c.print(table)


def show_commits_view(state: StateManager, feature: str, *, _console: Console | None = None) -> None:
    """Show recent commits per worker branch.

    Args:
        state: State manager
        feature: Feature name
    """
    c = _console or console
    c.print()
    c.print(Panel("[bold cyan]Worker Commits[/bold cyan]"))
    c.print()

    table = Table(show_header=True)
    table.add_column("Worker")
    table.add_column("Branch")
    table.add_column("Commits", justify="center")
    table.add_column("Latest Commit")

    workers = state.get_all_workers()
    workers_data = state._state.get("workers", {})

    if not workers:
        c.print("[dim]No workers active[/dim]")
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
        except Exception:  # noqa: BLE001 -- best-effort git log
            commit_count = 0
            latest = "[dim]error[/dim]"

        table.add_row(
            f"worker-{worker_id}",
            branch,
            str(commit_count),
            latest,
        )

    c.print(table)


def show_worker_metrics(state: StateManager, *, _console: Console | None = None) -> None:
    """Show worker metrics table with timing information.

    Args:
        state: State manager
    """
    from zerg.logging import get_logger

    c = _console or console
    logger = get_logger("status")

    try:
        collector = MetricsCollector(state)
        feature_metrics = collector.compute_feature_metrics()
    except Exception as e:  # noqa: BLE001 -- metrics are best-effort
        logger.debug(f"Could not compute metrics: {e}")
        return

    if not feature_metrics.worker_metrics:
        return

    c.print("[bold]Worker Metrics:[/bold]")

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

    c.print(table)
    c.print()


def show_level_metrics(state: StateManager, *, _console: Console | None = None) -> None:
    """Show level metrics table with timing and percentiles.

    Args:
        state: State manager
    """
    from zerg.logging import get_logger

    c = _console or console
    logger = get_logger("status")

    try:
        collector = MetricsCollector(state)
        feature_metrics = collector.compute_feature_metrics()
    except Exception as e:  # noqa: BLE001 -- metrics are best-effort
        logger.debug(f"Could not compute metrics: {e}")
        return

    if not feature_metrics.level_metrics:
        return

    c.print("[bold]Level Metrics:[/bold]")

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

    c.print(table)
    c.print()


def show_live_status(
    state: StateManager,
    feature: str,
    *,
    _console: Console | None = None,
    _live_cls: type | None = None,
    _time_sleep: Any = None,
) -> None:
    """Live event streaming mode using EventEmitter.

    Subscribes to events and displays them in real-time using Rich Live.

    Args:
        state: State manager
        feature: Feature name
    """
    from zerg.event_emitter import EventEmitter

    c = _console or console
    live_cls = _live_cls or Live
    sleep_fn = _time_sleep or _time_mod.sleep

    emitter = EventEmitter(feature)
    events_text = Text()
    event_count = 0

    def handle_event(event_type: str, data: dict[str, Any]) -> None:
        nonlocal events_text, event_count
        event_count += 1
        ts = datetime.now().strftime("%H:%M:%S")

        line = Text()
        line.append(f"[{ts}] ", style="dim")

        if event_type == "level_start":
            line.append("\u25b6 ", style="cyan")
            line.append(f"Level {data.get('level', '?')} started")
        elif event_type == "task_complete":
            line.append("\u2713 ", style="green")
            line.append(f"Task {data.get('task_id', '?')} complete")
        elif event_type == "task_fail":
            line.append("\u2717 ", style="red")
            line.append(f"Task {data.get('task_id', '?')} failed: {data.get('error', 'unknown')[:40]}")
        elif event_type == "level_complete":
            line.append("\u2713 ", style="green bold")
            line.append(f"Level {data.get('level', '?')} complete")
        else:
            line.append(f"\u2022 {event_type}: ")
            line.append(str(data)[:60])

        events_text.append(line)
        events_text.append("\n")

    c.print(f"[bold]Live Events for {feature}[/bold]")
    c.print("[dim]Watching for events... (Ctrl+C to stop)[/dim]\n")

    emitter.start_watching(handle_event)

    try:
        with live_cls(events_text, console=c, refresh_per_second=4) as live:
            while True:
                sleep_fn(0.25)
                live.update(events_text)
    except KeyboardInterrupt:
        pass
    finally:
        emitter.stop_watching()
        c.print(f"\n[dim]Received {event_count} events[/dim]")


def show_dashboard(
    state: StateManager,
    feature: str,
    interval: int = 1,
    *,
    _console: Console | None = None,
    _live_cls: type | None = None,
    _time_sleep: Any = None,
) -> None:
    """Real-time dashboard view.

    Falls back to reading Claude Code Tasks from disk when the state JSON
    has no task data (e.g., when workers were launched via slash commands).

    Args:
        state: State manager
        feature: Feature name
        interval: Refresh interval in seconds
    """
    from zerg.logging import get_logger

    c = _console or console
    live_cls = _live_cls or Live
    sleep_fn = _time_sleep or _time_mod.sleep
    logger = get_logger("status")

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

    with live_cls(console=c, refresh_per_second=1, screen=True) as live:
        try:
            while True:
                if reader and task_list_dir:
                    state.inject_state(reader.read_tasks(task_list_dir))
                else:
                    state.load()
                live.update(renderer.render())
                sleep_fn(interval)
        except KeyboardInterrupt:
            pass


def show_status(
    state: StateManager,
    feature: str,
    level_filter: int | None,
    *,
    _console: Console | None = None,
) -> None:
    """Show current status.

    Args:
        state: State manager
        feature: Feature name
        level_filter: Level to filter to
    """
    c = _console or console

    # Header
    c.print()
    c.print(Panel(f"[bold cyan]ZERG Status: {feature}[/bold cyan]"))
    c.print()

    # Get task stats
    all_tasks = state._state.get("tasks", {})
    completed = len(state.get_tasks_by_status(TaskStatus.COMPLETE))
    total = len(all_tasks) if all_tasks else 42  # Fallback estimate

    # Progress bar
    progress_pct = (completed / total * 100) if total > 0 else 0
    progress_bar = create_progress_bar(progress_pct)
    c.print(f"Progress: {progress_bar} {progress_pct:.0f}% ({completed}/{total} tasks)")
    c.print()

    # Level status
    show_level_status(state, level_filter, _console=c)

    # Worker status
    show_worker_status(state, _console=c)

    # Worker metrics (timing, throughput)
    show_worker_metrics(state, _console=c)

    # Level metrics (duration, percentiles)
    show_level_metrics(state, _console=c)

    # Recent events
    show_recent_events(state, limit=5, _console=c)

    # Error state
    error = state.get_error()
    if error:
        c.print(f"\n[red]Error:[/red] {error}")


def show_watch_status(
    state: StateManager,
    feature: str,
    level_filter: int | None,
    interval: int,
    *,
    _console: Console | None = None,
    _live_cls: type | None = None,
    _time_sleep: Any = None,
) -> None:
    """Show continuously updating status.

    Args:
        state: State manager
        feature: Feature name
        level_filter: Level to filter to
        interval: Update interval
    """
    c = _console or console
    live_cls = _live_cls or Live
    sleep_fn = _time_sleep or _time_mod.sleep

    with live_cls(console=c, refresh_per_second=1) as live:
        while True:
            # Reload state
            state.load()

            # Build output
            output = build_status_output(state, feature, level_filter)
            live.update(output)

            sleep_fn(interval)


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


def show_json_status(
    state: StateManager,
    level_filter: int | None,
    *,
    _console: Console | None = None,
) -> None:
    """Output status as JSON.

    Args:
        state: State manager
        level_filter: Level to filter to
    """
    c = _console or console
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

    c.print(json.dumps(output, indent=2, default=str))


def get_metrics_dict(state: StateManager) -> dict[str, Any] | None:
    """Get metrics as a dictionary for JSON output.

    Args:
        state: State manager

    Returns:
        Metrics dictionary or None if unavailable
    """
    from zerg.logging import get_logger

    logger = get_logger("status")

    try:
        collector = MetricsCollector(state)
        feature_metrics = collector.compute_feature_metrics()
        return feature_metrics.to_dict()
    except Exception as e:  # noqa: BLE001 -- best-effort metrics
        logger.debug(f"Could not compute metrics: {e}")
        return None
