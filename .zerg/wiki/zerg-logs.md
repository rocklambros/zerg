# /zerg:logs

Stream, filter, and aggregate worker logs for debugging and monitoring.

## Synopsis

```
/zerg:logs [WORKER_ID] [OPTIONS]
```

## Description

`/zerg:logs` provides access to structured JSONL logs written by workers and the orchestrator. It supports filtering by worker, task, log level, execution phase, event type, and time range. Logs can be viewed in human-readable format or exported as raw JSON.

### Log Format

Workers write structured JSON lines to `.zerg/logs/workers/worker-<id>.jsonl`. Each entry contains:

| Field | Required | Description |
|-------|----------|-------------|
| `ts` | Yes | ISO 8601 timestamp |
| `level` | Yes | Log level: debug, info, warn, error |
| `message` | Yes | Human-readable message |
| `worker_id` | Yes | Worker identifier |
| `feature` | Yes | Feature name |
| `task_id` | No | Task identifier |
| `phase` | No | Execution phase |
| `event` | No | Event type |
| `data` | No | Additional structured data |
| `duration_ms` | No | Duration in milliseconds |

### Log Levels

| Level | Description |
|-------|-------------|
| debug | Detailed debugging information |
| info | Normal operational messages |
| warn | Warning conditions |
| error | Error conditions requiring attention |

### Execution Phases

| Phase | Description |
|-------|-------------|
| claim | Worker claiming a task |
| execute | Claude Code invocation running |
| verify | Running the task's verification command |
| commit | Git commit of changes |
| cleanup | Post-task cleanup |

### Event Types

| Event | Description |
|-------|-------------|
| task_started | Task execution began |
| task_completed | Task finished successfully |
| task_failed | Task execution failed |
| verification_passed | Verification command succeeded |
| verification_failed | Verification command failed |
| artifact_captured | Artifact file written |
| level_started | Orchestrator started a new level |
| level_complete | All tasks in a level finished |
| merge_started | Branch merge began |
| merge_complete | Branch merge finished |

### Task Artifacts

Each task produces artifact files that can be viewed with `--artifacts`:

- `claude_output.txt` -- stdout/stderr from the Claude Code invocation
- `verification_output.txt` -- Output from the verification command
- `git_diff.patch` -- Changes committed by the task
- `execution.jsonl` -- Structured event log for the task

## Options

| Option | Description |
|--------|-------------|
| `WORKER_ID` | Optional. Filter logs to a specific worker |
| `-f`, `--feature TEXT` | Feature name (auto-detected from `.gsd/.current-feature`) |
| `-n`, `--tail INTEGER` | Number of lines to show (default: 100) |
| `--follow` | Stream new log entries continuously (Ctrl+C to stop) |
| `-l`, `--level LEVEL` | Filter by log level: `debug`, `info`, `warn`, `error` |
| `--json` | Output raw JSON format |
| `--aggregate` | Merge all worker JSONL logs sorted by timestamp |
| `--task TEXT` | Filter to a specific task ID |
| `--artifacts TEXT` | Show artifact file contents for a task |
| `--phase TEXT` | Filter by execution phase |
| `--event TEXT` | Filter by event type |
| `--since TEXT` | Only entries after this ISO 8601 timestamp |
| `--until TEXT` | Only entries before this ISO 8601 timestamp |
| `--search TEXT` | Text search within log messages |

## Examples

```bash
# Show recent logs from all workers
/zerg:logs

# Show logs from worker 1
/zerg:logs 1

# Follow logs in real-time
/zerg:logs --follow

# Show only errors
/zerg:logs --level error

# Show more lines
/zerg:logs --tail 200

# Aggregate all worker logs by timestamp
/zerg:logs --aggregate

# Filter to a specific task
/zerg:logs --task TASK-015

# Show task artifacts (Claude output, verification, git diff)
/zerg:logs --artifacts TASK-015

# Filter by phase and event
/zerg:logs --aggregate --phase verify --event verification_failed

# Time range filtering
/zerg:logs --aggregate --since 2026-01-28T10:00:00Z --until 2026-01-28T12:00:00Z

# Text search
/zerg:logs --aggregate --search "failed"

# Export structured logs for external analysis
/zerg:logs --aggregate --json > logs.jsonl
```

## Log Locations

| Log Type | Path |
|----------|------|
| Worker JSONL logs | `.zerg/logs/workers/worker-<id>.jsonl` |
| Orchestrator log | `.zerg/logs/orchestrator.jsonl` |
| Task execution log | `.zerg/logs/tasks/<TASK-ID>/execution.jsonl` |
| Claude output | `.zerg/logs/tasks/<TASK-ID>/claude_output.txt` |
| Verification output | `.zerg/logs/tasks/<TASK-ID>/verification_output.txt` |
| Git diff | `.zerg/logs/tasks/<TASK-ID>/git_diff.patch` |
| Legacy worker logs | `.zerg/logs/worker-<id>.log` |

## See Also

- [[zerg-status]] -- High-level progress overview
- [[zerg-retry]] -- Re-run tasks identified through log inspection
- [[zerg-cleanup]] -- Remove log files with `--keep-logs` option to preserve them
- [[zerg-Reference]] -- Full command index
