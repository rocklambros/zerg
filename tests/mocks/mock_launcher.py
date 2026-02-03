"""Mock ContainerLauncher with exec verification.

Provides MockContainerLauncher for testing launcher exec behavior
with configurable exec verification and process monitoring.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from zerg.constants import WorkerStatus
from zerg.launcher import LauncherConfig, SpawnResult, WorkerHandle, WorkerLauncher


@dataclass
class ExecAttempt:
    """Record of an exec attempt."""

    container_id: str
    command: str
    timestamp: datetime = field(default_factory=datetime.now)
    success: bool = False
    process_started: bool = False
    error: str | None = None


@dataclass
class SpawnAttempt:
    """Record of a spawn attempt."""

    worker_id: int
    feature: str
    worktree_path: Path
    branch: str
    timestamp: datetime = field(default_factory=datetime.now)
    success: bool = False
    container_id: str | None = None
    exec_success: bool = False
    process_verified: bool = False
    error: str | None = None


class MockContainerLauncher(WorkerLauncher):
    """Mock ContainerLauncher with exec verification for testing.

    Simulates container spawning with configurable exec success/failure
    and process verification behavior.

    Example:
        launcher = MockContainerLauncher()
        launcher.configure(
            exec_fail_workers={1},  # Worker 1 exec fails
            process_fail_workers={2},  # Worker 2 process doesn't start
        )

        result = launcher.spawn(0, "test", Path("/work"), "branch")
        assert result.success  # Worker 0 succeeds

        result = launcher.spawn(1, "test", Path("/work"), "branch")
        assert not result.success  # Worker 1 exec fails
    """

    CONTAINER_PREFIX = "mock-zerg-worker"

    def __init__(
        self,
        config: LauncherConfig | None = None,
        image_name: str = "mock-zerg-worker",
        network: str | None = None,
    ) -> None:
        """Initialize mock container launcher.

        Args:
            config: Launcher configuration
            image_name: Docker image name (ignored in mock)
            network: Docker network (ignored in mock)
        """
        super().__init__(config)
        self.image_name = image_name
        self.network = network or "mock-network"

        # Track container IDs
        self._container_ids: dict[int, str] = {}
        self._container_counter = 0

        # Track attempts
        self._spawn_attempts: list[SpawnAttempt] = []
        self._exec_attempts: list[ExecAttempt] = []

        # Track process state
        self._process_running: dict[str, bool] = {}

        # Configurable behavior
        self._spawn_fail_workers: set[int] = set()
        self._exec_fail_workers: set[int] = set()
        self._process_fail_workers: set[int] = set()
        self._container_crash_workers: set[int] = set()
        self._spawn_delay: float = 0.0
        self._exec_delay: float = 0.0
        self._process_verify_timeout: float = 5.0

    def configure(
        self,
        spawn_fail_workers: set[int] | None = None,
        exec_fail_workers: set[int] | None = None,
        process_fail_workers: set[int] | None = None,
        container_crash_workers: set[int] | None = None,
        spawn_delay: float = 0.0,
        exec_delay: float = 0.0,
        process_verify_timeout: float = 5.0,
    ) -> MockContainerLauncher:
        """Configure mock behavior.

        Args:
            spawn_fail_workers: Worker IDs where container start fails
            exec_fail_workers: Worker IDs where exec returns failure
            process_fail_workers: Worker IDs where process doesn't start
            container_crash_workers: Worker IDs where container crashes
            spawn_delay: Simulated spawn delay in seconds
            exec_delay: Simulated exec delay in seconds
            process_verify_timeout: Timeout for process verification

        Returns:
            Self for chaining
        """
        self._spawn_fail_workers = spawn_fail_workers or set()
        self._exec_fail_workers = exec_fail_workers or set()
        self._process_fail_workers = process_fail_workers or set()
        self._container_crash_workers = container_crash_workers or set()
        self._spawn_delay = spawn_delay
        self._exec_delay = exec_delay
        self._process_verify_timeout = process_verify_timeout
        return self

    def spawn(
        self,
        worker_id: int,
        feature: str,
        worktree_path: Path,
        branch: str,
        env: dict[str, str] | None = None,
    ) -> SpawnResult:
        """Spawn a mock container worker.

        Args:
            worker_id: Worker identifier
            feature: Feature name
            worktree_path: Path to worktree
            branch: Git branch
            env: Environment variables

        Returns:
            SpawnResult with success/failure
        """
        attempt = SpawnAttempt(
            worker_id=worker_id,
            feature=feature,
            worktree_path=worktree_path,
            branch=branch,
        )

        # Apply spawn delay
        if self._spawn_delay > 0:
            time.sleep(self._spawn_delay)

        # Check for spawn failure
        if worker_id in self._spawn_fail_workers:
            attempt.error = f"Simulated spawn failure for worker {worker_id}"
            self._spawn_attempts.append(attempt)
            return SpawnResult(
                success=False,
                worker_id=worker_id,
                error=attempt.error,
            )

        # Create container ID
        self._container_counter += 1
        container_id = f"mock-{self._container_counter:08x}"
        attempt.container_id = container_id

        # Simulate container ready
        self._container_ids[worker_id] = container_id
        self._process_running[container_id] = False  # Not yet running

        # Execute worker entry
        exec_success = self._exec_worker_entry(container_id)
        attempt.exec_success = exec_success

        if not exec_success:
            attempt.error = "Failed to execute worker entry script"
            self._spawn_attempts.append(attempt)
            # Clean up
            del self._container_ids[worker_id]
            del self._process_running[container_id]
            return SpawnResult(
                success=False,
                worker_id=worker_id,
                error=attempt.error,
            )

        # Verify process running
        process_verified = self._verify_worker_process(container_id, worker_id)
        attempt.process_verified = process_verified

        if not process_verified:
            attempt.error = "Worker process failed to start"
            self._spawn_attempts.append(attempt)
            # Clean up
            del self._container_ids[worker_id]
            del self._process_running[container_id]
            return SpawnResult(
                success=False,
                worker_id=worker_id,
                error=attempt.error,
            )

        # Create handle
        handle = WorkerHandle(
            worker_id=worker_id,
            container_id=container_id,
            status=WorkerStatus.RUNNING,
        )

        self._workers[worker_id] = handle
        attempt.success = True
        self._spawn_attempts.append(attempt)

        return SpawnResult(
            success=True,
            worker_id=worker_id,
            handle=handle,
        )

    def _exec_worker_entry(self, container_id: str) -> bool:
        """Execute the worker entry script in mock container.

        Args:
            container_id: Container ID

        Returns:
            True if execution started successfully
        """
        # Apply exec delay
        if self._exec_delay > 0:
            time.sleep(self._exec_delay)

        # Find worker ID for this container
        worker_id = None
        for wid, cid in self._container_ids.items():
            if cid == container_id:
                worker_id = wid
                break

        # Check for exec failure
        if worker_id is not None and worker_id in self._exec_fail_workers:
            self._exec_attempts.append(
                ExecAttempt(
                    container_id=container_id,
                    command="worker_entry.sh",
                    success=False,
                    process_started=False,
                    error=f"Simulated exec failure for worker {worker_id}",
                )
            )
            return False

        # Record successful exec
        self._exec_attempts.append(
            ExecAttempt(
                container_id=container_id,
                command="worker_entry.sh",
                success=True,
                process_started=True,
            )
        )

        return True

    def _verify_worker_process(
        self,
        container_id: str,
        worker_id: int,
        timeout: float | None = None,
    ) -> bool:
        """Verify the worker process is running.

        Args:
            container_id: Container ID
            worker_id: Worker ID
            timeout: Verification timeout

        Returns:
            True if process is running
        """
        timeout = timeout or self._process_verify_timeout

        # Check for process failure
        if worker_id in self._process_fail_workers:
            return False

        # Simulate process running
        self._process_running[container_id] = True
        return True

    def monitor(self, worker_id: int) -> WorkerStatus:
        """Check mock worker status.

        Args:
            worker_id: Worker to check

        Returns:
            Current worker status
        """
        handle = self._workers.get(worker_id)
        container_id = self._container_ids.get(worker_id)

        if not handle or not container_id:
            return WorkerStatus.STOPPED

        # Check for crash simulation
        if worker_id in self._container_crash_workers:
            handle.status = WorkerStatus.CRASHED
            handle.exit_code = 1
            return WorkerStatus.CRASHED

        # Check if process is running
        if not self._process_running.get(container_id, False):
            handle.status = WorkerStatus.STOPPED
            return WorkerStatus.STOPPED

        return handle.status

    def terminate(self, worker_id: int, force: bool = False) -> bool:
        """Terminate a mock worker.

        Args:
            worker_id: Worker to terminate
            force: Force termination

        Returns:
            True if termination succeeded
        """
        handle = self._workers.get(worker_id)
        container_id = self._container_ids.get(worker_id)

        if not handle or not container_id:
            return False

        # Mark as stopped
        handle.status = WorkerStatus.STOPPED
        handle.exit_code = 0
        self._process_running[container_id] = False

        # Clean up
        if worker_id in self._container_ids:
            del self._container_ids[worker_id]
        if worker_id in self._workers:
            del self._workers[worker_id]

        return True

    def get_output(self, worker_id: int, tail: int = 100) -> str:
        """Get mock worker output.

        Args:
            worker_id: Worker to get output from
            tail: Number of lines

        Returns:
            Mock output string
        """
        container_id = self._container_ids.get(worker_id)
        if not container_id:
            return ""
        return f"[Mock container {container_id} output for worker {worker_id}]"

    def ensure_network(self) -> bool:
        """Mock ensure_network - always succeeds.

        Returns:
            True
        """
        return True

    def image_exists(self) -> bool:
        """Mock image_exists - always True.

        Returns:
            True
        """
        return True

    # Inspection methods for testing

    def get_spawn_attempts(self) -> list[SpawnAttempt]:
        """Get all spawn attempts.

        Returns:
            List of SpawnAttempt records
        """
        return self._spawn_attempts.copy()

    def get_exec_attempts(self) -> list[ExecAttempt]:
        """Get all exec attempts.

        Returns:
            List of ExecAttempt records
        """
        return self._exec_attempts.copy()

    def get_successful_spawns(self) -> list[SpawnAttempt]:
        """Get successful spawn attempts.

        Returns:
            List of successful SpawnAttempt records
        """
        return [a for a in self._spawn_attempts if a.success]

    def get_failed_spawns(self) -> list[SpawnAttempt]:
        """Get failed spawn attempts.

        Returns:
            List of failed SpawnAttempt records
        """
        return [a for a in self._spawn_attempts if not a.success]

    def get_exec_failed_spawns(self) -> list[SpawnAttempt]:
        """Get spawns that failed due to exec failure.

        Returns:
            List of SpawnAttempt records with exec failure
        """
        return [a for a in self._spawn_attempts if a.container_id and not a.exec_success]

    def get_process_failed_spawns(self) -> list[SpawnAttempt]:
        """Get spawns that failed due to process not starting.

        Returns:
            List of SpawnAttempt records with process failure
        """
        return [a for a in self._spawn_attempts if a.exec_success and not a.process_verified]

    def is_process_running(self, container_id: str) -> bool:
        """Check if a process is marked as running.

        Args:
            container_id: Container ID

        Returns:
            True if process is running
        """
        return self._process_running.get(container_id, False)

    def reset(self) -> None:
        """Reset mock state."""
        self._workers.clear()
        self._container_ids.clear()
        self._container_counter = 0
        self._spawn_attempts.clear()
        self._exec_attempts.clear()
        self._process_running.clear()
