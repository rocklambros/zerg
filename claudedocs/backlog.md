# Test Backlog

**Updated**: 2026-01-31
**Test Run**: `pytest tests/ -x -q` (serial, full suite)
**Results**: 5418 passed, 0 failed, 1 skipped (100% pass rate on non-skipped), 5m55s

## Fixed Issues (all resolved)

| # | Root Cause | Failures | Status | Fixed In |
|---|-----------|----------|--------|----------|
| 1 | `harness.py:131` task graph parsing expects dicts, gets strings | 7 | FIXED | previous session |
| 2 | `min_minutes` parameter removed but test still passes it | 1 | FIXED | previous session |
| 3 | `claim_next_task` poll loop exceeds 60s test timeout | 2 | FIXED | previous session |
| 4 | E2E test requires real Claude CLI | 1 | SKIPPED | previous session |
| 5 | Mock worker task ID mismatch (`T1.2` vs `L1-002`) | 1 | FIXED | 2451f86 |
| 6 | `is_level_complete` treated failed tasks as resolved | 1 | FIXED | 2451f86 |
| 7 | MetricsCollector patched in wrong module (orchestrator vs level_coordinator) | 1 | FIXED | 2451f86 |

## Remaining Issues

None.

---

## Fix Details (Issues 5-7, commit 2451f86)

### Issue 5: Mock Worker Task ID Mismatch

**File**: `tests/e2e/test_full_pipeline.py`
**Root Cause**: Test used `fail_tasks={"T1.2"}` but the `sample_e2e_task_graph` fixture defines task IDs as `L1-001`, `L1-002`, etc. The fail set never matched any real task ID, so all tasks succeeded.
**Fix**: Changed fail set to `{"L1-002"}`.

### Issue 6: is_level_complete Semantics

**File**: `zerg/levels.py`, `zerg/types.py`, `zerg/orchestrator.py`
**Root Cause**: `is_level_complete()` counted `completed + failed == total`, treating failed tasks as resolved. This contradicted the test expectation that failed tasks should block level completion.
**Fix**: Split into two methods:
- `is_level_complete()` — True only when ALL tasks completed successfully
- `is_level_resolved()` — True when all tasks are terminal (completed + failed)

Orchestrator and `can_advance()` now use `is_level_resolved()` for advancement decisions.

### Issue 7: MetricsCollector Patch Location

**File**: `tests/integration/test_orchestrator_integration.py`
**Root Cause**: Test patched `zerg.orchestrator.MetricsCollector` but `_on_level_complete_handler` delegates to `LevelCoordinator.handle_level_complete()` which imports `MetricsCollector` from `zerg.level_coordinator`.
**Fix**: Changed patch target to `zerg.level_coordinator.MetricsCollector`.

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
