# Technical Design: fix-codeql-scanning-alerts

## Metadata
- **Feature**: fix-codeql-scanning-alerts
- **Status**: DRAFT
- **Created**: 2026-02-15
- **Author**: Factory Design Mode

---

## 1. Overview

### 1.1 Summary
Resolve all 115 open CodeQL code scanning alerts through targeted code fixes (comments, dead code removal, security hardening) and GitHub UI dismissal of ~17 genuine false positives. Additionally fix the `/z:plan` WORKFLOW BOUNDARY bug that prevents spec file generation. No behavioral changes to existing code — only safety/quality improvements.

### 1.2 Goals
- Zero open CodeQL alerts on the main branch
- Fix 3 HIGH-severity security vulnerabilities
- Fix `/z:plan` command to reliably produce spec files
- All existing tests continue to pass

### 1.3 Non-Goals
- Refactoring code beyond minimum needed to resolve alerts
- Adding `.github/codeql-config.yml` query exclusions
- Addressing broader exception handling debt (issue #137)

---

## 2. Architecture

### 2.1 High-Level Design

This is a bulk edit task, not a traditional feature. No new components or data flows are introduced.

```
┌────────────────────────────────────────────┐
│           115 CodeQL Alerts                │
├──────┬──────┬──────┬──────┬───────┬───────┤
│ Sec  │Empty │Dead  │Import│ Misc  │ FP    │
│  3   │Except│ Code │  21  │  14   │  17   │
│      │  33  │  27  │      │       │       │
├──────┴──────┴──────┴──────┴───────┴───────┤
│  Code Fixes: ~98        Dismiss: ~17      │
└────────────────────────────────────────────┘
```

### 2.2 Fix Strategies by Alert Category

| Category | Count | Strategy | Risk |
|----------|-------|----------|------|
| Security (HIGH) | 3 | Code fix: `html.escape()`, `0o700` | Low — safer behavior |
| Empty except | 33 | Add comment to `pass` line | Zero — comment only |
| Unused globals | 8 | Remove dead definitions | Low — verified unused |
| Unused loggers | 4 | Verify usage; remove if dead | Low |
| Unused imports | 7 | Remove import statements | Zero |
| Unused locals | 5 | Remove or prefix `_` | Zero |
| Import-and-import-from | 9 | Consolidate or note test pattern | Low |
| Cyclic imports | 12 | GitHub UI dismiss (TYPE_CHECKING guards) | Zero |
| Undefined exports | 3 | GitHub UI dismiss (`__getattr__` pattern) | Zero |
| Multiple definitions | 3 | Remove redundant assignments | Low |
| Redundant comparison | 2 | Simplify conditions | Low |
| Misc (7) | 7 | Mixed: code fix + dismiss | Low |
| Plan command fix | 2 files | Already implemented | Zero |

### 2.3 Data Flow
No changes to data flow. All fixes are:
- Adding comments to existing code (empty except)
- Removing dead code (unused globals/imports/locals)
- Replacing unsafe patterns with safe ones (security)
- No new modules, no new interfaces

---

## 3. Detailed Design

### 3.1 Security Fix: HTML Sanitization (pr_engine.py:63)

**Before:**
```python
sanitized = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
sanitized = re.sub(r"<iframe[^>]*>.*?</iframe>", "", sanitized, flags=re.DOTALL | re.IGNORECASE)
```

**After:**
```python
import html
sanitized = html.escape(text, quote=True)
```

Rationale: Regex-based HTML stripping is bypassable (nested tags, encoding tricks). `html.escape()` is comprehensive — escapes `<`, `>`, `&`, `"`, `'`. Since PR body is Markdown, HTML entities are rendered safely.

### 3.2 Security Fix: File Permissions (history_engine.py:572,664)

**Before:** `os.chmod(script_path, 0o755)`
**After:** `os.chmod(script_path, 0o700)`

Rationale: These are temp GIT_SEQUENCE_EDITOR scripts. Only the owner needs execute permission. World-readable+executable temp scripts are a security risk (CWE-732).

### 3.3 Empty Except Pattern

**Before:** `pass`
**After:** `pass  # <contextual reason>`

Comment templates by context:
- File/resource cleanup: `pass  # Best-effort cleanup`
- Process/tool detection: `pass  # Optional tool not available`
- Config fallback: `pass  # Fall through to default`
- Lock/heartbeat: `pass  # Best-effort; non-critical`
- JSON parsing: `pass  # Malformed data; skip entry`
- Git operations: `pass  # Best-effort git cleanup`
- Keyboard interrupt: `pass  # Suppress interrupt during shutdown`

### 3.4 Plan Command Fix

**Already implemented.** Changes in plan.md and plan.core.md:
- Replaced overbroad "MUST NEVER run implementation tools" with explicit PROHIBITED/REQUIRED/ALLOWED sections
- REQUIRED section mandates Write tool for `.gsd/specs/` files
- Added `.plan-complete` sentinel file write in Phase 5.5

---

## 4. Key Decisions

### Decision: html.escape() over allowlist stripping

**Context**: PR body text contains user-generated content that could include HTML injection.
**Options**: (1) Regex strip specific tags, (2) html.escape() all HTML, (3) bleach/sanitizer library
**Decision**: html.escape() — zero dependencies, comprehensive, correct for Markdown context.
**Consequences**: All HTML in PR bodies becomes entities. Since GitHub renders Markdown, this is safe and correct.

### Decision: GitHub UI dismissal for false positives

**Context**: ~17 CodeQL alerts are genuine false positives (TYPE_CHECKING guards, __getattr__ lazy loading, intentional test fixtures).
**Options**: (1) Refactor code to avoid patterns, (2) .github/codeql-config.yml exclusions, (3) GitHub UI dismiss
**Decision**: GitHub UI dismiss with "False positive" reason.
**Consequences**: Alerts disappear from dashboard. New alerts of same type in same patterns will need manual dismissal. This is simpler than config exclusions and doesn't require code restructuring of correct patterns.

### Decision: Comments over code changes for empty except

**Context**: 33 empty except blocks with bare `pass` trigger CodeQL EmptyExcept.
**Options**: (1) Add logging, (2) Add comment, (3) Narrow exception type
**Decision**: Add comment. These are intentionally silent (best-effort cleanup, optional tool detection).
**Consequences**: CodeQL resolves the alert. No behavioral change. Clear documentation of intent.

---

## 5. Implementation Plan

### 5.1 Phase Summary

| Phase | Level | Tasks | Parallel | Est. Time |
|-------|-------|-------|----------|-----------|
| Fixes | 1 | 9 | Yes (all) | ~15 min each |
| Quality | 2 | 1 | No | ~10 min |

### 5.2 File Ownership

| File | Task | Operation |
|------|------|-----------|
| zerg/git/pr_engine.py | TASK-001 | modify |
| zerg/git/history_engine.py | TASK-001 | modify |
| zerg/git/bisect_engine.py | TASK-001 | modify |
| zerg/git/release_engine.py | TASK-001 | modify |
| zerg/data/commands/plan.md | TASK-002 | modify (done) |
| zerg/data/commands/plan.core.md | TASK-002 | modify (done) |
| zerg/commands/_utils.py | TASK-003 | modify |
| zerg/commands/build.py | TASK-003 | modify |
| zerg/commands/init.py | TASK-003 | modify |
| zerg/commands/install_commands.py | TASK-003 | modify |
| zerg/commands/git_cmd.py | TASK-003 | modify |
| zerg/commands/test_cmd.py | TASK-003 | modify |
| zerg/commands/logs.py | TASK-003 | modify |
| zerg/commands/status.py | TASK-003 | modify |
| zerg/commands/debug.py | TASK-003 | modify |
| zerg/commands/design.py | TASK-003 | modify |
| zerg/commands/document.py | TASK-003 | modify |
| zerg/commands/wiki.py | TASK-003 | modify |
| zerg/formatter_detector.py | TASK-004 | modify |
| zerg/validate_commands.py | TASK-004 | modify |
| zerg/token_tracker.py | TASK-004 | modify |
| zerg/token_counter.py | TASK-004 | modify |
| zerg/mcp_router.py | TASK-004 | modify |
| zerg/repo_map.py | TASK-004 | modify |
| zerg/repo_map_js.py | TASK-004 | modify |
| zerg/progress_reporter.py | TASK-004 | modify |
| zerg/log_aggregator.py | TASK-004 | modify |
| zerg/heartbeat.py | TASK-004 | modify |
| zerg/dryrun.py | TASK-004 | modify |
| zerg/orchestrator.py | TASK-004 | modify |
| zerg/async_helpers.py | TASK-004 | modify |
| zerg/cleanup.py | TASK-004 | modify |
| zerg/status_formatter.py | TASK-004 | modify |
| zerg/backlog.py | TASK-004 | modify |
| zerg/protocol_types.py | TASK-004 | modify |
| zerg/diagnostics/system_diagnostics.py | TASK-005 | modify |
| zerg/diagnostics/env_diagnostics.py | TASK-005 | modify |
| zerg/diagnostics/log_correlator.py | TASK-005 | modify |
| zerg/diagnostics/knowledge_base.py | TASK-005 | modify |
| zerg/diagnostics/hypothesis_engine.py | TASK-005 | modify |
| zerg/diagnostics/error_intel.py | TASK-005 | modify |
| zerg/diagnostics/code_fixer.py | TASK-005 | modify |
| zerg/diagnostics/recovery.py | TASK-005 | modify |
| zerg/performance/stack_detector.py | TASK-005 | modify |
| zerg/performance/catalog.py | TASK-005 | modify |
| zerg/performance/adapters/dive_adapter.py | TASK-005 | modify |
| zerg/security/scanner.py | TASK-006 | modify |
| zerg/security/rules.py | TASK-006 | modify |
| zerg/security/cve.py | TASK-006 | modify |
| zerg/rendering/status_renderer.py | TASK-006 | modify |
| zerg/rendering/dryrun_renderer.py | TASK-006 | modify |
| zerg/rendering/shared.py | TASK-006 | modify |
| zerg/launchers/__init__.py | TASK-006 | modify |
| zerg/doc_engine/detector.py | TASK-006 | modify |
| .zerg/security.py | TASK-007 | modify |
| .zerg/rush.py | TASK-007 | modify |
| .zerg/quality_tools.py | TASK-007 | modify |
| .zerg/container.py | TASK-007 | modify |
| .zerg/git_ops.py | TASK-007 | modify |
| tests/unit/test_worker_commit.py | TASK-008 | modify |
| tests/unit/test_small_modules.py | TASK-008 | modify |
| tests/unit/test_main_entry.py | TASK-008 | modify |
| tests/unit/test_worker_protocol.py | TASK-008 | modify |
| tests/unit/test_schemas.py | TASK-008 | modify |
| tests/fixtures/hook_samples/clean/test_file.py | TASK-008 | modify |
| tests/fixtures/state_fixtures.py | TASK-008 | modify |
| tests/fixtures/orchestrator_fixtures.py | TASK-008 | modify |
| .zerg/tests/mocks/mock_state.py | TASK-008 | modify |
| tests/mocks/mock_launcher.py | TASK-008 | modify |
| zerg/verify.py | TASK-009 | modify |
| zerg/verification_gates.py | TASK-009 | modify |
| zerg/level_coordinator.py | TASK-009 | modify |
| zerg/merge.py | TASK-009 | modify |
| CHANGELOG.md | TASK-010 | modify |

### 5.3 Consumer Matrix

All tasks are leaf tasks (no new modules created, only modifications to existing files). No consumer matrix needed.

### 5.4 Dependency Graph

```
Level 1 (all parallel):
  TASK-001 ──┐
  TASK-002 ──┤
  TASK-003 ──┤
  TASK-004 ──┤
  TASK-005 ──┼──▶ TASK-010 (CHANGELOG + verification)
  TASK-006 ──┤
  TASK-007 ──┤
  TASK-008 ──┤
  TASK-009 ──┘

Level 2:
  TASK-010 (depends on all Level 1)
```

---

## 6. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Removing "unused" code that's actually used | Low | Medium | Grep for all references before removing |
| html.escape() breaks PR body rendering | Low | Low | GitHub renders Markdown entities correctly |
| Empty except comments don't resolve CodeQL | Low | Low | Verify against CodeQL query logic |
| Test regressions from import cleanup | Low | Medium | Run full test suite in verification |

---

## 7. Testing Strategy

### 7.1 Unit Tests
No new tests needed. All changes are comment additions, dead code removal, or security hardening. Existing tests validate current behavior is preserved.

### 7.2 Verification Commands

Per-task verification:
- `ruff check {owned_files}` — no new lint errors
- `python -m py_compile {file}` — syntax valid

Global verification (TASK-010):
- `python -m pytest tests/ --timeout=120` — full suite green
- `python -m zerg.validate_commands` — drift check clean
- `ruff check zerg/ tests/` — no new lint errors

---

## 8. Parallel Execution Notes

### 8.1 Safe Parallelization
- All Level 1 tasks have zero dependencies and zero file overlap
- Each task owns exclusive files — no merge conflicts possible
- Tasks are edit-only (no file creation) — no directory race conditions

### 8.2 Recommended Workers
- Minimum: 1 worker (sequential, ~90 min)
- Optimal: 5 workers (covers widest level efficiently, ~20 min)
- Maximum: 9 workers (one per L1 task, ~15 min)

### 8.3 Estimated Duration
- Single worker: ~90 minutes
- With 5 workers: ~20 minutes
- With 9 workers: ~15 minutes
- Speedup: 5-6x

---

## 9. False Positives Requiring GitHub UI Dismissal

After all code fixes, these ~17 alerts need manual dismissal as "False positive" in GitHub Security tab:

| Count | Query | Files | Reason |
|-------|-------|-------|--------|
| 12 | py/cyclic-import | verify.py, verification_gates.py, level_coordinator.py, merge.py, dryrun.py, dryrun_renderer.py, shared.py, debug.py, recovery.py | TYPE_CHECKING guards already prevent runtime cycles |
| 3 | py/undefined-export | launchers/__init__.py | `__getattr__` handles lazy loading; names in `__all__` |
| 1 | py/unused-global-variable | protocol_types.py (_SENTINEL) | Used cross-file by protocol_state.py |
| 1 | py/syntax-error | test fixture | Intentional merge conflict test fixture |

---

## 10. Approval

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Architecture | | | PENDING |
| Engineering | | | PENDING |
