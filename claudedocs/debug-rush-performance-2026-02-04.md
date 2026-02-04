# ZERG Rush Performance Debug Report

**Date**: 2026-02-04
**Feature**: github-issues-batch
**Symptom**: "PAINFULLY slow" rush execution
**Classification**: INFRASTRUCTURE (Quality Gate Architecture)

## Executive Summary

The ZERG rush was slow because **merge gates bypass the caching layer**. Each merge retry re-runs ALL quality gates from scratch. A single level took ~6 minutes to merge when actual gate execution should take ~30s with caching.

## Root Cause

### Finding: GatePipeline Not Used for Merge Gates

| Component | Uses Caching? | Location |
|-----------|---------------|----------|
| Improvement Loop | ✅ Yes | `orchestrator.py:_run_level_loop()` |
| Pre-merge Gates | ❌ No | `merge.py:run_pre_merge_gates()` |
| Post-merge Gates | ❌ No | `merge.py:run_post_merge_gates()` |

The `GatePipeline` class exists with staleness checking (30 min cache), but `MergeCoordinator` uses basic `GateRunner` which re-runs everything.

### Timeline Evidence

From `github-issues-batch` state JSON:
- Level 1 tasks completed in ~2 minutes
- Level 1 merge took ~6 minutes (3 retry attempts)
- Each retry ran all gates from scratch: lint + smoke + test × 2 (pre + post)

### Impact

| Metric | Observed |
|--------|----------|
| Gate runs for Level 1 | 6+ (should be 1-2 with caching) |
| Time wasted on retries | ~4 minutes (65% overhead) |
| Rush restarts | 3 (due to gate failures) |

## Solution

### Primary Fix: Wire GatePipeline to MergeCoordinator

```python
# zerg/merge.py - Accept GatePipeline in __init__
def __init__(self, ..., gate_pipeline=None):
    self._gate_pipeline = gate_pipeline

# Use cached execution in run_pre_merge_gates()
if self._gate_pipeline:
    results = self._gate_pipeline.run_gates_for_level(level=0, gates=gates)
    # Returns cached results if fresh
```

### Expected Improvement

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Level merge time | ~6 min | ~30s | 12x faster |
| Total rush (6 tasks) | ~26 min | ~8 min | 3x faster |
| Gate runs per level | 6+ | 1-2 | 80% reduction |

## Secondary Recommendations

1. **Test Tiering**: Add `@pytest.mark.smoke` to critical tests (plan exists at `radiant-greeting-waterfall.md`)
2. **Skip-Tests Mode**: Use `--skip-tests` for non-final levels
3. **Gate Timeouts**: Reduce from 180s to 120s for faster failure detection

## Files Involved

- `zerg/merge.py` - MergeCoordinator (needs GatePipeline)
- `zerg/orchestrator.py` - Owns GatePipeline instance
- `zerg/level_coordinator.py` - Contains GatePipeline class
- `.zerg/config.yaml` - Gate configuration

## Related Issues

- #118: rush performance optimization (recent PR)
- Existing plan: `radiant-greeting-waterfall.md` (test tiering)
