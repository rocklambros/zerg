"""Worker protocol handler for ZERG workers."""

import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from zerg.config import ZergConfig
from zerg.constants import DEFAULT_CONTEXT_THRESHOLD, ExitCode, TaskStatus
from zerg.context_tracker import ContextTracker
from zerg.git_ops import GitOps
from zerg.logging import get_logger, set_worker_context
from zerg.parser import TaskParser
from zerg.spec_loader import SpecLoader
from zerg.state import StateManager
from zerg.types import Task
from zerg.verify import VerificationExecutor

logger = get_logger("worker_protocol")

# Default Claude Code invocation settings
CLAUDE_CLI_DEFAULT_TIMEOUT = 1800  # 30 minutes
CLAUDE_CLI_COMMAND = "claude"


@dataclass
class ClaudeInvocationResult:
    """Result of Claude Code CLI invocation."""

    success: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    task_id: str
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "exit_code": self.exit_code,
            "stdout": self.stdout[:1000] if len(self.stdout) > 1000 else self.stdout,
            "stderr": self.stderr[:1000] if len(self.stderr) > 1000 else self.stderr,
            "duration_ms": self.duration_ms,
            "task_id": self.task_id,
            "timestamp": self.timestamp.isoformat(),
        }


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
        task_graph_path: Path | str | None = None,
    ) -> None:
        """Initialize worker protocol.

        Args:
            worker_id: Worker ID (from env if not provided)
            feature: Feature name (from env if not provided)
            config: ZERG configuration
            task_graph_path: Path to task graph JSON (from env if not provided)
        """
        # Get from environment if not provided
        self.worker_id = worker_id or int(os.environ.get("ZERG_WORKER_ID", "0"))
        self.feature = feature or os.environ.get("ZERG_FEATURE", "unknown")
        self.branch = os.environ.get("ZERG_BRANCH", f"zerg/{self.feature}/worker-{self.worker_id}")
        self.worktree_path = Path(os.environ.get("ZERG_WORKTREE", ".")).resolve()

        # Task graph path from arg or env
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
        self.context_tracker = ContextTracker(
            threshold_percent=self.context_threshold * 100
        )

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

    def signal_ready(self) -> None:
        """Signal to orchestrator that worker is ready for tasks.

        Updates state and logs event for orchestrator polling.
        """
        logger.info(f"Worker {self.worker_id} signaling ready")

        self._is_ready = True
        self.state.set_worker_ready(self.worker_id)
        self.state.append_event("worker_ready", {
            "worker_id": self.worker_id,
            "worktree": str(self.worktree_path),
            "branch": self.branch,
        })

    def wait_for_ready(self, timeout: float = 30.0) -> bool:
        """Wait until worker is ready.

        Used primarily for testing and synchronization.

        Args:
            timeout: Maximum seconds to wait

        Returns:
            True if ready, False if timeout
        """
        start = time.time()
        while time.time() - start < timeout:
            if self._is_ready:
                return True
            time.sleep(0.1)
        return False

    @property
    def is_ready(self) -> bool:
        """Check if worker is ready for tasks."""
        return self._is_ready

    def claim_next_task(self) -> Task | None:
        """Claim the next available task.

        Attempts to claim tasks assigned to this worker from the pending queue.
        Loads full task details from the task graph if available.

        Returns:
            Task to execute or None if no tasks available
        """
        # Get pending tasks for this worker
        pending = self.state.get_tasks_by_status(TaskStatus.PENDING)

        for task_id in pending:
            # Try to claim this task
            if self.state.claim_task(task_id, self.worker_id):
                # Load full task from task graph if available
                task = self._load_task_details(task_id)
                self.current_task = task
                logger.info(f"Claimed task {task_id}: {task.get('title', 'untitled')}")
                return task

        return None

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

    def execute_task(self, task: Task) -> bool:
        """Execute a task using Claude Code CLI.

        The full task execution flow:
        1. Update status to IN_PROGRESS
        2. Build task prompt from task spec
        3. Invoke Claude Code CLI with the prompt
        4. Run verification command if specified
        5. Commit changes if successful
        6. Track context usage

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
            # Step 1: Invoke Claude Code to implement the task
            claude_result = self.invoke_claude_code(task)

            if not claude_result.success:
                logger.error(f"Claude Code invocation failed for {task_id}")
                self.state.append_event("claude_failed", {
                    "task_id": task_id,
                    "worker_id": self.worker_id,
                    "exit_code": claude_result.exit_code,
                    "stderr": claude_result.stderr[:500],
                })
                return False

            # Step 2: Run verification if specified
            if task.get("verification") and not self.run_verification(task):
                logger.error(f"Verification failed for {task_id}")
                return False

            # Step 3: Commit changes
            if not self.commit_task_changes(task):
                logger.error(f"Commit failed for {task_id}")
                return False

            # Step 4: Track context usage
            self.context_tracker.track_task_execution(task_id)

            return True

        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")
            self.state.append_event("task_exception", {
                "task_id": task_id,
                "worker_id": self.worker_id,
                "error": str(e),
            })
            return False

    def invoke_claude_code(
        self,
        task: Task,
        timeout: int | None = None,
    ) -> ClaudeInvocationResult:
        """Invoke Claude Code CLI to implement a task.

        Builds a prompt from the task specification and runs Claude Code
        in non-interactive mode with --print flag.

        Args:
            task: Task to implement
            timeout: Timeout in seconds (default: CLAUDE_CLI_DEFAULT_TIMEOUT)

        Returns:
            ClaudeInvocationResult with success status and output
        """
        task_id = task["id"]
        timeout = timeout or CLAUDE_CLI_DEFAULT_TIMEOUT

        # Build the prompt from task specification
        prompt = self._build_task_prompt(task)

        # Build command - use --print for non-interactive execution
        # --dangerously-skip-permissions allows tool execution in automated mode
        cmd = [
            CLAUDE_CLI_COMMAND,
            "--print",
            "--dangerously-skip-permissions",
            prompt,
        ]

        logger.info(f"Invoking Claude Code for task {task_id}")
        logger.debug(f"Prompt: {prompt[:200]}...")

        start_time = time.time()

        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.worktree_path),
                capture_output=True,
                text=True,
                timeout=timeout,
                env={
                    **os.environ,
                    "ZERG_TASK_ID": task_id,
                    "ZERG_WORKER_ID": str(self.worker_id),
                },
            )

            duration_ms = int((time.time() - start_time) * 1000)
            success = result.returncode == 0

            if success:
                logger.info(f"Claude Code completed for {task_id} ({duration_ms}ms)")
            else:
                logger.warning(f"Claude Code failed for {task_id} (exit {result.returncode})")

            return ClaudeInvocationResult(
                success=success,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                duration_ms=duration_ms,
                task_id=task_id,
            )

        except subprocess.TimeoutExpired:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Claude Code timed out for {task_id} after {timeout}s")

            return ClaudeInvocationResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=f"Claude Code invocation timed out after {timeout}s",
                duration_ms=duration_ms,
                task_id=task_id,
            )

        except FileNotFoundError:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Claude CLI not found: {CLAUDE_CLI_COMMAND}")

            return ClaudeInvocationResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=f"Claude CLI not found: {CLAUDE_CLI_COMMAND}",
                duration_ms=duration_ms,
                task_id=task_id,
            )

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Claude Code invocation error: {e}")

            return ClaudeInvocationResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration_ms=duration_ms,
                task_id=task_id,
            )

    def _build_task_prompt(self, task: Task) -> str:
        """Build a Claude Code prompt from task specification.

        Includes feature context (requirements/design specs) as a prefix
        when available, followed by the task-specific prompt.

        Args:
            task: Task specification

        Returns:
            Formatted prompt string
        """
        parts = []

        # Inject feature context if available
        if self._spec_context:
            parts.append(self._spec_context)

        # Task header
        parts.append(f"# Task: {task.get('title', task['id'])}")
        parts.append("")

        # Description
        if description := task.get("description"):
            parts.append("## Description")
            parts.append(description)
            parts.append("")

        # Files to work with
        if files := task.get("files"):
            parts.append("## Files")
            if create := files.get("create"):
                parts.append(f"Create: {', '.join(create)}")
            if modify := files.get("modify"):
                parts.append(f"Modify: {', '.join(modify)}")
            if read := files.get("read"):
                parts.append(f"Reference: {', '.join(read)}")
            parts.append("")

        # Verification command
        if verification := task.get("verification"):
            parts.append("## Verification")
            parts.append(f"Command: `{verification.get('command', '')}`")
            parts.append("")

        # Instructions
        parts.append("## Instructions")
        parts.append("Implement the task as specified. Make all necessary changes.")
        parts.append("Do NOT commit - the orchestrator handles commits.")

        return "\n".join(parts)

    def run_verification(
        self,
        task: Task,
        max_retries: int = 2,
    ) -> bool:
        """Run task verification with retry support.

        Args:
            task: Task to verify
            max_retries: Maximum retry attempts on failure

        Returns:
            True if verification passed
        """
        task_id = task["id"]
        verification = task.get("verification")

        if not verification:
            logger.info(f"No verification for {task_id} - auto-pass")
            return True

        command = verification.get("command", "")
        timeout = verification.get("timeout_seconds", 30)

        if not command:
            logger.info(f"Empty verification command for {task_id} - auto-pass")
            return True

        logger.info(f"Running verification for {task_id}: {command}")

        # Use verifier with retry support
        result = self.verifier.verify_with_retry(
            command,
            task_id,
            max_retries=max_retries,
            timeout=timeout,
            cwd=self.worktree_path,
        )

        if result.success:
            logger.info(f"Verification passed for {task_id}")
            self.state.append_event("verification_passed", {
                "task_id": task_id,
                "worker_id": self.worker_id,
                "duration_ms": result.duration_ms,
            })
            return True
        else:
            logger.error(f"Verification failed for {task_id}: {result.stderr}")
            self.state.append_event("verification_failed", {
                "task_id": task_id,
                "worker_id": self.worker_id,
                "exit_code": result.exit_code,
                "stderr": result.stderr[:500],
            })
            return False

    def commit_task_changes(self, task: Task) -> bool:
        """Commit changes for a completed task.

        BF-009: Added HEAD verification after commit.

        Args:
            task: Completed task

        Returns:
            True if commit succeeded (or no changes)
        """
        task_id = task["id"]

        if not self.git.has_changes():
            logger.info(f"No changes to commit for {task_id}")
            return True

        try:
            # BF-009: Record HEAD before commit for verification
            head_before = self.git.current_commit()

            # Build commit message
            title = task.get("title", task_id)
            commit_msg = f"ZERG [{self.worker_id}]: {title}\n\nTask-ID: {task_id}"

            self.git.commit(commit_msg, add_all=True)

            # BF-009: Verify HEAD changed after commit
            head_after = self.git.current_commit()
            if head_before == head_after:
                logger.error(f"Commit succeeded but HEAD unchanged for {task_id}")
                self.state.append_event("commit_verification_failed", {
                    "task_id": task_id,
                    "worker_id": self.worker_id,
                    "head_before": head_before,
                    "head_after": head_after,
                    "error": "HEAD unchanged after commit",
                })
                return False

            logger.info(f"Committed changes for {task_id}: {head_after[:8]}")

            # Include commit_sha in event (BF-009)
            self.state.append_event("task_committed", {
                "task_id": task_id,
                "worker_id": self.worker_id,
                "branch": self.branch,
                "commit_sha": head_after,
            })

            return True

        except Exception as e:
            logger.error(f"Commit failed for {task_id}: {e}")
            self.state.append_event("commit_failed", {
                "task_id": task_id,
                "worker_id": self.worker_id,
                "error": str(e),
            })
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
