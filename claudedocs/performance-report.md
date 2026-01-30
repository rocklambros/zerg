# Performance Analysis Report

**Overall Score**: 86/100 | **Factors Checked**: 97/103

## Tool Availability
| Tool | Status | Version |
|------|--------|---------|
| semgrep | Available | 1.150.0 |
| radon | Available | 6.0.1 |
| lizard | Available | 1.20.0 |
| vulture | Available | vulture 2.14 |
| jscpd | Available | 4.0.8 |
| deptry | Available | deptry 0.24.0 |
| pipdeptree | Available | 2.30.0 |
| dive | Available | dive 0.13.1 |
| hadolint | Available | Haskell Dockerfile Linter 2.14.0 |
| trivy | Available | Version: 0.69.0 |
| cloc | Available | 2.08 |

## Code-Level Patterns (Score: 0/100)
| Severity | File | Line | Message |
|----------|------|------|---------|
| HIGH | _plugin_task_graph@12-369@./tests/e2e/test_dogfood_plugin.py | - | Function './tests/e2e/test_dogfood_plugin.py' has 343 lines of code |
| HIGH | debug@997-1418@./zerg/commands/debug.py | - | Function './zerg/commands/debug.py' has 334 lines of code |
| HIGH | generate_backlog_markdown@193-447@./zerg/backlog.py | - | Function './zerg/backlog.py' has 205 lines of code |
| HIGH | tests/e2e/test_container_e2e.py | 143 | Unused variable 'container_e2e_setup' (100% confidence) |
| HIGH | tests/e2e/test_container_e2e.py | 155 | Unused variable 'container_e2e_setup' (100% confidence) |
| HIGH | tests/e2e/test_container_e2e.py | 187 | Unused variable 'container_e2e_setup' (100% confidence) |
| HIGH | tests/e2e/test_container_e2e.py | 202 | Unused variable 'container_e2e_setup' (100% confidence) |
| HIGH | tests/e2e/test_container_e2e.py | 213 | Unused variable 'container_e2e_setup' (100% confidence) |
| HIGH | tests/e2e/test_container_e2e.py | 224 | Unused variable 'container_e2e_setup' (100% confidence) |
| HIGH | tests/e2e/test_container_e2e.py | 243 | Unused variable 'container_e2e_setup' (100% confidence) |
| HIGH | tests/e2e/test_container_e2e.py | 258 | Unused variable 'container_e2e_setup' (100% confidence) |
| HIGH | tests/e2e/test_failure_recovery.py | 113 | Unused variable 'recovery_setup' (100% confidence) |
| HIGH | tests/e2e/test_failure_recovery.py | 127 | Unused variable 'recovery_setup' (100% confidence) |
| HIGH | tests/e2e/test_failure_recovery.py | 146 | Unused variable 'recovery_setup' (100% confidence) |
| HIGH | tests/e2e/test_failure_recovery.py | 159 | Unused variable 'recovery_setup' (100% confidence) |
| HIGH | tests/e2e/test_failure_recovery.py | 173 | Unused variable 'recovery_setup' (100% confidence) |
| HIGH | tests/e2e/test_failure_recovery.py | 190 | Unused variable 'recovery_setup' (100% confidence) |
| HIGH | tests/e2e/test_failure_recovery.py | 206 | Unused variable 'recovery_setup' (100% confidence) |
| HIGH | tests/e2e/test_failure_recovery.py | 215 | Unused variable 'recovery_setup' (100% confidence) |
| HIGH | tests/e2e/test_failure_recovery.py | 230 | Unused variable 'recovery_setup' (100% confidence) |
| HIGH | tests/e2e/test_failure_recovery.py | 243 | Unused variable 'recovery_setup' (100% confidence) |
| HIGH | tests/e2e/test_failure_recovery.py | 260 | Unused variable 'recovery_setup' (100% confidence) |
| HIGH | tests/e2e/test_failure_recovery.py | 280 | Unused variable 'recovery_setup' (100% confidence) |
| HIGH | tests/e2e/test_failure_recovery.py | 301 | Unused variable 'recovery_setup' (100% confidence) |
| HIGH | tests/e2e/test_failure_recovery.py | 318 | Unused variable 'recovery_setup' (100% confidence) |
| HIGH | tests/e2e/test_failure_recovery.py | 331 | Unused variable 'recovery_setup' (100% confidence) |
| HIGH | tests/e2e/test_subprocess_e2e.py | 110 | Unused variable 'e2e_orchestrator' (100% confidence) |
| HIGH | tests/e2e/test_subprocess_e2e.py | 121 | Unused variable 'e2e_orchestrator' (100% confidence) |
| HIGH | tests/e2e/test_subprocess_e2e.py | 138 | Unused variable 'e2e_orchestrator' (100% confidence) |
| HIGH | tests/e2e/test_subprocess_e2e.py | 152 | Unused variable 'e2e_orchestrator' (100% confidence) |
| HIGH | tests/e2e/test_subprocess_e2e.py | 167 | Unused variable 'e2e_orchestrator' (100% confidence) |
| HIGH | tests/e2e/test_subprocess_e2e.py | 189 | Unused variable 'e2e_orchestrator' (100% confidence) |
| HIGH | tests/e2e/test_subprocess_e2e.py | 198 | Unused variable 'e2e_orchestrator' (100% confidence) |
| HIGH | tests/e2e/test_subprocess_e2e.py | 214 | Unused variable 'e2e_orchestrator' (100% confidence) |
| HIGH | tests/e2e/test_subprocess_e2e.py | 232 | Unused variable 'e2e_orchestrator' (100% confidence) |
| HIGH | tests/e2e/test_subprocess_e2e.py | 243 | Unused variable 'e2e_orchestrator' (100% confidence) |
| HIGH | tests/helpers/async_helpers.py | 286 | Unused variable 'input' (100% confidence) |
| HIGH | tests/integration/test_container_orchestrator.py | 27 | Unused variable 'mock_sync' (100% confidence) |
| HIGH | tests/integration/test_container_orchestrator.py | 32 | Unused variable 'mock_containers' (100% confidence) |
| HIGH | tests/integration/test_container_orchestrator.py | 33 | Unused variable 'mock_worktrees' (100% confidence) |
| HIGH | tests/integration/test_container_orchestrator.py | 70 | Unused variable 'mock_sync' (100% confidence) |
| HIGH | tests/integration/test_container_orchestrator.py | 75 | Unused variable 'mock_containers' (100% confidence) |
| HIGH | tests/integration/test_container_orchestrator.py | 76 | Unused variable 'mock_worktrees' (100% confidence) |
| HIGH | tests/unit/test_merge_cmd.py | 132 | Unused variable 'feature_state_file' (100% confidence) |
| HIGH | tests/unit/test_merge_cmd.py | 357 | Unused variable 'feature_state_file' (100% confidence) |
| HIGH | tests/unit/test_merge_cmd.py | 370 | Unused variable 'feature_state_file' (100% confidence) |
| HIGH | tests/unit/test_merge_cmd.py | 387 | Unused variable 'feature_state_file' (100% confidence) |
| HIGH | tests/unit/test_merge_cmd.py | 404 | Unused variable 'feature_state_file' (100% confidence) |
| HIGH | tests/unit/test_merge_cmd.py | 435 | Unused variable 'feature_state_file' (100% confidence) |
| HIGH | tests/unit/test_merge_cmd.py | 469 | Unused variable 'feature_state_file' (100% confidence) |
| HIGH | tests/unit/test_merge_cmd.py | 506 | Unused variable 'feature_state_file' (100% confidence) |
| HIGH | tests/unit/test_merge_cmd.py | 535 | Unused variable 'feature_state_file' (100% confidence) |
| HIGH | tests/unit/test_merge_cmd.py | 566 | Unused variable 'feature_state_file' (100% confidence) |
| HIGH | tests/unit/test_merge_cmd.py | 598 | Unused variable 'feature_state_file' (100% confidence) |
| HIGH | tests/unit/test_merge_cmd.py | 631 | Unused variable 'feature_state_file' (100% confidence) |
| HIGH | tests/unit/test_merge_cmd.py | 651 | Unused variable 'feature_state_file' (100% confidence) |
| HIGH | tests/unit/test_merge_cmd.py | 677 | Unused variable 'feature_state_file' (100% confidence) |
| HIGH | tests/unit/test_merge_cmd.py | 709 | Unused variable 'feature_state_file' (100% confidence) |
| HIGH | tests/unit/test_merge_cmd.py | 744 | Unused variable 'feature_state_file' (100% confidence) |
| HIGH | tests/unit/test_merge_cmd.py | 758 | Unused variable 'feature_state_file' (100% confidence) |
| HIGH | tests/unit/test_merge_cmd.py | 795 | Unused variable 'feature_state_file' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 29 | Unused variable 'mock_task_sync' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 30 | Unused variable 'mock_merge_coordinator' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 31 | Unused variable 'mock_port_allocator' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 32 | Unused variable 'mock_container_manager' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 33 | Unused variable 'mock_worktree_manager' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 35 | Unused variable 'mock_task_parser' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 36 | Unused variable 'mock_level_controller' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 78 | Unused variable 'mock_task_sync' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 79 | Unused variable 'mock_merge_coordinator' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 80 | Unused variable 'mock_port_allocator' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 81 | Unused variable 'mock_container_manager' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 82 | Unused variable 'mock_worktree_manager' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 84 | Unused variable 'mock_task_parser' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 85 | Unused variable 'mock_level_controller' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 126 | Unused variable 'mock_task_sync' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 127 | Unused variable 'mock_merge_coordinator' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 128 | Unused variable 'mock_port_allocator' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 129 | Unused variable 'mock_container_manager' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 130 | Unused variable 'mock_worktree_manager' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 132 | Unused variable 'mock_task_parser' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 133 | Unused variable 'mock_level_controller' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 170 | Unused variable 'mock_task_sync' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 171 | Unused variable 'mock_merge_coordinator' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 172 | Unused variable 'mock_port_allocator' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 173 | Unused variable 'mock_container_manager' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 174 | Unused variable 'mock_worktree_manager' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 176 | Unused variable 'mock_task_parser' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 177 | Unused variable 'mock_level_controller' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 210 | Unused variable 'mock_task_sync' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 211 | Unused variable 'mock_merge_coordinator' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 212 | Unused variable 'mock_port_allocator' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 213 | Unused variable 'mock_container_manager' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 214 | Unused variable 'mock_worktree_manager' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 216 | Unused variable 'mock_task_parser' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 217 | Unused variable 'mock_level_controller' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 254 | Unused variable 'mock_task_sync' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 255 | Unused variable 'mock_merge_coordinator' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 256 | Unused variable 'mock_port_allocator' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 257 | Unused variable 'mock_container_manager' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 258 | Unused variable 'mock_worktree_manager' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 260 | Unused variable 'mock_task_parser' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 261 | Unused variable 'mock_level_controller' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 302 | Unused variable 'mock_task_sync' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 303 | Unused variable 'mock_merge_coordinator' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 304 | Unused variable 'mock_port_allocator' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 305 | Unused variable 'mock_container_manager' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 306 | Unused variable 'mock_worktree_manager' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 308 | Unused variable 'mock_task_parser' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 309 | Unused variable 'mock_level_controller' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 350 | Unused variable 'mock_task_sync' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 351 | Unused variable 'mock_merge_coordinator' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 352 | Unused variable 'mock_port_allocator' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 353 | Unused variable 'mock_container_manager' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 354 | Unused variable 'mock_worktree_manager' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 356 | Unused variable 'mock_task_parser' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 357 | Unused variable 'mock_level_controller' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 399 | Unused variable 'mock_task_sync' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 400 | Unused variable 'mock_merge_coordinator' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 401 | Unused variable 'mock_port_allocator' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 402 | Unused variable 'mock_container_manager' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 403 | Unused variable 'mock_worktree_manager' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 405 | Unused variable 'mock_task_parser' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 406 | Unused variable 'mock_level_controller' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 443 | Unused variable 'mock_task_sync' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 444 | Unused variable 'mock_merge_coordinator' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 445 | Unused variable 'mock_port_allocator' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 446 | Unused variable 'mock_container_manager' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 447 | Unused variable 'mock_worktree_manager' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 449 | Unused variable 'mock_task_parser' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 450 | Unused variable 'mock_level_controller' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 483 | Unused variable 'mock_task_sync' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 484 | Unused variable 'mock_merge_coordinator' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 485 | Unused variable 'mock_port_allocator' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 486 | Unused variable 'mock_container_manager' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 487 | Unused variable 'mock_worktree_manager' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 489 | Unused variable 'mock_task_parser' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 490 | Unused variable 'mock_level_controller' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 522 | Unused variable 'mock_auto_detect' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 525 | Unused variable 'mock_task_sync' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 526 | Unused variable 'mock_merge_coordinator' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 527 | Unused variable 'mock_port_allocator' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 528 | Unused variable 'mock_container_manager' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 529 | Unused variable 'mock_worktree_manager' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 531 | Unused variable 'mock_task_parser' (100% confidence) |
| HIGH | tests/unit/test_orchestrator_container_mode.py | 532 | Unused variable 'mock_level_controller' (100% confidence) |
| HIGH | zerg/commands/design.py | 355 | Unused variable 'min_minutes' (100% confidence) |
| MEDIUM | mock_orchestrator_deps@28-146@./tests/unit/test_orchestrator.py | - | Function './tests/unit/test_orchestrator.py' has 104 lines of code |
| MEDIUM | mock_orchestrator_deps@23-143@./tests/unit/test_orchestrator_recovery.py | - | Function './tests/unit/test_orchestrator_recovery.py' has 106 lines of code |
| MEDIUM | mock_orchestrator_deps@79-231@./tests/fixtures/orchestrator_fixtures.py | - | Function './tests/fixtures/orchestrator_fixtures.py' has 120 lines of code |
| MEDIUM | test_cmd@517-664@./zerg/commands/test_cmd.py | - | Function './zerg/commands/test_cmd.py' has 101 lines of code |
| MEDIUM | design@27-177@./zerg/commands/design.py | - | Function './zerg/commands/design.py' has 103 lines of code |
| MEDIUM | create_task_graph_template@351-528@./zerg/commands/design.py | - | Function './zerg/commands/design.py' has 165 lines of code |
| MEDIUM | run@400-546@./zerg/commands/debug.py | - | Function './zerg/commands/debug.py' has 103 lines of code |
| MEDIUM | format_result@679-874@./zerg/commands/debug.py | - | Function './zerg/commands/debug.py' has 170 lines of code |
| MEDIUM | handle_level_complete@163-304@./zerg/level_coordinator.py | - | Function './zerg/level_coordinator.py' has 108 lines of code |
| MEDIUM | __init__@74-213@./zerg/orchestrator.py | - | Function './zerg/orchestrator.py' has 114 lines of code |
| MEDIUM | tests/integration/test_orchestrator_fixes.py | 10 | Unused import 'PropertyMock' (90% confidence) |
| MEDIUM | tests/unit/test_build_cmd.py | 8 | Unused import 'PropertyMock' (90% confidence) |
| MEDIUM | tests/unit/test_log_aggregator.py | 8 | Unused import 'LogQuery' (90% confidence) |
| MEDIUM | tests/unit/test_orchestrator_timeout.py | 16 | Unused import 'PropertyMock' (90% confidence) |
| MEDIUM | tests/unit/test_state_sync.py | 9 | Unused import 'PropertyMock' (90% confidence) |
| MEDIUM | tests/unit/test_worker_protocol.py | 12 | Unused import 'PropertyMock' (90% confidence) |
| MEDIUM | tests/test_types.py | - | File has maintainability index 7.0 (rank C) |
| MEDIUM | tests/unit/test_design_cmd.py | - | File has maintainability index 8.6 (rank C) |
| MEDIUM | tests/unit/test_validation.py | - | File has maintainability index 0.0 (rank C) |
| MEDIUM | tests/unit/test_debug_cmd.py | - | File has maintainability index 0.0 (rank C) |
| MEDIUM | tests/unit/test_test_cmd.py | - | File has maintainability index 0.0 (rank C) |
| MEDIUM | tests/unit/test_review_cmd.py | - | File has maintainability index 0.0 (rank C) |
| MEDIUM | tests/unit/test_metrics.py | - | File has maintainability index 5.3 (rank C) |
| MEDIUM | tests/unit/test_build_cmd.py | - | File has maintainability index 0.0 (rank C) |
| MEDIUM | tests/unit/test_worker_protocol.py | - | File has maintainability index 0.0 (rank C) |
| MEDIUM | tests/unit/test_status_cmd.py | - | File has maintainability index 8.1 (rank C) |
| MEDIUM | tests/unit/test_security_rules_cmd.py | - | File has maintainability index 6.0 (rank C) |
| MEDIUM | tests/unit/test_state.py | - | File has maintainability index 0.5 (rank C) |
| MEDIUM | tests/unit/test_orchestrator.py | - | File has maintainability index 8.2 (rank C) |
| MEDIUM | tests/unit/test_init_cmd.py | - | File has maintainability index 0.0 (rank C) |
| MEDIUM | tests/unit/test_plan_cmd.py | - | File has maintainability index 2.1 (rank C) |
| MEDIUM | tests/unit/test_containers.py | - | File has maintainability index 3.8 (rank C) |
| MEDIUM | tests/unit/test_charter_full.py | - | File has maintainability index 7.1 (rank C) |
| MEDIUM | tests/unit/test_worker_metrics.py | - | File has maintainability index 8.0 (rank C) |
| MEDIUM | tests/unit/test_config.py | - | File has maintainability index 4.7 (rank C) |
| MEDIUM | tests/unit/test_git_cmd.py | - | File has maintainability index 5.8 (rank C) |
| MEDIUM | tests/unit/test_refactor_cmd.py | - | File has maintainability index 0.0 (rank C) |
| MEDIUM | tests/unit/test_logs_cmd.py | - | File has maintainability index 6.6 (rank C) |
| MEDIUM | tests/unit/test_analyze_cmd.py | - | File has maintainability index 0.0 (rank C) |
| MEDIUM | tests/unit/test_merge_flow.py | - | File has maintainability index 6.0 (rank C) |
| MEDIUM | tests/unit/test_launcher.py | - | File has maintainability index 0.0 (rank C) |
| MEDIUM | tests/unit/test_security_rules_full.py | - | File has maintainability index 0.0 (rank C) |
| MEDIUM | zerg/commands/debug.py | - | File has maintainability index 0.0 (rank C) |
| LOW | configure@96-124@./tests/mocks/mock_git.py | - | Function './tests/mocks/mock_git.py' has 7 parameters |
| LOW | configure@101-150@./tests/mocks/mock_merge.py | - | Function './tests/mocks/mock_merge.py' has 14 parameters |
| LOW | _record_attempt@280-309@./tests/mocks/mock_merge.py | - | Function './tests/mocks/mock_merge.py' has 8 parameters |
| LOW | configure@93-130@./tests/mocks/mock_state.py | - | Function './tests/mocks/mock_state.py' has 10 parameters |
| LOW | configure@106-137@./tests/mocks/mock_launcher.py | - | Function './tests/mocks/mock_launcher.py' has 8 parameters |
| LOW | spawn@139-236@./tests/mocks/mock_launcher.py | - | Function './tests/mocks/mock_launcher.py' has 6 parameters |
| LOW | test_review_writes_output_file@1267-1298@./tests/unit/test_review_cmd.py | - | Function './tests/unit/test_review_cmd.py' has 6 parameters |
| LOW | test_init_with_explicit_args@159-185@./tests/unit/test_worker_protocol.py | - | Function './tests/unit/test_worker_protocol.py' has 8 parameters |
| LOW | test_init_from_environment@203-229@./tests/unit/test_worker_protocol.py | - | Function './tests/unit/test_worker_protocol.py' has 7 parameters |
| LOW | test_init_defaults_when_no_env@238-262@./tests/unit/test_worker_protocol.py | - | Function './tests/unit/test_worker_protocol.py' has 7 parameters |
| LOW | test_init_with_task_graph_env@276-306@./tests/unit/test_worker_protocol.py | - | Function './tests/unit/test_worker_protocol.py' has 9 parameters |
| LOW | test_init_with_task_graph_arg@315-349@./tests/unit/test_worker_protocol.py | - | Function './tests/unit/test_worker_protocol.py' has 9 parameters |
| LOW | test_init_task_parser_error_handled@358-397@./tests/unit/test_worker_protocol.py | - | Function './tests/unit/test_worker_protocol.py' has 9 parameters |
| LOW | test_init_with_spec_dir_env@406-432@./tests/unit/test_worker_protocol.py | - | Function './tests/unit/test_worker_protocol.py' has 7 parameters |
| LOW | test_signal_ready@444-473@./tests/unit/test_worker_protocol.py | - | Function './tests/unit/test_worker_protocol.py' has 7 parameters |
| LOW | test_wait_for_ready_already_ready@485-511@./tests/unit/test_worker_protocol.py | - | Function './tests/unit/test_worker_protocol.py' has 7 parameters |
| LOW | test_wait_for_ready_timeout@519-545@./tests/unit/test_worker_protocol.py | - | Function './tests/unit/test_worker_protocol.py' has 7 parameters |
| LOW | test_is_ready_property@553-578@./tests/unit/test_worker_protocol.py | - | Function './tests/unit/test_worker_protocol.py' has 7 parameters |
| LOW | test_claim_next_task_success@590-621@./tests/unit/test_worker_protocol.py | - | Function './tests/unit/test_worker_protocol.py' has 7 parameters |
| LOW | test_claim_next_task_no_pending@629-657@./tests/unit/test_worker_protocol.py | - | Function './tests/unit/test_worker_protocol.py' has 7 parameters |
| LOW | test_claim_next_task_claim_fails@665-694@./tests/unit/test_worker_protocol.py | - | Function './tests/unit/test_worker_protocol.py' has 7 parameters |
| LOW | test_load_task_details_from_parser@706-743@./tests/unit/test_worker_protocol.py | - | Function './tests/unit/test_worker_protocol.py' has 7 parameters |
| LOW | test_load_task_details_fallback_stub@751-783@./tests/unit/test_worker_protocol.py | - | Function './tests/unit/test_worker_protocol.py' has 7 parameters |
| LOW | test_load_task_details_no_parser@791-818@./tests/unit/test_worker_protocol.py | - | Function './tests/unit/test_worker_protocol.py' has 7 parameters |
| LOW | test_build_task_prompt_basic@830-862@./tests/unit/test_worker_protocol.py | - | Function './tests/unit/test_worker_protocol.py' has 7 parameters |
| LOW | test_build_task_prompt_with_description@870-903@./tests/unit/test_worker_protocol.py | - | Function './tests/unit/test_worker_protocol.py' has 7 parameters |
| LOW | test_build_task_prompt_with_files@911-950@./tests/unit/test_worker_protocol.py | - | Function './tests/unit/test_worker_protocol.py' has 7 parameters |
| LOW | test_build_task_prompt_with_verification@958-993@./tests/unit/test_worker_protocol.py | - | Function './tests/unit/test_worker_protocol.py' has 7 parameters |
| LOW | test_build_task_prompt_with_spec_context@1001-1033@./tests/unit/test_worker_protocol.py | - | Function './tests/unit/test_worker_protocol.py' has 7 parameters |
| LOW | test_build_task_prompt_uses_id_when_no_title@1041-1071@./tests/unit/test_worker_protocol.py | - | Function './tests/unit/test_worker_protocol.py' has 7 parameters |
| LOW | test_invoke_claude_code_success@1084-1120@./tests/unit/test_worker_protocol.py | - | Function './tests/unit/test_worker_protocol.py' has 8 parameters |
| LOW | test_invoke_claude_code_failure@1129-1164@./tests/unit/test_worker_protocol.py | - | Function './tests/unit/test_worker_protocol.py' has 8 parameters |
| LOW | test_invoke_claude_code_timeout@1173-1206@./tests/unit/test_worker_protocol.py | - | Function './tests/unit/test_worker_protocol.py' has 8 parameters |
| LOW | test_invoke_claude_code_not_found@1215-1246@./tests/unit/test_worker_protocol.py | - | Function './tests/unit/test_worker_protocol.py' has 8 parameters |
| LOW | test_invoke_claude_code_generic_exception@1255-1286@./tests/unit/test_worker_protocol.py | - | Function './tests/unit/test_worker_protocol.py' has 8 parameters |
| LOW | test_invoke_claude_code_custom_timeout@1295-1330@./tests/unit/test_worker_protocol.py | - | Function './tests/unit/test_worker_protocol.py' has 8 parameters |
| LOW | test_run_verification_success@1342-1383@./tests/unit/test_worker_protocol.py | - | Function './tests/unit/test_worker_protocol.py' has 7 parameters |
| LOW | test_run_verification_failure@1391-1433@./tests/unit/test_worker_protocol.py | - | Function './tests/unit/test_worker_protocol.py' has 7 parameters |
| LOW | test_run_verification_no_verification_spec@1441-1468@./tests/unit/test_worker_protocol.py | - | Function './tests/unit/test_worker_protocol.py' has 7 parameters |
| LOW | test_run_verification_empty_command@1476-1506@./tests/unit/test_worker_protocol.py | - | Function './tests/unit/test_worker_protocol.py' has 7 parameters |
| LOW | test_commit_task_changes_success@1518-1557@./tests/unit/test_worker_protocol.py | - | Function './tests/unit/test_worker_protocol.py' has 7 parameters |
| LOW | test_commit_task_changes_no_changes@1565-1596@./tests/unit/test_worker_protocol.py | - | Function './tests/unit/test_worker_protocol.py' has 7 parameters |
| LOW | test_commit_task_changes_exception@1604-1639@./tests/unit/test_worker_protocol.py | - | Function './tests/unit/test_worker_protocol.py' has 7 parameters |
| LOW | test_execute_task_success@1651-1703@./tests/unit/test_worker_protocol.py | - | Function './tests/unit/test_worker_protocol.py' has 7 parameters |
| LOW | test_execute_task_claude_failure@1711-1752@./tests/unit/test_worker_protocol.py | - | Function './tests/unit/test_worker_protocol.py' has 7 parameters |
| LOW | test_execute_task_verification_failure@1760-1803@./tests/unit/test_worker_protocol.py | - | Function './tests/unit/test_worker_protocol.py' has 7 parameters |
| LOW | test_execute_task_commit_failure@1811-1850@./tests/unit/test_worker_protocol.py | - | Function './tests/unit/test_worker_protocol.py' has 7 parameters |
| LOW | test_execute_task_exception@1858-1890@./tests/unit/test_worker_protocol.py | - | Function './tests/unit/test_worker_protocol.py' has 7 parameters |
| LOW | test_report_complete@1902-1936@./tests/unit/test_worker_protocol.py | - | Function './tests/unit/test_worker_protocol.py' has 7 parameters |
| LOW | test_report_failed@1944-1976@./tests/unit/test_worker_protocol.py | - | Function './tests/unit/test_worker_protocol.py' has 7 parameters |
| LOW | test_check_context_usage@1988-2018@./tests/unit/test_worker_protocol.py | - | Function './tests/unit/test_worker_protocol.py' has 7 parameters |
| LOW | test_should_checkpoint@2026-2055@./tests/unit/test_worker_protocol.py | - | Function './tests/unit/test_worker_protocol.py' has 7 parameters |
| LOW | test_track_file_read@2063-2090@./tests/unit/test_worker_protocol.py | - | Function './tests/unit/test_worker_protocol.py' has 7 parameters |
| LOW | test_track_tool_call@2098-2125@./tests/unit/test_worker_protocol.py | - | Function './tests/unit/test_worker_protocol.py' has 7 parameters |
| LOW | test_checkpoint_and_exit_with_changes@2138-2177@./tests/unit/test_worker_protocol.py | - | Function './tests/unit/test_worker_protocol.py' has 8 parameters |
| LOW | test_checkpoint_and_exit_no_changes@2186-2221@./tests/unit/test_worker_protocol.py | - | Function './tests/unit/test_worker_protocol.py' has 8 parameters |
| LOW | test_checkpoint_and_exit_no_current_task@2230-2265@./tests/unit/test_worker_protocol.py | - | Function './tests/unit/test_worker_protocol.py' has 8 parameters |
| LOW | test_get_status@2277-2316@./tests/unit/test_worker_protocol.py | - | Function './tests/unit/test_worker_protocol.py' has 7 parameters |
| LOW | test_get_status_no_current_task@2324-2358@./tests/unit/test_worker_protocol.py | - | Function './tests/unit/test_worker_protocol.py' has 7 parameters |
| LOW | test_start_no_tasks@2372-2415@./tests/unit/test_worker_protocol.py | - | Function './tests/unit/test_worker_protocol.py' has 9 parameters |
| LOW | test_start_executes_tasks@2425-2480@./tests/unit/test_worker_protocol.py | - | Function './tests/unit/test_worker_protocol.py' has 9 parameters |
| LOW | test_start_task_execution_failure@2490-2552@./tests/unit/test_worker_protocol.py | - | Function './tests/unit/test_worker_protocol.py' has 9 parameters |
| LOW | test_start_checkpoints_on_high_context@2561-2597@./tests/unit/test_worker_protocol.py | - | Function './tests/unit/test_worker_protocol.py' has 8 parameters |
| LOW | test_container_mode_initialization@26-59@./tests/unit/test_orchestrator_container_mode.py | - | Function './tests/unit/test_orchestrator_container_mode.py' has 12 parameters |
| LOW | test_get_worker_image_name_from_config@75-111@./tests/unit/test_orchestrator_container_mode.py | - | Function './tests/unit/test_orchestrator_container_mode.py' has 12 parameters |
| LOW | test_get_worker_image_name_default@123-151@./tests/unit/test_orchestrator_container_mode.py | - | Function './tests/unit/test_orchestrator_container_mode.py' has 12 parameters |
| LOW | test_launcher_type_container_mode@167-195@./tests/unit/test_orchestrator_container_mode.py | - | Function './tests/unit/test_orchestrator_container_mode.py' has 12 parameters |
| LOW | test_launcher_type_subprocess_mode@207-235@./tests/unit/test_orchestrator_container_mode.py | - | Function './tests/unit/test_orchestrator_container_mode.py' has 12 parameters |
| LOW | test_container_launcher_config_timeout@251-287@./tests/unit/test_orchestrator_container_mode.py | - | Function './tests/unit/test_orchestrator_container_mode.py' has 12 parameters |
| LOW | test_container_launcher_config_log_dir@299-335@./tests/unit/test_orchestrator_container_mode.py | - | Function './tests/unit/test_orchestrator_container_mode.py' has 12 parameters |
| LOW | test_container_launcher_image_name_passed@347-384@./tests/unit/test_orchestrator_container_mode.py | - | Function './tests/unit/test_orchestrator_container_mode.py' has 12 parameters |
| LOW | test_container_launcher_ensure_network_called@396-422@./tests/unit/test_orchestrator_container_mode.py | - | Function './tests/unit/test_orchestrator_container_mode.py' has 12 parameters |
| LOW | test_explicit_container_never_produces_subprocess@439-468@./tests/unit/test_orchestrator_container_mode.py | - | Function './tests/unit/test_orchestrator_container_mode.py' has 13 parameters |
| LOW | test_explicit_container_raises_on_network_failure@480-506@./tests/unit/test_orchestrator_container_mode.py | - | Function './tests/unit/test_orchestrator_container_mode.py' has 12 parameters |
| LOW | test_auto_container_falls_back_on_network_failure@520-554@./tests/unit/test_orchestrator_container_mode.py | - | Function './tests/unit/test_orchestrator_container_mode.py' has 14 parameters |
| LOW | create_test_state_file@56-99@./tests/unit/test_status_cmd.py | - | Function './tests/unit/test_status_cmd.py' has 9 parameters |
| LOW | create_mock_state_manager@102-153@./tests/unit/test_status_cmd.py | - | Function './tests/unit/test_status_cmd.py' has 8 parameters |
| LOW | test_wait_ready_times_out_on_slow_container@220-244@./tests/unit/test_launcher_errors.py | - | Function './tests/unit/test_launcher_errors.py' has 6 parameters |
| LOW | test_wait_ready_container_exits_during_health_check@250-275@./tests/unit/test_launcher_errors.py | - | Function './tests/unit/test_launcher_errors.py' has 6 parameters |
| LOW | test_wait_ready_handles_generic_exception@281-306@./tests/unit/test_launcher_errors.py | - | Function './tests/unit/test_launcher_errors.py' has 6 parameters |
| LOW | test_spawn_cleans_up_on_exec_failure@316-339@./tests/unit/test_launcher_errors.py | - | Function './tests/unit/test_launcher_errors.py' has 6 parameters |
| LOW | test_spawn_cleans_up_on_verify_failure@346-371@./tests/unit/test_launcher_errors.py | - | Function './tests/unit/test_launcher_errors.py' has 7 parameters |
| LOW | test_cleanup_called_on_exec_failure@122-145@./tests/unit/test_launcher_network.py | - | Function './tests/unit/test_launcher_network.py' has 6 parameters |
| LOW | test_cleanup_called_on_verify_failure@152-177@./tests/unit/test_launcher_network.py | - | Function './tests/unit/test_launcher_network.py' has 7 parameters |
| LOW | test_spawn_cleanup_preserves_other_workers@482-527@./tests/unit/test_launcher_network.py | - | Function './tests/unit/test_launcher_network.py' has 6 parameters |
| LOW | test_graceful_sends_checkpoint_signals@225-247@./tests/unit/test_stop_cmd.py | - | Function './tests/unit/test_stop_cmd.py' has 6 parameters |
| LOW | test_graceful_updates_worker_status_to_stopping@282-310@./tests/unit/test_stop_cmd.py | - | Function './tests/unit/test_stop_cmd.py' has 6 parameters |
| LOW | test_graceful_waits_for_shutdown@314-353@./tests/unit/test_stop_cmd.py | - | Function './tests/unit/test_stop_cmd.py' has 6 parameters |
| LOW | test_graceful_forces_remaining_on_timeout@358-391@./tests/unit/test_stop_cmd.py | - | Function './tests/unit/test_stop_cmd.py' has 7 parameters |
| LOW | test_graceful_handles_signal_failure@395-415@./tests/unit/test_stop_cmd.py | - | Function './tests/unit/test_stop_cmd.py' has 6 parameters |
| LOW | test_graceful_all_workers_stop_before_timeout@419-450@./tests/unit/test_stop_cmd.py | - | Function './tests/unit/test_stop_cmd.py' has 6 parameters |
| LOW | test_graceful_timeout_with_no_remaining_workers@457-483@./tests/unit/test_stop_cmd.py | - | Function './tests/unit/test_stop_cmd.py' has 7 parameters |
| LOW | test_stop_force_skips_confirmation@700-726@./tests/unit/test_stop_cmd.py | - | Function './tests/unit/test_stop_cmd.py' has 8 parameters |
| LOW | test_stop_graceful_requires_confirmation@732-757@./tests/unit/test_stop_cmd.py | - | Function './tests/unit/test_stop_cmd.py' has 8 parameters |
| LOW | test_stop_confirmation_declined_aborts@763-789@./tests/unit/test_stop_cmd.py | - | Function './tests/unit/test_stop_cmd.py' has 8 parameters |
| LOW | test_stop_specific_worker@795-825@./tests/unit/test_stop_cmd.py | - | Function './tests/unit/test_stop_cmd.py' has 8 parameters |
| LOW | test_stop_specific_worker_not_found_fails@829-854@./tests/unit/test_stop_cmd.py | - | Function './tests/unit/test_stop_cmd.py' has 6 parameters |
| LOW | test_stop_custom_timeout@860-888@./tests/unit/test_stop_cmd.py | - | Function './tests/unit/test_stop_cmd.py' has 8 parameters |
| LOW | test_stop_auto_detects_feature@895-923@./tests/unit/test_stop_cmd.py | - | Function './tests/unit/test_stop_cmd.py' has 9 parameters |
| LOW | test_stop_prints_completion_message@966-990@./tests/unit/test_stop_cmd.py | - | Function './tests/unit/test_stop_cmd.py' has 8 parameters |
| LOW | test_full_force_stop_workflow@1004-1036@./tests/unit/test_stop_cmd.py | - | Function './tests/unit/test_stop_cmd.py' has 7 parameters |
| LOW | test_full_graceful_stop_workflow@1042-1081@./tests/unit/test_stop_cmd.py | - | Function './tests/unit/test_stop_cmd.py' has 8 parameters |
| LOW | test_cleanup_aborted_on_no_confirm@158-186@./tests/unit/test_cleanup_cmd.py | - | Function './tests/unit/test_cleanup_cmd.py' has 7 parameters |
| LOW | test_cleanup_executes_on_confirm@194-223@./tests/unit/test_cleanup_cmd.py | - | Function './tests/unit/test_cleanup_cmd.py' has 7 parameters |
| LOW | test_cleanup_with_specific_feature@230-259@./tests/unit/test_cleanup_cmd.py | - | Function './tests/unit/test_cleanup_cmd.py' has 6 parameters |
| LOW | test_execute_reports_multiple_errors@1040-1073@./tests/unit/test_cleanup_cmd.py | - | Function './tests/unit/test_cleanup_cmd.py' has 6 parameters |
| LOW | test_full_cleanup_flow@1089-1141@./tests/unit/test_cleanup_cmd.py | - | Function './tests/unit/test_cleanup_cmd.py' has 8 parameters |
| LOW | test_cleanup_with_keep_options@1146-1181@./tests/unit/test_cleanup_cmd.py | - | Function './tests/unit/test_cleanup_cmd.py' has 6 parameters |
| LOW | test_spawn_success@986-1013@./tests/unit/test_launcher.py | - | Function './tests/unit/test_launcher.py' has 7 parameters |
| LOW | test_spawn_with_api_key@1081-1105@./tests/unit/test_launcher.py | - | Function './tests/unit/test_launcher.py' has 6 parameters |
| LOW | test_spawn_with_config_env_vars@1111-1136@./tests/unit/test_launcher.py | - | Function './tests/unit/test_launcher.py' has 6 parameters |
| LOW | test_spawn_with_additional_env@1142-1167@./tests/unit/test_launcher.py | - | Function './tests/unit/test_launcher.py' has 6 parameters |
| LOW | test_auto_detect_without_devcontainer@25-57@./tests/integration/test_container_orchestrator.py | - | Function './tests/integration/test_container_orchestrator.py' has 11 parameters |
| LOW | test_subprocess_mode_explicit@68-103@./tests/integration/test_container_orchestrator.py | - | Function './tests/integration/test_container_orchestrator.py' has 11 parameters |
| LOW | zerg_state_factory._create_state@617-670@./tests/fixtures/state_fixtures.py | - | Function './tests/fixtures/state_fixtures.py' has 6 parameters |
| LOW | worker_state_factory._create_worker@821-856@./tests/fixtures/state_fixtures.py | - | Function './tests/fixtures/state_fixtures.py' has 7 parameters |
| LOW | __init__@102-123@./tests/helpers/async_helpers.py | - | Function './tests/helpers/async_helpers.py' has 6 parameters |
| LOW | spawn@473-516@./tests/helpers/command_mocks.py | - | Function './tests/helpers/command_mocks.py' has 6 parameters |
| LOW | run@1230-1296@./tests/helpers/command_mocks.py | - | Function './tests/helpers/command_mocks.py' has 9 parameters |
| LOW | build@439-566@./zerg/commands/build.py | - | Function './zerg/commands/build.py' has 9 parameters |
| LOW | plan@29-130@./zerg/commands/plan.py | - | Function './zerg/commands/plan.py' has 8 parameters |
| LOW | refactor@446-560@./zerg/commands/refactor.py | - | Function './zerg/commands/refactor.py' has 7 parameters |
| LOW | merge_cmd@29-157@./zerg/commands/merge_cmd.py | - | Function './zerg/commands/merge_cmd.py' has 6 parameters |
| LOW | test_cmd@517-664@./zerg/commands/test_cmd.py | - | Function './zerg/commands/test_cmd.py' has 9 parameters |
| LOW | design@27-177@./zerg/commands/design.py | - | Function './zerg/commands/design.py' has 7 parameters |
| LOW | cleanup@34-103@./zerg/commands/cleanup.py | - | Function './zerg/commands/cleanup.py' has 7 parameters |
| LOW | retry@25-107@./zerg/commands/retry.py | - | Function './zerg/commands/retry.py' has 6 parameters |
| LOW | git_cmd@364-423@./zerg/commands/git_cmd.py | - | Function './zerg/commands/git_cmd.py' has 8 parameters |
| LOW | logs@62-185@./zerg/commands/logs.py | - | Function './zerg/commands/logs.py' has 15 parameters |
| LOW | _show_aggregated_logs@188-232@./zerg/commands/logs.py | - | Function './zerg/commands/logs.py' has 12 parameters |
| LOW | run@400-546@./zerg/commands/debug.py | - | Function './zerg/commands/debug.py' has 8 parameters |
| LOW | debug@997-1418@./zerg/commands/debug.py | - | Function './zerg/commands/debug.py' has 13 parameters |
| LOW | init@113-230@./zerg/commands/init.py | - | Function './zerg/commands/init.py' has 7 parameters |
| LOW | rush@46-203@./zerg/commands/rush.py | - | Function './zerg/commands/rush.py' has 13 parameters |
| LOW | analyze@395-530@./zerg/commands/analyze.py | - | Function './zerg/commands/analyze.py' has 7 parameters |
| LOW | status@57-116@./zerg/commands/status.py | - | Function './zerg/commands/status.py' has 7 parameters |
| LOW | _ccn_finding@112-131@./zerg/performance/adapters/lizard_adapter.py | - | Function './zerg/performance/adapters/lizard_adapter.py' has 6 parameters |
| LOW | _nloc_finding@133-152@./zerg/performance/adapters/lizard_adapter.py | - | Function './zerg/performance/adapters/lizard_adapter.py' has 6 parameters |
| LOW | query@47-127@./zerg/log_aggregator.py | - | Function './zerg/log_aggregator.py' has 11 parameters |
| LOW | setup_logging@145-194@./zerg/logging.py | - | Function './zerg/logging.py' has 6 parameters |
| LOW | start_worker@162-225@./zerg/containers.py | - | Function './zerg/containers.py' has 6 parameters |
| LOW | __init__@179-211@./zerg/command_executor.py | - | Function './zerg/command_executor.py' has 7 parameters |
| LOW | execute@298-434@./zerg/command_executor.py | - | Function './zerg/command_executor.py' has 7 parameters |
| LOW | __init__@48-94@./zerg/level_coordinator.py | - | Function './zerg/level_coordinator.py' has 14 parameters |
| LOW | run_all_gates@126-201@./zerg/gates.py | - | Function './zerg/gates.py' has 7 parameters |
| LOW | complete@32-61@./zerg/worker_metrics.py | - | Function './zerg/worker_metrics.py' has 6 parameters |
| LOW | complete_task@181-233@./zerg/worker_metrics.py | - | Function './zerg/worker_metrics.py' has 7 parameters |
| LOW | __init__@45-97@./zerg/worker_manager.py | - | Function './zerg/worker_manager.py' has 17 parameters |
| LOW | __init__@39-52@./zerg/exceptions.py | - | Function './zerg/exceptions.py' has 7 parameters |
| LOW | __init__@154-169@./zerg/exceptions.py | - | Function './zerg/exceptions.py' has 7 parameters |
| LOW | spawn@197-217@./zerg/launcher.py | - | Function './zerg/launcher.py' has 6 parameters |
| LOW | spawn_async@335-360@./zerg/launcher.py | - | Function './zerg/launcher.py' has 6 parameters |
| LOW | spawn@423-525@./zerg/launcher.py | - | Function './zerg/launcher.py' has 6 parameters |
| LOW | spawn_async@686-795@./zerg/launcher.py | - | Function './zerg/launcher.py' has 6 parameters |
| LOW | __init__@896-918@./zerg/launcher.py | - | Function './zerg/launcher.py' has 6 parameters |
| LOW | spawn@920-1035@./zerg/launcher.py | - | Function './zerg/launcher.py' has 6 parameters |
| LOW | spawn_async@1481-1606@./zerg/launcher.py | - | Function './zerg/launcher.py' has 6 parameters |
| LOW | verify@66-147@./zerg/verify.py | - | Function './zerg/verify.py' has 6 parameters |
| LOW | verify_with_retry@185-218@./zerg/verify.py | - | Function './zerg/verify.py' has 6 parameters |
| LOW | __init__@26-48@./zerg/task_retry_manager.py | - | Function './zerg/task_retry_manager.py' has 6 parameters |
| LOW | emit@51-96@./zerg/log_writer.py | - | Function './zerg/log_writer.py' has 8 parameters |
| LOW | __init__@91-195@./zerg/worker_protocol.py | - | Function './zerg/worker_protocol.py' has 6 parameters |
| LOW | __init__@120-134@./zerg/dryrun.py | - | Function './zerg/dryrun.py' has 7 parameters |
| LOW | __init__@62-78@./zerg/preflight.py | - | Function './zerg/preflight.py' has 8 parameters |
| LOW | set_worker_state@187-230@./.zerg/tests/mocks/mock_state.py | - | Function './.zerg/tests/mocks/mock_state.py' has 7 parameters |
| LOW | set_task_state@280-339@./.zerg/tests/mocks/mock_state.py | - | Function './.zerg/tests/mocks/mock_state.py' has 7 parameters |
| LOW | create_checkpoint@616-650@./.zerg/tests/mocks/mock_state.py | - | Function './.zerg/tests/mocks/mock_state.py' has 7 parameters |

