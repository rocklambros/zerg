# ZERG Rush Performance Optimization

**Status: APPROVED**
**Created**: 2026-02-03

## Problem Statement

Rush execution for `github-issues-batch` (9 tasks, 5 levels) took **~6 hours** when it should take ~30-60 minutes.

## Root Cause

### Primary: Gate Executions Per Level

**Minimum safe gates: 10 total** (2 per level × 5 levels)
**Current with loops: 15-30 total** (3-6 per level × 5 levels)

| Gate Type | Per Level | Required? | Can Eliminate? |
|-----------|-----------|-----------|----------------|
| Pre-merge | 1 | YES | NO - prevents bad merges |
| Post-merge | 1 | YES | NO - catches integration issues |
| Loop initial | 1 | NO | YES - duplicates post-merge |
| Loop iterations | 0-3 | NO | YES - quality only, not safety |

### Secondary: 7,624 Tests

PR #115 (`bf51949`) added **2,190+ test lines**:
- `test_resilience_e2e.py` (809 lines)
- `test_state_reconciler.py` (882 lines)
- `test_resilience_config.py` (550 lines)

## Requirements

### REQ-1: Config Changes
- Set `staleness_threshold_seconds: 1800` (30 min cache)
- Set `improvement_loops.max_iterations: 1`

### REQ-2: Reuse Post-Merge Results
- Pass `MergeFlowResult.gate_results` to improvement loop
- Use as initial score instead of re-running gates

### REQ-3: Add --skip-tests Flag
- New CLI flag for rush command
- Runs only lint gates during development
- Full test suite on final level only

### REQ-4: Mark Slow Tests
- Add `@pytest.mark.slow` to resilience tests
- Split gate config: fast tests (required) vs slow tests (optional)

## Files to Modify

| File | Change | Priority |
|------|--------|----------|
| `.zerg/config.yaml` | staleness=1800, loops.max_iterations=1 | P0 |
| `zerg/orchestrator.py` | Reuse post-merge results in loop | P0 |
| `zerg/commands/rush.py` | Add --skip-tests flag | P1 |
| `zerg/merge.py` | Respect --skip-tests flag | P1 |
| `tests/unit/test_resilience_*.py` | Add @pytest.mark.slow | P2 |
| `tests/integration/test_resilience_e2e.py` | Add @pytest.mark.slow | P2 |

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Gate runs per level | 3-6 | 2 |
| Test runs per rush | 15-30 | 2-5 |
| Rush time (5 levels) | ~6 hours | ~45 min |

## Verification

- [ ] `pytest tests/ -x` passes (no regressions)
- [ ] `grep "Running gate: test" /tmp/rush*.log | wc -l` shows ~5
- [ ] `zerg rush --skip-tests` completes in <15 min
- [ ] `pytest -m slow --collect-only` shows resilience tests marked

## Implementation Steps

### Step 1: Config Changes (5 min)
```yaml
# .zerg/config.yaml additions
verification:
  staleness_threshold_seconds: 1800

improvement_loops:
  enabled: true
  max_iterations: 1
```

### Step 2: Reuse Post-Merge Results (30 min)
- **File**: `zerg/orchestrator.py` ~line 574
- Pass `MergeFlowResult.gate_results` to `_run_level_loop()`
- Use as initial score instead of re-running gates

### Step 3: Add --skip-tests Flag (1 hour)
- **File**: `zerg/commands/rush.py` - add CLI flag
- **File**: `zerg/orchestrator.py` - propagate flag to gate runner
- **File**: `zerg/merge.py` - respect flag in pre/post merge gates

### Step 4: Mark Slow Tests (30 min)
- **Files**:
  - `tests/unit/test_resilience_config.py`
  - `tests/unit/test_state_reconciler.py`
  - `tests/integration/test_resilience_e2e.py`
- Add `@pytest.mark.slow` to test classes
- Update `.zerg/config.yaml` gate commands
