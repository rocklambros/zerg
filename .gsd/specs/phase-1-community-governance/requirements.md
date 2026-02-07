# Feature Requirements: phase-1-community-governance

## Metadata
- **Feature**: phase-1-community-governance
- **Status**: APPROVED
- **Created**: 2026-02-07T16:20:00
- **Author**: Factory Plan Mode
- **Parent Epic**: #179 (ZERG Public Release)
- **Issues**: #185, #186, #187, #188

---

## 1. Problem Statement

### 1.1 Background
ZERG is preparing for public release as `zerg-ai` on PyPI. Phase 0 (blockers) is complete — distribution renamed, CHANGELOG frozen, TestPyPI validated, GitHub environments and branch protection configured. The repo is currently private.

### 1.2 Problem
The repo lacks standard open-source community infrastructure: issue templates, PR template, Code of Conduct, Dependabot config, README badges, and GitHub topics. Without these, contributors see an incomplete project and have no structured way to report bugs or submit PRs.

### 1.3 Impact
Without Phase 1:
- Bug reports lack reproducibility info (no template)
- PRs have inconsistent descriptions (no template)
- No Code of Conduct signals unclear community standards
- No badges means no at-a-glance project health
- No topics means poor GitHub discoverability
- No Dependabot means dependency vulnerabilities go unnoticed

---

## 2. Users

### 2.1 Primary Users
- Open-source contributors who want to file issues or submit PRs
- Developers evaluating ZERG from the GitHub repo page

### 2.2 Secondary Users
- Maintainer (rocklambros) — benefits from structured issue reports and consistent PRs

### 2.3 User Stories
- As a contributor, I want issue templates so that I provide the right information in bug reports
- As a contributor, I want a PR template so that I know what to include in my pull requests
- As a visitor, I want README badges so that I can assess project health at a glance
- As a maintainer, I want Dependabot so that I'm alerted to vulnerable dependencies

---

## 3. Functional Requirements

### 3.1 Core Capabilities

| ID | Requirement | Priority | Issue | Notes |
|----|-------------|----------|-------|-------|
| FR-001 | Bug report issue template (YAML form) | Must | #185 | Fields: description, repro steps, expected/actual, environment, logs |
| FR-002 | Feature request issue template (YAML form) | Must | #185 | Fields: problem statement, proposed solution, alternatives, context |
| FR-003 | Issue template config.yml | Must | #185 | Disable blank issues, link to Discussions for questions, link to SECURITY.md |
| FR-004 | Pull request template | Must | #186 | Sections: Summary, Changes, Test Plan, Checklist |
| FR-005 | CODE_OF_CONDUCT.md | Must | #186 | Contributor Covenant v2.1 |
| FR-006 | Dependabot config | Must | #187 | pip ecosystem, weekly schedule |
| FR-007 | Enable secret scanning | Must | #187 | Via GitHub API |
| FR-008 | Enable push protection | Should | #187 | Via GitHub API |
| FR-009 | README badges | Must | #188 | PyPI version, Python version, License, CI status |
| FR-010 | GitHub topics | Must | #188 | claude-code, parallel-execution, ai-coding, etc. |
| FR-011 | License compatibility audit | Should | #188 | Verify all deps are MIT/BSD/Apache compatible |
| FR-012 | Update SECURITY.md supported versions | Must | — | Add 0.2.x, reflect current state |

### 3.2 Inputs
- Issue template YAML specs
- Contributor Covenant v2.1 text
- Dependabot config YAML
- Badge markdown from shields.io

### 3.3 Outputs
- 6 new files: 3 issue templates, 1 PR template, 1 CoC, 1 Dependabot config
- 2 modified files: README.md (badges), SECURITY.md (versions)
- GitHub API changes: topics, secret scanning, push protection

### 3.4 Business Rules
- Issue templates use YAML format (renders as forms in GitHub UI)
- Bug report requires: description, repro steps, ZERG version
- Feature request requires: problem statement, proposed solution
- PR template checklist references existing CI requirements
- CoC enforcement contact: use GitHub Security Advisories (no personal email)

---

## 4. Non-Functional Requirements

### 4.1 Performance
N/A — configuration files only, no runtime impact

### 4.2 Security
- Secret scanning enabled to catch leaked API keys
- Push protection enabled to block commits containing secrets
- Dependabot alerts for dependency vulnerabilities

### 4.3 Reliability
N/A — static files

### 4.4 Scalability
N/A — static files

---

## 5. Scope

