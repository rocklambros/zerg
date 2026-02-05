# Technical Design: core-refactoring

## Metadata
- **Feature**: core-refactoring
- **Status**: DRAFT
- **Created**: 2026-02-05
- **Issues**: #132, #136, #138 (SEQUENCED)
- **Author**: Factory Design Mode

---

## 1. Overview

### 1.1 Summary
Refactor 3 god classes (~4,500 lines) into maintainable modules across 3 sequenced PRs: sync/async dedup (~445 line reduction), god class splitting (3 files → 10+ files, all ≤500 lines), and state decoupling via WorkerRegistry.

### 1.2 Goals
- Eliminate all sync/async duplicate method pairs
- Split launcher.py (2,010L), orchestrator.py (1,344L), worker_protocol.py (1,143L) below 500-line soft cap
- Replace shared `dict[int, WorkerState]` with thread-safe WorkerRegistry
- Maintain 100% behavioral compatibility — all existing tests pass

### 1.3 Non-Goals
- New features or capabilities
- Changing public CLI interface
- Modifying container execution model
- Adding new dependencies

---

## 2. Architecture

### 2.1 High-Level Design

**Before:**
```
┌──────────────┐  ┌──────────────────┐  ┌──────────────────────┐
│ launcher.py  │  │ orchestrator.py  │  │ worker_protocol.py   │
│ 2,010 lines  │  │ 1,344 lines      │  │ 1,143 lines          │
│ 5 classes    │  │ 1 class          │  │ 3 classes             │
│ sync+async   │  │ sync+async       │  │ sync+async            │
└──────────────┘  └──────────────────┘  └──────────────────────┘
```

**After PR 1 (Dedup):**
```
┌──────────────┐  ┌──────────────────┐  ┌──────────────────────┐
│ launcher.py  │  │ orchestrator.py  │  │ worker_protocol.py   │
│ ~1,565 lines │  │ ~1,150 lines     │  │ ~1,100 lines         │
│ async-first  │  │ unified loops    │  │ async-first           │
└──────────────┘  └──────────────────┘  └──────────────────────┘
```

**After PR 2 (Split):**
```
zerg/
├── launcher_types.py         ~80L   # LauncherConfig, SpawnResult, WorkerHandle
├── env_validator.py          ~50L   # validate_env_vars, ALLOWED/DANGEROUS sets
├── launchers/
│   ├── __init__.py           ~40L   # Factory, re-exports
│   ├── base.py               ~250L  # WorkerLauncher ABC + retry logic
│   ├── subprocess_launcher.py ~350L # SubprocessLauncher
│   └── container_launcher.py  ~500L # ContainerLauncher
├── orchestrator.py           ~500L  # Slim coordinator (main loop only)
├── protocol_types.py         ~100L  # ClaudeInvocationResult, WorkerContext, ExitCode mapping
├── protocol_handler.py       ~500L  # Task execution, Claude invocation, verification
└── protocol_state.py         ~450L  # State machine, claiming, checkpointing
```

**After PR 3 (Registry):**
```
zerg/
├── worker_registry.py        ~150L  # WorkerRegistry: thread-safe worker state
└── (5 consumers migrated from raw dict to registry)
```

### 2.2 Component Breakdown

| Component | Responsibility | Target Lines |
|-----------|---------------|-------------|
| `launcher_types.py` | Dataclasses: LauncherConfig, SpawnResult, WorkerHandle, LauncherType enum | ~80 |
| `env_validator.py` | Env var validation, ALLOWED_ENV_VARS, DANGEROUS_ENV_VARS | ~50 |
| `launchers/base.py` | WorkerLauncher ABC, spawn_with_retry, common interface | ~250 |
| `launchers/subprocess_launcher.py` | SubprocessLauncher (async-first) | ~350 |
| `launchers/container_launcher.py` | ContainerLauncher (async-first) | ~500 |
| `launchers/__init__.py` | Factory function, public re-exports | ~40 |
| `orchestrator.py` | Slim coordinator: main loop, init, delegation | ~500 |
| `protocol_types.py` | ClaudeInvocationResult, WorkerContext dataclasses | ~100 |
| `protocol_handler.py` | execute_task, invoke_claude_code, run_verification, commit_task_changes | ~500 |
| `protocol_state.py` | WorkerProtocol: start, claim_next_task, checkpoint, state machine | ~450 |
| `worker_registry.py` | WorkerRegistry: register, get, update_status, all, active, by_level | ~150 |

