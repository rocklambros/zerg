# Requirements: test-suite-reduction-phase2

**Status: APPROVED**
**Created**: 2026-02-06
**Feature**: Test Suite Reduction — Phases 1-3
**Parent Issue**: #156

## Problem Statement

After PR #155 (cleanup) and PR #157 (smoke tests + launcher consolidation), the test suite stands at 7,764 tests with 92% coverage. Target from #156: ~3,000 tests at 75-80% coverage. This PR tackles the first three phases: wholesale gap-filling file deletion, doc engine gutting, and command test consolidation/thinning.

**Current**: 7,764 tests | 190 unit test files | 92% coverage | ~4.5min CI
**After this PR**: ~5,200 tests | ~160 unit test files | ~83-87% coverage | ~3min CI

## Scope: Phases 1, 2, 3 from #156

### Phase 1: Wholesale Gap-Filling File Deletion (~649 tests, 14 files)

Delete all `_coverage`, `_extended`, `_full`, `_misc` gap-filling files. Base test files already cover core paths.

**DELETE (14 files)**:

| File | Tests | Rationale |
|------|------:|-----------|
| test_cleanup_rush_coverage.py | 30 | Gap-filler, covered by test_cleanup_cmd.py |
| test_containers_coverage.py | 32 | Gap-filler, covered by test_launcher_container_ops.py |
| test_debug_coverage.py | 42 | Gap-filler, covered by test_debug_cmd.py |
| test_launcher_coverage.py | 49 | Gap-filler, covered by test_launcher.py + test_launcher_container_ops.py |
| test_perf_adapters_coverage.py | 76 | Gap-filler, covered by test_performance_*.py |
| test_utils_coverage.py | 69 | Gap-filler, covered by test_utils.py |
| test_levels_extended.py | 52 | Extended, covered by test_levels.py |
| test_logging_extended.py | 6 | Extended, covered by test_logging.py |
| test_logs_cmd_extended.py | 8 | Extended, covered by test_logs_cmd.py |
| test_ports_extended.py | 26 | Extended, covered by test_ports.py |
| test_state_extended.py | 34 | Extended, covered by test_state.py |
| test_worktree_extended.py | 29 | Extended, covered by test_worktree.py |
| test_charter_full.py | 41 | Full-coverage, covered by test_charter.py |
| test_security_rules_full.py | 121 | Full-coverage, covered by test_security_rules_cmd.py |

**Acceptance Criteria**:
- All 14 files deleted
- pytest passes on all remaining test files
- No unique assertions lost (base files cover same paths)
- Coverage stays >= 80%

### Phase 2: Doc Engine Gutting (~400 tests, 3 files deleted + 1 thinned)

Non-critical wiki generator with 434 tests across 4 files. Keep ~30 essential tests.

**DELETE entirely (3 files)**:

| File | Tests | Rationale |
|------|------:|-----------|
| test_doc_engine_crossref.py | 113 | Cross-ref permutations, low value |
| test_doc_engine_extractor.py | 118 | Extraction edge cases, low value |
| test_doc_engine_renderer.py | 114 | Formatting variants, low value |

**THIN (1 file)**:

| File | Current | Target | Keep |
|------|--------:|-------:|------|
| test_doc_engine.py | 89 | ~30 | Instantiation, generate() happy path, missing file errors, basic rendering |

**Acceptance Criteria**:
- 3 files deleted
- test_doc_engine.py thinned to ~25-35 tests
- pytest passes on test_doc_engine.py
- Coverage on doc_engine module >= 60%

### Phase 3: Command Test Consolidation (~1,474 tests → ~430)

#### Phase 3A: Merge `test_cmd_*` into `test_*_cmd` counterparts (8 files, 75 tests)

For each `test_cmd_*.py`, merge 2-3 essential tests into the corresponding `test_*_cmd.py`, then delete the `test_cmd_*.py` file.

