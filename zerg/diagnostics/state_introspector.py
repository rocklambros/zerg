"""ZERG state introspection for deep debugging."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from zerg.logging import get_logger

logger = get_logger("diagnostics.state")


@dataclass
class ZergHealthReport:
    """Health report from ZERG state introspection."""

    feature: str
    state_exists: bool
    total_tasks: int
    task_summary: dict[str, int] = field(default_factory=dict)
    worker_summary: dict[str, str] = field(default_factory=dict)
    failed_tasks: list[dict[str, Any]] = field(default_factory=list)
    stale_tasks: list[dict[str, Any]] = field(default_factory=list)
    recent_errors: list[str] = field(default_factory=list)
    current_level: int = 0
    is_paused: bool = False
    global_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "feature": self.feature,
            "state_exists": self.state_exists,
            "total_tasks": self.total_tasks,
            "task_summary": self.task_summary,
            "worker_summary": self.worker_summary,
            "failed_tasks": self.failed_tasks,
            "stale_tasks": self.stale_tasks,
            "recent_errors": self.recent_errors,
            "current_level": self.current_level,
            "is_paused": self.is_paused,
            "global_error": self.global_error,
        }


class ZergStateIntrospector:
    """Introspect ZERG state for diagnostic analysis."""

    def __init__(
        self,
        state_dir: Path | str = Path(".zerg/state"),
        logs_dir: Path | str = Path(".zerg/logs"),
    ) -> None:
        self.state_dir = Path(state_dir)
        self.logs_dir = Path(logs_dir)

    def find_latest_feature(self) -> str | None:
        """Find the most recently modified feature state file."""
        if not self.state_dir.exists():
            return None

        state_files = sorted(
            self.state_dir.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        # Skip backup files
        state_files = [f for f in state_files if not f.name.endswith(".bak")]
        if not state_files:
            return None
        return state_files[0].stem

    def get_health_report(self, feature: str) -> ZergHealthReport:
        """Generate a health report for a feature."""
        state_file = self.state_dir / f"{feature}.json"
        if not state_file.exists():
            return ZergHealthReport(
                feature=feature,
                state_exists=False,
                total_tasks=0,
            )

        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to read state file: {e}")
            return ZergHealthReport(
                feature=feature,
                state_exists=True,
                total_tasks=0,
                global_error=f"Corrupt state file: {e}",
            )

        # Extract task summary
        tasks = state.get("tasks", {})
        task_summary: dict[str, int] = {}
        failed_tasks: list[dict[str, Any]] = []
        total = 0

        for task_id, task_data in tasks.items():
            status = task_data.get("status", "unknown")
            task_summary[status] = task_summary.get(status, 0) + 1
            total += 1

            if status == "failed":
                failed_tasks.append(
                    {
                        "task_id": task_id,
                        "error": task_data.get("error", ""),
                        "retry_count": task_data.get("retry_count", 0),
                        "worker_id": task_data.get("worker_id"),
                    }
                )

        # Extract worker summary
        workers = state.get("workers", {})
        worker_summary: dict[str, str] = {}
        for wid, wdata in workers.items():
            if isinstance(wdata, dict):
                worker_summary[str(wid)] = wdata.get("status", "unknown")
            else:
                worker_summary[str(wid)] = str(wdata)

        # Find stale tasks (in_progress but no recent update)
        stale_tasks: list[dict[str, Any]] = []
        for task_id, task_data in tasks.items():
            if task_data.get("status") in ("in_progress", "claimed"):
                stale_tasks.append(
                    {
                        "task_id": task_id,
                        "status": task_data.get("status"),
                        "worker_id": task_data.get("worker_id"),
                    }
                )

        # Collect recent errors
        recent_errors: list[str] = []
        errors_seen: set[str] = set()
        for task_data in tasks.values():
            err = task_data.get("error", "")
            if err and err not in errors_seen:
                errors_seen.add(err)
                recent_errors.append(err)

        # Global state
        current_level = state.get("current_level", 0)
        is_paused = state.get("paused", False)
        global_error = state.get("error")

        return ZergHealthReport(
            feature=feature,
            state_exists=True,
            total_tasks=total,
            task_summary=task_summary,
            worker_summary=worker_summary,
            failed_tasks=failed_tasks,
            stale_tasks=stale_tasks,
            recent_errors=recent_errors,
            current_level=current_level,
            is_paused=is_paused,
            global_error=global_error,
        )

    def get_failed_task_details(self, feature: str) -> list[dict[str, Any]]:
        """Return detailed info for failed tasks."""
        report = self.get_health_report(feature)
        return report.failed_tasks

    def get_worker_logs(self, worker_id: int, lines: int = 50) -> dict[str, str]:
        """Get last N lines of worker stdout and stderr logs."""
        result: dict[str, str] = {"stdout": "", "stderr": ""}

        for stream in ("stdout", "stderr"):
            log_file = self.logs_dir / f"worker-{worker_id}.{stream}.log"
            if not log_file.exists():
                continue
            try:
                content = log_file.read_text(encoding="utf-8", errors="replace")
                all_lines = content.splitlines()
                result[stream] = "\n".join(all_lines[-lines:])
            except OSError as e:
                logger.warning(f"Failed to read {log_file}: {e}")
                result[stream] = f"<error reading log: {e}>"

        return result

    def detect_state_corruption(self, feature: str) -> list[str]:
        """Compare state tasks vs task-graph tasks, find orphans."""
        issues: list[str] = []

        state_file = self.state_dir / f"{feature}.json"
        if not state_file.exists():
            issues.append(f"State file not found: {state_file}")
            return issues

        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            issues.append(f"Cannot parse state file: {e}")
            return issues

        state_tasks = set(state.get("tasks", {}).keys())

        # Try to load task graph for comparison
        graph_file = Path(f".gsd/specs/{feature}/task-graph.json")
        if graph_file.exists():
            try:
                graph = json.loads(graph_file.read_text(encoding="utf-8"))
                graph_tasks = set()
                for task in graph.get("tasks", []):
                    tid = task.get("id", "")
                    if tid:
                        graph_tasks.add(tid)

                orphaned_state = state_tasks - graph_tasks
                missing_state = graph_tasks - state_tasks

                if orphaned_state:
                    issues.append(f"Tasks in state but not in graph: {sorted(orphaned_state)}")
                if missing_state:
                    issues.append(f"Tasks in graph but not in state: {sorted(missing_state)}")
            except (json.JSONDecodeError, OSError) as e:
                issues.append(f"Cannot parse task graph: {e}")
        else:
            issues.append(f"Task graph not found: {graph_file}")

        return issues
