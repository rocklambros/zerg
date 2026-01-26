"""ZERG logs command - stream worker logs."""

import json
import time
from pathlib import Path

import click
from rich.console import Console
from rich.text import Text

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
@click.pass_context
def logs(
    ctx: click.Context,
    worker_id: int | None,
    feature: str | None,
    tail: int,
    follow: bool,
    level: str,
    json_output: bool,
) -> None:
    """Stream worker logs.

    Shows logs from workers with optional filtering.

    Examples:

        zerg logs

        zerg logs 1

        zerg logs --follow --level debug

        zerg logs --tail 50 --feature user-auth
    """
    try:
        # Auto-detect feature
        if not feature:
            feature = detect_feature()

        if not feature:
            console.print("[red]Error:[/red] No active feature found")
            console.print("Specify a feature with [cyan]--feature[/cyan]")
            raise SystemExit(1)

        # Find log files
        log_dir = Path(".zerg/logs")
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
        raise SystemExit(1)


def detect_feature() -> str | None:
    """Detect active feature from state files.

    Returns:
        Feature name or None
    """
    state_dir = Path(".zerg/state")
    if not state_dir.exists():
        return None

    # Find most recent state file
    state_files = list(state_dir.glob("*.json"))
    if not state_files:
        return None

    # Sort by modification time
    state_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return state_files[0].stem


def get_level_priority(level: str) -> int:
    """Get numeric priority for log level.

    Args:
        level: Level name

    Returns:
        Priority number (lower = more verbose)
    """
    priorities = {"debug": 0, "info": 1, "warn": 2, "warning": 2, "error": 3, "critical": 4}
    return priorities.get(level.lower(), 1)


def parse_log_line(line: str) -> dict | None:
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
        return json.loads(line)
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


def format_log_entry(entry: dict) -> Text:
    """Format a log entry for display.

    Args:
        entry: Log entry dict

    Returns:
        Rich Text object
    """
    text = Text()

    # Timestamp
    ts = entry.get("timestamp", "")
    if ts:
        # Show just time portion
        if len(ts) >= 19:
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
    for key in ["task_id", "error"]:
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
            console.print(json.dumps(entry))
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
                                    console.print(json.dumps(entry))
                                else:
                                    console.print(format_log_entry(entry))

                except Exception as e:
                    logger.warning(f"Error reading {log_file}: {e}")

        time.sleep(0.5)
