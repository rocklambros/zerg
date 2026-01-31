# Requirements: Fix Pre-Existing Test Failures

- **Feature**: fix-test-failures
- **Status**: APPROVED
- **Created**: 2026-01-30

## Problem

3 tests have been failing on main for multiple commits. They were identified during the CLAUDE_CODE_TASK_LIST_ID feature implementation and confirmed as pre-existing by running on clean main.

## Failures

### F1: test_mock_pipeline_handles_task_failure
- **File**: tests/e2e/test_full_pipeline.py:163
- **Type**: TEST BUG
- **Root Cause**: Monkeypatch targets `tests.e2e.mock_worker.MockWorker` but harness.py:215 imports `from tests.e2e.mock_worker import MockWorker` at call time. The `from` import creates a new binding that isn't affected by patching the source module.
- **Fix**: Change monkeypatch target to the import location in the harness.

### F2: test_metrics_computed_after_level_completion
- **File**: tests/integration/test_orchestrator_integration.py:678
- **Type**: TEST BUG
- **Root Cause**: Patches `zerg.orchestrator.MetricsCollector` but `_on_level_complete_handler` delegates to `LevelCoordinator.handle_level_complete()` which calls `MetricsCollector` from `zerg.level_coordinator` (line 238). Wrong patch location.
- **Fix**: Patch `zerg.level_coordinator.MetricsCollector` instead.

### F3: test_task_failure_blocks_level
- **File**: tests/integration/test_rush_flow.py:145
- **Type**: SOURCE BUG
- **Root Cause**: `LevelController.is_level_complete()` at `zerg/levels.py:220-223` treats failed tasks as resolved (`completed + failed == total`). Should only count completed tasks.
- **Fix**: Change `is_level_complete` to require all tasks completed (not just resolved). Add separate `is_level_resolved` method for the "all tasks terminal" check.

## Acceptance Criteria

- All 3 tests pass
- No regressions in existing passing tests (5415 tests)
