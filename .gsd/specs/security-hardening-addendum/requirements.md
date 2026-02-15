# Feature Requirements: security-hardening-addendum

## Metadata
- **Feature**: security-hardening-addendum
- **Status**: APPROVED
- **Created**: 2026-02-15
- **Author**: Factory Plan Mode
- **Parent**: fix/codeql-scanning-alerts (addendum to existing branch)

---

## 1. Problem Statement

### 1.1 Background
Security review of `review-fixes-before-merge` identified 2 pre-existing low-severity hardening opportunities. Neither is exploitable in the current deployment context, but both violate defense-in-depth principles.

### 1.2 Problem
- **PR title not sanitized**: `_generate_title()` returns raw `commit.message` data. While the title is passed as a list element to `subprocess.run()` (no shell injection) and GitHub sanitizes server-side, the PR body is sanitized at output boundary but the title is not — an asymmetry that could become exploitable if the code is adapted for non-GitHub platforms.
- **Temp file permission race window**: `tempfile.NamedTemporaryFile(delete=False)` creates files with system default umask (commonly 0o644), then `os.chmod(script_path, 0o700)` tightens permissions after the write. Brief window where file is world-readable.

### 1.3 Impact
Low. Neither is currently exploitable. Fixes bring consistency with OWASP defense-in-depth and CWE-377 best practices.

---

## 2. Users

### 2.1 Primary Users
- ZERG maintainers creating PRs via `zerg git pr`
- ZERG maintainers using `zerg git rewrite`

### 2.2 User Stories
- As a maintainer, I want PR titles sanitized at output boundary for defense-in-depth consistency
- As a maintainer, I want temp rebase scripts created with owner-only permissions from the start

---

## 3. Functional Requirements

| ID | Requirement | Priority | Notes |
|----|-------------|----------|-------|
| FR-001 | Sanitize PR title at output boundary in `PRCreator.create()` | Should | Apply `_sanitize_pr_content()` to title at line 509 |
| FR-002 | Sanitize PR title in draft save path at line 586 | Should | Apply `_sanitize_pr_content()` to title in draft content |
| FR-003 | Create temp rebase scripts with 0o700 from the start (squash) | Should | Use `os.open()` with `O_CREAT|O_EXCL` at mode 0o700, then `os.fdopen()` |
| FR-004 | Create temp rebase scripts with 0o700 from the start (reorder) | Should | Same pattern as FR-003 |

### 3.1 Detailed Changes

**FR-001 (pr_engine.py:509):**
```python
# BEFORE:
title = pr_data.get("title", "Update")

# AFTER:
title = _sanitize_pr_content(pr_data.get("title", "Update"))
```

**FR-002 (pr_engine.py:586):**
```python
# BEFORE:
content = f"# {pr_data.get('title', 'PR Draft')}\n\n{pr_data.get('body', '')}"

# AFTER:
content = f"# {_sanitize_pr_content(pr_data.get('title', 'PR Draft'))}\n\n{pr_data.get('body', '')}"
```

**FR-003 (history_engine.py:546-570) — replace NamedTemporaryFile with secure creation:**
```python
# BEFORE:
with tempfile.NamedTemporaryFile(
    mode="w", suffix=".py", delete=False, prefix="zerg_rebase_",
) as script_file:
    script_path = script_file.name
    # ... write content ...
os.chmod(script_path, 0o700)

# AFTER:
script_dir = tempfile.gettempdir()
fd, script_path = tempfile.mkstemp(suffix=".py", prefix="zerg_rebase_", dir=script_dir)
os.fchmod(fd, 0o700)
with os.fdopen(fd, "w") as script_file:
    # ... write content (unchanged) ...
# Remove os.chmod(script_path, 0o700) — already set via fchmod
```

**FR-004 (history_engine.py:633-662) — same pattern for reorder:**
```python
# BEFORE:
with tempfile.NamedTemporaryFile(
    mode="w", suffix=".py", delete=False, prefix="zerg_reorder_",
) as script_file:
    script_path = script_file.name
    # ... write content ...
os.chmod(script_path, 0o700)

# AFTER:
script_dir = tempfile.gettempdir()
fd, script_path = tempfile.mkstemp(suffix=".py", prefix="zerg_reorder_", dir=script_dir)
os.fchmod(fd, 0o700)
with os.fdopen(fd, "w") as script_file:
    # ... write content (unchanged) ...
# Remove os.chmod(script_path, 0o700) — already set via fchmod
```

### 3.2 Business Rules
- No behavioral changes — output remains identical
- Temp script content unchanged; only creation mechanism changes
- PR title sanitization mirrors existing body sanitization pattern
- `_sanitize_pr_content()` uses `html.escape()` — safe for all text content

---

## 4. Non-Functional Requirements

### 4.1 Performance
- No performance impact

### 4.2 Security
- Eliminates CWE-79 asymmetry in PR title vs body sanitization
- Eliminates CWE-377 temp file permission race window
- Defense-in-depth improvements only — no active exploit path existed

### 4.3 Reliability
- All existing tests must pass
- `ruff check` must show no new lint errors

---

## 5. Scope

### 5.1 In Scope
- pr_engine.py: Sanitize PR title at 2 output boundaries
- history_engine.py: Secure temp file creation at 2 locations
- CHANGELOG.md update

### 5.2 Out of Scope
- Refactoring `_sanitize_pr_content()` itself
- Adding new tests (existing test suite covers these paths)
- Any other security findings

### 5.3 Constraints
- Changes go on existing `fix/codeql-scanning-alerts` branch
- Must not break any existing tests

---

## 6. Dependencies

| Dependency | Type | Status |
|------------|------|--------|
| Existing test suite | Required | Available |
| `tempfile.mkstemp` | Required | Available (Python stdlib) |
| `os.fchmod` | Required | Available (Python stdlib) |

---

## 7. Acceptance Criteria

- [ ] PR title sanitized via `_sanitize_pr_content()` at `create()` line 509
- [ ] PR title sanitized in draft save content at line 586
- [ ] Temp rebase script (squash) created with 0o700 from start via `mkstemp`+`fchmod`
- [ ] Temp rebase script (reorder) created with 0o700 from start via `mkstemp`+`fchmod`
- [ ] `python -m pytest tests/ --timeout=120` — green
- [ ] `ruff check zerg/git/pr_engine.py zerg/git/history_engine.py` — clean

---

## 8. Open Questions

| ID | Question | Status |
|----|----------|--------|
| — | None | — |

---

## 9. Approval

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Product | | | PENDING |
| Engineering | | | PENDING |

---

## 10. Documentation Impact Analysis

| File | Required Update | Priority |
|------|-----------------|----------|
| CHANGELOG.md | Add entries for title sanitization and temp file hardening | Must |

---

## 11. Estimated Effort

2 files changed, ~12 lines modified. Minimal risk. ~5 minutes implementation.
