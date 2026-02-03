"""ZERG logs command - stream worker logs."""

import json
import subprocess
import time
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.text import Text

from zerg.log_aggregator import LogAggregator
from zerg.logging import get_logger

console = Console()
logger = get_logger("logs")


# Log level colors
LEVEL_COLORS = {
    "debug": "dim",
    "info": "blue",
    "warning": "yellow",
    "warn": "yellow",
    "error": "red",
    "critical": "bold red",
}


@click.command()
@click.argument("worker_id", required=False, type=int)
@click.option("--feature", "-f", help="Feature name")
@click.option("--tail", "-n", default=100, type=int, help="Lines to show")
@click.option("--follow", is_flag=True, help="Stream new logs")
@click.option(
    "--level",
    "-l",
    type=click.Choice(["debug", "info", "warn", "error"]),
    default="info",
    help="Log level filter",
)
@click.option("--json", "json_output", is_flag=True, help="Raw JSON output")
@click.option("--aggregate", is_flag=True, help="Merge all worker JSONL logs by timestamp")
@click.option("--task", "task_id", type=str, default=None, help="Filter to specific task ID")
@click.option(
    "--artifacts",
    "artifacts_task",
    type=str,
    default=None,
    help="Show artifact file contents for a task",
)
@click.option(
    "--phase",
    type=str,
    default=None,
    help="Filter by execution phase (claim/execute/verify/commit/cleanup)",
)
@click.option(
    "--event",
    type=str,
    default=None,
    help="Filter by event type (task_started, task_completed, etc.)",
)
@click.option("--since", type=str, default=None, help="Only entries after this ISO8601 timestamp")
@click.option("--until", type=str, default=None, help="Only entries before this ISO8601 timestamp")
@click.option("--search", type=str, default=None, help="Text search in messages")
@click.pass_context
def logs(
    ctx: click.Context,
    worker_id: int | None,
    feature: str | None,
    tail: int,
    follow: bool,
    level: str,
    json_output: bool,
    aggregate: bool,
    task_id: str | None,
    artifacts_task: str | None,
    phase: str | None,
    event: str | None,
    since: str | None,
    until: str | None,
    search: str | None,
) -> None:
    """Stream worker logs.

    Shows logs from workers with optional filtering.
    Use --aggregate for structured JSONL log aggregation across all workers.

    Examples:

        zerg logs

        zerg logs 1

        zerg logs --follow --level debug

        zerg logs --tail 50 --feature user-auth

        zerg logs --aggregate

        zerg logs --task T1.1

        zerg logs --artifacts T1.1

        zerg logs --aggregate --phase verify --event verification_failed
    """
    try:
        # Auto-detect feature
        if not feature:
            feature = detect_feature()

        if not feature:
            console.print("[red]Error:[/red] No active feature found")
            console.print("Specify a feature with [cyan]--feature[/cyan]")
            raise SystemExit(1)

        log_dir = Path(".zerg/logs")

        # Handle --artifacts mode
        if artifacts_task:
            _show_task_artifacts(log_dir, artifacts_task)
            return

        # Handle --aggregate or structured query mode
        if aggregate or task_id or phase or event or since or until or search:
            _show_aggregated_logs(
                log_dir=log_dir,
                feature=feature,
                worker_id=worker_id,
                task_id=task_id,
                level=level,
                phase=phase,
                event=event,
                since=since,
                until=until,
                search=search,
                tail=tail,
                json_output=json_output,
            )
            return

        # Check if container mode — try docker logs first
        launcher_type = _get_launcher_type()
        if launcher_type == "container" and worker_id is not None:
            container_output = _get_container_logs(worker_id)
            if container_output is not None:
                if not json_output:
                    console.print(f"[dim]Container logs for worker {worker_id}:[/dim]\n")
                console.print(container_output)
                return

        # Find log files (legacy .log files)
        if not log_dir.exists():
            console.print("[yellow]No logs directory found[/yellow]")
            return

        # Get log files
        if worker_id is not None:
            log_files = [log_dir / f"worker-{worker_id}.log"]
        else:
            log_files = sorted(log_dir.glob("*.log"))

        if not log_files:
            console.print("[yellow]No log files found[/yellow]")
            return

        # Check which files exist
        existing_files = [f for f in log_files if f.exists()]
        if not existing_files:
            console.print("[yellow]No log files found[/yellow]")
            return

        if not json_output:
            console.print(f"[bold cyan]ZERG Logs[/bold cyan] - {feature}\n")

        # Convert level to priority
        level_priority = get_level_priority(level)

        if follow:
            stream_logs(existing_files, level_priority, json_output)
        else:
            show_logs(existing_files, tail, level_priority, json_output)

    except KeyboardInterrupt:
        console.print("\n[dim]Stopped[/dim]")
    except Exception as e:
        console.print(f"\n[red]Error:[/red] {e}")
        raise SystemExit(1) from None


