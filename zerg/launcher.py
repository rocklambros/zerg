"""ZERG worker launcher abstraction.

Provides pluggable launcher backends for spawning and managing worker processes.
"""

import asyncio
import os
import subprocess
import sys
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from zerg.constants import LOGS_TASKS_DIR, LOGS_WORKERS_DIR, WorkerStatus
from zerg.logging import get_logger
from zerg.retry_backoff import RetryBackoffCalculator

logger = get_logger("launcher")


# Allowlisted environment variables that can be set from config
ALLOWED_ENV_VARS = {
    # ZERG-specific
    "ZERG_WORKER_ID",
    "ZERG_FEATURE",
    "ZERG_WORKTREE",
    "ZERG_BRANCH",
    "ZERG_TASK_ID",
    "ZERG_SPEC_DIR",
    "ZERG_STATE_DIR",
    "ZERG_REPO_PATH",
    "ZERG_LOG_LEVEL",
    "ZERG_DEBUG",
    "ZERG_ANALYSIS_DEPTH",
    "ZERG_COMPACT_MODE",
    "ZERG_MCP_HINT",
    "ZERG_TOKEN_BUDGET",
    "ZERG_BEHAVIORAL_MODE",
    "ZERG_TDD_MODE",
    "ZERG_RULES_ENABLED",
    "ZERG_LOOP_ENABLED",
    "ZERG_LOOP_ITERATIONS",
    "ZERG_VERIFICATION_GATES",
    "ZERG_STALENESS_THRESHOLD",
    # Claude Code cross-session coordination
    "CLAUDE_CODE_TASK_LIST_ID",
    # Common development env vars
    "CI",
    "DEBUG",
    "LOG_LEVEL",
    "VERBOSE",
    "TERM",
    "COLORTERM",
    "NO_COLOR",
    # API keys (user-provided)
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    # Build/test env vars
    "NODE_ENV",
    "PYTHON_ENV",
    "RUST_BACKTRACE",
    "PYTEST_CURRENT_TEST",
}

# Dangerous environment variables that should NEVER be overridden
DANGEROUS_ENV_VARS = {
    "LD_PRELOAD",
    "LD_LIBRARY_PATH",
    "DYLD_INSERT_LIBRARIES",
    "DYLD_LIBRARY_PATH",
    "PATH",
    "PYTHONPATH",
    "NODE_PATH",
    "HOME",
    "USER",
    "SHELL",
    "TMPDIR",
    "TMP",
    "TEMP",
}

# Container path constants
CONTAINER_HOME_DIR = "/home/worker"
CONTAINER_HEALTH_FILE = "/tmp/.zerg-alive"


def validate_env_vars(env: dict[str, str]) -> dict[str, str]:
    """Validate and filter environment variables.

    Args:
        env: Environment variables to validate

    Returns:
        Validated environment variables
    """
    validated = {}

    for key, value in env.items():
        # Check for dangerous vars
        if key.upper() in DANGEROUS_ENV_VARS:
            logger.warning(f"Blocked dangerous environment variable: {key}")
            continue

        # Check if in allowlist or is a ZERG_ prefixed var
        if key.upper() in ALLOWED_ENV_VARS or key.upper().startswith("ZERG_"):
            # Validate value doesn't contain shell metacharacters
            if any(c in value for c in [";", "|", "&", "`", "$", "(", ")", "<", ">"]):
                logger.warning(f"Blocked env var with shell metacharacters: {key}")
                continue

            validated[key] = value
        else:
            logger.debug(f"Skipping unlisted environment variable: {key}")

    return validated


