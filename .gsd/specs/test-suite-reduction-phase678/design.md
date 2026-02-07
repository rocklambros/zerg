# Technical Design: test-suite-reduction-phase678

## Metadata
- **Feature**: test-suite-reduction-phase678
- **Status**: DRAFT
- **Created**: 2026-02-06
- **Author**: Factory Design Mode

---

## 1. Overview

### 1.1 Summary
Final phases of test suite reduction: mark 13 container test files with `@pytest.mark.docker` (11 integration + 2 unit), delete 14 redundant integration test files, thin 9 oversized integration test files, update CI config with docker exclusion + coverage floor, and verify the final state.

### 1.2 Goals
- Reduce test count from ~3,894 to ~3,200-3,500
- Exclude 101+ container tests from CI via `@pytest.mark.docker`
- Delete 263 redundant integration tests across 14 files
- Thin ~133 tests across 9 integration files
- Add `--cov-fail-under=75` to CI
- Regenerate `.test_durations` for pytest-split balancing

### 1.3 Non-Goals
- No production code changes (except adding pytest markers)
- No new test infrastructure
- No changes to e2e or pressure test directories

---

## 2. Architecture

### 2.1 High-Level Design

This is a test-only refactoring. No new components are created. The work is purely subtractive (delete/thin) and configurational (markers, CI).

```
Phase 6A: Mark container tests ─────┐
Phase 6B: Delete redundant tests ───┼── All independent, fully parallel
Phase 6C: Thin large test files ────┘
                                     │
Phase 7: CI config changes ──────────┤  Depends on 6A (docker marker)
                                     │
Phase 8: Verification ───────────────┘  Depends on ALL above
```

### 2.2 Component Breakdown

| Component | Responsibility | Files |
|-----------|---------------|-------|
| Docker marker (6A) | Add `pytestmark = pytest.mark.docker` to container test files | 11 integration + 2 unit files |
| Deletion (6B) | Remove 14 redundant integration test files | 14 files deleted |
| Thinning (6C) | Reduce test count in 9 large integration files | 9 files edited |
| CI config (7) | Update marker exclusion + coverage floor | `.github/workflows/ci.yml` |
| Verification (8) | Run full suite, check coverage, update artifacts | `.test_durations`, `CHANGELOG.md` |

### 2.3 Data Flow
N/A — no data flow changes. This is test infrastructure only.

---

## 3. Detailed Design

### 3.1 Docker Marker Pattern

Each container test file gets a module-level marker:

```python
import pytest

pytestmark = pytest.mark.docker
```

This is added near the top of each file, after imports. The marker is already registered in `pyproject.toml`.

### 3.2 CI Config Changes

**Line 86** of `.github/workflows/ci.yml` changes from:
```yaml
run: pytest tests/ --ignore=tests/e2e --ignore=tests/pressure -m "not slow" -v --tb=short --timeout=120 --splits 2 --group ${{ matrix.shard }}
```

To:
```yaml
run: pytest tests/ --ignore=tests/e2e --ignore=tests/pressure -m "not slow and not docker" --cov=zerg --cov-fail-under=75 -v --tb=short --timeout=120 --splits 2 --group ${{ matrix.shard }}
```

### 3.3 Thinning Rules (from requirements)

1. Keep 1 happy-path + 1 error-path test per class
2. Collapse enum tests to 1 parametrized test
3. Parametrize where 3+ tests differ only by input
4. Remove arg permutation tests (keep boundary + typical)
5. Preserve ALL @pytest.mark.smoke tests
6. Remove duplicate assertions on same code path

---

## 4. Key Decisions

### 4.1 Parallel Task Grouping

**Context**: 6A (markers), 6B (deletion), and 6C (thinning) touch completely disjoint file sets. 6B deletes files that 6C doesn't touch, and 6A only adds markers.

**Decision**: Run 6A, 6B, and 6C as Level 1 tasks in parallel, with 6C split into individual file tasks for maximum parallelism.

**Rationale**: No file conflicts. Each task owns exclusive files. This maximizes worker utilization.

### 4.2 Thinning Task Granularity

