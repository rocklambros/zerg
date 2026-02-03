"""Tests for ZERG progress reporter module."""

import json
from pathlib import Path

from zerg.progress_reporter import ProgressReporter, TierProgress, WorkerProgress


class TestTierProgress:
    """Tests for TierProgress dataclass."""

    def test_creation(self) -> None:
        tp = TierProgress(tier=1, name="syntax", success=True)
        assert tp.tier == 1
        assert tp.name == "syntax"
        assert tp.success is True
        assert tp.retry == 0

    def test_to_dict(self) -> None:
        tp = TierProgress(tier=2, name="correctness", success=False, retry=1)
        d = tp.to_dict()
        assert d["tier"] == 2
        assert d["retry"] == 1


class TestWorkerProgress:
    """Tests for WorkerProgress dataclass."""

    def test_defaults(self) -> None:
        wp = WorkerProgress(worker_id=1)
        assert wp.tasks_completed == 0
        assert wp.tasks_total == 0
        assert wp.current_task is None
        assert wp.current_step == "idle"
        assert wp.tier_results == []

    def test_to_dict(self) -> None:
        wp = WorkerProgress(
            worker_id=1,
            tasks_completed=2,
            tasks_total=5,
            current_task="TASK-003",
            current_step="implementing",
            tier_results=[TierProgress(1, "syntax", True)],
        )
        d = wp.to_dict()
        assert d["worker_id"] == 1
        assert d["tasks_completed"] == 2
        assert len(d["tier_results"]) == 1

    def test_from_dict(self) -> None:
        data = {
            "worker_id": 2,
            "tasks_completed": 3,
            "tasks_total": 5,
            "current_task": "TASK-005",
            "current_step": "verifying",
            "tier_results": [{"tier": 1, "name": "syntax", "success": True, "retry": 0}],
        }
        wp = WorkerProgress.from_dict(data)
        assert wp.worker_id == 2
        assert wp.tasks_completed == 3
        assert len(wp.tier_results) == 1


class TestProgressReporter:
    """Tests for ProgressReporter."""

    def test_update(self, tmp_path: Path) -> None:
        reporter = ProgressReporter(worker_id=1, state_dir=tmp_path)
        reporter.update(
            current_task="TASK-001",
            current_step="implementing",
            tasks_total=5,
        )
        assert reporter.progress.current_task == "TASK-001"

        # File should exist
        path = tmp_path / "progress-1.json"
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["current_task"] == "TASK-001"

    def test_add_tier_result(self, tmp_path: Path) -> None:
        reporter = ProgressReporter(worker_id=1, state_dir=tmp_path)
        reporter.add_tier_result(1, "syntax", True)
        reporter.add_tier_result(2, "correctness", False, retry=1)

        assert len(reporter.progress.tier_results) == 2
        data = json.loads((tmp_path / "progress-1.json").read_text())
        assert len(data["tier_results"]) == 2

    def test_clear_tier_results(self, tmp_path: Path) -> None:
        reporter = ProgressReporter(worker_id=1, state_dir=tmp_path)
        reporter.add_tier_result(1, "syntax", True)
        reporter.clear_tier_results()
        assert len(reporter.progress.tier_results) == 0

    def test_cleanup(self, tmp_path: Path) -> None:
        reporter = ProgressReporter(worker_id=1, state_dir=tmp_path)
        reporter.update(current_task="T1")
        assert reporter.progress_path.exists()
        reporter.cleanup()
        assert not reporter.progress_path.exists()

    def test_read_static(self, tmp_path: Path) -> None:
        data = {
            "worker_id": 1,
            "tasks_completed": 2,
            "tasks_total": 5,
            "current_task": "T3",
            "current_step": "impl",
            "tier_results": [],
        }
        (tmp_path / "progress-1.json").write_text(json.dumps(data))

        wp = ProgressReporter.read(1, state_dir=tmp_path)
        assert wp is not None
        assert wp.tasks_completed == 2

    def test_read_nonexistent(self, tmp_path: Path) -> None:
        assert ProgressReporter.read(99, state_dir=tmp_path) is None

    def test_read_all_static(self, tmp_path: Path) -> None:
        for wid in [1, 2]:
            data = {
                "worker_id": wid,
                "tasks_completed": 0,
                "tasks_total": 5,
                "current_task": None,
                "current_step": "idle",
                "tier_results": [],
            }
            (tmp_path / f"progress-{wid}.json").write_text(json.dumps(data))

        all_progress = ProgressReporter.read_all(state_dir=tmp_path)
        assert len(all_progress) == 2