def get_plugin_launcher(name: str, registry: "Any") -> "WorkerLauncher | None":
    """Look up a launcher from the plugin registry.

    Args:
        name: Launcher name to look up
        registry: Plugin registry instance (PluginRegistry or None)

    Returns:
        WorkerLauncher instance from plugin, or None if not found/available
    """
    if registry is None:
        return None
    plugin = registry.get_launcher(name)
    if plugin is None:
        return None
    try:
        launcher: WorkerLauncher | None = plugin.create_launcher(None)
        return launcher
    except Exception as e:
        logger.warning(f"Plugin launcher '{name}' failed to create launcher instance: {e}")
        return None


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

    def sync_state(self) -> dict[int, WorkerStatus]:
        """Reconcile internal state with actual worker status.

        Polls all tracked workers and updates their status.
        Removes handles for workers that have stopped.

        Returns:
            Dictionary of worker_id to current status
        """
        results: dict[int, WorkerStatus] = {}
        stopped_workers: list[int] = []

        for worker_id in list(self._workers.keys()):
            status = self.monitor(worker_id)
            results[worker_id] = status

            # Track stopped workers for cleanup
            if status in (WorkerStatus.STOPPED, WorkerStatus.CRASHED):
                stopped_workers.append(worker_id)

        # Clean up stopped workers from tracking
        for worker_id in stopped_workers:
            if worker_id in self._workers:
                logger.debug(f"Removing stopped worker {worker_id} from tracking")
                del self._workers[worker_id]

        return results

    def spawn_with_retry(
        self,
        worker_id: int,
        feature: str,
        worktree_path: Path,
        branch: str,
        env: dict[str, str] | None = None,
        max_attempts: int = 3,
        backoff_strategy: str = "exponential",
        backoff_base_seconds: float = 2.0,
        backoff_max_seconds: float = 30.0,
    ) -> SpawnResult:
        """Spawn a worker with retry logic using exponential backoff.

        Attempts to spawn a worker, retrying on transient failures with
        configurable backoff. Uses RetryBackoffCalculator for delay calculation.

        Args:
            worker_id: Unique worker identifier
            feature: Feature name being worked on
            worktree_path: Path to worker's git worktree
            branch: Git branch for worker
            env: Additional environment variables
            max_attempts: Maximum number of spawn attempts (default: 3)
            backoff_strategy: Backoff strategy (exponential, linear, fixed)
            backoff_base_seconds: Base delay in seconds for backoff
            backoff_max_seconds: Maximum delay cap in seconds

        Returns:
            SpawnResult with handle on success, or error after all attempts fail
        """
        last_error: str = ""

        for attempt in range(1, max_attempts + 1):
            logger.info(f"Spawn attempt {attempt}/{max_attempts} for worker {worker_id}")

            result = self.spawn(worker_id, feature, worktree_path, branch, env)

            if result.success:
                if attempt > 1:
                    logger.info(f"Worker {worker_id} spawned successfully on attempt {attempt}")
                return result

            last_error = result.error or "Unknown error"
            logger.warning(f"Spawn attempt {attempt}/{max_attempts} failed for worker {worker_id}: {last_error}")

            # Don't sleep after the last attempt
            if attempt < max_attempts:
                delay = RetryBackoffCalculator.calculate_delay(
                    attempt=attempt,
                    strategy=backoff_strategy,
                    base_seconds=int(backoff_base_seconds),
                    max_seconds=int(backoff_max_seconds),
                )
                logger.info(f"Waiting {delay:.2f}s before retry {attempt + 1}/{max_attempts}")
                time.sleep(delay)

        # All attempts exhausted
        logger.error(f"All {max_attempts} spawn attempts failed for worker {worker_id}. Last error: {last_error}")
        return SpawnResult(
            success=False,
            error=f"All {max_attempts} spawn attempts failed. Last error: {last_error}",
            worker_id=worker_id,
        )

    async def spawn_with_retry_async(
        self,
        worker_id: int,
        feature: str,
        worktree_path: Path,
        branch: str,
        env: dict[str, str] | None = None,
        max_attempts: int = 3,
        backoff_strategy: str = "exponential",
        backoff_base_seconds: float = 2.0,
        backoff_max_seconds: float = 30.0,
    ) -> SpawnResult:
        """Spawn a worker with retry logic asynchronously.

        Async version of spawn_with_retry() using asyncio.sleep() for non-blocking
        delays between retry attempts.

        Args:
            worker_id: Unique worker identifier
            feature: Feature name being worked on
            worktree_path: Path to worker's git worktree
            branch: Git branch for worker
            env: Additional environment variables
            max_attempts: Maximum number of spawn attempts (default: 3)
            backoff_strategy: Backoff strategy (exponential, linear, fixed)
            backoff_base_seconds: Base delay in seconds for backoff
            backoff_max_seconds: Maximum delay cap in seconds

        Returns:
            SpawnResult with handle on success, or error after all attempts fail
        """
        last_error: str = ""

        for attempt in range(1, max_attempts + 1):
            logger.info(f"Async spawn attempt {attempt}/{max_attempts} for worker {worker_id}")

            result = await self.spawn_async(worker_id, feature, worktree_path, branch, env)

            if result.success:
                if attempt > 1:
                    logger.info(f"Worker {worker_id} spawned successfully on attempt {attempt}")
                return result

            last_error = result.error or "Unknown error"
            logger.warning(f"Async spawn attempt {attempt}/{max_attempts} failed for worker {worker_id}: {last_error}")

            # Don't sleep after the last attempt
            if attempt < max_attempts:
                delay = RetryBackoffCalculator.calculate_delay(
                    attempt=attempt,
                    strategy=backoff_strategy,
                    base_seconds=int(backoff_base_seconds),
                    max_seconds=int(backoff_max_seconds),
                )
                logger.info(f"Waiting {delay:.2f}s before async retry {attempt + 1}/{max_attempts}")
                await asyncio.sleep(delay)

        # All attempts exhausted
        logger.error(f"All {max_attempts} async spawn attempts failed for worker {worker_id}. Last error: {last_error}")
        return SpawnResult(
            success=False,
            error=f"All {max_attempts} spawn attempts failed. Last error: {last_error}",
            worker_id=worker_id,
        )

    async def spawn_async(
        self,
        worker_id: int,
        feature: str,
        worktree_path: Path,
        branch: str,
        env: dict[str, str] | None = None,
    ) -> SpawnResult:
        """Spawn a new worker process asynchronously.

        Default implementation falls back to sync spawn via asyncio.to_thread().
        Subclasses should override for native async behavior.

        Args:
            worker_id: Unique worker identifier
            feature: Feature name being worked on
            worktree_path: Path to worker's git worktree
            branch: Git branch for worker
            env: Additional environment variables

        Returns:
            SpawnResult with handle or error
        """
        return await asyncio.to_thread(self.spawn, worker_id, feature, worktree_path, branch, env)

    async def terminate_async(self, worker_id: int, force: bool = False) -> bool:
        """Terminate a worker asynchronously.

        Default implementation falls back to sync terminate via asyncio.to_thread().
        Subclasses should override for native async behavior.

        Args:
            worker_id: Worker to terminate
            force: Force termination without graceful shutdown

        Returns:
            True if termination succeeded
        """
        return await asyncio.to_thread(self.terminate, worker_id, force)

    async def wait_all_async(self, worker_ids: list[int]) -> dict[int, WorkerStatus]:
        """Wait for multiple workers to complete asynchronously.

        Uses asyncio.gather() to poll all workers concurrently.

        Args:
            worker_ids: List of worker IDs to wait for

        Returns:
            Dictionary of worker_id to final WorkerStatus
        """

        async def _wait_single(wid: int) -> tuple[int, WorkerStatus]:
            """Wait for a single worker to finish."""
            while True:
                status = await asyncio.to_thread(self.monitor, wid)
                if status not in (
                    WorkerStatus.INITIALIZING,
                    WorkerStatus.READY,
                    WorkerStatus.RUNNING,
                    WorkerStatus.IDLE,
                ):
                    return wid, status
                await asyncio.sleep(1.0)

        results = await asyncio.gather(*[_wait_single(wid) for wid in worker_ids])
        return dict(results)


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
            # Check heartbeat for stall detection
            if handle.status == WorkerStatus.RUNNING:
                from zerg.heartbeat import HeartbeatMonitor

                hb_monitor = HeartbeatMonitor()
                hb = hb_monitor.read(worker_id)
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

        except Exception as e:
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

        except Exception as e:
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

            except Exception as e:
                logger.error(f"Failed to async terminate worker {worker_id}: {e}")
                return False

            finally:
                if worker_id in self._async_processes:
                    del self._async_processes[worker_id]
                if worker_id in self._workers:
                    del self._workers[worker_id]

        return await asyncio.to_thread(self.terminate, worker_id, force)


