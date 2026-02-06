# Technical Design: test-suite-reduction-phase45

## Metadata
- **Feature**: test-suite-reduction-phase45
- **Status**: DRAFT
- **Created**: 2026-02-06
- **Author**: Factory Design Mode

---

## 1. Overview

### 1.1 Summary
Systematic reduction of the ZERG test suite from ~5,608 tests to ~3,700 tests through module consolidation (Phase 4: delete 18 files, thin 12 files) and secondary thinning (Phase 5: thin 53 files). No production code changes. All work is test file deletion and thinning using established rules from Phase 2.

### 1.2 Goals
- Reduce test count to 3,500–3,800 range
- Delete 18 redundant test files
- Thin 65 test files to target counts
- Maintain ≥75% coverage
- CI continues passing

### 1.3 Non-Goals
- Production code changes
- New test infrastructure
- Coverage tool changes
- Test framework migration

---

## 2. Architecture

### 2.1 High-Level Design

```
Phase 4: Module Consolidation          Phase 5: Secondary Thinning
┌──────────────────────────┐           ┌──────────────────────────┐
│ L1: Delete 18 files      │           │ L3: Thin 53 files        │
│  ├─ 4A: state (3 files)  │           │  ├─ 5A: worker (10)     │
│  ├─ 4B: merge+orch (9)   │           │  ├─ 5B: git+val (12)   │
│  └─ 4C: diagnostics (6)  │           │  ├─ 5C: launcher (5)   │
└──────────┬───────────────┘           │  ├─ 5D: perf+sec (7)   │
           │                           │  ├─ 5E: infra (6)      │
           ▼                           │  ├─ 5F: build/hooks (7) │
┌──────────────────────────┐           │  └─ 5G: analysis (7)   │
│ L2: Thin 12 files        │           └──────────┬───────────────┘
│  ├─ 4A: state thin (5)   │                      │
│  ├─ 4B: merge thin (2)   │                      │
│  └─ 4C: diag thin (5)    │                      ▼
└──────────┬───────────────┘           ┌──────────────────────────┐
           │                           │ L4: Quality Gate         │
           └───────────────────────────│  Full suite, smoke,     │
                                       │  validate_commands,     │
                                       │  CHANGELOG, durations   │
                                       └──────────────────────────┘
```

### 2.2 Component Breakdown

| Component | Responsibility | Files Affected |
|-----------|---------------|----------------|
| Phase 4A (State) | Delete 3 state test files, thin 5 | 8 test files |
| Phase 4B (Merge+Orch) | Delete 9 merge/orchestrator test files, thin 2 | 11 test files |
| Phase 4C (Diagnostics) | Delete 6 diagnostics test files, thin 5 | 11 test files |
| Phase 5A (Worker+Resilience) | Thin 10 worker/resilience files | 10 test files |
| Phase 5B (Git+Validation) | Thin 12 git/validation files | 12 test files |
| Phase 5C (Launcher+Cross-cutting) | Thin 5 launcher/cross-cutting files | 5 test files |
| Phase 5D (Perf+Security+Token) | Thin 7 performance/security/token files | 7 test files |
| Phase 5E (Misc Infrastructure) | Thin 6 infrastructure files | 6 test files |
| Phase 5F (Misc Build/Hooks) | Thin 7 build/hooks files | 7 test files |
| Phase 5G (Misc Analysis/Cmd) | Thin 7 analysis/cmd files | 7 test files |

### 2.3 Data Flow
Not applicable — this is test file reduction, not a feature.

---

## 3. Detailed Design

### 3.1 Thinning Rules (from requirements)

1. Keep 1 happy-path + 1 error-path test per class
2. Collapse enum tests to 1 parametrized test
3. Parametrize where 3+ tests differ only by input
4. Remove arg permutation tests (keep boundary + typical)
5. Preserve ALL @pytest.mark.smoke tests
6. Remove duplicate assertions on same code path

### 3.2 State Merge Rules (Phase 4A special)

For deleted state files, merge 5-8 essential tests into test_state.py before deletion:
- test_state_sync.py → merge essential sync tests into test_state.py
- test_state_sync_service.py → merge essential service tests into test_state.py
- test_state_workers.py → merge essential worker state tests into test_state.py

### 3.3 Important Disambiguation

- `test_diagnostics/test_types.py` (DELETE) is NOT `test_types.py` (KEEP)
- test_launcher_configurator.py (11 tests) — KEEP as-is, already minimal

---

## 4. Key Decisions

### 4.1 Level Structure: 4 levels not 5

