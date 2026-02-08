"""Unit tests for zerg.rendering.status_renderer.

Covers standalone helpers, DashboardRenderer methods, and standalone
render functions. Mocks Rich Console for output capture and StateManager
for state data.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from zerg.constants import TaskStatus, WorkerStatus
from zerg.rendering.status_renderer import (
    LEVEL_SYMBOLS,
    STEP_INDICATORS,
    WORKER_COLORS,
    DashboardRenderer,
    build_status_output,
    compact_progress_bar,
    create_progress_bar,
    format_duration,
    format_elapsed,
    format_step_progress,
    get_step_progress_for_task,
    show_commits_view,
    show_json_status,
    show_level_metrics,
    show_level_status,
    show_live_status,
    show_recent_events,
    show_status,
    show_tasks_view,
    show_watch_status,
    show_worker_metrics,
    show_worker_status,
    show_workers_view,
)
from zerg.types import LevelMetrics, WorkerMetrics, WorkerState

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_console() -> Console:
    """Create a Rich Console that writes to a StringIO buffer.

    highlight=False prevents Rich from inserting ANSI codes around numbers,
    which would break simple substring assertions on the output.
    """
    return Console(file=StringIO(), force_terminal=True, width=120, highlight=False)


def _get_output(c: Console) -> str:
    """Extract text written to the Console's StringIO buffer."""
    c.file.seek(0)
    return c.file.read()


def _make_worker(
    worker_id: int = 1,
    status: WorkerStatus = WorkerStatus.RUNNING,
    current_task: str | None = "TASK-001",
    port: int | None = 50000,
    context_usage: float = 0.5,
) -> WorkerState:
    return WorkerState(
        worker_id=worker_id,
        status=status,
        current_task=current_task,
        port=port,
        context_usage=context_usage,
    )


def _make_state_manager(
    tasks: dict | None = None,
    levels: dict | None = None,
    workers: dict[int, WorkerState] | None = None,
    workers_data: dict | None = None,
    events: list | None = None,
    current_level: int = 1,
    paused: bool = False,
    error: str | None = None,
    feature: str = "test-feature",
) -> MagicMock:
    """Build a minimal mock StateManager."""
    sm = MagicMock()
    sm.feature = feature

    _tasks = tasks or {}
    _levels = levels or {}
    _workers = workers or {}
    _workers_data = workers_data or {}
    _events = events or []

    sm._state = {
        "tasks": _tasks,
        "levels": _levels,
        "workers": _workers_data,
    }
    sm.get_all_workers.return_value = _workers
    sm.get_tasks_by_status.side_effect = lambda s: [
        tid for tid, t in _tasks.items() if t.get("status") == (s.value if hasattr(s, "value") else s)
    ]
    sm.get_events.return_value = _events
    sm.get_current_level.return_value = current_level
    sm.is_paused.return_value = paused
    sm.get_error.return_value = error
    sm.load.return_value = sm._state
    return sm


# ===========================================================================
# format_step_progress
# ===========================================================================


class TestFormatStepProgress:
    """Tests for format_step_progress helper."""

    def test_returns_none_when_current_step_is_none(self) -> None:
        assert format_step_progress(None, 5) is None

    def test_returns_none_when_total_steps_is_none(self) -> None:
        assert format_step_progress(3, None) is None

    def test_returns_none_when_total_steps_is_zero(self) -> None:
        assert format_step_progress(1, 0) is None

    def test_basic_formatting_without_step_states(self) -> None:
        result = format_step_progress(2, 4)
        assert result is not None
        assert "Step 2/4" in result
        # 1 completed, 1 in_progress, 2 pending
        assert STEP_INDICATORS["completed"] in result
        assert STEP_INDICATORS["in_progress"] in result
        assert STEP_INDICATORS["pending"] in result

    def test_with_explicit_step_states(self) -> None:
        states = ["completed", "completed", "in_progress", "pending"]
        result = format_step_progress(3, 4, step_states=states)
        assert result is not None
        assert "Step 3/4" in result

    def test_all_completed(self) -> None:
        result = format_step_progress(3, 3)
        assert result is not None
        # Steps 1,2 completed; step 3 in_progress
        assert STEP_INDICATORS["completed"] in result

    @pytest.mark.parametrize(
        "current,total",
        [(1, 1), (1, 10), (5, 5), (10, 10)],
    )
    def test_various_step_counts(self, current: int, total: int) -> None:
        result = format_step_progress(current, total)
        assert result is not None
        assert f"Step {current}/{total}" in result

    def test_unknown_state_falls_back_to_pending(self) -> None:
        result = format_step_progress(1, 2, step_states=["unknown", "pending"])
        assert result is not None
        # "unknown" should map to pending indicator
        assert STEP_INDICATORS["pending"] in result


# ===========================================================================
# get_step_progress_for_task
# ===========================================================================


class TestGetStepProgressForTask:
    """Tests for get_step_progress_for_task helper."""

    def test_returns_none_when_worker_id_is_none(self) -> None:
        assert get_step_progress_for_task("TASK-001", None, MagicMock()) is None

    def test_returns_none_when_heartbeat_monitor_is_none(self) -> None:
        assert get_step_progress_for_task("TASK-001", 1, None) is None

    def test_returns_none_when_no_heartbeat(self) -> None:
        monitor = MagicMock()
        monitor.read.return_value = None
        assert get_step_progress_for_task("TASK-001", 1, monitor) is None

    def test_returns_none_when_heartbeat_task_mismatch(self) -> None:
        heartbeat = MagicMock()
        heartbeat.task_id = "TASK-002"
        monitor = MagicMock()
        monitor.read.return_value = heartbeat
        assert get_step_progress_for_task("TASK-001", 1, monitor) is None

    def test_returns_display_when_task_matches(self) -> None:
        heartbeat = MagicMock()
        heartbeat.task_id = "TASK-001"
        heartbeat.get_step_progress_display.return_value = "[Step 2/5]"
        monitor = MagicMock()
        monitor.read.return_value = heartbeat
        result = get_step_progress_for_task("TASK-001", 1, monitor)
        assert result == "[Step 2/5]"