**Context**: 9 files need thinning. Could be 1 task, 3 tasks, or 9 tasks.

**Decision**: Split into 3 tasks of 3 files each, grouped by target count similarity.

**Rationale**: Balance between parallelism and overhead. 9 separate tasks would be too granular for test thinning (each requires reading, understanding, and carefully pruning). 1 task wastes parallelism. 3 tasks of 3 files each is the sweet spot.

### 4.3 Shard Evaluation

**Context**: Requirements say evaluate 1 vs 2 shards after reduction.

**Decision**: Keep 2 shards initially. Phase 8 verification includes a timing check. If total time <2.5min with 1 shard, a follow-up PR can consolidate.

**Rationale**: Shard consolidation is low-risk and can be done separately. Bundling it adds complexity to an already large PR.

---

## 5. Implementation Plan

### 5.1 Phase Summary

| Phase | Tasks | Parallel | Est. Time |
|-------|-------|----------|-----------|
| Level 1: Markers + Delete + Thin | 6 | Yes | 25 min |
| Level 2: CI Config | 1 | No | 10 min |
| Level 3: Verification | 1 | No | 15 min |

### 5.2 File Ownership

| File | Task ID | Operation |
|------|---------|-----------|
| tests/integration/test_container_detection.py | TASK-001 | modify (add marker) |
| tests/integration/test_container_devcontainer.py | TASK-001 | modify (add marker) |
| tests/integration/test_container_e2e_live.py | TASK-001 | modify (add marker) |
| tests/integration/test_container_e2e.py | TASK-001 | modify (add marker) |
| tests/integration/test_container_init_cmd.py | TASK-001 | modify (add marker) |
| tests/integration/test_container_launcher_checks.py | TASK-001 | modify (add marker) |
| tests/integration/test_container_launcher.py | TASK-001 | modify (add marker) |
| tests/integration/test_container_lifecycle.py | TASK-001 | modify (add marker) |
| tests/integration/test_container_orchestrator.py | TASK-001 | modify (add marker) |
| tests/integration/test_container_rush_cmd.py | TASK-001 | modify (add marker) |
| tests/integration/test_container_startup.py | TASK-001 | modify (add marker) |
| tests/unit/test_containers.py | TASK-002 | modify (add marker) |
| tests/unit/test_container_resources.py | TASK-002 | modify (add marker) |
| tests/integration/test_test_cmd.py | TASK-003 | delete |
| tests/integration/test_git_cmd.py | TASK-003 | delete |
| tests/integration/test_git_ops_extended.py | TASK-003 | delete |
| tests/integration/test_worker_protocol_extended.py | TASK-003 | delete |
| tests/integration/test_dedup_behavioral.py | TASK-003 | delete |
| tests/integration/test_merge_coordination.py | TASK-003 | delete |
| tests/integration/test_merge_flow.py | TASK-003 | delete |
| tests/integration/test_rush_performance.py | TASK-003 | delete |
| tests/integration/test_analyze_all_checks.py | TASK-003 | delete |
| tests/integration/test_design_wiring_injection.py | TASK-003 | delete |
| tests/integration/test_wiring_enforcement.py | TASK-003 | delete |
| tests/integration/test_inception_mode.py | TASK-003 | delete |
| tests/integration/test_orchestrator_fixes.py | TASK-003 | delete |
| tests/integration/test_resilience_e2e.py | TASK-003 | delete |
| tests/integration/test_merge_integration.py | TASK-004 | modify (thin 47→20) |
| tests/integration/test_launcher_integration.py | TASK-004 | modify (thin 34→15) |
| tests/integration/test_step_execution.py | TASK-004 | modify (thin 31→15) |
| tests/integration/test_debug.py | TASK-005 | modify (thin 30→15) |
| tests/integration/test_state_integration.py | TASK-005 | modify (thin 29→15) |
| tests/integration/test_context_engineering.py | TASK-005 | modify (thin 23→12) |
| tests/integration/test_refactor.py | TASK-006 | modify (thin 23→12) |
| tests/integration/test_review.py | TASK-006 | modify (thin 23→12) |
| tests/integration/test_build.py | TASK-006 | modify (thin 21→12) |
| .github/workflows/ci.yml | TASK-007 | modify |
| .test_durations | TASK-008 | regenerate |
| CHANGELOG.md | TASK-008 | modify |

