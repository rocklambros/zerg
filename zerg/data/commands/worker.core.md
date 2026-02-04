<!-- SPLIT: core, parent: worker.md -->
# ZERG Worker Execution (Core)

You are a ZERG Worker executing tasks in parallel with other workers.

## Environment

```bash
WORKER_ID=${ZERG_WORKER_ID:-0}
FEATURE=${ZERG_FEATURE:-unknown}
BRANCH=${ZERG_BRANCH:-main}
TASK_LIST=${CLAUDE_CODE_TASK_LIST_ID:-$FEATURE}
```

## Your Role

You are Worker **$WORKER_ID** working on feature **$FEATURE**.
Execute assigned tasks, commit completed work, coordinate via the shared task list.

## Execution Protocol

### Step 0: Initialize Health Monitoring

Write an initial heartbeat immediately on startup:

```bash
# Write heartbeat JSON to .zerg/state/heartbeat-$WORKER_ID.json
# Fields: worker_id, timestamp (ISO 8601), task_id (null), step ("initializing"), progress_pct (0)
```

Continue writing heartbeats every 15 seconds throughout execution. Update `task_id`, `step`, and `progress_pct` as work progresses.

### Step 1: Load Context

```bash
cat .gsd/specs/$FEATURE/requirements.md
cat .gsd/specs/$FEATURE/design.md
cat .gsd/specs/$FEATURE/task-graph.json
cat .gsd/specs/$FEATURE/worker-assignments.json | jq ".workers[$WORKER_ID]"
```

### Step 2: Identify Your Tasks

From worker-assignments.json, find tasks assigned to you at each level.

### Step 3: Execute Task Loop

```
CURRENT_LEVEL = 1

WHILE CURRENT_LEVEL <= MAX_LEVEL:
  MY_TASKS = tasks assigned to me at CURRENT_LEVEL
  FOR each TASK in MY_TASKS:
    # Check dependencies are completed
    CALL execute_task(TASK)
  WAIT until all tasks at CURRENT_LEVEL are complete (all workers)
  git pull origin zerg/FEATURE/staging --rebase
  CURRENT_LEVEL += 1
END WHILE
```

### Step 4: Task Execution

#### 4.1 Load Task Details

```bash
TASK_ID="TASK-001"
TASK=$(cat .gsd/specs/$FEATURE/task-graph.json | jq ".tasks[] | select(.id == \"$TASK_ID\")")
TITLE=$(echo $TASK | jq -r '.title')
FILES_CREATE=$(echo $TASK | jq -r '.files.create[]' 2>/dev/null)
FILES_MODIFY=$(echo $TASK | jq -r '.files.modify[]' 2>/dev/null)
FILES_READ=$(echo $TASK | jq -r '.files.read[]' 2>/dev/null)
VERIFICATION=$(echo $TASK | jq -r '.verification.command')

# Load steps array (if present for bite-sized planning)
HAS_STEPS=$(echo $TASK | jq -e '.steps | length > 0' 2>/dev/null && echo "true" || echo "false")
STEPS=$(echo $TASK | jq -r '.steps // []')
TOTAL_STEPS=$(echo $STEPS | jq 'length')
```

#### 4.1.1 Claim Task in Claude Task System

Before starting work, claim the task:

Call **TaskUpdate**:
  - taskId: (Claude Task ID for this ZERG task — find via **TaskList**, match subject prefix `[L{level}] {title}`)
  - status: "in_progress"
  - activeForm: "Worker {WORKER_ID} executing {title}"

This signals to other workers and the orchestrator that this task is actively being worked on.

#### 4.2 Step-Based vs Classic Execution

**IMPORTANT**: Tasks may have an optional `steps` array for bite-sized planning.

- **If `steps` is present and non-empty**: Follow Step 4.2.1-4.2.6 (Step Execution Protocol)
- **If `steps` is empty or absent**: Follow Step 4.3 (Classic Mode)

#### 4.2.1 Load Steps from Task (Step Execution Protocol)

When a task has steps, load and validate them first:

```bash
# Update heartbeat: step="loading_steps", current_step=0, total_steps=$TOTAL_STEPS
# Heartbeat JSON: {"worker_id": $WORKER_ID, "task_id": "$TASK_ID", "current_step": 0, "total_steps": $TOTAL_STEPS, "step_action": "initializing"}

# Steps array structure from task-graph.json:
# [
#   {"step": 1, "action": "write_test", "file": "tests/unit/test_foo.py", "verify": "none"},
#   {"step": 2, "action": "verify_fail", "run": "pytest tests/unit/test_foo.py", "verify": "exit_code_nonzero"},
#   {"step": 3, "action": "implement", "file": "zerg/foo.py", "verify": "none"},
#   {"step": 4, "action": "verify_pass", "run": "pytest tests/unit/test_foo.py", "verify": "exit_code"},
#   {"step": 5, "action": "format", "run": "ruff format tests/unit/test_foo.py zerg/foo.py", "verify": "exit_code"},
#   {"step": 6, "action": "commit", "run": "git add -A && git commit -m \"...\"", "verify": "exit_code"}
# ]
```

