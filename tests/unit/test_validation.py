"""Unit tests for ZERG validation module."""

import json
from pathlib import Path

import pytest

from zerg.exceptions import ValidationError
from zerg.validation import (
    load_and_validate_task_graph,
    sanitize_task_id,
    validate_dependencies,
    validate_file_ownership,
    validate_task_graph,
    validate_task_id,
)


class TestValidateTaskId:
    """Tests for task ID validation."""

    def test_valid_task_id(self) -> None:
        """Test valid task IDs pass validation."""
        valid_ids = ["TASK-001", "CLI-L1-001", "TEST-001", "GAP-L0-001"]
        for task_id in valid_ids:
            is_valid, error = validate_task_id(task_id)
            assert is_valid, f"Expected {task_id} to be valid: {error}"

    def test_empty_task_id_invalid(self) -> None:
        """Test empty task ID is invalid."""
        is_valid, error = validate_task_id("")
        assert not is_valid
        assert "empty" in error.lower()

    def test_task_id_max_length(self) -> None:
        """Test task ID length limit."""
        long_id = "T" * 65
        is_valid, error = validate_task_id(long_id)
        assert not is_valid
        assert "too long" in error.lower()

    def test_dangerous_characters_rejected(self) -> None:
        """Test dangerous characters are rejected."""
        dangerous_ids = [
            "TASK;rm -rf",
            "TASK|cat",
            "TASK&echo",
            "TASK`pwd`",
            "TASK$(id)",
            "TASK'inject",
            'TASK"inject',
        ]
        for task_id in dangerous_ids:
            is_valid, error = validate_task_id(task_id)
            assert not is_valid, f"Expected {task_id} to be rejected"
            assert "dangerous" in error.lower()

    def test_strict_pattern_validation(self) -> None:
        """Test strict pattern validation."""
        is_valid, error = validate_task_id("TASK-001", strict=True)
        assert is_valid

        is_valid, error = validate_task_id("lowercase-001", strict=True)
        assert not is_valid

    def test_non_string_task_id(self) -> None:
        """Test non-string task ID is rejected."""
        is_valid, error = validate_task_id(123)  # type: ignore
        assert not is_valid
        assert "string" in error.lower()


class TestSanitizeTaskId:
    """Tests for task ID sanitization."""

    def test_sanitize_valid_id(self) -> None:
        """Test sanitization preserves valid IDs."""
        assert sanitize_task_id("TASK-001") == "TASK-001"

    def test_sanitize_removes_dangerous_chars(self) -> None:
        """Test sanitization removes dangerous characters."""
        assert sanitize_task_id("TASK;rm") == "TASK_rm"
        assert sanitize_task_id("TASK|cat") == "TASK_cat"

    def test_sanitize_empty_returns_unknown(self) -> None:
        """Test sanitization of empty ID returns unknown."""
        assert sanitize_task_id("") == "unknown"
        assert sanitize_task_id(None) == "unknown"  # type: ignore

    def test_sanitize_truncates_long_ids(self) -> None:
        """Test sanitization truncates long IDs."""
        long_id = "T" * 100
        result = sanitize_task_id(long_id)
        assert len(result) <= 64

    def test_sanitize_ensures_starts_with_letter(self) -> None:
        """Test sanitization ensures ID starts with letter."""
        result = sanitize_task_id("123task")
        assert result[0].isalpha()


