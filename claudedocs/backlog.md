# ZERG Development Backlog

**Updated**: 2026-01-29

## Completed

| # | Item | Completed | Commit |
|---|------|-----------|--------|
| 1 | State file IPC: Workers write WorkerState, orchestrator reloads in poll loop | 2026-01-28 | a189fc7 |
| 2 | Container execution: Docker image, ContainerLauncher, resource limits, health checks, security hardening | 2026-01-28 | ce7d58e |
| 4 | Debug cleanup: Gate verbose diagnostic details behind `--verbose` in troubleshoot.py | 2026-01-28 | 763ef8c |
| 3 | Test coverage: 96.53% coverage across 64 modules (4468 tests), P0 files all at 100% | 2026-01-28 | 06abc7c + 1dc4f8e |
| 6 | Log aggregation: Structured JSONL logging per worker, per-task artifact capture, read-side aggregation, CLI query/filter | 2026-01-29 | a0b6e66 |

## Backlog

| # | Area | Description | Effort | Status |
|---|------|-------------|--------|--------|
| 5 | Production dogfooding | Never tested against a real feature build end-to-end | Large | Open |
| 7 | Task retry logic | Auto-retry failed tasks with backoff, max attempts | Medium | Open |
| 8 | Dry-run improvements | Better simulation of rush without actual execution | Medium | Open |
| 9 | Troubleshoot enhancement | Improve `/zerg:troubleshoot` to be a world-class debugger — deep root-cause analysis, automated log correlation, hypothesis testing, fix suggestions, environment diagnostics, and structured resolution workflows | Large | Open |
| 10 | `/z` shortcut alias | Create `/z` shortcut for all `/zerg` commands (e.g., `/z:rush`, `/z:status`). Support both prefixes with full autocomplete parity | Medium | Open |
| 11 | Rename troubleshoot → debug | Rename `/zerg:troubleshoot` to `/zerg:debug` (and `zerg troubleshoot` to `zerg debug`). Cascade rename across all code, commands, docs, tests, and references project-wide | Medium | Open |
