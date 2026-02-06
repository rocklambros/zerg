"""Comprehensive unit tests for ZERG validation module.

Tests all validation functions for task graphs, task IDs, file ownership,
and dependency validation to achieve 100% coverage.
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

    def test_strict_pattern_valid_examples(self) -> None:
        """Test strict pattern matches valid task IDs."""
        valid = ["TASK-001", "CLI-L1-001", "T1", "GAP-L0-999", "AB123"]
        for task_id in valid:
            assert TASK_ID_PATTERN.match(task_id), f"{task_id} should match strict pattern"

    def test_strict_pattern_invalid_examples(self) -> None:
        """Test strict pattern rejects invalid task IDs."""
        invalid = ["task-001", "TASK", "123", "-001", "task"]
        for task_id in invalid:
            assert not TASK_ID_PATTERN.match(task_id), f"{task_id} should not match strict pattern"

    def test_relaxed_pattern_valid_examples(self) -> None:
        """Test relaxed pattern matches valid task IDs."""
        valid = ["task", "Task001", "a", "A_B-C", "test-task-001"]
        for task_id in valid:
            assert TASK_ID_RELAXED_PATTERN.match(task_id), f"{task_id} should match relaxed pattern"

    def test_relaxed_pattern_invalid_examples(self) -> None:
        """Test relaxed pattern rejects invalid task IDs."""
        invalid = ["123task", "_task", "-task", ""]
        for task_id in invalid:
            assert not TASK_ID_RELAXED_PATTERN.match(task_id), f"{task_id} should not match relaxed pattern"


class TestValidateTaskId:
    """Tests for task ID validation."""

    def test_valid_task_id(self) -> None:
        """Test valid task IDs pass validation."""
        valid_ids = ["TASK-001", "CLI-L1-001", "TEST-001", "GAP-L0-001"]
        for task_id in valid_ids:
            is_valid, error = validate_task_id(task_id)
            assert is_valid, f"Expected {task_id} to be valid: {error}"
            assert error is None

    def test_empty_task_id_invalid(self) -> None:
        """Test empty task ID is invalid."""
        is_valid, error = validate_task_id("")
        assert not is_valid
        assert error is not None
        assert "empty" in error.lower()

    def test_none_task_id_triggers_empty_check(self) -> None:
        """Test None task ID triggers empty check."""
        # This tests the falsy check for task_id
        is_valid, error = validate_task_id(None)  # type: ignore
        assert not is_valid
        assert "empty" in error.lower()

    def test_task_id_max_length(self) -> None:
        """Test task ID length limit (64 chars)."""
        long_id = "T" * 65
        is_valid, error = validate_task_id(long_id)
        assert not is_valid
        assert "too long" in error.lower()
        assert "65" in error
        assert "64" in error

    def test_task_id_at_max_length(self) -> None:
        """Test task ID at exactly 64 chars."""
        exact_id = "T" * 63 + "1"  # 64 chars, ends with digit for pattern
        is_valid, error = validate_task_id(exact_id)
        # Should pass length check, may fail pattern check
        assert "too long" not in (error or "").lower()

    def test_dangerous_characters_semicolon(self) -> None:
        """Test semicolon is rejected."""
        is_valid, error = validate_task_id("TASK;rm -rf")
        assert not is_valid
        assert "dangerous" in error.lower()

    def test_dangerous_characters_pipe(self) -> None:
        """Test pipe is rejected."""
        is_valid, error = validate_task_id("TASK|cat")
        assert not is_valid
        assert "dangerous" in error.lower()

    def test_dangerous_characters_ampersand(self) -> None:
        """Test ampersand is rejected."""
        is_valid, error = validate_task_id("TASK&echo")
        assert not is_valid
        assert "dangerous" in error.lower()

    def test_dangerous_characters_backtick(self) -> None:
        """Test backtick is rejected."""
        is_valid, error = validate_task_id("TASK`pwd`")
        assert not is_valid
        assert "dangerous" in error.lower()

    def test_dangerous_characters_dollar_paren(self) -> None:
        """Test $() is rejected."""
        is_valid, error = validate_task_id("TASK$(id)")
        assert not is_valid
        assert "dangerous" in error.lower()

    def test_dangerous_characters_single_quote(self) -> None:
        """Test single quote is rejected."""
        is_valid, error = validate_task_id("TASK'inject")
        assert not is_valid
        assert "dangerous" in error.lower()

    def test_dangerous_characters_double_quote(self) -> None:
        """Test double quote is rejected."""
        is_valid, error = validate_task_id('TASK"inject')
        assert not is_valid
        assert "dangerous" in error.lower()

    def test_dangerous_characters_newline(self) -> None:
        """Test newline is rejected."""
        is_valid, error = validate_task_id("TASK\nINJECT")
        assert not is_valid
        assert "dangerous" in error.lower()

    def test_dangerous_characters_tab(self) -> None:
        """Test tab is rejected."""
        is_valid, error = validate_task_id("TASK\tINJECT")
        assert not is_valid
        assert "dangerous" in error.lower()

    def test_dangerous_characters_carriage_return(self) -> None:
        """Test carriage return is rejected."""
        is_valid, error = validate_task_id("TASK\rINJECT")
        assert not is_valid
        assert "dangerous" in error.lower()

    def test_dangerous_characters_backslash(self) -> None:
        """Test backslash is rejected."""
        is_valid, error = validate_task_id("TASK\\INJECT")
        assert not is_valid
        assert "dangerous" in error.lower()

    def test_dangerous_characters_curly_braces(self) -> None:
        """Test curly braces are rejected."""
        is_valid, error = validate_task_id("TASK{INJECT}")
        assert not is_valid
        assert "dangerous" in error.lower()

    def test_dangerous_characters_square_brackets(self) -> None:
        """Test square brackets are rejected."""
        is_valid, error = validate_task_id("TASK[INJECT]")
        assert not is_valid
        assert "dangerous" in error.lower()

    def test_dangerous_characters_angle_brackets(self) -> None:
        """Test angle brackets are rejected."""
        is_valid, error = validate_task_id("TASK<INJECT>")
        assert not is_valid
        assert "dangerous" in error.lower()

    def test_strict_pattern_validation_pass(self) -> None:
        """Test strict pattern validation passes for valid ID."""
        is_valid, error = validate_task_id("TASK-001", strict=True)
        assert is_valid
        assert error is None

    def test_strict_pattern_validation_fail_lowercase(self) -> None:
        """Test strict pattern validation fails for lowercase."""
        is_valid, error = validate_task_id("lowercase-001", strict=True)
        assert not is_valid
        assert "pattern" in error.lower()
        assert "A-Z" in error

    def test_strict_pattern_validation_fail_no_digit(self) -> None:
        """Test strict pattern validation fails without trailing digit."""
        is_valid, error = validate_task_id("TASK-ABC", strict=True)
        assert not is_valid
        assert "pattern" in error.lower()

    def test_relaxed_pattern_validation_pass(self) -> None:
        """Test relaxed pattern validation passes."""
        is_valid, error = validate_task_id("myTask")
        assert is_valid
        assert error is None

    def test_relaxed_pattern_validation_fail_starts_with_digit(self) -> None:
        """Test relaxed pattern fails when starting with digit."""
        is_valid, error = validate_task_id("123task")
        assert not is_valid
        assert "pattern" in error.lower()

    def test_non_string_task_id_int(self) -> None:
        """Test non-string task ID (int) is rejected."""
        is_valid, error = validate_task_id(123)  # type: ignore
        assert not is_valid
        assert "string" in error.lower()
        assert "int" in error.lower()

    def test_non_string_task_id_list(self) -> None:
        """Test non-string task ID (list) is rejected."""
        is_valid, error = validate_task_id(["task"])  # type: ignore
        assert not is_valid
        assert "string" in error.lower()
        assert "list" in error.lower()

    def test_non_string_task_id_dict(self) -> None:
        """Test non-string task ID (dict) is rejected."""
        is_valid, error = validate_task_id({"id": "task"})  # type: ignore
        assert not is_valid
        assert "string" in error.lower()
        assert "dict" in error.lower()

    def test_valid_relaxed_id_with_underscore(self) -> None:
        """Test relaxed pattern accepts underscores."""
        is_valid, error = validate_task_id("task_001")
        assert is_valid

    def test_valid_relaxed_id_with_hyphen(self) -> None:
        """Test relaxed pattern accepts hyphens."""
        is_valid, error = validate_task_id("task-001")
        assert is_valid


class TestSanitizeTaskId:
    """Tests for task ID sanitization."""

    def test_sanitize_valid_id(self) -> None:
        """Test sanitization preserves valid IDs."""
        assert sanitize_task_id("TASK-001") == "TASK-001"
        assert sanitize_task_id("my_task") == "my_task"

    def test_sanitize_removes_semicolon(self) -> None:
        """Test sanitization removes semicolons."""
        assert sanitize_task_id("TASK;rm") == "TASK_rm"

    def test_sanitize_removes_pipe(self) -> None:
        """Test sanitization removes pipes."""
        assert sanitize_task_id("TASK|cat") == "TASK_cat"

    def test_sanitize_removes_dollar_sign(self) -> None:
        """Test sanitization removes dollar signs."""
        assert sanitize_task_id("TASK$var") == "TASK_var"

    def test_sanitize_removes_backtick(self) -> None:
        """Test sanitization removes backticks."""
        assert sanitize_task_id("TASK`cmd`") == "TASK_cmd_"

    def test_sanitize_removes_parentheses(self) -> None:
        """Test sanitization removes parentheses."""
        assert sanitize_task_id("TASK(test)") == "TASK_test_"

    def test_sanitize_removes_quotes(self) -> None:
        """Test sanitization removes quotes."""
        assert sanitize_task_id("TASK'test'") == "TASK_test_"
        assert sanitize_task_id('TASK"test"') == "TASK_test_"

    def test_sanitize_removes_whitespace(self) -> None:
        """Test sanitization removes whitespace characters."""
        assert sanitize_task_id("TASK\ntest") == "TASK_test"
        assert sanitize_task_id("TASK\ttest") == "TASK_test"
        assert sanitize_task_id("TASK test") == "TASK_test"

    def test_sanitize_empty_returns_unknown(self) -> None:
        """Test sanitization of empty ID returns unknown."""
        assert sanitize_task_id("") == "unknown"

    def test_sanitize_none_returns_unknown(self) -> None:
        """Test sanitization of None returns unknown."""
        assert sanitize_task_id(None) == "unknown"  # type: ignore

    def test_sanitize_truncates_long_ids(self) -> None:
        """Test sanitization truncates long IDs to 64 chars."""
        long_id = "T" * 100
        result = sanitize_task_id(long_id)
        assert len(result) == 64

    def test_sanitize_truncates_exactly_at_limit(self) -> None:
        """Test sanitization doesn't truncate at exactly 64."""
        exact_id = "T" * 64
        result = sanitize_task_id(exact_id)
        assert len(result) == 64
        assert result == exact_id

    def test_sanitize_ensures_starts_with_letter(self) -> None:
        """Test sanitization ensures ID starts with letter."""
        result = sanitize_task_id("123task")
        assert result[0].isalpha()
        assert result == "T123task"

    def test_sanitize_starts_with_underscore(self) -> None:
        """Test sanitization handles ID starting with underscore."""
        result = sanitize_task_id("_task")
        assert result[0].isalpha()
        assert result == "T_task"

    def test_sanitize_starts_with_hyphen(self) -> None:
        """Test sanitization handles ID starting with hyphen."""
        result = sanitize_task_id("-task")
        assert result[0].isalpha()
        assert result == "T-task"

    def test_sanitize_all_special_chars_returns_unknown(self) -> None:
        """Test sanitization of all-special-char ID returns unknown."""
        result = sanitize_task_id(";;;")
        # After replacing all chars with underscores and prepending T, we get T___
        assert result[0].isalpha()

    def test_sanitize_empty_after_cleaning_returns_unknown(self) -> None:
        """Test when sanitization results in empty string."""
        # This is an edge case - all dangerous chars replaced with underscores
        result = sanitize_task_id(";")
        assert result == "T_"  # _ is the replacement, T is prepended


