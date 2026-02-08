"""Unit tests for zerg/rendering/shared.py."""

from __future__ import annotations

from dataclasses import dataclass, field

from rich.text import Text

from zerg.rendering.shared import (
    format_elapsed_compact,
    render_gantt_chart,
    render_progress_bar,
    render_progress_bar_str,
)


# ---------------------------------------------------------------------------
# Lightweight stand-in for LevelTimeline so we don't import dryrun internals.
# ---------------------------------------------------------------------------
@dataclass
class _FakeLevelTimeline:
    level: int
    task_count: int
    wall_minutes: int
    worker_loads: dict[int, int] = field(default_factory=dict)


# ── render_progress_bar ──────────────────────────────────────────────────


class TestRenderProgressBar:
    """Tests for the Rich Text progress bar helper."""

    def test_zero_percent(self):
        bar = render_progress_bar(0, width=10)
        assert isinstance(bar, Text)
        assert str(bar) == "\u2591" * 10

    def test_full_percent(self):
        bar = render_progress_bar(100, width=10)
        assert str(bar) == "\u2588" * 10

    def test_fifty_percent(self):
        bar = render_progress_bar(50, width=20)
        plain = str(bar)
        assert plain == "\u2588" * 10 + "\u2591" * 10

    def test_default_width(self):
        bar = render_progress_bar(25)
        plain = str(bar)
        assert len(plain) == 20
        assert plain.count("\u2588") == 5
        assert plain.count("\u2591") == 15


# ── render_progress_bar_str ──────────────────────────────────────────────


class TestRenderProgressBarStr:
    """Tests for the plain-string progress bar helper."""

    def test_zero_percent(self):
        result = render_progress_bar_str(0, width=10)
        assert result == "\u2591" * 10

    def test_full_percent(self):
        result = render_progress_bar_str(100, width=10)
        assert result == "\u2588" * 10

    def test_partial(self):
        result = render_progress_bar_str(50, width=20)
        assert result == "\u2588" * 10 + "\u2591" * 10

    def test_default_width(self):
        result = render_progress_bar_str(75)
        assert len(result) == 20


# ── render_gantt_chart ───────────────────────────────────────────────────


class TestRenderGanttChart:
    """Tests for the Gantt chart renderer."""

    def test_empty_per_level(self):
        result = render_gantt_chart({}, worker_count=3)
        assert "No timeline data" in str(result)

    def test_zero_total_wall(self):
        per_level = {
            1: _FakeLevelTimeline(level=1, task_count=2, wall_minutes=0),
        }
        result = render_gantt_chart(per_level, worker_count=2)
        assert "No timeline data" in str(result)

    def test_single_level_with_workers(self):
        per_level = {
            1: _FakeLevelTimeline(
                level=1,
                task_count=2,
                wall_minutes=10,
                worker_loads={0: 8, 1: 5},
            ),
        }
        result = render_gantt_chart(per_level, worker_count=2, chart_width=20)
        plain = str(result)
        # Should contain level label and worker labels
        assert "L1" in plain
        assert "W0" in plain
        assert "W1" in plain
        # Should contain load annotations
        assert "8m" in plain
        assert "5m" in plain

    def test_worker_with_zero_load(self):
        per_level = {
            1: _FakeLevelTimeline(
                level=1,
                task_count=1,
                wall_minutes=5,
                worker_loads={0: 5},
            ),
        }
        # Worker 1 has no load entry
        result = render_gantt_chart(per_level, worker_count=2, chart_width=20)
        plain = str(result)
        assert "W1" in plain
        # The middle-dot character for idle workers
        assert "\u00b7" in plain

    def test_multiple_levels(self):
        per_level = {
            1: _FakeLevelTimeline(level=1, task_count=1, wall_minutes=5, worker_loads={0: 5}),
            2: _FakeLevelTimeline(level=2, task_count=1, wall_minutes=10, worker_loads={0: 10}),
        }
        result = render_gantt_chart(per_level, worker_count=1, chart_width=30)
        plain = str(result)
        assert "L1" in plain
        assert "L2" in plain
        # Total wall time shown in header
        assert "15m" in plain


# ── format_elapsed_compact ───────────────────────────────────────────────


class TestFormatElapsedCompact:
    """Tests for the compact elapsed-time formatter."""

    def test_seconds_only(self):
        assert format_elapsed_compact(0) == "0s"
        assert format_elapsed_compact(30) == "30s"
        assert format_elapsed_compact(59) == "59s"

    def test_minutes_and_seconds(self):
        assert format_elapsed_compact(61) == "1m1s"
        assert format_elapsed_compact(90) == "1m30s"

    def test_exact_minutes(self):
        assert format_elapsed_compact(60) == "1m"
        assert format_elapsed_compact(120) == "2m"

    def test_hours_and_minutes(self):
        assert format_elapsed_compact(3660) == "1h1m"
        assert format_elapsed_compact(7200) == "2h"

    def test_exact_hours(self):
        assert format_elapsed_compact(3600) == "1h"
