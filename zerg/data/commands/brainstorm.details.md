<!-- SPLIT: details, parent: brainstorm.md -->
# ZERG Brainstorm: Details & Templates

Reference material for `/zerg:brainstorm`. See `brainstorm.core.md` for primary workflow.

---

## Research Phase Guidelines

### WebSearch Query Templates

Run 3-5 WebSearch queries tailored to the domain. Adapt these templates:

1. **Competitors**: `"{domain} alternatives comparison {current year}"`
2. **Pain points**: `"{domain} common problems user complaints"`
3. **Trends**: `"{domain} trends emerging features {current year}"`
4. **Best practices**: `"{domain} best practices architecture patterns"`
5. **Failures**: `"{domain} common mistakes pitfalls to avoid"`

### Research Summarization

For each query, extract:
- Key competitors and their differentiators (2-3 bullet points each)
- Recurring user pain points (ranked by frequency)
- Market gaps no one is addressing
- Emerging trends and technologies

### Research Output Template (research.md)

```markdown
# Research: {domain}

## Session
- **Session ID**: {session-id}
- **Date**: {timestamp}
- **Queries**: {N} searches conducted

---

## Competitive Landscape

| Competitor | Strengths | Weaknesses | Differentiator |
|------------|-----------|------------|----------------|
| {name} | {strengths} | {weaknesses} | {what sets apart} |

## User Pain Points (Ranked)

1. **{pain point}** -- Frequency: High/Medium/Low
   - Evidence: {source or quote}
2. **{pain point}** -- Frequency: High/Medium/Low
   - Evidence: {source or quote}

## Market Gaps

- {gap}: {why it matters}
- {gap}: {why it matters}

## Emerging Trends

- {trend}: {relevance to our project}
- {trend}: {relevance to our project}

## Key Takeaways

1. {insight}
2. {insight}
3. {insight}
```

---

## Socratic Round Templates

### Round 1: Problem Space (3-4 questions)

Present these via a single AskUserQuestion call. Adapt to the domain.

```
ROUND 1: PROBLEM SPACE
======================

I've completed initial research on {domain}. Before diving into solutions,
let me understand the problem landscape.

1. What specific problems or inefficiencies do you see in the current
   {domain} space? What frustrates users most?

2. Who are the primary users you want to serve, and what are their
   most critical workflows?

3. What existing solutions have you tried or evaluated?
   What falls short about them?

4. Are there opportunities you see that competitors are missing
   or ignoring entirely?

(Answer as much or as little as you like -- I'll follow up on anything unclear.)
```

### Round 2: Solution Ideation (3-4 questions)

```
ROUND 2: SOLUTION IDEATION
===========================

Based on the problems you described and my research findings, let me
explore the solution space.

1. If you could build the ideal solution with no constraints,
   what would it look like? What features would it have?

2. For each feature idea, roughly how would you rank them on a
   value-to-effort scale? (High value + low effort = quick wins)

3. Are there technical constraints or existing systems we need to
   integrate with? Any hard boundaries?

4. What would make this solution genuinely better than alternatives,
   not just different?

(Feel free to think big -- we'll narrow down in the next round.)
```

### Round 3: Prioritization (3-4 questions)

```
ROUND 3: PRIORITIZATION
========================

Now let's get concrete about what to build and in what order.

1. If you could only ship 2-3 features in the first version,
   which would they be and why?

2. How would you sequence the remaining features?
   Are there dependencies between them?

3. What does success look like? What metrics would tell you
   this is working?

4. Is there a timeline or milestone driving urgency for any
   particular feature?

(This will help me generate well-prioritized issues.)
```

### Additional Rounds (4-5, if --rounds > 3)

```
ROUND {N}: DEEP DIVE
=====================

Based on what we've discussed, I want to dig deeper into {specific area}.

1. {Follow-up question based on previous answers}
2. {Clarification on ambiguous requirement}
3. {Edge case or risk exploration}
4. {Integration or dependency question}
```

### Socratic Transcript Template (transcript.md)

```markdown
# Discovery Transcript: {domain}

## Session
- **Session ID**: {session-id}
- **Date**: {timestamp}
- **Rounds**: {N}

---

### Round 1: Problem Space
- **Q1**: {question}
  **A**: {answer}
- **Q2**: {question}
  **A**: {answer}
- **Q3**: {question}
  **A**: {answer}
- **Q4**: {question}
  **A**: {answer}

### Round 2: Solution Ideation
- **Q1**: {question}
  **A**: {answer}
...

### Round 3: Prioritization
- **Q1**: {question}
  **A**: {answer}
...
```

---

## Issue Template

For each identified feature, create a GitHub issue using `gh issue create`:

