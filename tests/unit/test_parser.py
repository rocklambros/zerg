"""Tests for ZERG task parser module."""

import json
from pathlib import Path

import pytest

from zerg.exceptions import TaskDependencyError, ValidationError
from zerg.parser import TaskParser


class TestTaskParser:
    """Tests for TaskParser class."""

    def test_init(self) -> None:
        """Test parser initialization."""
        parser = TaskParser()
        assert parser._graph is None
        assert len(parser._tasks) == 0

    def test_parse_file_not_found(self, tmp_path: Path) -> None:
        """Test parsing non-existent file raises error."""
        parser = TaskParser()

        with pytest.raises(ValidationError) as exc_info:
            parser.parse(tmp_path / "nonexistent.json")

        assert "not found" in str(exc_info.value).lower()

    def test_parse_valid_file(self, tmp_path: Path) -> None:
        """Test parsing a valid task graph file."""
        graph = {
            "feature": "test-feature",
            "tasks": [
                {"id": "TASK-001", "title": "Test", "level": 1, "dependencies": []},
            ],
        }

        file_path = tmp_path / "task-graph.json"
        with open(file_path, "w") as f:
            json.dump(graph, f)

        parser = TaskParser()
        result = parser.parse(file_path)

        assert result["feature"] == "test-feature"
        assert len(parser._tasks) == 1

    def test_parse_dict(self) -> None:
        """Test parsing from dictionary."""
        graph = {
            "feature": "test-feature",
            "tasks": [
                {"id": "TASK-001", "title": "Test", "level": 1, "dependencies": []},
            ],
        }

        parser = TaskParser()
        result = parser.parse_dict(graph)

        assert result["feature"] == "test-feature"
        assert parser.get_task("TASK-001") is not None


class TestTaskAccess:
    """Tests for task access methods."""

    @pytest.fixture
    def loaded_parser(self) -> TaskParser:
        """Create a parser with loaded tasks."""
        graph = {
            "feature": "test-feature",
            "tasks": [
                {"id": "TASK-001", "title": "First", "level": 1, "dependencies": []},
                {"id": "TASK-002", "title": "Second", "level": 1, "dependencies": []},
                {"id": "TASK-003", "title": "Third", "level": 2, "dependencies": ["TASK-001", "TASK-002"]},
            ],
        }

        parser = TaskParser()
        parser.parse_dict(graph)
        return parser

    def test_get_task(self, loaded_parser: TaskParser) -> None:
        """Test getting a task by ID."""
        task = loaded_parser.get_task("TASK-001")

        assert task is not None
        assert task["id"] == "TASK-001"
        assert task["title"] == "First"

    def test_get_task_not_found(self, loaded_parser: TaskParser) -> None:
        """Test getting non-existent task."""
        task = loaded_parser.get_task("NONEXISTENT")
        assert task is None

    def test_get_all_tasks(self, loaded_parser: TaskParser) -> None:
        """Test getting all tasks."""
        tasks = loaded_parser.get_all_tasks()

        assert len(tasks) == 3
        task_ids = {t["id"] for t in tasks}
        assert task_ids == {"TASK-001", "TASK-002", "TASK-003"}

    def test_get_tasks_for_level(self, loaded_parser: TaskParser) -> None:
        """Test getting tasks for a specific level."""
        level_1 = loaded_parser.get_tasks_for_level(1)
        level_2 = loaded_parser.get_tasks_for_level(2)

        assert len(level_1) == 2
        assert len(level_2) == 1
        assert all(t["level"] == 1 for t in level_1)
        assert all(t["level"] == 2 for t in level_2)

    def test_get_tasks_for_level_empty(self, loaded_parser: TaskParser) -> None:
        """Test getting tasks for level with no tasks."""
        level_99 = loaded_parser.get_tasks_for_level(99)
        assert level_99 == []


