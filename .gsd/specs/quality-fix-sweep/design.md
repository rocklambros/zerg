# Technical Design: quality-fix-sweep

## Metadata
- **Feature**: quality-fix-sweep
- **Status**: REVIEW
- **Created**: 2026-01-30

---

## 1. Overview

### 1.1 Summary
Fix all 182 mypy errors and 19 ruff lint violations. Work is partitioned by file ownership to enable maximum parallelization. Each task owns a disjoint set of files.

### 1.2 Goals
- Zero mypy errors (`python -m mypy zerg/`)
- Zero ruff errors (`python -m ruff check zerg/`)
- No behavioral changes — type fixes only
- All existing tests continue to pass

### 1.3 Non-Goals
- No refactoring of god classes or function decomposition
- No new features or behavior changes
- No test additions (unless a fix changes semantics)

---

## 2. Architecture

### 2.1 Approach
Pure type-safety and lint fixes. Three categories of change:

1. **Fix broken call sites** — Use correct method names, access correct attributes
2. **Add/fix type annotations** — Generic params, return types, variable annotations
3. **Lint cleanup** — Line length, context managers, collapsible ifs, unused imports

### 2.2 Key Decision: Fix broken methods vs add stubs
**Decision**: Fix call sites to use existing correct methods. Don't add new stubs.
**Rationale**: The classes already have the correct methods; callers just use wrong names.

---

## 3. Implementation Plan

### Level 1: P0 Broken Code Paths (7 tasks, fully parallel)
Each task owns one command file. Fixes attr-defined/name-defined errors.

### Level 2: P1 Type Mismatches (6 tasks, fully parallel)
Each task owns a disjoint set of core module files. Fixes return types, annotations, assignment mismatches.

### Level 3: P2 Generic Type Params + Ruff Lint (5 tasks, fully parallel)
Bulk annotation fixes across types.py, backlog.py, diagnostics, commands, and lint fixes.

---

## 4. File Ownership Matrix

| Task | Files Owned (modify) |
|------|---------------------|
| QFS-L1-001 | commands/cleanup.py |
| QFS-L1-002 | commands/stop.py |
| QFS-L1-003 | commands/retry.py |
| QFS-L1-004 | commands/merge_cmd.py, types.py (MergeFlowResult only) |
| QFS-L1-005 | commands/rush.py |
| QFS-L1-006 | commands/review.py |
| QFS-L1-007 | commands/plan.py |
| QFS-L2-001 | state.py |
| QFS-L2-002 | logging.py, ports.py, retry_backoff.py, validation.py |
| QFS-L2-003 | launcher.py, command_executor.py |
| QFS-L2-004 | security.py, plugins.py, config.py |
| QFS-L2-005 | parser.py, metrics.py, orchestrator.py |
| QFS-L2-006 | dryrun.py, whatif.py |
| QFS-L3-001 | types.py (generic params only — after L1-004) |
| QFS-L3-002 | backlog.py |
| QFS-L3-003 | diagnostics/ (all 4 files) |
| QFS-L3-004 | commands/init.py, design.py, build.py, refactor.py, logs.py, status.py, troubleshoot.py, analyze.py |
| QFS-L3-005 | gates.py, plugin_config.py, preflight.py, risk_scoring.py, whatif.py (line-length), orchestrator.py (ruff only) |

---

## 5. Verification

Each task verifies with: `python -m mypy {owned_files} --no-error-summary && python -m ruff check {owned_files}`

Final gate: `python -m mypy zerg/ && python -m ruff check zerg/ && python -m pytest tests/unit/ -x -q`

---

## 6. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Type fix changes runtime behavior | Low | Medium | Tests catch regressions |
| File ownership conflict on types.py | Medium | Low | L1-004 adds field; L3-001 adds generics — different edits |
| orchestrator.py shared between L2-005 and L3-005 | Medium | Low | L2-005 fixes return types; L3-005 fixes lint — sequenced by levels |

---

## 7. Recommended Workers
- **Optimal**: 7 (widest level is L1 with 7 tasks)
- **Maximum useful**: 8 (L3 has 5 tasks but some are small)
