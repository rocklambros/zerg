"""Unit tests for ZERG metrics collection and computation."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from zerg.constants import TaskStatus, WorkerStatus
from zerg.metrics import (
    MetricsCollector,
    calculate_percentile,
    duration_ms,
)
from zerg.state import StateManager
from zerg.types import (
    FeatureMetrics,
    LevelMetrics,
    TaskMetrics,
    WorkerMetrics,
    WorkerState,
)


class TestDurationMs:
    """Tests for duration_ms helper function."""

    @pytest.mark.parametrize(
        "start,end,expected",
        [
            (datetime(2026, 1, 27, 10, 0, 0), datetime(2026, 1, 27, 10, 0, 5), 5000),
            (datetime(2026, 1, 27, 10, 0, 0, 0), datetime(2026, 1, 27, 10, 0, 1, 500000), 1500),
            (datetime(2026, 1, 27, 10, 0, 10), datetime(2026, 1, 27, 10, 0, 5), -5000),
            ("2026-01-27T10:00:00", "2026-01-27T10:00:10", 10000),
        ],
        ids=["basic-5s", "milliseconds", "negative", "string-timestamps"],
    )
    def test_duration_ms_valid(self, start, end, expected) -> None:
        """duration_ms computes correct milliseconds for various input types."""
        assert duration_ms(start, end) == expected

    @pytest.mark.parametrize(
        "start,end",
        [(None, datetime(2026, 1, 27)), (datetime(2026, 1, 27), None), (None, None)],
        ids=["none-start", "none-end", "both-none"],
    )
    def test_duration_ms_none_returns_none(self, start, end) -> None:
        """duration_ms returns None when either timestamp is None."""
        assert duration_ms(start, end) is None

    def test_duration_ms_zero(self) -> None:
        """duration_ms returns 0 for same timestamp."""
        ts = datetime(2026, 1, 27, 10, 0, 0)
        assert duration_ms(ts, ts) == 0


class TestCalculatePercentile:
    """Tests for calculate_percentile function."""

    @pytest.mark.parametrize(
        "values,percentile,expected",
        [
            ([10, 20, 30, 40, 50], 50, 30),
            ([10, 20, 30, 40], 50, 25),
            ([10, 20, 30, 40, 50], 0, 10),
            ([10, 20, 30, 40, 50], 100, 50),
            ([50, 10, 40, 20, 30], 50, 30),
            ([], 50, 0),
            ([42], 50, 42),
        ],
        ids=["p50-odd", "p50-even", "p0-min", "p100-max", "unsorted", "empty", "single"],
    )
    def test_calculate_percentile(self, values, percentile, expected) -> None:
        """calculate_percentile returns correct values across edge cases."""
        assert calculate_percentile(values, percentile) == expected


class TestMetricsCollector:
    """Tests for MetricsCollector class."""

    @pytest.fixture
    def state_manager(self, tmp_path: Path) -> StateManager:
        """Create a state manager with test data."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        return manager

    @pytest.fixture
    def populated_state(self, state_manager: StateManager) -> StateManager:
        """Create state manager with populated test data."""
        now = datetime.now()
        for wid in range(2):
            worker = WorkerState(
                worker_id=wid,
                status=WorkerStatus.READY,
                port=49152 + wid,
                started_at=now - timedelta(minutes=10),
                ready_at=now - timedelta(minutes=9, seconds=30),
            )
            state_manager.set_worker_state(worker)

        state_manager._state["tasks"] = {
            "TASK-001": {
                "status": TaskStatus.COMPLETE.value,
                "worker_id": 0,
                "level": 1,
                "created_at": (now - timedelta(minutes=10)).isoformat(),
                "claimed_at": (now - timedelta(minutes=9)).isoformat(),
                "started_at": (now - timedelta(minutes=9)).isoformat(),
                "completed_at": (now - timedelta(minutes=5)).isoformat(),
                "duration_ms": 240000,
            },
            "TASK-002": {
                "status": TaskStatus.COMPLETE.value,
                "worker_id": 1,
                "level": 1,
                "created_at": (now - timedelta(minutes=10)).isoformat(),
                "claimed_at": (now - timedelta(minutes=8)).isoformat(),
                "started_at": (now - timedelta(minutes=8)).isoformat(),
                "completed_at": (now - timedelta(minutes=4)).isoformat(),
                "duration_ms": 240000,
            },
            "TASK-003": {
                "status": TaskStatus.FAILED.value,
                "worker_id": 0,
                "level": 2,
                "created_at": (now - timedelta(minutes=5)).isoformat(),
                "claimed_at": (now - timedelta(minutes=4)).isoformat(),
                "started_at": (now - timedelta(minutes=4)).isoformat(),
                "error": "Test failure",
            },
        }
        state_manager._state["levels"] = {
            "1": {
                "status": "complete",
                "started_at": (now - timedelta(minutes=10)).isoformat(),
                "completed_at": (now - timedelta(minutes=4)).isoformat(),
            },
            "2": {
                "status": "running",
                "started_at": (now - timedelta(minutes=4)).isoformat(),
            },
        }
        state_manager.save()
        return state_manager


