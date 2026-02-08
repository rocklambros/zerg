"""Task graph parsing and dependency management."""

from pathlib import Path
from typing import Any

from zerg.exceptions import TaskDependencyError, ValidationError
from zerg.json_utils import load as json_load
from zerg.logging import get_logger
from zerg.types import Task, TaskGraph, VerificationSpec
from zerg.validation import validate_dependencies, validate_file_ownership, validate_task_graph

logger = get_logger("parser")


class TaskParser:
    """Parse and manage task graphs."""

    def __init__(self) -> None:
        """Initialize task parser."""
        self._graph: TaskGraph | None = None
        self._tasks: dict[str, Task] = {}
        self._dependencies: dict[str, list[str]] = {}
        self._dependents: dict[str, list[str]] = {}

    def parse(self, path: str | Path) -> TaskGraph:
        """Parse a task graph from a JSON file.

        Args:
            path: Path to task-graph.json

        Returns:
            Parsed TaskGraph

        Raises:
            ValidationError: If the task graph is invalid
        """
        path = Path(path)

        if not path.exists():
            raise ValidationError(f"Task graph not found: {path}", field="path")

        with open(path) as f:
            data = json_load(f)

        return self.parse_dict(data)

    def parse_dict(self, data: dict[str, Any]) -> TaskGraph:
        """Parse a task graph from a dictionary.

        Args:
            data: Task graph dictionary

        Returns:
            Parsed TaskGraph

        Raises:
            ValidationError: If the task graph is invalid
        """
        # Validate structure
        is_valid, errors = validate_task_graph(data)
        if not is_valid:
            raise ValidationError(
                f"Invalid task graph: {'; '.join(errors)}",
                field="schema",
                details={"errors": errors},
            )

        # Validate file ownership
        is_valid, errors = validate_file_ownership(data)
        if not is_valid:
            raise ValidationError(
                f"File ownership conflict: {'; '.join(errors)}",
                field="file_ownership",
                details={"errors": errors},
            )

        # Validate dependencies
        is_valid, errors = validate_dependencies(data)
        if not is_valid:
            raise ValidationError(
                f"Dependency error: {'; '.join(errors)}",
                field="dependencies",
                details={"errors": errors},
            )

        # Build internal structures — data dict conforms to TaskGraph TypedDict
        # after validation above, so the cast is safe.
        self._graph: TaskGraph = data  # type: ignore[assignment]  # validated above
        self._tasks.clear()
        self._dependencies.clear()
        self._dependents.clear()

        for task in data.get("tasks", []):
            task_id = task["id"]
            self._tasks[task_id] = task
            self._dependencies[task_id] = task.get("dependencies", [])

            # Build reverse dependency map
            for dep in task.get("dependencies", []):
                if dep not in self._dependents:
                    self._dependents[dep] = []
                self._dependents[dep].append(task_id)

        logger.info(f"Parsed task graph: {data.get('feature')} with {len(self._tasks)} tasks")

        assert self._graph is not None
        return self._graph

    def get_task(self, task_id: str) -> Task | None:
        """Get a task by ID.

        Args:
            task_id: Task identifier

        Returns:
            Task or None if not found
        """
        return self._tasks.get(task_id)

    def get_all_tasks(self) -> list[Task]:
        """Get all tasks.

        Returns:
            List of all tasks
        """
        return list(self._tasks.values())

    def get_tasks_for_level(self, level: int) -> list[Task]:
        """Get all tasks for a specific level.

        Args:
            level: Level number

        Returns:
            List of tasks in the level
        """
        return [t for t in self._tasks.values() if t.get("level") == level]

    def get_dependencies(self, task_id: str) -> list[str]:
        """Get task IDs that a task depends on.

        Args:
            task_id: Task identifier

        Returns:
            List of dependency task IDs
        """
        return self._dependencies.get(task_id, [])

    def get_dependents(self, task_id: str) -> list[str]:
        """Get task IDs that depend on a task.

        Args:
            task_id: Task identifier

        Returns:
            List of dependent task IDs
        """
        return self._dependents.get(task_id, [])

    def are_dependencies_complete(self, task_id: str, completed_tasks: set[str]) -> bool:
        """Check if all dependencies of a task are complete.

        Args:
            task_id: Task identifier
            completed_tasks: Set of completed task IDs

        Returns:
            True if all dependencies are complete
        """
        deps = self.get_dependencies(task_id)
        return all(dep in completed_tasks for dep in deps)

    def get_ready_tasks(self, completed_tasks: set[str], in_progress: set[str]) -> list[Task]:
        """Get tasks that are ready to execute.

        A task is ready if:
        - All its dependencies are complete
        - It is not already complete or in progress

        Args:
            completed_tasks: Set of completed task IDs
            in_progress: Set of in-progress task IDs

        Returns:
            List of ready tasks
        """
        ready = []
        for task_id, task in self._tasks.items():
            if task_id in completed_tasks or task_id in in_progress:
                continue
            if self.are_dependencies_complete(task_id, completed_tasks):
                ready.append(task)
        return ready

    def topological_sort(self) -> list[str]:
        """Return tasks in topological order (dependencies first).

        Returns:
            List of task IDs in execution order

        Raises:
            TaskDependencyError: If there is a cycle
        """
        # Kahn's algorithm
        in_degree: dict[str, int] = dict.fromkeys(self._tasks, 0)
        for task_id, deps in self._dependencies.items():
            in_degree[task_id] = len(deps)

        # Start with tasks that have no dependencies
        queue = [tid for tid, degree in in_degree.items() if degree == 0]
        result = []

        while queue:
            # Sort by level for deterministic order
            queue.sort(key=lambda tid: (self._tasks[tid].get("level", 0), tid))
            task_id = queue.pop(0)
            result.append(task_id)

            # Decrease in-degree for dependents
            for dependent in self._dependents.get(task_id, []):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        if len(result) != len(self._tasks):
            # Find tasks involved in cycle
            remaining = set(self._tasks.keys()) - set(result)
            raise TaskDependencyError(
                "Dependency cycle detected",
                task_id=task_id or "unknown",
                missing_deps=list(remaining),
            )

        return result

    def get_critical_path(self) -> list[str]:
        """Get the critical path through the task graph.

        The critical path is the longest path by estimated duration.

        Returns:
            List of task IDs on the critical path
        """
        if self._graph and "critical_path" in self._graph:
            return self._graph["critical_path"]

        # Calculate if not provided
        # Use dynamic programming: longest path to each node
        topo_order = self.topological_sort()
        dist: dict[str, int] = dict.fromkeys(self._tasks, 0)
        pred: dict[str, str | None] = dict.fromkeys(self._tasks)

        for task_id in topo_order:
            for dep in self._dependencies.get(task_id, []):
                dep_dist = dist[dep] + self._tasks[dep].get("estimate_minutes", 0)
                if dep_dist > dist[task_id]:
                    dist[task_id] = dep_dist
                    pred[task_id] = dep

        # Find the end of critical path (max distance)
        end_task = max(
            topo_order,
            key=lambda tid: dist[tid] + self._tasks[tid].get("estimate_minutes", 0),
        )

        # Reconstruct path
        path = [end_task]
        current = pred[end_task]
        while current:
            path.insert(0, current)
            current = pred[current]

        return path

    def get_files_for_task(self, task_id: str) -> dict[str, list[str]]:
        """Get file specifications for a task.

        Args:
            task_id: Task identifier

        Returns:
            Dictionary with create, modify, read lists
        """
        task = self._tasks.get(task_id)
        if not task:
            return {"create": [], "modify": [], "read": []}

        files = task.get("files", {})
        return {
            "create": files.get("create", []),
            "modify": files.get("modify", []),
            "read": files.get("read", []),
        }

    def get_verification(self, task_id: str) -> VerificationSpec | None:
        """Get verification specification for a task.

        Args:
            task_id: Task identifier

        Returns:
            Verification spec or None
        """
        task = self._tasks.get(task_id)
        return task.get("verification") if task else None

    @property
    def feature_name(self) -> str:
        """Get the feature name from the task graph."""
        return self._graph.get("feature", "unknown") if self._graph else "unknown"

    @property
    def total_tasks(self) -> int:
        """Get total number of tasks."""
        return len(self._tasks)

    @property
    def levels(self) -> list[int]:
        """Get sorted list of level numbers."""
        level_set = {t.get("level", 1) for t in self._tasks.values()}
        return sorted(level_set)
