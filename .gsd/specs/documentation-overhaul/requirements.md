# Requirements: Documentation Overhaul

**Status: APPROVED**
**Created**: 2026-02-04
**Feature**: documentation-overhaul

## Problem Statement

The GitHub wiki Command-Reference page returns 404 (never created). Documentation exists but is fragmented across README.md, docs/, and ARCHITECTURE.md. Users need:
1. Comprehensive command reference with every flag and example
2. Tutorial-focused README for new users
3. Full wiki with 10+ pages
4. Updated ARCHITECTURE.md reflecting current system

### Current State

| Document | Status | Issue |
|----------|--------|-------|
| README.md | Exists (844 lines) | Comprehensive but not tutorial-focused |
| docs/commands.md | Exists (~1000 lines) | Incomplete, not exhaustive |
| Wiki Command-Reference | 404 | Never created |
| ARCHITECTURE.md | Exists (36KB) | Needs audit against current code |
| docs/*.md | 6 files exist | May need updates |

### Expected Outcome

- Wiki is primary documentation with 10+ pages
- README becomes tutorial-focused with step-by-step guide
- All 26 commands documented exhaustively with every flag and example
- ARCHITECTURE.md audited and updated

## Functional Requirements

### FR-1: Wiki Population (Primary Documentation)

Create comprehensive GitHub wiki with these pages:

| Page | Content |
|------|---------|
| Home | Overview, quick start, links to other pages |
| Command-Reference | All commands grouped by workflow phase, alphabetical within groups |
| Configuration | .zerg/config.yaml, environment variables, tuning |
| Architecture | System design, module reference, execution model |
| Tutorial | Minerals-store walkthrough with all ZERG features |
| Plugins | Quality gates, lifecycle hooks, custom launchers |
| Security | Security rules integration, vulnerability reporting |
| Context-Engineering | Token optimization, command splitting, task context |
| Troubleshooting | Common issues, diagnostics, recovery |
| FAQ | Frequently asked questions |
| Contributing | Development setup, code style, PR process |

### FR-2: Exhaustive Command Documentation

For each of the 26 commands, document:

1. **Synopsis**: One-line description
2. **Usage**: Full command syntax
3. **Description**: Detailed explanation (2-3 paragraphs)
4. **Flags**: Table with every flag, type, default, description
5. **Examples**: 3-5 examples covering common use cases
6. **Related Commands**: Links to related commands
7. **Notes**: Edge cases, warnings, tips

Commands grouped by workflow phase, alphabetical within each group:

**Core Workflow**: /zerg:brainstorm, /zerg:design, /zerg:init, /zerg:plan, /zerg:rush

**Monitoring & Control**: /zerg:cleanup, /zerg:logs, /zerg:merge, /zerg:retry, /zerg:status, /zerg:stop

**Quality & Analysis**: /zerg:analyze, /zerg:build, /zerg:refactor, /zerg:review, /zerg:security, /zerg:test

**Utilities**: /zerg:create-command, /zerg:debug, /zerg:git, /zerg:plugins, /zerg:worker

**Documentation & AI**: /zerg:document, /zerg:estimate, /zerg:explain, /zerg:index, /zerg:select-tool

### FR-3: Tutorial-Focused README

Restructure README.md as a tutorial:

1. **Quick Overview** (what ZERG does, 1 paragraph)
2. **Installation** (step-by-step with prerequisites)
3. **Tutorial: Your First ZERG Project** (using minerals-store)
   - Step 1: `/zerg:init` — Initialize project
   - Step 2: `/zerg:brainstorm` — Discover requirements
   - Step 3: `/zerg:plan` — Capture requirements
   - Step 4: `/zerg:design` — Create architecture
   - Step 5: `/zerg:rush` — Execute in parallel
   - Step 6: `/zerg:status`, `/zerg:logs` — Monitor
   - Step 7: `/zerg:review`, `/zerg:test` — Quality checks
   - Step 8: `/zerg:git --action ship` — Ship it
4. **Command Quick Reference** (table linking to wiki)
5. **Configuration** (brief, links to wiki)
6. **Links to Full Documentation** (wiki, ARCHITECTURE.md)

### FR-4: ARCHITECTURE.md Audit

Audit and update ARCHITECTURE.md:

1. Verify all module references exist
2. Update diagrams for new features (worker intelligence, context engineering)
3. Add sections for: cross-cutting capabilities, resilience, diagnostics engine
4. Remove references to deprecated code
5. Cross-reference with current source files

### FR-5: Documentation Generation via /zerg:document --deep

Use `/zerg:document --deep` to generate initial documentation:

1. Run on each major subsystem
2. Review and enhance with examples
3. Ensure all slash commands use `/zerg:` format (never "Command-init")
4. Verify flag descriptions match source files

## Non-Functional Requirements

### NFR-1: Consistency

- All commands referenced as `/zerg:command` (with shortcut `/z:command`)
- Never use "Command-init" or "zerg-init" format
- Consistent flag formatting: `--flag VALUE` with type and default

### NFR-2: Completeness

- Every flag from every command file documented
- Every example is copy-pasteable and works
- No placeholder text ("TODO", "Coming soon")

### NFR-3: Discoverability

- Table of contents on every wiki page
- Cross-links between related commands
- Search-friendly headings

### NFR-4: Maintainability

- Wiki can be updated independently of releases
- docs/ mirrors wiki for offline access
- Source of truth is wiki, docs/ syncs from it

## Scope

### In Scope

1. Create all wiki pages (10+)
2. Restructure README.md as tutorial
3. Exhaustive command reference
4. ARCHITECTURE.md audit
5. Use `/zerg:document --deep` for generation

### Out of Scope

1. New features or commands
2. Code changes (documentation only)
3. Translations
4. Video tutorials

## Acceptance Criteria

1. **Wiki Complete**: All 10+ wiki pages exist and are accessible
2. **Commands Documented**: All 26 commands have exhaustive documentation with flags and examples
3. **Tutorial Works**: New user can follow README tutorial end-to-end
4. **Architecture Current**: ARCHITECTURE.md reflects current code (spot-checked against 5 key modules)
5. **Format Consistent**: All command references use `/zerg:` format

## Implementation Approach

### Phase 1: Audit (using /zerg:document --deep)

1. Run `/zerg:document --deep` on zerg/data/commands/
2. Run `/zerg:document --deep` on zerg/ (core modules)
3. Compare generated docs against current docs/
4. Identify gaps

### Phase 2: Wiki Creation

1. Create wiki Home page
2. Create Command-Reference (exhaustive)
3. Create remaining pages from generated content
4. Add cross-links

### Phase 3: README Restructure

1. Extract tutorial from current README
2. Restructure as step-by-step guide
3. Link to wiki for details

### Phase 4: Architecture Update

1. Audit ARCHITECTURE.md against current modules
2. Update diagrams
3. Add new sections

### Phase 5: Validation

1. Walk through tutorial as new user
2. Verify all wiki links work
3. Spot-check 5 commands for flag accuracy

## Open Questions

1. **Wiki edit permissions**: Can wiki be edited via GitHub API or must it be manual?
   - Recommendation: Use `gh` CLI if possible, manual if not

2. **Sync strategy**: How to keep docs/ in sync with wiki?
   - Recommendation: Wiki is source of truth, periodic manual sync to docs/

3. **Tutorial project location**: Should minerals-store be a separate repo?
   - Recommendation: Keep as tutorial in docs/, not a real repo

## Files to Create/Modify

| File | Operation |
|------|-----------|
| Wiki: Home | Create |
| Wiki: Command-Reference | Create |
| Wiki: Configuration | Create |
| Wiki: Architecture | Create |
| Wiki: Tutorial | Create |
| Wiki: Plugins | Create |
| Wiki: Security | Create |
| Wiki: Context-Engineering | Create |
| Wiki: Troubleshooting | Create |
| Wiki: FAQ | Create |
| Wiki: Contributing | Create |
| README.md | Modify (restructure) |
| ARCHITECTURE.md | Modify (audit/update) |
| docs/commands.md | Modify (sync from wiki) |
