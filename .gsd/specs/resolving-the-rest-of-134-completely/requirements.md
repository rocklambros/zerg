# Requirements: Resolve the Rest of GitHub Issue #134 Completely

## Metadata
- **Feature**: resolving-the-rest-of-134-completely
- **Status**: APPROVED
- **Created**: 2026-02-06
- **Issue**: https://github.com/klambros/ZERG/issues/134
- **Title**: Performance: Multiple rglob scans traverse directory tree repeatedly

---

## 1. Problem Statement

Issue #134 identified that ZERG performs redundant `rglob` directory traversals across multiple modules. A shared `fs_utils.collect_files()` utility was created (PR #161) and adopted by `repo_map.py` and `stack_detector.py`, but **18 rglob calls across 16 files** remain unconverted.

Each unconverted `rglob` call independently walks the directory tree, wasting I/O on large projects. The fix is mechanical: replace each scattered `rglob` with a call to `fs_utils.collect_files()` (or a thin wrapper), preserving existing filter/exclusion behavior.

---

## 2. Current State

### Already Migrated (2 modules)
| Module | Status |
|--------|--------|
| `zerg/repo_map.py` | Uses `collect_files()` |
| `zerg/performance/stack_detector.py` | Uses `collect_files()` |

### fs_utils.py Itself (1 call — canonical, no change needed)
| Module | Line | Pattern |
|--------|------|---------|
| `zerg/fs_utils.py:58` | `root.rglob("*")` | The single-pass implementation itself |

### Already Single-Pass (1 call — no change needed)
| Module | Line | Pattern |
|--------|------|---------|
| `zerg/security_rules.py:220` | `project_path.rglob("*")` | Already walks once with inline filtering |

### Remaining rglob Calls to Migrate (18 calls across 16 files)

**Pattern A — Single-extension rglob (10 calls)**
Simple `rglob("*.py")` or `rglob("*.md")` replaceable with `collect_files(root, extensions={".py"})`.

| # | File:Line | Current Call | Extension |
|---|-----------|-------------|-----------|
| 1 | `zerg/doc_engine/dependencies.py:134` | `root_dir.rglob("*.py")` | `.py` |
| 2 | `zerg/validate_commands.py:501` | `package_dir.rglob("*.py")` | `.py` |
| 3 | `zerg/test_scope.py:153` | `tests_dir.rglob("*.py")` | `.py` |
| 4 | `zerg/commands/analyze.py:570` | `scope_path.rglob("*.py")` | `.py` |
| 5 | `zerg/commands/analyze.py:635` | `scope_path.rglob("*.py")` | `.py` |
| 6 | `zerg/commands/wiki.py:99` | `(project_root / "zerg").rglob("*.py")` | `.py` |
| 7 | `zerg/commands/refactor.py:424` | `target.rglob("*.py")` | `.py` |
| 8 | `zerg/diagnostics/code_fixer.py:65` | `project_root.rglob("*.py")` | `.py` |
| 9 | `zerg/commands/test_cmd.py:574` | `source_dir.rglob("*.py")` | `.py` |
| 10 | `zerg/security_rules.py:611` | `rules_dir.rglob("*.md")` | `.md` |

**Pattern B — Multi-extension loop (4 calls)**
Loop over multiple extensions, each calling `rglob(ext)`. Replace with single `collect_files()` call.

| # | File:Line | Extensions |
|---|-----------|-----------|
| 11 | `zerg/commands/analyze.py:866` | `.py`, `.js`, `.ts`, `.go`, `.rs` |
| 12 | `zerg/commands/build.py:380` | `.py`, `.js`, `.ts`, `.go`, `.rs`, `.java` |
| 13 | `zerg/commands/test_cmd.py:458` | `.py`, `.js`, `.ts`, `.go`, `.rs` |
| 14 | `zerg/commands/review.py:400` | `.py`, `.js`, `.ts`, `.go`, `.rs` |

**Pattern C — Wildcard rglob with inline filtering (3 calls)**
`rglob("*")` with custom `is_file()` / name checks. May need `collect_files()` or keep as-is if filter logic is unique.