### 5.3 Dependency Graph

```
Level 1 (parallel):
  TASK-001: Mark integration container tests (docker marker)
  TASK-002: Mark unit container tests (docker marker)
  TASK-003: Delete 14 redundant integration files
  TASK-004: Thin batch A (merge_integration, launcher_integration, step_execution)
  TASK-005: Thin batch B (debug, state_integration, context_engineering)
  TASK-006: Thin batch C (refactor, review, build)

Level 2 (depends on Level 1):
  TASK-007: Update CI config (needs TASK-001 + TASK-002 for docker marker to be in place)

Level 3 (depends on ALL):
  TASK-008: Final verification + artifacts
```

---

## 6. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Coverage drops below 75% | Low | Medium | Each thinning task verifies coverage locally |
| Deleted integration test covers unique path | Medium | Medium | Requirements pre-audited for redundancy |
| Docker marker breaks local test runs | Low | Low | Marker only affects `-m "not docker"` |
| Thinning removes smoke-marked test | Low | High | Thinning rules explicitly preserve smoke tests |

---

## 7. Testing Strategy

### 7.1 Per-Task Verification
- Marker tasks: `pytest tests/integration/test_container_detection.py --collect-only -m docker -q` (should collect all)
- Deletion task: `python -c "import pathlib; assert not pathlib.Path('tests/integration/test_test_cmd.py').exists()"`
- Thinning tasks: `pytest {file} --collect-only -q | tail -1` (check count ≤ target)
- CI task: `grep -q 'not docker' .github/workflows/ci.yml && grep -q 'cov-fail-under=75' .github/workflows/ci.yml`

### 7.2 Final Verification (TASK-008)
1. `pytest tests/ --ignore=tests/e2e --ignore=tests/pressure -m "not slow and not docker" --timeout=120`
2. `pytest tests/ --ignore=tests/e2e --ignore=tests/pressure -m "not slow and not docker" --cov=zerg --cov-fail-under=75 --timeout=120`
3. `pytest -m smoke -x --timeout=5`
4. `python -c "import zerg; print('OK')"`
5. `python -m zerg.validate_commands`
6. Count total tests in range 3,200-3,500
7. Regenerate `.test_durations`

---

## 8. Parallel Execution Notes

### 8.1 Safe Parallelization
- Level 1: 6 tasks, zero file conflicts, fully parallel
- Level 2: 1 task (CI config), depends on marker tasks
- Level 3: 1 task (verification), depends on all

### 8.2 Recommended Workers
- Minimum: 1 worker (sequential, ~50 min)
- Optimal: 6 workers (matches Level 1 width)
- Maximum: 6 workers (only 6 L1 tasks, L2/L3 are sequential)

### 8.3 Estimated Duration
- Single worker: ~50 min
- With 6 workers: ~25 min (L1 parallel) + 10 min (L2) + 15 min (L3) = ~50 min wall, ~25 min critical path
- Speedup: ~2x

---

## 9. Consumer Matrix

| Task | Creates/Modifies | Consumed By | Integration Test |
|------|---------|-------------|-----------------|
| TASK-001 | 11 integration container test files | TASK-007 (CI reads markers) | — (marker-only, verified by collect) |
| TASK-002 | 2 unit container test files | TASK-007 (CI reads markers) | — (marker-only, verified by collect) |
| TASK-003 | — (deletes 14 files) | leaf | — |
| TASK-004 | 3 thinned integration files | leaf | — |
| TASK-005 | 3 thinned integration files | leaf | — |
| TASK-006 | 3 thinned integration files | leaf | — |
| TASK-007 | .github/workflows/ci.yml | TASK-008 (verification reads CI) | — |
| TASK-008 | .test_durations, CHANGELOG.md | leaf | — |

---

## 10. Approval

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Architecture | | | PENDING |
| Engineering | | | PENDING |
