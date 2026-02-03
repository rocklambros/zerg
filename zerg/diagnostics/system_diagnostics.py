"""System-level diagnostics for ZERG debugging."""

from __future__ import annotations

import shutil
import socket
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from zerg.logging import get_logger

if TYPE_CHECKING:
    from zerg.config import ZergConfig

logger = get_logger("diagnostics.system")

SUBPROCESS_TIMEOUT = 5


@dataclass
class SystemHealthReport:
    """System health report from infrastructure checks."""

    git_clean: bool = True
    git_branch: str = ""
    git_uncommitted_files: int = 0
    disk_free_gb: float = 0.0
    docker_running: bool | None = None
    docker_containers: int | None = None
    port_conflicts: list[int] = field(default_factory=list)
    worktree_count: int = 0
    orphaned_worktrees: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "git_clean": self.git_clean,
            "git_branch": self.git_branch,
            "git_uncommitted_files": self.git_uncommitted_files,
            "disk_free_gb": round(self.disk_free_gb, 2),
            "docker_running": self.docker_running,
            "docker_containers": self.docker_containers,
            "port_conflicts": self.port_conflicts,
            "worktree_count": self.worktree_count,
            "orphaned_worktrees": self.orphaned_worktrees,
        }


class SystemDiagnostics:
    """Run system-level diagnostic checks."""

    def __init__(self, config: ZergConfig | None = None) -> None:
        self.config = config

    def _run_cmd(self, cmd: list[str]) -> tuple[str, bool]:
        """Run a command with timeout, return (stdout, success)."""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=SUBPROCESS_TIMEOUT,
            )
            return result.stdout.strip(), result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            logger.warning(f"Command failed: {cmd!r}: {e}")
            return "", False

    def check_git_state(self) -> dict[str, Any]:
        """Check git working tree state."""
        result: dict[str, Any] = {
            "clean": True,
            "branch": "",
            "uncommitted_files": 0,
        }

        stdout, ok = self._run_cmd(["git", "status", "--porcelain"])
        if ok:
            lines = [ln for ln in stdout.splitlines() if ln.strip()]
            result["uncommitted_files"] = len(lines)
            result["clean"] = len(lines) == 0

        stdout, ok = self._run_cmd(["git", "branch", "--show-current"])
        if ok:
            result["branch"] = stdout.strip()

        return result

    def check_disk_space(self) -> float:
        """Return free disk space in GB."""
        try:
            usage = shutil.disk_usage(".")
            return usage.free / (1024**3)
        except OSError as e:
            logger.warning(f"Failed to check disk space: {e}")
            return 0.0

    def check_docker(self) -> dict[str, Any] | None:
        """Check Docker status. Returns None if docker is not applicable."""
        stdout, ok = self._run_cmd(["docker", "info"])
        if not ok:
            return None

        container_count = 0
        stdout, ok = self._run_cmd(["docker", "ps", "-q"])
        if ok:
            container_count = len([ln for ln in stdout.splitlines() if ln.strip()])

        return {
            "running": True,
            "containers": container_count,
        }

    def check_ports(self, range_start: int = 9500, range_end: int = 9510) -> list[int]:
        """Check for port conflicts in range."""
        conflicts: list[int] = []
        for port in range(range_start, range_end + 1):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(0.5)
                    result = s.connect_ex(("127.0.0.1", port))
                    if result == 0:
                        conflicts.append(port)
            except OSError:
                pass
        return conflicts

    def check_worktrees(self) -> dict[str, Any]:
        """Check git worktrees for orphans."""
        result: dict[str, Any] = {
            "count": 0,
            "orphaned": [],
        }

        stdout, ok = self._run_cmd(["git", "worktree", "list", "--porcelain"])
        if not ok:
            return result

        worktrees: list[str] = []
        current_path = ""
        for line in stdout.splitlines():
            if line.startswith("worktree "):
                current_path = line[len("worktree ") :]
                worktrees.append(current_path)

        result["count"] = len(worktrees)

        # Detect orphaned worktrees (path doesn't exist)
        for wt_path in worktrees:
            if not Path(wt_path).exists():
                result["orphaned"].append(wt_path)

        return result

    def run_all(self) -> SystemHealthReport:
        """Run all system diagnostics and return report."""
        git = self.check_git_state()
        disk_free = self.check_disk_space()
        docker = self.check_docker()
        worktrees = self.check_worktrees()

        # Determine port range from config or defaults
        port_start = 9500
        port_end = 9510
        if self.config:
            try:
                port_start = self.config.ports.range_start
                port_end = min(port_start + 10, self.config.ports.range_end)
            except AttributeError:
                pass

        ports = self.check_ports(port_start, port_end)

        return SystemHealthReport(
            git_clean=git.get("clean", True),
            git_branch=git.get("branch", ""),
            git_uncommitted_files=git.get("uncommitted_files", 0),
            disk_free_gb=disk_free,
            docker_running=docker.get("running") if docker else None,
            docker_containers=docker.get("containers") if docker else None,
            port_conflicts=ports,
            worktree_count=worktrees.get("count", 0),
            orphaned_worktrees=worktrees.get("orphaned", []),
        )
