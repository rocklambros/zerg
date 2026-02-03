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

    def test_duration_ms_valid_timestamps(self) -> None:
        """Test duration_ms with valid datetime timestamps."""
        start = datetime(2026, 1, 27, 10, 0, 0)
        end = datetime(2026, 1, 27, 10, 0, 5)  # 5 seconds later

        result = duration_ms(start, end)

        assert result == 5000  # 5 seconds = 5000 ms

    def test_duration_ms_with_milliseconds(self) -> None:
        """Test duration_ms captures millisecond precision."""
        start = datetime(2026, 1, 27, 10, 0, 0, 0)
        end = datetime(2026, 1, 27, 10, 0, 1, 500000)  # 1.5 seconds

        result = duration_ms(start, end)

        assert result == 1500

    def test_duration_ms_with_none_start(self) -> None:
        """Test duration_ms returns None when start is None."""
        end = datetime(2026, 1, 27, 10, 0, 0)

        result = duration_ms(None, end)

        assert result is None

    def test_duration_ms_with_none_end(self) -> None:
        """Test duration_ms returns None when end is None."""
        start = datetime(2026, 1, 27, 10, 0, 0)

        result = duration_ms(start, None)

        assert result is None

    def test_duration_ms_with_both_none(self) -> None:
        """Test duration_ms returns None when both timestamps are None."""
        result = duration_ms(None, None)

        assert result is None

    def test_duration_ms_with_strings(self) -> None:
        """Test duration_ms with ISO format string timestamps."""
        start = "2026-01-27T10:00:00"
        end = "2026-01-27T10:00:10"  # 10 seconds later

        result = duration_ms(start, end)

        assert result == 10000

    def test_duration_ms_with_mixed_types(self) -> None:
        """Test duration_ms with datetime start and string end."""
        start = datetime(2026, 1, 27, 10, 0, 0)
        end = "2026-01-27T10:00:05"

        result = duration_ms(start, end)

        assert result == 5000

    def test_duration_ms_negative_duration(self) -> None:
        """Test duration_ms with end before start returns negative."""
        start = datetime(2026, 1, 27, 10, 0, 10)
        end = datetime(2026, 1, 27, 10, 0, 5)  # 5 seconds before

        result = duration_ms(start, end)

        assert result == -5000

    def test_duration_ms_zero_duration(self) -> None:
        """Test duration_ms returns 0 for same timestamp."""
        timestamp = datetime(2026, 1, 27, 10, 0, 0)

        result = duration_ms(timestamp, timestamp)

        assert result == 0