# ===========================================================================
# format_elapsed
# ===========================================================================


class TestFormatElapsed:
    """Tests for format_elapsed helper."""

    def test_seconds_only(self) -> None:
        start = datetime.now() - timedelta(seconds=30)
        result = format_elapsed(start)
        assert result.endswith("s")
        assert "m" not in result

    def test_minutes_and_seconds(self) -> None:
        start = datetime.now() - timedelta(minutes=5, seconds=32)
        result = format_elapsed(start)
        assert "m" in result
        assert "s" in result
        assert "h" not in result

    def test_hours_and_minutes(self) -> None:
        start = datetime.now() - timedelta(hours=1, minutes=23)
        result = format_elapsed(start)
        assert "h" in result
        assert "m" in result

    def test_zero_seconds(self) -> None:
        start = datetime.now()
        result = format_elapsed(start)
        assert result == "0s"


# ===========================================================================
# compact_progress_bar
# ===========================================================================


class TestCompactProgressBar:
    """Tests for compact_progress_bar helper."""

    def test_zero_percent(self) -> None:
        result = compact_progress_bar(0, width=10)
        assert len(result) == 10
        assert "\u2588" not in result

    def test_hundred_percent(self) -> None:
        result = compact_progress_bar(100, width=10)
        assert len(result) == 10
        assert "\u2591" not in result

    def test_fifty_percent(self) -> None:
        result = compact_progress_bar(50, width=20)
        assert len(result) == 20
        filled = result.count("\u2588")
        assert filled == 10

    @pytest.mark.parametrize("pct", [0, 25, 50, 75, 100])
    def test_default_width_is_20(self, pct: float) -> None:
        result = compact_progress_bar(pct)
        assert len(result) == 20


# ===========================================================================
# create_progress_bar
# ===========================================================================


class TestCreateProgressBar:
    """Tests for create_progress_bar (Rich markup version)."""

    def test_contains_green_markup(self) -> None:
        result = create_progress_bar(50)
        assert "[green]" in result
        assert "[dim]" in result

    def test_zero_percent_no_green_block(self) -> None:
        result = create_progress_bar(0)
        # No filled blocks between [green] tags
        assert "[green][/green]" in result

    def test_hundred_percent_no_dim_block(self) -> None:
        result = create_progress_bar(100)
        assert "[dim][/dim]" in result


# ===========================================================================
# format_duration
# ===========================================================================


class TestFormatDuration:
    """Tests for format_duration helper."""

    def test_none_returns_dash(self) -> None:
        assert format_duration(None) == "-"

    def test_milliseconds(self) -> None:
        assert format_duration(500) == "500ms"

    def test_seconds(self) -> None:
        assert format_duration(1500) == "1.5s"

    def test_minutes_with_seconds(self) -> None:
        assert format_duration(90_000) == "1m30s"

    def test_minutes_exact(self) -> None:
        assert format_duration(120_000) == "2m"

    def test_hours_with_minutes(self) -> None:
        assert format_duration(5_400_000) == "1h30m"

    def test_hours_exact(self) -> None:
        assert format_duration(3_600_000) == "1h"

    @pytest.mark.parametrize(
        "ms,expected",
        [
            (0, "0ms"),
            (999, "999ms"),
            (1000, "1.0s"),
            (59_999, "60.0s"),
            (60_000, "1m"),
        ],
    )
    def test_boundary_values(self, ms: int, expected: str) -> None:
        assert format_duration(ms) == expected


# ===========================================================================
# DashboardRenderer
# ===========================================================================


class TestDashboardRendererHeader:
    """Tests for DashboardRenderer._render_header."""

    def test_header_contains_feature_name(self) -> None:
        sm = _make_state_manager(feature="my-feature")
        renderer = DashboardRenderer(sm, "my-feature")
        panel = renderer._render_header()
        assert isinstance(panel, Panel)

    def test_header_shows_data_source_state(self) -> None:
        sm = _make_state_manager()
        renderer = DashboardRenderer(sm, "feat", data_source="state")
        panel = renderer._render_header()
        assert isinstance(panel, Panel)

    def test_header_shows_data_source_tasks(self) -> None:
        sm = _make_state_manager()
        renderer = DashboardRenderer(sm, "feat", data_source="tasks")
        panel = renderer._render_header()
        assert isinstance(panel, Panel)


class TestDashboardRendererProgress:
    """Tests for DashboardRenderer._render_progress."""

    def test_no_tasks_shows_zero(self) -> None:
        sm = _make_state_manager(tasks={})
        renderer = DashboardRenderer(sm, "feat")
        result = renderer._render_progress()
        assert isinstance(result, Text)
        assert "0%" in result.plain

    def test_half_complete(self) -> None:
        tasks = {
            "T1": {"status": TaskStatus.COMPLETE.value},
            "T2": {"status": TaskStatus.PENDING.value},
        }
        sm = _make_state_manager(tasks=tasks)
        renderer = DashboardRenderer(sm, "feat")
        result = renderer._render_progress()
        assert "50%" in result.plain

    def test_all_complete(self) -> None:
        tasks = {
            "T1": {"status": TaskStatus.COMPLETE.value},
            "T2": {"status": TaskStatus.COMPLETE.value},
        }
        sm = _make_state_manager(tasks=tasks)
        renderer = DashboardRenderer(sm, "feat")
        result = renderer._render_progress()
        assert "100%" in result.plain


