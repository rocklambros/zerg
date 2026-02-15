# Requirements: Phase 3 — Post-Release Polish

**Status**: APPROVED
**Epic**: #179 (ZERG Public Release)
**Issue**: #191
**Feature**: phase-3-post-release-polish
**Date**: 2026-02-07

## 1. Problem Statement

v0.2.0 is live on PyPI. The repo needs post-release polish: sponsorship setup, release automation, CI link checking, and pre-commit hygiene hooks. These are independent quality-of-life improvements for contributors and maintainers.

## 2. Scope

### In Scope

| # | Task | Deliverable |
|---|------|-------------|
| 1 | FUNDING.yml | `.github/FUNDING.yml` enabling Sponsor button |
| 2 | Release notes automation | `.github/release.yml` with categorized auto-notes |
| 3 | Documentation link checker | CI job using `lychee` on `docs/` and `README.md` |
| 4 | Pre-commit expansion | Add standard hooks to `.pre-commit-config.yaml` |

### Out of Scope

- Terminal demo recording (manual creative task)
- Social preview image (manual creative task)
- Docker Hub image (deferred — ZERG installs via pip)

## 3. Functional Requirements

### 3.1 FUNDING.yml

- Create `.github/FUNDING.yml` with `github: rocklambros`
- Comment out `buy_me_a_coffee` and `open_collective` as placeholders
- Verify Sponsor button appears on repo page

### 3.2 Release Notes Automation

- Create `.github/release.yml` (NOT the workflow — the release config file)
- Categories:
  - "New Features" → `enhancement` label
  - "Bug Fixes" → `bug` label
  - "Documentation" → `documentation` label
  - "Dependencies" → `dependencies` label
  - "Other Changes" → `*` (catch-all)
- Exclude `skip-changelog` and `duplicate` labels from release notes

### 3.3 Documentation Link Checker

- Add `lychee` link checker as a CI job in `.github/workflows/ci.yml`
- Scope: `docs/**/*.md`, `README.md`, `CONTRIBUTING.md`, `CHANGELOG.md`
- Exclude: localhost URLs, example.com, PyPI badge URLs (flaky)
- Run on: PRs and pushes to main
- Failure mode: warning (non-blocking) initially — can promote to required later

### 3.4 Pre-commit Expansion

- Current config: only `ruff` + `ruff-format`
- Add `pre-commit/pre-commit-hooks` repo with:
  - `trailing-whitespace`
  - `end-of-file-fixer`
  - `check-yaml`
  - `check-json`
  - `check-toml`
  - `check-added-large-files` (max 500KB)
- Preserve existing ruff hooks unchanged

## 4. Non-Functional Requirements

- All tasks are independent — no ordering dependencies
- No new Python dependencies required
- CI changes must not break existing required checks (`quality`, `smoke`, `test (1)`, `test (2)`, `audit`)
- Link checker must be tolerant of external URL flakiness (retries, timeout config)

## 5. Dependencies

- None — all tasks are self-contained
- Pre-commit hooks require contributors to run `pre-commit install` (already documented)

## 6. Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|-------------|
| 1 | `.github/FUNDING.yml` exists with correct content | `cat .github/FUNDING.yml` |
| 2 | `.github/release.yml` has 5 categories | `cat .github/release.yml` |
| 3 | Link checker job runs in CI without failing on valid links | `gh run view` after PR |
| 4 | Pre-commit config has 8 hooks (2 ruff + 6 standard) | `grep -c 'id:' .pre-commit-config.yaml` |
| 5 | Existing CI checks still pass | CI green on PR |

## 7. Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Link checker flaky on external URLs | Configure retries, timeouts, exclude list; non-blocking initially |
| Pre-commit hooks conflict with existing ruff | Add new repo block after existing ruff block; test locally |
| `.github/release.yml` conflicts with `.github/workflows/release.yml` | Different files — config vs workflow; no conflict |

## 8. Task Sizing

All 4 tasks are small (1-2 files each, <20 lines). Total: ~4 files modified/created.
Suitable for a single worker level or sequential execution.

## 9. CHANGELOG Impact

Add under `[Unreleased]`:
- **Added**: `.github/FUNDING.yml` for GitHub Sponsors
- **Added**: `.github/release.yml` for auto-categorized release notes
- **Added**: `lychee` link checker CI job for documentation
- **Changed**: Pre-commit config expanded with 6 standard hooks

## 10. Documentation Impact

- None — these are infrastructure/CI changes, not user-facing features
- README may gain a "Sponsor" badge after FUNDING.yml is live (optional follow-up)

## 11. Open Questions

None — all requirements are well-defined from issue #191.
