# Feature Requirements: fix-codeql-scanning-alerts

## Metadata
- **Feature**: fix-codeql-scanning-alerts
- **Status**: APPROVED
- **Created**: 2026-02-15
- **Author**: Factory Plan Mode

---

## 1. Problem Statement

### 1.1 Background
GitHub CodeQL scanning on `rocklambros/zerg` reports 115 open alerts. CodeQL runs on every push/PR and these alerts create noise, mask real issues, and block adoption of branch protection rules requiring zero alerts.

Additionally, the `/z:plan` command has a recurring bug where it fails to generate its primary output (`requirements.md`) due to an overbroad WORKFLOW BOUNDARY guard that prohibits the Write tool entirely — including for spec files which are the command's intended output.

### 1.2 Problem
- **3 HIGH-severity security alerts**: Bad HTML filter regex (XSS risk), overly permissive `chmod 0o755` on temp scripts
- **112 code quality alerts**: Empty except blocks, unused code, cyclic imports, import pattern issues, ineffectual statements, etc.
- **~17 false positives**: CodeQL doesn't understand lazy `__getattr__` exports, `TYPE_CHECKING` cyclic import guards, or intentional test fixtures
- **`/z:plan` bug**: WORKFLOW BOUNDARY says "MUST NEVER run implementation tools (Write, Edit, Bash)" which prevents creating requirements.md — the command's primary deliverable

### 1.3 Impact
Without this fix:
- Security vulnerabilities remain in PR body sanitization and temp script permissions
- Cannot enable "zero CodeQL alerts" branch protection
- Signal-to-noise ratio on code scanning dashboard is unusable
- `/z:plan` continues failing to produce spec documents, requiring manual workarounds every time

---

## 2. Users

### 2.1 Primary Users
- ZERG maintainers reviewing code scanning alerts
- CI/CD pipeline enforcing quality gates

### 2.2 Secondary Users
- Contributors opening PRs (see CodeQL results on their PRs)
- Users of `/z:plan` command

### 2.3 User Stories
- As a maintainer, I want zero open CodeQL alerts so that new alerts are immediately visible
- As a contributor, I want CodeQL checks to pass so my PRs aren't blocked by pre-existing issues
- As a user, I want `/z:plan` to produce a requirements.md file so I can review and approve specs

---

## 3. Functional Requirements

### 3.1 Core Capabilities

| ID | Requirement | Priority | Notes |
|----|-------------|----------|-------|
| FR-001 | Fix bad HTML filter regex in pr_engine.py | Must | Replace regex stripping with `html.escape()` |
| FR-002 | Fix overly permissive chmod in history_engine.py | Must | `0o755` → `0o700` (2 locations) |
| FR-003 | Add explanatory comments to 33 empty except blocks | Must | `pass` → `pass  # <reason>` |
| FR-004 | Remove 8 dead global variables | Must | Unused constants/patterns |
| FR-005 | Remove 4 unused logger definitions | Must | Dead `getLogger()` calls |
| FR-006 | Remove 7 unused imports | Must | Across test fixtures and source |
| FR-007 | Fix 5 unused local variables | Must | Remove or prefix `_` |
| FR-008 | Consolidate import-and-import-from (9 alerts) | Should | Fix in source; suppress in tests where pattern is intentional |
| FR-009 | Suppress 12 cyclic import false positives | Must | Already mitigated via TYPE_CHECKING guards |
| FR-010 | Fix 3 multiple-definition alerts | Must | Remove redundant assignments |
| FR-011 | Suppress 3 undefined-export false positives | Must | Lazy `__getattr__` pattern |
| FR-012 | Fix 2 redundant comparison alerts | Should | Remove tautological conditions |
| FR-013 | Fix remaining 7 misc alerts | Should | Lambda, assignment, conditional, BaseException, etc. |
| FR-014 | Fix 7 alerts in .zerg/ runtime files | Must | These are runtime, not generated |
| FR-015 | Fix `/z:plan` WORKFLOW BOUNDARY bug | Must | Allow Write for .gsd/ files; add sentinel |
| FR-016 | Add programmatic stop sentinel to `/z:plan` | Must | `.plan-complete` sentinel file |

### 3.2 Inputs
- 115 CodeQL alert locations (file:line from GitHub code scanning)
- `/z:plan` command files (plan.md, plan.core.md)

### 3.3 Outputs
- Zero open CodeQL alerts on main branch
- Fixed plan.md and plan.core.md with correct tool allowlists
- `.plan-complete` sentinel mechanism for handoff enforcement

### 3.4 Business Rules
- Security fixes (FR-001, FR-002) are non-negotiable code changes
- False positives (FR-009, FR-011) use inline `# codeql[rule-id]` suppression comments
- Empty except fixes (FR-003) add explanatory comments — no logic changes
- No behavioral changes to existing code — only safety/quality improvements
- All existing tests must continue to pass

---

## 4. Non-Functional Requirements

