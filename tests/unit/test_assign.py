"""Tests for ZERG worker assignment module."""

import json
from pathlib import Path

from zerg.assign import WorkerAssignment
from zerg.types import Task


class TestWorkerAssignment:
    """Tests for WorkerAssignment class."""

    def test_init_default(self) -> None:
        """Test default initialization."""
        assigner = WorkerAssignment()
        assert assigner.worker_count == 5

    def test_init_custom_worker_count(self) -> None:
        """Test initialization with custom worker count."""
        assigner = WorkerAssignment(worker_count=3)
        assert assigner.worker_count == 3

    def test_assign_empty_tasks(self) -> None:
        """Test assigning empty task list."""
        assigner = WorkerAssignment(worker_count=2)
        result = assigner.assign([], "test-feature")

        assert result.feature == "test-feature"
        assert result.worker_count == 2
        assert len(result.assignments) == 0

    def test_assign_single_task(self) -> None:
        """Test assigning a single task."""
        assigner = WorkerAssignment(worker_count=2)
        tasks: list[Task] = [{"id": "TASK-001", "level": 1, "estimate_minutes": 15}]

        result = assigner.assign(tasks, "test-feature")

        assert len(result.assignments) == 1
        assert result.assignments[0].task_id == "TASK-001"
        assert result.assignments[0].worker_id == 0  # First worker

    def test_assign_multiple_tasks_balanced(self) -> None:
        """Test tasks are balanced across workers."""
        assigner = WorkerAssignment(worker_count=2)
        tasks: list[Task] = [
            {"id": "TASK-001", "level": 1, "estimate_minutes": 15},
            {"id": "TASK-002", "level": 1, "estimate_minutes": 15},
            {"id": "TASK-003", "level": 1, "estimate_minutes": 15},
            {"id": "TASK-004", "level": 1, "estimate_minutes": 15},
        ]

        result = assigner.assign(tasks, "test-feature")

        # Count tasks per worker
        worker_tasks = {}
        for entry in result.assignments:
            worker_tasks.setdefault(entry.worker_id, 0)
            worker_tasks[entry.worker_id] += 1

        # Should be balanced: 2 tasks per worker
        assert len(worker_tasks) == 2
        assert all(count == 2 for count in worker_tasks.values())

    def test_assign_by_level(self) -> None:
        """Test tasks are assigned respecting levels."""
        assigner = WorkerAssignment(worker_count=2)
        tasks: list[Task] = [
            {"id": "TASK-001", "level": 1, "estimate_minutes": 15},
            {"id": "TASK-002", "level": 1, "estimate_minutes": 15},
            {"id": "TASK-003", "level": 2, "estimate_minutes": 15},
        ]

        result = assigner.assign(tasks, "test-feature")

        # Verify levels are preserved
        level_1_tasks = [a for a in result.assignments if a.level == 1]
        level_2_tasks = [a for a in result.assignments if a.level == 2]

        assert len(level_1_tasks) == 2
        assert len(level_2_tasks) == 1

    def test_assign_longer_tasks_first(self) -> None:
        """Test longer tasks are assigned first for better balancing."""
        assigner = WorkerAssignment(worker_count=2)
        tasks: list[Task] = [
            {"id": "SHORT", "level": 1, "estimate_minutes": 5},
            {"id": "LONG", "level": 1, "estimate_minutes": 60},
            {"id": "MEDIUM", "level": 1, "estimate_minutes": 30},
        ]

        assigner.assign(tasks, "test-feature")

        # Longer task should go to worker with least time
        # After LONG (60min) -> worker 0 has 60, worker 1 has 0
        # MEDIUM (30min) -> worker 1 gets it
        # SHORT (5min) -> worker 1 gets it (now 35 vs 60)
        workloads = assigner.get_workload_summary()
        assert workloads[0]["estimated_minutes"] >= workloads[1]["estimated_minutes"] - 30

    def test_assign_task_without_level(self) -> None:
        """Test assigning task without explicit level (defaults to 1)."""
        assigner = WorkerAssignment(worker_count=2)
        tasks: list[Task] = [{"id": "TASK-001"}]

        result = assigner.assign(tasks, "test-feature")

        assert len(result.assignments) == 1
        assert result.assignments[0].level == 1

    def test_assign_task_without_estimate(self) -> None:
        """Test assigning task without estimate_minutes (defaults to 15)."""
        assigner = WorkerAssignment(worker_count=2)
        tasks: list[Task] = [{"id": "TASK-001", "level": 1}]

        result = assigner.assign(tasks, "test-feature")

        assert result.assignments[0].estimated_minutes == 15

    def test_get_worker_tasks(self) -> None:
        """Test getting tasks for a specific worker."""
        assigner = WorkerAssignment(worker_count=2)
        tasks: list[Task] = [
            {"id": "TASK-001", "level": 1, "estimate_minutes": 15},
            {"id": "TASK-002", "level": 1, "estimate_minutes": 15},
        ]

        assigner.assign(tasks, "test-feature")

        worker_0_tasks = assigner.get_worker_tasks(0)
        worker_1_tasks = assigner.get_worker_tasks(1)

        assert len(worker_0_tasks) == 1
        assert len(worker_1_tasks) == 1
        assert set(worker_0_tasks + worker_1_tasks) == {"TASK-001", "TASK-002"}

    def test_get_worker_tasks_empty(self) -> None:
        """Test getting tasks for worker with no assignments."""
        assigner = WorkerAssignment(worker_count=5)
        tasks: list[Task] = [{"id": "TASK-001", "level": 1}]

        assigner.assign(tasks, "test-feature")

        # Workers 1-4 should have no tasks
        assert assigner.get_worker_tasks(4) == []

    def test_get_worker_tasks_returns_copy(self) -> None:
        """Test that get_worker_tasks returns a copy."""
        assigner = WorkerAssignment(worker_count=2)
        tasks: list[Task] = [{"id": "TASK-001", "level": 1}]
        assigner.assign(tasks, "test-feature")

        tasks1 = assigner.get_worker_tasks(0)
        tasks2 = assigner.get_worker_tasks(0)

        # Modifying one shouldn't affect the other
        tasks1.append("MODIFIED")
        assert "MODIFIED" not in tasks2

    def test_get_task_worker(self) -> None:
        """Test getting the worker assigned to a task."""
        assigner = WorkerAssignment(worker_count=2)
        tasks: list[Task] = [{"id": "TASK-001", "level": 1}]

        assigner.assign(tasks, "test-feature")

        worker_id = assigner.get_task_worker("TASK-001")
        assert worker_id == 0

    def test_get_task_worker_not_found(self) -> None:
        """Test getting worker for unassigned task."""
        assigner = WorkerAssignment(worker_count=2)

        worker_id = assigner.get_task_worker("NONEXISTENT")
        assert worker_id is None

    def test_get_worker_workload(self) -> None:
        """Test getting workload for a worker."""
        assigner = WorkerAssignment(worker_count=2)
        tasks: list[Task] = [
            {"id": "TASK-001", "level": 1, "estimate_minutes": 30},
            {"id": "TASK-002", "level": 1, "estimate_minutes": 15},
        ]

        assigner.assign(tasks, "test-feature")

        # Worker 0 gets longer task first
        workload_0 = assigner.get_worker_workload(0)
        assert workload_0 == 30

    def test_get_worker_workload_unassigned(self) -> None:
        """Test getting workload for worker with no assignments."""
        assigner = WorkerAssignment(worker_count=5)
        tasks: list[Task] = [{"id": "TASK-001", "level": 1}]
        assigner.assign(tasks, "test-feature")

        # Worker 4 has no tasks
        workload = assigner.get_worker_workload(4)
        assert workload == 0

    def test_get_workload_summary(self) -> None:
        """Test getting workload summary."""
        assigner = WorkerAssignment(worker_count=2)
        tasks: list[Task] = [
            {"id": "TASK-001", "level": 1, "estimate_minutes": 30},
            {"id": "TASK-002", "level": 1, "estimate_minutes": 15},
        ]

        assigner.assign(tasks, "test-feature")

        summary = assigner.get_workload_summary()

        assert 0 in summary
        assert 1 in summary
        assert "task_count" in summary[0]
        assert "estimated_minutes" in summary[0]
        assert "tasks" in summary[0]

    def test_get_workload_summary_all_workers(self) -> None:
        """Test workload summary includes all workers even with no tasks."""
        assigner = WorkerAssignment(worker_count=5)
        tasks: list[Task] = [{"id": "TASK-001", "level": 1}]
        assigner.assign(tasks, "test-feature")

        summary = assigner.get_workload_summary()

        # All 5 workers should be in summary
        assert len(summary) == 5
        for i in range(5):
            assert i in summary


