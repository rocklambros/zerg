"""Task verification execution for ZERG."""

import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from zerg.exceptions import TaskTimeoutError, TaskVerificationFailed
from zerg.logging import get_logger
from zerg.types import Task

logger = get_logger("verify")


@dataclass
class VerificationExecutionResult:
    """Full result of a verification execution."""

    task_id: str
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    command: str
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "success": self.success,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration_ms": self.duration_ms,
            "command": self.command,
            "timestamp": self.timestamp.isoformat(),
        }


class VerificationExecutor:
    """Execute task verification commands."""

    def __init__(self, default_timeout: int = 30) -> None:
        """Initialize verification executor.

        Args:
            default_timeout: Default timeout in seconds
        """
        self.default_timeout = default_timeout
        self._results: list[VerificationExecutionResult] = []

    def verify(
        self,
        command: str,
        task_id: str,
        timeout: int | None = None,
        cwd: str | Path | None = None,
        env: dict[str, str] | None = None,
    ) -> VerificationExecutionResult:
        """Run a verification command.

        Args:
            command: Shell command to run
            task_id: Task ID for logging
            timeout: Timeout in seconds
            cwd: Working directory
            env: Environment variables

        Returns:
            VerificationExecutionResult
        """
        timeout = timeout or self.default_timeout
        cwd = Path(cwd) if cwd else Path.cwd()

        logger.info(f"Verifying task {task_id}: {command}")
        start_time = time.time()

        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
            )

            duration_ms = int((time.time() - start_time) * 1000)
            success = result.returncode == 0

            if success:
                logger.info(f"Task {task_id} verification passed ({duration_ms}ms)")
            else:
                logger.warning(f"Task {task_id} verification failed (exit code {result.returncode})")

            exec_result = VerificationExecutionResult(
                task_id=task_id,
                success=success,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                duration_ms=duration_ms,
                command=command,
            )

        except subprocess.TimeoutExpired:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Task {task_id} verification timed out after {timeout}s")

            exec_result = VerificationExecutionResult(
                task_id=task_id,
                success=False,
                exit_code=-1,
                stdout="",
                stderr=f"Verification timed out after {timeout}s",
                duration_ms=duration_ms,
                command=command,
            )

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Task {task_id} verification error: {e}")

            exec_result = VerificationExecutionResult(
                task_id=task_id,
                success=False,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration_ms=duration_ms,
                command=command,
            )

        self._results.append(exec_result)
        return exec_result

    def verify_task(
        self,
        task: Task,
        cwd: str | Path | None = None,
        env: dict[str, str] | None = None,
    ) -> VerificationExecutionResult:
        """Verify a task using its verification spec.

        Args:
            task: Task with verification spec
            cwd: Working directory
            env: Environment variables

        Returns:
            VerificationExecutionResult
        """
        task_id = task.get("id", "unknown")
        verification = task.get("verification")

        if not verification:
            logger.warning(f"Task {task_id} has no verification spec")
            return VerificationExecutionResult(
                task_id=task_id,
                success=True,  # No verification = auto-pass
                exit_code=0,
                stdout="No verification command",
                stderr="",
                duration_ms=0,
                command="",
            )

        command = verification.get("command", "")
        timeout = verification.get("timeout_seconds", self.default_timeout)

        return self.verify(command, task_id, timeout=timeout, cwd=cwd, env=env)

    def verify_with_retry(
        self,
        command: str,
        task_id: str,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        **kwargs: Any,
    ) -> VerificationExecutionResult:
        """Verify with retries on failure.

        Args:
            command: Shell command
            task_id: Task ID
            max_retries: Maximum retry attempts
            retry_delay: Delay between retries in seconds
            **kwargs: Additional arguments for verify()

        Returns:
            VerificationExecutionResult (last attempt)
        """
        last_result = None

        for attempt in range(max_retries):
            result = self.verify(command, task_id, **kwargs)

            if result.success:
                return result

            last_result = result
            if attempt < max_retries - 1:
                logger.info(f"Retry {attempt + 1}/{max_retries} for task {task_id}")
                time.sleep(retry_delay)

        return last_result  # type: ignore

    def check_result(
        self,
        result: VerificationExecutionResult,
        raise_on_failure: bool = True,
    ) -> bool:
        """Check verification result and optionally raise on failure.

        Args:
            result: Verification result
            raise_on_failure: Raise exception on failure

        Returns:
            True if verification passed

        Raises:
            TaskVerificationFailed: If verification failed
            TaskTimeoutError: If verification timed out
        """
        if result.success:
            return True

        if not raise_on_failure:
            return False

        if "timed out" in result.stderr.lower():
            raise TaskTimeoutError(
                f"Task {result.task_id} verification timed out",
                task_id=result.task_id,
                timeout_seconds=result.duration_ms // 1000,
            )

        raise TaskVerificationFailed(
            f"Task {result.task_id} verification failed",
            task_id=result.task_id,
            command=result.command,
            exit_code=result.exit_code,
            stdout=result.stdout,
            stderr=result.stderr,
        )

    def get_results(self) -> list[VerificationExecutionResult]:
        """Get all verification results.

        Returns:
            List of VerificationExecutionResult
        """
        return self._results.copy()

    def get_results_for_task(self, task_id: str) -> list[VerificationExecutionResult]:
        """Get verification results for a specific task.

        Args:
            task_id: Task ID

        Returns:
            List of results for the task
        """
        return [r for r in self._results if r.task_id == task_id]

    def clear_results(self) -> None:
        """Clear stored results."""
        self._results.clear()

    def get_summary(self) -> dict[str, Any]:
        """Get summary of verification results.

        Returns:
            Summary dictionary
        """
        passed = sum(1 for r in self._results if r.success)
        failed = len(self._results) - passed

        return {
            "total": len(self._results),
            "passed": passed,
            "failed": failed,
            "pass_rate": (passed / len(self._results) * 100) if self._results else 0,
        }
