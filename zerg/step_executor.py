"""Step-by-step task execution for bite-sized planning.

This module provides the StepExecutor class for executing TDD-style steps
within tasks. Each step has an action, command to run, and verification
requirements. Steps are executed in strict order with heartbeat updates.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypedDict

from zerg.command_executor import CommandExecutor, CommandValidationError
from zerg.logging import get_logger

if TYPE_CHECKING:
    from zerg.heartbeat import HeartbeatWriter

logger = get_logger("step_executor")


class StepAction(StrEnum):
    """TDD step action types."""

    WRITE_TEST = "write_test"
    VERIFY_FAIL = "verify_fail"
    IMPLEMENT = "implement"
    VERIFY_PASS = "verify_pass"
    FORMAT = "format"
    COMMIT = "commit"


class StepVerify(StrEnum):
    """Step verification modes."""

    EXIT_CODE = "exit_code"  # Expect exit code 0 (success)
    EXIT_CODE_NONZERO = "exit_code_nonzero"  # Expect non-zero exit (e.g., test should fail)
    NONE = "none"  # No verification needed


class StepState(StrEnum):
    """Step execution states."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class Step(TypedDict, total=False):
    """A single execution step within a task."""

    step: int  # Step number (1-indexed)
    action: str  # StepAction value
    file: str  # Target file for this step
    code_snippet: str  # Optional code snippet (for high detail)
    run: str  # Command to run
    verify: str  # StepVerify value (exit_code, exit_code_nonzero, none)


@dataclass
class StepResult:
    """Result of executing a single step."""

    step_number: int
    action: str
    state: StepState
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = 0
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "step_number": self.step_number,
            "action": self.action,
            "state": self.state.value,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration_ms": self.duration_ms,
            "error_message": self.error_message,
        }


@dataclass
class TaskResult:
    """Result of executing a task (with or without steps)."""

    task_id: str
    success: bool
    failed_step: int | None = None  # Step number that failed (1-indexed)
    step_results: list[StepResult] = field(default_factory=list)
    total_duration_ms: int = 0
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "task_id": self.task_id,
            "success": self.success,
            "failed_step": self.failed_step,
            "step_results": [sr.to_dict() for sr in self.step_results],
            "total_duration_ms": self.total_duration_ms,
            "error_message": self.error_message,
        }