class ContainerLauncher(WorkerLauncher):
    """Launch workers in Docker containers.

    Uses devcontainer configuration to spawn isolated worker environments.
    Each worker runs in its own container with mounted workspace.
    """

    # Container configuration
    # Use default bridge network for internet access (required for API calls)
    DEFAULT_NETWORK = "bridge"
    CONTAINER_PREFIX = "zerg-worker"
    WORKER_ENTRY_SCRIPT = ".zerg/worker_entry.sh"

    def __init__(
        self,
        config: LauncherConfig | None = None,
        image_name: str = "zerg-worker",
        network: str | None = None,
        memory_limit: str = "4g",
        cpu_limit: float = 2.0,
    ) -> None:
        """Initialize container launcher.

        Args:
            config: Launcher configuration
            image_name: Docker image name for workers
            network: Docker network name (default: zerg-internal)
            memory_limit: Docker --memory limit (e.g., '4g', '512m')
            cpu_limit: Docker --cpus limit (e.g., 2.0)
        """
        super().__init__(config)
        self.image_name = image_name
        self.network = network or self.DEFAULT_NETWORK
        self.memory_limit = memory_limit
        self.cpu_limit = cpu_limit
        self._container_ids: dict[int, str] = {}

    def spawn(
        self,
        worker_id: int,
        feature: str,
        worktree_path: Path,
        branch: str,
        env: dict[str, str] | None = None,
    ) -> SpawnResult:
        """Spawn a new worker container.

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
            # Validate worker_id
            if not isinstance(worker_id, int) or worker_id < 0:
                raise ValueError(f"Invalid worker_id: {worker_id}")

            container_name = f"{self.CONTAINER_PREFIX}-{int(worker_id)}"

            # Remove any existing container with the same name
            subprocess.run(
                ["docker", "rm", "-f", container_name],
                capture_output=True,
            )

            # Build environment
            container_env = {
                "ZERG_WORKER_ID": str(worker_id),
                "ZERG_FEATURE": feature,
                "ZERG_WORKTREE": "/workspace",
                "ZERG_BRANCH": branch,
                "ZERG_SPEC_DIR": f"/workspace/.gsd/specs/{feature}",
                **(
                    {"CLAUDE_CODE_TASK_LIST_ID": os.environ["CLAUDE_CODE_TASK_LIST_ID"]}
                    if "CLAUDE_CODE_TASK_LIST_ID" in os.environ
                    else {}
                ),
            }

            # Add API key from environment or .env file
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                env_file = Path(".env")
                if env_file.exists():
                    for line in env_file.read_text().splitlines():
                        line = line.strip()
                        if line.startswith("ANTHROPIC_API_KEY"):
                            _, _, val = line.partition("=")
                            api_key = val.strip().strip("'\"")
                            break
            if api_key:
                container_env["ANTHROPIC_API_KEY"] = api_key

            # Validate and add additional env vars
            if self.config.env_vars:
                validated = validate_env_vars(self.config.env_vars)
                container_env.update(validated)
            if env:
                validated = validate_env_vars(env)
                container_env.update(validated)

            # Start container
            container_id = self._start_container(
                container_name=container_name,
                worktree_path=worktree_path,
                env=container_env,
            )

            if not container_id:
                return SpawnResult(
                    success=False,
                    worker_id=worker_id,
                    error="Failed to start container",
                )

            # Create handle
            handle = WorkerHandle(
                worker_id=worker_id,
                container_id=container_id,
                status=WorkerStatus.INITIALIZING,
            )

            # Store references
            self._workers[worker_id] = handle
            self._container_ids[worker_id] = container_id

            # Wait for container ready
            if not self._wait_ready(container_id, timeout=30):
                return SpawnResult(
                    success=False,
                    worker_id=worker_id,
                    error="Container failed to become ready",
                )

            # Entry script runs as container CMD (no separate docker exec needed).
            # Wait longer for worker to start since it includes dependency install.
            if not self._verify_worker_process(container_id, timeout=120.0):
                logger.error(f"Worker process failed to start for worker {worker_id}")
                self._cleanup_failed_container(container_id, worker_id)
                return SpawnResult(
                    success=False,
                    worker_id=worker_id,
                    error="Worker process failed to start",
                )

            handle.status = WorkerStatus.RUNNING
            logger.info(f"Spawned container {container_name} ({container_id[:12]})")

            return SpawnResult(success=True, worker_id=worker_id, handle=handle)

        except Exception as e:
            logger.error(f"Failed to spawn container for worker {worker_id}: {e}")
            return SpawnResult(success=False, worker_id=worker_id, error=str(e))

    def _start_container(
        self,
        container_name: str,
        worktree_path: Path,
        env: dict[str, str],
    ) -> str | None:
        """Start a Docker container.

        Args:
            container_name: Name for the container
            worktree_path: Host path to mount as workspace
            env: Environment variables for container

        Returns:
            Container ID or None on failure
        """
        # Build docker run command
        # Mount worktree as workspace and share state directory from main repo
        main_repo = worktree_path.parent.parent.parent  # .zerg-worktrees/feature/worker-N -> repo
        state_dir = main_repo / ".zerg" / "state"

        # Git worktrees need access to:
        # 1. The worktree metadata in main repo's .git/worktrees/<name>
        # 2. The main repo's .git directory for objects/refs
        worktree_name = worktree_path.name  # e.g., "worker-0"
        main_git_dir = main_repo / ".git"
        git_worktree_dir = main_git_dir / "worktrees" / worktree_name

        # Mount ~/.claude for OAuth credentials if it exists
        claude_config_dir = Path.home() / ".claude"

        # Get current user's UID/GID to run container as non-root
        # This is required because --dangerously-skip-permissions doesn't work as root
        uid = os.getuid()
        gid = os.getgid()
        home_dir = CONTAINER_HOME_DIR

        cmd = [
            "docker",
            "run",
            "-d",
            "--name",
            container_name,
            "--user",
            f"{uid}:{gid}",
            "-v",
            f"{worktree_path.absolute()}:/workspace",
            "-v",
            f"{state_dir.absolute()}:/workspace/.zerg/state",  # Share state with orchestrator
        ]

        # Mount main repo's .git and worktree metadata for git operations inside container
        if main_git_dir.exists() and git_worktree_dir.exists():
            # Mount the main .git to /repo/.git so git can find objects/refs
            # Note: Not read-only because git needs write access for commits
            cmd.extend(["-v", f"{main_git_dir.absolute()}:/repo/.git"])
            # Mount the worktree metadata
            cmd.extend(["-v", f"{git_worktree_dir.absolute()}:/workspace/.git-worktree"])
            # Pass env vars so entry script can fix the git paths
            env["ZERG_GIT_WORKTREE_DIR"] = "/workspace/.git-worktree"
            env["ZERG_GIT_MAIN_DIR"] = "/repo/.git"

        # Add Claude config mount for OAuth authentication (needs write for debug logs)
        if claude_config_dir.exists():
            cmd.extend(["-v", f"{claude_config_dir.absolute()}:{home_dir}/.claude"])
            cmd.extend(["-e", f"HOME={home_dir}"])

        # Mount ~/.claude.json for OAuth token (separate file from ~/.claude/ directory)
        claude_config_file = Path.home() / ".claude.json"
        if claude_config_file.exists():
            cmd.extend(["-v", f"{claude_config_file.absolute()}:{home_dir}/.claude.json"])

        # Resource limits
        cmd.extend(["--memory", self.memory_limit])
        cmd.extend(["--cpus", str(self.cpu_limit)])

        cmd.extend(
            [
                "-w",
                "/workspace",
                "--network",
                self.network,
            ]
        )

        # Add environment variables
        for key, value in env.items():
            cmd.extend(["-e", f"{key}={value}"])

        # Run entry script directly as container CMD.
        # The entry script uses 'exec' to become worker_main (PID 1).
        # If it fails, the fallback keeps the container alive for debugging.
        cmd.extend(
            [
                self.image_name,
                "bash",
                "-c",
                f"bash /workspace/{self.WORKER_ENTRY_SCRIPT} 2>&1; "
                f"echo 'Worker entry exited with code '$?; sleep infinity",
            ]
        )

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode == 0:
                container_id = result.stdout.strip()
                return container_id
            else:
                logger.error(f"Docker run failed: {result.stderr}")
                return None

        except subprocess.TimeoutExpired:
            logger.error("Docker run timed out")
            return None
        except Exception as e:
            logger.error(f"Docker run error: {e}")
            return None

    def _wait_ready(self, container_id: str, timeout: float = 30) -> bool:
        """Wait for container to be ready.

        Args:
            container_id: Container ID
            timeout: Maximum wait time in seconds

        Returns:
            True if container is running
        """
        import time

        start = time.time()
        while time.time() - start < timeout:
            try:
                result = subprocess.run(
                    ["docker", "inspect", "-f", "{{.State.Running}}", container_id],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0 and result.stdout.strip() == "true":
                    return True
            except (subprocess.TimeoutExpired, Exception):
                pass
            time.sleep(0.5)

        return False

    def _exec_worker_entry(self, container_id: str) -> bool:
        """Execute the worker entry script in container.

        Args:
            container_id: Container ID

        Returns:
            True if execution started successfully
        """
        cmd = [
            "docker",
            "exec",
            "-d",
            "-w",
            "/workspace",
            container_id,
            "/bin/bash",
            f"/workspace/{self.WORKER_ENTRY_SCRIPT}",
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Failed to exec worker entry: {e}")
            return False

    def _verify_worker_process(self, container_id: str, timeout: float = 5.0) -> bool:
        """Verify the worker process is running in container.

        BF-008: Added process verification after exec.

        Args:
            container_id: Container ID
            timeout: Maximum time to wait for process

        Returns:
            True if worker process is running
        """
        import time as _time

        start = _time.time()
        while _time.time() - start < timeout:
            try:
                result = subprocess.run(
                    ["docker", "exec", container_id, "pgrep", "-f", "worker_main"],
                    capture_output=True,
                    timeout=2,
                )
                if result.returncode == 0:
                    logger.debug(f"Worker process verified running in {container_id[:12]}")
                    return True
            except (subprocess.TimeoutExpired, Exception) as e:
                logger.debug(f"Process check failed: {e}")
            _time.sleep(0.5)

        logger.warning(f"Worker process not found in container {container_id[:12]} after {timeout}s")
        return False

    def _cleanup_failed_container(self, container_id: str, worker_id: int) -> None:
        """Clean up container after spawn failure.

        Args:
            container_id: Container to clean up
            worker_id: Worker ID
        """
        try:
            subprocess.run(
                ["docker", "rm", "-f", container_id],
                capture_output=True,
                timeout=10,
            )
            logger.debug(f"Cleaned up failed container {container_id[:12]}")
        except Exception as e:
            logger.warning(f"Failed to clean up container: {e}")

        # Remove from tracking
        if worker_id in self._container_ids:
            del self._container_ids[worker_id]
        if worker_id in self._workers:
            del self._workers[worker_id]

    def monitor(self, worker_id: int) -> WorkerStatus:
        """Check worker container status.

        Args:
            worker_id: Worker to check

        Returns:
            Current worker status
        """
        handle = self._workers.get(worker_id)
        container_id = self._container_ids.get(worker_id)

        if not handle or not container_id:
            return WorkerStatus.STOPPED

        try:
            # Check container state
            result = subprocess.run(
                ["docker", "inspect", "-f", "{{.State.Running}},{{.State.ExitCode}}", container_id],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                handle.status = WorkerStatus.STOPPED
                return WorkerStatus.STOPPED

            running, exit_code = result.stdout.strip().split(",")

            if running == "true":
                # Container is running, but the CMD sleep keeps it alive after
                # the worker process exits. Check /tmp/.zerg-alive marker file
                # which the entry script removes on exit.
                # Only check after a grace period (marker created during init).
                if handle.started_at:
                    from datetime import timedelta

                    age = datetime.now() - handle.started_at
                    if age > timedelta(seconds=60):
                        alive_check = subprocess.run(
                            ["docker", "exec", container_id, "test", "-f", CONTAINER_HEALTH_FILE],
                            capture_output=True,
                            timeout=5,
                        )
                        if alive_check.returncode != 0:
                            logger.info(f"Worker {worker_id} process exited (marker file absent)")
                            handle.status = WorkerStatus.STOPPED
                            return WorkerStatus.STOPPED
                if handle.status == WorkerStatus.INITIALIZING:
                    handle.status = WorkerStatus.RUNNING
                return handle.status
            else:
                # Container has exited
                handle.exit_code = int(exit_code)

                if exit_code == "0":
                    handle.status = WorkerStatus.STOPPED
                elif exit_code == "2":
                    handle.status = WorkerStatus.CHECKPOINTING
                elif exit_code == "3":
                    handle.status = WorkerStatus.BLOCKED
                else:
                    handle.status = WorkerStatus.CRASHED

                return handle.status

        except Exception as e:
            logger.error(f"Failed to monitor container: {e}")
            return handle.status if handle else WorkerStatus.STOPPED

    def terminate(self, worker_id: int, force: bool = False) -> bool:
        """Terminate a worker container.

        Args:
            worker_id: Worker to terminate
            force: Force termination (docker kill vs docker stop)

        Returns:
            True if termination succeeded
        """
        container_id = self._container_ids.get(worker_id)
        handle = self._workers.get(worker_id)

        if not container_id or not handle:
            return False

        try:
            # Stop or kill container
            cmd = ["docker", "kill" if force else "stop", container_id]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30 if not force else 10,
            )

            if result.returncode == 0:
                handle.status = WorkerStatus.STOPPED
                logger.info(f"Terminated container for worker {worker_id}")

                # Remove container
                subprocess.run(
                    ["docker", "rm", "-f", container_id],
                    capture_output=True,
                    timeout=10,
                )

                return True
            else:
                logger.error(f"Failed to stop container: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            # Force kill on timeout
            subprocess.run(
                ["docker", "kill", container_id],
                capture_output=True,
                timeout=5,
            )
            handle.status = WorkerStatus.STOPPED
            return True

        except Exception as e:
            logger.error(f"Failed to terminate container: {e}")
            return False

        finally:
            # Clean up references
            if worker_id in self._container_ids:
                del self._container_ids[worker_id]
            # Also remove from worker handles to prevent stale state
            if worker_id in self._workers:
                del self._workers[worker_id]

    def get_output(self, worker_id: int, tail: int = 100) -> str:
        """Get worker container logs.

        Args:
            worker_id: Worker to get output from
            tail: Number of lines from end

        Returns:
            Output string
        """
        container_id = self._container_ids.get(worker_id)

        if not container_id:
            return ""

        try:
            result = subprocess.run(
                ["docker", "logs", "--tail", str(tail), container_id],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.stdout + result.stderr
        except Exception as e:
            logger.error(f"Failed to get container logs: {e}")
            return ""

    def ensure_network(self) -> bool:
        """Ensure the Docker network exists.

        Returns:
            True if network exists or was created
        """
        try:
            # Check if network exists
            result = subprocess.run(
                ["docker", "network", "inspect", self.network],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                return True

            # Create network
            result = subprocess.run(
                ["docker", "network", "create", self.network],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                logger.info(f"Created Docker network: {self.network}")
                return True
            else:
                logger.error(f"Failed to create network: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Network setup error: {e}")
            return False

    def image_exists(self) -> bool:
        """Check if the worker image exists.

        Returns:
            True if image exists locally
        """
        try:
            result = subprocess.run(
                ["docker", "image", "inspect", self.image_name],
                capture_output=True,
                timeout=10,
            )
            return result.returncode == 0
        except Exception as e:
            logger.debug(f"Container check failed: {e}")
            return False

    async def spawn_async(
        self,
        worker_id: int,
        feature: str,
        worktree_path: Path,
        branch: str,
        env: dict[str, str] | None = None,
    ) -> SpawnResult:
        """Spawn a new worker container asynchronously.

        Uses asyncio.create_subprocess_exec() for docker commands
        instead of blocking subprocess.run().

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
            # Validate worker_id
            if not isinstance(worker_id, int) or worker_id < 0:
                raise ValueError(f"Invalid worker_id: {worker_id}")

            container_name = f"{self.CONTAINER_PREFIX}-{int(worker_id)}"

            # Remove any existing container with the same name
            proc = await asyncio.create_subprocess_exec(
                "docker",
                "rm",
                "-f",
                container_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()

            # Build environment
            container_env: dict[str, str] = {
                "ZERG_WORKER_ID": str(worker_id),
                "ZERG_FEATURE": feature,
                "ZERG_WORKTREE": "/workspace",
                "ZERG_BRANCH": branch,
                "ZERG_SPEC_DIR": f"/workspace/.gsd/specs/{feature}",
                **(
                    {"CLAUDE_CODE_TASK_LIST_ID": os.environ["CLAUDE_CODE_TASK_LIST_ID"]}
                    if "CLAUDE_CODE_TASK_LIST_ID" in os.environ
                    else {}
                ),
            }

            # Add API key from environment or .env file
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                env_file = Path(".env")
                if env_file.exists():
                    for line in env_file.read_text().splitlines():
                        line = line.strip()
                        if line.startswith("ANTHROPIC_API_KEY"):
                            _, _, val = line.partition("=")
                            api_key = val.strip().strip("'\"")
                            break
            if api_key:
                container_env["ANTHROPIC_API_KEY"] = api_key

            # Validate and add additional env vars
            if self.config.env_vars:
                validated = validate_env_vars(self.config.env_vars)
                container_env.update(validated)
            if env:
                validated = validate_env_vars(env)
                container_env.update(validated)

            # Start container asynchronously
            container_id = await self._start_container_async(
                container_name=container_name,
                worktree_path=worktree_path,
                env=container_env,
            )

            if not container_id:
                return SpawnResult(
                    success=False,
                    worker_id=worker_id,
                    error="Failed to start container",
                )

            # Create handle
            handle = WorkerHandle(
                worker_id=worker_id,
                container_id=container_id,
                status=WorkerStatus.INITIALIZING,
            )

            # Store references
            self._workers[worker_id] = handle
            self._container_ids[worker_id] = container_id

            # Wait for container ready (fall back to sync for complex checks)
            ready = await asyncio.to_thread(self._wait_ready, container_id, 30)
            if not ready:
                return SpawnResult(
                    success=False,
                    worker_id=worker_id,
                    error="Container failed to become ready",
                )

            # Verify worker process
            verified = await asyncio.to_thread(self._verify_worker_process, container_id, 120.0)
            if not verified:
                logger.error(f"Worker process failed to start for worker {worker_id}")
                await asyncio.to_thread(self._cleanup_failed_container, container_id, worker_id)
                return SpawnResult(
                    success=False,
                    worker_id=worker_id,
                    error="Worker process failed to start",
                )

            handle.status = WorkerStatus.RUNNING
            logger.info(f"Spawned async container {container_name} ({container_id[:12]})")

            return SpawnResult(success=True, worker_id=worker_id, handle=handle)

        except Exception as e:
            logger.error(f"Failed to spawn async container for worker {worker_id}: {e}")
            return SpawnResult(success=False, worker_id=worker_id, error=str(e))

    async def _start_container_async(
        self,
        container_name: str,
        worktree_path: Path,
        env: dict[str, str],
    ) -> str | None:
        """Start a Docker container asynchronously.

        Args:
            container_name: Name for the container
            worktree_path: Host path to mount as workspace
            env: Environment variables for container

        Returns:
            Container ID or None on failure
        """
        # Build docker run command
        main_repo = worktree_path.parent.parent.parent
        state_dir = main_repo / ".zerg" / "state"

        worktree_name = worktree_path.name
        main_git_dir = main_repo / ".git"
        git_worktree_dir = main_git_dir / "worktrees" / worktree_name

        claude_config_dir = Path.home() / ".claude"
        uid = os.getuid()
        gid = os.getgid()
        home_dir = CONTAINER_HOME_DIR

        cmd_args = [
            "run",
            "-d",
            "--name",
            container_name,
            "--user",
            f"{uid}:{gid}",
            "-v",
            f"{worktree_path.absolute()}:/workspace",
            "-v",
            f"{state_dir.absolute()}:/workspace/.zerg/state",
        ]

        if main_git_dir.exists() and git_worktree_dir.exists():
            cmd_args.extend(["-v", f"{main_git_dir.absolute()}:/repo/.git"])
            cmd_args.extend(["-v", f"{git_worktree_dir.absolute()}:/workspace/.git-worktree"])
            env["ZERG_GIT_WORKTREE_DIR"] = "/workspace/.git-worktree"
            env["ZERG_GIT_MAIN_DIR"] = "/repo/.git"

        if claude_config_dir.exists():
            cmd_args.extend(["-v", f"{claude_config_dir.absolute()}:{home_dir}/.claude"])
            cmd_args.extend(["-e", f"HOME={home_dir}"])

        claude_config_file = Path.home() / ".claude.json"
        if claude_config_file.exists():
            cmd_args.extend(["-v", f"{claude_config_file.absolute()}:{home_dir}/.claude.json"])

        cmd_args.extend(["--memory", self.memory_limit])
        cmd_args.extend(["--cpus", str(self.cpu_limit)])

        cmd_args.extend(
            [
                "-w",
                "/workspace",
                "--network",
                self.network,
            ]
        )

        for key, value in env.items():
            cmd_args.extend(["-e", f"{key}={value}"])

        cmd_args.extend(
            [
                self.image_name,
                "bash",
                "-c",
                f"bash /workspace/{self.WORKER_ENTRY_SCRIPT} 2>&1; "
                f"echo 'Worker entry exited with code '$?; sleep infinity",
            ]
        )

        try:
            proc = await asyncio.create_subprocess_exec(
                "docker",
                *cmd_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)

            if proc.returncode == 0:
                container_id = stdout.decode().strip()
                return container_id
            else:
                logger.error(f"Docker run failed: {stderr.decode()}")
                return None

        except TimeoutError:
            logger.error("Docker run timed out")
            return None
        except Exception as e:
            logger.error(f"Docker run error: {e}")
            return None

    async def terminate_async(self, worker_id: int, force: bool = False) -> bool:
        """Terminate a worker container asynchronously.

        Uses asyncio.create_subprocess_exec() for docker stop/kill commands.

        Args:
            worker_id: Worker to terminate
            force: Force termination (docker kill vs docker stop)

        Returns:
            True if termination succeeded
        """
        container_id = self._container_ids.get(worker_id)
        handle = self._workers.get(worker_id)

        if not container_id or not handle:
            return False

        try:
            action = "kill" if force else "stop"
            timeout = 10 if force else 30

            proc = await asyncio.create_subprocess_exec(
                "docker",
                action,
                container_id,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)

            if proc.returncode == 0:
                handle.status = WorkerStatus.STOPPED
                logger.info(f"Async terminated container for worker {worker_id}")

                # Remove container
                rm_proc = await asyncio.create_subprocess_exec(
                    "docker",
                    "rm",
                    "-f",
                    container_id,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await asyncio.wait_for(rm_proc.communicate(), timeout=10)

                return True
            else:
                logger.error(f"Failed to stop container: {stderr.decode()}")
                return False

        except TimeoutError:
            # Force kill on timeout
            kill_proc = await asyncio.create_subprocess_exec(
                "docker",
                "kill",
                container_id,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await kill_proc.communicate()
            handle.status = WorkerStatus.STOPPED
            return True

        except Exception as e:
            logger.error(f"Failed to async terminate container: {e}")
            return False

        finally:
            # Clean up references
            if worker_id in self._container_ids:
                del self._container_ids[worker_id]
            if worker_id in self._workers:
                del self._workers[worker_id]
