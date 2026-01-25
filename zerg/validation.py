"""ZERG validation functions for task graphs and configurations."""

import json
from pathlib import Path
from typing import Any

from zerg.exceptions import ValidationError
from zerg.schemas import get_schema_path


def validate_task_graph(data: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate a task graph against the schema.

    Args:
        data: Task graph dictionary to validate

    Returns:
        Tuple of (is_valid, list of error messages)
    """
    errors: list[str] = []

    # Required fields
    if "feature" not in data:
        errors.append("Missing required field: feature")

    if "tasks" not in data:
        errors.append("Missing required field: tasks")
        return False, errors

    tasks = data.get("tasks", [])
    if not isinstance(tasks, list) or len(tasks) == 0:
        errors.append("Tasks must be a non-empty list")
        return False, errors

    # Validate each task
    task_ids: set[str] = set()
    for i, task in enumerate(tasks):
        task_errors = _validate_task(task, i, task_ids)
        errors.extend(task_errors)
        if "id" in task:
            task_ids.add(task["id"])

    # Validate dependencies reference existing tasks
    for task in tasks:
        deps = task.get("dependencies", [])
        for dep in deps:
            if dep not in task_ids:
                errors.append(f"Task {task.get('id', '?')}: dependency '{dep}' not found")

    # Validate levels if present
    if "levels" in data:
        level_errors = _validate_levels(data["levels"], task_ids)
        errors.extend(level_errors)

    return len(errors) == 0, errors


def _validate_task(task: dict[str, Any], index: int, existing_ids: set[str]) -> list[str]:
    """Validate a single task definition.

    Args:
        task: Task dictionary
        index: Task index in list
        existing_ids: Set of already seen task IDs

    Returns:
        List of error messages
    """
    errors: list[str] = []
    prefix = f"Task[{index}]"

    if not isinstance(task, dict):
        errors.append(f"{prefix}: must be an object")
        return errors

    # Required fields
    if "id" not in task:
        errors.append(f"{prefix}: missing required field 'id'")
    elif task["id"] in existing_ids:
        errors.append(f"{prefix}: duplicate id '{task['id']}'")

    if "title" not in task:
        errors.append(f"{prefix}: missing required field 'title'")

    if "level" not in task:
        errors.append(f"{prefix}: missing required field 'level'")
    elif not isinstance(task.get("level"), int) or task["level"] < 1:
        errors.append(f"{prefix}: level must be a positive integer")

    # Validate verification if present
    if "verification" in task:
        if not isinstance(task["verification"], dict):
            errors.append(f"{prefix}: verification must be an object")
        elif "command" not in task["verification"]:
            errors.append(f"{prefix}: verification missing 'command'")

    # Validate files if present
    if "files" in task:
        files = task["files"]
        if not isinstance(files, dict):
            errors.append(f"{prefix}: files must be an object")
        else:
            for key in ["create", "modify", "read"]:
                if key in files and not isinstance(files[key], list):
                    errors.append(f"{prefix}: files.{key} must be a list")

    return errors


def _validate_levels(levels: dict[str, Any], task_ids: set[str]) -> list[str]:
    """Validate level definitions.

    Args:
        levels: Levels dictionary
        task_ids: Set of valid task IDs

    Returns:
        List of error messages
    """
    errors: list[str] = []

    if not isinstance(levels, dict):
        errors.append("Levels must be an object")
        return errors

    for level_num, level_def in levels.items():
        prefix = f"Level[{level_num}]"

        if not isinstance(level_def, dict):
            errors.append(f"{prefix}: must be an object")
            continue

        if "name" not in level_def:
            errors.append(f"{prefix}: missing required field 'name'")

        if "tasks" not in level_def:
            errors.append(f"{prefix}: missing required field 'tasks'")
        elif not isinstance(level_def["tasks"], list):
            errors.append(f"{prefix}: tasks must be a list")
        else:
            for task_id in level_def["tasks"]:
                if task_id not in task_ids:
                    errors.append(f"{prefix}: unknown task '{task_id}'")

    return errors


def validate_file_ownership(task_graph: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate that no two tasks modify the same file.

    Args:
        task_graph: Task graph dictionary

    Returns:
        Tuple of (is_valid, list of conflict messages)
    """
    errors: list[str] = []
    file_owners: dict[str, str] = {}  # file_path -> task_id

    tasks = task_graph.get("tasks", [])
    for task in tasks:
        task_id = task.get("id", "unknown")
        files = task.get("files", {})

        # Check create and modify files for conflicts
        for file_path in files.get("create", []) + files.get("modify", []):
            if file_path in file_owners:
                errors.append(
                    f"File conflict: '{file_path}' claimed by both "
                    f"{file_owners[file_path]} and {task_id}"
                )
            else:
                file_owners[file_path] = task_id

    return len(errors) == 0, errors


def validate_dependencies(task_graph: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate dependency graph for cycles and level consistency.

    Args:
        task_graph: Task graph dictionary

    Returns:
        Tuple of (is_valid, list of error messages)
    """
    errors: list[str] = []
    tasks = task_graph.get("tasks", [])

    # Build task info lookup
    task_info: dict[str, dict[str, Any]] = {}
    for task in tasks:
        task_id = task.get("id")
        if task_id:
            task_info[task_id] = task

    # Check level consistency (dependencies must be in lower levels)
    for task in tasks:
        task_id = task.get("id", "unknown")
        task_level = task.get("level", 0)

        for dep_id in task.get("dependencies", []):
            if dep_id in task_info:
                dep_level = task_info[dep_id].get("level", 0)
                if dep_level >= task_level:
                    errors.append(
                        f"Task {task_id} (L{task_level}) depends on "
                        f"{dep_id} (L{dep_level}) - dependency must be in lower level"
                    )

    # Check for cycles using DFS
    visited: set[str] = set()
    rec_stack: set[str] = set()

    def has_cycle(task_id: str) -> bool:
        visited.add(task_id)
        rec_stack.add(task_id)

        task = task_info.get(task_id, {})
        for dep_id in task.get("dependencies", []):
            if dep_id not in visited:
                if has_cycle(dep_id):
                    return True
            elif dep_id in rec_stack:
                errors.append(f"Dependency cycle detected involving {task_id} -> {dep_id}")
                return True

        rec_stack.remove(task_id)
        return False

    for task_id in task_info:
        if task_id not in visited:
            has_cycle(task_id)

    return len(errors) == 0, errors


def load_and_validate_task_graph(path: str | Path) -> dict[str, Any]:
    """Load and validate a task graph from file.

    Args:
        path: Path to task graph JSON file

    Returns:
        Validated task graph dictionary

    Raises:
        ValidationError: If validation fails
    """
    path = Path(path)

    if not path.exists():
        raise ValidationError(f"Task graph file not found: {path}", field="path")

    with open(path) as f:
        data = json.load(f)

    # Run all validations
    is_valid, schema_errors = validate_task_graph(data)
    if not is_valid:
        raise ValidationError(
            f"Task graph schema validation failed: {'; '.join(schema_errors)}",
            field="schema",
            details={"errors": schema_errors},
        )

    is_valid, ownership_errors = validate_file_ownership(data)
    if not is_valid:
        raise ValidationError(
            f"File ownership validation failed: {'; '.join(ownership_errors)}",
            field="file_ownership",
            details={"errors": ownership_errors},
        )

    is_valid, dep_errors = validate_dependencies(data)
    if not is_valid:
        raise ValidationError(
            f"Dependency validation failed: {'; '.join(dep_errors)}",
            field="dependencies",
            details={"errors": dep_errors},
        )

    return data