| # | File:Line | Notes |
|---|-----------|-------|
| 15 | `zerg/doc_engine/detector.py:84` | `directory.rglob("*")` — classifies all files |
| 16 | `zerg/performance/adapters/dive_adapter.py:69` | `root.rglob("*")` — finds Dockerfiles by name |
| 17 | `zerg/performance/adapters/hadolint_adapter.py:69` | `root.rglob("*")` — finds Dockerfiles by name |

**Pattern D — Specialized pattern (1 call)**
| # | File:Line | Notes |
|---|-----------|-------|
| 18 | `zerg/commands/rush.py:323` | `Path(".gsd").rglob("task-graph.json")` — tiny dir, low impact |

**Pattern E — Dynamic pattern (1 call)**
| # | File:Line | Notes |
|---|-----------|-------|
| 19 | `zerg/ast_analyzer.py:450` | `directory.rglob(file_pattern)` — pattern is a parameter |

---

## 3. Functional Requirements

### FR-1: Migrate Pattern A calls to `collect_files()`
Convert all 10 single-extension rglob calls to use `fs_utils.collect_files()`. Each site gets the flat list from the grouped dict: `collect_files(root, {".py"})[".py"]`.

### FR-2: Migrate Pattern B calls to `collect_files()`
Convert all 4 multi-extension loop sites. Replace the for-loop-over-extensions pattern with a single `collect_files()` call that returns all needed extensions at once.

### FR-3: Migrate Pattern C calls where beneficial
The 3 wildcard rglob sites (`detector.py`, `dive_adapter.py`, `hadolint_adapter.py`) already do `rglob("*")` with filtering. Evaluate whether `collect_files()` with `extensions=None` provides meaningful benefit. If the directory is small or the filtering is highly specialized (e.g. Dockerfile name matching), document the decision to keep or convert.

### FR-4: Handle Pattern D and E pragmatically
- `rush.py:323` — `.gsd` is tiny. Document as intentionally kept (negligible perf impact).
- `ast_analyzer.py:450` — Dynamic pattern parameter. Add `collect_files()` support or document exception.

### FR-5: Extend `collect_files()` if needed
If any migration site needs capabilities `collect_files()` doesn't have (e.g. name-based matching, suffix-less files), extend the function minimally. Do NOT over-engineer — only add what actual call sites need.

### FR-6: Preserve existing exclusion behavior
Each call site may have its own exclusion logic (e.g. `__pycache__`, hidden dirs, test files). The migration must preserve identical file sets. Default excludes in `fs_utils._DEFAULT_EXCLUDES` cover most cases but verify per-site.

### FR-7: No behavioral changes
This is a pure refactor. No module should return different results after migration. Tests must pass identically.

---

## 4. Non-Functional Requirements

### NFR-1: Performance
The whole point of #134. After migration, repeated directory scans within a single invocation should share results where possible.

### NFR-2: No new dependencies
`fs_utils` uses only `pathlib`. Keep it that way.

### NFR-3: Test coverage
Each migrated site must have its existing tests still pass. No new test files needed — this is a refactor.

---

## 5. Scope Boundaries

### In Scope
- All 19 rglob call sites listed above (minus fs_utils.py itself)
- Minimal extensions to `collect_files()` if required
- Updating imports in affected modules

### Out of Scope
- Test file rglob calls (only production `zerg/` code)
- Performance benchmarking (the improvement is self-evident: fewer traversals)
- Caching/memoization of collect_files results across calls (future optimization)

---

## 6. Acceptance Criteria

1. `grep -r '\.rglob(' zerg/ --include='*.py'` returns ONLY:
   - `zerg/fs_utils.py:58` (the canonical single-pass)
   - Any explicitly documented exceptions (rush.py, ast_analyzer.py, security_rules.py:220)
2. `make test` passes (or equivalent CI suite)
3. `ruff check` passes
4. `mypy` passes
5. No new files created except if `collect_files()` needs a helper

---

## 7. Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Subtle filter difference breaks a module | Medium | Medium | Verify each site's exclusion logic matches `_DEFAULT_EXCLUDES` |
| `collect_files()` needs extension that bloats API | Low | Low | Keep extensions minimal and optional |
| Performance regression from collecting too many files | Low | Low | Use `extensions` parameter to limit scope |

---

## 8. Open Questions

None — scope is well-defined and purely mechanical.
