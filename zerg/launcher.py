"""ZERG worker launcher abstraction.

Provides pluggable launcher backends for spawning and managing worker processes.
"""

import os
import subprocess
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from zerg.constants import WorkerStatus
from zerg.logging import get_logger

logger = get_logger("launcher")


class LauncherType(Enum):
    """Worker launcher backend types."""

    SUBPROCESS = "subprocess"
    CONTAINER = "container"


@dataclass
class LauncherConfig:
    """Configuration for worker launcher."""

    launcher_type: LauncherType = LauncherType.SUBPROCESS
    timeout_seconds: int = 3600
    env_vars: dict[str, str] = field(default_factory=dict)
    working_dir: Path | None = None
    log_dir: Path | None = None


@dataclass
class SpawnResult:
    """Result of spawning a worker."""

    success: bool
    worker_id: int
    handle: "WorkerHandle | None" = None
    error: str | None = None


@dataclass
class WorkerHandle:
    """Handle to a running worker process."""

    worker_id: int
    pid: int | None = None
    container_id: str | None = None
    status: WorkerStatus = WorkerStatus.INITIALIZING
    started_at: datetime = field(default_factory=datetime.now)
    exit_code: int | None = None

    def is_alive(self) -> bool:
        """Check if worker is still running."""
        return self.status in (
            WorkerStatus.INITIALIZING,
            WorkerStatus.READY,
            WorkerStatus.RUNNING,
            WorkerStatus.IDLE,
            WorkerStatus.CHECKPOINTING,
        )


class WorkerLauncher(ABC):
    """Abstract base class for worker launchers.

    Defines the interface for spawning, monitoring, and terminating workers.
    Implementations can use subprocess, container, or other backends.
    """

    def __init__(self, config: LauncherConfig | None = None) -> None:
        """Initialize launcher.

        Args:
            config: Launcher configuration
        """
        self.config = config or LauncherConfig()
        self._workers: dict[int, WorkerHandle] = {}

    @abstractmethod
    def spawn(
        self,
        worker_id: int,
        feature: str,
        worktree_path: Path,
        branch: str,
        env: dict[str, str] | None = None,
    ) -> SpawnResult:
        """Spawn a new worker process.

        Args:
            worker_id: Unique worker identifier
            feature: Feature name being worked on
            worktree_path: Path to worker's git worktree
            branch: Git branch for worker
            env: Additional environment variables

        Returns:
            SpawnResult with handle or error
        """
        pass

    @abstractmethod
    def monitor(self, worker_id: int) -> WorkerStatus:
        """Check worker status.

        Args:
            worker_id: Worker to check

        Returns:
            Current worker status
        """
        pass

    @abstractmethod
    def terminate(self, worker_id: int, force: bool = False) -> bool:
        """Terminate a worker.

        Args:
            worker_id: Worker to terminate
            force: Force termination without graceful shutdown

        Returns:
            True if termination succeeded
        """
        pass

    @abstractmethod
    def get_output(self, worker_id: int, tail: int = 100) -> str:
        """Get worker output/logs.

        Args:
            worker_id: Worker to get output from
            tail: Number of lines from end

        Returns:
            Output string
        """
        pass

    def get_handle(self, worker_id: int) -> WorkerHandle | None:
        """Get handle for a worker.

        Args:
            worker_id: Worker identifier

        Returns:
            WorkerHandle or None if not found
        """
        return self._workers.get(worker_id)

    def get_all_workers(self) -> dict[int, WorkerHandle]:
        """Get all worker handles.

        Returns:
            Dictionary of worker_id to WorkerHandle
        """
        return self._workers.copy()

    def terminate_all(self, force: bool = False) -> dict[int, bool]:
        """Terminate all workers.

        Args:
            force: Force termination

        Returns:
            Dictionary of worker_id to success status
        """
        results = {}
        for worker_id in list(self._workers.keys()):
            results[worker_id] = self.terminate(worker_id, force=force)
        return results

    def get_status_summary(self) -> dict[str, Any]:
        """Get summary of all worker statuses.

        Returns:
            Summary dictionary
        """
        by_status: dict[str, int] = {}
        for handle in self._workers.values():
            status_name = handle.status.value
            by_status[status_name] = by_status.get(status_name, 0) + 1

        return {
            "total": len(self._workers),
            "by_status": by_status,
            "alive": sum(1 for h in self._workers.values() if h.is_alive()),
        }


