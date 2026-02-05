# Technical Design: documentation-overhaul

## Metadata
- **Feature**: documentation-overhaul
- **Status**: APPROVED
- **Created**: 2026-02-04
- **Author**: ZERG Design Mode

---

## 1. Overview

### 1.1 Summary

Comprehensive documentation overhaul creating a complete GitHub wiki (11 pages), restructuring README.md as a step-by-step tutorial, exhaustively documenting all 26 commands with every flag, and auditing ARCHITECTURE.md against current code.

### 1.2 Goals
- Wiki as primary documentation with 11 interconnected pages
- Exhaustive command reference (26 commands, every flag, 3-5 examples each)
- Tutorial-focused README with minerals-store walkthrough
- ARCHITECTURE.md verified against current source code
- All commands referenced as `/zerg:command` format

### 1.3 Non-Goals
- New features or code changes (documentation only)
- Translations
- Video tutorials
- Changes to Python CLI behavior

---

## 2. Architecture

### 2.1 Documentation Structure

```
Wiki Pages (Primary)          docs/ (Mirror)              README.md
├── Home                      ├── commands.md (sync)      └── Tutorial-focused
├── Command-Reference         ├── configuration.md             step-by-step guide
├── Configuration             ├── context-engineering.md       with quick reference
├── Architecture              ├── plugins.md                   table
├── Tutorial                  ├── tutorial-minerals-store.md
├── Plugins                   └── design-principles.md
├── Security
├── Context-Engineering       ARCHITECTURE.md
├── Troubleshooting           └── Audited, updated
├── FAQ
└── Contributing
```

### 2.2 Command Documentation Template

Each command gets exhaustive documentation:

```markdown
## /zerg:{command}

{Synopsis — one line}

**When to use**: {context}

### Usage

{Full command syntax with all variants}

### Flags

| Flag | Short | Type | Default | Description |
|------|-------|------|---------|-------------|
| ... | ... | ... | ... | ... |

### Description

{2-3 paragraphs explaining behavior, modes, workflow}

### Examples

1. {Common use case}
2. {Variant use case}
3. {Edge case or advanced use}
4-5. {Additional examples as needed}

### Related Commands

- `/zerg:{related1}` — {why related}
- `/zerg:{related2}` — {why related}

### Notes

- {Edge cases}
- {Warnings}
- {Tips}
```

### 2.3 Data Flow

```
Source files (zerg/data/commands/*.md)
          │
          ▼
    /zerg:document --deep
          │
          ▼
    Generated content
          │
          ├──▶ Wiki pages (.gsd/wiki/)
          │
          ├──▶ docs/commands.md (exhaustive)
          │
          └──▶ README.md (tutorial extract)
```

---

## 3. Detailed Design

### 3.1 Wiki Pages Specification

| Page | Content | Source |
|------|---------|--------|
| Home | Overview, quick start, navigation links | Extract from README |
| Command-Reference | All 26 commands with full flag tables, examples | Command files + docs/commands.md |
| Configuration | config.yaml structure, env vars, tuning | docs/configuration.md + enhance |
| Architecture | System design, module ref, execution model | ARCHITECTURE.md |
| Tutorial | minerals-store walkthrough, all phases | docs/tutorial-minerals-store.md + enhance |
| Plugins | Quality gates, hooks, launchers | docs/plugins.md |
| Security | Security rules integration, pre-commit | CLAUDE.md security section + enhance |
| Context-Engineering | Token optimization, command splitting | docs/context-engineering.md |
| Troubleshooting | Common issues, diagnostics, recovery | Extract from README + enhance |
| FAQ | Frequently asked questions | New content |
| Contributing | Dev setup, code style, PR process | CONTRIBUTING.md |

### 3.2 Command Groupings

Commands grouped by workflow phase, alphabetical within groups:

**Core Workflow** (5 commands):
- `/zerg:brainstorm`
- `/zerg:design`
- `/zerg:init`
- `/zerg:plan`
- `/zerg:rush`

**Monitoring & Control** (6 commands):
- `/zerg:cleanup`
- `/zerg:logs`
- `/zerg:merge`
- `/zerg:retry`
- `/zerg:status`
- `/zerg:stop`

**Quality & Analysis** (6 commands):
- `/zerg:analyze`
- `/zerg:build`
- `/zerg:refactor`
- `/zerg:review`
- `/zerg:security`
- `/zerg:test`

**Utilities** (4 commands):
- `/zerg:create-command`
- `/zerg:debug`
- `/zerg:git`
- `/zerg:plugins`
- `/zerg:worker`

**Documentation & AI** (5 commands):
- `/zerg:document`
- `/zerg:estimate`
- `/zerg:explain`
- `/zerg:index`
- `/zerg:select-tool`

### 3.3 README Tutorial Structure

```markdown
# ZERG

{Logo}

{1 paragraph overview}

## Quick Start (5 minutes)

Step-by-step from zero to first feature:
1. Installation
2. /zerg:init
3. /zerg:brainstorm (optional)
4. /zerg:plan
5. /zerg:design
6. /zerg:rush
7. Monitor & Review
8. /zerg:git --action ship

## Command Quick Reference

| Category | Command | Purpose |
|----------|---------|---------|
| Core | /zerg:init | Initialize project |
| ... | ... | ... |

→ Full documentation: [Wiki](link)

## Configuration

Brief overview → [Wiki: Configuration](link)

## Links

- [Full Command Reference](wiki)
- [Architecture](ARCHITECTURE.md)
- [Tutorial: Minerals Store](wiki)
```

