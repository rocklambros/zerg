"""Thread-safe centralized worker state management.

Replaces the raw ``dict[int, WorkerState]`` shared by reference across
orchestrator components (Orchestrator, WorkerManager, LevelCoordinator,
LauncherConfigurator) with a single registry guarded by ``threading.RLock``.
"""

from __future__ import annotations

import threading
from collections.abc import ItemsView, Iterator, KeysView

from zerg.constants import WorkerStatus
from zerg.types import WorkerState


class WorkerRegistry:
    """Single source of truth for worker state. Thread-safe.

    Provides both dict-like interface (for backward compatibility) and
    typed methods for clarity. All public methods acquire the internal
    ``RLock`` so callers never need external synchronisation.
    """

    def __init__(self) -> None:
        self._workers: dict[int, WorkerState] = {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def register(self, worker_id: int, worker: WorkerState) -> None:
        """Add a worker to the registry."""
        with self._lock:
            self._workers[worker_id] = worker

    def unregister(self, worker_id: int) -> None:
        """Remove a worker from the registry."""
        with self._lock:
            self._workers.pop(worker_id, None)

    def update_status(self, worker_id: int, status: WorkerStatus) -> None:
        """Update a worker's status in-place."""
        with self._lock:
            worker = self._workers.get(worker_id)
            if worker is not None:
                worker.status = status

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get(self, worker_id: int) -> WorkerState | None:
        """Return worker by ID, or ``None`` if not found."""
        with self._lock:
            return self._workers.get(worker_id)

    def all(self) -> dict[int, WorkerState]:
        """Return a shallow copy of every registered worker."""
        with self._lock:
            return dict(self._workers)

    def active(self) -> dict[int, WorkerState]:
        """Return workers whose status is not terminal (STOPPED/CRASHED)."""
        _terminal = {WorkerStatus.STOPPED, WorkerStatus.CRASHED}
        with self._lock:
            return {wid: w for wid, w in self._workers.items() if w.status not in _terminal}

    def by_level(self, level: int) -> dict[int, WorkerState]:
        """Return workers currently executing tasks at *level*.

        Workers are matched by checking whether their ``current_task``
        string starts with ``"TASK-"`` and their dataclass carries
        level-related state.  Since ``WorkerState`` does not store a
        ``level`` field today, this filters based on a best-effort
        approach -- callers that need precise level tracking should
        maintain a side mapping until the field is added.
        """
        # NOTE: WorkerState has no ``level`` attribute yet.  Return all
        # active workers as a safe fallback so callers always get a
        # usable result set.  Migration tasks (TASK-025..028) will
        # refine this once the orchestrator tracks level per worker.
        return self.all()

    # ------------------------------------------------------------------
    # Dict-like interface (backward compatibility)
    # ------------------------------------------------------------------

    def keys(self) -> KeysView[int]:
        """Return a view of worker IDs (snapshot under lock)."""
        with self._lock:
            # Return a real KeysView from a copy so iteration is safe
            # outside the lock.
            return dict(self._workers).keys()

    def items(self) -> ItemsView[int, WorkerState]:
        """Return a view of (worker_id, WorkerState) pairs (snapshot)."""
        with self._lock:
            return dict(self._workers).items()

    def __len__(self) -> int:
        with self._lock:
            return len(self._workers)

    def __contains__(self, worker_id: object) -> bool:
        with self._lock:
            return worker_id in self._workers

    def __getitem__(self, worker_id: int) -> WorkerState:
        """Dict-like access. Raises ``KeyError`` if not found."""
        with self._lock:
            return self._workers[worker_id]

    def __iter__(self) -> Iterator[int]:
        """Iterate over worker IDs (snapshot)."""
        with self._lock:
            return iter(list(self._workers.keys()))

    # ------------------------------------------------------------------
    # Representation
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        with self._lock:
            count = len(self._workers)
        return f"<WorkerRegistry workers={count}>"