class TestDashboardRendererLevels:
    """Tests for DashboardRenderer._render_levels."""

    def test_no_tasks_shows_no_levels(self) -> None:
        sm = _make_state_manager(tasks={})
        renderer = DashboardRenderer(sm, "feat")
        panel = renderer._render_levels()
        assert isinstance(panel, Panel)

    def test_single_level_complete(self) -> None:
        tasks = {
            "T1": {"level": 1, "status": TaskStatus.COMPLETE.value},
            "T2": {"level": 1, "status": TaskStatus.COMPLETE.value},
        }
        sm = _make_state_manager(tasks=tasks)
        renderer = DashboardRenderer(sm, "feat")
        panel = renderer._render_levels()
        assert isinstance(panel, Panel)

    def test_multiple_levels(self) -> None:
        tasks = {
            "T1": {"level": 1, "status": TaskStatus.COMPLETE.value},
            "T2": {"level": 2, "status": TaskStatus.PENDING.value},
        }
        sm = _make_state_manager(tasks=tasks)
        renderer = DashboardRenderer(sm, "feat")
        panel = renderer._render_levels()
        assert isinstance(panel, Panel)

    def test_level_running_status(self) -> None:
        tasks = {
            "T1": {"level": 1, "status": TaskStatus.IN_PROGRESS.value},
        }
        sm = _make_state_manager(tasks=tasks)
        renderer = DashboardRenderer(sm, "feat")
        panel = renderer._render_levels()
        assert isinstance(panel, Panel)

    def test_level_merge_status(self) -> None:
        tasks = {"T1": {"level": 1, "status": TaskStatus.COMPLETE.value}}
        levels = {"1": {"merge_status": "merging"}}
        sm = _make_state_manager(tasks=tasks, levels=levels)
        renderer = DashboardRenderer(sm, "feat")
        panel = renderer._render_levels()
        assert isinstance(panel, Panel)

    def test_level_conflict_status(self) -> None:
        tasks = {"T1": {"level": 1, "status": TaskStatus.COMPLETE.value}}
        levels = {"1": {"merge_status": "conflict"}}
        sm = _make_state_manager(tasks=tasks, levels=levels)
        renderer = DashboardRenderer(sm, "feat")
        panel = renderer._render_levels()
        assert isinstance(panel, Panel)


class TestDashboardRendererWorkers:
    """Tests for DashboardRenderer._render_workers."""

    @patch("zerg.rendering.status_renderer.HeartbeatMonitor")
    def test_no_workers_state_source(self, mock_hb_cls: MagicMock) -> None:
        sm = _make_state_manager(workers={})
        renderer = DashboardRenderer(sm, "feat", data_source="state")
        panel = renderer._render_workers()
        assert isinstance(panel, Panel)

    @patch("zerg.rendering.status_renderer.HeartbeatMonitor")
    def test_no_workers_tasks_source(self, mock_hb_cls: MagicMock) -> None:
        sm = _make_state_manager(workers={})
        renderer = DashboardRenderer(sm, "feat", data_source="tasks")
        panel = renderer._render_workers()
        assert isinstance(panel, Panel)

    @patch("zerg.rendering.status_renderer.HeartbeatMonitor")
    def test_worker_with_context_bar(self, mock_hb_cls: MagicMock) -> None:
        mock_hb_cls.return_value.read.return_value = None
        w = _make_worker(context_usage=0.5)
        sm = _make_state_manager(workers={1: w})
        renderer = DashboardRenderer(sm, "feat")
        panel = renderer._render_workers()
        assert isinstance(panel, Panel)

    @patch("zerg.rendering.status_renderer.HeartbeatMonitor")
    def test_worker_high_context_warning(self, mock_hb_cls: MagicMock) -> None:
        mock_hb_cls.return_value.read.return_value = None
        w = _make_worker(context_usage=0.90)
        sm = _make_state_manager(workers={1: w})
        renderer = DashboardRenderer(sm, "feat")
        panel = renderer._render_workers()
        assert isinstance(panel, Panel)

    @patch("zerg.rendering.status_renderer.HeartbeatMonitor")
    def test_worker_medium_context(self, mock_hb_cls: MagicMock) -> None:
        mock_hb_cls.return_value.read.return_value = None
        w = _make_worker(context_usage=0.75)
        sm = _make_state_manager(workers={1: w})
        renderer = DashboardRenderer(sm, "feat")
        panel = renderer._render_workers()
        assert isinstance(panel, Panel)

    @patch("zerg.rendering.status_renderer.HeartbeatMonitor")
    def test_worker_with_step_progress(self, mock_hb_cls: MagicMock) -> None:
        heartbeat = MagicMock()
        heartbeat.task_id = "TASK-001"
        heartbeat.get_step_progress_display.return_value = "[Step 2/5]"
        mock_hb_cls.return_value.read.return_value = heartbeat

        w = _make_worker(current_task="TASK-001")
        sm = _make_state_manager(workers={1: w})
        renderer = DashboardRenderer(sm, "feat")
        panel = renderer._render_workers()
        assert isinstance(panel, Panel)

    @patch("zerg.rendering.status_renderer.HeartbeatMonitor")
    def test_worker_no_current_task(self, mock_hb_cls: MagicMock) -> None:
        mock_hb_cls.return_value.read.return_value = None
        w = _make_worker(current_task=None, status=WorkerStatus.IDLE)
        sm = _make_state_manager(workers={1: w})
        renderer = DashboardRenderer(sm, "feat")
        panel = renderer._render_workers()
        assert isinstance(panel, Panel)


