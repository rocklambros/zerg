"""Generate markdown backlog files from ZERG task graph data."""

from __future__ import annotations

import math
import re
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any


def _get_owned_files(task: dict[str, Any]) -> str:
    """Extract owned files (create + modify) from a task's file spec."""
    files_spec = task.get("files", {})
    owned = []
    for key in ("create", "modify"):
        owned.extend(files_spec.get(key, []))
    if not owned:
        return "-"
    return ", ".join(f"`{f}`" for f in owned)


def _get_verification(task: dict[str, Any]) -> str:
    """Extract verification command from a task."""
    verification = task.get("verification", {})
    command = verification.get("command", "-")
    if command and command != "-":
        return f"`{command}`"
    return "-"


def _get_deps(task: dict[str, Any]) -> str:
    """Format task dependencies."""
    deps = task.get("dependencies", [])
    if not deps:
        return "-"
    return ", ".join(deps)


def _group_tasks_by_level(tasks: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    """Group tasks by their level field."""
    levels: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for task in tasks:
        level = task.get("level", 1)
        levels[level].append(task)
    return dict(sorted(levels.items()))


def _get_level_name(level_num: int, levels_spec: dict[str, Any] | None) -> str:
    """Get the name for a level from the levels spec, or generate a default."""
    if levels_spec:
        level_key = str(level_num)
        if level_key in levels_spec:
            name: str = levels_spec[level_key].get("name", f"Level {level_num}")
            return name
    return f"Level {level_num}"


def compute_critical_path(tasks: list[dict[str, Any]]) -> list[str]:
    """Compute the DAG longest-path by estimate_minutes.

    Uses dynamic programming on the topologically sorted task graph to find
    the path with the maximum total estimated duration.

    Args:
        tasks: List of task dicts, each with "id", "dependencies", and
            optionally "estimate_minutes" (defaults to 15 if missing).

    Returns:
        Ordered list of task IDs on the critical path, from first to last.
    """
    if not tasks:
        return []

    if len(tasks) == 1:
        return [tasks[0]["id"]]

    # Build lookup structures
    task_map: dict[str, dict[str, Any]] = {t["id"]: t for t in tasks}
    estimates: dict[str, int] = {t["id"]: t.get("estimate_minutes", 15) for t in tasks}

    # Topological sort via Kahn's algorithm
    in_degree: dict[str, int] = dict.fromkeys(task_map, 0)
    adjacency: dict[str, list[str]] = {tid: [] for tid in task_map}

    for task in tasks:
        tid = task["id"]
        for dep in task.get("dependencies", []):
            if dep in task_map:
                adjacency[dep].append(tid)
                in_degree[tid] += 1

    queue = [tid for tid, deg in in_degree.items() if deg == 0]
    topo_order: list[str] = []

    while queue:
        # Sort for deterministic ordering among equal-degree nodes
        queue.sort()
        node = queue.pop(0)
        topo_order.append(node)
        for neighbor in adjacency[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    # DP for longest path
    dist: dict[str, int] = {tid: estimates[tid] for tid in task_map}
    predecessor: dict[str, str | None] = dict.fromkeys(task_map, None)

    for node in topo_order:
        for neighbor in adjacency[node]:
            candidate = dist[node] + estimates[neighbor]
            if candidate > dist[neighbor]:
                dist[neighbor] = candidate
                predecessor[neighbor] = node

    # Find the endpoint with maximum distance
    end_node = max(dist, key=lambda tid: dist[tid])

    # Trace back the path
    path: list[str] = []
    current: str | None = end_node
    while current is not None:
        path.append(current)
        current = predecessor[current]

    path.reverse()
    return path


def estimate_sessions(
    tasks: list[dict[str, Any]],
    max_workers: int = 5,
    session_minutes: int = 90,
) -> dict[str, int | float]:
    """Estimate execution sessions for single and parallel worker scenarios.

    Groups tasks by level, computes sequential vs parallel duration, and
    derives speedup factor.

    Args:
        tasks: List of task dicts with "level" and optionally "estimate_minutes".
        max_workers: Maximum number of parallel workers per level.
        session_minutes: Duration of a single work session in minutes.

    Returns:
        Dict with keys: single_worker, with_workers, worker_count, speedup.
        Time values are number of sessions (rounded up).
    """
    if not tasks:
        return {
            "single_worker": 0,
            "with_workers": 0,
            "worker_count": max_workers,
            "speedup": 1.0,
        }

    levels = _group_tasks_by_level(tasks)

    total_minutes = sum(t.get("estimate_minutes", 15) for t in tasks)

    parallel_minutes = 0
    for _level_num, level_tasks in levels.items():
        task_estimates = [t.get("estimate_minutes", 15) for t in level_tasks]
        # With parallel workers, level duration is the max single task estimate
        # (assuming workers >= tasks, otherwise we'd need to bin-pack)
        if len(task_estimates) <= max_workers:
            parallel_minutes += max(task_estimates)
        else:
            # More tasks than workers: approximate by distributing evenly
            sorted_est = sorted(task_estimates, reverse=True)
            worker_loads = [0] * max_workers
            for est in sorted_est:
                worker_loads[worker_loads.index(min(worker_loads))] += est
            parallel_minutes += max(worker_loads)

    single_sessions = math.ceil(total_minutes / session_minutes)
    parallel_sessions = math.ceil(parallel_minutes / session_minutes)

    speedup = total_minutes / parallel_minutes if parallel_minutes > 0 else 1.0

    return {
        "single_worker": single_sessions,
        "with_workers": parallel_sessions,
        "worker_count": max_workers,
        "speedup": round(speedup, 1),
    }


def _render_header(
    lines: list[str],
    feature: str,
    total_tasks: int,
    task_data: dict[str, Any],
) -> None:
    """Render the backlog header section."""
    lines.append(f"# ZERG {feature} Task Backlog")
    lines.append("")
    lines.append(f"**Created**: {date.today().isoformat()}")
    lines.append("**Status**: PENDING")
    lines.append(f"**Feature**: {feature}")
    lines.append(f"**Total Tasks**: {total_tasks}")
    if task_data.get("estimated_duration_minutes"):
        lines.append(f"**Estimated Duration**: {task_data['estimated_duration_minutes']} minutes")
    lines.append("")
    lines.append("---")
    lines.append("")


def _render_execution_summary(
    lines: list[str],
    levels: dict[int, list[dict[str, Any]]],
    levels_spec: dict[str, Any] | None,
    max_parallel: int,
    total_tasks: int,
    session_info: dict[str, int | float],
) -> None:
    """Render the execution summary table."""
    lines.append("## Execution Summary")
    lines.append("")
    lines.append("| Level | Tasks | Parallel Workers | Est. Focus |")
    lines.append("|-------|-------|------------------|------------|")
    for level_num, level_tasks in levels.items():
        level_name = _get_level_name(level_num, levels_spec)
        worker_count = min(len(level_tasks), max_parallel)
        lines.append(f"| L{level_num} | {len(level_tasks)} | {worker_count} | {level_name} |")
    lines.append("")
    lines.append(f"**Total Tasks**: {total_tasks}")
    lines.append(f"**Max Parallelization**: {max_parallel} workers")
    lines.append(f"**Estimated Sessions**: {session_info['with_workers']} (with {max_parallel} parallel workers)")
    lines.append("")
    lines.append("---")
    lines.append("")


def _render_task_backlog_by_level(
    lines: list[str],
    levels: dict[int, list[dict[str, Any]]],
    levels_spec: dict[str, Any] | None,
) -> None:
    """Render the per-level task backlog tables."""
    lines.append("## Task Backlog by Level")
    lines.append("")

    for level_num, level_tasks in levels.items():
        level_name = _get_level_name(level_num, levels_spec)
        task_count = len(level_tasks)
        lines.append(f"### Level {level_num}: {level_name} (Parallel: {task_count} tasks)")
        lines.append("")
        lines.append("| ID | Description | Files Owned | Deps | Status | Verification |")
        lines.append("|----|-------------|-------------|------|--------|--------------|")

        for task in level_tasks:
            tid = task["id"]
            desc = task.get("title", task.get("description", "-"))
            files_owned = _get_owned_files(task)
            deps = _get_deps(task)
            status = task.get("status", "todo").upper()
            verification = _get_verification(task)
            lines.append(f"| **{tid}** | {desc} | {files_owned} | {deps} | {status} | {verification} |")

        lines.append("")

    lines.append("---")
    lines.append("")


def _render_critical_path(
    lines: list[str],
    critical_path_ids: list[str],
    tasks: list[dict[str, Any]],
    levels: dict[int, list[dict[str, Any]]],
) -> None:
    """Render the critical path ASCII diagram section."""
    lines.append("## Critical Path")
    lines.append("")
    lines.append("```")

    if critical_path_ids:
        path_by_level: dict[int, list[str]] = defaultdict(list)
        task_map = {t["id"]: t for t in tasks}
        for tid in critical_path_ids:
            task = task_map.get(tid, {})
            level = task.get("level", 1)
            path_by_level[level].append(tid)

        sorted_levels = sorted(path_by_level.keys())
        for i, level_num in enumerate(sorted_levels):
            level_task_ids = path_by_level[level_num]
            all_level_tasks = levels.get(level_num, [])
            non_critical = [t["id"] for t in all_level_tasks if t["id"] not in level_task_ids]

            if len(level_task_ids) == 1:
                tid = level_task_ids[0]
                title = task_map.get(tid, {}).get("title", "")
                short = f" ({title})" if title else ""
                line = f"{tid}{short}"
            else:
                parts = []
                for tid in level_task_ids:
                    title = task_map.get(tid, {}).get("title", "")
                    short = f" ({title})" if title else ""
                    parts.append(f"{tid}{short}")
                line = " + ".join(parts)

            if non_critical:
                parallel_count = len(all_level_tasks)
                line += f" [+{len(non_critical)} parallel, {parallel_count} total]"

            lines.append(line)
            if i < len(sorted_levels) - 1:
                lines.append("  |")
                lines.append("  v")
    else:
        lines.append("No tasks defined.")

    lines.append("```")
    lines.append("")

    if critical_path_ids:
        lines.append(f"**Critical Path Tasks**: {' -> '.join(critical_path_ids)}")
        lines.append("")

    lines.append("---")
    lines.append("")


def _render_progress_tracking(
    lines: list[str],
    levels: dict[int, list[dict[str, Any]]],
    total_tasks: int,
) -> None:
    """Render the progress tracking table."""
    lines.append("## Progress Tracking")
    lines.append("")
    lines.append("| Level | Status | Completed | Total | % |")
    lines.append("|-------|--------|-----------|-------|---|")

    total_completed = 0
    for level_num, level_tasks in levels.items():
        completed = sum(1 for t in level_tasks if t.get("status") == "complete")
        total_completed += completed
        total_in_level = len(level_tasks)
        pct = int((completed / total_in_level) * 100) if total_in_level else 0
        status = "COMPLETE" if completed == total_in_level else "PENDING"
        if any(t.get("status") in ("in_progress", "claimed") for t in level_tasks):
            status = "IN PROGRESS"
        lines.append(f"| L{level_num} | {status} | {completed} | {total_in_level} | {pct}% |")

    total_pct = int((total_completed / total_tasks) * 100) if total_tasks else 0
    overall_status = "COMPLETE" if total_completed == total_tasks else "PENDING"
    if total_completed > 0 and total_completed < total_tasks:
        overall_status = "IN PROGRESS"
    lines.append(f"| **TOTAL** | **{overall_status}** | **{total_completed}** | **{total_tasks}** | **{total_pct}%** |")
    lines.append("")
    lines.append("---")
    lines.append("")


def _render_estimated_sessions(
    lines: list[str],
    session_info: dict[str, int | float],
) -> None:
    """Render the estimated sessions section."""
    lines.append("## Estimated Sessions")
    lines.append("")
    lines.append(f"- **Single worker**: {session_info['single_worker']} sessions")
    lines.append(f"- **With {session_info['worker_count']} workers**: {session_info['with_workers']} sessions")
    lines.append(f"- **Speedup**: {session_info['speedup']}x")
    lines.append("")
    lines.append("---")
    lines.append("")


def _render_blockers(
    lines: list[str],
    tasks: list[dict[str, Any]],
) -> None:
    """Render the blockers and notes section."""
    lines.append("## Blockers & Notes")
    lines.append("")
    blocked_tasks = [t for t in tasks if t.get("status") == "blocked"]
    if blocked_tasks:
        for task in blocked_tasks:
            tid = task["id"]
            msg = task.get("execution", {}).get("error_message", "Unknown blocker")
            lines.append(f"- **{tid}**: {msg}")
    else:
        lines.append("- No blockers identified.")
    lines.append("")
    lines.append("---")
    lines.append("")


def _render_verification_commands(
    lines: list[str],
    tasks: list[dict[str, Any]],
) -> None:
    """Render the verification commands section."""
    lines.append("## Verification Commands")
    lines.append("")
    lines.append("```bash")
    verification_cmds = set()
    for task in tasks:
        cmd = task.get("verification", {}).get("command")
        if cmd:
            verification_cmds.add(cmd)
    if verification_cmds:
        for cmd in sorted(verification_cmds):
            lines.append(cmd)
    else:
        lines.append("# No verification commands defined")
    lines.append("```")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"*Last Updated: {date.today().isoformat()}*")
    lines.append("")


def generate_backlog_markdown(
    task_data: dict[str, Any],
    feature: str,
    output_dir: str | Path = "tasks",
) -> Path:
    """Generate a markdown backlog file from task graph data.

    Creates a comprehensive backlog document with execution summary,
    per-level task tables, critical path diagram, and progress tracking.

    Args:
        task_data: A task-graph.json dict conforming to the ZERG task graph schema.
        feature: Feature name used for the filename and header.
        output_dir: Directory to write the backlog file into.

    Returns:
        Path to the created markdown file.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    filename = f"{feature.upper().replace(' ', '-')}-BACKLOG.md"
    file_path = output_path / filename

    tasks = task_data.get("tasks", [])
    levels_spec = task_data.get("levels")
    levels = _group_tasks_by_level(tasks)
    total_tasks = len(tasks)
    max_parallel = task_data.get("max_parallelization", 5)

    critical_path_ids = compute_critical_path(tasks)
    session_info = estimate_sessions(tasks, max_workers=max_parallel)

    lines: list[str] = []

    _render_header(lines, feature, total_tasks, task_data)
    _render_execution_summary(lines, levels, levels_spec, max_parallel, total_tasks, session_info)
    _render_task_backlog_by_level(lines, levels, levels_spec)
    _render_critical_path(lines, critical_path_ids, tasks, levels)
    _render_progress_tracking(lines, levels, total_tasks)
    _render_estimated_sessions(lines, session_info)
    _render_blockers(lines, tasks)
    _render_verification_commands(lines, tasks)

    file_path.write_text("\n".join(lines), encoding="utf-8")
    return file_path


def update_backlog_task_status(
    backlog_path: Path | str,
    task_id: str,
    status: str,
    blocker: str | None = None,
) -> bool:
    """Update a task's status in an existing backlog markdown file.

    Finds the row containing the task_id in the markdown table and replaces
    the Status column value. Optionally adds or updates a blocker entry.

    Args:
        backlog_path: Path to the backlog markdown file.
        task_id: The task ID to find (e.g., "FEAT-L1-001").
        status: The new status string to set.
        blocker: Optional blocker description to add to the Blockers section.

    Returns:
        True if the task was found and updated, False otherwise.
    """
    path = Path(backlog_path)
    if not path.exists():
        return False

    content = path.read_text(encoding="utf-8")

    # Match a table row containing the task_id in the ID column.
    # Table format: | **TASK-ID** | desc | files | deps | STATUS | verification |
    pattern = r"(\| \*\*" + re.escape(task_id) + r"\*\* \|[^|]*\|[^|]*\|[^|]*\|)\s*([^|]*?)(\s*\|[^|]*\|)"

    match = re.search(pattern, content)
    if not match:
        return False

    replacement = f"{match.group(1)} {status.upper()} {match.group(3)}"
    content = content[: match.start()] + replacement + content[match.end() :]

    # Handle blocker addition/update
    if blocker is not None:
        blocker_line = f"- **{task_id}**: {blocker}"
        # Check if there's already a blocker for this task
        existing_blocker_pattern = r"- \*\*" + re.escape(task_id) + r"\*\*:.*"
        if re.search(existing_blocker_pattern, content):
            content = re.sub(existing_blocker_pattern, blocker_line, content)
        else:
            # Add after "## Blockers & Notes" section header
            blockers_pattern = r"(## Blockers & Notes\n\n)"
            blockers_match = re.search(blockers_pattern, content)
            if blockers_match:
                insert_pos = blockers_match.end()
                # Remove "No blockers identified" if present
                no_blockers = "- No blockers identified.\n"
                if content[insert_pos:].startswith(no_blockers):
                    content = content[:insert_pos] + content[insert_pos + len(no_blockers) :]
                    insert_pos = insert_pos  # position stays the same
                content = content[:insert_pos] + blocker_line + "\n" + content[insert_pos:]

    path.write_text(content, encoding="utf-8")
    return True
