<!-- SPLIT: core, parent: plan.md -->
# ZERG Plan: $ARGUMENTS

Capture complete requirements for feature: **$ARGUMENTS**

## ⛔ WORKFLOW BOUNDARY (NON-NEGOTIABLE)

**CRITICAL: This is a PLANNING-ONLY command. You gather requirements and write spec files. You MUST NEVER write source code or proceed to implementation.**

### PROHIBITED (absolute — zero exceptions):
- Call **EnterPlanMode** or **ExitPlanMode** tools (these have approve→implement semantics that override stop guards)
- Automatically run `/z:design` or any design/implementation phase
- Automatically proceed to implementation after approval
- Call the **Skill** tool to invoke another command (including `/z:design`)
- Write, Edit, or Bash against ANY file OUTSIDE of `.gsd/` directory
- Create, modify, or delete source code files (anything in `zerg/`, `tests/`, `src/`, etc.)
- Continue executing after the PLANNING COMPLETE banner is output

### REQUIRED (mandatory — the command fails if these don't happen):
- You **MUST** use the **Write** tool to create `.gsd/specs/{feature}/requirements.md`
- You **MUST** use **Bash** to create `.gsd/specs/{feature}/` directory and sentinel files
- You **MUST** call **AskUserQuestion** for Phase 5 approval — never assume approval
- You **MUST** call **AskUserQuestion** for Phase 5.5 next-step prompt — never skip
- You **MUST** write `.gsd/specs/{feature}/.plan-complete` sentinel after approval
- You **MUST** output the PLANNING COMPLETE banner as your final action, then STOP

### ALLOWED tools and their scopes:
- **Read, Grep, Glob**: Any file (for context gathering)
- **Write**: ONLY files under `.gsd/specs/{feature}/` (requirements.md, sentinels)
- **Bash**: ONLY `mkdir -p` and `echo` into `.gsd/` paths; `gh issue view`; `git log`
- **AskUserQuestion**: For elicitation (Phase 2), approval (Phase 5), handoff (Phase 5.5)
- **TaskCreate, TaskUpdate**: For Claude Task tracking
- **WebSearch, WebFetch**: For research if needed

After Phase 5.5 completes, the command STOPS. The user must manually run `/z:design`.

**⛔ PLAN MODE PROHIBITION**: Do NOT call EnterPlanMode. This is a requirements-gathering command, NOT an implementation task. EnterPlanMode creates a contract where ExitPlanMode signals "ready to implement" — which conflicts with this command's purpose of writing requirements and stopping.

## Flags

- `--socratic` or `-s`: Use structured 3-round discovery mode (see details file)
- `--rounds N`: Number of rounds (default: 3, max: 5)
- `--skip-validation`: Skip Phase 0 pre-execution validation checks
- `--issue N` or `#N`: Load a GitHub issue as brainstorm context for requirements seeding

## Pre-Flight

```bash
FEATURE=${ZERG_FEATURE:-"$ARGUMENTS"}

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

# Extract issue number from --issue N or #N shorthand
ISSUE_NUM=""
if [[ "$ARGUMENTS" =~ --issue[[:space:]]+([0-9]+) ]]; then
  ISSUE_NUM="${BASH_REMATCH[1]}"
elif [[ "$ARGUMENTS" =~ \#([0-9]+) ]]; then
  ISSUE_NUM="${BASH_REMATCH[1]}"
fi
```

## Phase 0: Pre-Execution Validation

If `--skip-validation` is in $ARGUMENTS, skip this phase entirely and continue to Phase 1.

Before proceeding, validate this plan hasn't been superseded:

1. **Extract Objective**
   - Read `.gsd/specs/$FEATURE/requirements.md` if exists
   - Identify key terms: feature name, main components, file patterns

2. **Check Recent Commits**
   ```bash
   git log --oneline -20 | grep -i "$FEATURE"
   ```
   - Flag if any commits mention the feature name

