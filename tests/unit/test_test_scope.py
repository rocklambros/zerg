"""Unit tests for zerg.test_scope module."""

from pathlib import Path

from zerg.test_scope import (
    _extract_imports_from_file,
    _module_path_to_dotted,
    build_pytest_path_filter,
    find_affected_tests,
    get_modified_modules,
    get_scoped_test_paths,
)


class TestGetScopedTestPaths:
    """Tests for get_scoped_test_paths function."""

    def test_empty_task_graph(self) -> None:
        """Empty task graph returns empty list."""
        result = get_scoped_test_paths({"tasks": []})
        assert result == []

    def test_no_test_files(self) -> None:
        """Tasks without test files return empty list."""
        task_graph = {
            "tasks": [
                {
                    "id": "TASK-001",
                    "files": {"create": ["src/module.py"], "modify": [], "read": []},
                }
            ]
        }
        result = get_scoped_test_paths(task_graph)
        assert result == []

    def test_extracts_test_files(self) -> None:
        """Extracts test files from files.create."""
        task_graph = {
            "tasks": [
                {
                    "id": "TASK-001",
                    "files": {
                        "create": ["tests/unit/test_foo.py", "src/foo.py"],
                        "modify": [],
                        "read": [],
                    },
                },
                {
                    "id": "TASK-002",
                    "files": {
                        "create": ["tests/integration/test_bar.py"],
                        "modify": [],
                        "read": [],
                    },
                },
            ]
        }
        result = get_scoped_test_paths(task_graph)
        assert result == ["tests/integration/test_bar.py", "tests/unit/test_foo.py"]

    def test_deduplicates_paths(self) -> None:
        """Duplicate paths are removed."""
        task_graph = {
            "tasks": [
                {
                    "id": "TASK-001",
                    "files": {"create": ["tests/test_foo.py"], "modify": [], "read": []},
                },
                {
                    "id": "TASK-002",
                    "files": {"create": ["tests/test_foo.py"], "modify": [], "read": []},
                },
            ]
        }
        result = get_scoped_test_paths(task_graph)
        assert result == ["tests/test_foo.py"]

    def test_handles_test_singular_directory(self) -> None:
        """Handles 'test/' directory (singular) as well as 'tests/'."""
        task_graph = {
            "tasks": [
                {
                    "id": "TASK-001",
                    "files": {"create": ["test/test_module.py"], "modify": [], "read": []},
                }
            ]
        }
        result = get_scoped_test_paths(task_graph)
        assert result == ["test/test_module.py"]


class TestGetModifiedModules:
    """Tests for get_modified_modules function."""

    def test_empty_task_graph(self) -> None:
        """Empty task graph returns empty list."""
        result = get_modified_modules({"tasks": []})
        assert result == []

    def test_extracts_created_modules(self) -> None:
        """Extracts Python modules from files.create."""
        task_graph = {
            "tasks": [
                {
                    "id": "TASK-001",
                    "files": {
                        "create": ["zerg/new_module.py", "config.json"],
                        "modify": [],
                        "read": [],
                    },
                }
            ]
        }
        result = get_modified_modules(task_graph)
        assert result == ["zerg/new_module.py"]

    def test_extracts_modified_modules(self) -> None:
        """Extracts Python modules from files.modify."""
        task_graph = {
            "tasks": [
                {
                    "id": "TASK-001",
                    "files": {
                        "create": [],
                        "modify": ["zerg/existing.py"],
                        "read": [],
                    },
                }
            ]
        }
        result = get_modified_modules(task_graph)
        assert result == ["zerg/existing.py"]

    def test_excludes_test_files(self) -> None:
        """Test files are excluded from module list."""
        task_graph = {
            "tasks": [
                {
                    "id": "TASK-001",
                    "files": {
                        "create": ["zerg/module.py", "tests/test_module.py"],
                        "modify": ["test/conftest.py"],
                        "read": [],
                    },
                }
            ]
        }
        result = get_modified_modules(task_graph)
        assert result == ["zerg/module.py"]


class TestModulePathToDotted:
    """Tests for _module_path_to_dotted helper."""

    def test_simple_path(self) -> None:
        """Converts simple path to dotted name."""
        assert _module_path_to_dotted("zerg/test_scope.py") == "zerg.test_scope"

    def test_nested_path(self) -> None:
        """Converts nested path to dotted name."""
        assert _module_path_to_dotted("zerg/commands/status.py") == "zerg.commands.status"

    def test_no_extension(self) -> None:
        """Handles path without .py extension."""
        assert _module_path_to_dotted("zerg/module") == "zerg.module"


