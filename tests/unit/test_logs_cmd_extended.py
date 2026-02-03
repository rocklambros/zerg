"""Unit tests for extended logs command options (aggregate, task, artifacts)."""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from zerg.commands.logs import logs


@pytest.fixture()
def log_dir(tmp_path: Path) -> Path:
    """Create a populated log directory for testing."""
    workers_dir = tmp_path / ".zerg" / "logs" / "workers"
    workers_dir.mkdir(parents=True)
    tasks_dir = tmp_path / ".zerg" / "logs" / "tasks"
    tasks_dir.mkdir(parents=True)

    # Worker 0 logs
    with open(workers_dir / "worker-0.jsonl", "w") as f:
        f.write(
            json.dumps(
                {
                    "ts": "2026-01-01T10:00:00Z",
                    "level": "info",
                    "worker_id": 0,
                    "message": "Task T1.1 started",
                    "task_id": "T1.1",
                    "phase": "execute",
                    "event": "task_started",
                    "feature": "test",
                }
            )
            + "\n"
        )
        f.write(
            json.dumps(
                {
                    "ts": "2026-01-01T10:00:05Z",
                    "level": "info",
                    "worker_id": 0,
                    "message": "Task T1.1 completed",
                    "task_id": "T1.1",
                    "phase": "execute",
                    "event": "task_completed",
                    "feature": "test",
                }
            )
            + "\n"
        )

    # Worker 1 logs
    with open(workers_dir / "worker-1.jsonl", "w") as f:
        f.write(
            json.dumps(
                {
                    "ts": "2026-01-01T10:00:01Z",
                    "level": "info",
                    "worker_id": 1,
                    "message": "Task T1.2 started",
                    "task_id": "T1.2",
                    "phase": "execute",
                    "event": "task_started",
                    "feature": "test",
                }
            )
            + "\n"
        )
        f.write(
            json.dumps(
                {
                    "ts": "2026-01-01T10:00:10Z",
                    "level": "error",
                    "worker_id": 1,
                    "message": "Verification failed for T1.2",
                    "task_id": "T1.2",
                    "phase": "verify",
                    "event": "verification_failed",
                    "feature": "test",
                }
            )
            + "\n"
        )

    # Task artifacts
    t1_dir = tasks_dir / "T1.1"
    t1_dir.mkdir()
    (t1_dir / "claude_output.txt").write_text("=== STDOUT ===\nHello world\n")
    (t1_dir / "git_diff.patch").write_text("diff --git a/file.py\n+new line\n")

    return tmp_path