class SubprocessLauncher(WorkerLauncher):
    """Launch workers as subprocess instances.

    Uses subprocess.Popen to spawn worker processes running zerg.worker_main.
    Suitable for local development and testing.
    """

    def __init__(self, config: LauncherConfig | None = None) -> None:
        """Initialize subprocess launcher.

        Args:
            config: Launcher configuration
        """
        super().__init__(config)
        self._processes: dict[int, subprocess.Popen[bytes]] = {}
        self._output_buffers: dict[int, list[str]] = {}

    def spawn(
        self,
        worker_id: int,
        feature: str,
        worktree_path: Path,
        branch: str,
        env: dict[str, str] | None = None,
    ) -> SpawnResult:
        """Spawn a new worker subprocess.

        Args:
            worker_id: Unique worker identifier
            feature: Feature name being worked on
            worktree_path: Path to worker's git worktree
            branch: Git branch for worker
            env: Additional environment variables

        Returns:
            SpawnResult with handle or error
        """
        try:
            # Build environment
            worker_env = os.environ.copy()
            worker_env.update({
                "ZERG_WORKER_ID": str(worker_id),
                "ZERG_FEATURE": feature,
                "ZERG_WORKTREE": str(worktree_path),
                "ZERG_BRANCH": branch,
            })
            if self.config.env_vars:
                worker_env.update(self.config.env_vars)
            if env:
                worker_env.update(env)

            # Build command
            cmd = [
                sys.executable,
                "-m", "zerg.worker_main",
                "--worker-id", str(worker_id),
                "--feature", feature,
                "--worktree", str(worktree_path),
                "--branch", branch,
            ]

            # Set working directory
            cwd = self.config.working_dir or worktree_path

            # Set up log file if configured
            stdout_file = None
            stderr_file = None
            if self.config.log_dir:
                self.config.log_dir.mkdir(parents=True, exist_ok=True)
                stdout_file = open(self.config.log_dir / f"worker-{worker_id}.stdout.log", "w")
                stderr_file = open(self.config.log_dir / f"worker-{worker_id}.stderr.log", "w")

            # Spawn process
            process = subprocess.Popen(
                cmd,
                env=worker_env,
                cwd=cwd,
                stdout=stdout_file or subprocess.PIPE,
                stderr=stderr_file or subprocess.PIPE,
            )

            # Create handle
            handle = WorkerHandle(
                worker_id=worker_id,
                pid=process.pid,
                status=WorkerStatus.INITIALIZING,
            )

            # Store references
            self._workers[worker_id] = handle
            self._processes[worker_id] = process
            self._output_buffers[worker_id] = []

            logger.info(f"Spawned worker {worker_id} with PID {process.pid}")
            return SpawnResult(success=True, worker_id=worker_id, handle=handle)

        except Exception as e:
            logger.error(f"Failed to spawn worker {worker_id}: {e}")
            return SpawnResult(success=False, worker_id=worker_id, error=str(e))

    def monitor(self, worker_id: int) -> WorkerStatus:
        """Check worker subprocess status.

        Args:
            worker_id: Worker to check

        Returns:
            Current worker status
        """
        handle = self._workers.get(worker_id)
        process = self._processes.get(worker_id)

        if not handle or not process:
            return WorkerStatus.STOPPED

        # Check if process is still running
        poll_result = process.poll()

        if poll_result is None:
            # Still running
            if handle.status == WorkerStatus.INITIALIZING:
                handle.status = WorkerStatus.RUNNING
            return handle.status

        # Process has exited
        handle.exit_code = poll_result

        if poll_result == 0:
            handle.status = WorkerStatus.STOPPED
        elif poll_result == 2:  # CHECKPOINT exit code
            handle.status = WorkerStatus.CHECKPOINTING
        elif poll_result == 3:  # BLOCKED exit code
            handle.status = WorkerStatus.BLOCKED
        else:
            handle.status = WorkerStatus.CRASHED

        return handle.status

    def terminate(self, worker_id: int, force: bool = False) -> bool:
        """Terminate a worker subprocess.

        Args:
            worker_id: Worker to terminate
            force: Force termination with SIGKILL

        Returns:
            True if termination succeeded
        """
        process = self._processes.get(worker_id)
        handle = self._workers.get(worker_id)

        if not process or not handle:
            return False

        try:
            if force:
                process.kill()
            else:
                process.terminate()

            # Wait for process to end (with timeout)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()

            handle.status = WorkerStatus.STOPPED
            handle.exit_code = process.returncode

            logger.info(f"Terminated worker {worker_id} (exit code: {handle.exit_code})")
            return True

        except Exception as e:
            logger.error(f"Failed to terminate worker {worker_id}: {e}")
            return False

        finally:
            # Clean up references
            if worker_id in self._processes:
                del self._processes[worker_id]

    def get_output(self, worker_id: int, tail: int = 100) -> str:
        """Get worker subprocess output.

        Args:
            worker_id: Worker to get output from
            tail: Number of lines from end

        Returns:
            Output string
        """
        # Try to read from log file first
        if self.config.log_dir:
            log_file = self.config.log_dir / f"worker-{worker_id}.stdout.log"
            if log_file.exists():
                lines = log_file.read_text().splitlines()
                return "\n".join(lines[-tail:])

        # Fall back to buffer
        buffer = self._output_buffers.get(worker_id, [])
        return "\n".join(buffer[-tail:])

    def wait_for_ready(self, worker_id: int, timeout: float = 30.0) -> bool:
        """Wait for worker to signal ready.

        Args:
            worker_id: Worker to wait for
            timeout: Maximum wait time in seconds

        Returns:
            True if worker became ready
        """
        import time

        start = time.time()
        while time.time() - start < timeout:
            status = self.monitor(worker_id)
            if status in (WorkerStatus.RUNNING, WorkerStatus.READY):
                return True
            if status in (WorkerStatus.CRASHED, WorkerStatus.STOPPED):
                return False
            time.sleep(0.5)
        return False

    def wait_all(self, timeout: float | None = None) -> dict[int, WorkerStatus]:
        """Wait for all workers to exit.

        Args:
            timeout: Maximum wait time in seconds

        Returns:
            Final status of all workers
        """
        import time

        start = time.time()
        while True:
            # Check if any still running
            all_done = True
            for worker_id in self._workers:
                status = self.monitor(worker_id)
                if status in (WorkerStatus.RUNNING, WorkerStatus.INITIALIZING, WorkerStatus.READY):
                    all_done = False
                    break

            if all_done:
                break

            if timeout and (time.time() - start > timeout):
                break

            time.sleep(1)

        return {wid: h.status for wid, h in self._workers.items()}