### 2.3 Data Flow

No change to data flow — this is a structural refactoring. All existing interfaces preserved.

---

## 3. Detailed Design

### 3.1 PR 1: Sync/Async Deduplication

#### Strategy: Hybrid

| Pair | Location | Strategy | Why |
|------|----------|----------|-----|
| `spawn_with_retry` | launcher.py:354-485 | async-first + `asyncio.run()` wrapper | No polling |
| `spawn` (subprocess) | SubprocessLauncher | async-first + wrapper | No polling |
| `spawn` (container) | ContainerLauncher | async-first + wrapper | No polling |
| `_start_container` | launcher.py:1235-1930 | async-first + wrapper | No polling |
| `_main_loop` | orchestrator.py:835-1207 | Callable injection (`sleep_fn`) | Has polling loop, sync fast-path needed |
| `_poll_workers` | orchestrator.py:900-1245 | Callable injection (`sleep_fn`) | Has polling loop + async has fewer features |
| `claim_next_task` | worker_protocol.py:346-457 | async-first + wrapper | No polling overhead issue |
| `wait_for_ready` | worker_protocol.py:304-339 | async-first + wrapper | Simple sleep loop |
| `terminate` / `terminate_async` | ContainerLauncher | async-first + wrapper | No polling |

#### Unified Loop Pattern

```python
# orchestrator.py — unified _main_loop with injectable sleep
async def _main_loop(self, sleep_fn=None):
    """Main orchestration loop.

    Args:
        sleep_fn: Awaitable sleep function. Defaults to asyncio.sleep.
    """
    if sleep_fn is None:
        sleep_fn = asyncio.sleep

    while self._running:
        await self._poll_workers()
        self._check_retry_ready_tasks()
        # ... level completion logic (identical for sync/async)
        await sleep_fn(self._poll_interval)

# Sync entry still uses asyncio.run():
def start_sync(self, ...):
    asyncio.run(self.start_async(...))
```

**Key fix**: Async `_poll_workers` currently lacks escalation check, progress aggregation, and stall detection. Unification brings full feature parity.

#### Async-First Pattern

```python
# launcher base.py
class WorkerLauncher(ABC):
    @abstractmethod
    async def spawn_async(self, worker_id, feature, worktree_path, branch, env=None) -> SpawnResult:
        ...

    def spawn(self, worker_id, feature, worktree_path, branch, env=None) -> SpawnResult:
        """Sync wrapper. Subclasses should NOT override."""
        return asyncio.run(self.spawn_async(worker_id, feature, worktree_path, branch, env))
```

### 3.2 PR 2: God Class Splitting

#### launcher.py Split Plan

**Current structure** (2,010 lines, 5 classes):
- `validate_env_vars()` + constants (lines 1-130) → `env_validator.py`
- `LauncherConfig`, `SpawnResult`, `WorkerHandle`, `LauncherType` (lines 131-250) → `launcher_types.py`
- `WorkerLauncher` ABC (lines 250-490) → `launchers/base.py`
- `SubprocessLauncher` (lines 490-820) → `launchers/subprocess_launcher.py`
- `ContainerLauncher` (lines 820-2010) → `launchers/container_launcher.py`
- Factory `get_plugin_launcher()` → `launchers/__init__.py`

**Import migration**: All 4 importers updated:
- `orchestrator.py` → `from zerg.launchers import ...`
- `worker_manager.py` → `from zerg.launchers import WorkerLauncher`
- `launcher_configurator.py` → `from zerg.launchers import ...`
- `config.py` → `from zerg.launcher_types import LauncherType`

