# Technical Design: documentation-tone-overhaul

## Metadata
- **Feature**: documentation-tone-overhaul
- **Status**: DRAFT
- **Created**: 2026-02-04
- **Author**: ZERG Design Mode

---

## 1. Overview

### 1.1 Summary

This feature rewrites all ZERG documentation from reference-style (tables, bullet lists, terse descriptions) to educational-style (concept-first explanations, narrative context, ASCII diagrams with annotations, simulated dialogues). The rewrite follows FR-1's structure: CONCEPT → NARRATIVE → DIAGRAM → COMMAND.

### 1.2 Goals

- Transform 15+ documentation files to educational tone
- Create dual command reference (quick-lookup + deep-dive)
- Add simulated dialogues for planning/discovery phases
- Ensure all pages are accessible to AI assistant newcomers

### 1.3 Non-Goals

- Adding new commands or features
- Changing command behavior
- Restructuring the wiki hierarchy
- Creating video or interactive tutorials

---

## 2. Architecture

### 2.1 High-Level Design

This is a documentation rewrite, not code architecture. The "architecture" is the content transformation pattern.

```
┌─────────────────────────────────────────────────────────────────┐
│                    TRANSFORMATION PIPELINE                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  CURRENT STATE                    TARGET STATE                   │
│  ─────────────                    ────────────                   │
│  ┌─────────────────┐             ┌─────────────────┐            │
│  │ Reference-style │             │ Educational     │            │
│  │ - Flag tables   │    ═══►     │ - Concept first │            │
│  │ - Step lists    │             │ - Narrative why │            │
│  │ - Terse bullets │             │ - ASCII + prose │            │
│  │ - "What" focus  │             │ - Dialogues     │            │
│  └─────────────────┘             └─────────────────┘            │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│                    FILE OPERATIONS                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  MODIFY (in-place rewrite):                                     │
│  - README.md (tutorial section)                                 │
│  - ARCHITECTURE.md (add educational prose)                      │
│  - .gsd/wiki/*.md (all 11 wiki pages)                          │
│                                                                  │
│  CREATE (new files):                                            │
│  - docs/commands-quick.md (terse reference)                     │
│  - docs/commands-deep.md (educational deep-dive)                │
│                                                                  │
│  DELETE:                                                         │
│  - docs/commands.md (replaced by split versions)                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Component Breakdown

| Component | Responsibility | Files |
|-----------|---------------|-------|
| Wiki Core | Main user-facing wiki pages | Home.md, Tutorial.md, Getting-Started.md |
| Wiki Reference | Technical reference pages | Command-Reference.md, Configuration.md |
| Wiki Advanced | Deep-dive topics | Architecture.md, Context-Engineering.md, Plugins.md |
| Wiki Support | Help and onboarding | FAQ.md, Troubleshooting.md, Contributing.md, Security.md |
| Core Docs | README and architecture | README.md, ARCHITECTURE.md |
| Command Docs | Split command reference | commands-quick.md, commands-deep.md |

### 2.3 Content Transformation Pattern

Each major concept must follow this structure (FR-1):

```markdown
## {Concept Name}

### What Is It?
{1-2 paragraphs explaining the concept in plain language}

### Why Does It Exist?
{Narrative context - what problem it solves, what would happen without it}
{Real-world analogy if helpful}

### How It Works
{ASCII diagram with annotations}

┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Step 1    │────▶│   Step 2    │────▶│   Result    │
│  {action}   │     │  {action}   │     │  {outcome}  │
└─────────────┘     └─────────────┘     └─────────────┘
           │                                    │
           └── {explanation of transition} ─────┘

### Using It
{Command syntax and examples}
{Expected output}
{Common variations}
```

### 2.4 Simulated Dialogue Pattern (FR-3)

Planning/discovery phases include dialogues:

```markdown
### Discovery Dialogue

```
ZERG: What problem does this feature solve for users?
YOU:  Users need to browse mineral products and add them to a cart.

ZERG: What are the core entities and their relationships?
YOU:  Products have prices and quantities. Carts hold product references.

ZERG: What happens at checkout?
YOU:  Cart becomes an order with shipping info and payment confirmation.
```

