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

## Exit Codes

Workers use specific exit codes to signal state to the orchestrator:

| Code | Constant | Meaning |
|------|----------|---------|
| 0 | SUCCESS | All assigned tasks completed successfully |
| 1 | ERROR | Unrecoverable error, check logs |
| 2 | CHECKPOINT | Context limit reached (70%), needs restart |
| 3 | BLOCKED | All remaining tasks blocked, intervention needed |
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
           CRASHED (on error)
```

### Communication Channels

1. **State File**: `.zerg/state/{feature}.json` - shared task state
2. **Progress Log**: `.gsd/specs/{feature}/progress.md` - human-readable log
3. **Worker Log**: `.zerg/logs/worker-{id}.log` - detailed worker output
4. **Event Stream**: State manager appends events for orchestrator
