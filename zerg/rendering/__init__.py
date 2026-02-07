"""Rendering package for ZERG CLI output.

Provides shared rendering utilities, and renderer classes for
dry-run and status displays.  Public API re-exported here for
convenience.
"""

from zerg.rendering.shared import (
    format_elapsed_compact,
    render_gantt_chart,
    render_progress_bar,
    render_progress_bar_str,
)

__all__ = [
    "format_elapsed_compact",
    "render_gantt_chart",
    "render_progress_bar",
    "render_progress_bar_str",
]