class TestDependencies:
    """Tests for dependency management."""

    @pytest.fixture
    def parser_with_deps(self) -> TaskParser:
        """Create parser with dependency structure."""
        graph = {
            "feature": "test",
            "tasks": [
                {"id": "TASK-A1", "title": "Task A", "level": 1, "dependencies": []},
                {"id": "TASK-B1", "title": "Task B", "level": 1, "dependencies": []},
                {"id": "TASK-C2", "title": "Task C", "level": 2, "dependencies": ["TASK-A1", "TASK-B1"]},
                {"id": "TASK-D3", "title": "Task D", "level": 3, "dependencies": ["TASK-C2"]},
            ],
        }

        parser = TaskParser()
        parser.parse_dict(graph)
        return parser

    def test_get_dependencies(self, parser_with_deps: TaskParser) -> None:
        """Test getting dependencies for a task."""
        deps_c = parser_with_deps.get_dependencies("TASK-C2")
        deps_a = parser_with_deps.get_dependencies("TASK-A1")

        assert set(deps_c) == {"TASK-A1", "TASK-B1"}
        assert deps_a == []

    def test_get_dependents(self, parser_with_deps: TaskParser) -> None:
        """Test getting dependents of a task."""
        dependents_a = parser_with_deps.get_dependents("TASK-A1")
        dependents_c = parser_with_deps.get_dependents("TASK-C2")

        assert "TASK-C2" in dependents_a
        assert "TASK-D3" in dependents_c

    def test_are_dependencies_complete(self, parser_with_deps: TaskParser) -> None:
        """Test checking if dependencies are complete."""
        completed = {"TASK-A1", "TASK-B1"}

        assert parser_with_deps.are_dependencies_complete("TASK-C2", completed) is True
        assert parser_with_deps.are_dependencies_complete("TASK-D3", completed) is False
        assert parser_with_deps.are_dependencies_complete("TASK-A1", set()) is True

    def test_get_ready_tasks(self, parser_with_deps: TaskParser) -> None:
        """Test getting tasks ready to execute."""
        # Initially only A and B are ready
        ready = parser_with_deps.get_ready_tasks(set(), set())
        ready_ids = {t["id"] for t in ready}
        assert ready_ids == {"TASK-A1", "TASK-B1"}

        # After A and B complete, C is ready
        ready = parser_with_deps.get_ready_tasks({"TASK-A1", "TASK-B1"}, set())
        ready_ids = {t["id"] for t in ready}
        assert ready_ids == {"TASK-C2"}

        # Tasks in progress are excluded
        ready = parser_with_deps.get_ready_tasks({"TASK-A1", "TASK-B1"}, {"TASK-C2"})
        assert len(ready) == 0


class TestTopologicalSort:
    """Tests for topological sorting."""

    def test_topological_sort_simple(self) -> None:
        """Test simple topological sort."""
        graph = {
            "feature": "test",
            "tasks": [
                {"id": "TASK-A1", "title": "Task A", "level": 1, "dependencies": []},
                {"id": "TASK-B2", "title": "Task B", "level": 2, "dependencies": ["TASK-A1"]},
                {"id": "TASK-C3", "title": "Task C", "level": 3, "dependencies": ["TASK-B2"]},
            ],
        }

        parser = TaskParser()
        parser.parse_dict(graph)

        order = parser.topological_sort()

        # A must come before B, B before C
        assert order.index("TASK-A1") < order.index("TASK-B2")
        assert order.index("TASK-B2") < order.index("TASK-C3")

    def test_topological_sort_parallel(self) -> None:
        """Test topological sort with parallel tasks."""
        graph = {
            "feature": "test",
            "tasks": [
                {"id": "TASK-A1", "title": "Task A", "level": 1, "dependencies": []},
                {"id": "TASK-B1", "title": "Task B", "level": 1, "dependencies": []},
                {"id": "TASK-C2", "title": "Task C", "level": 2, "dependencies": ["TASK-A1", "TASK-B1"]},
            ],
        }

        parser = TaskParser()
        parser.parse_dict(graph)

        order = parser.topological_sort()

        # A and B before C
        assert order.index("TASK-A1") < order.index("TASK-C2")
        assert order.index("TASK-B1") < order.index("TASK-C2")

    def test_topological_sort_cycle_detection(self) -> None:
        """Test cycle detection in topological sort."""
        # Note: This test depends on validation allowing the cycle to be created
        # If validation prevents it, this will need adjustment
        parser = TaskParser()
        parser._tasks = {
            "A": {"id": "A", "level": 1, "dependencies": ["B"]},
            "B": {"id": "B", "level": 1, "dependencies": ["A"]},
        }
        parser._dependencies = {"A": ["B"], "B": ["A"]}
        parser._dependents = {"A": ["B"], "B": ["A"]}

        with pytest.raises(TaskDependencyError):
            parser.topological_sort()


class TestCriticalPath:
    """Tests for critical path calculation."""

    def test_get_critical_path_provided(self) -> None:
        """Test getting critical path from task graph."""
        graph = {
            "feature": "test",
            "critical_path": ["TASK-A1", "TASK-C2", "TASK-D3"],
            "tasks": [
                {"id": "TASK-A1", "title": "A", "level": 1, "dependencies": [], "estimate_minutes": 30},
                {"id": "TASK-B1", "title": "B", "level": 1, "dependencies": [], "estimate_minutes": 10},
                {
                    "id": "TASK-C2",
                    "title": "C",
                    "level": 2,
                    "dependencies": ["TASK-A1", "TASK-B1"],
                    "estimate_minutes": 20,
                },
                {"id": "TASK-D3", "title": "D", "level": 3, "dependencies": ["TASK-C2"], "estimate_minutes": 15},
            ],
        }

        parser = TaskParser()
        parser.parse_dict(graph)

        path = parser.get_critical_path()
        assert path == ["TASK-A1", "TASK-C2", "TASK-D3"]

    def test_get_critical_path_calculated(self) -> None:
        """Test calculating critical path."""
        graph = {
            "feature": "test",
            "tasks": [
                {"id": "TASK-A1", "title": "A", "level": 1, "dependencies": [], "estimate_minutes": 30},
                {"id": "TASK-B1", "title": "B", "level": 1, "dependencies": [], "estimate_minutes": 10},
                {
                    "id": "TASK-C2",
                    "title": "C",
                    "level": 2,
                    "dependencies": ["TASK-A1", "TASK-B1"],
                    "estimate_minutes": 20,
                },
            ],
        }

        parser = TaskParser()
        parser.parse_dict(graph)

        path = parser.get_critical_path()

        # Longest path: A (30) -> C (20) = 50
        # vs B (10) -> C (20) = 30
        assert "TASK-A1" in path
        assert "TASK-C2" in path


