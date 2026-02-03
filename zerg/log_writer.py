"""Structured JSONL log writer for ZERG workers.

Each worker writes to its own worker-{id}.jsonl file.
Thread-safe via threading.Lock on write operations.
"""

import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from zerg.constants import LogEvent, LogPhase


class StructuredLogWriter:
    """Writes structured JSONL log entries to a per-worker file.

    Thread-safe. Each worker gets its own file: workers/worker-{id}.jsonl
    """

    def __init__(
        self,
        log_dir: str | Path,
        worker_id: int | str,
        feature: str,
        max_size_mb: int = 50,
    ) -> None:
        """Initialize writer.

        Args:
            log_dir: Base log directory (.zerg/logs)
            worker_id: Worker identifier (int or "orchestrator")
            feature: Feature name
            max_size_mb: Max file size in MB before rotation
        """
        self.log_dir = Path(log_dir)
        self.worker_id = worker_id
        self.feature = feature
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self._lock = threading.Lock()

        # Create workers directory
        workers_dir = self.log_dir / "workers"
        workers_dir.mkdir(parents=True, exist_ok=True)

        # Open file
        self._file_path = workers_dir / f"worker-{worker_id}.jsonl"
        self._file = open(self._file_path, "a")  # noqa: SIM115

    def emit(
        self,
        level: str,
        message: str,
        task_id: str | None = None,
        phase: LogPhase | str | None = None,
        event: LogEvent | str | None = None,
        data: dict[str, Any] | None = None,
        duration_ms: int | None = None,
    ) -> None:
        """Write a structured log entry.

        Args:
            level: Log level (debug, info, warn, error)
            message: Human-readable message
            task_id: Optional task identifier
            phase: Optional execution phase
            event: Optional event type
            data: Optional extra data dict
            duration_ms: Optional duration in milliseconds
        """
        entry: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "level": level,
            "worker_id": self.worker_id,
            "feature": self.feature,
            "message": message,
        }

        if task_id is not None:
            entry["task_id"] = task_id
        if phase is not None:
            entry["phase"] = phase.value if isinstance(phase, LogPhase) else phase
        if event is not None:
            entry["event"] = event.value if isinstance(event, LogEvent) else event
        if data is not None:
            entry["data"] = data
        if duration_ms is not None:
            entry["duration_ms"] = duration_ms

        line = json.dumps(entry) + "\n"

        with self._lock:
            self._rotate_if_needed()
            self._file.write(line)
            self._file.flush()

    def _rotate_if_needed(self) -> None:
        """Rotate log file if it exceeds max size."""
        try:
            pos = self._file.tell()
            if pos > self.max_size_bytes:
                self._file.close()
                # Rename current to .1 (overwrite previous rotation)
                rotated = self._file_path.with_suffix(".jsonl.1")
                self._file_path.rename(rotated)
                self._file = open(self._file_path, "a")  # noqa: SIM115
        except OSError:
            pass  # Best-effort rotation

    def close(self) -> None:
        """Flush and close the log file."""
        with self._lock:
            self._file.flush()
            self._file.close()


class TaskArtifactCapture:
    """Captures per-task artifacts into tasks/{task_id}/ directory.

    Artifacts include:
    - execution.jsonl: Structured execution events
    - claude_output.txt: Claude CLI stdout/stderr
    - verification_output.txt: Verification command output
    - git_diff.patch: Git diff of changes
    """

    def __init__(self, log_dir: str | Path, task_id: str) -> None:
        """Initialize artifact capture.

        Args:
            log_dir: Base log directory (.zerg/logs)
            task_id: Task identifier
        """
        self.log_dir = Path(log_dir)
        self.task_id = task_id
        self.task_dir = self.log_dir / "tasks" / task_id
        self.task_dir.mkdir(parents=True, exist_ok=True)

    def capture_claude_output(self, stdout: str, stderr: str) -> None:
        """Capture Claude CLI output.

        Args:
            stdout: Standard output
            stderr: Standard error
        """
        output_path = self.task_dir / "claude_output.txt"
        with open(output_path, "w") as f:
            if stdout:
                f.write("=== STDOUT ===\n")
                f.write(str(stdout))
                f.write("\n")
            if stderr:
                f.write("=== STDERR ===\n")
                f.write(str(stderr))
                f.write("\n")

    def capture_verification(self, stdout: str, stderr: str, exit_code: int) -> None:
        """Capture verification command output.

        Args:
            stdout: Standard output
            stderr: Standard error
            exit_code: Process exit code
        """
        output_path = self.task_dir / "verification_output.txt"
        with open(output_path, "w") as f:
            f.write(f"Exit code: {exit_code}\n")
            if stdout:
                f.write("=== STDOUT ===\n")
                f.write(str(stdout))
                f.write("\n")
            if stderr:
                f.write("=== STDERR ===\n")
                f.write(str(stderr))
                f.write("\n")

    def capture_git_diff(self, diff_text: str) -> None:
        """Capture git diff output.

        Args:
            diff_text: Git diff text
        """
        diff_path = self.task_dir / "git_diff.patch"
        with open(diff_path, "w") as f:
            f.write(str(diff_text))

    def write_event(self, event_data: dict[str, Any]) -> None:
        """Append an event to execution.jsonl.

        Args:
            event_data: Event data dictionary
        """
        event_data.setdefault("ts", datetime.now(UTC).isoformat().replace("+00:00", "Z"))
        execution_path = self.task_dir / "execution.jsonl"
        with open(execution_path, "a") as f:
            f.write(json.dumps(event_data) + "\n")

    def cleanup(self, success: bool, config: Any) -> None:
        """Clean up artifacts based on retention policy.

        Args:
            success: Whether the task succeeded
            config: LoggingConfig with retention settings
        """
        retain_on_success = getattr(config, "ephemeral_retain_on_success", False)
        retain_on_failure = getattr(config, "ephemeral_retain_on_failure", True)

        should_retain = (success and retain_on_success) or (not success and retain_on_failure)

        if not should_retain:
            import contextlib
            import shutil

            with contextlib.suppress(OSError):
                shutil.rmtree(self.task_dir)

    def get_artifact_paths(self) -> dict[str, Path]:
        """Get paths to all artifacts.

        Returns:
            Dict of artifact name to path (only existing files)
        """
        artifacts = {}
        for name in [
            "execution.jsonl",
            "claude_output.txt",
            "verification_output.txt",
            "git_diff.patch",
        ]:
            path = self.task_dir / name
            if path.exists():
                artifacts[name] = path
        return artifacts
