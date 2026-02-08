"""Integration tests for worker metrics system."""

import json
from datetime import datetime, timedelta
from pathlib import Path

from click.testing import CliRunner

from zerg.cli import cli
from zerg.constants import TaskStatus, WorkerStatus
from zerg.metrics import MetricsCollector
from zerg.state import StateManager
from zerg.types import FeatureMetrics


class TestMetricsPersistence:
    """Tests for metrics persistence to state file."""

    def test_metrics_persist_to_state(self, tmp_path: Path) -> None:
        """Metrics are saved to and loaded from state file."""
        # Create state manager with temp directory
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)

        state = StateManager("test-persist", state_dir=state_dir)
        state.load()

        # Add some task data
        state.set_task_status("T-001", "complete", worker_id=0)
        state._persistence._state["tasks"]["T-001"]["started_at"] = "2026-01-27T10:00:00"
        state._persistence._state["tasks"]["T-001"]["completed_at"] = "2026-01-27T10:01:00"
        state._persistence._state["tasks"]["T-001"]["duration_ms"] = 60000
        state.save()

        # Compute and store metrics
        collector = MetricsCollector(state)
        metrics = collector.compute_feature_metrics()
        state.store_metrics(metrics)

        # Reload state and verify metrics persisted
        state2 = StateManager("test-persist", state_dir=state_dir)
        state2.load()

        retrieved = state2.get_metrics()

        assert retrieved is not None
        assert retrieved.tasks_completed == 1
        assert isinstance(retrieved, FeatureMetrics)

    def test_metrics_overwrite_on_recompute(self, tmp_path: Path) -> None:
        """Recomputing metrics overwrites previous values."""
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)

        state = StateManager("test-overwrite", state_dir=state_dir)
        state.load()

        # First computation
        state.set_task_status("T-001", TaskStatus.COMPLETE, worker_id=0)
        collector = MetricsCollector(state)
        state.store_metrics(collector.compute_feature_metrics())

        first_metrics = state.get_metrics()
        assert first_metrics is not None
        assert first_metrics.tasks_completed == 1

        # Add another task and recompute
        state.set_task_status("T-002", TaskStatus.COMPLETE, worker_id=0)
        state.store_metrics(collector.compute_feature_metrics())

        second_metrics = state.get_metrics()
        assert second_metrics is not None
        assert second_metrics.tasks_completed == 2


class TestMetricsWithStateManager:
    """Tests for StateManager metrics methods."""

    def test_record_task_claimed(self, tmp_path: Path) -> None:
        """record_task_claimed sets claimed_at timestamp."""
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)

        state = StateManager("test-claimed", state_dir=state_dir)
        state.load()

        # Record claim
        state.record_task_claimed("T-001", worker_id=0)

        # Verify claimed_at is set
        task_state = state._persistence._state.get("tasks", {}).get("T-001", {})
        assert "claimed_at" in task_state
        assert task_state["worker_id"] == 0

    def test_record_task_duration(self, tmp_path: Path) -> None:
        """record_task_duration sets duration_ms field."""
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)

        state = StateManager("test-duration", state_dir=state_dir)
        state.load()

        # Create task first
        state.set_task_status("T-001", TaskStatus.IN_PROGRESS, worker_id=0)

        # Record duration
        state.record_task_duration("T-001", 45000)

        # Verify duration is set
        task_state = state._persistence._state.get("tasks", {}).get("T-001", {})
        assert task_state.get("duration_ms") == 45000


