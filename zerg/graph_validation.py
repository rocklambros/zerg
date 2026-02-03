"""Task graph property validation for ZERG rush execution."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def validate_graph_properties(
    task_graph: dict[str, Any],
) -> tuple[list[str], list[str]]:
    """Validate graph properties beyond schema/ownership/cycles.

    Args:
        task_graph: Parsed task-graph.json dict with "tasks" key containing
            list of task dicts. Each task has: id, title, level, dependencies,
            consumers (optional), integration_test (optional).

    Returns:
        (errors, warnings) -- errors are fatal, warnings are printed.
    """
    errors: list[str] = []
    warnings: list[str] = []

    tasks = task_graph.get("tasks", [])
    task_ids = {t["id"] for t in tasks}
    task_by_id: dict[str, dict[str, Any]] = {t["id"]: t for t in tasks}

    # 1. Dependency references — all must point to existing task IDs
    _check_dependency_references(tasks, task_ids, errors)

    # 2. Intra-level circular dependencies
    _check_intra_level_cycles(tasks, task_by_id, errors)

    # 3. Orphan tasks (L2+ with no dependents)
    _check_orphan_tasks(tasks, task_ids, task_by_id, warnings)

    # 4. Unreachable tasks (not reachable from L1 roots)
    _check_unreachable_tasks(tasks, task_by_id, errors)

    # 5. Consumer references — all must point to existing task IDs
    _check_consumer_references(tasks, task_ids, errors)

    # 6. Tasks with non-empty consumers must have integration_test
    _check_consumer_integration_tests(tasks, errors)

    return errors, warnings


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _check_dependency_references(
    tasks: list[dict[str, Any]],
    task_ids: set[str],
    errors: list[str],
) -> None:
    """Check that every dependency references an existing task ID."""
    for task in tasks:
        for dep_id in task.get("dependencies", []):
            if dep_id not in task_ids:
                errors.append(f"Task '{task['id']}' depends on unknown task '{dep_id}'")


def _dfs_cycle(
    node: str,
    path: list[str],
    color: dict[str, int],
    adj: dict[str, list[str]],
    level: int,
    errors: list[str],
) -> bool:
    """DFS helper for intra-level cycle detection.

    Args:
        node: Current node being visited.
        path: Current DFS path for cycle reporting.
        color: Node visitation state (0=white, 1=gray, 2=black).
        adj: Adjacency list restricted to same-level dependencies.
        level: The level number (for error messages).
        errors: Accumulator for error messages.

    Returns:
        True if a cycle was detected, False otherwise.
    """
    white, gray, black = 0, 1, 2
    color[node] = gray
    path.append(node)
    for neighbor in adj[node]:
        if color[neighbor] == gray:
            cycle_start = path.index(neighbor)
            cycle = path[cycle_start:]
            errors.append(f"Intra-level cycle at level {level}: {' -> '.join(cycle)} -> {neighbor}")
            return True
        if color[neighbor] == white and _dfs_cycle(neighbor, path, color, adj, level, errors):
            return True
    path.pop()
    color[node] = black
    return False


def _check_intra_level_cycles(
    tasks: list[dict[str, Any]],
    task_by_id: dict[str, dict[str, Any]],
    errors: list[str],
) -> None:
    """Detect cycles among tasks within the same level."""
    white = 0
    levels: dict[int, list[str]] = defaultdict(list)
    for task in tasks:
        levels[task["level"]].append(task["id"])

    for level, ids in levels.items():
        level_set = set(ids)
        # Build adjacency list restricted to same-level deps
        adj: dict[str, list[str]] = {tid: [] for tid in ids}
        for tid in ids:
            for dep_id in task_by_id[tid].get("dependencies", []):
                if dep_id in level_set:
                    adj[tid].append(dep_id)

        color: dict[str, int] = dict.fromkeys(ids, white)

        for tid in ids:
            if color[tid] == white:
                _dfs_cycle(tid, [], color, adj, level, errors)


def _check_orphan_tasks(
    tasks: list[dict[str, Any]],
    task_ids: set[str],
    task_by_id: dict[str, dict[str, Any]],
    warnings: list[str],
) -> None:
    """Warn about L2+ tasks that no other task depends on."""
    # Build set of IDs that appear as a dependency somewhere
    depended_on: set[str] = set()
    for task in tasks:
        for dep_id in task.get("dependencies", []):
            depended_on.add(dep_id)

    for task in tasks:
        if task["level"] < 2:
            continue
        tid = task["id"]
        if tid in depended_on:
            continue
        # Also skip if it has explicit consumers (leaf by design)
        consumers = task.get("consumers") or []
        if consumers:
            continue
        warnings.append(f"Task '{tid}' (level {task['level']}) has no dependents — possible orphan")


def _check_unreachable_tasks(
    tasks: list[dict[str, Any]],
    task_by_id: dict[str, dict[str, Any]],
    errors: list[str],
) -> None:
    """Error on tasks not reachable from L1 roots via dependency edges."""
    if not tasks:
        return

    all_ids = {t["id"] for t in tasks}

    # L1 roots: tasks at level 1
    roots = {t["id"] for t in tasks if t["level"] == 1}
    if not roots:
        return

    # Build reverse-dependency map: dep_id -> set of tasks that depend on it
    # i.e., "who does this task feed into?"
    feeds_into: dict[str, set[str]] = defaultdict(set)
    for task in tasks:
        for dep_id in task.get("dependencies", []):
            feeds_into[dep_id].add(task["id"])

    # BFS from roots following feeds_into edges
    visited: set[str] = set()
    queue = list(roots)
    while queue:
        current = queue.pop()
        if current in visited:
            continue
        visited.add(current)
        for downstream in feeds_into.get(current, set()):
            if downstream not in visited:
                queue.append(downstream)

    unreachable = all_ids - visited
    for tid in sorted(unreachable):
        errors.append(f"Task '{tid}' (level {task_by_id[tid]['level']}) is unreachable from L1 roots")


def _check_consumer_references(
    tasks: list[dict[str, Any]],
    task_ids: set[str],
    errors: list[str],
) -> None:
    """Check that every consumer reference points to an existing task ID."""
    for task in tasks:
        for consumer_id in task.get("consumers") or []:
            if consumer_id not in task_ids:
                errors.append(f"Task '{task['id']}' lists unknown consumer '{consumer_id}'")


def _check_consumer_integration_tests(
    tasks: list[dict[str, Any]],
    errors: list[str],
) -> None:
    """Tasks with non-empty consumers must have an integration_test field."""
    for task in tasks:
        consumers = task.get("consumers") or []
        if not consumers:
            continue
        integration_test = task.get("integration_test")
        if not integration_test:
            errors.append(f"Task '{task['id']}' has consumers {consumers} but no integration_test defined")
