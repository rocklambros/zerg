# Requirements: git-cleanup-issues-docs

## Metadata
- **Feature**: git-cleanup-issues-docs
- **Status**: REVIEW
- **Created**: 2026-02-02
- **Author**: /zerg:plan --socratic

---

## 1. Problem Statement

Three gaps in the ZERG toolchain:

1. **No git cleanup action.** `/zerg:git` has 12 actions but no way to prune merged branches, stale remote refs, orphaned worktrees, stashes, or ZERG Docker containers. Users must run ad-hoc git commands.

2. **No git issue action.** Issues are created manually or via `/zerg:brainstorm`. There's no way to create a single, maximally-detailed GitHub issue from a description or from auto-scanning code quality signals. Existing issues often lack enough detail for an AI coding assistant to resolve unambiguously.

3. **Wiki naming inconsistency.** The user has asked MULTIPLE times to fix command naming across documentation. The `_Sidebar.md` displays plain names (`init`, `plan`) instead of `/zerg:init`, `/zerg:plan`. Wiki files are named `Command-init.md` instead of `zerg-init.md`. The Command-Reference Global CLI Flags table still references deprecated `--uc`/`--compact` instead of `--no-compact` (ON by default). This must be fixed permanently.

---

## 2. Functional Requirements

### FR-1: `/zerg:git --action cleanup`

A new action in the git command that performs comprehensive repository hygiene.

**Behavior:**
- Delete local branches already merged into base (default: `main`)
- Prune stale remote tracking refs (`git remote prune origin`)
- Remove orphaned git worktrees (`git worktree prune` + remove `.zerg-worktrees/` orphans)
- Clear stashes (with `--include-stashes` flag, off by default)
- Auto-detect and remove stopped ZERG Docker containers (`factory-worker-*`)
- Auto-detect and remove dangling ZERG Docker images
- `--no-docker` flag to skip Docker cleanup
- `--dry-run` flag to preview what would be deleted without deleting
- `--base BRANCH` to specify base branch (default: `main`)
- Print summary table of what was cleaned

**Output format:**
```
Git Cleanup Summary:
  Local branches deleted:    3  (feature/auth, feature/old, fix/typo)
  Remote refs pruned:        2  (origin/feature/auth, origin/fix/typo)
  Worktrees removed:         1  (.zerg-worktrees/old-feature/worker-0)
  Docker containers removed: 2  (factory-worker-0, factory-worker-1)
  Docker images removed:     0
  Stashes cleared:           0  (use --include-stashes to clear)
```

### FR-2: `/zerg:git --action issue`

A new action that creates maximally-detailed GitHub issues optimized for AI coding assistants.

**Two modes:**

#### Mode A: From description (`--title` + description text)
```
/zerg:git --action issue --title "Fix auth timeout" "Users report 504 errors after 30s on login"
```
- Takes a title and description from the user
- Enriches with codebase analysis: finds relevant files, traces code paths, identifies root cause candidates
- Produces a structured issue body (see FR-2.1 template)
- Creates the issue via `gh issue create`

#### Mode B: From scan (`--scan`, default behavior when no title given)
```
/zerg:git --action issue --scan
/zerg:git --action issue              # --scan is default
```
- Scans codebase for problems across ALL of:
  - Test failures (parse most recent pytest/jest output)
  - TODO/FIXME/HACK comments in source code
  - Lint/type errors (`ruff`, `mypy`, `eslint`, `tsc`)
  - Security findings (from ZERG security rules)
  - Orphaned modules (no production callers, per `validate_commands`)
  - Stale dependencies
  - CI pipeline results (parse most recent `gh run` output)
- Groups related findings into logical issues
- Creates one issue per distinct problem
- `--dry-run` to preview issues without creating
- `--limit N` to cap number of issues created (default: 10)
- `--label LABEL` to add labels to all created issues
- `--priority P0|P1|P2` to filter by severity

#### FR-2.1: Issue Body Template (Strict)

Every issue MUST follow this template:

```markdown
## Problem Statement
{2-3 sentences describing the problem. What's broken/missing and who is affected.}

## Root Cause Analysis
{Why this problem exists. Technical explanation with evidence.}

## Affected Files
{Exhaustive list of files involved, with line numbers where relevant.}

| File | Lines | Role |
|------|-------|------|
| `path/to/file.py` | 45-67 | Contains the buggy function |
| `path/to/other.py` | 12 | Caller that triggers the issue |

## Reproduction Steps
1. {Step 1}
2. {Step 2}
3. {Observe: expected vs actual}

## Proposed Solution
{Concrete implementation plan. Not vague — specific changes to specific files.}

### Changes Required
- **`path/to/file.py`**: {What to change and why}
- **`path/to/other.py`**: {What to change and why}

### Code Sketch
```python
# Before (problematic)
def buggy_function():
    ...

# After (fixed)
def fixed_function():
    ...
