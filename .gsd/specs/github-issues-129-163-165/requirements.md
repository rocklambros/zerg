# Feature Requirements: GitHub Issues #129, #163, #165

## Metadata
- **Feature**: github-issues-129-163-165
- **Status**: APPROVED
- **Created**: 2026-02-07
- **Author**: Factory Plan Mode (Socratic)

---

## 1. Problem Statement

### 1.1 Background
Three related issues affect ZERG's documentation and workflow quality:
- Issue #129: `/zerg:document` produces only terse reference docs. An educational tone was manually developed but must be applied by hand.
- Issue #163: `/z:plan` occasionally bypasses the plan->design->rush workflow and auto-implements, violating the strict phase boundaries.
- Issue #165: Neither `/z:plan` nor `/z:design` systematically track documentation impact, leading to features shipping without updated docs.

### 1.2 Problem
1. No automated way to generate educational-style documentation from `/zerg:document`
2. Plan command lacks sufficient prompt-level guards against auto-implementation drift
3. Documentation drift: features ship without CHANGELOG, README, wiki, or command reference updates

### 1.3 Impact
- New users struggle with terse reference docs (no concept explanations, no diagrams)
- Workflow violations waste time and break the plan->design->rush contract
- Stale documentation erodes trust and creates confusion

---

## 2. Users

### 2.1 Primary Users
- Developers using ZERG to parallelize Claude Code work
- Contributors modifying ZERG commands

### 2.2 User Stories
- As a developer, I want `/zerg:document --tone educational` to auto-generate concept-first documentation so I don't have to manually rewrite reference docs
- As a user, I want `/z:plan` to never start implementing so the plan->design->rush workflow is respected
- As a contributor, I want `/z:plan` and `/z:design` to surface documentation impacts so docs stay current

---

## 3. Functional Requirements

### 3.1 Core Capabilities

| ID | Requirement | Priority | Issue |
|----|-------------|----------|-------|
| FR-001 | Add `--tone educational\|reference\|tutorial` flag to `/zerg:document` | Must | #129 |
| FR-002 | `educational` is the DEFAULT tone (not reference) | Must | #129 |
| FR-003 | Tone definitions stored as separate files at `zerg/data/tones/{tone}.md` | Must | #129 |
| FR-004 | Educational tone: every concept has CONCEPT, NARRATIVE, DIAGRAM, COMMAND sections | Must | #129 |
| FR-005 | Reference tone: terse tables and API signatures (current behavior) | Must | #129 |
| FR-006 | Tutorial tone: step-by-step walkthrough with simulated dialogues | Must | #129 |
| FR-007 | Add redundant anti-implementation guards to `plan.core.md` at 4 locations | Must | #163 |
| FR-008 | Plan terminal output: "PLANNING COMPLETE" banner with explicit EXIT statement | Must | #163 |
| FR-009 | Add Section 11 "Documentation Impact Analysis" to plan's requirements.md template | Must | #165 |
| FR-010 | Design command always generates CHANGELOG.md task in Level 5 quality phase | Must | #165 |
| FR-011 | Design command generates doc update tasks whenever command/flag functionality changes | Must | #165 |
| FR-012 | Update project documentation (README, wiki, command refs, CLAUDE.md) for this feature | Must | #165 |

### 3.2 Inputs
- `--tone` flag value: `educational` (default), `reference`, `tutorial`
- Tone definition files: `zerg/data/tones/{tone}.md`

### 3.3 Outputs
- Documentation generated in the specified tone style
- Plan requirements.md with Section 11 documentation impact analysis
- Design task-graph.json with mandatory doc/CHANGELOG tasks
- Updated project documentation reflecting all changes

---

## 4. Non-Functional Requirements

### 4.1 Performance
- No performance impact — tone is a prompt-level directive, not a computational change

### 4.2 Maintainability
- Tone definitions as separate files: adding a new tone = adding a file (no editing existing commands)
- `document.md` stays under 300-line split threshold

### 4.3 Testing
- Unit tests for `--tone` flag parsing in `document.py`
- CI drift check via `validate_commands` for plan anti-implementation guards
- Verification commands for each task in the task graph

---

## 5. Scope

