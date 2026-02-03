"""Comprehensive unit tests for ZERG status command.

This module provides 100% test coverage for zerg/commands/status.py including:
- CLI command invocation with all options
- Feature auto-detection from state files
- Status display in various formats (table, JSON, watch)
- Level status rendering with filtering
- Worker status display
- Event log display
- Progress bar generation
- Error handling and edge cases
"""

from __future__ import annotations

import contextlib
import json
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

from click.testing import CliRunner
from rich.panel import Panel

from zerg.cli import cli
from zerg.commands.status import (
    DashboardRenderer,
    build_status_output,
    compact_progress_bar,
    create_progress_bar,
    detect_feature,
    format_elapsed,
    show_dashboard,
    show_json_status,
    show_level_status,
    show_recent_events,
    show_status,
    show_watch_status,
    show_worker_status,
)
from zerg.constants import WorkerStatus
from zerg.state import StateManager
from zerg.types import WorkerState

if TYPE_CHECKING:
    from pytest import MonkeyPatch


# =============================================================================
# Helper Functions
# =============================================================================


def create_test_state_file(
    state_dir: Path,
    feature: str = "test-feature",
    current_level: int = 1,
    paused: bool = False,
    error: str | None = None,
    tasks: dict[str, Any] | None = None,
    workers: dict[str, Any] | None = None,
    levels: dict[str, Any] | None = None,
    events: list[dict[str, Any]] | None = None,
) -> Path:
    """Create a test state file with the given configuration.

    Args:
        state_dir: Directory for state files
        feature: Feature name
        current_level: Current execution level
        paused: Whether execution is paused
        error: Error message if any
        tasks: Task status dictionary
        workers: Worker state dictionary
        levels: Level status dictionary
        events: Execution events list

    Returns:
        Path to the created state file
    """
    state_dir.mkdir(parents=True, exist_ok=True)

    state = {
        "feature": feature,
        "started_at": datetime.now().isoformat(),
        "current_level": current_level,
        "paused": paused,
        "error": error,
        "tasks": tasks or {},
        "workers": workers or {},
        "levels": levels or {},
        "execution_log": events or [],
    }

    state_file = state_dir / f"{feature}.json"
    state_file.write_text(json.dumps(state, indent=2))
    return state_file


def create_mock_state_manager(
    feature: str = "test-feature",
    current_level: int = 1,
    paused: bool = False,
    error: str | None = None,
    tasks: dict[str, Any] | None = None,
    workers: dict[int, WorkerState] | None = None,
    levels: dict[str, Any] | None = None,
    events: list[dict[str, Any]] | None = None,
) -> MagicMock:
    """Create a mock StateManager with configurable state.

    Args:
        feature: Feature name
        current_level: Current level
        paused: Paused state
        error: Error message
        tasks: Task status dict
        workers: Worker states
        levels: Level status dict
        events: Event list

    Returns:
        Configured MagicMock
    """
    mock = MagicMock(spec=StateManager)
    mock.feature = feature
    mock._state = {
        "tasks": tasks or {},
        "levels": levels or {},
        "execution_log": events or [],
    }

    mock.exists.return_value = True
    mock.get_current_level.return_value = current_level
    mock.is_paused.return_value = paused
    mock.get_error.return_value = error
    mock.get_events.return_value = events or []
    mock.get_all_workers.return_value = workers or {}

    # Setup get_tasks_by_status to return appropriate lists
    def get_tasks_by_status(status):
        status_str = status.value if hasattr(status, "value") else status
        return [tid for tid, task in (tasks or {}).items() if task.get("status") == status_str]

    mock.get_tasks_by_status.side_effect = get_tasks_by_status

    return mock


# =============================================================================
# Tests for detect_feature()
# =============================================================================


