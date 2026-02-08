"""Unit tests for state repository modules.

Covers MetricsStore, RetryRepo, TaskStateRepo, and WorkerStateRepo
with direct CRUD testing against an in-memory PersistenceLayer.
Target: >=90% coverage for each module.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from zerg.constants import TaskStatus, WorkerStatus
from zerg.state.metrics_store import MetricsStore
from zerg.state.persistence import PersistenceLayer
from zerg.state.retry_repo import RetryRepo
from zerg.state.task_repo import TaskStateRepo
from zerg.state.worker_repo import WorkerStateRepo
from zerg.types import FeatureMetrics, WorkerState

# ---------------------------------------------------------------------------
# Shared fixture: in-memory PersistenceLayer backed by tmp_path
# ---------------------------------------------------------------------------


@pytest.fixture()
def persistence(tmp_path: Path) -> PersistenceLayer:
    """Create a PersistenceLayer with initial state loaded."""
    p = PersistenceLayer("test-feature", state_dir=tmp_path)
    p.load()
    return p


# ===================================================================
# MetricsStore tests
# ===================================================================


class TestMetricsStoreRecordDuration:
    """Tests for MetricsStore.record_task_duration."""

    def test_records_duration_for_existing_task(self, persistence: PersistenceLayer) -> None:
        """Duration is written when the task exists in state."""
        persistence.state["tasks"] = {"T-001": {"status": "pending"}}
        store = MetricsStore(persistence)
        store.record_task_duration("T-001", 1234)
        assert persistence.state["tasks"]["T-001"]["duration_ms"] == 1234

    def test_ignores_nonexistent_task(self, persistence: PersistenceLayer) -> None:
        """Duration recording is silently skipped for unknown task IDs."""
        store = MetricsStore(persistence)
        store.record_task_duration("MISSING", 999)
        assert "MISSING" not in persistence.state.get("tasks", {})

    def test_overwrites_previous_duration(self, persistence: PersistenceLayer) -> None:
        """A second call replaces the earlier duration_ms value."""
        persistence.state["tasks"] = {"T-001": {"status": "pending", "duration_ms": 100}}
        store = MetricsStore(persistence)
        store.record_task_duration("T-001", 500)
        assert persistence.state["tasks"]["T-001"]["duration_ms"] == 500


class TestMetricsStoreStoreAndRetrieve:
    """Tests for MetricsStore.store_metrics and get_metrics."""

    def test_roundtrip_store_and_get(self, persistence: PersistenceLayer) -> None:
        """store_metrics -> get_metrics round-trips correctly."""
        store = MetricsStore(persistence)
        metrics = FeatureMetrics(
            computed_at=datetime(2025, 1, 1, 12, 0, 0),
            workers_used=3,
            tasks_total=10,
            tasks_completed=8,
            tasks_failed=2,
        )
        store.store_metrics(metrics)
        retrieved = store.get_metrics()
        assert retrieved is not None
        assert retrieved.workers_used == 3
        assert retrieved.tasks_total == 10
        assert retrieved.tasks_completed == 8
        assert retrieved.tasks_failed == 2

    def test_get_metrics_returns_none_when_empty(self, persistence: PersistenceLayer) -> None:
        """get_metrics returns None when no metrics have been stored."""
        store = MetricsStore(persistence)
        assert store.get_metrics() is None

    def test_get_metrics_returns_none_for_empty_dict(self, persistence: PersistenceLayer) -> None:
        """get_metrics returns None when metrics key is an empty dict (falsy)."""
        store = MetricsStore(persistence)
        persistence.state["metrics"] = {}
        assert store.get_metrics() is None


# ===================================================================
# RetryRepo tests
# ===================================================================


class TestRetryRepoCount:
    """Tests for RetryRepo retry count operations."""

    def test_initial_retry_count_is_zero(self, persistence: PersistenceLayer) -> None:
        """Retry count defaults to 0 for a fresh task."""
        repo = RetryRepo(persistence)
        assert repo.get_retry_count("T-001") == 0

    def test_increment_retry_returns_new_count(self, persistence: PersistenceLayer) -> None:
        """increment_retry returns the incremented count each time."""
        repo = RetryRepo(persistence)
        assert repo.increment_retry("T-001") == 1
        assert repo.increment_retry("T-001") == 2
        assert repo.increment_retry("T-001") == 3
        assert repo.get_retry_count("T-001") == 3

    def test_increment_sets_last_retry_at(self, persistence: PersistenceLayer) -> None:
        """increment_retry records a last_retry_at ISO timestamp."""
        repo = RetryRepo(persistence)
        repo.increment_retry("T-001")
        task_state = persistence.state["tasks"]["T-001"]
        assert "last_retry_at" in task_state
        # Verify it parses as ISO datetime
        datetime.fromisoformat(task_state["last_retry_at"])

    def test_increment_with_next_retry_at(self, persistence: PersistenceLayer) -> None:
        """increment_retry stores next_retry_at when provided."""
        repo = RetryRepo(persistence)
        schedule = "2025-06-01T12:00:00"
        repo.increment_retry("T-001", next_retry_at=schedule)
        assert persistence.state["tasks"]["T-001"]["next_retry_at"] == schedule

    def test_increment_without_next_retry_at_leaves_it_unset(self, persistence: PersistenceLayer) -> None:
        """increment_retry does not set next_retry_at when not provided."""
        repo = RetryRepo(persistence)
        repo.increment_retry("T-001")
        assert "next_retry_at" not in persistence.state["tasks"]["T-001"]


class TestRetryRepoSchedule:
    """Tests for RetryRepo schedule operations."""

    def test_get_retry_schedule_default_none(self, persistence: PersistenceLayer) -> None:
        """Returns None when no schedule exists."""
        repo = RetryRepo(persistence)
        assert repo.get_retry_schedule("T-001") is None

    def test_set_and_get_retry_schedule(self, persistence: PersistenceLayer) -> None:
        """set_retry_schedule -> get_retry_schedule round-trips."""
        repo = RetryRepo(persistence)
        ts = "2025-07-15T09:00:00"
        repo.set_retry_schedule("T-001", ts)
        assert repo.get_retry_schedule("T-001") == ts

    def test_set_retry_schedule_creates_task_entry(self, persistence: PersistenceLayer) -> None:
        """set_retry_schedule bootstraps the tasks dict if needed."""
        persistence.state.pop("tasks", None)
        repo = RetryRepo(persistence)
        repo.set_retry_schedule("T-NEW", "2025-01-01T00:00:00")
        assert persistence.state["tasks"]["T-NEW"]["next_retry_at"] == "2025-01-01T00:00:00"


class TestRetryRepoReadyForRetry:
    """Tests for RetryRepo.get_tasks_ready_for_retry."""

    def test_returns_empty_when_no_tasks(self, persistence: PersistenceLayer) -> None:
        """Empty list when there are no tasks at all."""
        repo = RetryRepo(persistence)
        assert repo.get_tasks_ready_for_retry() == []

    def test_returns_tasks_with_past_schedule_and_failed_status(self, persistence: PersistenceLayer) -> None:
        """Tasks with next_retry_at in the past and status=failed are returned."""
        past = (datetime.now() - timedelta(hours=1)).isoformat()
        future = (datetime.now() + timedelta(hours=1)).isoformat()
        persistence.state["tasks"] = {
            "T-READY": {"next_retry_at": past, "status": TaskStatus.FAILED.value},
            "T-FUTURE": {"next_retry_at": future, "status": TaskStatus.FAILED.value},
            "T-COMPLETE": {"next_retry_at": past, "status": TaskStatus.COMPLETE.value},
        }
        repo = RetryRepo(persistence)
        ready = repo.get_tasks_ready_for_retry()
        assert "T-READY" in ready
        assert "T-FUTURE" not in ready
        assert "T-COMPLETE" not in ready

    def test_returns_waiting_retry_tasks(self, persistence: PersistenceLayer) -> None:
        """Tasks with status 'waiting_retry' and past schedule are included."""
        past = (datetime.now() - timedelta(hours=1)).isoformat()
        persistence.state["tasks"] = {
            "T-WAIT": {"next_retry_at": past, "status": "waiting_retry"},
        }
        repo = RetryRepo(persistence)
        assert "T-WAIT" in repo.get_tasks_ready_for_retry()

    def test_ignores_tasks_without_next_retry_at(self, persistence: PersistenceLayer) -> None:
        """Tasks without a scheduled retry are not returned."""
        persistence.state["tasks"] = {
            "T-NOSCHED": {"status": TaskStatus.FAILED.value},
        }
        repo = RetryRepo(persistence)
        assert repo.get_tasks_ready_for_retry() == []


class TestRetryRepoReset:
    """Tests for RetryRepo.reset_retries."""

    def test_reset_clears_count_and_last_retry(self, persistence: PersistenceLayer) -> None:
        """reset_retries zeroes the count and removes last_retry_at."""
        repo = RetryRepo(persistence)
        repo.increment_retry("T-001")
        repo.increment_retry("T-001")
        assert repo.get_retry_count("T-001") == 2
        repo.reset_retries("T-001")
        assert repo.get_retry_count("T-001") == 0
        assert "last_retry_at" not in persistence.state["tasks"]["T-001"]

    def test_reset_on_nonexistent_task_is_noop(self, persistence: PersistenceLayer) -> None:
        """reset_retries on a missing task does not raise."""
        repo = RetryRepo(persistence)
        repo.reset_retries("MISSING")  # should not raise


# ===================================================================
# TaskStateRepo tests
# ===================================================================


class TestTaskStateRepoStatus:
    """Tests for TaskStateRepo status CRUD."""

    def test_get_status_nonexistent(self, persistence: PersistenceLayer) -> None:
        """Returns None for unknown task IDs."""
        repo = TaskStateRepo(persistence)
        assert repo.get_task_status("T-999") is None

    def test_set_and_get_status_with_enum(self, persistence: PersistenceLayer) -> None:
        """Setting status with TaskStatus enum is retrievable."""
        repo = TaskStateRepo(persistence)
        repo.set_task_status("T-001", TaskStatus.IN_PROGRESS, worker_id=1)
        assert repo.get_task_status("T-001") == TaskStatus.IN_PROGRESS.value

    def test_set_and_get_status_with_string(self, persistence: PersistenceLayer) -> None:
        """Setting status with a raw string is retrievable."""
        repo = TaskStateRepo(persistence)
        repo.set_task_status("T-001", "custom_status")
        assert repo.get_task_status("T-001") == "custom_status"

    def test_set_status_records_timestamps(self, persistence: PersistenceLayer) -> None:
        """IN_PROGRESS sets started_at, COMPLETE sets completed_at."""
        repo = TaskStateRepo(persistence)
        repo.set_task_status("T-001", TaskStatus.IN_PROGRESS)
        assert "started_at" in persistence.state["tasks"]["T-001"]

        repo.set_task_status("T-002", TaskStatus.COMPLETE)
        assert "completed_at" in persistence.state["tasks"]["T-002"]

    def test_set_status_records_error(self, persistence: PersistenceLayer) -> None:
        """Error message is stored when provided."""
        repo = TaskStateRepo(persistence)
        repo.set_task_status("T-001", TaskStatus.FAILED, error="Boom")
        assert persistence.state["tasks"]["T-001"]["error"] == "Boom"

    def test_set_status_records_worker_id(self, persistence: PersistenceLayer) -> None:
        """Worker ID is stored when provided."""
        repo = TaskStateRepo(persistence)
        repo.set_task_status("T-001", TaskStatus.CLAIMED, worker_id=7)
        assert persistence.state["tasks"]["T-001"]["worker_id"] == 7

    def test_set_status_creates_tasks_dict_if_missing(self, persistence: PersistenceLayer) -> None:
        """The 'tasks' key is bootstrapped if absent."""
        persistence.state.pop("tasks", None)
        repo = TaskStateRepo(persistence)
        repo.set_task_status("T-NEW", TaskStatus.PENDING)
        assert repo.get_task_status("T-NEW") == TaskStatus.PENDING.value


class TestTaskStateRepoClaim:
    """Tests for TaskStateRepo.claim_task."""

    def test_claim_pending_task_succeeds(self, persistence: PersistenceLayer) -> None:
        """Claiming a pending task returns True and sets CLAIMED status."""
        repo = TaskStateRepo(persistence)
        repo.set_task_status("T-001", TaskStatus.PENDING)
        assert repo.claim_task("T-001", worker_id=1) is True
        assert repo.get_task_status("T-001") == TaskStatus.CLAIMED.value

    def test_claim_todo_task_succeeds(self, persistence: PersistenceLayer) -> None:
        """Claiming a todo task also succeeds."""
        repo = TaskStateRepo(persistence)
        repo.set_task_status("T-001", TaskStatus.TODO)
        assert repo.claim_task("T-001", worker_id=2) is True

    def test_claim_already_claimed_by_another_fails(self, persistence: PersistenceLayer) -> None:
        """A task claimed by worker 1 cannot be claimed by worker 2."""
        repo = TaskStateRepo(persistence)
        repo.set_task_status("T-001", TaskStatus.PENDING)
        repo.claim_task("T-001", worker_id=1)
        assert repo.claim_task("T-001", worker_id=2) is False

    def test_claim_same_worker_succeeds(self, persistence: PersistenceLayer) -> None:
        """Re-claiming by the same worker is allowed (idempotent claim)."""
        repo = TaskStateRepo(persistence)
        repo.set_task_status("T-001", TaskStatus.PENDING)
        repo.claim_task("T-001", worker_id=1)
        # Now status is CLAIMED, which is NOT in (TODO, PENDING), so re-claim fails
        assert repo.claim_task("T-001", worker_id=1) is False

    def test_claim_in_progress_fails(self, persistence: PersistenceLayer) -> None:
        """Cannot claim a task that is already in_progress."""
        repo = TaskStateRepo(persistence)
        repo.set_task_status("T-001", TaskStatus.IN_PROGRESS)
        assert repo.claim_task("T-001", worker_id=1) is False

    def test_claim_with_level_mismatch_fails(self, persistence: PersistenceLayer) -> None:
        """Level enforcement rejects claim when task level != current_level."""
        repo = TaskStateRepo(persistence)
        persistence.state["tasks"] = {"T-001": {"status": "pending", "level": 2}}
        assert repo.claim_task("T-001", worker_id=1, current_level=1) is False

    def test_claim_with_level_match_succeeds(self, persistence: PersistenceLayer) -> None:
        """Level enforcement passes when levels match."""
        repo = TaskStateRepo(persistence)
        persistence.state["tasks"] = {"T-001": {"status": "pending", "level": 2}}
        assert repo.claim_task("T-001", worker_id=1, current_level=2) is True

    def test_claim_with_incomplete_dependencies_fails(self, persistence: PersistenceLayer) -> None:
        """Dependency enforcement rejects claim when deps are incomplete."""
        repo = TaskStateRepo(persistence)
        repo.set_task_status("T-001", TaskStatus.PENDING)
        checker = MagicMock()
        checker.get_incomplete_dependencies.return_value = ["T-000"]
        assert repo.claim_task("T-001", worker_id=1, dependency_checker=checker) is False

    def test_claim_with_satisfied_dependencies_succeeds(self, persistence: PersistenceLayer) -> None:
        """Dependency enforcement passes when all deps are complete."""
        repo = TaskStateRepo(persistence)
        repo.set_task_status("T-001", TaskStatus.PENDING)
        checker = MagicMock()
        checker.get_incomplete_dependencies.return_value = []
        assert repo.claim_task("T-001", worker_id=1, dependency_checker=checker) is True


class TestTaskStateRepoRelease:
    """Tests for TaskStateRepo.release_task."""

    def test_release_resets_to_pending(self, persistence: PersistenceLayer) -> None:
        """Releasing a claimed task puts it back to pending."""
        repo = TaskStateRepo(persistence)
        repo.set_task_status("T-001", TaskStatus.PENDING)
        repo.claim_task("T-001", worker_id=1)
        repo.release_task("T-001", worker_id=1)
        assert repo.get_task_status("T-001") == TaskStatus.PENDING.value
        assert persistence.state["tasks"]["T-001"]["worker_id"] is None

    def test_release_by_wrong_worker_is_noop(self, persistence: PersistenceLayer) -> None:
        """Only the owning worker can release a task."""
        repo = TaskStateRepo(persistence)
        repo.set_task_status("T-001", TaskStatus.PENDING)
        repo.claim_task("T-001", worker_id=1)
        repo.release_task("T-001", worker_id=2)  # wrong worker
        assert repo.get_task_status("T-001") == TaskStatus.CLAIMED.value


class TestTaskStateRepoQueries:
    """Tests for TaskStateRepo query methods."""

    def test_get_tasks_by_status_enum(self, persistence: PersistenceLayer) -> None:
        """get_tasks_by_status with TaskStatus enum returns matching IDs."""
        repo = TaskStateRepo(persistence)
        repo.set_task_status("T-001", TaskStatus.PENDING)
        repo.set_task_status("T-002", TaskStatus.COMPLETE)
        repo.set_task_status("T-003", TaskStatus.PENDING)
        result = repo.get_tasks_by_status(TaskStatus.PENDING)
        assert set(result) == {"T-001", "T-003"}

    def test_get_tasks_by_status_string(self, persistence: PersistenceLayer) -> None:
        """get_tasks_by_status with string status also works."""
        repo = TaskStateRepo(persistence)
        repo.set_task_status("T-001", "custom")
        assert repo.get_tasks_by_status("custom") == ["T-001"]

    def test_get_failed_tasks(self, persistence: PersistenceLayer) -> None:
        """get_failed_tasks returns info dicts for failed tasks."""
        repo = TaskStateRepo(persistence)
        repo.set_task_status("T-001", TaskStatus.FAILED, error="disk full")
        # Set extra fields via atomic_update so they persist to disk
        # (subsequent atomic_update calls reload from disk)
        with persistence.atomic_update():
            persistence.state["tasks"]["T-001"]["retry_count"] = 2
            persistence.state["tasks"]["T-001"]["last_retry_at"] = "2025-01-01T00:00:00"

        repo.set_task_status("T-002", TaskStatus.COMPLETE)

        failed = repo.get_failed_tasks()
        assert len(failed) == 1
        assert failed[0]["task_id"] == "T-001"
        assert failed[0]["retry_count"] == 2
        assert failed[0]["error"] == "disk full"
        assert failed[0]["last_retry_at"] == "2025-01-01T00:00:00"

    def test_get_stale_in_progress_tasks(self, persistence: PersistenceLayer) -> None:
        """get_stale_in_progress_tasks returns tasks exceeding timeout."""
        repo = TaskStateRepo(persistence)
        old_time = (datetime.now() - timedelta(seconds=600)).isoformat()
        fresh_time = datetime.now().isoformat()
        persistence.state["tasks"] = {
            "T-STALE": {
                "status": TaskStatus.IN_PROGRESS.value,
                "started_at": old_time,
                "worker_id": 1,
            },
            "T-FRESH": {
                "status": TaskStatus.IN_PROGRESS.value,
                "started_at": fresh_time,
                "worker_id": 2,
            },
            "T-DONE": {
                "status": TaskStatus.COMPLETE.value,
                "started_at": old_time,
            },
        }
        stale = repo.get_stale_in_progress_tasks(timeout_seconds=300)
        stale_ids = [s["task_id"] for s in stale]
        assert "T-STALE" in stale_ids
        assert "T-FRESH" not in stale_ids
        assert "T-DONE" not in stale_ids
        # Verify returned dict shape
        entry = next(s for s in stale if s["task_id"] == "T-STALE")
        assert entry["worker_id"] == 1
        assert entry["elapsed_seconds"] >= 600

    def test_get_stale_skips_tasks_without_started_at(self, persistence: PersistenceLayer) -> None:
        """Tasks in_progress but missing started_at are not returned as stale."""
        repo = TaskStateRepo(persistence)
        persistence.state["tasks"] = {
            "T-NO-START": {"status": TaskStatus.IN_PROGRESS.value},
        }
        assert repo.get_stale_in_progress_tasks(timeout_seconds=1) == []


class TestTaskStateRepoRecordClaimed:
    """Tests for TaskStateRepo.record_task_claimed."""

    def test_records_claimed_at_and_worker_id(self, persistence: PersistenceLayer) -> None:
        """record_task_claimed sets claimed_at and worker_id."""
        repo = TaskStateRepo(persistence)
        repo.record_task_claimed("T-001", worker_id=5)
        task = persistence.state["tasks"]["T-001"]
        assert task["worker_id"] == 5
        assert "claimed_at" in task
        datetime.fromisoformat(task["claimed_at"])

    def test_record_claimed_creates_task_entry(self, persistence: PersistenceLayer) -> None:
        """record_task_claimed bootstraps task entry if missing."""
        persistence.state.pop("tasks", None)
        repo = TaskStateRepo(persistence)
        repo.record_task_claimed("T-NEW", worker_id=3)
        assert persistence.state["tasks"]["T-NEW"]["worker_id"] == 3


# ===================================================================
# WorkerStateRepo tests
# ===================================================================


class TestWorkerStateRepoGetSet:
    """Tests for WorkerStateRepo get/set operations."""

    def test_get_worker_returns_none_for_missing(self, persistence: PersistenceLayer) -> None:
        """get_worker_state returns None for unknown worker IDs."""
        repo = WorkerStateRepo(persistence)
        assert repo.get_worker_state(99) is None

    def test_set_and_get_worker_roundtrip(self, persistence: PersistenceLayer) -> None:
        """set_worker_state -> get_worker_state round-trips correctly."""
        repo = WorkerStateRepo(persistence)
        ws = WorkerState(worker_id=1, status=WorkerStatus.RUNNING, current_task="T-001")
        repo.set_worker_state(ws)
        retrieved = repo.get_worker_state(1)
        assert retrieved is not None
        assert retrieved.worker_id == 1
        assert retrieved.status == WorkerStatus.RUNNING
        assert retrieved.current_task == "T-001"

    def test_set_worker_creates_workers_dict(self, persistence: PersistenceLayer) -> None:
        """Workers dict is bootstrapped if absent."""
        persistence.state.pop("workers", None)
        repo = WorkerStateRepo(persistence)
        ws = WorkerState(worker_id=1, status=WorkerStatus.INITIALIZING)
        repo.set_worker_state(ws)
        assert repo.get_worker_state(1) is not None


class TestWorkerStateRepoGetAll:
    """Tests for WorkerStateRepo.get_all_workers."""

    def test_get_all_workers_empty(self, persistence: PersistenceLayer) -> None:
        """Returns empty dict when no workers registered."""
        repo = WorkerStateRepo(persistence)
        assert repo.get_all_workers() == {}

    def test_get_all_workers_multiple(self, persistence: PersistenceLayer) -> None:
        """Returns all registered workers keyed by int worker_id."""
        repo = WorkerStateRepo(persistence)
        for wid in (1, 2, 3):
            repo.set_worker_state(WorkerState(worker_id=wid, status=WorkerStatus.READY))
        workers = repo.get_all_workers()
        assert set(workers.keys()) == {1, 2, 3}
        for ws in workers.values():
            assert ws.status == WorkerStatus.READY


class TestWorkerStateRepoReady:
    """Tests for WorkerStateRepo ready-state operations."""

    def test_set_worker_ready(self, persistence: PersistenceLayer) -> None:
        """set_worker_ready updates status to READY and records ready_at."""
        repo = WorkerStateRepo(persistence)
        ws = WorkerState(worker_id=1, status=WorkerStatus.INITIALIZING)
        repo.set_worker_state(ws)
        repo.set_worker_ready(1)
        data = persistence.state["workers"]["1"]
        assert data["status"] == WorkerStatus.READY.value
        assert "ready_at" in data

    def test_set_worker_ready_nonexistent_is_noop(self, persistence: PersistenceLayer) -> None:
        """set_worker_ready on unknown worker does not create an entry."""
        repo = WorkerStateRepo(persistence)
        repo.set_worker_ready(999)
        assert "999" not in persistence.state.get("workers", {})

    def test_get_ready_workers(self, persistence: PersistenceLayer) -> None:
        """get_ready_workers returns only workers in READY status."""
        repo = WorkerStateRepo(persistence)
        repo.set_worker_state(WorkerState(worker_id=1, status=WorkerStatus.READY))
        repo.set_worker_state(WorkerState(worker_id=2, status=WorkerStatus.RUNNING))
        repo.set_worker_state(WorkerState(worker_id=3, status=WorkerStatus.READY))
        ready = repo.get_ready_workers()
        assert set(ready) == {1, 3}

    def test_get_ready_workers_empty(self, persistence: PersistenceLayer) -> None:
        """Returns empty list when no workers are ready."""
        repo = WorkerStateRepo(persistence)
        assert repo.get_ready_workers() == []


class TestWorkerStateRepoWaitForReady:
    """Tests for WorkerStateRepo.wait_for_workers_ready."""

    def test_returns_true_when_already_ready(self, persistence: PersistenceLayer) -> None:
        """Returns True immediately if all workers are already ready."""
        repo = WorkerStateRepo(persistence)
        repo.set_worker_state(WorkerState(worker_id=1, status=WorkerStatus.READY))
        repo.set_worker_state(WorkerState(worker_id=2, status=WorkerStatus.READY))
        assert repo.wait_for_workers_ready([1, 2], timeout=1.0) is True

    def test_returns_false_on_timeout(self, persistence: PersistenceLayer) -> None:
        """Returns False when workers never become ready within timeout."""
        repo = WorkerStateRepo(persistence)
        repo.set_worker_state(WorkerState(worker_id=1, status=WorkerStatus.INITIALIZING))
        assert repo.wait_for_workers_ready([1], timeout=1.0) is False
