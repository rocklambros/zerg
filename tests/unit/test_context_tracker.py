"""Tests for ZERG context tracker module."""

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

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
    """Tests for ContextUsage dataclass."""

    def test_creation(self) -> None:
        """Test creating usage snapshot."""
        usage = ContextUsage(
            estimated_tokens=50000,
            threshold_percent=70.0,
            files_read=5,
            tasks_executed=3,
            tool_calls=10,
        )

        assert usage.estimated_tokens == 50000
        assert usage.threshold_percent == 70.0
        assert usage.files_read == 5
        assert isinstance(usage.timestamp, datetime)

    def test_usage_percent(self) -> None:
        """Test usage percentage calculation."""
        usage = ContextUsage(
            estimated_tokens=100000,
            threshold_percent=70.0,
            files_read=0,
            tasks_executed=0,
            tool_calls=0,
        )

        # 100000 / 200000 = 50%
        assert usage.usage_percent == 50.0

    def test_is_over_threshold(self) -> None:
        """Test threshold check."""
        under_threshold = ContextUsage(
            estimated_tokens=100000,  # 50%
            threshold_percent=70.0,
            files_read=0,
            tasks_executed=0,
            tool_calls=0,
        )

        over_threshold = ContextUsage(
            estimated_tokens=150000,  # 75%
            threshold_percent=70.0,
            files_read=0,
            tasks_executed=0,
            tool_calls=0,
        )

        assert under_threshold.is_over_threshold is False
        assert over_threshold.is_over_threshold is True

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        usage = ContextUsage(
            estimated_tokens=100000,
            threshold_percent=70.0,
            files_read=5,
            tasks_executed=3,
            tool_calls=10,
        )

        data = usage.to_dict()

        assert data["estimated_tokens"] == 100000
        assert data["usage_percent"] == 50.0
        assert data["threshold_percent"] == 70.0
        assert data["files_read"] == 5
        assert data["tasks_executed"] == 3
        assert data["tool_calls"] == 10
        assert "timestamp" in data


class TestContextTracker:
    """Tests for ContextTracker class."""

    def test_init_default(self) -> None:
        """Test default initialization."""
        tracker = ContextTracker()

        assert tracker.threshold_percent == 70.0
        assert tracker.max_tokens == MAX_CONTEXT_TOKENS

    def test_init_custom(self) -> None:
        """Test custom initialization."""
        tracker = ContextTracker(threshold_percent=80.0, max_tokens=100000)

        assert tracker.threshold_percent == 80.0
        assert tracker.max_tokens == 100000

    def test_track_file_read_with_size(self) -> None:
        """Test tracking file read with explicit size."""
        tracker = ContextTracker()

        tracker.track_file_read("/path/to/file.py", size=1000)

        assert len(tracker._files_read) == 1
        assert tracker._files_read[0] == ("/path/to/file.py", 1000)

    def test_track_file_read_auto_size(self, tmp_path: Path) -> None:
        """Test tracking file read with auto-detected size."""
        test_file = tmp_path / "test.py"
        test_file.write_text("x" * 500)

        tracker = ContextTracker()
        tracker.track_file_read(test_file)

        assert len(tracker._files_read) == 1
        assert tracker._files_read[0][1] == 500

    def test_track_file_read_nonexistent(self) -> None:
        """Test tracking non-existent file."""
        tracker = ContextTracker()

        tracker.track_file_read("/nonexistent/file.py")

        assert len(tracker._files_read) == 1
        assert tracker._files_read[0][1] == 0

    def test_track_task_execution(self) -> None:
        """Test tracking task execution."""
        tracker = ContextTracker()

        tracker.track_task_execution("TASK-001")
        tracker.track_task_execution("TASK-002")

        assert len(tracker._tasks_executed) == 2
        assert "TASK-001" in tracker._tasks_executed
        assert "TASK-002" in tracker._tasks_executed

    def test_track_tool_call(self) -> None:
        """Test tracking tool calls."""
        tracker = ContextTracker()

        tracker.track_tool_call()
        tracker.track_tool_call()
        tracker.track_tool_call()

        assert tracker._tool_calls == 3


