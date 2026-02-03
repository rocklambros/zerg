"""Integration tests for log aggregation across workers."""

import json
import threading
from pathlib import Path

from zerg.config import LoggingConfig
from zerg.log_aggregator import LogAggregator
from zerg.log_writer import StructuredLogWriter, TaskArtifactCapture


class TestConcurrentWorkerLogging:
    """Test multiple workers writing structured logs concurrently."""

    def test_three_workers_concurrent_logging(self, tmp_path: Path) -> None:
        """Simulate 3 workers writing structured logs concurrently.

        Verifies aggregated query returns all entries in timestamp order.
        """
        log_dir = tmp_path / "logs"
        errors: list[str] = []

        def worker_fn(worker_id: int) -> None:
            try:
                writer = StructuredLogWriter(log_dir, worker_id=worker_id, feature="test-feature")
                for i in range(10):
                    writer.emit(
                        "info",
                        f"Worker {worker_id} entry {i}",
                        task_id=f"T1.{worker_id}",
                        phase="execute",
                        event="task_started" if i == 0 else None,
                    )
                writer.close()
            except Exception as e:
                errors.append(f"Worker {worker_id}: {e}")

        # Run 3 workers concurrently
        threads = [threading.Thread(target=worker_fn, args=(w,)) for w in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors

        # Verify aggregated query
        aggregator = LogAggregator(log_dir)
        all_entries = aggregator.query()

        assert len(all_entries) == 30  # 3 workers * 10 entries

        # Should be sorted by timestamp
        timestamps = [e["ts"] for e in all_entries]
        assert timestamps == sorted(timestamps)

        # Filter by worker
        w0_entries = aggregator.query(worker_id=0)
        assert len(w0_entries) == 10
        assert all(e["worker_id"] == 0 for e in w0_entries)

    def test_task_artifact_directories_created(self, tmp_path: Path) -> None:
        """Verify task artifact directories are created with expected files."""
        log_dir = tmp_path / "logs"

        # Simulate artifact capture for a task
        artifact = TaskArtifactCapture(log_dir, "T1.1")
        artifact.capture_claude_output("Implementation output", "")
        artifact.capture_verification("All tests passed", "", 0)
        artifact.capture_git_diff("diff --git a/file.py\n+new line\n")
        artifact.write_event({"event": "task_completed", "worker_id": 0})

        # Verify files exist
        task_dir = log_dir / "tasks" / "T1.1"
        assert task_dir.exists()
        assert (task_dir / "claude_output.txt").exists()
        assert (task_dir / "verification_output.txt").exists()
        assert (task_dir / "git_diff.patch").exists()
        assert (task_dir / "execution.jsonl").exists()

        # Verify through aggregator
        aggregator = LogAggregator(log_dir)
        artifacts = aggregator.get_task_artifacts("T1.1")
        assert len(artifacts) == 4
        assert "claude_output.txt" in artifacts
        assert "verification_output.txt" in artifacts
        assert "git_diff.patch" in artifacts
        assert "execution.jsonl" in artifacts

    def test_retention_cleanup_prunes_success_artifacts(self, tmp_path: Path) -> None:
        """Verify retention cleanup prunes successful task artifacts."""
        log_dir = tmp_path / "logs"
        config = LoggingConfig(
            ephemeral_retain_on_success=False,
            ephemeral_retain_on_failure=True,
        )

        # Create artifacts for a successful task
        artifact_success = TaskArtifactCapture(log_dir, "T-success")
        artifact_success.capture_claude_output("output", "")
        artifact_success.cleanup(success=True, config=config)

        # Create artifacts for a failed task
        artifact_failure = TaskArtifactCapture(log_dir, "T-failure")
        artifact_failure.capture_claude_output("output", "error")
        artifact_failure.cleanup(success=False, config=config)

        # Successful task artifacts should be pruned
        assert not (log_dir / "tasks" / "T-success").exists()
        # Failed task artifacts should be retained
        assert (log_dir / "tasks" / "T-failure").exists()

    def test_orchestrator_jsonl_lifecycle_events(self, tmp_path: Path) -> None:
        """Verify orchestrator.jsonl contains lifecycle events."""
        log_dir = tmp_path / "logs"

        # Simulate orchestrator writing events
        writer = StructuredLogWriter(log_dir, worker_id="orchestrator", feature="test-feature")
        writer.emit("info", "Level 1 started", event="level_started", data={"level": 1})
        writer.emit("info", "Merge started for level 1", event="merge_started")
        writer.emit("info", "Merge complete", event="merge_complete")
        writer.emit("info", "Level 1 complete", event="level_complete")
        writer.close()

        # Verify through aggregator
        aggregator = LogAggregator(log_dir)
        all_entries = aggregator.query()
        assert len(all_entries) == 4

        events = [e.get("event") for e in all_entries]
        assert "level_started" in events
        assert "merge_started" in events
        assert "merge_complete" in events
        assert "level_complete" in events

    def test_aggregated_query_across_workers_and_orchestrator(self, tmp_path: Path) -> None:
        """Test query merges worker and orchestrator logs correctly."""
        log_dir = tmp_path / "logs"

        # Worker writes
        w0 = StructuredLogWriter(log_dir, worker_id=0, feature="test")
        w0.emit("info", "Worker 0 task", task_id="T1.1")
        w0.close()

        w1 = StructuredLogWriter(log_dir, worker_id=1, feature="test")
        w1.emit("info", "Worker 1 task", task_id="T1.2")
        w1.close()

        # Orchestrator writes to its own file (not workers dir)
        orch_file = log_dir / "orchestrator.jsonl"
        orch_file.parent.mkdir(parents=True, exist_ok=True)
        with open(orch_file, "w") as f:
            f.write(
                json.dumps(
                    {
                        "ts": "2026-01-01T12:00:00Z",
                        "level": "info",
                        "worker_id": "orchestrator",
                        "message": "Level started",
                        "event": "level_started",
                    }
                )
                + "\n"
            )

        aggregator = LogAggregator(log_dir)
        all_entries = aggregator.query()

        # Should have all 3 entries
        assert len(all_entries) == 3
        worker_ids = {e.get("worker_id") for e in all_entries}
        assert 0 in worker_ids
        assert 1 in worker_ids
        assert "orchestrator" in worker_ids

    def test_list_tasks_from_logs_and_artifacts(self, tmp_path: Path) -> None:
        """Test list_tasks returns task IDs from both sources."""
        log_dir = tmp_path / "logs"

        # Write logs with task IDs
        writer = StructuredLogWriter(log_dir, worker_id=0, feature="test")
        writer.emit("info", "task 1", task_id="T1.1")
        writer.emit("info", "task 2", task_id="T1.2")
        writer.close()

        # Create artifact dir for T1.3
        (log_dir / "tasks" / "T1.3").mkdir(parents=True)

        aggregator = LogAggregator(log_dir)
        tasks = aggregator.list_tasks()
        assert "T1.1" in tasks
        assert "T1.2" in tasks
        assert "T1.3" in tasks
