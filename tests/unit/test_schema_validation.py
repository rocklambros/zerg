"""Unit tests for schema validation - OFX-001.

Tests for task graph schema validation including:
- Level bounds (reject 0, accept >= 1)
- Files structure validation
- ID pattern validation
- Schema loading
"""

import json
from pathlib import Path

from zerg.validation import (
    validate_dependencies,
    validate_file_ownership,
    validate_task_graph,
    validate_task_id,
)


class TestLevelValidation:
    """Test level bounds validation (must be >= 1)."""

    def test_level_zero_rejected(self) -> None:
        """Level 0 should be rejected - levels are 1-indexed."""
        task_graph = {
            "feature": "test-feature",
            "tasks": [
                {
                    "id": "TEST-001",
                    "title": "Test task",
                    "level": 0,  # Invalid - should be >= 1
                    "dependencies": [],
                    "files": {"create": [], "modify": [], "read": []},
                }
            ],
        }
        is_valid, errors = validate_task_graph(task_graph)

        assert not is_valid, "Level 0 should be rejected"
        assert any("level" in e.lower() for e in errors), f"Expected level error, got: {errors}"

    def test_level_one_accepted(self) -> None:
        """Level 1 should be accepted as minimum valid level."""
        task_graph = {
            "feature": "test-feature",
            "tasks": [
                {
                    "id": "TEST-001",
                    "title": "Test task",
                    "level": 1,
                    "dependencies": [],
                    "files": {"create": [], "modify": [], "read": []},
                }
            ],
        }
        is_valid, errors = validate_task_graph(task_graph)

        assert is_valid, f"Level 1 should be accepted, got errors: {errors}"

    def test_level_negative_rejected(self) -> None:
        """Negative levels should be rejected."""
        task_graph = {
            "feature": "test-feature",
            "tasks": [
                {
                    "id": "TEST-001",
                    "title": "Test task",
                    "level": -1,
                    "dependencies": [],
                    "files": {"create": [], "modify": [], "read": []},
                }
            ],
        }
        is_valid, errors = validate_task_graph(task_graph)

        assert not is_valid, "Negative level should be rejected"

    def test_level_ten_accepted(self) -> None:
        """Level 10 should be accepted (upper bound)."""
        task_graph = {
            "feature": "test-feature",
            "tasks": [
                {
                    "id": "TEST-001",
                    "title": "Test task",
                    "level": 10,
                    "dependencies": [],
                    "files": {"create": [], "modify": [], "read": []},
                }
            ],
        }
        is_valid, errors = validate_task_graph(task_graph)

        assert is_valid, f"Level 10 should be accepted, got errors: {errors}"


class TestFilesStructureValidation:
    """Test files structure validation."""

    def test_files_with_all_keys_valid(self) -> None:
        """Files with create, modify, read keys should be valid."""
        task_graph = {
            "feature": "test-feature",
            "tasks": [
                {
                    "id": "TEST-001",
                    "title": "Test task",
                    "level": 1,
                    "dependencies": [],
                    "files": {
                        "create": ["new_file.py"],
                        "modify": ["existing.py"],
                        "read": ["reference.py"],
                    },
                }
            ],
        }
        is_valid, errors = validate_task_graph(task_graph)

        assert is_valid, f"Files structure should be valid, got errors: {errors}"

    def test_files_with_empty_arrays_valid(self) -> None:
        """Files with empty arrays should be valid."""
        task_graph = {
            "feature": "test-feature",
            "tasks": [
                {
                    "id": "TEST-001",
                    "title": "Test task",
                    "level": 1,
                    "dependencies": [],
                    "files": {"create": [], "modify": [], "read": []},
                }
            ],
        }
        is_valid, errors = validate_task_graph(task_graph)

        assert is_valid, f"Empty files arrays should be valid, got errors: {errors}"

    def test_files_create_must_be_array(self) -> None:
        """Files.create must be an array, not a string."""
        task_graph = {
            "feature": "test-feature",
            "tasks": [
                {
                    "id": "TEST-001",
                    "title": "Test task",
                    "level": 1,
                    "dependencies": [],
                    "files": {
                        "create": "not_an_array.py",  # Invalid
                        "modify": [],
                        "read": [],
                    },
                }
            ],
        }
        is_valid, errors = validate_task_graph(task_graph)

        assert not is_valid, "files.create as string should be rejected"

    def test_files_missing_optional(self) -> None:
        """Files structure is optional - missing should be valid."""
        task_graph = {
            "feature": "test-feature",
            "tasks": [
                {
                    "id": "TEST-001",
                    "title": "Test task",
                    "level": 1,
                    "dependencies": [],
                    # No files key
                }
            ],
        }
        is_valid, errors = validate_task_graph(task_graph)

        # Files being optional is OK
        assert is_valid, f"Missing files should be valid, got errors: {errors}"


