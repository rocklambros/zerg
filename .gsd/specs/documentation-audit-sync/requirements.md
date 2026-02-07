# Requirements: Documentation Audit & Sync

**Status: APPROVED**
**Created**: 2026-02-06
**Feature**: documentation-audit-sync
**Trigger**: PR #166 shipped `--tone` flag but wiki/docs updates were incomplete

## Problem Statement

PR #166 claimed to "Update CHANGELOG, README, CLAUDE.md, wiki, and command docs" for the `--tone` flag, but the wiki Command-Reference received only a single table row (`+1` line). No explanation, no examples, no tone descriptions. This is symptomatic of a broader pattern: new flags ship without full documentation coverage across all documentation surfaces.

A complete audit reveals **multiple flags exist in the Python CLI code that are missing or underrepresented** across the documentation ecosystem.

## Audit Findings

### Critical Gaps (flags in code, missing from docs)

#### `/zerg:rush` — 4 flags missing from commands-quick.md AND wiki
| Flag | Code Location | Purpose |
|------|---------------|---------|
| `--check-gates` | `rush.py:43` | Pre-run quality gates during dry-run |
| `--what-if` | `rush.py:44` | Compare different worker counts and modes |
| `--risk` | `rush.py:45` | Show risk assessment for task graph |
| `--skip-tests` | `rush.py:47` | Skip test gates (lint-only mode) |

#### `/zerg:plan` — 1 flag missing from commands-quick.md AND wiki
| Flag | Code Location | Purpose |
|------|---------------|---------|
| `--from-issue` | `plan.py:24` | Import requirements from GitHub issue URL |

#### `/zerg:debug` — 2 flags missing from commands-quick.md
| Flag | Code Location | Purpose |
|------|---------------|---------|
| `--deep` | `debug.py:1263` | Run system-level diagnostics |
| `--env` | `debug.py:1265` | Run environment diagnostics |

#### `/zerg:merge` — 1 flag missing from commands-quick.md
| Flag | Code Location | Purpose |
|------|---------------|---------|
| `--target` | `merge_cmd.py:24` | Target branch (default: main) |

#### `/zerg:retry` — 1 flag missing from commands-quick.md
| Flag | Code Location | Purpose |
|------|---------------|---------|
| `--worker` | `retry.py:21` | Assign task to specific worker |

#### `/zerg:analyze` — 1 flag missing from commands-quick.md
| Flag | Code Location | Purpose |
|------|---------------|---------|
| `--performance` | `analyze.py:909` | Run comprehensive performance audit (140 factors) |

### Incomplete Documentation (flag listed but inadequately described)

#### Wiki Command-Reference.md: `/zerg:document --tone`
- **Current**: Single table row: `| --tone | educational|reference|tutorial | educational | Documentation tone — controls output style |`
- **Missing**: No explanation of what each tone does, no examples showing output differences, no mention of config default, no workflow diagram update

#### Wiki Command-Reference.md: `/zerg:git --admin`
- **Current**: Brief mention in ship section flags table
- **Missing**: No "Why Use It" explanation, no example showing when admin merge is needed

### Documentation Surface Coverage

| Doc Surface | Status | Issues |
|-------------|--------|--------|
| `docs/commands-quick.md` | 🟡 Mostly good | Missing 10 flags across 6 commands |
| `docs/commands-deep.md` | 🟡 Good for covered cmds | `--tone` well-documented; some commands have no deep section |
| `.gsd/wiki/Command-Reference.md` | 🔴 Incomplete | `--tone` is a stub; many new flags missing; no updated workflow diagrams |
| `.gsd/wiki/Tutorial.md` | 🟡 Brief mention | `--tone` mentioned in 3 lines at end; no hands-on example |
| `README.md` | ✅ Adequate | High-level; `--tone` and `--admin` mentioned |
| `CHANGELOG.md` | ✅ Up to date | New flags listed in [Unreleased] |
| `zerg/data/commands/document.md` | ✅ Complete | `--tone` fully documented with usage |

## Functional Requirements

### FR-1: Fix Missing Flags in commands-quick.md

Add all 10 missing flags to `docs/commands-quick.md` in the correct command sections:

- `/zerg:rush`: `--check-gates`, `--what-if`, `--risk`, `--skip-tests`
- `/zerg:plan`: `--from-issue`
- `/zerg:debug`: `--deep`, `--env`
- `/zerg:merge`: `--target`
- `/zerg:retry`: `--worker`
- `/zerg:analyze`: `--performance`

Each flag entry must include: flag name, type, default, and description matching the Python click option help text.

### FR-2: Fix Missing Flags in Wiki Command-Reference.md

Add all 10 missing flags to `.gsd/wiki/Command-Reference.md` in the correct command sections. Follow the existing format: flag tables with description.

For `/zerg:rush`, also update the "Using It" section to show examples of `--what-if` and `--risk`.

### FR-3: Expand `/zerg:document --tone` in Wiki

Replace the stub `--tone` row in wiki Command-Reference.md with a full explanation:

1. Add a "Tone Options" subsection (like the existing "Depth Levels" in the wiki)
2. Describe each tone value (`educational`, `reference`, `tutorial`) with 2-3 sentences
3. Add usage examples showing `--tone` with each value
4. Mention config default (`documentation.default_tone` in `.zerg/config.yaml`)
5. Update the workflow diagram to show tone selection step

### FR-4: Expand `/zerg:document --tone` in Wiki Tutorial

Update `.gsd/wiki/Tutorial.md` to include a hands-on example of `--tone` usage in the documentation section (currently only 3 lines at the end). Show before/after output for at least `educational` vs `reference` tones.

### FR-5: Sync commands-deep.md with All Current Flags

Verify and update the `/zerg:document` section in `docs/commands-deep.md` to ensure it matches the current codebase. Specifically:
- `--tone` section exists and is complete (already done in PR #166 — verify)
- All other command sections that have new flags are updated

### FR-6: Push Wiki Changes to GitHub

After all wiki files are updated, the changes must be pushed to the GitHub wiki repo so they appear at `https://github.com/rocklambros/zerg/wiki/`.

### FR-7: Update CHANGELOG.md

Add entry under `[Unreleased]` → Changed:
- `docs: comprehensive documentation audit — sync all commands and flags across wiki, command references, and tutorials`

## Non-Functional Requirements

### NFR-1: Consistency

All documentation surfaces must agree on:
- Flag names and types
- Default values
- Description wording (can vary in detail level but must not contradict)

### NFR-2: Educational Tone for Wiki

All wiki updates should follow the educational tone pattern: explain why before how, include diagrams where helpful.

### NFR-3: No Code Changes

This is a documentation-only feature. No Python code, no template changes, no test changes.

## Acceptance Criteria

1. All 10 missing flags appear in `docs/commands-quick.md`
2. All 10 missing flags appear in `.gsd/wiki/Command-Reference.md`
3. `/zerg:document --tone` has full explanation in wiki (not just a table row)
4. `/zerg:document --tone` has hands-on example in wiki Tutorial
5. `docs/commands-deep.md` matches current codebase for all commands
6. Wiki changes are pushed to GitHub wiki
7. `CHANGELOG.md` updated
8. No contradictions between any documentation surface

## Scope Boundaries

### In Scope
- `docs/commands-quick.md` flag additions
- `.gsd/wiki/Command-Reference.md` flag additions + tone expansion
- `.gsd/wiki/Tutorial.md` tone example
- `docs/commands-deep.md` verification/fixes
- `CHANGELOG.md` update
- Wiki push to GitHub

### Out of Scope
- Python code changes
- New documentation pages
- Template changes
- Test changes
- README.md changes (already adequate)
- CLAUDE.md changes (already adequate)

## Files to Modify

| File | Change |
|------|--------|
| `docs/commands-quick.md` | Add 10 missing flags to 6 command sections |
| `.gsd/wiki/Command-Reference.md` | Add 10 missing flags + expand `--tone` section |
| `.gsd/wiki/Tutorial.md` | Expand `--tone` hands-on example |
| `docs/commands-deep.md` | Verify/fix flag coverage for all commands |
| `CHANGELOG.md` | Add [Unreleased] entry |

## Documentation Impact Analysis

This IS the documentation update feature. No additional documentation surfaces needed.

## Dependencies

- Current codebase on `main` branch (source of truth for flags)
- GitHub wiki push access

## Open Questions

None.
