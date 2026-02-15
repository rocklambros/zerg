# Technical Design: security-hardening-addendum

## Metadata
- **Feature**: security-hardening-addendum
- **Status**: APPROVED
- **Created**: 2026-02-15
- **Author**: Factory Design Mode
- **Parent Branch**: fix/codeql-scanning-alerts

---

## 1. Overview

### 1.1 Summary
Apply 4 defense-in-depth hardening fixes across 2 files: sanitize PR titles at output boundaries in `pr_engine.py` (2 locations) and eliminate temp file permission race windows in `history_engine.py` (2 locations). All changes are minimal, non-behavioral, and use existing patterns/functions already in the codebase.

### 1.2 Goals
- PR title sanitized at output boundary (consistency with body sanitization)
- Temp rebase scripts created with 0o700 from the start (no race window)

### 1.3 Non-Goals
- Refactoring `_sanitize_pr_content()` itself
- Adding new tests (existing suite covers these paths)
- Addressing any other security findings

---

## 2. Architecture

### 2.1 High-Level Design

No architectural changes. Two localized hardening patterns applied to existing code:

```
PR Title Flow (BEFORE):
  raw title → subprocess.run() args list
  raw title → draft markdown file

PR Title Flow (AFTER):
  raw title → _sanitize_pr_content() → subprocess.run() args list
  raw title → _sanitize_pr_content() → draft markdown file

Temp Script Flow (BEFORE):
  NamedTemporaryFile(delete=False) → write → os.chmod(0o700)
  [race window: default umask permissions until chmod]

Temp Script Flow (AFTER):
  mkstemp() → os.fchmod(fd, 0o700) → os.fdopen(fd) → write
  [no race window: permissions set before any content written]
```

### 2.2 Component Breakdown

| Component | Responsibility | Files |
|-----------|---------------|-------|
| PRCreator.create() | PR creation via gh CLI | zerg/git/pr_engine.py |
| PRCreator._save_draft() | Draft file fallback | zerg/git/pr_engine.py |
| HistoryEngine._squash_commits() | Git rebase squash script | zerg/git/history_engine.py |
| HistoryEngine._reorder_commits() | Git rebase reorder script | zerg/git/history_engine.py |

### 2.3 Data Flow
- **PR title**: `pr_data["title"]` → `_sanitize_pr_content()` → `html.escape()` → safe string
- **Temp script**: `tempfile.mkstemp()` returns `(fd, path)` → `os.fchmod(fd, 0o700)` → `os.fdopen(fd, "w")` → write script content

---

## 3. Detailed Design

### 3.1 PR Title Sanitization (pr_engine.py)

**Location 1 — `create()` method, line 509:**
```python
# BEFORE:
title = pr_data.get("title", "Update")

# AFTER:
title = _sanitize_pr_content(pr_data.get("title", "Update"))
```

**Location 2 — `_save_draft()` method, line 586:**
```python
# BEFORE:
content = f"# {pr_data.get('title', 'PR Draft')}\n\n{pr_data.get('body', '')}"

# AFTER:
content = f"# {_sanitize_pr_content(pr_data.get('title', 'PR Draft'))}\n\n{pr_data.get('body', '')}"
```

### 3.2 Temp File Permission Hardening (history_engine.py)

**Location 1 — `_squash_commits()`, lines 546-570:**
```python
# BEFORE:
with tempfile.NamedTemporaryFile(
    mode="w", suffix=".py", delete=False, prefix="zerg_rebase_",
) as script_file:
    script_path = script_file.name
    # ... write content ...
os.chmod(script_path, 0o700)

# AFTER:
fd, script_path = tempfile.mkstemp(suffix=".py", prefix="zerg_rebase_")
os.fchmod(fd, 0o700)
with os.fdopen(fd, "w") as script_file:
    # ... write content (unchanged) ...
# os.chmod removed — permissions already set via fchmod
```

**Location 2 — `_reorder_commits()`, lines 633-662:**
```python
# BEFORE:
with tempfile.NamedTemporaryFile(
    mode="w", suffix=".py", delete=False, prefix="zerg_reorder_",
) as script_file:
    script_path = script_file.name
    # ... write content ...
os.chmod(script_path, 0o700)

# AFTER:
fd, script_path = tempfile.mkstemp(suffix=".py", prefix="zerg_reorder_")
os.fchmod(fd, 0o700)
with os.fdopen(fd, "w") as script_file:
    # ... write content (unchanged) ...
# os.chmod removed — permissions already set via fchmod
```

---

## 4. Key Decisions

### 4.1 Use `_sanitize_pr_content()` for Title (Not a New Function)

**Context**: PR title needs sanitization. Could create a title-specific function or reuse existing.

**Decision**: Reuse `_sanitize_pr_content()` — it uses `html.escape()` which is safe for all text.

**Rationale**: Function already exists, is well-tested via body path, and provides consistent behavior.

### 4.2 Use `mkstemp` + `fchmod` (Not `opener` Kwarg)

**Context**: Need atomic secure file creation. Options: `mkstemp`+`fchmod`, `os.open`+`os.fdopen`, or `open(opener=...)`.

**Decision**: `mkstemp` + `fchmod` — simplest, most explicit, stdlib-only.

**Rationale**: `mkstemp` returns an fd, `fchmod` sets permissions before any content is written. Clear pattern, no race window.

---

## 5. Implementation Plan

### 5.1 Phase Summary

| Phase | Tasks | Parallel | Est. Time |
|-------|-------|----------|-----------|
| Core | 2 | Yes | 3 min |
| Quality | 1 | No | 2 min |

### 5.2 File Ownership

| File | Task ID | Operation |
|------|---------|-----------|
| zerg/git/pr_engine.py | TASK-001 | modify |
| zerg/git/history_engine.py | TASK-002 | modify |
| CHANGELOG.md | TASK-003 | modify |

### 5.3 Dependency Graph

```
TASK-001 [PR title sanitization] ──┐
                                    ├──▶ TASK-003 [CHANGELOG + verify]
TASK-002 [Temp file hardening]  ───┘
```

---

## 6. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| `os.fchmod` not available on platform | Very Low | Med | Python stdlib on all POSIX; not used on Windows |
| `_sanitize_pr_content` over-escapes title | Low | Low | Uses `html.escape()` which is idempotent and safe |
| Existing tests break | Very Low | Med | Changes are non-behavioral; run full suite |

---

## 7. Testing Strategy

### 7.1 Verification
- `python -m pytest tests/ --timeout=120` — full suite green
- `ruff check zerg/git/pr_engine.py zerg/git/history_engine.py` — clean

### 7.2 No New Tests Required
Existing test suite covers PR creation and history engine paths. Changes are non-behavioral.

---

## 8. Parallel Execution Notes

### 8.1 Safe Parallelization
- TASK-001 and TASK-002 modify different files — fully parallel
- TASK-003 depends on both completing

### 8.2 Recommended Workers
- Minimum: 1 worker (sequential)
- Optimal: 2 workers (one per file)
- Maximum: 2 workers

### 8.3 Estimated Duration
- Single worker: ~5 min
- With 2 workers: ~3 min
- Speedup: 1.7x

---

## 9. Approval

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Architecture | | | PENDING |
| Engineering | | | PENDING |
