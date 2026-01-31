# ZERG Logs

Stream, filter, and aggregate worker logs for debugging and monitoring.

## Usage

```bash
# Show recent logs from all workers
zerg logs

# Show logs from specific worker
zerg logs 1

# Follow logs in real-time
zerg logs --follow

# Filter by log level
zerg logs --level error

# Show more lines
zerg logs --tail 200

# Output as JSON for scripting
zerg logs --json

# Aggregate structured JSONL logs across all workers
zerg logs --aggregate

# Filter to a specific task
zerg logs --task T1.1

# Show task artifacts (Claude output, verification, git diff)
zerg logs --artifacts T1.1

# Filter by execution phase and event
zerg logs --aggregate --phase verify --event verification_failed

# Time range filtering
zerg logs --aggregate --since 2026-01-28T10:00:00Z --until 2026-01-28T12:00:00Z

# Text search in messages
zerg logs --aggregate --search "failed"
```

## CLI Flags

```
zerg logs [WORKER_ID] [OPTIONS]

Arguments:
  WORKER_ID              Optional worker ID to filter logs

Options:
  -f, --feature TEXT     Feature name (auto-detected)
  -n, --tail INTEGER     Number of lines to show (default: 100)
  --follow               Stream new logs continuously
  -l, --level LEVEL      Filter by log level: debug|info|warn|error
  --json                 Output raw JSON format
  --aggregate            Merge all worker JSONL logs by timestamp
  --task TEXT            Filter to specific task ID
  --artifacts TEXT       Show artifact file contents for a task
  --phase TEXT           Filter by execution phase (claim/execute/verify/commit/cleanup)
  --event TEXT           Filter by event type (task_started, task_completed, etc.)
  --since TEXT           Only entries after this ISO8601 timestamp
  --until TEXT           Only entries before this ISO8601 timestamp
  --search TEXT          Text search in messages
```

## Log Format

### Structured JSONL Format (workers/*.jsonl)

Each worker writes structured JSON lines to `.zerg/logs/workers/worker-{id}.jsonl`:

```json
{"ts":"2026-01-28T10:30:45.123Z","level":"info","worker_id":0,"task_id":"T1.1","feature":"user-auth","phase":"execute","event":"task_started","message":"Task T1.1 started"}
```

Required fields: `ts`, `level`, `message`, `worker_id`, `feature`.
Optional fields: `task_id`, `phase`, `event`, `data`, `duration_ms`.

### Human-Readable Format (console output)

```
[10:30:45] [INFO ] W0 Task T1.1 started task_id=T1.1 phase=execute event=task_started
[10:31:12] [INFO ] W0 Verification passed task_id=T1.1 phase=verify event=verification_passed
[10:31:13] [INFO ] W0 Task T1.1 completed task_id=T1.1 event=task_completed
[10:31:45] [ERROR] W1 Task T1.3 failed task_id=T1.3 event=task_failed
```

### JSON Output (--json)

```json
{"ts":"2026-01-28T10:30:45.123Z","level":"info","worker_id":0,"message":"Task T1.1 started","task_id":"T1.1","phase":"execute","event":"task_started","feature":"user-auth"}
```

## Log Levels

| Level | Description | Color |
|-------|-------------|-------|
| debug | Detailed debugging information | dim |
| info | Normal operational messages | blue |
| warn | Warning conditions | yellow |
| error | Error conditions | red |

## Execution Phases

| Phase | Description |
|-------|-------------|
| claim | Worker claiming a task |
| execute | Claude Code invocation |
| verify | Running verification command |
| commit | Git commit of changes |
| cleanup | Post-task cleanup |

## Event Types

| Event | Description |
|-------|-------------|
| task_started | Task execution began |
| task_completed | Task finished successfully |
| task_failed | Task failed |
| verification_passed | Verification command passed |
| verification_failed | Verification command failed |
| artifact_captured | Artifact file written |
| level_started | Orchestrator started a level |
| level_complete | All tasks in level finished |
| merge_started | Branch merge began |
| merge_complete | Branch merge finished |

## Log Locations

### Structured JSONL Logs (new)
- **Worker logs**: `.zerg/logs/workers/worker-{id}.jsonl`
- **Orchestrator log**: `.zerg/logs/orchestrator.jsonl`

### Task Artifacts
- **Execution log**: `.zerg/logs/tasks/{TASK-ID}/execution.jsonl`
- **Claude output**: `.zerg/logs/tasks/{TASK-ID}/claude_output.txt`
- **Verification output**: `.zerg/logs/tasks/{TASK-ID}/verification_output.txt`
- **Git diff**: `.zerg/logs/tasks/{TASK-ID}/git_diff.patch`

### Legacy Logs
- **Worker logs**: `.zerg/logs/worker-{id}.log`

## Aggregation Mode

Use `--aggregate` to merge all worker JSONL files by timestamp. This performs read-side aggregation (no aggregated file on disk). Combine with filters:

```bash
# All structured logs, sorted by time
zerg logs --aggregate

# Only errors across all workers
zerg logs --aggregate --level error

# Task timeline
zerg logs --task T1.1

# Failed verifications
zerg logs --aggregate --event verification_failed

# Logs from worker 2 in verify phase
zerg logs 2 --aggregate --phase verify
```

## Task Artifacts

View captured artifacts for a specific task:

```bash
zerg logs --artifacts T1.1
```

This shows the contents of all artifact files:
- `claude_output.txt` — stdout/stderr from Claude Code
- `verification_output.txt` — verification command output
- `git_diff.patch` — changes committed
- `execution.jsonl` — structured event log

## Streaming Mode

Use `--follow` for real-time log streaming (legacy .log files):

```bash
zerg logs --follow
```

Press `Ctrl+C` to stop streaming.

## Task Tracking

On invocation, create a Claude Code Task to track this command:

Call TaskCreate:
  - subject: "[Logs] View worker logs"
  - description: "Viewing logs for {feature}. Filters: worker={worker_id}, level={level}."
  - activeForm: "Viewing worker logs"

Immediately call TaskUpdate:
  - taskId: (the Claude Task ID)
  - status: "in_progress"

On completion, call TaskUpdate:
  - taskId: (the Claude Task ID)
  - status: "completed"

## Integration with Other Commands

```bash
# Aggregate all errors
zerg logs --aggregate --level error

# Check why a task failed
zerg logs --task TASK-015

# View artifacts from failed task
zerg logs --artifacts TASK-015

# Monitor all workers in real-time
zerg logs --follow --level info

# Export structured logs for analysis
zerg logs --aggregate --json > logs.jsonl

# Clean up old logs
zerg cleanup --logs
```

## Help

When `--help` is passed in `$ARGUMENTS`, display usage and exit:

```
/zerg:logs — Stream, filter, and aggregate worker logs for debugging and monitoring.

Flags:
  WORKER_ID              Optional worker ID to filter logs
  -f, --feature TEXT     Feature name (auto-detected)
  -n, --tail INTEGER     Number of lines to show (default: 100)
  --follow               Stream new logs continuously
  -l, --level LEVEL      Filter by log level: debug|info|warn|error
  --json                 Output raw JSON format
  --aggregate            Merge all worker JSONL logs by timestamp
  --task TEXT            Filter to specific task ID
  --artifacts TEXT       Show artifact file contents for a task
  --phase TEXT           Filter by execution phase (claim/execute/verify/commit/cleanup)
  --event TEXT           Filter by event type (task_started, task_completed, etc.)
  --since TEXT           Only entries after this ISO8601 timestamp
  --until TEXT           Only entries before this ISO8601 timestamp
  --search TEXT          Text search in messages
  --help                Show this help message
```