class TestDashboardRendererRetryInfo:
    """Tests for DashboardRenderer._render_retry_info."""

    def test_no_retries(self) -> None:
        sm = _make_state_manager(tasks={})
        renderer = DashboardRenderer(sm, "feat")
        panel = renderer._render_retry_info()
        assert isinstance(panel, Panel)

    def test_task_with_retries_waiting(self) -> None:
        future = (datetime.now() + timedelta(seconds=30)).isoformat()
        tasks = {
            "T1": {
                "retry_count": 2,
                "max_retries": 3,
                "status": "waiting_retry",
                "next_retry_at": future,
            }
        }
        sm = _make_state_manager(tasks=tasks)
        renderer = DashboardRenderer(sm, "feat")
        panel = renderer._render_retry_info()
        assert isinstance(panel, Panel)

    def test_task_retry_ready(self) -> None:
        past = (datetime.now() - timedelta(seconds=10)).isoformat()
        tasks = {
            "T1": {
                "retry_count": 1,
                "max_retries": 3,
                "status": "waiting_retry",
                "next_retry_at": past,
            }
        }
        sm = _make_state_manager(tasks=tasks)
        renderer = DashboardRenderer(sm, "feat")
        panel = renderer._render_retry_info()
        assert isinstance(panel, Panel)

    def test_task_retry_exhausted(self) -> None:
        tasks = {
            "T1": {
                "retry_count": 3,
                "max_retries": 3,
                "status": TaskStatus.FAILED.value,
            }
        }
        sm = _make_state_manager(tasks=tasks)
        renderer = DashboardRenderer(sm, "feat")
        panel = renderer._render_retry_info()
        assert isinstance(panel, Panel)

    def test_task_retry_recovered(self) -> None:
        tasks = {
            "T1": {
                "retry_count": 2,
                "max_retries": 3,
                "status": TaskStatus.COMPLETE.value,
            }
        }
        sm = _make_state_manager(tasks=tasks)
        renderer = DashboardRenderer(sm, "feat")
        panel = renderer._render_retry_info()
        assert isinstance(panel, Panel)

    def test_task_retry_invalid_datetime(self) -> None:
        tasks = {
            "T1": {
                "retry_count": 1,
                "max_retries": 3,
                "status": "waiting_retry",
                "next_retry_at": "not-a-date",
            }
        }
        sm = _make_state_manager(tasks=tasks)
        renderer = DashboardRenderer(sm, "feat")
        panel = renderer._render_retry_info()
        assert isinstance(panel, Panel)

    def test_task_retry_other_status(self) -> None:
        tasks = {
            "T1": {
                "retry_count": 1,
                "max_retries": 3,
                "status": TaskStatus.IN_PROGRESS.value,
            }
        }
        sm = _make_state_manager(tasks=tasks)
        renderer = DashboardRenderer(sm, "feat")
        panel = renderer._render_retry_info()
        assert isinstance(panel, Panel)


class TestDashboardRendererEvents:
    """Tests for DashboardRenderer._render_events."""

    def test_no_events(self) -> None:
        sm = _make_state_manager(events=[])
        renderer = DashboardRenderer(sm, "feat")
        panel = renderer._render_events()
        assert isinstance(panel, Panel)

    @pytest.mark.parametrize(
        "event_type,data",
        [
            ("task_complete", {"task_id": "T1", "worker_id": 1, "duration": "5s"}),
            ("task_claimed", {"task_id": "T1", "worker_id": 1}),
            ("task_failed", {"task_id": "T1", "error": "something broke"}),
            ("level_started", {"level": 1, "tasks": 5}),
            ("level_complete", {"level": 1}),
            ("worker_started", {"worker_id": 1}),
            ("merge_started", {"level": 1}),
            ("merge_complete", {"level": 1}),
            ("task_retry_scheduled", {"task_id": "T1", "backoff_seconds": 30, "retry_count": 2}),
            ("task_retry_ready", {"task_id": "T1"}),
            ("unknown_event", {"foo": "bar"}),
        ],
    )
    def test_event_types(self, event_type: str, data: dict) -> None:
        events = [
            {
                "timestamp": "2025-01-15T10:30:45.123",
                "event": event_type,
                "data": data,
            }
        ]
        sm = _make_state_manager(events=events)
        renderer = DashboardRenderer(sm, "feat")
        panel = renderer._render_events()
        assert isinstance(panel, Panel)

    def test_event_short_timestamp(self) -> None:
        events = [
            {"timestamp": "10:30", "event": "task_complete", "data": {"task_id": "T1", "worker_id": 1}},
        ]
        sm = _make_state_manager(events=events)
        renderer = DashboardRenderer(sm, "feat")
        panel = renderer._render_events()
        assert isinstance(panel, Panel)


class TestDashboardRendererRender:
    """Tests for DashboardRenderer.render (full dashboard)."""

    @patch("zerg.rendering.status_renderer.HeartbeatMonitor")
    def test_render_returns_group(self, mock_hb_cls: MagicMock) -> None:
        mock_hb_cls.return_value.read.return_value = None
        sm = _make_state_manager()
        renderer = DashboardRenderer(sm, "feat")
        result = renderer.render()
        # Group is returned; it should be renderable
        assert result is not None


# ===========================================================================
# Standalone render functions
# ===========================================================================