#### orchestrator.py Slimming

**What stays** (~500L): `__init__`, `start_async`, `start_sync`, `_main_loop`, `_poll_workers`, `stop`, `stop_async`, `status`, callbacks, `generate_task_contexts`

**What gets removed** (already delegated thin wrappers, ~200L): 24 one-liner delegations to `_worker_manager`, `_level_coord`, `_retry_manager`, `_state_sync`, `_launcher_config` — call extracted components directly from `_main_loop` and `_poll_workers`.

#### worker_protocol.py Split Plan

**Current structure** (1,143 lines, 3 classes):
- `ClaudeInvocationResult`, `WorkerContext` (lines 46-87) → `protocol_types.py`
- `WorkerProtocol.__init__`, `start()`, `claim_next_task()`, `signal_ready()`, state machine (lines 89-457) → `protocol_state.py`
- `execute_task()`, `invoke_claude_code()`, `_build_task_prompt()`, `run_verification()`, `commit_task_changes()` (lines 459-991) → `protocol_handler.py`
- `report_complete`, `report_failed`, `checkpoint_and_exit`, `get_status`, context tracking (lines 993-1143) → stays in `protocol_state.py`

**Composition pattern**: `protocol_state.py::WorkerProtocol` creates a `ProtocolHandler` internally:

```python
# protocol_state.py
class WorkerProtocol:
    def __init__(self, ...):
        self._handler = ProtocolHandler(state=self.state, git=self.git, ...)

    def start(self):
        while True:
            task = self.claim_next_task()
            if task:
                success = self._handler.execute_task(task)
```

### 3.3 PR 3: WorkerRegistry

```python
# worker_registry.py
import threading
from zerg.types import WorkerState
from zerg.constants import WorkerStatus

class WorkerRegistry:
    """Single source of truth for worker state. Thread-safe."""

    def __init__(self):
        self._workers: dict[int, WorkerState] = {}
        self._lock = threading.RLock()

    def register(self, worker_id: int, handle: WorkerState) -> None:
        with self._lock:
            self._workers[worker_id] = handle

    def unregister(self, worker_id: int) -> WorkerState | None:
        with self._lock:
            return self._workers.pop(worker_id, None)

    def get(self, worker_id: int) -> WorkerState | None:
        with self._lock:
            return self._workers.get(worker_id)

    def update_status(self, worker_id: int, status: WorkerStatus) -> None:
        with self._lock:
            if worker_id in self._workers:
                self._workers[worker_id].status = status

    def all(self) -> list[WorkerState]:
        with self._lock:
            return list(self._workers.values())

    def active(self) -> list[WorkerState]:
        with self._lock:
            return [w for w in self._workers.values()
                    if w.status not in (WorkerStatus.STOPPED, WorkerStatus.CRASHED)]

    def by_level(self, level: int) -> list[WorkerState]:
        """Not tracked yet — reserved for future use."""
        return self.all()

    def keys(self) -> list[int]:
        with self._lock:
            return list(self._workers.keys())

    def items(self) -> list[tuple[int, WorkerState]]:
        with self._lock:
            return list(self._workers.items())

    def __len__(self) -> int:
        with self._lock:
            return len(self._workers)

    def __contains__(self, worker_id: int) -> bool:
        with self._lock:
            return worker_id in self._workers
```

**Migration**: Replace `workers: dict[int, WorkerState]` parameter in all 5 consumers:

| Component | Constructor Change | Internal Changes |
|-----------|-------------------|-----------------|
| `Orchestrator.__init__` | `self._workers = WorkerRegistry()` | All `self._workers[x]` → `self._registry.get(x)` etc. |
| `WorkerManager.__init__` | `registry: WorkerRegistry` param | `self._workers[x] = y` → `self._registry.register(x, y)` |
| `LevelCoordinator.__init__` | `registry: WorkerRegistry` param | `self._workers.items()` → `self._registry.items()` |
| `LauncherConfigurator._check_container_health` | `registry: WorkerRegistry` param | Same pattern |
| Orchestrator `_poll_workers` | Direct access | `for wid, w in self._registry.items()` |

