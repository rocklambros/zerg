"""SubprocessLauncher for spawning workers as local subprocesses.

Extracted from zerg/launcher.py. Uses subprocess.Popen to spawn worker
processes running zerg.worker_main. Suitable for local development and testing.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zerg.heartbeat import HeartbeatMonitor

from zerg.constants import LOGS_TASKS_DIR, LOGS_WORKERS_DIR, WorkerStatus
from zerg.env_validator import validate_env_vars
from zerg.launcher_types import LauncherConfig, SpawnResult, WorkerHandle
from zerg.launchers.base import WorkerLauncher
from zerg.logging import get_logger

logger = get_logger("launcher")


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
        # FR-4: Cache HeartbeatMonitor instance instead of creating per-call
        self._heartbeat_monitor: HeartbeatMonitor | None = None

    @property
    def heartbeat_monitor(self) -> HeartbeatMonitor:
        """Lazy singleton for HeartbeatMonitor (FR-4)."""
        if self._heartbeat_monitor is None:
            from zerg.heartbeat import HeartbeatMonitor

            self._heartbeat_monitor = HeartbeatMonitor()
        return self._heartbeat_monitor

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
            # Build environment with ZERG-specific vars (always allowed)
            # Use current directory as main repo path (workers run in worktrees)
            repo_path = Path.cwd().resolve()
            worker_env = os.environ.copy()
            log_dir = repo_path / LOGS_WORKERS_DIR.rsplit("/", 1)[0]  # .zerg/logs
            worker_env.update(
                {
                    "ZERG_WORKER_ID": str(worker_id),
                    "ZERG_FEATURE": feature,
                    "ZERG_WORKTREE": str(worktree_path),
                    "ZERG_BRANCH": branch,
                    "ZERG_SPEC_DIR": str(worktree_path / ".gsd" / "specs" / feature),
                    "ZERG_STATE_DIR": str(repo_path / ".zerg" / "state"),
                    "ZERG_REPO_PATH": str(repo_path),
                    "ZERG_LOG_DIR": str(log_dir),
                }
            )

            # Cross-session task list coordination
            task_list_id = os.environ.get("CLAUDE_CODE_TASK_LIST_ID")
            if task_list_id:
                worker_env.setdefault("CLAUDE_CODE_TASK_LIST_ID", task_list_id)

            # Ensure structured log directories exist
            (repo_path / LOGS_WORKERS_DIR).mkdir(parents=True, exist_ok=True)
            (repo_path / LOGS_TASKS_DIR).mkdir(parents=True, exist_ok=True)
            # Validate additional env vars from config
            if self.config.env_vars:
                validated_config_env = validate_env_vars(self.config.env_vars)
                worker_env.update(validated_config_env)
            # Validate additional env vars from caller
            if env:
                validated_env = validate_env_vars(env)
                worker_env.update(validated_env)

            # Build command
            cmd = [
                sys.executable,
                "-m",
                "zerg.worker_main",
                "--worker-id",
                str(worker_id),
                "--feature",
                feature,
                "--worktree",
                str(worktree_path),
                "--branch",
                branch,
            ]

            # Set working directory
            cwd = self.config.working_dir or worktree_path

            # Set up log file if configured
            stdout_file = None
            stderr_file = None
            if self.config.log_dir:
                # Validate worker_id is an integer to prevent path injection
                if not isinstance(worker_id, int) or worker_id < 0:
                    raise ValueError(f"Invalid worker_id: {worker_id}")
                self.config.log_dir.mkdir(parents=True, exist_ok=True)
                # Use safe integer formatting for log file names
                stdout_path = self.config.log_dir / f"worker-{int(worker_id)}.stdout.log"
                stderr_path = self.config.log_dir / f"worker-{int(worker_id)}.stderr.log"
                stdout_file = stdout_path.open("w")  # noqa: SIM115
                stderr_file = stderr_path.open("w")  # noqa: SIM115

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

        except (OSError, subprocess.SubprocessError, ValueError) as e:
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
            # Check heartbeat for stall detection
            # FR-4: Use cached HeartbeatMonitor instance
            if handle.status == WorkerStatus.RUNNING:
                hb = self.heartbeat_monitor.read(worker_id)
                if hb and hb.is_stale(120):  # default stall timeout
                    handle.status = WorkerStatus.STALLED
            return handle.status

        # Process has exited
        handle.exit_code = poll_result

        if poll_result == 0:
            handle.status = WorkerStatus.STOPPED
        elif poll_result == 2:  # CHECKPOINT exit code
            handle.status = WorkerStatus.CHECKPOINTING
        elif poll_result == 3:  # BLOCKED exit code
            handle.status = WorkerStatus.BLOCKED
        elif poll_result == 4:  # ESCALATION exit code
            handle.status = WorkerStatus.STOPPED
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

        except (OSError, subprocess.SubprocessError) as e:
            logger.error(f"Failed to terminate worker {worker_id}: {e}")
            return False

        finally:
            # Clean up references
            if worker_id in self._processes:
                del self._processes[worker_id]
            # Also remove from worker handles to prevent stale state
            if worker_id in self._workers:
                del self._workers[worker_id]

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

    async def spawn_async(
        self,
        worker_id: int,
        feature: str,
        worktree_path: Path,
        branch: str,
        env: dict[str, str] | None = None,
    ) -> SpawnResult:
        """Spawn a new worker subprocess asynchronously.

        Uses asyncio.create_subprocess_exec() instead of subprocess.Popen
        for non-blocking process creation.

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
            # Build environment with ZERG-specific vars
            repo_path = Path.cwd().resolve()
            worker_env = os.environ.copy()
            log_dir = repo_path / LOGS_WORKERS_DIR.rsplit("/", 1)[0]
            worker_env.update(
                {
                    "ZERG_WORKER_ID": str(worker_id),
                    "ZERG_FEATURE": feature,
                    "ZERG_WORKTREE": str(worktree_path),
                    "ZERG_BRANCH": branch,
                    "ZERG_SPEC_DIR": str(worktree_path / ".gsd" / "specs" / feature),
                    "ZERG_STATE_DIR": str(repo_path / ".zerg" / "state"),
                    "ZERG_REPO_PATH": str(repo_path),
                    "ZERG_LOG_DIR": str(log_dir),
                }
            )

            # Cross-session task list coordination
            task_list_id = os.environ.get("CLAUDE_CODE_TASK_LIST_ID")
            if task_list_id:
                worker_env.setdefault("CLAUDE_CODE_TASK_LIST_ID", task_list_id)

            # Ensure structured log directories exist
            (repo_path / LOGS_WORKERS_DIR).mkdir(parents=True, exist_ok=True)
            (repo_path / LOGS_TASKS_DIR).mkdir(parents=True, exist_ok=True)

            # Validate additional env vars from config
            if self.config.env_vars:
                validated_config_env = validate_env_vars(self.config.env_vars)
                worker_env.update(validated_config_env)
            # Validate additional env vars from caller
            if env:
                validated_env = validate_env_vars(env)
                worker_env.update(validated_env)

            # Build command arguments (first element is the program)
            program = sys.executable
            args = [
                "-m",
                "zerg.worker_main",
                "--worker-id",
                str(worker_id),
                "--feature",
                feature,
                "--worktree",
                str(worktree_path),
                "--branch",
                branch,
            ]

            # Set working directory
            cwd = str(self.config.working_dir or worktree_path)

            # Set up log file if configured
            stdout_target: int | None = asyncio.subprocess.PIPE
            stderr_target: int | None = asyncio.subprocess.PIPE
            stdout_file = None
            stderr_file = None
            if self.config.log_dir:
                if not isinstance(worker_id, int) or worker_id < 0:
                    raise ValueError(f"Invalid worker_id: {worker_id}")
                self.config.log_dir.mkdir(parents=True, exist_ok=True)
                stdout_path = self.config.log_dir / f"worker-{int(worker_id)}.stdout.log"
                stderr_path = self.config.log_dir / f"worker-{int(worker_id)}.stderr.log"
                stdout_file = stdout_path.open("w")  # noqa: SIM115
                stderr_file = stderr_path.open("w")  # noqa: SIM115
                stdout_target = stdout_file.fileno()
                stderr_target = stderr_file.fileno()

            # Spawn process asynchronously
            process = await asyncio.create_subprocess_exec(
                program,
                *args,
                env=worker_env,
                cwd=cwd,
                stdout=stdout_target,
                stderr=stderr_target,
            )

            # Create handle
            handle = WorkerHandle(
                worker_id=worker_id,
                pid=process.pid,
                status=WorkerStatus.INITIALIZING,
            )

            # Store references - store the async process for wait_async
            self._workers[worker_id] = handle
            if not hasattr(self, "_async_processes"):
                self._async_processes: dict[int, asyncio.subprocess.Process] = {}
            self._async_processes[worker_id] = process
            self._output_buffers[worker_id] = []

            logger.info(f"Spawned async worker {worker_id} with PID {process.pid}")
            return SpawnResult(success=True, worker_id=worker_id, handle=handle)

        except (OSError, subprocess.SubprocessError, ValueError) as e:
            logger.error(f"Failed to spawn async worker {worker_id}: {e}")
            return SpawnResult(success=False, worker_id=worker_id, error=str(e))

    async def wait_async(self, worker_id: int) -> WorkerStatus:
        """Wait for a worker subprocess to complete asynchronously.

        Uses process.wait() on the async process handle if available,
        otherwise falls back to polling via asyncio.to_thread().

        Args:
            worker_id: Worker to wait for

        Returns:
            Final worker status
        """
        if hasattr(self, "_async_processes") and worker_id in self._async_processes:
            process = self._async_processes[worker_id]
            await process.wait()

            handle = self._workers.get(worker_id)
            if handle:
                exit_code = process.returncode
                handle.exit_code = exit_code
                if exit_code == 0:
                    handle.status = WorkerStatus.STOPPED
                elif exit_code == 2:
                    handle.status = WorkerStatus.CHECKPOINTING
                elif exit_code == 3:
                    handle.status = WorkerStatus.BLOCKED
                else:
                    handle.status = WorkerStatus.CRASHED
                return handle.status

        return await asyncio.to_thread(self.monitor, worker_id)

    async def terminate_async(self, worker_id: int, force: bool = False) -> bool:
        """Terminate a worker subprocess asynchronously.

        If an async process handle exists, terminates it directly.
        Otherwise falls back to sync terminate via asyncio.to_thread().

        Args:
            worker_id: Worker to terminate
            force: Force termination with SIGKILL

        Returns:
            True if termination succeeded
        """
        if hasattr(self, "_async_processes") and worker_id in self._async_processes:
            process = self._async_processes[worker_id]
            handle = self._workers.get(worker_id)

            if not handle:
                return False

            try:
                if force:
                    process.kill()
                else:
                    process.terminate()

                try:
                    await asyncio.wait_for(process.wait(), timeout=10)
                except TimeoutError:
                    process.kill()
                    await process.wait()

                handle.status = WorkerStatus.STOPPED
                handle.exit_code = process.returncode

                logger.info(f"Async terminated worker {worker_id} (exit code: {handle.exit_code})")
                return True

            except (OSError, ProcessLookupError) as e:
                logger.error(f"Failed to async terminate worker {worker_id}: {e}")
                return False

            finally:
                if worker_id in self._async_processes:
                    del self._async_processes[worker_id]
                if worker_id in self._workers:
                    del self._workers[worker_id]

        return await asyncio.to_thread(self.terminate, worker_id, force)