class TestCalculatePercentile:
    """Tests for calculate_percentile function."""

    def test_calculate_percentile_p50_odd_count(self) -> None:
        """Test p50 with odd number of values."""
        values = [10, 20, 30, 40, 50]

        result = calculate_percentile(values, 50)

        assert result == 30

    def test_calculate_percentile_p50_even_count(self) -> None:
        """Test p50 with even number of values (interpolation)."""
        values = [10, 20, 30, 40]

        result = calculate_percentile(values, 50)

        # p50 at index 1.5, interpolate between 20 and 30
        assert result == 25

    def test_calculate_percentile_p95(self) -> None:
        """Test p95 calculation."""
        values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

        result = calculate_percentile(values, 95)

        # At 95th percentile of 10 items
        # Index = 0.95 * (10 - 1) = 8.55
        # Interpolate between values[8]=9 and values[9]=10
        assert result == 9 or result == 10  # Either due to interpolation

    def test_calculate_percentile_p99(self) -> None:
        """Test p99 calculation."""
        values = list(range(1, 101))  # 1 to 100

        result = calculate_percentile(values, 99)

        # Should be near 99
        assert 98 <= result <= 100

    def test_calculate_percentile_empty_list(self) -> None:
        """Test calculate_percentile returns 0 for empty list."""
        result = calculate_percentile([], 50)

        assert result == 0

    def test_calculate_percentile_single_value(self) -> None:
        """Test calculate_percentile with single value."""
        result = calculate_percentile([42], 50)

        assert result == 42

    def test_calculate_percentile_p0(self) -> None:
        """Test p0 returns minimum value."""
        values = [10, 20, 30, 40, 50]

        result = calculate_percentile(values, 0)

        assert result == 10

    def test_calculate_percentile_p100(self) -> None:
        """Test p100 returns maximum value."""
        values = [10, 20, 30, 40, 50]

        result = calculate_percentile(values, 100)

        assert result == 50

    def test_calculate_percentile_unsorted_input(self) -> None:
        """Test that unsorted input is sorted correctly."""
        values = [50, 10, 40, 20, 30]

        result = calculate_percentile(values, 50)

        assert result == 30  # Same as sorted [10, 20, 30, 40, 50]

    def test_calculate_percentile_with_floats(self) -> None:
        """Test calculate_percentile with float values."""
        values = [1.5, 2.5, 3.5, 4.5, 5.5]

        result = calculate_percentile(values, 50)

        assert result == 3  # Returns int


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

        # Add workers
        for wid in range(2):
            worker = WorkerState(
                worker_id=wid,
                status=WorkerStatus.READY,
                port=49152 + wid,
                started_at=now - timedelta(minutes=10),
                ready_at=now - timedelta(minutes=9, seconds=30),
            )
            state_manager.set_worker_state(worker)

        # Add tasks with timing data
        state_manager._state["tasks"] = {
            "TASK-001": {
                "status": TaskStatus.COMPLETE.value,
                "worker_id": 0,
                "level": 1,
                "created_at": (now - timedelta(minutes=10)).isoformat(),
                "claimed_at": (now - timedelta(minutes=9)).isoformat(),
                "started_at": (now - timedelta(minutes=9)).isoformat(),
                "completed_at": (now - timedelta(minutes=5)).isoformat(),
                "duration_ms": 240000,  # 4 minutes
            },
            "TASK-002": {
                "status": TaskStatus.COMPLETE.value,
                "worker_id": 1,
                "level": 1,
                "created_at": (now - timedelta(minutes=10)).isoformat(),
                "claimed_at": (now - timedelta(minutes=8)).isoformat(),
                "started_at": (now - timedelta(minutes=8)).isoformat(),
                "completed_at": (now - timedelta(minutes=4)).isoformat(),
                "duration_ms": 240000,  # 4 minutes
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

        # Add levels
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
        """Test computing metrics for a worker."""
        collector = MetricsCollector(populated_state)

        metrics = collector.compute_worker_metrics(0)

        assert isinstance(metrics, WorkerMetrics)
        assert metrics.worker_id == 0
        assert metrics.initialization_ms is not None
        assert metrics.initialization_ms == 30000  # 30 seconds
        assert metrics.uptime_ms > 0
        assert metrics.tasks_completed == 1
        assert metrics.tasks_failed == 1
        assert metrics.total_task_duration_ms == 240000
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

        assert metrics.worker_id == 5
        assert metrics.tasks_completed == 0
        assert metrics.tasks_failed == 0
        assert metrics.total_task_duration_ms == 0
        assert metrics.avg_task_duration_ms == 0.0

    def test_compute_worker_metrics_missing_timestamps(self, state_manager: StateManager) -> None:
        """Test computing metrics when worker has no timestamps."""
        worker = WorkerState(
            worker_id=6,
            status=WorkerStatus.INITIALIZING,
            port=49158,
        )
        state_manager.set_worker_state(worker)

        collector = MetricsCollector(state_manager)
        metrics = collector.compute_worker_metrics(6)

        assert metrics.initialization_ms is None
        assert metrics.uptime_ms == 0


class TestComputeTaskMetrics(TestMetricsCollector):
    """Tests for compute_task_metrics method."""

    def test_compute_task_metrics(self, populated_state: StateManager) -> None:
        """Test computing metrics for a completed task."""
        collector = MetricsCollector(populated_state)

        metrics = collector.compute_task_metrics("TASK-001")

        assert isinstance(metrics, TaskMetrics)
        assert metrics.task_id == "TASK-001"
        assert metrics.queue_wait_ms is not None
        assert metrics.queue_wait_ms == 60000  # 1 minute wait
        assert metrics.execution_duration_ms is not None
        assert metrics.total_duration_ms is not None

    def test_compute_task_metrics_incomplete_task(self, state_manager: StateManager) -> None:
        """Test computing metrics for task without completion."""
        now = datetime.now()
        state_manager._state["tasks"] = {
            "TASK-RUNNING": {
                "status": TaskStatus.IN_PROGRESS.value,
                "created_at": (now - timedelta(minutes=5)).isoformat(),
                "claimed_at": (now - timedelta(minutes=4)).isoformat(),
                "started_at": (now - timedelta(minutes=4)).isoformat(),
            }
        }
        state_manager.save()

        collector = MetricsCollector(state_manager)
        metrics = collector.compute_task_metrics("TASK-RUNNING")

        assert metrics.task_id == "TASK-RUNNING"
        assert metrics.queue_wait_ms is not None
        assert metrics.execution_duration_ms is None  # No completed_at
        assert metrics.total_duration_ms is None

    def test_compute_task_metrics_nonexistent_task(self, state_manager: StateManager) -> None:
        """Test computing metrics for non-existent task."""
        collector = MetricsCollector(state_manager)

        metrics = collector.compute_task_metrics("NONEXISTENT")

        assert metrics.task_id == "NONEXISTENT"
        assert metrics.queue_wait_ms is None
        assert metrics.execution_duration_ms is None


class TestComputeLevelMetrics(TestMetricsCollector):
    """Tests for compute_level_metrics method."""

    def test_compute_level_metrics(self, populated_state: StateManager) -> None:
        """Test computing metrics for a completed level."""
        collector = MetricsCollector(populated_state)

        metrics = collector.compute_level_metrics(1)

        assert isinstance(metrics, LevelMetrics)
        assert metrics.level == 1
        assert metrics.duration_ms is not None
        assert metrics.duration_ms == 360000  # 6 minutes
        assert metrics.task_count == 2
        assert metrics.completed_count == 2
        assert metrics.failed_count == 0
        assert metrics.avg_task_duration_ms == 240000.0
        assert metrics.p50_duration_ms == 240000
        assert metrics.p95_duration_ms == 240000

    def test_compute_level_metrics_with_failures(self, populated_state: StateManager) -> None:
        """Test computing metrics for level with failed tasks."""
        collector = MetricsCollector(populated_state)

        metrics = collector.compute_level_metrics(2)

        assert metrics.level == 2
        assert metrics.task_count == 1
        assert metrics.completed_count == 0
        assert metrics.failed_count == 1
        assert metrics.duration_ms is None  # Level not complete

    def test_compute_level_metrics_nonexistent_level(self, state_manager: StateManager) -> None:
        """Test computing metrics for non-existent level."""
        collector = MetricsCollector(state_manager)

        metrics = collector.compute_level_metrics(99)

        assert metrics.level == 99
        assert metrics.duration_ms is None
        assert metrics.task_count == 0


class TestComputeFeatureMetrics(TestMetricsCollector):
    """Tests for compute_feature_metrics method."""

    def test_compute_feature_metrics(self, populated_state: StateManager) -> None:
        """Test computing aggregated feature metrics."""
        collector = MetricsCollector(populated_state)

        metrics = collector.compute_feature_metrics()

        assert isinstance(metrics, FeatureMetrics)
        assert metrics.computed_at is not None
        assert metrics.total_duration_ms is not None
        assert metrics.workers_used == 2
        assert metrics.tasks_total == 3
        assert metrics.tasks_completed == 2
        assert metrics.tasks_failed == 1
        assert metrics.levels_completed == 1
        assert len(metrics.worker_metrics) == 2
        assert len(metrics.level_metrics) == 2

    def test_compute_feature_metrics_empty_state(self, state_manager: StateManager) -> None:
        """Test computing feature metrics with empty state."""
        collector = MetricsCollector(state_manager)

        metrics = collector.compute_feature_metrics()

        assert metrics.workers_used == 0
        assert metrics.tasks_total == 0
        assert metrics.tasks_completed == 0
        assert metrics.tasks_failed == 0
        assert len(metrics.worker_metrics) == 0
        assert len(metrics.level_metrics) == 0

    def test_feature_metrics_serialization(self, populated_state: StateManager) -> None:
        """Test that feature metrics can be serialized to dict."""
        collector = MetricsCollector(populated_state)

        metrics = collector.compute_feature_metrics()
        data = metrics.to_dict()

        assert "computed_at" in data
        assert "total_duration_ms" in data
        assert "workers_used" in data
        assert "worker_metrics" in data
        assert isinstance(data["worker_metrics"], list)

    def test_feature_metrics_roundtrip(self, populated_state: StateManager) -> None:
        """Test that feature metrics survive serialization roundtrip."""
        collector = MetricsCollector(populated_state)

        original = collector.compute_feature_metrics()
        data = original.to_dict()
        restored = FeatureMetrics.from_dict(data)

        assert restored.workers_used == original.workers_used
        assert restored.tasks_total == original.tasks_total
        assert restored.tasks_completed == original.tasks_completed
        assert len(restored.worker_metrics) == len(original.worker_metrics)
        assert len(restored.level_metrics) == len(original.level_metrics)


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

        assert "computed_at" in data
        assert "workers_used" in data
        assert data["workers_used"] == 2

    def test_export_json_creates_parent_dir(self, populated_state: StateManager, tmp_path: Path) -> None:
        """Test export_json creates parent directories if needed."""
        collector = MetricsCollector(populated_state)
        output_path = tmp_path / "subdir" / "nested" / "metrics.json"

        collector.export_json(output_path)

        assert output_path.exists()

    def test_export_json_with_string_path(self, populated_state: StateManager, tmp_path: Path) -> None:
        """Test export_json accepts string path."""
        collector = MetricsCollector(populated_state)
        output_path = str(tmp_path / "metrics_str.json")

        collector.export_json(output_path)

        assert Path(output_path).exists()


class TestWorkerMetricsDataclass:
    """Tests for WorkerMetrics dataclass methods."""

    def test_worker_metrics_to_dict(self) -> None:
        """Test WorkerMetrics serialization."""
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

        assert data["worker_id"] == 0
        assert data["initialization_ms"] == 5000
        assert data["uptime_ms"] == 600000
        assert data["tasks_completed"] == 10
        assert data["tasks_failed"] == 2
        assert data["avg_task_duration_ms"] == 30000.0

    def test_worker_metrics_from_dict(self) -> None:
        """Test WorkerMetrics deserialization."""
        data = {
            "worker_id": 1,
            "initialization_ms": 3000,
            "uptime_ms": 500000,
            "tasks_completed": 5,
            "tasks_failed": 1,
            "total_task_duration_ms": 200000,
            "avg_task_duration_ms": 40000.0,
        }

        metrics = WorkerMetrics.from_dict(data)

        assert metrics.worker_id == 1
        assert metrics.initialization_ms == 3000
        assert metrics.tasks_completed == 5

    def test_worker_metrics_from_dict_with_defaults(self) -> None:
        """Test WorkerMetrics deserialization with missing fields."""
        data = {"worker_id": 2}

        metrics = WorkerMetrics.from_dict(data)

        assert metrics.worker_id == 2
        assert metrics.initialization_ms is None
        assert metrics.uptime_ms == 0
        assert metrics.tasks_completed == 0


class TestTaskMetricsDataclass:
    """Tests for TaskMetrics dataclass methods."""

    def test_task_metrics_to_dict(self) -> None:
        """Test TaskMetrics serialization."""
        metrics = TaskMetrics(
            task_id="TASK-001",
            queue_wait_ms=5000,
            execution_duration_ms=60000,
            verification_duration_ms=1000,
            total_duration_ms=66000,
        )

        data = metrics.to_dict()

        assert data["task_id"] == "TASK-001"
        assert data["queue_wait_ms"] == 5000
        assert data["execution_duration_ms"] == 60000
        assert data["total_duration_ms"] == 66000

    def test_task_metrics_from_dict(self) -> None:
        """Test TaskMetrics deserialization."""
        data = {
            "task_id": "TASK-002",
            "queue_wait_ms": 2000,
            "execution_duration_ms": 30000,
        }

        metrics = TaskMetrics.from_dict(data)

        assert metrics.task_id == "TASK-002"
        assert metrics.queue_wait_ms == 2000
        assert metrics.verification_duration_ms is None


class TestLevelMetricsDataclass:
    """Tests for LevelMetrics dataclass methods."""

    def test_level_metrics_to_dict(self) -> None:
        """Test LevelMetrics serialization."""
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

        assert data["level"] == 1
        assert data["duration_ms"] == 300000
        assert data["task_count"] == 5
        assert data["p50_duration_ms"] == 55000
        assert data["p95_duration_ms"] == 90000

    def test_level_metrics_from_dict(self) -> None:
        """Test LevelMetrics deserialization."""
        data = {
            "level": 2,
            "duration_ms": 180000,
            "task_count": 3,
            "completed_count": 3,
            "failed_count": 0,
            "avg_task_duration_ms": 60000.0,
            "p50_duration_ms": 58000,
            "p95_duration_ms": 70000,
        }

        metrics = LevelMetrics.from_dict(data)

        assert metrics.level == 2
        assert metrics.duration_ms == 180000
        assert metrics.failed_count == 0


class TestFeatureMetricsDataclass:
    """Tests for FeatureMetrics dataclass methods."""

    def test_feature_metrics_to_dict(self) -> None:
        """Test FeatureMetrics serialization with nested metrics."""
        worker_metrics = [
            WorkerMetrics(worker_id=0, tasks_completed=5),
            WorkerMetrics(worker_id=1, tasks_completed=3),
        ]
        level_metrics = [
            LevelMetrics(level=1, task_count=5, completed_count=5),
            LevelMetrics(level=2, task_count=3, completed_count=3),
        ]

        metrics = FeatureMetrics(
            computed_at=datetime(2026, 1, 27, 12, 0, 0),
            total_duration_ms=600000,
            workers_used=2,
            tasks_total=8,
            tasks_completed=8,
            tasks_failed=0,
            levels_completed=2,
            worker_metrics=worker_metrics,
            level_metrics=level_metrics,
        )

        data = metrics.to_dict()

        assert data["computed_at"] == "2026-01-27T12:00:00"
        assert data["workers_used"] == 2
        assert data["tasks_total"] == 8
        assert len(data["worker_metrics"]) == 2
        assert len(data["level_metrics"]) == 2
        assert data["worker_metrics"][0]["worker_id"] == 0

    def test_feature_metrics_from_dict(self) -> None:
        """Test FeatureMetrics deserialization with nested metrics."""
        data = {
            "computed_at": "2026-01-27T12:00:00",
            "total_duration_ms": 500000,
            "workers_used": 2,
            "tasks_total": 6,
            "tasks_completed": 5,
            "tasks_failed": 1,
            "levels_completed": 2,
            "worker_metrics": [
                {"worker_id": 0, "tasks_completed": 3},
                {"worker_id": 1, "tasks_completed": 2},
            ],
            "level_metrics": [
                {"level": 1, "task_count": 4, "completed_count": 4},
            ],
        }

        metrics = FeatureMetrics.from_dict(data)

        assert metrics.computed_at == datetime(2026, 1, 27, 12, 0, 0)
        assert metrics.tasks_failed == 1
        assert len(metrics.worker_metrics) == 2
        assert metrics.worker_metrics[0].worker_id == 0
        assert len(metrics.level_metrics) == 1
        assert metrics.level_metrics[0].level == 1

    def test_feature_metrics_from_dict_empty_lists(self) -> None:
        """Test FeatureMetrics deserialization with empty metric lists."""
        data = {
            "computed_at": "2026-01-27T12:00:00",
            "total_duration_ms": 0,
            "workers_used": 0,
            "tasks_total": 0,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "levels_completed": 0,
            "worker_metrics": [],
            "level_metrics": [],
        }

        metrics = FeatureMetrics.from_dict(data)

        assert len(metrics.worker_metrics) == 0
        assert len(metrics.level_metrics) == 0