class TestExtractImportsFromFile:
    """Tests for _extract_imports_from_file helper."""

    def test_import_statement(self, tmp_path: Path) -> None:
        """Extracts simple import statements."""
        test_file = tmp_path / "test.py"
        test_file.write_text("import os\nimport json\n")

        imports = _extract_imports_from_file(test_file)

        assert "os" in imports
        assert "json" in imports

    def test_from_import_statement(self, tmp_path: Path) -> None:
        """Extracts from...import statements."""
        test_file = tmp_path / "test.py"
        test_file.write_text("from pathlib import Path\nfrom zerg.parser import TaskParser\n")

        imports = _extract_imports_from_file(test_file)

        assert "pathlib" in imports
        assert "zerg.parser" in imports

    def test_handles_syntax_error(self, tmp_path: Path) -> None:
        """Returns empty set for files with syntax errors."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def broken(\n")

        imports = _extract_imports_from_file(test_file)

        assert imports == set()

    def test_handles_missing_file(self, tmp_path: Path) -> None:
        """Returns empty set for missing files."""
        missing_file = tmp_path / "nonexistent.py"

        imports = _extract_imports_from_file(missing_file)

        assert imports == set()


class TestFindAffectedTests:
    """Tests for find_affected_tests function."""

    def test_empty_modules(self, tmp_path: Path) -> None:
        """No modified modules returns empty list."""
        result = find_affected_tests([], tmp_path)
        assert result == []

    def test_no_tests_dir(self, tmp_path: Path) -> None:
        """Non-existent tests directory returns empty list."""
        nonexistent = tmp_path / "nonexistent_tests"
        result = find_affected_tests(["zerg/module.py"], nonexistent)
        assert result == []

    def test_finds_importing_tests(self, tmp_path: Path) -> None:
        """Finds tests that import modified modules."""
        # Create test directory structure
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()

        # Create a test file that imports zerg.test_scope
        test_file = tests_dir / "test_example.py"
        test_file.write_text("from zerg.test_scope import get_scoped_test_paths\n")

        result = find_affected_tests(["zerg/test_scope.py"], tests_dir)

        assert len(result) == 1
        assert "test_example.py" in result[0]

    def test_ignores_unrelated_tests(self, tmp_path: Path) -> None:
        """Tests that don't import modified modules are not included."""
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()

        # Create a test file that imports something else
        test_file = tests_dir / "test_other.py"
        test_file.write_text("import json\n")

        result = find_affected_tests(["zerg/test_scope.py"], tests_dir)

        assert result == []

    def test_skips_private_files(self, tmp_path: Path) -> None:
        """Files starting with underscore are skipped."""
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()

        private_file = tests_dir / "_helper.py"
        private_file.write_text("from zerg.test_scope import get_scoped_test_paths\n")

        result = find_affected_tests(["zerg/test_scope.py"], tests_dir)

        assert result == []


class TestBuildPytestPathFilter:
    """Tests for build_pytest_path_filter function."""

    def test_empty_task_graph(self, tmp_path: Path) -> None:
        """Empty task graph returns empty string."""
        result = build_pytest_path_filter({"tasks": []}, tmp_path)
        assert result == ""

    def test_combines_new_and_affected(self, tmp_path: Path) -> None:
        """Combines new test files with affected tests."""
        # Create test directory with an existing test
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        existing_test = tests_dir / "test_existing.py"
        existing_test.write_text("from zerg.module import something\n")

        task_graph = {
            "tasks": [
                {
                    "id": "TASK-001",
                    "files": {
                        "create": ["zerg/module.py", "tests/test_new.py"],
                        "modify": [],
                        "read": [],
                    },
                }
            ]
        }

        result = build_pytest_path_filter(task_graph, tests_dir)

        assert "tests/test_new.py" in result

    def test_deduplicates_results(self, tmp_path: Path) -> None:
        """Duplicate paths are removed from result."""
        task_graph = {
            "tasks": [
                {
                    "id": "TASK-001",
                    "files": {
                        "create": ["tests/test_foo.py"],
                        "modify": [],
                        "read": [],
                    },
                },
                {
                    "id": "TASK-002",
                    "files": {
                        "create": ["tests/test_foo.py"],
                        "modify": [],
                        "read": [],
                    },
                },
            ]
        }

        result = build_pytest_path_filter(task_graph, tmp_path)

        assert result.count("tests/test_foo.py") == 1
