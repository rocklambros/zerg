# Feature Requirements: changelog-enforcement

## Metadata
- **Feature**: changelog-enforcement
- **Status**: APPROVED
- **Created**: 2026-02-02
- **Author**: ZERG Plan Mode

---

## 1. Problem Statement

### 1.1 Problem
CHANGELOG.md updates are required by CI (`check-changelog` workflow) but nothing in the ZERG workflow enforces this before it's too late. The `/zerg:design` phase generates task graphs without a CHANGELOG task, and the `/zerg:git --action ship` pipeline pushes and creates PRs without verifying CHANGELOG was updated.

### 1.2 Impact
PRs fail CI, requiring an extra commit-push cycle to fix. This happened on PR #96.

---

## 2. Functional Requirements

### 2.1 Workstream A: Design Phase — Always Include CHANGELOG Task

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-A01 | `/zerg:design` must always include a CHANGELOG update task in the final quality level of the task graph | Must |
| FR-A02 | The CHANGELOG task should modify `CHANGELOG.md` under `[Unreleased]` with entries describing the feature's changes | Must |
| FR-A03 | The CHANGELOG task should be in the last level (Quality phase), depending on all prior tasks | Must |

### 2.2 Workstream B: Ship Action — Pre-Push Validation

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-B01 | `/zerg:git --action ship` must check if CHANGELOG.md has been modified (via `git diff`) before pushing | Must |
| FR-B02 | If CHANGELOG.md is not modified, warn the user and ask to continue or abort | Must |
| FR-B03 | The check should compare against the base branch (default: `main`) to detect CHANGELOG changes across all commits on the branch | Must |

---

## 3. Scope

### 3.1 In Scope
- Add CHANGELOG task instruction to `design.core.md` Phase 2 (Implementation Plan) and Phase 5 (Quality level)
- Add CHANGELOG validation step to `git.details.md` ship action pipeline

### 3.2 Out of Scope
- Modifying CI workflows
- Auto-generating CHANGELOG entries (workers write them as part of the task)
- Modifying other git actions besides `ship`

---

## 4. Acceptance Criteria

- [ ] `design.core.md` instructs inclusion of a CHANGELOG task in every task graph's quality level
- [ ] `git.details.md` ship action includes a CHANGELOG validation step before push
- [ ] Ship validation warns (not blocks) if CHANGELOG is unmodified, with option to continue

---

## 5. Documentation

After implementation, execute `/zerg:document` to update all documentation surfaces:
- Ensure all ZERG commands and flags are accounted for in documentation
- Wiki command pages must follow the `zerg-*.md` naming convention (non-command pages unaffected)
- Before executing documentation updates, plan the work via `/zerg:design` and estimate via `/zerg:estimate`
