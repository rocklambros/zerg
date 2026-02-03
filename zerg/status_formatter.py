"""Status dashboard formatting for ZERG — rendering for HEALTH, REPO MAP, and TOKEN sections.

Pure functions that transform heartbeat, escalation, progress, repo-index,
and token-aggregation data into ASCII table strings for the /zerg:status dashboard.
"""

from __future__ import annotations

from datetime import UTC
from typing import Any

# Dashboard width matching existing status.core.md format
DASHBOARD_WIDTH = 79

# Column widths for the health table (total inner = 79 - 2 outer borders = 77)
# Each column: content + 2 padding spaces + 1 separator = varies
_COL_WORKER = 6
_COL_STATUS = 7
_COL_TASK = 8
_COL_STEP = 13
_COL_PROGRESS = 8
_COL_RESTARTS = 8


def _truncate(value: str, width: int) -> str:
    """Truncate string to width, adding ellipsis if needed."""
    if len(value) <= width:
        return value
    return value[: width - 1] + "\u2026"


def _build_row(cells: list[str], widths: list[int]) -> str:
    """Build a single table row with pipe separators."""
    parts = []
    for cell, width in zip(cells, widths):
        parts.append(f" {_truncate(cell, width):<{width}} ")
    return "\u2502" + "\u2502".join(parts) + "\u2502"


def _build_separator(widths: list[int], left: str, mid: str, right: str) -> str:
    """Build a horizontal separator line."""
    segments = ["\u2500" * (w + 2) for w in widths]
    return left + mid.join(segments) + right


def _determine_status(heartbeat: dict[str, Any], stall_timeout: int = 120) -> str:
    """Determine worker status from heartbeat data."""
    from datetime import datetime

    timestamp = heartbeat.get("timestamp", "")
    if not timestamp:
        return "unknown"

    try:
        ts = datetime.fromisoformat(timestamp)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        now = datetime.now(UTC)
        age = (now - ts).total_seconds()
    except (ValueError, TypeError):
        return "unknown"

    if age > stall_timeout:
        return "stale"
    return "active"


def _count_restarts(progress_data: list[dict[str, Any]], worker_id: int) -> int:
    """Count retry attempts from progress tier results for a worker."""
    for p in progress_data:
        if p.get("worker_id") == worker_id:
            total = 0
            for tier in p.get("tier_results", []):
                total += tier.get("retry", 0)
            return total
    return 0


def format_health_table(
    heartbeats: list[dict[str, Any]],
    escalations: list[dict[str, Any]] | None = None,
    progress_data: list[dict[str, Any]] | None = None,
    stall_timeout: int = 120,
) -> str:
    """Format worker health data as an ASCII table.

    Args:
        heartbeats: List of heartbeat dicts with keys:
            worker_id, timestamp, task_id, step, progress_pct.
        escalations: Optional list of escalation dicts (unused here,
            passed through for context; use format_escalations separately).
        progress_data: Optional list of worker progress dicts with keys:
            worker_id, tasks_completed, tasks_total, tier_results.
        stall_timeout: Seconds after which a heartbeat is considered stale.

    Returns:
        Formatted ASCII table string.
    """
    if not heartbeats:
        return "No worker data available"

    progress_data = progress_data or []
    widths = [_COL_WORKER, _COL_STATUS, _COL_TASK, _COL_STEP, _COL_PROGRESS, _COL_RESTARTS]
    headers = ["Worker", "Status", "Task", "Step", "Progress", "Restarts"]

    lines: list[str] = []
    lines.append(_build_separator(widths, "\u250c", "\u252c", "\u2510"))
    lines.append(_build_row(headers, widths))
    lines.append(_build_separator(widths, "\u251c", "\u253c", "\u2524"))

    sorted_hbs = sorted(heartbeats, key=lambda h: h.get("worker_id", 0))

    for hb in sorted_hbs:
        worker_id = hb.get("worker_id", "?")
        status = _determine_status(hb, stall_timeout)
        task_id = hb.get("task_id") or "-"
        step = hb.get("step", "unknown")
        progress_pct = hb.get("progress_pct", 0)
        restarts = _count_restarts(progress_data, worker_id)

        cells = [
            str(worker_id),
            status,
            str(task_id),
            step,
            f"{progress_pct}%",
            str(restarts),
        ]
        lines.append(_build_row(cells, widths))

    lines.append(_build_separator(widths, "\u2514", "\u2534", "\u2518"))
    return "\n".join(lines)


def format_escalations(escalations: list[dict[str, Any]]) -> str:
    """Format escalation data for the status dashboard.

    Args:
        escalations: List of escalation dicts with keys:
            worker_id, task_id, category, message, resolved.

    Returns:
        Formatted string showing unresolved escalations.
    """
    if not escalations:
        return "No escalations"

    unresolved = [e for e in escalations if not e.get("resolved", False)]
    resolved_count = len(escalations) - len(unresolved)

    if not unresolved:
        return f"No escalations (0 unresolved, {resolved_count} resolved)"

    lines: list[str] = []
    for esc in unresolved:
        worker_id = esc.get("worker_id", "?")
        task_id = esc.get("task_id", "?")
        category = esc.get("category", "unknown")
        message = esc.get("message", "")

        lines.append(f"  \U0001f6a8 {task_id} (Worker {worker_id}): {category}")
        if message:
            # Wrap long messages at dashboard width minus indent
            max_msg = DASHBOARD_WIDTH - 7
            display_msg = message if len(message) <= max_msg else message[: max_msg - 3] + "..."
            lines.append(f"     {display_msg!r}")

    lines.append(f"  Total: {len(unresolved)} unresolved, {resolved_count} resolved")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Repository map stats