### 5.1 In Scope
- `--tone` flag for `/zerg:document` with 3 tones
- 3 tone definition files (`educational.md`, `reference.md`, `tutorial.md`)
- Anti-implementation hardening of `plan.core.md` and `plan.md` (prompt-level only)
- Section 11 in plan's requirements.md template
- Mandatory doc task generation in design command
- Project documentation updates (README, wiki, command refs, CLAUDE.md)
- CHANGELOG.md entries

### 5.2 Out of Scope
- Python-level enforcement of plan workflow boundaries (deferred)
- Tone content transformation engine (tone is prompt-level, not programmatic)
- Splitting `document.md` into core/details (stays under 300 lines)

### 5.3 Assumptions
- `/zerg:document` is a Claude Code slash command where Claude has file access to read tone files
- Parent files (`plan.md`, `design.md`) must stay synchronized with their `.core.md` counterparts

---

## 6. Dependencies

### 6.1 Internal Dependencies
| Dependency | Type | Status |
|------------|------|--------|
| `zerg/commands/document.py` | Modify | Exists |
| `zerg/data/commands/document.md` | Modify | Exists |
| `zerg/data/commands/plan.core.md` | Modify | Exists |
| `zerg/data/commands/plan.details.md` | Modify | Exists |
| `zerg/data/commands/design.core.md` | Modify | Exists |
| `.gsd/specs/documentation-tone-overhaul/requirements.md` | Reference | Approved |

---

## 7. Acceptance Criteria

### 7.1 Definition of Done
- [ ] `--tone` flag accepted by `/zerg:document` with educational as default
- [ ] 3 tone definition files exist at `zerg/data/tones/`
- [ ] `plan.core.md` has anti-implementation guards at 4+ locations
- [ ] Plan terminal output shows "PLANNING COMPLETE" banner
- [ ] `plan.details.md` requirements template includes Section 11
- [ ] `design.core.md` has "Mandatory Documentation Tasks" subsection
- [ ] All unit tests pass
- [ ] `validate_commands` passes
- [ ] Project docs (README, wiki, command refs, CLAUDE.md) updated
- [ ] CHANGELOG.md updated

### 7.2 Test Scenarios

| ID | Scenario | Given | When | Then |
|----|----------|-------|------|------|
| TC-001 | Default tone | No --tone flag | Run /zerg:document | Educational tone used |
| TC-002 | Explicit reference | --tone reference | Run /zerg:document | Reference style output |
| TC-003 | Invalid tone | --tone bogus | Run /zerg:document | Click rejects with error |
| TC-004 | Plan guards | Run /z:plan | Requirements approved | No implementation occurs; "PLANNING COMPLETE" shown |
| TC-005 | Design doc tasks | Run /z:design | Task graph generated | CHANGELOG task present in Level 5 |

---

## 8. Open Questions

None — all resolved through Socratic discovery rounds.

---

## 9. Approval

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Engineering | User | 2026-02-07 | APPROVED |

---

## 10. Documentation

After implementation, execute `/zerg:document` to update all documentation surfaces.

---

## 11. Documentation Impact Analysis

### 11.1 Files Requiring Documentation Updates
| File | Current State | Required Update | Priority |
|------|--------------|-----------------|----------|
| `CHANGELOG.md` | [Unreleased] section | Add entries for --tone flag, plan guards, doc impact analysis | Must |
| `README.md` | Shows `/zerg:document` without --tone | Add --tone flag to usage examples | Must |
| `docs/commands-quick.md` | Document flag table lacks --tone | Add --tone row | Must |
| `docs/commands-deep.md` | No tone documentation | Add --tone deep docs with tone descriptions | Must |
| `.gsd/wiki/Command-Reference.md` | Document entry lacks --tone | Update with --tone flag | Must |
| `.gsd/wiki/Tutorial.md` | Document examples lack tone | Update examples to mention tone | Should |
| `CLAUDE.md` | No doc impact analysis requirement | Document the new requirement for /z:plan and /z:design | Must |

### 11.2 Documentation Tasks for Design Phase
- [x] CHANGELOG.md update task (ALWAYS required)
- [x] README.md update (new CLI flag)
- [x] Command reference updates (command/flag functionality changed)
- [x] CLAUDE.md update (new project convention)
- [x] Wiki updates (user-facing behavior changes)