class TestValidateTaskGraph:
    """Tests for task graph validation."""

    def test_valid_task_graph(self) -> None:
        """Test valid task graph passes validation."""
        graph = {
            "feature": "test",
            "tasks": [
                {"id": "TASK-001", "title": "Test", "level": 1, "dependencies": []},
            ],
        }
        is_valid, errors = validate_task_graph(graph)
        assert is_valid
        assert len(errors) == 0

    def test_missing_feature_invalid(self) -> None:
        """Test missing feature field is invalid."""
        graph = {"tasks": [{"id": "TASK-001", "title": "Test", "level": 1}]}
        is_valid, errors = validate_task_graph(graph)
        assert not is_valid
        assert any("feature" in e.lower() for e in errors)

    def test_missing_tasks_invalid(self) -> None:
        """Test missing tasks field is invalid."""
        graph = {"feature": "test"}
        is_valid, errors = validate_task_graph(graph)
        assert not is_valid
        assert any("tasks" in e.lower() for e in errors)

    def test_empty_tasks_invalid(self) -> None:
        """Test empty tasks list is invalid."""
        graph = {"feature": "test", "tasks": []}
        is_valid, errors = validate_task_graph(graph)
        assert not is_valid

    def test_task_missing_id_invalid(self) -> None:
        """Test task missing ID is invalid."""
        graph = {"feature": "test", "tasks": [{"title": "Test", "level": 1}]}
        is_valid, errors = validate_task_graph(graph)
        assert not is_valid
        assert any("id" in e.lower() for e in errors)

    def test_duplicate_task_id_invalid(self) -> None:
        """Test duplicate task IDs are invalid."""
        graph = {
            "feature": "test",
            "tasks": [
                {"id": "TASK-001", "title": "Test 1", "level": 1},
                {"id": "TASK-001", "title": "Test 2", "level": 1},
            ],
        }
        is_valid, errors = validate_task_graph(graph)
        assert not is_valid
        assert any("duplicate" in e.lower() for e in errors)


class TestValidateFileOwnership:
    """Tests for file ownership validation."""

    def test_no_conflicts(self) -> None:
        """Test no conflicts when files are unique."""
        graph = {
            "tasks": [
                {"id": "T1", "files": {"create": ["a.py"], "modify": []}},
                {"id": "T2", "files": {"create": ["b.py"], "modify": []}},
            ]
        }
        is_valid, errors = validate_file_ownership(graph)
        assert is_valid
        assert len(errors) == 0

    def test_conflict_detected(self) -> None:
        """Test conflict detected when files overlap."""
        graph = {
            "tasks": [
                {"id": "T1", "files": {"create": ["shared.py"], "modify": []}},
                {"id": "T2", "files": {"create": ["shared.py"], "modify": []}},
            ]
        }
        is_valid, errors = validate_file_ownership(graph)
        assert not is_valid
        assert any("conflict" in e.lower() for e in errors)


class TestValidateDependencies:
    """Tests for dependency validation."""

    def test_valid_dependencies(self) -> None:
        """Test valid dependencies pass."""
        graph = {
            "tasks": [
                {"id": "T1", "level": 1, "dependencies": []},
                {"id": "T2", "level": 2, "dependencies": ["T1"]},
            ]
        }
        is_valid, errors = validate_dependencies(graph)
        assert is_valid

    def test_dependency_wrong_level(self) -> None:
        """Test dependency in wrong level is rejected."""
        graph = {
            "tasks": [
                {"id": "T1", "level": 2, "dependencies": []},
                {"id": "T2", "level": 1, "dependencies": ["T1"]},  # T1 is level 2
            ]
        }
        is_valid, errors = validate_dependencies(graph)
        assert not is_valid


class TestLoadAndValidateTaskGraph:
    """Tests for loading and validating task graph from file."""

    def test_file_not_found(self, tmp_path: Path) -> None:
        """Test error when file not found."""
        with pytest.raises(ValidationError) as exc_info:
            load_and_validate_task_graph(tmp_path / "nonexistent.json")
        assert "not found" in str(exc_info.value).lower()

    def test_valid_file_loads(self, tmp_path: Path) -> None:
        """Test valid file loads successfully."""
        graph = {
            "feature": "test",
            "tasks": [
                {"id": "TASK-001", "title": "Test", "level": 1, "dependencies": []},
            ],
        }
        file_path = tmp_path / "task-graph.json"
        file_path.write_text(json.dumps(graph))

        result = load_and_validate_task_graph(file_path)
        assert result["feature"] == "test"