```bash
gh issue create \
  --title "{Feature Name}" \
  --label "brainstorm,{priority}" \
  --body "$(cat <<'ISSUE_EOF'
## Problem

{2-3 sentences describing the problem this feature solves, grounded in
research findings and user responses from the Socratic rounds.}

## Proposed Solution

{Description of the proposed feature and how it addresses the problem.
Include key capabilities and user-facing behavior.}

## Acceptance Criteria

- [ ] {Criterion 1}
- [ ] {Criterion 2}
- [ ] {Criterion 3}
- [ ] {Criterion 4}

## Competitive Context

{How competitors handle this. What gap this fills. Reference research.md findings.}

## Priority

**{P0/P1/P2}** -- {One-sentence justification}

- P0: Must-have for MVP, blocks other work
- P1: Important, should be in first release
- P2: Nice-to-have, can defer to later iteration

## Effort Estimate

**{Small/Medium/Large}** -- {Brief justification}

---

_Generated by `/zerg:brainstorm` session {session-id}_
ISSUE_EOF
)"
```

### Priority Assignment Guidelines

| Priority | Criteria | Label |
|----------|----------|-------|
| P0 | User identified as must-have, blocks other features, addresses critical pain point | `P0-critical` |
| P1 | High value, mentioned in MVP scope, strong competitive advantage | `P1-important` |
| P2 | Nice-to-have, future iteration, lower user urgency | `P2-nice-to-have` |

---

## Output Schemas

### brainstorm.md (Session Summary)

```markdown
# Brainstorm Summary: {domain}

## Session
- **Session ID**: {session-id}
- **Domain**: {domain}
- **Date**: {timestamp}
- **Rounds**: {N}
- **Issues Created**: {N}

---

## Key Insights

1. {Top insight from research and discovery}
2. {Second insight}
3. {Third insight}

## Features Identified (Ranked)

| Rank | Feature | Priority | Effort | Issue |
|------|---------|----------|--------|-------|
| 1 | {feature} | P0 | {S/M/L} | #{number} |
| 2 | {feature} | P1 | {S/M/L} | #{number} |
| 3 | {feature} | P2 | {S/M/L} | #{number} |

## Recommended Next Steps

1. `/zerg:plan {top-feature}` -- Start planning the highest-priority feature
2. Review and refine issues on GitHub
3. Share brainstorm summary with stakeholders

## Session Artifacts

- `research.md` -- Competitive analysis and market research
- `transcript.md` -- Full Socratic discovery transcript
- `issues.json` -- Machine-readable issue manifest
- `brainstorm.md` -- This summary
```

### issues.json (Machine-Readable Manifest)

```json
{
  "session_id": "{session-id}",
  "domain": "{domain}",
  "created": "{ISO-8601 timestamp}",
  "issues": [
    {
      "number": 42,
      "url": "https://github.com/{owner}/{repo}/issues/42",
      "title": "{Feature Name}",
      "priority": "P0",
      "effort": "Medium",
      "feature_name": "{feature-slug}",
      "labels": ["brainstorm", "P0-critical"]
    }
  ],
  "next_recommended": "{top-feature-slug}"
}
```

If `--dry-run` was used, `number` and `url` will be `null`.

---

## Handoff Prompt Template

```
=====================================================================
                    BRAINSTORM SESSION COMPLETE
=====================================================================

Domain: {domain}
Session: {session-id}

Issues Created: {N}
  P0 (Critical):    {count}
  P1 (Important):   {count}
  P2 (Nice-to-have): {count}

Top Recommendations:
  1. {feature} (P0, {effort}) -- #{issue-number}
  2. {feature} (P1, {effort}) -- #{issue-number}
  3. {feature} (P2, {effort}) -- #{issue-number}

Session Artifacts:
  .gsd/specs/{session-id}/research.md
  .gsd/specs/{session-id}/transcript.md
  .gsd/specs/{session-id}/brainstorm.md
  .gsd/specs/{session-id}/issues.json

---------------------------------------------------------------------

Suggested next step:
  /zerg:plan {top-feature}

=====================================================================
```

---

## Example Session

### Input
```
/zerg:brainstorm notification-system
```

### Phase 1: Research
WebSearch queries:
- "notification system alternatives comparison 2026"
- "push notification pain points user complaints"
- "notification system architecture best practices"

Findings saved to `.gsd/specs/brainstorm-20260201-143022/research.md`.

### Phase 2: Socratic Discovery

**Round 1 (Problem Space)**:
- Q: What problems do you see in the notification space?
- A: Users get too many irrelevant notifications and miss the important ones.

**Round 2 (Solution Ideation)**:
- Q: What would the ideal notification system look like?
- A: Smart filtering with user preferences, digest mode, and priority channels.

**Round 3 (Prioritization)**:
- Q: Which 2-3 features are must-haves?
- A: Priority channels, user preference settings, and digest mode.

### Phase 3: Issue Generation
Created 5 issues:
- #101: Priority Channels (P0)
- #102: User Notification Preferences (P0)
- #103: Digest Mode (P1)
- #104: Smart Filtering with ML (P2)
- #105: Notification Analytics Dashboard (P2)

### Phase 4: Handoff
Presented summary, suggested `/zerg:plan priority-channels` as next step.