---

## 4. Key Decisions

### Decision: Async-First vs Sync-First for Dedup

**Context**: 6 duplicate pairs need unification.

**Options**:
1. Sync-first, async wraps sync: Simple but blocks event loop
2. Async-first, sync wraps async via `asyncio.run()`: Clean but slight overhead on sync path
3. Callable injection for all: Uniform but overengineered for non-loop methods

**Decision**: Hybrid — async-first for non-loop methods, callable injection for `_main_loop` / `_poll_workers`.

**Rationale**: `asyncio.run()` overhead is negligible for spawn/terminate (already I/O bound). But polling loops run every 15 seconds — callable injection avoids `asyncio.run()` per-tick.

### Decision: Flat Modules vs Subpackage for Protocol Split

**Context**: worker_protocol.py → 3 files.

**Options**:
1. Subpackage `protocol/`: Consistent with launcher split
2. Flat modules with `protocol_` prefix: Matches project style

**Decision**: Flat modules (`protocol_types.py`, `protocol_handler.py`, `protocol_state.py`).

**Rationale**: Requirements specify flat modules. Project has no existing protocol subpackage convention.

### Decision: Clean Break vs Re-export for Import Migration

**Context**: Moving classes between files breaks existing imports.

**Decision**: Clean break — update all imports in-PR, no re-exports.

**Rationale**: Re-exports add tech debt. With `python -m zerg.validate_commands` in CI, broken imports are caught immediately.

---

## 5. Implementation Plan

### 5.1 Phase Summary

| Phase | PR | Tasks | Parallel | Est. Time |
|-------|-----|-------|----------|-----------|
| 1: Dedup Foundation | PR1 | 3 | Yes | 15 min |
| 2: Dedup Core | PR1 | 4 | Yes | 30 min |
| 3: Dedup Integration | PR1 | 2 | Yes | 20 min |
| 4: Dedup Tests | PR1 | 1 | No | 25 min |
| 5: Split Foundation | PR2 | 4 | Yes | 15 min |
| 6: Split Core | PR2 | 4 | Yes | 30 min |
| 7: Split Integration | PR2 | 2 | Yes | 20 min |
| 8: Split Tests | PR2 | 1 | No | 25 min |
| 9: Registry Foundation | PR3 | 1 | No | 15 min |
| 10: Registry Migration | PR3 | 3 | Yes | 25 min |
| 11: Registry Tests | PR3 | 1 | No | 20 min |
| **Totals** | | **26** | | **~240 min** |

### 5.2 File Ownership

