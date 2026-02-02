<!-- SPLIT: details, parent: worker.md -->
# ZERG Worker Execution (Details)

Reference material, examples, error recovery, and protocol specifications for ZERG workers.

## Task Assignment Format

From worker-assignments.json:

```json
{
  "assignments": {
    "1": ["TASK-001", "TASK-003"],
    "2": ["TASK-005", "TASK-007"],
    "3": ["TASK-009"]
  }
}
```

## Dependency Checking (Step 3 Detail)

```
FOR each DEP in DEPS:
  IF DEP.status != "completed":
    WAIT or SKIP (dependency not ready)
```

## Reading Dependencies (Step 4.2)

```bash
# Read files this task depends on
for FILE in $FILES_READ; do
  cat "$FILE"
done
```

## Implementation Guidelines (Step 4.3)

Follow the design document exactly:
- Create files listed in `files.create`
- Modify files listed in `files.modify`
- Follow established patterns from the codebase
- Add clear comments explaining your implementation
- Ensure code is complete and working

## Failure Handling (Step 4.7 Detail)

If verification fails:

```bash
RETRY_COUNT=$((RETRY_COUNT + 1))

if [ $RETRY_COUNT -lt 3 ]; then
  echo "Retry $RETRY_COUNT/3..."
  # Re-read design, try different approach
  # Go back to step 4.3
else
  echo "Task blocked after 3 retries"
  # Mark task as blocked
  # Log detailed error information
  # Move to next task
fi
```

## Context Management (Step 5 Detail)

Monitor your context usage. **The 70% threshold is critical** for ensuring clean handoffs.

```
IF context_usage > 70%:

  # Commit any work in progress
  git add -A
  git commit -m "WIP: Context limit reached, handing off

  Worker: $WORKER_ID
  Last completed: $LAST_TASK_ID
  Next task: $NEXT_TASK_ID
  "

  # Log handoff state
  echo "Context limit reached at task $NEXT_TASK_ID" >> .gsd/specs/$FEATURE/progress.md

  # Exit cleanly (orchestrator will restart fresh instance)
  exit 0
```

## Level Completion (Step 6 Detail)

After completing all your tasks at a level:

```bash
# Signal completion
echo "Worker $WORKER_ID completed level $CURRENT_LEVEL"

# Wait for merge signal from orchestrator
# (Orchestrator merges all worker branches after all workers complete level)

# Pull merged result
git fetch origin
git rebase origin/zerg/FEATURE/staging

# Proceed to next level
```

## Communication Protocol

### Logging

Log all actions to progress file:

```bash
LOG_FILE=".gsd/specs/$FEATURE/progress.md"

log() {
  echo "[$(date -Iseconds)] Worker $WORKER_ID: $1" >> $LOG_FILE
}

log "Started task $TASK_ID"
log "Verification passed for $TASK_ID"
log "Committed $TASK_ID to branch $BRANCH"
```

### Error Reporting

On errors, provide detailed information:

```bash
log_error() {
  echo "[$(date -Iseconds)] Worker $WORKER_ID ERROR: $1" >> $LOG_FILE
  echo "  Command: $2" >> $LOG_FILE
  echo "  Exit code: $3" >> $LOG_FILE
  echo "  Output: $4" >> $LOG_FILE
}
```

## Quality Standards

Every task you complete must:

1. **Follow the design** - Implement exactly as specified in design.md
2. **Match patterns** - Use existing code patterns from the project
3. **Be complete** - No TODOs, no placeholders, no "implement later"
4. **Be verified** - Pass the verification command
5. **Be documented** - Include inline comments for complex logic
6. **Be typed** - Full TypeScript types, no `any`
7. **Handle errors** - Proper error handling, not just happy path

## Completion Output Format

```
═══════════════════════════════════════════════════════════════
              WORKER $WORKER_ID COMPLETE
═══════════════════════════════════════════════════════════════

Feature: $FEATURE
Tasks completed: {N}
Commits made: {N}
Duration: {time}

Final commit: {hash}

Worker shutting down.
═══════════════════════════════════════════════════════════════
```

## Heartbeat Protocol

Workers write heartbeat files every 15 seconds to `.zerg/state/heartbeat-{WORKER_ID}.json`:

```json
{
  "worker_id": 1,
  "timestamp": "2026-02-02T10:30:00Z",
  "task_id": "TASK-003",
  "step": "verifying_tier2",
  "progress_pct": 65
}
```

**Step values**: `initializing`, `loading_context`, `implementing`, `verifying_tier1`, `verifying_tier2`, `verifying_tier3`, `committing`, `idle`

