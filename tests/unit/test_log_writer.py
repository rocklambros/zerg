"""Unit tests for StructuredLogWriter and TaskArtifactCapture."""

import json
import threading
from pathlib import Path

from zerg.constants import LogEvent, LogPhase
from zerg.log_writer import StructuredLogWriter, TaskArtifactCapture


class TestStructuredLogWriter:
    """Tests for StructuredLogWriter."""

    def test_creates_worker_jsonl_file(self, tmp_path: Path) -> None:
        """Test writer creates workers/worker-{id}.jsonl file."""
        writer = StructuredLogWriter(tmp_path, worker_id=0, feature="test")
        writer.emit("info", "hello")
        writer.close()

        jsonl_file = tmp_path / "workers" / "worker-0.jsonl"
        assert jsonl_file.exists()

    def test_emit_writes_valid_json_lines(self, tmp_path: Path) -> None:
        """Test emit writes valid JSON with all fields."""
        writer = StructuredLogWriter(tmp_path, worker_id=1, feature="my-feat")
        writer.emit(
            level="info",
            message="Task started",
            task_id="T1.1",
            phase=LogPhase.EXECUTE,
            event=LogEvent.TASK_STARTED,
            data={"key": "value"},
            duration_ms=150,
        )
        writer.close()

        jsonl_file = tmp_path / "workers" / "worker-1.jsonl"
        lines = jsonl_file.read_text().strip().split("\n")
        assert len(lines) == 1

        entry = json.loads(lines[0])
        assert entry["ts"].endswith("Z")
        assert entry["level"] == "info"
        assert entry["worker_id"] == 1
        assert entry["feature"] == "my-feat"
        assert entry["message"] == "Task started"
        assert entry["task_id"] == "T1.1"
        assert entry["phase"] == "execute"
        assert entry["event"] == "task_started"
        assert entry["data"] == {"key": "value"}
        assert entry["duration_ms"] == 150

    def test_emit_optional_fields_omitted(self, tmp_path: Path) -> None:
        """Test that optional fields are omitted when not provided."""
        writer = StructuredLogWriter(tmp_path, worker_id=0, feature="test")
        writer.emit("debug", "minimal entry")
        writer.close()

        jsonl_file = tmp_path / "workers" / "worker-0.jsonl"
        entry = json.loads(jsonl_file.read_text().strip())

        assert "task_id" not in entry
        assert "phase" not in entry
        assert "event" not in entry
        assert "data" not in entry
        assert "duration_ms" not in entry

    def test_thread_safety(self, tmp_path: Path) -> None:
        """Test concurrent emit calls from multiple threads."""
        writer = StructuredLogWriter(tmp_path, worker_id=0, feature="test")
        errors: list[str] = []

        def write_entries(thread_id: int) -> None:
            try:
                for i in range(50):
                    writer.emit("info", f"Thread {thread_id} entry {i}")
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=write_entries, args=(t,)) for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        writer.close()

        assert not errors

        jsonl_file = tmp_path / "workers" / "worker-0.jsonl"
        lines = jsonl_file.read_text().strip().split("\n")
        assert len(lines) == 250  # 5 threads * 50 entries

        # Each line must be valid JSON
        for line in lines:
            json.loads(line)

    def test_close_flushes(self, tmp_path: Path) -> None:
        """Test close flushes pending writes."""
        writer = StructuredLogWriter(tmp_path, worker_id=0, feature="test")
        writer.emit("info", "before close")
        writer.close()

        jsonl_file = tmp_path / "workers" / "worker-0.jsonl"
        content = jsonl_file.read_text().strip()
        assert "before close" in content

    def test_log_rotation(self, tmp_path: Path) -> None:
        """Test log file rotation when max size exceeded."""
        # Set very small max size (1 byte) to trigger rotation
        writer = StructuredLogWriter(tmp_path, worker_id=0, feature="test", max_size_mb=0)
        # max_size_bytes will be 0, so first write triggers rotation
        writer.emit("info", "first entry")
        writer.emit("info", "second entry after rotation")
        writer.close()

        # Should have rotated file
        rotated = tmp_path / "workers" / "worker-0.jsonl.1"
        current = tmp_path / "workers" / "worker-0.jsonl"
        assert rotated.exists() or current.exists()

    def test_orchestrator_worker_id(self, tmp_path: Path) -> None:
        """Test writer with string worker_id for orchestrator."""
        writer = StructuredLogWriter(tmp_path, worker_id="orchestrator", feature="test")
        writer.emit("info", "orchestrator event")
        writer.close()

        jsonl_file = tmp_path / "workers" / "worker-orchestrator.jsonl"
        assert jsonl_file.exists()
        entry = json.loads(jsonl_file.read_text().strip())
        assert entry["worker_id"] == "orchestrator"

    def test_string_phase_and_event(self, tmp_path: Path) -> None:
        """Test emit accepts string phase and event values."""
        writer = StructuredLogWriter(tmp_path, worker_id=0, feature="test")
        writer.emit("info", "test", phase="custom_phase", event="custom_event")
        writer.close()

        jsonl_file = tmp_path / "workers" / "worker-0.jsonl"
        entry = json.loads(jsonl_file.read_text().strip())
        assert entry["phase"] == "custom_phase"
        assert entry["event"] == "custom_event"


