<!-- SPLIT: core, parent: status.md -->
# ZERG Status

Display current factory execution status.

## Load State

```bash
FEATURE=${ZERG_FEATURE:-$(cat .gsd/.current-feature 2>/dev/null)}
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

## Worker Health

Display per-worker health table and escalation summary using `StatusFormatter`.

### Procedure

1. Read heartbeat files: `.zerg/state/heartbeat-{id}.json` for each active worker
2. Read escalations: `.zerg/state/escalations.json`
3. Read progress files: `.zerg/state/progress-{id}.json` for each active worker
4. Format with `zerg.status_formatter`:

```python
from zerg.status_formatter import format_health_table, format_escalations

health_output = format_health_table(heartbeats, escalations, progress_data)
escalation_output = format_escalations(escalations)
```

5. Render in the dashboard:

```
───────────────────────────────────────────────────────────────────────────────
                            WORKER HEALTH
───────────────────────────────────────────────────────────────────────────────

{output of format_health_table()}

Escalations:
{output of format_escalations()}

───────────────────────────────────────────────────────────────────────────────
```

If no heartbeat files exist, display "No worker data available" and skip the table.

## Repository Map

Display repository index statistics from the incremental symbol index.

### Procedure

1. Read index file: `.zerg/state/repo-index.json`
2. Parse the `_meta` and `files` sections to build stats (or use `IncrementalIndex.get_stats()`)
3. Format with `zerg.status_formatter`:

```python
from zerg.status_formatter import format_repo_map_stats

repo_map_output = format_repo_map_stats(index_data)
```

4. Render in the dashboard:

```
───────────────────────────────────────────────────────────────────────────────
                           REPOSITORY MAP
───────────────────────────────────────────────────────────────────────────────

{output of format_repo_map_stats()}

───────────────────────────────────────────────────────────────────────────────
```

If no repo-index.json exists, display "No repo map data available" and skip the section.

### Data Sources

- Index file: `.zerg/state/repo-index.json` — `_meta.last_updated`, file entries with hash + symbols
- Stats: `IncrementalIndex.get_stats()` — total_files, indexed_files, stale_files, last_updated

### Data Sources

- Heartbeats: `.zerg/state/heartbeat-{id}.json` — worker_id, timestamp, task_id, step, progress_pct
- Escalations: `.zerg/state/escalations.json` — list of {worker_id, task_id, category, message, resolved}
- Progress: `.zerg/state/progress-{id}.json` — worker_id, tasks_completed, tasks_total, tier_results
- Stall threshold: `config.heartbeat.stall_timeout_seconds` (default: 120s)

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

## Token Usage

Display per-worker token consumption and savings analysis from the token aggregator.

### Procedure

1. Read token files: `.zerg/state/tokens-*.json` via `TokenAggregator`
2. Call `aggregate()` and `calculate_savings()`
3. Format with `zerg.status_formatter`:

```python
from zerg.token_aggregator import TokenAggregator
from zerg.status_formatter import format_token_table, format_savings

aggregator = TokenAggregator(state_dir=".zerg/state")
agg = aggregator.aggregate()
savings = aggregator.calculate_savings()

token_table = format_token_table(agg.per_worker)
savings_output = format_savings(savings)
```

4. Render in the dashboard:

```
───────────────────────────────────────────────────────────────────────────────
                            TOKEN USAGE
───────────────────────────────────────────────────────────────────────────────

{output of format_token_table()}

Savings:
{output of format_savings()}

───────────────────────────────────────────────────────────────────────────────
```

If no token files exist, display "No token data available" and skip the section.

Note: The Mode column shows "(estimated)" when using heuristic token counting and "(exact)" when using API-counted values.

### Token Usage Data Sources

- Token files: `.zerg/state/tokens-*.json` — per-worker cumulative and per-task breakdowns
- Aggregator: `TokenAggregator.aggregate()` — AggregateResult with per_worker, total_tokens, breakdown_totals
- Savings: `TokenAggregator.calculate_savings()` — SavingsResult with injected vs baseline comparison

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
