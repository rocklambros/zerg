# Requirements: Documentation Tone Overhaul

**Status: APPROVED**
**Created**: 2026-02-04
**Feature**: documentation-tone-overhaul

## Problem Statement

The recent documentation overhaul (PR #128) created comprehensive, exhaustive documentation but lost the educational, layman-friendly tone of the original wiki. The new docs are reference-style (dense tables, bullet lists, terse descriptions) rather than narrative-style (concept explanations, simulated dialogues, ASCII diagrams with context).

### Current State

| Document | Issue |
|----------|-------|
| README.md | Tutorial section is step-list, not narrative |
| ARCHITECTURE.md | Has diagrams but lacks educational prose |
| Wiki (12 pages) | Reference-style, not concept-first |
| docs/commands.md | Flag tables without explanations |
| Tutorial.md | Numbered steps without "why" |

### Desired State

All documentation follows the "concept-first, command-second" pattern:
1. Explain the concept in plain language
2. Provide narrative context (why this matters)
3. Show ASCII diagram with explanatory text
4. Then show the command/code

## Functional Requirements

### FR-1: Educational Tone Standard

All documentation must follow this structure for each concept:

```
1. CONCEPT: Plain-language explanation (1-2 paragraphs)
   - What is it?
   - Why does it exist?
   - What problem does it solve?

2. NARRATIVE: Context and mental model
   - How does it fit into the bigger picture?
   - What would happen without it?
   - Real-world analogy if helpful

3. DIAGRAM: ASCII visualization with annotations
   - Show relationships visually
   - Label important parts
   - Include explanatory caption

4. COMMAND: The actual syntax/usage
   - Command examples
   - Expected output
   - Common variations
```

### FR-2: Target Audience

Write for someone who:
- Is new to AI coding assistants
- Knows basic programming but not distributed systems
- Understands git basics (commit, branch, push) but not worktrees
- Needs concepts explained before implementation
- Benefits from analogies and "why" explanations

**Avoid assuming knowledge of:**
- Concurrency patterns
- Distributed systems
- Container orchestration
- Advanced git (worktrees, cherry-pick, rebase)

### FR-3: Simulated Dialogues

Tutorials must include simulated dialogues for planning/discovery phases:

```
ZERG: What problem does the minerals store solve for users?
YOU:  Users need to browse and purchase mineral products through a REST API.

ZERG: What are the core entities and their relationships?
YOU:  Products, Cart, Orders. A cart becomes an order at checkout.
```

Execution phases (rush, merge, status) show real command output instead.

### FR-4: Command Reference Split

Create two versions of command documentation:

| Document | Purpose | Content |
|----------|---------|---------|
| `docs/commands-quick.md` | Quick lookup | Flag tables, terse descriptions |
| `docs/commands-deep.md` | Learning | Concept explanations, use cases, examples |
| Wiki Command-Reference | Learning | Same as commands-deep.md |

### FR-5: Scope of Updates

All documentation must be updated:

| File | Operation | Notes |
|------|-----------|-------|
| README.md | Rewrite tutorial section | Add narrative depth, keep "Why I Built This" |
| ARCHITECTURE.md | Add educational prose | Explain concepts before diagrams |
| .gsd/wiki/Home.md | Rewrite | Concept-first introduction |
| .gsd/wiki/Command-Reference.md | Rewrite | Deep educational version |
| .gsd/wiki/Configuration.md | Rewrite | Explain why each setting matters |
| .gsd/wiki/Architecture.md | Rewrite | Narrative system explanation |
| .gsd/wiki/Tutorial.md | Rewrite | Dialogues + narrative + real output |
| .gsd/wiki/Plugins.md | Rewrite | Concept-first plugin explanation |
| .gsd/wiki/Security.md | Rewrite | Why security matters, then how |
| .gsd/wiki/Context-Engineering.md | Rewrite | Explain token economics first |
| .gsd/wiki/Troubleshooting.md | Rewrite | Problem → why it happens → fix |
| .gsd/wiki/FAQ.md | Rewrite | Deeper answers with context |
| .gsd/wiki/Contributing.md | Rewrite | Explain the "why" of conventions |
| .gsd/wiki/Getting-Started.md | Restore/Update | Original had best tone |
| docs/commands.md | Split | Quick + Deep versions |

### FR-6: Workflow

1. Run `/zerg:document --deep` on each subsystem to generate base content
2. Rewrite output following FR-1 educational tone standard
3. Add simulated dialogues where appropriate (FR-3)
4. Verify concept-first structure in all sections

## Non-Functional Requirements

### NFR-1: Explanation Depth

Every concept must be explained at "deep" level:
- Full concept explanation (what, why, how)
- ASCII diagram with annotations
- Rules/constraints stated explicitly
- Rationale for why rules exist

### NFR-2: Consistency

- All pages follow the same educational structure
- Terminology consistent across all documents
- Cross-references use same link format
- All commands use `/zerg:` format

### NFR-3: Accessibility

- No jargon without explanation
- Acronyms defined on first use
- Complex concepts have analogies
- Progressive disclosure (simple first, details later)

## Acceptance Criteria

1. **Tone Test**: A developer new to AI assistants can understand any page without external references
2. **Structure Test**: Every major concept has: explanation → narrative → diagram → command
3. **Dialogue Test**: Planning tutorials have simulated ZERG/YOU dialogues
4. **Split Test**: Command docs exist in both quick-reference and deep-dive versions
5. **Coverage Test**: All 15+ documents updated with educational tone

## Implementation Approach

### Phase 1: Generate Base Content
- Run `/zerg:document --deep` on each module
- Collect output as raw material

### Phase 2: Rewrite Wiki Pages
- Start with Getting-Started.md (restore original tone)
- Apply pattern to remaining wiki pages
- Prioritize Tutorial.md and Command-Reference.md

### Phase 3: Update Core Docs
- README.md tutorial section
- ARCHITECTURE.md educational prose
- docs/commands.md split into quick/deep

### Phase 4: Validation
- Review each page against FR-1 structure
- Test with fresh eyes (would a beginner understand?)
- Verify cross-links work

## Open Questions

None — all questions resolved via Socratic discovery.

## Future Enhancement

GitHub Issue to be created for `/zerg:document --tone educational` flag that produces this style automatically.