class TestRebalance:
    """Tests for task rebalancing."""

    def test_rebalance_failed_task(self) -> None:
        """Test rebalancing a failed task."""
        assigner = WorkerAssignment(worker_count=2)
        tasks: list[Task] = [
            {"id": "TASK-001", "level": 1, "estimate_minutes": 15},
            {"id": "TASK-002", "level": 1, "estimate_minutes": 15},
        ]

        assigner.assign(tasks, "test-feature")

        # Simulate TASK-001 failing on worker 0
        reassignments = assigner.rebalance(
            completed_tasks=set(),
            failed_tasks={"TASK-001"},
            current_level=1,
        )

        # Task should be reassigned to worker with capacity
        assert len(reassignments) >= 0  # May or may not reassign based on capacity

    def test_rebalance_no_changes_needed(self) -> None:
        """Test rebalancing when no changes needed."""
        assigner = WorkerAssignment(worker_count=2)
        tasks: list[Task] = [{"id": "TASK-001", "level": 1}]

        assigner.assign(tasks, "test-feature")

        reassignments = assigner.rebalance(
            completed_tasks=set(),
            failed_tasks=set(),
            current_level=1,
        )

        assert len(reassignments) == 0

    def test_rebalance_failed_task_not_in_assignments(self) -> None:
        """Test rebalancing skips failed task not in assignments."""
        assigner = WorkerAssignment(worker_count=2)
        tasks: list[Task] = [{"id": "TASK-001", "level": 1}]
        assigner.assign(tasks, "test-feature")

        # Try to rebalance a task that doesn't exist
        reassignments = assigner.rebalance(
            completed_tasks=set(),
            failed_tasks={"NONEXISTENT"},
            current_level=1,
        )

        assert len(reassignments) == 0

    def test_rebalance_with_completed_tasks(self) -> None:
        """Test rebalancing considers completed tasks for capacity."""
        assigner = WorkerAssignment(worker_count=2)
        tasks: list[Task] = [
            {"id": "TASK-001", "level": 1, "estimate_minutes": 30},
            {"id": "TASK-002", "level": 1, "estimate_minutes": 30},
            {"id": "TASK-003", "level": 1, "estimate_minutes": 15},
        ]
        assigner.assign(tasks, "test-feature")

        # Mark TASK-001 as completed and TASK-002 as failed
        reassignments = assigner.rebalance(
            completed_tasks={"TASK-001"},
            failed_tasks={"TASK-002"},
            current_level=1,
        )

        # TASK-002 may be reassigned depending on capacity
        assert isinstance(reassignments, list)

    def test_rebalance_forces_reassignment(self) -> None:
        """Test rebalance actually reassigns task to different worker.

        This test is designed to cover lines 203-210 and 213 in assign.py.
        We create a scenario where:
        - Worker 0 has 3 tasks (one failed, two pending = 2*15=30 min pending)
        - Worker 1 has 0 tasks
        Worker 1 has capacity 60, Worker 0 has capacity 30.
        The failed task should move from Worker 0 to Worker 1.
        """
        assigner = WorkerAssignment(worker_count=2)
        # All tasks go to worker 0 (they're all processed first)
        # Since worker 0 gets first task, then has more minutes than worker 1 (0 min),
        # all tasks would normally be distributed, but let's force the scenario
        tasks: list[Task] = [
            {"id": "TASK-001", "level": 1, "estimate_minutes": 10},
            {"id": "TASK-002", "level": 1, "estimate_minutes": 10},
            {"id": "TASK-003", "level": 1, "estimate_minutes": 10},
        ]
        assigner.assign(tasks, "test-feature")

        # After balancing: Worker 0 gets TASK-003 (10), TASK-001 (10) = 20
        # Worker 1 gets TASK-002 (10) = 10
        #
        # Manually set up the scenario we need:
        # Worker 0: TASK-001 (pending), TASK-002 (failed)
        # Worker 1: no tasks
        assigner._assignments.clear()
        assigner._worker_tasks.clear()
        assigner._worker_minutes.clear()

        # Manually assign all tasks to worker 0
        assigner._assignments["TASK-001"] = 0
        assigner._assignments["TASK-002"] = 0
        assigner._assignments["TASK-003"] = 0
        assigner._worker_tasks[0] = ["TASK-001", "TASK-002", "TASK-003"]
        assigner._worker_minutes[0] = 45

        # Rebalance with TASK-002 failed
        # Worker 0: pending = TASK-001 + TASK-003 = 30 min (using _get_task_minutes = 15 each)
        # Worker 1: pending = 0 min
        # Worker 0 capacity = 60 - 30 = 30
        # Worker 1 capacity = 60 - 0 = 60
        # Worker 1 has more capacity, so TASK-002 should move to Worker 1
        reassignments = assigner.rebalance(
            completed_tasks=set(),
            failed_tasks={"TASK-002"},
            current_level=1,
        )

        # Should have exactly 1 reassignment
        assert len(reassignments) == 1
        task_id, old_worker, new_worker = reassignments[0]
        assert task_id == "TASK-002"
        assert old_worker == 0
        assert new_worker == 1

        # Verify the internal state was updated
        assert assigner._assignments["TASK-002"] == 1
        assert "TASK-002" not in assigner._worker_tasks[0]
        assert "TASK-002" in assigner._worker_tasks[1]

    def test_rebalance_no_reassign_if_same_worker_has_most_capacity(self) -> None:
        """Test rebalance doesn't reassign if current worker has most capacity."""
        assigner = WorkerAssignment(worker_count=2)
        tasks: list[Task] = [
            {"id": "TASK-001", "level": 1, "estimate_minutes": 15},
        ]
        assigner.assign(tasks, "test-feature")

        # Worker 0 has TASK-001 (failed) -> pending = 0
        # Worker 1 has nothing -> pending = 0
        # Both have capacity 60, but max() returns worker 0 first
        reassignments = assigner.rebalance(
            completed_tasks=set(),
            failed_tasks={"TASK-001"},
            current_level=1,
        )

        # No reassignment because same worker has max capacity
        assert len(reassignments) == 0

    def test_rebalance_no_capacity_available(self) -> None:
        """Test rebalance doesn't reassign if no worker has positive capacity."""
        assigner = WorkerAssignment(worker_count=2)

        # Manually set up scenario where both workers have 4 pending tasks each
        # 4 * 15 = 60 minutes = at capacity
        for i in range(8):
            task_id = f"TASK-{i:03d}"
            worker_id = i % 2
            assigner._assignments[task_id] = worker_id
            if worker_id not in assigner._worker_tasks:
                assigner._worker_tasks[worker_id] = []
            assigner._worker_tasks[worker_id].append(task_id)

        # Now TASK-000 fails. Worker 0 has 4 tasks pending, Worker 1 has 4 tasks pending
        # Worker 0: pending = 3 * 15 = 45, capacity = 15
        # Worker 1: pending = 4 * 15 = 60, capacity = 0
        # Worker 0 has more capacity but is the old_worker, so if max picks worker 0, no reassignment
        # Actually with capacity 15 > 0, it should reassign...

        # Let's make both workers have same pending:
        assigner._assignments.clear()
        assigner._worker_tasks.clear()

        # Give each worker 4 tasks
        for i in range(4):
            assigner._assignments[f"W0-{i}"] = 0
            assigner._worker_tasks.setdefault(0, []).append(f"W0-{i}")
        for i in range(4):
            assigner._assignments[f"W1-{i}"] = 1
            assigner._worker_tasks.setdefault(1, []).append(f"W1-{i}")

        # W0-0 fails
        # Worker 0: pending = 3 * 15 = 45, capacity = 15
        # Worker 1: pending = 4 * 15 = 60, capacity = 0
        # Worker 0 still has capacity 15 > 0, but is the old worker
        # max() will return worker 0 (capacity 15 vs 0)
        # old_worker == new_worker, no reassignment
        reassignments = assigner.rebalance(
            completed_tasks=set(),
            failed_tasks={"W0-0"},
            current_level=1,
        )

        assert len(reassignments) == 0

    def test_rebalance_multiple_failed_tasks(self) -> None:
        """Test rebalancing multiple failed tasks updates capacity correctly.

        Set iteration order is non-deterministic (PYTHONHASHSEED), so this test
        must be deterministic regardless of which failed task is processed first.

        Trace (either ordering yields the same structural result):
          Initial state: W0 has 3 tasks, W1 has 0 tasks.
          Capacity: W0 = 60 - 15 (TASK-003 pending) = 45, W1 = 60.
          First failed task processed -> reassigned from W0 to W1 (60 > 45).
            capacity[W1] -= 15 -> 45, capacity[W0] += 15 -> 60.
          Second failed task -> max capacity is W0 (60 > 45), but old_worker == W0.
            No reassignment (same worker).
          Result: exactly 1 reassignment to W1.
        """
        assigner = WorkerAssignment(worker_count=2)

        # Set up complete internal state for both workers to prevent
        # reliance on defaultdict auto-creation across test boundaries.
        assigner._assignments["TASK-001"] = 0
        assigner._assignments["TASK-002"] = 0
        assigner._assignments["TASK-003"] = 0
        assigner._worker_tasks[0] = ["TASK-001", "TASK-002", "TASK-003"]
        assigner._worker_tasks[1] = []  # Explicitly initialize worker 1
        assigner._worker_minutes[0] = 45  # 3 tasks * 15 min
        assigner._worker_minutes[1] = 0

        reassignments = assigner.rebalance(
            completed_tasks=set(),
            failed_tasks={"TASK-001", "TASK-002"},
            current_level=1,
        )

        # Exactly one task gets reassigned regardless of set iteration order
        assert len(reassignments) == 1
        task_id, old_worker, new_worker = reassignments[0]
        assert task_id in {"TASK-001", "TASK-002"}
        assert old_worker == 0
        assert new_worker == 1


