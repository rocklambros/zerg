# Technical Design: #66 Enhanced Brainstorm Questioning Methodology

## Metadata
- **Feature**: 66-questioning-methodology
- **Status**: DRAFT
- **Created**: 2026-02-01
- **Epic**: #66
- **Sub-issues**: #69, #70, #71, #72, #73

---

## 1. Overview

### 1.1 Summary
Enhance `/zerg:brainstorm` with 5 features: `--socratic` single-question mode with adaptive domain-specific question trees, dedicated trade-off exploration round, 4-checkpoint incremental design validation, and binary YAGNI gate. All changes are markdown command file edits — no Python code modifications. The architecture uses the existing core/details split pattern to keep behavioral flow in core.md (≤300 lines) and all templates/trees in details.md (unlimited).

### 1.2 Goals
- Single-question mode via `--socratic` flag with structured AskUserQuestion options
- Hybrid adaptive questioning: domain trees + LLM fallback for "Other" answers
- Dynamic question count with progress indicator and saturation detection
- Trade-off exploration, design validation, and YAGNI scope filtering in both modes
- 6 domain question trees covering common brainstorm domains

### 1.3 Non-Goals
- Python code changes or new modules
- Changing batch mode default behavior
- Adding new CLI flags beyond `--socratic`
- Modifying the install-commands mechanism

---

## 2. Architecture

### 2.1 High-Level Design

```
┌─────────────────────────────────────────────────────────┐
│                  brainstorm.core.md                      │
│  (behavioral flow, ≤300 lines)                          │
│                                                          │
│  Phase 1: Research (unchanged)                           │
│  Phase 2: Socratic Discovery                             │
│    ├─ Batch mode (default, unchanged)                    │
│    └─ Socratic mode (--socratic)                         │
│         ├─ Domain detection → tree selection             │
│         ├─ Question loop (AskUserQuestion × N)           │
│         ├─ Hybrid: tree branches + LLM fallback          │
│         └─ Saturation detection → stop                   │
│  Phase 2.5: Trade-off Exploration (both modes)           │
│  Phase 2.6: Design Validation (both modes)               │
│  Phase 2.7: YAGNI Gate (both modes)                      │
│  Phase 3: Issue Generation (YAGNI-filtered)              │
│  Phase 4: Handoff (unchanged)                            │
└─────────────────────────────────────────────────────────┘
                          │
                          │ "See details file for..."
                          ▼
┌─────────────────────────────────────────────────────────┐
│                brainstorm.details.md                      │
│  (templates & reference, unlimited)                      │
│                                                          │
│  Existing: Research templates, Round 1/2/3 templates,    │
│            Issue template, Output schemas, Example        │
│                                                          │
│  NEW: Question Trees (6 domains)                         │
│       Saturation Detection guidance                      │
│       Trade-off Round templates                          │
│       Validation Checkpoint templates                    │
│       YAGNI Gate template                                │
│       Updated transcript template                        │
└─────────────────────────────────────────────────────────┘
```

### 2.2 Component Breakdown

| Component | Responsibility | Location |
|-----------|---------------|----------|
| Flag parsing | Detect `--socratic`, set mode | core.md Flags section |
| Dual-mode Phase 2 | Branch batch vs socratic flow | core.md Phase 2 |
| Domain detection | Match $ARGUMENTS to tree category | core.md Phase 2 |
| Question loop | Iterate AskUserQuestion calls | core.md Phase 2 |
| Saturation detection | Stop when answers converge | core.md Phase 2 + details.md |
| Question trees | 6 domain-specific branching trees | details.md |
| Trade-off round | Present alternatives per decision | core.md Phase 2.5 + details.md |
| Design validation | 4 sequential checkpoints | core.md Phase 2.6 + details.md |
| YAGNI gate | Binary keep/drop feature filter | core.md Phase 2.7 + details.md |

### 2.3 Data Flow

