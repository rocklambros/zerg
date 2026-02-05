"""Task execution pipeline handler for ZERG workers.

Extracted from worker_protocol.py. Encapsulates the task execution side
of the protocol: invoking Claude Code, running verification, and committing
changes. Collaborators are injected via constructor (dependency injection).
"""

from __future__ import annotations

import contextlib
import os
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from zerg.constants import (
    LogEvent,
    LogPhase,
    PluginHookEvent,
    TaskStatus,
    WorkerStatus,
)
from zerg.log_writer import TaskArtifactCapture
from zerg.logging import get_logger
from zerg.plugins import LifecycleEvent
from zerg.protocol_types import CLAUDE_CLI_COMMAND, CLAUDE_CLI_DEFAULT_TIMEOUT, ClaudeInvocationResult
from zerg.types import Task

if TYPE_CHECKING:
    from zerg.config import ZergConfig
    from zerg.context_tracker import ContextTracker
    from zerg.git_ops import GitOps
    from zerg.log_writer import StructuredLogWriter
    from zerg.plugins import PluginRegistry
    from zerg.state import StateManager
    from zerg.verify import VerificationExecutor

logger = get_logger("protocol_handler")


class ProtocolHandler:
    """Task execution pipeline handler for ZERG workers.

    Encapsulates the execution side of the worker protocol:
    - execute_task(): runs a single task through the full pipeline
    - invoke_claude_code(): calls the Claude CLI
    - _build_task_prompt(): constructs the prompt for the worker
    - run_verification(): runs the verification command
    - commit_task_changes(): git add + commit the task's files

    Collaborators (state, git, verifier, etc.) are injected via constructor
    to enable testing and composition with the protocol state manager.
    """

    def __init__(
        self,
        *,
        worker_id: int,
        feature: str,
        branch: str,
        worktree_path: Path,
        state: StateManager,
        git: GitOps,
        verifier: VerificationExecutor,
        context_tracker: ContextTracker,
        config: ZergConfig,
        spec_context: str = "",
        structured_writer: StructuredLogWriter | None = None,
        plugin_registry: PluginRegistry | None = None,
    ) -> None:
        """Initialize the protocol handler.

        Args:
            worker_id: Worker identifier.
            feature: Feature name being worked on.
            branch: Git branch for this worker.
            worktree_path: Path to the git worktree.
            state: State manager for task/worker state persistence.
            git: Git operations helper.
            verifier: Verification command executor.
            context_tracker: Context usage tracker.
            config: ZERG configuration.
            spec_context: Pre-loaded spec context string for prompt injection.
            structured_writer: Optional structured JSONL log writer.
            plugin_registry: Optional plugin registry for lifecycle hooks.
        """
        self.worker_id = worker_id
        self.feature = feature
        self.branch = branch
        self.worktree_path = worktree_path
        self.state = state
        self.git = git
        self.verifier = verifier
        self.context_tracker = context_tracker
        self.config = config
        self._spec_context = spec_context
        self._structured_writer = structured_writer
        self._plugin_registry = plugin_registry

    def execute_task(
        self,
        task: Task,
        *,
        update_worker_state: Any | None = None,
    ) -> bool:
        """Execute a task using Claude Code CLI.

        The full task execution flow:
        1. Update status to IN_PROGRESS
        2. Build task prompt from task spec
        3. Invoke Claude Code CLI with the prompt
        4. Run verification command if specified
        5. Commit changes if successful
        6. Track context usage

        Args:
            task: Task to execute.
            update_worker_state: Optional callback to update worker state.
                Signature: (status: WorkerStatus, current_task=..., tasks_completed=...) -> None

        Returns:
            True if task succeeded.
        """
        task_id = task["id"]
        logger.info(f"Executing task {task_id}: {task.get('title', 'untitled')}")

        # Update status
        self.state.set_task_status(task_id, TaskStatus.IN_PROGRESS, worker_id=self.worker_id)
        if update_worker_state:
            update_worker_state(WorkerStatus.RUNNING, current_task=task_id)

        task_start_time = time.time()

        # Set up artifact capture
        log_dir = os.environ.get("ZERG_LOG_DIR", ".zerg/logs")
        artifact = TaskArtifactCapture(log_dir, task_id)

        # Emit structured event
        if self._structured_writer:
            self._structured_writer.emit(
                "info",
                f"Task {task_id} started",
                task_id=task_id,
                phase=LogPhase.EXECUTE,
                event=LogEvent.TASK_STARTED,
            )

        # Emit plugin lifecycle event
        if self._plugin_registry:
            with contextlib.suppress(Exception):
                self._plugin_registry.emit_event(
                    LifecycleEvent(
                        event_type=PluginHookEvent.TASK_STARTED.value,
                        data={"task_id": task_id, "worker_id": self.worker_id, "feature": self.feature},
                    )
                )

        success = False
        try:
            # Step 1: Invoke Claude Code to implement the task
            claude_result = self.invoke_claude_code(task)

            # Capture Claude output
            artifact.capture_claude_output(claude_result.stdout, claude_result.stderr)
            artifact.write_event(
                {
                    "event": "claude_invocation",
                    "success": claude_result.success,
                    "exit_code": claude_result.exit_code,
                    "duration_ms": claude_result.duration_ms,
                }
            )

            if not claude_result.success:
                logger.error(f"Claude Code invocation failed for {task_id}")
                self.state.append_event(
                    "claude_failed",
                    {
                        "task_id": task_id,
                        "worker_id": self.worker_id,
                        "exit_code": claude_result.exit_code,
                        "stderr": claude_result.stderr[:500],
                    },
                )
                if self._structured_writer:
                    self._structured_writer.emit(
                        "error",
                        f"Task {task_id} failed: Claude invocation failed",
                        task_id=task_id,
                        phase=LogPhase.EXECUTE,
                        event=LogEvent.TASK_FAILED,
                    )
                return False

            # Step 2: Run verification if specified
            if task.get("verification") and not self.run_verification(task, artifact=artifact):
                logger.error(f"Verification failed for {task_id}")
                if self._structured_writer:
                    self._structured_writer.emit(
                        "error",
                        f"Task {task_id} verification failed",
                        task_id=task_id,
                        phase=LogPhase.VERIFY,
                        event=LogEvent.VERIFICATION_FAILED,
                    )
                return False

            # Step 3: Commit changes
            if not self.commit_task_changes(task, artifact=artifact):
                logger.error(f"Commit failed for {task_id}")
                return False

            # Step 4: Track context usage
            self.context_tracker.track_task_execution(task_id)

            # Step 5: Record task duration
            duration = int((time.time() - task_start_time) * 1000)
            self.state.record_task_duration(task_id, duration)

            success = True

            if self._structured_writer:
                self._structured_writer.emit(
                    "info",
                    f"Task {task_id} completed",
                    task_id=task_id,
                    phase=LogPhase.EXECUTE,
                    event=LogEvent.TASK_COMPLETED,
                    duration_ms=duration,
                )

            # Emit plugin lifecycle event
            if self._plugin_registry:
                with contextlib.suppress(Exception):
                    self._plugin_registry.emit_event(
                        LifecycleEvent(
                            event_type=PluginHookEvent.TASK_COMPLETED.value,
                            data={
                                "task_id": task_id,
                                "worker_id": self.worker_id,
                                "success": True,
                                "duration_ms": duration,
                            },
                        )
                    )

            return True

        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")
            self.state.append_event(
                "task_exception",
                {
                    "task_id": task_id,
                    "worker_id": self.worker_id,
                    "error": str(e),
                },
            )
            if self._structured_writer:
                self._structured_writer.emit(
                    "error",
                    f"Task {task_id} exception: {e}",
                    task_id=task_id,
                    phase=LogPhase.EXECUTE,
                    event=LogEvent.TASK_FAILED,
                )
            if self._plugin_registry:
                with contextlib.suppress(Exception):
                    self._plugin_registry.emit_event(
                        LifecycleEvent(
                            event_type=PluginHookEvent.TASK_COMPLETED.value,
                            data={
                                "task_id": task_id,
                                "worker_id": self.worker_id,
                                "success": False,
                                "error": str(e),
                            },
                        )
                    )
            return False
        finally:
            # Clean up artifacts based on retention policy
            artifact.cleanup(success, self.config.logging)

    def invoke_claude_code(
        self,
        task: Task,
        timeout: int | None = None,
    ) -> ClaudeInvocationResult:
        """Invoke Claude Code CLI to implement a task.

        Builds a prompt from the task specification and runs Claude Code
        in non-interactive mode with --print flag.

        Args:
            task: Task to implement.
            timeout: Timeout in seconds (default: CLAUDE_CLI_DEFAULT_TIMEOUT).

        Returns:
            ClaudeInvocationResult with success status and output.
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
            invocation_success = result.returncode == 0

            if invocation_success:
                logger.info(f"Claude Code completed for {task_id} ({duration_ms}ms)")
            else:
                logger.warning(f"Claude Code failed for {task_id} (exit {result.returncode})")

            return ClaudeInvocationResult(
                success=invocation_success,
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
            task: Task specification.

        Returns:
            Formatted prompt string.
        """
        parts: list[str] = []

        # Inject task-scoped context if available, otherwise fall back to full spec context
        if task_context := task.get("context"):
            parts.append("# Task Context (Scoped)")
            parts.append(task_context)
        elif self._spec_context:
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
        artifact: TaskArtifactCapture | None = None,
    ) -> bool:
        """Run task verification with retry support.

        Args:
            task: Task to verify.
            max_retries: Maximum retry attempts on failure.
            artifact: Optional artifact capture for verification output.

        Returns:
            True if verification passed.
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

        # Capture verification output as artifact
        if artifact:
            artifact.capture_verification(result.stdout, result.stderr, result.exit_code)

        if result.success:
            logger.info(f"Verification passed for {task_id}")
            self.state.append_event(
                "verification_passed",
                {
                    "task_id": task_id,
                    "worker_id": self.worker_id,
                    "duration_ms": result.duration_ms,
                },
            )
            if self._structured_writer:
                self._structured_writer.emit(
                    "info",
                    f"Verification passed for {task_id}",
                    task_id=task_id,
                    phase=LogPhase.VERIFY,
                    event=LogEvent.VERIFICATION_PASSED,
                    duration_ms=result.duration_ms,
                )
            return True
        else:
            logger.error(f"Verification failed for {task_id}: {result.stderr}")
            self.state.append_event(
                "verification_failed",
                {
                    "task_id": task_id,
                    "worker_id": self.worker_id,
                    "exit_code": result.exit_code,
                    "stderr": result.stderr[:500],
                },
            )
            return False

    def commit_task_changes(
        self,
        task: Task,
        artifact: TaskArtifactCapture | None = None,
    ) -> bool:
        """Commit changes for a completed task.

        BF-009: Added HEAD verification after commit.

        Args:
            task: Completed task.
            artifact: Optional artifact capture for git diff.

        Returns:
            True if commit succeeded (or no changes).
        """
        task_id = task["id"]

        if not self.git.has_changes():
            logger.info(f"No changes to commit for {task_id}")
            return True

        try:
            # Capture git diff as artifact before commit
            if artifact:
                try:
                    diff_result = subprocess.run(
                        ["git", "diff", "--cached"],
                        cwd=str(self.worktree_path),
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    # Also get unstaged diff
                    unstaged = subprocess.run(
                        ["git", "diff"],
                        cwd=str(self.worktree_path),
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    diff_text = diff_result.stdout + unstaged.stdout
                    if diff_text:
                        artifact.capture_git_diff(diff_text)
                except Exception as e:
                    logger.debug(f"Best-effort artifact capture failed: {e}")

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
                self.state.append_event(
                    "commit_verification_failed",
                    {
                        "task_id": task_id,
                        "worker_id": self.worker_id,
                        "head_before": head_before,
                        "head_after": head_after,
                        "error": "HEAD unchanged after commit",
                    },
                )
                return False

            logger.info(f"Committed changes for {task_id}: {head_after[:8]}")

            # Include commit_sha in event (BF-009)
            self.state.append_event(
                "task_committed",
                {
                    "task_id": task_id,
                    "worker_id": self.worker_id,
                    "branch": self.branch,
                    "commit_sha": head_after,
                },
            )

            return True

        except Exception as e:
            logger.error(f"Commit failed for {task_id}: {e}")
            self.state.append_event(
                "commit_failed",
                {
                    "task_id": task_id,
                    "worker_id": self.worker_id,
                    "error": str(e),
                },
            )
            return False