3. **Check Open PRs**
   ```bash
   gh pr list --state open | grep -i "$FEATURE"
   ```
   - Flag if any open PRs match

4. **Search Codebase**
   - Grep for key implementation patterns from the requirements
   - Flag if substantial matches found (>5 files)

5. **Validation Decision**
   IF any checks flag potential conflicts:
     STOP and present:
     ```
     ⚠️  VALIDATION WARNING

     Potential conflict detected:
     - [Commits/PRs/Code] matching "{feature}" found

     Options:
     1. Update plan - Revise spec to account for existing work
     2. Archive - Move to .gsd/specs/_archived/
     3. Proceed anyway - Override and continue
     ```

     Use AskUserQuestion to get user decision.

   IF validation passes:
     Continue to Phase 1.

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

0. **Check for issue context** — If `--issue N` or `#N` was provided in arguments:
   - Run `gh issue view $ISSUE_NUM` to read the issue
   - Parse title, body, labels, and acceptance criteria
   - Store as issue context for Phase 2
   - Output: "Found GitHub issue #N: '{title}'. Loading brainstorm context from issue body..."
   - If `--issue` not provided, skip this step (backward compatible)

1. **Read PROJECT.md and INFRASTRUCTURE.md** — Understand existing tech stack
2. **Explore Codebase** — List directory structure, read key files, identify patterns
3. **Search for Similar Patterns** — How are existing features structured?

> ⛔ **IMPLEMENTATION GUARD**: You are gathering requirements. DO NOT write code, DO NOT create implementation files, DO NOT design architecture. Stay in requirements-gathering mode.

### Phase 2: Requirements Elicitation

Ask clarifying questions grouped logically. Don't ask everything at once. Cover:
- Problem Space, Functional Requirements, Non-Functional Requirements
- Scope Boundaries, Dependencies, Acceptance Criteria

See details file for full question categories.

> **Issue Context Advisory**: When issue context was loaded in Phase 1, acknowledge what the issue already captured (scope, acceptance criteria, priority, proposed solution). Present a summary: "Issue #N already covers: [list]. Asking about gaps only." Then focus elicitation on areas the issue didn't cover or where plan needs deeper specificity. Use judgment about what's already answered vs. what needs more detail.

### Phase 3: Generate requirements.md

After completing Phases 1-2, proceed directly to writing the requirements document.

Write comprehensive requirements document to `.gsd/specs/{feature}/requirements.md`.

See details file for the full template.

### Phase 4: Infrastructure Requirements

Identify additional infrastructure needs (services, MCP servers, env vars, resources).
Update `.gsd/INFRASTRUCTURE.md` if needed.

> ⛔ **IMPLEMENTATION GUARD**: You are presenting requirements for approval. DO NOT proceed to design or implementation. DO NOT invoke /z:design. DO NOT write any code. After approval, output the PLANNING COMPLETE banner and STOP.

### Phase 5: User Approval

Present requirements for approval, then call AskUserQuestion to capture the decision:

Call AskUserQuestion:
  - question: "Do you approve these requirements?"
  - header: "Approval"
  - options:
    - label: "Approve"
      description: "Lock requirements and stop. You will run /z:design separately."
    - label: "Request changes"
      description: "Describe what needs to change"

User replies with:
- "APPROVED" / "Approve" — requirements are complete and locked
- "REJECTED" / "Request changes" — describe what needs to change
- Specific questions or concerns

---

### Phase 5.5: Post-Approval Handoff

After the user replies "APPROVED":

1. First, call TaskUpdate to mark the plan task `completed`
2. Update requirements.md with `Status: APPROVED` (use Write tool — this is a .gsd/ file)
3. Write the sentinel file:
   ```bash
   echo "$(date -Iseconds)" > ".gsd/specs/$FEATURE/.plan-complete"
   ```
4. Then use AskUserQuestion to prompt the user for next steps:

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
  --skip-validation     Skip pre-execution validation checks
  --issue N             Load GitHub issue N as brainstorm context
  --help                Show this help message
```
