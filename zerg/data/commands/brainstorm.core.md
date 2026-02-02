<!-- SPLIT: core, parent: brainstorm.md -->
# ZERG Brainstorm: $ARGUMENTS

Discover opportunities and generate actionable GitHub issues for domain: **$ARGUMENTS**

## Flags

- `--rounds N`: Number of Socratic rounds (default: 3, max: 5)
- `--skip-research`: Skip competitive analysis web research phase
- `--skip-issues`: Ideate only, don't create GitHub issues
- `--dry-run`: Preview issues without creating them
- `--resume`: Resume previous session from checkpoint
- `--socratic`: Enable single-question Socratic mode with domain question trees (default: batch mode)
- `--help`: Show usage

## Pre-Flight

```bash
DOMAIN="$ARGUMENTS"

# Validate domain argument
if [ -z "$DOMAIN" ]; then
  echo "ERROR: Domain or topic required"
  echo "Usage: /zerg:brainstorm domain-or-topic"
  exit 1
fi

# Sanitize domain name (lowercase, hyphens only)
DOMAIN=$(echo "$DOMAIN" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | tr -cd 'a-z0-9-')

# Generate session ID
SESSION_ID="brainstorm-$(date +%Y%m%d-%H%M%S)"

# Cross-session task list coordination
TASK_LIST=${CLAUDE_CODE_TASK_LIST_ID:-$DOMAIN}

# Create session directory
mkdir -p ".gsd/specs/$SESSION_ID"
echo "$SESSION_ID" > .gsd/.current-brainstorm
echo "$DOMAIN" > ".gsd/specs/$SESSION_ID/.domain"
echo "$(date -Iseconds)" > ".gsd/specs/$SESSION_ID/.started"

# Verify gh CLI if creating issues
if [[ "$ARGUMENTS" != *"--skip-issues"* ]] && [[ "$ARGUMENTS" != *"--dry-run"* ]]; then
  if ! command -v gh &> /dev/null; then
    echo "WARNING: gh CLI not found. Issues will be saved locally only."
    echo "Install: https://cli.github.com/"
  elif ! gh auth status &> /dev/null 2>&1; then
    echo "WARNING: gh CLI not authenticated. Run 'gh auth login' first."
  fi
fi
```

---

## Track in Claude Task System

At the START of brainstorming (before Phase 1), create a tracking task:

Call TaskCreate:
  - subject: "[Brainstorm] Discovery: {domain}"
  - description: "Brainstorm session for {domain}. Researching, discovering, and generating issues via /zerg:brainstorm."
  - activeForm: "Brainstorming {domain}"

Immediately call TaskUpdate to set it in_progress:
  - taskId: (the Claude Task ID just created)
  - status: "in_progress"

After session completes (all phases done), call TaskUpdate to mark completed:
  - taskId: (the same Claude Task ID)
  - status: "completed"
  - description: "Brainstorm complete for {domain}. {N} issues created. Ready for /zerg:plan {feature}."

This ensures the task system tracks the full lifecycle: start -> in_progress -> completed.

---

## Workflow Overview

### Phase 1: Research

Before asking questions, research the domain:

1. **Read PROJECT.md and INFRASTRUCTURE.md** -- Understand existing tech stack and project context
2. **WebSearch for competitive landscape** -- 3-5 queries covering:
   - Competitors and alternatives in this space
   - Common user pain points and complaints
   - Market gaps and emerging trends
3. **Save research findings** to `.gsd/specs/{session-id}/research.md`

If `--skip-research` is set, skip this phase entirely.

### Phase 2: Socratic Discovery

**Batch Mode** (default): Conduct structured discovery via AskUserQuestion. Batch 3-4 questions per round to reduce back-and-forth. Default: 3 rounds. Override with `--rounds N` (max 5). See details file for round templates.

**Socratic Mode** (`--socratic`): Single-question interactive mode with domain question trees.

1. **Domain Detection**: Match $ARGUMENTS keywords to question tree:
   - auth/login/session/jwt/oauth/password/token/2fa → Auth & Authorization tree
   - api/rest/graphql/endpoint/route/http → API Design tree
   - data/pipeline/etl/streaming/batch/warehouse → Data Pipeline tree
   - ui/frontend/react/vue/angular/component/css → UI/Frontend tree
   - infra/deploy/ci/cd/docker/kubernetes/cloud → Infrastructure tree
   - (no match) → General tree