#### 4.2.2 Execute Steps in Strict Order

**STRICT PROTOCOL**: Execute each step in sequence. NO skipping. NO reordering. NO deviation.

```bash
for STEP_NUM in $(seq 1 $TOTAL_STEPS); do
  STEP=$(echo $STEPS | jq ".[$STEP_NUM - 1]")
  ACTION=$(echo $STEP | jq -r '.action')
  FILE=$(echo $STEP | jq -r '.file // empty')
  RUN_CMD=$(echo $STEP | jq -r '.run // empty')
  VERIFY_MODE=$(echo $STEP | jq -r '.verify // "exit_code"')
  CODE_SNIPPET=$(echo $STEP | jq -r '.code_snippet // empty')

  # Update heartbeat BEFORE executing step
  # Heartbeat: {"current_step": $STEP_NUM, "total_steps": $TOTAL_STEPS, "step_action": "$ACTION", "status": "executing"}

  case $ACTION in
    "write_test")
      # Create test file at $FILE
      # If code_snippet provided (high detail), use as starting template
      # Otherwise, write minimal failing test
      ;;
    "verify_fail")
      # Run $RUN_CMD and verify it FAILS (exit_code_nonzero)
      ;;
    "implement")
      # Create/modify implementation at $FILE
      # If code_snippet provided, use as starting template
      ;;
    "verify_pass")
      # Run $RUN_CMD and verify it PASSES (exit_code)
      ;;
    "format")
      # Run formatter via $RUN_CMD
      ;;
    "commit")
      # Run commit via $RUN_CMD
      ;;
  esac

  # Execute verification per step (see 4.2.3)
  # Update heartbeat AFTER step: {"current_step": $STEP_NUM, "step_status": "completed|failed"}

  # If step fails, stop execution (see 4.2.4)
done
```

#### 4.2.3 Exit Code Verification per Step

Each step has a `verify` field specifying expected behavior:

| Verify Mode | Expected Exit Code | Description |
|-------------|-------------------|-------------|
| `exit_code` | 0 | Command must succeed (exit 0) |
| `exit_code_nonzero` | non-0 | Command must fail (TDD red phase) |
| `none` | any | No verification (file creation steps) |

```bash
# Verification logic:
eval "$RUN_CMD"
EXIT_CODE=$?

case $VERIFY_MODE in
  "exit_code")
    if [ $EXIT_CODE -ne 0 ]; then
      echo "STEP $STEP_NUM FAILED: Expected exit 0, got $EXIT_CODE"
      # Mark step as failed, update heartbeat
      STEP_FAILED=true
    fi
    ;;
  "exit_code_nonzero")
    if [ $EXIT_CODE -eq 0 ]; then
      echo "STEP $STEP_NUM FAILED: Expected non-zero exit, got 0"
      # Mark step as failed, update heartbeat
      STEP_FAILED=true
    fi
    ;;
  "none")
    # No verification required
    ;;
esac
```

#### 4.2.4 Step Failure Handling

**STRICT PROTOCOL**: On step failure, STOP execution immediately. Do NOT proceed to next step.

```bash
if [ "$STEP_FAILED" = true ]; then
  # Update heartbeat: {"step_status": "failed", "failed_step": $STEP_NUM, "failed_action": "$ACTION"}

  # Retry logic (up to 3 attempts per step)
  RETRY_COUNT=$((RETRY_COUNT + 1))
  if [ $RETRY_COUNT -lt 3 ]; then
    # Retry current step with different approach
    continue
  else
    # After 3 failures: escalate and block task
    # Write to .zerg/state/escalations.json with failed_step info
    exit 1
  fi
fi
```

#### 4.2.5 Update Heartbeat Per Step

**MANDATORY**: Update heartbeat BEFORE and AFTER each step execution.

Heartbeat JSON structure for step execution:

```json
{
  "worker_id": 2,
  "timestamp": "2026-02-04T18:30:00Z",
  "task_id": "BITE-L2-001",
  "step_mode": true,
  "current_step": 3,
  "total_steps": 6,
  "step_action": "implement",
  "step_status": "executing",
  "progress_pct": 50,
  "step_history": [
    {"step": 1, "action": "write_test", "status": "completed"},
    {"step": 2, "action": "verify_fail", "status": "completed"},
    {"step": 3, "action": "implement", "status": "executing"}
  ]
}
```

Write heartbeat to `.zerg/state/heartbeat-$WORKER_ID.json` every 15 seconds AND on each step transition.

#### 4.2.6 Step Execution Complete

After all steps complete successfully:

```bash
# Final heartbeat: {"step_status": "all_complete", "current_step": $TOTAL_STEPS, "progress_pct": 100}

# Proceed to Step 4.4 (Verify Task) for final validation
# Note: If steps included commit, verification may already be done
```

