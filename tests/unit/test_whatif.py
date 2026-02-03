"""Unit tests for ZERG what-if analysis engine."""

from __future__ import annotations

from typing import Any

import pytest

from zerg.whatif import WhatIfEngine, WhatIfReport


@pytest.fixture
def sample_task_data() -> dict[str, Any]:
    """A sample task graph for what-if tests."""
    return {
        "feature": "test-feature",
        "tasks": [
            {
                "id": "T1-001",
                "title": "Task A",
                "level": 1,
                "dependencies": [],
                "files": {"create": ["a.py"], "modify": [], "read": []},
                "verification": {"command": "true"},
                "estimate_minutes": 10,
            },
            {
                "id": "T1-002",
                "title": "Task B",
                "level": 1,
                "dependencies": [],
                "files": {"create": ["b.py"], "modify": [], "read": []},
                "verification": {"command": "true"},
                "estimate_minutes": 15,
            },
            {
                "id": "T2-001",
                "title": "Task C",
                "level": 2,
                "dependencies": ["T1-001", "T1-002"],
                "files": {"create": ["c.py"], "modify": [], "read": []},
                "verification": {"command": "true"},
                "estimate_minutes": 20,
            },
        ],
        "levels": {
            "1": {"name": "foundation", "tasks": ["T1-001", "T1-002"]},
            "2": {"name": "core", "tasks": ["T2-001"]},
        },
    }


class TestWhatIfEngine:
    """Tests for WhatIfEngine."""

    def test_compare_worker_counts(self, sample_task_data: dict) -> None:
        engine = WhatIfEngine(sample_task_data, feature="test")
        report = engine.compare_worker_counts(counts=[2, 3, 5])
        assert len(report.scenarios) == 3
        assert report.scenarios[0].workers == 2
        assert report.scenarios[1].workers == 3
        assert report.scenarios[2].workers == 5

    def test_compare_modes(self, sample_task_data: dict) -> None:
        engine = WhatIfEngine(sample_task_data, feature="test")
        report = engine.compare_modes(modes=["subprocess", "container"])
        assert len(report.scenarios) == 2
        assert report.scenarios[0].mode == "subprocess"
        assert report.scenarios[1].mode == "container"

    def test_container_overhead(self, sample_task_data: dict) -> None:
        engine = WhatIfEngine(sample_task_data, feature="test")
        report = engine.compare_modes(modes=["subprocess", "container"], workers=2)
        sub = next(s for s in report.scenarios if s.mode == "subprocess")
        con = next(s for s in report.scenarios if s.mode == "container")
        # Container should have >= subprocess wall time due to overhead
        assert con.estimated_wall_minutes >= sub.estimated_wall_minutes

    def test_compare_all(self, sample_task_data: dict) -> None:
        engine = WhatIfEngine(sample_task_data, feature="test")
        report = engine.compare_all(counts=[2, 3], modes=["subprocess", "container"])
        assert len(report.scenarios) == 4  # 2 counts * 2 modes

    def test_recommendation_provided(self, sample_task_data: dict) -> None:
        engine = WhatIfEngine(sample_task_data, feature="test")
        report = engine.compare_worker_counts(counts=[2, 5])
        assert report.recommendation != ""

    def test_scenario_result_fields(self, sample_task_data: dict) -> None:
        engine = WhatIfEngine(sample_task_data, feature="test")
        report = engine.compare_worker_counts(counts=[2])
        s = report.scenarios[0]
        assert s.total_sequential_minutes == 45  # 10+15+20
        assert s.estimated_wall_minutes > 0
        assert 0 <= s.efficiency <= 1.0
        assert s.max_worker_load >= s.min_worker_load

    def test_more_workers_less_wall_time(self, sample_task_data: dict) -> None:
        engine = WhatIfEngine(sample_task_data, feature="test")
        report = engine.compare_worker_counts(counts=[1, 5])
        one = next(s for s in report.scenarios if s.workers == 1)
        five = next(s for s in report.scenarios if s.workers == 5)
        assert five.estimated_wall_minutes <= one.estimated_wall_minutes

    def test_empty_task_graph(self) -> None:
        engine = WhatIfEngine({"feature": "empty", "tasks": []})
        report = engine.compare_worker_counts(counts=[3])
        assert len(report.scenarios) == 1
        assert report.scenarios[0].estimated_wall_minutes == 0

    def test_default_counts(self, sample_task_data: dict) -> None:
        engine = WhatIfEngine(sample_task_data, feature="test")
        report = engine.compare_worker_counts()
        assert len(report.scenarios) == 3  # default [3, 5, 7]


class TestWhatIfReport:
    """Tests for WhatIfReport dataclass."""

    def test_empty_report(self) -> None:
        report = WhatIfReport()
        assert report.scenarios == []
        assert report.recommendation == ""


class TestRender:
    """Tests for render output."""

    def test_render_does_not_crash(self, sample_task_data: dict, capsys: pytest.CaptureFixture[str]) -> None:
        engine = WhatIfEngine(sample_task_data, feature="test")
        report = engine.compare_worker_counts(counts=[2, 3])
        engine.render(report)
        captured = capsys.readouterr()
        assert "What-If Comparison" in captured.out
        assert "Recommendation" in captured.out
