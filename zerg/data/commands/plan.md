
# ZERG Plan: $ARGUMENTS

Capture complete requirements for feature: **$ARGUMENTS**

## ⛔ WORKFLOW BOUNDARY (NON-NEGOTIABLE)

**CRITICAL: This is a PLANNING-ONLY command. You MUST NEVER write code, create files, or implement anything.**

This command MUST NEVER:
- Automatically run `/z:design` or any design phase
- Automatically proceed to implementation
- Call the Skill tool to invoke another command
- Write code or make code changes
- Create, modify, or delete source files
- Run implementation tools (Write, Edit, Bash for code changes)

After Phase 5.5 completes, the command STOPS. The user must manually run `/z:design`.

**If you find yourself about to write code or create files: STOP IMMEDIATELY. You are in planning mode.**

## Flags

- `--socratic` or `-s`: Use structured 3-round discovery mode (see details file)
- `--rounds N`: Number of rounds (default: 3, max: 5)
- `--skip-validation`: Skip Phase 0 pre-execution validation checks

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

# Cross-session task list coordination
TASK_LIST=${CLAUDE_CODE_TASK_LIST_ID:-$FEATURE}

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

> ⛔ **IMPLEMENTATION GUARD**: You are gathering requirements. DO NOT write code, DO NOT create implementation files, DO NOT design architecture. Stay in requirements-gathering mode.

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

> ⛔ **IMPLEMENTATION GUARD**: You are presenting requirements for approval. DO NOT proceed to design or implementation. DO NOT invoke /z:design. DO NOT write any code. After approval, output the PLANNING COMPLETE banner and STOP.

### Phase 5: User Approval

Present requirements for approval. User replies with:
- "APPROVED" — proceed to design phase
- "REJECTED" — describe what needs to change
- Specific questions or concerns

---

### Phase 5.5: Post-Approval Handoff

After the user replies "APPROVED":

1. First, call TaskUpdate to mark the plan task `completed`
2. Update requirements.md with `Status: APPROVED`
3. Then use AskUserQuestion to prompt the user for next steps:

Call AskUserQuestion:
  - question: "Requirements approved! How would you like to proceed?"
  - header: "Next step"
  - options:
    - label: "Clear context, then /z:design (Recommended)"
      description: "Run /compact to free token budget, then start /z:design in a fresh context"
    - label: "Stop here"
      description: "I'll run /z:design later in a new session"

Based on user response:
- **"Clear context, then /z:design"**: Output: "Run `/compact` to clear context, then run `/z:design` to begin architecture."
- **"Stop here"**: Command completes normally with no further output.

**⛔ DO NOT auto-run /z:design. DO NOT write code. The user must manually invoke the next command.**

Output this banner to the user:

```
═══════════════════════════════════════════════════════════════
                    ⛔ PLANNING COMPLETE ⛔
═══════════════════════════════════════════════════════════════

This command has finished. DO NOT proceed to implementation.
The user must manually run /z:design to continue.

EXIT NOW — do not write code, do not invoke other commands.
═══════════════════════════════════════════════════════════════
```

**After outputting this banner, the command is DONE. Do not take any further action. Do not write code. Do not call any tools. STOP.**

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

## Help

When `--help` is passed in `$ARGUMENTS`, display usage and exit:

```
/zerg:plan — Capture complete requirements for a feature.

Flags:
  -s, --socratic        Use structured 3-round discovery mode
  --rounds N            Number of rounds (default: 3, max: 5)
  --help                Show this help message
```
