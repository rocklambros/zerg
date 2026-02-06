"""Tests for ZERG Worker Metrics module."""

import json
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from zerg.worker_metrics import (
    LevelMetrics,
    TaskExecutionMetrics,
    WorkerMetrics,
    WorkerMetricsCollector,
    estimate_execution_cost,
)


class TestTaskExecutionMetrics:
    """Tests for TaskExecutionMetrics dataclass."""

    def test_creation_defaults_and_complete(self):
        """Test creation, defaults, and completing a task."""
        metrics = TaskExecutionMetrics(
            task_id="T1",
            worker_id=0,
            started_at=datetime.now(),
        )
        assert metrics.task_id == "T1"
        assert metrics.status == "running"
        assert metrics.completed_at is None
        assert metrics.retry_count == 0

        time.sleep(0.01)
        metrics.complete(status="completed", context_usage=0.5)
        assert metrics.status == "completed"
        assert metrics.completed_at is not None
        assert metrics.duration_seconds >= 0.01

    def test_complete_with_error(self):
        """Test completing with error."""
        metrics = TaskExecutionMetrics(task_id="T1", worker_id=0, started_at=datetime.now())
        metrics.complete(status="failed", error_message="Test error")
        assert metrics.status == "failed"
        assert metrics.error_message == "Test error"

    def test_to_dict(self):
        """Test serialization to dictionary."""
        metrics = TaskExecutionMetrics(task_id="T1", worker_id=0, started_at=datetime.now(), context_usage_before=0.2)
        metrics.complete(status="completed", context_usage=0.4)
        data = metrics.to_dict()
        assert data["task_id"] == "T1"
        assert data["status"] == "completed"
        assert data["context_delta"] == pytest.approx(0.2, abs=0.001)


class TestWorkerMetrics:
    """Tests for WorkerMetrics dataclass."""

    def test_creation_and_properties(self):
        """Test creation and computed properties."""
        metrics = WorkerMetrics(worker_id=0)
        assert metrics.tasks_completed == 0
        assert metrics.success_rate == 0.0

        metrics.tasks_completed = 8
        metrics.tasks_failed = 2
        assert metrics.total_tasks == 10
        assert metrics.success_rate == 0.8

    def test_start_and_complete_task(self):
        """Test starting and completing a task."""
        metrics = WorkerMetrics(worker_id=0)
        task_metrics = metrics.start_task("T1", context_usage=0.3)
        assert metrics.current_task == "T1"
        assert task_metrics.context_usage_before == 0.3

        time.sleep(0.01)
        metrics.complete_task("T1", status="completed", context_usage=0.5)
        assert metrics.current_task is None
        assert metrics.tasks_completed == 1
        assert metrics.peak_context_usage == 0.5

    def test_complete_task_failed_and_skipped(self):
        """Test completing failed and skipped tasks."""
        metrics = WorkerMetrics(worker_id=0)
        metrics.start_task("T1")
        metrics.complete_task("T1", status="failed", error_message="Error")
        assert metrics.tasks_failed == 1

        metrics.start_task("T2")
        metrics.complete_task("T2", status="skipped")
        assert metrics.tasks_skipped == 1

    def test_to_dict_and_from_dict(self):
        """Test serialization roundtrip."""
        metrics = WorkerMetrics(worker_id=0)
        metrics.start_task("T1")
        metrics.complete_task("T1", status="completed")
        data = metrics.to_dict()
        assert data["tasks_completed"] == 1
        assert data["success_rate"] == 1.0

        restored = WorkerMetrics.from_dict(
            {
                "worker_id": 1,
                "started_at": "2026-01-27T10:00:00",
                "tasks_completed": 5,
                "context_usage": 0.6,
            }
        )
        assert restored.worker_id == 1
        assert restored.tasks_completed == 5

    def test_stop_and_health_check(self):
        """Test stop and health check recording."""
        metrics = WorkerMetrics(worker_id=0)
        metrics.record_health_check(True)
        assert metrics.last_health_check_ok is True
        metrics.record_health_check(False)
        assert metrics.health_check_failures == 1
        metrics.stop()
        assert metrics.stopped_at is not None


class TestLevelMetrics:
    """Tests for LevelMetrics dataclass."""

    def test_creation_and_properties(self):
        """Test creation and computed properties."""
        metrics = LevelMetrics(level=1, total_tasks=5, completed_tasks=3, failed_tasks=2)
        assert metrics.is_complete is True
        assert metrics.success_rate == 0.6

    def test_duration_states(self):
        """Test duration in different states."""
        not_started = LevelMetrics(level=1)
        assert not_started.duration_seconds == 0.0

        running = LevelMetrics(level=1, started_at=datetime.now() - timedelta(seconds=30))
        assert running.duration_seconds >= 30.0


class TestWorkerMetricsCollector:
    """Tests for WorkerMetricsCollector class."""

    def test_register_and_get_worker(self, tmp_path: Path):
        """Test registering and retrieving workers."""
        collector = WorkerMetricsCollector(feature="test", metrics_dir=tmp_path / "metrics")
        worker = collector.register_worker(0)
        assert worker.worker_id == 0
        assert collector.get_worker(0) is worker
        assert collector.register_worker(0) is worker  # idempotent
        assert collector.get_worker(99) is None

    def test_level_lifecycle(self, tmp_path: Path):
        """Test starting and completing a level."""
        collector = WorkerMetricsCollector(feature="test", metrics_dir=tmp_path / "metrics")
        collector.start_level(level=1, total_tasks=5, worker_count=3)
        collector.record_task_completion(level=1, success=True)
        collector.record_task_completion(level=1, success=False)
        time.sleep(0.01)
        collector.complete_level(1)

        summary = collector.get_level_summary(1)
        assert summary["total_tasks"] == 5
        assert summary["completed_tasks"] == 1
        assert summary["failed_tasks"] == 1

    def test_get_summary(self, tmp_path: Path):
        """Test getting execution summary."""
        collector = WorkerMetricsCollector(feature="test", metrics_dir=tmp_path / "metrics")
        w0 = collector.register_worker(0)
        w0.start_task("T1")
        w0.complete_task("T1", status="completed")
        w1 = collector.register_worker(1)
        w1.start_task("T2")
        w1.complete_task("T2", status="failed")

        summary = collector.get_summary()
        assert summary["worker_count"] == 2
        assert summary["completed_tasks"] == 1
        assert summary["failed_tasks"] == 1

    def test_export(self, tmp_path: Path):
        """Test exporting metrics to JSON."""
        collector = WorkerMetricsCollector(feature="test", metrics_dir=tmp_path / "metrics")
        collector.register_worker(0).start_task("T1")
        collector.get_worker(0).complete_task("T1", status="completed")
        path = collector.export()
        assert path.exists()
        data = json.loads(path.read_text())
        assert "summary" in data
        assert "workers" in data


class TestEstimateExecutionCost:
    """Tests for cost estimation function."""

    @pytest.mark.parametrize(
        "model, expected",
        [
            ("sonnet", 10.2),
            ("opus", 51.0),
            ("haiku", 0.85),
        ],
    )
    def test_model_costs(self, model: str, expected: float):
        """Test cost estimation for different models."""
        cost = estimate_execution_cost(1_000_000, model=model)
        assert cost == pytest.approx(expected, abs=0.01)

    def test_unknown_model_defaults_to_sonnet(self):
        """Test unknown model defaults to Sonnet pricing."""
        assert estimate_execution_cost(1_000_000, model="unknown") == estimate_execution_cost(1_000_000, model="sonnet")
