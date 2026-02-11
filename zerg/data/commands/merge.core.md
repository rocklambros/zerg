<!-- SPLIT: core, parent: merge.md -->
# ZERG Merge — Core

Manually trigger or manage level merge operations.

## Pre-Flight

```bash
FEATURE=${ZERG_FEATURE:-$(cat .gsd/.current-feature 2>/dev/null)}
TASK_LIST=${CLAUDE_CODE_TASK_LIST_ID:-$FEATURE}
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

### Step 5.5: Wiring Verification

After quality gates pass, verify new modules are connected:

```bash
echo "Checking module wiring..."

# Find all .py files created in this level's commits
MERGE_BASE=$(git merge-base HEAD zerg/$FEATURE/base)
NEW_FILES=$(git diff --name-only --diff-filter=A "$MERGE_BASE" HEAD -- '*.py' | grep -v 'tests/' | grep -v '__init__.py')

WIRING_WARNINGS=()
for FILE in $NEW_FILES; do
  # Convert path to module pattern (zerg/foo.py -> zerg.foo)
  MODULE=$(echo "$FILE" | sed 's|/|.|g' | sed 's|\.py$||')
  MODULE_NAME=$(basename "$FILE" .py)
  PKG=$(dirname "$FILE" | sed 's|/|.|g')

  # Search for production imports (exclude tests/ and the file itself)
  IMPORTERS=$(grep -rl "from ${MODULE} import\|import ${MODULE}\|from ${PKG} import ${MODULE_NAME}" --include="*.py" . 2>/dev/null | grep -v "tests/" | grep -v "$FILE" | head -1)

  if [ -z "$IMPORTERS" ]; then
    WIRING_WARNINGS+=("$FILE")
  fi
done

if [ ${#WIRING_WARNINGS[@]} -gt 0 ]; then
  echo "⚠️  Wiring warnings: ${#WIRING_WARNINGS[@]} new module(s) have no production callers:"
  for W in "${WIRING_WARNINGS[@]}"; do
    echo "  - $W"
  done
  echo "  These modules may be orphaned. Verify they have consumers."
fi
```

Wiring verification is advisory (warning only). Use `python -m zerg.validate_commands --strict-wiring` to enforce.

### Step 5.6: Update Task System After Merge

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

## Help

When `--help` is passed in `$ARGUMENTS`, display usage and exit:

```
/zerg:merge — Manually trigger or manage level merge operations.

Flags:
  --force               Force merge even if quality gates fail
  --help                Show this help message
```