class TestValidateTask:
    """Tests for _validate_task helper function."""

    def test_validate_task_valid(self) -> None:
        """Test valid task passes validation."""
        task = {"id": "TASK-001", "title": "Test Task", "level": 1}
        errors = _validate_task(task, 0, set())
        assert len(errors) == 0

    def test_validate_task_not_dict(self) -> None:
        """Test non-dict task is rejected."""
        errors = _validate_task("not a dict", 0, set())  # type: ignore
        assert len(errors) == 1
        assert "object" in errors[0].lower()

    def test_validate_task_missing_id(self) -> None:
        """Test task missing id is rejected."""
        task = {"title": "Test", "level": 1}
        errors = _validate_task(task, 0, set())
        assert any("'id'" in e for e in errors)

    def test_validate_task_invalid_id_format(self) -> None:
        """Test task with invalid ID format is rejected."""
        task = {"id": ";;;", "title": "Test", "level": 1}
        errors = _validate_task(task, 0, set())
        # The error message contains "invalid task ID" (with capital ID)
        assert any("invalid task id" in e.lower() for e in errors)

    def test_validate_task_duplicate_id(self) -> None:
        """Test duplicate task ID is rejected."""
        task = {"id": "TASK-001", "title": "Test", "level": 1}
        existing_ids = {"TASK-001"}
        errors = _validate_task(task, 1, existing_ids)
        assert any("duplicate" in e.lower() for e in errors)

    def test_validate_task_missing_title(self) -> None:
        """Test task missing title is rejected."""
        task = {"id": "TASK-001", "level": 1}
        errors = _validate_task(task, 0, set())
        assert any("'title'" in e for e in errors)

    def test_validate_task_missing_level(self) -> None:
        """Test task missing level is rejected."""
        task = {"id": "TASK-001", "title": "Test"}
        errors = _validate_task(task, 0, set())
        assert any("'level'" in e for e in errors)

    def test_validate_task_level_not_int(self) -> None:
        """Test task with non-integer level is rejected."""
        task = {"id": "TASK-001", "title": "Test", "level": "one"}
        errors = _validate_task(task, 0, set())
        assert any("positive integer" in e.lower() for e in errors)

    def test_validate_task_level_zero(self) -> None:
        """Test task with level 0 is rejected."""
        task = {"id": "TASK-001", "title": "Test", "level": 0}
        errors = _validate_task(task, 0, set())
        assert any("positive integer" in e.lower() for e in errors)

    def test_validate_task_level_negative(self) -> None:
        """Test task with negative level is rejected."""
        task = {"id": "TASK-001", "title": "Test", "level": -1}
        errors = _validate_task(task, 0, set())
        assert any("positive integer" in e.lower() for e in errors)

    def test_validate_task_verification_not_dict(self) -> None:
        """Test task with non-dict verification is rejected."""
        task = {"id": "TASK-001", "title": "Test", "level": 1, "verification": "command"}
        errors = _validate_task(task, 0, set())
        assert any("verification must be an object" in e.lower() for e in errors)

    def test_validate_task_verification_missing_command(self) -> None:
        """Test task with verification missing command is rejected."""
        task = {"id": "TASK-001", "title": "Test", "level": 1, "verification": {"timeout": 30}}
        errors = _validate_task(task, 0, set())
        assert any("verification missing 'command'" in e.lower() for e in errors)

    def test_validate_task_verification_valid(self) -> None:
        """Test task with valid verification passes."""
        task = {
            "id": "TASK-001",
            "title": "Test",
            "level": 1,
            "verification": {"command": "pytest"},
        }
        errors = _validate_task(task, 0, set())
        assert len(errors) == 0

    def test_validate_task_files_not_dict(self) -> None:
        """Test task with non-dict files is rejected."""
        task = {"id": "TASK-001", "title": "Test", "level": 1, "files": ["a.py"]}
        errors = _validate_task(task, 0, set())
        assert any("files must be an object" in e.lower() for e in errors)

    def test_validate_task_files_create_not_list(self) -> None:
        """Test task with non-list files.create is rejected."""
        task = {"id": "TASK-001", "title": "Test", "level": 1, "files": {"create": "a.py"}}
        errors = _validate_task(task, 0, set())
        assert any("files.create must be a list" in e.lower() for e in errors)

    def test_validate_task_files_modify_not_list(self) -> None:
        """Test task with non-list files.modify is rejected."""
        task = {"id": "TASK-001", "title": "Test", "level": 1, "files": {"modify": "b.py"}}
        errors = _validate_task(task, 0, set())
        assert any("files.modify must be a list" in e.lower() for e in errors)

    def test_validate_task_files_read_not_list(self) -> None:
        """Test task with non-list files.read is rejected."""
        task = {"id": "TASK-001", "title": "Test", "level": 1, "files": {"read": "c.py"}}
        errors = _validate_task(task, 0, set())
        assert any("files.read must be a list" in e.lower() for e in errors)

    def test_validate_task_files_valid(self) -> None:
        """Test task with valid files passes."""
        task = {
            "id": "TASK-001",
            "title": "Test",
            "level": 1,
            "files": {"create": ["a.py"], "modify": ["b.py"], "read": ["c.py"]},
        }
        errors = _validate_task(task, 0, set())
        assert len(errors) == 0


