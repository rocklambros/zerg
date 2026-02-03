# Requirements: Container Mode Resilience

**Feature:** issue-102-resilience
**Status:** APPROVED
**Created:** 2026-02-03
**Source:** GitHub Issue #102

---

## Problem Statement

During multi-container, multi-worker execution (`zerg rush --mode container --workers=3`), several resilience gaps cause rushes to stall at high completion percentages. A single stuck task can block level progression indefinitely, requiring manual intervention.

**Observed failure modes:**
1. Initial spawn failures with no auto-retry (transient Docker issues)
2. Tasks stuck in `in_progress` when workers crash mid-execution
3. State inconsistency: Level marked "DONE" while tasks still `in_progress`
4. Task `level=None` when claimed via stub (missing level parsing)
5. task-graph.json inaccessible inside containers (mount path issue)
6. No automatic task reassignment on worker crash

---

## Stakeholder Requirements

### Goal
Build a comprehensive resilience system that auto-recovers from transient failures, maintains state consistency, and prevents task starvation.

### Activation
- Resilience features enabled by default
- Configurable via `.zerg/config.yaml` for per-project tuning
- No explicit `--resilient` flag needed (always on)

---

## Functional Requirements

### FR-1: Spawn Retry with Exponential Backoff

**Description:** Retry worker spawning on transient failures before failing the rush.

**Behavior:**
- On spawn failure, retry up to N attempts (default: 3)
- Use exponential backoff: `base_seconds * 2^attempt` (default base: 2s)
- Maximum backoff cap (default: 30s)
- Log each retry attempt with reason
- After exhausting retries, fail gracefully with actionable error

**Configuration:**
```yaml
workers:
  spawn_retry_attempts: 3          # Default: 3
  spawn_backoff_strategy: exponential  # exponential|linear|fixed
  spawn_backoff_base_seconds: 2    # Default: 2
  spawn_backoff_max_seconds: 30    # Default: 30
```

**Location:** `zerg/launcher.py` — Add retry loop in `SubprocessLauncher.spawn()` and `ContainerLauncher.spawn()`

**Acceptance Criteria:**
- [ ] Spawn failures retry 3× with exponential backoff before failing
- [ ] Each retry attempt logged with timestamp and attempt number
- [ ] Config values respected when provided

---

### FR-2: Task Timeout Watchdog

**Description:** Auto-fail tasks stuck in `in_progress` beyond configurable timeout.

**Behavior:**
- Monitor all `in_progress` tasks during orchestrator main loop
- If task exceeds `task_stale_timeout` (default: 600s / 10 minutes) without heartbeat update, mark as failed
- Queue failed task for immediate reassignment to healthy worker
- Log timeout event with task ID, assigned worker, elapsed time

**Configuration:**
```yaml
workers:
  task_stale_timeout_seconds: 600  # Default: 10 minutes
```

**Location:** `zerg/task_retry_manager.py` — Add `check_stale_tasks()` method, call from orchestrator loop

**Acceptance Criteria:**
- [ ] Tasks in `in_progress` > timeout auto-fail and retry
- [ ] Timeout configurable via config
- [ ] Stale task events logged with full context

---

### FR-3: Enhanced Heartbeat System

**Description:** Replace existing stall detection with unified heartbeat monitoring.

**Behavior:**
- Workers emit heartbeat every 30s with: `{worker_id, timestamp, task_id, step, progress_pct}`
- Orchestrator marks worker stale if no heartbeat for 2 minutes (configurable)
- Stale workers trigger task reassignment (FR-5)
- Heartbeat files written atomically to `.zerg/state/heartbeat-{worker_id}.json`

**Configuration:**
```yaml
workers:
  heartbeat_interval_seconds: 30   # Default: 30
  heartbeat_stale_threshold: 120   # Default: 2 minutes
```

**Location:** `zerg/heartbeat.py` — Enhance `HeartbeatWriter` and `HeartbeatMonitor` (existing infrastructure)