```
$ARGUMENTS + --socratic
  → Domain detection (auth|api|data|ui|infra|general)
  → Select question tree from details.md
  → Question loop:
      for each question:
        tree has branch? → present tree question
        tree exhausted or "Other"? → LLM generates from transcript
        → AskUserQuestion(multiSelect: false)
        → Record answer → update ~M estimate
        → Saturation check (2 consecutive empty → stop)
  → Trade-off round (2-3 decisions, AskUserQuestion each)
  → Validation checkpoints (4 stops, AskUserQuestion each)
  → YAGNI gate (AskUserQuestion, multiSelect: true)
  → Issue generation (kept features only)
  → Handoff
```

---

## 3. Detailed Design

### 3.1 core.md Changes (behavioral flow)

**Flags section** — Add `--socratic` flag:
```markdown
- `--socratic`: One question at a time with structured options (default: batch mode)
```

**Phase 2 replacement** — Dual-mode with socratic loop:
- Batch mode stub (4 lines, references existing round templates)
- Socratic mode block (~30 lines): methodology explanation, domain detection, question loop, hybrid branching, saturation rule, progress indicator
- Checkpoint logic (3 lines)

**Phase 2.5** — Trade-off exploration (~15 lines):
- Trigger: after discovery in both modes
- Present 2-3 alternatives per major decision
- Skip if no decisions identified

**Phase 2.6** — Design validation (~18 lines):
- 4 checkpoints: Scope → Entities → Workflows → NFRs
- Confirm/Revise/Add options
- Revision cascades downstream

**Phase 2.7** — YAGNI gate (~12 lines):
- multiSelect: true, binary keep/drop
- Dropped features logged as "Deferred"

**Phase 3 update** — Add YAGNI filter line

**Help section** — Add --socratic to help text

**Context Management** — Add socratic mode bullet

**Estimated total: ~260 lines (under 300 limit)**

### 3.2 details.md Additions (templates & trees)

**Question Trees** (~170 lines total, 6 domains):

Each tree follows this structure:
```
### Domain: {Name}

Keywords: {comma-separated trigger words for domain detection}

Q1: "{question}"
  a) {option} → Q2a
  b) {option} → Q2b
  c) {option} → Q2c
  d) Other → LLM follow-up

Q2a: "{follow-up for option a}"
  a) {option} → Q3a
  b) {option} → Q3b
  c) Other → LLM follow-up

[... 3-5 depth levels, 5-8 questions per path]
```

Domains: Auth (session/JWT/OAuth), API (REST/GraphQL/versioning), Data Pipeline (batch/streaming/ETL), UI/Frontend (framework/SSR/state), Infrastructure (hosting/CI-CD/monitoring), General (catch-all).

**Saturation Detection** (~15 lines):
- Definition: 2 consecutive answers with zero new entities/constraints/requirements
- Signal phrases, minimum 3 questions rule

**Trade-off Templates** (~40 lines):
- Format template with pros/cons per option
- Common trade-offs table by domain

**Validation Checkpoint Templates** (~50 lines):
- 4 checkpoint format blocks (scope, entities, workflows, NFRs)
- validated-design.md output schema

**YAGNI Gate Template** (~25 lines):
- AskUserQuestion format with multiSelect: true
- Deferred feature log entry

**Updated Transcript Template** (~15 lines):
- Socratic mode format (individual Q&A pairs)
- Trade-off outcomes section
- Validation results section
- YAGNI gate results section

**Estimated total: ~715 lines**

---

## 4. Key Decisions

### 4.1 --socratic activates full pipeline
**Context**: Should --socratic only change questioning style, or enable trade-offs/validation/YAGNI too?
**Decision**: --socratic enables the full enhanced pipeline. Trade-offs, validation, and YAGNI gate are also available in batch mode as non-breaking additions.
**Rationale**: Users who opt into --socratic want the complete improved experience. Making the post-discovery phases available in both modes maximizes value.

### 4.2 All logic in markdown, no Python
**Context**: Question trees could live in Python (testable) or YAML config (customizable) or markdown (context-efficient).
**Decision**: All in brainstorm.details.md.
**Rationale**: Minimizes context usage per ZERG's context engineering methodology. No new files to manage. Workers load details.md only when needed.