2. **Question Loop**: Present questions one at a time via AskUserQuestion (multiSelect: false). Show "Question N of ~M" in header. If user picks a tree option, follow that branch. If user picks "Other" or tree is exhausted, generate LLM follow-up.

3. **Saturation Rule**: Stop when 2 consecutive answers introduce zero new entities, constraints, or requirements. Minimum 3 questions before checking. Announce: "Discovery complete — your answers have converged."

Save discovery transcript to `.gsd/specs/{session-id}/transcript.md`. After each round/question, save checkpoint.

### Phase 2.5: Trade-off Exploration

Runs in both batch and socratic modes. For each architectural decision identified during discovery:

1. Present 2-3 alternatives via AskUserQuestion, each with one-line pro and one-line con
2. Record chosen approach and reasoning
3. Skip if no architectural decisions were identified

Save trade-off outcomes to `.gsd/specs/{session-id}/tradeoffs.md`.

### Phase 2.6: Design Validation

Runs in both modes. 4 validation checkpoints via AskUserQuestion:

1. **Scope**: "Does this scope match your vision?" → Confirmed / Revise / Add
2. **Entities**: "Are these the right data models?" → Confirmed / Revise / Add
3. **Workflows**: "Do these user flows cover your needs?" → Confirmed / Revise / Add
4. **NFRs**: "Are these non-functional requirements correct?" → Confirmed / Revise / Add

If user selects "Revise" or "Add" at checkpoint N, regenerate checkpoints N+1..4 with updated context. Save to `.gsd/specs/{session-id}/validated-design.md`.

### Phase 2.7: YAGNI Gate

Runs in both modes. Present all identified features via AskUserQuestion (multiSelect: true):

- Header: "YAGNI Gate"
- Question: "Which features should be built now? Unselected items will be deferred."
- Options: Each identified feature with one-line description

Kept features → proceed to Phase 3. Dropped features → logged in `.gsd/specs/{session-id}/deferred.md`.

### Phase 3: Issue Generation

Apply YAGNI filter: only generate issues for features that passed the YAGNI Gate (Phase 2.7).

For each identified feature/opportunity, create a GitHub issue via `gh issue create`.

Each issue includes:
- Title with clear feature name
- Problem statement (2-3 sentences)
- Proposed solution
- Acceptance criteria (checkboxes)
- Priority label (P0/P1/P2)
- Competitive context from research

If `--skip-issues` is set, skip this phase.
If `--dry-run` is set, preview issues in terminal without creating them.

Save issue manifest to `.gsd/specs/{session-id}/issues.json`.

See details file for issue template.

### Phase 4: Handoff

Present ranked recommendations:
1. Show prioritized feature list with effort estimates
2. Save session summary to `.gsd/specs/{session-id}/brainstorm.md`
3. Suggest next step: `/zerg:plan {top-feature}`

---

## Context Management

- **Command splitting**: Workers get core only unless details needed
- **Scoped loading**: Load PROJECT.md first, codebase only if relevant
- **Session resumability**: State saved after each phase via checkpoint files
- **Question batching**: 3-4 questions per AskUserQuestion call to minimize round-trips
- **Socratic mode**: Single-question flow with domain trees, saturation detection, and dynamic follow-ups

## Completion Criteria

- Research findings saved to `.gsd/specs/{session-id}/research.md` (unless `--skip-research`)
- All Socratic rounds completed with transcript saved
- Issues created on GitHub (unless `--skip-issues` or `--dry-run`)
- Issue manifest saved to `.gsd/specs/{session-id}/issues.json`
- Session summary saved to `.gsd/specs/{session-id}/brainstorm.md`
- Task system updated to completed

## Help

When `--help` is passed in `$ARGUMENTS`, display usage and exit:

```
/zerg:brainstorm -- Discover opportunities and generate GitHub issues.

Usage: /zerg:brainstorm domain-or-topic [flags]

Flags:
  --rounds N            Number of Socratic rounds (default: 3, max: 5)
  --skip-research       Skip competitive analysis web research phase
  --skip-issues         Ideate only, don't create GitHub issues
  --dry-run             Preview issues without creating them
  --resume              Resume previous session from checkpoint
  --socratic            Single-question mode with domain question trees
  --help                Show this help message

Examples:
  /zerg:brainstorm user-authentication
  /zerg:brainstorm payment-processing --rounds 5
  /zerg:brainstorm api-redesign --skip-research --dry-run
  /zerg:brainstorm user-auth --socratic
```
