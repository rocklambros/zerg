"""ZERG v2 Worker Runner - TDD protocol enforcement and verification."""

import re
import subprocess
from dataclasses import dataclass, field


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

    def __init__(self, spec: TaskSpec):
        """Initialize verification enforcer.

        Args:
            spec: Task specification
        """
        self.spec = spec

    def run(self) -> VerificationResult:
        """Run verification command.

        THE IRON LAW: No completion without fresh verification.

        Returns:
            VerificationResult with command output
        """
        try:
            result = subprocess.run(
                self.spec.verification_command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.spec.verification_timeout,
            )
            return VerificationResult(
                command=self.spec.verification_command,
                exit_code=result.returncode,
                output=result.stdout + result.stderr,
                passed=result.returncode == 0,
            )
        except subprocess.TimeoutExpired:
            return VerificationResult(
                command=self.spec.verification_command,
                exit_code=-1,
                output=f"Timeout after {self.spec.verification_timeout}s",
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


class WorkerRunner:
    """Runs a task with TDD and verification enforcement."""

    def __init__(self, spec: TaskSpec):
        """Initialize worker runner.

        Args:
            spec: Task specification
        """
        self.spec = spec
        self.tdd_enforcer = TDDEnforcer(spec)
        self.verification_enforcer = VerificationEnforcer(spec)

    def run(self) -> dict:
        """Execute the task with protocol enforcement.

        Returns:
            Dictionary with execution results
        """
        return {
            "task_id": self.spec.task_id,
            "tdd_complete": self.tdd_enforcer.result.is_complete,
            "verification": None,  # Will be set after verification
        }

    def verify(self) -> VerificationResult:
        """Run verification and return result.

        Returns:
            VerificationResult
        """
        return self.verification_enforcer.run()
