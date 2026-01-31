<!-- SPLIT: core, parent: zerg:plan.md -->
# ZERG Plan: $ARGUMENTS

Capture complete requirements for feature: **$ARGUMENTS**

## Flags

- `--socratic` or `-s`: Use structured 3-round discovery mode (see details file)
- `--rounds N`: Number of rounds (default: 3, max: 5)

## Pre-Flight

```bash
FEATURE="$ARGUMENTS"

# Validate feature name
if [ -z "$FEATURE" ]; then
  echo "ERROR: Feature name required"
  echo "Usage: /zerg:plan feature-name"
  exit 1
fi

# Sanitize feature name (lowercase, hyphens only)
FEATURE=$(echo "$FEATURE" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | tr -cd 'a-z0-9-')

# Create spec directory
mkdir -p ".gsd/specs/$FEATURE"
echo "$FEATURE" > .gsd/.current-feature
echo "$(date -Iseconds)" > ".gsd/specs/$FEATURE/.started"
```

## Enter Plan Mode

**Press Shift+Tab twice** to enter plan mode (Opus 4.5 for reasoning).

Plan mode gives you read-only tools to explore the codebase without making changes.

---

## Track in Claude Task System

At the START of planning (before Phase 1), create a tracking task:

Call TaskCreate:
  - subject: "[Plan] Capture requirements: {feature}"
  - description: "Planning phase for {feature}. Gathering requirements via /zerg:plan."
  - activeForm: "Planning {feature}"

Immediately call TaskUpdate to set it in_progress:
  - taskId: (the Claude Task ID just created)
  - status: "in_progress"

After user approves requirements, call TaskUpdate to mark completed:
  - taskId: (the same Claude Task ID)
  - status: "completed"
  - description: "Requirements captured and approved for {feature}. Ready for /zerg:design."

This ensures the task system tracks the full lifecycle: start → in_progress → completed.

---

## Workflow Overview

### Phase 1: Context Gathering

Before asking questions, understand the current state:

1. **Read PROJECT.md and INFRASTRUCTURE.md** — Understand existing tech stack
2. **Explore Codebase** — List directory structure, read key files, identify patterns
3. **Search for Similar Patterns** — How are existing features structured?

### Phase 2: Requirements Elicitation

Ask clarifying questions grouped logically. Don't ask everything at once. Cover:
- Problem Space, Functional Requirements, Non-Functional Requirements
- Scope Boundaries, Dependencies, Acceptance Criteria

See details file for full question categories.

### Phase 3: Generate requirements.md

Write comprehensive requirements document to `.gsd/specs/{feature}/requirements.md`.

See details file for the full template.

### Phase 4: Infrastructure Requirements

Identify additional infrastructure needs (services, MCP servers, env vars, resources).
Update `.gsd/INFRASTRUCTURE.md` if needed.

### Phase 5: User Approval

Present requirements for approval. User replies with:
- "APPROVED" — proceed to design phase
- "REJECTED" — describe what needs to change
- Specific questions or concerns

---

## Status Markers

- **Status: DRAFT** - Initial creation, still gathering requirements
- **Status: REVIEW** - Requirements complete, awaiting approval
- **Status: APPROVED** - Requirements approved, ready for design
- **Status: REJECTED** - Requirements need revision

## Completion Criteria

- requirements.md exists with Status: APPROVED
- All open questions resolved or accepted
- User has explicitly approved with "APPROVED"
- Infrastructure needs identified and documented
