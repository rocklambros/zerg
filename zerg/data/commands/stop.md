# ZERG Stop

Stop ZERG workers gracefully or forcefully.

## Usage

```bash
# Stop all workers gracefully
zerg stop

# Stop specific worker
zerg stop --worker 2

# Force immediate termination
zerg stop --force

# Stop specific feature
zerg stop --feature user-auth
```

## CLI Flags

```
zerg stop [OPTIONS]

Options:
  -f, --feature TEXT     Feature to stop (auto-detected)
  -w, --worker INTEGER   Stop specific worker only
  --force                Force immediate termination (no checkpoint)
  --timeout INTEGER      Graceful shutdown timeout in seconds (default: 30)
```

## Graceful vs Force Stop

### Graceful Stop (Default)

1. Sends checkpoint signal to workers
2. Workers commit any in-progress work (WIP commit)
3. Workers update state with checkpoint info
4. Containers stop cleanly
5. State preserved for resume

```bash
zerg stop
```

### Force Stop (--force)

1. Immediately terminates containers
2. No WIP commits made
3. In-progress tasks marked as failed
4. May lose uncommitted work

```bash
zerg stop --force
```

## Checkpoint Behavior

When stopped gracefully, workers:

1. **Commit WIP**: Creates checkpoint commit with current progress
2. **Update State**: Marks current task as PAUSED
3. **Log Context**: Records where to resume
4. **Clean Exit**: Exits with code 2 (CHECKPOINT)

### WIP Commit Format

```
WIP: ZERG [worker-{id}] checkpoint during {task_id}

Status: {percentage}% complete
Files modified:
  - path/to/file1.py (added)

Worker-ID: {id}
Feature: {feature}
Context-Usage: {percentage}%
```

## Cross-Session Coordination

```bash
FEATURE=$(cat .gsd/.current-feature 2>/dev/null)
TASK_LIST=${CLAUDE_CODE_TASK_LIST_ID:-$FEATURE}
```

## Task System Updates

After checkpoint/stop completes, update Claude Code Tasks to reflect stopped state:

**Graceful Stop:**
1. Call TaskList to find all in_progress tasks
2. For each in_progress task, call TaskUpdate:
   - taskId: the task's Claude Task ID
   - description: Append "PAUSED: Graceful stop at {timestamp}. Resume with /zerg:rush --resume"
   - (Keep status as "in_progress" — no "paused" status exists in the Task system)

**Force Stop (--force):**
1. Call TaskList to find all in_progress tasks
2. For each in_progress task, call TaskUpdate:
   - taskId: the task's Claude Task ID
   - description: Append "FORCE STOPPED: {timestamp}. Uncommitted work may be lost."
   - (Keep status as "in_progress" — orchestrator will decide next action on resume)

## Recovery After Stop

Resume execution:

```bash
# Resume from checkpoint
zerg rush --resume

# Resume with different worker count
zerg rush --resume --workers 3
```

Check state:

```bash
# See what was in progress
zerg status

# Check for blocked tasks
zerg status --json | jq '.tasks | map(select(.status == "paused"))'
```

## Stopping Specific Workers

```bash
# Stop only worker 2
zerg stop --worker 2

# Force stop worker 2
zerg stop --worker 2 --force
```

Other workers continue executing.

## Timeout Handling

Default timeout is 30 seconds for graceful shutdown.

```bash
# Wait longer for checkpoint
zerg stop --timeout 60

# Quick timeout
zerg stop --timeout 10
```

If timeout expires, remaining workers are force-stopped.

## State After Stop

| Component | Graceful | Force |
|-----------|----------|-------|
| Containers | Stopped | Killed |
| Worktrees | Preserved | Preserved |
| State file | Updated | May be stale |
| Current tasks | PAUSED | FAILED |
| WIP changes | Committed | Lost |

## Examples

```bash
# Lunch break - stop gracefully
zerg stop

# Emergency - stop immediately
zerg stop --force

# Stop problematic worker
zerg stop --worker 3 --force

# Clean stop with extra time
zerg stop --timeout 60
```

## Integration

After stopping:

```bash
# Check final status
zerg status

# View logs for issues
zerg logs --level error

# Retry failed tasks
zerg retry --all-failed

# Resume execution
zerg rush --resume

# Full cleanup
zerg cleanup --feature my-feature
```

## Help

When `--help` is passed in `$ARGUMENTS`, display usage and exit:

```
/zerg:stop — Stop ZERG workers gracefully or forcefully.

Flags:
  -f, --feature TEXT     Feature to stop (auto-detected)
  -w, --worker INTEGER   Stop specific worker only
  --force                Force immediate termination (no checkpoint)
  --timeout INTEGER      Graceful shutdown timeout in seconds (default: 30)
  --help                 Show this help message
```