def _show_aggregated_logs(
    log_dir: Path,
    feature: str,
    worker_id: int | None = None,
    task_id: str | None = None,
    level: str = "info",
    phase: str | None = None,
    event: str | None = None,
    since: str | None = None,
    until: str | None = None,
    search: str | None = None,
    tail: int = 100,
    json_output: bool = False,
) -> None:
    """Show aggregated structured JSONL logs.

    Uses LogAggregator to merge all worker JSONL files by timestamp.
    """
    aggregator = LogAggregator(log_dir)

    entries = aggregator.query(
        worker_id=worker_id,
        task_id=task_id,
        level=level if level != "info" else None,  # Don't filter by info (show all >= info)
        phase=phase,
        event=event,
        since=since,
        until=until,
        search=search,
        limit=tail,
    )

    if not entries:
        console.print("[yellow]No structured log entries found[/yellow]")
        console.print("[dim]Hint: Structured JSONL logs are in .zerg/logs/workers/[/dim]")
        return

    if not json_output:
        console.print(f"[bold cyan]ZERG Aggregated Logs[/bold cyan] - {feature}\n")

    for entry in entries:
        if json_output:
            console.print(json.dumps(entry), soft_wrap=True)
        else:
            console.print(format_log_entry(entry))


def _show_task_artifacts(log_dir: Path, task_id: str) -> None:
    """Show artifact file contents for a task.

    Args:
        log_dir: Log directory
        task_id: Task identifier
    """
    aggregator = LogAggregator(log_dir)
    artifacts = aggregator.get_task_artifacts(task_id)

    if not artifacts:
        console.print(f"[yellow]No artifacts found for task {task_id}[/yellow]")
        return

    console.print(f"[bold cyan]Artifacts for {task_id}[/bold cyan]\n")

    for name, path in sorted(artifacts.items()):
        console.print(f"[bold]--- {name} ---[/bold]")
        try:
            content = path.read_text()
            if name.endswith(".jsonl"):
                # Format JSONL entries
                for line in content.strip().split("\n"):
                    if line.strip():
                        try:
                            entry = json.loads(line)
                            console.print(json.dumps(entry, indent=2))
                        except json.JSONDecodeError:
                            console.print(line)
            else:
                console.print(content)
        except Exception as e:
            console.print(f"[red]Error reading {name}: {e}[/red]")
        console.print()


def _get_launcher_type() -> str:
    """Detect launcher type from config.

    Returns:
        'container' or 'subprocess'
    """
    try:
        from zerg.config import ZergConfig

        config = ZergConfig.load()
        return config.workers.launcher_type
    except Exception as e:
        logger.debug(f"Mode detection failed: {e}")
        return "subprocess"


