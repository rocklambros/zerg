"""Tests for ZERG context tracker module."""

from datetime import datetime
from pathlib import Path

import pytest

from zerg.context_tracker import (
    MAX_CONTEXT_TOKENS,
    TOKENS_PER_CHAR,
    TOKENS_PER_FILE_READ,
    TOKENS_PER_TASK,
    TOKENS_PER_TOOL_CALL,
    ContextTracker,
    ContextUsage,
    estimate_file_tokens,
    estimate_task_tokens,
)


class TestContextUsage:
    def test_creation_and_to_dict(self) -> None:
        usage = ContextUsage(
            estimated_tokens=50000,
            threshold_percent=70.0,
            files_read=5,
            tasks_executed=3,
            tool_calls=10,
        )
        assert usage.estimated_tokens == 50000
        assert isinstance(usage.timestamp, datetime)
        data = usage.to_dict()
        assert data["usage_percent"] == 25.0
        assert data["files_read"] == 5
        assert "timestamp" in data

    def test_threshold_check(self) -> None:
        under = ContextUsage(
            estimated_tokens=100000, threshold_percent=70.0, files_read=0, tasks_executed=0, tool_calls=0
        )
        over = ContextUsage(
            estimated_tokens=150000, threshold_percent=70.0, files_read=0, tasks_executed=0, tool_calls=0
        )
        assert under.is_over_threshold is False
        assert over.is_over_threshold is True


class TestContextTracker:
    def test_init(self) -> None:
        default = ContextTracker()
        assert default.threshold_percent == 70.0
        assert default.max_tokens == MAX_CONTEXT_TOKENS
        custom = ContextTracker(threshold_percent=80.0, max_tokens=100000)
        assert custom.threshold_percent == 80.0

    def test_track_file_read(self, tmp_path: Path) -> None:
        tracker = ContextTracker()
        tracker.track_file_read("/path/to/file.py", size=1000)
        assert tracker._files_read[0] == ("/path/to/file.py", 1000)
        test_file = tmp_path / "test.py"
        test_file.write_text("x" * 500)
        tracker.track_file_read(test_file)
        assert tracker._files_read[1][1] == 500
        tracker.track_file_read("/nonexistent/file.py")
        assert tracker._files_read[2][1] == 0

    def test_track_task_and_tool(self) -> None:
        tracker = ContextTracker()
        tracker.track_task_execution("TASK-001")
        tracker.track_task_execution("TASK-002")
        assert len(tracker._tasks_executed) == 2
        tracker.track_tool_call()
        tracker.track_tool_call()
        assert tracker._tool_calls == 2

    def test_estimate_combined(self) -> None:
        tracker = ContextTracker()
        tracker.track_file_read("/file.py", size=4000)
        tracker.track_task_execution("TASK-001")
        tracker.track_tool_call()
        tokens = tracker.estimate_tokens()
        min_expected = int(4000 * TOKENS_PER_CHAR) + TOKENS_PER_FILE_READ + TOKENS_PER_TASK + TOKENS_PER_TOOL_CALL
        assert tokens >= min_expected

    def test_get_usage(self) -> None:
        tracker = ContextTracker(threshold_percent=75.0)
        tracker.track_file_read("/file.py", size=1000)
        tracker.track_task_execution("TASK-001")
        tracker.track_tool_call()
        usage = tracker.get_usage()
        assert usage.files_read == 1
        assert usage.tasks_executed == 1
        assert usage.estimated_tokens > 0

    def test_should_checkpoint_high_usage(self) -> None:
        tracker = ContextTracker(threshold_percent=70.0)
        for i in range(100):
            tracker.track_file_read(f"/file{i}.py", size=100000)
        assert tracker.should_checkpoint() is True

    def test_reset(self) -> None:
        tracker = ContextTracker()
        tracker.track_file_read("/file.py", size=1000)
        tracker.track_task_execution("TASK-001")
        tracker.track_tool_call()
        tracker.reset()
        assert len(tracker._files_read) == 0
        assert tracker._tool_calls == 0

    def test_get_summary(self) -> None:
        tracker = ContextTracker(threshold_percent=75.0, max_tokens=200000)
        tracker.track_file_read("/file.py", size=1000)
        summary = tracker.get_summary()
        assert summary["threshold_percent"] == 75.0
        assert "should_checkpoint" in summary


class TestEstimateFunctions:
    def test_estimate_file_tokens(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test.py"
        test_file.write_text("x" * 1000)
        tokens = estimate_file_tokens(test_file)
        expected = int(1000 * TOKENS_PER_CHAR) + TOKENS_PER_FILE_READ
        assert tokens == expected
        assert estimate_file_tokens("/nonexistent/file.py") == TOKENS_PER_FILE_READ

    def test_estimate_task_tokens(self) -> None:
        task = {
            "id": "TASK-001",
            "description": "x" * 100,
            "files": {"create": ["a.py", "b.py"], "modify": ["c.py"], "read": ["d.py", "e.py", "f.py"]},
        }
        tokens = estimate_task_tokens(task)
        expected_min = TOKENS_PER_TASK + int(100 * TOKENS_PER_CHAR) + 6 * TOKENS_PER_FILE_READ
        assert tokens >= expected_min


class TestBudgetForTask:
    @pytest.mark.parametrize(
        "budget,files,expected",
        [
            (10000, ["a.py", "b.py", "c.py", "d.py", "e.py"], 2000),
            (4000, ["only.py"], 4000),
            (4000, [], 4000),
            (1000, [f"f{i}.py" for i in range(10)], 500),
        ],
        ids=["divide_evenly", "single_file", "empty_files", "clamp_minimum"],
    )
    def test_budget_allocation(self, budget: int, files: list[str], expected: int) -> None:
        tracker = ContextTracker()
        assert tracker.budget_for_task(budget, files) == expected

    def test_context_budget_summary(self) -> None:
        tracker = ContextTracker()
        tasks = [
            {"id": "T-1", "files": {"create": ["a.py", "b.py"], "modify": ["c.py"]}},
            {"id": "T-2", "files": {"create": ["d.py"]}},
        ]
        summary = tracker.context_budget_summary(tasks, total_budget=10000)
        assert summary["total_budget"] == 10000
        assert summary["per_task"]["T-1"] == 3333
        assert summary["per_task"]["T-2"] == 10000