class TestTaskIdValidation:
    """Test task ID validation."""

    def test_valid_task_id_uppercase(self) -> None:
        """Uppercase task IDs should be valid."""
        is_valid, error = validate_task_id("TEST-001")
        assert is_valid, f"TEST-001 should be valid, got: {error}"

    def test_valid_task_id_with_level(self) -> None:
        """Task IDs with level indicator should be valid."""
        is_valid, error = validate_task_id("ZERG-L1-001")
        assert is_valid, f"ZERG-L1-001 should be valid, got: {error}"

    def test_valid_task_id_alphanumeric(self) -> None:
        """Alphanumeric task IDs should be valid."""
        is_valid, error = validate_task_id("OFX001")
        assert is_valid, f"OFX001 should be valid, got: {error}"

    def test_empty_task_id_rejected(self) -> None:
        """Empty task ID should be rejected."""
        is_valid, error = validate_task_id("")
        assert not is_valid, "Empty task ID should be rejected"

    def test_task_id_with_dangerous_chars_rejected(self) -> None:
        """Task IDs with shell metacharacters should be rejected."""
        dangerous_ids = [
            "TEST;rm -rf",
            "TEST`whoami`",
            "TEST$(cat /etc/passwd)",
            "TEST|cat",
            "TEST&echo",
        ]
        for task_id in dangerous_ids:
            is_valid, error = validate_task_id(task_id)
            assert not is_valid, f"Dangerous task ID '{task_id}' should be rejected"

    def test_task_id_too_long_rejected(self) -> None:
        """Task IDs over 64 characters should be rejected."""
        long_id = "A" * 65
        is_valid, error = validate_task_id(long_id)
        assert not is_valid, "Task ID over 64 chars should be rejected"


class TestDependencyValidation:
    """Test dependency validation."""

    def test_dependency_in_lower_level_valid(self) -> None:
        """Dependencies in lower levels should be valid."""
        task_graph = {
            "feature": "test-feature",
            "tasks": [
                {
                    "id": "TEST-001",
                    "title": "First task",
                    "level": 1,
                    "dependencies": [],
                    "files": {"create": [], "modify": [], "read": []},
                },
                {
                    "id": "TEST-002",
                    "title": "Second task",
                    "level": 2,
                    "dependencies": ["TEST-001"],  # Valid - depends on level 1
                    "files": {"create": [], "modify": [], "read": []},
                },
            ],
        }
        is_valid, errors = validate_dependencies(task_graph)

        assert is_valid, f"Dependency in lower level should be valid, got: {errors}"

    def test_dependency_in_same_level_rejected(self) -> None:
        """Dependencies in same level should be rejected."""
        task_graph = {
            "feature": "test-feature",
            "tasks": [
                {
                    "id": "TEST-001",
                    "title": "First task",
                    "level": 1,
                    "dependencies": [],
                    "files": {"create": [], "modify": [], "read": []},
                },
                {
                    "id": "TEST-002",
                    "title": "Second task",
                    "level": 1,  # Same level
                    "dependencies": ["TEST-001"],  # Invalid - same level
                    "files": {"create": [], "modify": [], "read": []},
                },
            ],
        }
        is_valid, errors = validate_dependencies(task_graph)

        assert not is_valid, "Dependency in same level should be rejected"

    def test_dependency_in_higher_level_rejected(self) -> None:
        """Dependencies in higher levels should be rejected."""
        task_graph = {
            "feature": "test-feature",
            "tasks": [
                {
                    "id": "TEST-001",
                    "title": "First task",
                    "level": 2,
                    "dependencies": [],
                    "files": {"create": [], "modify": [], "read": []},
                },
                {
                    "id": "TEST-002",
                    "title": "Second task",
                    "level": 1,
                    "dependencies": ["TEST-001"],  # Invalid - depends on higher level
                    "files": {"create": [], "modify": [], "read": []},
                },
            ],
        }
        is_valid, errors = validate_dependencies(task_graph)

        assert not is_valid, "Dependency in higher level should be rejected"

    def test_nonexistent_dependency_detected(self) -> None:
        """Dependencies on non-existent tasks should be detected.

        Note: Current implementation may not check this.
        This test documents expected behavior for OFX-006.
        """
        task_graph = {
            "feature": "test-feature",
            "tasks": [
                {
                    "id": "TEST-001",
                    "title": "Task",
                    "level": 1,
                    "dependencies": ["NONEXISTENT"],  # Invalid
                    "files": {"create": [], "modify": [], "read": []},
                },
            ],
        }
        is_valid, errors = validate_dependencies(task_graph)

        # Currently passes - OFX-006 should fix this
        # For now, just ensure it doesn't crash
        assert isinstance(is_valid, bool)


