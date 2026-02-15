# Technical Design: test-coverage-improvement

## Metadata
- **Feature**: test-coverage-improvement
- **Status**: DRAFT
- **Created**: 2026-02-07
- **Author**: Factory Design Mode

---

## 1. Overview

### 1.1 Summary
Add targeted unit tests to 26 under-covered modules using the streamlined test method (parameterization, direct unit testing, shared fixtures). No production code changes — pure test additions.

### 1.2 Goals
- Raise overall coverage from 77% to >80%
- Eliminate all modules below 50% coverage
- All critical-path modules ≥75%

### 1.3 Non-Goals
- Refactoring production code
- Changing CI/CD configuration
- Adding test infrastructure beyond conftest fixtures

---

## 2. Architecture

### 2.1 High-Level Design

No architectural changes. This is a test-only effort adding/enhancing test files.

```
tests/unit/
├── test_merge.py                    # NEW: Direct MergeCoordinator tests
├── test_state_reconciler.py         # ENHANCE: Add reconciliation path tests
├── test_ports.py                    # NEW: Port allocation tests
├── test_status_renderer.py          # NEW: Rich rendering tests
├── test_subprocess_launcher.py      # NEW: SubprocessLauncher tests
├── test_history_engine.py           # ENHANCE: Add uncovered paths
├── test_protocol_handler.py         # NEW: Message handling tests
├── test_level_coordinator.py        # ENHANCE: Add uncovered paths
├── test_inception.py                # ENHANCE: Add uncovered paths
├── test_spec_loader.py              # ENHANCE: Add uncovered paths
├── test_container_launcher.py       # ENHANCE: Add uncovered paths
├── test_launcher_base.py            # ENHANCE: Add uncovered paths
├── test_rescue.py                   # ENHANCE: Add uncovered paths
├── test_perf_adapters_batch.py      # NEW: Batch adapter coverage
├── test_state_repos.py              # NEW: retry/worker/metrics/task repos
├── test_rendering_shared.py         # NEW: Shared rendering utilities
├── test_json_utils.py               # NEW: JSON utility tests
├── test_render_utils.py             # NEW: Render utils tests
└── test_retry_backoff.py            # NEW: Retry backoff tests
```

### 2.2 Component Breakdown

| Component | Responsibility | Test Files |
|-----------|---------------|------------|
| Critical (<50%) | 11 modules, biggest coverage gaps | 6 new + 2 enhanced |
| Low (50-74%) | 15 modules, partial gaps | 3 new + 8 enhanced |
| Micro modules | Small files <30 lines | 3 new (bundled) |

### 2.3 Test Method

Each test file follows the streamlined pattern:
1. Import the class/function under test directly
2. Use `@pytest.fixture` for setup, `@pytest.mark.parametrize` for variants
3. Mock external dependencies (filesystem, subprocess, network)
4. Test behavior (return values, side effects), not implementation
5. One test class per public class, organized by method

---

## 3. Detailed Design

### 3.1 Critical Modules (<50% coverage)

#### merge.py (25% → 80%)
- Test `MergeCoordinator.merge_level()`, `run_quality_gates()`, `finalize()`
- Mock git operations, state manager
- ~15 tests covering success, failure, partial merge paths

#### state_reconciler.py (28% → 80%)
- Test `reconcile()`, `detect_drift()`, `repair_state()`
- Mock state manager, task list
- ~12 tests covering drift detection, repair scenarios

#### status_renderer.py (45% → 75%)
- Test each `render_*()` method with mock data
- Mock Rich console output
- ~20 parameterized tests across render methods

#### subprocess_launcher.py (50% → 80%)
- Test `launch()`, `wait()`, `kill()`, error paths
- Mock subprocess.Popen
- ~15 tests covering lifecycle and error handling

#### Performance adapters (25-38% → 80%)
- Batch test: pipdeptree, jscpd, cloc, deptry with parameterized inputs
- Mock subprocess calls for each tool
- ~20 parameterized tests

#### ports.py (33% → 90%)
- Test port allocation, release, conflict detection
- Mock socket operations
- ~10 tests

#### render_utils.py (0% → 100%)
- Tiny module, 2 lines — 2 tests

#### json_utils.py (58% → 95%)
- Test JSON encoding/decoding edge cases
- ~5 tests

### 3.2 Low-Coverage Modules (50-74%)

#### history_engine.py (52% → 80%)
- Test commit parsing, blame analysis, history traversal
- Mock git subprocess calls
- ~15 tests for uncovered branches

#### spec_loader.py (62% → 85%)
- Test file loading, parsing, error handling
- Mock filesystem
- ~8 tests

#### State repos (61-69% → 90%)
- metrics_store, retry_repo, task_repo, worker_repo
- Direct CRUD testing with in-memory state
- ~15 parameterized tests across 4 repos

#### inception.py (66% → 85%)
- Test project detection, template selection
- Mock filesystem scanning
- ~8 tests

#### rendering/shared.py (67% → 90%)
- Test formatting helpers
- ~5 tests

#### container_launcher.py (69% → 80%)
- Test Docker command building, volume mounts, env injection
- Mock Docker subprocess
- ~10 tests

#### launchers/base.py (73% → 90%)
- Test base launcher methods
- ~5 tests

