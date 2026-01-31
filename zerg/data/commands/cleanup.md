# ZERG Cleanup

Remove ZERG artifacts and clean up resources.

## Usage

```bash
# Clean specific feature
zerg cleanup --feature user-auth

# Clean all features
zerg cleanup --all

# Preview what will be cleaned
zerg cleanup --all --dry-run

# Keep logs for debugging
zerg cleanup --feature user-auth --keep-logs
```

## CLI Flags

```
zerg cleanup [OPTIONS]

Options:
  -f, --feature TEXT   Feature to clean (required unless --all)
  --all                Clean all ZERG features
  --keep-logs          Preserve log files
  --keep-branches      Preserve git branches
  --dry-run            Show cleanup plan without executing
```

## Pre-Flight

```bash
FEATURE=$(cat .gsd/.current-feature 2>/dev/null)
TASK_LIST=${CLAUDE_CODE_TASK_LIST_ID:-$FEATURE}
```

## Task Archive

Before removing state, archive the task list:
1. Call TaskList to get all tasks for this feature
2. Write to `.zerg/archive/{feature}/tasks-{timestamp}.json`
3. Log: "Archived {N} tasks to .zerg/archive/{feature}/"

## Cleanup Scope

### What Gets Removed

| Resource | Path/Pattern | Removed |
|----------|--------------|---------|
| Worktrees | `.zerg/worktrees/{feature}-worker-*` | Yes |
| State files | `.zerg/state/{feature}.json` | Yes |
| Log files | `.zerg/logs/worker-*.log` | Unless --keep-logs |
| Git branches | `zerg/{feature}/*` | Unless --keep-branches |
| Containers | `zerg-worker-{feature}-*` | Yes |

### What's Preserved

- Source code and commits on main branch
- Merged changes (already in target branch)
- Spec files (`.gsd/specs/{feature}/`)
- Task graph and design docs
- Task history (`.zerg/archive/{feature}/`)

## Dry Run Mode

Always preview first:

```bash
# See what will be cleaned
zerg cleanup --all --dry-run
```

Output:

```
╭─────────────────────────────────────────────────────╮
│                Cleanup Plan (DRY RUN)               │
├──────────────────┬──────────────────────────────────┤
│ Category         │ Items                      Count │
├──────────────────┼──────────────────────────────────┤
│ Features         │ user-auth, payment-api         2 │
│ Worktrees        │ user-auth-worker-0, ...        5 │
│ Branches         │ zerg/user-auth/*, ...         10 │
│ Container pats   │ zerg-worker-user-auth-*        2 │
│ State files      │ .zerg/state/user-auth.json     2 │
│ Log files        │ 15 files                      15 │
╰──────────────────┴──────────────────────────────────╯

Dry run - no changes made
```

## Selective Cleanup

### Keep Logs

Keep logs for post-mortem analysis:

```bash
zerg cleanup --feature user-auth --keep-logs
```

### Keep Branches

Keep branches for manual inspection:

```bash
zerg cleanup --feature user-auth --keep-branches
```

### Full Cleanup

Remove everything:

```bash
zerg cleanup --all
```

## Recovery

### Before Cleanup

If you might need to resume:

```bash
# Check status first
zerg status

# Export logs
zerg logs --json > feature-logs.jsonl

# Backup state
cp .zerg/state/feature.json feature-backup.json
```

### After Accidental Cleanup

Branches can be recovered from git reflog:

```bash
# Find deleted branch
git reflog | grep "zerg/feature"

# Recover branch
git checkout -b zerg/feature/worker-0 abc1234
```

Worktrees must be recreated with `zerg rush`.

## Examples

```bash
# Normal cleanup after completion
zerg cleanup --feature user-auth

# Debug failed feature
zerg cleanup --feature user-auth --keep-logs

# Full project reset
zerg cleanup --all --dry-run  # preview
zerg cleanup --all            # execute

# Selective cleanup
zerg cleanup --feature old-feature --keep-branches
```

## Integration

Typical workflow:

```bash
# After successful completion
zerg status                           # Verify complete
zerg cleanup --feature user-auth      # Clean up

# After failure analysis
zerg logs --level error              # Analyze issues
zerg cleanup --feature user-auth --keep-logs  # Keep logs
```

## Automation

For CI/CD pipelines:

```bash
# Non-interactive cleanup
zerg cleanup --all --dry-run && \
  echo "y" | zerg cleanup --all
```

## Task Tracking

On invocation, create a Claude Code Task to track this command:

Call TaskCreate:
  - subject: "[Cleanup] Clean {feature}"
  - description: "Removing ZERG artifacts for {feature}. Flags: {flags}."
  - activeForm: "Cleaning up {feature}"

Immediately call TaskUpdate:
  - taskId: (the Claude Task ID)
  - status: "in_progress"

On completion, call TaskUpdate:
  - taskId: (the Claude Task ID)
  - status: "completed"

**Task History Cleanup:**

After cleaning artifacts, ask the user whether to delete task history:

Call AskUserQuestion:
  - "Delete task history for {feature}?"
  - Options: "Keep as history" / "Delete tasks"

If user chooses "Delete tasks":
  - Call TaskList to find all tasks with subject prefix matching the feature (e.g., `[L1]`, `[L2]`, `[Plan]`, `[Design]`)
  - For each matching task, call TaskUpdate with status "deleted"

## Safety Features

1. **Dry run by default**: Preview shows exact resources
2. **Confirmation prompt**: Must confirm before execution
3. **Feature required**: Must specify feature or --all
4. **Preserves spec files**: Design docs never deleted
5. **Git reflog**: Branches recoverable for 30 days

## Help

When `--help` is passed in `$ARGUMENTS`, display usage and exit:

```
/zerg:cleanup — Remove ZERG artifacts and clean up resources.

Flags:
  -f, --feature TEXT  Feature to clean (required unless --all)
  --all               Clean all ZERG features
  --keep-logs         Preserve log files
  --keep-branches     Preserve git branches
  --dry-run           Show cleanup plan without executing
  --help              Show this help message
```