### 4.1 Performance
- No performance impact — changes are comments, dead code removal, and minor security fixes

### 4.2 Security
- PR body sanitization must use `html.escape()` instead of regex stripping (OWASP A05)
- Temp scripts must use `0o700` permissions (owner-only, CWE-732)

### 4.3 Reliability
- Zero test regressions — full test suite must pass
- `python -m zerg.validate_commands` must pass (drift check)
- `ruff check` must show no new lint errors

---

## 5. Scope

### 5.1 In Scope
- All 115 CodeQL alerts (fix or suppress with justification)
- `/z:plan` WORKFLOW BOUNDARY bug fix
- `/z:plan` sentinel file mechanism
- CHANGELOG.md update

### 5.2 Out of Scope
- Refactoring code beyond what's needed to resolve alerts (deferred)
- Adding new CodeQL query configurations (deferred)
- `.github/codeql-config.yml` to exclude test fixtures (accept inline suppression for now)
- Fixing the broader exception handling debt from issue #137 (separate feature)

### 5.3 Assumptions
- CodeQL's `EmptyExcept.ql` resolves when a comment is added to the `pass` line
- `# codeql[rule-id]` inline suppression syntax works for false positives
- Lazy `__getattr__` and `TYPE_CHECKING` patterns are architecturally correct and should be suppressed, not refactored

### 5.4 Constraints
- Must not change public API surfaces
- Must not modify test behavior (only test infrastructure/fixtures)
- Single PR to main branch

---

## 6. Dependencies

### 6.1 Internal Dependencies
| Dependency | Type | Status |
|------------|------|--------|
| Existing test suite | Required | Available |
| validate_commands.py | Required | Available |
| ruff linter config | Required | Available |

### 6.2 External Dependencies
| Dependency | Type | Owner |
|------------|------|-------|
| GitHub CodeQL scanning | Verification | GitHub |

---

## 7. Acceptance Criteria

### 7.1 Definition of Done
- [ ] All 115 CodeQL alerts resolved (98 fixes + 17 suppressions)
- [ ] `python -m pytest tests/ --timeout=120` — full suite green
- [ ] `python -m zerg.validate_commands` — drift check clean
- [ ] `ruff check zerg/ tests/` — no new lint errors
- [ ] CHANGELOG.md updated under `[Unreleased]` > `Fixed`
- [ ] `/z:plan` produces requirements.md when invoked
- [ ] `/z:plan` stops and prompts user at Phase 5.5 (never auto-proceeds)

### 7.2 Test Scenarios

| ID | Scenario | Given | When | Then |
|----|----------|-------|------|------|
| TC-001 | Security: HTML sanitization | PR body with `<script>` tag | `_sanitize_pr_body()` called | Tags are HTML-escaped, not stripped |
| TC-002 | Security: chmod permissions | Temp script created | `os.chmod()` called | Permission is `0o700` |
| TC-003 | Empty except resolution | Any file with `pass` in except | CodeQL scans | No EmptyExcept alert |
| TC-004 | False positive suppression | `__getattr__` lazy export | CodeQL scans | No undefined-export alert |
| TC-005 | Plan command spec output | User runs `/z:plan foo` | Phases 1-5 complete | `.gsd/specs/foo/requirements.md` exists |
| TC-006 | Plan command stops | User approves requirements | Phase 5.5 executes | AskUserQuestion called; no auto-design |

### 7.3 Success Metrics
- CodeQL open alerts: 115 → 0
- Test suite: 100% green (no regressions)
- `/z:plan` reliability: produces spec file every invocation

---

## 8. Open Questions

| ID | Question | Owner | Due | Status |
|----|----------|-------|-----|--------|
| Q-001 | Alert #29 (debug.py): Is it redundant `confidence = 0.0` before conditional? | Engineer | During impl | Open |
| Q-002 | repo_map.py cache vars (#22-25): Suppress vs refactor into cache class? | Engineer | During impl | Resolved: Suppress (lower risk) |
| Q-003 | Should we add `.github/codeql-config.yml` to exclude test fixtures? | Maintainer | Post-impl | Resolved: Inline suppress for now |

---

## 9. Approval

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Product | klambros | 2026-02-15 | APPROVED |
| Engineering | Claude | 2026-02-15 | APPROVED |

---

## 10. Documentation

After implementation, ensure:
- CHANGELOG.md updated with all fix categories
- No new documentation surfaces needed (this is internal quality work)

---

## 11. Documentation Impact Analysis

### 11.1 Files Requiring Documentation Updates
| File | Current State | Required Update | Priority |
|------|--------------|-----------------|----------|
| `CHANGELOG.md` | Missing entries | Add Fixed section for security + quality | Must |
| `README.md` | N/A | No changes needed | Skip |
| `CLAUDE.md` | N/A | No changes needed | Skip |

### 11.2 Documentation Tasks for Design Phase
- [ ] CHANGELOG.md update task (ALWAYS required)
