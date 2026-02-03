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

    def test_creation(self):
        """Test TaskExecutionMetrics can be created."""
        metrics = TaskExecutionMetrics(
            task_id="T1",
            worker_id=0,
            started_at=datetime.now(),
        )
        assert metrics.task_id == "T1"
        assert metrics.worker_id == 0
        assert metrics.status == "running"

    def test_defaults(self):
        """Test default values."""
        metrics = TaskExecutionMetrics(
            task_id="T1",
            worker_id=0,
            started_at=datetime.now(),
        )
        assert metrics.completed_at is None
        assert metrics.duration_seconds is None
        assert metrics.context_usage_before == 0.0
        assert metrics.context_usage_after == 0.0
        assert metrics.retry_count == 0
        assert metrics.verification_passed is None
        assert metrics.error_message is None

    def test_complete(self):
        """Test completing a task."""
        metrics = TaskExecutionMetrics(
            task_id="T1",
            worker_id=0,
            started_at=datetime.now(),
        )
        time.sleep(0.01)
        metrics.complete(status="completed", context_usage=0.5)

        assert metrics.status == "completed"
        assert metrics.completed_at is not None
        assert metrics.duration_seconds is not None
        assert metrics.duration_seconds >= 0.01
        assert metrics.context_usage_after == 0.5

    def test_complete_with_verification(self):
        """Test completing with verification results."""
        metrics = TaskExecutionMetrics(
            task_id="T1",
            worker_id=0,
            started_at=datetime.now(),
        )
        metrics.complete(
            status="completed",
            verification_passed=True,
            verification_duration_ms=150,
        )

        assert metrics.verification_passed is True
        assert metrics.verification_duration_ms == 150

    def test_complete_with_error(self):
        """Test completing with error."""
        metrics = TaskExecutionMetrics(
            task_id="T1",
            worker_id=0,
            started_at=datetime.now(),
        )
        metrics.complete(status="failed", error_message="Test error")

        assert metrics.status == "failed"
        assert metrics.error_message == "Test error"

    def test_context_delta(self):
        """Test context delta calculation."""
        metrics = TaskExecutionMetrics(
            task_id="T1",
            worker_id=0,
            started_at=datetime.now(),
            context_usage_before=0.3,
        )
        metrics.complete(context_usage=0.5)

        assert metrics.context_delta == pytest.approx(0.2, abs=0.001)

    def test_to_dict(self):
        """Test serialization to dictionary."""
        metrics = TaskExecutionMetrics(
            task_id="T1",
            worker_id=0,
            started_at=datetime.now(),
            context_usage_before=0.2,
        )
        metrics.complete(status="completed", context_usage=0.4)

        data = metrics.to_dict()
        assert data["task_id"] == "T1"
        assert data["worker_id"] == 0
        assert data["status"] == "completed"
        assert "started_at" in data
        assert "completed_at" in data
        assert data["context_delta"] == pytest.approx(0.2, abs=0.001)


