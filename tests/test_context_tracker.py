"""Tests for ZERG context tracker."""

from pathlib import Path

from zerg.context_tracker import (
    MAX_CONTEXT_TOKENS,
    TOKENS_PER_CHAR,
    TOKENS_PER_FILE_READ,
    TOKENS_PER_TASK,
    ContextTracker,
    ContextUsage,
    estimate_file_tokens,
    estimate_task_tokens,
)


class TestContextUsage:
    """Tests for ContextUsage dataclass."""

    def test_usage_percent_calculation(self) -> None:
        """Test percentage calculation from tokens."""
        usage = ContextUsage(
            estimated_tokens=100_000,
            threshold_percent=70.0,
            files_read=5,
            tasks_executed=3,
            tool_calls=10,
        )

        assert usage.usage_percent == 50.0  # 100k / 200k = 50%

    def test_is_over_threshold_true(self) -> None:
        """Test threshold detection when over."""
        usage = ContextUsage(
            estimated_tokens=150_000,  # 75%
            threshold_percent=70.0,
            files_read=0,
            tasks_executed=0,
            tool_calls=0,
        )

        assert usage.is_over_threshold is True

    def test_is_over_threshold_false(self) -> None:
        """Test threshold detection when under."""
        usage = ContextUsage(
            estimated_tokens=100_000,  # 50%
            threshold_percent=70.0,
            files_read=0,
            tasks_executed=0,
            tool_calls=0,
        )

        assert usage.is_over_threshold is False

    def test_to_dict(self) -> None:
        """Test dictionary conversion."""
        usage = ContextUsage(
            estimated_tokens=50_000,
            threshold_percent=70.0,
            files_read=3,
            tasks_executed=2,
            tool_calls=5,
        )

        result = usage.to_dict()

        assert result["estimated_tokens"] == 50_000
        assert result["usage_percent"] == 25.0
        assert result["threshold_percent"] == 70.0
        assert result["is_over_threshold"] is False
        assert result["files_read"] == 3
        assert result["tasks_executed"] == 2
        assert result["tool_calls"] == 5
        assert "timestamp" in result


