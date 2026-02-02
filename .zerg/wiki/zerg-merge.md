# /zerg:merge

Manually trigger or manage level merge operations.

## Synopsis

```
/zerg:merge [OPTIONS]
```

## Description

`/zerg:merge` combines worker branches into a staging branch after all tasks in a level complete. It runs quality gates (lint, tests, type checking) on the merged result and rebases worker branches onto the new base for the next level.

During normal execution, the orchestrator triggers merges automatically between levels. This command is primarily used for manual intervention or recovery scenarios.

### Merge Protocol

The command follows a seven-step protocol:

1. **Check Level Completion** -- Verifies all tasks in the current level are complete. Aborts if any are pending (unless `--force` is used).

2. **Collect Worker Branches** -- Gathers all worker branches that have commits for this level.

3. **Create Staging Branch** -- Creates `zerg/<feature>/staging-level-<N>` from the base branch.

4. **Merge Worker Branches** -- Merges each worker branch into staging with `--no-ff`. Records conflicts to `.zerg/conflicts-level-<N>.txt` if any occur.

5. **Run Quality Gates** -- Executes lint (`ruff check`), tests (`pytest`), and type checking (`mypy`) on the merged code. Gate failures block the merge unless `--force` or `--skip-gates` is used.

6. **Finalize Merge** -- Tags the merge point as `zerg/<feature>/level-<N>-complete`, updates the state file, and confirms Task system consistency.

7. **Rebase Worker Branches** -- Rebases all worker branches onto the staging branch so they have the merged code for the next level.

### Merge States

| State | Description |
|-------|-------------|
| `pending` | Level not yet started |
| `waiting` | Waiting for workers to finish |
| `collecting` | Gathering worker branches |
| `merging` | Merge in progress |
| `validating` | Running quality gates |
| `rebasing` | Rebasing worker branches |
| `complete` | Merge succeeded |
| `conflict` | Manual intervention needed |
| `failed` | Merge or validation failed |

### Conflict Resolution

When merge conflicts occur, three options are available:

1. **Resolve manually** -- Edit conflicting files, `git add` them, and commit.
2. **Accept one side** -- Use `git checkout --theirs <file>` or `git checkout --ours <file>`.
3. **Re-run the task** -- Use `/zerg:retry TASK-ID --on-base` to re-execute the conflicting task on the merged base.

## Options

| Option | Description |
|--------|-------------|
| `-l`, `--level INTEGER` | Merge a specific level (default: current level) |
| `-f`, `--force` | Force merge despite conflicts or quality gate failures |
| `--abort` | Abort an in-progress merge |
| `--dry-run` | Show the merge plan without executing |
| `--skip-gates` | Skip quality gate checks |
| `--no-rebase` | Skip rebasing worker branches after merge |
| `-v`, `--verbose` | Verbose output |

## Examples

```bash
# Merge the current level
/zerg:merge

# Merge a specific level
/zerg:merge --level 2

# Preview what the merge would do
/zerg:merge --dry-run

# Force merge with conflicts
/zerg:merge --force

# Abort an in-progress merge
/zerg:merge --abort

# Skip quality gates (not recommended for production)
/zerg:merge --skip-gates

# Merge without rebasing workers
/zerg:merge --no-rebase
```

## Troubleshooting

### "Level has incomplete tasks"

All tasks in the level must finish before merging. Check for blocked or failed tasks with `/zerg:status`. Use `--force` only if a partial merge is acceptable.

### "Merge conflict detected"

Review conflicting files listed in `.zerg/conflicts-level-<N>.txt`. Resolve manually or re-run the affected task. Avoid `--force` for conflicts as it may produce broken code.

### "Quality gates failed"

Review gate output in the logs. Fix issues on the staging branch, or use `--skip-gates` as a last resort.

### "Rebase failed"

A worker branch has diverged significantly from staging. Manual rebase may be necessary, or recreate the worker branch from staging.

## See Also

- [[zerg-rush]] -- Triggers merges automatically between levels
- [[zerg-status]] -- Check level completion before merging
- [[zerg-retry]] -- Re-run tasks that caused conflicts
- [[zerg-Reference]] -- Full command index