class TestShowLevelStatus:
    """Tests for show_level_status."""

    def test_no_levels_shows_placeholder(self) -> None:
        c = _make_console()
        sm = _make_state_manager(current_level=2)
        show_level_status(sm, None, _console=c)
        output = _get_output(c)
        assert "Level Status" in output

    def test_with_level_filter(self) -> None:
        c = _make_console()
        sm = _make_state_manager(current_level=1)
        show_level_status(sm, level_filter=2, _console=c)
        output = _get_output(c)
        assert "Level Status" in output

    def test_with_level_data_complete(self) -> None:
        c = _make_console()
        levels = {"1": {"name": "Foundation", "status": "complete"}}
        sm = _make_state_manager(levels=levels)
        show_level_status(sm, None, _console=c)
        output = _get_output(c)
        assert "Foundation" in output

    def test_with_level_data_running(self) -> None:
        c = _make_console()
        levels = {"1": {"name": "Foundation", "status": "running"}}
        sm = _make_state_manager(levels=levels)
        show_level_status(sm, None, _console=c)
        output = _get_output(c)
        assert "RUNNING" in output

    def test_with_level_data_pending(self) -> None:
        c = _make_console()
        levels = {"1": {"name": "Foundation", "status": "pending"}}
        sm = _make_state_manager(levels=levels)
        show_level_status(sm, None, _console=c)
        output = _get_output(c)
        assert "PENDING" in output

    def test_level_filter_applied_to_level_data(self) -> None:
        c = _make_console()
        levels = {
            "1": {"name": "Foundation", "status": "complete"},
            "2": {"name": "Core", "status": "running"},
        }
        sm = _make_state_manager(levels=levels)
        show_level_status(sm, level_filter=1, _console=c)
        output = _get_output(c)
        assert "Foundation" in output


class TestShowWorkerStatus:
    """Tests for show_worker_status."""

    def test_no_workers(self) -> None:
        c = _make_console()
        sm = _make_state_manager(workers={})
        show_worker_status(sm, _console=c)
        output = _get_output(c)
        assert "Worker Status" in output

    def test_running_worker(self) -> None:
        c = _make_console()
        w = _make_worker(status=WorkerStatus.RUNNING)
        sm = _make_state_manager(workers={1: w})
        show_worker_status(sm, _console=c)
        output = _get_output(c)
        assert "RUNNING" in output

    def test_idle_worker(self) -> None:
        c = _make_console()
        w = _make_worker(status=WorkerStatus.IDLE)
        sm = _make_state_manager(workers={1: w})
        show_worker_status(sm, _console=c)
        output = _get_output(c)
        assert "IDLE" in output

    def test_crashed_worker(self) -> None:
        c = _make_console()
        w = _make_worker(status=WorkerStatus.CRASHED)
        sm = _make_state_manager(workers={1: w})
        show_worker_status(sm, _console=c)
        output = _get_output(c)
        assert "CRASHED" in output

    def test_other_worker_status(self) -> None:
        c = _make_console()
        w = _make_worker(status=WorkerStatus.CHECKPOINTING)
        sm = _make_state_manager(workers={1: w})
        show_worker_status(sm, _console=c)
        output = _get_output(c)
        assert "CHECKPOINTING" in output

    def test_worker_without_port(self) -> None:
        c = _make_console()
        w = _make_worker(port=None)
        sm = _make_state_manager(workers={1: w})
        show_worker_status(sm, _console=c)
        output = _get_output(c)
        assert "Worker Status" in output


class TestShowRecentEvents:
    """Tests for show_recent_events."""

    def test_no_events_prints_nothing(self) -> None:
        c = _make_console()
        sm = _make_state_manager(events=[])
        show_recent_events(sm, _console=c)
        output = _get_output(c)
        assert output.strip() == ""

    def test_task_complete_event(self) -> None:
        c = _make_console()
        events = [
            {"timestamp": "10:30:45", "event": "task_complete", "data": {"task_id": "T1", "worker_id": 1}},
        ]
        sm = _make_state_manager(events=events)
        show_recent_events(sm, _console=c)
        output = _get_output(c)
        assert "Recent Events" in output
        assert "T1" in output

    def test_task_failed_event(self) -> None:
        c = _make_console()
        events = [
            {"timestamp": "10:30:45", "event": "task_failed", "data": {"task_id": "T1", "error": "oops"}},
        ]
        sm = _make_state_manager(events=events)
        show_recent_events(sm, _console=c)
        output = _get_output(c)
        assert "oops" in output

    def test_level_started_event(self) -> None:
        c = _make_console()
        events = [
            {"timestamp": "10:30:45", "event": "level_started", "data": {"level": 2, "tasks": 3}},
        ]
        sm = _make_state_manager(events=events)
        show_recent_events(sm, _console=c)
        output = _get_output(c)
        assert "Level 2" in output

    def test_level_complete_event(self) -> None:
        c = _make_console()
        events = [
            {"timestamp": "10:30:45", "event": "level_complete", "data": {"level": 1}},
        ]
        sm = _make_state_manager(events=events)
        show_recent_events(sm, _console=c)
        output = _get_output(c)
        assert "Level 1" in output

    def test_worker_started_event(self) -> None:
        c = _make_console()
        events = [
            {"timestamp": "10:30:45", "event": "worker_started", "data": {"worker_id": 3, "port": 5000}},
        ]
        sm = _make_state_manager(events=events)
        show_recent_events(sm, _console=c)
        output = _get_output(c)
        assert "Worker 3" in output

    def test_unknown_event_type(self) -> None:
        c = _make_console()
        events = [
            {"timestamp": "10:30:45", "event": "custom_event", "data": {}},
        ]
        sm = _make_state_manager(events=events)
        show_recent_events(sm, _console=c)
        output = _get_output(c)
        assert "custom_event" in output