class TestComputeWorkerMetrics(TestMetricsCollector):
    """Tests for compute_worker_metrics method."""

    def test_compute_worker_metrics(self, populated_state: StateManager) -> None:
        """Test computing metrics for a worker with tasks."""
        collector = MetricsCollector(populated_state)
        metrics = collector.compute_worker_metrics(0)
        assert isinstance(metrics, WorkerMetrics)
        assert metrics.worker_id == 0
        assert metrics.initialization_ms == 30000
        assert metrics.tasks_completed == 1
        assert metrics.tasks_failed == 1
        assert metrics.avg_task_duration_ms == 240000.0

    def test_compute_worker_metrics_no_tasks(self, state_manager: StateManager) -> None:
        """Test computing metrics for worker with no tasks."""
        now = datetime.now()
        worker = WorkerState(
            worker_id=5,
            status=WorkerStatus.READY,
            port=49157,
            started_at=now - timedelta(minutes=5),
            ready_at=now - timedelta(minutes=4),
        )
        state_manager.set_worker_state(worker)
        collector = MetricsCollector(state_manager)
        metrics = collector.compute_worker_metrics(5)
        assert metrics.tasks_completed == 0
        assert metrics.avg_task_duration_ms == 0.0


class TestComputeTaskMetrics(TestMetricsCollector):
    """Tests for compute_task_metrics method."""

    def test_compute_task_metrics_completed(self, populated_state: StateManager) -> None:
        """Test computing metrics for a completed task."""
        collector = MetricsCollector(populated_state)
        metrics = collector.compute_task_metrics("TASK-001")
        assert isinstance(metrics, TaskMetrics)
        assert metrics.queue_wait_ms == 60000
        assert metrics.execution_duration_ms is not None

    def test_compute_task_metrics_nonexistent(self, state_manager: StateManager) -> None:
        """Test computing metrics for non-existent task."""
        collector = MetricsCollector(state_manager)
        metrics = collector.compute_task_metrics("NONEXISTENT")
        assert metrics.queue_wait_ms is None


class TestComputeLevelMetrics(TestMetricsCollector):
    """Tests for compute_level_metrics method."""

    def test_compute_level_metrics_complete(self, populated_state: StateManager) -> None:
        """Test computing metrics for a completed level."""
        collector = MetricsCollector(populated_state)
        metrics = collector.compute_level_metrics(1)
        assert isinstance(metrics, LevelMetrics)
        assert metrics.duration_ms == 360000
        assert metrics.task_count == 2
        assert metrics.completed_count == 2

    def test_compute_level_metrics_with_failures(self, populated_state: StateManager) -> None:
        """Test computing metrics for level with failed tasks."""
        collector = MetricsCollector(populated_state)
        metrics = collector.compute_level_metrics(2)
        assert metrics.failed_count == 1
        assert metrics.duration_ms is None