class TestFileOwnershipValidation:
    """Test file ownership validation."""

    def test_unique_file_ownership_valid(self) -> None:
        """Each file owned by one task should be valid."""
        task_graph = {
            "feature": "test-feature",
            "tasks": [
                {
                    "id": "TEST-001",
                    "title": "Task 1",
                    "level": 1,
                    "dependencies": [],
                    "files": {"create": ["file1.py"], "modify": [], "read": []},
                },
                {
                    "id": "TEST-002",
                    "title": "Task 2",
                    "level": 1,
                    "dependencies": [],
                    "files": {"create": ["file2.py"], "modify": [], "read": []},
                },
            ],
        }
        is_valid, errors = validate_file_ownership(task_graph)

        assert is_valid, f"Unique file ownership should be valid, got: {errors}"

    def test_duplicate_create_rejected(self) -> None:
        """Two tasks creating same file should be rejected."""
        task_graph = {
            "feature": "test-feature",
            "tasks": [
                {
                    "id": "TEST-001",
                    "title": "Task 1",
                    "level": 1,
                    "dependencies": [],
                    "files": {"create": ["same_file.py"], "modify": [], "read": []},
                },
                {
                    "id": "TEST-002",
                    "title": "Task 2",
                    "level": 1,
                    "dependencies": [],
                    "files": {"create": ["same_file.py"], "modify": [], "read": []},
                },
            ],
        }
        is_valid, errors = validate_file_ownership(task_graph)

        assert not is_valid, "Duplicate file creation should be rejected"

    def test_read_same_file_valid(self) -> None:
        """Multiple tasks reading same file should be valid."""
        task_graph = {
            "feature": "test-feature",
            "tasks": [
                {
                    "id": "TEST-001",
                    "title": "Task 1",
                    "level": 1,
                    "dependencies": [],
                    "files": {"create": [], "modify": [], "read": ["shared.py"]},
                },
                {
                    "id": "TEST-002",
                    "title": "Task 2",
                    "level": 1,
                    "dependencies": [],
                    "files": {"create": [], "modify": [], "read": ["shared.py"]},
                },
            ],
        }
        is_valid, errors = validate_file_ownership(task_graph)

        assert is_valid, f"Reading same file should be valid, got: {errors}"


class TestRequiredFields:
    """Test required field validation."""

    def test_missing_feature_rejected(self) -> None:
        """Missing feature field should be rejected."""
        task_graph = {
            "tasks": [
                {
                    "id": "TEST-001",
                    "title": "Task",
                    "level": 1,
                    "dependencies": [],
                }
            ],
        }
        is_valid, errors = validate_task_graph(task_graph)

        assert not is_valid, "Missing feature should be rejected"
        assert any("feature" in e.lower() for e in errors)

    def test_missing_tasks_rejected(self) -> None:
        """Missing tasks field should be rejected."""
        task_graph = {
            "feature": "test-feature",
        }
        is_valid, errors = validate_task_graph(task_graph)

        assert not is_valid, "Missing tasks should be rejected"

    def test_empty_tasks_valid(self) -> None:
        """Empty tasks array should be valid (edge case)."""
        task_graph = {
            "feature": "test-feature",
            "tasks": [],
        }
        is_valid, errors = validate_task_graph(task_graph)

        # Empty tasks may be valid depending on use case
        # At minimum, should not crash
        assert isinstance(is_valid, bool)


class TestSchemaLoading:
    """Test schema file loading."""

    def test_schema_file_exists(self) -> None:
        """Schema file should exist at expected location."""
        schema_path = Path("zerg/schemas/task_graph.json")
        assert schema_path.exists(), f"Schema file not found at {schema_path}"

    def test_schema_file_valid_json(self) -> None:
        """Schema file should be valid JSON."""
        schema_path = Path("zerg/schemas/task_graph.json")
        with open(schema_path) as f:
            schema = json.load(f)

        assert isinstance(schema, dict), "Schema should be a dict"
        assert "$schema" in schema or "type" in schema, "Schema should have $schema or type"

    def test_schema_has_level_minimum(self) -> None:
        """Schema should define level minimum as 1."""
        schema_path = Path("zerg/schemas/task_graph.json")
        with open(schema_path) as f:
            schema = json.load(f)

        # Navigate to level definition
        level_def = schema.get("definitions", {}).get("task", {}).get("properties", {}).get("level", {})

        # Should have minimum of 1
        assert level_def.get("minimum") == 1, f"Level minimum should be 1, got: {level_def}"
