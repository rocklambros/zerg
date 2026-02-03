"""Comprehensive tests for the ZERG backlog module."""

from __future__ import annotations

from pathlib import Path

import pytest

from zerg.backlog import (
    compute_critical_path,
    estimate_sessions,
    generate_backlog_markdown,
    update_backlog_task_status,
)


@pytest.fixture
def sample_task_data():
    """Reusable task data fixture representing a small feature with two levels."""
    return {
        "feature": "test-feature",
        "version": "2.0",
        "generated": "2026-01-28T10:00:00Z",
        "total_tasks": 3,
        "estimated_duration_minutes": 45,
        "max_parallelization": 2,
        "critical_path_minutes": 30,
        "tasks": [
            {
                "id": "TEST-L1-001",
                "title": "Create types",
                "description": "Define types",
                "level": 1,
                "dependencies": [],
                "files": {"create": ["src/types.py"], "modify": [], "read": []},
                "verification": {
                    "command": "python -c 'import types'",
                    "timeout_seconds": 60,
                },
                "estimate_minutes": 15,
            },
            {
                "id": "TEST-L1-002",
                "title": "Create config",
                "description": "Setup config",
                "level": 1,
                "dependencies": [],
                "files": {"create": ["src/config.py"], "modify": [], "read": []},
                "verification": {
                    "command": "python -c 'import config'",
                    "timeout_seconds": 60,
                },
                "estimate_minutes": 10,
            },
            {
                "id": "TEST-L2-001",
                "title": "Core logic",
                "description": "Implement core",
                "level": 2,
                "dependencies": ["TEST-L1-001", "TEST-L1-002"],
                "files": {
                    "create": ["src/core.py"],
                    "modify": [],
                    "read": ["src/types.py"],
                },
                "verification": {
                    "command": "pytest tests/",
                    "timeout_seconds": 120,
                },
                "estimate_minutes": 20,
            },
        ],
        "levels": {
            "1": {
                "name": "foundation",
                "tasks": ["TEST-L1-001", "TEST-L1-002"],
                "parallel": True,
                "estimated_minutes": 15,
            },
            "2": {
                "name": "core",
                "tasks": ["TEST-L2-001"],
                "parallel": True,
                "estimated_minutes": 20,
                "depends_on_levels": [1],
            },
        },
    }


class TestComputeCriticalPath:
    """Tests for compute_critical_path which finds the longest dependency chain."""

    def test_linear_chain(self) -> None:
        """Three tasks in sequence A->B->C should return [A, B, C]."""
        tasks = [
            {"id": "A", "dependencies": [], "estimate_minutes": 10},
            {"id": "B", "dependencies": ["A"], "estimate_minutes": 10},
            {"id": "C", "dependencies": ["B"], "estimate_minutes": 10},
        ]
        result = compute_critical_path(tasks)
        assert result == ["A", "B", "C"]

    def test_diamond_dependency(self) -> None:
        """Diamond: A->B, A->C, B->D, C->D. B has higher estimate so path goes through B."""
        tasks = [
            {"id": "A", "dependencies": [], "estimate_minutes": 5},
            {"id": "B", "dependencies": ["A"], "estimate_minutes": 20},
            {"id": "C", "dependencies": ["A"], "estimate_minutes": 5},
            {"id": "D", "dependencies": ["B", "C"], "estimate_minutes": 10},
        ]
        result = compute_critical_path(tasks)
        assert "A" in result
        assert "B" in result
        assert "D" in result
        # C should not be on the critical path since B's branch is longer
        assert "C" not in result

    def test_single_task(self) -> None:
        """A single task with no dependencies returns a list containing just that task."""
        tasks = [{"id": "ONLY", "dependencies": [], "estimate_minutes": 30}]
        result = compute_critical_path(tasks)
        assert result == ["ONLY"]

    def test_empty_tasks(self) -> None:
        """An empty task list returns an empty critical path."""
        result = compute_critical_path([])
        assert result == []

    def test_no_estimate_defaults_to_15(self) -> None:
        """Tasks missing estimate_minutes should default to 15 minutes."""
        tasks = [
            {"id": "A", "dependencies": []},
            {"id": "B", "dependencies": ["A"]},
        ]
        result = compute_critical_path(tasks)
        # Both tasks should be on the path (linear chain)
        assert result == ["A", "B"]


