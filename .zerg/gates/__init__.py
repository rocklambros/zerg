"""ZERG v2 Quality Gates - Two-stage quality verification."""

import shlex
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Import secure command executor
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from zerg.command_executor import CommandExecutor, CommandValidationError


@dataclass
class CheckResult:
    """Result of a single check."""

    passed: bool
    issues: list[str] = field(default_factory=list)


@dataclass
class GateResult:
    """Result of a quality gate stage."""

    stage: int
    passed: bool
    failures: list[str] = field(default_factory=list)

    def summary(self) -> str:
        """Generate summary string."""
        status = "PASSED" if self.passed else "FAILED"
        result = f"Stage {self.stage}: {status}"
        if self.failures:
            result += f" ({len(self.failures)} issues)"
        return result


@dataclass
class QualityConfig:
    """Configuration for quality gates."""

    coverage_threshold: int = 70
    complexity_threshold: int = 10
    run_security_scan: bool = False
    lint_command: str = "ruff check"
    coverage_command: str = "python -m pytest --cov"


class SpecComplianceGate:
    """Stage 1: Verify implementation matches spec."""

    def run(self, level: int, tasks: list) -> GateResult:
        """Run all spec compliance checks.

        Args:
            level: Current level number
            tasks: Tasks completed in this level

        Returns:
            GateResult with pass/fail and any failures
        """
        checks = [
            self._check_requirements_met,
            self._check_acceptance_criteria,
            self._check_file_ownership,
            self._check_dependencies_respected,
        ]

        failures = []
        for check in checks:
            result = check(level, tasks)
            if not result.passed:
                failures.extend(result.issues)

        return GateResult(stage=1, passed=len(failures) == 0, failures=failures)

    def _check_requirements_met(self, level: int, tasks: list) -> CheckResult:
        """Check that all tasks completed successfully."""
        issues = []
        for task in tasks:
            status = getattr(task, "status", "pending")
            if status not in ("completed", "verified"):
                issues.append(f"Task {task.id} not completed (status: {status})")
        return CheckResult(passed=len(issues) == 0, issues=issues)

    def _check_acceptance_criteria(self, level: int, tasks: list) -> CheckResult:
        """Check that acceptance criteria are defined."""
        issues = []
        for task in tasks:
            criteria = getattr(task, "acceptance_criteria", [])
            if not criteria:
                issues.append(f"Task {task.id} missing acceptance criteria")
        return CheckResult(passed=len(issues) == 0, issues=issues)

    def _check_file_ownership(self, level: int, tasks: list) -> CheckResult:
        """Check for file ownership conflicts."""
        issues = []
        file_owners: dict[str, str] = {}

        for task in tasks:
            files = getattr(task, "files", None)
            if not files:
                continue

            created = getattr(files, "create", []) or []
            modified = getattr(files, "modify", []) or []

            for f in created + modified:
                if f in file_owners:
                    issues.append(
                        f"File conflict: {f} owned by both {file_owners[f]} and {task.id}"
                    )
                else:
                    file_owners[f] = task.id

        return CheckResult(passed=len(issues) == 0, issues=issues)

    def _check_dependencies_respected(self, level: int, tasks: list) -> CheckResult:
        """Check that task dependencies are respected.

        Note: Dependencies from earlier levels are assumed complete.
        Within-level dependencies are validated during execution.
        """
        # Currently a pass-through check - dependencies validated at execution time
        return CheckResult(passed=True, issues=[])


class CodeQualityGate:
    """Stage 2: Verify code quality standards."""

    def __init__(self, config: QualityConfig | None = None):
        """Initialize with optional config."""
        self.config = config or QualityConfig()
        self._executor = CommandExecutor(
            allow_unlisted=True,  # Allow lint commands
            timeout=60,
        )

    def run(self, level: int, changed_files: list[str]) -> GateResult:
        """Run all code quality checks.

        Args:
            level: Current level number
            changed_files: Files changed in this level

        Returns:
            GateResult with pass/fail and any failures
        """
        checks = [
            self._run_linter,
            self._check_coverage,
        ]

        if self.config.run_security_scan:
            checks.append(self._run_security_scan)

        failures = []
        for check in checks:
            result = check(changed_files)
            if not result.passed:
                failures.extend(result.issues)

        return GateResult(stage=2, passed=len(failures) == 0, failures=failures)

    def _run_linter(self, files: list[str]) -> CheckResult:
        """Run linter on changed files."""
        if not files:
            return CheckResult(passed=True, issues=[])

        try:
            # Sanitize file paths to prevent injection
            sanitized_files = self._executor.sanitize_paths(files)
            # Build command as list to avoid shell injection
            cmd_parts = shlex.split(self.config.lint_command)
            cmd_parts.extend(sanitized_files)

            # Use secure command executor - no shell=True
            result = self._executor.execute(cmd_parts, timeout=60)

            if not result.success:
                return CheckResult(
                    passed=False, issues=[f"Lint failed: {result.stdout or result.stderr}"]
                )
            return CheckResult(passed=True, issues=[])
        except CommandValidationError as e:
            return CheckResult(passed=False, issues=[f"Command validation failed: {e}"])
        except Exception as e:
            return CheckResult(passed=False, issues=[f"Lint error: {e}"])

    def _check_coverage(self, files: list[str]) -> CheckResult:
        """Check coverage threshold."""
        # Without actual coverage data, pass by default
        # Real implementation would parse coverage report
        return CheckResult(passed=True, issues=[])

    def _run_security_scan(self, files: list[str]) -> CheckResult:
        """Run security scan on changed files."""
        # Placeholder - real implementation would use semgrep/bandit
        return CheckResult(passed=True, issues=[])


class GateRunner:
    """Orchestrator for running quality gates."""

    def __init__(
        self,
        spec_gate: SpecComplianceGate | None = None,
        quality_gate: CodeQualityGate | None = None,
    ):
        """Initialize gate runner."""
        self.spec_gate = spec_gate or SpecComplianceGate()
        self.quality_gate = quality_gate or CodeQualityGate()

    def run_stage1(self, level: int, tasks: list) -> GateResult:
        """Run stage 1 (spec compliance) only."""
        return self.spec_gate.run(level, tasks)

    def run_stage2(self, level: int, changed_files: list[str]) -> GateResult:
        """Run stage 2 (code quality) only."""
        return self.quality_gate.run(level, changed_files)

    def run_all(
        self,
        level: int,
        tasks: list,
        changed_files: list[str],
        stop_on_failure: bool = False,
    ) -> list[GateResult]:
        """Run both stages.

        Args:
            level: Current level number
            tasks: Tasks completed in this level
            changed_files: Files changed in this level
            stop_on_failure: Stop after stage 1 if it fails

        Returns:
            List of GateResults for each stage
        """
        results = []

        stage1_result = self.run_stage1(level, tasks)
        results.append(stage1_result)

        if stop_on_failure and not stage1_result.passed:
            return results

        stage2_result = self.run_stage2(level, changed_files)
        results.append(stage2_result)

        return results


# Convenience functions for quick access
def run_spec_compliance(level: int, tasks: list) -> GateResult:
    """Run spec compliance gate."""
    return SpecComplianceGate().run(level, tasks)


def run_code_quality(level: int, changed_files: list[str]) -> GateResult:
    """Run code quality gate."""
    return CodeQualityGate().run(level, changed_files)


__all__ = [
    "CheckResult",
    "GateResult",
    "QualityConfig",
    "SpecComplianceGate",
    "CodeQualityGate",
    "GateRunner",
    "run_spec_compliance",
    "run_code_quality",
]