class TestEstimateTokens:
    """Tests for token estimation."""

    def test_estimate_empty(self) -> None:
        """Test estimation with no activity."""
        tracker = ContextTracker()

        # Only time-based tokens should be present (minimal)
        tokens = tracker.estimate_tokens()

        assert tokens >= 0
        assert tokens < 1000  # Should be very small for new tracker

    def test_estimate_file_tokens(self) -> None:
        """Test file token estimation."""
        tracker = ContextTracker()

        # Track a 4000 byte file (should be ~1000 tokens + overhead)
        tracker.track_file_read("/file.py", size=4000)

        tokens = tracker.estimate_tokens()

        expected_file_tokens = int(4000 * TOKENS_PER_CHAR) + TOKENS_PER_FILE_READ
        assert tokens >= expected_file_tokens

    def test_estimate_task_tokens(self) -> None:
        """Test task token estimation."""
        tracker = ContextTracker()

        tracker.track_task_execution("TASK-001")
        tracker.track_task_execution("TASK-002")

        tokens = tracker.estimate_tokens()

        expected_task_tokens = 2 * TOKENS_PER_TASK
        assert tokens >= expected_task_tokens

    def test_estimate_tool_call_tokens(self) -> None:
        """Test tool call token estimation."""
        tracker = ContextTracker()

        for _ in range(10):
            tracker.track_tool_call()

        tokens = tracker.estimate_tokens()

        expected_tool_tokens = 10 * TOKENS_PER_TOOL_CALL
        assert tokens >= expected_tool_tokens

    def test_estimate_combined(self) -> None:
        """Test combined token estimation."""
        tracker = ContextTracker()

        tracker.track_file_read("/file.py", size=4000)
        tracker.track_task_execution("TASK-001")
        tracker.track_tool_call()

        tokens = tracker.estimate_tokens()

        # Should be sum of all components plus time-based
        min_expected = (
            int(4000 * TOKENS_PER_CHAR) + TOKENS_PER_FILE_READ +
            TOKENS_PER_TASK +
            TOKENS_PER_TOOL_CALL
        )
        assert tokens >= min_expected


class TestGetUsage:
    """Tests for getting usage snapshot."""

    def test_get_usage(self) -> None:
        """Test getting usage snapshot."""
        tracker = ContextTracker(threshold_percent=75.0)

        tracker.track_file_read("/file.py", size=1000)
        tracker.track_task_execution("TASK-001")
        tracker.track_tool_call()

        usage = tracker.get_usage()

        assert usage.files_read == 1
        assert usage.tasks_executed == 1
        assert usage.tool_calls == 1
        assert usage.threshold_percent == 75.0
        assert usage.estimated_tokens > 0


class TestShouldCheckpoint:
    """Tests for checkpoint decision."""

    def test_should_not_checkpoint_low_usage(self) -> None:
        """Test no checkpoint for low usage."""
        tracker = ContextTracker(threshold_percent=70.0)

        # Minimal activity
        tracker.track_tool_call()

        assert tracker.should_checkpoint() is False

    def test_should_checkpoint_high_usage(self) -> None:
        """Test checkpoint for high usage."""
        tracker = ContextTracker(threshold_percent=70.0)

        # Simulate high usage by tracking many large files
        for i in range(100):
            tracker.track_file_read(f"/file{i}.py", size=100000)

        # This should exceed 70% of 200K tokens
        assert tracker.should_checkpoint() is True


class TestReset:
    """Tests for resetting tracker."""

    def test_reset(self) -> None:
        """Test resetting tracker state."""
        tracker = ContextTracker()

        tracker.track_file_read("/file.py", size=1000)
        tracker.track_task_execution("TASK-001")
        tracker.track_tool_call()

        tracker.reset()

        assert len(tracker._files_read) == 0
        assert len(tracker._tasks_executed) == 0
        assert tracker._tool_calls == 0


class TestGetSummary:
    """Tests for getting summary."""

    def test_get_summary(self) -> None:
        """Test getting tracking summary."""
        tracker = ContextTracker(threshold_percent=75.0, max_tokens=200000)

        tracker.track_file_read("/file.py", size=1000)

        summary = tracker.get_summary()

        assert "usage" in summary
        assert summary["threshold_percent"] == 75.0
        assert summary["max_tokens"] == 200000
        assert "should_checkpoint" in summary
        assert "session_duration_minutes" in summary


class TestEstimateFileTokens:
    """Tests for estimate_file_tokens function."""

    def test_estimate_existing_file(self, tmp_path: Path) -> None:
        """Test estimating tokens for existing file."""
        test_file = tmp_path / "test.py"
        test_file.write_text("x" * 1000)

        tokens = estimate_file_tokens(test_file)

        expected = int(1000 * TOKENS_PER_CHAR) + TOKENS_PER_FILE_READ
        assert tokens == expected

    def test_estimate_nonexistent_file(self) -> None:
        """Test estimating tokens for non-existent file."""
        tokens = estimate_file_tokens("/nonexistent/file.py")

        assert tokens == TOKENS_PER_FILE_READ


