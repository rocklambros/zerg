"""Dry-run report renderer.

Extracts all Rich rendering logic from ``zerg.dryrun.DryRunSimulator``
into a dedicated renderer class for clean SRP separation.

TASK-013 will populate the method bodies by moving the ``_render_*``
methods from ``DryRunSimulator`` into this class.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zerg.dryrun import DryRunReport


class DryRunRenderer:
    """Render a :class:`DryRunReport` to the terminal via Rich.

    This class is a stub created by TASK-012.  TASK-013 will move the
    rendering methods from ``DryRunSimulator`` here.
    """

    def render(self, report: DryRunReport) -> None:
        """Render the full dry-run report.

        Args:
            report: Completed dry-run report to display.
        """
        pass

    def render_preflight(self, report: DryRunReport) -> None:
        """Render pre-flight checks panel."""
        pass

    def render_validation(self, report: DryRunReport) -> None:
        """Render validation checks panel."""
        pass

    def render_risk(self, report: DryRunReport) -> None:
        """Render risk assessment panel."""
        pass

    def render_levels(self, report: DryRunReport) -> None:
        """Render per-level task tables."""
        pass

    def render_worker_loads(self, report: DryRunReport) -> None:
        """Render worker load balance panel."""
        pass

    def render_gantt(self, report: DryRunReport) -> None:
        """Render Gantt-style timeline visualization."""
        pass

    def render_timeline(self, report: DryRunReport) -> None:
        """Render timeline estimate panel."""
        pass

    def render_snapshots(self, report: DryRunReport) -> None:
        """Render projected status snapshots."""
        pass

    def render_gates(self, report: DryRunReport) -> None:
        """Render quality gates panel."""
        pass

    def render_summary(self, report: DryRunReport) -> None:
        """Render summary line."""
        pass
