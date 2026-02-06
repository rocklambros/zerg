# Requirements: Fix CI Test Failures + Streamline Test Suite

## Metadata
- **Feature**: test-suite-cleanup
- **Status**: APPROVED
- **Created**: 2026-02-06
- **Author**: Claude Opus 4.6

---

## 1. Problem Statement

CI run on main has 25 test failures across 4 root causes. The test suite also has redundancy: 8 root-level test files duplicate their `tests/unit/` counterparts (0 unique tests), and 2 coverage-padding files have broken tests. 10 additional root-level test files have no unit counterpart and need relocation.

---

## 2. Functional Requirements

### FR-1: Fix 25 CI Test Failures → 0

| File | Failures | Root Cause | Action |
|------|----------|------------|--------|
| test_near_complete_coverage.py | 14+ | Stale method calls (run_verification, etc.) | Delete file |
| test_orchestrator_coverage.py | 2 | Stale mock targets, asyncio collision | Delete file |
| test_orchestrator.py | 4 | Mock targets renamed to _worker_manager.* | Fix mocks |
| test_orchestrator_container_mode.py | 1 | Regex mismatch ("explicitly requested" vs actual msg) | Fix regex |
| tests/test_worker_protocol.py | 1 | Root duplicate — timeout, remove with Phase 2 | Delete (dup) |

### FR-2: Remove 8 Root-Level Duplicates

All have 0 unique tests vs unit counterpart. Pure deletes:

| Root File | Lines |
|-----------|-------|
| tests/test_config.py | 178 |
| tests/test_context_tracker.py | 271 |
| tests/test_git_ops.py | 406 |
| tests/test_launcher.py | 382 |
| tests/test_orchestrator.py | 340 |
| tests/test_state.py | 268 |
| tests/test_worker_protocol.py | 692 |
| tests/test_worktree.py | 182 |

### FR-3: Move 10 Root-Level Tests to tests/unit/

| File | Lines | Tests |
|------|-------|-------|
| test_claude_tasks_reader.py | 261 | 23 |
| test_config_caching.py | 478 | 22 |
| test_doc_engine.py | 826 | 89 |
| test_gates.py | 529 | 36 |
| test_levels.py | 333 | 28 |
| test_log_aggregator_caching.py | 232 | 7 |
| test_repo_map_caching.py | 246 | 9 |
| test_single_traversal.py | 343 | 20 |
| test_token_counter_memory.py | 261 | 8 |
| test_types.py | 553 | 34 |

### FR-4: Regenerate .test_durations

After all moves/deletes, run `pytest tests/unit tests/integration --store-durations -q` to update paths.

---

## 3. Affected Files

| Action | Files | Count |
|--------|-------|-------|
| Delete | 2 broken coverage files + 8 duplicate root files | 10 |
| Fix | test_orchestrator.py (4 mocks), test_orchestrator_container_mode.py (1 regex) | 2 |
| Move | 10 root-level tests → tests/unit/ | 10 |
| Regenerate | .test_durations | 1 |

---

## 4. Acceptance Criteria

- [ ] `pytest tests/ --ignore=tests/e2e --ignore=tests/pressure -m "not slow" --timeout=120 -q` passes with 0 failures
- [ ] No test files remain in `tests/` root (only __init__.py, conftest.py)
- [ ] .test_durations updated with correct paths
- [ ] Total lines removed: ~5,400+

---

## 5. Out of Scope

- Refactoring test content or adding new tests
- Fixing tests/e2e or tests/pressure
- Changing CI configuration