#### rescue.py (70% → 85%)
- Test rescue operations, state recovery
- Mock git/state
- ~8 tests

#### level_coordinator.py (71% → 85%)
- Test level transitions, dependency resolution
- Mock orchestrator state
- ~10 tests

#### protocol_handler.py (73% → 85%)
- Test message parsing, dispatch, error handling
- ~8 tests

#### retry_backoff.py (67% → 100%)
- Tiny module — 3 tests for exponential backoff calculation

#### trivy_adapter.py (68% → 85%)
- Test output parsing, vulnerability scoring
- Mock subprocess
- ~5 tests

---

## 4. Key Decisions

### Decision: Direct unit testing vs CLI-through testing

**Context**: Many low-coverage modules are only tested indirectly through CLI command tests.

**Options Considered**:
1. Add more CLI-level tests: Slow, fragile, poor isolation
2. Direct class/function unit tests: Fast, focused, reliable
3. Integration tests: More realistic but harder to isolate specific paths

**Decision**: Direct unit tests (option 2)

**Rationale**: The streamlined method explicitly favors direct testing over indirect. CLI tests already cover happy paths; we need to cover error/edge paths which are best isolated via unit tests.

### Decision: New files vs enhancing existing

**Context**: 7 modules have no test file, others have partial coverage.

**Decision**: Create new files for untested modules, enhance existing files for partial coverage.

**Rationale**: No gap-filling files (per test method). One test file per production module, following naming convention `test_{module}.py`.

---

## 5. Implementation Plan

### 5.1 Phase Summary

| Phase | Tasks | Parallel | Est. Time |
|-------|-------|----------|-----------|
| Foundation (L1) | 6 | Yes | 15 min |
| Core (L2) | 6 | Yes | 20 min |
| Integration (L3) | 5 | Yes | 20 min |
| Quality (L4) | 1 | No | 10 min |

### 5.2 File Ownership

| File | Task ID | Operation |
|------|---------|-----------|
| tests/unit/test_merge.py | TASK-001 | create |
| tests/unit/test_state_reconciler.py | TASK-002 | modify |
| tests/unit/test_ports.py | TASK-003 | create |
| tests/unit/test_status_renderer.py | TASK-004 | create |
| tests/unit/test_subprocess_launcher.py | TASK-005 | create |
| tests/unit/test_perf_adapters_batch.py | TASK-006 | create |
| tests/unit/test_history_engine.py | TASK-007 | modify |
| tests/unit/test_state_repos.py | TASK-008 | create |
| tests/unit/test_inception.py | TASK-009 | modify |
| tests/unit/test_spec_loader.py | TASK-010 | modify |
| tests/unit/test_container_launcher_coverage.py | TASK-011 | create |
| tests/unit/test_level_coordinator.py | TASK-012 | modify |
| tests/unit/test_protocol_handler.py | TASK-013 | create |
| tests/unit/test_rendering_shared.py | TASK-014 | create |
| tests/unit/test_rescue.py | TASK-015 | modify |
| tests/unit/test_launcher_base.py | TASK-016 | create |
| tests/unit/test_small_modules.py | TASK-017 | create |
| CHANGELOG.md | TASK-018 | modify |

### 5.3 Dependency Graph

```
Level 1 (Foundation — no deps, fully parallel):
  TASK-001: test_merge.py
  TASK-002: test_state_reconciler.py
  TASK-003: test_ports.py
  TASK-004: test_status_renderer.py
  TASK-005: test_subprocess_launcher.py
  TASK-006: test_perf_adapters_batch.py

Level 2 (Core — no deps on L1, fully parallel):
  TASK-007: test_history_engine.py
  TASK-008: test_state_repos.py
  TASK-009: test_inception.py
  TASK-010: test_spec_loader.py
  TASK-011: test_container_launcher_coverage.py
  TASK-012: test_level_coordinator.py

Level 3 (More coverage — no deps on L2, fully parallel):
  TASK-013: test_protocol_handler.py
  TASK-014: test_rendering_shared.py
  TASK-015: test_rescue.py
  TASK-016: test_launcher_base.py
  TASK-017: test_small_modules.py (render_utils, json_utils, retry_backoff)

Level 4 (Quality — depends on all above):
  TASK-018: CHANGELOG.md update + coverage verification
```

---

## 6. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Flaky tests from mocking | Medium | Medium | Use deterministic mocks, avoid time-dependent tests |
| Tests pass locally, fail CI | Low | Medium | Run full suite locally before marking complete |
| Coverage numbers don't improve enough | Low | Low | Each task has specific coverage target |

---

## 7. Testing Strategy

### 7.1 Verification per task
Each task verifies with: `pytest {test_file} -v --timeout=30`

### 7.2 Final verification
`pytest tests/unit/ -m "not slow" --cov=zerg --cov-fail-under=80 --timeout=120`

---

## 8. Parallel Execution Notes

### 8.1 Safe Parallelization
- All tasks create/modify independent test files
- No two tasks touch the same file
- No production code changes

### 8.2 Recommended Workers
- Minimum: 3 workers
- Optimal: 6 workers (matches widest level)
- Maximum: 6 workers (no benefit beyond)

### 8.3 Estimated Duration
- Single worker: ~65 min
- With 6 workers: ~25 min
- Speedup: ~2.6x