class TestWorkerMetrics:
    """Tests for WorkerMetrics dataclass."""

    def test_creation(self):
        """Test WorkerMetrics can be created."""
        metrics = WorkerMetrics(worker_id=0)
        assert metrics.worker_id == 0
        assert metrics.tasks_completed == 0
        assert metrics.tasks_failed == 0

    def test_total_tasks(self):
        """Test total_tasks property."""
        metrics = WorkerMetrics(worker_id=0)
        metrics.tasks_completed = 5
        metrics.tasks_failed = 2
        metrics.tasks_skipped = 1

        assert metrics.total_tasks == 8

    def test_success_rate(self):
        """Test success_rate calculation."""
        metrics = WorkerMetrics(worker_id=0)
        metrics.tasks_completed = 8
        metrics.tasks_failed = 2

        assert metrics.success_rate == 0.8

    def test_success_rate_no_tasks(self):
        """Test success_rate with no tasks."""
        metrics = WorkerMetrics(worker_id=0)
        assert metrics.success_rate == 0.0

    def test_uptime_seconds(self):
        """Test uptime_seconds calculation."""
        metrics = WorkerMetrics(
            worker_id=0,
            started_at=datetime.now() - timedelta(seconds=10),
        )
        assert metrics.uptime_seconds >= 10.0

    def test_uptime_seconds_stopped(self):
        """Test uptime_seconds when stopped."""
        start = datetime.now() - timedelta(seconds=30)
        stop = start + timedelta(seconds=20)
        metrics = WorkerMetrics(
            worker_id=0,
            started_at=start,
            stopped_at=stop,
        )
        assert metrics.uptime_seconds == 20.0

    def test_utilization(self):
        """Test utilization calculation."""
        metrics = WorkerMetrics(
            worker_id=0,
            started_at=datetime.now() - timedelta(seconds=100),
        )
        metrics.total_task_duration_seconds = 80.0

        # Allow some tolerance for elapsed time
        assert 0.75 <= metrics.utilization <= 0.85

    def test_avg_task_duration(self):
        """Test avg_task_duration calculation."""
        metrics = WorkerMetrics(worker_id=0)
        metrics.tasks_completed = 4
        metrics.tasks_failed = 1
        metrics.total_task_duration_seconds = 100.0

        assert metrics.avg_task_duration == 20.0

    def test_start_task(self):
        """Test starting a task."""
        metrics = WorkerMetrics(worker_id=0)
        task_metrics = metrics.start_task("T1", context_usage=0.3)

        assert metrics.current_task == "T1"
        assert task_metrics.task_id == "T1"
        assert task_metrics.worker_id == 0
        assert task_metrics.context_usage_before == 0.3
        assert len(metrics.task_history) == 1

    def test_complete_task(self):
        """Test completing a task."""
        metrics = WorkerMetrics(worker_id=0)
        metrics.start_task("T1")
        time.sleep(0.01)
        metrics.complete_task("T1", status="completed", context_usage=0.5)

        assert metrics.current_task is None
        assert metrics.tasks_completed == 1
        assert metrics.context_usage == 0.5
        assert metrics.peak_context_usage == 0.5

    def test_complete_task_failed(self):
        """Test completing a failed task."""
        metrics = WorkerMetrics(worker_id=0)
        metrics.start_task("T1")
        metrics.complete_task("T1", status="failed", error_message="Error")

        assert metrics.tasks_failed == 1
        assert metrics.task_history[0].error_message == "Error"

    def test_complete_task_skipped(self):
        """Test completing a skipped task."""
        metrics = WorkerMetrics(worker_id=0)
        metrics.start_task("T1")
        metrics.complete_task("T1", status="skipped")

        assert metrics.tasks_skipped == 1

    def test_record_context_reset(self):
        """Test recording context reset."""
        metrics = WorkerMetrics(worker_id=0)
        metrics.context_usage = 0.8
        metrics.record_context_reset()

        assert metrics.context_resets == 1
        assert metrics.context_usage == 0.0

    def test_record_health_check_success(self):
        """Test recording successful health check."""
        metrics = WorkerMetrics(worker_id=0)
        metrics.record_health_check(True)

        assert metrics.last_health_check_ok is True
        assert metrics.health_check_failures == 0
        assert metrics.last_health_check_at is not None

    def test_record_health_check_failure(self):
        """Test recording failed health check."""
        metrics = WorkerMetrics(worker_id=0)
        metrics.record_health_check(False)

        assert metrics.last_health_check_ok is False
        assert metrics.health_check_failures == 1

    def test_stop(self):
        """Test stopping worker."""
        metrics = WorkerMetrics(worker_id=0)
        metrics.stop()

        assert metrics.stopped_at is not None

    def test_to_dict(self):
        """Test serialization to dictionary."""
        metrics = WorkerMetrics(worker_id=0)
        metrics.start_task("T1")
        metrics.complete_task("T1", status="completed")

        data = metrics.to_dict()
        assert data["worker_id"] == 0
        assert data["tasks_completed"] == 1
        assert data["success_rate"] == 1.0
        assert "task_history" in data
        assert len(data["task_history"]) == 1

    def test_from_dict(self):
        """Test deserialization from dictionary."""
        data = {
            "worker_id": 1,
            "started_at": "2026-01-27T10:00:00",
            "tasks_completed": 5,
            "tasks_failed": 1,
            "context_usage": 0.6,
            "peak_context_usage": 0.8,
        }
        metrics = WorkerMetrics.from_dict(data)

        assert metrics.worker_id == 1
        assert metrics.tasks_completed == 5
        assert metrics.context_usage == 0.6

    def test_idle_time_tracking(self):
        """Test idle time is tracked between tasks."""
        metrics = WorkerMetrics(worker_id=0)

        # Complete first task
        metrics.start_task("T1")
        metrics.complete_task("T1")

        # Simulate idle time
        time.sleep(0.02)

        # Start second task
        metrics.start_task("T2")

        assert metrics.total_idle_seconds >= 0.02