class StepExecutor:
    """Executes steps within a task in strict order.

    The StepExecutor handles:
    - Executing steps in sequential order
    - Verifying exit codes based on step.verify field
    - Updating heartbeat with current step progress
    - Returning detailed results with failed_step if applicable

    For tasks without steps (classic mode), this class can still be used
    but will simply return success without step-level tracking.
    """

    def __init__(
        self,
        task_id: str,
        heartbeat_writer: HeartbeatWriter | None = None,
        working_dir: str | None = None,
        default_timeout: int = 120,
    ) -> None:
        """Initialize StepExecutor.

        Args:
            task_id: ID of the task being executed.
            heartbeat_writer: Optional HeartbeatWriter for progress updates.
            working_dir: Working directory for command execution.
            default_timeout: Default timeout for commands in seconds.
        """
        self._task_id = task_id
        self._heartbeat_writer = heartbeat_writer
        self._working_dir = working_dir
        self._default_timeout = default_timeout
        self._step_states: list[str] = []
        self._executor = CommandExecutor(
            working_dir=Path(working_dir) if working_dir else None,
            timeout=default_timeout,
            trust_commands=True,  # Task-graph commands are trusted
        )

    def execute(self, steps: list[Step] | None) -> TaskResult:
        """Execute all steps in a task.

        Args:
            steps: List of steps to execute. If None or empty, returns success
                   (classic mode - task has no step-level tracking).

        Returns:
            TaskResult with success/failure and step details.
        """
        start_time = time.monotonic()

        # Handle classic mode (no steps)
        if not steps:
            logger.debug("Task %s has no steps, using classic mode", self._task_id)
            return TaskResult(
                task_id=self._task_id,
                success=True,
                total_duration_ms=0,
            )

        # Initialize step states
        total_steps = len(steps)
        self._step_states = [StepState.PENDING.value] * total_steps
        step_results: list[StepResult] = []

        logger.info("Executing %d steps for task %s", total_steps, self._task_id)

        for idx, step in enumerate(steps):
            step_number = step.get("step", idx + 1)
            action = step.get("action", "unknown")

            # Update heartbeat to show current step
            self._update_heartbeat(step_number, total_steps)

            # Mark step as in progress
            self._step_states[idx] = StepState.IN_PROGRESS.value
            self._update_heartbeat(step_number, total_steps)

            # Execute the step
            result = self._execute_step(step, step_number)
            step_results.append(result)

            # Check if step failed
            if result.state == StepState.FAILED:
                self._step_states[idx] = StepState.FAILED.value
                # Mark remaining steps as skipped
                for remaining_idx in range(idx + 1, total_steps):
                    self._step_states[remaining_idx] = StepState.SKIPPED.value

                self._update_heartbeat(step_number, total_steps)

                total_duration = int((time.monotonic() - start_time) * 1000)
                logger.warning(
                    "Task %s failed at step %d (%s): %s",
                    self._task_id,
                    step_number,
                    action,
                    result.error_message,
                )
                return TaskResult(
                    task_id=self._task_id,
                    success=False,
                    failed_step=step_number,
                    step_results=step_results,
                    total_duration_ms=total_duration,
                    error_message=result.error_message,
                )

            # Mark step as completed
            self._step_states[idx] = StepState.COMPLETED.value
            logger.debug(
                "Step %d/%d (%s) completed for task %s",
                step_number,
                total_steps,
                action,
                self._task_id,
            )

        # All steps completed successfully
        total_duration = int((time.monotonic() - start_time) * 1000)
        self._update_heartbeat(total_steps, total_steps)

        logger.info(
            "All %d steps completed successfully for task %s in %dms",
            total_steps,
            self._task_id,
            total_duration,
        )
        return TaskResult(
            task_id=self._task_id,
            success=True,
            step_results=step_results,
            total_duration_ms=total_duration,
        )

    def _execute_step(self, step: Step, step_number: int) -> StepResult:
        """Execute a single step.

        Args:
            step: Step definition to execute.
            step_number: Step number for result tracking.

        Returns:
            StepResult with execution details.
        """
        action = step.get("action", "unknown")
        command = step.get("run", "")
        verify_mode = step.get("verify", StepVerify.EXIT_CODE.value)

        start_time = time.monotonic()

        # If no command, treat as documentation-only step
        if not command:
            logger.debug("Step %d (%s) has no command, skipping execution", step_number, action)
            return StepResult(
                step_number=step_number,
                action=action,
                state=StepState.COMPLETED,
                duration_ms=0,
            )

        try:
            # Execute the command using CommandExecutor
            result = self._executor.execute(
                command,
                timeout=self._default_timeout,
            )

            duration_ms = int((time.monotonic() - start_time) * 1000)
            exit_code = result.exit_code

            # Verify exit code based on verify mode
            verification_passed = self._verify_exit_code(exit_code, verify_mode)

            if verification_passed:
                return StepResult(
                    step_number=step_number,
                    action=action,
                    state=StepState.COMPLETED,
                    exit_code=exit_code,
                    stdout=result.stdout[:10000] if result.stdout else "",  # Limit output size
                    stderr=result.stderr[:10000] if result.stderr else "",
                    duration_ms=duration_ms,
                )
            else:
                error_msg = self._format_verification_error(exit_code, verify_mode, result.stderr)
                return StepResult(
                    step_number=step_number,
                    action=action,
                    state=StepState.FAILED,
                    exit_code=exit_code,
                    stdout=result.stdout[:10000] if result.stdout else "",
                    stderr=result.stderr[:10000] if result.stderr else "",
                    duration_ms=duration_ms,
                    error_message=error_msg,
                )

        except CommandValidationError as e:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            return StepResult(
                step_number=step_number,
                action=action,
                state=StepState.FAILED,
                duration_ms=duration_ms,
                error_message=f"Command validation failed: {e}",
            )

        except Exception as e:  # noqa: BLE001 — intentional: boundary method converts exceptions to StepResult
            duration_ms = int((time.monotonic() - start_time) * 1000)
            logger.exception(f"Step {step_number} execution error: {e}")
            return StepResult(
                step_number=step_number,
                action=action,
                state=StepState.FAILED,
                duration_ms=duration_ms,
                error_message=f"Execution error: {e}",
            )

    def _verify_exit_code(self, exit_code: int, verify_mode: str) -> bool:
        """Verify exit code based on verification mode.

        Args:
            exit_code: The actual exit code from the command.
            verify_mode: The verification mode (exit_code, exit_code_nonzero, none).

        Returns:
            True if verification passed, False otherwise.
        """
        if verify_mode == StepVerify.EXIT_CODE.value:
            # Expect success (exit code 0)
            return exit_code == 0
        elif verify_mode == StepVerify.EXIT_CODE_NONZERO.value:
            # Expect failure (non-zero exit code) - used for "test should fail" scenarios
            return exit_code != 0
        elif verify_mode == StepVerify.NONE.value:
            # No verification - always passes
            return True
        else:
            # Unknown verify mode - treat as exit_code (expect success)
            logger.warning("Unknown verify mode '%s', treating as exit_code", verify_mode)
            return exit_code == 0

    def _format_verification_error(self, exit_code: int, verify_mode: str, stderr: str) -> str:
        """Format verification error message.

        Args:
            exit_code: The actual exit code.
            verify_mode: The expected verification mode.
            stderr: Standard error output.

        Returns:
            Formatted error message.
        """
        if verify_mode == StepVerify.EXIT_CODE.value:
            msg = f"Expected exit code 0 but got {exit_code}"
        elif verify_mode == StepVerify.EXIT_CODE_NONZERO.value:
            msg = f"Expected non-zero exit code but got {exit_code}"
        else:
            msg = f"Verification failed with exit code {exit_code}"

        if stderr:
            # Include first 200 chars of stderr
            stderr_preview = stderr[:200]
            if len(stderr) > 200:
                stderr_preview += "..."
            msg += f": {stderr_preview}"

        return msg

    def _update_heartbeat(self, current_step: int, total_steps: int) -> None:
        """Update heartbeat with current step progress.

        Args:
            current_step: Current step number (1-indexed).
            total_steps: Total number of steps.
        """
        if self._heartbeat_writer is None:
            return

        try:
            self._heartbeat_writer.write(
                task_id=self._task_id,
                step=f"step_{current_step}",
                progress_pct=int((current_step / total_steps) * 100) if total_steps > 0 else 0,
                current_step=current_step,
                total_steps=total_steps,
                step_states=self._step_states.copy(),
            )
        except Exception as e:  # noqa: BLE001 — intentional: heartbeat updates are best-effort, must not fail step execution
            logger.debug("Failed to update heartbeat: %s", e)