---

## 4. Key Decisions

### 4.1 Wiki as Primary Documentation

**Context**: Documentation is fragmented across README, docs/, ARCHITECTURE.md.

**Decision**: Wiki is the primary documentation. docs/ syncs from wiki. README focuses on tutorial.

**Rationale**: Wiki can be updated independently of releases, supports navigation sidebar, is the expected location for project documentation on GitHub.

**Consequences**: Must create wiki pages (manual or via gh CLI). docs/ becomes a mirror for offline access.

### 4.2 Exhaustive Flag Documentation

**Context**: Current docs/commands.md has most flags but lacks consistency.

**Decision**: Every flag for every command must be documented with type, default, and description.

**Rationale**: Users need complete reference without reading source files.

**Consequences**: Requires reading all 28 command files to extract every flag.

### 4.3 Grouped + Alphabetical Command Order

**Context**: User requested grouped by workflow phase, alphabetical within groups.

**Decision**: Five groups (Core, Monitoring, Quality, Utilities, Docs & AI), alphabetical within each.

**Rationale**: Users can find commands by context (what am I doing?) and by name.

---

## 5. Implementation Plan

### 5.1 Phase Summary

| Phase | Tasks | Parallel | Est. Files |
|-------|-------|----------|-----------|
| Foundation | 3 | Yes | 3 |
| Core Wiki | 4 | Yes | 4 |
| Extended Wiki | 5 | Yes | 5 |
| Command Docs | 5 | Yes | 5 |
| Quality | 3 | No | 3 |

### 5.2 File Ownership

| File | Task ID | Operation |
|------|---------|-----------|
| `.gsd/wiki/Home.md` | TASK-001 | create |
| `.gsd/wiki/Command-Reference.md` | TASK-002 | create |
| `.gsd/wiki/Configuration.md` | TASK-003 | create |
| `.gsd/wiki/Architecture.md` | TASK-004 | create |
| `.gsd/wiki/Tutorial.md` | TASK-005 | create |
| `.gsd/wiki/Plugins.md` | TASK-006 | create |
| `.gsd/wiki/Security.md` | TASK-007 | create |
| `.gsd/wiki/Context-Engineering.md` | TASK-008 | create |
| `.gsd/wiki/Troubleshooting.md` | TASK-009 | create |
| `.gsd/wiki/FAQ.md` | TASK-010 | create |
| `.gsd/wiki/Contributing.md` | TASK-011 | create |
| `docs/commands.md` | TASK-012 | modify |
| `README.md` | TASK-013 | modify |
| `ARCHITECTURE.md` | TASK-014 | modify |
| `.gsd/wiki/_Sidebar.md` | TASK-015 | create |

### 5.3 Dependency Graph

```
Level 1 (Foundation):
  TASK-001 (Home) ───────┐
  TASK-002 (Command-Ref) ├──▶ Level 2 (Core Wiki)
  TASK-003 (Configuration)│

Level 2 (Core Wiki):
  TASK-004 (Architecture) ─┐
  TASK-005 (Tutorial) ─────├──▶ Level 3 (Extended Wiki)
  TASK-006 (Plugins) ──────┤
  TASK-007 (Security) ─────┘

Level 3 (Extended Wiki):
  TASK-008 (Context-Eng) ──┐
  TASK-009 (Troubleshoot) ─├──▶ Level 4 (Sync)
  TASK-010 (FAQ) ──────────┤
  TASK-011 (Contributing) ─┘

Level 4 (Sync & Polish):
  TASK-012 (docs/commands.md sync)
  TASK-013 (README restructure)
  TASK-014 (ARCHITECTURE audit)
  TASK-015 (_Sidebar.md navigation)

Level 5 (Validation):
  TASK-016 (Validation & Cross-links)
```

---

## 6. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Wiki push requires manual steps | Medium | Low | Document wiki clone/push process |
| Flag extraction misses edge cases | Low | Medium | Cross-check against command source files |
| Tutorial becomes stale | Low | Low | Tutorial uses actual ZERG commands |
| Large context for command docs | Medium | Low | Split into multiple tasks by group |

---

## 7. Testing Strategy

### 7.1 Link Validation

All wiki pages must have valid cross-links. Check:
- Internal wiki links resolve
- External links to docs/ work
- Command references use `/zerg:` format

### 7.2 Acceptance Criteria Validation

1. **Wiki Complete**: All 11 wiki pages exist in `.gsd/wiki/`
2. **Commands Documented**: All 26 commands have flags, examples
3. **Tutorial Works**: New user can follow README end-to-end
4. **Architecture Current**: ARCHITECTURE.md matches current modules
5. **Format Consistent**: All `/zerg:` references, no "Command-init"

---

## 8. Parallel Execution Notes

### 8.1 Safe Parallelization

- Level 1: 3 tasks (foundation pages) — fully parallel
- Level 2: 4 tasks (core wiki pages) — fully parallel
- Level 3: 4 tasks (extended wiki) — fully parallel
- Level 4: 4 tasks (sync operations) — fully parallel
- Level 5: 1 task (validation) — sequential

### 8.2 Recommended Workers

- Minimum: 3 workers
- Optimal: 4 workers (matches widest level)
- Maximum: 5 workers

### 8.3 Estimated Duration

- Single worker: ~4 hours
- With 4 workers: ~1.5 hours
- Speedup: ~2.7x

---

## 9. Approval

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Architecture | | | PENDING |
| Engineering | | | PENDING |
