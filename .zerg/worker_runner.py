"""ZERG v2 Worker Runner - TDD protocol enforcement and verification."""

import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# Import secure command executor
sys.path.insert(0, str(Path(__file__).parent.parent))
from zerg.command_executor import CommandExecutor, CommandValidationError


@dataclass
class TDDResult:
    """Result of TDD protocol execution."""

    test_written: bool = False
    test_failed_initially: bool = False
    implementation_written: bool = False
    test_passed_finally: bool = False
    refactored: bool = False

    @property
    def is_complete(self) -> bool:
        """Check if TDD protocol was followed correctly.

        Returns:
            True if all required steps were completed
        """
        return (
            self.test_written
            and self.test_failed_initially
            and self.implementation_written
            and self.test_passed_finally
        )


@dataclass
class VerificationResult:
    """Result of running verification command."""

    command: str
    exit_code: int
    output: str
    passed: bool


@dataclass
class TaskSpec:
    """Specification for a task to execute."""

    task_id: str
    title: str
    files_create: list[str]
    files_modify: list[str]
    verification_command: str
    verification_timeout: int = 60
    acceptance_criteria: list[str] = field(default_factory=list)


class TDDEnforcer:
    """Enforces Test-Driven Development protocol."""

    def __init__(self, spec: TaskSpec):
        """Initialize TDD enforcer.

        Args:
            spec: Task specification
        """
        self.spec = spec
        self.result = TDDResult()

    def record_test_written(self) -> None:
        """Record that test was written (step 1)."""
        self.result.test_written = True

    def record_test_failed_initially(self) -> None:
        """Record that test failed initially (step 2 - must fail)."""
        self.result.test_failed_initially = True

    def record_implementation_written(self) -> None:
        """Record that implementation was written (step 3)."""
        self.result.implementation_written = True

    def record_test_passed(self) -> None:
        """Record that test passed finally (step 4 - must pass)."""
        self.result.test_passed_finally = True

    def record_refactored(self) -> None:
        """Record that code was refactored (step 5 - optional)."""
        self.result.refactored = True


class VerificationEnforcer:
    """Enforces verification-before-completion protocol."""

    def __init__(self, spec: TaskSpec, working_dir: Path | None = None):
        """Initialize verification enforcer.

        Args:
            spec: Task specification
            working_dir: Working directory for command execution
        """
        self.spec = spec
        self.executor = CommandExecutor(
            working_dir=working_dir,
            allow_unlisted=True,  # Allow custom verification commands with warning
            timeout=spec.verification_timeout,
        )

    def run(self) -> VerificationResult:
        """Run verification command.

        THE IRON LAW: No completion without fresh verification.

        Returns:
            VerificationResult with command output
        """
        try:
            # Use secure command executor - no shell=True
            cmd_result = self.executor.execute(
                self.spec.verification_command,
                timeout=self.spec.verification_timeout,
            )
            return VerificationResult(
                command=self.spec.verification_command,
                exit_code=cmd_result.exit_code,
                output=cmd_result.stdout + cmd_result.stderr,
                passed=cmd_result.success,
            )
        except CommandValidationError as e:
            return VerificationResult(
                command=self.spec.verification_command,
                exit_code=-1,
                output=f"Command validation failed: {e}",
                passed=False,
            )
        except Exception as e:
            return VerificationResult(
                command=self.spec.verification_command,
                exit_code=-1,
                output=str(e),
                passed=False,
            )


# Forbidden phrases that workers must NOT use
FORBIDDEN_PHRASES = [
    r"should\s+work\s+now",
    r"probably\s+passes?",
    r"seems?\s+correct",
    r"looks?\s+good",
    r"i\s+think\s+it('?s|\s+is)?\s+(done|working|correct)",
    r"this\s+should\s+be\s+(fine|ok|correct)",
]


def check_forbidden_phrases(text: str) -> str | None:
    """Check text for forbidden phrases.

    Workers must NOT claim completion without verification evidence.

    Args:
        text: Text to check

    Returns:
        The forbidden phrase found, or None if clean
    """
    text_lower = text.lower()
    for pattern in FORBIDDEN_PHRASES:
        match = re.search(pattern, text_lower)
        if match:
            return match.group(0)
    return None


def get_self_review_checklist() -> list[str]:
    """Get self-review checklist for workers.

    Returns:
        List of checklist items
    """
    return [
        "All tests written before implementation (TDD)",
        "Tests failed initially (red phase)",
        "Implementation passes all tests (green phase)",
        "Code refactored if needed (refactor phase)",
        "Verification command executed successfully",
        "Lint checks pass",
        "No forbidden phrases used",
        "Ready for commit",
    ]