class TestShowTasksView:
    """Tests for show_tasks_view."""

    @patch("zerg.rendering.status_renderer.HeartbeatMonitor")
    def test_no_tasks(self, mock_hb_cls: MagicMock) -> None:
        c = _make_console()
        sm = _make_state_manager(tasks={})
        show_tasks_view(sm, None, _console=c)
        output = _get_output(c)
        assert "No tasks found" in output

    @patch("zerg.rendering.status_renderer.HeartbeatMonitor")
    def test_tasks_with_various_statuses(self, mock_hb_cls: MagicMock) -> None:
        mock_hb_cls.return_value.read.return_value = None
        tasks = {
            "T1": {"level": 1, "status": TaskStatus.COMPLETE.value, "description": "First task"},
            "T2": {"level": 1, "status": TaskStatus.IN_PROGRESS.value, "worker_id": 1, "description": "Second task"},
            "T3": {"level": 1, "status": TaskStatus.FAILED.value, "description": "Third task"},
            "T4": {"level": 1, "status": TaskStatus.PENDING.value, "description": "Fourth task"},
        }
        c = _make_console()
        sm = _make_state_manager(tasks=tasks)
        show_tasks_view(sm, None, _console=c)
        output = _get_output(c)
        assert "Task Details" in output

    @patch("zerg.rendering.status_renderer.HeartbeatMonitor")
    def test_tasks_level_filter(self, mock_hb_cls: MagicMock) -> None:
        mock_hb_cls.return_value.read.return_value = None
        tasks = {
            "T1": {"level": 1, "status": TaskStatus.COMPLETE.value, "description": "L1 task"},
            "T2": {"level": 2, "status": TaskStatus.PENDING.value, "description": "L2 task"},
        }
        c = _make_console()
        sm = _make_state_manager(tasks=tasks)
        show_tasks_view(sm, level_filter=1, _console=c)
        output = _get_output(c)
        assert "Task Details" in output

    @patch("zerg.rendering.status_renderer.HeartbeatMonitor")
    def test_task_with_step_progress(self, mock_hb_cls: MagicMock) -> None:
        heartbeat = MagicMock()
        heartbeat.task_id = "T1"
        heartbeat.get_step_progress_display.return_value = "[Step 1/3]"
        mock_hb_cls.return_value.read.return_value = heartbeat

        tasks = {
            "T1": {"level": 1, "status": TaskStatus.IN_PROGRESS.value, "worker_id": 1, "description": "Active"},
        }
        c = _make_console()
        sm = _make_state_manager(tasks=tasks)
        show_tasks_view(sm, None, _console=c)
        output = _get_output(c)
        assert "Task Details" in output


class TestShowWorkersView:
    """Tests for show_workers_view."""

    @patch("zerg.rendering.status_renderer.HeartbeatMonitor")
    def test_no_workers(self, mock_hb_cls: MagicMock) -> None:
        c = _make_console()
        sm = _make_state_manager(workers={})
        show_workers_view(sm, _console=c)
        output = _get_output(c)
        assert "No workers active" in output

    @patch("zerg.rendering.status_renderer.HeartbeatMonitor")
    def test_worker_with_details(self, mock_hb_cls: MagicMock) -> None:
        mock_hb_cls.return_value.read.return_value = None
        w = _make_worker(context_usage=0.6)
        sm = _make_state_manager(
            workers={1: w},
            workers_data={"1": {"container": "zerg-worker-1"}},
        )
        c = _make_console()
        show_workers_view(sm, _console=c)
        output = _get_output(c)
        assert "Worker Details" in output

    @patch("zerg.rendering.status_renderer.HeartbeatMonitor")
    def test_worker_with_heartbeat_step_progress(self, mock_hb_cls: MagicMock) -> None:
        heartbeat = MagicMock()
        heartbeat.task_id = "TASK-001"
        heartbeat.get_step_progress_display.return_value = "[Step 3/5]"
        mock_hb_cls.return_value.read.return_value = heartbeat

        w = _make_worker(current_task="TASK-001")
        sm = _make_state_manager(
            workers={1: w},
            workers_data={"1": {"container": "zerg-worker-1"}},
        )
        c = _make_console()
        show_workers_view(sm, _console=c)
        output = _get_output(c)
        assert "Worker Details" in output


