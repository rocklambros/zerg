"""Unit tests for zerg.token_tracker module."""

from __future__ import annotations

import json

from zerg.token_tracker import TokenTracker


class TestRecordTask:
    """Tests for TokenTracker.record_task."""

    def test_record_and_read_back(self, tmp_path) -> None:
        """Write a task, read it back, verify schema."""
        tracker = TokenTracker(state_dir=tmp_path)
        breakdown = {"command_template": 100, "task_context": 200}
        tracker.record_task("w0", "TASK-001", breakdown)

        data = tracker.read("w0")
        assert data is not None
        assert data["worker_id"] == "w0"
        assert "TASK-001" in data["tasks"]
        task = data["tasks"]["TASK-001"]
        assert task["breakdown"] == breakdown
        assert task["total"] == 300
        assert task["mode"] == "estimated"
        assert "timestamp" in task

    def test_multiple_tasks_same_worker(self, tmp_path) -> None:
        """Record 2 tasks for same worker; both present."""
        tracker = TokenTracker(state_dir=tmp_path)
        tracker.record_task("w0", "TASK-001", {"a": 10})
        tracker.record_task("w0", "TASK-002", {"b": 20})

        data = tracker.read("w0")
        assert "TASK-001" in data["tasks"]
        assert "TASK-002" in data["tasks"]

    def test_cumulative_totals(self, tmp_path) -> None:
        """Cumulative total_tokens and tasks_completed update correctly."""
        tracker = TokenTracker(state_dir=tmp_path)
        tracker.record_task("w0", "TASK-001", {"x": 50})
        tracker.record_task("w0", "TASK-002", {"y": 70})

        data = tracker.read("w0")
        assert data["cumulative"]["total_tokens"] == 120
        assert data["cumulative"]["tasks_completed"] == 2

    def test_custom_mode(self, tmp_path) -> None:
        """Record with mode='exact' stores correctly."""
        tracker = TokenTracker(state_dir=tmp_path)
        tracker.record_task("w0", "TASK-001", {"a": 5}, mode="exact")

        data = tracker.read("w0")
        assert data["tasks"]["TASK-001"]["mode"] == "exact"


class TestRead:
    """Tests for TokenTracker.read and read_all."""

    def test_read_nonexistent_worker(self, tmp_path) -> None:
        """Reading a worker that does not exist returns None."""
        tracker = TokenTracker(state_dir=tmp_path)
        assert tracker.read("ghost") is None

    def test_read_all_multiple_workers(self, tmp_path) -> None:
        """Create files for 2 workers; read_all returns both."""
        tracker = TokenTracker(state_dir=tmp_path)
        tracker.record_task("w0", "T1", {"a": 10})
        tracker.record_task("w1", "T2", {"b": 20})

        all_data = tracker.read_all()
        assert "w0" in all_data
        assert "w1" in all_data

    def test_read_all_empty_dir(self, tmp_path) -> None:
        """read_all on a directory with no token files returns empty dict."""
        tracker = TokenTracker(state_dir=tmp_path)
        assert tracker.read_all() == {}


class TestAtomicWrite:
    """Tests for atomic file writing."""

    def test_file_is_valid_json(self, tmp_path) -> None:
        """After write, the file on disk is valid JSON."""
        tracker = TokenTracker(state_dir=tmp_path)
        tracker.record_task("w0", "TASK-001", {"a": 10})

        path = tmp_path / "tokens-w0.json"
        data = json.loads(path.read_text())
        assert data["worker_id"] == "w0"


class TestCorruptionHandling:
    """Tests for graceful handling of corrupt data."""

    def test_corrupt_json_returns_none(self, tmp_path) -> None:
        """If the file contains invalid JSON, read returns None."""
        tracker = TokenTracker(state_dir=tmp_path)
        corrupt_path = tmp_path / "tokens-bad.json"
        corrupt_path.write_text("{not valid json!!!")

        result = tracker.read("bad")
        assert result is None

    def test_record_overwrites_corrupt_file(self, tmp_path) -> None:
        """Recording a task when existing file is corrupt creates fresh data."""
        tracker = TokenTracker(state_dir=tmp_path)
        corrupt_path = tmp_path / "tokens-w0.json"
        corrupt_path.write_text("BROKEN")

        # read returns None for corrupt file, so record_task starts fresh
        tracker.record_task("w0", "T1", {"a": 5})
        data = tracker.read("w0")
        assert data is not None
        assert data["cumulative"]["total_tokens"] == 5