**Acceptance Criteria:**
- [ ] Workers emit heartbeat every 30s during task execution
- [ ] Stale workers detected within 2× heartbeat interval
- [ ] Heartbeat includes task progress percentage

---

### FR-4: State Reconciliation

**Description:** Detect and resolve state inconsistencies between workers and orchestrator.

**Behavior:**
- **Periodic (every 60s):** Light check comparing task states, log divergence
- **On level transitions:** Thorough reconciliation before advancing
- Fix inconsistencies:
  - Tasks `in_progress` with dead workers → mark failed, requeue
  - Level marked "done" with incomplete tasks → recalculate level status
  - Task `level=None` → parse level from task ID pattern `*-L{level}-*`

**Level Completion Fix:**
```python
def is_level_complete(self, level: int) -> bool:
    tasks = self.get_tasks_for_level(level)
    return all(
        self._tasks[tid].get("status") in (TaskStatus.COMPLETE.value, TaskStatus.FAILED.value)
        for tid in tasks
    )
```

**Location:**
- `zerg/state_sync_service.py` — Add `StateReconciler` class
- `zerg/levels.py` — Fix `is_level_complete()` logic

**Acceptance Criteria:**
- [ ] Periodic state check every 60s during rush
- [ ] Thorough reconciliation on level transitions
- [ ] Level completion accurately reflects actual task states
- [ ] Task level always populated (parse from ID if needed)

---

### FR-5: Worker Crash Recovery with Task Reassignment

**Description:** When a worker crashes, immediately reassign its in-progress task to a healthy worker.

**Behavior:**
- Detect worker exit via process monitor or container health check
- If worker had `in_progress` task:
  1. Mark task as `failed` with reason "worker_crash"
  2. Reset task retry count (crash ≠ task bug)
  3. Reassign to healthy worker from pool
- If no healthy workers available, queue task for when workers recover

**Location:**
- `zerg/launcher.py` — Add `handle_worker_exit()` callback
- `zerg/orchestrator.py` — Implement reassignment logic

**Acceptance Criteria:**
- [ ] Worker crash triggers automatic task reassignment
- [ ] Crashed worker's task reassigned within 1 heartbeat interval
- [ ] Task retry count not incremented on crash (distinguishes crash from failure)

---

### FR-6: Auto-Respawn of Failed Workers

**Description:** Maintain worker count by automatically spawning replacements.

**Behavior:**
- Track target worker count from `--workers` flag
- When worker exits (crash or completion), check if below target
- Auto-spawn replacement using same configuration
- Use spawn retry logic (FR-1) for replacement spawns
- Cap respawn attempts to prevent infinite loops on systemic issues

**Configuration:**
```yaml
workers:
  auto_respawn: true              # Default: true
  max_respawn_attempts: 5         # Per-worker respawn cap
```

**Location:** `zerg/orchestrator.py` — Add respawn logic to worker exit handler

**Acceptance Criteria:**
- [ ] Failed workers auto-replaced to maintain target count
- [ ] Respawn uses same retry logic as initial spawn
- [ ] Respawn capped to prevent runaway loops

---

### FR-7: Container Mount Fix for task-graph.json

**Description:** Ensure task-graph.json is accessible inside containers.

**Current issue:** Container path to spec files differs from host path; workers can't read task definitions.

**Fix:**
```python
# In ContainerLauncher._start_container()
spec_dir = repo_path / ".gsd" / "specs" / feature
cmd.extend(["-v", f"{spec_dir.absolute()}:/workspace/.gsd/specs/{feature}:ro"])
```

**Location:** `zerg/launcher.py` — `ContainerLauncher._start_container()`

**Acceptance Criteria:**
- [ ] task-graph.json readable inside containers at expected path
- [ ] Workers no longer log "Task not found in graph, using stub"
- [ ] Container workers have full task context (description, verification, file ownership)

