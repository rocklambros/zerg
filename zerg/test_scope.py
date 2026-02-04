"""Test scope detection for wiring verification.

Provides functions to detect which tests should run for a given task graph,
including new test files created by tasks and existing tests affected by
modified modules.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zerg.types import Task, TaskGraph


def get_scoped_test_paths(task_graph: TaskGraph) -> list[str]:
    """Extract test file paths from task graph files.create lists.

    Scans all tasks in the graph and collects test files (matching tests/**/*.py)
    from their files.create entries.

    Args:
        task_graph: Parsed task graph dictionary.

    Returns:
        List of test file paths created by tasks in the graph.
    """
    test_paths: list[str] = []
    test_pattern = re.compile(r"^tests?/.*\.py$")

    tasks: list[Task] = task_graph.get("tasks", [])
    for task in tasks:
        files = task.get("files", {})
        created_files: list[str] = files.get("create", [])

        for file_path in created_files:
            if test_pattern.match(file_path):
                test_paths.append(file_path)

    return sorted(set(test_paths))


def get_modified_modules(task_graph: TaskGraph) -> list[str]:
    """Extract non-test module paths from task graph files.create and files.modify.

    Args:
        task_graph: Parsed task graph dictionary.

    Returns:
        List of module paths (excluding test files) created or modified by tasks.
    """
    module_paths: list[str] = []
    test_pattern = re.compile(r"^tests?/")

    tasks: list[Task] = task_graph.get("tasks", [])
    for task in tasks:
        files = task.get("files", {})

        for file_path in files.get("create", []):
            if file_path.endswith(".py") and not test_pattern.match(file_path):
                module_paths.append(file_path)

        for file_path in files.get("modify", []):
            if file_path.endswith(".py") and not test_pattern.match(file_path):
                module_paths.append(file_path)

    return sorted(set(module_paths))


def _extract_imports_from_file(file_path: Path) -> set[str]:
    """Extract module names imported by a Python file.

    Uses AST parsing to find import statements.

    Args:
        file_path: Path to Python file.

    Returns:
        Set of imported module names (dotted paths).
    """
    imports: set[str] = set()

    try:
        content = file_path.read_text()
        tree = ast.parse(content)
    except (OSError, SyntaxError):
        return imports

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)
                # Also add full paths for specific imports
                for alias in node.names:
                    imports.add(f"{node.module}.{alias.name}")

    return imports


def _module_path_to_dotted(file_path: str) -> str:
    """Convert a file path to a dotted module name.

    Args:
        file_path: File path like "zerg/test_scope.py"

    Returns:
        Dotted module name like "zerg.test_scope"
    """
    # Remove .py extension
    if file_path.endswith(".py"):
        file_path = file_path[:-3]

    # Convert path separators to dots
    return file_path.replace("/", ".").replace("\\", ".")


def find_affected_tests(
    modified_modules: list[str],
    tests_dir: Path,
) -> list[str]:
    """Find test files that import any of the modified modules.

    Scans test files and checks if they import any of the given modules.

    Args:
        modified_modules: List of module file paths (e.g., ["zerg/test_scope.py"])
        tests_dir: Path to the tests directory.

    Returns:
        List of test file paths that import the modified modules.
    """
    if not tests_dir.exists():
        return []

    # Convert file paths to dotted module names for matching
    module_names: set[str] = set()
    for mod_path in modified_modules:
        dotted = _module_path_to_dotted(mod_path)
        module_names.add(dotted)
        # Also add partial matches (e.g., "zerg" matches "zerg.test_scope")
        parts = dotted.split(".")
        for i in range(len(parts)):
            module_names.add(".".join(parts[: i + 1]))

    affected_tests: list[str] = []

    for test_file in tests_dir.rglob("*.py"):
        if test_file.name.startswith("_"):
            continue

        imports = _extract_imports_from_file(test_file)

        # Check if any import matches our modified modules
        for imp in imports:
            if imp in module_names or any(imp.startswith(f"{m}.") for m in module_names):
                # Return relative path from project root
                try:
                    rel_path = test_file.relative_to(tests_dir.parent)
                    affected_tests.append(str(rel_path))
                except ValueError:
                    affected_tests.append(str(test_file))
                break

    return sorted(set(affected_tests))


def build_pytest_path_filter(
    task_graph: TaskGraph,
    tests_dir: Path | None = None,
) -> str:
    """Build a pytest path filter string for scoped test execution.

    Combines new test files from the task graph with existing tests
    affected by modified modules.

    Args:
        task_graph: Parsed task graph dictionary.
        tests_dir: Path to tests directory. Defaults to "tests/" in cwd.

    Returns:
        Space-separated string of test paths for pytest, or empty string
        if no tests to run.
    """
    if tests_dir is None:
        tests_dir = Path("tests")

    # Get new test files from task graph
    new_tests = get_scoped_test_paths(task_graph)

    # Get modules being created/modified
    modified = get_modified_modules(task_graph)

    # Find existing tests affected by the modifications
    affected = find_affected_tests(modified, tests_dir)

    # Combine and deduplicate
    all_tests = sorted(set(new_tests + affected))

    return " ".join(all_tests)