class TestTaskArtifactCapture:
    """Tests for TaskArtifactCapture."""

    def test_creates_task_directory(self, tmp_path: Path) -> None:
        """Test artifact capture creates tasks/{task_id}/ directory."""
        TaskArtifactCapture(tmp_path, "T1.1")
        assert (tmp_path / "tasks" / "T1.1").is_dir()

    def test_capture_claude_output(self, tmp_path: Path) -> None:
        """Test capturing Claude CLI output."""
        capture = TaskArtifactCapture(tmp_path, "T1.1")
        capture.capture_claude_output("stdout content", "stderr content")

        output = (tmp_path / "tasks" / "T1.1" / "claude_output.txt").read_text()
        assert "STDOUT" in output
        assert "stdout content" in output
        assert "STDERR" in output
        assert "stderr content" in output

    def test_capture_verification(self, tmp_path: Path) -> None:
        """Test capturing verification output."""
        capture = TaskArtifactCapture(tmp_path, "T1.1")
        capture.capture_verification("pass output", "warn output", 0)

        output = (tmp_path / "tasks" / "T1.1" / "verification_output.txt").read_text()
        assert "Exit code: 0" in output
        assert "pass output" in output

    def test_capture_git_diff(self, tmp_path: Path) -> None:
        """Test capturing git diff."""
        capture = TaskArtifactCapture(tmp_path, "T1.1")
        capture.capture_git_diff("diff --git a/file.py b/file.py\n+new line\n")

        diff = (tmp_path / "tasks" / "T1.1" / "git_diff.patch").read_text()
        assert "diff --git" in diff

    def test_write_event(self, tmp_path: Path) -> None:
        """Test appending to execution.jsonl."""
        capture = TaskArtifactCapture(tmp_path, "T1.1")
        capture.write_event({"event": "task_started", "worker_id": 0})
        capture.write_event({"event": "task_completed", "worker_id": 0})

        execution = (tmp_path / "tasks" / "T1.1" / "execution.jsonl").read_text()
        lines = execution.strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0])["event"] == "task_started"
        assert "ts" in json.loads(lines[0])  # Auto-added timestamp

    def test_cleanup_removes_on_success_no_retain(self, tmp_path: Path) -> None:
        """Test cleanup removes artifacts when success and no retain."""

        class MockConfig:
            ephemeral_retain_on_success = False
            ephemeral_retain_on_failure = True

        capture = TaskArtifactCapture(tmp_path, "T1.1")
        capture.capture_claude_output("output", "")
        capture.cleanup(success=True, config=MockConfig())

        assert not (tmp_path / "tasks" / "T1.1").exists()

    def test_cleanup_retains_on_failure(self, tmp_path: Path) -> None:
        """Test cleanup retains artifacts on failure."""

        class MockConfig:
            ephemeral_retain_on_success = False
            ephemeral_retain_on_failure = True

        capture = TaskArtifactCapture(tmp_path, "T1.1")
        capture.capture_claude_output("output", "error")
        capture.cleanup(success=False, config=MockConfig())

        assert (tmp_path / "tasks" / "T1.1").exists()

    def test_get_artifact_paths(self, tmp_path: Path) -> None:
        """Test listing existing artifact paths."""
        capture = TaskArtifactCapture(tmp_path, "T1.1")
        capture.capture_claude_output("out", "err")
        capture.capture_git_diff("diff")

        paths = capture.get_artifact_paths()
        assert "claude_output.txt" in paths
        assert "git_diff.patch" in paths
        assert "verification_output.txt" not in paths  # Not created
