# Technical Design: documentation-audit-sync

## Metadata
- **Feature**: documentation-audit-sync
- **Status**: APPROVED
- **Created**: 2026-02-07
- **Author**: Factory Design Mode

---

## 1. Overview

### 1.1 Summary
Documentation-only feature that synchronizes 10 missing CLI flags across 5 documentation surfaces and expands the `--tone` flag coverage in the wiki. No code changes, no tests — purely Markdown file edits.

### 1.2 Goals
- Add 10 missing flags to `docs/commands-quick.md` and wiki `Command-Reference.md`
- Expand `--tone` documentation in wiki Command-Reference and Tutorial
- Verify/fix flag tables in `docs/commands-deep.md`
- Update CHANGELOG.md
- Push wiki changes to GitHub

### 1.3 Non-Goals
- Python code changes
- New documentation pages
- Template or test changes
- README.md changes (already adequate)
- CLAUDE.md changes (already adequate)

---

## 2. Architecture

### 2.1 High-Level Design

```
┌─────────────────────────────────────────────────┐
│               Source of Truth                     │
│  Python CLI code (click options in zerg/commands) │
└──────────────────────┬──────────────────────────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
  ┌──────────────┐ ┌──────────┐ ┌──────────────┐
  │commands-quick│ │commands- │ │ Wiki Command │
  │    .md       │ │ deep.md  │ │ Reference.md │
  └──────────────┘ └──────────┘ └──────────────┘
                                       │
                                ┌──────┴──────┐
                                ▼             ▼
                         ┌──────────┐  ┌──────────┐
                         │ Tutorial │  │ CHANGELOG│
                         │   .md    │  │   .md    │
                         └──────────┘  └──────────┘
```

All 5 doc surfaces must agree on flag names, types, defaults, and descriptions.

### 2.2 Component Breakdown

| Component | Responsibility | Files |
|-----------|---------------|-------|
| Quick Reference | Concise flag tables | `docs/commands-quick.md` |
| Deep Guide | Detailed explanations + examples | `docs/commands-deep.md` |
| Wiki Reference | Educational command docs | `.gsd/wiki/Command-Reference.md` |
| Wiki Tutorial | Hands-on examples | `.gsd/wiki/Tutorial.md` |
| Changelog | Release notes | `CHANGELOG.md` |

### 2.3 Data Flow

1. Read flag definitions from Python CLI source code
2. Add missing flags to each documentation surface
3. Expand `--tone` section in wiki with descriptions, examples, config reference
4. Verify cross-surface consistency
5. Push wiki changes to GitHub

---

## 3. Detailed Design

### 3.1 Missing Flags to Add

**10 flags across 6 commands:**

| Command | Flag | Type | Default | Help Text |
|---------|------|------|---------|-----------|
| `/zerg:rush` | `--check-gates` | bool | false | Pre-run quality gates during dry-run |
| `/zerg:rush` | `--what-if` | bool | false | Compare different worker counts and modes |
| `/zerg:rush` | `--risk` | bool | false | Show risk assessment for task graph |
| `/zerg:rush` | `--skip-tests` | bool | false | Skip test gates (lint-only mode) |
| `/zerg:plan` | `--from-issue` | string | "" | Import requirements from GitHub issue URL |
| `/zerg:debug` | `--deep` | bool | false | System-level diagnostics |
| `/zerg:debug` | `--env` | bool | false | Environment diagnostics |
| `/zerg:merge` | `--target` | string | main | Target branch |
| `/zerg:retry` | `--worker` | int | — | Assign task to specific worker |
| `/zerg:analyze` | `--performance` | bool | false | Comprehensive performance audit (140 factors) |

**Note**: `--deep` and `--env` already exist in commands-quick.md and wiki but are confirmed missing from commands-quick.md per requirements. On inspection, commands-quick.md **does** include `--deep` and `--env` for debug (lines 297-302). The wiki also has them (lines 2441, 2444). The requirements claim they're missing from commands-quick.md — but upon reading the file, they are present. We will verify and only add what's truly missing.

**Verified missing from commands-quick.md**: `--check-gates`, `--what-if`, `--risk`, `--skip-tests` (rush), `--from-issue` (plan), `--target` (merge), `--worker` (retry), `--performance` (analyze). Debug flags `--deep` and `--env` are already present — will verify wiki.

