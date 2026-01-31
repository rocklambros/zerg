<!-- SPLIT: core, parent: zerg:merge.md -->
# ZERG Merge — Core

Manually trigger or manage level merge operations.

## Pre-Flight

```bash
FEATURE=$(cat .gsd/.current-feature 2>/dev/null)
STATE_FILE=".zerg/state/$FEATURE.json"
SPEC_DIR=".gsd/specs/$FEATURE"

[ -z "$FEATURE" ] && { echo "ERROR: No active feature"; exit 1; }
[ ! -f "$STATE_FILE" ] && { echo "ERROR: No state file found"; exit 1; }
```

## Merge Protocol Summary

1. **Check Level Completion** — All tasks at current level must be complete
2. **Collect Worker Branches** — Gather branches from state file (see details)
3. **Create Staging Branch** — Branch from base for merge target (see details)
4. **Merge Worker Branches** — Merge each worker branch into staging (see details)
5. **Run Quality Gates** — lint, test, typecheck
6. **Update Task System** — TaskUpdate/TaskList after gates
7. **Finalize Merge** — Tag, update state, verify Tasks
8. **Rebase Worker Branches** — Rebase onto merged base (see details)

### Step 1: Check Level Completion

```bash
CURRENT_LEVEL=$(jq '.current_level' "$STATE_FILE")
PENDING=$(jq "[.tasks | to_entries[] | select(.value.level == $CURRENT_LEVEL and .value.status != \"complete\")] | length" "$STATE_FILE")

if [ "$PENDING" -gt 0 ]; then
  echo "ERROR: Level $CURRENT_LEVEL has $PENDING incomplete tasks"
  exit 1
fi
```

### Step 5: Run Quality Gates

```bash
echo "Running quality gates on merged code..."

if ! ruff check .; then GATE_FAILURES+=("lint"); fi
if ! pytest tests/ -v --tb=short; then GATE_FAILURES+=("test"); fi
if ! mypy . --ignore-missing-imports; then GATE_FAILURES+=("typecheck"); fi

if [ ${#GATE_FAILURES[@]} -gt 0 ]; then
  echo "Quality gates failed: ${GATE_FAILURES[*]}"
  if [ "$FORCE" != "true" ]; then exit 1; fi
fi
```

### Step 5.5: Update Task System After Merge

After quality gates pass, update Claude Code Tasks for this level:

1. Call **TaskList** to get all tasks
2. For each task at the current level (match subject prefix `[L{CURRENT_LEVEL}]`):
   - If quality gates passed: Call **TaskUpdate** with status "completed"
   - If quality gates failed: Do NOT update task status (leave as in_progress for retry)
3. Log any tasks that could not be updated

If quality gates failed, skip this step entirely — tasks remain in_progress for the orchestrator to handle.

### Step 6: Finalize Merge

```bash
git tag "zerg/$FEATURE/level-$CURRENT_LEVEL-complete"
jq ".levels[\"$CURRENT_LEVEL\"].status = \"complete\" | .levels[\"$CURRENT_LEVEL\"].merge_commit = \"$(git rev-parse HEAD)\"" "$STATE_FILE" > tmp && mv tmp "$STATE_FILE"
echo "Level $CURRENT_LEVEL merge complete"
```

After finalization, verify Task system consistency:

Call **TaskList** and confirm all tasks at level `$CURRENT_LEVEL` show status "completed".
If any task is not completed, log a warning: `Task {subject} not marked completed in Task system`.
