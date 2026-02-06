# Technical Design: test-suite-reduction-phase2

## Metadata
- **Feature**: test-suite-reduction-phase2
- **Status**: DRAFT
- **Created**: 2026-02-06
- **Author**: Factory Design Mode

---

## 1. Overview

### 1.1 Summary
Delete 25 gap-filling/doc-engine test files and thin 18 command test files from ~1,399 to ~400 tests. No production code changes. Pure test file deletion and reduction.

### 1.2 Goals
- Delete 14 gap-filling files (649 tests)
- Delete 3 doc engine files + thin 1 (404 tests)
- Merge 8 test_cmd_* files into counterparts then delete (75 tests)
- Thin 18 command test files (1,399 → ~400 tests)
- Maintain >= 80% coverage

### 1.3 Non-Goals
- Production code changes
- Module consolidation (Phase 4-5 of #156)
- Integration test reduction (Phase 6)
- CI configuration changes (Phase 7)

---

## 2. Architecture

### 2.1 Approach

No architectural changes. This is a test-only reduction with three strategies:

1. **Wholesale deletion** — Remove entire files where base tests cover same paths
2. **Merge + delete** — Migrate 2-3 unique tests from test_cmd_* into test_*_cmd counterparts, delete source
3. **Thinning** — Reduce test count per file using systematic rules

### 2.2 Thinning Rules (for Phase 3B workers)

Each worker thins a command test file by applying these rules in order:

1. **Enum tests**: Keep 1 test asserting all enum values exist. Delete individual per-value tests.
2. **Detection tests**: Keep 1 test per language/framework. Delete permutation variants.
3. **Feature class tests**: Keep 1 happy-path + 1 error-path per class. Delete edge case variants.
4. **CLI tests**: Keep 1 help test + 1 basic execution. Delete argument permutation tests.
5. **Parametrize consolidation**: Where multiple individual tests test the same function with different inputs, replace with a single `@pytest.mark.parametrize` covering the key cases.

**Do NOT delete**: Tests that cover unique code paths, error handlers, or security-relevant behavior.

---

## 3. Key Decisions

### 3.1 Single Task for Phase 1 Deletions

**Context**: 14 files to delete with no content preservation needed.
**Decision**: One task deletes all 14 files.
**Rationale**: Pure `git rm` operations, no merge logic. One worker can delete all in seconds.

### 3.2 Phase 3B: Split by File Size

**Context**: 18 files to thin, ranging from 765 LOC to 1,788 LOC.
**Decision**: Split into 3 workers by file count (6 files each), balanced by total LOC.
**Rationale**: Each file is independent. 3 workers matches max parallelization from prior rush.

### 3.3 Phase 3A Before 3B for Shared Files

**Context**: test_cmd_cleanup.py merges into test_cleanup_cmd.py, which also gets thinned.
**Decision**: Phase 3A (merge) runs at Level 2, Phase 3B (thin) at Level 3.
**Rationale**: Must merge unique tests before thinning, or we lose them.

---

## 4. Implementation Plan

### 4.1 Phase Summary

| Level | Phase | Tasks | Parallel | Est. Time |
|-------|-------|-------|----------|-----------|
| 1 | Deletion | 2 | Yes | 3 min |
| 2 | Cmd merge | 1 | No | 8 min |
| 3 | Cmd thinning | 3 | Yes | 15 min |
| 4 | Verification | 1 | No | 8 min |

### 4.2 File Ownership

**Level 1 — Deletions (2 tasks, parallel)**

| File | Task | Operation |
|------|------|-----------|
| tests/unit/test_cleanup_rush_coverage.py | TSR2-L1-001 | delete |
| tests/unit/test_containers_coverage.py | TSR2-L1-001 | delete |
| tests/unit/test_debug_coverage.py | TSR2-L1-001 | delete |
| tests/unit/test_launcher_coverage.py | TSR2-L1-001 | delete |
| tests/unit/test_perf_adapters_coverage.py | TSR2-L1-001 | delete |
| tests/unit/test_utils_coverage.py | TSR2-L1-001 | delete |
| tests/unit/test_levels_extended.py | TSR2-L1-001 | delete |
| tests/unit/test_logging_extended.py | TSR2-L1-001 | delete |
| tests/unit/test_logs_cmd_extended.py | TSR2-L1-001 | delete |
| tests/unit/test_ports_extended.py | TSR2-L1-001 | delete |
| tests/unit/test_state_extended.py | TSR2-L1-001 | delete |
| tests/unit/test_worktree_extended.py | TSR2-L1-001 | delete |
| tests/unit/test_charter_full.py | TSR2-L1-001 | delete |
| tests/unit/test_security_rules_full.py | TSR2-L1-001 | delete |
| tests/unit/test_doc_engine_crossref.py | TSR2-L1-002 | delete |
| tests/unit/test_doc_engine_extractor.py | TSR2-L1-002 | delete |
| tests/unit/test_doc_engine_renderer.py | TSR2-L1-002 | delete |
| tests/unit/test_doc_engine_misc.py | TSR2-L1-002 | delete |
| tests/unit/test_doc_engine.py | TSR2-L1-002 | thin (89→30) |

**Level 2 — Cmd merges (1 task)**

| File | Task | Operation |
|------|------|-----------|
| tests/unit/test_cmd_cleanup.py | TSR2-L2-001 | merge→delete |
| tests/unit/test_cmd_init.py | TSR2-L2-001 | merge→delete |
| tests/unit/test_cmd_logs.py | TSR2-L2-001 | merge→delete |
| tests/unit/test_cmd_merge.py | TSR2-L2-001 | merge→delete |
| tests/unit/test_cmd_retry.py | TSR2-L2-001 | merge→delete |
| tests/unit/test_cmd_security_rules.py | TSR2-L2-001 | merge→delete |
| tests/unit/test_cmd_status.py | TSR2-L2-001 | merge→delete |
| tests/unit/test_cmd_stop.py | TSR2-L2-001 | merge→delete |
| tests/unit/test_cleanup_cmd.py | TSR2-L2-001 | modify (receive merge) |
| tests/unit/test_init_cmd.py | TSR2-L2-001 | modify (receive merge) |
| tests/unit/test_logs_cmd.py | TSR2-L2-001 | modify (receive merge) |
| tests/unit/test_merge_cmd.py | TSR2-L2-001 | modify (receive merge) |
| tests/unit/test_retry_cmd.py | TSR2-L2-001 | modify (receive merge) |
| tests/unit/test_security_rules_cmd.py | TSR2-L2-001 | modify (receive merge) |
| tests/unit/test_status_cmd.py | TSR2-L2-001 | modify (receive merge) |
| tests/unit/test_stop_cmd.py | TSR2-L2-001 | modify (receive merge) |

**Level 3 — Cmd thinning (3 tasks, parallel)**

Worker A (6 files, ~7,466 LOC):

| File | Task | Current → Target |
|------|------|-----------------|
| tests/unit/test_debug_cmd.py | TSR2-L3-001 | 139→30 |
| tests/unit/test_rush_cmd.py | TSR2-L3-001 | 59→25 |
| tests/unit/test_status_cmd.py | TSR2-L3-001 | 82→25 |
| tests/unit/test_review_cmd.py | TSR2-L3-001 | 90→25 |
| tests/unit/test_git_cmd.py | TSR2-L3-001 | 101→30 |
| tests/unit/test_test_cmd.py | TSR2-L3-001 | 109→25 |

Worker B (6 files, ~7,032 LOC):

| File | Task | Current → Target |
|------|------|-----------------|
| tests/unit/test_build_cmd.py | TSR2-L3-002 | 105→25 |
| tests/unit/test_init_cmd.py | TSR2-L3-002 | 107→25 |
| tests/unit/test_refactor_cmd.py | TSR2-L3-002 | 92→25 |
| tests/unit/test_analyze_cmd.py | TSR2-L3-002 | 89→25 |
| tests/unit/test_cleanup_cmd.py | TSR2-L3-002 | 52→20 |
| tests/unit/test_logs_cmd.py | TSR2-L3-002 | 84→20 |

Worker C (6 files, ~5,440 LOC):

| File | Task | Current → Target |
|------|------|-----------------|
| tests/unit/test_plan_cmd.py | TSR2-L3-003 | 65→25 |
| tests/unit/test_design_cmd.py | TSR2-L3-003 | 53→20 |
| tests/unit/test_stop_cmd.py | TSR2-L3-003 | 40→15 |
| tests/unit/test_retry_cmd.py | TSR2-L3-003 | 46→15 |
| tests/unit/test_merge_cmd.py | TSR2-L3-003 | 36→15 |
| tests/unit/test_security_rules_cmd.py | TSR2-L3-003 | 50→15 |

**Level 4 — Verification (1 task)**

| File | Task | Operation |
|------|------|-----------|
| CHANGELOG.md | TSR2-L4-001 | modify |
| .test_durations | TSR2-L4-001 | regenerate |

### 4.3 Dependency Graph

```
L1: TSR2-L1-001 (gap-fill delete)  ──┐
    TSR2-L1-002 (doc engine)        ──┤
                                      ├──▶ L2: TSR2-L2-001 (cmd merge) ──▶ L3: TSR2-L3-001 (thin A) ──┐
                                      │                                     TSR2-L3-002 (thin B) ──┤
                                      │                                     TSR2-L3-003 (thin C) ──┤
                                      │                                                             │
                                      └─────────────────────────────────────────────────────────────┴──▶ L4: TSR2-L4-001 (verify)
```

---

## 5. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Coverage drops below 80% | Low | Medium | 92% baseline, removing ~2,100 tests from 7,764 still leaves core coverage |
| Unique assertions lost in thinning | Medium | Medium | Workers read full file, keep all unique happy-path tests |
| Phase 3B targets too aggressive | Low | Low | Targets ±5, workers use judgment |
| CI breaks after deletions | Low | High | Verification task runs full suite |

---

## 6. Testing Strategy

- Each deletion task runs pytest on remaining related files
- Phase 3B workers run pytest on each thinned file
- Verification task runs full suite + validate_commands + smoke suite
- Coverage checked at verification stage

---

## 7. Parallel Execution Notes

- **Level 1**: 2 workers (gap-fill + doc engine) — fully parallel
- **Level 2**: 1 worker (cmd merges) — sequential, touches 16 files
- **Level 3**: 3 workers (thinning A/B/C) — fully parallel, no file overlap
- **Level 4**: 1 worker (verification) — sequential
- **Optimal workers**: 3
- **Single worker**: ~35 min
- **With 3 workers**: ~20 min

---

## 8. Approval

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Architecture | | | PENDING |
| Engineering | | | PENDING |