### 5.1 In Scope
- GitHub issue templates (bug, feature, config)
- PR template
- CODE_OF_CONDUCT.md (Contributor Covenant v2.1)
- Dependabot configuration
- Secret scanning + push protection enablement
- README badges (PyPI, Python, License, CI)
- GitHub repository topics
- License compatibility audit
- SECURITY.md version table update

### 5.2 Out of Scope
- CodeQL workflow (deferred to Phase 2, #189)
- mypy in CI (deferred to Phase 2, #189)
- mkdocs documentation site (deferred to Phase 2, #190)
- GitHub Discussions setup (already enabled)
- Terminal demo / social preview (deferred to Phase 3, #191)
- Making repo public (separate decision, not part of this spec)

### 5.3 Assumptions
- Repo stays private during Phase 1 (go-public is a separate step)
- Badges will show "not found" until repo is public — that's fine
- Dependabot alerts are already enabled (confirmed via API)
- Branch protection is already configured from Phase 0

### 5.4 Constraints
- Must use Contributor Covenant v2.1 (standard, widely recognized)
- Issue templates must use YAML format (not markdown) for form rendering
- All changes must pass existing CI (quality, smoke, test, audit)

---

## 6. Dependencies

### 6.1 Internal Dependencies
| Dependency | Type | Status |
|------------|------|--------|
| Phase 0 (blockers) | Required | Complete |
| Branch protection | Required | Complete (5 checks configured) |
| CONTRIBUTING.md | Reference | Exists |
| SECURITY.md | Reference | Exists (needs version update) |

### 6.2 External Dependencies
| Dependency | Type | Owner |
|------------|------|-------|
| shields.io | Badge rendering | External service |
| GitHub API | Repo settings | GitHub |
| Contributor Covenant | CoC text | contributorcovenant.org |

---

## 7. Acceptance Criteria

### 7.1 Definition of Done
- [ ] All 6 new files created and committed
- [ ] README badges render (or show expected "not found" while private)
- [ ] GitHub topics set (9 topics)
- [ ] Secret scanning + push protection enabled
- [ ] Dependabot config triggers automated PRs
- [ ] License audit passes (all deps MIT/BSD/Apache compatible)
- [ ] SECURITY.md shows 0.2.x as supported
- [ ] CI passes on PR
- [ ] CHANGELOG.md updated

### 7.2 Test Scenarios

| ID | Scenario | Given | When | Then |
|----|----------|-------|------|------|
| TC-001 | Bug report template | Repo has templates | User clicks "New Issue" | Bug report form renders with required fields |
| TC-002 | Feature request template | Repo has templates | User clicks "New Issue" | Feature request form renders |
| TC-003 | Blank issue blocked | config.yml disables blank | User tries blank issue | Redirected to templates or Discussions |
| TC-004 | PR template | Template exists | User opens new PR | Description pre-filled with template |
| TC-005 | Dependabot | Config exists | Dependency has CVE | Dependabot opens alert/PR |
| TC-006 | Badges | Badges in README | User views README | Badges visible with correct links |

### 7.3 Success Metrics
- All 4 issues (#185-#188) closeable
- Zero new files outside `.github/` and project root
- No runtime code changes

---

## 8. Open Questions

| ID | Question | Owner | Status |
|----|----------|-------|--------|
| Q-001 | Should we enable "require linear history" (squash-only merges)? | maintainer | Resolved: No — allow merge commits |
| Q-002 | What email/contact for CoC enforcement? Use GH Security Advisories link? | maintainer | Resolved: Yes — use GitHub Security Advisories |

---

## 9. Approval

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Product | rocklambros | | PENDING |

---

## 10. Documentation

After implementation:
- CHANGELOG.md updated with Phase 1 entries (ALWAYS required)
- README.md updated with badges
- SECURITY.md version table updated
- CONTRIBUTING.md may need minor link updates (to PR template, CoC)

---

## 11. Documentation Impact Analysis

### 11.1 Files Requiring Documentation Updates
| File | Current State | Required Update | Priority |
|------|--------------|-----------------|----------|
| `CHANGELOG.md` | Has [Unreleased] | Add Phase 1 entries | Must |
| `README.md` | No badges | Add badge row at top | Must |
| `SECURITY.md` | Shows 0.1.x only | Add 0.2.x to supported versions | Must |
| `CONTRIBUTING.md` | Exists, complete | Link to CoC if not already linked | Should |

### 11.2 Documentation Tasks for Design Phase
- [x] CHANGELOG.md update task (ALWAYS required)
- [x] README.md update (badges)
- [x] SECURITY.md update (version table)
- [ ] CONTRIBUTING.md update (CoC link — check if needed)
