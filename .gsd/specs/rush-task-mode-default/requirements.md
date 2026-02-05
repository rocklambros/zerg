# Requirements: Fix /zerg:rush Task Tool Mode Default

**Status: APPROVED**
**Created**: 2026-02-04
**Feature**: rush-task-mode-default

## Problem Statement

When `/zerg:rush` is invoked as a Claude Code slash command without explicit `--mode`, it incorrectly delegates to the Python CLI/Orchestrator (subprocess mode) instead of executing in Task Tool Mode.

### Root Cause

The current `rush.core.md` describes container/subprocess mode as the primary execution path:
- Step 2: Create Worker Branches (git worktrees)
- Step 5: Launch Containers (Docker)
- Step 6: Start Orchestrator (Python process)

Task Tool Mode is documented in `rush.details.md` but is never invoked as the default path. The core file lacks:
1. Mode detection logic at the start
2. Conditional branching based on mode
3. Task Tool execution loop as the primary path

### Expected Behavior

```
/zerg:rush                    → Task Tool Mode (default)
/zerg:rush --mode task        → Task Tool Mode (explicit)
/zerg:rush --mode container   → Container Mode (Docker + worktrees)
/zerg:rush --mode subprocess  → Subprocess Mode (Python processes)
```

## Functional Requirements

### FR-1: Mode Detection at Entry

At the start of `/zerg:rush` execution, detect the requested mode:

```
IF $ARGUMENTS contains "--mode container":
  MODE = "container"
ELSE IF $ARGUMENTS contains "--mode subprocess":
  MODE = "subprocess"
ELSE:
  MODE = "task"  # DEFAULT
```

### FR-2: Task Tool Mode as Primary Execution Path

When `MODE = "task"` (default), the slash command executor (Claude) drives execution directly via the Task tool. No external processes are spawned.

**Level Execution Loop:**
```
FOR each level in task-graph.json (ascending order):
  1. Collect all tasks at this level
  2. Batch tasks by WORKERS count
  3. FOR each batch:
       Launch all tasks as parallel Task tool calls
       (subagent_type: "general-purpose")
       Wait for all to return
       Record pass/fail per task
  4. Handle failures:
       - Retry failed tasks ONCE
       - If retry fails: mark blocked, warn, continue
       - If ALL tasks fail: ABORT
  5. Run quality gates (lint, typecheck)
  6. Proceed to next level
END FOR
```

### FR-3: Subagent Prompt Structure

Each Task tool call uses the template from `rush.details.md:263-301`:
- Task ID, title, description, level
- Files to create/modify/read
- Design context references
- Acceptance criteria
- Verification command
- Commit instructions

### FR-4: Container/Subprocess Mode Fallback

When `MODE = "container"` or `MODE = "subprocess"`, invoke the Python Orchestrator:

```python
from zerg.orchestrator import Orchestrator
orch = Orchestrator(feature=FEATURE, launcher_mode=MODE)
orch.start(task_graph_path=SPEC_DIR/task-graph.json, worker_count=WORKERS)
```

This path is only taken with explicit `--mode container` or `--mode subprocess`.

### FR-5: Claude Code Task System Integration

In Task Tool Mode, use Claude Code's native Task system for tracking:
- TaskCreate for each task from task-graph.json
- TaskUpdate to mark in_progress when launching subagent
- TaskUpdate to mark completed/failed on return
- TaskList for resume logic

### FR-6: Resume Support

`/zerg:rush --resume` behavior in Task Tool Mode:
1. Call TaskList to get current task states
2. Skip tasks with status "completed"
3. Resume from first incomplete level
4. Maintain retry counts from previous run

## Non-Functional Requirements

### NFR-1: No Python Process Spawning in Default Mode

Task Tool Mode must NOT spawn any external processes:
- No `python3 -m zerg.orchestrator`
- No `docker run`
- No subprocess.Popen

All orchestration happens within the slash command context.

### NFR-2: Parallel Execution via Task Tool

Tasks at the same level execute in parallel via multiple Task tool calls in a single message. This is the Task tool's native parallel execution capability.

### NFR-3: Shared Workspace

In Task Tool Mode, all subagents work in the same workspace (no worktrees). File ownership from task-graph.json prevents conflicts.

### NFR-4: Single Branch Commits

No worker branches or merge operations. Subagents commit directly to the current branch, sequentially after each batch.

## Scope

### In Scope

1. Restructure `rush.core.md` to use Task Tool Mode as default
2. Move container/subprocess instructions to conditional section
3. Add mode detection logic at entry
4. Ensure Task Tool execution loop is complete and actionable

### Out of Scope

1. Changes to Python CLI (`zerg/commands/rush.py`)
2. Changes to Orchestrator (`zerg/orchestrator.py`)
3. Changes to launcher infrastructure
4. New Python code

## Acceptance Criteria

1. `/zerg:rush` without flags executes via Task tool subagents
2. `/zerg:rush --mode container` invokes Python Orchestrator with container launcher
3. `/zerg:rush --mode subprocess` invokes Python Orchestrator with subprocess launcher
4. Task Tool Mode completes a multi-level task graph successfully
5. Resume works correctly in Task Tool Mode
6. Documentation matches implementation

## Files to Modify

| File | Change |
|------|--------|
| `zerg/data/commands/rush.core.md` | Restructure: Task Tool Mode as default, container/subprocess as conditional |
| `zerg/data/commands/rush.md` | Update to match core (backward compat) |
| `zerg/data/commands/rush.details.md` | No changes (already documents Task Tool Mode correctly) |

## Open Questions

1. **Quality gates in Task Tool Mode**: Should we run gates after each level or only at the end?
   - Recommendation: After each level (matches container mode behavior)

2. **Error handling granularity**: How detailed should failure reporting be?
   - Recommendation: Report task ID, error summary, suggest retry

3. **Progress display**: How to show progress without external orchestrator?
   - Recommendation: Print progress table after each batch completes