class TestStatusCommandMetrics:
    """Tests for metrics in status command output."""

    def test_json_status_includes_metrics(self, tmp_path: Path, monkeypatch) -> None:
        """Status --json output includes metrics section."""
        # Set up state
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)

        state = StateManager("test-json-metrics", state_dir=state_dir)
        state.load()
        state.set_task_status("T-001", TaskStatus.COMPLETE, worker_id=0)
        state._persistence._state["tasks"]["T-001"]["duration_ms"] = 30000
        state.save()

        # Compute and store metrics
        collector = MetricsCollector(state)
        state.store_metrics(collector.compute_feature_metrics())

        # Patch StateManager in the status command module so the CLI reads
        # from the same tmp_path state directory the test populated above.
        # NOTE: ``import zerg.commands.status`` resolves to the Click command
        # object (due to re-export in __init__.py), so we grab the real module
        # from sys.modules.
        import sys

        status_mod = sys.modules["zerg.commands.status"]

        _OrigStateManager = StateManager

        class _PatchedStateManager(_OrigStateManager):
            def __init__(self, feature: str, state_dir_arg: str | Path | None = None) -> None:
                super().__init__(feature, state_dir=state_dir_arg or state_dir)

        monkeypatch.setattr(status_mod, "StateManager", _PatchedStateManager)

        # Run status command with --json
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["status", "--feature", "test-json-metrics", "--json"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, f"CLI failed with output:\n{result.output}"
        output = json.loads(result.output)
        assert "metrics" in output

    def test_status_displays_without_crash(self, tmp_path: Path) -> None:
        """Status command doesn't crash when displaying metrics."""
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)

        state = StateManager("test-no-crash", state_dir=state_dir)
        state.load()

        # Empty state should not crash metrics computation
        collector = MetricsCollector(state)
        metrics = collector.compute_feature_metrics()

        # Verify we got valid metrics (even if empty)
        assert metrics.tasks_total == 0
        assert metrics.workers_used == 0


class TestMetricsAccuracy:
    """Tests for metrics calculation accuracy."""

    def test_level_percentiles_accurate(self, tmp_path: Path) -> None:
        """Level p50/p95 calculations are accurate."""
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)

        state = StateManager("test-percentiles", state_dir=state_dir)
        state.load()

        # Add tasks with known durations.
        # set_task_status uses _atomic_update which reloads from disk,
        # so we must set all statuses first, then add extra fields.
        durations = [10000, 20000, 30000, 40000, 50000]
        for i in range(len(durations)):
            state.set_task_status(f"T-{i:03d}", TaskStatus.COMPLETE, worker_id=0)

        # Now reload and add level/duration metadata
        state.load()
        for i, duration in enumerate(durations):
            task_id = f"T-{i:03d}"
            state._persistence._state["tasks"][task_id]["level"] = 1
            state._persistence._state["tasks"][task_id]["duration_ms"] = duration

        state._persistence._state["levels"] = {"1": {"status": "complete"}}
        state.save()

        # Compute level metrics
        collector = MetricsCollector(state)
        level_metrics = collector.compute_level_metrics(1)

        # Verify
        assert level_metrics.task_count == 5
        assert level_metrics.completed_count == 5
        assert level_metrics.p50_duration_ms == 30000  # Median
        assert level_metrics.avg_task_duration_ms == 30000.0  # Average

    def test_worker_uptime_calculation(self, tmp_path: Path) -> None:
        """Worker uptime is calculated correctly."""
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)

        state = StateManager("test-uptime", state_dir=state_dir)
        state.load()

        # Set worker with started_at in the past
        past = datetime.now() - timedelta(minutes=5)
        state._persistence._state["workers"] = {
            "0": {
                "worker_id": 0,
                "status": WorkerStatus.READY.value,
                "started_at": past.isoformat(),
                "ready_at": (past + timedelta(seconds=2)).isoformat(),
                "tasks_completed": 3,
                "context_usage": 0.5,
            }
        }
        state.save()

        # Compute worker metrics
        collector = MetricsCollector(state)
        worker_metrics = collector.compute_worker_metrics(0)

        # Uptime should be roughly 5 minutes (300000ms)
        # Allow some tolerance for test execution time
        assert worker_metrics.uptime_ms > 290000  # At least ~4:50
        assert worker_metrics.uptime_ms < 320000  # At most ~5:20

    def test_worker_initialization_time_accurate(self, tmp_path: Path) -> None:
        """Worker initialization time calculation is accurate."""
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)

        state = StateManager("test-init-time", state_dir=state_dir)
        state.load()

        # Set worker with known init time
        started = datetime.now() - timedelta(minutes=10)
        ready = started + timedelta(seconds=5)  # 5 second init time = 5000ms

        state._persistence._state["workers"] = {
            "0": {
                "worker_id": 0,
                "status": WorkerStatus.READY.value,
                "started_at": started.isoformat(),
                "ready_at": ready.isoformat(),
                "tasks_completed": 0,
                "context_usage": 0.0,
            }
        }
        state.save()

        # Compute worker metrics
        collector = MetricsCollector(state)
        worker_metrics = collector.compute_worker_metrics(0)

        # Initialization time should be 5000ms
        assert worker_metrics.initialization_ms == 5000


