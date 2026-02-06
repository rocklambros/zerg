"""Unit tests for ZERG validation module.

Thinned: collapsed permutation tests into parametrized tests.
Keeps 1 happy-path + 1 error-path per validation category.
"""

import json
from pathlib import Path

import pytest

from zerg.exceptions import ValidationError
from zerg.validation import (
    TASK_ID_PATTERN,
    TASK_ID_RELAXED_PATTERN,
    _validate_levels,
    _validate_task,
    load_and_validate_task_graph,
    sanitize_task_id,
    validate_dependencies,
    validate_file_ownership,
    validate_task_graph,
    validate_task_id,
)


class TestTaskIdPatterns:
    """Tests for task ID regex patterns."""

    @pytest.mark.parametrize(
        "task_id,strict,relaxed",
        [
            ("TASK-001", True, True),
            ("T1", True, True),
            ("task-001", False, True),
            ("123task", False, False),
            ("", False, False),
        ],
    )
    def test_patterns(self, task_id: str, strict: bool, relaxed: bool) -> None:
        assert bool(TASK_ID_PATTERN.match(task_id)) == strict
        assert bool(TASK_ID_RELAXED_PATTERN.match(task_id)) == relaxed


class TestValidateTaskId:
    """Tests for task ID validation."""

    def test_valid_id(self) -> None:
        is_valid, error = validate_task_id("TASK-001")
        assert is_valid and error is None

    @pytest.mark.parametrize(
        "task_id,error_word",
        [
            ("", "empty"),
            ("T" * 65, "too long"),
            ("TASK;rm", "dangerous"),
            ("TASK|cat", "dangerous"),
            ("TASK`pwd`", "dangerous"),
            ("TASK\nX", "dangerous"),
            ("TASK\\X", "dangerous"),
            ("TASK{X}", "dangerous"),
        ],
    )
    def test_invalid_ids(self, task_id: str, error_word: str) -> None:
        is_valid, error = validate_task_id(task_id)
        assert not is_valid and error_word in error.lower()

    def test_strict_mode(self) -> None:
        assert validate_task_id("TASK-001", strict=True)[0] is True
        assert validate_task_id("lowercase", strict=True)[0] is False

    def test_non_string_type(self) -> None:
        is_valid, error = validate_task_id(123)  # type: ignore
        assert not is_valid and "string" in error.lower()


class TestSanitizeTaskId:
    """Tests for task ID sanitization."""

    @pytest.mark.parametrize(
        "input_id,expected",
        [
            ("TASK-001", "TASK-001"),
            ("TASK;rm", "TASK_rm"),
            ("TASK|cat", "TASK_cat"),
            ("", "unknown"),
            (None, "unknown"),
        ],
    )
    def test_sanitize(self, input_id, expected: str) -> None:
        assert sanitize_task_id(input_id) == expected

    def test_truncates_and_prefixes(self) -> None:
        assert len(sanitize_task_id("T" * 100)) == 64
        assert sanitize_task_id("123task") == "T123task"


class TestValidateTask:
    """Tests for _validate_task helper function."""

    def test_valid_task(self) -> None:
        task = {"id": "TASK-001", "title": "Test Task", "level": 1}
        assert len(_validate_task(task, 0, set())) == 0

    def test_not_dict(self) -> None:
        assert any("object" in e.lower() for e in _validate_task("bad", 0, set()))  # type: ignore

    def test_missing_required_fields(self) -> None:
        assert any("'id'" in e for e in _validate_task({"title": "T", "level": 1}, 0, set()))
        assert any("'title'" in e for e in _validate_task({"id": "T1", "level": 1}, 0, set()))
        assert any("'level'" in e for e in _validate_task({"id": "T1", "title": "T"}, 0, set()))

    def test_duplicate_id(self) -> None:
        task = {"id": "T1", "title": "T", "level": 1}
        assert any("duplicate" in e.lower() for e in _validate_task(task, 1, {"T1"}))

    def test_level_not_positive(self) -> None:
        task = {"id": "T1", "title": "T", "level": 0}
        assert any("positive integer" in e.lower() for e in _validate_task(task, 0, set()))

    def test_verification_valid_and_invalid(self) -> None:
        good = {"id": "T1", "title": "T", "level": 1, "verification": {"command": "pytest"}}
        assert len(_validate_task(good, 0, set())) == 0
        bad = {"id": "T1", "title": "T", "level": 1, "verification": "cmd"}
        assert any("verification must be an object" in e.lower() for e in _validate_task(bad, 0, set()))

    def test_files_not_dict(self) -> None:
        task = {"id": "T1", "title": "T", "level": 1, "files": ["a.py"]}
        assert any("files must be an object" in e.lower() for e in _validate_task(task, 0, set()))


