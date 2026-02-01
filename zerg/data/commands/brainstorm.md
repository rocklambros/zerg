
# ZERG Brainstorm: $ARGUMENTS

Discover opportunities and generate actionable GitHub issues for domain: **$ARGUMENTS**

## Flags

- `--rounds N`: Number of Socratic rounds (default: 3, max: 5)
- `--skip-research`: Skip competitive analysis web research phase
- `--skip-issues`: Ideate only, don't create GitHub issues
- `--dry-run`: Preview issues without creating them
- `--resume`: Resume previous session from checkpoint
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

Conduct structured discovery via AskUserQuestion. Batch 3-4 questions per round to reduce back-and-forth.

Default: 3 rounds. Override with `--rounds N` (max 5).

**Round 1: Problem Space**
Ask 3-4 questions about problems, users, and inadequacies in current solutions.
See details file for question templates.

**Round 2: Solution Ideation**
Ask 3-4 questions about features, value/effort tradeoffs, and constraints.
See details file for question templates.

**Round 3: Prioritization**
Ask 3-4 questions about MVP scope, sequencing, dependencies, and success metrics.
See details file for question templates.

Save discovery transcript to `.gsd/specs/{session-id}/transcript.md`.

After each round, save a checkpoint to `.gsd/specs/{session-id}/.checkpoint` with the current round number. If `--resume` is set, read the checkpoint and skip completed rounds.

### Phase 3: Issue Generation

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
  --help                Show this help message

Examples:
  /zerg:brainstorm user-authentication
  /zerg:brainstorm payment-processing --rounds 5
  /zerg:brainstorm api-redesign --skip-research --dry-run
```
