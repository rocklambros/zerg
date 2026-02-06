# Requirements: test-suite-reduction-phase45

**Status: APPROVED**
**Created**: 2026-02-06
**Feature**: Test Suite Reduction — Phases 4-5
**Parent Issue**: #156

## Problem Statement

After PRs #155, #157, #158 completed Phases 1-3, the suite stands at 5,608 tests with ~87% coverage. Target from #156: ~3,000 tests at 75-80% coverage. This PR tackles Phases 4 (module consolidation) and 5 (secondary thinning).

**Current**: 5,608 tests | ~160 unit test files | ~87% coverage | ~3.5min CI
**After this PR**: ~3,700 tests | ~142 unit test files | ~80% coverage | ~2.5min CI

## Scope: Phases 4+5 from #156

### Phase 4: Module Consolidation (~740 tests → ~280)

#### 4A: State Module (8→5 files, 247→82 tests)
- DELETE: test_state_sync.py (16), test_state_sync_service.py (7), test_state_workers.py (16) — merge 5-8 essential tests into test_state.py
- THIN: test_state.py 78→35, test_state_levels.py 38→15, test_state_persistence.py 26→10, test_state_reconciler.py 36→12, test_state_tasks.py 30→10

#### 4B: Merge + Orchestrator (11→2 files, 276→60 tests)
- DELETE merge: test_merge_full_flow.py (26), test_merge_gates.py (27), test_merge_execute.py (20), test_merge_coordinator_init.py (11)
- DELETE orchestrator: test_orchestrator_workers.py (24), test_orchestrator_recovery.py (24), test_orchestrator_merge.py (16), test_orchestrator_levels.py (15), test_orchestrator_container_mode.py (14)
- THIN: test_merge_flow.py 39→20, test_orchestrator.py 60→40

#### 4C: Diagnostics (11→5 files, 224→59 tests)
- DELETE: test_diagnostics/test_types.py (20), test_diagnostics/test_knowledge_base.py (12), test_diagnostics/test_log_correlator.py (21), test_diagnostics/test_env_diagnostics.py (14), test_diagnostics/test_system_diagnostics.py (17), test_diagnostics/test_code_fixer.py (15)
- THIN: test_error_intel.py 27→12, test_hypothesis_engine.py 27→12, test_log_analyzer.py 18→10, test_recovery.py 32→15, test_state_introspector.py 21→10

### Phase 5: Secondary Module Thinning (~1,130 tests → ~400)

#### 5A: Worker + Resilience (10 files, 407→165 tests)
- THIN: test_worker_commit.py 19→10, test_worker_lifecycle.py 28→12, test_worker_main.py 40→20, test_worker_manager_component.py 14→8, test_worker_metrics.py 55→20, test_worker_protocol.py 67→25, test_worker_registry.py 48→20
- THIN: test_resilience_config.py 65→20, test_circuit_breaker.py 34→15, test_backpressure.py 37→15

#### 5B: Git + Validation (12 files, 417→167 tests)
- THIN: test_validation.py 109→25
- THIN: test_git_base.py 15→10, test_git_bisect_engine.py 35→15, test_git_commit_engine.py 32→15, test_git_config.py 20→10, test_git_history_engine.py 31→15, test_git_ops.py 55→20, test_git_pr_engine.py 26→12, test_git_prereview.py 20→10, test_git_release_engine.py 31→15, test_git_rescue.py 31→12, test_git_types.py 12→8

#### 5C: Launcher + Cross-cutting (5 files, 406→150 tests)
- THIN: test_launcher.py 131→50, test_launcher_container_ops.py 103→40
- THIN: test_tdd.py 59→20, test_modes.py 71→25, test_efficiency.py 42→15
- KEEP: test_launcher_configurator.py (11, already minimal)

#### 5D: Performance + Security + Token (7 files, 196→84 tests)
- THIN: test_performance_adapters.py 42→15, test_performance_formatters.py 14→8, test_performance_types.py 14→8
- THIN: test_security.py 41→15, test_security_rules.py 39→15
- THIN: test_context_tracker.py 35→15, test_token_counter.py 11→8
- KEEP as-is: perf_aggregator (5), perf_catalog (7), perf_registry (7), perf_stack (6), security_path_traversal (11), token_aggregator (10), token_counter_memory (8), token_tracker (10), context_plugin (11)

#### 5E: Misc Infrastructure (6 files, 354→135 tests)
- THIN: test_mcp_router.py 73→25, test_containers.py 70→25, test_depth_tiers.py 55→20, test_worktree.py 53→20, test_config.py 53→25, test_step_generator.py 50→20

#### 5F: Misc Build/Hooks (7 files, 303→145 tests)
- THIN: test_dedup_unified.py 46→20, test_validate_commands.py 45→25, test_metrics.py 45→20, test_install_commands.py 44→20, test_verification_gates.py 41→20, test_hooks.py 41→20, test_command_executor.py 41→20

#### 5G: Misc Analysis/Cmd 2nd Pass (7 files, 294→145 tests)
- THIN: test_debug_cmd.py 57→25, test_build_cmd.py 49→25, test_container_resources.py 38→15, test_analyze_new_checks.py 38→20, test_adaptive_detail.py 38→20, test_loops.py 37→20, test_assign.py 37→20

## Thinning Rules (same as Phase 2)

1. Keep 1 happy-path + 1 error-path test per class
2. Collapse enum tests to 1 parametrized test
3. Parametrize where 3+ tests differ only by input
4. Remove arg permutation tests (keep boundary + typical)
5. Preserve ALL @pytest.mark.smoke tests
6. Remove duplicate assertions on same code path

## Non-Functional Requirements

- Coverage stays >= 75% overall
- No production code changes
- CI must continue passing (smoke + test shards)
- No security-related tests removed unless redundant
- validate_commands must pass
- test_diagnostics/test_types.py (DELETE) is NOT test_types.py (KEEP)

## Acceptance Criteria

- Each thinned file within ±5 of target count
- All deleted files confirmed absent
- Full test suite passes
- Smoke tests pass
- CHANGELOG updated
- .test_durations regenerated
- Total test count in range 3,500-3,800

## Estimated Reduction

| Phase | Tests Removed | Files Deleted |
|-------|-------------:|-------------:|
| Phase 4 | ~460 | 18 |
| Phase 5 | ~1,470 | 0 (65 thinned) |
| **Total** | **~1,930** | **18 deleted** |

## Dependencies

No new dependencies. Existing infrastructure sufficient.

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Coverage drops below 75% | Low | Medium | Monitor after each level |
| Unique assertions lost | Medium | Medium | Read each file fully before thinning |
| State merge introduces failures | Low | High | Merge essential tests first, run pytest, then thin |
