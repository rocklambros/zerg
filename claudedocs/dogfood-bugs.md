# ZERG Dogfood Bug Tracker

Tracking bugs discovered during production dogfooding runs.

## Categories

| Category | Description |
|----------|-------------|
| orchestrator | Task scheduling, level management, main loop |
| worker | Task execution, Claude invocation, context tracking |
| merge | Branch merging, conflict resolution, rebase |
| state-ipc | State file read/write, worker-orchestrator sync |
| launcher | Process/container spawning, health checks |
| plugin | Plugin loading, hooks, gates, lifecycle events |

## Severity Levels

| Level | Description | Response |
|-------|-------------|----------|
| P0 | Blocker — stops rush execution | Fix immediately |
| P1 | Major — task failures, data loss | Fix before next rush |
| P2 | Minor — cosmetic, non-blocking | Fix when convenient |

## Bug Template

### BUG-XXX: [Title]
- **Severity**: P0/P1/P2
- **Category**: orchestrator/worker/merge/state-ipc/launcher/plugin
- **Discovered**: YYYY-MM-DD
- **Status**: Open/In Progress/Fixed
- **Feature**: [feature name]
- **Repro**: [steps to reproduce]
- **Expected**: [expected behavior]
- **Actual**: [actual behavior]
- **Root Cause**: [analysis]
- **Fix**: [commit hash or PR]

---

## Bugs

### BUG-001: /zerg:rush --container bypasses Orchestrator pipeline
- **Severity**: P0
- **Category**: orchestrator
- **Discovered**: 2026-01-29
- **Status**: Open
- **Feature**: production-dogfooding
- **Repro**: Run `/zerg:rush --workers 5 --container` in a Claude Code session
- **Expected**: The rush command invokes `Orchestrator.start()` with `launcher_mode="container"`, which spawns Docker containers via `ContainerLauncher`, creates git worktrees, runs workers through the full `WorkerProtocol` pipeline, and coordinates level-by-level execution with merge gates.
- **Actual**: The rush command dispatches tasks as Claude Code Task sub-agents, completely bypassing the Orchestrator, ContainerLauncher, git worktrees, state IPC, and merge coordination. No Docker containers are started regardless of the `--container` flag.
- **Root Cause**: The `/zerg:rush` command documents three execution modes (lines 349-413 of `zerg:rush.md`): container, subprocess, and task-tool. Auto-detection logic (lines 356-359) selects task-tool mode when running as a Claude Code slash command (rule 3), even when `--container` is explicitly passed. Rule 1 ("If `--mode` is explicitly set → use that mode") should take precedence, but the executing agent ignored the explicit flag and defaulted to task-tool mode.
- **Fix**: Two changes needed: (1) The executing agent must honor explicit `--mode`/`--container` flags per rule 1 of the auto-detection logic. When `--container` is specified, invoke `Orchestrator(feature=feature, launcher_mode="container").start(task_graph_path, worker_count)` via Python subprocess instead of dispatching Task sub-agents. (2) Add a guard in the rush command file that explicitly rejects task-tool mode when `--container` or `--mode container` is passed.

### BUG-002: No verification that container mode was actually used
- **Severity**: P1
- **Category**: launcher
- **Discovered**: 2026-01-29
- **Status**: Open
- **Feature**: production-dogfooding
- **Repro**: Complete a rush with `--container` flag
- **Expected**: Post-rush status or logs should confirm container mode was active (container IDs, Docker network, worktree paths)
- **Actual**: No diagnostic output confirms or denies container mode usage. The user had to explicitly ask `/zerg:debug` to discover containers were never used.
- **Root Cause**: The rush completion output does not include launcher mode verification. Neither `/zerg:status` nor the rush summary reports which launcher mode was active.
- **Fix**: Add launcher mode to rush summary output and `/zerg:status` response. Include container IDs in worker status when container mode is active.
