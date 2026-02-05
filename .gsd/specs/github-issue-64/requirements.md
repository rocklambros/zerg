# Requirements: Command Authoring Framework (GitHub Issue #64)

## Metadata
- **Feature**: github-issue-64
- **Status**: APPROVED
- **Created**: 2026-02-04
- **Source**: https://github.com/anthropics/claude-code/issues/64
- **Discovery**: Socratic (3 rounds)

---

## 1. Problem Statement

Creating new ZERG commands requires:
1. Copying `_template.md` and manually editing
2. Remembering Task ecosystem requirements (backbone drift is common)
3. Running `validate_commands.py` repeatedly to check compliance
4. Manually splitting files when they exceed 300 lines
5. No automated testing that command instructions produce expected behavior

Authors frequently miss required sections, forget Task tool calls, or create commands that pass validation but fail in practice.

---

## 2. Functional Requirements

### FR-1: Scaffold Command (`/zerg:create-command`)
- **FR-1.1**: Create new command file from template
- **FR-1.2**: Hybrid mode: quick scaffold by default, `--interactive` flag for wizard
- **FR-1.3**: Auto-detect split requirement at 300 lines, create .core.md + .details.md pair
- **FR-1.4**: Generate skeleton test file alongside command
- **FR-1.5**: Inject Task tracking boilerplate (TaskCreate/TaskUpdate pattern)

### FR-2: Enhanced Validation (extend validate_commands.py)
- **FR-2.1**: Validate required sections exist (Pre-Flight, Help, Task Tracking)
- **FR-2.2**: Check Task tool call patterns match backbone requirements
- **FR-2.3**: Verify split pairs have matching content references
- **FR-2.4**: Report validation errors with line numbers and fix suggestions

### FR-3: Pressure Testing Framework
- **FR-3.1**: Optional pressure test scaffold in generated test file
- **FR-3.2**: Test command behavior with/without command loaded
- **FR-3.3**: Verify expected tool calls, output patterns, error handling
- **FR-3.4**: Passing pressure tests NOT required to ship (recommended only)

### FR-4: Auto-Documentation
- **FR-4.1**: Generate command reference in `docs/commands/{name}.md`
- **FR-4.2**: Update wiki index pages with new command entry
- **FR-4.3**: Extract help text, flags, examples from command file
- **FR-4.4**: Sync documentation when command file changes

---

## 3. Non-Functional Requirements

### NFR-1: Integration
- Extend existing `validate_commands.py` (single source of truth)
- No new module files for core validation logic
- New command file: `zerg/data/commands/create-command.md`

### NFR-2: Backward Compatibility
- Existing commands continue to pass validation
- No changes to validation strictness without opt-in
- Template updates don't break existing commands

### NFR-3: Developer Experience
- Quick scaffold completes in <2 seconds
- Clear error messages with actionable fix suggestions
- Pressure test scaffold is runnable out-of-box (may fail, but runs)

---

## 4. Scope Boundaries

### In Scope
- `/zerg:create-command` slash command
- Authoring functions in validate_commands.py
- Pressure test framework scaffold
- Wiki + reference documentation generation

### Out of Scope
- GUI/TUI for command authoring
- Automatic command migration from old formats
- Integration with external documentation systems
- AI-assisted command generation

---

## 5. User Stories

### US-1: Quick Scaffold
> As a ZERG contributor, I want to run `/zerg:create-command my-command` and get a valid, Task-integrated command file so I can start implementing immediately.

### US-2: Interactive Wizard
> As a new contributor, I want to run `/zerg:create-command my-command --interactive` and be guided through required sections so I don't miss anything.

### US-3: Validation Feedback
> As an author, I want validation errors to tell me exactly what's wrong and how to fix it so I don't have to guess.

### US-4: Pressure Testing
> As a maintainer, I want scaffold-generated test files that verify command behavior so I can catch regressions.

### US-5: Auto-Documentation
> As a documentation maintainer, I want command references auto-generated so docs stay in sync with commands.

---

## 6. Acceptance Criteria

### AC-1: Scaffold Command
- [ ] `/zerg:create-command foo` creates `zerg/data/commands/foo.md`
- [ ] File includes Pre-Flight, Task Tracking, Help sections
- [ ] File passes `python -m zerg.validate_commands`
- [ ] `--interactive` prompts for command metadata

### AC-2: Auto-Split
- [ ] Commands >300 lines auto-split to .core.md + .details.md
- [ ] Split files reference each other correctly
- [ ] Parent file retains core content

### AC-3: Validation
- [ ] Required sections flagged if missing
- [ ] Task tool patterns validated
- [ ] Errors include line numbers

### AC-4: Pressure Tests
- [ ] Scaffold generates `tests/pressure/test_{name}.py`
- [ ] Test file is syntactically valid and runnable
- [ ] Test verifies basic command loading

### AC-5: Documentation
- [ ] `docs/commands/{name}.md` generated from command
- [ ] Wiki index updated with command entry
- [ ] Help text extracted accurately

---

## 7. Technical Constraints

- Python 3.11+ required
- Must integrate with existing validate_commands.py (630 lines)
- Command file follows ZERG conventions (bash pseudo-code, markdown structure)
- Test files use pytest

---

## 8. Open Questions

_None remaining after Socratic discovery._

---

## 9. Dependencies

- validate_commands.py (extend, not replace)
- _template.md (base template for scaffolding)
- Command splitting infrastructure (existing in validate_commands.py)

---

## 10. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Validation too strict breaks existing | Low | High | Add opt-in flag for new strictness |
| Auto-split heuristics wrong | Medium | Low | Allow manual override |
| Wiki sync fails silently | Medium | Medium | Log warnings, don't fail scaffold |

---

## 11. Approval

Reply with:
- **"APPROVED"** to proceed to design phase
- **"REJECTED"** with specific concerns
- Questions for clarification
