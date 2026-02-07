"""ZERG status command - show execution progress."""

import json
import time
from pathlib import Path

import click
from rich.live import Live

import zerg.rendering.status_renderer as _status_renderer
from zerg.claude_tasks_reader import ClaudeTasksReader
from zerg.constants import SPECS_DIR
from zerg.logging import get_logger
from zerg.rendering.status_renderer import (  # noqa: F401 -- re-exports
    DashboardRenderer,
    build_status_output,
    compact_progress_bar,
    create_progress_bar,
    format_duration,
    format_elapsed,
    format_step_progress,
    get_metrics_dict,
    get_step_progress_for_task,
)
from zerg.state import StateManager

# The canonical Console instance for this module.  Tests patch
# ``zerg.commands.status.console`` so every render function called from
# here must receive this object (or the mock that replaces it).
console = _status_renderer.console
logger = get_logger("status")


# ---------------------------------------------------------------------------
# Thin wrappers that forward the patchable ``console`` / ``Live`` / ``time``
# references from *this* module into the renderer implementations.
# ---------------------------------------------------------------------------


def show_level_status(state: StateManager, level_filter: int | None) -> None:  # noqa: D401
    """Show level status table (forwards to renderer)."""
    _status_renderer.show_level_status(state, level_filter, _console=console)


def show_worker_status(state: StateManager) -> None:  # noqa: D401
    """Show worker status table (forwards to renderer)."""
    _status_renderer.show_worker_status(state, _console=console)


def show_recent_events(state: StateManager, limit: int = 5) -> None:  # noqa: D401
    """Show recent events (forwards to renderer)."""
    _status_renderer.show_recent_events(state, limit, _console=console)


def show_tasks_view(state: StateManager, level_filter: int | None) -> None:  # noqa: D401
    """Show detailed task table (forwards to renderer)."""
    _status_renderer.show_tasks_view(state, level_filter, _console=console)


def show_workers_view(state: StateManager) -> None:  # noqa: D401
    """Show detailed per-worker info (forwards to renderer)."""
    _status_renderer.show_workers_view(state, _console=console)


def show_commits_view(state: StateManager, feature: str) -> None:  # noqa: D401
    """Show recent commits per worker branch (forwards to renderer)."""
    _status_renderer.show_commits_view(state, feature, _console=console)


def show_worker_metrics(state: StateManager) -> None:  # noqa: D401
    """Show worker metrics (forwards to renderer)."""
    _status_renderer.show_worker_metrics(state, _console=console)


def show_level_metrics(state: StateManager) -> None:  # noqa: D401
    """Show level metrics (forwards to renderer)."""
    _status_renderer.show_level_metrics(state, _console=console)


def show_live_status(state: StateManager, feature: str) -> None:  # noqa: D401
    """Live event streaming mode (forwards to renderer)."""
    _status_renderer.show_live_status(state, feature, _console=console, _live_cls=Live, _time_sleep=time.sleep)


def show_dashboard(state: StateManager, feature: str, interval: int = 1) -> None:  # noqa: D401
    """Real-time dashboard view (forwards to renderer)."""
    _status_renderer.show_dashboard(state, feature, interval, _console=console, _live_cls=Live, _time_sleep=time.sleep)


def show_status(state: StateManager, feature: str, level_filter: int | None) -> None:  # noqa: D401
    """Show current status (forwards to renderer)."""
    _status_renderer.show_status(state, feature, level_filter, _console=console)


def show_watch_status(
    state: StateManager,
    feature: str,
    level_filter: int | None,
    interval: int,
) -> None:  # noqa: D401
    """Show continuously updating status (forwards to renderer)."""
    _status_renderer.show_watch_status(
        state, feature, level_filter, interval, _console=console, _live_cls=Live, _time_sleep=time.sleep
    )


def show_json_status(state: StateManager, level_filter: int | None) -> None:  # noqa: D401
    """Output status as JSON (forwards to renderer)."""
    _status_renderer.show_json_status(state, level_filter, _console=console)


# Re-export all rendering symbols for backward compatibility.
# Tests and other modules import these from zerg.commands.status.
__all__ = [
    "DashboardRenderer",
    "build_status_output",
    "compact_progress_bar",
    "create_progress_bar",
    "detect_feature",
    "format_duration",
    "format_elapsed",
    "format_step_progress",
    "get_metrics_dict",
    "get_step_progress_for_task",
    "show_commits_view",
    "show_dashboard",
    "show_json_status",
    "show_level_metrics",
    "show_level_status",
    "show_live_status",
    "show_recent_events",
    "show_status",
    "show_tasks_view",
    "show_watch_status",
    "show_worker_metrics",
    "show_worker_status",
    "show_workers_view",
]


@click.command()
@click.option("--feature", "-f", help="Feature to show status for")
@click.option("--watch", "-w", is_flag=True, help="Continuous update mode")
@click.option("--dashboard", "-d", is_flag=True, help="Real-time dashboard view")
@click.option("--live", is_flag=True, help="Live event streaming mode")
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
    live: bool,
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
            except Exception:  # noqa: BLE001 -- intentional fallback
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
                        except Exception:  # noqa: BLE001 -- best-effort JSON display
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
        elif live:
            show_live_status(state, feature)
        elif dashboard:
            show_dashboard(state, feature, interval)
        elif watch:
            show_watch_status(state, feature, level, interval)
        else:
            show_status(state, feature, level)

    except KeyboardInterrupt:
        console.print("\n[dim]Stopped watching[/dim]")
    except Exception as e:  # noqa: BLE001 -- top-level CLI error handler
        console.print(f"\n[red]Error:[/red] {e}")
        raise SystemExit(1) from None


def detect_feature() -> str | None:
    """Detect active feature. Re-exported from shared utility.

    See :func:`zerg.commands._utils.detect_feature` for details.
    """
    from zerg.commands._utils import detect_feature as _detect

    return _detect()
