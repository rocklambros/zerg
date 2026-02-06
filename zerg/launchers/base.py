"""WorkerLauncher abstract base class.

Extracted from zerg/launcher.py. Defines the interface for spawning,
monitoring, and terminating workers. Implementations (SubprocessLauncher,
ContainerLauncher) live in sibling modules.
"""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from zerg.constants import WorkerStatus
from zerg.launcher_types import LauncherConfig, SpawnResult, WorkerHandle
from zerg.logging import get_logger
from zerg.retry_backoff import RetryBackoffCalculator

logger = get_logger("launcher")


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

    async def _spawn_with_retry_impl(
        self,
        worker_id: int,
        feature: str,
        worktree_path: Path,
        branch: str,
        env: dict[str, str] | None,
        max_attempts: int,
        backoff_strategy: str,
        backoff_base_seconds: float,
        backoff_max_seconds: float,
        spawn_fn: Any,
        sleep_fn: Any,
    ) -> SpawnResult:
        """Core retry logic for spawning workers. Single source of truth.

        Both spawn_with_retry() and spawn_with_retry_async() delegate here,
        passing appropriate spawn and sleep callables for sync vs async contexts.

        Args:
            worker_id: Unique worker identifier
            feature: Feature name being worked on
            worktree_path: Path to worker's git worktree
            branch: Git branch for worker
            env: Additional environment variables
            max_attempts: Maximum number of spawn attempts
            backoff_strategy: Backoff strategy (exponential, linear, fixed)
            backoff_base_seconds: Base delay in seconds for backoff
            backoff_max_seconds: Maximum delay cap in seconds
            spawn_fn: Awaitable callable that spawns a worker and returns SpawnResult
            sleep_fn: Awaitable callable for delaying between retries

        Returns:
            SpawnResult with handle on success, or error after all attempts fail
        """
        last_error: str = ""

        for attempt in range(1, max_attempts + 1):
            logger.info(f"Spawn attempt {attempt}/{max_attempts} for worker {worker_id}")

            result = await spawn_fn(worker_id, feature, worktree_path, branch, env)

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
                await sleep_fn(delay)

        # All attempts exhausted
        logger.error(f"All {max_attempts} spawn attempts failed for worker {worker_id}. Last error: {last_error}")
        return SpawnResult(
            success=False,
            error=f"All {max_attempts} spawn attempts failed. Last error: {last_error}",
            worker_id=worker_id,
        )

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

        Sync wrapper that delegates to _spawn_with_retry_impl() with
        sync-compatible callables (self.spawn wrapped as coroutine, time.sleep).

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

        async def _sync_spawn(wid: int, feat: str, wt: Path, br: str, e: dict[str, str] | None) -> SpawnResult:
            return self.spawn(wid, feat, wt, br, e)

        async def _sync_sleep(delay: float) -> None:
            time.sleep(delay)

        return asyncio.run(
            self._spawn_with_retry_impl(
                worker_id=worker_id,
                feature=feature,
                worktree_path=worktree_path,
                branch=branch,
                env=env,
                max_attempts=max_attempts,
                backoff_strategy=backoff_strategy,
                backoff_base_seconds=backoff_base_seconds,
                backoff_max_seconds=backoff_max_seconds,
                spawn_fn=_sync_spawn,
                sleep_fn=_sync_sleep,
            )
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

        Async wrapper that delegates to _spawn_with_retry_impl() with
        native async callables (self.spawn_async, asyncio.sleep).

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
        return await self._spawn_with_retry_impl(
            worker_id=worker_id,
            feature=feature,
            worktree_path=worktree_path,
            branch=branch,
            env=env,
            max_attempts=max_attempts,
            backoff_strategy=backoff_strategy,
            backoff_base_seconds=backoff_base_seconds,
            backoff_max_seconds=backoff_max_seconds,
            spawn_fn=self.spawn_async,
            sleep_fn=asyncio.sleep,
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
