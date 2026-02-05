# Requirements: core-refactoring

**Status: APPROVED**
**Created**: 2026-02-05
**Issues**: #132, #136, #138 (SEQUENCED)
**Scope**: Refactor 3 god classes (~4,500 lines) into maintainable modules

---

## Executive Summary

Refactor `launcher.py` (2,010 lines), `orchestrator.py` (1,344 lines), and `worker_protocol.py` (1,143 lines) to eliminate sync/async duplication, split god classes, and decouple shared mutable state. Delivered as 3 sequenced PRs.

---

## Sequence

| Order | Issue | Title | Priority |
|-------|-------|-------|----------|
| 1 | #136 | Sync/async deduplication | MEDIUM |
| 2 | #132 | God class splitting | HIGH |
| 3 | #138 | State decoupling via WorkerRegistry | MEDIUM |

**Rationale**: Dedup first reduces code volume by ~445 lines, making splits cleaner. State decoupling is easiest after classes are properly sized.

---

## PR 1: Sync/Async Deduplication (#136)

### Strategy: Hybrid

- **Most methods**: Async-first implementation, sync wrappers via `asyncio.run()`
- **Poll/heartbeat loops**: Shared logic extraction with `sleep_fn` callable injection (sync fast-path required)

### Targets (6 duplication pairs, ~445 lines)

| Component | Sync | Async | Strategy |
|-----------|------|-------|----------|
| `spawn_with_retry` | launcher.py:354-420 | launcher.py:422-485 | async-first + wrapper |
| `spawn` (subprocess) | SubprocessLauncher | SubprocessLauncher | async-first + wrapper |
| `spawn` (container) | ContainerLauncher | ContainerLauncher | async-first + wrapper |
| `_start_container` | launcher.py:1235-1357 | launcher.py:1833-1930 | async-first + wrapper |
| `_main_loop` | orchestrator.py | orchestrator.py | callable injection (has polling) |
| `_poll_workers` | orchestrator.py | orchestrator.py | callable injection (has polling) |
| `claim_next_task` | level_coordinator.py | level_coordinator.py | async-first + wrapper |

### Acceptance Criteria

- [ ] No duplicate sync/async method pairs remain
- [ ] Single source of truth for retry logic
- [ ] Single source of truth for Docker command building
- [ ] Poll/heartbeat loops have zero `asyncio.run()` overhead in sync mode
- [ ] All existing tests pass
- [ ] No new dependencies added

---

## PR 2: God Class Splitting (#132)

### Strategy: Split into subpackages and flat modules

#### launcher.py (2,010 lines) → launchers/ subpackage

```
zerg/
├── launcher_types.py          # LauncherConfig, SpawnResult, WorkerHandle dataclasses
├── env_validator.py           # Environment variable validation logic
└── launchers/
    ├── __init__.py            # Factory function, public re-exports
    ├── base.py                # WorkerLauncher ABC + retry logic
    ├── subprocess_launcher.py # SubprocessLauncher
    └── container_launcher.py  # ContainerLauncher
```

#### orchestrator.py (1,344 lines) → slimmed orchestrator + extracted components

- Extract `_create_launcher` → `launcher_configurator.py` (already exists, verify coverage)
- Slim `__init__` using Builder pattern
- Remove thin wrappers (lines 297-526) — call extracted components directly
- **Target**: orchestrator.py ≤ 500 lines (coordination logic only)

#### worker_protocol.py (1,143 lines) → flat modules

```
zerg/
├── protocol_types.py     # Message types, enums, dataclasses
├── protocol_handler.py   # Protocol parsing, message routing
└── protocol_state.py     # State machine, transitions
```

### Compatibility

- **Clean break**: No re-exports from old import paths
- Update all imports project-wide in the same PR
- Update `__init__.py` exports

### File Size Target

- **Soft cap**: 500 lines
- **Hard cap**: 600 lines (only if natural class boundary requires it)

### Acceptance Criteria

- [ ] No file exceeds 600 lines (target 500)
- [ ] Each class has single responsibility
- [ ] All imports updated — no broken references
- [ ] Unit tests can mock individual components
- [ ] `python -m zerg.validate_commands` passes

---

## PR 3: State Decoupling via WorkerRegistry (#138)

### Strategy: WorkerRegistry abstraction

```python
class WorkerRegistry:
    """Single source of truth for worker state."""

    def __init__(self):
        self._workers: dict[int, WorkerHandle] = {}
        self._lock = threading.RLock()

    def register(self, worker_id: int, handle: WorkerHandle) -> None: ...
    def get(self, worker_id: int) -> WorkerHandle | None: ...
    def update_status(self, worker_id: int, status: WorkerStatus) -> None: ...
    def all(self) -> list[WorkerHandle]: ...
    def active(self) -> list[WorkerHandle]: ...
    def by_level(self, level: int) -> list[WorkerHandle]: ...
```

### Migration Scope: All shared-dict consumers

| Component | Current | After |
|-----------|---------|-------|
| `orchestrator.py` | `self._workers` dict | `self._registry: WorkerRegistry` |
| `worker_manager.py` | `workers=self._workers` | `registry=self._registry` |
| `level_coordinator.py` | `workers=self._workers` | `registry=self._registry` |
| `state_sync_service.py` | `workers=self._workers` | `registry=self._registry` |
| `task_retry_manager.py` | `workers=self._workers` | `registry=self._registry` |

### New File

- `zerg/worker_registry.py` — WorkerRegistry class (~100-150 lines)

### Acceptance Criteria

- [ ] Worker state owned by single component (WorkerRegistry)
- [ ] All 5 consumers migrated from raw dict to registry
- [ ] Clear mutation paths with thread-safe access (RLock)
- [ ] Components testable with mock registry
- [ ] No direct `self._workers` dict access outside WorkerRegistry

---

## Cross-Cutting Requirements

### Testing

- Each PR includes updated/new unit tests for refactored modules
- Integration tests verify end-to-end worker lifecycle still works
- No test may be skipped or deleted to pass CI

### Quality Gates

- `python -m zerg.validate_commands` must pass (drift detection)
- `ruff check` / `ruff format` pass
- Type checking passes (if configured)
- All existing CI checks green

### Risk Mitigations

- Each PR is independently mergeable and testable
- PR 2 (splits) builds on PR 1 (dedup) — must not start until PR 1 is merged
- PR 3 (registry) builds on PR 2 (splits) — must not start until PR 2 is merged
- Feature branch per PR: `refactor/sync-async-dedup`, `refactor/god-class-split`, `refactor/worker-registry`

---

## Open Questions

None — all resolved during Socratic discovery.

---

## Decision Log

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Sequence | #136 → #132 → #138 | Dedup reduces volume before splits |
| Async pattern | Hybrid (async-first + callable injection for polling) | Sync fast-path needed for poll/heartbeat |
| Protocol structure | Flat modules (not subpackage) | Matches project style |
| File size limit | 500 soft / 600 hard | Allows natural class boundaries |
| PR strategy | 1 PR per issue (3 total) | Atomic logical changes |
| Registry scope | All 5 shared-dict consumers | Full decoupling |
| Backward compat | Clean break, no re-exports | Simpler codebase |
| DI approach | Simple WorkerRegistry | No new dependencies |