class TestEstimateTaskTokens:
    """Tests for estimate_task_tokens function."""

    def test_estimate_basic_task(self) -> None:
        """Test estimating tokens for basic task."""
        task = {
            "id": "TASK-001",
            "description": "Test task",
        }

        tokens = estimate_task_tokens(task)

        assert tokens >= TOKENS_PER_TASK

    def test_estimate_task_with_files(self) -> None:
        """Test estimating tokens for task with files."""
        task = {
            "id": "TASK-001",
            "description": "x" * 100,
            "files": {
                "create": ["a.py", "b.py"],
                "modify": ["c.py"],
                "read": ["d.py", "e.py", "f.py"],
            },
        }

        tokens = estimate_task_tokens(task)

        # Base + description + file overhead
        expected_min = TOKENS_PER_TASK + int(100 * TOKENS_PER_CHAR) + 6 * TOKENS_PER_FILE_READ
        assert tokens >= expected_min

    def test_estimate_task_with_long_description(self) -> None:
        """Test estimating tokens for task with long description."""
        long_desc = "x" * 2000  # 2000 chars = ~500 tokens

        task = {
            "id": "TASK-001",
            "description": long_desc,
        }

        tokens = estimate_task_tokens(task)

        expected_desc_tokens = int(2000 * TOKENS_PER_CHAR)
        assert tokens >= TOKENS_PER_TASK + expected_desc_tokens


class TestConstants:
    """Tests for module constants."""

    def test_tokens_per_char(self) -> None:
        """Test tokens per char is reasonable."""
        # Typically 3-4 chars per token
        assert 0.2 <= TOKENS_PER_CHAR <= 0.5

    def test_max_context_tokens(self) -> None:
        """Test max context is Claude's window size."""
        assert MAX_CONTEXT_TOKENS == 200_000

    def test_tokens_per_task(self) -> None:
        """Test task token estimate is reasonable."""
        assert 100 <= TOKENS_PER_TASK <= 1000

    def test_tokens_per_tool_call(self) -> None:
        """Test tool call token estimate is reasonable."""
        assert 10 <= TOKENS_PER_TOOL_CALL <= 200


class TestBudgetForTask:
    """Tests for budget_for_task method."""

    def test_budget_for_task(self) -> None:
        """Test budget allocation based on file count."""
        tracker = ContextTracker()

        # 10000 budget, 5 files -> 10000 // 5 = 2000 per task
        budget = tracker.budget_for_task(10000, ["a.py", "b.py", "c.py", "d.py", "e.py"])

        assert budget == 2000

    def test_budget_for_task_single_file(self) -> None:
        """Test budget allocation with single file gets full budget."""
        tracker = ContextTracker()

        budget = tracker.budget_for_task(4000, ["only.py"])

        assert budget == 4000

    def test_budget_for_task_empty_files(self) -> None:
        """Test budget allocation with empty file list uses minimum 1."""
        tracker = ContextTracker()

        budget = tracker.budget_for_task(4000, [])

        # max(len([]), 1) = 1, so 4000 // 1 = 4000
        assert budget == 4000

    def test_budget_for_task_clamps_to_minimum(self) -> None:
        """Test budget is clamped to minimum of 500."""
        tracker = ContextTracker()

        # 1000 budget, 10 files -> 1000 // 10 = 100 -> clamped to 500
        budget = tracker.budget_for_task(1000, [f"f{i}.py" for i in range(10)])

        assert budget == 500


class TestContextBudgetSummary:
    """Tests for context_budget_summary method."""

    def test_context_budget_summary(self) -> None:
        """Test that budget summary returns correct structure and values."""
        tracker = ContextTracker()

        tasks = [
            {
                "id": "T-1",
                "files": {"create": ["a.py", "b.py"], "modify": ["c.py"]},
            },
            {
                "id": "T-2",
                "files": {"create": ["d.py"]},
            },
        ]

        summary = tracker.context_budget_summary(tasks, total_budget=10000)

        assert summary["total_budget"] == 10000
        assert "allocated" in summary
        assert "per_task" in summary
        assert "avg_per_task" in summary
        assert "T-1" in summary["per_task"]
        assert "T-2" in summary["per_task"]

        # T-1 has 3 files: 10000 // 3 = 3333
        assert summary["per_task"]["T-1"] == 3333
        # T-2 has 1 file: 10000 // 1 = 10000
        assert summary["per_task"]["T-2"] == 10000
