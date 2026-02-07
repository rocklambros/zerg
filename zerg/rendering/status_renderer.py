"""Status display renderer.

Extracts Rich rendering logic from ``zerg.commands.status`` into a
dedicated renderer class and standalone helper functions for clean SRP
separation.

TASK-013 will populate the method/function bodies by moving the render
functions from ``zerg.commands.status`` into this module.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from zerg.state import StateManager


class StatusRenderer:
    """Render ZERG execution status to the terminal via Rich.

    This class is a stub created by TASK-012.  TASK-013 will move the
    rendering logic from ``zerg.commands.status`` here.
    """

    def __init__(self, state: StateManager, feature: str) -> None:
        """Initialize the status renderer.

        Args:
            state: State manager instance.
            feature: Feature name.
        """
        self.state = state
        self.feature = feature

    def render_full(self, level_filter: int | None = None) -> None:
        """Render the full status view.

        Args:
            level_filter: Optional level to filter to.
        """
        pass

    def render_level_status(self, level_filter: int | None = None) -> None:
        """Render level status table.

        Args:
            level_filter: Optional level to filter to.
        """
        pass

    def render_worker_status(self) -> None:
        """Render worker status table."""
        pass

    def render_worker_metrics(self) -> None:
        """Render worker metrics table."""
        pass

    def render_level_metrics(self) -> None:
        """Render level metrics table."""
        pass

    def render_recent_events(self, limit: int = 5) -> None:
        """Render recent events.

        Args:
            limit: Number of events to show.
        """
        pass

    def render_tasks_view(self, level_filter: int | None = None) -> None:
        """Render detailed task table.

        Args:
            level_filter: Optional level to filter to.
        """
        pass

    def render_workers_view(self) -> None:
        """Render detailed per-worker info."""
        pass

    def render_commits_view(self) -> None:
        """Render recent commits per worker branch."""
        pass


# -- standalone helper functions (stubs) -----------------------------------


def create_progress_bar(percent: float, width: int = 20) -> str:
    """Create a text progress bar with Rich markup.

    Args:
        percent: Percentage complete (0-100).
        width: Bar width in characters.

    Returns:
        Progress bar string with Rich markup.
    """
    pass


def format_elapsed(start: Any) -> str:
    """Format elapsed time from a start datetime.

    Args:
        start: Start datetime.

    Returns:
        Formatted elapsed string like '5m 32s'.
    """
    pass


def compact_progress_bar(percent: float, width: int = 20) -> str:
    """Create a compact Unicode block progress bar.

    Args:
        percent: Percentage complete (0-100).
        width: Bar width in characters.

    Returns:
        Progress bar string without Rich markup.
    """
    pass


def format_duration(ms: int | None) -> str:
    """Format duration in milliseconds to human-readable string.

    Args:
        ms: Duration in milliseconds, or None.

    Returns:
        Formatted string like '1.2s', '4m30s', or '-'.
    """
    pass