class TestLevelMetrics:
    """Tests for LevelMetrics dataclass."""

    def test_creation(self):
        """Test LevelMetrics can be created."""
        metrics = LevelMetrics(level=1, total_tasks=5)
        assert metrics.level == 1
        assert metrics.total_tasks == 5

    def test_duration_seconds_complete(self):
        """Test duration when complete."""
        metrics = LevelMetrics(
            level=1,
            started_at=datetime.now() - timedelta(seconds=30),
            completed_at=datetime.now() - timedelta(seconds=10),
        )
        assert metrics.duration_seconds == pytest.approx(20.0, abs=0.01)

    def test_duration_seconds_incomplete(self):
        """Test duration when still running."""
        metrics = LevelMetrics(
            level=1,
            started_at=datetime.now() - timedelta(seconds=30),
        )
        assert metrics.duration_seconds >= 30.0

    def test_duration_seconds_not_started(self):
        """Test duration when not started."""
        metrics = LevelMetrics(level=1)
        assert metrics.duration_seconds == 0.0

    def test_success_rate(self):
        """Test success_rate calculation."""
        metrics = LevelMetrics(
            level=1,
            completed_tasks=8,
            failed_tasks=2,
        )
        assert metrics.success_rate == 0.8

    def test_is_complete(self):
        """Test is_complete property."""
        metrics = LevelMetrics(
            level=1,
            total_tasks=5,
            completed_tasks=3,
            failed_tasks=2,
        )
        assert metrics.is_complete is True

    def test_is_complete_false(self):
        """Test is_complete when not complete."""
        metrics = LevelMetrics(
            level=1,
            total_tasks=5,
            completed_tasks=3,
            failed_tasks=0,
        )
        assert metrics.is_complete is False

    def test_to_dict(self):
        """Test serialization to dictionary."""
        metrics = LevelMetrics(
            level=1,
            total_tasks=5,
            completed_tasks=5,
            started_at=datetime.now(),
        )
        data = metrics.to_dict()

        assert data["level"] == 1
        assert data["total_tasks"] == 5
        assert "started_at" in data