## Code Volume (Score: 0/100)
| Severity | File | Line | Message |
|----------|------|------|---------|
| HIGH | .gsd/specs/coverage-100/task-graph.json | 1 | Duplicated block (635 lines, 0 tokens) between .gsd/specs/coverage-100/task-graph.json and .zerg/specs/coverage-100/task-graph.json |
| HIGH | .zerg/templates/quality-reviewer.md | 5 | Duplicated block (52 lines, 0 tokens) between .zerg/templates/quality-reviewer.md and .gsd/tasks/prompts/L1-TASK-004-prompt-templates.md |
| HIGH | .zerg/templates/implementer.md | 3 | Duplicated block (66 lines, 0 tokens) between .zerg/templates/implementer.md and .gsd/tasks/prompts/L1-TASK-004-prompt-templates.md |
| HIGH | .claude/commands/zerg:worker.md | 3 | Duplicated block (382 lines, 0 tokens) between .claude/commands/zerg:worker.md and zerg/data/commands/zerg:worker.md |
| HIGH | .claude/commands/zerg:test.md | 3 | Duplicated block (79 lines, 0 tokens) between .claude/commands/zerg:test.md and zerg/data/commands/zerg:test.md |
| HIGH | .claude/commands/zerg:stop.md | 3 | Duplicated block (190 lines, 0 tokens) between .claude/commands/zerg:stop.md and zerg/data/commands/zerg:stop.md |
| HIGH | .claude/commands/zerg:status.md | 3 | Duplicated block (311 lines, 0 tokens) between .claude/commands/zerg:status.md and zerg/data/commands/zerg:status.md |
| HIGH | .claude/commands/zerg:security.md | 3 | Duplicated block (138 lines, 0 tokens) between .claude/commands/zerg:security.md and zerg/data/commands/zerg:security.md |
| HIGH | .claude/commands/zerg:rush.md | 3 | Duplicated block (620 lines, 0 tokens) between .claude/commands/zerg:rush.md and zerg/data/commands/zerg:rush.md |
| HIGH | .claude/commands/zerg:review.md | 3 | Duplicated block (82 lines, 0 tokens) between .claude/commands/zerg:review.md and zerg/data/commands/zerg:review.md |
| HIGH | .claude/commands/zerg:retry.md | 3 | Duplicated block (229 lines, 0 tokens) between .claude/commands/zerg:retry.md and zerg/data/commands/zerg:retry.md |
| HIGH | .claude/commands/zerg:refactor.md | 3 | Duplicated block (90 lines, 0 tokens) between .claude/commands/zerg:refactor.md and zerg/data/commands/zerg:refactor.md |
| HIGH | .claude/commands/zerg:plugins.md | 3 | Duplicated block (542 lines, 0 tokens) between .claude/commands/zerg:plugins.md and zerg/data/commands/zerg:plugins.md |
| HIGH | .claude/commands/zerg:plan.md | 3 | Duplicated block (466 lines, 0 tokens) between .claude/commands/zerg:plan.md and zerg/data/commands/zerg:plan.md |
| HIGH | .claude/commands/zerg:merge.md | 3 | Duplicated block (313 lines, 0 tokens) between .claude/commands/zerg:merge.md and zerg/data/commands/zerg:merge.md |
| HIGH | .claude/commands/zerg:logs.md | 3 | Duplicated block (226 lines, 0 tokens) between .claude/commands/zerg:logs.md and zerg/data/commands/zerg:logs.md |
| HIGH | .claude/commands/zerg:init.md | 3 | Duplicated block (666 lines, 0 tokens) between .claude/commands/zerg:init.md and zerg/data/commands/zerg:init.md |
| HIGH | .claude/commands/zerg:git.md | 3 | Duplicated block (94 lines, 0 tokens) between .claude/commands/zerg:git.md and zerg/data/commands/zerg:git.md |
| HIGH | .claude/commands/zerg:design.md | 3 | Duplicated block (649 lines, 0 tokens) between .claude/commands/zerg:design.md and zerg/data/commands/zerg:design.md |
| HIGH | .claude/commands/zerg:debug.md | 3 | Duplicated block (513 lines, 0 tokens) between .claude/commands/zerg:debug.md and zerg/data/commands/zerg:debug.md |
| HIGH | .claude/commands/zerg:cleanup.md | 3 | Duplicated block (212 lines, 0 tokens) between .claude/commands/zerg:cleanup.md and zerg/data/commands/zerg:cleanup.md |
| HIGH | .claude/commands/zerg:build.md | 3 | Duplicated block (69 lines, 0 tokens) between .claude/commands/zerg:build.md and zerg/data/commands/zerg:build.md |
| HIGH | .claude/commands/zerg:analyze.md | 3 | Duplicated block (69 lines, 0 tokens) between .claude/commands/zerg:analyze.md and zerg/data/commands/zerg:analyze.md |
| HIGH | .claude/commands/z:worker.md | 3 | Duplicated block (382 lines, 0 tokens) between .claude/commands/z:worker.md and zerg/data/commands/zerg:worker.md |
| HIGH | .claude/commands/z:test.md | 3 | Duplicated block (79 lines, 0 tokens) between .claude/commands/z:test.md and zerg/data/commands/zerg:test.md |
| HIGH | .claude/commands/z:stop.md | 3 | Duplicated block (190 lines, 0 tokens) between .claude/commands/z:stop.md and zerg/data/commands/zerg:stop.md |
| HIGH | .claude/commands/z:status.md | 3 | Duplicated block (311 lines, 0 tokens) between .claude/commands/z:status.md and zerg/data/commands/zerg:status.md |
| HIGH | .claude/commands/z:security.md | 3 | Duplicated block (138 lines, 0 tokens) between .claude/commands/z:security.md and zerg/data/commands/zerg:security.md |
| HIGH | .claude/commands/z:rush.md | 3 | Duplicated block (620 lines, 0 tokens) between .claude/commands/z:rush.md and zerg/data/commands/zerg:rush.md |
| HIGH | .claude/commands/z:review.md | 3 | Duplicated block (82 lines, 0 tokens) between .claude/commands/z:review.md and zerg/data/commands/zerg:review.md |
| HIGH | .claude/commands/z:retry.md | 3 | Duplicated block (229 lines, 0 tokens) between .claude/commands/z:retry.md and zerg/data/commands/zerg:retry.md |
| HIGH | .claude/commands/z:refactor.md | 3 | Duplicated block (90 lines, 0 tokens) between .claude/commands/z:refactor.md and zerg/data/commands/zerg:refactor.md |
| HIGH | .claude/commands/z:plugins.md | 3 | Duplicated block (542 lines, 0 tokens) between .claude/commands/z:plugins.md and zerg/data/commands/zerg:plugins.md |
| HIGH | .claude/commands/z:plan.md | 3 | Duplicated block (466 lines, 0 tokens) between .claude/commands/z:plan.md and zerg/data/commands/zerg:plan.md |
| HIGH | .claude/commands/z:merge.md | 3 | Duplicated block (313 lines, 0 tokens) between .claude/commands/z:merge.md and zerg/data/commands/zerg:merge.md |
| HIGH | .claude/commands/z:logs.md | 3 | Duplicated block (226 lines, 0 tokens) between .claude/commands/z:logs.md and zerg/data/commands/zerg:logs.md |
| HIGH | .claude/commands/z:init.md | 3 | Duplicated block (666 lines, 0 tokens) between .claude/commands/z:init.md and zerg/data/commands/zerg:init.md |
| HIGH | .claude/commands/z:git.md | 3 | Duplicated block (94 lines, 0 tokens) between .claude/commands/z:git.md and zerg/data/commands/zerg:git.md |
| HIGH | .claude/commands/z:design.md | 3 | Duplicated block (649 lines, 0 tokens) between .claude/commands/z:design.md and zerg/data/commands/zerg:design.md |
| HIGH | .claude/commands/z:debug.md | 3 | Duplicated block (513 lines, 0 tokens) between .claude/commands/z:debug.md and zerg/data/commands/zerg:debug.md |
| HIGH | .claude/commands/z:cleanup.md | 3 | Duplicated block (212 lines, 0 tokens) between .claude/commands/z:cleanup.md and zerg/data/commands/zerg:cleanup.md |
| HIGH | .claude/commands/z:build.md | 3 | Duplicated block (69 lines, 0 tokens) between .claude/commands/z:build.md and zerg/data/commands/zerg:build.md |
| HIGH | .claude/commands/z:analyze.md | 3 | Duplicated block (69 lines, 0 tokens) between .claude/commands/z:analyze.md and zerg/data/commands/zerg:analyze.md |
| HIGH | .zerg/build.py | 59 | Duplicated block (94 lines, 0 tokens) between .zerg/build.py and zerg/commands/build.py |
| MEDIUM | .gsd/tasks/prompts/L4-advanced-commands.md | 21 | Duplicated block (42 lines, 0 tokens) between .gsd/tasks/prompts/L4-advanced-commands.md and zerg/data/commands/zerg:git.md |
| MEDIUM | .gsd/specs/coverage-100/feature.yaml | 1 | Duplicated block (43 lines, 0 tokens) between .gsd/specs/coverage-100/feature.yaml and .zerg/specs/coverage-100/feature.yaml |
| MEDIUM | zerg/commands/status.py | 113 | Duplicated block (27 lines, 0 tokens) between zerg/commands/status.py and zerg/commands/stop.py |
| MEDIUM | zerg/commands/retry.py | 110 | Duplicated block (21 lines, 0 tokens) between zerg/commands/retry.py and zerg/commands/stop.py |
| MEDIUM | zerg/commands/logs.py | 303 | Duplicated block (24 lines, 0 tokens) between zerg/commands/logs.py and zerg/commands/stop.py |
| MEDIUM | tests/unit/test_worktree.py | 9 | Duplicated block (49 lines, 0 tokens) between tests/unit/test_worktree.py and tests/unit/test_worktree_extended.py |
| MEDIUM | tests/unit/test_worktree.py | 187 | Duplicated block (23 lines, 0 tokens) between tests/unit/test_worktree.py and tests/unit/test_worktree_extended.py |
| MEDIUM | tests/unit/test_orchestrator_recovery.py | 496 | Duplicated block (25 lines, 0 tokens) between tests/unit/test_orchestrator_recovery.py and tests/unit/test_orchestrator_recovery.py |
| MEDIUM | tests/unit/test_orchestrator_levels.py | 15 | Duplicated block (21 lines, 0 tokens) between tests/unit/test_orchestrator_levels.py and tests/unit/test_orchestrator_workers.py |
| MEDIUM | tests/unit/test_merge_gates.py | 340 | Duplicated block (21 lines, 0 tokens) between tests/unit/test_merge_gates.py and tests/unit/test_merge_gates.py |
| MEDIUM | tests/unit/test_merge_gates.py | 383 | Duplicated block (26 lines, 0 tokens) between tests/unit/test_merge_gates.py and tests/unit/test_merge_gates.py |
| MEDIUM | tests/unit/test_merge_gates.py | 418 | Duplicated block (35 lines, 0 tokens) between tests/unit/test_merge_gates.py and tests/unit/test_merge_gates.py |
| MEDIUM | tests/unit/test_merge_gates.py | 459 | Duplicated block (23 lines, 0 tokens) between tests/unit/test_merge_gates.py and tests/unit/test_merge_gates.py |
| MEDIUM | tests/unit/test_merge_gates.py | 480 | Duplicated block (22 lines, 0 tokens) between tests/unit/test_merge_gates.py and tests/unit/test_merge_gates.py |
| MEDIUM | tests/unit/test_merge_gates.py | 577 | Duplicated block (22 lines, 0 tokens) between tests/unit/test_merge_gates.py and tests/unit/test_merge_gates.py |
| MEDIUM | tests/unit/test_merge_gates.py | 608 | Duplicated block (24 lines, 0 tokens) between tests/unit/test_merge_gates.py and tests/unit/test_merge_gates.py |
| MEDIUM | tests/unit/test_merge_gates.py | 641 | Duplicated block (24 lines, 0 tokens) between tests/unit/test_merge_gates.py and tests/unit/test_merge_gates.py |
| MEDIUM | tests/unit/test_merge_gates.py | 710 | Duplicated block (22 lines, 0 tokens) between tests/unit/test_merge_gates.py and tests/unit/test_merge_gates.py |
| MEDIUM | tests/unit/test_merge_gates.py | 789 | Duplicated block (23 lines, 0 tokens) between tests/unit/test_merge_gates.py and tests/unit/test_merge_gates.py |
| MEDIUM | tests/unit/test_merge_gates.py | 822 | Duplicated block (22 lines, 0 tokens) between tests/unit/test_merge_gates.py and tests/unit/test_merge_gates.py |
| MEDIUM | tests/unit/test_merge_gates.py | 852 | Duplicated block (24 lines, 0 tokens) between tests/unit/test_merge_gates.py and tests/unit/test_merge_gates.py |
| MEDIUM | tests/unit/test_merge_full_flow.py | 449 | Duplicated block (27 lines, 0 tokens) between tests/unit/test_merge_full_flow.py and tests/unit/test_merge_full_flow.py |
| MEDIUM | tests/unit/test_merge_full_flow.py | 798 | Duplicated block (21 lines, 0 tokens) between tests/unit/test_merge_full_flow.py and tests/unit/test_merge_full_flow.py |
| MEDIUM | tests/unit/test_charter.py | 87 | Duplicated block (36 lines, 0 tokens) between tests/unit/test_charter.py and tests/unit/test_charter_full.py |
| MEDIUM | tests/unit/test_charter.py | 123 | Duplicated block (50 lines, 0 tokens) between tests/unit/test_charter.py and tests/unit/test_charter_full.py |
| MEDIUM | tests/unit/test_charter.py | 172 | Duplicated block (41 lines, 0 tokens) between tests/unit/test_charter.py and tests/unit/test_charter_full.py |
| MEDIUM | tests/unit/test_charter.py | 210 | Duplicated block (21 lines, 0 tokens) between tests/unit/test_charter.py and tests/unit/test_charter_full.py |
| MEDIUM | tests/unit/test_charter.py | 228 | Duplicated block (21 lines, 0 tokens) between tests/unit/test_charter.py and tests/unit/test_charter_full.py |
| MEDIUM | tests/integration/test_orchestrator_integration.py | 340 | Duplicated block (21 lines, 0 tokens) between tests/integration/test_orchestrator_integration.py and tests/integration/test_orchestrator_integration.py |
| MEDIUM | tests/e2e/test_multilevel_execution.py | 78 | Duplicated block (26 lines, 0 tokens) between tests/e2e/test_multilevel_execution.py and tests/e2e/test_subprocess_e2e.py |
| MEDIUM | tests/e2e/test_failure_recovery.py | 44 | Duplicated block (28 lines, 0 tokens) between tests/e2e/test_failure_recovery.py and tests/e2e/test_multilevel_execution.py |
| MEDIUM | tests/e2e/test_failure_recovery.py | 81 | Duplicated block (29 lines, 0 tokens) between tests/e2e/test_failure_recovery.py and tests/e2e/test_subprocess_e2e.py |
| MEDIUM | tests/e2e/test_bugfix_e2e.py | 21 | Duplicated block (22 lines, 0 tokens) between tests/e2e/test_bugfix_e2e.py and tests/unit/test_orchestrator_workers.py |
| MEDIUM | .zerg/tests/test_task_graph.py | 166 | Duplicated block (27 lines, 0 tokens) between .zerg/tests/test_task_graph.py and .zerg/tests/test_task_graph.py |
| MEDIUM | .zerg/tests/test_task_graph.py | 198 | Duplicated block (27 lines, 0 tokens) between .zerg/tests/test_task_graph.py and .zerg/tests/test_task_graph.py |
| MEDIUM | .zerg/templates/spec-reviewer.md | 30 | Duplicated block (21 lines, 0 tokens) between .zerg/templates/spec-reviewer.md and .gsd/tasks/prompts/L1-TASK-004-prompt-templates.md |
| MEDIUM | .gsd/sessions/2026-01-26-test-coverage.md | 82 | Duplicated block (34 lines, 0 tokens) between .gsd/sessions/2026-01-26-test-coverage.md and .gsd/tasks/test-coverage/COMPLETE.md |
| MEDIUM | zerg/orchestrator.py | 651 | Duplicated block (22 lines, 0 tokens) between zerg/orchestrator.py and zerg/orchestrator.py |
| MEDIUM | zerg/orchestrator.py | 673 | Duplicated block (22 lines, 0 tokens) between zerg/orchestrator.py and zerg/orchestrator.py |
| MEDIUM | zerg/orchestrator.py | 694 | Duplicated block (33 lines, 0 tokens) between zerg/orchestrator.py and zerg/orchestrator.py |
| MEDIUM | zerg/orchestrator.py | 789 | Duplicated block (44 lines, 0 tokens) between zerg/orchestrator.py and zerg/orchestrator.py |
| MEDIUM | zerg/orchestrator.py | 858 | Duplicated block (30 lines, 0 tokens) between zerg/orchestrator.py and zerg/orchestrator.py |
| MEDIUM | tests/test_worker_protocol.py | 413 | Duplicated block (25 lines, 0 tokens) between tests/test_worker_protocol.py and tests/test_worker_protocol.py |
| MEDIUM | tests/test_orchestrator.py | 51 | Duplicated block (36 lines, 0 tokens) between tests/test_orchestrator.py and tests/unit/test_orchestrator_recovery.py |
| MEDIUM | htmlcov/z_5ded25b5ad8e2eac_stop_py.html | 14 | Duplicated block (44 lines, 0 tokens) between htmlcov/z_5ded25b5ad8e2eac_stop_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| MEDIUM | htmlcov/z_5ded25b5ad8e2eac_security_rules_cmd_py.html | 14 | Duplicated block (44 lines, 0 tokens) between htmlcov/z_5ded25b5ad8e2eac_security_rules_cmd_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| MEDIUM | htmlcov/z_5ded25b5ad8e2eac_rush_py.html | 14 | Duplicated block (44 lines, 0 tokens) between htmlcov/z_5ded25b5ad8e2eac_rush_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| MEDIUM | htmlcov/z_5ded25b5ad8e2eac_retry_py.html | 14 | Duplicated block (44 lines, 0 tokens) between htmlcov/z_5ded25b5ad8e2eac_retry_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| MEDIUM | htmlcov/z_5ded25b5ad8e2eac_merge_cmd_py.html | 14 | Duplicated block (44 lines, 0 tokens) between htmlcov/z_5ded25b5ad8e2eac_merge_cmd_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| MEDIUM | htmlcov/z_5ded25b5ad8e2eac_install_commands_py.html | 15 | Duplicated block (43 lines, 0 tokens) between htmlcov/z_5ded25b5ad8e2eac_install_commands_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| MEDIUM | htmlcov/z_5ded25b5ad8e2eac_cleanup_py.html | 14 | Duplicated block (44 lines, 0 tokens) between htmlcov/z_5ded25b5ad8e2eac_cleanup_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| MEDIUM | htmlcov/z_5ded25b5ad8e2eac___init___py.html | 14 | Duplicated block (44 lines, 0 tokens) between htmlcov/z_5ded25b5ad8e2eac___init___py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| MEDIUM | htmlcov/z_4dc1c953114105d3_system_diagnostics_py.html | 15 | Duplicated block (43 lines, 0 tokens) between htmlcov/z_4dc1c953114105d3_system_diagnostics_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| MEDIUM | htmlcov/z_4dc1c953114105d3_state_introspector_py.html | 15 | Duplicated block (43 lines, 0 tokens) between htmlcov/z_4dc1c953114105d3_state_introspector_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| MEDIUM | htmlcov/z_4dc1c953114105d3_recovery_py.html | 15 | Duplicated block (43 lines, 0 tokens) between htmlcov/z_4dc1c953114105d3_recovery_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| MEDIUM | htmlcov/z_4dc1c953114105d3_log_analyzer_py.html | 14 | Duplicated block (44 lines, 0 tokens) between htmlcov/z_4dc1c953114105d3_log_analyzer_py.html and htmlcov/z_4dc1c953114105d3_system_diagnostics_py.html |
| MEDIUM | htmlcov/z_4dc1c953114105d3___init___py.html | 14 | Duplicated block (44 lines, 0 tokens) between htmlcov/z_4dc1c953114105d3___init___py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| MEDIUM | htmlcov/z_2f9928aca2d82036_worktree_py.html | 14 | Duplicated block (44 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_worktree_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| MEDIUM | htmlcov/z_2f9928aca2d82036_worker_main_py.html | 14 | Duplicated block (44 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_worker_main_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| MEDIUM | htmlcov/z_2f9928aca2d82036_verify_py.html | 14 | Duplicated block (44 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_verify_py.html and htmlcov/z_4dc1c953114105d3_state_introspector_py.html |
| MEDIUM | htmlcov/z_2f9928aca2d82036_task_sync_py.html | 14 | Duplicated block (44 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_task_sync_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| MEDIUM | htmlcov/z_2f9928aca2d82036_spec_loader_py.html | 15 | Duplicated block (43 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_spec_loader_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| MEDIUM | htmlcov/z_2f9928aca2d82036_security_py.html | 15 | Duplicated block (43 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_security_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| MEDIUM | htmlcov/z_2f9928aca2d82036_ports_py.html | 15 | Duplicated block (44 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_ports_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| MEDIUM | htmlcov/z_2f9928aca2d82036_parser_py.html | 14 | Duplicated block (44 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_parser_py.html and htmlcov/z_2f9928aca2d82036_ports_py.html |
| MEDIUM | htmlcov/z_2f9928aca2d82036_metrics_py.html | 14 | Duplicated block (44 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_metrics_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| MEDIUM | htmlcov/z_2f9928aca2d82036_merge_py.html | 14 | Duplicated block (44 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_merge_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| MEDIUM | htmlcov/z_2f9928aca2d82036_logging_py.html | 14 | Duplicated block (44 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_logging_py.html and htmlcov/z_4dc1c953114105d3_system_diagnostics_py.html |
| MEDIUM | htmlcov/z_2f9928aca2d82036_levels_py.html | 14 | Duplicated block (50 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_levels_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| MEDIUM | htmlcov/z_2f9928aca2d82036_gates_py.html | 15 | Duplicated block (43 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_gates_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| MEDIUM | htmlcov/z_2f9928aca2d82036_exceptions_py.html | 14 | Duplicated block (44 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_exceptions_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| MEDIUM | htmlcov/z_2f9928aca2d82036_context_tracker_py.html | 14 | Duplicated block (44 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_context_tracker_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| MEDIUM | htmlcov/z_2f9928aca2d82036_constants_py.html | 14 | Duplicated block (44 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_constants_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| MEDIUM | htmlcov/z_2f9928aca2d82036_config_py.html | 14 | Duplicated block (44 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_config_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| MEDIUM | htmlcov/z_2f9928aca2d82036_cli_py.html | 14 | Duplicated block (44 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_cli_py.html and htmlcov/z_4dc1c953114105d3_recovery_py.html |
| MEDIUM | htmlcov/z_2f9928aca2d82036_assign_py.html | 14 | Duplicated block (44 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_assign_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| MEDIUM | htmlcov/z_2f9928aca2d82036___main___py.html | 14 | Duplicated block (44 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036___main___py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| MEDIUM | htmlcov/z_2f9928aca2d82036___init___py.html | 14 | Duplicated block (44 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036___init___py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| MEDIUM | claudedocs/zerg_scratch.md | 325 | Duplicated block (26 lines, 0 tokens) between claudedocs/zerg_scratch.md and claudedocs/zerg_scratch.md |
| MEDIUM | claudedocs/zerg_scratch.md | 359 | Duplicated block (26 lines, 0 tokens) between claudedocs/zerg_scratch.md and claudedocs/zerg_scratch.md |
| MEDIUM | claudedocs/zerg_scratch.md | 385 | Duplicated block (26 lines, 0 tokens) between claudedocs/zerg_scratch.md and claudedocs/zerg_scratch.md |
| MEDIUM | claudedocs/zerg_scratch.md | 457 | Duplicated block (25 lines, 0 tokens) between claudedocs/zerg_scratch.md and claudedocs/zerg_scratch.md |
| MEDIUM | claudedocs/zerg_scratch.md | 510 | Duplicated block (23 lines, 0 tokens) between claudedocs/zerg_scratch.md and claudedocs/zerg_scratch.md |
| MEDIUM | .zerg/test_runner.py | 14 | Duplicated block (45 lines, 0 tokens) between .zerg/test_runner.py and zerg/commands/test_cmd.py |
| MEDIUM | .zerg/test_runner.py | 226 | Duplicated block (22 lines, 0 tokens) between .zerg/test_runner.py and zerg/commands/test_cmd.py |
| MEDIUM | .zerg/test_runner.py | 269 | Duplicated block (22 lines, 0 tokens) between .zerg/test_runner.py and zerg/commands/test_cmd.py |
| MEDIUM | .zerg/review.py | 8 | Duplicated block (26 lines, 0 tokens) between .zerg/review.py and zerg/commands/review.py |
| MEDIUM | .zerg/review.py | 38 | Duplicated block (35 lines, 0 tokens) between .zerg/review.py and zerg/commands/review.py |
| MEDIUM | .zerg/review.py | 171 | Duplicated block (22 lines, 0 tokens) between .zerg/review.py and zerg/commands/review.py |
| MEDIUM | .zerg/refactor.py | 8 | Duplicated block (33 lines, 0 tokens) between .zerg/refactor.py and zerg/commands/refactor.py |
| MEDIUM | .zerg/refactor.py | 40 | Duplicated block (39 lines, 0 tokens) between .zerg/refactor.py and zerg/commands/refactor.py |
| MEDIUM | .zerg/refactor.py | 270 | Duplicated block (35 lines, 0 tokens) between .zerg/refactor.py and zerg/commands/refactor.py |
| MEDIUM | .zerg/build.py | 15 | Duplicated block (45 lines, 0 tokens) between .zerg/build.py and zerg/commands/build.py |
| MEDIUM | .zerg/build.py | 201 | Duplicated block (22 lines, 0 tokens) between .zerg/build.py and zerg/commands/build.py |
| MEDIUM | .zerg/build.py | 286 | Duplicated block (26 lines, 0 tokens) between .zerg/build.py and zerg/commands/build.py |
| MEDIUM | .zerg/analyze.py | 24 | Duplicated block (26 lines, 0 tokens) between .zerg/analyze.py and zerg/commands/analyze.py |
| MEDIUM | .zerg/analyze.py | 91 | Duplicated block (37 lines, 0 tokens) between .zerg/analyze.py and zerg/commands/analyze.py |
| MEDIUM | .zerg/analyze.py | 243 | Duplicated block (25 lines, 0 tokens) between .zerg/analyze.py and zerg/commands/analyze.py |
| LOW | zerg/performance/adapters/dive_adapter.py | 67 | Duplicated block (12 lines, 0 tokens) between zerg/performance/adapters/dive_adapter.py and zerg/performance/adapters/hadolint_adapter.py |
| LOW | tests/unit/test_diagnostics/test_recovery.py | 288 | Duplicated block (13 lines, 0 tokens) between tests/unit/test_diagnostics/test_recovery.py and tests/unit/test_diagnostics/test_recovery.py |
| LOW | tests/unit/test_diagnostics/test_error_intel.py | 230 | Duplicated block (10 lines, 0 tokens) between tests/unit/test_diagnostics/test_error_intel.py and tests/unit/test_diagnostics/test_error_intel.py |
| LOW | .gsd/specs/phase1/capability_matrix.md | 156 | Duplicated block (12 lines, 0 tokens) between .gsd/specs/phase1/capability_matrix.md and .gsd/specs/phase1/synthesis.md |
| LOW | zerg/diagnostics/log_analyzer.py | 128 | Duplicated block (10 lines, 0 tokens) between zerg/diagnostics/log_analyzer.py and zerg/diagnostics/log_analyzer.py |
| LOW | zerg/diagnostics/env_diagnostics.py | 109 | Duplicated block (17 lines, 0 tokens) between zerg/diagnostics/env_diagnostics.py and zerg/diagnostics/env_diagnostics.py |
| LOW | zerg/diagnostics/env_diagnostics.py | 172 | Duplicated block (10 lines, 0 tokens) between zerg/diagnostics/env_diagnostics.py and zerg/diagnostics/env_diagnostics.py |
| LOW | zerg/diagnostics/env_diagnostics.py | 217 | Duplicated block (17 lines, 0 tokens) between zerg/diagnostics/env_diagnostics.py and zerg/diagnostics/env_diagnostics.py |
| LOW | zerg/commands/test_cmd.py | 265 | Duplicated block (10 lines, 0 tokens) between zerg/commands/test_cmd.py and zerg/commands/test_cmd.py |
| LOW | zerg/commands/security_rules_cmd.py | 105 | Duplicated block (17 lines, 0 tokens) between zerg/commands/security_rules_cmd.py and zerg/commands/security_rules_cmd.py |
| LOW | tests/unit/test_worktree.py | 70 | Duplicated block (20 lines, 0 tokens) between tests/unit/test_worktree.py and tests/unit/test_worktree_extended.py |
| LOW | tests/unit/test_worktree.py | 171 | Duplicated block (17 lines, 0 tokens) between tests/unit/test_worktree.py and tests/unit/test_worktree_extended.py |
| LOW | tests/unit/test_worktree.py | 231 | Duplicated block (15 lines, 0 tokens) between tests/unit/test_worktree.py and tests/unit/test_worktree_extended.py |
| LOW | tests/unit/test_worktree.py | 275 | Duplicated block (16 lines, 0 tokens) between tests/unit/test_worktree.py and tests/unit/test_worktree_extended.py |
| LOW | tests/unit/test_worktree.py | 290 | Duplicated block (19 lines, 0 tokens) between tests/unit/test_worktree.py and tests/unit/test_worktree_extended.py |
| LOW | tests/unit/test_worktree.py | 331 | Duplicated block (18 lines, 0 tokens) between tests/unit/test_worktree.py and tests/unit/test_worktree_extended.py |
| LOW | tests/unit/test_worktree.py | 410 | Duplicated block (18 lines, 0 tokens) between tests/unit/test_worktree.py and tests/unit/test_worktree_extended.py |
| LOW | tests/unit/test_worktree.py | 535 | Duplicated block (12 lines, 0 tokens) between tests/unit/test_worktree.py and tests/unit/test_worktree_extended.py |
| LOW | tests/unit/test_worker_lifecycle.py | 182 | Duplicated block (15 lines, 0 tokens) between tests/unit/test_worker_lifecycle.py and tests/unit/test_worker_lifecycle.py |
| LOW | tests/unit/test_validation.py | 886 | Duplicated block (10 lines, 0 tokens) between tests/unit/test_validation.py and tests/unit/test_validation.py |
| LOW | tests/unit/test_state_sync.py | 108 | Duplicated block (18 lines, 0 tokens) between tests/unit/test_state_sync.py and tests/unit/test_worker_lifecycle.py |
| LOW | tests/unit/test_state.py | 71 | Duplicated block (10 lines, 0 tokens) between tests/unit/test_state.py and tests/unit/test_state_persistence.py |
| LOW | tests/unit/test_state.py | 228 | Duplicated block (11 lines, 0 tokens) between tests/unit/test_state.py and tests/unit/test_state_tasks.py |
| LOW | tests/unit/test_security_rules_cmd.py | 546 | Duplicated block (11 lines, 0 tokens) between tests/unit/test_security_rules_cmd.py and tests/unit/test_security_rules_cmd.py |
| LOW | tests/unit/test_security_rules_cmd.py | 713 | Duplicated block (17 lines, 0 tokens) between tests/unit/test_security_rules_cmd.py and tests/unit/test_security_rules_cmd.py |
| LOW | tests/unit/test_security_rules_cmd.py | 736 | Duplicated block (15 lines, 0 tokens) between tests/unit/test_security_rules_cmd.py and tests/unit/test_security_rules_cmd.py |
| LOW | tests/unit/test_schema_validation.py | 126 | Duplicated block (15 lines, 0 tokens) between tests/unit/test_schema_validation.py and tests/unit/test_schema_validation.py |
| LOW | tests/unit/test_schema_validation.py | 257 | Duplicated block (14 lines, 0 tokens) between tests/unit/test_schema_validation.py and tests/unit/test_schema_validation.py |
| LOW | tests/unit/test_risk_scoring.py | 104 | Duplicated block (10 lines, 0 tokens) between tests/unit/test_risk_scoring.py and tests/unit/test_risk_scoring.py |
| LOW | tests/unit/test_retry_cmd.py | 519 | Duplicated block (12 lines, 0 tokens) between tests/unit/test_retry_cmd.py and tests/unit/test_retry_cmd.py |
| LOW | tests/unit/test_retry_cmd.py | 547 | Duplicated block (12 lines, 0 tokens) between tests/unit/test_retry_cmd.py and tests/unit/test_retry_cmd.py |
| LOW | tests/unit/test_retry_cmd.py | 575 | Duplicated block (12 lines, 0 tokens) between tests/unit/test_retry_cmd.py and tests/unit/test_retry_cmd.py |
| LOW | tests/unit/test_retry_cmd.py | 595 | Duplicated block (19 lines, 0 tokens) between tests/unit/test_retry_cmd.py and tests/unit/test_retry_cmd.py |
| LOW | tests/unit/test_retry_cmd.py | 627 | Duplicated block (13 lines, 0 tokens) between tests/unit/test_retry_cmd.py and tests/unit/test_retry_cmd.py |
| LOW | tests/unit/test_retry_cmd.py | 655 | Duplicated block (10 lines, 0 tokens) between tests/unit/test_retry_cmd.py and tests/unit/test_retry_cmd.py |
| LOW | tests/unit/test_retry_cmd.py | 667 | Duplicated block (12 lines, 0 tokens) between tests/unit/test_retry_cmd.py and tests/unit/test_retry_cmd.py |
| LOW | tests/unit/test_retry_cmd.py | 689 | Duplicated block (20 lines, 0 tokens) between tests/unit/test_retry_cmd.py and tests/unit/test_retry_cmd.py |
| LOW | tests/unit/test_retry_cmd.py | 724 | Duplicated block (11 lines, 0 tokens) between tests/unit/test_retry_cmd.py and tests/unit/test_retry_cmd.py |
| LOW | tests/unit/test_retry_cmd.py | 745 | Duplicated block (20 lines, 0 tokens) between tests/unit/test_retry_cmd.py and tests/unit/test_retry_cmd.py |
| LOW | tests/unit/test_retry_cmd.py | 829 | Duplicated block (10 lines, 0 tokens) between tests/unit/test_retry_cmd.py and tests/unit/test_retry_cmd.py |
| LOW | tests/unit/test_plugins.py | 374 | Duplicated block (12 lines, 0 tokens) between tests/unit/test_plugins.py and tests/unit/test_plugins.py |
| LOW | tests/unit/test_performance_adapters.py | 266 | Duplicated block (13 lines, 0 tokens) between tests/unit/test_performance_adapters.py and tests/unit/test_performance_adapters.py |
| LOW | tests/unit/test_performance_adapters.py | 287 | Duplicated block (12 lines, 0 tokens) between tests/unit/test_performance_adapters.py and tests/unit/test_performance_adapters.py |
| LOW | tests/unit/test_performance_adapters.py | 454 | Duplicated block (10 lines, 0 tokens) between tests/unit/test_performance_adapters.py and tests/unit/test_performance_adapters.py |
| LOW | tests/unit/test_performance_adapters.py | 762 | Duplicated block (16 lines, 0 tokens) between tests/unit/test_performance_adapters.py and tests/unit/test_performance_adapters.py |
| LOW | tests/unit/test_performance_adapters.py | 793 | Duplicated block (16 lines, 0 tokens) between tests/unit/test_performance_adapters.py and tests/unit/test_performance_adapters.py |
| LOW | tests/unit/test_orchestrator_workers.py | 85 | Duplicated block (10 lines, 0 tokens) between tests/unit/test_orchestrator_workers.py and tests/unit/test_worker_manager_component.py |
| LOW | tests/unit/test_orchestrator_recovery.py | 52 | Duplicated block (17 lines, 0 tokens) between tests/unit/test_orchestrator_recovery.py and tests/unit/test_orchestrator_workers.py |
| LOW | tests/unit/test_orchestrator_recovery.py | 69 | Duplicated block (14 lines, 0 tokens) between tests/unit/test_orchestrator_recovery.py and tests/unit/test_orchestrator_workers.py |
| LOW | tests/unit/test_orchestrator_recovery.py | 83 | Duplicated block (19 lines, 0 tokens) between tests/unit/test_orchestrator_recovery.py and tests/unit/test_orchestrator_workers.py |
| LOW | tests/unit/test_orchestrator_recovery.py | 653 | Duplicated block (13 lines, 0 tokens) between tests/unit/test_orchestrator_recovery.py and tests/unit/test_orchestrator_recovery.py |
| LOW | tests/unit/test_orchestrator_levels.py | 58 | Duplicated block (16 lines, 0 tokens) between tests/unit/test_orchestrator_levels.py and tests/unit/test_orchestrator_workers.py |
| LOW | tests/unit/test_orchestrator_levels.py | 83 | Duplicated block (13 lines, 0 tokens) between tests/unit/test_orchestrator_levels.py and tests/unit/test_orchestrator_workers.py |
| LOW | tests/unit/test_orchestrator_levels.py | 146 | Duplicated block (12 lines, 0 tokens) between tests/unit/test_orchestrator_levels.py and tests/unit/test_orchestrator_workers.py |
| LOW | tests/unit/test_orchestrator_container_mode.py | 123 | Duplicated block (15 lines, 0 tokens) between tests/unit/test_orchestrator_container_mode.py and tests/unit/test_orchestrator_container_mode.py |
| LOW | tests/unit/test_orchestrator_container_mode.py | 167 | Duplicated block (15 lines, 0 tokens) between tests/unit/test_orchestrator_container_mode.py and tests/unit/test_orchestrator_container_mode.py |
| LOW | tests/unit/test_orchestrator_container_mode.py | 182 | Duplicated block (14 lines, 0 tokens) between tests/unit/test_orchestrator_container_mode.py and tests/unit/test_orchestrator_container_mode.py |
| LOW | tests/unit/test_orchestrator_container_mode.py | 207 | Duplicated block (15 lines, 0 tokens) between tests/unit/test_orchestrator_container_mode.py and tests/unit/test_orchestrator_container_mode.py |
| LOW | tests/unit/test_orchestrator_container_mode.py | 251 | Duplicated block (15 lines, 0 tokens) between tests/unit/test_orchestrator_container_mode.py and tests/unit/test_orchestrator_container_mode.py |
| LOW | tests/unit/test_orchestrator_container_mode.py | 271 | Duplicated block (12 lines, 0 tokens) between tests/unit/test_orchestrator_container_mode.py and tests/unit/test_orchestrator_container_mode.py |
| LOW | tests/unit/test_orchestrator_container_mode.py | 299 | Duplicated block (15 lines, 0 tokens) between tests/unit/test_orchestrator_container_mode.py and tests/unit/test_orchestrator_container_mode.py |
| LOW | tests/unit/test_orchestrator_container_mode.py | 320 | Duplicated block (16 lines, 0 tokens) between tests/unit/test_orchestrator_container_mode.py and tests/unit/test_orchestrator_container_mode.py |
| LOW | tests/unit/test_orchestrator_container_mode.py | 347 | Duplicated block (15 lines, 0 tokens) between tests/unit/test_orchestrator_container_mode.py and tests/unit/test_orchestrator_container_mode.py |
| LOW | tests/unit/test_orchestrator_container_mode.py | 368 | Duplicated block (17 lines, 0 tokens) between tests/unit/test_orchestrator_container_mode.py and tests/unit/test_orchestrator_container_mode.py |
| LOW | tests/unit/test_orchestrator_container_mode.py | 396 | Duplicated block (15 lines, 0 tokens) between tests/unit/test_orchestrator_container_mode.py and tests/unit/test_orchestrator_container_mode.py |
| LOW | tests/unit/test_orchestrator_container_mode.py | 441 | Duplicated block (14 lines, 0 tokens) between tests/unit/test_orchestrator_container_mode.py and tests/unit/test_orchestrator_container_mode.py |
| LOW | tests/unit/test_orchestrator_container_mode.py | 480 | Duplicated block (15 lines, 0 tokens) between tests/unit/test_orchestrator_container_mode.py and tests/unit/test_orchestrator_container_mode.py |
| LOW | tests/unit/test_orchestrator_container_mode.py | 522 | Duplicated block (15 lines, 0 tokens) between tests/unit/test_orchestrator_container_mode.py and tests/unit/test_orchestrator_container_mode.py |
| LOW | tests/unit/test_merge_gates.py | 88 | Duplicated block (18 lines, 0 tokens) between tests/unit/test_merge_gates.py and tests/unit/test_merge_gates.py |
| LOW | tests/unit/test_merge_gates.py | 129 | Duplicated block (18 lines, 0 tokens) between tests/unit/test_merge_gates.py and tests/unit/test_merge_gates.py |
| LOW | tests/unit/test_merge_gates.py | 185 | Duplicated block (16 lines, 0 tokens) between tests/unit/test_merge_gates.py and tests/unit/test_merge_gates.py |
| LOW | tests/unit/test_merge_gates.py | 209 | Duplicated block (11 lines, 0 tokens) between tests/unit/test_merge_gates.py and tests/unit/test_merge_gates.py |
| LOW | tests/unit/test_merge_gates.py | 228 | Duplicated block (19 lines, 0 tokens) between tests/unit/test_merge_gates.py and tests/unit/test_merge_gates.py |
| LOW | tests/unit/test_merge_gates.py | 271 | Duplicated block (16 lines, 0 tokens) between tests/unit/test_merge_gates.py and tests/unit/test_merge_gates.py |
| LOW | tests/unit/test_merge_gates.py | 314 | Duplicated block (15 lines, 0 tokens) between tests/unit/test_merge_gates.py and tests/unit/test_merge_gates.py |
| LOW | tests/unit/test_merge_gates.py | 438 | Duplicated block (17 lines, 0 tokens) between tests/unit/test_merge_gates.py and tests/unit/test_merge_gates.py |
| LOW | tests/unit/test_merge_gates.py | 514 | Duplicated block (15 lines, 0 tokens) between tests/unit/test_merge_gates.py and tests/unit/test_merge_gates.py |
| LOW | tests/unit/test_merge_gates.py | 673 | Duplicated block (17 lines, 0 tokens) between tests/unit/test_merge_gates.py and tests/unit/test_merge_gates.py |
| LOW | tests/unit/test_merge_gates.py | 755 | Duplicated block (18 lines, 0 tokens) between tests/unit/test_merge_gates.py and tests/unit/test_merge_gates.py |
| LOW | tests/unit/test_merge_full_flow.py | 214 | Duplicated block (12 lines, 0 tokens) between tests/unit/test_merge_full_flow.py and tests/unit/test_merge_full_flow.py |
| LOW | tests/unit/test_merge_full_flow.py | 239 | Duplicated block (14 lines, 0 tokens) between tests/unit/test_merge_full_flow.py and tests/unit/test_merge_full_flow.py |
| LOW | tests/unit/test_merge_full_flow.py | 303 | Duplicated block (14 lines, 0 tokens) between tests/unit/test_merge_full_flow.py and tests/unit/test_merge_full_flow.py |
| LOW | tests/unit/test_merge_full_flow.py | 356 | Duplicated block (19 lines, 0 tokens) between tests/unit/test_merge_full_flow.py and tests/unit/test_merge_full_flow.py |
| LOW | tests/unit/test_merge_full_flow.py | 405 | Duplicated block (18 lines, 0 tokens) between tests/unit/test_merge_full_flow.py and tests/unit/test_merge_full_flow.py |
| LOW | tests/unit/test_merge_full_flow.py | 479 | Duplicated block (16 lines, 0 tokens) between tests/unit/test_merge_full_flow.py and tests/unit/test_merge_full_flow.py |
| LOW | tests/unit/test_merge_full_flow.py | 543 | Duplicated block (19 lines, 0 tokens) between tests/unit/test_merge_full_flow.py and tests/unit/test_merge_full_flow.py |
| LOW | tests/unit/test_merge_full_flow.py | 655 | Duplicated block (11 lines, 0 tokens) between tests/unit/test_merge_full_flow.py and tests/unit/test_merge_full_flow.py |
| LOW | tests/unit/test_merge_full_flow.py | 656 | Duplicated block (13 lines, 0 tokens) between tests/unit/test_merge_full_flow.py and tests/unit/test_merge_full_flow.py |
| LOW | tests/unit/test_merge_full_flow.py | 683 | Duplicated block (17 lines, 0 tokens) between tests/unit/test_merge_full_flow.py and tests/unit/test_merge_full_flow.py |
| LOW | tests/unit/test_merge_full_flow.py | 708 | Duplicated block (17 lines, 0 tokens) between tests/unit/test_merge_full_flow.py and tests/unit/test_merge_full_flow.py |
| LOW | tests/unit/test_merge_full_flow.py | 733 | Duplicated block (17 lines, 0 tokens) between tests/unit/test_merge_full_flow.py and tests/unit/test_merge_full_flow.py |
| LOW | tests/unit/test_merge_full_flow.py | 770 | Duplicated block (17 lines, 0 tokens) between tests/unit/test_merge_full_flow.py and tests/unit/test_merge_full_flow.py |
| LOW | tests/unit/test_merge_execute.py | 204 | Duplicated block (12 lines, 0 tokens) between tests/unit/test_merge_execute.py and tests/unit/test_merge_execute.py |
| LOW | tests/unit/test_merge_execute.py | 286 | Duplicated block (15 lines, 0 tokens) between tests/unit/test_merge_execute.py and tests/unit/test_merge_execute.py |
| LOW | tests/unit/test_merge_execute.py | 308 | Duplicated block (11 lines, 0 tokens) between tests/unit/test_merge_execute.py and tests/unit/test_merge_execute.py |
| LOW | tests/unit/test_merge_cmd.py | 569 | Duplicated block (13 lines, 0 tokens) between tests/unit/test_merge_cmd.py and tests/unit/test_merge_cmd.py |
| LOW | tests/unit/test_merge_cmd.py | 601 | Duplicated block (12 lines, 0 tokens) between tests/unit/test_merge_cmd.py and tests/unit/test_merge_cmd.py |
| LOW | tests/unit/test_merge_cmd.py | 654 | Duplicated block (12 lines, 0 tokens) between tests/unit/test_merge_cmd.py and tests/unit/test_merge_cmd.py |
| LOW | tests/unit/test_merge_cmd.py | 680 | Duplicated block (13 lines, 0 tokens) between tests/unit/test_merge_cmd.py and tests/unit/test_merge_cmd.py |
| LOW | tests/unit/test_merge_cmd.py | 761 | Duplicated block (11 lines, 0 tokens) between tests/unit/test_merge_cmd.py and tests/unit/test_merge_cmd.py |
| LOW | tests/unit/test_merge_cmd.py | 775 | Duplicated block (14 lines, 0 tokens) between tests/unit/test_merge_cmd.py and tests/unit/test_merge_cmd.py |
| LOW | tests/unit/test_merge_cmd.py | 798 | Duplicated block (14 lines, 0 tokens) between tests/unit/test_merge_cmd.py and tests/unit/test_merge_cmd.py |
| LOW | tests/unit/test_logs_cmd_extended.py | 92 | Duplicated block (10 lines, 0 tokens) between tests/unit/test_logs_cmd_extended.py and tests/unit/test_logs_cmd_extended.py |
| LOW | tests/unit/test_logs_cmd_extended.py | 112 | Duplicated block (10 lines, 0 tokens) between tests/unit/test_logs_cmd_extended.py and tests/unit/test_logs_cmd_extended.py |
| LOW | tests/unit/test_logs_cmd_extended.py | 132 | Duplicated block (10 lines, 0 tokens) between tests/unit/test_logs_cmd_extended.py and tests/unit/test_logs_cmd_extended.py |
| LOW | tests/unit/test_logs_cmd_extended.py | 153 | Duplicated block (12 lines, 0 tokens) between tests/unit/test_logs_cmd_extended.py and tests/unit/test_logs_cmd_extended.py |
| LOW | tests/unit/test_logs_cmd_extended.py | 174 | Duplicated block (11 lines, 0 tokens) between tests/unit/test_logs_cmd_extended.py and tests/unit/test_logs_cmd_extended.py |
| LOW | tests/unit/test_logging_extended.py | 160 | Duplicated block (11 lines, 0 tokens) between tests/unit/test_logging_extended.py and tests/unit/test_logging_extended.py |
| LOW | tests/unit/test_launcher_process.py | 424 | Duplicated block (14 lines, 0 tokens) between tests/unit/test_launcher_process.py and tests/unit/test_launcher_process.py |
| LOW | tests/unit/test_launcher_process.py | 549 | Duplicated block (16 lines, 0 tokens) between tests/unit/test_launcher_process.py and tests/unit/test_launcher_process.py |
| LOW | tests/unit/test_launcher_process.py | 608 | Duplicated block (16 lines, 0 tokens) between tests/unit/test_launcher_process.py and tests/unit/test_launcher_process.py |
| LOW | tests/unit/test_launcher_network.py | 164 | Duplicated block (16 lines, 0 tokens) between tests/unit/test_launcher_network.py and tests/unit/test_launcher_network.py |
| LOW | tests/unit/test_launcher_network.py | 422 | Duplicated block (10 lines, 0 tokens) between tests/unit/test_launcher_network.py and tests/unit/test_launcher_network.py |
| LOW | tests/unit/test_launcher_extended.py | 509 | Duplicated block (15 lines, 0 tokens) between tests/unit/test_launcher_extended.py and tests/unit/test_launcher_extended.py |
| LOW | tests/unit/test_launcher_exec.py | 108 | Duplicated block (11 lines, 0 tokens) between tests/unit/test_launcher_exec.py and tests/unit/test_launcher_process.py |
| LOW | tests/unit/test_launcher_errors.py | 332 | Duplicated block (15 lines, 0 tokens) between tests/unit/test_launcher_errors.py and tests/unit/test_launcher_network.py |
| LOW | tests/unit/test_charter.py | 3 | Duplicated block (19 lines, 0 tokens) between tests/unit/test_charter.py and tests/unit/test_charter_full.py |
| LOW | tests/unit/test_charter.py | 43 | Duplicated block (17 lines, 0 tokens) between tests/unit/test_charter.py and tests/unit/test_charter_full.py |
| LOW | tests/unit/test_charter.py | 59 | Duplicated block (19 lines, 0 tokens) between tests/unit/test_charter.py and tests/unit/test_charter_full.py |
| LOW | tests/unit/test_charter.py | 246 | Duplicated block (20 lines, 0 tokens) between tests/unit/test_charter.py and tests/unit/test_charter_full.py |
| LOW | tests/integration/test_worker_protocol_extended.py | 207 | Duplicated block (13 lines, 0 tokens) between tests/integration/test_worker_protocol_extended.py and tests/integration/test_worker_protocol_extended.py |
| LOW | tests/integration/test_worker_protocol_extended.py | 329 | Duplicated block (20 lines, 0 tokens) between tests/integration/test_worker_protocol_extended.py and tests/integration/test_worker_protocol_extended.py |
| LOW | tests/integration/test_worker_protocol_extended.py | 362 | Duplicated block (11 lines, 0 tokens) between tests/integration/test_worker_protocol_extended.py and tests/integration/test_worker_protocol_extended.py |
| LOW | tests/integration/test_worker_protocol_extended.py | 383 | Duplicated block (12 lines, 0 tokens) between tests/integration/test_worker_protocol_extended.py and tests/integration/test_worker_protocol_extended.py |
| LOW | tests/integration/test_worker_protocol_extended.py | 403 | Duplicated block (12 lines, 0 tokens) between tests/integration/test_worker_protocol_extended.py and tests/integration/test_worker_protocol_extended.py |
| LOW | tests/integration/test_worker_protocol_extended.py | 499 | Duplicated block (10 lines, 0 tokens) between tests/integration/test_worker_protocol_extended.py and tests/integration/test_worker_protocol_extended.py |
| LOW | tests/integration/test_spec_injection.py | 137 | Duplicated block (16 lines, 0 tokens) between tests/integration/test_spec_injection.py and tests/integration/test_spec_injection.py |
| LOW | tests/integration/test_spec_injection.py | 177 | Duplicated block (15 lines, 0 tokens) between tests/integration/test_spec_injection.py and tests/integration/test_spec_injection.py |
| LOW | tests/integration/test_spec_injection.py | 225 | Duplicated block (10 lines, 0 tokens) between tests/integration/test_spec_injection.py and tests/integration/test_spec_injection.py |
| LOW | tests/integration/test_plan_design.py | 289 | Duplicated block (13 lines, 0 tokens) between tests/integration/test_plan_design.py and tests/integration/test_plan_design.py |
| LOW | tests/integration/test_orchestrator_integration.py | 206 | Duplicated block (16 lines, 0 tokens) between tests/integration/test_orchestrator_integration.py and tests/integration/test_orchestrator_integration.py |
| LOW | tests/integration/test_orchestrator_integration.py | 367 | Duplicated block (18 lines, 0 tokens) between tests/integration/test_orchestrator_integration.py and tests/integration/test_orchestrator_integration.py |
| LOW | tests/integration/test_orchestrator_integration.py | 431 | Duplicated block (17 lines, 0 tokens) between tests/integration/test_orchestrator_integration.py and tests/integration/test_orchestrator_integration.py |
| LOW | tests/integration/test_orchestrator_integration.py | 458 | Duplicated block (14 lines, 0 tokens) between tests/integration/test_orchestrator_integration.py and tests/integration/test_orchestrator_integration.py |
| LOW | tests/integration/test_orchestrator_integration.py | 498 | Duplicated block (12 lines, 0 tokens) between tests/integration/test_orchestrator_integration.py and tests/integration/test_orchestrator_integration.py |
| LOW | tests/integration/test_orchestrator_integration.py | 556 | Duplicated block (20 lines, 0 tokens) between tests/integration/test_orchestrator_integration.py and tests/integration/test_orchestrator_integration.py |
| LOW | tests/integration/test_orchestrator_integration.py | 622 | Duplicated block (10 lines, 0 tokens) between tests/integration/test_orchestrator_integration.py and tests/integration/test_orchestrator_integration.py |
| LOW | tests/integration/test_orchestrator_integration.py | 690 | Duplicated block (14 lines, 0 tokens) between tests/integration/test_orchestrator_integration.py and tests/integration/test_orchestrator_integration.py |
| LOW | tests/integration/test_orchestrator_integration.py | 744 | Duplicated block (10 lines, 0 tokens) between tests/integration/test_orchestrator_integration.py and tests/integration/test_orchestrator_integration.py |
| LOW | tests/integration/test_orchestrator_integration.py | 745 | Duplicated block (13 lines, 0 tokens) between tests/integration/test_orchestrator_integration.py and tests/integration/test_orchestrator_integration.py |
| LOW | tests/integration/test_orchestrator_integration.py | 813 | Duplicated block (12 lines, 0 tokens) between tests/integration/test_orchestrator_integration.py and tests/integration/test_orchestrator_integration.py |
| LOW | tests/integration/test_orchestrator_integration.py | 860 | Duplicated block (12 lines, 0 tokens) between tests/integration/test_orchestrator_integration.py and tests/integration/test_orchestrator_integration.py |
| LOW | tests/integration/test_orchestrator_integration.py | 864 | Duplicated block (13 lines, 0 tokens) between tests/integration/test_orchestrator_integration.py and tests/integration/test_orchestrator_integration.py |
| LOW | tests/integration/test_orchestrator_integration.py | 917 | Duplicated block (18 lines, 0 tokens) between tests/integration/test_orchestrator_integration.py and tests/integration/test_orchestrator_integration.py |
| LOW | tests/integration/test_orchestrator_integration.py | 948 | Duplicated block (20 lines, 0 tokens) between tests/integration/test_orchestrator_integration.py and tests/integration/test_orchestrator_integration.py |
| LOW | tests/integration/test_merge_integration.py | 8 | Duplicated block (11 lines, 0 tokens) between tests/integration/test_merge_integration.py and tests/unit/test_merge_full_flow.py |
| LOW | tests/integration/test_level_advancement.py | 28 | Duplicated block (17 lines, 0 tokens) between tests/integration/test_level_advancement.py and tests/unit/test_orchestrator_workers.py |
| LOW | tests/integration/test_level_advancement.py | 183 | Duplicated block (13 lines, 0 tokens) between tests/integration/test_level_advancement.py and tests/integration/test_level_advancement.py |
| LOW | tests/integration/test_git_ops_extended.py | 19 | Duplicated block (10 lines, 0 tokens) between tests/integration/test_git_ops_extended.py and tests/unit/test_worktree_extended.py |
| LOW | tests/integration/test_full_rush_cycle.py | 255 | Duplicated block (11 lines, 0 tokens) between tests/integration/test_full_rush_cycle.py and tests/unit/test_schema_validation.py |
| LOW | tests/integration/test_container_startup.py | 318 | Duplicated block (16 lines, 0 tokens) between tests/integration/test_container_startup.py and tests/integration/test_container_startup.py |
| LOW | tests/fixtures/orchestrator_fixtures.py | 112 | Duplicated block (18 lines, 0 tokens) between tests/fixtures/orchestrator_fixtures.py and tests/unit/test_orchestrator_workers.py |
| LOW | tests/e2e/test_subprocess_e2e.py | 42 | Duplicated block (13 lines, 0 tokens) between tests/e2e/test_subprocess_e2e.py and tests/unit/test_orchestrator_workers.py |
| LOW | tests/e2e/test_subprocess_e2e.py | 86 | Duplicated block (15 lines, 0 tokens) between tests/e2e/test_subprocess_e2e.py and tests/unit/test_orchestrator_workers.py |
| LOW | tests/e2e/test_multilevel_execution.py | 126 | Duplicated block (19 lines, 0 tokens) between tests/e2e/test_multilevel_execution.py and tests/e2e/test_subprocess_e2e.py |
| LOW | tests/e2e/test_container_e2e.py | 69 | Duplicated block (20 lines, 0 tokens) between tests/e2e/test_container_e2e.py and tests/e2e/test_multilevel_execution.py |
| LOW | tests/e2e/test_bugfix_e2e.py | 414 | Duplicated block (15 lines, 0 tokens) between tests/e2e/test_bugfix_e2e.py and tests/e2e/test_bugfix_e2e.py |
| LOW | tests/e2e/conftest.py | 147 | Duplicated block (14 lines, 0 tokens) between tests/e2e/conftest.py and tests/e2e/harness.py |
| LOW | .zerg/tests/test_task_graph.py | 69 | Duplicated block (14 lines, 0 tokens) between .zerg/tests/test_task_graph.py and .zerg/tests/test_task_graph.py |
| LOW | .zerg/tests/test_task_graph.py | 141 | Duplicated block (15 lines, 0 tokens) between .zerg/tests/test_task_graph.py and .zerg/tests/test_task_graph.py |
| LOW | .zerg/tests/test_task_graph.py | 248 | Duplicated block (12 lines, 0 tokens) between .zerg/tests/test_task_graph.py and .zerg/tests/test_task_graph.py |
| LOW | .zerg/tests/test_task_graph.py | 270 | Duplicated block (15 lines, 0 tokens) between .zerg/tests/test_task_graph.py and .zerg/tests/test_task_graph.py |
| LOW | .zerg/tests/test_task_graph.py | 288 | Duplicated block (15 lines, 0 tokens) between .zerg/tests/test_task_graph.py and .zerg/tests/test_task_graph.py |
| LOW | .zerg/tests/test_task_graph.py | 311 | Duplicated block (10 lines, 0 tokens) between .zerg/tests/test_task_graph.py and .zerg/tests/test_task_graph.py |
| LOW | .zerg/tests/test_task_graph.py | 323 | Duplicated block (11 lines, 0 tokens) between .zerg/tests/test_task_graph.py and .zerg/tests/test_task_graph.py |
| LOW | .zerg/tests/test_task_graph.py | 345 | Duplicated block (10 lines, 0 tokens) between .zerg/tests/test_task_graph.py and .zerg/tests/test_task_graph.py |
| LOW | .zerg/tests/test_task_graph.py | 354 | Duplicated block (12 lines, 0 tokens) between .zerg/tests/test_task_graph.py and .zerg/tests/test_task_graph.py |
| LOW | .zerg/tests/test_task_graph.py | 386 | Duplicated block (12 lines, 0 tokens) between .zerg/tests/test_task_graph.py and .zerg/tests/test_task_graph.py |
| LOW | .zerg/tests/test_rush.py | 204 | Duplicated block (14 lines, 0 tokens) between .zerg/tests/test_rush.py and .zerg/tests/test_rush.py |
| LOW | .zerg/tests/test_rush.py | 269 | Duplicated block (20 lines, 0 tokens) between .zerg/tests/test_rush.py and .zerg/tests/test_rush.py |
| LOW | .zerg/tests/test_gates.py | 74 | Duplicated block (15 lines, 0 tokens) between .zerg/tests/test_gates.py and .zerg/tests/test_gates.py |
| LOW | .zerg/tests/test_gates.py | 134 | Duplicated block (11 lines, 0 tokens) between .zerg/tests/test_gates.py and .zerg/tests/test_gates.py |
| LOW | .zerg/tests/test_gates.py | 235 | Duplicated block (13 lines, 0 tokens) between .zerg/tests/test_gates.py and .zerg/tests/test_gates.py |
| LOW | .zerg/tests/test_gates.py | 260 | Duplicated block (16 lines, 0 tokens) between .zerg/tests/test_gates.py and .zerg/tests/test_gates.py |
| LOW | .zerg/tests/test_gates.py | 282 | Duplicated block (15 lines, 0 tokens) between .zerg/tests/test_gates.py and .zerg/tests/test_gates.py |
| LOW | .zerg/schemas/state.schema.json | 24 | Duplicated block (11 lines, 0 tokens) between .zerg/schemas/state.schema.json and .zerg/schemas/task.schema.json |
| LOW | zerg/state.py | 194 | Duplicated block (20 lines, 0 tokens) between zerg/state.py and tests/mocks/mock_state.py |
| LOW | zerg/state.py | 223 | Duplicated block (18 lines, 0 tokens) between zerg/state.py and tests/mocks/mock_state.py |
| LOW | zerg/state.py | 244 | Duplicated block (20 lines, 0 tokens) between zerg/state.py and tests/mocks/mock_state.py |
| LOW | zerg/state.py | 319 | Duplicated block (13 lines, 0 tokens) between zerg/state.py and tests/mocks/mock_state.py |
| LOW | zerg/state.py | 356 | Duplicated block (14 lines, 0 tokens) between zerg/state.py and tests/mocks/mock_state.py |
| LOW | zerg/state.py | 423 | Duplicated block (18 lines, 0 tokens) between zerg/state.py and tests/mocks/mock_state.py |
| LOW | zerg/state.py | 532 | Duplicated block (20 lines, 0 tokens) between zerg/state.py and tests/mocks/mock_state.py |
| LOW | zerg/state.py | 551 | Duplicated block (18 lines, 0 tokens) between zerg/state.py and zerg/state.py |
| LOW | zerg/state.py | 682 | Duplicated block (12 lines, 0 tokens) between zerg/state.py and tests/mocks/mock_state.py |
| LOW | zerg/state.py | 720 | Duplicated block (11 lines, 0 tokens) between zerg/state.py and zerg/state.py |
| LOW | zerg/state.py | 778 | Duplicated block (19 lines, 0 tokens) between zerg/state.py and tests/mocks/mock_state.py |
| LOW | zerg/containers.py | 507 | Duplicated block (17 lines, 0 tokens) between zerg/containers.py and zerg/containers.py |
| LOW | tests/test_worker_protocol.py | 44 | Duplicated block (16 lines, 0 tokens) between tests/test_worker_protocol.py and tests/unit/test_worker_lifecycle.py |
| LOW | tests/test_worker_protocol.py | 360 | Duplicated block (14 lines, 0 tokens) between tests/test_worker_protocol.py and tests/test_worker_protocol.py |
| LOW | tests/test_worker_protocol.py | 388 | Duplicated block (17 lines, 0 tokens) between tests/test_worker_protocol.py and tests/test_worker_protocol.py |
| LOW | tests/test_worker_protocol.py | 545 | Duplicated block (11 lines, 0 tokens) between tests/test_worker_protocol.py and tests/test_worker_protocol.py |
| LOW | tests/test_state.py | 67 | Duplicated block (11 lines, 0 tokens) between tests/test_state.py and tests/unit/test_state_extended.py |
| LOW | tests/test_state.py | 88 | Duplicated block (10 lines, 0 tokens) between tests/test_state.py and tests/unit/test_state.py |
| LOW | tests/test_state.py | 169 | Duplicated block (12 lines, 0 tokens) between tests/test_state.py and tests/unit/test_state_extended.py |
| LOW | tests/test_state.py | 188 | Duplicated block (13 lines, 0 tokens) between tests/test_state.py and tests/unit/test_state_extended.py |
| LOW | tests/test_orchestrator.py | 14 | Duplicated block (17 lines, 0 tokens) between tests/test_orchestrator.py and tests/unit/test_orchestrator_workers.py |
| LOW | tests/test_orchestrator.py | 38 | Duplicated block (15 lines, 0 tokens) between tests/test_orchestrator.py and tests/unit/test_orchestrator_workers.py |
| LOW | tests/test_orchestrator.py | 86 | Duplicated block (19 lines, 0 tokens) between tests/test_orchestrator.py and tests/unit/test_orchestrator_levels.py |
| LOW | tests/test_levels.py | 174 | Duplicated block (16 lines, 0 tokens) between tests/test_levels.py and tests/integration/test_rush_flow.py |
| LOW | tests/test_launcher.py | 20 | Duplicated block (11 lines, 0 tokens) between tests/test_launcher.py and tests/unit/test_launcher_extended.py |
| LOW | tests/test_launcher.py | 272 | Duplicated block (14 lines, 0 tokens) between tests/test_launcher.py and tests/test_launcher.py |
| LOW | tests/test_launcher.py | 352 | Duplicated block (10 lines, 0 tokens) between tests/test_launcher.py and tests/integration/test_container_lifecycle.py |
| LOW | tests/test_git_ops.py | 71 | Duplicated block (11 lines, 0 tokens) between tests/test_git_ops.py and tests/unit/test_git_ops.py |
| LOW | tests/test_git_ops.py | 130 | Duplicated block (10 lines, 0 tokens) between tests/test_git_ops.py and tests/unit/test_git_ops.py |
| LOW | tests/test_git_ops.py | 141 | Duplicated block (16 lines, 0 tokens) between tests/test_git_ops.py and tests/unit/test_git_ops.py |
| LOW | tests/test_git_ops.py | 241 | Duplicated block (13 lines, 0 tokens) between tests/test_git_ops.py and tests/unit/test_git_ops.py |
| LOW | tests/test_config.py | 125 | Duplicated block (13 lines, 0 tokens) between tests/test_config.py and tests/unit/test_config.py |
| LOW | htmlcov/z_5ded25b5ad8e2eac_stop_py.html | 5 | Duplicated block (10 lines, 0 tokens) between htmlcov/z_5ded25b5ad8e2eac_stop_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_5ded25b5ad8e2eac_stop_py.html | 65 | Duplicated block (19 lines, 0 tokens) between htmlcov/z_5ded25b5ad8e2eac_stop_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_5ded25b5ad8e2eac_security_rules_cmd_py.html | 5 | Duplicated block (10 lines, 0 tokens) between htmlcov/z_5ded25b5ad8e2eac_security_rules_cmd_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_5ded25b5ad8e2eac_security_rules_cmd_py.html | 65 | Duplicated block (19 lines, 0 tokens) between htmlcov/z_5ded25b5ad8e2eac_security_rules_cmd_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_5ded25b5ad8e2eac_rush_py.html | 5 | Duplicated block (10 lines, 0 tokens) between htmlcov/z_5ded25b5ad8e2eac_rush_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_5ded25b5ad8e2eac_rush_py.html | 65 | Duplicated block (19 lines, 0 tokens) between htmlcov/z_5ded25b5ad8e2eac_rush_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_5ded25b5ad8e2eac_retry_py.html | 5 | Duplicated block (10 lines, 0 tokens) between htmlcov/z_5ded25b5ad8e2eac_retry_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_5ded25b5ad8e2eac_retry_py.html | 65 | Duplicated block (19 lines, 0 tokens) between htmlcov/z_5ded25b5ad8e2eac_retry_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_5ded25b5ad8e2eac_merge_cmd_py.html | 5 | Duplicated block (10 lines, 0 tokens) between htmlcov/z_5ded25b5ad8e2eac_merge_cmd_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_5ded25b5ad8e2eac_merge_cmd_py.html | 65 | Duplicated block (19 lines, 0 tokens) between htmlcov/z_5ded25b5ad8e2eac_merge_cmd_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_5ded25b5ad8e2eac_merge_cmd_py.html | 83 | Duplicated block (10 lines, 0 tokens) between htmlcov/z_5ded25b5ad8e2eac_merge_cmd_py.html and htmlcov/z_5ded25b5ad8e2eac_rush_py.html |
| LOW | htmlcov/z_5ded25b5ad8e2eac_merge_cmd_py.html | 132 | Duplicated block (11 lines, 0 tokens) between htmlcov/z_5ded25b5ad8e2eac_merge_cmd_py.html and htmlcov/z_5ded25b5ad8e2eac_stop_py.html |
| LOW | htmlcov/z_5ded25b5ad8e2eac_install_commands_py.html | 5 | Duplicated block (10 lines, 0 tokens) between htmlcov/z_5ded25b5ad8e2eac_install_commands_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_5ded25b5ad8e2eac_install_commands_py.html | 65 | Duplicated block (19 lines, 0 tokens) between htmlcov/z_5ded25b5ad8e2eac_install_commands_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_5ded25b5ad8e2eac_cleanup_py.html | 5 | Duplicated block (10 lines, 0 tokens) between htmlcov/z_5ded25b5ad8e2eac_cleanup_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_5ded25b5ad8e2eac_cleanup_py.html | 65 | Duplicated block (19 lines, 0 tokens) between htmlcov/z_5ded25b5ad8e2eac_cleanup_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_5ded25b5ad8e2eac_cleanup_py.html | 83 | Duplicated block (11 lines, 0 tokens) between htmlcov/z_5ded25b5ad8e2eac_cleanup_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_5ded25b5ad8e2eac___init___py.html | 5 | Duplicated block (10 lines, 0 tokens) between htmlcov/z_5ded25b5ad8e2eac___init___py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_5ded25b5ad8e2eac___init___py.html | 65 | Duplicated block (19 lines, 0 tokens) between htmlcov/z_5ded25b5ad8e2eac___init___py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_4dc1c953114105d3_system_diagnostics_py.html | 5 | Duplicated block (10 lines, 0 tokens) between htmlcov/z_4dc1c953114105d3_system_diagnostics_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_4dc1c953114105d3_system_diagnostics_py.html | 65 | Duplicated block (19 lines, 0 tokens) between htmlcov/z_4dc1c953114105d3_system_diagnostics_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_4dc1c953114105d3_state_introspector_py.html | 5 | Duplicated block (10 lines, 0 tokens) between htmlcov/z_4dc1c953114105d3_state_introspector_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_4dc1c953114105d3_state_introspector_py.html | 65 | Duplicated block (19 lines, 0 tokens) between htmlcov/z_4dc1c953114105d3_state_introspector_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_4dc1c953114105d3_recovery_py.html | 5 | Duplicated block (10 lines, 0 tokens) between htmlcov/z_4dc1c953114105d3_recovery_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_4dc1c953114105d3_recovery_py.html | 65 | Duplicated block (19 lines, 0 tokens) between htmlcov/z_4dc1c953114105d3_recovery_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_4dc1c953114105d3_log_analyzer_py.html | 5 | Duplicated block (10 lines, 0 tokens) between htmlcov/z_4dc1c953114105d3_log_analyzer_py.html and htmlcov/z_4dc1c953114105d3_system_diagnostics_py.html |
| LOW | htmlcov/z_4dc1c953114105d3_log_analyzer_py.html | 65 | Duplicated block (19 lines, 0 tokens) between htmlcov/z_4dc1c953114105d3_log_analyzer_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_4dc1c953114105d3___init___py.html | 5 | Duplicated block (10 lines, 0 tokens) between htmlcov/z_4dc1c953114105d3___init___py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_4dc1c953114105d3___init___py.html | 65 | Duplicated block (19 lines, 0 tokens) between htmlcov/z_4dc1c953114105d3___init___py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_2f9928aca2d82036_worktree_py.html | 5 | Duplicated block (10 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_worktree_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_2f9928aca2d82036_worktree_py.html | 65 | Duplicated block (19 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_worktree_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_2f9928aca2d82036_worker_main_py.html | 5 | Duplicated block (10 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_worker_main_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_2f9928aca2d82036_worker_main_py.html | 65 | Duplicated block (19 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_worker_main_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_2f9928aca2d82036_verify_py.html | 5 | Duplicated block (10 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_verify_py.html and htmlcov/z_4dc1c953114105d3_state_introspector_py.html |
| LOW | htmlcov/z_2f9928aca2d82036_verify_py.html | 65 | Duplicated block (19 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_verify_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_2f9928aca2d82036_task_sync_py.html | 5 | Duplicated block (10 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_task_sync_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_2f9928aca2d82036_task_sync_py.html | 65 | Duplicated block (19 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_task_sync_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_2f9928aca2d82036_spec_loader_py.html | 5 | Duplicated block (10 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_spec_loader_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_2f9928aca2d82036_spec_loader_py.html | 65 | Duplicated block (19 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_spec_loader_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_2f9928aca2d82036_security_py.html | 5 | Duplicated block (10 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_security_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_2f9928aca2d82036_security_py.html | 65 | Duplicated block (19 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_security_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_2f9928aca2d82036_ports_py.html | 5 | Duplicated block (10 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_ports_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_2f9928aca2d82036_ports_py.html | 65 | Duplicated block (19 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_ports_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_2f9928aca2d82036_parser_py.html | 5 | Duplicated block (10 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_parser_py.html and htmlcov/z_2f9928aca2d82036_ports_py.html |
| LOW | htmlcov/z_2f9928aca2d82036_parser_py.html | 65 | Duplicated block (19 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_parser_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_2f9928aca2d82036_metrics_py.html | 5 | Duplicated block (10 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_metrics_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_2f9928aca2d82036_metrics_py.html | 65 | Duplicated block (19 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_metrics_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_2f9928aca2d82036_merge_py.html | 5 | Duplicated block (10 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_merge_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_2f9928aca2d82036_merge_py.html | 65 | Duplicated block (19 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_merge_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_2f9928aca2d82036_logging_py.html | 5 | Duplicated block (10 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_logging_py.html and htmlcov/z_4dc1c953114105d3_system_diagnostics_py.html |
| LOW | htmlcov/z_2f9928aca2d82036_logging_py.html | 65 | Duplicated block (19 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_logging_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_2f9928aca2d82036_levels_py.html | 5 | Duplicated block (10 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_levels_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_2f9928aca2d82036_levels_py.html | 65 | Duplicated block (19 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_levels_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_2f9928aca2d82036_gates_py.html | 5 | Duplicated block (10 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_gates_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_2f9928aca2d82036_gates_py.html | 65 | Duplicated block (19 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_gates_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_2f9928aca2d82036_exceptions_py.html | 5 | Duplicated block (10 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_exceptions_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_2f9928aca2d82036_exceptions_py.html | 65 | Duplicated block (19 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_exceptions_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_2f9928aca2d82036_context_tracker_py.html | 5 | Duplicated block (10 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_context_tracker_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_2f9928aca2d82036_context_tracker_py.html | 65 | Duplicated block (19 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_context_tracker_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_2f9928aca2d82036_constants_py.html | 5 | Duplicated block (10 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_constants_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_2f9928aca2d82036_constants_py.html | 65 | Duplicated block (19 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_constants_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_2f9928aca2d82036_config_py.html | 5 | Duplicated block (10 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_config_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_2f9928aca2d82036_config_py.html | 65 | Duplicated block (19 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_config_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_2f9928aca2d82036_cli_py.html | 5 | Duplicated block (10 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_cli_py.html and htmlcov/z_4dc1c953114105d3_recovery_py.html |
| LOW | htmlcov/z_2f9928aca2d82036_cli_py.html | 65 | Duplicated block (19 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_cli_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_2f9928aca2d82036_assign_py.html | 5 | Duplicated block (10 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_assign_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_2f9928aca2d82036_assign_py.html | 65 | Duplicated block (19 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036_assign_py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_2f9928aca2d82036___main___py.html | 5 | Duplicated block (10 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036___main___py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_2f9928aca2d82036___main___py.html | 65 | Duplicated block (19 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036___main___py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_2f9928aca2d82036___init___py.html | 5 | Duplicated block (10 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036___init___py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/z_2f9928aca2d82036___init___py.html | 65 | Duplicated block (19 lines, 0 tokens) between htmlcov/z_2f9928aca2d82036___init___py.html and htmlcov/z_b7674d2cb1ab17f4___init___py.html |
| LOW | htmlcov/index.html | 14 | Duplicated block (12 lines, 0 tokens) between htmlcov/index.html and htmlcov/z_4dc1c953114105d3_state_introspector_py.html |
| LOW | htmlcov/index.html | 463 | Duplicated block (10 lines, 0 tokens) between htmlcov/index.html and htmlcov/index.html |
| LOW | claudedocs/zerg_scratch.md | 289 | Duplicated block (10 lines, 0 tokens) between claudedocs/zerg_scratch.md and claudedocs/zerg_scratch.md |
| LOW | claudedocs/zerg_scratch.md | 299 | Duplicated block (15 lines, 0 tokens) between claudedocs/zerg_scratch.md and claudedocs/zerg_scratch.md |
| LOW | .zerg/test_runner.py | 58 | Duplicated block (18 lines, 0 tokens) between .zerg/test_runner.py and zerg/commands/test_cmd.py |
| LOW | .zerg/test_runner.py | 94 | Duplicated block (16 lines, 0 tokens) between .zerg/test_runner.py and zerg/commands/test_cmd.py |
| LOW | .zerg/test_runner.py | 138 | Duplicated block (16 lines, 0 tokens) between .zerg/test_runner.py and zerg/commands/test_cmd.py |
| LOW | .zerg/test_runner.py | 174 | Duplicated block (13 lines, 0 tokens) between .zerg/test_runner.py and zerg/commands/test_cmd.py |
| LOW | .zerg/test_runner.py | 310 | Duplicated block (11 lines, 0 tokens) between .zerg/test_runner.py and zerg/commands/test_cmd.py |
| LOW | .zerg/test_runner.py | 319 | Duplicated block (19 lines, 0 tokens) between .zerg/test_runner.py and zerg/commands/test_cmd.py |
| LOW | .zerg/state.py | 34 | Duplicated block (10 lines, 0 tokens) between .zerg/state.py and .zerg/tests/mocks/mock_state.py |
| LOW | .zerg/refactor.py | 125 | Duplicated block (11 lines, 0 tokens) between .zerg/refactor.py and zerg/commands/refactor.py |
| LOW | .zerg/refactor.py | 201 | Duplicated block (18 lines, 0 tokens) between .zerg/refactor.py and zerg/commands/refactor.py |
| LOW | .zerg/build.py | 169 | Duplicated block (17 lines, 0 tokens) between .zerg/build.py and zerg/commands/build.py |
| LOW | .zerg/build.py | 186 | Duplicated block (16 lines, 0 tokens) between .zerg/build.py and zerg/commands/build.py |
| LOW | .zerg/build.py | 222 | Duplicated block (16 lines, 0 tokens) between .zerg/build.py and zerg/commands/build.py |
| LOW | .zerg/build.py | 260 | Duplicated block (17 lines, 0 tokens) between .zerg/build.py and zerg/commands/build.py |
| LOW | .zerg/analyze.py | 231 | Duplicated block (12 lines, 0 tokens) between .zerg/analyze.py and zerg/commands/analyze.py |
| LOW | .zerg/analyze.py | 280 | Duplicated block (16 lines, 0 tokens) between .zerg/analyze.py and zerg/commands/analyze.py |

## Container Runtime (Score: 0/100)
| Severity | File | Line | Message |
|----------|------|------|---------|
| HIGH | .devcontainer/Dockerfile | - | DS-0002: Image user should not be 'root' |
| HIGH | .devcontainer/Dockerfile | - | DS-0029: 'apt-get' missing '--no-install-recommends' |
| HIGH | .devcontainer/Dockerfile | - | DS-0029: 'apt-get' missing '--no-install-recommends' |

## Dependencies (Score: 75/100)
| Severity | File | Line | Message |
|----------|------|------|---------|
| HIGH | - | - | Very large transitive dependency tree: 1207 transitive dependencies |

## CPU and Compute (Score: 100/100)
No findings.

## Memory (Score: 100/100)
No findings.

## Disk I/O (Score: 100/100)
No findings.

## Network I/O (Score: 100/100)
No findings.

## Database (Score: 100/100)
No findings.

## Caching (Score: 100/100)
No findings.

## Concurrency (Score: 100/100)
No findings.

## Abstraction and Structure (Score: 100/100)
No findings.

## Error Handling (Score: 100/100)
No findings.

## Container Image (Score: 100/100)
No findings.

## Observability (Score: 100/100)
No findings.

## Architecture (Score: 100/100)
| Severity | File | Line | Message |
|----------|------|------|---------|
| INFO | - | - | Large codebase: 242,259 lines of code across 3,302 files |

## AI Code Detection (Score: 100/100)
No findings.

## Security Patterns (Score: 100/100)
No findings.

## Orchestration (Score: N/A/100)
No findings.

## Summary
- Total findings: 961
- Critical: 5, High: 215, Medium: 275, Low: 465, Info: 1
- Tools used: semgrep, radon, lizard, vulture, jscpd, deptry, pipdeptree, dive, hadolint, trivy, cloc
- Detected stack: javascript, python, none
