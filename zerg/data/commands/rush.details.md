<!-- SPLIT: details, parent: rush.md -->
# rush — Detailed Reference

This file contains extended examples, templates, and edge cases.
Core instructions are in `rush.core.md`.

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

Monitor:  zerg status --dashboard  (run in separate terminal)

───────────────────────────────────────────────────────────────

Commands (after rush completes):
  /zerg:status     - Check progress snapshot
  /zerg:logs N     - Stream logs from worker N
  /zerg:stop       - Stop all workers

Live monitoring (separate terminal):
  zerg status --dashboard

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

## CLI Flags

```
zerg rush [OPTIONS]

Options:
  -w, --workers INTEGER    Number of workers to launch (default: 5, max: 10)
  -f, --feature TEXT       Feature name (auto-detected if not provided)
  -l, --level INTEGER      Start from specific level (default: 1)
  -g, --task-graph PATH    Path to task-graph.json
  -m, --mode TEXT          Worker execution mode: subprocess, container, task, auto (default: auto)
  --dry-run                Show execution plan without starting workers
  --resume                 Continue from previous run
  --timeout INTEGER        Max execution time in seconds (default: 3600)
  -v, --verbose            Enable verbose output
```

## Execution Modes

### Auto Mode (Default)

```bash
zerg rush --mode auto
```

Auto-detection logic:
1. If `--mode` is explicitly set (or `--container`/`--subprocess` shorthand) → use that mode. **This overrides all other rules.**
2. If `.devcontainer/devcontainer.json` exists AND worker image is built → **container mode**
3. If running as a Claude Code slash command (`/zerg:rush`) and no explicit mode → **task mode**
4. Otherwise → **subprocess mode**

**IMPORTANT**: When `--mode container` or `--container` is specified, you MUST invoke the Python Orchestrator via subprocess, NOT use task-tool mode. Run:
```bash
python3 -c "
from zerg.orchestrator import Orchestrator
orch = Orchestrator(feature='$FEATURE', launcher_mode='container')
orch.start(task_graph_path='.gsd/specs/$FEATURE/task-graph.json', worker_count=$WORKERS)
"
```
This spawns Docker containers through ContainerLauncher with git worktrees, state IPC, and merge coordination.

### Subprocess Mode

```bash
zerg rush --mode subprocess
```

- Runs workers as local Python subprocesses
- No Docker required
- Suitable for local development and testing
- Workers share the host environment

### Container Mode

```bash
zerg rush --mode container
```

- Runs workers in isolated Docker containers
- Requires Docker and built devcontainer image
- Full environment isolation
- Each worker has its own filesystem view

### Container Setup

To use container mode:

```bash
# 1. Initialize with container support
zerg init --with-containers

# 2. Build the devcontainer image
devcontainer build --workspace-folder .

# 3. Run with container mode
zerg rush --mode container --workers 5
```

The ContainerLauncher:
- Creates Docker network `zerg-internal` for worker isolation
- Mounts worktrees as bind volumes
- Passes ANTHROPIC_API_KEY to containers
- Executes `.zerg/worker_entry.sh` in each container

### Task Tool Mode (Slash Command)

```bash
zerg rush --mode task
```

- Used automatically when `/zerg:rush` is invoked as a Claude Code slash command
- Launches parallel Task tool subagents (type: `general-purpose`)
- No Docker, worktrees, or orchestrator process needed
- File ownership from task-graph.json prevents conflicts in the shared workspace
- Level sync is natural: launch N Task tools in one message, wait for all to return

## Task Tool Execution

When running in task mode, the orchestrator (you, the slash command executor) drives execution directly through the Task tool. No external processes are spawned.

### Level Execution Loop

```
FOR each level in task-graph.json (ascending order):
  1. Collect all tasks at this level
  2. IF tasks > WORKERS:
       Split into batches of WORKERS
     ELSE:
       Single batch = all tasks
  3. FOR each batch:
       Launch all tasks in the batch as parallel Task tool calls
         (one Task tool invocation per task, all in a single message)
       Wait for all to return
       Record results (pass/fail) per task
  4. Handle failures:
       - Retry each failed task ONCE (single Task tool call)
       - If retry fails: mark task as blocked, warn, continue
       - If ALL tasks in level failed: ABORT execution
  5. After all batches complete:
       Run quality gates (lint, typecheck) on the workspace
       IF gates fail: ABORT with diagnostics
  6. Proceed to next level
END FOR
```

### Subagent Prompt Template

Each Task tool call uses subagent_type `general-purpose` with the following prompt structure:

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
- .gsd/specs/{feature}/requirements.md
- .gsd/specs/{feature}/design.md
- .gsd/specs/{feature}/task-graph.json (your task entry)

