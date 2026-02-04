# Requirements: Rush Performance Fix

## Metadata
- **Feature**: rush-perf-fix
- **Status**: APPROVED
- **Created**: 2026-02-04
- **Source**: Debug investigation of slow rush execution

---

## Problem Statement

ZERG rush execution is PAINFULLY slow due to excessive Docker subprocess calls in the container monitoring loop. The poll loop runs every 5 seconds and executes `docker inspect` + `docker exec` for EVERY worker, causing 120+ Docker calls per minute.

### Root Cause (from `/z:debug --deep`)

**Location**: `zerg/launcher.py:1457-1527` (`ContainerLauncher.monitor()`)

**Impact with 5 workers**:
- Normal case: 5 × (inspect + exec) = 10 calls × ~100ms = 1000ms per poll
- 120+ docker subprocess calls per minute
- 10-20% of poll time spent on monitoring overhead

---

## Functional Requirements

### FR-1: Monitor Status Caching
Add a cooldown to `ContainerLauncher.monitor()` to skip Docker calls if status was checked recently.

- Cache validity: 10 seconds (configurable)
- Return cached `handle.status` if last check < cooldown
- Update `handle.health_check_at` after each actual Docker check
- Must handle edge case: newly spawned workers (no cached status yet)

### FR-2: Increase Poll Interval
Change orchestrator poll interval from 5 seconds to 15 seconds.

- Modify `self._poll_interval` in `zerg/orchestrator.py`
- Worker state changes are infrequent; 15s is sufficient
- Keep 5s available as config option for debugging

### FR-3: Batch Docker Inspect (Optional/Future)
Instead of calling `docker inspect` N times, call once for all containers.

- Single subprocess call: `docker inspect container1 container2 ...`
- Parse JSON output for all containers
- Lower priority — FR-1 and FR-2 provide most benefit

### FR-4: Singleton HeartbeatMonitor
Cache HeartbeatMonitor instance in SubprocessLauncher instead of creating new one every `monitor()` call.

- Move instantiation to `__init__` or use lazy singleton
- Reduces object allocation overhead

---

## Non-Functional Requirements

### NFR-1: Security
- No new subprocess calls with user input
- Maintain existing security posture
- No changes to container isolation

### NFR-2: Quality
- All existing tests must pass
- Add unit tests for caching logic
- Add integration test for poll interval behavior

### NFR-3: Performance
- Reduce Docker calls from 120+/min to ~20-30/min
- Reduce monitoring overhead from 20% to <5% of poll time
- Expected rush speedup: 15-20%

---

## Verification Commands

```bash
# Unit tests pass
pytest tests/unit/test_launcher.py -v

# Integration tests pass
pytest tests/integration/ -v -k "launcher or orchestrator"

# Performance verification (manual)
# Run rush with 5 workers, observe docker calls via:
# docker events --filter type=container --since 1m | grep inspect
```

---

## Out of Scope

- Refactoring entire monitoring architecture
- Docker events API integration (too invasive)
- Container health via Docker HEALTHCHECK (already exists, not the issue)

---

## Acceptance Criteria

1. ✅ `ContainerLauncher.monitor()` skips Docker calls if checked < 10s ago
2. ✅ Poll interval increased to 15 seconds
3. ✅ `SubprocessLauncher` reuses HeartbeatMonitor instance
4. ✅ All existing tests pass
5. ✅ New tests for caching behavior