def _get_container_logs(worker_id: int) -> str | None:
    """Fetch logs from a running or stopped container.

    Args:
        worker_id: Worker ID

    Returns:
        Log output string or None if unavailable
    """
    name = f"zerg-worker-{worker_id}"
    try:
        result = subprocess.run(
            ["docker", "logs", name],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout if result.returncode == 0 else None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def detect_feature() -> str | None:
    """Detect active feature. Re-exported from shared utility.

    See :func:`zerg.commands._utils.detect_feature` for details.
    """
    from zerg.commands._utils import detect_feature as _detect

    return _detect()


def get_level_priority(level: str) -> int:
    """Get numeric priority for log level.

    Args:
        level: Level name

    Returns:
        Priority number (lower = more verbose)
    """
    priorities = {"debug": 0, "info": 1, "warn": 2, "warning": 2, "error": 3, "critical": 4}
    return priorities.get(level.lower(), 1)


def parse_log_line(line: str) -> dict[str, Any] | None:
    """Parse a log line.

    Args:
        line: Raw log line

    Returns:
        Parsed log dict or None
    """
    line = line.strip()
    if not line:
        return None

    # Try JSON format first
    try:
        result: dict[str, Any] = json.loads(line)
        return result
    except json.JSONDecodeError:
        pass

    # Try plain format
    # Format: 2025-01-25 10:30:45 [INFO] worker:123 - Message
    parts = line.split(" - ", 1)
    if len(parts) >= 2:
        prefix = parts[0]
        message = parts[1]

        return {
            "timestamp": prefix[:19] if len(prefix) >= 19 else "",
            "level": extract_level(prefix),
            "message": message,
        }

    return {"message": line, "level": "info", "timestamp": ""}


def extract_level(prefix: str) -> str:
    """Extract log level from prefix.

    Args:
        prefix: Log prefix

    Returns:
        Level string
    """
    prefix_upper = prefix.upper()
    for level in ["DEBUG", "INFO", "WARNING", "WARN", "ERROR", "CRITICAL"]:
        if level in prefix_upper:
            return level.lower()
    return "info"


def format_log_entry(entry: dict[str, Any]) -> Text:
    """Format a log entry for display.

    Args:
        entry: Log entry dict

    Returns:
        Rich Text object
    """
    text = Text()

    # Timestamp - support both "timestamp" (legacy) and "ts" (JSONL) fields
    ts = entry.get("ts", entry.get("timestamp", ""))
    if ts:
        # Show just time portion
        if "T" in ts:
            ts = ts.split("T")[1][:8]  # ISO8601 format
        elif len(ts) >= 19:
            ts = ts[11:19]
        text.append(f"[{ts}] ", style="dim")

    # Level
    level = entry.get("level", "info").lower()
    color = LEVEL_COLORS.get(level, "white")
    text.append(f"[{level.upper():5}] ", style=color)

    # Worker ID if present
    worker_id = entry.get("worker_id")
    if worker_id is not None:
        text.append(f"W{worker_id} ", style="cyan")

    # Message
    message = entry.get("message", str(entry))
    text.append(message)

    # Extra fields
    for key in ["task_id", "phase", "event", "error"]:
        if key in entry and entry[key]:
            text.append(f" {key}={entry[key]}", style="dim")

    return text


def show_logs(
    log_files: list[Path],
    tail: int,
    level_priority: int,
    json_output: bool,
) -> None:
    """Show recent logs.

    Args:
        log_files: Log files to read
        tail: Number of lines
        level_priority: Minimum level priority
        json_output: Whether to output JSON
    """
    # Collect all entries
    entries = []

    for log_file in log_files:
        try:
            with open(log_file) as f:
                lines = f.readlines()

            # Take last N lines
            for line in lines[-tail:]:
                entry = parse_log_line(line)
                if entry:
                    entry["_file"] = log_file.name
                    entries.append(entry)
        except Exception as e:
            logger.warning(f"Error reading {log_file}: {e}")

    # Sort by timestamp
    entries.sort(key=lambda e: e.get("timestamp", ""))

    # Filter by level
    filtered = []
    for entry in entries:
        entry_level = entry.get("level", "info").lower()
        entry_priority = get_level_priority(entry_level)
        if entry_priority >= level_priority:
            filtered.append(entry)

    # Output
    for entry in filtered[-tail:]:
        if json_output:
            console.print(json.dumps(entry), soft_wrap=True)
        else:
            console.print(format_log_entry(entry))


def stream_logs(
    log_files: list[Path],
    level_priority: int,
    json_output: bool,
) -> None:
    """Stream logs continuously.

    Args:
        log_files: Log files to stream
        level_priority: Minimum level priority
        json_output: Whether to output JSON
    """
    # Track file positions
    positions: dict[Path, int] = {}
    for log_file in log_files:
        if log_file.exists():
            positions[log_file] = log_file.stat().st_size

    console.print("[dim]Streaming logs (Ctrl+C to stop)...[/dim]\n")

    while True:
        for log_file in log_files:
            if not log_file.exists():
                continue

            current_size = log_file.stat().st_size
            last_pos = positions.get(log_file, 0)

            if current_size > last_pos:
                # Read new content
                try:
                    with open(log_file) as f:
                        f.seek(last_pos)
                        new_content = f.read()

                    positions[log_file] = current_size

                    # Process new lines
                    for line in new_content.splitlines():
                        entry = parse_log_line(line)
                        if entry:
                            entry_level = entry.get("level", "info").lower()
                            entry_priority = get_level_priority(entry_level)

                            if entry_priority >= level_priority:
                                if json_output:
                                    console.print(json.dumps(entry), soft_wrap=True)
                                else:
                                    console.print(format_log_entry(entry))

                except Exception as e:
                    logger.warning(f"Error reading {log_file}: {e}")

        time.sleep(0.5)


# Alias for external import
logs_command = logs
