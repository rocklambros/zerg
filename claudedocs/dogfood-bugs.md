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

(No bugs found yet — add entries as discovered during dogfooding runs.)
