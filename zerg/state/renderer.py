"""State renderer — STATE.md generation from current state.

Generates a human-readable markdown summary of execution state
including task progress, worker status, levels, blockers, and events.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from zerg.constants import GSD_DIR, TaskStatus
from zerg.logging import get_logger

if TYPE_CHECKING:
    from zerg.state.persistence import PersistenceLayer

logger = get_logger("state.renderer")


class StateRenderer:
    """Generates STATE.md from current execution state.

    Reads the in-memory state dict from the PersistenceLayer and
    produces a markdown file summarizing execution progress.
    """

    def __init__(self, persistence: PersistenceLayer) -> None:
        """Initialize state renderer.

        Args:
            persistence: PersistenceLayer instance for data access
        """
        self._persistence = persistence

    def generate_state_md(self, gsd_dir: str | Path | None = None) -> Path:
        """Generate a human-readable STATE.md file from current state.

        Creates a markdown file in the GSD directory summarizing the current
        execution state, task progress, and any decisions or blockers.

        Args:
            gsd_dir: GSD directory path (defaults to .gsd)

        Returns:
            Path to generated STATE.md file
        """
        gsd_path = Path(gsd_dir or GSD_DIR)
        gsd_path.mkdir(parents=True, exist_ok=True)
        state_md_path = gsd_path / "STATE.md"

        with self._persistence.lock:
            lines = self._build_state_md_content()

        state_md_path.write_text("\n".join(lines), encoding="utf-8")
        logger.info(f"Generated STATE.md at {state_md_path}")
        return state_md_path

    def _build_state_md_content(self) -> list[str]:
        """Build the content lines for STATE.md.

        Returns:
            List of markdown lines
        """
        lines: list[str] = []
        now = datetime.now().isoformat()
        state = self._persistence.state

        # Header
        lines.append(f"# ZERG State: {self._persistence.feature}")
        lines.append("")

        # Current phase info
        current_level = state.get("current_level", 0)
        started_at = state.get("started_at", "unknown")
        is_paused = state.get("paused", False)
        error = state.get("error")

        lines.append("## Current Phase")
        lines.append(f"- **Level:** {current_level}")
        lines.append(f"- **Started:** {started_at}")
        lines.append(f"- **Last Update:** {now}")
        if is_paused:
            lines.append("- **Status:** PAUSED")
        if error:
            lines.append(f"- **Error:** {error}")
        lines.append("")

        # Task progress table
        lines.append("## Tasks")
        lines.append("")
        lines.append("| ID | Status | Worker | Updated |")
        lines.append("|----|--------|--------|---------|")

        tasks = state.get("tasks", {})
        for task_id, task_state in sorted(tasks.items()):
            status = task_state.get("status", "unknown")
            worker = task_state.get("worker_id", "-")
            updated = task_state.get("updated_at", "-")
            # Truncate timestamp for display
            if isinstance(updated, str) and "T" in updated:
                updated = updated.split("T")[1][:8]
            lines.append(f"| {task_id} | {status} | {worker} | {updated} |")

        lines.append("")

        # Workers section
        workers = state.get("workers", {})
        if workers:
            lines.append("## Workers")
            lines.append("")
            lines.append("| ID | Status | Tasks Done | Branch |")
            lines.append("|----|--------|------------|--------|")
            for wid, worker_data in sorted(workers.items(), key=lambda x: int(x[0])):
                status = worker_data.get("status", "unknown")
                tasks_done = worker_data.get("tasks_completed", 0)
                branch = worker_data.get("branch", "-")
                # Truncate branch name
                if len(branch) > 30:
                    branch = "..." + branch[-27:]
                lines.append(f"| {wid} | {status} | {tasks_done} | {branch} |")
            lines.append("")

        # Levels section
        levels = state.get("levels", {})
        if levels:
            lines.append("## Levels")
            lines.append("")
            for level, level_data in sorted(levels.items(), key=lambda x: int(x[0])):
                status = level_data.get("status", "pending")
                merge_status = level_data.get("merge_status", "-")
                lines.append(f"- **Level {level}:** {status}")
                if merge_status != "-":
                    lines.append(f"  - Merge: {merge_status}")
                if merge_commit := level_data.get("merge_commit"):
                    lines.append(f"  - Commit: {merge_commit[:8]}")
            lines.append("")

        # Failed tasks details
        failed = self._get_failed_tasks(state)
        if failed:
            lines.append("## Blockers")
            lines.append("")
            for task_info in failed:
                task_id = task_info["task_id"]
                error_msg = task_info.get("error", "Unknown error")
                retry_count = task_info.get("retry_count", 0)
                lines.append(f"- **{task_id}** (retries: {retry_count})")
                lines.append(f"  - {error_msg}")
            lines.append("")

        # Recent events
        events = state.get("execution_log", [])[-10:]  # Last 10 events
        if events:
            lines.append("## Recent Events")
            lines.append("")
            for event in reversed(events):
                timestamp = event.get("timestamp", "")
                if isinstance(timestamp, str) and "T" in timestamp:
                    timestamp = timestamp.split("T")[1][:8]
                event_type = event.get("event", "unknown")
                lines.append(f"- `{timestamp}` {event_type}")
            lines.append("")

        return lines

    @staticmethod
    def _get_failed_tasks(state: dict[str, Any]) -> list[dict[str, Any]]:
        """Get failed tasks from state dict for rendering.

        Args:
            state: State dictionary

        Returns:
            List of failed task info dictionaries
        """
        failed = []
        for task_id, task_state in state.get("tasks", {}).items():
            if task_state.get("status") == TaskStatus.FAILED.value:
                failed.append(
                    {
                        "task_id": task_id,
                        "retry_count": task_state.get("retry_count", 0),
                        "error": task_state.get("error"),
                        "last_retry_at": task_state.get("last_retry_at"),
                    }
                )
        return failed
