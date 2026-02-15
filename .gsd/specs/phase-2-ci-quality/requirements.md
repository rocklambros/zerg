# Feature Requirements: phase-2-ci-quality

## Metadata
- **Feature**: phase-2-ci-quality
- **Status**: APPROVED
- **Created**: 2026-02-07
- **Author**: Factory Plan Mode
- **Parent Epic**: #179 (ZERG Public Release)
- **Issues**: #189, #190

---

## 1. Problem Statement

### 1.1 Background
ZERG is preparing for public release. Phase 0 (blockers) and Phase 1 (community governance) are complete. The repo has basic CI (`ci.yml` with quality, smoke, test, audit jobs) but lacks security scanning, type checking in CI, Python 3.13 coverage, a documentation site, and structured GitHub Discussions.

### 1.2 Problem
- No automated security scanning (CodeQL) — vulnerabilities in PRs go undetected
- mypy runs locally but is not enforced in CI — type regressions can merge
- CI only tests Python 3.12 — no 3.13 verification despite `>=3.12` requirement
- Documentation exists as raw markdown in `docs/` — no searchable, navigable site
- GitHub Discussions enabled but has no categories or README link

### 1.3 Impact
Without Phase 2:
- Security vulnerabilities merge undetected
- Type errors regress silently
- Contributors on Python 3.13 hit untested issues
- Users can't easily browse documentation
- Community questions end up as issues instead of discussions

---

## 2. Users

### 2.1 Primary Users
- Open-source contributors submitting PRs (benefit from CI checks)
- Developers evaluating ZERG (benefit from docs site)

### 2.2 Secondary Users
- Maintainer (rocklambros) — benefits from automated security scanning and type enforcement
- Community members — benefit from structured Discussions categories

---

## 3. Functional Requirements

### 3.1 Core Capabilities

| ID | Requirement | Priority | Issue | Notes |
|----|-------------|----------|-------|-------|
| FR-001 | CodeQL security scanning workflow | Must | #189 | Python, security-and-quality suite, push + PR + weekly schedule |
| FR-002 | mypy in CI quality job | Must | #189 | Use existing pyproject.toml config, block merge on failure |
| FR-003 | Python 3.12 + 3.13 test matrix | Must | #189 | Add 3.13 to matrix, update pyproject.toml classifiers |
| FR-004 | CODEOWNERS file | Must | #189 | Default @rocklambros, specific paths for core, CI, docs |
| FR-005 | mkdocs.yml config | Must | #190 | Material theme, navigation tabs, search |
| FR-006 | docs/index.md | Must | #190 | Landing page for docs site (can adapt from README) |
| FR-007 | GitHub Pages deployment workflow | Must | #190 | .github/workflows/docs.yml, deploy on push to main |
| FR-008 | GitHub Discussions categories | Must | #190 | Q&A, Ideas, Show and Tell, General |
| FR-009 | README Discussions link | Must | #190 | Add link in README |
| FR-010 | mkdocs + mkdocs-material in optional deps | Must | #190 | `[project.optional-dependencies.docs]` |
| FR-011 | Coverage badge in README | Should | #189 | shields.io coverage badge |

### 3.2 Inputs
- Existing `ci.yml` workflow (add mypy step, expand matrix)
- Existing `pyproject.toml` mypy config (strict mode, py312)
- Existing `docs/` folder content (8 markdown files)
- GitHub API for Discussions categories

### 3.3 Outputs
- 3 new files: `codeql.yml`, `docs.yml`, `CODEOWNERS`
- 2 new files: `mkdocs.yml`, `docs/index.md`
- 2 modified files: `ci.yml` (mypy + matrix), `pyproject.toml` (classifiers + docs deps)
- 1 modified file: `README.md` (Discussions link, coverage badge)
- 1 modified file: `CHANGELOG.md` (Phase 2 entries)
- GitHub API: Discussions categories

### 3.4 Business Rules
- CodeQL must scan on push to main, PRs, and weekly cron
- mypy failure must block merge (required check)
- Python 3.13 tests use same test suite — no special handling
- Docs site uses Material for MkDocs theme
- Docs site deploys automatically on push to main
- CODEOWNERS uses @rocklambros as default owner

---

## 4. Non-Functional Requirements

### 4.1 Performance
- CodeQL scan should complete within 10 minutes
- Docs build should complete within 2 minutes
- Adding mypy to quality job should add <60s to CI

### 4.2 Security
- CodeQL provides automated vulnerability detection (SAST)
- CODEOWNERS ensures review for sensitive paths

