"""Worker protocol handler for ZERG workers."""

import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from zerg.config import ZergConfig
from zerg.constants import DEFAULT_CONTEXT_THRESHOLD, ExitCode, TaskStatus
from zerg.exceptions import TaskVerificationFailed
from zerg.git_ops import GitOps
from zerg.logging import get_logger, set_worker_context
from zerg.state import StateManager
from zerg.types import Task
from zerg.verify import VerificationExecutor

logger = get_logger("worker_protocol")


@dataclass
class WorkerContext:
    """Context for a worker instance."""

    worker_id: int
    feature: str
    worktree_path: Path
    branch: str
    context_threshold: float = DEFAULT_CONTEXT_THRESHOLD


class WorkerProtocol:
    """Protocol handler for ZERG workers.

    Implements the worker-side protocol for:
    - Task claiming and execution
    - Context monitoring
    - Checkpointing
    - Completion reporting
    """

    def __init__(
        self,
        worker_id: int | None = None,
        feature: str | None = None,
        config: ZergConfig | None = None,
    ) -> None:
        """Initialize worker protocol.

        Args:
            worker_id: Worker ID (from env if not provided)
            feature: Feature name (from env if not provided)
            config: ZERG configuration
        """
        # Get from environment if not provided
        self.worker_id = worker_id or int(os.environ.get("ZERG_WORKER_ID", "0"))
        self.feature = feature or os.environ.get("ZERG_FEATURE", "unknown")
        self.branch = os.environ.get("ZERG_BRANCH", f"zerg/{self.feature}/worker-{self.worker_id}")
        self.worktree_path = Path(os.environ.get("ZERG_WORKTREE", ".")).resolve()

        self.config = config or ZergConfig.load()
        self.context_threshold = self.config.context_threshold

        # Initialize components
        self.state = StateManager(self.feature)
        self.verifier = VerificationExecutor()
        self.git = GitOps(self.worktree_path)

        # Runtime state
        self.current_task: Task | None = None
        self.tasks_completed = 0
        self._started_at: datetime | None = None

        # Set logging context
        set_worker_context(worker_id=self.worker_id, feature=self.feature)

    def start(self) -> None:
        """Start the worker protocol.

        Called when worker container starts.
        """
        logger.info(f"Worker {self.worker_id} starting for feature {self.feature}")
        self._started_at = datetime.now()

        # Load state
        self.state.load()

        # Main execution loop
        while True:
            # Check context usage
            if self.should_checkpoint():
                self.checkpoint_and_exit()
                return

            # Claim next task
            task = self.claim_next_task()
            if not task:
                logger.info("No more tasks available")
                break

            # Execute task
            success = self.execute_task(task)

            if success:
                self.report_complete(task["id"])
            else:
                self.report_failed(task["id"], "Task execution failed")

        # Clean exit
        logger.info(f"Worker {self.worker_id} completed {self.tasks_completed} tasks")
        sys.exit(ExitCode.SUCCESS)

    def claim_next_task(self) -> Task | None:
        """Claim the next available task.

        Returns:
            Task to execute or None if no tasks available
        """
        # Get pending tasks for this worker
        pending = self.state.get_tasks_by_status(TaskStatus.PENDING)

        for task_id in pending:
            # Try to claim this task
            if self.state.claim_task(task_id, self.worker_id):
                # Load task details (would come from task graph in real impl)
                task: Task = {
                    "id": task_id,
                    "title": f"Task {task_id}",
                    "level": 1,
                }
                self.current_task = task
                logger.info(f"Claimed task {task_id}")
                return task

        return None

    def execute_task(self, task: Task) -> bool:
        """Execute a task.

        Args:
            task: Task to execute

        Returns:
            True if task succeeded
        """
        task_id = task["id"]
        logger.info(f"Executing task {task_id}: {task.get('title', 'untitled')}")

        # Update status
        self.state.set_task_status(task_id, TaskStatus.IN_PROGRESS, worker_id=self.worker_id)

        try:
            # Execute the task (in real implementation, this would run Claude Code)
            # For now, we simulate by running verification
            verification = task.get("verification")

            if verification:
                command = verification.get("command", "")
                timeout = verification.get("timeout_seconds", 30)

                result = self.verifier.verify(
                    command,
                    task_id,
                    timeout=timeout,
                    cwd=self.worktree_path,
                )

                if not result.success:
                    return False

            # Commit changes
            if self.git.has_changes():
                self.git.commit(
                    f"ZERG [{self.worker_id}]: Complete {task_id}",
                    add_all=True,
                )

            return True

        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")
            return False

    def report_complete(self, task_id: str) -> None:
        """Report task completion.

        Args:
            task_id: Completed task ID
        """
        logger.info(f"Task {task_id} complete")

        self.state.set_task_status(task_id, TaskStatus.COMPLETE, worker_id=self.worker_id)
        self.state.append_event("task_complete", {
            "task_id": task_id,
            "worker_id": self.worker_id,
        })

        self.tasks_completed += 1
        self.current_task = None

    def report_failed(self, task_id: str, error: str | None = None) -> None:
        """Report task failure.

        Args:
            task_id: Failed task ID
            error: Error message
        """
        logger.error(f"Task {task_id} failed: {error}")

        self.state.set_task_status(
            task_id,
            TaskStatus.FAILED,
            worker_id=self.worker_id,
            error=error,
        )
        self.state.append_event("task_failed", {
            "task_id": task_id,
            "worker_id": self.worker_id,
            "error": error,
        })

        self.current_task = None

    def check_context_usage(self) -> float:
        """Check current context usage.

        Returns:
            Context usage as float 0.0-1.0
        """
        # In a real implementation, this would check Claude Code's context
        # For now, we estimate based on time and tasks
        if not self._started_at:
            return 0.0

        # Simulate context growth
        elapsed = (datetime.now() - self._started_at).total_seconds()
        tasks_factor = self.tasks_completed * 0.1  # 10% per task

        return min(tasks_factor + (elapsed / 3600) * 0.5, 1.0)

    def should_checkpoint(self) -> bool:
        """Check if worker should checkpoint and exit.

        Returns:
            True if context threshold exceeded
        """
        usage = self.check_context_usage()
        return usage >= self.context_threshold

    def checkpoint_and_exit(self) -> None:
        """Checkpoint current work and exit.

        Commits any in-progress work and exits with checkpoint code.
        """
        logger.info(f"Worker {self.worker_id} checkpointing")

        # Commit WIP if there are changes
        if self.git.has_changes():
            task_ref = self.current_task["id"] if self.current_task else "no-task"
            self.git.commit(
                f"WIP: ZERG [{self.worker_id}] checkpoint during {task_ref}",
                add_all=True,
            )

        # Update task status
        if self.current_task:
            self.state.set_task_status(
                self.current_task["id"],
                TaskStatus.PAUSED,
                worker_id=self.worker_id,
            )

        # Log checkpoint
        self.state.append_event("worker_checkpoint", {
            "worker_id": self.worker_id,
            "tasks_completed": self.tasks_completed,
            "current_task": self.current_task["id"] if self.current_task else None,
        })

        logger.info(f"Worker {self.worker_id} checkpointed - exiting")
        sys.exit(ExitCode.CHECKPOINT)

    def get_status(self) -> dict[str, Any]:
        """Get worker status.

        Returns:
            Status dictionary
        """
        return {
            "worker_id": self.worker_id,
            "feature": self.feature,
            "branch": self.branch,
            "worktree": str(self.worktree_path),
            "current_task": self.current_task["id"] if self.current_task else None,
            "tasks_completed": self.tasks_completed,
            "context_usage": self.check_context_usage(),
            "context_threshold": self.context_threshold,
            "started_at": self._started_at.isoformat() if self._started_at else None,
        }


def run_worker() -> None:
    """Entry point for running a worker."""
    try:
        protocol = WorkerProtocol()
        protocol.start()
    except Exception as e:
        logger.error(f"Worker failed: {e}")
        sys.exit(ExitCode.ERROR)


if __name__ == "__main__":
    run_worker()