### 4.3 6 domain trees at launch
**Context**: Could start with 3 trees or ship all 6.
**Decision**: Ship all 6 to provide complete coverage.
**Rationale**: The general tree catches edge cases. Having domain-specific trees for common categories (auth, API, data, UI, infra) provides immediate value.

---

## 5. Implementation Plan

### 5.1 Phase Summary (Optimized for Max Parallelism)

| Level | Tasks | Parallel Workers | Description |
|-------|-------|-----------------|-------------|
| L1 | T1, T2, T3, T4 | 4 | Foundation: core.md flow + question trees + templates + CHANGELOG |
| L2 | T5, T6 | 2 | Assembly: details.md merge + brainstorm.md mirror |
| L3 | T7 | 1 | Validation: verify all constraints |

### 5.2 File Ownership

| File | Task ID | Operation |
|------|---------|-----------|
| `zerg/data/commands/brainstorm.core.md` | TASK-001 | modify |
| `.gsd/specs/66-questioning-methodology/question-trees.md` | TASK-002 | create |
| `.gsd/specs/66-questioning-methodology/new-templates.md` | TASK-003 | create |
| `CHANGELOG.md` | TASK-004 | modify |
| `zerg/data/commands/brainstorm.details.md` | TASK-005 | modify |
| `zerg/data/commands/brainstorm.md` | TASK-006 | modify |
| (no file — validation only) | TASK-007 | read-only |

### 5.3 Dependency Graph

```
L1:  T1 (core.md)  ||  T2 (trees)  ||  T3 (templates)  ||  T4 (CHANGELOG)
      │                  │                │
      │                  └────────┬───────┘
      │                           │
L2:  T6 (mirror)           T5 (assemble details.md)
      │                           │
      └───────────┬───────────────┘
                  │
L3:           T7 (validate)
```

---

## 6. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| core.md exceeds 300 lines | Low | High | Track line count per edit. Current: 180, budget: 120 lines |
| validate_commands fails | Low | Medium | Run validation in T7 before PR. Fix in place if needed |
| Parent .md out of sync | Medium | High | T6 does exact copy. T7 verifies with diff |
| Question trees too generic | Medium | Low | General tree catches all. Domain trees can be refined later |
| Batch mode regression | Low | High | T7 verifies batch mode sections unchanged |

---

## 7. Testing Strategy

### 7.1 Automated Verification (TASK-007)
```bash
python -m zerg.validate_commands                                    # Drift checks pass
wc -l zerg/data/commands/brainstorm.core.md                        # ≤ 300 lines
diff zerg/data/commands/brainstorm.core.md zerg/data/commands/brainstorm.md  # Identical
grep -c "socratic" zerg/data/commands/brainstorm.core.md           # ≥ 3 references
grep -c "TaskCreate\|TaskUpdate" zerg/data/commands/brainstorm.core.md  # ≥ 2 markers
grep -c "YAGNI" zerg/data/commands/brainstorm.details.md           # ≥ 1 reference
grep -c "Saturation" zerg/data/commands/brainstorm.details.md      # ≥ 1 reference
```

### 7.2 Manual Validation
- Run `/zerg:brainstorm test-domain --socratic` — expect single questions with options
- Run `/zerg:brainstorm test-domain` — expect unchanged batch behavior
- Verify question trees load for recognized domains (auth, api keywords)

---

## 8. Parallel Execution Notes

### 8.1 Recommended Workers
- **Minimum**: 1 worker (sequential)
- **Optimal**: 4 workers (L1 parallelism)
- **Maximum**: 4 workers (L1 is the widest level)

### 8.2 Strategy: Intermediate Files
Tasks T2 and T3 write to intermediate files in `.gsd/specs/` to avoid file ownership conflicts on `brainstorm.details.md`. Task T5 assembles the final details.md by appending intermediate content.

---

## 9. Approval

Status: **DRAFT** — Awaiting user approval before `/zerg:rush`.
