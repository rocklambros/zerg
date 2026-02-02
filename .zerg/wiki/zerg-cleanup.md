# /zerg:cleanup

Remove ZERG artifacts and clean up resources after a feature is complete or abandoned.

## Synopsis

```
/zerg:cleanup [OPTIONS]
```

## Description

`/zerg:cleanup` removes temporary resources created during ZERG execution, including git worktrees, worker branches, Docker containers, state files, and log files. It preserves spec files, design documents, merged code, and task archives.

Before removing any state, the command archives the Claude Code Task list to `.zerg/archive/<feature>/tasks-<timestamp>.json`.

### What Gets Removed

| Resource | Path / Pattern | Removed |
|----------|----------------|---------|
| Git worktrees | `.zerg/worktrees/<feature>-worker-*` | Yes |
| State files | `.zerg/state/<feature>.json` | Yes |
| Log files | `.zerg/logs/worker-*.log` | Unless `--keep-logs` |
| Git branches | `zerg/<feature>/*` | Unless `--keep-branches` |
| Docker containers | `zerg-worker-<feature>-*` | Yes |

### What Is Preserved

- Source code and commits on the main branch
- Merged changes already in the target branch
- Spec files in `.gsd/specs/<feature>/` (requirements, design, task graph)
- Task archive in `.zerg/archive/<feature>/`

## Options

| Option | Description |
|--------|-------------|
| `-f`, `--feature TEXT` | Feature to clean up (required unless `--all` is specified) |
| `--all` | Clean up all ZERG features |
| `--keep-logs` | Preserve log files for post-mortem analysis |
| `--keep-branches` | Preserve git branches for manual inspection |
| `--dry-run` | Show the cleanup plan without executing |

## Examples

```bash
# Clean up a specific feature
/zerg:cleanup --feature user-auth

# Preview what will be cleaned
/zerg:cleanup --all --dry-run

# Clean all features
/zerg:cleanup --all

# Keep logs for debugging
/zerg:cleanup --feature user-auth --keep-logs

# Keep branches for inspection
/zerg:cleanup --feature user-auth --keep-branches
```

## Dry Run

Always preview before cleaning:

```bash
/zerg:cleanup --all --dry-run
```

The dry run output lists every resource that would be removed, grouped by category (worktrees, branches, containers, state files, log files), with item counts.

## Recovery

### Before Cleanup

If you might need to resume later:

```bash
# Check status first
/zerg:status

# Export logs
/zerg:logs --json > feature-logs.jsonl

# Backup state
cp .zerg/state/<feature>.json feature-backup.json
```

### After Accidental Cleanup

Git branches can be recovered from the reflog for up to 30 days:

```bash
# Find the deleted branch
git reflog | grep "zerg/<feature>"

# Recover the branch
git checkout -b zerg/<feature>/worker-0 <commit-hash>
```

Worktrees must be recreated by running `/zerg:rush` again.

## Safety Features

1. **Dry run support** -- Preview shows exact resources before removal.
2. **Confirmation prompt** -- Interactive confirmation before executing.
3. **Feature required** -- Must specify `--feature` or `--all` explicitly.
4. **Spec preservation** -- Design documents and requirements are never deleted.
5. **Task archival** -- Task history is archived before removal.
6. **Git reflog** -- Deleted branches remain recoverable for 30 days.

## See Also

- [[zerg-status]] -- Verify completion before cleanup
- [[zerg-logs]] -- Export logs before cleanup
- [[zerg-stop]] -- Stop workers before cleanup if still running
- [[zerg-Reference]] -- Full command index
