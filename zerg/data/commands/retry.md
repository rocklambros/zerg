# ZERG Retry

Retry failed or blocked tasks.

## Pre-Flight

```bash
FEATURE=$(cat .gsd/.current-feature 2>/dev/null)
TASK_LIST=${CLAUDE_CODE_TASK_LIST_ID:-$FEATURE}
STATE_FILE=".zerg/state/$FEATURE.json"

# Validate prerequisites
[ -z "$FEATURE" ] && { echo "ERROR: No active feature"; exit 1; }
[ ! -f "$STATE_FILE" ] && { echo "ERROR: No state file found. Run /zerg:rush first"; exit 1; }
```

## Usage

```bash
# Retry all failed tasks
zerg retry

# Retry specific task
zerg retry TASK-001

# Retry with increased timeout
zerg retry --timeout 3600

# Retry and clear error state
zerg retry --reset
```

## Retry Protocol

### Step 1: Identify Failed Tasks

```bash
# Get failed tasks from state
jq -r '.tasks | to_entries[] | select(.value.status == "failed") | .key' "$STATE_FILE"
```

### Step 2: Analyze Failure

For each failed task:
1. Check error message in state
2. Review worker logs
3. Check if dependencies changed
4. Verify file ownership still valid

### Step 3: Reset Task State

```bash
# Reset task to pending
jq '.tasks["TASK-ID"].status = "pending" | .tasks["TASK-ID"].error = null | .tasks["TASK-ID"].retry_count += 1' "$STATE_FILE" > tmp && mv tmp "$STATE_FILE"
```

### Step 3.5: Update Claude Task System

After resetting state JSON, sync with Claude Code Tasks:

1. Call TaskList to find the task (match subject `[L{level}] {title}`)
2. Call TaskGet with the task ID to read current state
3. Call TaskUpdate:
   - taskId: the Claude Task ID
   - status: "pending"
   - description: Append "RETRY #{retry_count}: Reset at {timestamp}. Previous error: {error_summary}"

### Step 4: Check Retry Limits

```bash
MAX_RETRIES=$(jq '.workers.retry_attempts' .zerg/config.yaml)
CURRENT_RETRIES=$(jq '.tasks["TASK-ID"].retry_count // 0' "$STATE_FILE")

if [ "$CURRENT_RETRIES" -ge "$MAX_RETRIES" ]; then
  echo "WARNING: Task has exceeded retry limit ($MAX_RETRIES)"
  echo "Use --force to retry anyway, or investigate the root cause"
fi
```

### Step 5: Reassign to Worker

```bash
# Find available worker or restart one
WORKER=$(jq -r '.workers | to_entries[] | select(.value.status == "idle") | .key' "$STATE_FILE" | head -1)

if [ -n "$WORKER" ]; then
  # Assign to existing worker
  jq ".tasks[\"TASK-ID\"].worker_id = $WORKER" "$STATE_FILE" > tmp && mv tmp "$STATE_FILE"
else
  # Spawn new worker for retry
  python -m zerg.orchestrator retry-task --task TASK-ID --feature "$FEATURE"
fi
```

After reassigning the task, update the Claude Task:

Call TaskUpdate:
  - taskId: the Claude Task ID for this task
  - status: "in_progress"
  - activeForm: "Retrying {title}"

## Retry Strategies

### Single Task Retry
```bash
zerg retry TASK-001
```
- Resets task to pending
- Clears error state
- Increments retry counter
- Assigns to first available worker

### Level Retry
```bash
zerg retry --level 2
```
- Retries all failed tasks in level 2
- Useful after fixing a systemic issue
- Preserves successful tasks

### Full Retry
```bash
zerg retry --all
```
- Retries all failed and blocked tasks
- Use after major configuration change
- Resets error states across the board

### Force Retry
```bash
zerg retry --force TASK-001
```
- Bypasses retry limit check
- Use when you've fixed the underlying issue
- Resets retry counter to 0

## Output

```
═══════════════════════════════════════════════════════════════
                    ZERG RETRY
═══════════════════════════════════════════════════════════════

Feature: {feature}
State: .zerg/state/{feature}.json

Failed Tasks Found: 3

┌───────────┬──────────────────────────────┬─────────┬──────────────────────┐
│ Task ID   │ Title                        │ Retries │ Last Error           │
├───────────┼──────────────────────────────┼─────────┼──────────────────────┤
│ TASK-003  │ Create auth middleware       │ 2/3     │ Verification failed  │
│ TASK-007  │ Add user validation          │ 1/3     │ Worker crashed       │
│ TASK-012  │ Implement session management │ 0/3     │ Dependency not found │
└───────────┴──────────────────────────────┴─────────┴──────────────────────┘

Action: Retrying TASK-003...
  - Reset status: pending
  - Cleared error state
  - Assigned to Worker 2

Action: Retrying TASK-007...
  - Reset status: pending
  - Cleared error state
  - Assigned to Worker 0

Action: Retrying TASK-012...
  - Reset status: pending
  - Cleared error state
  - Assigned to Worker 1

═══════════════════════════════════════════════════════════════
Retry complete. 3 tasks queued for re-execution.

Run /zerg:status to monitor progress.
═══════════════════════════════════════════════════════════════
```

## CLI Flags

```
zerg retry [OPTIONS] [TASK_IDS]...

Arguments:
  TASK_IDS              Specific task IDs to retry (optional)

Options:
  -l, --level INTEGER   Retry all failed tasks in level
  -a, --all             Retry all failed tasks
  -f, --force           Bypass retry limit
  -t, --timeout INT     Override timeout for retry (seconds)
  --reset               Reset retry counters
  --dry-run             Show what would be retried
  -v, --verbose         Verbose output
```

## Error Investigation

Before retrying, investigate failures:

```bash
# View task error details
jq '.tasks["TASK-ID"]' "$STATE_FILE"

# View worker logs for task
cat ".zerg/logs/worker-N.log" | grep "TASK-ID"

# Check verification command output
cat ".zerg/logs/verification/TASK-ID.log"
```

## Common Failure Patterns

### Verification Failed
- Check verification command in task-graph.json
- Run command manually to debug
- May need to fix code before retry

### Worker Crashed
- Check worker logs for crash reason
- May be resource exhaustion (memory, disk)
- Restart with resource limits adjusted

### Dependency Not Found
- Check if dependency task completed successfully
- May need to retry dependency first
- Check file existence

### Timeout
- Task took longer than allowed
- Increase timeout with --timeout
- Or break task into smaller pieces

## Help

When `--help` is passed in `$ARGUMENTS`, display usage and exit:

```
/zerg:retry — Retry failed or blocked tasks.

Flags:
  TASK_IDS              Specific task IDs to retry (optional)
  -l, --level INTEGER   Retry all failed tasks in level
  -a, --all             Retry all failed tasks
  -f, --force           Bypass retry limit
  -t, --timeout INT     Override timeout for retry (seconds)
  --reset               Reset retry counters
  --dry-run             Show what would be retried
  -v, --verbose         Verbose output
  --help                Show this help message
```
