"""State reconciliation for ZERG orchestrator.

Detects and resolves state inconsistencies between workers and orchestrator,
ensuring accurate level completion tracking and task state consistency.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from zerg.constants import TaskStatus
from zerg.logging import get_logger

if TYPE_CHECKING:
    from zerg.heartbeat import HeartbeatMonitor
    from zerg.levels import LevelController
    from zerg.state import StateManager

logger = get_logger("state_reconciler")


@dataclass
class ReconciliationFix:
    """A single fix applied during reconciliation."""

    fix_type: str
    task_id: str | None
    level: int | None
    worker_id: int | None
    old_value: Any
    new_value: Any
    reason: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging/serialization."""
        return {
            "fix_type": self.fix_type,
            "task_id": self.task_id,
            "level": self.level,
            "worker_id": self.worker_id,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "reason": self.reason,
        }


@dataclass
class ReconciliationResult:
    """Result of a reconciliation operation."""

    reconciliation_type: str  # "periodic" or "level_transition"
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    fixes_applied: list[ReconciliationFix] = field(default_factory=list)
    divergences_found: int = 0
    tasks_checked: int = 0
    workers_checked: int = 0
    level_checked: int | None = None
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """Check if reconciliation completed without errors."""
        return len(self.errors) == 0

    @property
    def had_fixes(self) -> bool:
        """Check if any fixes were applied."""
        return len(self.fixes_applied) > 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging/serialization."""
        return {
            "reconciliation_type": self.reconciliation_type,
            "timestamp": self.timestamp.isoformat(),
            "fixes_applied": [f.to_dict() for f in self.fixes_applied],
            "divergences_found": self.divergences_found,
            "tasks_checked": self.tasks_checked,
            "workers_checked": self.workers_checked,
            "level_checked": self.level_checked,
            "errors": self.errors,
            "success": self.success,
            "had_fixes": self.had_fixes,
        }


class StateReconciler:
    """Detect and fix state inconsistencies between workers and orchestrator.

    Responsibilities:
    - Periodic (every 60s): Light check comparing task states, log divergence
    - On level transitions: Thorough reconciliation before advancing
    - Fix inconsistencies:
      - Tasks in_progress with dead workers -> mark failed, requeue
      - Level marked "done" with incomplete tasks -> recalculate level status
      - Task level=None -> parse level from task ID pattern *-L{level}-*
    """

    # Pattern for extracting level from task ID: e.g., "RES-L3-003" -> level 3
    LEVEL_PATTERN = re.compile(r"-L(\d+)-")

    def __init__(
        self,
        state: StateManager,
        levels: LevelController,
        heartbeat_monitor: HeartbeatMonitor | None = None,
    ) -> None:
        """Initialize StateReconciler.

        Args:
            state: Shared state manager for reading/writing disk state.
            levels: In-memory level controller to keep in sync.
            heartbeat_monitor: Optional heartbeat monitor for stale worker detection.
        """
        self._state = state
        self._levels = levels
        self._heartbeat_monitor = heartbeat_monitor
        self._last_reconcile_at: datetime | None = None

    def reconcile_periodic(self) -> ReconciliationResult:
        """Perform light periodic reconciliation check (every 60s).

        This check:
        - Compares task states between disk and in-memory LevelController
        - Logs divergences without necessarily fixing all of them
        - Fixes critical issues (tasks with dead workers, missing levels)

        Returns:
            ReconciliationResult with details of checks and fixes applied.
        """
        result = ReconciliationResult(reconciliation_type="periodic")
        self._last_reconcile_at = result.timestamp

        try:
            # Check task states
            self._reconcile_task_states(result)

            # Check for tasks with missing level
            self._fix_missing_task_levels(result)

            # Check workers with stale heartbeats (if monitor available)
            if self._heartbeat_monitor:
                self._check_stale_workers(result)

        except Exception as e:
            result.errors.append(f"Periodic reconciliation failed: {e}")
            logger.error("Periodic reconciliation failed", exc_info=True)

        if result.had_fixes:
            logger.info(
                f"Periodic reconciliation applied {len(result.fixes_applied)} fixes "
                f"({result.divergences_found} divergences found)"
            )
        else:
            logger.debug(f"Periodic reconciliation: {result.tasks_checked} tasks checked, no fixes needed")

        return result

    def reconcile_level_transition(self, level: int) -> ReconciliationResult:
        """Perform thorough reconciliation before level advancement.

        This is called before advancing from level N to level N+1 and ensures:
        - All tasks in level N are truly in terminal state (complete or failed)
        - LevelController accurately reflects actual task states
        - No tasks are stuck in_progress with dead workers

        Args:
            level: The level being completed (about to transition FROM).

        Returns:
            ReconciliationResult with details of checks and fixes applied.
        """
        result = ReconciliationResult(
            reconciliation_type="level_transition",
            level_checked=level,
        )

        try:
            # First, fix any missing task levels
            self._fix_missing_task_levels(result)

            # Sync all task states from disk to LevelController
            self._reconcile_task_states(result, level_filter=level)

            # Check for tasks stuck in_progress
            self._fix_stuck_in_progress_tasks(result, level_filter=level)

            # Verify level completion accuracy
            self._verify_level_completion(result, level)

            # Final consistency check
            self._final_level_check(result, level)

        except Exception as e:
            result.errors.append(f"Level transition reconciliation failed: {e}")
            logger.error(f"Level {level} transition reconciliation failed", exc_info=True)

        if result.had_fixes:
            logger.info(f"Level {level} transition reconciliation applied {len(result.fixes_applied)} fixes")
        else:
            logger.info(f"Level {level} transition reconciliation: all checks passed")

        return result

    def parse_level_from_task_id(self, task_id: str) -> int | None:
        """Parse level from task ID pattern *-L{level}-*.

        Examples:
            "RES-L3-003" -> 3
            "COV-L1-001" -> 1
            "TASK-001" -> None (no level pattern)

        Args:
            task_id: Task identifier string.

        Returns:
            Level number if found, None otherwise.
        """
        match = self.LEVEL_PATTERN.search(task_id)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                return None
        return None

    def _reconcile_task_states(self, result: ReconciliationResult, level_filter: int | None = None) -> None:
        """Reconcile task states between disk and LevelController.

        Args:
            result: ReconciliationResult to update with findings.
            level_filter: If provided, only check tasks at this level.
        """
        tasks_state = self._state._state.get("tasks", {})

        for task_id, task_state in tasks_state.items():
            result.tasks_checked += 1

            # Apply level filter if specified
            task_level = task_state.get("level")
            if level_filter is not None and task_level != level_filter:
                continue

            disk_status = task_state.get("status", "")
            level_status = self._levels.get_task_status(task_id)

            # Check for divergence
            if disk_status != level_status:
                result.divergences_found += 1

                # Apply fix based on disk status (disk is source of truth)
                if disk_status == TaskStatus.COMPLETE.value:
                    if level_status != TaskStatus.COMPLETE.value:
                        self._levels.mark_task_complete(task_id)
                        result.fixes_applied.append(
                            ReconciliationFix(
                                fix_type="task_status_sync",
                                task_id=task_id,
                                level=task_level,
                                worker_id=task_state.get("worker_id"),
                                old_value=level_status,
                                new_value=disk_status,
                                reason="Disk shows complete, syncing to LevelController",
                            )
                        )

                elif disk_status == TaskStatus.FAILED.value:
                    if level_status != TaskStatus.FAILED.value:
                        self._levels.mark_task_failed(task_id)
                        result.fixes_applied.append(
                            ReconciliationFix(
                                fix_type="task_status_sync",
                                task_id=task_id,
                                level=task_level,
                                worker_id=task_state.get("worker_id"),
                                old_value=level_status,
                                new_value=disk_status,
                                reason="Disk shows failed, syncing to LevelController",
                            )
                        )

                elif disk_status in (
                    TaskStatus.IN_PROGRESS.value,
                    TaskStatus.CLAIMED.value,
                ):
                    if level_status not in (
                        TaskStatus.IN_PROGRESS.value,
                        TaskStatus.CLAIMED.value,
                    ):
                        worker_id = task_state.get("worker_id")
                        self._levels.mark_task_in_progress(task_id, worker_id)
                        result.fixes_applied.append(
                            ReconciliationFix(
                                fix_type="task_status_sync",
                                task_id=task_id,
                                level=task_level,
                                worker_id=worker_id,
                                old_value=level_status,
                                new_value=disk_status,
                                reason="Disk shows in_progress, syncing to LevelController",
                            )
                        )

    def _fix_missing_task_levels(self, result: ReconciliationResult) -> None:
        """Fix tasks with missing level by parsing from task ID.

        Args:
            result: ReconciliationResult to update with findings.
        """
        tasks_state = self._state._state.get("tasks", {})

        for task_id, task_state in tasks_state.items():
            current_level = task_state.get("level")

            if current_level is None:
                parsed_level = self.parse_level_from_task_id(task_id)
                if parsed_level is not None:
                    task_state["level"] = parsed_level
                    result.fixes_applied.append(
                        ReconciliationFix(
                            fix_type="level_parsed",
                            task_id=task_id,
                            level=parsed_level,
                            worker_id=task_state.get("worker_id"),
                            old_value=None,
                            new_value=parsed_level,
                            reason=f"Parsed level {parsed_level} from task ID pattern",
                        )
                    )
                    logger.info(f"Parsed level {parsed_level} for task {task_id}")

        # Save if any fixes were applied
        if any(f.fix_type == "level_parsed" for f in result.fixes_applied):
            self._state.save()

    def _fix_stuck_in_progress_tasks(self, result: ReconciliationResult, level_filter: int | None = None) -> None:
        """Fix tasks stuck in_progress with no active worker.

        Args:
            result: ReconciliationResult to update with findings.
            level_filter: If provided, only check tasks at this level.
        """
        tasks_state = self._state._state.get("tasks", {})
        workers_state = self._state._state.get("workers", {})

        # Build set of active worker IDs
        active_workers = {
            int(wid) for wid, w in workers_state.items() if w.get("status") in ("ready", "running", "idle")
        }

        for task_id, task_state in tasks_state.items():
            task_level = task_state.get("level")
            if level_filter is not None and task_level != level_filter:
                continue

            status = task_state.get("status", "")
            worker_id = task_state.get("worker_id")

            # Check if task is stuck: in_progress but worker is not active
            if status == TaskStatus.IN_PROGRESS.value and worker_id is not None:
                if worker_id not in active_workers:
                    # Mark task as failed with reason
                    self._state.set_task_status(
                        task_id,
                        TaskStatus.FAILED.value,
                        error_message="worker_crash",
                    )
                    self._levels.mark_task_failed(task_id, error=f"Worker {worker_id} crashed/stopped")

                    # Reset retry count since this is a crash, not a task bug
                    # (the task_retry_manager will handle requeueing)
                    self._state.reset_task_retry(task_id)

                    result.fixes_applied.append(
                        ReconciliationFix(
                            fix_type="stuck_task_recovered",
                            task_id=task_id,
                            level=task_level,
                            worker_id=worker_id,
                            old_value=TaskStatus.IN_PROGRESS.value,
                            new_value=TaskStatus.FAILED.value,
                            reason=f"Worker {worker_id} no longer active, marking failed for reassignment",
                        )
                    )
                    logger.warning(f"Task {task_id} stuck on dead worker {worker_id}, marked failed for reassignment")

    def _check_stale_workers(self, result: ReconciliationResult, timeout_seconds: int = 120) -> None:
        """Check for workers with stale heartbeats.

        Args:
            result: ReconciliationResult to update with findings.
            timeout_seconds: Heartbeat timeout threshold.
        """
        if not self._heartbeat_monitor:
            return

        workers_state = self._state._state.get("workers", {})
        worker_ids = [int(wid) for wid in workers_state.keys()]

        stale_workers = self._heartbeat_monitor.get_stalled_workers(worker_ids, timeout_seconds)

        for worker_id in stale_workers:
            result.workers_checked += 1
            logger.warning(f"Worker {worker_id} has stale heartbeat (>{timeout_seconds}s)")
            # Note: actual worker recovery is handled by the orchestrator,
            # we just detect and report here

    def _verify_level_completion(self, result: ReconciliationResult, level: int) -> None:
        """Verify that level completion status is accurate.

        Args:
            result: ReconciliationResult to update with findings.
            level: Level to verify.
        """
        # Get actual task states from disk
        tasks_state = self._state._state.get("tasks", {})

        level_tasks = [(tid, ts) for tid, ts in tasks_state.items() if ts.get("level") == level]

        total = len(level_tasks)
        complete = sum(1 for _, ts in level_tasks if ts.get("status") == TaskStatus.COMPLETE.value)
        failed = sum(1 for _, ts in level_tasks if ts.get("status") == TaskStatus.FAILED.value)
        resolved = complete + failed

        # Check if level status matches reality
        level_status = self._levels.get_level_status(level)
        if level_status:
            if level_status.completed_tasks != complete:
                logger.warning(
                    f"Level {level} completed_tasks mismatch: "
                    f"LevelController={level_status.completed_tasks}, disk={complete}"
                )
                result.divergences_found += 1

            if level_status.failed_tasks != failed:
                logger.warning(
                    f"Level {level} failed_tasks mismatch: LevelController={level_status.failed_tasks}, disk={failed}"
                )
                result.divergences_found += 1

            # Update LevelController if needed
            if level_status.completed_tasks != complete or level_status.failed_tasks != failed:
                level_status.completed_tasks = complete
                level_status.failed_tasks = failed
                result.fixes_applied.append(
                    ReconciliationFix(
                        fix_type="level_counts_corrected",
                        task_id=None,
                        level=level,
                        worker_id=None,
                        old_value={
                            "completed": level_status.completed_tasks,
                            "failed": level_status.failed_tasks,
                        },
                        new_value={"completed": complete, "failed": failed},
                        reason="Corrected level task counts from disk state",
                    )
                )

        # Log summary
        logger.info(
            f"Level {level} verification: {complete}/{total} complete, "
            f"{failed}/{total} failed, {resolved}/{total} resolved"
        )

    def _final_level_check(self, result: ReconciliationResult, level: int) -> None:
        """Final consistency check before level transition.

        Ensures:
        - All tasks at this level are in terminal state (complete or failed)
        - No tasks are stuck in_progress

        Args:
            result: ReconciliationResult to update with findings.
            level: Level to check.
        """
        tasks_state = self._state._state.get("tasks", {})

        stuck_tasks = []
        for task_id, task_state in tasks_state.items():
            if task_state.get("level") != level:
                continue

            status = task_state.get("status", "")
            if status not in (TaskStatus.COMPLETE.value, TaskStatus.FAILED.value):
                stuck_tasks.append((task_id, status))

        if stuck_tasks:
            for task_id, status in stuck_tasks:
                logger.error(
                    f"Task {task_id} still in '{status}' status at level {level} transition - this should not happen"
                )
                result.errors.append(f"Task {task_id} not in terminal state at level transition")
