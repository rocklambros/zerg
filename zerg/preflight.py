"""Pre-flight checks for ZERG rush execution.

Validates environment readiness before launching workers:
Docker image availability, authentication, port availability,
git worktree support, and disk space.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from zerg.logging import get_logger

logger = get_logger("preflight")


@dataclass
class CheckResult:
    """Result of a single pre-flight check."""

    name: str
    passed: bool
    message: str
    severity: str = "error"  # error | warning


@dataclass
class PreflightReport:
    """Aggregate results of all pre-flight checks."""

    checks: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """All error-severity checks passed."""
        return all(c.passed for c in self.checks if c.severity == "error")

    @property
    def errors(self) -> list[CheckResult]:
        return [c for c in self.checks if not c.passed and c.severity == "error"]

    @property
    def warnings(self) -> list[CheckResult]:
        return [c for c in self.checks if not c.passed and c.severity == "warning"]

    def __str__(self) -> str:
        lines = []
        for c in self.checks:
            symbol = "PASS" if c.passed else "FAIL"
            lines.append(f"[{symbol}] {c.name}: {c.message}")
        return "\n".join(lines)


class PreflightChecker:
    """Run pre-flight checks before a rush."""

    def __init__(
        self,
        mode: str = "auto",
        worker_count: int = 5,
        repo_path: str | Path = ".",
        port_range_start: int = 7860,
        port_range_end: int = 7960,
        min_disk_gb: float = 1.0,
        docker_image: str = "zerg-worker:latest",
    ) -> None:
        self.mode = mode
        self.worker_count = worker_count
        self.repo_path = Path(repo_path)
        self.port_range_start = port_range_start
        self.port_range_end = port_range_end
        self.min_disk_gb = min_disk_gb
        self.docker_image = docker_image

    def run_all(self) -> PreflightReport:
        """Run all applicable pre-flight checks."""
        report = PreflightReport()

        report.checks.append(self.check_disk_space())
        report.checks.append(self.check_git_repo())

        if self.mode in ("container", "auto"):
            report.checks.append(self.check_docker_available())
            report.checks.append(self.check_docker_image())
            report.checks.append(self.check_auth())

        report.checks.append(self.check_ports())
        report.checks.append(self.check_worktree_feasibility())

        return report

    def check_docker_available(self) -> CheckResult:
        """Check that Docker daemon is reachable."""
        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                timeout=10,
            )
            if result.returncode == 0:
                return CheckResult(
                    name="Docker daemon",
                    passed=True,
                    message="Docker is running",
                )
            return CheckResult(
                name="Docker daemon",
                passed=False,
                message="Docker daemon not responding",
            )
        except FileNotFoundError:
            return CheckResult(
                name="Docker daemon",
                passed=False,
                message="Docker CLI not found on PATH",
            )
        except subprocess.TimeoutExpired:
            return CheckResult(
                name="Docker daemon",
                passed=False,
                message="Docker info timed out",
            )

    def check_docker_image(self) -> CheckResult:
        """Check that the worker Docker image exists locally."""
        try:
            result = subprocess.run(
                ["docker", "image", "inspect", self.docker_image],
                capture_output=True,
                timeout=10,
            )
            if result.returncode == 0:
                return CheckResult(
                    name="Docker image",
                    passed=True,
                    message=f"Image '{self.docker_image}' found",
                )
            return CheckResult(
                name="Docker image",
                passed=False,
                message=f"Image '{self.docker_image}' not found locally",
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return CheckResult(
                name="Docker image",
                passed=False,
                message="Could not inspect Docker image",
            )

    def check_auth(self) -> CheckResult:
        """Check that worker authentication is available.

        Two methods: ANTHROPIC_API_KEY env var OR ~/.claude credentials.
        """
        has_api_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
        claude_dir = Path.home() / ".claude"
        has_claude_dir = claude_dir.is_dir()

        if has_api_key:
            return CheckResult(
                name="Authentication",
                passed=True,
                message="ANTHROPIC_API_KEY is set",
            )
        if has_claude_dir:
            return CheckResult(
                name="Authentication",
                passed=True,
                message="~/.claude directory found (OAuth)",
            )
        return CheckResult(
            name="Authentication",
            passed=False,
            message="No ANTHROPIC_API_KEY and no ~/.claude directory",
        )

    def check_ports(self) -> CheckResult:
        """Check that enough ports are available in the configured range."""
        needed = self.worker_count
        available = 0

        for port in range(self.port_range_start, self.port_range_end):
            if available >= needed:
                break
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(0.1)
                    s.bind(("127.0.0.1", port))
                    available += 1
            except OSError:
                continue

        if available >= needed:
            return CheckResult(
                name="Port availability",
                passed=True,
                message=f"{available} ports available (need {needed})",
            )
        return CheckResult(
            name="Port availability",
            passed=False,
            message=(
                f"Only {available}/{needed} ports available in range {self.port_range_start}-{self.port_range_end}"
            ),
        )

    def check_worktree_feasibility(self) -> CheckResult:
        """Check that git worktrees can be created for workers."""
        git_dir = self.repo_path / ".git"
        if not git_dir.exists():
            return CheckResult(
                name="Git worktree",
                passed=False,
                message="Not a git repository",
                severity="warning",
            )

        try:
            result = subprocess.run(
                ["git", "worktree", "list"],
                capture_output=True,
                cwd=self.repo_path,
                timeout=5,
            )
            if result.returncode == 0:
                return CheckResult(
                    name="Git worktree",
                    passed=True,
                    message=f"Git worktree supported ({self.worker_count} workers)",
                )
            return CheckResult(
                name="Git worktree",
                passed=False,
                message="Git worktree command failed",
                severity="warning",
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return CheckResult(
                name="Git worktree",
                passed=False,
                message="Could not verify git worktree support",
                severity="warning",
            )

    def check_disk_space(self) -> CheckResult:
        """Check that sufficient disk space is available."""
        try:
            usage = shutil.disk_usage(str(self.repo_path))
            free_gb = usage.free / (1024**3)
            if free_gb >= self.min_disk_gb:
                return CheckResult(
                    name="Disk space",
                    passed=True,
                    message=f"{free_gb:.1f} GB free",
                )
            return CheckResult(
                name="Disk space",
                passed=False,
                message=f"{free_gb:.1f} GB free (need {self.min_disk_gb} GB)",
            )
        except OSError as e:
            return CheckResult(
                name="Disk space",
                passed=False,
                message=f"Could not check disk space: {e}",
            )

    def check_git_repo(self) -> CheckResult:
        """Check that we're in a git repository."""
        if (self.repo_path / ".git").exists():
            return CheckResult(
                name="Git repository",
                passed=True,
                message="Git repository detected",
            )
        return CheckResult(
            name="Git repository",
            passed=False,
            message="No .git directory found",
        )
