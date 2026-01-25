# ZERG Logs

Stream and filter worker logs for debugging and monitoring.

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
```

## Log Format

### Human-Readable Format

```
[10:30:45] [INFO ] W0 Claimed task TASK-001
[10:30:46] [INFO ] W0 Starting execution task_id=TASK-001
[10:31:12] [INFO ] W0 Verification passed task_id=TASK-001
[10:31:13] [INFO ] W0 Task complete task_id=TASK-001
[10:31:14] [WARN ] W1 Retry attempt retry=2 task_id=TASK-003
[10:31:45] [ERROR] W1 Verification failed task_id=TASK-003 error="Test timeout"
```

### JSON Format (--json)

```json
{
  "timestamp": "2026-01-25T10:30:45.123Z",
  "level": "info",
  "worker_id": 0,
  "message": "Claimed task TASK-001",
  "task_id": "TASK-001",
  "feature": "user-auth"
}
```

## Log Levels

| Level | Description | Color |
|-------|-------------|-------|
| debug | Detailed debugging information | dim |
| info | Normal operational messages | blue |
| warn | Warning conditions | yellow |
| error | Error conditions | red |

## Filtering Examples

```bash
# Only errors
zerg logs --level error

# Errors from worker 2
zerg logs 2 --level error

# Debug output (verbose)
zerg logs --level debug

# Last 500 lines
zerg logs --tail 500
```

## Log Locations

- **Worker logs**: `.zerg/logs/worker-{id}.log`
- **Orchestrator log**: `.zerg/logs/orchestrator.log`
- **Progress log**: `.gsd/specs/{feature}/progress.md`

## Streaming Mode

Use `--follow` for real-time log streaming:

```bash
zerg logs --follow
```

Press `Ctrl+C` to stop streaming.

## Integration with Other Commands

```bash
# Check why a task failed
zerg logs 2 --level error | grep TASK-015

# Monitor all workers in real-time
zerg logs --follow --level info

# Export logs for analysis
zerg logs --json > logs.jsonl
```
