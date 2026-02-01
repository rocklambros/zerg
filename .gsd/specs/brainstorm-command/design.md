# Technical Design: /z:brainstorm Command + Feature Issues + Documentation

## Metadata
- **Feature**: brainstorm-command
- **Status**: DRAFT
- **Created**: 2026-02-01

---

## 1. Overview

### 1.1 Summary
Add `/zerg:brainstorm` (alias `/z:brainstorm`) as a new discovery command that performs competitive research, Socratic ideation, and automated GitHub issue creation. Update all 18+ documentation files to reflect 26 commands. Create 6-10 feature issues for the open-source roadmap.

### 1.2 Goals
- New brainstorm command following all ZERG patterns (command splitting, task ecosystem, context management)
- Complete documentation sweep: every reference to "25 commands" updated, wiki page created, tutorials updated
- Feature issues created with full acceptance criteria and priority labels

### 1.3 Non-Goals
- Python implementation module (brainstorm is a slash command spec, not a CLI subcommand)
- Automated brainstorm execution (it's interactive, driven by user dialogue)

---

## 2. Architecture

### 2.1 Command File Structure

```
zerg/data/commands/
  brainstorm.md          # Main file (mirrors core, backward compat)
  brainstorm.core.md     # Essential: workflow, flags, task tracking (~150 lines)
  brainstorm.details.md  # Reference: question templates, schemas (~250 lines)
```

### 2.2 Workflow Phases

```
Phase 1: Research (WebSearch)
    |
    v
Phase 2: Socratic Discovery (3 rounds × AskUserQuestion)
    |
    v
Phase 3: Issue Generation (gh issue create)
    |
    v
Phase 4: Handoff (save artifacts, suggest /z:plan)
```

### 2.3 Context Management Integration

| Feature | Implementation |
|---------|---------------|
| Command splitting | `.core.md` (~30%) + `.details.md` (~70%) |
| Scoped loading | Phase 1: PROJECT.md only. Phase 2: codebase if needed. |
| Session resumability | State saved after each phase to `.gsd/specs/brainstorm-{id}/` |
| Question batching | 3-4 questions per AskUserQuestion call |
| Compact output | JSON manifest for machine parsing; concise markdown summary |

---

## 3. Documentation Impact Matrix

### 3.1 Command Count Updates ("25" → "26")

| File | Line | Change |
|------|------|--------|
| `README.md` | 3, 52, 86, 400, 576 | "25" → "26" |
| `CHANGELOG.md` | 27 | "25 slash commands" → "26 slash commands" + add `/zerg:brainstorm` |
| `docs/commands.md` | 3 | "all 25" → "all 26" |
| `docs/tutorial-minerals-store.md` | 1557 | "all 25" → "all 26" |
| `.zerg/wiki/Home.md` | 80 | "25 commands" → "26 commands" |
| `.zerg/wiki/Command-Reference.md` | 2 | "all 25" → "all 26" |
| `.zerg/wiki/Contributing.md` | 87, 363 | "25 commands" → "26 commands" |
| `.zerg/wiki/Your-First-Feature.md` | 412 | "19" → "26" (was already stale) |

### 3.2 Files Requiring New Content

| File | New Content |
|------|-------------|
| `docs/commands.md` | TOC entry + full brainstorm section (~80 lines) |
| `README.md` | Command overview table row |
| `ARCHITECTURE.md` | CLI Commands table row (~line 407) |
| `.zerg/wiki/Command-brainstorm.md` | New wiki page (full reference, ~90 lines) |
| `.zerg/wiki/Command-Reference.md` | Index table row + category entry |
| `.zerg/wiki/_Sidebar.md` | Link under Core Workflow |
| `.zerg/wiki/Home.md` | Key Commands listing |
| `.zerg/wiki/Quick-Start.md` | Optional brainstorm step before Plan |
| `.zerg/wiki/Your-First-Feature.md` | Tip about brainstorm for discovery |
| `.zerg/wiki/Getting-Started.md` | Workflow table row |
| `.zerg/wiki/Tutorials.md` | Lifecycle reference update |
| `.zerg/wiki/Installation.md` | Slash commands listing |
| `.zerg/wiki/FAQ.md` | Workflow description |
| `.zerg/wiki/Glossary.md` | "Brainstorm" term definition |
| `.zerg/wiki/Context-Engineering.md` | Split commands list (9 → 10) |
| `CLAUDE.md` | Quick Start + Task Subject Convention |
| `docs/context-engineering.md` | Split commands list (9 → 10) |

---

## 4. Key Decisions

### Decision: Brainstorm placement in workflow

**Context**: Where does brainstorm fit in init → plan → design → rush?

**Decision**: Before plan, as an optional discovery step.

**Rationale**: Brainstorm produces feature ideas and GitHub issues. Plan takes a specific feature name. Brainstorm feeds into plan naturally.

**Workflow**: `brainstorm (optional) → plan → design → rush → merge`

### Decision: Command categorization

**Context**: Which category in docs/commands.md?

**Decision**: Core Workflow (between init and plan).

**Rationale**: Brainstorm is a workflow stage, not a utility. It's the entry point for feature discovery.

---

## 5. File Ownership

| File | Task | Operation |
|------|------|-----------|
| `zerg/data/commands/brainstorm.md` | BS-001 | create |
| `zerg/data/commands/brainstorm.core.md` | BS-001 | create |
| `zerg/data/commands/brainstorm.details.md` | BS-001 | create |
| `docs/commands.md` | BS-002 | modify |
| `README.md` | BS-002 | modify |
| `ARCHITECTURE.md` | BS-002 | modify |
| `CLAUDE.md` | BS-002 | modify |
| `docs/context-engineering.md` | BS-002 | modify |
| `docs/tutorial-minerals-store.md` | BS-002 | modify |
| `CHANGELOG.md` | BS-002 | modify |
| `.zerg/wiki/Command-brainstorm.md` | BS-003 | create |
| `.zerg/wiki/Command-Reference.md` | BS-003 | modify |
| `.zerg/wiki/_Sidebar.md` | BS-003 | modify |
| `.zerg/wiki/Home.md` | BS-003 | modify |
| `.zerg/wiki/Quick-Start.md` | BS-003 | modify |
| `.zerg/wiki/Your-First-Feature.md` | BS-003 | modify |
| `.zerg/wiki/Getting-Started.md` | BS-003 | modify |
| `.zerg/wiki/Tutorials.md` | BS-003 | modify |
| `.zerg/wiki/Installation.md` | BS-003 | modify |
| `.zerg/wiki/FAQ.md` | BS-003 | modify |
| `.zerg/wiki/Glossary.md` | BS-003 | modify |
| `.zerg/wiki/Context-Engineering.md` | BS-003 | modify |
| `.zerg/wiki/Contributing.md` | BS-003 | modify |
| (GitHub issues) | BS-004 | create |

---

## 6. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Missing a "25 commands" reference | Med | Low | grep verification in BS-005 |
| Wiki link syntax wrong | Low | Low | Follow existing Command-plan.md pattern exactly |
| Command not discovered by install_commands.py | Low | Med | File naming follows exact pattern of existing commands |

---

## 7. Parallel Execution Notes

### 7.1 Safe Parallelization
- BS-001 (command files) has no file overlap with BS-002 (project docs) or BS-003 (wiki docs)
- BS-002 and BS-003 have no file overlap (different directories)
- BS-004 (issues) is independent of all file tasks
- BS-005 (validation) depends on all others

### 7.2 Recommended Workers
- Minimum: 1 worker (sequential)
- Optimal: 4 workers (one per independent task)
- Maximum: 4 workers

---

## 8. Approval

Status: DRAFT — awaiting review.
