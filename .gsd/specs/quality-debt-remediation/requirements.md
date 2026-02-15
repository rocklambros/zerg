# Requirements: quality-debt-remediation

**Status: DRAFT**
**Created**: 2026-02-06
**Feature**: Quality Debt Remediation (Issues #134, #137, #139, #140, #143, #145, #146)

## Problem Statement

Codebase audit of 7 open GitHub issues reveals **none have been fully resolved**. Current state:

| Issue | Title | Filed | Current | Delta |
|-------|-------|-------|---------|-------|
| #134 | Multiple rglob scans | P1 | 28 rglob calls across 18 production files; multi-pass still in 5+ modules | ~0% fixed |
| #137 | Bare except Exception | P2 | **192 handlers** (was 62) — 59 HIGH (silent), 122 MEDIUM (log+swallow), 11 LOW | **Worse** |
| #139 | dict[str, Any] overuse | P2 | **319 occurrences** (was 318); 12 TypedDicts exist but top offenders unchanged | ~0% fixed |
| #140 | CLI/business layer mixing | P2 | dryrun.py: 671 lines, 11 render methods; status.py: 1315 lines; no rendering/ pkg | ~0% fixed |
| #143 | StateManager SRP | P2 | 1009 lines, 41 public methods, 11 responsibilities, 30 importers | ~0% fixed |
| #145 | orjson adoption | P3 | 0 orjson refs; 50 files use `import json`; 95 json.loads/dumps calls | 0% fixed |
| #146 | type: ignore cleanup | P3 | 13 instances (unchanged); 11/13 lack justification; pyproject missing `warn_unused_ignores` | ~0% fixed |

### Critical Finding
`zerg/commands/analyze.py:284` — security checker returns **PASS on exception**. If the scanner crashes, the system reports no security issues. This is a fail-open security bug.

## Phased Approach

8 phases, ordered by priority and dependency. Each phase is a separate PR.

---

## Phase 1: Critical Security & Exception Hygiene (P0)

**PR scope**: Fix the fail-open security bug + triage the 59 highest-risk bare-except handlers.

### 1A: Fix analyze.py fail-open (CRITICAL)

`zerg/commands/analyze.py:282-285` — both `CommandValidationError` and bare `Exception` handlers return `passed=True`. On exception, security analysis should **fail closed** (report error, not PASS).

**Fix**: Return `passed=False` with an error issue on exception. On `CommandValidationError` (tool not installed), return a skip/warning result, not a pass.

**Files**: `zerg/commands/analyze.py`
**Verification**: `pytest tests/ -k "analyze" --timeout=30`

### 1B: Fix 59 HIGH-severity silent exception handlers

These catch `Exception` with **no logging and no re-raise** — bugs are invisible.

**Strategy**: For each handler, apply one of:
1. **Add logging** — `logger.exception("context", exc_info=True)` (most cases)
2. **Narrow the type** — replace `Exception` with specific type (e.g., `FileNotFoundError`, `json.JSONDecodeError`)
3. **Re-raise after logging** — where the caller should know about the failure

**Priority files** (most handlers):
- `zerg/commands/cleanup.py` — 7 handlers
- `zerg/commands/analyze.py` — 5 handlers
- `zerg/orchestrator.py` — 4 handlers
- `zerg/token_counter.py` — 3 handlers
- `zerg/git/bisect_engine.py` — 3 handlers

**Files**: ~30 files (see full list in issue #137 audit)
**Verification**: `grep -c "except Exception" zerg/ -r` count should drop by ~59; `ruff check zerg/ --select BLE001` should report 0

### 1C: Enable ruff BLE001 lint rule

Add `BLE001` (bare-except) to ruff select in `pyproject.toml` to prevent new bare-except additions.

**Files**: `pyproject.toml`
**Verification**: `ruff check zerg/ --select BLE001`

**Acceptance Criteria (Phase 1)**:
- [ ] analyze.py security check fails closed on exception
- [ ] 59 HIGH silent handlers fixed (logged or narrowed)
- [ ] BLE001 ruff rule enabled, CI passes
- [ ] All existing tests pass

---

## Phase 2: rglob Single-Pass Optimization (P1)

**PR scope**: Apply single-pass `rglob('*')` pattern to remaining multi-traversal modules.

### 2A: Core rglob offenders

Modules doing **multiple rglob calls** that should use single-pass:

| Module | Current Pattern | Fix |
|--------|----------------|-----|
| `performance/stack_detector.py` | 3 rglobs: `*.yaml`, `*.yml`, `*` | Merge yaml/yml into single `*` traversal already at line 72 |
| `performance/adapters/hadolint_adapter.py` | 2 rglobs: `*.Dockerfile`, `Dockerfile.*` | Single `rglob('*')` + filter |
| `performance/adapters/dive_adapter.py` | 2 rglobs: `*.Dockerfile`, `Dockerfile.*` | Single `rglob('*')` + filter |
| `commands/analyze.py` | 3 rglobs: `*.py` (L559), `*.py` (L624), ext loop (L855) | Consolidate to single pass per invocation |
| `repo_map.py` | 2 rglobs: per-ext loop (L433) + `*` (L501) | Merge into single traversal |

### 2B: Extract shared utility

Create `zerg/fs_utils.py` with a `collect_files(root, extensions)` helper:
```python
def collect_files(root: Path, extensions: set[str], exclude_dirs: set[str] = ...) -> dict[str, list[Path]]:
    """Single rglob('*') traversal, returns files grouped by extension."""
```

Adopt in all modules above.

**Files**: New `zerg/fs_utils.py`, 5 modified modules
**Verification**: `python -c "from zerg.fs_utils import collect_files"` + existing tests pass + `grep -c "rglob(" zerg/ -r --include="*.py"` count drops significantly

**Acceptance Criteria (Phase 2)**:
- [ ] `fs_utils.py` utility created with single-pass traversal
- [ ] 5 multi-traversal modules converted
- [ ] Total rglob count in production code reduced from 28 to <15
- [ ] All existing tests pass

---

## Phase 3: StateManager Decomposition (P2)

**PR scope**: Split 1009-line StateManager monolith into `zerg/state/` package.

### 3A: Create zerg/state/ package

Extract 11 responsibility groups into focused modules:

```
zerg/state/
├── __init__.py          # Re-exports StateManager facade
├── manager.py           # StateManager facade (thin orchestrator, <100 lines)
├── persistence.py       # PersistenceLayer: load/save/backup/lock (7 methods)
├── task_repo.py         # TaskStateRepo: get/set/claim/release task state (7 methods)
├── retry_repo.py        # RetryRepo: retry counts, schedules, cooldowns (6 methods)
├── worker_repo.py       # WorkerStateRepo: worker registration, health (6 methods)
├── level_repo.py        # LevelStateRepo: level progression + merge status (6 methods)
├── execution.py         # ExecutionLog + control state: events, pause, errors (6 methods)
├── metrics_store.py     # MetricsStore: timing, counts (2 methods)
└── renderer.py          # StateRenderer: STATE.md generation (1 method)
```

### 3B: StateManager becomes facade

```python
class StateManager:
    """Thin facade delegating to specialized repositories."""
    def __init__(self, feature: str, state_dir: Path):
        self._persistence = PersistenceLayer(feature, state_dir)
        self._tasks = TaskStateRepo(self._persistence)
        self._workers = WorkerStateRepo(self._persistence)
        # ... etc

    # Delegate methods (backward compatible)
    def get_task_status(self, task_id): return self._tasks.get_status(task_id)
```

### 3C: Update 15 production importers

Update all `from zerg.state import StateManager` to use the new package. The facade ensures backward compatibility — no API changes needed.

### 3D: Update 15 test files

Ensure all state tests pass against the new package structure.

**Files**: New `zerg/state/` package (9 files), delete `zerg/state.py`, update 30 importers
**Verification**: `pytest tests/unit/test_state*.py tests/integration/test_state*.py --timeout=60`

**Acceptance Criteria (Phase 3)**:
- [ ] `zerg/state/` package with 9 focused modules
- [ ] No module > 200 lines
- [ ] No class > 10 public methods
- [ ] StateManager facade backward-compatible
- [ ] All 30 importers updated
- [ ] All state-related tests pass

---

## Phase 4: TypedDict Introduction (P2)

**PR scope**: Define TypedDicts for top offenders, reduce dict[str, Any] by 50%+.

### 4A: Define core TypedDicts in zerg/types.py

`zerg/types.py` already has 12 TypedDicts. Add missing ones for the top offenders:

| TypedDict | Replaces | Used In |
|-----------|----------|---------|
| `BacklogItemDict` | dict[str, Any] in backlog.py (20 uses) | backlog.py |
| `DiagnosticResultDict` | dict[str, Any] in env_diagnostics.py (19 uses) | diagnostics/ |
| `GraphNodeDict` | dict[str, Any] in graph_validation.py (11 uses) | graph_validation.py |
| `StateDict` | dict[str, Any] in state.py (11 uses) | state/ package |
| `WorkerMetricsDict` | dict[str, Any] in worker_metrics.py (7 uses) | worker_metrics.py |
| `StatusFormatterDict` | dict[str, Any] in status_formatter.py (8 uses) | status_formatter.py |
| `TaskSyncDict` | dict[str, Any] in task_sync.py (8 uses) | task_sync.py |
| `PRDataDict` | dict[str, Any] in git/pr_engine.py (8 uses) | git/pr_engine.py |

### 4B: Apply TypedDicts to top offenders

Convert the 8 highest-count files (covering ~112 of 319 occurrences).

### 4C: Update type annotations in exceptions.py

`exceptions.py` has 9 occurrences — these are often `context: dict[str, Any]` fields that could be narrowed.

**Files**: `zerg/types.py` + 10 modified modules
**Verification**: `mypy zerg/ --strict 2>&1 | grep -c "dict\[str, Any\]"` reduced; all tests pass

**Acceptance Criteria (Phase 4)**:
- [ ] 8+ new TypedDicts defined
- [ ] dict[str, Any] count reduced from 319 to <160 (50%+ reduction)
- [ ] Top 8 offender files converted
- [ ] mypy --strict passes
- [ ] All tests pass

---

## Phase 5: Rendering Layer Extraction (P2)

**PR scope**: Separate CLI rendering from business logic in dryrun.py and status.py.

### 5A: Create zerg/rendering/ package

```
zerg/rendering/
├── __init__.py
├── shared.py            # Move render_utils.py content here
├── dryrun_renderer.py   # Extract 11 _render_* methods from dryrun.py
└── status_renderer.py   # Extract DashboardRenderer + render functions from status.py
```

### 5B: Refactor dryrun.py

Split `DryRunSimulator` into:
- **`DryRunAnalyzer`** (business logic): validation, timeline computation, risk analysis, gate checks
- **`DryRunRenderer`** (rendering): all 11 `_render_*` methods using Rich

`DryRunSimulator.run()` becomes: `analyzer.analyze()` → `renderer.render(report)`

### 5C: Refactor status.py

Split into:
- **`StatusCollector`** (business logic): data gathering from state, task list, file system
- **`StatusRenderer`** (rendering): DashboardRenderer + 6 `_render_*` methods + 10 standalone render functions

### 5D: Move render_utils.py into package

Move `zerg/render_utils.py` → `zerg/rendering/shared.py`, update imports.

**Files**: New `zerg/rendering/` (4 files), modified `dryrun.py`, `status.py`, delete `render_utils.py`
**Verification**: `pytest tests/ -k "dryrun or status" --timeout=60`

**Acceptance Criteria (Phase 5)**:
- [ ] `zerg/rendering/` package exists with 4 modules
- [ ] dryrun.py business logic separated from rendering
- [ ] status.py business logic separated from rendering
- [ ] No Rich imports in business-logic-only modules
- [ ] All tests pass

---

## Phase 6: MEDIUM Exception Handlers (P2)

**PR scope**: Address the 122 MEDIUM-severity exception handlers (log but swallow).

**Strategy**: Not all need changing — some log-and-swallow patterns are intentional for resilience. Categorize and fix:

### 6A: Identify handlers that should re-raise

Handlers in **critical paths** where swallowing hides failures:
- `zerg/merge.py` — merge failures should propagate
- `zerg/gates.py` — quality gate failures should propagate
- `zerg/verify.py` — verification failures should propagate
- `zerg/state.py` — persistence failures should propagate

### 6B: Narrow exception types

Replace broad `except Exception` with specific types in handlers where the failure mode is known:
- `json.JSONDecodeError` for JSON parsing
- `FileNotFoundError` / `OSError` for file operations
- `subprocess.SubprocessError` for command execution
- `KeyError` / `ValueError` for data validation

### 6C: Add noqa comments for intentional swallows

For handlers that intentionally swallow (e.g., plugin loading, non-critical diagnostics), add:
```python
except Exception as e:  # noqa: BLE001 — intentional: plugin failure shouldn't crash orchestrator
    logger.warning("Plugin %s failed: %s", name, e)
```

**Files**: ~40 files
**Verification**: `ruff check zerg/ --select BLE001` reports only annotated exceptions; all tests pass

**Acceptance Criteria (Phase 6)**:
- [ ] Critical-path handlers re-raise or fail explicitly
- [ ] 50+ handlers narrowed to specific exception types
- [ ] Remaining intentional swallows have noqa + justification
- [ ] Total `except Exception` count reduced from 192 to <80
- [ ] All tests pass

---

## Phase 7: orjson Integration (P3)

**PR scope**: Add orjson wrapper + migrate hot-path modules.

### 7A: Create zerg/json_utils.py

```python
"""JSON abstraction — uses orjson when available, falls back to stdlib json."""
try:
    import orjson
    def loads(data: str | bytes) -> Any: return orjson.loads(data)
    def dumps(obj: Any, *, indent: bool = False) -> str:
        opts = orjson.OPT_INDENT_2 if indent else 0
        return orjson.dumps(obj, option=opts, default=str).decode()
    def dump(obj: Any, fp, *, indent: bool = False) -> None:
        fp.write(dumps(obj, indent=indent))
    def load(fp) -> Any: return loads(fp.read())
except ImportError:
    import json
    def loads(data): return json.loads(data)
    def dumps(obj, *, indent=False): return json.dumps(obj, indent=2 if indent else None, default=str)
    def dump(obj, fp, *, indent=False): json.dump(obj, fp, indent=2 if indent else None, default=str)
    def load(fp): return json.load(fp)
```

### 7B: Add orjson to optional dependencies

```toml
[project.optional-dependencies]
performance = ["orjson>=3.9.0"]
all = ["zerg[dev]", "zerg[metrics]", "zerg[performance]"]
```

### 7C: Migrate hot-path modules

Priority modules (highest JSON I/O frequency):
1. `zerg/state.py` (or `zerg/state/persistence.py` after Phase 3) — most critical
2. `zerg/log_aggregator.py` — frequent log parsing
3. `zerg/token_counter.py` — metadata persistence
4. `zerg/parser.py` — task graph parsing
5. `zerg/validation.py` — graph validation

### 7D: Gradual migration of remaining 45 files

Batch migrate remaining `import json` users to `from zerg.json_utils import loads, dumps`.

**Files**: New `zerg/json_utils.py`, `pyproject.toml`, 50 modified files
**Verification**: `python -c "from zerg.json_utils import loads, dumps"` + all tests pass

**Acceptance Criteria (Phase 7)**:
- [ ] `json_utils.py` abstraction with orjson/stdlib fallback
- [ ] orjson in optional dependencies
- [ ] Hot-path modules migrated
- [ ] All 50 json-using files migrated
- [ ] All tests pass with and without orjson installed

---

## Phase 8: Type Ignore Resolution & Lint Hardening (P3)

**PR scope**: Resolve or annotate all 13 type: ignore comments + harden mypy config.

### 8A: Resolve 5 easy fixes

| File | Fix |
|------|-----|
| `config.py:39` | Install `types-pyyaml` or add to dev deps |
| `rules/loader.py:11` | Same — yaml stubs |
| `commands/init.py:410` | Same — yaml stubs |
| `diagnostics/env_diagnostics.py:355` | Same — yaml stubs |
| `formatter_detector.py:16` | Use `sys.version_info` conditional import |

### 8B: Resolve 7 medium fixes

| File | Fix |
|------|-----|
| `git/history_engine.py:356,471` | Replace `max(d, key=d.get)` with `max(d, key=lambda k: d[k])` |
| `git/rescue.py:430` | Add explicit type cast with validation |
| `protocol_state.py:209` | Add type narrowing for sentinel check |
| `commands/design.py:692` | Define proper key type alias |
| `verify.py:218` | Add None guard before return |
| `parser.py:87` | Add explicit type assertion |

### 8C: Annotate 1 genuinely needed ignore

`plugins.py:285` — importlib.metadata API polymorphism. Add justification comment.

### 8D: Harden pyproject.toml

```toml
[tool.mypy]
warn_unused_ignores = true
show_error_codes = true
```

**Files**: `pyproject.toml`, 10 modified files
**Verification**: `mypy zerg/ --strict` passes with 0 errors and 0 unnecessary ignores

**Acceptance Criteria (Phase 8)**:
- [ ] `types-pyyaml` added to dev dependencies
- [ ] type: ignore count reduced from 13 to ≤1
- [ ] Remaining ignores have justification comments
- [ ] `warn_unused_ignores = true` in mypy config
- [ ] mypy --strict passes clean

---

## Phase Dependencies

```
Phase 1 (exceptions) ─────────────────────────────────────> Phase 6 (medium exceptions)
Phase 2 (rglob) ──────────> standalone
Phase 3 (StateManager) ───> Phase 4 (TypedDict) ─> can reference state/ types
Phase 5 (rendering) ──────> standalone (can parallel with 3/4)
Phase 7 (orjson) ─────────> after Phase 3 (state.py moves)
Phase 8 (type:ignore) ────> after Phase 7 (pyproject changes)
```

**Recommended execution order**: 1 → 2 → 3 → [4, 5 parallel] → 6 → 7 → 8

## Scope Boundaries

### In Scope
- All 7 GitHub issues (#134, #137, #139, #140, #143, #145, #146)
- New utility modules (fs_utils.py, json_utils.py)
- Package creation (zerg/state/, zerg/rendering/)
- Lint rule additions (BLE001)
- Dependency additions (types-pyyaml, orjson optional)

### Out of Scope
- New features
- Test additions beyond what's needed for new modules
- Performance benchmarking (orjson gains are well-documented)
- Mypy strict mode enforcement on test files

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| StateManager decomposition breaks 30 importers | Facade pattern preserves exact API |
| orjson bytes vs str incompatibility | Wrapper always returns str via `.decode()` |
| Exception narrowing misses edge cases | Run full test suite per file change |
| Rendering extraction changes CLI output | Visual diff testing of status/dryrun output |

## Unresolved Questions

1. **Phase 3 timing**: Should StateManager decomposition wait for any in-flight features that touch state.py?
2. **orjson as required vs optional**: The issue says optional, but if we're migrating all 50 files, should it be a required dependency?
3. **Exception handler count target**: Is reducing from 192 to <80 ambitious enough, or should we aim for <40?
4. **dict[str, Any] in exceptions.py**: The `context` field is intentionally `Any` — should we keep it or narrow to `str | int | float | bool | None`?
5. **Phase 5 rendering tests**: dryrun.py and status.py have limited test coverage — should we add rendering tests as part of the extraction, or just ensure no regression?
