# Technical Design: issue-94

## Metadata
- **Feature**: issue-94
- **Status**: DRAFT
- **Created**: 2026-02-02
- **Author**: ZERG Design Mode

---

## 1. Overview

### 1.1 Summary
Three changes to the ZERG plan command and documentation: (A) add AskUserQuestion post-approval prompt with next-step options, (B) add a Documentation section to the requirements.md template, (C) fix documentation gaps in `docs/commands.md` for missing git flags.

### 1.2 Goals
- Smooth handoff from plan → design phase
- Every plan output includes documentation task guidance
- All command flags documented accurately in `docs/commands.md`

### 1.3 Non-Goals
- Auto-invoking `/z:design` from within the plan command
- Changing non-command wiki pages
- Adding new commands or flags

---

## 2. Architecture

### 2.1 High-Level Design

No new components. This is purely markdown content changes across 4 files:

```
plan.md / plan.core.md  → Add Phase 5.5: Post-Approval Prompt
plan.details.md         → Add Section 10: Documentation to template
docs/commands.md        → Add missing git flags to flag table
```

### 2.2 Component Breakdown

| Component | Responsibility | Files |
|-----------|---------------|-------|
| Post-approval prompt | AskUserQuestion instruction after APPROVED | `plan.md`, `plan.core.md` |
| Documentation template section | Standing docs section in requirements template | `plan.details.md` |
| Git flag docs | Missing flags in commands.md | `docs/commands.md` |

### 2.3 Data Flow

User says "APPROVED" → TaskUpdate(completed) → AskUserQuestion(3 options) → instruction text based on choice.

---

## 3. Detailed Design

### 3.1 Post-Approval Prompt (plan.md + plan.core.md)

Insert after Phase 5 (User Approval), before Status Markers. New section:

```markdown
### Phase 5.5: Post-Approval Handoff

After the user replies "APPROVED":

1. Call TaskUpdate to mark the plan task completed (this happens first)
2. Update requirements.md with `Status: APPROVED`
3. Use AskUserQuestion to prompt the user:

Call AskUserQuestion:
  - question: "Requirements approved! How would you like to proceed?"
  - header: "Next step"
  - options:
    - label: "Clear context, then /z:design (Recommended)"
      description: "Run /compact to free token budget, then start /z:design in a fresh context"
    - label: "Run /z:design now"
      description: "Continue in the current context — may have reduced token budget"
    - label: "Stop here"
      description: "I'll run /z:design later in a new session"

Based on response:
- Option 1: Output "Run `/compact` to clear context, then run `/z:design` to begin architecture."
- Option 2: Output "Run `/z:design` now to begin architecture."
- Option 3: Output nothing further, command completes.
```

### 3.2 Documentation Template Section (plan.details.md)

Add after Section 9 (Approval) in the requirements.md template:

```markdown
## 10. Documentation

After implementation, execute `/zerg:document` to update all documentation:
- Ensure all ZERG commands and flags are accounted for in docs
- Wiki command pages must follow the `zerg-*.md` naming convention (non-command pages unaffected)
- Before executing documentation updates, plan via `/zerg:design` and estimate via `/zerg:estimate`
```

### 3.3 Missing Git Flags in docs/commands.md

Add to the `/zerg:git` flag table:

| Flag | Description |
|------|-------------|
| `--no-docker` | Skip Docker cleanup (for cleanup action) |
| `--include-stashes` | Clear git stashes during cleanup (off by default) |
| `--limit N` | Max issues to create (for issue action, default: 10) |
| `--priority P` | Filter by priority: `P0`, `P1`, `P2` (for issue action) |

---

## 4. Key Decisions

### 4.1 TaskUpdate Before AskUserQuestion
**Context**: Should TaskUpdate fire before or after the prompt?
**Decision**: Before. The plan task is done regardless of which next-step the user picks.
**Rationale**: FR-A05 and FR-A06 require this ordering.

### 4.2 Template vs Post-Approval for Documentation
**Context**: Where does the `/zerg:document` guidance live?
**Decision**: In the requirements.md template (Section 10).
**Rationale**: User chose this in planning phase. Every generated requirements.md will include it.

---

## 5. Implementation Plan

### 5.1 Phase Summary

| Phase | Tasks | Parallel | Description |
|-------|-------|----------|-------------|
| L1 | 3 | Yes | All file edits (no dependencies between them) |

All 3 tasks are independent — they modify different files with no shared dependencies.

### 5.2 File Ownership

| File | Task ID | Operation |
|------|---------|-----------|
| `zerg/data/commands/plan.md` | TASK-001 | modify |
| `zerg/data/commands/plan.core.md` | TASK-001 | modify |
| `zerg/data/commands/plan.details.md` | TASK-002 | modify |
| `docs/commands.md` | TASK-003 | modify |

Note: TASK-001 owns both plan.md and plan.core.md since they must stay in sync.

### 5.3 Dependency Graph

```
TASK-001 ──┐
TASK-002 ──┼── (all Level 1, no dependencies)
TASK-003 ──┘
```

---

## 6. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| plan.md and plan.core.md get out of sync | Low | Medium | Single task owns both files |
| Template section numbering conflicts | Low | Low | Check existing section numbers before inserting |

---

## 7. Testing Strategy

### 7.1 Verification
- TASK-001: `grep -q "AskUserQuestion" zerg/data/commands/plan.md && grep -q "AskUserQuestion" zerg/data/commands/plan.core.md`
- TASK-002: `grep -q "Documentation" zerg/data/commands/plan.details.md && grep -q "zerg:document" zerg/data/commands/plan.details.md`
- TASK-003: `grep -q "no-docker" docs/commands.md && grep -q "include-stashes" docs/commands.md && grep -q "limit N" docs/commands.md && grep -q "priority P" docs/commands.md`

### 7.2 Manual Verification
- Run `/zerg:plan test-feature` and verify the post-approval prompt appears after approval
- Check that the generated requirements.md includes Section 10 (Documentation)

---

## 8. Parallel Execution Notes

### 8.1 Safe Parallelization
- All 3 tasks are Level 1 with no dependencies
- No two tasks modify the same file

### 8.2 Recommended Workers
- Minimum: 1 worker (sequential)
- Optimal: 3 workers (one per task)
- Maximum: 3 workers (only 3 tasks)

### 8.3 Estimated Duration
- Single worker: ~15 minutes
- With 3 workers: ~5 minutes
- Speedup: 3x
