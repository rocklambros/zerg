"""Thinned unit tests for ZERG status command.

Reduced from 82 to ~25 tests by:
- Collapsing per-status permutations into single parametrized tests
- Keeping 1 happy-path + 1 error-path per class
- Removing redundant event type tests (1 per event type -> parametrize)
- Merging dashboard sub-tests into core render test
"""

from __future__ import annotations

import contextlib
import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
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
    """Create a test state file with the given configuration."""
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
    """Create a mock StateManager with configurable state."""
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

    def test_detect_single_state_file(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test detects feature from single state file."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        create_test_state_file(state_dir, feature="user-auth")

        result = detect_feature()
        assert result == "user-auth"


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

    def test_status_no_feature_no_state(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test status shows error when no feature found."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        runner = CliRunner()
        result = runner.invoke(cli, ["status"])

        assert result.exit_code != 0
        assert "no active feature found" in result.output.lower()

    def test_status_basic_display(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test basic status display."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        create_test_state_file(state_dir, feature="test-feature")

        runner = CliRunner()
        result = runner.invoke(cli, ["status", "--feature", "test-feature"])

        assert "test-feature" in result.output.lower()

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


# =============================================================================
# Tests for show_status()
# =============================================================================


class TestShowStatus:
    """Tests for the show_status function."""

    def test_show_status_basic(self) -> None:
        """Test basic status display with tasks."""
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
            assert mock_console.print.called

    def test_show_status_with_error(self) -> None:
        """Test status display shows error message."""
        mock_state = create_mock_state_manager(
            feature="test-feature",
            error="Critical failure in TASK-001",
        )

        with patch("zerg.commands.status.console") as mock_console:
            show_status(mock_state, "test-feature", level_filter=None)
            calls = [str(call) for call in mock_console.print.call_args_list]
            error_displayed = any("error" in call.lower() for call in calls)
            assert error_displayed


# =============================================================================
# Tests for show_level_status()
# =============================================================================


class TestShowLevelStatus:
    """Tests for the show_level_status function."""

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
            },
        )

        with patch("zerg.commands.status.console") as mock_console:
            show_level_status(mock_state, level_filter=2)
            assert mock_console.print.called


# =============================================================================
# Tests for show_worker_status()
# =============================================================================


class TestShowWorkerStatus:
    """Tests for the show_worker_status function."""

    @pytest.mark.parametrize(
        "status,current_task,port",
        [
            (WorkerStatus.RUNNING, "TASK-001", 49152),
            (WorkerStatus.IDLE, None, 49153),
            (WorkerStatus.CRASHED, "TASK-003", 49154),
            (WorkerStatus.BLOCKED, None, 49155),
        ],
    )
    def test_show_worker_status_by_state(self, status: WorkerStatus, current_task: str | None, port: int) -> None:
        """Test worker status display for various worker states."""
        worker = WorkerState(
            worker_id=0,
            status=status,
            port=port,
            current_task=current_task,
            context_usage=0.5,
            branch="zerg/test/worker-0",
            started_at=datetime.now(),
        )

        mock_state = create_mock_state_manager(workers={0: worker})

        with patch("zerg.commands.status.console") as mock_console:
            show_worker_status(mock_state)
            assert mock_console.print.called

    def test_show_worker_status_no_workers(self) -> None:
        """Test worker status with no workers."""
        mock_state = create_mock_state_manager(workers={})

        with patch("zerg.commands.status.console") as mock_console:
            show_worker_status(mock_state)
            assert mock_console.print.called


# =============================================================================
# Tests for show_recent_events()
# =============================================================================


class TestShowRecentEvents:
    """Tests for the show_recent_events function."""

    @pytest.mark.parametrize(
        "event_type,data",
        [
            ("task_complete", {"task_id": "TASK-001", "worker_id": 0}),
            ("task_failed", {"task_id": "TASK-001", "error": "Verification failed"}),
            ("level_started", {"level": 2, "tasks": 5}),
            ("level_complete", {"level": 1}),
            ("worker_started", {"worker_id": 0, "port": 49152}),
            ("custom_event", {}),
        ],
    )
    def test_show_recent_events_by_type(self, event_type: str, data: dict) -> None:
        """Test various event type displays."""
        events = [{"timestamp": "2025-01-26T10:30:00", "event": event_type, "data": data}]
        mock_state = create_mock_state_manager(events=events)

        with patch("zerg.commands.status.console") as mock_console:
            show_recent_events(mock_state, limit=5)
            assert mock_console.print.called

    def test_show_recent_events_no_events(self) -> None:
        """Test with no events."""
        mock_state = create_mock_state_manager(events=[])

        with patch("zerg.commands.status.console"):
            show_recent_events(mock_state, limit=5)


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
            call_args = mock_console.print.call_args[0][0]
            data = json.loads(call_args)
            assert data["feature"] == "test-feature"
            assert data["current_level"] == 1


# =============================================================================
# Tests for progress bars
# =============================================================================


class TestCreateProgressBar:
    """Tests for the create_progress_bar function."""

    @pytest.mark.parametrize("percent", [0, 50, 100])
    def test_progress_bar_values(self, percent: int) -> None:
        """Test progress bar at various percentages."""
        bar = create_progress_bar(percent)
        assert "green" in bar


class TestCompactProgressBar:
    """Tests for compact progress bar generation."""

    @pytest.mark.parametrize(
        "percent,expected_filled",
        [(0, 0), (50, 10), (100, 20)],
    )
    def test_compact_progress_bar(self, percent: int, expected_filled: int) -> None:
        """Test compact progress bar at various percentages."""
        result = compact_progress_bar(percent)
        assert result == "\u2588" * expected_filled + "\u2591" * (20 - expected_filled)


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

    def test_format_elapsed_hours_minutes(self) -> None:
        """Test formatting with hours and minutes."""
        from datetime import timedelta

        start = datetime.now() - timedelta(hours=1, minutes=23)
        result = format_elapsed(start)
        assert result == "1h 23m"


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

    def test_dashboard_renderer_empty_state(self) -> None:
        """Test rendering with empty state (no workers, no events)."""
        mock_state = create_mock_state_manager()
        renderer = DashboardRenderer(mock_state, "test-feature")

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
            with patch("zerg.commands.status.time.sleep", side_effect=KeyboardInterrupt):
                show_dashboard(mock_state, "test-feature", interval=1)

            mock_live.assert_called_once()


# =============================================================================
# Tests for Dashboard CLI flag
# =============================================================================


class TestDashboardCLI:
    """Tests for --dashboard CLI flag."""

    def test_dashboard_short_flag(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test -d short flag triggers show_dashboard."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        create_test_state_file(state_dir, feature="test-feature")

        with patch("zerg.commands.status.show_dashboard") as mock_show:
            runner = CliRunner()
            runner.invoke(cli, ["status", "-d", "--feature", "test-feature"])
            mock_show.assert_called_once()
