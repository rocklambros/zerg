# ZERG Launch

Launch parallel workers to execute the task graph.

## Pre-Flight

```bash
FEATURE=$(cat .gsd/.current-feature 2>/dev/null)
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

Register tasks in Claude Code's native Tasks system:

```bash
# Set the shared task list ID
export CLAUDE_CODE_TASK_LIST_ID="$FEATURE"

# For each task in task-graph.json, create in native Tasks
# (This is done via Claude Code's /tasks command internally)
```

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
    -e CLAUDE_CODE_TASK_LIST_ID=$FEATURE \
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
  --assignments "$SPEC_DIR/worker-assignments.json" \
  --dashboard-port 8080 &

ORCHESTRATOR_PID=$!
echo $ORCHESTRATOR_PID > ".zerg/.orchestrator.pid"
```

## Output

```
═══════════════════════════════════════════════════════════════
                    FACTORY LAUNCHED
═══════════════════════════════════════════════════════════════

Feature: {feature}
Workers: {N}
Tasks: {N} total across {N} levels

Worker Status:
┌──────────┬────────┬────────────────────────────┬──────────┐
│ Worker   │ Port   │ Branch                     │ Status   │
├──────────┼────────┼────────────────────────────┼──────────┤
│ worker-0 │ 49152  │ zerg/{feature}/worker-0 │ Starting │
│ worker-1 │ 49153  │ zerg/{feature}/worker-1 │ Starting │
│ worker-2 │ 49154  │ zerg/{feature}/worker-2 │ Starting │
│ worker-3 │ 49155  │ zerg/{feature}/worker-3 │ Starting │
│ worker-4 │ 49156  │ zerg/{feature}/worker-4 │ Starting │
└──────────┴────────┴────────────────────────────┴──────────┘

Dashboard: http://localhost:8080

───────────────────────────────────────────────────────────────

Commands:
  /zerg:status     - Check progress
  /zerg:logs N     - Stream logs from worker N
  /zerg:stop       - Stop all workers
  /zerg:stop N     - Stop worker N

═══════════════════════════════════════════════════════════════
```

## Worker Execution Loop

Each worker runs this loop:

```markdown
WHILE tasks remain at my assigned levels:
  
  1. Check current level's tasks
     - Are my assigned tasks for this level complete?
     - If all complete, wait for level merge, then proceed to next level
  
  2. Pick next task from my assignments
     - Must be at current level
     - Must have all dependencies satisfied
     - Must not be locked by another worker
  
  3. Lock the task
     - Set status = "in_progress"
     - Set worker_id = my ID
  
  4. Load task context
     - Read requirements.md
     - Read design.md  
     - Read task details from task-graph.json
     - Read any files listed in "read" dependencies
  
  5. Execute task
     - Create/modify files as specified
     - Follow design patterns from design.md
     - Add inline comments explaining decisions
  
  6. Verify task
     - Run verification command
     - Check exit code
  
  7. On SUCCESS:
     - git add {files}
     - git commit with task metadata
     - Set task status = "completed"
     - Log success
  
  8. On FAILURE:
     - Increment retry count
     - If retries < 3: go to step 4 (retry)
     - If retries >= 3:
       - Set task status = "blocked"
       - Log failure with error details
       - Move to next task (if any)
  
  9. Check context usage
     - If > 70% context used:
       - Commit any in-progress work
       - Log handoff point
       - Exit cleanly (orchestrator will restart)
  
END WHILE

Report completion to orchestrator
```

## Level Synchronization

After each level completes:

1. All workers pause
2. Orchestrator runs quality gates on each branch
3. Orchestrator merges all worker branches to staging
4. If conflicts: orchestrator re-runs affected tasks
5. Run integration tests on merged code
6. If passing: merge staging to each worker branch
7. Workers resume with next level

## Error Handling

### Worker Crash
- Orchestrator detects via health check
- Respawns container
- Worker resumes from last committed task

### Task Timeout
- Task killed after configured timeout
- Marked as blocked
- Worker moves to next task

### All Workers Blocked
- Orchestrator pauses factory
- Alerts human for intervention
- Provides diagnostic information

### Merge Conflict
- Identifies conflicting commits
- Re-runs one worker's tasks on merged base
- Continues after resolution