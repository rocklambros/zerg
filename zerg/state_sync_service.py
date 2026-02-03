"""State synchronization service for ZERG orchestrator.

Syncs in-memory LevelController state with on-disk task state,
and reassigns tasks stranded on stopped/crashed workers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from zerg.constants import TaskStatus
from zerg.levels import LevelController
from zerg.logging import get_logger
from zerg.state import StateManager
from zerg.state_reconciler import ReconciliationResult, StateReconciler

if TYPE_CHECKING:
    from zerg.heartbeat import HeartbeatMonitor

logger = get_logger("state_sync")


class StateSyncService:
    """Synchronise LevelController with persisted task state.

    Dependencies are injected via ``__init__`` so the service remains
    decoupled from the Orchestrator and is independently testable.
    """

    def __init__(
        self,
        state: StateManager,
        levels: LevelController,
        heartbeat_monitor: HeartbeatMonitor | None = None,
    ) -> None:
        """Initialize StateSyncService.

        Args:
            state: Shared state manager for reading/writing disk state.
            levels: In-memory level controller to keep in sync.
            heartbeat_monitor: Optional heartbeat monitor for stale worker detection.
        """
        self.state = state
        self.levels = levels
        self._reconciler = StateReconciler(state, levels, heartbeat_monitor)

    def sync_from_disk(self) -> None:
        """Sync LevelController with task completions from disk state.

        Workers write task completions directly to the shared state JSON.
        The orchestrator's in-memory LevelController must be updated to
        reflect these completions so level advancement can trigger.
        """
        tasks_state = self.state._state.get("tasks", {})
        for task_id, task_state in tasks_state.items():
            disk_status = task_state.get("status", "")
            level_status = self.levels.get_task_status(task_id)

            # Task is complete on disk but not in LevelController
            complete = TaskStatus.COMPLETE.value
            if disk_status == complete and level_status != complete:
                self.levels.mark_task_complete(task_id)
                logger.info(f"Synced task {task_id} completion to LevelController")

            # Task is failed on disk but not in LevelController
            elif disk_status == TaskStatus.FAILED.value and level_status != TaskStatus.FAILED.value:
                self.levels.mark_task_failed(task_id)
                logger.info(f"Synced task {task_id} failure to LevelController")

            # Task is in progress on disk but not in LevelController
            elif disk_status in (TaskStatus.IN_PROGRESS.value, TaskStatus.CLAIMED.value):
                if level_status not in (TaskStatus.IN_PROGRESS.value, TaskStatus.CLAIMED.value):
                    worker_id = task_state.get("worker_id")
                    self.levels.mark_task_in_progress(task_id, worker_id)

    def reassign_stranded_tasks(self, active_worker_ids: set[int]) -> None:
        """Reassign tasks stuck on stopped/crashed workers.

        Args:
            active_worker_ids: Set of worker IDs that are still alive.
                The caller is responsible for computing this from both
                disk state AND in-memory workers.
        """
        tasks_state = self.state._state.get("tasks", {})
        for task_id, task_state in tasks_state.items():
            status = task_state.get("status", "")
            worker_id = task_state.get("worker_id")
            if (
                status in (TaskStatus.PENDING.value, TaskStatus.TODO.value, "pending", "todo")
                and worker_id is not None
                and worker_id not in active_worker_ids
            ):
                task_state["worker_id"] = None
                logger.info(
                    f"Reassigned stranded task {task_id} (was worker {worker_id}, now unassigned)"
                )
        self.state.save()

    def reconcile_periodic(self) -> ReconciliationResult:
        """Perform light periodic reconciliation check (every 60s).

        Delegates to StateReconciler for:
        - Comparing task states between disk and in-memory LevelController
        - Logging divergences
        - Fixing critical issues (tasks with dead workers, missing levels)

        Returns:
            ReconciliationResult with details of checks and fixes applied.
        """
        return self._reconciler.reconcile_periodic()

    def reconcile_level_transition(self, level: int) -> ReconciliationResult:
        """Perform thorough reconciliation before level advancement.

        Called before advancing from level N to level N+1 to ensure:
        - All tasks in level N are truly in terminal state (complete or failed)
        - LevelController accurately reflects actual task states
        - No tasks are stuck in_progress with dead workers

        Args:
            level: The level being completed (about to transition FROM).

        Returns:
            ReconciliationResult with details of checks and fixes applied.
        """
        return self._reconciler.reconcile_level_transition(level)
