# /zerg:status

Display current execution status and progress.

## Synopsis

```
/zerg:status [OPTIONS]
```

## Description

`/zerg:status` produces a snapshot of the current ZERG execution state, including feature name, phase, orchestrator status, elapsed time, and per-level progress bars.

### Data Sources

The command uses two data sources:

1. **Claude Code Task system** (primary) -- Retrieves task statuses via `TaskList`. This is the authoritative source of truth.
2. **State JSON** (supplementary) -- Reads `.zerg/state/<feature>.json` for worker assignment details not stored in the Task system.

If the two sources disagree, the Task system takes precedence. Mismatches are flagged in the output.

### Phases

The status report shows the current phase of the feature:

| Phase | Description |
|-------|-------------|
| PLANNING | Requirements gathering in progress |
| DESIGNING | Architecture and task graph generation |
| EXECUTING | Workers actively running tasks |
| MERGING | Level merge in progress |
| COMPLETE | All tasks finished |

## Options

| Option | Description |
|--------|-------------|
| `--tasks` | Show detailed per-task status with individual task states |
| `--dashboard` | Launch live TUI dashboard (requires separate terminal) |
| `--watch` | Auto-refresh text-based status display |
| `--interval N` | Refresh interval in seconds for `--watch` mode (default: 5) |
| `--json` | Output status as JSON for scripting |

## Examples

```bash
# One-shot status check
/zerg:status

# Detailed task list
/zerg:status --tasks

# Live TUI dashboard (run in a separate terminal during rush)
/zerg:status --dashboard

# Auto-refreshing text output
/zerg:status --watch --interval 2

# JSON output for scripting
/zerg:status --json
```

## Output

A typical status report:

```
======================================================================
                         FACTORY STATUS
======================================================================

Feature:      user-auth
Phase:        EXECUTING
Orchestrator: Running (PID: 12345)
Started:      2026-01-28T10:30:00Z
Elapsed:      00:15:32

----------------------------------------------------------------------
                              PROGRESS
----------------------------------------------------------------------

Task System: 8/12 tasks (2 pending, 2 active)
Overall: [=============>        ] 67% (8/12 tasks)

Level 1 (Foundation):   [====================] Complete (3/3 tasks)
Level 2 (Core):         [=============>      ] In Progress (3/4 tasks)
Level 3 (Integration):  [                    ] Pending (0/3 tasks)
Level 4 (Testing):      [                    ] Pending (0/2 tasks)

======================================================================

Commands:
  /zerg:logs {N}      View logs from worker N
  /zerg:stop          Stop all workers
  /zerg:retry {ID}    Retry a failed task

======================================================================
```

## See Also

- [[zerg-rush]] -- Starts the execution that status monitors
- [[zerg-logs]] -- Detailed worker and task logs
- [[zerg-stop]] -- Stop execution
- [[zerg-Reference]] -- Full command index
