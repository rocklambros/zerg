# Technical Design: Orchestrator Coordination Fix

## Metadata
- **Feature**: orchestrator-coordination-fix
- **Status**: APPROVED
- **Created**: 2026-02-04
- **GitHub Issues**: Related to #65, #119 (bite-sized-planning rush failures)

---

## 1. Overview

### 1.1 Summary

Fix 6 critical bugs in ZERG orchestrator that cause merge conflicts, level violations, and redundant gate runs. The core fix is simple: defer all merges to ship time instead of merging after each level.

### 1.2 Goals

- Main branch untouched during rush execution
- Strict level enforcement at task claim time
- Strict dependency enforcement at runtime
- Quality gates run exactly once (at ship)
- Live status streaming for user visibility

### 1.3 Non-Goals

- Changing ship command's PR creation logic
- Adding new merge strategies
- Modifying worker spawn behavior

---

## 2. Architecture

### 2.1 Current Flow (Broken)

```
Level 1 complete → merge_level() → full_merge_flow(target="main") → MAIN MODIFIED
Level 2 complete → merge_level() → full_merge_flow(target="main") → MAIN MODIFIED (again)
...
```

### 2.2 Fixed Flow

```
Level 1 complete → set_level_status("complete") → advance to Level 2 → NO MERGE
Level 2 complete → set_level_status("complete") → advance to Level 3 → NO MERGE
...
All levels complete → Rush DONE (main untouched)

/z:git --action ship:
  → Create staging from main
  → Merge all worker branches to staging
  → Run quality gates ONCE
  → Merge staging to main / Create PR
  → Cleanup
```

### 2.3 Component Changes

| Component | Current | After Fix |
|-----------|---------|-----------|
| `level_coordinator.py` | Calls `merge_level()` on level complete | Skips merge if `defer_merge_to_ship=True` |
| `state.py:claim_task()` | Only checks status + worker | Also checks level + dependencies |
| `merge.py:full_merge_flow()` | Always runs gates | Skips gates if `skip_gates_until_ship=True` |
| `git_cmd.py:action_ship()` | Uses `gh pr merge` directly | Uses `MergeCoordinator` with gates |
| `merge.py:finalize()` | Checkouts target branch | Uses detached HEAD |

---

## 3. Detailed Design

### 3.1 Config Changes

```python
# zerg/config.py

class RushConfig(BaseModel):
    # Existing fields...

    # NEW: Coordination fixes
    defer_merge_to_ship: bool = Field(
        default=True,
        description="Defer all merges to /z:git --action ship"
    )
    gates_at_ship_only: bool = Field(
        default=True,
        description="Run quality gates only at ship time, not per level"
    )
```

### 3.2 DependencyChecker Helper

```python
# zerg/dependency_checker.py

class DependencyChecker:
    def __init__(self, state: StateManager, parser: TaskParser):
        self._state = state
        self._parser = parser

    def are_dependencies_complete(self, task_id: str) -> bool:
        """Check if all dependencies of task_id are COMPLETE."""
        task = self._parser.get_task(task_id)
        if not task:
            return False

        for dep_id in task.get("dependencies", []):
            dep_status = self._state.get_task_status(dep_id)
            if dep_status != TaskStatus.COMPLETE.value:
                return False

        return True

    def get_incomplete_dependencies(self, task_id: str) -> list[str]:
        """Return list of dependency IDs that are not COMPLETE."""
        task = self._parser.get_task(task_id)
        if not task:
            return []

        incomplete = []
        for dep_id in task.get("dependencies", []):
            dep_status = self._state.get_task_status(dep_id)
            if dep_status != TaskStatus.COMPLETE.value:
                incomplete.append(dep_id)

        return incomplete
```

### 3.3 EventEmitter for Live Streaming

```python
# zerg/event_emitter.py

class EventEmitter:
    def __init__(self, feature: str, state_dir: Path):
        self._event_file = state_dir / f"{feature}-events.jsonl"

    def emit(self, event_type: str, data: dict | None = None) -> None:
        """Append event to JSONL file."""
        entry = {
            "ts": datetime.now().isoformat(),
            "event": event_type,
            "data": data or {}
        }
        with open(self._event_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def subscribe(self, callback: Callable[[dict], None]) -> None:
        """Tail event file and call callback for new events."""
        # Implementation: use watchdog or simple polling
```

### 3.4 Modified claim_task()