class TestMetricsCleanup:
    """Tests for metrics cleanup and state management."""

    def test_metrics_cleanup_on_delete(self, tmp_path: Path) -> None:
        """State delete removes metrics file."""
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)

        state = StateManager("test-cleanup", state_dir=state_dir)
        state.load()
        state.save()

        # Verify file exists
        state_file = state_dir / "test-cleanup.json"
        assert state_file.exists()

        # Delete state
        state.delete()

        # Verify file is gone
        assert not state_file.exists()

    def test_metrics_none_when_not_stored(self, tmp_path: Path) -> None:
        """get_metrics returns None when no metrics stored."""
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)

        state = StateManager("test-no-metrics", state_dir=state_dir)
        state.load()

        # No metrics stored yet
        retrieved = state.get_metrics()
        assert retrieved is None


class TestMetricsEdgeCases:
    """Tests for edge cases in metrics computation."""

    def test_metrics_with_no_tasks(self, tmp_path: Path) -> None:
        """Metrics computation handles empty task list."""
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)

        state = StateManager("test-empty", state_dir=state_dir)
        state.load()

        collector = MetricsCollector(state)
        metrics = collector.compute_feature_metrics()

        assert metrics.tasks_total == 0
        assert metrics.tasks_completed == 0
        assert metrics.tasks_failed == 0

    def test_metrics_with_no_workers(self, tmp_path: Path) -> None:
        """Metrics computation handles empty worker list."""
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)

        state = StateManager("test-no-workers", state_dir=state_dir)
        state.load()

        collector = MetricsCollector(state)
        metrics = collector.compute_feature_metrics()

        assert metrics.workers_used == 0
        assert len(metrics.worker_metrics) == 0

    def test_level_metrics_with_no_tasks_in_level(self, tmp_path: Path) -> None:
        """Level metrics handles level with no tasks."""
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)

        state = StateManager("test-empty-level", state_dir=state_dir)
        state.load()
        state._persistence._state["levels"] = {"1": {"status": "complete"}}
        state.save()

        collector = MetricsCollector(state)
        level_metrics = collector.compute_level_metrics(1)

        assert level_metrics.task_count == 0
        assert level_metrics.p50_duration_ms == 0
        assert level_metrics.avg_task_duration_ms == 0.0

    def test_task_metrics_with_missing_timestamps(self, tmp_path: Path) -> None:
        """Task metrics handles missing timestamps gracefully."""
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)

        state = StateManager("test-missing-ts", state_dir=state_dir)
        state.load()

        # Create task without timestamps
        state._persistence._state["tasks"] = {"T-001": {"status": TaskStatus.IN_PROGRESS.value, "worker_id": 0}}
        state.save()

        collector = MetricsCollector(state)
        task_metrics = collector.compute_task_metrics("T-001")

        # All durations should be None when timestamps missing
        assert task_metrics.execution_duration_ms is None
        assert task_metrics.total_duration_ms is None

    def test_worker_metrics_with_failed_tasks(self, tmp_path: Path) -> None:
        """Worker metrics correctly counts failed tasks."""
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)

        state = StateManager("test-failed", state_dir=state_dir)
        state.load()

        # Add worker
        past = datetime.now() - timedelta(minutes=1)
        state._persistence._state["workers"] = {
            "0": {
                "worker_id": 0,
                "status": WorkerStatus.READY.value,
                "started_at": past.isoformat(),
                "tasks_completed": 0,
                "context_usage": 0.0,
            }
        }

        # Add completed and failed tasks
        state.set_task_status("T-001", TaskStatus.COMPLETE, worker_id=0)
        state.set_task_status("T-002", TaskStatus.COMPLETE, worker_id=0)
        state.set_task_status("T-003", TaskStatus.FAILED, worker_id=0)
        state.save()

        collector = MetricsCollector(state)
        worker_metrics = collector.compute_worker_metrics(0)

        assert worker_metrics.tasks_completed == 2
        assert worker_metrics.tasks_failed == 1
