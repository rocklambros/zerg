"""Read Claude Code Task files from disk for dashboard display.

Bridges the gap between slash-command workers (which use Claude Code Tasks)
and the Python CLI dashboard (which reads StateManager state dicts).
"""

import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from zerg.constants import TaskStatus
from zerg.logging import get_logger

logger = get_logger("claude_tasks_reader")

# Pattern for ZERG execution tasks: [L1] Title, [L2] Title, etc.
ZERG_TASK_RE = re.compile(r"^\[L(\d+)\]\s+(.+)")

# Pattern for ZERG meta tasks: [Plan], [Design], [Rush], etc.
ZERG_META_RE = re.compile(r"^\[(Plan|Design|Rush|Debug|Init|Cleanup|Review|Build|Test|Status)\]")

# Claude Task status → ZERG TaskStatus mapping
_STATUS_MAP_NO_BLOCKERS = {
    "pending": TaskStatus.PENDING.value,
    "in_progress": TaskStatus.IN_PROGRESS.value,
    "completed": TaskStatus.COMPLETE.value,
}

_STATUS_BLOCKED = TaskStatus.BLOCKED.value


class ClaudeTasksReader:
    """Read Claude Code Tasks from ~/.claude/tasks/ on disk.

    Discovers ZERG task lists by scanning for [L{n}] subject patterns,
    then synthesizes a state dict compatible with StateManager._state.
    """

    TASKS_DIR = Path.home() / ".claude" / "tasks"

    def __init__(self, tasks_dir: Path | None = None) -> None:
        """Initialize reader.

        Args:
            tasks_dir: Override task directory (for testing).
        """
        self._tasks_dir = tasks_dir or self.TASKS_DIR
        self._cached_dir: Path | None = None
        self._cache_time: float = 0.0
        self._cache_ttl: float = 10.0  # seconds

    def find_feature_task_list(self, feature: str) -> Path | None:
        """Find the Claude Task list directory containing ZERG tasks for a feature.

        Scans ~/.claude/tasks/{UUID}/ directories for task JSON files with
        [L{n}] subject prefixes. Returns the most recently modified match.

        Args:
            feature: Feature name to match against task descriptions.

        Returns:
            Path to task list directory, or None if not found.
        """
        # Return cached result if still fresh
        now = time.monotonic()
        if self._cached_dir and (now - self._cache_time) < self._cache_ttl:
            if self._cached_dir.exists():
                return self._cached_dir

        if not self._tasks_dir.exists():
            logger.debug("Tasks directory not found: %s", self._tasks_dir)
            return None

        # List all UUID directories, sorted by mtime (newest first)
        try:
            task_list_dirs = sorted(
                (d for d in self._tasks_dir.iterdir() if d.is_dir()),
                key=lambda d: d.stat().st_mtime,
                reverse=True,
            )
        except OSError as e:
            logger.warning("Failed to list tasks directory: %s", e)
            return None

        feature_lower = feature.lower()

        for dir_path in task_list_dirs:
            zerg_count, feature_match = self._scan_dir_for_zerg_tasks(dir_path, feature_lower)
            if zerg_count > 0 and feature_match:
                logger.info(
                    "Found ZERG task list for '%s' at %s (%d tasks)",
                    feature,
                    dir_path.name,
                    zerg_count,
                )
                self._cached_dir = dir_path
                self._cache_time = now
                return dir_path

        # Fallback: return any dir with ZERG tasks (no feature match required)
        for dir_path in task_list_dirs:
            zerg_count, _ = self._scan_dir_for_zerg_tasks(dir_path, feature_lower)
            if zerg_count >= 3:  # At least 3 level tasks = likely a real execution
                logger.info(
                    "Found ZERG task list (no feature match) at %s (%d tasks)",
                    dir_path.name,
                    zerg_count,
                )
                self._cached_dir = dir_path
                self._cache_time = now
                return dir_path

        logger.debug("No ZERG task list found for feature '%s'", feature)
        return None

    def read_tasks(self, task_list_dir: Path) -> dict[str, Any]:
        """Read all task JSON files and synthesize a StateManager-compatible state dict.

        Args:
            task_list_dir: Path to a Claude Task list directory.

        Returns:
            State dict with keys: tasks, workers, levels, execution_log, etc.
        """
        tasks: dict[str, Any] = {}
        max_level = 0

        # Read all JSON task files
        try:
            json_files = sorted(task_list_dir.glob("*.json"))
        except OSError as e:
            logger.warning("Failed to list task files: %s", e)
            return self._empty_state()

        for json_path in json_files:
            try:
                data = json.loads(json_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as e:
                logger.debug("Skipping %s: %s", json_path.name, e)
                continue

            subject = data.get("subject", "")
            match = ZERG_TASK_RE.match(subject)
            if not match:
                continue  # Skip non-level tasks ([Plan], [Design], etc.)

            level = int(match.group(1))
            title = match.group(2)
            max_level = max(max_level, level)

            claude_status = data.get("status", "pending")
            blocked_by = data.get("blockedBy", [])
            zerg_status = self._map_status(claude_status, blocked_by)

            task_id = data.get("id", json_path.stem)
            tasks[f"TASK-{task_id}"] = {
                "status": zerg_status,
                "level": level,
                "title": title,
                "worker_id": None,
                "started_at": None,
                "completed_at": None,
            }

        # Build levels dict
        levels: dict[str, Any] = {}
        for level_num in range(1, max_level + 1):
            level_tasks = [t for t in tasks.values() if t.get("level") == level_num]
            all_complete = all(t["status"] == TaskStatus.COMPLETE.value for t in level_tasks)
            any_running = any(
                t["status"] in (TaskStatus.IN_PROGRESS.value, TaskStatus.CLAIMED.value) for t in level_tasks
            )
            levels[str(level_num)] = {
                "status": ("complete" if all_complete and level_tasks else "running" if any_running else "pending"),
                "merge_status": None,
            }

        # Determine current level
        current_level = 0
        for level_num in range(1, max_level + 1):
            level_info = levels.get(str(level_num), {})
            if level_info.get("status") != "complete":
                current_level = level_num
                break
        else:
            current_level = max_level

        return {
            "feature": "unknown",
            "started_at": datetime.now().isoformat(),
            "current_level": current_level,
            "tasks": tasks,
            "workers": {},
            "levels": levels,
            "execution_log": [],
            "metrics": None,
            "paused": False,
            "error": None,
        }

    def _scan_dir_for_zerg_tasks(self, dir_path: Path, feature_lower: str) -> tuple[int, bool]:
        """Scan a task list directory for ZERG tasks.

        Args:
            dir_path: Task list directory to scan.
            feature_lower: Lowercase feature name for matching.

        Returns:
            Tuple of (zerg_task_count, feature_matched).
        """
        zerg_count = 0
        feature_match = False

        try:
            json_files = sorted(dir_path.glob("*.json"))
        except OSError:
            return 0, False

        # Sample up to 15 files to avoid scanning huge directories
        for json_path in json_files[:15]:
            try:
                data = json.loads(json_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue

            subject = data.get("subject", "")
            description = data.get("description", "")

            if ZERG_TASK_RE.match(subject):
                zerg_count += 1

            # Check for feature name in description or meta tasks
            if feature_lower:
                text = f"{subject} {description}".lower()
                if feature_lower in text:
                    feature_match = True

        return zerg_count, feature_match

    @staticmethod
    def _map_status(claude_status: str, blocked_by: list[str]) -> str:
        """Map Claude Task status to ZERG TaskStatus value.

        Args:
            claude_status: Claude Task status string.
            blocked_by: List of blocking task IDs.

        Returns:
            ZERG TaskStatus value string.
        """
        if claude_status == "pending" and blocked_by:
            return _STATUS_BLOCKED
        return _STATUS_MAP_NO_BLOCKERS.get(claude_status, TaskStatus.PENDING.value)

    @staticmethod
    def _empty_state() -> dict[str, Any]:
        """Return an empty state dict."""
        return {
            "feature": "unknown",
            "started_at": datetime.now().isoformat(),
            "current_level": 0,
            "tasks": {},
            "workers": {},
            "levels": {},
            "execution_log": [],
            "metrics": None,
            "paused": False,
            "error": None,
        }