### 4.3 Reliability
- Docs deployment should not block CI (separate workflow)
- CodeQL failure should not block merge (advisory only initially)

---

## 5. Scope

### 5.1 In Scope
- CodeQL workflow (.github/workflows/codeql.yml)
- mypy added to CI quality job
- Python 3.12 + 3.13 test matrix
- CODEOWNERS file
- mkdocs configuration and docs site
- GitHub Pages deployment workflow
- GitHub Discussions categories
- README updates (Discussions link, coverage badge)

### 5.2 Out of Scope
- Coverage floor change (keeping at 50 per user decision)
- Terminal demo / social preview (Phase 3, #191)
- Making repo public (separate decision)
- FUNDING.yml (Phase 3)
- Link checker workflow (Phase 3)
- Secret scanning (requires public repo or Advanced Security)

### 5.3 Assumptions
- Repo stays private during Phase 2 (docs site won't be publicly visible until repo is public)
- GitHub Discussions is already enabled (confirmed — linked in issue template)
- All current dependencies support Python 3.13
- `mkdocs build --strict` should pass with existing docs content

### 5.4 Constraints
- Must not break existing 5 required CI checks (quality, smoke, test (1), test (2), audit)
- mypy must use existing pyproject.toml config (strict mode)
- Docs site must build from existing `docs/` content without major rewrites

---

## 6. Dependencies

### 6.1 Internal Dependencies
| Dependency | Type | Status |
|------------|------|--------|
| Phase 0 (blockers) | Required | Complete |
| Phase 1 (community governance) | Required | Complete |
| Existing ci.yml | Modify | Exists |
| Existing pyproject.toml | Modify | Exists |
| Existing docs/ folder | Reference | 8 files present |

### 6.2 External Dependencies
| Dependency | Type | Owner |
|------------|------|-------|
| GitHub CodeQL | Security scanning | GitHub |
| GitHub Pages | Docs hosting | GitHub |
| mkdocs-material | Docs theme | squidfunk |
| shields.io | Coverage badge | External |

---

## 7. Acceptance Criteria

### 7.1 Definition of Done
- [ ] CodeQL workflow runs on PRs and weekly
- [ ] mypy passes in CI quality job
- [ ] Tests pass on Python 3.12 and 3.13
- [ ] CODEOWNERS assigns @rocklambros as default reviewer
- [ ] `mkdocs build --strict` passes
- [ ] Docs workflow deploys on push to main
- [ ] Discussions has 4 categories (Q&A, Ideas, Show and Tell, General)
- [ ] README links to Discussions
- [ ] CI passes on PR
- [ ] CHANGELOG.md updated

### 7.2 Test Scenarios

| ID | Scenario | Given | When | Then |
|----|----------|-------|------|------|
| TC-001 | CodeQL scan | codeql.yml exists | PR opened | CodeQL runs Python security scan |
| TC-002 | mypy in CI | mypy step in quality | PR with type error | quality job fails |
| TC-003 | Python 3.13 | Matrix includes 3.13 | Tests run | All tests pass on 3.13 |
| TC-004 | Docs build | mkdocs.yml exists | `mkdocs build --strict` | Build succeeds |
| TC-005 | CODEOWNERS | File exists | PR touches zerg/*.py | @rocklambros auto-requested |

---

## 8. Open Questions

| ID | Question | Owner | Status |
|----|----------|-------|--------|
| Q-001 | Should CodeQL failure block merge or be advisory? | maintainer | Resolved: Advisory (don't add to required checks initially) |
| Q-002 | Should we add a `docs` required check? | maintainer | Open |

---

## 9. Approval

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Product | rocklambros | | PENDING |

---

## 10. Documentation

After implementation:
- CHANGELOG.md updated with Phase 2 entries (ALWAYS required)
- README.md updated with Discussions link + coverage badge
- pyproject.toml updated with 3.13 classifier + docs deps

---

## 11. Documentation Impact Analysis

### 11.1 Files Requiring Documentation Updates
| File | Current State | Required Update | Priority |
|------|--------------|-----------------|----------|
| `CHANGELOG.md` | Has [Unreleased] | Add Phase 2 entries | Must |
| `README.md` | Has 4 badges | Add coverage badge, Discussions link | Must |
| `pyproject.toml` | 3.12 classifier only | Add 3.13 classifier, docs optional deps | Must |
| `CONTRIBUTING.md` | Complete | No changes needed | — |

### 11.2 Documentation Tasks for Design Phase
- [x] CHANGELOG.md update task (ALWAYS required)
- [x] README.md update (badge + link)
- [x] pyproject.toml updates (classifiers + deps)