**Context**: Could organize as 5 levels (one per phase sub-step) or consolidate.

**Options Considered**:
1. 5 levels (delete, thin-4, thin-5-first, thin-5-second, quality) — more granular but slower
2. 4 levels (delete, thin-4, thin-5, quality) — optimal parallelism
3. 3 levels (all-delete-and-thin, quality) — risky, deletion should precede thinning of same module

**Decision**: 4 levels

**Rationale**: Level 1 deletions must complete before Level 2 thinning within Phase 4 (e.g., state merge requires deleted files absorbed first). Phase 5 thinning is independent of Phase 4 thinning so could theoretically run at Level 2, but keeping it at Level 3 ensures Phase 4 is fully verified first. 7 workers at Level 3 maximizes parallelism.

### 4.2 Phase 4A State Merge Strategy

**Context**: 3 state files are being deleted, but essential tests need preservation.

**Decision**: Level 1 task for 4A handles both: read deleted files, merge 5-8 essential tests into test_state.py, then delete source files. The Level 2 thin of test_state.py is aware the file was modified at Level 1.

### 4.3 Maximum Workers: 7

**Context**: Level 3 has 7 independent sub-phases (5A-5G).

**Decision**: Recommend 7 workers for maximum parallelism at Level 3.

---

## 5. Implementation Plan

### 5.1 Phase Summary

| Phase | Level | Tasks | Parallel | Est. Time |
|-------|-------|-------|----------|-----------|
| Deletion (4A/4B/4C) | 1 | 3 | Yes | 5 min |
| Thin Phase 4 (4A/4B/4C) | 2 | 3 | Yes | 12 min |
| Thin Phase 5 (5A-5G) | 3 | 7 | Yes | 20 min |
| Quality Gate | 4 | 1 | No | 10 min |

### 5.2 File Ownership

#### Level 1 — Deletions + Merges

| File | Task ID | Operation |
|------|---------|-----------|
| tests/unit/test_state_sync.py | TSR45-L1-001 | delete (merge essential→test_state.py) |
| tests/unit/test_state_sync_service.py | TSR45-L1-001 | delete (merge essential→test_state.py) |
| tests/unit/test_state_workers.py | TSR45-L1-001 | delete (merge essential→test_state.py) |
| tests/unit/test_state.py | TSR45-L1-001 | modify (receive merged tests) |
| tests/unit/test_merge_full_flow.py | TSR45-L1-002 | delete |
| tests/unit/test_merge_gates.py | TSR45-L1-002 | delete |
| tests/unit/test_merge_execute.py | TSR45-L1-002 | delete |
| tests/unit/test_merge_coordinator_init.py | TSR45-L1-002 | delete |
| tests/unit/test_orchestrator_workers.py | TSR45-L1-002 | delete |
| tests/unit/test_orchestrator_recovery.py | TSR45-L1-002 | delete |
| tests/unit/test_orchestrator_merge.py | TSR45-L1-002 | delete |
| tests/unit/test_orchestrator_levels.py | TSR45-L1-002 | delete |
| tests/unit/test_orchestrator_container_mode.py | TSR45-L1-002 | delete |
| tests/unit/test_diagnostics/test_types.py | TSR45-L1-003 | delete |
| tests/unit/test_diagnostics/test_knowledge_base.py | TSR45-L1-003 | delete |
| tests/unit/test_diagnostics/test_log_correlator.py | TSR45-L1-003 | delete |
| tests/unit/test_diagnostics/test_env_diagnostics.py | TSR45-L1-003 | delete |
| tests/unit/test_diagnostics/test_system_diagnostics.py | TSR45-L1-003 | delete |
| tests/unit/test_diagnostics/test_code_fixer.py | TSR45-L1-003 | delete |

#### Level 2 — Phase 4 Thinning

| File | Task ID | Operation |
|------|---------|-----------|
| tests/unit/test_state.py | TSR45-L2-001 | thin 78→35 |
| tests/unit/test_state_levels.py | TSR45-L2-001 | thin 38→15 |
| tests/unit/test_state_persistence.py | TSR45-L2-001 | thin 26→10 |
| tests/unit/test_state_reconciler.py | TSR45-L2-001 | thin 36→12 |
| tests/unit/test_state_tasks.py | TSR45-L2-001 | thin 30→10 |
| tests/unit/test_merge_flow.py | TSR45-L2-002 | thin 39→20 |
| tests/unit/test_orchestrator.py | TSR45-L2-002 | thin 60→40 |
| tests/unit/test_diagnostics/test_error_intel.py | TSR45-L2-003 | thin 27→12 |
| tests/unit/test_diagnostics/test_hypothesis_engine.py | TSR45-L2-003 | thin 27→12 |
| tests/unit/test_diagnostics/test_log_analyzer.py | TSR45-L2-003 | thin 18→10 |
| tests/unit/test_diagnostics/test_recovery.py | TSR45-L2-003 | thin 32→15 |
| tests/unit/test_diagnostics/test_state_introspector.py | TSR45-L2-003 | thin 21→10 |