The orchestrator detects stalled workers via heartbeat staleness (default: 120s timeout). Stalled workers are auto-restarted up to 2 times before task reassignment.

## Progress Reporting

Workers write progress to `.zerg/state/progress-{WORKER_ID}.json`:

```json
{
  "worker_id": 1,
  "tasks_completed": 2,
  "tasks_total": 5,
  "current_task": "TASK-003",
  "current_step": "implementing",
  "tier_results": [
    {"tier": 1, "name": "syntax", "success": true, "retry": 0},
    {"tier": 2, "name": "correctness", "success": false, "retry": 1}
  ]
}
```

## Escalation Protocol

When a failure is ambiguous (unclear spec, missing dependency, unclear verification), workers escalate instead of silently blocking. Write to `.zerg/state/escalations.json`:

```json
{
  "escalations": [
    {
      "worker_id": 1,
      "task_id": "TASK-003",
      "timestamp": "2026-02-02T10:32:00Z",
      "category": "ambiguous_spec",
      "message": "Spec says 'handle auth errors' but doesn't define error types",
      "context": {"attempted": ["TypeError catch", "generic Exception"], "verification_output": "..."},
      "resolved": false
    }
  ]
}
```

**Categories**: `ambiguous_spec`, `dependency_missing`, `verification_unclear`

The orchestrator auto-detects new escalations and alerts the terminal.

## Three-Tier Verification

Verification runs in three tiers, stopping on blocking failure:

| Tier | Name | Blocking | Purpose |
|------|------|----------|---------|
| 1 | syntax | Yes (default) | Linting, type checking, import validation |
| 2 | correctness | Yes (default) | Unit tests, task verification command |
| 3 | quality | No (default) | Code quality, coverage, style |

Tier commands are configured in `.zerg/config.yaml` under `verification_tiers`. If no tier 2 command is configured, the task's own `verification.command` is used.

## Exit Codes

Workers use specific exit codes to signal state to the orchestrator:

| Code | Constant | Meaning |
|------|----------|---------|
| 0 | SUCCESS | All assigned tasks completed successfully |
| 1 | ERROR | Unrecoverable error, check logs |
| 2 | CHECKPOINT | Context limit reached (70%), needs restart |
| 3 | BLOCKED | All remaining tasks blocked, intervention needed |
| 4 | ESCALATION | Worker escalated ambiguous failure |
| 130 | INTERRUPTED | Received stop signal, graceful shutdown |

## Task Claiming Protocol

Workers claim tasks atomically to prevent conflicts:

```python
# 1. Check task availability
task = state.get_pending_task(level=current_level, worker_id=my_id)

# 2. Atomic claim (returns False if already claimed)
if state.claim_task(task.id, worker_id=my_id):
    # 3. Execute task
    execute_task(task)
else:
    # Another worker claimed it, get next task
    continue
```

## WIP Commit Format

Work-in-progress commits follow a specific format for recovery:

```
WIP: ZERG [worker-{id}] checkpoint during {task_id}

Status: {percentage}% complete
Files modified:
  - path/to/file1.py (added)
  - path/to/file2.py (modified)

Resume context:
  - Current step: {description}
  - Next action: {what to do}
  - Blockers: {any issues}

Worker-ID: {id}
Feature: {feature}
Context-Usage: {percentage}%
```

## Protocol Specification

### Task State Transitions

```
PENDING → IN_PROGRESS → COMPLETE
                    ↘→ FAILED → PENDING (on retry)
                    ↘→ BLOCKED (after 3 failures)
                    ↘→ PAUSED (on checkpoint)
```

### Worker State Transitions

```
STARTING → RUNNING → STOPPED
              ↓         ↑
          CHECKPOINT ────┘
              ↓
           STALLED → auto-restart (up to 2x) → RUNNING
              ↓
           CRASHED (on error)
```

### Communication Channels

1. **Task System**: TaskList/TaskGet — authoritative task status
2. **State File**: `.zerg/state/{feature}.json` - supplementary shared state
3. **Progress Log**: `.gsd/specs/{feature}/progress.md` - human-readable log
4. **Worker Log**: `.zerg/logs/worker-{id}.log` - detailed worker output
5. **Event Stream**: State manager appends events for orchestrator
6. **Heartbeat**: `.zerg/state/heartbeat-{id}.json` - health monitoring
7. **Progress**: `.zerg/state/progress-{id}.json` - structured progress
8. **Escalations**: `.zerg/state/escalations.json` - shared escalation queue
