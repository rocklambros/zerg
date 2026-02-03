# Technical Design: changelog-enforcement

## Metadata
- **Feature**: changelog-enforcement
- **Status**: APPROVED
- **Created**: 2026-02-02
- **Author**: ZERG Design Mode

---

## 1. Overview

### 1.1 Summary
Two markdown edits: (A) add CHANGELOG task requirement to design.core.md's Phase 2 quality level and completion criteria, (B) add CHANGELOG validation step to git.details.md's ship action pipeline.

### 1.2 Goals
- Every task graph includes a CHANGELOG update task
- Ship action warns before pushing without CHANGELOG changes

### 1.3 Non-Goals
- Auto-generating CHANGELOG content
- Modifying CI workflows
- Hard-blocking ship on missing CHANGELOG

---

## 2. Detailed Design

### 2.1 TASK-001: Design phase CHANGELOG requirement (design.core.md)

**Change 1**: In Phase 2's Phase Structure template (line 120-124), add "CHANGELOG.md update" to the Quality (Level 5) bullet list:

```markdown
### Phase 5: Quality (Level 5)
Final polish.
- Documentation
- CHANGELOG.md update (required — add entries under [Unreleased])
- Type coverage
- Lint fixes
```

**Change 2**: In the Completion Criteria section (line 582-591), add:

```markdown
- Task graph includes a CHANGELOG.md update task in the final quality level
```

### 2.2 TASK-002: Ship action CHANGELOG validation (git.details.md)

Insert a validation step between existing steps 1 (Commit) and 2 (Push) in the ship pipeline. The new pipeline becomes:

```
1. Commit
1.5. CHANGELOG check  <-- NEW
2. Push
3. Create PR
4. Merge
5. Cleanup
```

The new step checks `git diff {base}...HEAD -- CHANGELOG.md` for changes. If none found, use AskUserQuestion to warn the user with options to continue or abort.

---

## 3. Implementation Plan

| Phase | Tasks | Parallel |
|-------|-------|----------|
| L1 | 2 | Yes |

All tasks are independent — different files.

### File Ownership

| File | Task ID | Operation |
|------|---------|-----------|
| `zerg/data/commands/design.core.md` | TASK-001 | modify |
| `zerg/data/commands/git.details.md` | TASK-002 | modify |
