# Brainstorm Summary: #66 Questioning Methodology

## Session Info
- Domain: /zerg:brainstorm questioning methodology enhancement
- Rounds: 5 (Socratic discovery)
- Issues created: 5 sub-issues + 1 epic update

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Default mode | --socratic opt-in | Backward compatible, batch stays default |
| YAGNI gate style | Binary keep/drop | Simpler UX, no 3-tier complexity |
| Adaptation strategy | Hybrid tree + LLM | Predictable paths + flexibility for custom answers |
| Checkpoints | 4 stops (scope/entities/workflows/NFRs) | Full incremental validation |
| Trade-off placement | Dedicated round | Clear separation from discovery |
| Architecture | brainstorm.details.md only | Minimizes context usage, no new Python code |
| Question count | Dynamic with progress indicator | Explain methodology upfront, show ~N remaining |
| Issue strategy | Epic + atomic sub-issues | Aligns with ZERG swarm/dependency model |

## Dependency Graph
```
L1: #69 (single-question mode — foundation)
L2: #70 (adaptive) || #71 (trade-offs)
    #72 (validation) ← depends on #71
L3: #73 (YAGNI gate) ← depends on #72
```

## Execution Flow (Enhanced Brainstorm)
```
Start → Explain methodology → Discovery (dynamic, ~5-15 questions)
  → Trade-off round → Scope ✓ → Entities ✓ → Workflows ✓ → NFRs ✓
  → YAGNI gate (keep/drop) → Issue generation → Handoff
```

## Next Step
```
/zerg:plan #66-questioning-methodology
```