| Source (delete) | Target (merge into) | Source Tests |
|----------------|---------------------|------------:|
| test_cmd_cleanup.py | test_cleanup_cmd.py | 9 |
| test_cmd_init.py | test_init_cmd.py | 8 |
| test_cmd_logs.py | test_logs_cmd.py | 7 |
| test_cmd_merge.py | test_merge_cmd.py | 9 |
| test_cmd_retry.py | test_retry_cmd.py | 9 |
| test_cmd_security_rules.py | test_security_rules_cmd.py | 11 |
| test_cmd_status.py | test_status_cmd.py | 13 |
| test_cmd_stop.py | test_stop_cmd.py | 9 |

**Acceptance Criteria**:
- 8 `test_cmd_*.py` files deleted
- 2-3 unique tests from each merged into target
- pytest passes on all target files

#### Phase 3B: Thin command test files (~1,399 → ~400)

Apply thinning rules to each `*_cmd.py` file:
- Keep 1 enum existence test, delete per-value tests
- Keep 1 detection test per language, delete permutations
- Keep 1 happy path + 1 error case per feature class
- Keep 1 CLI help + 1 basic execution, delete arg permutations

| File | Current | Target |
|------|--------:|-------:|
| test_test_cmd.py | 109 | 25 |
| test_build_cmd.py | 105 | 25 |
| test_init_cmd.py | 107 | 25 |
| test_debug_cmd.py | 139 | 30 |
| test_git_cmd.py | 101 | 30 |
| test_review_cmd.py | 90 | 25 |
| test_refactor_cmd.py | 92 | 25 |
| test_analyze_cmd.py | 89 | 25 |
| test_status_cmd.py | 82 | 25 |
| test_cleanup_cmd.py | 52 | 20 |
| test_logs_cmd.py | 84 | 20 |
| test_plan_cmd.py | 65 | 25 |
| test_design_cmd.py | 53 | 20 |
| test_rush_cmd.py | 59 | 25 |
| test_stop_cmd.py | 40 | 15 |
| test_retry_cmd.py | 46 | 15 |
| test_merge_cmd.py | 36 | 15 |
| test_security_rules_cmd.py | 50 | 15 |

**Acceptance Criteria**:
- Each file thinned to target count (±5)
- pytest passes on all thinned files
- Coverage on command modules >= 70%
- No happy-path coverage holes

## Non-Functional Requirements

- Coverage stays >= 80% overall (currently 92%)
- No production code changes
- CI must continue passing (smoke + test shards)
- No security-related tests removed unless redundant
- validate_commands must pass

## Scope Boundaries

### In Scope
- Phase 1: 14 gap-filling file deletions
- Phase 2: 3 doc engine file deletions + 1 thinning
- Phase 3A: 8 cmd file merges + deletions
- Phase 3B: 18 cmd file thinnings
- CHANGELOG update
- .test_durations regeneration

### Out of Scope (future PRs)
- Phase 4: Module consolidation (state, merge, orchestrator, diagnostics, launcher thinning)
- Phase 5: Secondary module thinning
- Phase 6: Integration test reduction
- Phase 7: CI config (single shard, coverage floor)
- Phase 8: Final verification

## Dependencies

No new dependencies. Existing infrastructure sufficient:
- pytest-split (installed)
- pytest-xdist (installed)
- Smoke marker + CI job (from PR #157)

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Coverage drops below 80% | Low | Medium | Monitor after each phase, add back tests if needed |
| Unique assertions lost in Phase 3B thinning | Medium | Medium | Read each file fully before thinning, keep all unique happy-path tests |
| Phase 3B thinning targets too aggressive | Low | Low | Targets are ±5, adjust per file |
| CI breaks | Low | High | Run full suite before committing each phase |

## Estimated Reduction

| Phase | Tests Removed | Files Deleted |
|-------|-------------:|-------------:|
| Phase 1 | ~649 | 14 |
| Phase 2 | ~404 | 3 + 1 thinned |
| Phase 3A | ~50 (after merge) | 8 |
| Phase 3B | ~999 | 0 (18 thinned) |
| **Total** | **~2,100** | **25 deleted** |

**Expected result**: ~5,600 → ~5,200 tests (accounting for merge preservation), ~165 unit test files, ~83-87% coverage.
