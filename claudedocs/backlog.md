# Test Backlog

**Updated**: 2026-01-30
**Test Run**: `pytest tests/ -n auto --timeout=60` (16 workers, pytest-xdist)
**Results**: 5366 passed, 3 failed, 1 skipped (99.9% pass rate), 2m09s

## Fixed Issues (previous run: 11 failures)

| # | Root Cause | Failures | Status |
|---|-----------|----------|--------|
| 1 | `harness.py:131` task graph parsing expects dicts, gets strings | 7 | FIXED |
| 2 | `min_minutes` parameter removed but test still passes it | 1 | FIXED |
| 3 | `claim_next_task` poll loop exceeds 60s test timeout | 2 | FIXED |
| 4 | E2E test requires real Claude CLI | 1 | SKIPPED |

## Remaining Issues (3 failures)

| # | Root Cause | Failures | Severity | Category |
|---|-----------|----------|----------|----------|
| 5 | Mock worker failure simulation not working | 1 | MEDIUM | Bug |
| 6 | LevelController marks level complete despite failed task | 1 | MEDIUM | Bug |
| 7 | Metrics compute_feature_metrics not called after level | 1 | MEDIUM | Bug |

---

## Issue 1: E2E Harness Task Graph Parsing Bug (7 failures)

**File**: `tests/e2e/harness.py:131`
**Error**: `AttributeError: 'str' object has no attribute 'get'`

`setup_task_graph()` iterates over task graph entries expecting dicts but receives strings. The `sample_e2e_task_graph` fixture likely provides a structure where `tasks` contains string task IDs instead of task objects, or the iteration is over dict keys rather than values.

**Affected tests**:
- `tests/integration/test_orchestrator_integration.py::test_metrics_computed_after_level_completion`
- `tests/integration/test_rush_flow.py::test_task_failure_blocks_level`
- `tests/e2e/test_full_pipeline.py::test_mock_pipeline_completes`
- `tests/e2e/test_full_pipeline.py::test_mock_pipeline_creates_files`
- `tests/e2e/test_full_pipeline.py::test_mock_pipeline_merges_levels`
- `tests/e2e/test_full_pipeline.py::test_mock_pipeline_state_consistent`
- `tests/e2e/test_full_pipeline.py::test_mock_pipeline_handles_task_failure`

**Fix**: Check `harness.py:131` — either fix the fixture to provide task dicts, or fix the iteration to handle the actual data structure.

---

## Issue 2: `min_minutes` Parameter Removal Regression (1 failure)

**File**: `tests/unit/test_design_cmd.py::test_task_graph_respects_min_minutes`
**Error**: `TypeError: create_task_graph_template() got an unexpected keyword argument 'min_minutes'`

Task PRF-L1-002 removed the unused `min_minutes` parameter from `create_task_graph_template()` in `zerg/commands/design.py`, but the corresponding test still passes it.

**Fix**: Update or remove `test_task_graph_respects_min_minutes` since the parameter no longer exists.

---

## Issue 3: `claim_next_task` Poll Timeout (2 failures)

**Files**:
- `tests/test_worker_protocol.py::test_claim_next_task_none_available`
- `tests/integration/test_worker_protocol_extended.py::test_claim_returns_none_when_no_tasks`

**Error**: `Failed: Timeout (>60.0s) from pytest-timeout`

`claim_next_task()` in `zerg/worker_protocol.py:383` enters a `time.sleep(interval)` poll loop. With the default 120s max poll time and no available tasks, the test exceeds the 60s pytest timeout before `claim_next_task` returns `None`.

**Fix**: Mock `time.sleep` in these tests, or reduce the poll timeout/interval for test scenarios. Alternatively, increase the pytest timeout for these specific tests.

---

## Issue 4: Real Execution E2E Requires Claude CLI (1 failure) — SKIPPED

**Status**: RESOLVED — `@pytest.mark.skip` added to `TestRealExecution` class.

---

## Issue 5: Mock Worker Failure Simulation Not Working (1 failure)

**File**: `tests/e2e/test_full_pipeline.py::test_mock_pipeline_handles_task_failure`
**Error**: `assert result.success is False` — but result shows `success=True, tasks_failed=0`

The test monkeypatches `tests.e2e.mock_worker.MockWorker` with a failing worker factory for task `T1.2`, but the mock pipeline still completes all 4 tasks successfully. The monkeypatch target path may not match where `MockWorker` is imported/used by the harness `run()` method.

**Fix**: Investigate mock worker patching — ensure the monkeypatch targets the correct import path where `MockWorker` is resolved at runtime.

---

## Issue 6: LevelController Marks Level Complete Despite Failed Task (1 failure)

**File**: `tests/integration/test_rush_flow.py::test_task_failure_blocks_level`
**Error**: `assert not controller.is_level_complete(1)` — but `is_level_complete(1)` returns `True`

After marking TASK-001 as failed and TASK-002 as complete, `is_level_complete(1)` still returns `True`. The level controller appears to consider a level complete when all tasks have a terminal status (including "failed"), rather than requiring all tasks to succeed.

**Fix**: Review `LevelController.is_level_complete()` — determine if the logic should treat failed tasks as blocking level completion, or if the test expectation is wrong.

---

## Issue 7: Metrics compute_feature_metrics Not Called After Level (1 failure)

**File**: `tests/integration/test_orchestrator_integration.py::test_metrics_computed_after_level_completion`
**Error**: `Expected 'compute_feature_metrics' to have been called once. Called 0 times.`

The orchestrator completes level 1 but never calls `compute_feature_metrics`. The mock for the metrics collector may not be injected correctly into the orchestrator instance.

**Fix**: Verify that the metrics mock is properly wired into the orchestrator's metrics pipeline.

---

## Feature Backlog

SuperClaude capability gaps identified for future implementation.

| # | Skill | Purpose | Priority |
|---|-------|---------|----------|
| 1 | `sc:document` | Focused docs generation for components, APIs, and functions. Auto-detect docstring style, generate usage examples, parameter tables, return type docs. | HIGH |
| 2 | `sc:index` | Project-wide knowledge base / API doc generation. Crawl codebase → build structured index with cross-references, dependency graphs, entry points. | HIGH |
| 3 | `sc:estimate` | Structured effort estimation with confidence intervals. Analyze complexity, dependencies, risk factors → output ranges (optimistic/expected/pessimistic). | MEDIUM |
| 4 | `sc:explain` | Educational code explanations with progressive depth. Layer 1: summary → Layer 2: logic flow → Layer 3: implementation details → Layer 4: design decisions. | MEDIUM |
| 5 | `sc:select-tool` | Intelligent MCP server routing. Score task complexity, map to optimal MCP server combinations, handle fallback chains when preferred tools unavailable. | LOW |

### Notes

- Items 1-2 address documentation gaps — currently no structured way to generate or maintain project docs.
- Item 3 fills planning gap — no evidence-based sizing beyond gut feel.
- Item 4 supports onboarding and knowledge transfer use cases.
- Item 5 formalizes the implicit tool selection logic already described in `MODE_Orchestration.md`.
