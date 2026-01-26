# ZERG Merge

Manually trigger or manage level merge operations.

## Pre-Flight

```bash
FEATURE=$(cat .gsd/.current-feature 2>/dev/null)
STATE_FILE=".zerg/state/$FEATURE.json"
SPEC_DIR=".gsd/specs/$FEATURE"

# Validate prerequisites
[ -z "$FEATURE" ] && { echo "ERROR: No active feature"; exit 1; }
[ ! -f "$STATE_FILE" ] && { echo "ERROR: No state file found"; exit 1; }
```

## Usage

```bash
# Merge current level (after all workers complete)
zerg merge

# Merge specific level
zerg merge --level 2

# Force merge with conflicts
zerg merge --force

# Dry run - show merge plan
zerg merge --dry-run

# Abort in-progress merge
zerg merge --abort
```

## Merge Protocol

### Step 1: Check Level Completion

```bash
CURRENT_LEVEL=$(jq '.current_level' "$STATE_FILE")
LEVEL_STATUS=$(jq ".levels[\"$CURRENT_LEVEL\"].status" "$STATE_FILE")

# All tasks must be complete
PENDING=$(jq "[.tasks | to_entries[] | select(.value.level == $CURRENT_LEVEL and .value.status != \"complete\")] | length" "$STATE_FILE")

if [ "$PENDING" -gt 0 ]; then
  echo "ERROR: Level $CURRENT_LEVEL has $PENDING incomplete tasks"
  echo "Wait for tasks to complete or use --force to merge partial results"
  exit 1
fi
```

### Step 2: Collect Worker Branches

```bash
# Get all worker branches for this level
BRANCHES=$(jq -r ".workers | to_entries[] | .value.branch" "$STATE_FILE")

echo "Collecting branches for merge:"
for branch in $BRANCHES; do
  echo "  - $branch"

  # Verify branch exists and has commits
  if ! git rev-parse --verify "$branch" >/dev/null 2>&1; then
    echo "    WARNING: Branch does not exist"
  fi
done
```

### Step 3: Create Staging Branch

```bash
STAGING_BRANCH="zerg/$FEATURE/staging-level-$CURRENT_LEVEL"
BASE_BRANCH=$(jq -r '.base_branch // "main"' "$STATE_FILE")

# Create staging from base
git checkout -B "$STAGING_BRANCH" "$BASE_BRANCH"
```

### Step 4: Merge Worker Branches

```bash
for branch in $BRANCHES; do
  echo "Merging $branch..."

  if git merge --no-ff "$branch" -m "Merge $branch into staging"; then
    echo "  ✓ Merged successfully"
  else
    echo "  ✗ Merge conflict detected"

    # Record conflicting files
    git diff --name-only --diff-filter=U > ".zerg/conflicts-level-$CURRENT_LEVEL.txt"

    if [ "$FORCE" != "true" ]; then
      echo "Aborting merge. Use --force to continue with conflicts"
      git merge --abort
      exit 1
    fi
  fi
done
```

### Step 5: Run Quality Gates

```bash
echo "Running quality gates on merged code..."

# Run lint
if ! ruff check .; then
  echo "WARNING: Lint failed"
  GATE_FAILURES+=("lint")
fi

# Run tests
if ! pytest tests/ -v --tb=short; then
  echo "WARNING: Tests failed"
  GATE_FAILURES+=("test")
fi

# Run type check
if ! mypy . --ignore-missing-imports; then
  echo "WARNING: Type check failed"
  GATE_FAILURES+=("typecheck")
fi

if [ ${#GATE_FAILURES[@]} -gt 0 ]; then
  echo "Quality gates failed: ${GATE_FAILURES[*]}"

  if [ "$FORCE" != "true" ]; then
    echo "Aborting merge. Fix issues or use --force"
    exit 1
  fi
fi
```

### Step 6: Finalize Merge

```bash
# Tag the merge point
git tag "zerg/$FEATURE/level-$CURRENT_LEVEL-complete"

# Update state
jq ".levels[\"$CURRENT_LEVEL\"].status = \"complete\" | .levels[\"$CURRENT_LEVEL\"].merge_commit = \"$(git rev-parse HEAD)\"" "$STATE_FILE" > tmp && mv tmp "$STATE_FILE"

echo "Level $CURRENT_LEVEL merge complete"
```

