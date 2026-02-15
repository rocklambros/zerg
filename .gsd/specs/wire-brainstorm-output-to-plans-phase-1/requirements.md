# Requirements: Fix Plan/Brainstorm Commands & Wire Brainstorm→Plan Handoff

**Feature**: wire-brainstorm-output-to-plans-phase-1
**Status**: APPROVED
**Created**: 2026-02-14

## Problem Statement

Two related issues with `/z:plan` and `/z:brainstorm`:

1. **Bug**: Both commands enter Claude Code plan mode (EnterPlanMode) proactively, which has approve→implement semantics that override the commands' text-based stop guards. After the user approves, Claude jumps to implementation instead of writing requirements/specs. This has persisted since v0.2.1 despite a partial fix in v0.2.2 that removed explicit EnterPlanMode calls but never added an explicit prohibition.

2. **Gap**: Brainstorm creates GitHub issues with full context (titles, descriptions, acceptance criteria, priority) but plan never reads them. Discovery work is lost and re-asked during plan's Phase 2.

## Requirements

### Bug Fix: EnterPlanMode Prohibition

#### R1: Add explicit EnterPlanMode/ExitPlanMode prohibition to plan

Add to WORKFLOW BOUNDARY's MUST NEVER list (first item):
- `Call **EnterPlanMode** or **ExitPlanMode** tools (these have approve→implement semantics that override stop guards)`

Add a `⛔ PLAN MODE PROHIBITION` paragraph explaining: this is a requirements-gathering command, not an implementation task. EnterPlanMode creates an approve→implement contract that conflicts with the command's purpose.

**Files modified**: `plan.md`, `plan.core.md`
**Status**: DONE (applied earlier this session)

#### R2: Add explicit EnterPlanMode/ExitPlanMode prohibition to brainstorm

Same prohibition as R1, adapted for brainstorm (discovery/brainstorming command, not implementation).

**Files modified**: `brainstorm.md`, `brainstorm.core.md`
**Status**: DONE (applied earlier this session)

#### R3: Restore v0.2.0 Phase 5.5 handoff in plan

Restore the AskUserQuestion in Phase 5.5 that was removed during the v0.2.2 fix:
- "Requirements approved! How would you like to proceed?"
- Options: "Clear context, then /z:design (Recommended)" / "Stop here"
- Based on response, output instructions (not auto-run)
- Then output PLANNING COMPLETE banner and STOP

**Files modified**: `plan.md`, `plan.core.md`
**Status**: DONE (applied earlier this session)

### Feature: Wire Brainstorm→Plan via GitHub Issues

#### R4: Plan accepts a GitHub issue number

Plan gains `--issue N` flag (and `#N` shorthand in feature argument). When provided, plan reads the issue via `gh issue view N` and uses it as brainstorm context.

Usage:
```
/z:plan user-auth --issue 42
/z:plan #42
```

Add to Flags section in plan.md and plan.core.md.

**Files modified**: `plan.md`, `plan.core.md`

#### R5: Plan Phase 1 loads issue context

Plan Phase 1 (Context Gathering) adds a new first step:

1. **Check for issue context** — If `--issue N` or `#N` provided, run `gh issue view N` and read the issue body.

If found, output:
```
Found GitHub issue #42: "Add user authentication"
Loading brainstorm context from issue body...
```

If `--issue` not provided, continue normally (backward compatible).

**Files modified**: `plan.md`, `plan.core.md`

#### R6: Plan Phase 2 skips questions already answered by issue

When issue context is loaded, plan's Phase 2 (Requirements Elicitation) should:

- Acknowledge what the issue already captured (scope, acceptance criteria, priority)
- Present a summary: "Issue #42 already covers: [list]. Asking about gaps only."
- Only ask about areas the issue didn't cover or where plan needs deeper specificity

Advisory guidance — the model uses judgment about what's already answered vs. what needs more detail.

**Files modified**: `plan.md`, `plan.core.md`

#### R7: Brainstorm handoff references issue numbers

Brainstorm's Phase 4 (Handoff) AskUserQuestion option should include the top issue number in the suggested next command:

```
"Run /compact then /z:plan {feature} --issue {top-issue-number}"
```

**Files modified**: `brainstorm.md`, `brainstorm.core.md`

## Scope Boundaries

### In Scope
- EnterPlanMode/ExitPlanMode prohibition in all 4 command files (R1-R2, DONE)
- Restore v0.2.0 Phase 5.5 AskUserQuestion handoff in plan (R3, DONE)
- Plan accepts `--issue N` flag to load GitHub issue as context (R4-R6)
- Brainstorm handoff includes issue number in suggested command (R7)

### Out of Scope
- Pointer files or custom artifact formats
- Changes to brainstorm's issue creation (Phase 3)
- Changes to design.md or downstream commands
- Python code changes (command-file-only)
- Auto-populating requirements.md from issue data

## Acceptance Criteria

- [x] Plan and brainstorm MUST NEVER list includes EnterPlanMode/ExitPlanMode (R1-R2)
- [x] Plan Phase 5.5 has AskUserQuestion with "Clear context, then /z:design" option (R3)
- [ ] Plan accepts `--issue N` and `#N` syntax (R4)
- [ ] Plan Phase 1 reads issue via `gh issue view N` when flag provided (R5)
- [ ] Plan Phase 1 works normally when no issue provided — backward compatible (R5)
- [ ] Plan Phase 2 acknowledges issue content and reduces redundant questions (R6)
- [ ] Brainstorm Phase 4 handoff includes issue number in suggested `/z:plan` command (R7)
- [ ] All 4 command files updated: plan.md, plan.core.md, brainstorm.md, brainstorm.core.md

## Dependencies

- `gh` CLI must be installed and authenticated (already a brainstorm dependency)

## Infrastructure Requirements

- None.

## Documentation Impact

- CHANGELOG.md: Add entry under `[Unreleased] > Fixed` (R1-R3) and `[Unreleased] > Changed` (R4-R7)