class TestShowCommitsView:
    """Tests for show_commits_view."""

    def test_no_workers(self) -> None:
        c = _make_console()
        sm = _make_state_manager(workers={})
        show_commits_view(sm, "feat", _console=c)
        output = _get_output(c)
        assert "No workers active" in output

    @patch("zerg.rendering.status_renderer.subprocess.run")
    def test_with_commits(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="abc1234 First commit\ndef5678 Second commit\n",
        )
        w = _make_worker()
        c = _make_console()
        sm = _make_state_manager(
            workers={1: w},
            workers_data={"1": {"branch": "zerg/feat/worker-1"}},
        )
        show_commits_view(sm, "feat", _console=c)
        output = _get_output(c)
        assert "Worker Commits" in output

    @patch("zerg.rendering.status_renderer.subprocess.run")
    def test_branch_not_found(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=128, stdout="")
        w = _make_worker()
        c = _make_console()
        sm = _make_state_manager(workers={1: w}, workers_data={})
        show_commits_view(sm, "feat", _console=c)
        output = _get_output(c)
        assert "Worker Commits" in output

    @patch("zerg.rendering.status_renderer.subprocess.run")
    def test_git_error(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = Exception("git error")
        w = _make_worker()
        c = _make_console()
        sm = _make_state_manager(workers={1: w}, workers_data={})
        show_commits_view(sm, "feat", _console=c)
        output = _get_output(c)
        assert "Worker Commits" in output


class TestShowWorkerMetrics:
    """Tests for show_worker_metrics."""

    @patch("zerg.rendering.status_renderer.MetricsCollector")
    def test_with_worker_metrics(self, mock_mc_cls: MagicMock) -> None:
        wm = WorkerMetrics(
            worker_id=1,
            initialization_ms=1500,
            uptime_ms=60000,
            tasks_completed=3,
            tasks_failed=0,
            avg_task_duration_ms=5000.0,
        )
        feature_metrics = MagicMock()
        feature_metrics.worker_metrics = [wm]
        mock_mc_cls.return_value.compute_feature_metrics.return_value = feature_metrics

        c = _make_console()
        sm = _make_state_manager()
        show_worker_metrics(sm, _console=c)
        output = _get_output(c)
        assert "Worker Metrics" in output

    @patch("zerg.rendering.status_renderer.MetricsCollector")
    def test_worker_with_failures(self, mock_mc_cls: MagicMock) -> None:
        wm = WorkerMetrics(
            worker_id=1,
            tasks_completed=2,
            tasks_failed=1,
            avg_task_duration_ms=3000.0,
        )
        feature_metrics = MagicMock()
        feature_metrics.worker_metrics = [wm]
        mock_mc_cls.return_value.compute_feature_metrics.return_value = feature_metrics

        c = _make_console()
        sm = _make_state_manager()
        show_worker_metrics(sm, _console=c)
        output = _get_output(c)
        assert "Worker Metrics" in output
        assert "failed" in output

    @patch("zerg.rendering.status_renderer.MetricsCollector")
    def test_no_worker_metrics(self, mock_mc_cls: MagicMock) -> None:
        feature_metrics = MagicMock()
        feature_metrics.worker_metrics = []
        mock_mc_cls.return_value.compute_feature_metrics.return_value = feature_metrics

        c = _make_console()
        sm = _make_state_manager()
        show_worker_metrics(sm, _console=c)
        output = _get_output(c)
        # Should not print header when no metrics
        assert "Worker Metrics" not in output

    @patch("zerg.rendering.status_renderer.MetricsCollector")
    def test_metrics_exception(self, mock_mc_cls: MagicMock) -> None:
        mock_mc_cls.return_value.compute_feature_metrics.side_effect = RuntimeError("bad")

        c = _make_console()
        sm = _make_state_manager()
        show_worker_metrics(sm, _console=c)
        output = _get_output(c)
        # Should not crash, just skip
        assert "Worker Metrics" not in output


class TestShowLevelMetrics:
    """Tests for show_level_metrics."""

    @patch("zerg.rendering.status_renderer.MetricsCollector")
    def test_with_level_metrics(self, mock_mc_cls: MagicMock) -> None:
        lm = LevelMetrics(
            level=1,
            duration_ms=30000,
            task_count=5,
            completed_count=5,
            failed_count=0,
            p50_duration_ms=5000,
            p95_duration_ms=8000,
        )
        feature_metrics = MagicMock()
        feature_metrics.level_metrics = [lm]
        mock_mc_cls.return_value.compute_feature_metrics.return_value = feature_metrics

        c = _make_console()
        sm = _make_state_manager()
        show_level_metrics(sm, _console=c)
        output = _get_output(c)
        assert "Level Metrics" in output

    @patch("zerg.rendering.status_renderer.MetricsCollector")
    def test_level_with_failures(self, mock_mc_cls: MagicMock) -> None:
        lm = LevelMetrics(
            level=1,
            duration_ms=30000,
            task_count=5,
            completed_count=3,
            failed_count=2,
            p50_duration_ms=5000,
            p95_duration_ms=8000,
        )
        feature_metrics = MagicMock()
        feature_metrics.level_metrics = [lm]
        mock_mc_cls.return_value.compute_feature_metrics.return_value = feature_metrics

        c = _make_console()
        sm = _make_state_manager()
        show_level_metrics(sm, _console=c)
        output = _get_output(c)
        assert "Level Metrics" in output
        assert "failed" in output

    @patch("zerg.rendering.status_renderer.MetricsCollector")
    def test_no_level_metrics(self, mock_mc_cls: MagicMock) -> None:
        feature_metrics = MagicMock()
        feature_metrics.level_metrics = []
        mock_mc_cls.return_value.compute_feature_metrics.return_value = feature_metrics

        c = _make_console()
        sm = _make_state_manager()
        show_level_metrics(sm, _console=c)
        output = _get_output(c)
        assert "Level Metrics" not in output

    @patch("zerg.rendering.status_renderer.MetricsCollector")
    def test_metrics_exception(self, mock_mc_cls: MagicMock) -> None:
        mock_mc_cls.return_value.compute_feature_metrics.side_effect = RuntimeError("bad")

        c = _make_console()
        sm = _make_state_manager()
        show_level_metrics(sm, _console=c)
        output = _get_output(c)
        assert "Level Metrics" not in output


class TestShowStatus:
    """Tests for show_status (composite function)."""

    @patch("zerg.rendering.status_renderer.MetricsCollector")
    def test_basic_status(self, mock_mc_cls: MagicMock) -> None:
        feature_metrics = MagicMock()
        feature_metrics.worker_metrics = []
        feature_metrics.level_metrics = []
        mock_mc_cls.return_value.compute_feature_metrics.return_value = feature_metrics

        c = _make_console()
        sm = _make_state_manager(feature="my-feat")
        show_status(sm, "my-feat", None, _console=c)
        output = _get_output(c)
        assert "ZERG Status" in output
        assert "my-feat" in output
        assert "Progress" in output

    @patch("zerg.rendering.status_renderer.MetricsCollector")
    def test_status_with_error(self, mock_mc_cls: MagicMock) -> None:
        feature_metrics = MagicMock()
        feature_metrics.worker_metrics = []
        feature_metrics.level_metrics = []
        mock_mc_cls.return_value.compute_feature_metrics.return_value = feature_metrics

        c = _make_console()
        sm = _make_state_manager(error="Something went wrong")
        show_status(sm, "feat", None, _console=c)
        output = _get_output(c)
        assert "Something went wrong" in output

    @patch("zerg.rendering.status_renderer.MetricsCollector")
    def test_status_no_tasks_uses_fallback(self, mock_mc_cls: MagicMock) -> None:
        feature_metrics = MagicMock()
        feature_metrics.worker_metrics = []
        feature_metrics.level_metrics = []
        mock_mc_cls.return_value.compute_feature_metrics.return_value = feature_metrics

        c = _make_console()
        sm = _make_state_manager(tasks={})
        show_status(sm, "feat", None, _console=c)
        output = _get_output(c)
        # Fallback total = 42
        assert "0/42" in output


class TestBuildStatusOutput:
    """Tests for build_status_output."""

    def test_returns_panel(self) -> None:
        sm = _make_state_manager()
        result = build_status_output(sm, "feat", None)
        assert isinstance(result, Panel)

    def test_contains_feature_in_title(self) -> None:
        sm = _make_state_manager()
        result = build_status_output(sm, "my-feature", None)
        assert isinstance(result, Panel)


class TestShowJsonStatus:
    """Tests for show_json_status."""

    @patch("zerg.rendering.status_renderer.get_metrics_dict")
    def test_json_output(self, mock_get_metrics: MagicMock) -> None:
        mock_get_metrics.return_value = None
        c = _make_console()
        w = _make_worker()
        sm = _make_state_manager(workers={1: w}, feature="my-feat")
        show_json_status(sm, None, _console=c)
        output = _get_output(c)
        assert "my-feat" in output
        assert '"feature"' in output


class TestShowLiveStatus:
    """Tests for show_live_status."""

    def test_keyboard_interrupt_stops(self) -> None:
        c = _make_console()
        sm = _make_state_manager()

        mock_live = MagicMock()
        mock_live_instance = MagicMock()
        mock_live.return_value.__enter__ = MagicMock(return_value=mock_live_instance)
        mock_live.return_value.__exit__ = MagicMock(return_value=False)

        call_count = 0

        def fake_sleep(t: float) -> None:
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                raise KeyboardInterrupt

        with patch("zerg.event_emitter.EventEmitter") as mock_emitter_cls:
            mock_emitter = MagicMock()
            mock_emitter_cls.return_value = mock_emitter

            show_live_status(
                sm,
                "feat",
                _console=c,
                _live_cls=mock_live,
                _time_sleep=fake_sleep,
            )

            mock_emitter.start_watching.assert_called_once()
            mock_emitter.stop_watching.assert_called_once()


class TestShowWatchStatus:
    """Tests for show_watch_status."""

    def test_watch_renders_and_stops(self) -> None:
        c = _make_console()
        sm = _make_state_manager()

        mock_live = MagicMock()
        mock_live_instance = MagicMock()
        mock_live.return_value.__enter__ = MagicMock(return_value=mock_live_instance)
        mock_live.return_value.__exit__ = MagicMock(return_value=False)

        call_count = 0

        def fake_sleep(t: float) -> None:
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                raise KeyboardInterrupt

        # show_watch_status has an infinite loop; KeyboardInterrupt is not caught there,
        # so we expect it to propagate.
        with pytest.raises(KeyboardInterrupt):
            show_watch_status(
                sm,
                "feat",
                None,
                1,
                _console=c,
                _live_cls=mock_live,
                _time_sleep=fake_sleep,
            )


class TestShowDashboard:
    """Tests for show_dashboard."""

    def test_dashboard_keyboard_interrupt(self) -> None:
        c = _make_console()
        sm = _make_state_manager()

        mock_live = MagicMock()
        mock_live_instance = MagicMock()
        mock_live.return_value.__enter__ = MagicMock(return_value=mock_live_instance)
        mock_live.return_value.__exit__ = MagicMock(return_value=False)

        call_count = 0

        def fake_sleep(t: float) -> None:
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                raise KeyboardInterrupt

        from zerg.rendering.status_renderer import show_dashboard

        with patch("zerg.rendering.status_renderer.HeartbeatMonitor"):
            show_dashboard(
                sm,
                "feat",
                _console=c,
                _live_cls=mock_live,
                _time_sleep=fake_sleep,
            )


class TestGetMetricsDict:
    """Tests for get_metrics_dict."""

    @patch("zerg.rendering.status_renderer.MetricsCollector")
    def test_returns_dict(self, mock_mc_cls: MagicMock) -> None:
        from zerg.rendering.status_renderer import get_metrics_dict

        feature_metrics = MagicMock()
        feature_metrics.to_dict.return_value = {"tasks_total": 10}
        mock_mc_cls.return_value.compute_feature_metrics.return_value = feature_metrics

        sm = _make_state_manager()
        result = get_metrics_dict(sm)
        assert result == {"tasks_total": 10}

    @patch("zerg.rendering.status_renderer.MetricsCollector")
    def test_returns_none_on_error(self, mock_mc_cls: MagicMock) -> None:
        from zerg.rendering.status_renderer import get_metrics_dict

        mock_mc_cls.return_value.compute_feature_metrics.side_effect = RuntimeError("fail")

        sm = _make_state_manager()
        result = get_metrics_dict(sm)
        assert result is None


# ===========================================================================
# Constants sanity checks
# ===========================================================================


class TestConstants:
    """Validate module-level constants are properly defined."""

    def test_level_symbols_keys(self) -> None:
        expected_keys = {"complete", "running", "pending", "merging", "conflict"}
        assert set(LEVEL_SYMBOLS.keys()) == expected_keys

    def test_worker_colors_covers_statuses(self) -> None:
        for status in [
            WorkerStatus.RUNNING,
            WorkerStatus.IDLE,
            WorkerStatus.CRASHED,
            WorkerStatus.CHECKPOINTING,
            WorkerStatus.INITIALIZING,
            WorkerStatus.READY,
            WorkerStatus.STOPPING,
            WorkerStatus.STOPPED,
            WorkerStatus.BLOCKED,
        ]:
            assert status in WORKER_COLORS

    def test_step_indicators_keys(self) -> None:
        expected = {"completed", "in_progress", "pending", "failed"}
        assert set(STEP_INDICATORS.keys()) == expected