class TestWorkerMetricsCollector:
    """Tests for WorkerMetricsCollector class."""

    def test_creation(self, tmp_path: Path):
        """Test collector can be created."""
        collector = WorkerMetricsCollector(
            feature="test-feature",
            metrics_dir=tmp_path / "metrics",
        )
        assert collector.feature == "test-feature"
        assert collector.execution_id is not None

    def test_register_worker(self, tmp_path: Path):
        """Test registering a worker."""
        collector = WorkerMetricsCollector(
            feature="test-feature",
            metrics_dir=tmp_path / "metrics",
        )
        worker = collector.register_worker(0)

        assert worker.worker_id == 0
        assert collector.get_worker(0) is worker

    def test_register_worker_idempotent(self, tmp_path: Path):
        """Test registering same worker twice returns same object."""
        collector = WorkerMetricsCollector(
            feature="test-feature",
            metrics_dir=tmp_path / "metrics",
        )
        worker1 = collector.register_worker(0)
        worker2 = collector.register_worker(0)

        assert worker1 is worker2

    def test_get_worker_not_found(self, tmp_path: Path):
        """Test getting non-existent worker."""
        collector = WorkerMetricsCollector(
            feature="test-feature",
            metrics_dir=tmp_path / "metrics",
        )
        assert collector.get_worker(99) is None

    def test_start_level(self, tmp_path: Path):
        """Test starting a level."""
        collector = WorkerMetricsCollector(
            feature="test-feature",
            metrics_dir=tmp_path / "metrics",
        )
        collector.start_level(level=1, total_tasks=5, worker_count=3)

        summary = collector.get_level_summary(1)
        assert summary is not None
        assert summary["total_tasks"] == 5
        assert summary["worker_count"] == 3

    def test_complete_level(self, tmp_path: Path):
        """Test completing a level."""
        collector = WorkerMetricsCollector(
            feature="test-feature",
            metrics_dir=tmp_path / "metrics",
        )
        collector.start_level(level=1, total_tasks=5, worker_count=3)
        time.sleep(0.01)
        collector.complete_level(1)

        summary = collector.get_level_summary(1)
        assert summary["completed_at"] is not None
        assert summary["duration_seconds"] >= 0.01

    def test_record_task_completion(self, tmp_path: Path):
        """Test recording task completion."""
        collector = WorkerMetricsCollector(
            feature="test-feature",
            metrics_dir=tmp_path / "metrics",
        )
        collector.start_level(level=1, total_tasks=2, worker_count=1)
        collector.record_task_completion(level=1, success=True)
        collector.record_task_completion(level=1, success=False)

        summary = collector.get_level_summary(1)
        assert summary["completed_tasks"] == 1
        assert summary["failed_tasks"] == 1

    def test_get_summary(self, tmp_path: Path):
        """Test getting execution summary."""
        collector = WorkerMetricsCollector(
            feature="test-feature",
            metrics_dir=tmp_path / "metrics",
        )

        # Set up workers with tasks
        worker0 = collector.register_worker(0)
        worker0.start_task("T1")
        worker0.complete_task("T1", status="completed")

        worker1 = collector.register_worker(1)
        worker1.start_task("T2")
        worker1.complete_task("T2", status="failed")

        summary = collector.get_summary()
        assert summary["feature"] == "test-feature"
        assert summary["worker_count"] == 2
        assert summary["total_tasks"] == 2
        assert summary["completed_tasks"] == 1
        assert summary["failed_tasks"] == 1
        assert summary["success_rate"] == 0.5

    def test_complete(self, tmp_path: Path):
        """Test completing the collector."""
        collector = WorkerMetricsCollector(
            feature="test-feature",
            metrics_dir=tmp_path / "metrics",
        )
        worker = collector.register_worker(0)
        collector.complete()

        assert collector.completed_at is not None
        assert worker.stopped_at is not None

    def test_export(self, tmp_path: Path):
        """Test exporting metrics to JSON."""
        collector = WorkerMetricsCollector(
            feature="test-feature",
            metrics_dir=tmp_path / "metrics",
        )
        worker = collector.register_worker(0)
        worker.start_task("T1")
        worker.complete_task("T1", status="completed")

        path = collector.export()
        assert path.exists()

        data = json.loads(path.read_text())
        assert "summary" in data
        assert "workers" in data
        assert "levels" in data

    def test_export_custom_path(self, tmp_path: Path):
        """Test exporting to custom path."""
        collector = WorkerMetricsCollector(
            feature="test-feature",
            metrics_dir=tmp_path / "metrics",
        )
        custom_path = tmp_path / "custom_metrics.json"
        path = collector.export(custom_path)

        assert path == custom_path
        assert custom_path.exists()

    def test_export_summary(self, tmp_path: Path):
        """Test exporting summary only."""
        collector = WorkerMetricsCollector(
            feature="test-feature",
            metrics_dir=tmp_path / "metrics",
        )
        worker = collector.register_worker(0)
        worker.start_task("T1")
        worker.complete_task("T1")

        path = collector.export_summary()
        assert path.exists()

        data = json.loads(path.read_text())
        # Summary only - no workers or levels keys at top level
        assert "execution_id" in data
        assert "feature" in data

    def test_parallel_efficiency(self, tmp_path: Path):
        """Test parallel efficiency calculation."""
        collector = WorkerMetricsCollector(
            feature="test-feature",
            metrics_dir=tmp_path / "metrics",
        )

        # Simulate 3 workers each doing 10 seconds of work
        for i in range(3):
            worker = collector.register_worker(i)
            worker.total_task_duration_seconds = 10.0

        time.sleep(0.01)

        summary = collector.get_summary()
        # With 3 workers doing 30s total work, efficiency depends on actual elapsed time
        assert "parallel_efficiency" in summary


