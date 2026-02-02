# /zerg:worker

Worker execution protocol for parallel task processing within a ZERG swarm.

## Synopsis

This command is not invoked directly by users. Workers are spawned by the `/zerg:rush` orchestrator and execute tasks according to the protocol described below.

## Description

A ZERG worker is an isolated Claude Code instance that executes tasks assigned to it from the task graph. Workers operate in parallel, each owning exclusive files to prevent conflicts. They coordinate through the shared Claude Code Task system and communicate progress through state files and logs.

### Environment Variables

| Variable | Description |
|----------|-------------|
| `ZERG_WORKER_ID` | Unique integer identifier for this worker. |
| `ZERG_FEATURE` | Name of the feature being built. |
| `ZERG_BRANCH` | Git branch assigned to this worker. |
| `CLAUDE_CODE_TASK_LIST_ID` | Shared task list identifier for cross-worker coordination. |

### Execution Protocol

**Step 1: Load Context** -- Read the feature requirements, design document, task graph, and worker assignments from `.gsd/specs/{feature}/`.

**Step 2: Identify Tasks** -- From `worker-assignments.json`, determine which tasks are assigned at each dependency level.

**Step 3: Execute Task Loop** -- For each level starting at 1:

1. Retrieve assigned tasks for the current level.
2. Verify all upstream dependencies are complete.
3. Execute each task (load details, implement, verify, commit).
4. Wait for all workers to finish the current level.
5. Pull merged changes from the staging branch.
6. Advance to the next level.

**Step 4: Task Execution** -- For each individual task:

1. Load task details from `task-graph.json` (title, description, files, verification command).
2. Claim the task in the Claude Task system by calling TaskUpdate with `in_progress`.
3. Read dependency files.
4. Implement the task following the design document exactly.
5. Run the verification command.
6. Commit on success with structured metadata.
7. Update the Claude Task status to `completed`.

**Step 5: Context Management** -- Monitor context usage. At 70% capacity, commit work in progress, log handoff state, and exit cleanly for the orchestrator to restart a fresh instance.

**Step 6: Level Completion** -- Signal completion, wait for the orchestrator merge, pull the merged result, and proceed to the next level.

### Task Claiming

Workers claim tasks atomically to prevent conflicts:

```python
task = state.get_pending_task(level=current_level, worker_id=my_id)
if state.claim_task(task.id, worker_id=my_id):
    execute_task(task)
else:
    continue  # Another worker claimed it
```

### Failure Handling

If a task verification fails, the worker retries up to 3 times. After 3 failures, the task is marked as blocked and the worker moves on to the next assigned task. Error details are appended to the Claude Task description.

### Context Checkpoints

When context usage exceeds 70%, the worker:

1. Commits all work in progress with a structured WIP commit.
2. Updates the Claude Task with checkpoint details (percentage complete, next action).
3. Exits with code 2 (CHECKPOINT) so the orchestrator can spawn a fresh instance.

### Quality Standards

Every completed task must:

1. Follow the design document exactly.
2. Match existing codebase patterns.
3. Contain no TODOs or placeholders.
4. Pass the verification command.
5. Include inline comments for complex logic.
6. Use full type annotations (no `any` in TypeScript).
7. Include proper error handling beyond the happy path.

### Task State Transitions

```
PENDING --> IN_PROGRESS --> COMPLETE
                       \-> FAILED --> PENDING (on retry)
                       \-> BLOCKED (after 3 failures)
                       \-> PAUSED (on checkpoint)
```

### Worker State Transitions

```
STARTING --> RUNNING --> STOPPED
                |
            CHECKPOINT --> STOPPED
                |
             CRASHED (on error)
```

### Communication Channels

| Channel | Path | Purpose |
|---------|------|---------|
| State file | `.zerg/state/{feature}.json` | Shared task state |
| Progress log | `.gsd/specs/{feature}/progress.md` | Human-readable activity log |
| Worker log | `.zerg/logs/worker-{id}.log` | Detailed worker output |
| Event stream | State manager | Append-only events for orchestrator |

### WIP Commit Format

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

## Exit Codes

| Code | Constant | Meaning |
|------|----------|---------|
| 0 | `SUCCESS` | All assigned tasks completed successfully. |
| 1 | `ERROR` | Unrecoverable error; check logs. |
| 2 | `CHECKPOINT` | Context limit reached (70%); needs restart. |
| 3 | `BLOCKED` | All remaining tasks blocked; intervention needed. |
| 130 | `INTERRUPTED` | Received stop signal; graceful shutdown. |

## Task Tracking

Workers use the Claude Code Task system extensively:

- **Claim**: TaskUpdate to `in_progress` before starting a task.
- **Complete**: TaskUpdate to `completed` after verification passes.
- **Fail**: TaskUpdate with error details appended to the description.
- **Checkpoint**: TaskUpdate with checkpoint context for resume.
- **Completion audit**: TaskList at shutdown to verify all assigned tasks are marked complete.

## See Also

- [[zerg-debug]] -- Diagnose worker failures
- [[zerg-plugins]] -- Custom lifecycle hooks that observe worker events
- [[zerg-index]] -- Generate documentation for the worker protocol