### Step 7: Rebase Worker Branches

```bash
echo "Rebasing worker branches onto merged base..."

for branch in $BRANCHES; do
  git checkout "$branch"

  if git rebase "$STAGING_BRANCH"; then
    echo "  ✓ $branch rebased"
  else
    echo "  ✗ Rebase conflict for $branch"
    git rebase --abort

    # Mark for manual intervention
    jq ".workers[] | select(.branch == \"$branch\") | .needs_rebase = true" "$STATE_FILE" > tmp && mv tmp "$STATE_FILE"
  fi
done

# Return to staging
git checkout "$STAGING_BRANCH"
```

## Conflict Resolution

When merge conflicts occur:

### Option 1: Resolve Manually
```bash
# View conflicting files
cat .zerg/conflicts-level-N.txt

# Edit files to resolve conflicts
vim <conflicting-file>

# Mark as resolved
git add <resolved-file>

# Continue merge
git commit -m "Resolve merge conflicts for level N"
```

### Option 2: Accept One Side
```bash
# Accept worker's version
git checkout --theirs <file>

# Accept base version
git checkout --ours <file>
```

### Option 3: Re-run Task
```bash
# Identify which worker's task caused conflict
# Re-run that task on the merged base

zerg retry TASK-ID --on-base
```

## Output

```
═══════════════════════════════════════════════════════════════
                    ZERG MERGE
═══════════════════════════════════════════════════════════════

Feature: {feature}
Level: 2 of 5
Status: Ready for merge

Worker Branches:
┌──────────┬──────────────────────────────┬──────────┬──────────┐
│ Worker   │ Branch                       │ Commits  │ Status   │
├──────────┼──────────────────────────────┼──────────┼──────────┤
│ worker-0 │ zerg/{feature}/worker-0      │ 3        │ Ready    │
│ worker-1 │ zerg/{feature}/worker-1      │ 2        │ Ready    │
│ worker-2 │ zerg/{feature}/worker-2      │ 4        │ Ready    │
└──────────┴──────────────────────────────┴──────────┴──────────┘

Merge Progress:
[1/5] Creating staging branch... ✓
[2/5] Merging worker-0... ✓
[3/5] Merging worker-1... ✓
[4/5] Merging worker-2... ✓
[5/5] Running quality gates...
      - lint: ✓
      - test: ✓
      - typecheck: ✓

═══════════════════════════════════════════════════════════════
Level 2 merge complete!

Merge commit: abc123def456
Tag: zerg/{feature}/level-2-complete

Next: Level 3 tasks are now unblocked.
Run /zerg:status to see progress.
═══════════════════════════════════════════════════════════════
```

## CLI Flags

```
zerg merge [OPTIONS]

Options:
  -l, --level INTEGER   Merge specific level (default: current)
  -f, --force           Force merge despite conflicts/failures
  --abort               Abort in-progress merge
  --dry-run             Show merge plan without executing
  --skip-gates          Skip quality gate checks
  --no-rebase           Don't rebase worker branches after merge
  -v, --verbose         Verbose output
```

## Merge States

| State | Description |
|-------|-------------|
| `pending` | Level not yet complete |
| `waiting` | Waiting for workers to finish |
| `collecting` | Gathering worker branches |
| `merging` | Merge in progress |
| `validating` | Running quality gates |
| `rebasing` | Rebasing worker branches |
| `complete` | Merge successful |
| `conflict` | Manual intervention needed |
| `failed` | Merge or validation failed |

## Troubleshooting

### "Level has incomplete tasks"
- Wait for tasks to complete
- Check for blocked/failed tasks with `/zerg:status`
- Use `--force` only if you're sure partial merge is acceptable

### "Merge conflict detected"
- Review conflicting files in `.zerg/conflicts-level-N.txt`
- Resolve conflicts manually or re-run affected task
- Use `--force` to continue with conflicts (not recommended)

### "Quality gates failed"
- Review gate output in logs
- Fix issues on staging branch
- Or use `--skip-gates` (not recommended for production)

### "Rebase failed"
- Worker branch diverged significantly
- Manual rebase may be needed
- Consider re-creating worker branch from staging