{Explanation of what ZERG learned from this dialogue}
```

---

## 3. Detailed Design

### 3.1 Wiki Page Transformations

#### Home.md (Entry Point)
- **Current**: Quick start bullets, installation table, page list
- **Target**: Welcome narrative explaining ZERG's purpose, guided navigation based on user goals, concept overview before commands

#### Tutorial.md (Learning Path)
- **Current**: Numbered steps with "What happens" bullets
- **Target**: Narrative walkthrough with simulated dialogues for planning phases, real command output for execution phases, "why" explanations at each step

#### Command-Reference.md (Wiki)
- **Current**: 1800+ lines of flag tables and brief descriptions
- **Target**: Deep educational version - each command gets concept/narrative/diagram/command treatment

#### Configuration.md
- **Current**: YAML tables with type/default/description
- **Target**: Each setting explained with "why you'd change this", real-world scenarios, default rationale

#### Architecture.md
- **Current**: Component diagrams with brief descriptions
- **Target**: Educational prose explaining each component's purpose, data flow narratives, decision rationale

#### Context-Engineering.md
- **Current**: Technical description of token optimization
- **Target**: "Token economics 101" introduction, why context matters, visual token budget diagrams

#### Plugins.md
- **Current**: Hook definitions and examples
- **Target**: "Why extend ZERG" narrative, use case stories, step-by-step plugin creation guide

#### Security.md
- **Current**: Security feature descriptions
- **Target**: "Why security matters in AI assistants", threat model explanation, then how ZERG addresses each

#### Troubleshooting.md
- **Current**: Problem → Solution tables
- **Target**: Problem → Why It Happens → How To Fix pattern with context

#### FAQ.md
- **Current**: Brief Q&A format
- **Target**: Deeper answers with context and cross-references

#### Contributing.md
- **Current**: Contribution guidelines
- **Target**: Explain "why" behind each convention, mental model for contributors

### 3.2 Command Docs Split (FR-4)

#### docs/commands-quick.md
```markdown
# Quick Reference

Fast lookup for experienced users. For explanations, see [commands-deep.md](commands-deep.md).

## /zerg:rush
Flags: `--workers=N`, `--mode container|task`, `--resume`
Start parallel workers. Requires approved design.
```

#### docs/commands-deep.md
```markdown
# Command Reference (Deep Dive)

## /zerg:rush

### What Is It?
The rush command is ZERG's execution engine...

### Why Use It?
When you have an approved design, rush spawns...

### How It Works
{ASCII diagram of worker spawning}

### Using It
{Examples with expected output}
```

### 3.3 README Tutorial Section

Transform from step-list to narrative:

```markdown
## Tutorial: Your First ZERG Project

Imagine you're building a Starcraft 2 themed store. You could write each file
one at a time, but that takes hours. ZERG lets you describe what you want,
then spawns a swarm of workers to build it in parallel.

Let's walk through how this works...

### Starting the Conversation

Before ZERG can help, it needs to understand your project. The `/zerg:plan`
command starts a discovery conversation:

```
ZERG: What problem does the minerals store solve for users?
YOU:  Users need to browse and purchase mineral products through a REST API.
```

{Continue with narrative explanation of each phase}
```

---

## 4. Key Decisions

### 4.1 Keep Both Command Reference Versions

**Context**: Requirements specify splitting docs/commands.md into quick and deep versions.

**Options Considered**:
1. Deep version only: Comprehensive but slow to scan
2. Quick version only: Fast lookup but no learning
3. Both versions: More maintenance but serves both needs

**Decision**: Create both versions (FR-4)

**Rationale**: Different users have different needs. Newcomers need deep explanations. Experienced users need quick lookup.

**Consequences**: 2 files to maintain. Wiki Command-Reference.md becomes the deep version.

### 4.2 Simulated Dialogues Only for Discovery Phases

**Context**: FR-3 requires simulated dialogues in tutorials.

**Options Considered**:
1. Dialogues everywhere
2. Dialogues only in discovery (brainstorm, plan, design)
3. No dialogues, just command output

**Decision**: Dialogues for discovery phases, real output for execution phases

**Rationale**: Discovery is conversational (ZERG asks, you answer). Execution is deterministic (ZERG runs commands, shows output). Mixing them confuses the mental model.

**Consequences**: Tutorial has hybrid format. Clear distinction helps readers understand ZERG's modes.

### 4.3 Rewrite In-Place vs. New Files

**Context**: 15+ files need transformation.

**Options Considered**:
1. Rewrite in-place (git tracks history)
2. Create new versioned files (e.g., Tutorial-v2.md)
3. Archive old versions in docs/archive/

**Decision**: Rewrite in-place

**Rationale**: Wiki pages are user-facing. Old versions add confusion. Git history preserves originals.

**Consequences**: No old files to delete. Clear upgrade path.

---

## 5. Implementation Plan

### 5.1 Phase Summary

| Phase | Tasks | Parallel | Est. Time |
|-------|-------|----------|-----------|
| Foundation | 2 | Yes | 30 min |
| Core Wiki | 4 | Yes | 60 min |
| Reference | 3 | Yes | 45 min |
| Advanced | 3 | Yes | 45 min |
| Support | 4 | Yes | 60 min |
| Finalization | 2 | Yes | 30 min |

### 5.2 File Ownership

| File | Task ID | Operation |
|------|---------|-----------|
| docs/commands-quick.md | TASK-001 | create |
| docs/commands-deep.md | TASK-002 | create |
| .gsd/wiki/Home.md | TASK-003 | modify |
| .gsd/wiki/Tutorial.md | TASK-004 | modify |
| README.md (tutorial section) | TASK-005 | modify |
| ARCHITECTURE.md | TASK-006 | modify |
| .gsd/wiki/Command-Reference.md | TASK-007 | modify |
| .gsd/wiki/Configuration.md | TASK-008 | modify |
| .gsd/wiki/Architecture.md | TASK-009 | modify |
| .gsd/wiki/Context-Engineering.md | TASK-010 | modify |
| .gsd/wiki/Plugins.md | TASK-011 | modify |
| .gsd/wiki/Security.md | TASK-012 | modify |
| .gsd/wiki/Troubleshooting.md | TASK-013 | modify |
| .gsd/wiki/FAQ.md | TASK-014 | modify |
| .gsd/wiki/Contributing.md | TASK-015 | modify |
| docs/commands.md | TASK-016 | delete |
| .gsd/wiki/_Sidebar.md | TASK-017 | modify |

### 5.3 Dependency Graph

```
Level 1 (Foundation - No dependencies):
  TASK-001: Create commands-quick.md
  TASK-002: Create commands-deep.md

