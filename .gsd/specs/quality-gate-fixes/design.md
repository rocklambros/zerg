# Technical Design: Quality Gate Fixes

## Metadata
- **Feature**: quality-gate-fixes
- **Status**: APPROVED
- **Created**: 2026-02-04
- **GitHub Issues**: #106, #107

---

## 1. Overview

### 1.1 Summary
Fix quality gate failures by documenting existing TYPE_CHECKING guards and adding explicit `__all__` exports to clarify public APIs. The circular imports are already correctly mitigated at runtime.

### 1.2 Goals
- Document the lazy import pattern in `zerg/verify.py`
- Add `__all__` to `zerg/config.py` and `zerg/types.py`
- Verify import-chain quality gate score improves

### 1.3 Non-Goals
- Fix deep import chains (depth >10) — deferred
- Remove unused exports — requires manual review
- Restructure module hierarchy

---

## 2. Architecture

### 2.1 Current State Analysis

Three potential circular imports were detected by the quality gate:

| Chain | Mitigation | Status |
|-------|------------|--------|
| `debug → code_fixer → recovery → debug` | TYPE_CHECKING in recovery.py | ✅ Already guarded |
| `verify ↔ verification_gates` | Lazy imports in methods | ✅ Works, needs docs |
| `dryrun → render_utils → dryrun` | TYPE_CHECKING in render_utils.py | ✅ Already guarded |

### 2.2 Changes Required

**1. Document lazy import pattern (verify.py)**
```python
def store_artifact(self, ...):
    # Lazy import to avoid circular dependency with verification_gates
    from zerg.verification_gates import ArtifactStore
```

**2. Add `__all__` to config.py**
Export configuration classes explicitly.

**3. Add `__all__` to types.py**
Export type definitions explicitly.

---

## 3. Detailed Design

### 3.1 verify.py Changes

Lines 297 and 320 contain lazy imports of `ArtifactStore`. Add comments documenting the pattern:

```python
def store_artifact(
    self,
    result: VerificationExecutionResult,
    artifact_dir: Path | None = None,
) -> Path:
    """Store verification result as artifact."""
    # Lazy import to avoid circular dependency with verification_gates
    from zerg.verification_gates import ArtifactStore

    store = ArtifactStore(base_dir=artifact_dir)
    return store.store("verification", result.task_id, result)
```

### 3.2 config.py __all__ Definition

```python
__all__ = [
    # Main config
    "ZergConfig",
    # Sub-configs
    "ProjectConfig",
    "WorkersConfig",
    "PortsConfig",
    "QualityGate",
    "ResourcesConfig",
    "LoggingConfig",
    "SecurityConfig",
    "ResilienceConfig",
    "EfficiencyConfig",
    "RulesConfig",
    "CircuitBreakerConfig",
    "BackpressureConfig",
    "ErrorRecoveryConfig",
    "LoopConfig",
    "VerificationConfig",
    "ModeConfig",
    "MCPRoutingConfig",
    "TDDConfig",
    "HeartbeatConfig",
    "EscalationConfig",
    "VerificationTiersConfig",
    "RepoMapConfig",
    "TokenMetricsConfig",
    "PlanningConfig",
    "RushConfig",
]
```

### 3.3 types.py __all__ Definition

```python
__all__ = [
    # Task types
    "FileSpec",
    "VerificationSpec",
    "VerificationResult",
    "TaskExecution",
    "Task",
    "LevelSpec",
    "TaskGraph",
    # Worker types
    "WorkerState",
    # Level types
    "LevelStatus",
    # Gate types
    "GateConfig",
    "GateRunResult",
    # Merge types
    "MergeResult",
    # Orchestrator types
    "LevelCompleteResult",
    "ExecutionEvent",
    "OrchestratorState",
    # Assignment types
    "WorkerAssignmentEntry",
    "WorkerAssignments",
    # Metrics types
    "WorkerMetrics",
    "TaskMetrics",
    "LevelMetrics",
    "FeatureMetrics",
]
```

---

## 4. Key Decisions

### 4.1 Document Rather Than Restructure

**Context**: The circular imports are already mitigated at runtime but detected by static analysis.

**Options Considered**:
1. Restructure modules to eliminate cycles: High effort, risk of breaking changes
2. Document existing patterns: Low effort, clarifies intent
3. Do nothing: Risk of future regressions

**Decision**: Document existing patterns with comments.

**Rationale**: The code works correctly. Documentation preserves knowledge for future maintainers without introducing risk.

### 4.2 Add __all__ to Core Modules Only

**Context**: 318 unused exports detected, but many are false positives (CLI commands, public API).

**Options Considered**:
1. Add __all__ to all modules: High effort, maintenance burden
2. Add __all__ to core modules only: Low effort, clarifies main API
3. Skip entirely: Misses opportunity to clarify public API

**Decision**: Add __all__ to config.py and types.py.

**Rationale**: These are the most-imported modules. Explicit exports clarify the public API without affecting runtime behavior.

---

## 5. Implementation Plan

### 5.1 Phase Summary

| Phase | Tasks | Parallel | Est. Time |
|-------|-------|----------|-----------|
| Foundation | 3 | Yes | 15m |
| Verification | 1 | No | 10m |

### 5.2 File Ownership

| File | Task ID | Operation |
|------|---------|-----------|
| zerg/verify.py | TASK-001 | modify |
| zerg/config.py | TASK-002 | modify |
| zerg/types.py | TASK-003 | modify |
| — | TASK-004 | verify |

### 5.3 Dependency Graph

```
Level 1 (Foundation):
  TASK-001 ─┐
  TASK-002 ─┼─> TASK-004 (Verification)
  TASK-003 ─┘
```

---

## 6. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Breaking imports | Low | High | Test all entry points |
| Quality gate still fails | Medium | Low | Manual verification |

---

## 7. Testing Strategy

### 7.1 Verification Commands

Each task has a verification command:
- TASK-001: `python -c "from zerg.verify import VerificationExecutor"`
- TASK-002: `python -c "from zerg.config import ZergConfig"`
- TASK-003: `python -c "from zerg.types import Task"`
- TASK-004: `pytest tests/ -x && python -m zerg.validate_commands`

---

## 8. Parallel Execution Notes

### 8.1 Safe Parallelization
- Level 1 tasks modify separate files, fully parallel
- Level 2 verification depends on all level 1 tasks

### 8.2 Recommended Workers
- Minimum: 1 worker
- Optimal: 3 workers (one per file)
- Maximum: 3 workers

### 8.3 Estimated Duration
- Single worker: ~25 minutes
- With 3 workers: ~15 minutes
- Speedup: 1.7x

---

## 9. Approval

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Architecture | | | PENDING |
| Engineering | | | PENDING |