class TestFileOperations:
    """Tests for file-related operations."""

    def test_get_files_for_task(self) -> None:
        """Test getting file specifications."""
        graph = {
            "feature": "test",
            "tasks": [
                {
                    "id": "TASK-001",
                    "title": "Test Task",
                    "level": 1,
                    "dependencies": [],
                    "files": {
                        "create": ["src/new.py"],
                        "modify": ["src/existing.py"],
                        "read": ["src/config.py"],
                    },
                },
            ],
        }

        parser = TaskParser()
        parser.parse_dict(graph)

        files = parser.get_files_for_task("TASK-001")

        assert files["create"] == ["src/new.py"]
        assert files["modify"] == ["src/existing.py"]
        assert files["read"] == ["src/config.py"]

    def test_get_files_for_task_missing(self) -> None:
        """Test getting files for task without file spec."""
        graph = {
            "feature": "test",
            "tasks": [{"id": "TASK-001", "title": "Test", "level": 1, "dependencies": []}],
        }

        parser = TaskParser()
        parser.parse_dict(graph)

        files = parser.get_files_for_task("TASK-001")

        assert files["create"] == []
        assert files["modify"] == []
        assert files["read"] == []

    def test_get_files_for_nonexistent_task(self) -> None:
        """Test getting files for non-existent task."""
        graph = {
            "feature": "test",
            "tasks": [{"id": "TASK-001", "title": "Test", "level": 1, "dependencies": []}],
        }
        parser = TaskParser()
        parser.parse_dict(graph)

        files = parser.get_files_for_task("NONEXISTENT")

        assert files == {"create": [], "modify": [], "read": []}


class TestVerification:
    """Tests for verification methods."""

    def test_get_verification(self) -> None:
        """Test getting verification spec."""
        graph = {
            "feature": "test",
            "tasks": [
                {
                    "id": "TASK-001",
                    "title": "Test Task",
                    "level": 1,
                    "dependencies": [],
                    "verification": {
                        "command": "pytest tests/",
                        "timeout_seconds": 60,
                    },
                },
            ],
        }

        parser = TaskParser()
        parser.parse_dict(graph)

        verification = parser.get_verification("TASK-001")

        assert verification is not None
        assert verification["command"] == "pytest tests/"
        assert verification["timeout_seconds"] == 60

    def test_get_verification_none(self) -> None:
        """Test getting verification when not defined."""
        graph = {
            "feature": "test",
            "tasks": [{"id": "TASK-001", "title": "Test", "level": 1, "dependencies": []}],
        }

        parser = TaskParser()
        parser.parse_dict(graph)

        verification = parser.get_verification("TASK-001")
        assert verification is None


class TestProperties:
    """Tests for parser properties."""

    def test_feature_name(self) -> None:
        """Test feature_name property."""
        graph = {
            "feature": "my-feature",
            "tasks": [{"id": "TASK-001", "title": "Test", "level": 1, "dependencies": []}],
        }

        parser = TaskParser()
        parser.parse_dict(graph)

        assert parser.feature_name == "my-feature"

    def test_feature_name_default(self) -> None:
        """Test feature_name with no graph."""
        parser = TaskParser()
        assert parser.feature_name == "unknown"

    def test_total_tasks(self) -> None:
        """Test total_tasks property."""
        graph = {
            "feature": "test",
            "tasks": [
                {"id": "TASK-A1", "title": "A", "level": 1, "dependencies": []},
                {"id": "TASK-B1", "title": "B", "level": 1, "dependencies": []},
                {"id": "TASK-C2", "title": "C", "level": 2, "dependencies": ["TASK-A1", "TASK-B1"]},
            ],
        }

        parser = TaskParser()
        parser.parse_dict(graph)

        assert parser.total_tasks == 3

    def test_levels(self) -> None:
        """Test levels property."""
        graph = {
            "feature": "test",
            "tasks": [
                {"id": "TASK-A1", "title": "A", "level": 1, "dependencies": []},
                {"id": "TASK-B3", "title": "B", "level": 3, "dependencies": ["TASK-C2"]},
                {"id": "TASK-C2", "title": "C", "level": 2, "dependencies": ["TASK-A1"]},
            ],
        }

        parser = TaskParser()
        parser.parse_dict(graph)

        assert parser.levels == [1, 2, 3]
