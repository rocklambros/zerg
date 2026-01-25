# ZERG Status

Display current factory execution status.

## Load State

```bash
FEATURE=$(cat .gsd/.current-feature 2>/dev/null)
SPEC_DIR=".gsd/specs/$FEATURE"

if [ -z "$FEATURE" ]; then
  echo "No active feature"
  exit 0
fi

# Check if orchestrator is running
ORCH_PID=$(cat .zerg/.orchestrator.pid 2>/dev/null)
if [ -n "$ORCH_PID" ] && kill -0 $ORCH_PID 2>/dev/null; then
  ORCH_STATUS="Running (PID: $ORCH_PID)"
else
  ORCH_STATUS="Not running"
fi
```

## Generate Status Report

```
═══════════════════════════════════════════════════════════════════════════════
                         FACTORY STATUS
═══════════════════════════════════════════════════════════════════════════════

Feature:      {feature}
Phase:        {phase: PLANNING | DESIGNING | EXECUTING | MERGING | COMPLETE}
Orchestrator: {orch_status}
Started:      {start_time}
Elapsed:      {elapsed_time}

───────────────────────────────────────────────────────────────────────────────
                              PROGRESS
───────────────────────────────────────────────────────────────────────────────

Overall: {progress_bar} {percent}% ({completed}/{total} tasks)

Level 1 (Foundation):   {bar} {status} ({n}/{n} tasks)
Level 2 (Core):         {bar} {status} ({n}/{n} tasks)
Level 3 (Integration):  {bar} {status} ({n}/{n} tasks)
Level 4 (Testing):      {bar} {status} ({n}/{n} tasks)
Level 5 (Quality):      {bar} {status} ({n}/{n} tasks)

───────────────────────────────────────────────────────────────────────────────
                              WORKERS
───────────────────────────────────────────────────────────────────────────────

┌──────────┬────────┬────────────┬─────────────┬───────────┬──────────────────┐
│ Worker   │ Port   │ Status     │ Task        │ Progress  │ Tasks Done       │
├──────────┼────────┼────────────┼─────────────┼───────────┼──────────────────┤
│ worker-0 │ 49152  │ 🟢 Running │ TASK-007    │ Verifying │ 3/6              │
│ worker-1 │ 49153  │ 🟢 Running │ TASK-008    │ Coding    │ 2/5              │
│ worker-2 │ 49154  │ 🟡 Idle    │ -           │ Waiting   │ 4/4              │
│ worker-3 │ 49155  │ 🔴 Failed  │ TASK-009    │ Blocked   │ 2/4              │
│ worker-4 │ 49156  │ 🟢 Running │ TASK-010    │ Coding    │ 2/5              │
└──────────┴────────┴────────────┴─────────────┴───────────┴──────────────────┘

───────────────────────────────────────────────────────────────────────────────
                            RECENT ACTIVITY
───────────────────────────────────────────────────────────────────────────────

{timestamp}  worker-1  TASK-006  ✅ Completed (8m 23s)
{timestamp}  worker-0  TASK-005  ✅ Completed (12m 47s)
{timestamp}  worker-3  TASK-009  ❌ Failed: Verification timeout
{timestamp}  MERGE     Level 1   ✅ Merged successfully
{timestamp}  worker-2  TASK-003  ✅ Completed (6m 12s)

───────────────────────────────────────────────────────────────────────────────
                            BLOCKED TASKS
───────────────────────────────────────────────────────────────────────────────

TASK-009: Implement rate limiter
  Worker: worker-3
  Error: Verification failed after 3 retries
  Last error: "RateLimiter.limit is not a function"
  Action: Review implementation, fix error, run /zerg:unblock TASK-009

───────────────────────────────────────────────────────────────────────────────
                            ESTIMATES
───────────────────────────────────────────────────────────────────────────────

Remaining tasks:    {n}
Estimated time:     {time} (at current pace)
Projected finish:   {timestamp}

═══════════════════════════════════════════════════════════════════════════════

Commands:
  /zerg:logs {N}      View logs from worker N
  /zerg:stop          Stop all workers
  /zerg:unblock {ID}  Retry a blocked task
  /zerg:scale {N}     Change number of workers

═══════════════════════════════════════════════════════════════════════════════
```

## Data Sources

### Task Status from Native Tasks

```bash
# Read from Claude Code's native Tasks
# CLAUDE_CODE_TASK_LIST_ID is set to feature name
```

### Worker Status from Docker

```bash
# Check container status
for i in $(seq 0 $((WORKERS - 1))); do
  STATUS=$(docker inspect -f '{{.State.Status}}' "factory-$FEATURE-worker-$i" 2>/dev/null || echo "not found")
  echo "worker-$i: $STATUS"
done
```

### Progress from Git

```bash
# Count commits per worker branch
for i in $(seq 0 $((WORKERS - 1))); do
  BRANCH="zerg/FEATURE/worker-$i"
  COUNT=$(git rev-list --count "zerg/FEATURE/base..$BRANCH" 2>/dev/null || echo 0)
  echo "worker-$i: $COUNT commits"
done
```

### Activity from Progress Log

```bash
# Read recent entries from progress file
tail -20 ".gsd/specs/$FEATURE/progress.md"
```

## Detailed Views

### /zerg:status --tasks

Show all tasks with their status:

```
┌───────────┬────────────────────────────────────┬─────────┬──────────┬──────────┐
│ Task ID   │ Title                              │ Level   │ Status   │ Worker   │
├───────────┼────────────────────────────────────┼─────────┼──────────┼──────────┤
│ TASK-001  │ Create auth types                  │ 1       │ ✅ Done  │ worker-0 │
│ TASK-002  │ Create user schema                 │ 1       │ ✅ Done  │ worker-1 │
│ TASK-003  │ Implement auth service             │ 2       │ ✅ Done  │ worker-2 │
│ TASK-004  │ Create password hashing            │ 2       │ ✅ Done  │ worker-0 │
│ TASK-005  │ Implement session service          │ 2       │ 🔄 WIP   │ worker-1 │
│ TASK-006  │ Create auth routes                 │ 3       │ ⏳ Wait  │ -        │
│ TASK-007  │ Create auth middleware             │ 3       │ ⏳ Wait  │ -        │
│ TASK-008  │ Implement rate limiter             │ 3       │ ❌ Block │ worker-3 │
└───────────┴────────────────────────────────────┴─────────┴──────────┴──────────┘
```

### /zerg:status --workers

Show detailed worker information:

```
Worker 0 (worker-0)
  Container: factory-auth-worker-0
  Port: 49152
  Branch: factory/auth/worker-0
  Status: Running
  Current task: TASK-007
  Tasks completed: 3
  Last activity: 2m ago
  
Worker 1 (worker-1)
  Container: factory-auth-worker-1
  Port: 49153
  Branch: factory/auth/worker-1
  Status: Running
  Current task: TASK-008
  Tasks completed: 2
  Last activity: 30s ago
  
...
```

### /zerg:status --commits

Show recent commits:

```
factory/auth/worker-0:
  abc1234 feat(auth): Create auth types (TASK-001)
  def5678 feat(auth): Create password hashing (TASK-004)
  
factory/auth/worker-1:
  ghi9012 feat(auth): Create user schema (TASK-002)
  jkl3456 feat(auth): Implement session service (TASK-005) [WIP]
```