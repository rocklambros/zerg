"""Tests for ZERG worker assignment module — thinned Phase 4/5."""

import json
from pathlib import Path

from zerg.assign import WorkerAssignment
from zerg.types import Task


class TestWorkerAssignment:
    def test_init_default(self) -> None:
        assert WorkerAssignment().worker_count == 5

    def test_assign_empty_tasks(self) -> None:
        result = WorkerAssignment(worker_count=2).assign([], "test-feature")
        assert result.feature == "test-feature" and len(result.assignments) == 0

    def test_assign_single_task(self) -> None:
        result = WorkerAssignment(worker_count=2).assign(
            [{"id": "TASK-001", "level": 1, "estimate_minutes": 15}], "test-feature"
        )
        assert len(result.assignments) == 1 and result.assignments[0].worker_id == 0

    def test_assign_multiple_tasks_balanced(self) -> None:
        tasks: list[Task] = [{"id": f"TASK-{i:03d}", "level": 1, "estimate_minutes": 15} for i in range(4)]
        result = WorkerAssignment(worker_count=2).assign(tasks, "test-feature")
        worker_counts = {}
        for a in result.assignments:
            worker_counts[a.worker_id] = worker_counts.get(a.worker_id, 0) + 1
        assert all(c == 2 for c in worker_counts.values())

    def test_assign_by_level(self) -> None:
        tasks: list[Task] = [
            {"id": "TASK-001", "level": 1, "estimate_minutes": 15},
            {"id": "TASK-002", "level": 1, "estimate_minutes": 15},
            {"id": "TASK-003", "level": 2, "estimate_minutes": 15},
        ]
        result = WorkerAssignment(worker_count=2).assign(tasks, "test-feature")
        assert len([a for a in result.assignments if a.level == 1]) == 2
        assert len([a for a in result.assignments if a.level == 2]) == 1

    def test_get_worker_tasks(self) -> None:
        assigner = WorkerAssignment(worker_count=2)
        assigner.assign(
            [
                {"id": "TASK-001", "level": 1, "estimate_minutes": 15},
                {"id": "TASK-002", "level": 1, "estimate_minutes": 15},
            ],
            "test-feature",
        )
        assert set(assigner.get_worker_tasks(0) + assigner.get_worker_tasks(1)) == {"TASK-001", "TASK-002"}

    def test_get_task_worker(self) -> None:
        assigner = WorkerAssignment(worker_count=2)
        assigner.assign([{"id": "TASK-001", "level": 1}], "test-feature")
        assert assigner.get_task_worker("TASK-001") == 0
        assert assigner.get_task_worker("NONEXISTENT") is None

    def test_get_workload_summary(self) -> None:
        assigner = WorkerAssignment(worker_count=2)
        assigner.assign(
            [
                {"id": "TASK-001", "level": 1, "estimate_minutes": 30},
                {"id": "TASK-002", "level": 1, "estimate_minutes": 15},
            ],
            "test-feature",
        )
        summary = assigner.get_workload_summary()
        assert 0 in summary and "task_count" in summary[0]


class TestRebalance:
    def test_rebalance_no_changes_needed(self) -> None:
        assigner = WorkerAssignment(worker_count=2)
        assigner.assign([{"id": "TASK-001", "level": 1}], "test-feature")
        assert len(assigner.rebalance(completed_tasks=set(), failed_tasks=set(), current_level=1)) == 0

    def test_rebalance_forces_reassignment(self) -> None:
        assigner = WorkerAssignment(worker_count=2)
        assigner._assignments["TASK-001"] = 0
        assigner._assignments["TASK-002"] = 0
        assigner._assignments["TASK-003"] = 0
        assigner._worker_tasks[0] = ["TASK-001", "TASK-002", "TASK-003"]
        assigner._worker_tasks[1] = []
        assigner._worker_minutes[0] = 45
        assigner._worker_minutes[1] = 0
        reassignments = assigner.rebalance(completed_tasks=set(), failed_tasks={"TASK-002"}, current_level=1)
        assert len(reassignments) == 1
        task_id, old_worker, new_worker = reassignments[0]
        assert task_id == "TASK-002" and old_worker == 0 and new_worker == 1


class TestSaveLoad:
    def test_save_to_file(self, tmp_path: Path) -> None:
        assigner = WorkerAssignment(worker_count=2)
        assigner.assign([{"id": "TASK-001", "level": 1}], "test-feature")
        output_file = tmp_path / "assignments.json"
        assigner.save_to_file(str(output_file), "test-feature")
        with open(output_file) as f:
            data = json.load(f)
        assert data["feature"] == "test-feature" and len(data["assignments"]) == 1

    def test_load_from_file(self, tmp_path: Path) -> None:
        data = {
            "feature": "test-feature",
            "worker_count": 3,
            "assignments": [
                {"task_id": "TASK-001", "worker_id": 0, "level": 1, "estimated_minutes": 15},
                {"task_id": "TASK-002", "worker_id": 1, "level": 1, "estimated_minutes": 20},
            ],
        }
        input_file = tmp_path / "assignments.json"
        with open(input_file, "w") as f:
            json.dump(data, f)
        assigner = WorkerAssignment.load_from_file(str(input_file))
        assert assigner.worker_count == 3 and assigner.get_task_worker("TASK-001") == 0


class TestBalanceByLevel:
    def test_balance_resets_per_level(self) -> None:
        assigner = WorkerAssignment(worker_count=2)
        tasks: list[Task] = [
            {"id": "L1-001", "level": 1, "estimate_minutes": 60},
            {"id": "L1-002", "level": 1, "estimate_minutes": 10},
            {"id": "L2-001", "level": 2, "estimate_minutes": 60},
            {"id": "L2-002", "level": 2, "estimate_minutes": 10},
        ]
        result = assigner.assign(tasks, "test", balance_by_level=True)
        assert len([a for a in result.assignments if a.level == 2]) == 2

    def test_assign_clears_previous_state(self) -> None:
        assigner = WorkerAssignment(worker_count=2)
        assigner.assign([{"id": "TASK-001", "level": 1}], "feature1")
        assigner.assign([{"id": "TASK-002", "level": 1}], "feature2")
        assert assigner.get_task_worker("TASK-001") is None
        assert assigner.get_task_worker("TASK-002") == 0
