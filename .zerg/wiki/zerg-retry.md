# /zerg:retry

Retry failed or blocked tasks.

## Synopsis

```
/zerg:retry [TASK_IDS]... [OPTIONS]
```

## Description

`/zerg:retry` identifies failed tasks, resets their state, and re-queues them for execution. It can target specific tasks, all failed tasks in a level, or all failed tasks across the feature.

### Retry Protocol

For each task being retried, the command:

1. **Identifies failed tasks** from the state file and Claude Code Task system.
2. **Analyzes the failure** by checking error messages, worker logs, dependency state, and file ownership.
3. **Resets task state** to `pending` in the state JSON, clears the error, and increments the retry counter.
4. **Updates the Task system** via `TaskUpdate` with retry annotations.
5. **Checks retry limits** against the configured maximum (from `.zerg/config.yaml`).
6. **Assigns to a worker** -- either an idle worker or a newly spawned one.

### Retry Strategies

| Strategy | Command | Description |
|----------|---------|-------------|
| Single task | `/zerg:retry TASK-001` | Retry one specific task |
| Level retry | `/zerg:retry --level 2` | Retry all failed tasks in a level |
| Full retry | `/zerg:retry --all` | Retry all failed and blocked tasks |
| Force retry | `/zerg:retry --force TASK-001` | Bypass retry limit, reset counter to 0 |

### Common Failure Patterns

| Pattern | Cause | Resolution |
|---------|-------|------------|
| Verification failed | Task output does not pass its verification command | Inspect verification output, fix code, then retry |
| Worker crashed | Resource exhaustion or runtime error | Check worker logs, adjust resource limits |
| Dependency not found | Upstream task incomplete or its output missing | Retry the dependency task first |
| Timeout | Task exceeded allowed execution time | Increase timeout with `--timeout` or break into smaller tasks |

## Options

| Option | Description |
|--------|-------------|
| `TASK_IDS` | Optional. One or more specific task IDs to retry |
| `-l`, `--level INTEGER` | Retry all failed tasks in the specified level |
| `-a`, `--all` | Retry all failed tasks across the feature |
| `-f`, `--force` | Bypass retry limit and reset retry counter |
| `-t`, `--timeout INTEGER` | Override timeout in seconds for retried tasks |
| `--reset` | Reset retry counters to zero |
| `--dry-run` | Show what would be retried without taking action |
| `-v`, `--verbose` | Verbose output |

## Prerequisites

- `/zerg:rush` must have been run (state file must exist)
- An active feature must be set in `.gsd/.current-feature`

## Examples

```bash
# Retry all failed tasks
/zerg:retry

# Retry a specific task
/zerg:retry TASK-003

# Retry all failed tasks in level 2
/zerg:retry --level 2

# Retry everything
/zerg:retry --all

# Force retry past the limit
/zerg:retry --force TASK-003

# Retry with increased timeout
/zerg:retry --timeout 3600

# Preview without executing
/zerg:retry --dry-run

# Reset retry counters and retry
/zerg:retry --reset
```

## Investigating Failures Before Retry

```bash
# View task error details from state
jq '.tasks["TASK-003"]' .zerg/state/<feature>.json

# View worker logs for the task
/zerg:logs --task TASK-003

# View verification output
/zerg:logs --artifacts TASK-003

# Check verification command manually
cat .gsd/specs/<feature>/task-graph.json | jq '.tasks[] | select(.id == "TASK-003") | .verification'
```

## See Also

- [[zerg-rush]] -- Original execution command
- [[zerg-logs]] -- Investigate failures before retrying
- [[zerg-status]] -- Check overall progress
- [[zerg-stop]] -- Tasks may need retry after a forced stop
- [[zerg-Reference]] -- Full command index
