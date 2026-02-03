"""Integration tests for rush pre-execution validation with graph validation."""

import json
from pathlib import Path

import pytest

from zerg.validation import ValidationError, load_and_validate_task_graph


def _write_task_graph(tmp_dir, graph_data):
    """Write a task graph JSON to a temp file."""
    path = Path(tmp_dir) / "task-graph.json"
    with open(path, "w") as f:
        json.dump(graph_data, f)
    return str(path)


def _minimal_task(id, level=1, deps=None, files_create=None, **extra):
    """Build a minimal valid task dict."""
    t = {
        "id": id,
        "title": f"Task {id}",
        "level": level,
        "dependencies": deps or [],
        "phase": "foundation",
        "files": {"create": files_create or [f"{id.lower()}.py"], "modify": [], "read": []},
        "verification": {"command": "echo ok", "timeout_seconds": 30},
        "estimate_minutes": 5,
        "skills_required": ["python"],
    }
    t.update(extra)
    return t


class TestRushGraphValidation:
    def test_valid_graph_passes(self, tmp_path):
        """A valid task graph should pass all validation including graph properties."""
        graph = {
            "feature": "test",
            "version": "2.0",
            "total_tasks": 2,
            "max_parallelization": 1,
            "tasks": [
                _minimal_task("TASK-001", level=1, files_create=["a.py"]),
                _minimal_task("TASK-002", level=2, deps=["TASK-001"], files_create=["b.py"]),
            ],
            "levels": {
                "1": {"name": "foundation", "tasks": ["TASK-001"]},
                "2": {"name": "core", "tasks": ["TASK-002"]},
            },
        }
        path = _write_task_graph(tmp_path, graph)
        result = load_and_validate_task_graph(path)
        assert "tasks" in result
        assert len(result["tasks"]) == 2

    def test_invalid_dep_ref_fails(self, tmp_path):
        """A graph with bad dependency references should fail validation."""
        graph = {
            "feature": "test",
            "version": "2.0",
            "total_tasks": 1,
            "max_parallelization": 1,
            "tasks": [
                _minimal_task("TASK-001", level=1, deps=["NONEXISTENT"], files_create=["a.py"]),
            ],
            "levels": {
                "1": {"name": "foundation", "tasks": ["TASK-001"]},
            },
        }
        path = _write_task_graph(tmp_path, graph)
        with pytest.raises((ValidationError, Exception)):
            load_and_validate_task_graph(path)

    def test_bad_consumer_ref_fails(self, tmp_path):
        """A graph with bad consumer references should fail via graph property validation."""
        graph = {
            "feature": "test",
            "version": "2.0",
            "total_tasks": 1,
            "max_parallelization": 1,
            "tasks": [
                _minimal_task(
                    "TASK-001",
                    level=1,
                    files_create=["a.py"],
                    consumers=["FAKE-999"],
                    integration_test="tests/test.py",
                ),
            ],
            "levels": {
                "1": {"name": "foundation", "tasks": ["TASK-001"]},
            },
        }
        path = _write_task_graph(tmp_path, graph)
        with pytest.raises((ValidationError, Exception)):
            load_and_validate_task_graph(path)

    def test_consumers_without_integration_test_fails(self, tmp_path):
        """Tasks with consumers but no integration_test should fail graph validation."""
        graph = {
            "feature": "test",
            "version": "2.0",
            "total_tasks": 2,
            "max_parallelization": 1,
            "tasks": [
                _minimal_task(
                    "TASK-001",
                    level=1,
                    files_create=["a.py"],
                    consumers=["TASK-002"],
                    # No integration_test — should fail
                ),
                _minimal_task("TASK-002", level=2, deps=["TASK-001"], files_create=["b.py"]),
            ],
            "levels": {
                "1": {"name": "foundation", "tasks": ["TASK-001"]},
                "2": {"name": "core", "tasks": ["TASK-002"]},
            },
        }
        path = _write_task_graph(tmp_path, graph)
        with pytest.raises(ValidationError) as exc_info:
            load_and_validate_task_graph(path)
        assert "integration_test" in str(exc_info.value).lower()

    def test_unreachable_task_fails(self, tmp_path):
        """A disconnected L2 task with no deps should fail as unreachable."""
        graph = {
            "feature": "test",
            "version": "2.0",
            "total_tasks": 2,
            "max_parallelization": 1,
            "tasks": [
                _minimal_task("TASK-001", level=1, files_create=["a.py"]),
                _minimal_task("TASK-002", level=2, deps=[], files_create=["b.py"]),
            ],
            "levels": {
                "1": {"name": "foundation", "tasks": ["TASK-001"]},
                "2": {"name": "core", "tasks": ["TASK-002"]},
            },
        }
        path = _write_task_graph(tmp_path, graph)
        with pytest.raises((ValidationError, Exception)):
            load_and_validate_task_graph(path)

    def test_file_not_found_raises(self, tmp_path):
        """Non-existent file should raise ValidationError."""
        path = str(tmp_path / "nonexistent.json")
        with pytest.raises(ValidationError):
            load_and_validate_task_graph(path)

    def test_file_ownership_conflict_fails(self, tmp_path):
        """Two tasks claiming the same file should fail."""
        graph = {
            "feature": "test",
            "version": "2.0",
            "total_tasks": 2,
            "max_parallelization": 1,
            "tasks": [
                _minimal_task("TASK-001", level=1, files_create=["shared.py"]),
                _minimal_task("TASK-002", level=2, deps=["TASK-001"], files_create=["shared.py"]),
            ],
            "levels": {
                "1": {"name": "foundation", "tasks": ["TASK-001"]},
                "2": {"name": "core", "tasks": ["TASK-002"]},
            },
        }
        path = _write_task_graph(tmp_path, graph)
        with pytest.raises(ValidationError) as exc_info:
            load_and_validate_task_graph(path)
        err_msg = str(exc_info.value).lower()
        assert "ownership" in err_msg or "conflict" in err_msg