| File | Task ID | Operation | PR |
|------|---------|-----------|-----|
| `zerg/launcher.py` | TASK-001 | modify (dedup spawn_with_retry) | PR1 |
| `zerg/launcher.py` | TASK-002 | modify (dedup _start_container) | PR1 |
| `zerg/launcher.py` | TASK-003 | modify (dedup terminate) | PR1 |
| `zerg/orchestrator.py` | TASK-004 | modify (unify _main_loop) | PR1 |
| `zerg/orchestrator.py` | TASK-005 | modify (unify _poll_workers) | PR1 |
| `zerg/worker_protocol.py` | TASK-006 | modify (dedup claim/wait) | PR1 |
| `zerg/level_coordinator.py` | TASK-007 | modify (dedup claim_next_task) | PR1 |
| `tests/unit/test_dedup_unified.py` | TASK-008 | create | PR1 |
| `tests/integration/test_dedup_behavioral.py` | TASK-009 | create | PR1 |
| `zerg/launcher_types.py` | TASK-010 | create | PR2 |
| `zerg/env_validator.py` | TASK-011 | create | PR2 |
| `zerg/launchers/__init__.py` | TASK-012 | create | PR2 |
| `zerg/launchers/base.py` | TASK-013 | create | PR2 |
| `zerg/launchers/subprocess_launcher.py` | TASK-014 | create | PR2 |
| `zerg/launchers/container_launcher.py` | TASK-015 | create | PR2 |
| `zerg/launcher.py` | TASK-016 | delete (replaced) | PR2 |
| `zerg/protocol_types.py` | TASK-017 | create | PR2 |
| `zerg/protocol_handler.py` | TASK-018 | create | PR2 |
| `zerg/protocol_state.py` | TASK-019 | create | PR2 |
| `zerg/worker_protocol.py` | TASK-020 | delete (replaced) | PR2 |
| `zerg/orchestrator.py` | TASK-021 | modify (slim thin wrappers) | PR2 |
| `zerg/*` (imports) | TASK-022 | modify (all import paths) | PR2 |
| `tests/**` (imports) | TASK-023 | modify (test import paths) | PR2 |
| `zerg/worker_registry.py` | TASK-024 | create | PR3 |
| `zerg/orchestrator.py` | TASK-025 | modify (use registry) | PR3 |
| `zerg/worker_manager.py` | TASK-026 | modify (use registry) | PR3 |
| `zerg/level_coordinator.py` | TASK-027 | modify (use registry) | PR3 |
| `zerg/launcher_configurator.py` | TASK-028 | modify (use registry) | PR3 |
| `tests/unit/test_worker_registry.py` | TASK-029 | create | PR3 |
| `tests/integration/test_registry_wiring.py` | TASK-030 | create | PR3 |

### 5.3 Dependency Graph

```
PR1 — Sync/Async Dedup:
  Level 1 (Foundation):
    TASK-001: Dedup spawn_with_retry in launcher.py
    TASK-002: Dedup _start_container in launcher.py
    TASK-003: Dedup terminate in launcher.py
  Level 2 (Core):
    TASK-004: Unify _main_loop in orchestrator.py     [depends: none - separate file]
    TASK-005: Unify _poll_workers in orchestrator.py   [depends: TASK-004]
    TASK-006: Dedup claim/wait in worker_protocol.py   [depends: none]
    TASK-007: Dedup claim_next_task in level_coordinator.py [depends: none]
  Level 3 (Integration):
    TASK-008: Unit tests for dedup                     [depends: TASK-001..007]
    TASK-009: Integration test for behavioral equiv    [depends: TASK-008]

PR2 — God Class Split:
  Level 4 (Foundation):
    TASK-010: Create launcher_types.py                 [depends: TASK-009]
    TASK-011: Create env_validator.py                  [depends: TASK-009]
    TASK-017: Create protocol_types.py                 [depends: TASK-009]
  Level 5 (Core):
    TASK-012: Create launchers/__init__.py             [depends: TASK-010]
    TASK-013: Create launchers/base.py                 [depends: TASK-010]
    TASK-014: Create launchers/subprocess_launcher.py  [depends: TASK-013]
    TASK-015: Create launchers/container_launcher.py   [depends: TASK-013]
    TASK-018: Create protocol_handler.py               [depends: TASK-017]
    TASK-019: Create protocol_state.py                 [depends: TASK-017, TASK-018]
  Level 6 (Integration):
    TASK-016: Delete old launcher.py + update __init__  [depends: TASK-012..015]
    TASK-020: Delete old worker_protocol.py             [depends: TASK-018, TASK-019]
    TASK-021: Slim orchestrator.py                      [depends: TASK-016]
    TASK-022: Update all source imports                  [depends: TASK-016, TASK-020]
  Level 7 (Verification):
    TASK-023: Update all test imports + run full suite   [depends: TASK-022]

PR3 — WorkerRegistry:
  Level 8 (Foundation):
    TASK-024: Create worker_registry.py                  [depends: TASK-023]
  Level 9 (Migration):
    TASK-025: Migrate orchestrator.py to registry        [depends: TASK-024]
    TASK-026: Migrate worker_manager.py to registry      [depends: TASK-024]
    TASK-027: Migrate level_coordinator.py to registry   [depends: TASK-024]
    TASK-028: Migrate launcher_configurator.py           [depends: TASK-024]
  Level 10 (Tests):
    TASK-029: Unit tests for WorkerRegistry              [depends: TASK-024]
    TASK-030: Integration tests for registry wiring      [depends: TASK-025..028]
```