---

### FR-8: Structured Resilience Logging

**Description:** Write detailed resilience events to `.zerg/monitor.log` for debugging.

**Format:**
```
2026-02-03T05:41:55.123Z [W0] [INFO] Worker 0 claimed task A-L1-002
2026-02-03T05:41:55.456Z [W0] [INFO] Invoking Claude Code for A-L1-002
2026-02-03T05:42:30.789Z [W0] [ERROR] Claude Code failed: exit code 1
```

**Events to log:**
- Worker lifecycle: spawn/ready/exit/crash/respawn
- Task lifecycle: claim/start/complete/fail/timeout/reassign
- Heartbeat: stale detection, health check results
- State reconciliation: divergence detected, auto-fixes applied
- Container: health check, process verification

**Location:** `zerg/log_writer.py` — Enhance `StructuredLogWriter` for monitor.log output

**Acceptance Criteria:**
- [ ] All resilience events written to `.zerg/monitor.log`
- [ ] ISO8601 timestamps with milliseconds
- [ ] Worker ID prefix for correlation
- [ ] Structured enough for automated analysis

---

## Non-Functional Requirements

### NFR-1: Performance
- Heartbeat overhead < 1% CPU per worker
- State reconciliation < 100ms per check
- Spawn retry delays shouldn't block orchestrator loop (async)

### NFR-2: Reliability
- All state mutations use cross-process file locking (existing)
- Atomic writes for heartbeat files (existing)
- Graceful degradation if resilience features fail

### NFR-3: Observability
- All resilience decisions logged with rationale
- Metrics: stale detections, task reassignments, worker respawns
- Status command shows resilience health

---

## Configuration Schema

Add to `.zerg/config.yaml`:

```yaml
resilience:
  enabled: true                    # Master toggle (default: true)

workers:
  # Spawn retry
  spawn_retry_attempts: 3
  spawn_backoff_strategy: exponential
  spawn_backoff_base_seconds: 2
  spawn_backoff_max_seconds: 30

  # Task timeout
  task_stale_timeout_seconds: 600

  # Heartbeat
  heartbeat_interval_seconds: 30
  heartbeat_stale_threshold: 120

  # Worker management
  auto_respawn: true
  max_respawn_attempts: 5
```

---

---

### FR-9: 100% Module Wiring Verification

**Description:** Ensure all new modules have production callers — no orphaned code.

**Behavior:**
- Every new `.py` file in `zerg/` must be imported by at least one other production file
- Test-only imports don't count as production callers
- Standalone entry points (`__main__.py`, `if __name__`) are exempt
- Run `python -m zerg.validate_commands` to verify wiring
- CI and pre-commit hooks enforce this automatically

**Verification:**
```bash
# Check for orphaned modules
python -m zerg.validate_commands --check-wiring

# Expected output: "All modules properly wired" or list of orphans
```

**Acceptance Criteria:**
- [ ] All new resilience modules imported by production code
- [ ] `validate_commands` passes with no orphaned module warnings
- [ ] Design phase `consumers` field documents who calls each new module

---

### FR-10: GitHub Documentation Update

**Description:** Update all GitHub documentation to reflect resilience features.

**README.md Updates:**
- Add "Resilience" section under Features
- Document new config options in Configuration section
- Add troubleshooting entries for common resilience scenarios

**Wiki Pages to Create/Update:**
- `Resilience-Architecture.md` — Overview of resilience subsystems
- `Configuration-Reference.md` — Add all new `resilience:` and `workers:` options
- `Troubleshooting.md` — Add sections for:
  - "Tasks stuck in progress"
  - "Workers failing to spawn"
  - "Level not advancing"
  - "How to read monitor.log"
- `Container-Mode.md` — Update with resilience behavior in containers

**CHANGELOG.md:**
- Add entry under `[Unreleased]` → `Added` section

