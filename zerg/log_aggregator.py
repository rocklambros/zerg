"""Read-side log aggregation for ZERG structured logs.

Merges all worker JSONL files by timestamp at read time.
No aggregated file on disk - purely read-side merging.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class LogQuery:
    """Query parameters for filtering log entries."""

    worker_id: int | str | None = None
    task_id: str | None = None
    level: str | None = None
    phase: str | None = None
    event: str | None = None
    level_filter: int | None = None
    since: str | datetime | None = None
    until: str | datetime | None = None
    search: str | None = None
    limit: int | None = None


class LogAggregator:
    """Aggregates structured JSONL logs from all workers.

    Reads workers/*.jsonl and orchestrator.jsonl, merges by timestamp.
    Supports filtering by worker, task, phase, event, time range, and text search.
    """

    def __init__(self, log_dir: str | Path) -> None:
        """Initialize aggregator.

        Args:
            log_dir: Base log directory (.zerg/logs)
        """
        self.log_dir = Path(log_dir)
        self.workers_dir = self.log_dir / "workers"
        self.tasks_dir = self.log_dir / "tasks"

    def query(
        self,
        worker_id: int | str | None = None,
        task_id: str | None = None,
        level: str | None = None,
        phase: str | None = None,
        event: str | None = None,
        level_filter: int | None = None,
        since: str | datetime | None = None,
        until: str | datetime | None = None,
        search: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Query log entries with optional filters.

        All filters are AND-combined. Returns entries sorted by timestamp.

        Args:
            worker_id: Filter by worker ID
            task_id: Filter by task ID
            level: Filter by log level (exact match)
            phase: Filter by execution phase
            event: Filter by event type
            level_filter: Filter by ZERG level number (task execution level)
            since: Only entries after this timestamp (ISO8601 string or datetime)
            until: Only entries before this timestamp (ISO8601 string or datetime)
            search: Text search in message field (case-insensitive)
            limit: Maximum entries to return

        Returns:
            List of log entry dicts sorted by timestamp
        """
        entries = self._read_all_entries()

        # Apply filters
        filtered = []
        for entry in entries:
            if worker_id is not None and entry.get("worker_id") != worker_id:
                continue
            if task_id is not None and entry.get("task_id") != task_id:
                continue
            if level is not None and entry.get("level") != level:
                continue
            if phase is not None and entry.get("phase") != phase:
                continue
            if event is not None and entry.get("event") != event:
                continue
            if level_filter is not None:
                entry_data = entry.get("data", {})
                if isinstance(entry_data, dict):
                    if entry_data.get("level") != level_filter:
                        continue
                else:
                    continue
            if since is not None:
                since_str = since.isoformat() if isinstance(since, datetime) else since
                if entry.get("ts", "") < since_str:
                    continue
            if until is not None:
                until_str = until.isoformat() if isinstance(until, datetime) else until
                if entry.get("ts", "") > until_str:
                    continue
            if search is not None:
                msg = entry.get("message", "")
                if search.lower() not in msg.lower():
                    continue

            filtered.append(entry)

        # Sort by timestamp
        filtered.sort(key=lambda e: e.get("ts", ""))

        # Apply limit
        if limit is not None:
            filtered = filtered[:limit]

        return filtered

    def _read_all_entries(self) -> list[dict[str, Any]]:
        """Read all log entries from all worker files and orchestrator.

        Returns:
            Unsorted list of all log entries
        """
        entries: list[dict[str, Any]] = []

        # Read worker files
        if self.workers_dir.exists():
            for jsonl_file in self.workers_dir.glob("*.jsonl"):
                entries.extend(self._read_jsonl(jsonl_file))

        # Read orchestrator file
        orchestrator_file = self.log_dir / "orchestrator.jsonl"
        if orchestrator_file.exists():
            entries.extend(self._read_jsonl(orchestrator_file))

        return entries

    def _read_jsonl(self, path: Path) -> list[dict[str, Any]]:
        """Read entries from a JSONL file.

        Args:
            path: Path to JSONL file

        Returns:
            List of parsed entries
        """
        entries = []
        try:
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except OSError:
            pass
        return entries

    def get_task_artifacts(self, task_id: str) -> dict[str, Path]:
        """Get artifact file paths for a task.

        Args:
            task_id: Task identifier

        Returns:
            Dict of artifact name to Path (only existing files)
        """
        task_dir = self.tasks_dir / task_id
        if not task_dir.exists():
            return {}

        artifacts = {}
        for name in [
            "execution.jsonl",
            "claude_output.txt",
            "verification_output.txt",
            "git_diff.patch",
        ]:
            path = task_dir / name
            if path.exists():
                artifacts[name] = path
        return artifacts

    def list_tasks(self) -> list[str]:
        """List all task IDs found in logs.

        Returns:
            Sorted list of unique task IDs
        """
        task_ids: set[str] = set()

        # From log entries
        entries = self._read_all_entries()
        for entry in entries:
            tid = entry.get("task_id")
            if tid:
                task_ids.add(tid)

        # From task artifact directories
        if self.tasks_dir.exists():
            for task_dir in self.tasks_dir.iterdir():
                if task_dir.is_dir():
                    task_ids.add(task_dir.name)

        return sorted(task_ids)