#### Level 3 — Phase 5 Thinning

| File | Task ID | Operation |
|------|---------|-----------|
| tests/unit/test_worker_commit.py | TSR45-L3-001 | thin 19→10 |
| tests/unit/test_worker_lifecycle.py | TSR45-L3-001 | thin 28→12 |
| tests/unit/test_worker_main.py | TSR45-L3-001 | thin 40→20 |
| tests/unit/test_worker_manager_component.py | TSR45-L3-001 | thin 14→8 |
| tests/unit/test_worker_metrics.py | TSR45-L3-001 | thin 55→20 |
| tests/unit/test_worker_protocol.py | TSR45-L3-001 | thin 67→25 |
| tests/unit/test_worker_registry.py | TSR45-L3-001 | thin 48→20 |
| tests/unit/test_resilience_config.py | TSR45-L3-001 | thin 65→20 |
| tests/unit/test_circuit_breaker.py | TSR45-L3-001 | thin 34→15 |
| tests/unit/test_backpressure.py | TSR45-L3-001 | thin 37→15 |
| tests/unit/test_validation.py | TSR45-L3-002 | thin 109→25 |
| tests/unit/test_git_base.py | TSR45-L3-002 | thin 15→10 |
| tests/unit/test_git_bisect_engine.py | TSR45-L3-002 | thin 35→15 |
| tests/unit/test_git_commit_engine.py | TSR45-L3-002 | thin 32→15 |
| tests/unit/test_git_config.py | TSR45-L3-002 | thin 20→10 |
| tests/unit/test_git_history_engine.py | TSR45-L3-002 | thin 31→15 |
| tests/unit/test_git_ops.py | TSR45-L3-002 | thin 55→20 |
| tests/unit/test_git_pr_engine.py | TSR45-L3-002 | thin 26→12 |
| tests/unit/test_git_prereview.py | TSR45-L3-002 | thin 20→10 |
| tests/unit/test_git_release_engine.py | TSR45-L3-002 | thin 31→15 |
| tests/unit/test_git_rescue.py | TSR45-L3-002 | thin 31→12 |
| tests/unit/test_git_types.py | TSR45-L3-002 | thin 12→8 |
| tests/unit/test_launcher.py | TSR45-L3-003 | thin 131→50 |
| tests/unit/test_launcher_container_ops.py | TSR45-L3-003 | thin 103→40 |
| tests/unit/test_tdd.py | TSR45-L3-003 | thin 59→20 |
| tests/unit/test_modes.py | TSR45-L3-003 | thin 71→25 |
| tests/unit/test_efficiency.py | TSR45-L3-003 | thin 42→15 |
| tests/unit/test_performance_adapters.py | TSR45-L3-004 | thin 42→15 |
| tests/unit/test_performance_formatters.py | TSR45-L3-004 | thin 14→8 |
| tests/unit/test_performance_types.py | TSR45-L3-004 | thin 14→8 |
| tests/unit/test_security.py | TSR45-L3-004 | thin 41→15 |
| tests/unit/test_security_rules.py | TSR45-L3-004 | thin 39→15 |
| tests/unit/test_context_tracker.py | TSR45-L3-004 | thin 35→15 |
| tests/unit/test_token_counter.py | TSR45-L3-004 | thin 11→8 |
| tests/unit/test_mcp_router.py | TSR45-L3-005 | thin 73→25 |
| tests/unit/test_containers.py | TSR45-L3-005 | thin 70→25 |
| tests/unit/test_depth_tiers.py | TSR45-L3-005 | thin 55→20 |
| tests/unit/test_worktree.py | TSR45-L3-005 | thin 53→20 |
| tests/unit/test_config.py | TSR45-L3-005 | thin 53→25 |
| tests/unit/test_step_generator.py | TSR45-L3-005 | thin 50→20 |
| tests/unit/test_dedup_unified.py | TSR45-L3-006 | thin 46→20 |
| tests/unit/test_validate_commands.py | TSR45-L3-006 | thin 45→25 |
| tests/unit/test_metrics.py | TSR45-L3-006 | thin 45→20 |
| tests/unit/test_install_commands.py | TSR45-L3-006 | thin 44→20 |
| tests/unit/test_verification_gates.py | TSR45-L3-006 | thin 41→20 |
| tests/unit/test_hooks.py | TSR45-L3-006 | thin 41→20 |
| tests/unit/test_command_executor.py | TSR45-L3-006 | thin 41→20 |
| tests/unit/test_debug_cmd.py | TSR45-L3-007 | thin 57→25 |
| tests/unit/test_build_cmd.py | TSR45-L3-007 | thin 49→25 |
| tests/unit/test_container_resources.py | TSR45-L3-007 | thin 38→15 |
| tests/unit/test_analyze_new_checks.py | TSR45-L3-007 | thin 38→20 |
| tests/unit/test_adaptive_detail.py | TSR45-L3-007 | thin 38→20 |
| tests/unit/test_loops.py | TSR45-L3-007 | thin 37→20 |
| tests/unit/test_assign.py | TSR45-L3-007 | thin 37→20 |

