"""Shared rendering utilities for ZERG status and dry-run displays.

Provides reusable Rich rendering components used by both
zerg/dryrun.py and zerg/commands/status.py.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.text import Text

if TYPE_CHECKING:
    from zerg.dryrun import LevelTimeline


def render_progress_bar(
    percent: float,
    width: int = 20,
    filled_style: str = "green",
    empty_style: str = "dim",
) -> Text:
    """Create a Rich Text progress bar.

    Args:
        percent: Percentage complete (0-100)
        width: Bar width in characters
        filled_style: Rich style for filled portion
        empty_style: Rich style for empty portion

    Returns:
        Rich Text with styled progress bar
    """
    filled = int(width * percent / 100)
    empty = width - filled
    bar = Text()
    bar.append("\u2588" * filled, style=filled_style)
    bar.append("\u2591" * empty, style=empty_style)
    return bar


def render_progress_bar_str(percent: float, width: int = 20) -> str:
    """Create a plain string progress bar.

    Args:
        percent: Percentage complete (0-100)
        width: Bar width in characters

    Returns:
        Progress bar string
    """
    filled = int(width * percent / 100)
    empty = width - filled
    return "\u2588" * filled + "\u2591" * empty


def render_gantt_chart(
    per_level: dict[int, LevelTimeline],
    worker_count: int,
    chart_width: int = 50,
) -> Text:
    """Render a horizontal Gantt-style chart showing worker execution per level.

    Each level shows bars for each worker based on their load in that level.

    Args:
        per_level: LevelTimeline data per level number
        worker_count: Total number of workers
        chart_width: Width of each bar in characters

    Returns:
        Rich Text with the complete Gantt chart
    """
    if not per_level:
        return Text("  No timeline data")

    total_wall = sum(lt.wall_minutes for lt in per_level.values())
    if total_wall == 0:
        return Text("  No timeline data")

    lines: list[Text] = []

    # Header
    header = Text()
    header.append("  Worker  ", style="bold")
    header.append("0")
    header.append(" " * (chart_width - 2))
    header.append(f"{total_wall}m")
    lines.append(header)

    cumulative = 0
    for level_num in sorted(per_level.keys()):
        lt = per_level[level_num]

        # Level separator
        sep = Text()
        sep.append(f"  L{level_num}      ", style="bold cyan")
        sep.append("\u2500" * chart_width, style="dim")
        lines.append(sep)

        # Per-worker bars for this level
        level_max = lt.wall_minutes if lt.wall_minutes > 0 else 1
        for worker_id in range(worker_count):
            load = lt.worker_loads.get(worker_id, 0)
            bar_len = int(chart_width * load / level_max) if level_max > 0 else 0

            line = Text()
            line.append(f"  W{worker_id}      ", style="bold")

            # Offset for position in overall timeline
            offset_chars = int(chart_width * cumulative / total_wall) if total_wall > 0 else 0
            offset_chars = min(offset_chars, chart_width - 1)

            # Bar
            bar_len = min(bar_len, chart_width - offset_chars)
            line.append(" " * offset_chars)
            if load > 0:
                line.append("\u2593" * max(bar_len, 1), style="cyan")
                line.append(f" {load}m", style="dim")
            else:
                line.append("\u00b7", style="dim")
            lines.append(line)

        cumulative += lt.wall_minutes

    return Text("\n").join(lines)


def format_elapsed_compact(total_seconds: int) -> str:
    """Format seconds into compact elapsed string.

    Args:
        total_seconds: Total seconds

    Returns:
        Formatted string like '5m32s' or '1h23m'
    """
    if total_seconds < 60:
        return f"{total_seconds}s"

    minutes = total_seconds // 60
    seconds = total_seconds % 60

    if minutes < 60:
        return f"{minutes}m{seconds}s" if seconds > 0 else f"{minutes}m"

    hours = minutes // 60
    remaining = minutes % 60
    return f"{hours}h{remaining}m" if remaining > 0 else f"{hours}h"
