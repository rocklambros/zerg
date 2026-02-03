"""Unit tests for ZERG risk scoring."""

from __future__ import annotations

from typing import Any

import pytest

from zerg.risk_scoring import RiskReport, RiskScorer, TaskRisk


@pytest.fixture
def simple_task_graph() -> dict[str, Any]:
    """A simple task graph for risk scoring tests."""
    return {
        "feature": "test",
        "tasks": [
            {
                "id": "T1-001",
                "title": "First Task",
                "level": 1,
                "dependencies": [],
                "files": {"create": ["a.py"], "modify": [], "read": []},
                "verification": {"command": "python -c 'print(1)'"},
                "estimate_minutes": 10,
            },
            {
                "id": "T1-002",
                "title": "Second Task",
                "level": 1,
                "dependencies": [],
                "files": {"create": ["b.py"], "modify": [], "read": []},
                "verification": {"command": "python -c 'print(2)'"},
                "estimate_minutes": 15,
            },
            {
                "id": "T2-001",
                "title": "Third Task",
                "level": 2,
                "dependencies": ["T1-001", "T1-002"],
                "files": {"create": ["c.py"], "modify": [], "read": []},
                "verification": {"command": "python -c 'print(3)'"},
                "estimate_minutes": 20,
            },
        ],
        "levels": {
            "1": {"name": "foundation", "tasks": ["T1-001", "T1-002"]},
            "2": {"name": "core", "tasks": ["T2-001"]},
        },
    }