#### Level 4 — Quality

| File | Task ID | Operation |
|------|---------|-----------|
| CHANGELOG.md | TSR45-L4-001 | modify |
| .test_durations | TSR45-L4-001 | modify |

### 5.3 Dependency Graph

```
Level 1 (parallel):
  TSR45-L1-001 (4A delete+merge) ──┐
  TSR45-L1-002 (4B delete)     ────┤
  TSR45-L1-003 (4C delete)     ────┤
                                    │
Level 2 (parallel):                 ▼
  TSR45-L2-001 (4A thin) ─────────┐
  TSR45-L2-002 (4B thin)  ────────┤
  TSR45-L2-003 (4C thin)  ────────┤
                                    │
Level 3 (parallel, 7 workers):     ▼
  TSR45-L3-001 (5A worker)  ──────┐
  TSR45-L3-002 (5B git)     ──────┤
  TSR45-L3-003 (5C launcher) ─────┤
  TSR45-L3-004 (5D perf/sec) ─────┤
  TSR45-L3-005 (5E infra)   ──────┤
  TSR45-L3-006 (5F build)   ──────┤
  TSR45-L3-007 (5G analysis) ─────┤
                                    │
Level 4 (sequential):              ▼
  TSR45-L4-001 (quality gate) ─────✓
```

---

## 6. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Coverage drops below 75% | Low | Medium | Monitor after each level; thin conservatively |
| Unique assertions lost | Medium | Medium | Read each file fully before thinning |
| State merge introduces failures | Low | High | Merge essential tests first, run pytest, then delete |
| test_diagnostics/test_types.py confused with test_types.py | Low | High | Explicit path in task context; disambiguation warning |
| Worker count bottleneck at L3 | Low | Low | 7 parallel tasks; can split further if needed |

---

## 7. Testing Strategy

### 7.1 Per-Task Verification
Each task runs pytest on its modified files immediately after thinning.

### 7.2 Level Gate
After each level completes, spot-check a sample of modified files.

### 7.3 Final Verification (Level 4)
- Full test suite: `python -m pytest tests/ --ignore=tests/e2e --ignore=tests/pressure -m 'not slow' --timeout=120`
- Smoke tests: `python -m pytest -m smoke -x --timeout=5`
- Validation: `python -m zerg.validate_commands`
- Test count verification: must be in 3,500–3,800 range

---

## 8. Parallel Execution Notes

### 8.1 Safe Parallelization
- Level 1: 3 tasks, zero file overlap (each handles different module)
- Level 2: 3 tasks, zero file overlap (state vs merge vs diagnostics)
- Level 3: 7 tasks, zero file overlap (each sub-phase owns distinct files)
- No two tasks at any level modify the same file

### 8.2 Recommended Workers
- Minimum: 1 worker (sequential by level)
- Optimal: 7 workers (matches Level 3 width)
- Maximum: 7 workers (Level 3 is widest; more workers idle)

### 8.3 Estimated Duration
- Single worker: ~85 min (5 + 12 + 20×7/1 + 10)
- With 3 workers: ~47 min
- With 7 workers: ~47 min (L1: 5, L2: 12, L3: 20, L4: 10)
- Speedup with 7 workers: ~1.8x vs 3 workers, ~4.3x vs 1 worker

### 8.4 Consumer Matrix

All tasks in this feature are leaf tasks (test file modifications). No task creates modules consumed by other tasks. Consumer field is empty for all tasks. Integration tests are not applicable since no production code is created.

---

## 9. Approval

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Architecture | | | PENDING |
| Engineering | | | PENDING |