class TestValidateLevels:
    """Tests for _validate_levels helper function."""

    def test_valid(self) -> None:
        assert len(_validate_levels({"1": {"name": "F", "tasks": ["T1"]}}, {"T1"})) == 0

    def test_invalid(self) -> None:
        assert any("object" in e.lower() for e in _validate_levels(["lvl"], set()))  # type: ignore
        assert any("unknown task" in e.lower() for e in _validate_levels({"1": {"name": "F", "tasks": ["X"]}}, set()))


class TestValidateTaskGraph:
    """Tests for task graph validation."""

    def test_valid_graph(self) -> None:
        graph = {"feature": "t", "tasks": [{"id": "T1", "title": "T", "level": 1, "dependencies": []}]}
        assert validate_task_graph(graph)[0] is True

    def test_missing_feature(self) -> None:
        assert validate_task_graph({"tasks": [{"id": "T1", "title": "T", "level": 1}]})[0] is False

    def test_empty_tasks(self) -> None:
        assert validate_task_graph({"feature": "t", "tasks": []})[0] is False

    def test_duplicate_ids(self) -> None:
        graph = {
            "feature": "t",
            "tasks": [{"id": "T1", "title": "A", "level": 1}, {"id": "T1", "title": "B", "level": 1}],
        }
        is_valid, errors = validate_task_graph(graph)
        assert not is_valid and any("duplicate" in e.lower() for e in errors)


class TestValidateFileOwnership:
    """Tests for file ownership validation."""

    def test_no_conflict(self) -> None:
        graph = {
            "tasks": [
                {"id": "T1", "files": {"create": ["a.py"], "modify": []}},
                {"id": "T2", "files": {"create": ["b.py"], "modify": []}},
            ]
        }
        assert validate_file_ownership(graph)[0] is True

    def test_conflict(self) -> None:
        graph = {
            "tasks": [
                {"id": "T1", "files": {"create": ["s.py"], "modify": []}},
                {"id": "T2", "files": {"create": ["s.py"], "modify": []}},
            ]
        }
        is_valid, errors = validate_file_ownership(graph)
        assert not is_valid and any("conflict" in e.lower() for e in errors)


class TestValidateDependencies:
    """Tests for dependency validation."""

    def test_valid(self) -> None:
        graph = {
            "tasks": [
                {"id": "T1", "level": 1, "dependencies": []},
                {"id": "T2", "level": 2, "dependencies": ["T1"]},
            ]
        }
        assert validate_dependencies(graph)[0] is True

    def test_wrong_level(self) -> None:
        graph = {
            "tasks": [
                {"id": "T1", "level": 2, "dependencies": []},
                {"id": "T2", "level": 1, "dependencies": ["T1"]},
            ]
        }
        assert validate_dependencies(graph)[0] is False

    def test_cycle(self) -> None:
        graph = {
            "tasks": [
                {"id": "T1", "level": 1, "dependencies": ["T2"]},
                {"id": "T2", "level": 1, "dependencies": ["T1"]},
            ]
        }
        is_valid, errors = validate_dependencies(graph)
        assert not is_valid and any("cycle" in e.lower() for e in errors)


class TestLoadAndValidateTaskGraph:
    """Tests for loading and validating task graph from file."""

    def test_file_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(ValidationError) as exc_info:
            load_and_validate_task_graph(tmp_path / "nonexistent.json")
        assert "not found" in str(exc_info.value).lower()

    def test_valid_file(self, tmp_path: Path) -> None:
        graph = {"feature": "t", "tasks": [{"id": "T1", "title": "T", "level": 1, "dependencies": []}]}
        fp = tmp_path / "task-graph.json"
        fp.write_text(json.dumps(graph))
        assert load_and_validate_task_graph(fp)["feature"] == "t"

    def test_schema_failure(self, tmp_path: Path) -> None:
        fp = tmp_path / "task-graph.json"
        fp.write_text(json.dumps({"feature": "t", "tasks": []}))
        with pytest.raises(ValidationError) as exc_info:
            load_and_validate_task_graph(fp)
        assert exc_info.value.field == "schema"

    def test_ownership_failure(self, tmp_path: Path) -> None:
        graph = {
            "feature": "t",
            "tasks": [
                {"id": "T1", "title": "A", "level": 1, "files": {"create": ["s.py"]}},
                {"id": "T2", "title": "B", "level": 1, "files": {"create": ["s.py"]}},
            ],
        }
        fp = tmp_path / "task-graph.json"
        fp.write_text(json.dumps(graph))
        with pytest.raises(ValidationError) as exc_info:
            load_and_validate_task_graph(fp)
        assert exc_info.value.field == "file_ownership"

    def test_dependency_failure(self, tmp_path: Path) -> None:
        graph = {
            "feature": "t",
            "tasks": [
                {"id": "T1", "title": "A", "level": 2, "dependencies": []},
                {"id": "T2", "title": "B", "level": 1, "dependencies": ["T1"]},
            ],
        }
        fp = tmp_path / "task-graph.json"
        fp.write_text(json.dumps(graph))
        with pytest.raises(ValidationError) as exc_info:
            load_and_validate_task_graph(fp)
        assert exc_info.value.field == "dependencies"
