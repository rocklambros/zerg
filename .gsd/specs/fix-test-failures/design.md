# Technical Design: fix-test-failures

- **Feature**: fix-test-failures
- **Status**: APPROVED
- **Created**: 2026-01-30

## Overview

Fix 3 pre-existing test failures on main through targeted patches to test files and one source code change.

## Tasks

### TASK-001: Fix monkeypatch target in E2E test (TEST BUG)
**File**: `tests/e2e/test_full_pipeline.py`
**Change**: Line 157 — change monkeypatch target from `"tests.e2e.mock_worker.MockWorker"` to `"tests.e2e.harness.MockWorker"` since harness.py does `from tests.e2e.mock_worker import MockWorker` inside run().

Wait — harness.py imports inside run(), so `tests.e2e.harness.MockWorker` doesn't exist at module level. The fix is to either:
(a) Change harness.py to use `import tests.e2e.mock_worker` then `tests.e2e.mock_worker.MockWorker()`, OR
(b) Change the harness import to module-level

Best fix: (a) — change harness.py line 215 from `from tests.e2e.mock_worker import MockWorker` to `import tests.e2e.mock_worker as mock_worker_mod` then use `mock_worker_mod.MockWorker()` at line 240. This makes the monkeypatch path work.

### TASK-002: Fix MetricsCollector patch location (TEST BUG)
**File**: `tests/integration/test_orchestrator_integration.py`
**Change**: Line 632 — change `patch("zerg.orchestrator.MetricsCollector")` to `patch("zerg.level_coordinator.MetricsCollector")`. The `_on_level_complete_handler` delegates to `LevelCoordinator.handle_level_complete()` which calls `MetricsCollector` from `zerg.level_coordinator` line 238.

### TASK-003: Fix is_level_complete semantics (SOURCE BUG)
**Files**: `zerg/levels.py`, `tests/unit/test_levels_extended.py`, `tests/integration/test_rush_flow.py`
**Change**:
1. In `zerg/levels.py`: Rename current `is_level_complete` to `is_level_resolved` (all tasks terminal). Create new `is_level_complete` that returns True only when ALL tasks are COMPLETED (zero failures).
2. Update orchestrator callers (lines 560, 815) and `can_advance()` (line 234) to use `is_level_resolved()` — preserving existing orchestrator behavior.
3. Update `test_is_level_complete_with_failures` to use `is_level_resolved` assertion.
4. The `test_task_failure_blocks_level` test now passes as-is.
