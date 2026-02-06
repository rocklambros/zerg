"""Worker protocol state machine for ZERG workers.

Extracted from worker_protocol.py. Manages the worker lifecycle state machine:
task claiming, readiness signalling, completion/failure reporting, checkpointing,
and context tracking. Delegates task execution to ProtocolHandler.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from zerg.config import ZergConfig
from zerg.constants import (
    ExitCode,
    TaskStatus,
    WorkerStatus,
)
from zerg.context_tracker import ContextTracker
from zerg.dependency_checker import DependencyChecker
from zerg.git_ops import GitOps
from zerg.logging import get_logger, set_worker_context, setup_structured_logging
from zerg.parser import TaskParser
from zerg.plugins import PluginRegistry
from zerg.protocol_handler import ProtocolHandler
from zerg.protocol_types import _SENTINEL, WorkerContext
from zerg.spec_loader import SpecLoader
from zerg.state import StateManager
from zerg.types import Task, WorkerState
from zerg.verify import VerificationExecutor

logger = get_logger("protocol_state")

# Re-export WorkerContext for consumers that import from this module
__all__ = ["WorkerProtocol", "run_worker", "WorkerContext"]


class WorkerProtocol:
    """Protocol state machine for ZERG workers.

    Implements the worker-side protocol for:
    - Task claiming and execution
    - Context monitoring
    - Checkpointing
    - Completion reporting

    Delegates the actual task execution pipeline (Claude Code invocation,
    verification, commit) to ProtocolHandler.
    """

    def __init__(
        self,
        worker_id: int | None = None,
        feature: str | None = None,
        config: ZergConfig | None = None,
        task_graph_path: Path | str | None = None,
        plugin_registry: PluginRegistry | None = None,
    ) -> None:
        """Initialize worker protocol.

        Args:
            worker_id: Worker ID (from env if not provided)
            feature: Feature name (from env if not provided)
            config: ZERG configuration
            task_graph_path: Path to task graph JSON (from env if not provided)
            plugin_registry: Optional plugin registry for lifecycle hooks
        """
        # Get from environment if not provided
        self.worker_id = worker_id or int(os.environ.get("ZERG_WORKER_ID", "0"))
        self.feature = feature or os.environ.get("ZERG_FEATURE", "unknown")
        self.branch = os.environ.get("ZERG_BRANCH", f"zerg/{self.feature}/worker-{self.worker_id}")
        self.worktree_path = Path(os.environ.get("ZERG_WORKTREE", ".")).resolve()

        # Task graph path from arg or env
        self.task_graph_path: Path | None
        if task_graph_path:
            self.task_graph_path = Path(task_graph_path)
        else:
            env_path = os.environ.get("ZERG_TASK_GRAPH")
            self.task_graph_path = Path(env_path) if env_path else None

        self.config = config or ZergConfig.load()
        self.context_threshold = self.config.context_threshold

        # Initialize components
        # Use ZERG_STATE_DIR from env if set (workers run in worktrees, need main repo state)
        state_dir = os.environ.get("ZERG_STATE_DIR")
        self.state = StateManager(self.feature, state_dir=state_dir)
        self.verifier = VerificationExecutor()
        self.git = GitOps(self.worktree_path)
        self.context_tracker = ContextTracker(threshold_percent=self.context_threshold * 100)

        # Task parser for loading task details
        self.task_parser: TaskParser | None = None
        if self.task_graph_path and self.task_graph_path.exists():
            self.task_parser = TaskParser()
            try:
                self.task_parser.parse(self.task_graph_path)
                logger.info(f"Loaded task graph from {self.task_graph_path}")
            except Exception as e:
                logger.warning(f"Failed to load task graph: {e}")
                self.task_parser = None

        # Dependency checker for enforcing task dependencies during claim
        self.dependency_checker: DependencyChecker | None = None
        if self.task_parser:
            self.dependency_checker = DependencyChecker(self.task_parser, self.state)
            logger.debug("Initialized DependencyChecker for task claiming")

        # Spec loader for feature context injection
        spec_dir = os.environ.get("ZERG_SPEC_DIR")
        if spec_dir:
            # Use parent of spec_dir as GSD root (spec_dir is .gsd/specs/{feature})
            gsd_root = Path(spec_dir).parent.parent
            self.spec_loader = SpecLoader(gsd_dir=gsd_root)
        else:
            self.spec_loader = SpecLoader(gsd_dir=self.worktree_path / ".gsd")

        # Pre-load feature specs for prompt injection
        self._spec_context: str = ""
        if self.spec_loader.specs_exist(self.feature):
            self._spec_context = self.spec_loader.load_and_format(self.feature)
            logger.info(f"Loaded spec context for {self.feature} ({len(self._spec_context)} chars)")

        # Runtime state
        self.current_task: Task | None = None
        self.tasks_completed = 0
        self._started_at: datetime | None = None
        self._is_ready = False

        # Set logging context
        set_worker_context(worker_id=self.worker_id, feature=self.feature)

        # Set up structured JSONL logging
        log_dir = os.environ.get("ZERG_LOG_DIR", ".zerg/logs")
        self._structured_writer = None
        try:
            self._structured_writer = setup_structured_logging(
                log_dir=log_dir,
                worker_id=self.worker_id,
                feature=self.feature,
                level=self.config.logging.level,
                max_size_mb=self.config.logging.max_log_size_mb,
            )
        except Exception as e:
            logger.warning(f"Failed to set up structured logging: {e}")

        # Plugin registry (optional, for lifecycle hooks)
        self._plugin_registry = plugin_registry
        has_plugins = hasattr(self.config, "plugins") and self.config.plugins.enabled
        if self._plugin_registry is None and has_plugins:
            try:
                self._plugin_registry = PluginRegistry()
                self._plugin_registry.load_yaml_hooks([h.model_dump() for h in self.config.plugins.hooks])
                self._plugin_registry.load_entry_points()
            except Exception as e:
                logger.warning(f"Failed to initialize plugin registry: {e}")
                self._plugin_registry = None

        # Create ProtocolHandler for task execution delegation
        self._handler = ProtocolHandler(
            worker_id=self.worker_id,
            feature=self.feature,
            branch=self.branch,
            worktree_path=self.worktree_path,
            state=self.state,
            git=self.git,
            verifier=self.verifier,
            context_tracker=self.context_tracker,
            config=self.config,
            spec_context=self._spec_context,
            structured_writer=self._structured_writer,
            plugin_registry=self._plugin_registry,
        )

    def _update_worker_state(
        self,
        status: WorkerStatus,
        current_task: object = _SENTINEL,
        tasks_completed: int | None = None,
    ) -> None:
        """Update worker state in shared state file using read-modify-write.

        Reloads state from disk first to avoid clobbering orchestrator writes,
        then updates the worker's own fields and saves.

        Args:
            status: New worker status
            current_task: Current task ID (use _SENTINEL to leave unchanged, None to clear)
            tasks_completed: Tasks completed count (None to leave unchanged)
        """
        self.state.load()  # Reload to avoid clobbering orchestrator writes
        worker_state = self.state.get_worker_state(self.worker_id)
        if not worker_state:
            worker_state = WorkerState(
                worker_id=self.worker_id,
                status=status,
                branch=self.branch,
                worktree_path=str(self.worktree_path),
                started_at=self._started_at,
            )
        worker_state.status = status
        if current_task is not _SENTINEL:
            worker_state.current_task = current_task  # type: ignore[assignment]
        if tasks_completed is not None:
            worker_state.tasks_completed = tasks_completed
        worker_state.context_usage = self.check_context_usage()
        self.state.set_worker_state(worker_state)

    def start(self) -> None:
        """Start the worker protocol.

        Called when worker container starts.
        """
        logger.info(f"Worker {self.worker_id} starting for feature {self.feature}")
        self._started_at = datetime.now()

        # Load state
        self.state.load()

        # Signal ready to orchestrator
        self.signal_ready()
        self._update_worker_state(WorkerStatus.RUNNING)

        # Main execution loop
        try:
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

                # Execute task via ProtocolHandler
                success = self._handler.execute_task(
                    task,
                    update_worker_state=self._update_worker_state,
                )

                if success:
                    self.report_complete(task["id"])
                else:
                    self.report_failed(task["id"], "Task execution failed")
        except Exception:
            self._update_worker_state(WorkerStatus.CRASHED, current_task=None)
            raise

        # Clean exit
        self._update_worker_state(WorkerStatus.STOPPED, current_task=None)
        logger.info(f"Worker {self.worker_id} completed {self.tasks_completed} tasks")
        sys.exit(ExitCode.SUCCESS)

    def signal_ready(self) -> None:
        """Signal to orchestrator that worker is ready for tasks.

        Updates state and logs event for orchestrator polling.
        """
        logger.info(f"Worker {self.worker_id} signaling ready")

        self._is_ready = True
        self.state.set_worker_ready(self.worker_id)
        self.state.append_event(
            "worker_ready",
            {
                "worker_id": self.worker_id,
                "worktree": str(self.worktree_path),
                "branch": self.branch,
            },
        )

    def wait_for_ready(self, timeout: float = 30.0) -> bool:
        """Wait until worker is ready (sync wrapper).

        Delegates to wait_for_ready_async via asyncio.run().
        Used primarily for testing and synchronization.

        Args:
            timeout: Maximum seconds to wait

        Returns:
            True if ready, False if timeout
        """
        return asyncio.run(self.wait_for_ready_async(timeout))

    async def wait_for_ready_async(self, timeout: float = 30.0) -> bool:
        """Wait until worker is ready.

        Single source of truth for wait_for_ready logic.
        Polls with asyncio.sleep for non-blocking behavior.

        Args:
            timeout: Maximum seconds to wait

        Returns:
            True if ready, False if timeout
        """
        start = time.time()
        while time.time() - start < timeout:
            if self._is_ready:
                return True
            await asyncio.sleep(0.1)
        return False

    @property
    def is_ready(self) -> bool:
        """Check if worker is ready for tasks."""
        return self._is_ready

    def claim_next_task(
        self,
        max_wait: float = 120.0,
        poll_interval: float = 2.0,
    ) -> Task | None:
        """Claim the next available task (sync wrapper).

        Delegates to claim_next_task_async via asyncio.run().

        Args:
            max_wait: Maximum seconds to wait for tasks to appear (default: 120s)
            poll_interval: Initial poll interval in seconds (doubles each attempt, cap 10s)

        Returns:
            Task to execute or None if no tasks available after waiting
        """
        return asyncio.run(self.claim_next_task_async(max_wait, poll_interval))

    async def claim_next_task_async(
        self,
        max_wait: float = 120.0,
        poll_interval: float = 2.0,
    ) -> Task | None:
        """Claim the next available task, polling if none are ready yet.

        Single source of truth for claim_next_task logic.

        Workers may start before the orchestrator assigns tasks via _start_level().
        This method polls with backoff to handle the timing gap between worker
        readiness and task assignment.

        Args:
            max_wait: Maximum seconds to wait for tasks to appear (default: 120s)
            poll_interval: Initial poll interval in seconds (doubles each attempt, cap 10s)

        Returns:
            Task to execute or None if no tasks available after waiting
        """
        start_time = time.time()
        interval = poll_interval
        attempt = 0

        while True:
            # Reload state from disk to pick up orchestrator writes
            self.state.load()

            # Get pending tasks for this worker
            pending = self.state.get_tasks_by_status(TaskStatus.PENDING)

            for task_id in pending:
                # Try to claim this task with dependency enforcement
                if self.state.claim_task(
                    task_id,
                    self.worker_id,
                    dependency_checker=self.dependency_checker,
                ):
                    # Load full task from task graph if available
                    task = self._load_task_details(task_id)
                    self.current_task = task
                    logger.info(f"Claimed task {task_id}: {task.get('title', 'untitled')}")
                    return task

            # Check if we've waited long enough
            elapsed = time.time() - start_time
            if elapsed >= max_wait:
                logger.info(f"No tasks found after {elapsed:.1f}s of polling")
                return None

            attempt += 1
            if attempt == 1:
                logger.info(f"No tasks available yet, polling (max {max_wait}s)...")

            await asyncio.sleep(interval)
            interval = min(interval * 1.5, 10.0)  # backoff, cap at 10s

    def _load_task_details(self, task_id: str) -> Task:
        """Load full task details from task graph.

        Args:
            task_id: Task identifier

        Returns:
            Task with full details or minimal stub
        """
        # Try to load from task parser
        if self.task_parser:
            parsed_task = self.task_parser.get_task(task_id)
            if parsed_task:
                logger.debug(f"Loaded task {task_id} from task graph")
                return parsed_task

        # Fall back to minimal stub
        logger.warning(f"Task {task_id} not found in graph, using stub")
        return {
            "id": task_id,
            "title": f"Task {task_id}",
            "level": 1,
        }

    def report_complete(self, task_id: str) -> None:
        """Report task completion.

        Args:
            task_id: Completed task ID
        """
        logger.info(f"Task {task_id} complete")

        self.state.set_task_status(task_id, TaskStatus.COMPLETE, worker_id=self.worker_id)
        self.state.append_event(
            "task_complete",
            {
                "task_id": task_id,
                "worker_id": self.worker_id,
            },
        )

        self.tasks_completed += 1
        self.current_task = None
        self._update_worker_state(
            WorkerStatus.RUNNING,
            current_task=None,
            tasks_completed=self.tasks_completed,
        )

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
        self.state.append_event(
            "task_failed",
            {
                "task_id": task_id,
                "worker_id": self.worker_id,
                "error": error,
            },
        )

        self.current_task = None
        self._update_worker_state(WorkerStatus.RUNNING, current_task=None)

    def check_context_usage(self) -> float:
        """Check current context usage.

        Returns:
            Context usage as float 0.0-1.0
        """
        # Use context tracker for estimation
        usage = self.context_tracker.get_usage()
        return usage.usage_percent / 100.0

    def should_checkpoint(self) -> bool:
        """Check if worker should checkpoint and exit.

        Returns:
            True if context threshold exceeded
        """
        return self.context_tracker.should_checkpoint()

    def track_file_read(self, path: str | Path, size: int | None = None) -> None:
        """Track a file read for context estimation.

        Args:
            path: File path that was read
            size: Optional file size (auto-detected if not provided)
        """
        self.context_tracker.track_file_read(path, size)

    def track_tool_call(self) -> None:
        """Track a tool invocation for context estimation."""
        self.context_tracker.track_tool_call()

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
        self.state.append_event(
            "worker_checkpoint",
            {
                "worker_id": self.worker_id,
                "tasks_completed": self.tasks_completed,
                "current_task": self.current_task["id"] if self.current_task else None,
            },
        )

        self._update_worker_state(WorkerStatus.CHECKPOINTING)
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