class TestComputeFeatureMetrics(TestMetricsCollector):
    """Tests for compute_feature_metrics method."""

    def test_compute_feature_metrics(self, populated_state: StateManager) -> None:
        """Test computing aggregated feature metrics."""
        collector = MetricsCollector(populated_state)
        metrics = collector.compute_feature_metrics()
        assert isinstance(metrics, FeatureMetrics)
        assert metrics.workers_used == 2
        assert metrics.tasks_total == 3
        assert metrics.tasks_completed == 2
        assert metrics.tasks_failed == 1

    def test_compute_feature_metrics_empty(self, state_manager: StateManager) -> None:
        """Test computing feature metrics with empty state."""
        collector = MetricsCollector(state_manager)
        metrics = collector.compute_feature_metrics()
        assert metrics.workers_used == 0
        assert metrics.tasks_total == 0

    def test_feature_metrics_roundtrip(self, populated_state: StateManager) -> None:
        """Test that feature metrics survive serialization roundtrip."""
        collector = MetricsCollector(populated_state)
        original = collector.compute_feature_metrics()
        data = original.to_dict()
        restored = FeatureMetrics.from_dict(data)
        assert restored.workers_used == original.workers_used
        assert restored.tasks_total == original.tasks_total
        assert len(restored.worker_metrics) == len(original.worker_metrics)


class TestExportJson(TestMetricsCollector):
    """Tests for export_json method."""

    def test_export_json(self, populated_state: StateManager, tmp_path: Path) -> None:
        """Test exporting metrics to JSON file."""
        collector = MetricsCollector(populated_state)
        output_path = tmp_path / "metrics.json"
        collector.export_json(output_path)
        assert output_path.exists()
        with open(output_path) as f:
            data = json.load(f)
        assert data["workers_used"] == 2

    def test_export_json_creates_parent_dir(self, populated_state: StateManager, tmp_path: Path) -> None:
        """Test export_json creates parent directories if needed."""
        collector = MetricsCollector(populated_state)
        output_path = tmp_path / "subdir" / "nested" / "metrics.json"
        collector.export_json(output_path)
        assert output_path.exists()


class TestDataclassSerDe:
    """Tests for dataclass to_dict/from_dict methods."""

    def test_worker_metrics_roundtrip(self) -> None:
        """WorkerMetrics serialization and deserialization."""
        metrics = WorkerMetrics(
            worker_id=0,
            initialization_ms=5000,
            uptime_ms=600000,
            tasks_completed=10,
            tasks_failed=2,
            total_task_duration_ms=300000,
            avg_task_duration_ms=30000.0,
        )
        data = metrics.to_dict()
        restored = WorkerMetrics.from_dict(data)
        assert restored.worker_id == 0
        assert restored.tasks_completed == 10

    def test_worker_metrics_from_dict_defaults(self) -> None:
        """WorkerMetrics deserialization with missing fields uses defaults."""
        metrics = WorkerMetrics.from_dict({"worker_id": 2})
        assert metrics.initialization_ms is None
        assert metrics.tasks_completed == 0

    def test_task_metrics_roundtrip(self) -> None:
        """TaskMetrics serialization and deserialization."""
        metrics = TaskMetrics(
            task_id="TASK-001",
            queue_wait_ms=5000,
            execution_duration_ms=60000,
            total_duration_ms=66000,
        )
        data = metrics.to_dict()
        restored = TaskMetrics.from_dict(data)
        assert restored.task_id == "TASK-001"
        assert restored.queue_wait_ms == 5000

    def test_level_metrics_roundtrip(self) -> None:
        """LevelMetrics serialization and deserialization."""
        metrics = LevelMetrics(
            level=1,
            duration_ms=300000,
            task_count=5,
            completed_count=4,
            failed_count=1,
            avg_task_duration_ms=60000.0,
            p50_duration_ms=55000,
            p95_duration_ms=90000,
        )
        data = metrics.to_dict()
        restored = LevelMetrics.from_dict(data)
        assert restored.level == 1
        assert restored.p50_duration_ms == 55000
