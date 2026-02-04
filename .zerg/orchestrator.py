"""ZERG v2 Orchestrator - Central coordination for parallel worker execution."""

import contextlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

import yaml
from worktree import LevelMergeResult, Worktree, WorktreeManager


class OrchestratorState(str, Enum):
    """Orchestrator execution states."""

    IDLE = "IDLE"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class MergeConflictError(Exception):
    """Raised when a merge conflict occurs during level completion."""

    def __init__(self, conflicts: list[str]):
        self.conflicts = conflicts
        super().__init__(f"Merge conflict in files: {', '.join(conflicts)}")


@dataclass
class WorkerInfo:
    """Information about a worker process."""

    worker_id: int
    pid: int | None = None
    state: str = "idle"
    current_task: str | None = None
    last_heartbeat: datetime | None = None
    tasks_completed: int = 0
    worktree: Worktree | None = None


@dataclass
class LevelResult:
    """Result of executing a level."""

    level: int
    tasks_total: int
    tasks_completed: int
    tasks_failed: int
    duration_seconds: float
    gate_results: list[dict] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """Check if level completed successfully."""
        return self.tasks_failed == 0 and self.tasks_completed == self.tasks_total


class Orchestrator:
    """Manages worker fleet lifecycle and task distribution.

    The orchestrator coordinates parallel worker execution across git worktrees,
    enforcing level-based task ordering and quality gates.
    """

    def __init__(self, config_path: str = ".zerg/config.yaml", feature: str = "default"):
        """Load configuration and initialize state.

        Args:
            config_path: Path to ZERG configuration file
            feature: Feature name for state isolation
        """
        self._config_path = Path(config_path)
        self._config = self._load_config()
        self._state = OrchestratorState.IDLE
        self._feature = feature
        self._state_path = f".zerg/state/{feature}.json"
        self._log_path = Path(self._config.get("logging", {}).get("directory", ".zerg/logs"))

        # Worker management
        self._workers: dict[int, WorkerInfo] = {}
        self._max_workers = self._config.get("workers", {}).get("max_concurrent", 5)
        self._worktree_manager = WorktreeManager()

        # Task management
        self._task_graph: dict = {}
        self._current_level = 0
        self._completed_tasks: list[str] = []
        self._failed_tasks: list[str] = []
        self._task_queue: list[dict] = []

        # Timing
        self._start_time: datetime | None = None
        self._level_start_time: datetime | None = None

        # Setup logging
        self._setup_logging()

    def _load_config(self) -> dict:
        """Load configuration from YAML file."""
        if not self._config_path.exists():
            return self._default_config()

        with open(self._config_path) as f:
            return yaml.safe_load(f) or self._default_config()

    def _default_config(self) -> dict:
        """Return default configuration."""
        return {
            "workers": {
                "max_concurrent": 5,
                "timeout_minutes": 30,
                "retry_attempts": 3,
                "context_threshold_percent": 70,
            },
            "quality_gates": [],
            "logging": {
                "level": "info",
                "directory": ".zerg/logs",
            },
        }

    def _setup_logging(self) -> None:
        """Configure logging."""
        self._log_path.mkdir(parents=True, exist_ok=True)
        log_file = self._log_path / "orchestrator.log"

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(),
            ],
        )
        self._logger = logging.getLogger("orchestrator")

    def start(
        self,
        task_graph_path: str,
        workers: int = 5,
        resume: bool = False,
        dry_run: bool = False,
    ) -> None:
        """Begin execution with specified worker count.

        Args:
            task_graph_path: Path to task-graph.json
            workers: Number of workers to spawn
            resume: Resume from checkpoint if available
            dry_run: Show plan without executing
        """
        self._logger.info(f"Starting orchestrator with {workers} workers")
        self._state = OrchestratorState.STARTING
        self._start_time = datetime.now()

        # Load task graph
        self._load_task_graph(task_graph_path)

        # Resume from checkpoint if requested
        if resume:
            self.load_checkpoint()

        # Validate worker count
        workers = min(workers, self._max_workers)

        if dry_run:
            self._logger.info("Dry run mode - showing execution plan")
            self._show_execution_plan(workers)
            self._state = OrchestratorState.COMPLETE
            return

        # Initialize workers
        self._spawn_workers(workers)
        self._state = OrchestratorState.RUNNING

        # Execute levels
        try:
            self._execute_all_levels()
            self._state = OrchestratorState.COMPLETE
            self._logger.info("Execution complete")
        except Exception as e:
            self._logger.error(f"Execution failed: {e}")
            self._state = OrchestratorState.FAILED
            raise

    def stop(self, force: bool = False) -> None:
        """Graceful or forced shutdown.

        Args:
            force: If True, terminate workers immediately without checkpointing
        """
        self._logger.info(f"Stopping orchestrator (force={force})")
        self._state = OrchestratorState.STOPPING

        if not force:
            # Save checkpoint before stopping
            self.save_checkpoint()

            # Signal workers to finish current task
            for worker_id in self._workers:
                self._signal_worker_stop(worker_id)

            # Wait for workers to finish (with timeout)
            timeout = self._config.get("workers", {}).get("timeout_minutes", 30) * 60
            self._wait_for_workers(timeout=timeout)

        # Terminate all workers
        self._terminate_workers()
        self._state = OrchestratorState.STOPPED
        self._logger.info("Orchestrator stopped")

    def get_status(self) -> dict:
        """Return current execution state.

        Returns:
            Dictionary with current status information
        """
        active_workers = sum(1 for w in self._workers.values() if w.state == "running")

        state_value = (
            self._state.value if isinstance(self._state, OrchestratorState) else self._state
        )
        return {
            "state": state_value,
            "workers": len(self._workers),
            "active_workers": active_workers,
            "max_workers": self._max_workers,
            "current_level": self._current_level,
            "completed_tasks": len(self._completed_tasks),
            "failed_tasks": len(self._failed_tasks),
            "total_tasks": len(self._task_graph.get("tasks", [])),
            "start_time": self._start_time.isoformat() if self._start_time else None,
            "elapsed_seconds": (
                (datetime.now() - self._start_time).total_seconds()
                if self._start_time
                else 0
            ),
        }

    def save_checkpoint(self) -> None:
        """Save current state for resumption."""
        state_value = (
            self._state.value if isinstance(self._state, OrchestratorState) else self._state
        )
        checkpoint = {
            "state": state_value,
            "current_level": self._current_level,
            "completed_tasks": self._completed_tasks,
            "failed_tasks": self._failed_tasks,
            "timestamp": datetime.now().isoformat(),
        }

        state_path = Path(self._state_path)
        state_path.parent.mkdir(parents=True, exist_ok=True)

        with open(state_path, "w") as f:
            json.dump(checkpoint, f, indent=2)

        self._logger.info(f"Checkpoint saved to {self._state_path}")

    def load_checkpoint(self) -> bool:
        """Load state from checkpoint.

        Returns:
            True if checkpoint was loaded successfully
        """
        state_path = Path(self._state_path)
        if not state_path.exists():
            self._logger.info("No checkpoint found")
            return False

        try:
            with open(state_path) as f:
                checkpoint = json.load(f)

            self._state = OrchestratorState(checkpoint.get("state", "IDLE"))
            self._current_level = checkpoint.get("current_level", 0)
            self._completed_tasks = checkpoint.get("completed_tasks", [])
            self._failed_tasks = checkpoint.get("failed_tasks", [])

            self._logger.info(f"Checkpoint loaded from {self._state_path}")
            return True
        except Exception as e:
            self._logger.error(f"Failed to load checkpoint: {e}")
            return False

    def _load_task_graph(self, path: str) -> None:
        """Load task graph from JSON file."""
        graph_path = Path(path)
        if not graph_path.exists():
            raise FileNotFoundError(f"Task graph not found: {path}")

        with open(graph_path) as f:
            self._task_graph = json.load(f)

        self._logger.info(f"Loaded task graph with {len(self._task_graph.get('tasks', []))} tasks")

    def _spawn_workers(self, count: int) -> None:
        """Spawn worker processes with isolated worktrees."""
        for i in range(count):
            worker = WorkerInfo(worker_id=i)
            self._workers[i] = worker
            self._logger.info(f"Spawned worker {i}")

    def spawn_worker(self, worker_id: str, task: dict) -> WorkerInfo:
        """Spawn a worker with an isolated worktree.

        Args:
            worker_id: Unique identifier for the worker
            task: Task to assign to the worker

        Returns:
            WorkerInfo with worktree attached
        """
        # Create isolated worktree
        worktree = self._worktree_manager.create(worker_id)

        # Create worker info
        worker = WorkerInfo(
            worker_id=int(worker_id) if worker_id.isdigit() else hash(worker_id) % 10000,
            worktree=worktree,
            current_task=task.get("id"),
            state="running",
        )

        self._workers[worker.worker_id] = worker
        self._logger.info(f"Spawned worker {worker_id} in worktree {worktree.path}")

        return worker

    def complete_level(self, level: int) -> LevelMergeResult:
        """Complete a level by merging all worker branches.

        Args:
            level: Level number that was completed

        Returns:
            LevelMergeResult with merge status
        """
        # Get all workers that have worktrees for this level
        worker_ids = [
            wt_id
            for wt_id, w in self._workers.items()
            if w.worktree is not None and w.state != "terminated"
        ]

        # Map integer worker IDs to worktree worker IDs
        wt_worker_ids = [
            self._workers[wid].worktree.worker_id
            for wid in worker_ids
            if self._workers[wid].worktree
        ]

        if not wt_worker_ids:
            return LevelMergeResult(success=True, merged_count=0)

        # Merge all worker branches
        result = self._worktree_manager.merge_level_branches(level, wt_worker_ids)

        if not result.success:
            self._logger.error(
                f"Level {level} merge failed for worker {result.failed_worker}: "
                f"{result.conflicts}"
            )
            raise MergeConflictError(result.conflicts or [])

        # Cleanup worktrees after successful merge
        for wt_id in wt_worker_ids:
            self._worktree_manager.cleanup(wt_id)

        self._logger.info(f"Level {level} completed: merged {result.merged_count} branches")
        return result

    def get_level_workers(self, level: int) -> list[WorkerInfo]:
        """Get all workers that worked on a specific level.

        Args:
            level: Level number

        Returns:
            List of WorkerInfo for workers at this level
        """
        return [w for w in self._workers.values() if w.worktree is not None]

    def _terminate_workers(self) -> None:
        """Terminate all worker processes."""
        for worker_id, worker in self._workers.items():
            if worker.pid:
                with contextlib.suppress(ProcessLookupError):
                    os.kill(worker.pid, 9)
            worker.state = "terminated"
            self._logger.info(f"Terminated worker {worker_id}")

    def _signal_worker_stop(self, worker_id: int) -> None:
        """Signal a worker to stop after current task."""
        if worker_id in self._workers:
            self._workers[worker_id].state = "stopping"

    def _wait_for_workers(self, timeout: int = 300) -> None:
        """Wait for workers to finish with timeout."""
        start = time.time()
        while time.time() - start < timeout:
            active = sum(1 for w in self._workers.values() if w.state == "running")
            if active == 0:
                return
            time.sleep(1)

    def _execute_all_levels(self) -> None:
        """Execute all levels in order."""
        levels = self._get_level_numbers()

        for level in levels:
            if level <= self._current_level and self._current_level > 0:
                continue  # Skip completed levels on resume

            result = self._execute_level(level)
            if not result.success:
                raise RuntimeError(f"Level {level} failed")

            # Run quality gates between levels
            self._run_quality_gates(level)

    def _get_level_numbers(self) -> list[int]:
        """Get sorted list of level numbers from task graph."""
        tasks = self._task_graph.get("tasks", [])
        levels = {t.get("level", 0) for t in tasks}
        return sorted(levels)

    def _execute_level(self, level: int) -> LevelResult:
        """Execute all tasks at a level."""
        self._current_level = level
        self._level_start_time = datetime.now()

        tasks = [t for t in self._task_graph.get("tasks", []) if t.get("level") == level]
        self._logger.info(f"Executing level {level} with {len(tasks)} tasks")

        completed = 0
        failed = 0

        for task in tasks:
            task_id = task.get("id", "unknown")
            if task_id in self._completed_tasks:
                completed += 1
                continue

            # Assign to available worker
            worker = self._get_available_worker()
            if worker:
                success = self._execute_task(worker.worker_id, task)
                if success:
                    self._completed_tasks.append(task_id)
                    completed += 1
                else:
                    self._failed_tasks.append(task_id)
                    failed += 1

        duration = (datetime.now() - self._level_start_time).total_seconds()

        return LevelResult(
            level=level,
            tasks_total=len(tasks),
            tasks_completed=completed,
            tasks_failed=failed,
            duration_seconds=duration,
        )

    def _get_available_worker(self) -> WorkerInfo | None:
        """Get an available worker."""
        for worker in self._workers.values():
            if worker.state in ("idle", "ready"):
                worker.state = "running"
                return worker
        return None

    def _execute_task(self, worker_id: int, task: dict) -> bool:
        """Execute a task on a worker."""
        task_id = task.get("id", "unknown")
        self._logger.info(f"Worker {worker_id} executing task {task_id}")

        worker = self._workers[worker_id]
        worker.current_task = task_id

        # In v2, actual execution happens via subprocess
        # For now, simulate success
        time.sleep(0.01)  # Minimal delay for testing

        worker.current_task = None
        worker.state = "idle"
        worker.tasks_completed += 1

        return True

    def _run_quality_gates(self, level: int) -> bool:
        """Run quality gates after level completion."""
        gates = self._config.get("quality_gates", [])

        for gate in gates:
            if not gate.get("required", True):
                continue

            name = gate.get("name", "unknown")
            self._logger.info(f"Running gate: {name}")
            # Gate execution will be implemented in L3-TASK-001

        return True

    def _show_execution_plan(self, workers: int) -> None:
        """Display execution plan without running."""
        levels = self._get_level_numbers()
        total_tasks = len(self._task_graph.get("tasks", []))

        print("\n=== ZERG Execution Plan ===")
        print(f"Workers: {workers}")
        print(f"Total Tasks: {total_tasks}")
        print(f"Levels: {len(levels)}")
        print()

        for level in levels:
            tasks = [t for t in self._task_graph.get("tasks", []) if t.get("level") == level]
            print(f"Level {level}: {len(tasks)} tasks")
            for task in tasks[:5]:  # Show first 5
                print(f"  - {task.get('id')}: {task.get('title', 'Untitled')}")
            if len(tasks) > 5:
                print(f"  ... and {len(tasks) - 5} more")

    @property
    def current_level(self) -> int:
        """Current execution level."""
        return self._current_level


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ZERG v2 Orchestrator")
    parser.add_argument("--feature", required=True, help="Feature name")
    parser.add_argument("--workers", type=int, default=5, help="Number of workers")
    parser.add_argument("--config", default=".zerg/config.yaml", help="Config file path")
    parser.add_argument("--task-graph", required=True, help="Path to task-graph.json")
    parser.add_argument("--assignments", help="Path to worker-assignments.json")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    parser.add_argument("--dry-run", action="store_true", help="Show plan without executing")
    args = parser.parse_args()

    orch = Orchestrator(config_path=args.config, feature=args.feature)
    orch.start(
        task_graph_path=args.task_graph,
        workers=args.workers,
        resume=args.resume,
        dry_run=args.dry_run,
    )
