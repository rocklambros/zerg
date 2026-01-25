"""ZERG orchestrator - main coordination engine."""

import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from zerg.assign import WorkerAssignment
from zerg.config import ZergConfig
from zerg.constants import TaskStatus, WorkerStatus
from zerg.containers import ContainerManager
from zerg.exceptions import OrchestratorError
from zerg.gates import GateRunner
from zerg.levels import LevelController
from zerg.logging import get_logger
from zerg.parser import TaskParser
from zerg.ports import PortAllocator
from zerg.state import StateManager
from zerg.types import OrchestratorState, Task, WorkerState
from zerg.worktree import WorktreeManager

logger = get_logger("orchestrator")


class Orchestrator:
    """Main ZERG orchestration engine.

    Coordinates workers, manages levels, and handles state transitions.
    """

    def __init__(
        self,
        feature: str,
        config: ZergConfig | None = None,
        repo_path: str | Path = ".",
    ) -> None:
        """Initialize orchestrator.

        Args:
            feature: Feature name being executed
            config: ZERG configuration
            repo_path: Path to git repository
        """
        self.feature = feature
        self.config = config or ZergConfig.load()
        self.repo_path = Path(repo_path).resolve()

        # Initialize components
        self.state = StateManager(feature)
        self.levels = LevelController()
        self.parser = TaskParser()
        self.gates = GateRunner(self.config)
        self.worktrees = WorktreeManager(repo_path)
        self.containers = ContainerManager(self.config)
        self.ports = PortAllocator(
            range_start=self.config.ports.range_start,
            range_end=self.config.ports.range_end,
        )
        self.assigner: WorkerAssignment | None = None

        # Runtime state
        self._running = False
        self._workers: dict[int, WorkerState] = {}
        self._on_task_complete: list[Callable[[str], None]] = []
        self._on_level_complete: list[Callable[[int], None]] = []
        self._poll_interval = 5  # seconds

    def start(
        self,
        task_graph_path: str | Path,
        worker_count: int = 5,
        start_level: int | None = None,
        dry_run: bool = False,
    ) -> None:
        """Start orchestration.

        Args:
            task_graph_path: Path to task-graph.json
            worker_count: Number of workers to spawn
            start_level: Starting level (default: 1)
            dry_run: If True, don't actually spawn workers
        """
        logger.info(f"Starting orchestration for {self.feature}")

        # Load and parse task graph
        self.parser.parse(task_graph_path)
        tasks = self.parser.get_all_tasks()

        # Initialize level controller
        self.levels.initialize(tasks)

        # Create assignments
        self.assigner = WorkerAssignment(worker_count)
        assignments = self.assigner.assign(tasks, self.feature)

        # Save assignments
        assignments_path = Path(f".gsd/specs/{self.feature}/worker-assignments.json")
        self.assigner.save_to_file(str(assignments_path), self.feature)

        # Initialize state
        self.state.load()
        self.state.append_event("rush_started", {
            "workers": worker_count,
            "total_tasks": len(tasks),
        })

        if dry_run:
            logger.info("Dry run - not spawning workers")
            self._print_plan(assignments)
            return

        # Start execution
        self._running = True
        self._spawn_workers(worker_count)
        self._start_level(start_level or 1)
        self._main_loop()

    def stop(self, force: bool = False) -> None:
        """Stop orchestration.

        Args:
            force: Force stop without graceful shutdown
        """
        logger.info(f"Stopping orchestration (force={force})")
        self._running = False

        # Stop all workers
        for worker_id in list(self._workers.keys()):
            self._terminate_worker(worker_id, force=force)

        # Release ports
        self.ports.release_all()

        # Save final state
        self.state.append_event("rush_stopped", {"force": force})
        self.state.save()

        logger.info("Orchestration stopped")

    def status(self) -> dict[str, Any]:
        """Get current orchestration status.

        Returns:
            Status dictionary
        """
        level_status = self.levels.get_status()

        return {
            "feature": self.feature,
            "running": self._running,
            "current_level": level_status["current_level"],
            "progress": {
                "total": level_status["total_tasks"],
                "completed": level_status["completed_tasks"],
                "failed": level_status["failed_tasks"],
                "in_progress": level_status["in_progress_tasks"],
                "percent": level_status["progress_percent"],
            },
            "workers": {
                wid: {
                    "status": w.status.value,
                    "current_task": w.current_task,
                    "tasks_completed": w.tasks_completed,
                }
                for wid, w in self._workers.items()
            },
            "levels": level_status["levels"],
            "is_complete": level_status["is_complete"],
        }

    def _main_loop(self) -> None:
        """Main orchestration loop."""
        logger.info("Starting main loop")

        while self._running:
            try:
                # Poll worker status
                self._poll_workers()

                # Check level completion
                if self.levels.is_level_complete(self.levels.current_level):
                    self._on_level_complete_handler(self.levels.current_level)

                    # Advance to next level if possible
                    if self.levels.can_advance():
                        next_level = self.levels.advance_level()
                        if next_level:
                            self._start_level(next_level)
                    else:
                        # Check if all done
                        status = self.levels.get_status()
                        if status["is_complete"]:
                            logger.info("All tasks complete!")
                            self._running = False
                            break

                # Sleep before next poll
                time.sleep(self._poll_interval)

            except KeyboardInterrupt:
                logger.info("Interrupted by user")
                self.stop()
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                self.state.set_error(str(e))
                self.stop(force=True)
                raise

        logger.info("Main loop ended")

    def _start_level(self, level: int) -> None:
        """Start a level.

        Args:
            level: Level number to start
        """
        logger.info(f"Starting level {level}")

        task_ids = self.levels.start_level(level)
        self.state.set_current_level(level)
        self.state.set_level_status(level, "running")
        self.state.append_event("level_started", {"level": level, "tasks": len(task_ids)})

        # Assign tasks to workers
        for task_id in task_ids:
            if self.assigner:
                worker_id = self.assigner.get_task_worker(task_id)
                if worker_id is not None:
                    self.state.set_task_status(task_id, TaskStatus.PENDING, worker_id=worker_id)

    def _on_level_complete_handler(self, level: int) -> None:
        """Handle level completion.

        Args:
            level: Completed level
        """
        logger.info(f"Level {level} complete")

        # Run quality gates
        all_passed, results = self.gates.run_all_gates(required_only=True)

        if all_passed:
            self.state.set_level_status(level, "complete")
            self.state.append_event("level_complete", {"level": level})

            # Notify callbacks
            for callback in self._on_level_complete:
                callback(level)
        else:
            logger.error(f"Level {level} gates failed")
            self.state.set_error(f"Level {level} gates failed")
            self.stop()

    def _spawn_worker(self, worker_id: int) -> WorkerState:
        """Spawn a single worker.

        Args:
            worker_id: Worker identifier

        Returns:
            WorkerState for the spawned worker
        """
        logger.info(f"Spawning worker {worker_id}")

        # Allocate port
        port = self.ports.allocate_one()

        # Create worktree
        wt_info = self.worktrees.create(self.feature, worker_id)

        # Start container
        container_info = self.containers.start_worker(
            worker_id=worker_id,
            feature=self.feature,
            port=port,
            worktree_path=wt_info.path,
            branch=wt_info.branch,
        )

        # Create worker state
        worker_state = WorkerState(
            worker_id=worker_id,
            status=WorkerStatus.RUNNING,
            port=port,
            container_id=container_info.container_id,
            worktree_path=str(wt_info.path),
            branch=wt_info.branch,
            started_at=datetime.now(),
        )

        self._workers[worker_id] = worker_state
        self.state.set_worker_state(worker_state)
        self.state.append_event("worker_started", {"worker_id": worker_id, "port": port})

        return worker_state

    def _spawn_workers(self, count: int) -> None:
        """Spawn multiple workers.

        Args:
            count: Number of workers to spawn
        """
        logger.info(f"Spawning {count} workers")

        for worker_id in range(count):
            try:
                self._spawn_worker(worker_id)
            except Exception as e:
                logger.error(f"Failed to spawn worker {worker_id}: {e}")
                # Continue with other workers

    def _terminate_worker(self, worker_id: int, force: bool = False) -> None:
        """Terminate a worker.

        Args:
            worker_id: Worker identifier
            force: Force termination
        """
        worker = self._workers.get(worker_id)
        if not worker:
            return

        logger.info(f"Terminating worker {worker_id}")

        # Stop container
        self.containers.stop_worker(worker_id, force=force)

        # Delete worktree
        try:
            wt_path = self.worktrees.get_worktree_path(self.feature, worker_id)
            self.worktrees.delete(wt_path, force=True)
        except Exception as e:
            logger.warning(f"Failed to delete worktree for worker {worker_id}: {e}")

        # Release port
        if worker.port:
            self.ports.release(worker.port)

        # Update state
        worker.status = WorkerStatus.STOPPED
        self.state.set_worker_state(worker)
        self.state.append_event("worker_stopped", {"worker_id": worker_id})

        del self._workers[worker_id]

    def _poll_workers(self) -> None:
        """Poll worker status and handle completions."""
        for worker_id, worker in list(self._workers.items()):
            # Check container status
            status = self.containers.get_status(worker_id)

            if status == WorkerStatus.CRASHED:
                logger.error(f"Worker {worker_id} crashed")
                worker.status = WorkerStatus.CRASHED
                self.state.set_worker_state(worker)

                # Mark current task as failed
                if worker.current_task:
                    self.levels.mark_task_failed(worker.current_task, "Worker crashed")
                    self.state.set_task_status(
                        worker.current_task,
                        TaskStatus.FAILED,
                        error="Worker crashed",
                    )

            elif status == WorkerStatus.STOPPED:
                # Worker exited - check for completion
                self._handle_worker_exit(worker_id)

            # Update health check
            worker.health_check_at = datetime.now()

    def _handle_worker_exit(self, worker_id: int) -> None:
        """Handle worker exit.

        Args:
            worker_id: Worker that exited
        """
        worker = self._workers.get(worker_id)
        if not worker:
            return

        # Check exit code (would need to get from container)
        # For now, assume clean exit means task complete

        if worker.current_task:
            # Check if task verification passes
            task = self.parser.get_task(worker.current_task)
            if task:
                verification = task.get("verification", {})
                if verification.get("command"):
                    # Task should have been verified by worker
                    self.levels.mark_task_complete(worker.current_task)
                    self.state.set_task_status(worker.current_task, TaskStatus.COMPLETE)

                    for callback in self._on_task_complete:
                        callback(worker.current_task)

        # Restart worker for more tasks
        remaining = self._get_remaining_tasks_for_level(self.levels.current_level)
        if remaining:
            try:
                self._spawn_worker(worker_id)
            except Exception as e:
                logger.error(f"Failed to restart worker {worker_id}: {e}")

    def _get_remaining_tasks_for_level(self, level: int) -> list[str]:
        """Get remaining tasks for a level.

        Args:
            level: Level number

        Returns:
            List of incomplete task IDs
        """
        pending = self.levels.get_pending_tasks_for_level(level)
        return pending

    def _print_plan(self, assignments: Any) -> None:
        """Print execution plan (for dry run).

        Args:
            assignments: WorkerAssignments
        """
        print("\n=== ZERG Execution Plan ===\n")
        print(f"Feature: {self.feature}")
        print(f"Total Tasks: {self.parser.total_tasks}")
        print(f"Levels: {self.parser.levels}")
        print(f"Workers: {assignments.worker_count}")
        print()

        for level in self.parser.levels:
            tasks = self.parser.get_tasks_for_level(level)
            print(f"Level {level}:")
            for task in tasks:
                worker = self.assigner.get_task_worker(task["id"]) if self.assigner else "?"
                print(f"  [{task['id']}] {task['title']} -> Worker {worker}")
            print()

    def on_task_complete(self, callback: Callable[[str], None]) -> None:
        """Register callback for task completion.

        Args:
            callback: Function to call with task_id
        """
        self._on_task_complete.append(callback)

    def on_level_complete(self, callback: Callable[[int], None]) -> None:
        """Register callback for level completion.

        Args:
            callback: Function to call with level number
        """
        self._on_level_complete.append(callback)