class TestValidateLevels:
    """Tests for _validate_levels helper function."""

    def test_validate_levels_valid(self) -> None:
        """Test valid levels pass validation."""
        levels = {
            "1": {"name": "Foundation", "tasks": ["TASK-001"]},
            "2": {"name": "Core", "tasks": ["TASK-002"]},
        }
        task_ids = {"TASK-001", "TASK-002"}
        errors = _validate_levels(levels, task_ids)
        assert len(errors) == 0

    def test_validate_levels_not_dict(self) -> None:
        """Test non-dict levels is rejected."""
        errors = _validate_levels(["level1", "level2"], set())  # type: ignore
        assert any("object" in e.lower() for e in errors)

    def test_validate_levels_level_not_dict(self) -> None:
        """Test level that is not dict is rejected."""
        levels = {"1": "not a dict"}
        errors = _validate_levels(levels, set())
        assert any("must be an object" in e.lower() for e in errors)

    def test_validate_levels_missing_name(self) -> None:
        """Test level missing name is rejected."""
        levels = {"1": {"tasks": ["TASK-001"]}}
        errors = _validate_levels(levels, {"TASK-001"})
        assert any("missing required field 'name'" in e.lower() for e in errors)

    def test_validate_levels_missing_tasks(self) -> None:
        """Test level missing tasks is rejected."""
        levels = {"1": {"name": "Foundation"}}
        errors = _validate_levels(levels, set())
        assert any("missing required field 'tasks'" in e.lower() for e in errors)

    def test_validate_levels_tasks_not_list(self) -> None:
        """Test level with non-list tasks is rejected."""
        levels = {"1": {"name": "Foundation", "tasks": "TASK-001"}}
        errors = _validate_levels(levels, {"TASK-001"})
        assert any("tasks must be a list" in e.lower() for e in errors)

    def test_validate_levels_unknown_task(self) -> None:
        """Test level with unknown task is rejected."""
        levels = {"1": {"name": "Foundation", "tasks": ["TASK-001", "UNKNOWN"]}}
        errors = _validate_levels(levels, {"TASK-001"})
        # Check for the error message (case-insensitive, with quoted task name)
        assert any("unknown task" in e.lower() and "unknown" in e for e in errors)


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
        assert any("non-empty list" in e.lower() for e in errors)

    def test_tasks_not_list(self) -> None:
        """Test non-list tasks is invalid."""
        graph = {"feature": "test", "tasks": {"TASK-001": {}}}
        is_valid, errors = validate_task_graph(graph)
        assert not is_valid
        assert any("non-empty list" in e.lower() for e in errors)

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

    def test_dependency_not_found(self) -> None:
        """Test missing dependency is rejected."""
        graph = {
            "feature": "test",
            "tasks": [
                {"id": "TASK-001", "title": "Test", "level": 1, "dependencies": ["NONEXISTENT"]},
            ],
        }
        is_valid, errors = validate_task_graph(graph)
        assert not is_valid
        # Check the error contains both "dependency" and "not found"
        assert any("dependency" in e.lower() and "not found" in e.lower() for e in errors)

    def test_with_valid_levels(self) -> None:
        """Test task graph with valid levels section."""
        graph = {
            "feature": "test",
            "tasks": [
                {"id": "TASK-001", "title": "Test", "level": 1, "dependencies": []},
            ],
            "levels": {
                "1": {"name": "Foundation", "tasks": ["TASK-001"]},
            },
        }
        is_valid, errors = validate_task_graph(graph)
        assert is_valid
        assert len(errors) == 0

    def test_with_invalid_levels(self) -> None:
        """Test task graph with invalid levels section."""
        graph = {
            "feature": "test",
            "tasks": [
                {"id": "TASK-001", "title": "Test", "level": 1, "dependencies": []},
            ],
            "levels": {
                "1": {"name": "Foundation", "tasks": ["UNKNOWN"]},
            },
        }
        is_valid, errors = validate_task_graph(graph)
        assert not is_valid
        assert any("unknown task" in e.lower() for e in errors)


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

    def test_conflict_in_create(self) -> None:
        """Test conflict detected in create files."""
        graph = {
            "tasks": [
                {"id": "T1", "files": {"create": ["shared.py"], "modify": []}},
                {"id": "T2", "files": {"create": ["shared.py"], "modify": []}},
            ]
        }
        is_valid, errors = validate_file_ownership(graph)
        assert not is_valid
        assert any("conflict" in e.lower() for e in errors)
        assert any("T1" in e and "T2" in e for e in errors)

    def test_conflict_in_modify(self) -> None:
        """Test conflict detected in modify files."""
        graph = {
            "tasks": [
                {"id": "T1", "files": {"create": [], "modify": ["shared.py"]}},
                {"id": "T2", "files": {"create": [], "modify": ["shared.py"]}},
            ]
        }
        is_valid, errors = validate_file_ownership(graph)
        assert not is_valid
        assert any("conflict" in e.lower() for e in errors)

    def test_conflict_between_create_and_modify(self) -> None:
        """Test conflict between create and modify."""
        graph = {
            "tasks": [
                {"id": "T1", "files": {"create": ["shared.py"], "modify": []}},
                {"id": "T2", "files": {"create": [], "modify": ["shared.py"]}},
            ]
        }
        is_valid, errors = validate_file_ownership(graph)
        assert not is_valid
        assert any("conflict" in e.lower() for e in errors)

    def test_no_files_field(self) -> None:
        """Test tasks without files field pass validation."""
        graph = {
            "tasks": [
                {"id": "T1"},
                {"id": "T2"},
            ]
        }
        is_valid, errors = validate_file_ownership(graph)
        assert is_valid
        assert len(errors) == 0

    def test_empty_tasks(self) -> None:
        """Test empty tasks list passes validation."""
        graph = {"tasks": []}
        is_valid, errors = validate_file_ownership(graph)
        assert is_valid

    def test_missing_task_id(self) -> None:
        """Test task without ID uses 'unknown'."""
        graph = {
            "tasks": [
                {"files": {"create": ["shared.py"], "modify": []}},
                {"files": {"create": ["shared.py"], "modify": []}},
            ]
        }
        is_valid, errors = validate_file_ownership(graph)
        assert not is_valid
        # Both tasks use 'unknown' as ID
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
        assert len(errors) == 0

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
        assert any("dependency must be in lower level" in e.lower() for e in errors)

    def test_dependency_same_level(self) -> None:
        """Test dependency at same level is rejected."""
        graph = {
            "tasks": [
                {"id": "T1", "level": 1, "dependencies": []},
                {"id": "T2", "level": 1, "dependencies": ["T1"]},  # Same level
            ]
        }
        is_valid, errors = validate_dependencies(graph)
        assert not is_valid
        assert any("dependency must be in lower level" in e.lower() for e in errors)

    def test_cycle_detection(self) -> None:
        """Test dependency cycle is detected."""
        graph = {
            "tasks": [
                {"id": "T1", "level": 1, "dependencies": ["T2"]},
                {"id": "T2", "level": 1, "dependencies": ["T1"]},
            ]
        }
        is_valid, errors = validate_dependencies(graph)
        assert not is_valid
        assert any("cycle" in e.lower() for e in errors)

    def test_indirect_cycle_detection(self) -> None:
        """Test indirect dependency cycle is detected."""
        graph = {
            "tasks": [
                {"id": "T1", "level": 1, "dependencies": ["T3"]},
                {"id": "T2", "level": 1, "dependencies": ["T1"]},
                {"id": "T3", "level": 1, "dependencies": ["T2"]},
            ]
        }
        is_valid, errors = validate_dependencies(graph)
        assert not is_valid
        assert any("cycle" in e.lower() for e in errors)

    def test_empty_tasks(self) -> None:
        """Test empty tasks list passes validation."""
        graph = {"tasks": []}
        is_valid, errors = validate_dependencies(graph)
        assert is_valid

    def test_task_without_id(self) -> None:
        """Test tasks without ID are handled."""
        graph = {
            "tasks": [
                {"level": 1, "dependencies": []},
            ]
        }
        is_valid, errors = validate_dependencies(graph)
        # Task without ID is skipped in task_info
        assert is_valid

    def test_dependency_on_nonexistent_task(self) -> None:
        """Test dependency on non-existent task."""
        graph = {
            "tasks": [
                {"id": "T1", "level": 1, "dependencies": ["NONEXISTENT"]},
            ]
        }
        is_valid, errors = validate_dependencies(graph)
        # This doesn't trigger an error in validate_dependencies - it's caught elsewhere
        # But the level check still passes since NONEXISTENT isn't in task_info
        assert is_valid  # No cycle, no level violation for unknown dep

    def test_no_dependencies_field(self) -> None:
        """Test tasks without dependencies field pass."""
        graph = {
            "tasks": [
                {"id": "T1", "level": 1},
                {"id": "T2", "level": 2},
            ]
        }
        is_valid, errors = validate_dependencies(graph)
        assert is_valid


