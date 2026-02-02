# Requirements: #66 Enhanced Brainstorm Questioning Methodology

**Status: APPROVED**
**Date**: 2026-02-01

## Functional Requirements

### FR-1: --socratic Single-Question Mode (#69)
- `--socratic` flag activates one-question-at-a-time mode via AskUserQuestion
- Each question: 2-4 options with descriptions, multiSelect: false, implicit "Other"
- Batch mode (default) unchanged without flag
- Methodology explanation displayed at session start
- Progress indicator: "Question N of ~M"

### FR-2: Hybrid Adaptive Questioning (#70)
- 6 domain question trees (auth, API, data-pipeline, UI, infrastructure, general)
- Domain detection from $ARGUMENTS keywords
- Tree-driven questions when branches available
- LLM-generated follow-ups when user picks "Other" or tree exhausted
- Dynamic question count, updated after each answer

### FR-3: Saturation Detection
- Stop discovery when 2 consecutive answers introduce zero new entities/constraints/requirements
- Minimum 3 questions before checking
- Announce: "Discovery complete -- your answers have converged."

### FR-4: Trade-off Exploration Round (#71)
- Runs in BOTH batch and socratic modes, after discovery
- Present 2-3 alternatives per major architectural decision
- Each option: label + one-line pro + one-line con via AskUserQuestion
- Skip if no decisions identified

### FR-5: Incremental Design Validation (#72)
- Runs in BOTH modes
- 4 sequential checkpoints: Scope → Entities → Workflows → NFRs
- Each via AskUserQuestion: "Confirmed" / "Revise" / "Add"
- Revision at checkpoint N regenerates N+1..4
- Output: validated-design.md

### FR-6: Binary YAGNI Gate (#73)
- Runs in BOTH modes, after validation
- AskUserQuestion with multiSelect: true
- All features listed with description + priority
- Kept features → Phase 3 issue generation
- Dropped features → logged as "Deferred" in transcript

## Non-Functional Requirements

### NFR-1: Line Budget
- brainstorm.core.md ≤ 300 lines
- brainstorm.md mirrors core.md exactly

### NFR-2: Context Efficiency
- All templates in details.md (loaded on demand)
- No new Python modules or config files

### NFR-3: Backward Compatibility
- Batch mode behavior unchanged without --socratic
- All existing flags continue to work

### NFR-4: Validation
- python -m zerg.validate_commands must pass
- Task ecosystem markers preserved
