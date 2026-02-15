# Technical Design: resolving-the-rest-of-134-completely

## Metadata
- **Feature**: resolving-the-rest-of-134-completely
- **Status**: REVIEW
- **Created**: 2026-02-06
- **Author**: Factory Design Mode

---

## 1. Overview

### 1.1 Summary
Replace 18 scattered `rglob` calls across 16 files with calls to `fs_utils.collect_files()`. This is a mechanical refactor — each call site gets the same result set via the shared single-pass traversal. Two call sites need a minor extension to `collect_files()` for name-based matching (Dockerfiles). Two sites are documented exceptions (rush.py tiny dir, ast_analyzer.py dynamic pattern).

### 1.2 Goals
- Eliminate redundant directory traversals (Issue #134)
- Standardize file collection through `fs_utils.collect_files()`
- Improve filtering consistency (replace fragile string-in-path checks with proper path-parts exclusion)

### 1.3 Non-Goals
- Cross-call caching/memoization of `collect_files()` results
- Performance benchmarking
- Refactoring duplicated Dockerfile-finding logic between adapters (separate concern)
- Changing any module's behavior or output

---

## 2. Architecture

### 2.1 High-Level Design

```
Before:                              After:

module_a ──rglob──┐                  module_a ──┐
module_b ──rglob──┤                  module_b ──┤
module_c ──rglob──┤  filesystem      module_c ──┼── fs_utils.collect_files() ── filesystem
module_d ──rglob──┤                  module_d ──┤     (single rglob("*"))
module_e ──rglob──┘                  module_e ──┘
(5 traversals)                       (1 traversal per call site)
```

Each call site still invokes `collect_files()` independently (no shared cache), but each invocation does exactly one `rglob("*")` instead of N separate `rglob("*.ext")` calls.

### 2.2 Component Breakdown

| Component | Responsibility | Files |
|-----------|---------------|-------|
| `fs_utils` | Single-pass file collection with extension and name filtering | `zerg/fs_utils.py` |
| Pattern A sites (10) | Single-extension rglob → `collect_files(root, {".py"})` | 8 files |
| Pattern B sites (4) | Multi-extension loop → `collect_files(root, {".py", ".js", ...})` | 4 files |
| Pattern C sites (3) | Wildcard rglob → `collect_files(root, extensions=None, names=...)` | 3 files |
| Documented exceptions | rush.py, ast_analyzer.py — kept as-is | 2 files |

### 2.3 Data Flow

1. Call site determines root directory and desired extensions
2. `collect_files(root, extensions=...)` walks root once via `rglob("*")`
3. Files grouped by extension, returned as `dict[str, list[Path]]`
4. Call site extracts needed extension bucket: `result[".py"]`
5. Call site applies any remaining post-filters (e.g., underscore exclusion)

---

## 3. Detailed Design

### 3.1 fs_utils Extension

`collect_files()` needs one addition: a `names` parameter for Pattern C (Dockerfile matching).

```python
def collect_files(
    root: Path,
    extensions: set[str] | None = None,
    exclude_dirs: set[str] = _DEFAULT_EXCLUDES,
    names: set[str] | None = None,  # NEW: match by filename substring
) -> dict[str, list[Path]]:
```

When `names` is provided, files matching any name pattern are included in a `"_by_name"` bucket regardless of extension. This handles Dockerfile variants (`Dockerfile`, `prod.Dockerfile`, `Dockerfile.dev`).

**Alternative considered**: Keep Pattern C sites as-is since they already do `rglob("*")` with inline filtering. The adapters scan project roots which can be large — using `collect_files()` gives them exclusion of hidden dirs and `__pycache__` for free.

**Decision**: Add `names` parameter. It's 4 lines of code and serves 3 call sites.

### 3.2 Migration Patterns

**Pattern A** (10 sites): Single-extension
```python
# Before:
py_files = sorted(root_dir.rglob("*.py"))

# After:
from zerg.fs_utils import collect_files
grouped = collect_files(root_dir, extensions={".py"})
py_files = grouped.get(".py", [])
```

**Pattern B** (4 sites): Multi-extension loop
```python
# Before:
files = []
for ext in ["*.py", "*.js", "*.ts", "*.go", "*.rs"]:
    files.extend(str(f) for f in target.rglob(ext))

# After:
from zerg.fs_utils import collect_files
grouped = collect_files(target, extensions={".py", ".js", ".ts", ".go", ".rs"})
files = [str(f) for ext in grouped for f in grouped[ext]]
```

**Pattern C** (3 sites): Name-based matching
```python
# Before (dive_adapter.py / hadolint_adapter.py):
for p in sorted(root.rglob("*")):
    if not p.is_file():
        continue
    if name.endswith(".Dockerfile") or name.startswith("Dockerfile."):
        results.append(p)

# After:
from zerg.fs_utils import collect_files
grouped = collect_files(root, names={"Dockerfile"})
dockerfiles = grouped.get("_by_name", [])
```

For `detector.py`, which classifies ALL files:
```python
# Before:
for child in sorted(directory.rglob("*")):
    ...

# After:
grouped = collect_files(directory, extensions=None)
all_files = sorted(f for ext_files in grouped.values() for f in ext_files)
```

---

## 4. Key Decisions

### 4.1 Add `names` Parameter vs Keep Pattern C As-Is

**Context**: 3 call sites use `rglob("*")` with name-based filtering. They already do a single traversal but lack exclusion of hidden/cache dirs.

**Options**:
1. Keep as-is — already single-traversal
2. Add `names` param to `collect_files()` — standardize + get free exclusion
3. Create separate `find_by_name()` function

**Decision**: Option 2 — add `names` param.

**Rationale**: Minimal code addition (4 lines), gives Pattern C sites consistent exclusion behavior, avoids proliferating utility functions.

### 4.2 Document Exceptions vs Force-Migrate

**Context**: `rush.py:323` scans `.gsd/` (tiny), `ast_analyzer.py:450` takes a dynamic pattern parameter.

**Decision**: Document as exceptions.

**Rationale**: rush.py scans ~20 files max. ast_analyzer.py's dynamic pattern doesn't map to `collect_files()` API without over-engineering. Cost of migration exceeds benefit.

### 4.3 Post-Filtering Responsibility

**Context**: Some sites filter by underscore prefix (`wiki.py`, `analyze.py`) or by "test" in name (`test_cmd.py`). Should `collect_files()` handle this?

**Decision**: Keep post-filtering at call sites.

**Rationale**: These filters are domain-specific (e.g., "skip __init__.py" is an analysis concern, not a filesystem concern). `collect_files()` handles universal exclusions (hidden dirs, caches). Domain filters stay local.

---

## 5. Implementation Plan

### 5.1 Phase Summary

| Phase | Tasks | Parallel | Est. Time |
|-------|-------|----------|-----------|
| Foundation | 1 | No | 5 min |
| Core — Batch 1 | 5 | Yes | 10 min |
| Core — Batch 2 | 5 | Yes | 10 min |
| Core — Batch 3 | 4 | Yes | 10 min |
| Verification | 1 | No | 5 min |

### 5.2 File Ownership

| File | Task ID | Operation |
|------|---------|-----------|
| `zerg/fs_utils.py` | TASK-001 | modify |
| `zerg/doc_engine/dependencies.py` | TASK-002 | modify |
| `zerg/validate_commands.py` | TASK-003 | modify |
| `zerg/test_scope.py` | TASK-004 | modify |
| `zerg/commands/analyze.py` | TASK-005 | modify |
| `zerg/commands/wiki.py` | TASK-006 | modify |
| `zerg/commands/refactor.py` | TASK-007 | modify |
| `zerg/diagnostics/code_fixer.py` | TASK-008 | modify |
| `zerg/commands/test_cmd.py` | TASK-009 | modify |
| `zerg/security_rules.py` | TASK-010 | modify |
| `zerg/commands/build.py` | TASK-011 | modify |
| `zerg/commands/review.py` | TASK-012 | modify |
| `zerg/doc_engine/detector.py` | TASK-013 | modify |
| `zerg/performance/adapters/dive_adapter.py` | TASK-014 | modify |
| `zerg/performance/adapters/hadolint_adapter.py` | TASK-015 | modify |

### 5.3 Dependency Graph

```
Level 1 (Foundation):
  TASK-001: Extend fs_utils.collect_files() with names param

Level 2 (Core — Batch 1, all parallel):
  TASK-002: dependencies.py         ──depends──▶ TASK-001
  TASK-003: validate_commands.py    ──depends──▶ TASK-001
  TASK-004: test_scope.py           ──depends──▶ TASK-001
  TASK-005: analyze.py (3 sites)    ──depends──▶ TASK-001
  TASK-006: wiki.py                 ──depends──▶ TASK-001

Level 2 (Core — Batch 2, all parallel):
  TASK-007: refactor.py             ──depends──▶ TASK-001
  TASK-008: code_fixer.py           ──depends──▶ TASK-001
  TASK-009: test_cmd.py (2 sites)   ──depends──▶ TASK-001
  TASK-010: security_rules.py       ──depends──▶ TASK-001
  TASK-011: build.py                ──depends──▶ TASK-001

Level 2 (Core — Batch 3, all parallel):
  TASK-012: review.py               ──depends──▶ TASK-001
  TASK-013: detector.py             ──depends──▶ TASK-001
  TASK-014: dive_adapter.py         ──depends──▶ TASK-001
  TASK-015: hadolint_adapter.py     ──depends──▶ TASK-001

Level 3 (Verification):
  TASK-016: Full verification       ──depends──▶ TASK-002..015
```

Note: All Level 2 tasks are independent of each other (no shared files). Batching is for worker count limits only — with enough workers, all 14 can run simultaneously.

---

## 6. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| `_DEFAULT_EXCLUDES` filters out files a module needs | Medium | Medium | Each task verifies existing tests pass |
| `names` param introduces suffix-less file bug | Low | Low | Test Dockerfile discovery specifically |
| `collect_files()` returns sorted lists but caller expected unsorted | Low | Low | `collect_files()` already sorts; no behavior change |
| File with no suffix skipped (e.g. `Makefile`) | Low | Low | Only affects Pattern C sites; `names` param handles this |

---

## 7. Testing Strategy

### 7.1 Unit Tests
No new unit tests. This is a pure refactor — existing tests validate behavior.

### 7.2 Integration Tests
Each task runs the full test suite as verification.

### 7.3 Verification Commands
- Per-task: `python -m pytest tests/ -x -q --tb=short` (fast fail)
- Final: `ruff check zerg/` + `grep -r '\.rglob(' zerg/ --include='*.py'` to confirm only exceptions remain

---

## 8. Parallel Execution Notes

### 8.1 Safe Parallelization
- TASK-001 (foundation) must complete first
- All 14 migration tasks (TASK-002..015) are fully independent — no shared files
- TASK-016 (verification) runs after all migrations

### 8.2 Recommended Workers
- Minimum: 1 worker (sequential)
- Optimal: 5 workers (14 tasks / ~3 per worker)
- Maximum: 14 workers (one per migration task)

### 8.3 Estimated Duration
- Single worker: ~40 min
- With 5 workers: ~15 min
- Speedup: ~2.7x

---

## 9. Documented Exceptions

These rglob calls are intentionally NOT migrated:

| File | Line | Reason |
|------|------|--------|
| `zerg/fs_utils.py:58` | `root.rglob("*")` | Canonical implementation itself |
| `zerg/security_rules.py:220` | `project_path.rglob("*")` | Already single-pass with inline filtering |
| `zerg/commands/rush.py:323` | `Path(".gsd").rglob("task-graph.json")` | Tiny directory (~20 files), specialized pattern |
| `zerg/ast_analyzer.py:450` | `directory.rglob(file_pattern)` | Dynamic pattern parameter; would require API redesign |

---

## 10. Approval

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Architecture | | | PENDING |
| Engineering | | | PENDING |
