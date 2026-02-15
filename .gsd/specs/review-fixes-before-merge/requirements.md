# Feature Requirements: review-fixes-before-merge

## Metadata
- **Feature**: review-fixes-before-merge
- **Status**: APPROVED
- **Created**: 2026-02-15
- **Author**: Factory Plan Mode
- **Parent**: fix/codeql-scanning-alerts (addendum to existing branch)

---

## 1. Problem Statement

### 1.1 Background
Code review of the `fix/codeql-scanning-alerts` branch identified 3 issues: a double-sanitization bug causing display corruption, missing `shlex.quote()` on temp script paths, and unverified CodeQL alert dismissals.

### 1.2 Problem
- **Double sanitization**: `_sanitize_pr_content()` called at parse time (line 198) AND output time (line 370) in pr_engine.py. Causes `<Tag>` → `&lt;Tag&gt;` → `&amp;lt;Tag&amp;gt;` in PR bodies.
- **Unquoted script path**: `GIT_SEQUENCE_EDITOR` set via f-string without quoting at history_engine.py:573,664. Breaks if TMPDIR contains spaces.
- **Unverified dismissals**: FR-009 (cyclic imports) and FR-011 (undefined exports) used GitHub UI dismissal. Need confirmation they're resolved.

### 1.3 Impact
Without fixes: commit messages with `<`, `>`, `&` render as `&amp;lt;` in PR bodies; edge case failure with spaces in temp paths; incomplete audit trail for CodeQL dismissals.

---

## 2. Users

### 2.1 Primary Users
- ZERG maintainers creating PRs via `zerg git pr`
- ZERG maintainers using `zerg git rewrite`

### 2.2 User Stories
- As a maintainer, I want PR bodies to render commit messages correctly so angle brackets and ampersands display properly
- As a maintainer, I want rebase scripts to work regardless of temp directory path

---

## 3. Functional Requirements

| ID | Requirement | Priority | Notes |
|----|-------------|----------|-------|
| FR-001 | Remove parse-time `_sanitize_pr_content()` call at pr_engine.py:198 | Must | Keep output-boundary calls at lines 370, 381, 401, 411 |
| FR-002 | Add `shlex.quote()` to script_path in history_engine.py:573 | Should | `f"python3 {shlex.quote(script_path)}"` |
| FR-003 | Add `shlex.quote()` to script_path in history_engine.py:664 | Should | Same pattern as FR-002 |
| FR-004 | Confirm FR-009/FR-011 CodeQL alerts are resolved | Must | Verified: `gh api` shows 0 open cyclic-import/undefined-export alerts |

### 3.1 Detailed Changes

**FR-001 (pr_engine.py:198):**
```python
# BEFORE (line 198):
message=_sanitize_pr_content(message.strip()),

# AFTER:
message=message.strip(),
```
Store raw commit messages in CommitInfo. Sanitization happens at output boundary (lines 370, 381, 401, 411).

**FR-002/FR-003 (history_engine.py:573, 664):**
```python
# BEFORE:
env["GIT_SEQUENCE_EDITOR"] = f"python3 {script_path}"

# AFTER:
env["GIT_SEQUENCE_EDITOR"] = f"python3 {shlex.quote(script_path)}"
```
Requires `import shlex` at top of file (or verify existing).

**FR-004 (verification only):**
- `gh api repos/rocklambros/zerg/code-scanning/alerts` confirms 0 open alerts for `cyclic-import` and `undefined-export` rules.
- No code changes needed. Document as verified in CHANGELOG.

### 3.2 Business Rules
- No behavioral changes to PR content beyond fixing double-encoding
- `_parse_commit_type()` operates on raw message (line 193), before sanitization was applied — unaffected by this change
- All 6 call sites of `_sanitize_pr_content` reviewed: only line 198 is redundant

---

## 4. Non-Functional Requirements

### 4.1 Performance
- No performance impact

### 4.2 Security
- Sanitization at output boundary is the standard secure pattern (OWASP)
- `shlex.quote()` prevents shell injection in edge cases

### 4.3 Reliability
- All existing tests must pass
- `ruff check` must show no new lint errors

---

## 5. Scope

### 5.1 In Scope
- pr_engine.py: Remove redundant parse-time sanitization
- history_engine.py: Add shlex.quote() to 2 locations
- Verify CodeQL alert status for FR-009/FR-011
- CHANGELOG.md update

### 5.2 Out of Scope
- Refactoring _sanitize_pr_content() itself
- Adding tests for shlex.quote edge case (TMPDIR with spaces is OS-level)
- Any other CodeQL fixes

### 5.3 Constraints
- Changes go on existing `fix/codeql-scanning-alerts` branch
- Must not break any existing tests

---

## 6. Dependencies

| Dependency | Type | Status |
|------------|------|--------|
| Existing test suite | Required | Available |
| `shlex` stdlib module | Required | Available (Python stdlib) |

---

## 7. Acceptance Criteria

- [ ] PR body renders `<Tag>` correctly (no double-encoding)
- [ ] `shlex.quote()` wraps script_path at both locations
- [ ] `python -m pytest tests/ --timeout=120` — green
- [ ] `ruff check zerg/git/pr_engine.py zerg/git/history_engine.py` — clean
- [ ] CodeQL cyclic-import/undefined-export alerts confirmed at 0

---

## 8. Open Questions

| ID | Question | Status |
|----|----------|--------|
| Q-001 | Sanitize at output vs parse time? | Resolved: Output boundary |
| Q-002 | Are FR-009/FR-011 alerts dismissed? | Resolved: Confirmed 0 open via gh api |

---

## 9. Approval

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Product | klambros | 2026-02-15 | APPROVED |
| Engineering | Claude | 2026-02-15 | APPROVED |

---

## 10. Documentation Impact Analysis

| File | Required Update | Priority |
|------|-----------------|----------|
| CHANGELOG.md | Add entry for double-sanitization fix and shlex.quote | Must |

---

## 11. Estimated Effort

3 files changed, ~6 lines modified. Minimal risk. ~5 minutes implementation.
