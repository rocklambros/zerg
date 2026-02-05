# ZERG Launch

Launch parallel workers to execute the task graph.

## Pre-Flight

```bash
FEATURE=$(cat .gsd/.current-feature 2>/dev/null)
TASK_LIST=${CLAUDE_CODE_TASK_LIST_ID:-$FEATURE}
SPEC_DIR=".gsd/specs/$FEATURE"

# Validate prerequisites
[ -z "$FEATURE" ] && { echo "ERROR: No active feature"; exit 1; }
[ ! -f "$SPEC_DIR/task-graph.json" ] && { echo "ERROR: Task graph not found. Run /zerg:design first"; exit 1; }

# Load configuration
WORKERS=${1:-5}  # Default 5 workers
MAX_WORKERS=10

if [ "$WORKERS" -gt "$MAX_WORKERS" ]; then
  echo "WARNING: Limiting to $MAX_WORKERS workers"
  WORKERS=$MAX_WORKERS
fi
```

## Step 1: Mode Detection

Parse `$ARGUMENTS` to determine execution mode:

```
MODE="task"  # DEFAULT

IF $ARGUMENTS contains "--mode container":
  MODE="container"
ELSE IF $ARGUMENTS contains "--mode subprocess":
  MODE="subprocess"
ELSE IF $ARGUMENTS contains "--mode task":
  MODE="task"
# No --mode flag = task mode (default for slash commands)
```

**Mode Summary:**
- `task` (default): Execute via parallel Task tool subagents. No external processes.
- `container`: Execute via Python Orchestrator with Docker containers and git worktrees.
- `subprocess`: Execute via Python Orchestrator with local Python subprocesses.

---

## Step 2: Task Tool Mode (Default)

**IF MODE == "task":**

This is the default execution path for `/zerg:rush` slash commands. The orchestrator (you) drives execution directly through the Task tool. No external processes are spawned.

### 2.1: Analyze Task Graph

```bash
TASKS=$(jq '.total_tasks' "$SPEC_DIR/task-graph.json")
MAX_PARALLEL=$(jq '.max_parallelization' "$SPEC_DIR/task-graph.json")
LEVELS=$(jq '.levels | keys | length' "$SPEC_DIR/task-graph.json")

echo "Feature: $FEATURE"
echo "Tasks: $TASKS across $LEVELS levels"
echo "Max parallelization: $MAX_PARALLEL"
echo "Workers: $WORKERS"
```

### 2.2: Register Tasks in Claude Task System

FOR each task in task-graph.json:

Call TaskCreate:
  - subject: "[L{level}] {title}"
  - description: "{description}\n\nFiles: {files.create + files.modify}\nVerification: {verification.command}"
  - activeForm: "Executing {title}"

After all TaskCreate calls, wire dependencies using TaskUpdate:
  - For each task with dependencies, call TaskUpdate with addBlockedBy

Verify with TaskList that all tasks appear correctly.

**Resume Logic (`--resume`):**
- Call TaskList first
- Only create tasks that don't already exist (match by subject prefix `[L{level}] {title}`)
- Skip tasks with status "completed"

### 2.3: Level Execution Loop

```
FOR each level in task-graph.json (ascending order):

  1. Collect all tasks at this level

  2. Batch tasks by WORKERS count:
     IF tasks > WORKERS:
       Split into batches of WORKERS
     ELSE:
       Single batch = all tasks

  3. FOR each batch:

     a. Mark tasks in_progress:
        FOR each task in batch:
          Call TaskUpdate(taskId, status="in_progress")

     b. Launch all tasks as parallel Task tool calls:
        Send a SINGLE message with multiple Task tool invocations:

        Task(
          description: "Execute {TASK_ID}: {title}",
          subagent_type: "general-purpose",
          prompt: [Subagent prompt - see 2.4 below]
        )

        All Task calls in the same message execute in parallel.

     c. Wait for all to return

     d. Record results:
        FOR each returned task:
          IF success:
            Call TaskUpdate(taskId, status="completed")
          ELSE:
            Record as failed

  4. Handle failures:
     FOR each failed task:
       - Retry ONCE with error context appended to prompt
       - IF retry succeeds: mark completed
       - IF retry fails: mark blocked, log warning, continue

     IF ALL tasks at this level failed:
       ABORT execution with diagnostics

  5. Run quality gates:
     ```bash
     # Run lint and typecheck on modified files
     make lint 2>/dev/null || npm run lint 2>/dev/null || true
     make typecheck 2>/dev/null || npm run typecheck 2>/dev/null || true
     ```

     IF critical gate fails: ABORT with diagnostics

  6. Proceed to next level

END FOR
```

### 2.4: Subagent Prompt Template

Each Task tool call uses `subagent_type: "general-purpose"` with this prompt:

```
You are ZERG Worker executing task {TASK_ID} for feature "{FEATURE}".

## Task
- **ID**: {TASK_ID}
- **Title**: {title}
- **Description**: {description}
- **Level**: {level}

## Files
- **Create**: {files.create}
- **Modify**: {files.modify}
- **Read (context only)**: {files.read}

IMPORTANT: Only touch files listed above. Other files are owned by other tasks.

## Design Context
Read these files for architectural guidance:
- .gsd/specs/{FEATURE}/requirements.md
- .gsd/specs/{FEATURE}/design.md
- .gsd/specs/{FEATURE}/task-graph.json (your task entry)

## Acceptance Criteria
{acceptance_criteria from task-graph.json}

## Verification
After implementation, run:
```
{verification.command}
```
Expected: exit code 0

## On Completion
1. Stage ONLY your owned files: git add {files.create + files.modify}
2. Commit with message: "feat({FEATURE}): {TASK_ID} - {title}"
3. Report: list files changed, verification result, any warnings
```