class TestContextTracker:
    """Tests for ContextTracker class."""

    def test_init_defaults(self) -> None:
        """Test default initialization."""
        tracker = ContextTracker()

        assert tracker.threshold_percent == 70.0
        assert tracker.max_tokens == MAX_CONTEXT_TOKENS

    def test_init_custom_threshold(self) -> None:
        """Test custom threshold initialization."""
        tracker = ContextTracker(threshold_percent=80.0)

        assert tracker.threshold_percent == 80.0

    def test_track_file_read(self, tmp_path: Path) -> None:
        """Test tracking file reads."""
        tracker = ContextTracker()

        # Create a test file
        test_file = tmp_path / "test.py"
        test_file.write_text("print('hello')")

        tracker.track_file_read(test_file)

        usage = tracker.get_usage()
        assert usage.files_read == 1

    def test_track_file_read_with_size(self) -> None:
        """Test tracking file reads with explicit size."""
        tracker = ContextTracker()

        tracker.track_file_read("/fake/path.py", size=1000)

        # Should include token estimate based on size
        tokens = tracker.estimate_tokens()
        expected_file_tokens = int(1000 * TOKENS_PER_CHAR) + TOKENS_PER_FILE_READ
        assert tokens >= expected_file_tokens

    def test_track_task_execution(self) -> None:
        """Test tracking task execution."""
        tracker = ContextTracker()

        tracker.track_task_execution("TASK-001")
        tracker.track_task_execution("TASK-002")

        usage = tracker.get_usage()
        assert usage.tasks_executed == 2

    def test_track_tool_call(self) -> None:
        """Test tracking tool calls."""
        tracker = ContextTracker()

        tracker.track_tool_call()
        tracker.track_tool_call()
        tracker.track_tool_call()

        usage = tracker.get_usage()
        assert usage.tool_calls == 3

    def test_estimate_tokens_empty(self) -> None:
        """Test token estimation with no activity."""
        tracker = ContextTracker()

        # Should have minimal tokens (just time-based)
        tokens = tracker.estimate_tokens()
        assert tokens >= 0

    def test_estimate_tokens_with_activity(self) -> None:
        """Test token estimation with tracked activity."""
        tracker = ContextTracker()

        # Track some activity
        tracker.track_file_read("/fake/path.py", size=1000)
        tracker.track_task_execution("TASK-001")
        tracker.track_tool_call()

        tokens = tracker.estimate_tokens()

        # Should include file, task, and tool tokens
        min_expected = (
            int(1000 * TOKENS_PER_CHAR) + TOKENS_PER_FILE_READ + TOKENS_PER_TASK + 50  # tool call tokens
        )
        assert tokens >= min_expected

    def test_should_checkpoint_false_initially(self) -> None:
        """Test checkpoint is not needed initially."""
        tracker = ContextTracker(threshold_percent=70.0)

        assert tracker.should_checkpoint() is False

    def test_should_checkpoint_true_when_over(self) -> None:
        """Test checkpoint is needed when over threshold."""
        tracker = ContextTracker(threshold_percent=70.0)

        # Add lots of activity to exceed threshold
        for i in range(300):
            tracker.track_task_execution(f"TASK-{i:03d}")
            tracker.track_file_read(f"/fake/file{i}.py", size=5000)

        assert tracker.should_checkpoint() is True

    def test_reset(self) -> None:
        """Test resetting tracker state."""
        tracker = ContextTracker()

        # Add activity
        tracker.track_file_read("/fake/path.py", size=1000)
        tracker.track_task_execution("TASK-001")
        tracker.track_tool_call()

        # Reset
        tracker.reset()

        usage = tracker.get_usage()
        assert usage.files_read == 0
        assert usage.tasks_executed == 0
        assert usage.tool_calls == 0

    def test_get_summary(self) -> None:
        """Test summary generation."""
        tracker = ContextTracker(threshold_percent=70.0)

        tracker.track_task_execution("TASK-001")

        summary = tracker.get_summary()

        assert "usage" in summary
        assert "threshold_percent" in summary
        assert "max_tokens" in summary
        assert "should_checkpoint" in summary
        assert "session_duration_minutes" in summary


class TestEstimateFunctions:
    """Tests for estimation utility functions."""

    def test_estimate_file_tokens_existing(self, tmp_path: Path) -> None:
        """Test file token estimation for existing file."""
        test_file = tmp_path / "test.py"
        test_file.write_text("x" * 100)  # 100 chars

        tokens = estimate_file_tokens(test_file)

        expected = int(100 * TOKENS_PER_CHAR) + TOKENS_PER_FILE_READ
        assert tokens == expected

    def test_estimate_file_tokens_missing(self) -> None:
        """Test file token estimation for missing file."""
        tokens = estimate_file_tokens("/nonexistent/file.py")

        # Should return just the overhead
        assert tokens == TOKENS_PER_FILE_READ

    def test_estimate_task_tokens_minimal(self) -> None:
        """Test task token estimation for minimal task."""
        task = {"id": "TASK-001", "title": "Test"}

        tokens = estimate_task_tokens(task)

        assert tokens >= TOKENS_PER_TASK

    def test_estimate_task_tokens_with_files(self) -> None:
        """Test task token estimation with file lists."""
        task = {
            "id": "TASK-001",
            "title": "Test",
            "files": {
                "create": ["a.py", "b.py"],
                "modify": ["c.py"],
                "read": ["d.py", "e.py", "f.py"],
            },
        }

        tokens = estimate_task_tokens(task)

        # Should include base + file overhead for 6 files
        expected_min = TOKENS_PER_TASK + (6 * TOKENS_PER_FILE_READ)
        assert tokens >= expected_min

    def test_estimate_task_tokens_with_description(self) -> None:
        """Test task token estimation with description."""
        description = "A" * 1000  # 1000 chars
        task = {
            "id": "TASK-001",
            "title": "Test",
            "description": description,
        }

        tokens = estimate_task_tokens(task)

        expected_min = TOKENS_PER_TASK + int(1000 * TOKENS_PER_CHAR)
        assert tokens >= expected_min
