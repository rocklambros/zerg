# Requirements: test-suite-reduction-phase678

**Status: APPROVED**
**Created**: 2026-02-06
**Feature**: Test Suite Reduction — Phases 6-8 (final)
**Parent Issue**: #156

## Problem Statement

Phases 1-5 of issue #156 are complete (PRs #157, #158, #159). Current state:
- **3,894 tests** (unit + integration), down from 7,821
- **878 integration tests** across 57 files (untouched by Phases 1-5)
- CI runs 2 shards, ~3 min, no docker exclusion, no coverage floor

Remaining work: Phase 6 (integration test reduction), Phase 7 (CI config), Phase 8 (verification).

**After this PR**: ~3,350 tests | ~43 integration test files | CI <2.5min | `--cov-fail-under=75`

## Scope

### Phase 6: Integration Test Reduction (~263 deleted + 101 CI-excluded + ~170 thinned)

#### 6A: Mark container integration tests with `@pytest.mark.docker` (101 tests, 0 deleted)

Add `@pytest.mark.docker` to all 11 `test_container_*.py` files in `tests/integration/`. These tests require Docker and should not run in CI. They remain runnable locally via `pytest -m docker`.

Files (11):
| File | Tests |
|------|------:|
| test_container_detection.py | ~10 |
| test_container_devcontainer.py | ~8 |
| test_container_e2e_live.py | ~6 |
| test_container_e2e.py | ~12 |
| test_container_init_cmd.py | ~8 |
| test_container_launcher_checks.py | ~7 |
| test_container_launcher.py | ~10 |
| test_container_lifecycle.py | ~12 |
| test_container_orchestrator.py | ~8 |
| test_container_rush_cmd.py | ~10 |
| test_container_startup.py | ~10 |
| **Total** | **101** |

Action: Add `@pytest.mark.docker` at module level (pytestmark) to each file.

#### 6B: Delete 14 redundant integration test files (~263 tests)

These files duplicate coverage already in unit tests or other integration files.

| File | Tests | Reason |
|------|------:|--------|
| test_test_cmd.py | 32 | Covered by unit test_test_cmd.py |
| test_git_cmd.py | 21 | Covered by unit test_git_cmd.py |
| test_git_ops_extended.py | 27 | Covered by unit test_git_ops.py |
| test_worker_protocol_extended.py | 24 | Covered by unit test_worker_protocol.py |
| test_dedup_behavioral.py | 26 | Covered by unit test_dedup_unified.py |
| test_merge_coordination.py | 25 | Covered by unit test_merge_flow.py |
| test_merge_flow.py | 11 | Covered by unit test_merge_flow.py |
| test_rush_performance.py | 14 | Non-functional perf tests |
| test_analyze_all_checks.py | 14 | Covered by unit test_analyze_new_checks.py |
| test_design_wiring_injection.py | 14 | Covered by unit tests |
| test_wiring_enforcement.py | 13 | Covered by unit tests |
| test_inception_mode.py | 13 | Covered by unit tests |
| test_orchestrator_fixes.py | 13 | Covered by unit test_orchestrator.py |
| test_resilience_e2e.py | 16 | Covered by unit resilience tests |
| **Total** | **263** |

#### 6C: Thin 9 remaining large integration test files (~170 tests removed)

Apply same thinning rules as Phases 2-5 to integration files with >20 tests.

| File | Current | Target |
|------|--------:|-------:|
| test_merge_integration.py | 47 | 20 |
| test_launcher_integration.py | 34 | 15 |
| test_step_execution.py | 31 | 15 |
| test_debug.py | 30 | 15 |
| test_state_integration.py | 29 | 15 |
| test_dedup_behavioral.py | 26 | — (deleted in 6B) |
| test_context_engineering.py | 23 | 12 |
| test_refactor.py | 23 | 12 |
| test_review.py | 23 | 12 |
| test_build.py | 21 | 12 |
| **Total thinned** | **261** | **128** (~133 removed) |

Files with ≤20 tests: keep as-is.

### Phase 7: CI Configuration

Changes to `.github/workflows/ci.yml`:

1. **Docker marker exclusion**: Change test command from:
   ```
   -m "not slow"
   ```
   to:
   ```
   -m "not slow and not docker"
   ```

2. **Coverage floor**: Add to test command:
   ```
   --cov=zerg --cov-fail-under=75
   ```

3. **Shard consolidation**: Evaluate whether to drop to 1 shard. If total test time <2.5min with 1 shard, consolidate. Otherwise keep 2.

4. **Unit container tests**: Add `@pytest.mark.docker` to `tests/unit/test_containers.py` and `tests/unit/test_container_resources.py` to exclude from CI (per issue #156 Phase 7 spec).

### Phase 8: Verification

Final validation after all changes:

1. Full test suite passes: `pytest tests/ --ignore=tests/e2e --ignore=tests/pressure -m "not slow and not docker" --timeout=120`
2. Coverage ≥ 75%: `--cov=zerg --cov-fail-under=75`
3. Smoke tests pass: `pytest -m smoke -x --timeout=5`
4. Import check: `python -c "import zerg; print('OK')"`
5. Validate commands: `python -m zerg.validate_commands`
6. Total test count in range 3,200-3,500
7. CHANGELOG updated
8. `.test_durations` regenerated

## Thinning Rules (same as Phases 2-5)

1. Keep 1 happy-path + 1 error-path test per class
2. Collapse enum tests to 1 parametrized test
3. Parametrize where 3+ tests differ only by input
4. Remove arg permutation tests (keep boundary + typical)
5. Preserve ALL @pytest.mark.smoke tests
6. Remove duplicate assertions on same code path

## Non-Functional Requirements

- Coverage stays ≥ 75% overall
- No production code changes (except adding pytest markers)
- CI must continue passing
- No security-related tests removed unless redundant
- validate_commands must pass
- Container tests remain runnable locally with `pytest -m docker`

## Acceptance Criteria

- 14 integration files deleted
- 11 container integration files marked with `@pytest.mark.docker`
- 2 unit container test files marked with `@pytest.mark.docker`
- 9 integration files thinned to targets (±5)
- CI config updated with docker exclusion and coverage floor
- Full test suite passes
- Total test count in range 3,200-3,500
- CHANGELOG updated
- `.test_durations` regenerated

## Estimated Reduction

| Phase | Tests Removed | Files Changed |
|-------|-------------:|-------------:|
| 6A: Docker markers | 0 (101 CI-excluded) | 11 marked |
| 6B: Integration deletion | ~263 | 14 deleted |
| 6C: Integration thinning | ~133 | 9 thinned |
| 7: CI config | 0 | 1 modified + 2 marked |
| 8: Verification | 0 | 2 updated |
| **Total** | **~396 + 101 excluded** | **14 deleted, 22 modified** |

## Dependencies

No new dependencies. Existing infrastructure sufficient.

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Coverage drops below 75% | Low | Medium | Monitor after each phase |
| Integration tests covering unique paths deleted | Medium | Medium | Read each file before deleting |
| Docker marker breaks existing CI | Low | Low | Marker only excludes, doesn't break |
| Shard consolidation too slow | Medium | Low | Keep 2 shards if >2.5min |
