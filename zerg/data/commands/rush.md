

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

## Launch Protocol

### Step 1: Analyze Task Graph

```bash
# Determine optimal worker count
TASKS=$(jq '.total_tasks' "$SPEC_DIR/task-graph.json")
MAX_PARALLEL=$(jq '.max_parallelization' "$SPEC_DIR/task-graph.json")

# Don't use more workers than can parallelize
if [ "$WORKERS" -gt "$MAX_PARALLEL" ]; then
  WORKERS=$MAX_PARALLEL
  echo "Adjusting to $WORKERS workers (max parallelization)"
fi
```

### Step 2: Create Worker Branches

For each worker, create a dedicated git worktree:

```bash
# Base branch for the feature
git checkout -b "zerg/FEATURE/base" 2>/dev/null || git checkout "zerg/FEATURE/base"

# Create worktrees for each worker
for i in $(seq 0 $((WORKERS - 1))); do
  BRANCH="zerg/FEATURE/worker-$i"
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

### Step 3: Partition Tasks

Assign tasks to workers based on:
1. Level (all Level 1 before Level 2)
2. File ownership (no conflicts)
3. Load balancing (distribute evenly)

```json
// Generated: .gsd/specs/{feature}/worker-assignments.json
{
  "feature": "{feature}",
  "generated": "{timestamp}",
  "workers": [
    {
      "id": 0,
      "branch": "zerg/{feature}/worker-0",
      "worktree": "../.zerg-worktrees/{feature}/worker-0",
      "port": 49152,
      "assignments": {
        "1": ["TASK-001"],
        "2": ["TASK-003"],
        "3": ["TASK-005"]
      }
    },
    {
      "id": 1,
      "branch": "zerg/{feature}/worker-1", 
      "worktree": "../.zerg-worktrees/{feature}/worker-1",
      "port": 49153,
      "assignments": {
        "1": ["TASK-002"],
        "2": ["TASK-004"],
        "3": ["TASK-006"]
      }
    }
  ],
  "execution_plan": [
    {
      "level": 1,
      "workers_active": [0, 1],
      "tasks": ["TASK-001", "TASK-002"],
      "merge_after": true
    },
    {
      "level": 2,
      "workers_active": [0, 1],
      "tasks": ["TASK-003", "TASK-004"],
      "merge_after": true
    }
  ]
}
```

### Step 4: Create Native Tasks

Register ALL tasks from task-graph.json in Claude Code's Task system:

For each task in task-graph.json, call TaskCreate:
  - subject: "[L{level}] {title}"
  - description: "{description}\n\nFiles: {files.create + files.modify}\nVerification: {verification.command}"
  - activeForm: "Executing {title}"

After all TaskCreate calls, wire dependencies using TaskUpdate:
  - For each task with dependencies, call TaskUpdate with addBlockedBy

When a worker claims a task, call TaskUpdate:
  - taskId: the task's Claude Task ID
  - status: "in_progress"
  - activeForm: "Worker {N} executing {title}"

Verify with TaskList that all tasks appear correctly.

**Error Handling for Task System:**
- If TaskCreate or TaskUpdate fails for any task, log a warning but continue execution
- State JSON (`.zerg/state/{feature}.json`) serves as fallback if Task system is unavailable
- Note in progress output: `⚠️ Task system partially unavailable — using state JSON as fallback`
- On `--resume`: Call TaskList first; only create tasks that don't already exist (match by subject prefix `[L{level}] {title}`)

### Step 5: Launch Containers

```bash
# Allocate ports
BASE_PORT=49152
for i in $(seq 0 $((WORKERS - 1))); do
  PORT=$((BASE_PORT + i))
  
  # Check port is available
  while nc -z localhost $PORT 2>/dev/null; do
    PORT=$((PORT + 1))
  done
  
  # Update assignment with actual port
  jq ".workers[$i].port = $PORT" "$SPEC_DIR/worker-assignments.json" > tmp && mv tmp "$SPEC_DIR/worker-assignments.json"
done

# Launch each worker container
for i in $(seq 0 $((WORKERS - 1))); do
  WORKER_PORT=$(jq -r ".workers[$i].port" "$SPEC_DIR/worker-assignments.json")
  WORKER_BRANCH=$(jq -r ".workers[$i].branch" "$SPEC_DIR/worker-assignments.json")
  WORKTREE=$(jq -r ".workers[$i].worktree" "$SPEC_DIR/worker-assignments.json")
  
  echo "Launching Worker $i on port $WORKER_PORT..."
  
  docker compose -f .devcontainer/docker-compose.yaml run \
    --detach \
    --name "factory-worker-$i" \
    -e ZERG_WORKER_ID=$i \
    -e ZERG_FEATURE=$FEATURE \
    -e ZERG_BRANCH=$WORKER_BRANCH \
    -e ZERG_PORT=$WORKER_PORT \
    -e CLAUDE_CODE_TASK_LIST_ID=${CLAUDE_CODE_TASK_LIST_ID:-} \
    -p "$WORKER_PORT:$WORKER_PORT" \
    -v "$(realpath $WORKTREE):/workspace" \
    workspace \
    bash -c "claude --dangerously-skip-permissions -p 'You are ZERG Worker $i. Run /zerg:worker to begin execution.'"
done
```

### Step 6: Start Orchestrator

Launch the orchestration process:

```bash
python3 .zerg/orchestrator.py \
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

## Help

When `--help` is passed in `$ARGUMENTS`, display usage and exit:

```
/zerg:rush — Launch parallel workers to execute the task graph.

Flags:
  --workers N           Number of workers to launch (default: 5, max: 10)
  --resume              Resume a previous run, skipping completed tasks
  --mode MODE           Execution mode: container|subprocess
  --help                Show this help message
```

