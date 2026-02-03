# Feature Requirements: issue-94

## Metadata
- **Feature**: issue-94
- **Status**: REVIEW
- **Created**: 2026-02-02
- **Author**: ZERG Plan Mode
- **Source**: https://github.com/rocklambros/zerg/issues/94

---

## 1. Problem Statement

### 1.1 Background
The `/zerg:plan` command captures requirements through multi-phase interactive discovery. After user approval, the command ends abruptly with no guidance on next steps, no documentation task in the plan output, and existing documentation across GitHub/wiki has gaps in command/flag coverage.

### 1.2 Problem
Three related gaps:
1. No post-approval handoff — users must manually know to run `/z:design`
2. Documentation updates are never part of generated plans — docs drift from code
3. Command/flag documentation is incomplete across surfaces (`docs/commands.md`, wiki `zerg-*.md` pages)

### 1.3 Impact
- Users lose momentum after plan approval (no next-step guidance)
- Documentation falls behind with every feature shipped
- Users discover undocumented flags through trial and error

---

## 2. Users

### 2.1 Primary Users
ZERG users running `/zerg:plan` to start feature development

### 2.2 User Stories
- As a user, I want to be prompted with next steps after plan approval so I don't lose momentum
- As a user, I want every plan to include a documentation task so docs stay in sync
- As a user, I want all command flags documented so I can discover capabilities without reading source

---

## 3. Functional Requirements

### 3.1 Workstream A: Post-Approval Prompt

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-A01 | After user replies "APPROVED", use `AskUserQuestion` to prompt next steps | Must |
| FR-A02 | Option 1: "Clear context and run /z:design" (Recommended) — instructs user to `/compact` or start new session, then run `/z:design` | Must |
| FR-A03 | Option 2: "Continue in current context with /z:design" — instructs user to run `/z:design` immediately | Must |
| FR-A04 | Option 3: "Stop here — I'll run /z:design later" — command completes normally | Must |
| FR-A05 | TaskUpdate to `completed` fires regardless of which option is chosen | Must |
| FR-A06 | The AskUserQuestion fires AFTER TaskUpdate marks the plan task completed | Must |

### 3.2 Workstream B: Documentation Task in Requirements Template

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-B01 | Add a "Documentation" section to the `requirements.md` template in `plan.details.md` | Must |
| FR-B02 | Section references `/zerg:document` as the execution command | Must |
| FR-B03 | Section specifies: ensure all commands and flags are accounted for in docs | Must |
| FR-B04 | Section specifies: wiki command pages must follow `zerg-*.md` naming convention (non-command pages unaffected) | Must |
| FR-B05 | Section specifies: run `/zerg:design` + `/zerg:estimate` before executing documentation updates | Should |

### 3.3 Workstream C: Command/Flag Documentation Audit

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-C01 | Audit all 26 commands in `zerg/data/commands/*.md` against `docs/commands.md` | Must |
| FR-C02 | Audit all 26 commands against wiki `zerg-*.md` pages | Must |
| FR-C03 | Check `zerg-Reference.md` wiki page for completeness | Should |
| FR-C04 | Verify cross-cutting capability flags (`--quick`, `--think`, `--think-hard`, `--ultrathink`, `--no-compact`, `--mcp`, `--no-mcp`, `--tdd`, `--no-loop`, `--iterations`) are documented | Must |
| FR-C05 | Verify `/z:*` shorthand aliases documented as equivalent to `/zerg:*` | Must |
| FR-C06 | For each command: all `--action` variants, all flags with types/defaults/aliases, usage examples | Must |
| FR-C07 | Fix all gaps found during audit | Must |

---

## 4. Non-Functional Requirements

### 4.1 Consistency
- Wiki command pages use `zerg-*.md` naming convention
- Flag tables use consistent format across all documentation surfaces
- No contradictions between `docs/commands.md`, wiki pages, and command source files

### 4.2 Backward Compatibility
- No breaking changes to plan command behavior for users who don't interact with the prompt
- "Stop here" option preserves existing behavior exactly

---

## 5. Scope

### 5.1 In Scope
- Modify `plan.md` and `plan.core.md` — add post-approval AskUserQuestion
- Modify `plan.details.md` — add Documentation section to requirements template
- Audit and fix `docs/commands.md`
- Audit and fix wiki `zerg-*.md` command pages
- Audit `zerg-Reference.md`, `README.md`, `CLAUDE.md` for flag coverage

### 5.2 Out of Scope
- Auto-invoking `/z:design` (user will be instructed manually)
- Changing non-command wiki pages (e.g., `Getting-Started.md`, `FAQ.md`)
- Adding new commands or flags
- Modifying the plan command's discovery phases (1-4)

### 5.3 Assumptions
- `plan.md` and `plan.core.md` are kept in sync (same content)
- Wiki is editable via git clone of `rocklambros/zerg.wiki.git`
- All 26 commands have corresponding wiki pages

---

## 6. Dependencies

### 6.1 Internal Dependencies
| Dependency | Type | Status |
|------------|------|--------|
| `zerg/data/commands/plan.md` | File to modify | Exists |
| `zerg/data/commands/plan.core.md` | File to modify | Exists |
| `zerg/data/commands/plan.details.md` | File to modify | Exists |
| `docs/commands.md` | File to modify | Exists |
| Wiki `zerg-*.md` pages | Files to audit/modify | Exist (26 pages) |

---

## 7. Acceptance Criteria

### 7.1 Definition of Done
- [ ] Post-approval AskUserQuestion prompt works with all 3 options
- [ ] "Clear context" option instructs user to `/compact` then `/z:design`
- [ ] "Stop here" option completes normally (same as current behavior)
- [ ] TaskUpdate fires correctly regardless of user choice
- [ ] Requirements template includes Documentation section referencing `/zerg:document`
- [ ] Documentation section specifies `zerg-*.md` naming for command wiki pages
- [ ] All 26 commands audited against `docs/commands.md` — gaps fixed
- [ ] All 26 commands audited against wiki pages — gaps fixed
- [ ] Cross-cutting capability flags documented in appropriate locations
- [ ] `/z:*` shorthand aliases documented

### 7.2 Test Scenarios

| ID | Scenario | Given | When | Then |
|----|----------|-------|------|------|
| TC-001 | Post-approval prompt appears | Plan approved | User says "APPROVED" | AskUserQuestion with 3 options shown |
| TC-002 | Clear context option | Prompt shown | User picks "Clear context" | Instruction to /compact then /z:design |
| TC-003 | Continue option | Prompt shown | User picks "Continue" | Instruction to run /z:design now |
| TC-004 | Stop option | Prompt shown | User picks "Stop here" | Command completes, no further action |
| TC-005 | Task tracking | Any option picked | After prompt | Task status is "completed" |
| TC-006 | Template has docs section | New plan run | requirements.md generated | Contains Documentation section |

---

## 8. Open Questions

| ID | Question | Status |
|----|----------|--------|
| Q-001 | Does `zerg-Reference.md` currently serve as a command index, or is it something else? | Open |

---

## 9. Documentation

Execute `/zerg:document` after implementation to update all documentation surfaces based on changes made. Ensure:
- All ZERG commands and flags are accounted for
- Wiki command pages follow the `zerg-*.md` naming convention (non-command pages unaffected)
- Before executing, plan via `/zerg:design` and estimate via `/zerg:estimate`