**Inline Documentation:**
- All new functions have docstrings
- Complex logic has explanatory comments
- Config schema has field descriptions

**Location:**
- `/README.md`
- `/docs/` or GitHub Wiki
- `/CHANGELOG.md`
- Inline in all modified `.py` files

**Acceptance Criteria:**
- [ ] README.md documents resilience features
- [ ] Wiki has dedicated Resilience-Architecture page
- [ ] Configuration-Reference includes all new options
- [ ] Troubleshooting covers common resilience scenarios
- [ ] CHANGELOG.md updated with feature entry
- [ ] All new code has docstrings

---

## Out of Scope

- Distributed state backend (Redis, etc.) — file-based state is sufficient
- Cross-machine orchestration — single-host container mode only
- Custom retry strategies per task — global config applies to all
- Web dashboard for monitoring — CLI/log-based observability

---

## Dependencies

- Existing: `circuit_breaker.py`, `heartbeat.py`, `task_retry_manager.py`, `retry_backoff.py`
- New modules: `state_reconciler.py` (or extend `state_sync_service.py`)
- Container mode: Docker daemon available, `zerg-worker` image built
- Documentation: GitHub Wiki write access, `gh` CLI for Wiki operations

---

## Acceptance Criteria Summary

Per GitHub Issue #102:
- [x] Spawn failures retry 3× with exponential backoff before failing
- [x] Tasks stuck `in_progress` > 10 minutes auto-fail and retry
- [x] Level completion accurately reflects actual task states
- [x] Task level is always populated (parse from ID if needed)
- [x] task-graph.json accessible inside containers
- [x] Worker crash triggers automatic task reassignment

Additional — Resilience:
- [x] Auto-respawn workers to maintain target count
- [x] Structured logging to `.zerg/monitor.log`
- [x] Configuration-driven timeouts and retry behavior

Additional — Quality:
- [x] 100% module wiring — no orphaned code, all imports verified
- [x] `python -m zerg.validate_commands` passes

Additional — Documentation:
- [x] README.md updated with resilience features
- [x] GitHub Wiki: Resilience-Architecture, Configuration-Reference, Troubleshooting
- [x] CHANGELOG.md entry added
- [x] All new code has docstrings

---

## Related

- GitHub Issue: #102
- GitHub Comment: Worker logging enhancement proposal
- Previous implementation: 95% completion stalled during `mega-issue-rush`

---

## Files Summary

**Code (modify):**
- `zerg/launcher.py` — Spawn retry, container mount fix, worker exit handling
- `zerg/task_retry_manager.py` — Stale task detection
- `zerg/heartbeat.py` — Enhanced heartbeat
- `zerg/levels.py` — Fix `is_level_complete()` logic
- `zerg/state_sync_service.py` — State reconciliation
- `zerg/log_writer.py` — Structured monitor.log output
- `zerg/config.py` — New resilience config fields
- `zerg/orchestrator.py` — Respawn logic, reassignment

**Code (possibly new):**
- `zerg/state_reconciler.py` — If not extending state_sync_service.py

**Documentation:**
- `README.md` — Resilience features section
- `CHANGELOG.md` — Unreleased entry
- `docs/wiki/Resilience-Architecture.md` — New
- `docs/wiki/Configuration-Reference.md` — Update
- `docs/wiki/Troubleshooting.md` — Update
- `docs/wiki/Container-Mode.md` — Update

**Tests:**
- Integration tests for all new resilience paths
- Unit tests for spawn retry, state reconciliation, heartbeat

---

## Next Steps

After approval:
1. Run `/z:design` to create technical architecture
2. Design will produce task-graph.json with:
   - Code implementation tasks (FR-1 through FR-8)
   - Wiring verification tasks (FR-9)
   - Documentation tasks (FR-10) — README, Wiki, CHANGELOG
3. Execute with `/z:rush`
4. Post-rush: Verify Wiki pages published, validate_commands passes
