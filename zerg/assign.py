"""Worker task assignment for ZERG."""

from collections import defaultdict
from typing import Any

from zerg.logging import get_logger
from zerg.types import Task, WorkerAssignmentEntry, WorkerAssignments

logger = get_logger("assign")


class WorkerAssignment:
    """Calculate and manage task assignments to workers."""

    def __init__(self, worker_count: int = 5) -> None:
        """Initialize worker assignment.

        Args:
            worker_count: Number of workers
        """
        self.worker_count = worker_count
        self._assignments: dict[str, int] = {}  # task_id -> worker_id
        self._worker_tasks: dict[int, list[str]] = defaultdict(list)  # worker_id -> [task_ids]
        self._worker_minutes: dict[int, int] = defaultdict(int)  # worker_id -> total minutes

    def assign(
        self,
        tasks: list[Task],
        feature: str,
        balance_by_level: bool = True,
    ) -> WorkerAssignments:
        """Assign tasks to workers.

        Args:
            tasks: List of tasks to assign
            feature: Feature name
            balance_by_level: Balance workload within each level

        Returns:
            WorkerAssignments with all assignments
        """
        self._assignments.clear()
        self._worker_tasks.clear()
        self._worker_minutes.clear()

        # Group tasks by level
        level_tasks: dict[int, list[Task]] = defaultdict(list)
        for task in tasks:
            level = task.get("level", 1)
            level_tasks[level].append(task)

        # Assign tasks level by level
        for level in sorted(level_tasks.keys()):
            level_task_list = level_tasks[level]

            if balance_by_level:
                # Reset worker minutes for each level for balanced assignment
                level_minutes: dict[int, int] = defaultdict(int)
            else:
                level_minutes = self._worker_minutes

            # Sort tasks by estimated minutes (longest first for better balancing)
            sorted_tasks = sorted(
                level_task_list,
                key=lambda t: t.get("estimate_minutes", 15),
                reverse=True,
            )

            for task in sorted_tasks:
                task_id = task["id"]
                minutes = task.get("estimate_minutes", 15)

                # Find worker with least assigned time in this level
                worker_id = min(
                    range(self.worker_count),
                    key=lambda w: level_minutes[w],
                )

                self._assignments[task_id] = worker_id
                self._worker_tasks[worker_id].append(task_id)
                self._worker_minutes[worker_id] += minutes
                level_minutes[worker_id] += minutes

        # Build result
        entries = []
        for task in tasks:
            task_id = task["id"]
            if task_id in self._assignments:
                entries.append(
                    WorkerAssignmentEntry(
                        task_id=task_id,
                        worker_id=self._assignments[task_id],
                        level=task.get("level", 1),
                        estimated_minutes=task.get("estimate_minutes", 15),
                    )
                )

        result = WorkerAssignments(
            feature=feature,
            worker_count=self.worker_count,
            assignments=entries,
        )

        logger.info(f"Assigned {len(tasks)} tasks to {self.worker_count} workers for feature {feature}")

        return result

    def get_worker_tasks(self, worker_id: int) -> list[str]:
        """Get task IDs assigned to a worker.

        Args:
            worker_id: Worker identifier

        Returns:
            List of task IDs
        """
        return self._worker_tasks.get(worker_id, []).copy()

    def get_task_worker(self, task_id: str) -> int | None:
        """Get the worker assigned to a task.

        Args:
            task_id: Task identifier

        Returns:
            Worker ID or None if not assigned
        """
        return self._assignments.get(task_id)

    def get_worker_workload(self, worker_id: int) -> int:
        """Get total estimated minutes for a worker.

        Args:
            worker_id: Worker identifier

        Returns:
            Total estimated minutes
        """
        return self._worker_minutes.get(worker_id, 0)

    def get_workload_summary(self) -> dict[int, dict[str, Any]]:
        """Get workload summary for all workers.

        Returns:
            Dictionary with worker stats
        """
        summary = {}
        for worker_id in range(self.worker_count):
            tasks = self._worker_tasks.get(worker_id, [])
            summary[worker_id] = {
                "task_count": len(tasks),
                "estimated_minutes": self._worker_minutes.get(worker_id, 0),
                "tasks": tasks,
            }
        return summary

    def rebalance(
        self,
        completed_tasks: set[str],
        failed_tasks: set[str],
        current_level: int,
    ) -> list[tuple[str, int, int]]:
        """Rebalance tasks after failures or completions.

        Args:
            completed_tasks: Set of completed task IDs
            failed_tasks: Set of failed task IDs
            current_level: Current execution level

        Returns:
            List of (task_id, old_worker, new_worker) tuples for reassignments
        """
        reassignments = []

        # Find workers with capacity (completed their current level tasks)
        worker_capacity: dict[int, int] = {}
        for worker_id in range(self.worker_count):
            tasks = self._worker_tasks.get(worker_id, [])
            pending_minutes = sum(
                self._get_task_minutes(tid) for tid in tasks if tid not in completed_tasks and tid not in failed_tasks
            )
            worker_capacity[worker_id] = 60 - pending_minutes  # Assume 60 min max

        # Failed tasks need to be reassigned
        for task_id in failed_tasks:
            if task_id not in self._assignments:
                continue

            old_worker = self._assignments[task_id]

            # Find worker with most capacity
            new_worker = max(
                range(self.worker_count),
                key=lambda w: worker_capacity.get(w, 0),
            )

            if new_worker != old_worker and worker_capacity.get(new_worker, 0) > 0:
                self._assignments[task_id] = new_worker
                self._worker_tasks[old_worker].remove(task_id)
                self._worker_tasks[new_worker].append(task_id)
                reassignments.append((task_id, old_worker, new_worker))

                minutes = self._get_task_minutes(task_id)
                worker_capacity[new_worker] -= minutes
                worker_capacity[old_worker] += minutes

        if reassignments:
            logger.info(f"Rebalanced {len(reassignments)} tasks")

        return reassignments

    def _get_task_minutes(self, task_id: str) -> int:
        """Get estimated minutes for a task (placeholder).

        Args:
            task_id: Task identifier

        Returns:
            Estimated minutes
        """
        # In a real implementation, this would look up the task
        return 15

    def save_to_file(self, path: str, feature: str) -> None:
        """Save assignments to a JSON file.

        Args:
            path: Output file path
            feature: Feature name
        """
        import json
        from pathlib import Path

        assignments = WorkerAssignments(
            feature=feature,
            worker_count=self.worker_count,
            assignments=[
                WorkerAssignmentEntry(
                    task_id=tid,
                    worker_id=wid,
                    level=0,  # Would need task data for actual level
                    estimated_minutes=15,
                )
                for tid, wid in self._assignments.items()
            ],
        )

        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(assignments.to_dict(), f, indent=2)

        logger.info(f"Saved assignments to {path}")

    @classmethod
    def load_from_file(cls, path: str) -> "WorkerAssignment":
        """Load assignments from a JSON file.

        Args:
            path: Input file path

        Returns:
            WorkerAssignment instance
        """
        import json
        from pathlib import Path

        with open(Path(path)) as f:
            data = json.load(f)

        assigner = cls(worker_count=data.get("worker_count", 5))

        for entry in data.get("assignments", []):
            task_id = entry["task_id"]
            worker_id = entry["worker_id"]
            assigner._assignments[task_id] = worker_id
            assigner._worker_tasks[worker_id].append(task_id)
            assigner._worker_minutes[worker_id] += entry.get("estimated_minutes", 15)

        return assigner