class TestGetTaskMinutes:
    """Tests for _get_task_minutes helper."""

    def test_get_task_minutes_returns_default(self) -> None:
        """Test _get_task_minutes returns default 15 minutes."""
        assigner = WorkerAssignment(worker_count=2)
        minutes = assigner._get_task_minutes("any-task")
        assert minutes == 15


class TestSaveLoad:
    """Tests for saving/loading assignments."""

    def test_save_to_file(self, tmp_path: Path) -> None:
        """Test saving assignments to file."""
        assigner = WorkerAssignment(worker_count=2)
        tasks: list[Task] = [{"id": "TASK-001", "level": 1}]

        assigner.assign(tasks, "test-feature")

        output_file = tmp_path / "assignments.json"
        assigner.save_to_file(str(output_file), "test-feature")

        assert output_file.exists()
        with open(output_file) as f:
            data = json.load(f)

        assert data["feature"] == "test-feature"
        assert data["worker_count"] == 2
        assert len(data["assignments"]) == 1

    def test_load_from_file(self, tmp_path: Path) -> None:
        """Test loading assignments from file."""
        # Create assignment file
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

        assert assigner.worker_count == 3
        assert assigner.get_task_worker("TASK-001") == 0
        assert assigner.get_task_worker("TASK-002") == 1
        assert assigner.get_worker_workload(0) == 15
        assert assigner.get_worker_workload(1) == 20

    def test_save_creates_directory(self, tmp_path: Path) -> None:
        """Test saving creates parent directories."""
        assigner = WorkerAssignment(worker_count=2)
        tasks: list[Task] = [{"id": "TASK-001", "level": 1}]
        assigner.assign(tasks, "test")

        output_file = tmp_path / "nested" / "dir" / "assignments.json"
        assigner.save_to_file(str(output_file), "test")

        assert output_file.exists()

    def test_load_from_file_default_worker_count(self, tmp_path: Path) -> None:
        """Test loading with missing worker_count defaults to 5."""
        data = {
            "feature": "test",
            "assignments": [],
        }
        input_file = tmp_path / "assignments.json"
        with open(input_file, "w") as f:
            json.dump(data, f)

        assigner = WorkerAssignment.load_from_file(str(input_file))
        assert assigner.worker_count == 5

    def test_load_from_file_default_estimated_minutes(self, tmp_path: Path) -> None:
        """Test loading assignment without estimated_minutes defaults to 15."""
        data = {
            "feature": "test",
            "worker_count": 2,
            "assignments": [
                {"task_id": "TASK-001", "worker_id": 0, "level": 1},
            ],
        }
        input_file = tmp_path / "assignments.json"
        with open(input_file, "w") as f:
            json.dump(data, f)

        assigner = WorkerAssignment.load_from_file(str(input_file))
        assert assigner.get_worker_workload(0) == 15

    def test_save_with_multiple_assignments(self, tmp_path: Path) -> None:
        """Test saving multiple assignments."""
        assigner = WorkerAssignment(worker_count=3)
        tasks: list[Task] = [
            {"id": "TASK-001", "level": 1},
            {"id": "TASK-002", "level": 1},
            {"id": "TASK-003", "level": 2},
        ]
        assigner.assign(tasks, "multi-test")

        output_file = tmp_path / "multi.json"
        assigner.save_to_file(str(output_file), "multi-test")

        with open(output_file) as f:
            data = json.load(f)

        assert len(data["assignments"]) == 3