```

## Acceptance Criteria
- [ ] {Criterion 1 — with verification command}
  ```bash
  pytest tests/unit/test_auth.py -v  # must pass
  ```
- [ ] {Criterion 2}
- [ ] {Criterion 3}

## Dependencies
- Blocked by: {issue numbers or "none"}
- Blocks: {issue numbers or "none"}
- Related: {issue numbers}

## Context for AI Assistants
- **Codebase patterns**: {Relevant patterns this fix should follow}
- **Test expectations**: {What tests exist, what new tests are needed}
- **Security considerations**: {Any OWASP/security implications}
```

### FR-3: Wiki File Renaming

Rename ALL wiki command files from `Command-{name}.md` to `zerg-{name}.md` and update ALL cross-references.

**Scope:**
- Rename 25 files: `Command-init.md` → `zerg-init.md`, etc.
- Update `_Sidebar.md`: `[[init|Command-init]]` → `[[/zerg:init|zerg-init]]`
- Update `Command-Reference.md` → `zerg-Command-Reference.md` (or keep as-is if it's the index)
- Update ALL `[[wiki links]]` across ALL wiki pages
- Update `docs/commands.md` wiki links
- Update `README.md` wiki references
- Validate: zero broken `[[links]]` after rename

### FR-4: Global CLI Flags Documentation Update

Update the deprecated flag references across ALL documentation to reflect PR #83 changes:

**Changes:**
- `--uc` / `--compact` → `--no-compact` (compact is ON by default)
- Add `--no-loop` (loops are ON by default)
- Add `--iterations N` (override loop iteration count)
- Remove/update any "coming soon" or "planned" capability references — all 8 capabilities are now wired

**Files to update:**
- `.zerg/wiki/Command-Reference.md` (or renamed equivalent) — Global CLI Flags table
- `.zerg/wiki/Home.md` — Cross-Cutting Capabilities table
- All 25 `.zerg/wiki/Command-*.md` (or renamed equivalents) — audit for stale flag refs
- `docs/commands.md` — already partially updated in PR #83, verify completeness
- `README.md` — verify Cross-Cutting Capabilities section
- `CLAUDE.md` — verify capabilities table

### FR-5: Git Command File Updates

Update the git command files (git.md, git.core.md, git.details.md) to include cleanup and issue actions:

- Add `cleanup` and `issue` to the actions table
- Add flags: `--scan`, `--title`, `--dry-run` (for both), `--no-docker`, `--include-stashes`, `--limit`, `--label`, `--priority`
- Add usage examples for both new actions
- Maintain command splitting consistency (core ~30%, details ~70%)

### FR-6: Full Documentation Consistency Audit

After all changes, verify:
- Every `/zerg:*` command is documented in: README, CLAUDE.md, docs/commands.md, wiki index, wiki sidebar
- All 26 commands listed with correct `/zerg:` prefix everywhere
- All 14 git actions (12 existing + cleanup + issue) documented
- All global CLI flags accurate (reflecting PR #83 inversions)
- No stale references to `Command-{name}` format anywhere
- CHANGELOG.md updated under [Unreleased]

---

## 3. Non-Functional Requirements

- **NFR-1**: Zero broken wiki links after rename
- **NFR-2**: `python -m zerg.validate_commands` passes after changes
- **NFR-3**: All existing tests pass (7218+)
- **NFR-4**: New actions have Task ecosystem integration (TaskCreate/TaskUpdate)
- **NFR-5**: Changes committed with conventional commit messages

---

## 4. Scope Boundaries

**In scope:**
- cleanup and issue actions in /zerg:git
- Wiki file renaming (25 files)
- Sidebar, Command-Reference, Home page link updates
- Global CLI flags documentation update
- Full documentation consistency audit
- CHANGELOG update

**Out of scope:**
- Implementing the actual git cleanup/issue Python runtime (these are Claude Code slash commands, not Python CLI — the command .md files ARE the implementation)
- Removing deprecated flags from cli.py (tracked in issue #84)
- Fixing pre-existing CI test failures (tracked in issue #85)

---

## 5. Acceptance Criteria

- [ ] `/zerg:git --action cleanup` works: prunes branches, refs, worktrees, Docker
- [ ] `/zerg:git --action issue --scan` auto-detects and creates detailed issues
- [ ] `/zerg:git --action issue --title "X" "description"` creates enriched issue
- [ ] All wiki files renamed from `Command-*.md` to `zerg-*.md`
- [ ] `_Sidebar.md` shows `/zerg:` prefix for all commands
- [ ] `grep -rl 'Command-' .zerg/wiki/` returns only non-command files (no stale refs)
- [ ] Global CLI Flags table updated with `--no-compact`, `--no-loop`, `--iterations`
- [ ] All 14 git actions documented in git.md, git.core.md, git.details.md
- [ ] `python -m zerg.validate_commands` passes
- [ ] All existing tests pass

---

## 6. Open Questions

None — all clarified via Socratic rounds.
