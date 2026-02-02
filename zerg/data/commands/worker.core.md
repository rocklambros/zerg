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
```

#### 4.1.1 Claim Task in Claude Task System

Before starting work, claim the task:

Call **TaskUpdate**:
  - taskId: (Claude Task ID for this ZERG task — find via **TaskList**, match subject prefix `[L{level}] {title}`)
  - status: "in_progress"
  - activeForm: "Worker {WORKER_ID} executing {title}"

This signals to other workers and the orchestrator that this task is actively being worked on.

#### 4.2-4.3 Read Dependencies & Implement

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
