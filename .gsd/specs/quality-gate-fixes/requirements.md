# Requirements: Quality Gate Fixes (Issues #106, #107)

**Status: APPROVED**
**Created**: 2026-02-04
**GitHub Issues**: #106 (import-chain), #107 (cross-file)

---

## Problem Statement

Two quality gate failures need resolution:
1. **Issue #106**: 3 circular imports + 5 deep import chains (score 20/100)
2. **Issue #107**: 318 unused exports detected (score 0/100)

## Scope

### In Scope
- Fix 3 circular imports using TYPE_CHECKING guards
- Add `__all__` to core public modules to clarify public API
- Run quality gates to verify improvement

### Out of Scope (Deferred)
- Deep import chains (depth >10) — separate PR
- Removing unused code — requires manual review
- Restructuring module hierarchy

---

## Functional Requirements

### FR-1: Fix Circular Import #1 (debug → code_fixer → recovery → debug)

**Current state:**
- `code_fixer.py` imports `RecoveryStep` from `recovery.py` at module level
- `recovery.py` imports `DiagnosticResult` from `commands/debug.py` via TYPE_CHECKING (already guarded)

**Fix:** Move `RecoveryStep` import in `code_fixer.py` to TYPE_CHECKING block.

**Files:** `zerg/diagnostics/code_fixer.py`

### FR-2: Fix Circular Import #2 (verify → verification_gates → verify)

**Current state:**
- `verification_gates.py` imports `VerificationExecutionResult, VerificationExecutor` from `verify.py`
- `verify.py` imports `ArtifactStore` from `verification_gates.py` inside methods

**Fix:** The cycle exists because `verify.py` has runtime imports of `verification_gates`. Move these to TYPE_CHECKING or keep as function-level lazy imports.

**Files:** `zerg/verify.py`, `zerg/verification_gates.py`

### FR-3: Fix Circular Import #3 (dryrun → render_utils → dryrun)

**Current state:**
- `render_utils.py` imports `LevelTimeline` from `dryrun.py` in TYPE_CHECKING (already guarded)
- `dryrun.py` imports `render_gantt_chart` from `render_utils.py` at module level

**Analysis:** This may already be properly guarded. Verify the import chain analysis tool's detection.

**Files:** `zerg/dryrun.py`, `zerg/render_utils.py`

### FR-4: Add `__all__` to Core Public Modules

Add explicit `__all__` exports to clarify public API:
- `zerg/__init__.py` — main package exports
- `zerg/config.py` — configuration classes
- `zerg/types.py` — type definitions

---

## Non-Functional Requirements

### NFR-1: No Breaking Changes
Existing imports must continue to work.

### NFR-2: Verification
Run `/z:analyze` import-chain gate after changes. Target: score >80/100.

---

## Acceptance Criteria

1. [ ] `python -c "from zerg.commands.debug import DebugCommand"` succeeds
2. [ ] `python -c "from zerg.verify import VerificationExecutor"` succeeds
3. [ ] `python -c "from zerg.dryrun import DryRunSimulator"` succeeds
4. [ ] Import-chain quality gate passes (score >80)
5. [ ] All existing tests pass

---

## Technical Approach

### Circular Import Fix Pattern

Use `TYPE_CHECKING` guard for type-only imports:

```python
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zerg.diagnostics.recovery import RecoveryStep
```

For runtime imports needed at call time, use lazy imports inside functions:

```python
def verify_task_tiered(self, ...):
    from zerg.verification_tiers import VerificationTiers
    # ...
```

### `__all__` Pattern

```python
__all__ = [
    "ClassName",
    "function_name",
]
```

---

## Dependencies

- None (internal refactoring only)

---

## Risks

| Risk | Mitigation |
|------|------------|
| Breaking existing imports | Test all entry points before/after |
| False positive detection by analyzer | Manual verification of cycles |

---

## Open Questions

None — all resolved via Socratic discovery.
