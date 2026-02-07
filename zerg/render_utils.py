"""Shared rendering utilities for ZERG status and dry-run displays.

**Backward-compatibility shim** -- all functionality has moved to
:mod:`zerg.rendering.shared`.  This module re-exports the public API so
existing callers (e.g. ``zerg.dryrun``) continue to work until they are
updated by TASK-013.
"""

from zerg.rendering.shared import (  # noqa: F401 -- re-export
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
