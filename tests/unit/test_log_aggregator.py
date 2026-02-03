"""Unit tests for LogAggregator and LogQuery."""

import json
from pathlib import Path

from zerg.log_aggregator import LogAggregator


def _write_jsonl(path: Path, entries: list[dict]) -> None:
    """Helper to write JSONL entries to a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")


class TestLogAggregatorQuery:
    """Tests for LogAggregator.query()."""

    def test_query_no_filters_returns_all_sorted(self, tmp_path: Path) -> None:
        """Test query with no filters returns all entries sorted by ts."""
        _write_jsonl(
            tmp_path / "workers" / "worker-0.jsonl",
            [
                {"ts": "2026-01-01T10:00:02Z", "level": "info", "message": "C", "worker_id": 0},
                {"ts": "2026-01-01T10:00:00Z", "level": "info", "message": "A", "worker_id": 0},
            ],
        )
        _write_jsonl(
            tmp_path / "workers" / "worker-1.jsonl",
            [
                {"ts": "2026-01-01T10:00:01Z", "level": "info", "message": "B", "worker_id": 1},
            ],
        )

        agg = LogAggregator(tmp_path)
        results = agg.query()

        assert len(results) == 3
        assert results[0]["message"] == "A"
        assert results[1]["message"] == "B"
        assert results[2]["message"] == "C"

    def test_filter_by_worker_id(self, tmp_path: Path) -> None:
        """Test filtering by worker_id."""
        _write_jsonl(
            tmp_path / "workers" / "worker-0.jsonl",
            [{"ts": "2026-01-01T10:00:00Z", "level": "info", "message": "W0", "worker_id": 0}],
        )
        _write_jsonl(
            tmp_path / "workers" / "worker-1.jsonl",
            [{"ts": "2026-01-01T10:00:01Z", "level": "info", "message": "W1", "worker_id": 1}],
        )

        agg = LogAggregator(tmp_path)
        results = agg.query(worker_id=0)
        assert len(results) == 1
        assert results[0]["message"] == "W0"

    def test_filter_by_task_id(self, tmp_path: Path) -> None:
        """Test filtering by task_id."""
        _write_jsonl(
            tmp_path / "workers" / "worker-0.jsonl",
            [
                {"ts": "2026-01-01T10:00:00Z", "level": "info", "message": "T1", "task_id": "T1.1"},
                {"ts": "2026-01-01T10:00:01Z", "level": "info", "message": "T2", "task_id": "T1.2"},
            ],
        )

        agg = LogAggregator(tmp_path)
        results = agg.query(task_id="T1.1")
        assert len(results) == 1
        assert results[0]["message"] == "T1"

    def test_filter_by_phase(self, tmp_path: Path) -> None:
        """Test filtering by phase."""
        _write_jsonl(
            tmp_path / "workers" / "worker-0.jsonl",
            [
                {"ts": "2026-01-01T10:00:00Z", "level": "info", "message": "exec", "phase": "execute"},
                {"ts": "2026-01-01T10:00:01Z", "level": "info", "message": "ver", "phase": "verify"},
            ],
        )

        agg = LogAggregator(tmp_path)
        results = agg.query(phase="verify")
        assert len(results) == 1
        assert results[0]["message"] == "ver"

    def test_filter_by_event(self, tmp_path: Path) -> None:
        """Test filtering by event type."""
        _write_jsonl(
            tmp_path / "workers" / "worker-0.jsonl",
            [
                {"ts": "2026-01-01T10:00:00Z", "level": "info", "message": "started", "event": "task_started"},
                {"ts": "2026-01-01T10:00:01Z", "level": "info", "message": "done", "event": "task_completed"},
            ],
        )

        agg = LogAggregator(tmp_path)
        results = agg.query(event="task_completed")
        assert len(results) == 1
        assert results[0]["message"] == "done"

    def test_filter_by_level(self, tmp_path: Path) -> None:
        """Test filtering by log level."""
        _write_jsonl(
            tmp_path / "workers" / "worker-0.jsonl",
            [
                {"ts": "2026-01-01T10:00:00Z", "level": "info", "message": "info msg"},
                {"ts": "2026-01-01T10:00:01Z", "level": "error", "message": "error msg"},
            ],
        )

        agg = LogAggregator(tmp_path)
        results = agg.query(level="error")
        assert len(results) == 1
        assert results[0]["message"] == "error msg"

    def test_filter_by_time_range(self, tmp_path: Path) -> None:
        """Test filtering by since/until."""
        _write_jsonl(
            tmp_path / "workers" / "worker-0.jsonl",
            [
                {"ts": "2026-01-01T09:00:00Z", "level": "info", "message": "early"},
                {"ts": "2026-01-01T10:00:00Z", "level": "info", "message": "middle"},
                {"ts": "2026-01-01T11:00:00Z", "level": "info", "message": "late"},
            ],
        )

        agg = LogAggregator(tmp_path)
        results = agg.query(since="2026-01-01T09:30:00Z", until="2026-01-01T10:30:00Z")
        assert len(results) == 1
        assert results[0]["message"] == "middle"

    def test_text_search(self, tmp_path: Path) -> None:
        """Test case-insensitive text search in message."""
        _write_jsonl(
            tmp_path / "workers" / "worker-0.jsonl",
            [
                {"ts": "2026-01-01T10:00:00Z", "level": "info", "message": "Task STARTED"},
                {"ts": "2026-01-01T10:00:01Z", "level": "info", "message": "Task completed"},
            ],
        )

        agg = LogAggregator(tmp_path)
        results = agg.query(search="started")
        assert len(results) == 1
        assert "STARTED" in results[0]["message"]

    def test_limit(self, tmp_path: Path) -> None:
        """Test limit parameter."""
        entries = [{"ts": f"2026-01-01T10:00:{i:02d}Z", "level": "info", "message": f"entry {i}"} for i in range(10)]
        _write_jsonl(tmp_path / "workers" / "worker-0.jsonl", entries)

        agg = LogAggregator(tmp_path)
        results = agg.query(limit=3)
        assert len(results) == 3
        assert results[0]["message"] == "entry 0"

    def test_query_includes_orchestrator(self, tmp_path: Path) -> None:
        """Test query includes orchestrator.jsonl entries."""
        _write_jsonl(
            tmp_path / "workers" / "worker-0.jsonl",
            [{"ts": "2026-01-01T10:00:00Z", "level": "info", "message": "worker"}],
        )
        _write_jsonl(
            tmp_path / "orchestrator.jsonl",
            [{"ts": "2026-01-01T10:00:01Z", "level": "info", "message": "orchestrator"}],
        )

        agg = LogAggregator(tmp_path)
        results = agg.query()
        assert len(results) == 2
        messages = [r["message"] for r in results]
        assert "worker" in messages
        assert "orchestrator" in messages

    def test_query_empty_log_dir(self, tmp_path: Path) -> None:
        """Test query with no log files returns empty list."""
        agg = LogAggregator(tmp_path)
        results = agg.query()
        assert results == []

    def test_query_malformed_json_lines_skipped(self, tmp_path: Path) -> None:
        """Test malformed JSON lines are silently skipped."""
        workers_dir = tmp_path / "workers"
        workers_dir.mkdir(parents=True)
        (workers_dir / "worker-0.jsonl").write_text(
            '{"ts": "2026-01-01T10:00:00Z", "level": "info", "message": "valid"}\n'
            "this is not json\n"
            '{"ts": "2026-01-01T10:00:01Z", "level": "info", "message": "also valid"}\n'
        )

        agg = LogAggregator(tmp_path)
        results = agg.query()
        assert len(results) == 2


class TestGetTaskArtifacts:
    """Tests for LogAggregator.get_task_artifacts()."""

    def test_returns_existing_artifacts(self, tmp_path: Path) -> None:
        """Test returns paths for existing artifact files."""
        task_dir = tmp_path / "tasks" / "T1.1"
        task_dir.mkdir(parents=True)
        (task_dir / "claude_output.txt").write_text("output")
        (task_dir / "git_diff.patch").write_text("diff")

        agg = LogAggregator(tmp_path)
        artifacts = agg.get_task_artifacts("T1.1")

        assert "claude_output.txt" in artifacts
        assert "git_diff.patch" in artifacts
        assert "verification_output.txt" not in artifacts

    def test_returns_empty_for_nonexistent_task(self, tmp_path: Path) -> None:
        """Test returns empty dict for nonexistent task."""
        agg = LogAggregator(tmp_path)
        artifacts = agg.get_task_artifacts("NONEXISTENT")
        assert artifacts == {}


class TestListTasks:
    """Tests for LogAggregator.list_tasks()."""

    def test_lists_tasks_from_logs_and_dirs(self, tmp_path: Path) -> None:
        """Test lists task IDs from log entries and artifact directories."""
        _write_jsonl(
            tmp_path / "workers" / "worker-0.jsonl",
            [
                {"ts": "2026-01-01T10:00:00Z", "level": "info", "message": "t1", "task_id": "T1.1"},
                {"ts": "2026-01-01T10:00:01Z", "level": "info", "message": "t2", "task_id": "T1.2"},
            ],
        )
        # Also create a task dir for T1.3 (not in logs)
        (tmp_path / "tasks" / "T1.3").mkdir(parents=True)

        agg = LogAggregator(tmp_path)
        tasks = agg.list_tasks()

        assert tasks == ["T1.1", "T1.2", "T1.3"]

    def test_lists_empty_when_no_data(self, tmp_path: Path) -> None:
        """Test returns empty list when no data."""
        agg = LogAggregator(tmp_path)
        assert agg.list_tasks() == []