---

## 6. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Import breakage after split | Medium | High | `python -m zerg.validate_commands` after every task |
| Async behavior change | Low | High | Integration tests verify behavioral equivalence |
| Thread safety gap in registry | Low | Medium | RLock on all operations; existing code is single-threaded |
| CI test timeout from import churn | Low | Low | Keep test changes in dedicated task |
| Merge conflicts between PRs | N/A | N/A | Sequential PRs — each builds on merged predecessor |

---

## 7. Testing Strategy

### 7.1 Unit Tests
- PR1: New `test_dedup_unified.py` verifying sync wrappers produce same results as async
- PR2: Existing launcher/protocol tests updated for new import paths
- PR3: New `test_worker_registry.py` testing all registry methods, thread safety

### 7.2 Integration Tests
- PR1: `test_dedup_behavioral.py` — end-to-end flow still works with unified methods
- PR2: Full `python -m zerg.validate_commands` + existing integration suite
- PR3: `test_registry_wiring.py` — all 5 consumers interact correctly via registry

### 7.3 Verification Commands
All tasks use: `python -m pytest tests/ -x -q --timeout=60 && python -m zerg.validate_commands && ruff check zerg/`

---

## 8. Parallel Execution Notes

### 8.1 Safe Parallelization
- PR1 Level 1: 3 tasks (launcher dedup) can run in parallel — different methods
- PR1 Level 2: 4 tasks — TASK-004/005 sequential (same file), 006/007 parallel
- PR2 Level 4: 3 tasks (new files) fully parallel
- PR2 Level 5: 6 tasks — launcher tasks sequential on base.py, protocol tasks parallel
- PR3 Level 9: 4 migration tasks fully parallel (different files)

### 8.2 Recommended Workers
- Minimum: 1 worker (sequential)
- Optimal: 4 workers (widest parallel level)
- Maximum: 6 workers (diminishing returns beyond)

### 8.3 Estimated Duration
- Single worker: ~240 minutes
- With 4 workers: ~120 minutes
- Speedup: ~2x

---

## 9. Consumer Matrix

| Task | Creates | Consumed By | Integration Test |
|------|---------|-------------|-----------------|
| TASK-010 | `launcher_types.py` | TASK-012, TASK-013 | `tests/integration/test_launcher_integration.py` |
| TASK-011 | `env_validator.py` | TASK-013, TASK-015 | `tests/integration/test_launcher_integration.py` |
| TASK-012 | `launchers/__init__.py` | TASK-016, TASK-022 | `tests/integration/test_launcher_integration.py` |
| TASK-013 | `launchers/base.py` | TASK-014, TASK-015 | `tests/integration/test_launcher_integration.py` |
| TASK-014 | `launchers/subprocess_launcher.py` | TASK-012 (re-export) | `tests/integration/test_launcher_integration.py` |
| TASK-015 | `launchers/container_launcher.py` | TASK-012 (re-export) | `tests/integration/test_container_launcher.py` |
| TASK-017 | `protocol_types.py` | TASK-018, TASK-019 | `tests/integration/test_worker_protocol_extended.py` |
| TASK-018 | `protocol_handler.py` | TASK-019 | `tests/integration/test_worker_protocol_extended.py` |
| TASK-019 | `protocol_state.py` | `worker_main.py` (leaf) | `tests/integration/test_worker_protocol_extended.py` |
| TASK-024 | `worker_registry.py` | TASK-025, TASK-026, TASK-027, TASK-028 | `tests/integration/test_registry_wiring.py` |

---

## 10. Approval

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Architecture | | | PENDING |
| Engineering | | | PENDING |