# ---------------------------------------------------------------------------


def format_repo_map_stats(index_data: dict[str, Any] | None) -> str:
    """Format IncrementalIndex.get_stats() output for the status dashboard.

    Args:
        index_data: Dict with keys total_files, indexed_files,
            stale_files, last_updated (from IncrementalIndex.get_stats()).

    Returns:
        Formatted multi-line string block.
    """
    if not index_data:
        return "No repo map data available"

    total = index_data.get("total_files", 0)
    indexed = index_data.get("indexed_files", 0)
    stale = index_data.get("stale_files", 0)
    last_updated = index_data.get("last_updated") or "never"

    if total == 0 and indexed == 0:
        return "No repo map data available"

    return (
        f"  Files tracked:  {total:>5}\n"
        f"  Files indexed:  {indexed:>5}\n"
        f"  Stale files:    {stale:>5}\n"
        f"  Last updated:   {last_updated}"
    )


# ---------------------------------------------------------------------------
# Token usage table
# ---------------------------------------------------------------------------

# Column widths for the token table
_TOK_COL_WORKER = 8
_TOK_COL_TASKS = 6
_TOK_COL_PER_TASK = 12
_TOK_COL_TOTAL = 10
_TOK_COL_MODE = 12


def format_token_table(worker_tokens: dict[str, Any] | None) -> str:
    """Format per-worker token data as an ASCII table.

    Args:
        worker_tokens: Dict keyed by worker id, each value a dict with
            total_tokens and tasks_completed (from AggregateResult.per_worker).

    Returns:
        Formatted ASCII table string.
    """
    if not worker_tokens:
        return "No token data available"

    widths = [
        _TOK_COL_WORKER,
        _TOK_COL_TASKS,
        _TOK_COL_PER_TASK,
        _TOK_COL_TOTAL,
        _TOK_COL_MODE,
    ]
    headers = ["Worker", "Tasks", "Tokens/Task", "Total", "Mode"]

    lines: list[str] = []
    lines.append(_build_separator(widths, "\u250c", "\u252c", "\u2510"))
    lines.append(_build_row(headers, widths))
    lines.append(_build_separator(widths, "\u251c", "\u253c", "\u2524"))

    grand_total = 0
    grand_tasks = 0

    for wid in sorted(worker_tokens.keys(), key=lambda k: str(k)):
        wdata = worker_tokens[wid]
        w_tokens = int(wdata.get("total_tokens", 0))
        w_tasks = int(wdata.get("tasks_completed", 0))
        per_task = w_tokens / w_tasks if w_tasks > 0 else 0
        mode = wdata.get("mode", "estimated")

        grand_total += w_tokens
        grand_tasks += w_tasks

        cells = [
            str(wid),
            str(w_tasks),
            f"{per_task:,.0f}",
            f"{w_tokens:,}",
            f"({mode})",
        ]
        lines.append(_build_row(cells, widths))

    # Summary row
    lines.append(_build_separator(widths, "\u251c", "\u253c", "\u2524"))
    overall_per_task = grand_total / grand_tasks if grand_tasks > 0 else 0
    summary_cells = [
        "TOTAL",
        str(grand_tasks),
        f"{overall_per_task:,.0f}",
        f"{grand_total:,}",
        "",
    ]
    lines.append(_build_row(summary_cells, widths))
    lines.append(_build_separator(widths, "\u2514", "\u2534", "\u2518"))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Token savings
# ---------------------------------------------------------------------------


def format_savings(savings_data: Any | None) -> str:
    """Format token savings data for the status dashboard.

    Args:
        savings_data: A SavingsResult dataclass or dict with fields:
            context_injected_tokens, full_spec_baseline_tokens,
            tokens_saved, savings_pct, breakdown.

    Returns:
        Formatted multi-line string block.
    """
    if savings_data is None:
        return "No savings data available"

    # Support both dataclass and dict
    if hasattr(savings_data, "__dataclass_fields__"):
        injected = savings_data.context_injected_tokens
        baseline = savings_data.full_spec_baseline_tokens
        saved = savings_data.tokens_saved
        pct = savings_data.savings_pct
        breakdown = savings_data.breakdown or {}
    elif isinstance(savings_data, dict):
        injected = savings_data.get("context_injected_tokens", 0)
        baseline = savings_data.get("full_spec_baseline_tokens", 0)
        saved = savings_data.get("tokens_saved", 0)
        pct = savings_data.get("savings_pct", 0.0)
        breakdown = savings_data.get("breakdown") or {}
    else:
        return "No savings data available"

    if baseline == 0 and injected == 0:
        return "No savings data available"

    lines: list[str] = [
        f"  Context injected: {injected:>10,} tokens",
        f"  Full-spec baseline: {baseline:>8,} tokens",
        f"  Tokens saved:     {saved:>10,} tokens ({pct:.1f}%)",
    ]

    if breakdown:
        lines.append("")
        lines.append("  Breakdown:")
        for component, detail in sorted(breakdown.items()):
            if isinstance(detail, dict):
                comp_injected = detail.get("injected", 0)
                comp_saved = detail.get("saved", 0)
                lines.append(f"    {component:<20s}  injected: {comp_injected:>7,}  saved: {comp_saved:>7,}")
            else:
                lines.append(f"    {component}: {detail}")

    return "\n".join(lines)