## Acceptance Criteria
{acceptance_criteria}

## Verification
After implementation, run:
```
{verification.command}
```
Expected: exit code 0

## On Completion
1. Stage ONLY your owned files: git add {files.create + files.modify}
2. Commit with message: "feat({feature}): {TASK_ID} - {title}"
3. Report: list files changed, verification result, any warnings
```

### Batching

When the number of tasks at a level exceeds `WORKERS`:

- Split tasks into chunks of size `WORKERS`
- Execute each chunk as a parallel batch
- Wait for the batch to complete before launching the next
- Example: 12 tasks, 5 workers → batch 1 (5), batch 2 (5), batch 3 (2)

### Error Handling (Task Mode)

| Scenario | Behavior |
|----------|----------|
| Task fails verification | Retry once with error context appended to prompt |
| Task fails retry | Mark blocked, log error, continue with remaining tasks |
| All tasks at level fail | Abort execution, display diagnostics |
| Partial failures at level | Warn, continue to next level with passing tasks |

### Differences from Container/Subprocess Modes

| Aspect | Container/Subprocess | Task Tool |
|--------|---------------------|-----------|
| Isolation | Git worktrees per worker | Shared workspace, file ownership |
| Branching | Worker branches + merge | Single branch, sequential commits |
| Orchestrator | External Python process | Slash command executor (you) |
| Health checks | Docker health / process poll | Task tool return status |
| Port allocation | Per-worker ports | Not needed |
| Resume | State file checkpoint | Re-run `/zerg:rush --resume` |
| Context management | 70% threshold per worker | Per-subagent (fresh context each) |

## Resume Instructions

To resume a stopped or interrupted execution:

```bash
# Resume with same configuration
zerg rush --resume

# Resume with different worker count
zerg rush --resume --workers 3

# Resume from specific level (skip earlier levels)
zerg rush --resume --level 3
```

Resume behavior:
1. Loads existing state from `.zerg/state/{feature}.json`
2. Identifies incomplete and failed tasks
3. Restores worker assignments where possible
4. Continues from last checkpoint

## Progress Display

During execution, the orchestrator shows:

```
═══════════════════════════════════════════════════════════════
Progress: ████████████░░░░░░░░ 60% (24/40 tasks)

Level 3 of 5 │ Workers: 5 active

┌────────┬────────────────────────────────┬──────────┬─────────┐
│ Worker │ Current Task                   │ Progress │ Status  │
├────────┼────────────────────────────────┼──────────┼─────────┤
│ W-0    │ TASK-015: Implement login API  │ ████░░   │ RUNNING │
│ W-1    │ TASK-016: Create user service  │ ██████   │ VERIFY  │
│ W-2    │ TASK-017: Add auth middleware  │ ██░░░░   │ RUNNING │
│ W-3    │ (waiting for dependency)       │ ░░░░░░   │ IDLE    │
│ W-4    │ TASK-018: Database migrations  │ ████░░   │ RUNNING │
└────────┴────────────────────────────────┴──────────┴─────────┘

Recent: ✓ TASK-014 (W-2) │ ✓ TASK-013 (W-1) │ ✓ TASK-012 (W-0)
═══════════════════════════════════════════════════════════════
```

## worker-assignments.json Format

```json
{
  "feature": "user-auth",
  "generated": "2026-01-25T10:30:00Z",
  "workers": [
    {
      "id": 0,
      "branch": "zerg/user-auth/worker-0",
      "worktree": ".zerg/worktrees/user-auth-worker-0",
      "port": 49152,
      "container_id": "abc123",
      "status": "running",
      "assignments": {
        "1": ["TASK-001", "TASK-003"],
        "2": ["TASK-005", "TASK-007"],
        "3": ["TASK-009"]
      },
      "completed_tasks": ["TASK-001"],
      "current_task": "TASK-003",
      "context_usage": 0.45
    }
  ],
  "execution_plan": [
    {
      "level": 1,
      "workers_active": [0, 1, 2, 3, 4],
      "tasks": ["TASK-001", "TASK-002", "TASK-003", "TASK-004", "TASK-005"],
      "status": "complete",
      "merge_after": true,
      "merge_result": "success"
    },
    {
      "level": 2,
      "workers_active": [0, 1, 2, 3, 4],
      "tasks": ["TASK-006", "TASK-007", "TASK-008", "TASK-009", "TASK-010"],
      "status": "in_progress",
      "merge_after": true
    }
  ],
  "stats": {
    "total_tasks": 40,
    "completed_tasks": 24,
    "failed_tasks": 0,
    "blocked_tasks": 0,
    "start_time": "2026-01-25T10:30:00Z",
    "elapsed_minutes": 45
  }
}
```