```python
# zerg/state.py

def claim_task(
    self,
    task_id: str,
    worker_id: int,
    current_level: int | None = None,
    dependency_checker: DependencyChecker | None = None
) -> bool:
    """Attempt to claim a task for a worker."""
    with self._atomic_update():
        task_state = self._state.get("tasks", {}).get(task_id, {})

        # NEW: Level enforcement
        if current_level is not None:
            task_level = task_state.get("level", 1)
            if task_level != current_level:
                logger.warning(f"Task {task_id} (L{task_level}) blocked - current level is {current_level}")
                return False

        # NEW: Dependency enforcement
        if dependency_checker is not None:
            if not dependency_checker.are_dependencies_complete(task_id):
                incomplete = dependency_checker.get_incomplete_dependencies(task_id)
                logger.warning(f"Task {task_id} blocked by incomplete deps: {incomplete}")
                return False

        # Existing checks...
        current_status = task_state.get("status", TaskStatus.PENDING.value)
        if current_status not in (TaskStatus.TODO.value, TaskStatus.PENDING.value):
            return False

        existing_worker = task_state.get("worker_id")
        if existing_worker is not None and existing_worker != worker_id:
            return False

        # Claim it
        self.set_task_status(task_id, TaskStatus.CLAIMED, worker_id=worker_id)
        self.record_task_claimed(task_id, worker_id)
        return True
```

### 3.5 Modified handle_level_complete()

```python
# zerg/level_coordinator.py

def handle_level_complete(self, level: int) -> bool:
    """Handle level completion."""
    # Check config
    if self.config.rush.defer_merge_to_ship:
        # NEW: No merge during rush
        logger.info(f"Level {level} complete. Merge deferred to ship.")
        self.state.set_level_status(level, "complete")
        self._emit_event("level_complete", {"level": level, "merge": "deferred"})
        return True

    # Legacy behavior: merge to main
    # ... existing merge code ...
```

### 3.6 Modified finalize()

```python
# zerg/merge.py

def finalize(self, staging_branch: str, target_branch: str) -> str:
    """Finalize merge to target branch."""
    # NEW: Use detached HEAD to avoid worktree lock
    current = self.git.current_branch()
    if current == staging_branch or current == target_branch:
        self.git.run(["checkout", "--detach"])

    # Checkout target and merge
    self.git.checkout(target_branch)
    commit = self.git.merge(staging_branch, message=f"ZERG: Complete level merge from {staging_branch}")

    # Cleanup
    self.git.delete_branch(staging_branch, force=True)

    return commit
```

---

## 4. Key Decisions

### 4.1 Decision: Config Flags for Backward Compatibility

**Context**: Need to avoid breaking existing workflows.

**Options**:
1. Hard-code new behavior (breaking change)
2. Config flags with new behavior as default
3. Config flags with old behavior as default

**Decision**: Option 2 - Config flags, new behavior default.

**Rationale**: Fixes bugs by default, but users can opt-out if needed.

### 4.2 Decision: Detached HEAD for finalize()

**Context**: Worktree lock errors when staging branch is checked out.

**Options**:
1. Dedicated merge worktree
2. Detached HEAD checkout
3. Force delete with `--force`

**Decision**: Option 2 - Detached HEAD.

**Rationale**: Simpler than worktree management, safer than force delete.

---

## 5. Implementation Plan

### 5.1 Task Summary

| Level | Tasks | Parallel | Est. Time |
|-------|-------|----------|-----------|
| Foundation (L1) | 3 | Yes | 30m |
| Core (L2) | 4 | Partial | 25m |
| Integration (L3) | 5 | Yes | 35m |
| Testing (L4) | 4 | Yes | 35m |
| Quality (L5) | 1 | No | 20m |

**Total**: 17 tasks, ~145m sequential, ~50m with 3 workers

### 5.2 File Ownership

| File | Task(s) |
|------|---------|
| `zerg/config.py` | OCF-L1-001 |
| `zerg/dependency_checker.py` | OCF-L1-002 |
| `zerg/event_emitter.py` | OCF-L1-003 |
| `zerg/state.py` | OCF-L2-001, OCF-L2-002 |
| `zerg/level_coordinator.py` | OCF-L2-003 |
| `zerg/merge.py` | OCF-L2-004, OCF-L3-002 |
| `zerg/commands/git_cmd.py` | OCF-L3-001 |
| `zerg/orchestrator.py` | OCF-L3-003 |
| `zerg/commands/status.py` | OCF-L3-004 |
| `zerg/worker_manager.py` | OCF-L3-005 |

---

## 6. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Breaking existing workflows | Low | High | Config flags with opt-out |
| Gate failures at ship time | Medium | Medium | Clear error messages, manual fix path |
| Event file growth | Low | Low | Cleanup at rush end |

---

## 7. Testing Strategy

### 7.1 Unit Tests

- `test_dependency_checker.py`: All dependency scenarios
- `test_event_emitter.py`: emit, subscribe, cleanup
- `test_claim_task_enforcement.py`: Level + dependency validation

### 7.2 Integration Tests

- `test_deferred_merge.py`: Main untouched during rush
- `test_claim_enforcement.py`: End-to-end level/dep enforcement

---

## 8. Parallel Execution Notes

### 8.1 Recommended Workers

- Minimum: 2 workers
- Optimal: 3 workers
- Maximum: 4 workers

### 8.2 Estimated Duration

- Single worker: ~145m
- With 3 workers: ~50m
- Speedup: ~3x

---

## 9. Approval

| Role | Status |
|------|--------|
| Architecture | APPROVED |
| Engineering | APPROVED |