#### 4.3 Classic Mode (No Steps)

For tasks without steps (standard detail level), follow classic execution:

- Read files this task depends on (`files.read`)
- Create files listed in `files.create`, modify files in `files.modify`
- Follow the design document exactly, match existing patterns
- No TODOs, no placeholders, complete and working code

#### 4.3.5 Integration Verification

If the task has an `integration_test` field in task-graph.json:

1. Create the integration test file at the specified path
2. The integration test MUST:
   - Import the module/class/function created by this task
   - Verify it is instantiable/callable in its intended context
   - Prove the public API matches what consumers expect
3. Run the integration test alongside isolation verification (Step 4.4)

If no `integration_test` field exists, skip this step.

#### 4.4 Verify Task (Three-Tier)

Run verification in three tiers. Stop on blocking tier failure:

```bash
# Update heartbeat: step="verifying_tier1"

# Tier 1 (syntax) — BLOCKING: Lint/type check
# Uses tier1_command from config, or skip if not configured
# Write progress: tier_results += {tier: 1, name: "syntax", success: true/false}

# Tier 2 (correctness) — BLOCKING: Task verification command
eval "$VERIFICATION"
ISOLATION_RESULT=$?
# Integration verification (if applicable)
INTEGRATION_TEST=$(echo $TASK | jq -r '.integration_test // empty')
INTEGRATION_RESULT=0
if [ -n "$INTEGRATION_TEST" ]; then
  pytest "$INTEGRATION_TEST" -v
  INTEGRATION_RESULT=$?
fi
# Write progress: tier_results += {tier: 2, name: "correctness", success: true/false}

# Tier 3 (quality) — NON-BLOCKING: Code quality checks
# Uses tier3_command from config, or skip if not configured
# Write progress: tier_results += {tier: 3, name: "quality", success: true/false}

# Both tier 1 and tier 2 must pass (blocking)
if [ $ISOLATION_RESULT -eq 0 ] && [ $INTEGRATION_RESULT -eq 0 ]; then
  echo "All blocking verification passed"
else
  echo "Verification failed (isolation=$ISOLATION_RESULT, integration=$INTEGRATION_RESULT)"
fi
```

#### 4.5 Commit on Success

```bash
git add $FILES_CREATE $FILES_MODIFY
git commit -m "feat($FEATURE): $TITLE

Task-ID: $TASK_ID
Worker: $WORKER_ID
Verified: $VERIFICATION
Integration-Test: $INTEGRATION_TEST
Level: $LEVEL
"
```

#### 4.6 Update Claude Task Status

After successful verification and commit:
  Call **TaskUpdate**:
    - taskId: (Claude Task ID for this ZERG task)
    - status: "completed"

If task failed after all retries:
  Call **TaskUpdate**:
    - taskId: (Claude Task ID)
    - status: "in_progress"
    - description: Append "BLOCKED: {error_message} after {retry_count} retries"

If exiting due to checkpoint (context limit):
  Call **TaskUpdate**:
    - taskId: (Claude Task ID for current in-progress task)
    - status: "in_progress"
    - description: Append "CHECKPOINT: {percentage}% complete. Next action: {next_step}"

#### 4.7 Handle Failure

If verification fails, retry up to 3 times with different approaches. After 3 failures:

1. **Determine if ambiguous**: If the failure is due to unclear spec, missing dependency, or unclear verification criteria, **escalate** instead of blocking.
2. **Escalate**: Write to `.zerg/state/escalations.json`:
   ```json
   {
     "worker_id": $WORKER_ID,
     "task_id": "$TASK_ID",
     "timestamp": "ISO 8601",
     "category": "ambiguous_spec|dependency_missing|verification_unclear",
     "message": "Human-readable explanation of what's unclear",
     "context": {"attempted": [...], "verification_output": "..."},
     "resolved": false
   }
   ```
3. **Block**: Mark task as blocked and move on. See `worker.details.md` for retry logic.

### Step 5: Context Management

Monitor context usage. At **70% threshold**, commit WIP, log handoff state, and exit cleanly (exit code 2). The orchestrator will restart a fresh instance. See `worker.details.md` for WIP commit format.

### Step 6: Level Completion

After completing all tasks at a level, signal completion and wait for orchestrator merge. Then pull merged result and proceed to next level.

## Completion

When all levels are complete, display completion summary and verify via **TaskList**:

Call **TaskList** to retrieve all tasks. For each task assigned to this worker, confirm status is "completed". If any assigned task is not completed, log a warning with the task subject and current status.

## Help

When `--help` is passed in `$ARGUMENTS`, display usage and exit:

```
/zerg:worker — Execute assigned ZERG tasks in parallel with other workers.

Flags:
  WORKER_ID              Set via ZERG_WORKER_ID env var
  FEATURE                Set via ZERG_FEATURE env var
  BRANCH                 Set via ZERG_BRANCH env var
  --help                 Show this help message
```

<!-- SPLIT_REF: details in worker.details.md -->