### 2.5: Completion

After all levels complete:

```
═══════════════════════════════════════════════════════════════
                    EXECUTION COMPLETE
═══════════════════════════════════════════════════════════════

Feature: {FEATURE}
Mode: Task Tool

Results:
  • Completed: {N} tasks
  • Blocked: {N} tasks
  • Levels: {N}

Time: {elapsed}

Next steps:
  /zerg:status    - View final state
  /zerg:review    - Code review
  /zerg:merge     - Merge to main

═══════════════════════════════════════════════════════════════
```

**END IF (MODE == "task")**

---

## Step 3: Container/Subprocess Mode (Explicit Only)

**IF MODE == "container" OR MODE == "subprocess":**

> These modes require explicit `--mode container` or `--mode subprocess` flag.

### 3.1: Create Worker Branches

For each worker, create a dedicated git worktree:

```bash
# Base branch for the feature
git checkout -b "zerg/$FEATURE/base" 2>/dev/null || git checkout "zerg/$FEATURE/base"

# Create worktrees for each worker
for i in $(seq 0 $((WORKERS - 1))); do
  BRANCH="zerg/$FEATURE/worker-$i"
  WORKTREE="../.zerg-worktrees/$FEATURE/worker-$i"

  mkdir -p "$(dirname $WORKTREE)"

  # Create branch if doesn't exist
  git branch "$BRANCH" 2>/dev/null || true

  # Create worktree
  git worktree add "$WORKTREE" "$BRANCH" 2>/dev/null || {
    git worktree remove "$WORKTREE" --force 2>/dev/null
    git worktree add "$WORKTREE" "$BRANCH"
  }
done
```

### 3.2: Partition Tasks

Assign tasks to workers based on:
1. Level (all Level 1 before Level 2)
2. File ownership (no conflicts)
3. Load balancing (distribute evenly)

Generate: `.gsd/specs/{feature}/worker-assignments.json`

### 3.3: Register Tasks in Claude Task System

FOR each task in task-graph.json, call TaskCreate:
  - subject: "[L{level}] {title}"
  - description: "{description}\n\nFiles: {files.create + files.modify}\nVerification: {verification.command}"
  - activeForm: "Executing {title}"

Wire dependencies using TaskUpdate(addBlockedBy).

### 3.4: Launch Workers

**IF MODE == "container":**

```bash
# Allocate ports and launch Docker containers
BASE_PORT=49152
for i in $(seq 0 $((WORKERS - 1))); do
  PORT=$((BASE_PORT + i))

  docker compose -f .devcontainer/docker-compose.yaml run \
    --detach \
    --name "factory-worker-$i" \
    -e ZERG_WORKER_ID=$i \
    -e ZERG_FEATURE=$FEATURE \
    -e CLAUDE_CODE_TASK_LIST_ID=${CLAUDE_CODE_TASK_LIST_ID:-} \
    -p "$PORT:$PORT" \
    -v "$(realpath $WORKTREE):/workspace" \
    workspace \
    bash -c "claude --dangerously-skip-permissions -p 'You are ZERG Worker $i. Run /zerg:worker to begin execution.'"
done
```

**ELSE IF MODE == "subprocess":**

Invoke the Python Orchestrator:

```python
from zerg.orchestrator import Orchestrator
orch = Orchestrator(feature=FEATURE, launcher_mode="subprocess")
orch.start(task_graph_path=f".gsd/specs/{FEATURE}/task-graph.json", worker_count=WORKERS)
```

### 3.5: Start Orchestrator

Launch the orchestration process:

```bash
python3 -m zerg.orchestrator \
  --feature "$FEATURE" \
  --workers "$WORKERS" \
  --config ".zerg/config.yaml" \
  --task-graph "$SPEC_DIR/task-graph.json" \
  --assignments "$SPEC_DIR/worker-assignments.json" \
  &

ORCHESTRATOR_PID=$!
echo $ORCHESTRATOR_PID > ".zerg/.orchestrator.pid"
```

### Monitoring During Execution

> Slash commands are single-threaded — you cannot run `/zerg:status` in this session while rush is active.

Tell the user to open a **separate terminal** for live monitoring:

```bash
# Recommended: live TUI dashboard
zerg status --dashboard

# Lighter text-based refresh
zerg status --watch --interval 2

# One-shot check
zerg status
```

**END IF (MODE == "container" OR MODE == "subprocess")**

---

## Help

When `--help` is passed in `$ARGUMENTS`, display usage and exit:

```
/zerg:rush — Launch parallel workers to execute the task graph.

Flags:
  --workers N           Number of workers to launch (default: 5, max: 10)
  --resume              Resume a previous run, skipping completed tasks
  --mode MODE           Execution mode: task|container|subprocess (default: task)
  --help                Show this help message

Modes:
  task (default)        Execute via Task tool subagents (no external processes)
  container             Execute via Docker containers with git worktrees
  subprocess            Execute via local Python subprocesses
```