class TestEstimateExecutionCost:
    """Tests for cost estimation function."""

    def test_sonnet_cost(self):
        """Test cost estimation for Sonnet model."""
        # 1M tokens with 40% input, 60% output
        # Input: 400k * $3/1M = $1.20
        # Output: 600k * $15/1M = $9.00
        # Total: $10.20
        cost = estimate_execution_cost(1_000_000, model="sonnet")
        assert cost == pytest.approx(10.2, abs=0.01)

    def test_opus_cost(self):
        """Test cost estimation for Opus model."""
        # 1M tokens with 40% input, 60% output
        # Input: 400k * $15/1M = $6.00
        # Output: 600k * $75/1M = $45.00
        # Total: $51.00
        cost = estimate_execution_cost(1_000_000, model="opus")
        assert cost == pytest.approx(51.0, abs=0.01)

    def test_haiku_cost(self):
        """Test cost estimation for Haiku model."""
        # 1M tokens with 40% input, 60% output
        # Input: 400k * $0.25/1M = $0.10
        # Output: 600k * $1.25/1M = $0.75
        # Total: $0.85
        cost = estimate_execution_cost(1_000_000, model="haiku")
        assert cost == pytest.approx(0.85, abs=0.01)

    def test_custom_input_ratio(self):
        """Test with custom input ratio."""
        # 1M tokens with 70% input, 30% output for Sonnet
        # Input: 700k * $3/1M = $2.10
        # Output: 300k * $15/1M = $4.50
        # Total: $6.60
        cost = estimate_execution_cost(1_000_000, input_ratio=0.7, model="sonnet")
        assert cost == pytest.approx(6.6, abs=0.01)

    def test_unknown_model_defaults_to_sonnet(self):
        """Test unknown model defaults to Sonnet pricing."""
        cost = estimate_execution_cost(1_000_000, model="unknown")
        sonnet_cost = estimate_execution_cost(1_000_000, model="sonnet")
        assert cost == sonnet_cost


class TestIntegration:
    """Integration tests for worker metrics."""

    def test_full_workflow(self, tmp_path: Path):
        """Test a complete metrics collection workflow."""
        collector = WorkerMetricsCollector(
            feature="integration-test",
            metrics_dir=tmp_path / "metrics",
        )

        # Register workers
        workers = [collector.register_worker(i) for i in range(3)]

        # Start level 1
        collector.start_level(level=1, total_tasks=6, worker_count=3)

        # Simulate task execution
        for i, worker in enumerate(workers):
            task_id = f"L1-T{i * 2 + 1}"
            worker.start_task(task_id, context_usage=0.1)
            time.sleep(0.01)
            worker.complete_task(
                task_id,
                status="completed",
                context_usage=0.2,
                verification_passed=True,
            )
            collector.record_task_completion(level=1, success=True)

            task_id = f"L1-T{i * 2 + 2}"
            worker.start_task(task_id, context_usage=0.2)
            time.sleep(0.01)
            if i == 2:  # Last worker has a failure
                worker.complete_task(task_id, status="failed", error_message="Test")
                collector.record_task_completion(level=1, success=False)
            else:
                worker.complete_task(task_id, status="completed", context_usage=0.3)
                collector.record_task_completion(level=1, success=True)

        collector.complete_level(1)

        # Verify level summary
        level_summary = collector.get_level_summary(1)
        assert level_summary["completed_tasks"] == 5
        assert level_summary["failed_tasks"] == 1
        assert level_summary["is_complete"] is True

        # Complete and export
        collector.complete()
        path = collector.export()

        # Verify export
        data = json.loads(path.read_text())
        assert data["summary"]["total_tasks"] == 6
        assert data["summary"]["completed_tasks"] == 5
        assert data["summary"]["failed_tasks"] == 1
        assert len(data["workers"]) == 3

    def test_context_tracking_across_tasks(self, tmp_path: Path):
        """Test context usage tracking across multiple tasks."""
        collector = WorkerMetricsCollector(
            feature="context-test",
            metrics_dir=tmp_path / "metrics",
        )
        worker = collector.register_worker(0)

        # Execute tasks with increasing context usage
        for i in range(5):
            context = (i + 1) * 0.15
            worker.start_task(f"T{i}", context_usage=context)
            worker.complete_task(f"T{i}", status="completed", context_usage=context)

        assert worker.peak_context_usage == 0.75
        assert len(worker.task_history) == 5

    def test_health_check_tracking(self, tmp_path: Path):
        """Test health check tracking."""
        collector = WorkerMetricsCollector(
            feature="health-test",
            metrics_dir=tmp_path / "metrics",
        )
        worker = collector.register_worker(0)

        # Simulate health checks
        worker.record_health_check(True)
        worker.record_health_check(True)
        worker.record_health_check(False)  # Failure
        worker.record_health_check(True)

        assert worker.health_check_failures == 1
        assert worker.last_health_check_ok is True

        summary = collector.get_summary()
        assert summary["worker_count"] == 1
