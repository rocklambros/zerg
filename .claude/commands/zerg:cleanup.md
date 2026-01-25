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

## Safety Features

1. **Dry run by default**: Preview shows exact resources
2. **Confirmation prompt**: Must confirm before execution
3. **Feature required**: Must specify feature or --all
4. **Preserves spec files**: Design docs never deleted
5. **Git reflog**: Branches recoverable for 30 days