**Verified missing from wiki Command-Reference.md**: Same flags as above. Wiki rush flags table (line 731-740) is missing the 4 rush flags. Wiki plan flags table (lines 603-605) missing `--from-issue`. Wiki merge flags table (lines 1118-1125) missing `--target`. Wiki retry flags table (lines 1242-1250) missing `--worker`. Wiki analyze flags table (lines 1600-1605) missing `--performance`.

### 3.2 Tone Expansion Plan

Replace the single stub row in wiki Command-Reference.md with:
1. "Tone Options" subsection after the flags table
2. Descriptions of each tone: educational, reference, tutorial
3. Usage examples showing `--tone` with each value
4. Config default mention (`documentation.default_tone`)
5. Updated workflow diagram showing tone selection step

### 3.3 Tutorial Tone Expansion Plan

Current state (3 lines at end of Tutorial): brief mention of 3 tones and one example.
Target: Add a proper "Using Documentation Tones" subsection with:
- Before/after output snippets for educational vs reference
- When to use each tone
- Config default mention

---

## 4. Key Decisions

### Decision: Debug flags --deep and --env

**Context**: Requirements claim these are missing from commands-quick.md, but they already exist at lines 297-302.

**Decision**: Verify both surfaces; only add where truly missing. Do not duplicate existing entries.

**Consequences**: May result in fewer than 10 flag additions per file if some already exist.

### Decision: commands-deep.md approach

**Context**: commands-deep.md uses a narrative format (What/Why/How/Using) without formal flag tables. Adding flag tables would break the document's style.

**Decision**: Add new flags inline within "Using It" sections as example commands, consistent with existing style. Do not add formal flag tables.

**Consequences**: Coverage is through examples and narrative rather than tabular format.

---

## 5. Implementation Plan

### 5.1 Phase Summary

| Phase | Tasks | Parallel | Est. Time |
|-------|-------|----------|-----------|
| Foundation (L1) | 3 | Yes | 10 min |
| Integration (L2) | 1 | No | 5 min |
| Quality (L3) | 1 | No | 5 min |

### 5.2 File Ownership

| File | Task ID | Operation |
|------|---------|-----------|
| `docs/commands-quick.md` | TASK-001 | modify |
| `.gsd/wiki/Command-Reference.md` | TASK-002 | modify |
| `.gsd/wiki/Tutorial.md` + `docs/commands-deep.md` | TASK-003 | modify |
| — (wiki push) | TASK-004 | git operation |
| `CHANGELOG.md` | TASK-005 | modify |

### 5.3 Dependency Graph

```
TASK-001 (commands-quick) ──┐
TASK-002 (wiki reference) ──┼──► TASK-004 (wiki push) ──► TASK-005 (CHANGELOG)
TASK-003 (tutorial+deep)  ──┘
```

---

## 6. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Wiki push requires auth | Low | Medium | Use `gh` CLI or manual push |
| Flag already present in some surfaces | Medium | Low | Verify before adding; skip duplicates |
| Inconsistent descriptions across surfaces | Low | Medium | Use Python help text as source of truth |

---

## 7. Testing Strategy

### 7.1 Verification Commands
- TASK-001: `grep -c "check-gates\|what-if\|risk\|skip-tests\|from-issue\|target\|worker\|performance" docs/commands-quick.md` (expect count ≥ 8)
- TASK-002: `grep -c "check-gates\|what-if\|risk\|skip-tests\|from-issue\|target.*branch\|worker.*specific\|performance" .gsd/wiki/Command-Reference.md` (expect count ≥ 8 new matches)
- TASK-003: `grep -c "tone" .gsd/wiki/Tutorial.md` (expect > 5) AND `grep -c "check-gates\|from-issue\|performance" docs/commands-deep.md` (expect ≥ 3)
- TASK-004: Manual verification of wiki push
- TASK-005: `grep -q "documentation audit" CHANGELOG.md` (expect success)

---

## 8. Parallel Execution Notes

### 8.1 Safe Parallelization
- Level 1: TASK-001, TASK-002, TASK-003 all modify different files — fully parallel
- Level 2: TASK-004 depends on TASK-002 (wiki push needs wiki files updated)
- Level 3: TASK-005 depends on all prior tasks

### 8.2 Recommended Workers
- Minimum: 1 worker (sequential)
- Optimal: 3 workers (Level 1 fully parallel)
- Maximum: 3 workers

### 8.3 Estimated Duration
- Single worker: ~25 min
- With 3 workers: ~15 min
- Speedup: 1.7x

---

## 9. Approval

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Architecture | | | PENDING |
| Engineering | | | PENDING |
