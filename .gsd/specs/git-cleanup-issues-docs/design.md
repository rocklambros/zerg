# Technical Design: git-cleanup-issues-docs

## Metadata
- **Feature**: git-cleanup-issues-docs
- **Status**: DRAFT
- **Created**: 2026-02-02
- **Author**: /zerg:design

---

## 1. Overview

### 1.1 Summary
Add two new actions (`cleanup` and `issue`) to `/zerg:git`, rename all wiki files from `Command-*.md` to `zerg-*.md` with full cross-reference updates, and audit all documentation for stale flag references from PR #83's flag inversions.

### 1.2 Goals
- Repository hygiene via `/zerg:git --action cleanup` (branches, refs, worktrees, Docker)
- AI-optimized issue creation via `/zerg:git --action issue` with strict template
- Consistent `/zerg:` prefix naming throughout all documentation
- All deprecated flags (`--uc`, `--compact`) replaced with current flags (`--no-compact`, `--no-loop`, `--iterations`)

### 1.3 Non-Goals
- Python runtime implementation (these are Claude Code slash commands — .md files ARE the implementation)
- Removing deprecated flags from cli.py (tracked in issue #84)
- Fixing CI test failures (tracked in issue #85)

---

## 2. Architecture

### 2.1 High-Level Design

This feature is entirely documentation/prompt engineering — no Python code changes except `sidebar.py`. The "architecture" is the command file structure:

```
zerg/data/commands/git.md          ← main entry (actions table + flags)
zerg/data/commands/git.core.md     ← quick reference (~30%)
zerg/data/commands/git.details.md  ← deep reference (~70%, action sections)

.zerg/wiki/zerg-*.md               ← renamed from Command-*.md (27 files)
.zerg/wiki/_Sidebar.md             ← navigation with /zerg: prefix
zerg/doc_engine/sidebar.py         ← hardcoded page name references
```

### 2.2 Component Breakdown

| Component | Responsibility | Files |
|-----------|---------------|-------|
| Git command files | Define cleanup + issue action behavior | git.md, git.core.md, git.details.md |
| Wiki command pages | Per-command reference docs | 27 zerg-*.md files |
| Wiki navigation | Sidebar + cross-references | _Sidebar.md, all wiki pages |
| Doc engine | Generate sidebar from page names | sidebar.py |
| Project docs | README, CLAUDE.md, commands.md, CHANGELOG | 4 files |

---

## 3. Key Decisions

### 3.1 Wiki File Naming Convention

**Context**: Wiki files are `Command-init.md` but user wants `/zerg:` prefix everywhere.

**Decision**: Rename to `zerg-init.md` (filesystem-safe, no colons).

**Rationale**: Colons are illegal in filenames on Windows/macOS. `zerg-` prefix is clean and maps clearly to `/zerg:init`. Display text in sidebar uses the full `/zerg:init` form.

### 3.2 Issue Template Strictness

**Context**: Issues need maximum detail for AI coding assistants.

**Decision**: Strict template with 8 mandatory sections: Problem Statement, Root Cause Analysis, Affected Files (with line numbers), Reproduction Steps, Proposed Solution (with code sketches), Acceptance Criteria (with verification commands), Dependencies, Context for AI Assistants.

**Rationale**: Removes all ambiguity. An AI assistant reading the issue has everything needed to implement a fix without guessing.

### 3.3 Cleanup Docker Auto-Detection

**Context**: Should Docker cleanup require an explicit flag?

**Decision**: Auto-detect ZERG containers. `--no-docker` flag to skip.

**Rationale**: If ZERG containers exist, they should be cleaned. Users who want to keep them opt out explicitly.

---

## 4. Implementation Plan

### 4.1 Phase Summary

| Phase | Level | Tasks | Parallel |
|-------|-------|-------|----------|
| Content | L0 | 5 | Yes (all 5) |
| Rename | L1 | 2 | Yes |
| Cross-refs | L2 | 2 | Yes |
| Finalize | L3 | 2 | Sequential |

### 4.2 File Ownership

| File(s) | Task | Op |
|---------|------|----|
| git.md, git.core.md, git.details.md | T-001 | modify |
| .zerg/wiki/Command-git.md | T-002 | modify |
| .zerg/wiki/Command-Reference.md, Home.md | T-003 | modify |
| README.md, docs/commands.md | T-004 | modify |
| CLAUDE.md | T-005 | modify |
| 27 .zerg/wiki/Command-*.md (rename) | T-006 | rename |
| zerg/doc_engine/sidebar.py | T-007 | modify |
| .zerg/wiki/_Sidebar.md | T-008 | modify |
| All .zerg/wiki/*.md (cross-refs) | T-009 | modify |
| CHANGELOG.md | T-010 | modify |

### 4.3 Dependency Graph

```
L0: T-001 + T-002 + T-003 + T-004 + T-005    [parallel, no deps]
L1: T-006 + T-007                               [parallel, depends on L0]
L2: T-008 + T-009                               [parallel, depends on L1]
L3: T-010 → T-011                               [sequential, depends on L2]
```

---

## 5. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Broken wiki links after rename | Medium | High | grep -rl 'Command-' validation |
| Missing cross-reference updates | Medium | Medium | Exhaustive grep + manual audit |
| sidebar.py breaks after rename | Low | High | Unit test for sidebar generation |

---

## 6. Parallel Execution Notes

### 6.1 Recommended Workers
- Optimal: 5 workers (matches L0 width)
- Maximum useful: 5 (L0 has 5 parallel tasks, L1-L3 have ≤2)

### 6.2 Estimated Duration
- Sequential: ~86 min
- With 5 workers: ~43 min
- Speedup: ~2x

---

## 9. Approval

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Architecture | | | PENDING |
| Engineering | | | PENDING |
