<!-- SPLIT: core, parent: status.md -->
# ZERG Status

Display current factory execution status.

## Load State

```bash
FEATURE=$(cat .gsd/.current-feature 2>/dev/null)
TASK_LIST=${CLAUDE_CODE_TASK_LIST_ID:-$FEATURE}
SPEC_DIR=".gsd/specs/$FEATURE"

if [ -z "$FEATURE" ]; then
  echo "No active feature"
  exit 0
fi

# Check if orchestrator is running
ORCH_PID=$(cat .zerg/.orchestrator.pid 2>/dev/null)
if [ -n "$ORCH_PID" ] && kill -0 $ORCH_PID 2>/dev/null; then
  ORCH_STATUS="Running (PID: $ORCH_PID)"
else
  ORCH_STATUS="Not running"
fi
```

## Generate Status Report

```
═══════════════════════════════════════════════════════════════════════════════
                         FACTORY STATUS
═══════════════════════════════════════════════════════════════════════════════

Feature:      {feature}
Task List:    $TASK_LIST
Phase:        {phase: PLANNING | DESIGNING | EXECUTING | MERGING | COMPLETE}
Orchestrator: {orch_status}
Started:      {start_time}
Elapsed:      {elapsed_time}

───────────────────────────────────────────────────────────────────────────────
                              PROGRESS
───────────────────────────────────────────────────────────────────────────────

Task System: {X}/{Y} tasks ({Z} pending, {W} active)
Overall: {progress_bar} {percent}% ({completed}/{total} tasks)

Level 1 (Foundation):   {bar} {status} ({n}/{n} tasks)
Level 2 (Core):         {bar} {status} ({n}/{n} tasks)
Level 3 (Integration):  {bar} {status} ({n}/{n} tasks)
Level 4 (Testing):      {bar} {status} ({n}/{n} tasks)
Level 5 (Quality):      {bar} {status} ({n}/{n} tasks)

═══════════════════════════════════════════════════════════════════════════════

Commands:
  /zerg:logs {N}      View logs from worker N
  /zerg:stop          Stop all workers
  /zerg:unblock {ID}  Retry a blocked task
  /zerg:scale {N}     Change number of workers

═══════════════════════════════════════════════════════════════════════════════
```

## Live Dashboard (CLI)

This slash command produces a text snapshot. For a **live-updating TUI dashboard** with progress bars, worker context usage, retries, and event streaming, use the CLI in a separate terminal:

```bash
zerg status --dashboard           # Full TUI (recommended during rush)
zerg status --dashboard -i 2      # Custom refresh interval
zerg status --watch               # Lighter text-based refresh
```

## Context Budget

Show context engineering stats when available:

```
CONTEXT BUDGET
──────────────────────────────────────────────
Split Commands:  {n} files split (core + details)
  Savings:       ~{tokens} tokens per worker session

Per-Task Context:
  Tasks with context:  {n}/{total} (populated at design time)
  Tasks using fallback: {n}/{total} (full spec loaded)
  Avg context size:    {n} tokens (budget: {limit})

Security Rules:
  Filtered:     {lang} ({n} tasks), {lang} ({n} tasks)
  Core only:    {n} tasks (OWASP rules only)
  Savings:      ~{tokens} tokens vs loading all rules
──────────────────────────────────────────────
```

### Context Budget Data Sources

- Split file count: `ls zerg/data/commands/*.core.md | wc -l`
- Task context: read `task.context` field from task-graph.json
- Security filtering: check task file extensions vs loaded rules
- Budget config: `ContextEngineeringConfig.task_context_budget_tokens`

## Data Sources

### Task Status from Native Tasks

Call TaskList to retrieve all Claude Code tasks for this feature.

Cross-reference with state JSON (`.zerg/state/{feature}.json`):
- For each task, compare Task system status vs state JSON status
- **Task system is authoritative** — if statuses disagree, prefer Task system
- Flag mismatches in output:
  ```
  ⚠️ Status mismatch: TASK-003 — Task system: "completed", state JSON: "in_progress"
  ```

Aggregate Task system data for the summary line:
- Count tasks by status: pending, in_progress, completed
- Calculate: `Task System: {completed + in_progress + pending}/{total} tasks ({pending} pending, {in_progress} active)`

### Detailed Views

#### /zerg:status --tasks

Show all tasks with their status. **Primary source**: TaskList + TaskGet from Claude Code Task system. Fall back to state JSON for worker assignment details not stored in Tasks.

For each task:
1. Call TaskList to get all tasks
2. For each task, use TaskGet if full description is needed
3. Supplement with worker assignment info from `.zerg/state/{feature}.json`

## Task Tracking

On invocation: TaskCreate (subject: `[Status] Check status: {feature}`)
Immediately: TaskUpdate status "in_progress"
On completion: TaskUpdate status "completed"

## Help

When `--help` is passed in `$ARGUMENTS`, display usage and exit:

```
/zerg:status — Display current factory execution status.

Flags:
  --tasks               Show all tasks with their status
  --dashboard           Full TUI dashboard (CLI only)
  -i, --interval N      Custom refresh interval for dashboard
  --watch               Lighter text-based refresh (CLI only)
  --json                Output as JSON
  --help                Show this help message
```
