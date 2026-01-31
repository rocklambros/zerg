# Technical Design: container-mode-bypass

## Metadata
- **Feature**: container-mode-bypass
- **Status**: APPROVED
- **Created**: 2026-01-31
- **Source**: GitHub Issue #2

## 1. Overview

### 1.1 Summary
Remove the unimplemented "task" launcher mode from CLI choices, make unknown modes fail loudly with `ValueError`, and add launcher mode logging/console output so users can confirm which mode is active.

### 1.2 Goals
- Eliminate silent fallback for unknown launcher modes
- Provide user-visible confirmation of launcher mode
- Prevent future confusion about supported modes

### 1.3 Non-Goals
- Implementing a TaskLauncher (separate feature if needed)
- Changing container or subprocess launcher behavior

## 2. Architecture

### 2.1 Data Flow

```
CLI (rush.py)                    Orchestrator._create_launcher()
  --mode {choice} ──────────────▶  mode dispatch:
  choices: subprocess,               subprocess → SubprocessLauncher
           container,                 container  → ContainerLauncher
           auto                       auto       → auto-detect
                                      unknown    → ValueError (NEW)
                                    ──────────────▶ logger.info(mode selected)
                                    ──────────────▶ console.print(launcher type)
```

### 2.2 Key Decision

**Decision**: Remove "task" from CLI rather than implement TaskLauncher.

**Rationale**: "task" mode has no implementation, no design, and no tests. Adding a stub would be scope creep. Remove it now; add it back with a proper implementation later if needed.

## 3. Implementation Plan

| Phase | Tasks | Parallel | Files |
|-------|-------|----------|-------|
| L1: Fix | 2 tasks | Yes | rush.py, orchestrator.py |
| L2: Docs + Tests | 2 tasks | Yes | rush.core.md, test files |

### File Ownership

| File | Task ID | Operation |
|------|---------|-----------|
| zerg/commands/rush.py | TASK-001 | modify |
| zerg/orchestrator.py | TASK-002 | modify |
| zerg/data/commands/rush.core.md | TASK-003 | modify |
| tests/unit/test_orchestrator_container_mode.py | TASK-004 | modify |

## 4. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Plugin launchers affected by ValueError | Low | Med | Plugin path checked before else branch |
| Existing tests break | Low | Low | Run full suite before commit |

## 5. Verification

```bash
pytest tests/unit/test_orchestrator_container_mode.py tests/unit/test_rush_cmd.py -v
pytest tests/ -x -q
```

## 6. Recommended Workers
- Optimal: 2 workers (L1 tasks parallel, L2 tasks parallel)