Level 2 (Core Wiki - No dependencies):
  TASK-003: Rewrite Home.md
  TASK-004: Rewrite Tutorial.md
  TASK-005: Rewrite README tutorial
  TASK-006: Rewrite ARCHITECTURE.md

Level 3 (Reference - Depends on commands-deep for consistency):
  TASK-007: Rewrite Command-Reference.md (wiki)
  TASK-008: Rewrite Configuration.md
  TASK-009: Rewrite Architecture.md (wiki)

Level 4 (Advanced):
  TASK-010: Rewrite Context-Engineering.md
  TASK-011: Rewrite Plugins.md
  TASK-012: Rewrite Security.md

Level 5 (Support):
  TASK-013: Rewrite Troubleshooting.md
  TASK-014: Rewrite FAQ.md
  TASK-015: Rewrite Contributing.md

Level 6 (Finalization - Depends on all others):
  TASK-016: Delete docs/commands.md
  TASK-017: Update _Sidebar.md with new structure
```

---

## 6. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Tone inconsistency across pages | Medium | Medium | Use FR-1 template strictly, review at merge |
| Missing concepts in rewrites | Low | High | Verify all original content preserved in new format |
| Over-explaining simple concepts | Medium | Low | Target audience is "new to AI assistants", not "never programmed" |
| Cross-reference breakage | Low | Medium | Check all internal links after rewrites |

---

## 7. Testing Strategy

### 7.1 Content Verification

Each rewritten file must pass:
1. **Structure check**: Has CONCEPT → NARRATIVE → DIAGRAM → COMMAND for each major topic
2. **Dialogue check**: Planning tutorials have ZERG/YOU dialogues
3. **Link check**: All internal links resolve
4. **Jargon check**: No unexplained technical terms

### 7.2 Verification Commands

```bash
# Structure check (manual review)
# Look for pattern: "What Is", "Why", "How", then code blocks

# Link check
grep -r "\[.*\](.*\.md)" .gsd/wiki/ docs/ README.md ARCHITECTURE.md | \
  while read line; do
    link=$(echo "$line" | grep -oP '\]\(\K[^)]+')
    # Verify link target exists
  done

# Jargon check (scan for unexplained terms)
# Run readability analysis or manual review
```

---

## 8. Parallel Execution Notes

### 8.1 Safe Parallelization

- Level 1-2 tasks have no dependencies, fully parallel
- Level 3+ can parallelize within level
- Each task owns exactly one file (no conflicts)
- No two tasks modify the same file

### 8.2 Recommended Workers

- Minimum: 2 workers (sequential levels)
- Optimal: 4 workers (widest level is 4 tasks)
- Maximum: 6 workers (diminishing returns beyond)

### 8.3 Estimated Duration

- Single worker: ~5 hours
- With 4 workers: ~1.5 hours
- Speedup: ~3x

---

## 9. Approval

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Architecture | | | PENDING |
| Engineering | | | PENDING |
