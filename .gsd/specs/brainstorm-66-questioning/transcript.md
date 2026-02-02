# Brainstorm Transcript: #66 Questioning Methodology

## Round 1: Problem Space
- **Core pain**: All three (overwhelm + shallow + no adaptation) compound. Fix must use detailed multiple-choice with Other.
- **Default mode**: --socratic is opt-in. Batch remains default for backward compatibility.

## Round 2: Solution Ideation
- **YAGNI gate**: Binary keep/drop (no 3-tier classification). Simple checkbox.
- **Adaptation**: Hybrid — question tree for known paths, LLM-generated follow-ups when user picks "Other".

## Round 3: Design Decisions
- **Checkpoints**: Full 4-checkpoint incremental validation (scope → entities → workflows → NFRs).
- **Trade-offs**: Dedicated round after discovery, not woven into flow.

## Round 4: Implementation Constraints
- **Architecture**: Question tree lives in brainstorm.details.md to minimize context. No new Python modules.
- **Question count**: Dynamic with saturation detection. Show estimated remaining count. Explain methodology upfront.

## Round 5: Prioritization & Scope
- **MVP**: Full scope — all 5 features in one implementation.
- **Issue strategy**: Epic + sub-issues. #66 becomes epic, atomic sub-tasks reference it. Aligns with ZERG swarm/dependency model.
