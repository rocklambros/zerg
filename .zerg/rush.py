"""ZERG v2 Rush Command - Task graph execution with orchestrator."""

from dataclasses import dataclass, field
from pathlib import Path

from orchestrator import Orchestrator
from state import ExecutionState
from task_graph import TaskGraph


class GraphLoadError(Exception):
    """Raised when task graph cannot be loaded."""

    pass


@dataclass
class ExecutionResult:
    """Result of a rush execution."""

    validated: bool
    execution_id: str | None = None
    tasks_completed: int = 0
    tasks_failed: int = 0
    errors: list[str] = field(default_factory=list)


class RushCommand:
    """Execute task graph with orchestrator."""

    default_workers: int = 5

    def __init__(self):
        """Initialize rush command."""
        self.orchestrator = Orchestrator()

    def execute(
        self,
        graph_path: Path,
        workers: int | None = None,
        dry_run: bool = False,
        resume: bool = False,
    ) -> ExecutionResult:
        """Execute the task graph.

        Args:
            graph_path: Path to task-graph.json
            workers: Number of parallel workers
            dry_run: Validate only, don't execute
            resume: Resume from checkpoint

        Returns:
            ExecutionResult with execution status
        """
        workers = workers or self.default_workers

        # Load or resume state
        if resume:
            try:
                state = ExecutionState.load()
            except (FileNotFoundError, ValueError, OSError):
                # No state to resume, create new
                state = ExecutionState.create(self._get_feature_name(graph_path))
        else:
            state = ExecutionState.create(self._get_feature_name(graph_path))

        # Load and validate task graph
        try:
            graph = self._load_graph(graph_path)
        except GraphLoadError as e:
            return ExecutionResult(
                validated=False,
                errors=[str(e)],
            )

        # Validate graph
        validation_errors = self._validate_graph(graph)
        if validation_errors:
            return ExecutionResult(
                validated=False,
                errors=validation_errors,
            )

        if dry_run:
            return ExecutionResult(
                validated=True,
                execution_id=state.feature,
                tasks_completed=0,
                tasks_failed=0,
            )

        # Execute with orchestrator
        self.orchestrator.start(graph, workers)

        return ExecutionResult(
            validated=True,
            execution_id=state.feature,
            tasks_completed=len(
                [t for t in graph.tasks.values() if getattr(t, "status", None) == "complete"]
            ),
            tasks_failed=len(
                [t for t in graph.tasks.values() if getattr(t, "status", None) == "failed"]
            ),
        )

    def _load_graph(self, graph_path: Path) -> TaskGraph:
        """Load task graph from file.

        Args:
            graph_path: Path to task-graph.json

        Returns:
            TaskGraph instance

        Raises:
            GraphLoadError: If file cannot be loaded
        """
        if not graph_path.exists():
            raise GraphLoadError(f"Task graph not found: {graph_path}")

        try:
            return TaskGraph.from_file(graph_path)
        except Exception as e:
            raise GraphLoadError(f"Failed to parse task graph: {e}") from e

    def _validate_graph(self, graph: TaskGraph) -> list[str]:
        """Validate task graph.

        Args:
            graph: TaskGraph to validate

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Cycles are detected during graph loading (from_file raises ValueError)
        # So if we get here, graph has no cycles

        # Check file ownership conflicts
        conflicts = graph.validate_file_ownership()
        if conflicts:
            for conflict in conflicts:
                errors.append(f"File ownership conflict: {conflict}")

        return errors

    def _get_feature_name(self, graph_path: Path) -> str:
        """Extract feature name from graph path.

        Args:
            graph_path: Path to task-graph.json

        Returns:
            Feature name or 'default'
        """
        # Expected path: .gsd/specs/{feature}/task-graph.json
        parts = graph_path.parts
        try:
            specs_idx = parts.index("specs")
            if specs_idx + 1 < len(parts) - 1:
                return parts[specs_idx + 1]
        except ValueError:
            pass  # "specs" not in path; fall through to default

        return "default"

    def _generate_summary(self, graph_path: Path) -> dict:
        """Generate execution summary.

        Args:
            graph_path: Path to task-graph.json

        Returns:
            Summary dictionary
        """
        graph = self._load_graph(graph_path)

        return {
            "total_tasks": len(graph.tasks),
            "levels": len({t.level for t in graph.tasks.values()}),
            "feature_name": self._get_feature_name(graph_path),
        }