class TestEstimateSessions:
    """Tests for estimate_sessions which calculates time and session estimates."""

    def test_single_level(self) -> None:
        """All tasks at level 1: single_worker sums all, with_workers takes the max."""
        tasks = [
            {"id": "A", "level": 1, "estimate_minutes": 20},
            {"id": "B", "level": 1, "estimate_minutes": 30},
            {"id": "C", "level": 1, "estimate_minutes": 10},
        ]
        result = estimate_sessions(tasks, max_workers=3)
        # Single worker: ceil(60/90) = 1 session
        assert result["single_worker"] == 1
        # With 3 workers, level 1 takes max(20,30,10)=30 → ceil(30/90) = 1 session
        assert result["with_workers"] == 1

    def test_multi_level(self) -> None:
        """Tasks at multiple levels accumulate per-level parallel time."""
        tasks = [
            {"id": "A", "level": 1, "estimate_minutes": 20},
            {"id": "B", "level": 1, "estimate_minutes": 10},
            {"id": "C", "level": 2, "estimate_minutes": 25},
            {"id": "D", "level": 2, "estimate_minutes": 15},
            {"id": "E", "level": 3, "estimate_minutes": 30},
        ]
        result = estimate_sessions(tasks, max_workers=5, session_minutes=90)
        # Single worker: ceil(100/90) = 2 sessions
        assert result["single_worker"] == 2
        # Parallel: 20+25+30=75 min → ceil(75/90) = 1 session
        assert result["with_workers"] == 1

    def test_custom_workers_and_session(self) -> None:
        """Custom max_workers and session_minutes affect speedup and session count."""
        tasks = [
            {"id": "A", "level": 1, "estimate_minutes": 60},
            {"id": "B", "level": 1, "estimate_minutes": 60},
        ]
        result = estimate_sessions(tasks, max_workers=2, session_minutes=45)
        # Single worker: ceil(120/45) = 3 sessions
        assert result["single_worker"] == 3
        # Parallel with 2 workers: max(60,60)=60 → ceil(60/45) = 2 sessions
        assert result["with_workers"] == 2
        # Speedup: 120/60 = 2.0
        assert result["speedup"] == pytest.approx(2.0)

    def test_empty_tasks(self) -> None:
        """An empty task list returns zero values."""
        result = estimate_sessions([])
        assert result["single_worker"] == 0
        assert result["with_workers"] == 0


class TestGenerateBacklogMarkdown:
    """Tests for generate_backlog_markdown which creates the backlog file."""

    def test_creates_file(self, tmp_path: Path, sample_task_data: dict) -> None:
        """Verify the markdown file is created at the expected path."""
        result = generate_backlog_markdown(sample_task_data, "test-feature", output_dir=tmp_path)
        assert result.exists()
        assert result.suffix == ".md"

    def test_contains_all_sections(self, tmp_path: Path, sample_task_data: dict) -> None:
        """Generated markdown must contain header, metadata, summary, levels, critical path, and progress."""
        path = generate_backlog_markdown(sample_task_data, "test-feature", output_dir=tmp_path)
        content = path.read_text()
        # Header
        assert "test-feature" in content.lower() or "Test Feature" in content
        # Metadata section markers
        assert "status" in content.lower() or "Feature" in content
        # Execution summary
        assert "estimat" in content.lower() or "duration" in content.lower()
        # Level tables
        assert "Level 1" in content or "level 1" in content.lower()
        assert "Level 2" in content or "level 2" in content.lower()
        # Critical path
        assert "critical" in content.lower()
        # Progress tracking
        assert "progress" in content.lower() or "status" in content.lower()

    def test_tasks_grouped_by_level(self, tmp_path: Path, sample_task_data: dict) -> None:
        """Tasks should appear under their corresponding level headers."""
        path = generate_backlog_markdown(sample_task_data, "test-feature", output_dir=tmp_path)
        content = path.read_text()
        # Level 1 tasks
        assert "TEST-L1-001" in content
        assert "TEST-L1-002" in content
        # Level 2 task
        assert "TEST-L2-001" in content

    def test_default_output_dir(self, sample_task_data: dict, tmp_path: Path) -> None:
        """When no output_dir is given, defaults to 'tasks' directory."""
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = generate_backlog_markdown(sample_task_data, "test-feature")
            assert "tasks" in str(result) or result.parent.name == "tasks"
        finally:
            os.chdir(original_cwd)

    def test_custom_output_dir(self, tmp_path: Path, sample_task_data: dict) -> None:
        """A custom output_dir is respected for file placement."""
        custom_dir = tmp_path / "custom" / "output"
        result = generate_backlog_markdown(sample_task_data, "test-feature", output_dir=custom_dir)
        assert custom_dir in result.parents or result.parent == custom_dir


class TestUpdateBacklogTaskStatus:
    """Tests for update_backlog_task_status which modifies task status in-place."""

    @pytest.fixture
    def backlog_file(self, tmp_path: Path, sample_task_data: dict) -> Path:
        """Generate a backlog file to use for update tests."""
        return generate_backlog_markdown(sample_task_data, "test-feature", output_dir=tmp_path)

    def test_updates_status_to_complete(self, backlog_file: Path) -> None:
        """Find a PENDING task row and change its status to COMPLETE."""
        result = update_backlog_task_status(backlog_file, "TEST-L1-001", "COMPLETE")
        assert result is True
        content = backlog_file.read_text()
        # The task row should now show COMPLETE
        for line in content.splitlines():
            if "TEST-L1-001" in line:
                assert "COMPLETE" in line
                break
        else:
            pytest.fail("TEST-L1-001 not found in backlog after update")

    def test_adds_blocker(self, backlog_file: Path) -> None:
        """When a blocker is provided, it should appear in the blockers section."""
        result = update_backlog_task_status(
            backlog_file,
            "TEST-L2-001",
            "BLOCKED",
            blocker="Waiting on API credentials",
        )
        assert result is True
        content = backlog_file.read_text()
        assert "Waiting on API credentials" in content

    def test_missing_task_returns_false(self, backlog_file: Path) -> None:
        """Attempting to update a non-existent task ID returns False."""
        result = update_backlog_task_status(backlog_file, "NONEXISTENT-999", "COMPLETE")
        assert result is False

    def test_nonexistent_file_returns_false(self, tmp_path: Path) -> None:
        """Attempting to update a file that does not exist returns False."""
        fake_path = tmp_path / "does_not_exist.md"
        result = update_backlog_task_status(fake_path, "TEST-L1-001", "COMPLETE")
        assert result is False
