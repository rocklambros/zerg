# Feature Requirements: plan-mode-conflict-fix

## Metadata
- **Feature**: plan-mode-conflict-fix
- **Status**: APPROVED
- **Created**: 2026-02-12
- **Author**: ZERG Plan Mode

---

## 1. Problem Statement

### 1.1 Background
ZERG's `/z:plan` command instructs Claude to "Press Shift+Tab twice" to enter Claude Code plan mode. Claude Code plan mode restricts tools to read-only (no Write, Edit, Bash). The command then requires Write (requirements.md) and Bash (mkdir) — which are blocked.

### 1.2 Problem
Two failure modes:
1. **Deadlock**: Claude enters plan mode but cannot write requirements.md or run Pre-Flight bash commands — the plan never gets created.
2. **Skip-to-implement**: When the user manually exits plan mode, the system message "You can now make edits, run tools, and take actions" causes Claude to jump to implementing the feature instead of writing the planning documents.

### 1.3 Impact
- Plan files (requirements.md) never written
- Feature spec directories never created
- Workflow skips from planning directly to implementation
- /z:design handoff never happens properly

---

## 2. Users

### 2.1 Primary Users
ZERG users running `/z:plan` and `/z:brainstorm` in Claude Code

### 2.2 User Stories
- As a user, I want `/z:plan` to automatically enter plan mode for analysis, then exit to write spec files, so that I get deep reasoning AND proper file outputs
- As a user, I want `/z:brainstorm` to follow the same pattern so that discovery is done in plan mode and outputs are written after exit

---

## 3. Functional Requirements

### 3.1 Core Capabilities

| ID | Requirement | Priority | Notes |
|----|-------------|----------|-------|
| FR-001 | `/z:plan` Pre-Flight runs BEFORE entering plan mode | Must | Pre-Flight needs Bash (mkdir, echo) |
| FR-002 | `/z:plan` calls EnterPlanMode automatically after Pre-Flight | Must | Replaces manual "Shift+Tab" instruction |
| FR-003 | `/z:plan` Phases 1-2 execute inside plan mode (read-only) | Must | Context Gathering + Requirements Elicitation |
| FR-004 | `/z:plan` calls ExitPlanMode after Phase 2, before Phase 3 | Must | Transitions to write mode for requirements.md |
| FR-005 | Post-exit guard prevents jumping to implementation | Must | Strong guardrail text after ExitPlanMode section |
| FR-006 | `/z:plan` Phases 3-5.5 execute in normal mode | Must | Write requirements.md, approval, handoff |
| FR-007 | `/z:brainstorm` enters plan mode after Pre-Flight | Should | Same pattern: plan mode for discovery phases |
| FR-008 | `/z:brainstorm` exits plan mode before Phase 3 (writes) | Should | Exit before saving files and creating issues |
| FR-009 | Post-exit guard in brainstorm prevents auto-running /z:plan | Should | Same guardrail pattern |

---

## 4. Scope

### 4.1 In Scope
- Modify `plan.md` — reorder and add plan mode transition sections
- Modify `plan.core.md` — same changes (core split)
- Modify `brainstorm.md` — add plan mode enter/exit sections
- Modify `brainstorm.core.md` — same changes (core split)

### 4.2 Out of Scope
- Changes to Claude Code's plan mode behavior (platform-level)
- Changes to other ZERG commands (design, rush, etc.)
- Changes to plan.details.md or brainstorm.details.md (reference material only)

### 4.3 Files to Modify
1. `zerg/data/commands/plan.md`
2. `zerg/data/commands/plan.core.md`
3. `zerg/data/commands/brainstorm.md`
4. `zerg/data/commands/brainstorm.core.md`

---

## 5. Implementation Spec

### 5.1 plan.md / plan.core.md Changes

**A. Rewrite "Enter Plan Mode" section** (currently lines 52-58 in plan.md, 100-106 in plan.core.md):

Replace manual Shift+Tab instruction with:
```markdown
## Enter Plan Mode

Call the **EnterPlanMode** tool to enter Claude Code plan mode.

Plan mode provides read-only tools (Glob, Grep, Read, WebSearch, AskUserQuestion) for deep
codebase exploration. You will stay in plan mode for Phases 1-2, then exit before Phase 3
when you need to write files.

⚠️ Do NOT attempt to write files or run Bash while in plan mode — those tools are restricted.
```

**B. Add new "Exit Plan Mode" section** between Phase 2 and Phase 3:

```markdown
## Exit Plan Mode (Before Phase 3)

After completing Phase 2, you have gathered all requirements through read-only exploration and
user questions. You now need to write files.

Write your plan summarizing:
- Key findings from Phase 1 (codebase patterns, tech stack, existing conventions)
- Requirements gathered from Phase 2 (functional, non-functional, scope, acceptance criteria)
- Files to be created: `.gsd/specs/{feature}/requirements.md`

Then call **ExitPlanMode** to present the plan for approval.

### ⛔ POST-EXIT GUARD (NON-NEGOTIABLE)

After the user approves and plan mode exits, you are STILL inside the `/z:plan` command.

Your ONLY remaining tasks are:
1. Phase 3: Write `requirements.md` to `.gsd/specs/{feature}/`
2. Phase 4: Check infrastructure needs
3. Phase 5: Present requirements for user approval
4. Phase 5.5: Mark task complete and STOP

**DO NOT implement the feature. DO NOT write code. DO NOT invoke /z:design.**
**You are writing PLANNING DOCUMENTS, not implementing.**
```

**C. Fix Phase 0 references** in plan.core.md:
- Line 54: "continue to Enter Plan Mode" — keep as-is (still valid)
- Line 96: "Continue to Enter Plan Mode." — keep as-is (still valid)

### 5.2 brainstorm.md / brainstorm.core.md Changes

**A. Add "Enter Plan Mode" section** after Pre-Flight / Track in Claude Task System:

```markdown
## Enter Plan Mode

Call the **EnterPlanMode** tool to enter Claude Code plan mode.

Plan mode provides read-only tools for deep codebase exploration and research. You will stay
in plan mode for Phases 1-2.7 (Research through YAGNI Gate), then exit before Phase 3 when
you need to write files and create GitHub issues.

⚠️ Do NOT attempt to write files or run Bash while in plan mode — those tools are restricted.
```

**B. Add "Exit Plan Mode" section** between Phase 2.7 (YAGNI Gate) and Phase 3 (Issue Generation):

```markdown
## Exit Plan Mode (Before Phase 3)

After completing Phase 2.7 (YAGNI Gate), you have completed all discovery. You now need to
write files and create GitHub issues.

Write your plan summarizing:
- Research findings from Phase 1
- Discovery insights from Phase 2
- Trade-off decisions from Phase 2.5
- Validated design from Phase 2.6
- Features passing YAGNI Gate from Phase 2.7

Then call **ExitPlanMode** to present the plan for approval.

### ⛔ POST-EXIT GUARD (NON-NEGOTIABLE)

After the user approves and plan mode exits, you are STILL inside `/z:brainstorm`.

Your ONLY remaining tasks are:
1. Phase 3: Save research/transcript files, create GitHub issues
2. Phase 4: Present handoff recommendations and STOP

**DO NOT implement features. DO NOT invoke /z:plan. DO NOT write code.**
**You are completing the brainstorm workflow, not starting implementation.**
```

---

## 6. Acceptance Criteria

### 6.1 Definition of Done
- [ ] All 4 files modified with plan mode enter/exit sections
- [ ] Pre-Flight runs before plan mode entry in both commands
- [ ] Post-exit guards prevent implementation jump in both commands
- [ ] Existing workflow phases unchanged (only transitions added)
- [ ] validate_commands passes

### 6.2 Test Scenarios

| ID | Scenario | Given | When | Then |
|----|----------|-------|------|------|
| TC-001 | Plan enters plan mode | User runs /z:plan foo | After Pre-Flight | EnterPlanMode called |
| TC-002 | Plan exits before writes | Phase 2 complete | Before Phase 3 | ExitPlanMode called |
| TC-003 | Plan writes after exit | Plan mode exited | Phase 3 begins | requirements.md written |
| TC-004 | Plan doesn't implement | Phase 5.5 complete | Command ends | No code written |
| TC-005 | Brainstorm enters plan mode | User runs /z:brainstorm foo | After Pre-Flight | EnterPlanMode called |
| TC-006 | Brainstorm exits before writes | Phase 2.7 complete | Before Phase 3 | ExitPlanMode called |

---

## 7. Open Questions

| ID | Question | Status |
|----|----------|--------|
| Q-001 | Should TaskCreate run before or after EnterPlanMode? TaskCreate works in both modes, but running it before keeps Pre-Flight + tracking grouped together. | Resolved: Before (in Pre-Flight section) |

---

## 8. Documentation Impact Analysis

### 8.1 Files Requiring Documentation Updates
| File | Required Update | Priority |
|------|-----------------|----------|
| `CHANGELOG.md` | Add entry under Fixed | Must |

### 8.2 Documentation Tasks for Design Phase
- [x] CHANGELOG.md update task (ALWAYS required)