class TestRiskScorer:
    """Tests for RiskScorer."""

    def test_basic_scoring(self, simple_task_graph: dict) -> None:
        scorer = RiskScorer(simple_task_graph, worker_count=2)
        report = scorer.score()
        assert isinstance(report, RiskReport)
        assert len(report.task_risks) == 3
        assert report.grade in ("A", "B", "C", "D")

    def test_low_risk_graph(self, simple_task_graph: dict) -> None:
        scorer = RiskScorer(simple_task_graph, worker_count=3)
        report = scorer.score()
        # Simple graph with verifications → low risk
        assert report.grade in ("A", "B")

    def test_no_verification_increases_risk(self) -> None:
        task_data = {
            "feature": "risky",
            "tasks": [
                {
                    "id": "T1",
                    "title": "No verify",
                    "level": 1,
                    "dependencies": [],
                    "files": {"create": ["a.py"], "modify": [], "read": []},
                    "estimate_minutes": 10,
                },
            ],
            "levels": {"1": {"name": "first", "tasks": ["T1"]}},
        }
        scorer = RiskScorer(task_data, worker_count=1)
        report = scorer.score()
        t1_risk = next(tr for tr in report.task_risks if tr.task_id == "T1")
        assert t1_risk.score >= 0.25
        assert any("verification" in f.lower() for f in t1_risk.factors)

    def test_high_file_count_increases_risk(self) -> None:
        task_data = {
            "feature": "many-files",
            "tasks": [
                {
                    "id": "T1",
                    "title": "Many files",
                    "level": 1,
                    "dependencies": [],
                    "files": {
                        "create": ["a.py", "b.py", "c.py"],
                        "modify": ["d.py", "e.py", "f.py"],
                        "read": [],
                    },
                    "verification": {"command": "true"},
                    "estimate_minutes": 10,
                },
            ],
            "levels": {"1": {"name": "first", "tasks": ["T1"]}},
        }
        scorer = RiskScorer(task_data, worker_count=1)
        report = scorer.score()
        t1_risk = next(tr for tr in report.task_risks if tr.task_id == "T1")
        assert t1_risk.score > 0
        assert any("file count" in f.lower() for f in t1_risk.factors)

    def test_deep_dependencies_increase_risk(self) -> None:
        task_data = {
            "feature": "deep",
            "tasks": [
                {
                    "id": "T1",
                    "title": "L1",
                    "level": 1,
                    "dependencies": [],
                    "files": {"create": ["a.py"], "modify": [], "read": []},
                    "verification": {"command": "true"},
                    "estimate_minutes": 5,
                },
                {
                    "id": "T2",
                    "title": "L2",
                    "level": 2,
                    "dependencies": ["T1"],
                    "files": {"create": ["b.py"], "modify": [], "read": []},
                    "verification": {"command": "true"},
                    "estimate_minutes": 5,
                },
                {
                    "id": "T3",
                    "title": "L3",
                    "level": 3,
                    "dependencies": ["T2"],
                    "files": {"create": ["c.py"], "modify": [], "read": []},
                    "verification": {"command": "true"},
                    "estimate_minutes": 5,
                },
                {
                    "id": "T4",
                    "title": "L4",
                    "level": 4,
                    "dependencies": ["T3"],
                    "files": {"create": ["d.py"], "modify": [], "read": []},
                    "verification": {"command": "true"},
                    "estimate_minutes": 5,
                },
                {
                    "id": "T5",
                    "title": "L5",
                    "level": 5,
                    "dependencies": ["T4"],
                    "files": {"create": ["e.py"], "modify": [], "read": []},
                    "verification": {"command": "true"},
                    "estimate_minutes": 5,
                },
            ],
            "levels": {
                "1": {"name": "L1", "tasks": ["T1"]},
                "2": {"name": "L2", "tasks": ["T2"]},
                "3": {"name": "L3", "tasks": ["T3"]},
                "4": {"name": "L4", "tasks": ["T4"]},
                "5": {"name": "L5", "tasks": ["T5"]},
            },
        }
        scorer = RiskScorer(task_data, worker_count=1)
        report = scorer.score()
        # T5 has dep depth of 4 (T5→T4→T3→T2→T1), which exceeds threshold of 3
        t5_risk = next(tr for tr in report.task_risks if tr.task_id == "T5")
        assert any("dependency" in f.lower() for f in t5_risk.factors)

    def test_critical_path_found(self, simple_task_graph: dict) -> None:
        scorer = RiskScorer(simple_task_graph, worker_count=2)
        report = scorer.score()
        assert len(report.critical_path) > 0
        # Critical path should start from a root task
        assert report.critical_path[0] in ("T1-001", "T1-002")

    def test_critical_path_tasks_marked(self, simple_task_graph: dict) -> None:
        scorer = RiskScorer(simple_task_graph, worker_count=2)
        report = scorer.score()
        cp_tasks = [tr for tr in report.task_risks if tr.on_critical_path]
        assert len(cp_tasks) > 0

    def test_empty_task_graph(self) -> None:
        scorer = RiskScorer({"feature": "empty", "tasks": []}, worker_count=1)
        report = scorer.score()
        assert report.overall_score == 0.0
        assert report.grade == "A"

    def test_risk_factors_cross_level_modification(self) -> None:
        task_data = {
            "feature": "cross-level",
            "tasks": [
                {
                    "id": "T1",
                    "title": "L1",
                    "level": 1,
                    "dependencies": [],
                    "files": {"create": [], "modify": ["shared.py"], "read": []},
                    "verification": {"command": "true"},
                    "estimate_minutes": 5,
                },
                {
                    "id": "T2",
                    "title": "L2",
                    "level": 2,
                    "dependencies": ["T1"],
                    "files": {"create": [], "modify": ["shared.py"], "read": []},
                    "verification": {"command": "true"},
                    "estimate_minutes": 5,
                },
            ],
            "levels": {
                "1": {"name": "L1", "tasks": ["T1"]},
                "2": {"name": "L2", "tasks": ["T2"]},
            },
        }
        scorer = RiskScorer(task_data, worker_count=1)
        report = scorer.score()
        assert any("modified in both" in f.lower() or "shared.py" in f for f in report.risk_factors)


class TestRiskReport:
    """Tests for RiskReport dataclass."""

    def test_high_risk_tasks(self) -> None:
        report = RiskReport(
            task_risks=[
                TaskRisk(task_id="T1", score=0.3),
                TaskRisk(task_id="T2", score=0.8),
                TaskRisk(task_id="T3", score=0.9),
            ]
        )
        high = report.high_risk_tasks
        assert len(high) == 2
        assert all(t.score >= 0.7 for t in high)

    def test_grade_computation(self) -> None:
        assert RiskScorer._compute_grade(0.1) == "A"
        assert RiskScorer._compute_grade(0.3) == "B"
        assert RiskScorer._compute_grade(0.6) == "C"
        assert RiskScorer._compute_grade(0.9) == "D"
