# Requirements: Enforce Workflow Boundaries

## Metadata
- **Feature**: enforce-workflow-boundaries
- **Status**: APPROVED
- **Created**: 2026-02-05
- **Author**: /zerg:plan

---

## 1. Problem Statement

Currently, `/z:plan` and `/z:brainstorm` commands can potentially auto-progress to the next workflow step (design or plan respectively). The user explicitly requires that:

1. **`/z:plan` MUST NEVER proceed directly to implementation or design** - it must always stop and prompt the user
2. **`/z:brainstorm` MUST NEVER proceed directly to `/z:plan`** - it must always stop and prompt the user

This is a workflow discipline requirement to ensure the user maintains full control over workflow progression.

---

## 2. Current State Analysis

### `/z:plan` (plan.md, plan.core.md)
- Phase 5.5 uses AskUserQuestion with 3 options after approval
- Options include "Run /z:design now" - this is OUTPUT TEXT only, not auto-execution
- **Gap**: No explicit HARD STOP language; Claude might interpret instructions loosely

### `/z:brainstorm` (brainstorm.md, brainstorm.core.md)
- Phase 4 (Handoff) only SUGGESTS next step: `/zerg:plan {top-feature}`
- No AskUserQuestion mechanism for user to choose next step
- **Gap**: Missing explicit handoff prompt; missing HARD STOP language

---

## 3. Functional Requirements

### FR-1: Add Workflow Boundary Enforcement to `/z:plan`

Add explicit HARD STOP rule at the top of the command file:

```markdown
## ⛔ WORKFLOW BOUNDARY (NON-NEGOTIABLE)

This command MUST NEVER:
- Automatically run `/z:design` or any design phase
- Automatically proceed to implementation
- Call the Skill tool to invoke another command
- Write code or make code changes

After Phase 5.5 completes, the command STOPS. The user must manually run `/z:design`.
```

### FR-2: Add Workflow Boundary Enforcement to `/z:brainstorm`

Add explicit HARD STOP rule at the top of the command file:

```markdown
## ⛔ WORKFLOW BOUNDARY (NON-NEGOTIABLE)

This command MUST NEVER:
- Automatically run `/z:plan` or any planning phase
- Automatically proceed to design or implementation
- Call the Skill tool to invoke another command
- Write code or make code changes

After Phase 4 completes, the command STOPS. The user must manually run `/z:plan`.
```

### FR-3: Add AskUserQuestion Handoff to `/z:brainstorm`

Update Phase 4 (Handoff) to use AskUserQuestion like `/z:plan` does:

```markdown
### Phase 4: Handoff

Present ranked recommendations:
1. Show prioritized feature list with effort estimates
2. Save session summary to `.gsd/specs/{session-id}/brainstorm.md`

**Then use AskUserQuestion to prompt the user for next steps:**

Call AskUserQuestion:
  - question: "Brainstorm complete! How would you like to proceed?"
  - header: "Next step"
  - options:
    - label: "Clear context, then /z:plan (Recommended)"
      description: "Run /compact to free token budget, then start /z:plan {top-feature} in fresh context"
    - label: "Stop here"
      description: "I'll run /z:plan later in a new session"

Based on user response:
- **"Clear context, then /z:plan"**: Output: "Run `/compact` to clear context, then run `/z:plan {top-feature}` to begin requirements."
- **"Stop here"**: Command completes normally with no further output.

**⛔ DO NOT auto-run /z:plan. The user must manually invoke it.**
```

### FR-4: Strengthen `/z:plan` Phase 5.5 Language

Update Phase 5.5 to emphasize the HARD STOP:

```markdown
### Phase 5.5: Post-Approval Handoff

After the user replies "APPROVED":

1. First, call TaskUpdate to mark the plan task `completed`
2. Update requirements.md with `Status: APPROVED`
3. Then use AskUserQuestion to prompt the user for next steps:

Call AskUserQuestion:
  - question: "Requirements approved! How would you like to proceed?"
  - header: "Next step"
  - options:
    - label: "Clear context, then /z:design (Recommended)"
      description: "Run /compact to free token budget, then start /z:design in a fresh context"
    - label: "Stop here"
      description: "I'll run /z:design later in a new session"

Based on user response:
- **"Clear context, then /z:design"**: Output: "Run `/compact` to clear context, then run `/z:design` to begin architecture."
- **"Stop here"**: Command completes normally with no further output.

**⛔ DO NOT auto-run /z:design. DO NOT write code. The user must manually invoke the next command.**
```

**NOTE**: Remove the "Run /z:design now" option - it could be misinterpreted as permission to auto-run.

---

## 4. Files to Modify

| File | Change |
|------|--------|
| `zerg/data/commands/plan.md` | Add workflow boundary section, strengthen Phase 5.5 |
| `zerg/data/commands/plan.core.md` | Same changes (keep in sync) |
| `zerg/data/commands/brainstorm.md` | Add workflow boundary section, add AskUserQuestion to Phase 4 |
| `zerg/data/commands/brainstorm.core.md` | Same changes (keep in sync) |

---

## 5. Acceptance Criteria

- [ ] `/z:plan` has explicit WORKFLOW BOUNDARY section at top
- [ ] `/z:plan` Phase 5.5 has only 2 options (removes "Run now" option)
- [ ] `/z:plan` has ⛔ warning after Phase 5.5
- [ ] `/z:brainstorm` has explicit WORKFLOW BOUNDARY section at top
- [ ] `/z:brainstorm` Phase 4 uses AskUserQuestion with 2 options
- [ ] `/z:brainstorm` has ⛔ warning after Phase 4
- [ ] Neither command can auto-invoke another command
- [ ] User must manually run the next workflow step

---

## 6. Non-Functional Requirements

- No code changes required (command files only)
- No test changes required (behavioral documentation)
- Changes should be applied to both `.md` and `.core.md` versions

---

## 7. Out of Scope

- Programmatic enforcement (Python code) - this is prompt-level enforcement
- Changes to `/z:design` or `/z:rush` commands
- CI/CD validation of workflow boundaries
