"""Worker state repository — worker registration, health, and readiness.

Manages worker lifecycle state including registration, status tracking,
health updates, and readiness polling.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import TYPE_CHECKING

from zerg.constants import WorkerStatus
from zerg.logging import get_logger
from zerg.types import WorkerState

if TYPE_CHECKING:
    from zerg.state.persistence import PersistenceLayer

logger = get_logger("state.worker_repo")


class WorkerStateRepo:
    """Worker state CRUD operations.

    Reads and mutates worker entries in the in-memory state dict
    managed by a PersistenceLayer instance.
    """

    def __init__(self, persistence: PersistenceLayer) -> None:
        """Initialize worker state repository.

        Args:
            persistence: PersistenceLayer instance for data access
        """
        self._persistence = persistence

    def get_worker_state(self, worker_id: int) -> WorkerState | None:
        """Get state of a worker.

        Args:
            worker_id: Worker identifier

        Returns:
            WorkerState or None if not found
        """
        with self._persistence.lock:
            worker_data = self._persistence.state.get("workers", {}).get(str(worker_id))
            if not worker_data:
                return None
            return WorkerState.from_dict(worker_data)

    def set_worker_state(self, worker_state: WorkerState) -> None:
        """Set state of a worker.

        Args:
            worker_state: Worker state to save
        """
        with self._persistence.atomic_update():
            if "workers" not in self._persistence.state:
                self._persistence.state["workers"] = {}

            self._persistence.state["workers"][str(worker_state.worker_id)] = worker_state.to_dict()

        logger.debug(f"Worker {worker_state.worker_id} state: {worker_state.status.value}")

    def get_all_workers(self) -> dict[int, WorkerState]:
        """Get all worker states.

        Returns:
            Dictionary of worker_id to WorkerState
        """
        with self._persistence.lock:
            workers = {}
            for wid_str, data in self._persistence.state.get("workers", {}).items():
                workers[int(wid_str)] = WorkerState.from_dict(data)
            return workers

    def set_worker_ready(self, worker_id: int) -> None:
        """Mark a worker as ready to receive tasks.

        Args:
            worker_id: Worker identifier
        """
        with self._persistence.atomic_update():
            worker_data = self._persistence.state.get("workers", {}).get(str(worker_id), {})
            if worker_data:
                worker_data["status"] = WorkerStatus.READY.value
                worker_data["ready_at"] = datetime.now().isoformat()

        logger.debug(f"Worker {worker_id} marked ready")

    def get_ready_workers(self) -> list[int]:
        """Get list of workers in ready state.

        Returns:
            List of ready worker IDs
        """
        with self._persistence.lock:
            ready = []
            for wid_str, worker_data in self._persistence.state.get("workers", {}).items():
                if worker_data.get("status") == WorkerStatus.READY.value:
                    ready.append(int(wid_str))
            return ready

    def wait_for_workers_ready(self, worker_ids: list[int], timeout: float = 60.0) -> bool:
        """Wait for specified workers to become ready.

        Note: This is a polling implementation. For production, consider
        using proper synchronization.

        Args:
            worker_ids: Workers to wait for
            timeout: Maximum wait time in seconds

        Returns:
            True if all workers became ready before timeout
        """
        start = time.time()
        while time.time() - start < timeout:
            self._persistence.load()  # Refresh state
            ready = self.get_ready_workers()
            if all(wid in ready for wid in worker_ids):
                return True
            time.sleep(0.5)
        return False