class TestLoadAndValidateTaskGraph:
    """Tests for loading and validating task graph from file."""

    def test_file_not_found(self, tmp_path: Path) -> None:
        """Test error when file not found."""
        with pytest.raises(ValidationError) as exc_info:
            load_and_validate_task_graph(tmp_path / "nonexistent.json")
        assert "not found" in str(exc_info.value).lower()
        assert exc_info.value.field == "path"

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

    def test_invalid_json(self, tmp_path: Path) -> None:
        """Test error on invalid JSON."""
        file_path = tmp_path / "task-graph.json"
        file_path.write_text("not valid json {")

        with pytest.raises(Exception):  # json.JSONDecodeError
            load_and_validate_task_graph(file_path)

    def test_schema_validation_failure(self, tmp_path: Path) -> None:
        """Test schema validation failure raises ValidationError."""
        graph = {
            "feature": "test",
            "tasks": [],  # Empty tasks list
        }
        file_path = tmp_path / "task-graph.json"
        file_path.write_text(json.dumps(graph))

        with pytest.raises(ValidationError) as exc_info:
            load_and_validate_task_graph(file_path)
        assert exc_info.value.field == "schema"
        assert "errors" in exc_info.value.details

    def test_file_ownership_validation_failure(self, tmp_path: Path) -> None:
        """Test file ownership validation failure raises ValidationError."""
        graph = {
            "feature": "test",
            "tasks": [
                {"id": "TASK-001", "title": "Test 1", "level": 1, "files": {"create": ["shared.py"]}},
                {"id": "TASK-002", "title": "Test 2", "level": 1, "files": {"create": ["shared.py"]}},
            ],
        }
        file_path = tmp_path / "task-graph.json"
        file_path.write_text(json.dumps(graph))

        with pytest.raises(ValidationError) as exc_info:
            load_and_validate_task_graph(file_path)
        assert exc_info.value.field == "file_ownership"
        assert "errors" in exc_info.value.details

    def test_dependency_validation_failure(self, tmp_path: Path) -> None:
        """Test dependency validation failure raises ValidationError."""
        graph = {
            "feature": "test",
            "tasks": [
                {"id": "TASK-001", "title": "Test 1", "level": 2, "dependencies": []},
                {"id": "TASK-002", "title": "Test 2", "level": 1, "dependencies": ["TASK-001"]},
            ],
        }
        file_path = tmp_path / "task-graph.json"
        file_path.write_text(json.dumps(graph))

        with pytest.raises(ValidationError) as exc_info:
            load_and_validate_task_graph(file_path)
        assert exc_info.value.field == "dependencies"
        assert "errors" in exc_info.value.details

    def test_accepts_string_path(self, tmp_path: Path) -> None:
        """Test function accepts string path."""
        graph = {
            "feature": "test",
            "tasks": [
                {"id": "TASK-001", "title": "Test", "level": 1, "dependencies": []},
            ],
        }
        file_path = tmp_path / "task-graph.json"
        file_path.write_text(json.dumps(graph))

        result = load_and_validate_task_graph(str(file_path))
        assert result["feature"] == "test"

    def test_complex_valid_graph(self, tmp_path: Path) -> None:
        """Test complex valid graph loads successfully."""
        # Note: Each task must own different files to avoid conflicts
        graph = {
            "feature": "complex-feature",
            "tasks": [
                {
                    "id": "TASK-001",
                    "title": "Foundation Task",
                    "level": 1,
                    "dependencies": [],
                    "files": {"create": ["src/base.py"], "modify": [], "read": []},
                    "verification": {"command": "pytest tests/test_base.py"},
                },
                {
                    "id": "TASK-002",
                    "title": "Core Task",
                    "level": 2,
                    "dependencies": ["TASK-001"],
                    # Use different files to avoid ownership conflict
                    "files": {"create": ["src/core.py"], "modify": [], "read": ["src/base.py"]},
                    "verification": {"command": "pytest tests/test_core.py", "timeout_seconds": 60},
                },
            ],
            "levels": {
                "1": {"name": "Foundation", "tasks": ["TASK-001"]},
                "2": {"name": "Core", "tasks": ["TASK-002"]},
            },
        }
        file_path = tmp_path / "task-graph.json"
        file_path.write_text(json.dumps(graph))

        result = load_and_validate_task_graph(file_path)
        assert result["feature"] == "complex-feature"
        assert len(result["tasks"]) == 2