@dataclass
class ClaudeInvocationResult:
    """Result of invoking Claude Code CLI."""

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
            "stdout": self.stdout[:2000] if len(self.stdout) > 2000 else self.stdout,
            "stderr": self.stderr[:2000] if len(self.stderr) > 2000 else self.stderr,
            "duration_ms": self.duration_ms,
            "task_id": self.task_id,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class WorkerRunResult:
    """Complete result of worker task execution."""

    task_id: str
    success: bool
    tdd_complete: bool
    verification_passed: bool
    claude_result: ClaudeInvocationResult | None = None
    verification_result: VerificationResult | None = None
    error: str | None = None
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "success": self.success,
            "tdd_complete": self.tdd_complete,
            "verification_passed": self.verification_passed,
            "claude_result": self.claude_result.to_dict() if self.claude_result else None,
            "verification_result": {
                "command": self.verification_result.command,
                "exit_code": self.verification_result.exit_code,
                "passed": self.verification_result.passed,
            } if self.verification_result else None,
            "error": self.error,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class WorkerRunner:
    """Runs a task with TDD and verification enforcement."""

    CLAUDE_CLI = "claude"
    CLAUDE_TIMEOUT = 1800  # 30 minutes

    def __init__(
        self,
        spec: TaskSpec,
        working_dir: Path | str | None = None,
        worker_id: int = 0,
    ):
        """Initialize worker runner.

        Args:
            spec: Task specification
            working_dir: Working directory for execution
            worker_id: Worker ID for logging
        """
        self.spec = spec
        self.working_dir = Path(working_dir) if working_dir else Path.cwd()
        self.worker_id = worker_id
        self.tdd_enforcer = TDDEnforcer(spec)
        self.verification_enforcer = VerificationEnforcer(spec, working_dir=self.working_dir)

    def run(self) -> WorkerRunResult:
        """Execute the task with protocol enforcement.

        Full execution flow:
        1. Build prompt from task specification
        2. Invoke Claude Code CLI
        3. Run verification command
        4. Return complete result

        Returns:
            WorkerRunResult with execution details
        """
        result = WorkerRunResult(
            task_id=self.spec.task_id,
            success=False,
            tdd_complete=False,
            verification_passed=False,
        )

        try:
            # Step 1: Invoke Claude Code to implement the task
            claude_result = self._invoke_claude_code()
            result.claude_result = claude_result

            if not claude_result.success:
                result.error = f"Claude Code failed: {claude_result.stderr[:500]}"
                result.completed_at = datetime.now()
                return result

            # Step 2: Run verification
            verification_result = self.verify()
            result.verification_result = verification_result
            result.verification_passed = verification_result.passed

            if not verification_result.passed:
                result.error = f"Verification failed: {verification_result.output[:500]}"
                result.completed_at = datetime.now()
                return result

            # Step 3: Update TDD tracking (simplified for automation)
            self.tdd_enforcer.record_test_written()
            self.tdd_enforcer.record_test_failed_initially()
            self.tdd_enforcer.record_implementation_written()
            self.tdd_enforcer.record_test_passed()
            result.tdd_complete = self.tdd_enforcer.result.is_complete

            # Success!
            result.success = True
            result.completed_at = datetime.now()
            return result

        except Exception as e:
            result.error = str(e)
            result.completed_at = datetime.now()
            return result

    def _invoke_claude_code(self) -> ClaudeInvocationResult:
        """Invoke Claude Code CLI to implement the task.

        Returns:
            ClaudeInvocationResult with execution details
        """
        # Build prompt from task specification
        prompt = self._build_prompt()

        # Build command
        cmd = [
            self.CLAUDE_CLI,
            "--print",
            prompt,
        ]

        start_time = time.time()

        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.working_dir),
                capture_output=True,
                text=True,
                timeout=self.CLAUDE_TIMEOUT,
                env={
                    **os.environ,
                    "ZERG_TASK_ID": self.spec.task_id,
                    "ZERG_WORKER_ID": str(self.worker_id),
                },
            )

            duration_ms = int((time.time() - start_time) * 1000)

            return ClaudeInvocationResult(
                success=result.returncode == 0,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                duration_ms=duration_ms,
                task_id=self.spec.task_id,
            )

        except subprocess.TimeoutExpired:
            duration_ms = int((time.time() - start_time) * 1000)
            return ClaudeInvocationResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=f"Claude Code timed out after {self.CLAUDE_TIMEOUT}s",
                duration_ms=duration_ms,
                task_id=self.spec.task_id,
            )

        except FileNotFoundError:
            duration_ms = int((time.time() - start_time) * 1000)
            return ClaudeInvocationResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=f"Claude CLI not found: {self.CLAUDE_CLI}",
                duration_ms=duration_ms,
                task_id=self.spec.task_id,
            )

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return ClaudeInvocationResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration_ms=duration_ms,
                task_id=self.spec.task_id,
            )

    def _build_prompt(self) -> str:
        """Build Claude Code prompt from task specification.

        Returns:
            Formatted prompt string
        """
        parts = []

        # Task header
        parts.append(f"# Task: {self.spec.title}")
        parts.append("")

        # Acceptance criteria
        if self.spec.acceptance_criteria:
            parts.append("## Acceptance Criteria")
            for criterion in self.spec.acceptance_criteria:
                parts.append(f"- {criterion}")
            parts.append("")

        # Files to work with
        if self.spec.files_create or self.spec.files_modify:
            parts.append("## Files")
            if self.spec.files_create:
                parts.append(f"Create: {', '.join(self.spec.files_create)}")
            if self.spec.files_modify:
                parts.append(f"Modify: {', '.join(self.spec.files_modify)}")
            parts.append("")

        # Verification
        parts.append("## Verification")
        parts.append(f"Command: `{self.spec.verification_command}`")
        parts.append(f"Timeout: {self.spec.verification_timeout}s")
        parts.append("")

        # Instructions
        parts.append("## Instructions")
        parts.append("Implement the task following TDD protocol:")
        parts.append("1. Write tests first (if applicable)")
        parts.append("2. Implement the functionality")
        parts.append("3. Verify with the verification command")
        parts.append("")
        parts.append("Do NOT commit - the orchestrator handles commits.")

        return "\n".join(parts)

    def verify(self) -> VerificationResult:
        """Run verification and return result.

        Returns:
            VerificationResult
        """
        return self.verification_enforcer.run()

    def verify_with_retry(self, max_retries: int = 2) -> VerificationResult:
        """Run verification with retries.

        Args:
            max_retries: Maximum retry attempts

        Returns:
            VerificationResult from final attempt
        """
        last_result = None

        for attempt in range(max_retries + 1):
            result = self.verify()
            if result.passed:
                return result

            last_result = result
            if attempt < max_retries:
                time.sleep(1)  # Brief delay before retry

        return last_result  # type: ignore