class TestAggregateMode:
    """Tests for --aggregate flag."""

    def test_aggregate_merges_all_workers(self, log_dir: Path) -> None:
        """Test --aggregate merges logs from all workers sorted by timestamp."""
        runner = CliRunner()
        orig_cwd = os.getcwd()
        try:
            os.chdir(log_dir)
            with patch("zerg.commands.logs.detect_feature", return_value="test"):
                result = runner.invoke(
                    logs,
                    [
                        "--aggregate",
                        "--json",
                        "--tail",
                        "100",
                    ],
                    catch_exceptions=False,
                )
        finally:
            os.chdir(orig_cwd)

        assert result.exit_code == 0
        lines = [ln for ln in result.output.strip().split("\n") if ln.strip()]
        entries = [json.loads(ln) for ln in lines]

        assert len(entries) == 4
        # Should be sorted by timestamp
        timestamps = [e["ts"] for e in entries]
        assert timestamps == sorted(timestamps)

    def test_aggregate_filter_by_task(self, log_dir: Path) -> None:
        """Test --task filters to specific task."""
        runner = CliRunner()
        orig_cwd = os.getcwd()
        try:
            os.chdir(log_dir)
            with patch("zerg.commands.logs.detect_feature", return_value="test"):
                result = runner.invoke(
                    logs,
                    [
                        "--task",
                        "T1.1",
                        "--json",
                    ],
                    catch_exceptions=False,
                )
        finally:
            os.chdir(orig_cwd)

        assert result.exit_code == 0
        lines = [ln for ln in result.output.strip().split("\n") if ln.strip()]
        entries = [json.loads(ln) for ln in lines]

        assert len(entries) == 2
        assert all(e.get("task_id") == "T1.1" for e in entries)

    def test_aggregate_filter_by_phase(self, log_dir: Path) -> None:
        """Test --phase filters by execution phase."""
        runner = CliRunner()
        orig_cwd = os.getcwd()
        try:
            os.chdir(log_dir)
            with patch("zerg.commands.logs.detect_feature", return_value="test"):
                result = runner.invoke(
                    logs,
                    [
                        "--phase",
                        "verify",
                        "--json",
                    ],
                    catch_exceptions=False,
                )
        finally:
            os.chdir(orig_cwd)

        assert result.exit_code == 0
        lines = [ln for ln in result.output.strip().split("\n") if ln.strip()]
        entries = [json.loads(ln) for ln in lines]

        assert len(entries) == 1
        assert entries[0]["phase"] == "verify"

    def test_aggregate_filter_by_event(self, log_dir: Path) -> None:
        """Test --event filters by event type."""
        runner = CliRunner()
        orig_cwd = os.getcwd()
        try:
            os.chdir(log_dir)
            with patch("zerg.commands.logs.detect_feature", return_value="test"):
                result = runner.invoke(
                    logs,
                    [
                        "--event",
                        "task_started",
                        "--json",
                    ],
                    catch_exceptions=False,
                )
        finally:
            os.chdir(orig_cwd)

        assert result.exit_code == 0
        lines = [ln for ln in result.output.strip().split("\n") if ln.strip()]
        entries = [json.loads(ln) for ln in lines]

        assert all(e.get("event") == "task_started" for e in entries)
        assert len(entries) == 2

    def test_aggregate_filter_by_time_range(self, log_dir: Path) -> None:
        """Test --since and --until filter by time range."""
        runner = CliRunner()
        orig_cwd = os.getcwd()
        try:
            os.chdir(log_dir)
            with patch("zerg.commands.logs.detect_feature", return_value="test"):
                result = runner.invoke(
                    logs,
                    [
                        "--since",
                        "2026-01-01T10:00:02Z",
                        "--until",
                        "2026-01-01T10:00:06Z",
                        "--json",
                    ],
                    catch_exceptions=False,
                )
        finally:
            os.chdir(orig_cwd)

        assert result.exit_code == 0
        lines = [ln for ln in result.output.strip().split("\n") if ln.strip()]
        entries = [json.loads(ln) for ln in lines]

        assert len(entries) == 1
        assert entries[0]["ts"] == "2026-01-01T10:00:05Z"

    def test_aggregate_search_text(self, log_dir: Path) -> None:
        """Test --search filters by text in message."""
        runner = CliRunner()
        orig_cwd = os.getcwd()
        try:
            os.chdir(log_dir)
            with patch("zerg.commands.logs.detect_feature", return_value="test"):
                result = runner.invoke(
                    logs,
                    [
                        "--search",
                        "Verification",
                        "--json",
                    ],
                    catch_exceptions=False,
                )
        finally:
            os.chdir(orig_cwd)

        assert result.exit_code == 0
        lines = [ln for ln in result.output.strip().split("\n") if ln.strip()]
        entries = [json.loads(ln) for ln in lines]

        assert len(entries) == 1
        assert "Verification" in entries[0]["message"]


class TestArtifactsMode:
    """Tests for --artifacts flag."""

    def test_shows_artifact_contents(self, log_dir: Path) -> None:
        """Test --artifacts shows file contents for a task."""
        runner = CliRunner()
        orig_cwd = os.getcwd()
        try:
            os.chdir(log_dir)
            with patch("zerg.commands.logs.detect_feature", return_value="test"):
                result = runner.invoke(
                    logs,
                    [
                        "--artifacts",
                        "T1.1",
                    ],
                    catch_exceptions=False,
                )
        finally:
            os.chdir(orig_cwd)

        assert result.exit_code == 0
        assert "claude_output.txt" in result.output
        assert "Hello world" in result.output
        assert "git_diff.patch" in result.output

    def test_no_artifacts_found(self, log_dir: Path) -> None:
        """Test --artifacts for nonexistent task shows message."""
        runner = CliRunner()
        orig_cwd = os.getcwd()
        try:
            os.chdir(log_dir)
            with patch("zerg.commands.logs.detect_feature", return_value="test"):
                result = runner.invoke(
                    logs,
                    [
                        "--artifacts",
                        "NONEXISTENT",
                    ],
                    catch_exceptions=False,
                )
        finally:
            os.chdir(orig_cwd)

        assert result.exit_code == 0
        assert "No artifacts found" in result.output