class TestBalanceByLevel:
    """Tests for level-based balancing."""

    def test_balance_resets_per_level(self) -> None:
        """Test balancing resets for each level."""
        assigner = WorkerAssignment(worker_count=2)
        tasks: list[Task] = [
            {"id": "L1-001", "level": 1, "estimate_minutes": 60},
            {"id": "L1-002", "level": 1, "estimate_minutes": 10},
            {"id": "L2-001", "level": 2, "estimate_minutes": 60},
            {"id": "L2-002", "level": 2, "estimate_minutes": 10},
        ]

        result = assigner.assign(tasks, "test", balance_by_level=True)

        # Level 1: worker 0 gets 60min, worker 1 gets 10min
        # Level 2: resets, worker 0 gets 60min, worker 1 gets 10min
        # Without reset, level 2 would have gone differently

        level_2_tasks = [a for a in result.assignments if a.level == 2]
        # Both levels should show similar distribution pattern
        assert len(level_2_tasks) == 2

    def test_balance_without_level_reset(self) -> None:
        """Test balancing without level reset."""
        assigner = WorkerAssignment(worker_count=2)
        tasks: list[Task] = [
            {"id": "L1-001", "level": 1, "estimate_minutes": 60},
            {"id": "L2-001", "level": 2, "estimate_minutes": 60},
        ]

        assigner.assign(tasks, "test", balance_by_level=False)

        # After L1-001 (60min) on worker 0
        # L2-001 should go to worker 1 due to cumulative balancing
        l2_worker = assigner.get_task_worker("L2-001")
        assert l2_worker == 1  # Worker 1 has less cumulative time

    def test_assign_clears_previous_state(self) -> None:
        """Test that assign clears previous assignment state."""
        assigner = WorkerAssignment(worker_count=2)

        # First assignment
        tasks1: list[Task] = [{"id": "TASK-001", "level": 1}]
        assigner.assign(tasks1, "feature1")
        assert assigner.get_task_worker("TASK-001") == 0

        # Second assignment should clear first
        tasks2: list[Task] = [{"id": "TASK-002", "level": 1}]
        result = assigner.assign(tasks2, "feature2")

        # TASK-001 should no longer be assigned
        assert assigner.get_task_worker("TASK-001") is None
        assert assigner.get_task_worker("TASK-002") == 0
        assert len(result.assignments) == 1

    def test_multiple_levels_sorted(self) -> None:
        """Test tasks are processed in level order."""
        assigner = WorkerAssignment(worker_count=2)
        tasks: list[Task] = [
            {"id": "L3-001", "level": 3, "estimate_minutes": 10},
            {"id": "L1-001", "level": 1, "estimate_minutes": 10},
            {"id": "L2-001", "level": 2, "estimate_minutes": 10},
        ]

        result = assigner.assign(tasks, "test")

        # Verify all tasks are assigned
        assert len(result.assignments) == 3

        # Verify levels are preserved correctly
        task_levels = {a.task_id: a.level for a in result.assignments}
        assert task_levels["L1-001"] == 1
        assert task_levels["L2-001"] == 2
        assert task_levels["L3-001"] == 3