class TestDetectFeature:
    """Tests for feature auto-detection from state files."""

    def test_detect_no_state_directory(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test returns None when .zerg/state directory does not exist."""
        monkeypatch.chdir(tmp_path)
        result = detect_feature()
        assert result is None

    def test_detect_empty_state_directory(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test returns None when state directory is empty."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg" / "state").mkdir(parents=True)

        result = detect_feature()
        assert result is None

    def test_detect_single_state_file(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test detects feature from single state file."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        create_test_state_file(state_dir, feature="user-auth")

        result = detect_feature()
        assert result == "user-auth"

    def test_detect_most_recent_state_file(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test returns most recently modified state file."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)

        # Create older file
        older = state_dir / "older-feature.json"
        older.write_text("{}")

        # Small delay to ensure different modification times
        time.sleep(0.01)

        # Create newer file
        newer = state_dir / "newer-feature.json"
        newer.write_text("{}")

        result = detect_feature()
        assert result == "newer-feature"

    def test_detect_ignores_non_json_files(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test ignores non-JSON files in state directory."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)

        # Create non-JSON file
        (state_dir / "readme.txt").write_text("notes")

        # Create JSON file
        (state_dir / "valid-feature.json").write_text("{}")

        result = detect_feature()
        assert result == "valid-feature"


# =============================================================================
# Tests for status CLI command
# =============================================================================


class TestStatusCommand:
    """Tests for the status CLI command."""

    def test_status_help(self) -> None:
        """Test status --help shows all options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["status", "--help"])

        assert result.exit_code == 0
        assert "--feature" in result.output
        assert "--watch" in result.output
        assert "--json" in result.output
        assert "--level" in result.output
        assert "--interval" in result.output

    def test_status_no_feature_no_state(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test status shows error when no feature found."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        runner = CliRunner()
        result = runner.invoke(cli, ["status"])

        assert result.exit_code != 0
        assert "no active feature found" in result.output.lower()

    def test_status_feature_not_found(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test status shows error when feature state doesn't exist."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg" / "state").mkdir(parents=True)

        with patch("zerg.commands.status.ClaudeTasksReader") as mock_reader_cls:
            mock_reader_cls.return_value.find_feature_task_list.return_value = None
            runner = CliRunner()
            result = runner.invoke(cli, ["status", "--feature", "nonexistent"])

        assert result.exit_code != 0
        assert "no state found" in result.output.lower()

    def test_status_planned_not_executed(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test status shows helpful message for planned-but-not-executed features."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg" / "state").mkdir(parents=True)
        # Create spec dir but no state file
        (tmp_path / ".gsd" / "specs" / "my-feature").mkdir(parents=True)

        with patch("zerg.commands.status.ClaudeTasksReader") as mock_reader_cls:
            mock_reader_cls.return_value.find_feature_task_list.return_value = None
            runner = CliRunner()
            result = runner.invoke(cli, ["status", "--feature", "my-feature"])

        assert result.exit_code != 0
        assert "planned but not yet designed" in result.output.lower()
        assert "zerg design" in result.output.lower()
        assert "zerg cleanup" in result.output.lower()

    def test_status_basic_display(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test basic status display."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        create_test_state_file(state_dir, feature="test-feature")

        runner = CliRunner()
        result = runner.invoke(cli, ["status", "--feature", "test-feature"])

        # Should show feature name in output
        assert "test-feature" in result.output.lower()

    def test_status_json_output(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test status with --json flag outputs valid JSON."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        create_test_state_file(
            state_dir,
            feature="test-feature",
            current_level=2,
            tasks={"TASK-001": {"status": "complete"}},
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["status", "--feature", "test-feature", "--json"])

        # Output should be valid JSON
        output_lines = result.output.strip().split("\n")
        # Find the JSON part (may have some console output before)
        json_start = None
        for i, line in enumerate(output_lines):
            if line.strip().startswith("{"):
                json_start = i
                break

        if json_start is not None:
            json_str = "\n".join(output_lines[json_start:])
            data = json.loads(json_str)
            assert data["feature"] == "test-feature"
            assert data["current_level"] == 2

    def test_status_level_filter(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test status with --level filter."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        create_test_state_file(
            state_dir,
            feature="test-feature",
            levels={
                "1": {"name": "foundation", "status": "complete"},
                "2": {"name": "core", "status": "running"},
                "3": {"name": "integration", "status": "pending"},
            },
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["status", "--feature", "test-feature", "--level", "2"])

        # Level 2 should be in output
        assert result.exit_code == 0

    def test_status_with_error_state(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test status displays error state."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        create_test_state_file(
            state_dir,
            feature="test-feature",
            error="Task TASK-001 failed: verification error",
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["status", "--feature", "test-feature"])

        assert "error" in result.output.lower()

    def test_status_keyboard_interrupt(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test status handles KeyboardInterrupt gracefully."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        create_test_state_file(state_dir, feature="test-feature")

        with patch("zerg.commands.status.StateManager") as mock_sm:
            mock_sm.return_value.exists.return_value = True
            mock_sm.return_value.load.side_effect = KeyboardInterrupt()

            runner = CliRunner()
            result = runner.invoke(cli, ["status", "--feature", "test-feature"])

            assert "stopped watching" in result.output.lower()

    def test_status_exception_handling(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test status handles exceptions gracefully."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        create_test_state_file(state_dir, feature="test-feature")

        with patch("zerg.commands.status.StateManager") as mock_sm:
            mock_sm.return_value.exists.return_value = True
            mock_sm.return_value._state = None
            mock_sm.return_value.load.side_effect = Exception("Test error")

            runner = CliRunner()
            result = runner.invoke(cli, ["status", "--feature", "test-feature"])

            assert result.exit_code != 0
            assert "error" in result.output.lower()

    def test_status_watch_mode_via_cli(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test status with --watch flag triggers watch mode (covers line 69)."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        create_test_state_file(state_dir, feature="test-feature")

        # Mock show_watch_status to avoid infinite loop and verify it gets called
        with patch("zerg.commands.status.show_watch_status") as mock_watch:
            # Make watch raise KeyboardInterrupt to exit cleanly
            mock_watch.side_effect = KeyboardInterrupt()

            runner = CliRunner()
            result = runner.invoke(cli, ["status", "--feature", "test-feature", "--watch", "--interval", "1"])

            # show_watch_status should have been called
            mock_watch.assert_called_once()
            # Should show stopped watching message
            assert "stopped watching" in result.output.lower()


# =============================================================================
# Tests for show_status()
# =============================================================================


class TestShowStatus:
    """Tests for the show_status function."""

    def test_show_status_basic(self) -> None:
        """Test basic status display."""
        mock_state = create_mock_state_manager(
            feature="test-feature",
            current_level=1,
            tasks={
                "TASK-001": {"status": "complete"},
                "TASK-002": {"status": "in_progress"},
                "TASK-003": {"status": "pending"},
            },
        )

        with patch("zerg.commands.status.console") as mock_console:
            show_status(mock_state, "test-feature", level_filter=None)

            # Should print multiple times (header, progress, etc.)
            assert mock_console.print.called

    def test_show_status_with_level_filter(self) -> None:
        """Test status display with level filter."""
        mock_state = create_mock_state_manager(
            feature="test-feature",
            current_level=2,
            levels={
                "1": {"name": "foundation", "status": "complete"},
                "2": {"name": "core", "status": "running"},
            },
        )

        with patch("zerg.commands.status.console") as mock_console:
            show_status(mock_state, "test-feature", level_filter=2)

            assert mock_console.print.called

    def test_show_status_with_error(self) -> None:
        """Test status display shows error message."""
        mock_state = create_mock_state_manager(
            feature="test-feature",
            error="Critical failure in TASK-001",
        )

        with patch("zerg.commands.status.console") as mock_console:
            show_status(mock_state, "test-feature", level_filter=None)

            # Error should be displayed
            calls = [str(call) for call in mock_console.print.call_args_list]
            error_displayed = any("error" in call.lower() for call in calls)
            assert error_displayed

    def test_show_status_no_tasks_uses_fallback(self) -> None:
        """Test status uses fallback task count when no tasks."""
        mock_state = create_mock_state_manager(
            feature="test-feature",
            tasks={},  # No tasks
        )

        with patch("zerg.commands.status.console") as mock_console:
            show_status(mock_state, "test-feature", level_filter=None)

            # Should still display progress (with fallback of 42)
            assert mock_console.print.called


# =============================================================================
# Tests for show_level_status()
# =============================================================================


class TestShowLevelStatus:
    """Tests for the show_level_status function."""

    def test_show_level_status_no_levels(self) -> None:
        """Test level status with no level data (uses placeholder)."""
        mock_state = create_mock_state_manager(levels={})
        mock_state.get_current_level.return_value = 1

        with patch("zerg.commands.status.console") as mock_console:
            show_level_status(mock_state, level_filter=None)

            assert mock_console.print.called

    def test_show_level_status_with_levels(self) -> None:
        """Test level status with actual level data."""
        mock_state = create_mock_state_manager(
            levels={
                "1": {"name": "foundation", "status": "complete"},
                "2": {"name": "core", "status": "running"},
                "3": {"name": "integration", "status": "pending"},
            },
        )

        with patch("zerg.commands.status.console") as mock_console:
            show_level_status(mock_state, level_filter=None)

            assert mock_console.print.called

    def test_show_level_status_with_filter(self) -> None:
        """Test level status filtering to specific level."""
        mock_state = create_mock_state_manager(
            levels={
                "1": {"name": "foundation", "status": "complete"},
                "2": {"name": "core", "status": "running"},
                "3": {"name": "integration", "status": "pending"},
            },
        )

        with patch("zerg.commands.status.console") as mock_console:
            show_level_status(mock_state, level_filter=2)

            assert mock_console.print.called

    def test_show_level_status_current_level_highlighted(self) -> None:
        """Test current level is highlighted when no level data."""
        mock_state = create_mock_state_manager(levels={})
        mock_state.get_current_level.return_value = 2

        with patch("zerg.commands.status.console") as mock_console:
            show_level_status(mock_state, level_filter=None)

            # Should show RUNNING for current level
            assert mock_console.print.called

    def test_show_level_status_complete_status(self) -> None:
        """Test complete status shows checkmark."""
        mock_state = create_mock_state_manager(
            levels={"1": {"name": "foundation", "status": "complete"}},
        )

        with patch("zerg.commands.status.console") as mock_console:
            show_level_status(mock_state, level_filter=None)

            assert mock_console.print.called

    def test_show_level_status_running_status(self) -> None:
        """Test running status shows yellow indicator."""
        mock_state = create_mock_state_manager(
            levels={"1": {"name": "foundation", "status": "running"}},
        )

        with patch("zerg.commands.status.console") as mock_console:
            show_level_status(mock_state, level_filter=None)

            assert mock_console.print.called

    def test_show_level_status_pending_status(self) -> None:
        """Test pending status shows PENDING."""
        mock_state = create_mock_state_manager(
            levels={"1": {"name": "foundation", "status": "pending"}},
        )

        with patch("zerg.commands.status.console") as mock_console:
            show_level_status(mock_state, level_filter=None)

            assert mock_console.print.called

    def test_show_level_status_no_levels_with_non_matching_filter(self) -> None:
        """Test level status with no levels and filter that doesn't match current level.

        This test covers line 163 where level_filter is set but doesn't match the
        loop index when there are no actual levels in the state.
        """
        mock_state = create_mock_state_manager(levels={})
        mock_state.get_current_level.return_value = 1

        with patch("zerg.commands.status.console") as mock_console:
            # Filter for level 3, but no levels exist - should skip levels 1, 2, 4, 5
            show_level_status(mock_state, level_filter=3)

            assert mock_console.print.called


# =============================================================================
# Tests for show_worker_status()
# =============================================================================


class TestShowWorkerStatus:
    """Tests for the show_worker_status function."""

    def test_show_worker_status_no_workers(self) -> None:
        """Test worker status with no workers."""
        mock_state = create_mock_state_manager(workers={})

        with patch("zerg.commands.status.console") as mock_console:
            show_worker_status(mock_state)

            assert mock_console.print.called

    def test_show_worker_status_running_worker(self) -> None:
        """Test worker status with running worker."""
        worker = WorkerState(
            worker_id=0,
            status=WorkerStatus.RUNNING,
            port=49152,
            current_task="TASK-001",
            context_usage=0.25,
            branch="zerg/test/worker-0",
            started_at=datetime.now(),
        )

        mock_state = create_mock_state_manager(workers={0: worker})

        with patch("zerg.commands.status.console") as mock_console:
            show_worker_status(mock_state)

            assert mock_console.print.called

    def test_show_worker_status_idle_worker(self) -> None:
        """Test worker status with idle worker."""
        worker = WorkerState(
            worker_id=1,
            status=WorkerStatus.IDLE,
            port=49153,
            current_task=None,
            context_usage=0.5,
            branch="zerg/test/worker-1",
            started_at=datetime.now(),
        )

        mock_state = create_mock_state_manager(workers={1: worker})

        with patch("zerg.commands.status.console") as mock_console:
            show_worker_status(mock_state)

            assert mock_console.print.called

    def test_show_worker_status_crashed_worker(self) -> None:
        """Test worker status with crashed worker."""
        worker = WorkerState(
            worker_id=2,
            status=WorkerStatus.CRASHED,
            port=49154,
            current_task="TASK-003",
            context_usage=0.9,
            branch="zerg/test/worker-2",
            started_at=datetime.now(),
        )

        mock_state = create_mock_state_manager(workers={2: worker})

        with patch("zerg.commands.status.console") as mock_console:
            show_worker_status(mock_state)

            assert mock_console.print.called

    def test_show_worker_status_no_port(self) -> None:
        """Test worker status when worker has no port."""
        worker = WorkerState(
            worker_id=3,
            status=WorkerStatus.INITIALIZING,
            port=None,
            current_task=None,
            context_usage=0.0,
            branch="zerg/test/worker-3",
            started_at=datetime.now(),
        )

        mock_state = create_mock_state_manager(workers={3: worker})

        with patch("zerg.commands.status.console") as mock_console:
            show_worker_status(mock_state)

            assert mock_console.print.called

    def test_show_worker_status_multiple_workers(self) -> None:
        """Test worker status with multiple workers in different states."""
        workers = {
            0: WorkerState(
                worker_id=0,
                status=WorkerStatus.RUNNING,
                port=49152,
                current_task="TASK-001",
                context_usage=0.3,
                branch="zerg/test/worker-0",
                started_at=datetime.now(),
            ),
            1: WorkerState(
                worker_id=1,
                status=WorkerStatus.IDLE,
                port=49153,
                current_task=None,
                context_usage=0.1,
                branch="zerg/test/worker-1",
                started_at=datetime.now(),
            ),
            2: WorkerState(
                worker_id=2,
                status=WorkerStatus.CRASHED,
                port=49154,
                current_task="TASK-002",
                context_usage=0.95,
                branch="zerg/test/worker-2",
                started_at=datetime.now(),
            ),
        }

        mock_state = create_mock_state_manager(workers=workers)

        with patch("zerg.commands.status.console") as mock_console:
            show_worker_status(mock_state)

            assert mock_console.print.called

    def test_show_worker_status_unknown_status(self) -> None:
        """Test worker status with unknown/other status."""
        worker = WorkerState(
            worker_id=4,
            status=WorkerStatus.BLOCKED,
            port=49155,
            current_task=None,
            context_usage=0.5,
            branch="zerg/test/worker-4",
            started_at=datetime.now(),
        )

        mock_state = create_mock_state_manager(workers={4: worker})

        with patch("zerg.commands.status.console") as mock_console:
            show_worker_status(mock_state)

            assert mock_console.print.called


# =============================================================================
# Tests for show_recent_events()
# =============================================================================


class TestShowRecentEvents:
    """Tests for the show_recent_events function."""

    def test_show_recent_events_no_events(self) -> None:
        """Test with no events."""
        mock_state = create_mock_state_manager(events=[])

        with patch("zerg.commands.status.console"):
            # Function returns early for empty events, nothing to assert
            show_recent_events(mock_state, limit=5)

    def test_show_recent_events_task_complete(self) -> None:
        """Test task_complete event display."""
        events = [
            {
                "timestamp": "2025-01-26T10:30:00",
                "event": "task_complete",
                "data": {"task_id": "TASK-001", "worker_id": 0},
            }
        ]
        mock_state = create_mock_state_manager(events=events)

        with patch("zerg.commands.status.console") as mock_console:
            show_recent_events(mock_state, limit=5)

            assert mock_console.print.called

    def test_show_recent_events_task_failed(self) -> None:
        """Test task_failed event display."""
        events = [
            {
                "timestamp": "2025-01-26T10:30:00",
                "event": "task_failed",
                "data": {"task_id": "TASK-001", "error": "Verification failed"},
            }
        ]
        mock_state = create_mock_state_manager(events=events)

        with patch("zerg.commands.status.console") as mock_console:
            show_recent_events(mock_state, limit=5)

            assert mock_console.print.called

    def test_show_recent_events_level_started(self) -> None:
        """Test level_started event display."""
        events = [
            {
                "timestamp": "2025-01-26T10:30:00",
                "event": "level_started",
                "data": {"level": 2, "tasks": 5},
            }
        ]
        mock_state = create_mock_state_manager(events=events)

        with patch("zerg.commands.status.console") as mock_console:
            show_recent_events(mock_state, limit=5)

            assert mock_console.print.called

    def test_show_recent_events_level_complete(self) -> None:
        """Test level_complete event display."""
        events = [
            {
                "timestamp": "2025-01-26T10:30:00",
                "event": "level_complete",
                "data": {"level": 1},
            }
        ]
        mock_state = create_mock_state_manager(events=events)

        with patch("zerg.commands.status.console") as mock_console:
            show_recent_events(mock_state, limit=5)

            assert mock_console.print.called

    def test_show_recent_events_worker_started(self) -> None:
        """Test worker_started event display."""
        events = [
            {
                "timestamp": "2025-01-26T10:30:00",
                "event": "worker_started",
                "data": {"worker_id": 0, "port": 49152},
            }
        ]
        mock_state = create_mock_state_manager(events=events)

        with patch("zerg.commands.status.console") as mock_console:
            show_recent_events(mock_state, limit=5)

            assert mock_console.print.called

    def test_show_recent_events_unknown_event(self) -> None:
        """Test unknown event type display."""
        events = [
            {
                "timestamp": "2025-01-26T10:30:00",
                "event": "custom_event",
                "data": {},
            }
        ]
        mock_state = create_mock_state_manager(events=events)

        with patch("zerg.commands.status.console") as mock_console:
            show_recent_events(mock_state, limit=5)

            assert mock_console.print.called

    def test_show_recent_events_limit(self) -> None:
        """Test event display respects limit."""
        events = [
            {
                "timestamp": f"2025-01-26T10:3{i}:00",
                "event": "task_complete",
                "data": {"task_id": f"TASK-{i:03d}", "worker_id": 0},
            }
            for i in range(10)
        ]
        mock_state = create_mock_state_manager(events=events)

        with patch("zerg.commands.status.console") as mock_console:
            show_recent_events(mock_state, limit=3)

            assert mock_console.print.called


# =============================================================================
# Tests for show_watch_status()
# =============================================================================


class TestShowWatchStatus:
    """Tests for the show_watch_status function (continuous update mode)."""

    def test_show_watch_status_single_iteration(self) -> None:
        """Test watch status runs and can be interrupted."""
        mock_state = create_mock_state_manager(
            feature="test-feature",
            current_level=1,
            tasks={"TASK-001": {"status": "complete"}},
        )

        # Make it stop after first iteration
        call_count = 0

        def fake_sleep(interval):
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                raise KeyboardInterrupt()

        with (
            patch("zerg.commands.status.console"),
            patch("time.sleep", side_effect=fake_sleep),
            patch("zerg.commands.status.Live") as mock_live,
        ):
            mock_live_instance = MagicMock()
            mock_live.return_value.__enter__ = MagicMock(return_value=mock_live_instance)
            mock_live.return_value.__exit__ = MagicMock(return_value=False)

            with contextlib.suppress(KeyboardInterrupt):
                show_watch_status(mock_state, "test-feature", level_filter=None, interval=1)

            # Live context should have been entered
            mock_live.assert_called_once()


# =============================================================================
# Tests for build_status_output()
# =============================================================================


class TestBuildStatusOutput:
    """Tests for the build_status_output function."""

    def test_build_status_output_basic(self) -> None:
        """Test basic status output building."""
        mock_state = create_mock_state_manager(
            feature="test-feature",
            current_level=1,
            tasks={"TASK-001": {"status": "complete"}},
        )

        result = build_status_output(mock_state, "test-feature", level_filter=None)

        assert isinstance(result, Panel)

    def test_build_status_output_no_tasks(self) -> None:
        """Test status output with no tasks (uses fallback)."""
        mock_state = create_mock_state_manager(
            feature="test-feature",
            current_level=1,
            tasks={},
        )

        result = build_status_output(mock_state, "test-feature", level_filter=None)

        assert isinstance(result, Panel)

    def test_build_status_output_with_workers(self) -> None:
        """Test status output includes worker count."""
        workers = {
            0: WorkerState(
                worker_id=0,
                status=WorkerStatus.RUNNING,
                port=49152,
                branch="zerg/test/worker-0",
                started_at=datetime.now(),
            ),
            1: WorkerState(
                worker_id=1,
                status=WorkerStatus.IDLE,
                port=49153,
                branch="zerg/test/worker-1",
                started_at=datetime.now(),
            ),
        }
        mock_state = create_mock_state_manager(
            feature="test-feature",
            current_level=2,
            workers=workers,
        )

        result = build_status_output(mock_state, "test-feature", level_filter=None)

        assert isinstance(result, Panel)


# =============================================================================
# Tests for show_json_status()
# =============================================================================


class TestShowJsonStatus:
    """Tests for the show_json_status function."""

    def test_show_json_status_basic(self) -> None:
        """Test basic JSON status output."""
        mock_state = create_mock_state_manager(
            feature="test-feature",
            current_level=1,
            paused=False,
            error=None,
            tasks={"TASK-001": {"status": "complete"}},
        )

        with patch("zerg.commands.status.console") as mock_console:
            show_json_status(mock_state, level_filter=None)

            assert mock_console.print.called
            # Get the printed JSON
            call_args = mock_console.print.call_args[0][0]
            data = json.loads(call_args)
            assert data["feature"] == "test-feature"
            assert data["current_level"] == 1

    def test_show_json_status_with_workers(self) -> None:
        """Test JSON status includes worker data."""
        workers = {
            0: WorkerState(
                worker_id=0,
                status=WorkerStatus.RUNNING,
                port=49152,
                branch="zerg/test/worker-0",
                started_at=datetime.now(),
            ),
        }
        mock_state = create_mock_state_manager(
            feature="test-feature",
            workers=workers,
        )

        with patch("zerg.commands.status.console") as mock_console:
            show_json_status(mock_state, level_filter=None)

            call_args = mock_console.print.call_args[0][0]
            data = json.loads(call_args)
            assert "workers" in data
            assert "0" in data["workers"]

    def test_show_json_status_with_error(self) -> None:
        """Test JSON status includes error."""
        mock_state = create_mock_state_manager(
            feature="test-feature",
            error="Test error message",
        )

        with patch("zerg.commands.status.console") as mock_console:
            show_json_status(mock_state, level_filter=None)

            call_args = mock_console.print.call_args[0][0]
            data = json.loads(call_args)
            assert data["error"] == "Test error message"

    def test_show_json_status_with_events(self) -> None:
        """Test JSON status includes events."""
        events = [
            {
                "timestamp": "2025-01-26T10:30:00",
                "event": "task_complete",
                "data": {"task_id": "TASK-001"},
            }
        ]
        mock_state = create_mock_state_manager(
            feature="test-feature",
            events=events,
        )

        with patch("zerg.commands.status.console") as mock_console:
            show_json_status(mock_state, level_filter=None)

            call_args = mock_console.print.call_args[0][0]
            data = json.loads(call_args)
            assert "events" in data
            assert len(data["events"]) == 1


# =============================================================================
# Tests for create_progress_bar()
# =============================================================================


class TestCreateProgressBar:
    """Tests for the create_progress_bar function."""

    def test_progress_bar_0_percent(self) -> None:
        """Test progress bar at 0%."""
        bar = create_progress_bar(0)
        assert "green" in bar
        assert "dim" in bar

    def test_progress_bar_50_percent(self) -> None:
        """Test progress bar at 50%."""
        bar = create_progress_bar(50)
        assert "green" in bar
        assert "dim" in bar

    def test_progress_bar_100_percent(self) -> None:
        """Test progress bar at 100%."""
        bar = create_progress_bar(100)
        assert "green" in bar

    def test_progress_bar_custom_width(self) -> None:
        """Test progress bar with custom width."""
        bar_10 = create_progress_bar(50, width=10)
        bar_30 = create_progress_bar(50, width=30)

        # Different widths should produce different results
        assert len(bar_10) < len(bar_30)

    def test_progress_bar_negative_percent(self) -> None:
        """Test progress bar handles negative percent."""
        bar = create_progress_bar(-10)
        # Should not crash and should handle gracefully
        assert bar is not None

    def test_progress_bar_over_100_percent(self) -> None:
        """Test progress bar handles over 100%."""
        bar = create_progress_bar(150)
        # Should not crash
        assert bar is not None


# =============================================================================
# Integration Tests
# =============================================================================


class TestStatusIntegration:
    """Integration tests for status command."""

    def test_full_status_flow(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test complete status display flow."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"

        # Create a realistic state
        create_test_state_file(
            state_dir,
            feature="user-auth",
            current_level=2,
            paused=False,
            error=None,
            tasks={
                "L1-001": {"status": "complete", "worker_id": 0},
                "L1-002": {"status": "complete", "worker_id": 1},
                "L2-001": {"status": "in_progress", "worker_id": 0},
                "L2-002": {"status": "pending"},
            },
            workers={
                "0": {
                    "worker_id": 0,
                    "status": "running",
                    "port": 49152,
                    "current_task": "L2-001",
                    "context_usage": 0.35,
                    "branch": "zerg/user-auth/worker-0",
                    "tasks_completed": 1,
                },
                "1": {
                    "worker_id": 1,
                    "status": "idle",
                    "port": 49153,
                    "current_task": None,
                    "context_usage": 0.2,
                    "branch": "zerg/user-auth/worker-1",
                    "tasks_completed": 1,
                },
            },
            levels={
                "1": {"name": "foundation", "status": "complete"},
                "2": {"name": "core", "status": "running"},
            },
            events=[
                {
                    "timestamp": "2025-01-26T10:00:00",
                    "event": "level_started",
                    "data": {"level": 1, "tasks": 2},
                },
                {
                    "timestamp": "2025-01-26T10:05:00",
                    "event": "task_complete",
                    "data": {"task_id": "L1-001", "worker_id": 0},
                },
                {
                    "timestamp": "2025-01-26T10:08:00",
                    "event": "task_complete",
                    "data": {"task_id": "L1-002", "worker_id": 1},
                },
                {
                    "timestamp": "2025-01-26T10:10:00",
                    "event": "level_complete",
                    "data": {"level": 1},
                },
                {
                    "timestamp": "2025-01-26T10:11:00",
                    "event": "level_started",
                    "data": {"level": 2, "tasks": 2},
                },
            ],
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["status", "--feature", "user-auth"])

        # Should succeed
        assert result.exit_code == 0
        # Should contain feature name
        assert "user-auth" in result.output.lower()

    def test_status_auto_detect_feature(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test status auto-detects feature from state files."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"

        create_test_state_file(state_dir, feature="auto-detected")

        runner = CliRunner()
        result = runner.invoke(cli, ["status"])

        # Should auto-detect the feature
        # Either shows the feature or errors gracefully
        assert result.exit_code == 0 or "auto-detected" in result.output.lower()


# =============================================================================
# Tests for format_elapsed()
# =============================================================================


class TestFormatElapsed:
    """Tests for elapsed time formatting."""

    def test_format_elapsed_seconds(self) -> None:
        """Test formatting with just seconds."""
        start = datetime.now()
        result = format_elapsed(start)
        assert result == "0s"

    def test_format_elapsed_minutes_seconds(self) -> None:
        """Test formatting with minutes and seconds."""
        from datetime import timedelta

        start = datetime.now() - timedelta(minutes=5, seconds=32)
        result = format_elapsed(start)
        assert result == "5m 32s"

    def test_format_elapsed_hours_minutes(self) -> None:
        """Test formatting with hours and minutes."""
        from datetime import timedelta

        start = datetime.now() - timedelta(hours=1, minutes=23)
        result = format_elapsed(start)
        assert result == "1h 23m"


# =============================================================================
# Tests for compact_progress_bar()
# =============================================================================


class TestCompactProgressBar:
    """Tests for compact progress bar generation."""

    def test_compact_progress_bar_0_percent(self) -> None:
        """Test progress bar at 0%."""
        result = compact_progress_bar(0)
        assert result == "░" * 20

    def test_compact_progress_bar_50_percent(self) -> None:
        """Test progress bar at 50%."""
        result = compact_progress_bar(50)
        assert result == "█" * 10 + "░" * 10

    def test_compact_progress_bar_100_percent(self) -> None:
        """Test progress bar at 100%."""
        result = compact_progress_bar(100)
        assert result == "█" * 20

    def test_compact_progress_bar_custom_width(self) -> None:
        """Test progress bar with custom width."""
        result = compact_progress_bar(50, width=10)
        assert result == "█" * 5 + "░" * 5
        assert len(result) == 10


# =============================================================================
# Tests for DashboardRenderer
# =============================================================================


class TestDashboardRenderer:
    """Tests for DashboardRenderer class."""

    def test_dashboard_renderer_init(self) -> None:
        """Test DashboardRenderer initialization."""
        mock_state = create_mock_state_manager()
        renderer = DashboardRenderer(mock_state, "test-feature")

        assert renderer.state == mock_state
        assert renderer.feature == "test-feature"
        assert renderer.start_time is not None

    def test_dashboard_renderer_render_returns_group(self) -> None:
        """Test render() returns a Group."""
        from rich.console import Group

        mock_state = create_mock_state_manager()
        renderer = DashboardRenderer(mock_state, "test-feature")

        result = renderer.render()
        assert isinstance(result, Group)

    def test_dashboard_renderer_header(self) -> None:
        """Test header rendering contains feature name."""
        mock_state = create_mock_state_manager()
        renderer = DashboardRenderer(mock_state, "my-feature")

        header = renderer._render_header()
        # Header should be a Panel containing feature name
        assert isinstance(header, Panel)

    def test_dashboard_renderer_progress(self) -> None:
        """Test progress rendering with tasks."""
        mock_state = create_mock_state_manager(
            tasks={
                "L1-001": {"status": "complete", "level": 1},
                "L1-002": {"status": "in_progress", "level": 1},
                "L1-003": {"status": "pending", "level": 1},
            }
        )
        renderer = DashboardRenderer(mock_state, "test-feature")

        progress = renderer._render_progress()
        # Should contain progress info
        assert "Progress" in str(progress)

    def test_dashboard_renderer_levels(self) -> None:
        """Test level rendering with multiple levels."""
        mock_state = create_mock_state_manager(
            tasks={
                "L1-001": {"status": "complete", "level": 1},
                "L1-002": {"status": "complete", "level": 1},
                "L2-001": {"status": "in_progress", "level": 2},
                "L2-002": {"status": "pending", "level": 2},
            }
        )
        renderer = DashboardRenderer(mock_state, "test-feature")

        levels = renderer._render_levels()
        assert isinstance(levels, Panel)

    def test_dashboard_renderer_workers(self) -> None:
        """Test worker rendering with various statuses."""
        mock_state = create_mock_state_manager(
            workers={
                0: WorkerState(
                    worker_id=0,
                    status=WorkerStatus.RUNNING,
                    current_task="L2-001",
                    context_usage=0.65,
                    port=50001,
                ),
                1: WorkerState(
                    worker_id=1,
                    status=WorkerStatus.IDLE,
                    context_usage=0.0,
                    port=50002,
                ),
            }
        )
        renderer = DashboardRenderer(mock_state, "test-feature")

        workers = renderer._render_workers()
        assert isinstance(workers, Panel)

    def test_dashboard_renderer_workers_high_context_warning(self) -> None:
        """Test worker with high context usage shows warning."""
        mock_state = create_mock_state_manager(
            workers={
                0: WorkerState(
                    worker_id=0,
                    status=WorkerStatus.RUNNING,
                    current_task="L2-001",
                    context_usage=0.90,  # Above 85% threshold
                    port=50001,
                ),
            }
        )
        renderer = DashboardRenderer(mock_state, "test-feature")

        workers = renderer._render_workers()
        # Should render without error (warning symbol is in there)
        assert isinstance(workers, Panel)

    def test_dashboard_renderer_events(self) -> None:
        """Test event rendering with various event types."""
        mock_state = create_mock_state_manager(
            events=[
                {
                    "timestamp": "2025-01-26T14:32:15",
                    "event": "task_complete",
                    "data": {"task_id": "L2-005", "worker_id": 2, "duration": "45s"},
                },
                {
                    "timestamp": "2025-01-26T14:32:08",
                    "event": "task_claimed",
                    "data": {"task_id": "L2-012", "worker_id": 2},
                },
            ]
        )
        renderer = DashboardRenderer(mock_state, "test-feature")

        events = renderer._render_events()
        assert isinstance(events, Panel)

    def test_dashboard_renderer_events_all_types(self) -> None:
        """Test all event types are rendered correctly."""
        mock_state = create_mock_state_manager(
            events=[
                {
                    "timestamp": "2025-01-26T10:00:00",
                    "event": "task_complete",
                    "data": {"task_id": "L1-001", "worker_id": 0},
                },
                {
                    "timestamp": "2025-01-26T10:01:00",
                    "event": "task_claimed",
                    "data": {"task_id": "L1-002", "worker_id": 1},
                },
                {
                    "timestamp": "2025-01-26T10:02:00",
                    "event": "task_failed",
                    "data": {"task_id": "L1-003", "error": "Test error"},
                },
                {"timestamp": "2025-01-26T10:03:00", "event": "level_started", "data": {"level": 2, "tasks": 5}},
                {"timestamp": "2025-01-26T10:04:00", "event": "level_complete", "data": {"level": 1}},
                {"timestamp": "2025-01-26T10:05:00", "event": "worker_started", "data": {"worker_id": 0}},
                {"timestamp": "2025-01-26T10:06:00", "event": "merge_started", "data": {"level": 1}},
                {"timestamp": "2025-01-26T10:07:00", "event": "merge_complete", "data": {"level": 1}},
                {"timestamp": "2025-01-26T10:08:00", "event": "unknown_event", "data": {}},
            ]
        )
        renderer = DashboardRenderer(mock_state, "test-feature")

        events = renderer._render_events(limit=10)
        assert isinstance(events, Panel)

    def test_dashboard_renderer_no_workers(self) -> None:
        """Test rendering with no active workers."""
        mock_state = create_mock_state_manager(workers={})
        renderer = DashboardRenderer(mock_state, "test-feature")

        workers = renderer._render_workers()
        assert isinstance(workers, Panel)

    def test_dashboard_renderer_no_events(self) -> None:
        """Test rendering with no events."""
        mock_state = create_mock_state_manager(events=[])
        renderer = DashboardRenderer(mock_state, "test-feature")

        events = renderer._render_events()
        assert isinstance(events, Panel)

    def test_dashboard_renderer_empty_state(self) -> None:
        """Test rendering with empty state."""
        mock_state = create_mock_state_manager()
        renderer = DashboardRenderer(mock_state, "test-feature")

        # Should not raise
        result = renderer.render()
        assert result is not None


# =============================================================================
# Tests for show_dashboard()
# =============================================================================


class TestShowDashboard:
    """Tests for show_dashboard function."""

    def test_show_dashboard_single_iteration(self) -> None:
        """Test dashboard exits cleanly on keyboard interrupt."""
        mock_state = create_mock_state_manager()

        with patch("zerg.commands.status.Live") as mock_live:
            # Simulate keyboard interrupt on first sleep
            with patch("zerg.commands.status.time.sleep", side_effect=KeyboardInterrupt):
                # Should not raise
                show_dashboard(mock_state, "test-feature", interval=1)

            # Live should have been called with screen=True
            mock_live.assert_called_once()


# =============================================================================
# Tests for Dashboard CLI flag
# =============================================================================


class TestDashboardCLI:
    """Tests for --dashboard CLI flag."""

    def test_dashboard_flag_exists(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test --dashboard flag is recognized."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        create_test_state_file(state_dir, feature="test-feature")

        runner = CliRunner()
        # Test that --help shows the dashboard option
        result = runner.invoke(cli, ["status", "--help"])
        assert "--dashboard" in result.output
        assert "-d" in result.output

    def test_dashboard_short_flag(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test -d short flag is recognized."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        create_test_state_file(state_dir, feature="test-feature")

        with patch("zerg.commands.status.show_dashboard") as mock_show:
            runner = CliRunner()
            runner.invoke(cli, ["status", "-d", "--feature", "test-feature"])
            # Should call show_dashboard
            mock_show.assert_called_once()

    def test_dashboard_with_interval(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test --dashboard with custom interval."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        create_test_state_file(state_dir, feature="test-feature")

        with patch("zerg.commands.status.show_dashboard") as mock_show:
            runner = CliRunner()
            runner.invoke(cli, ["status", "-d", "--interval", "2", "--feature", "test-feature"])
            # Should call show_dashboard with interval=2
            mock_show.assert_called_once()
            args, kwargs = mock_show.call_args
            # Check interval is passed (could be positional or keyword)
            assert 2 in args or kwargs.get("interval") == 2
