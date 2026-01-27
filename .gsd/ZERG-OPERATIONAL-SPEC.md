# ZERG Operational Specification v2.0

> Zero-Effort Rapid Growth: Parallel Claude Code execution through Task orchestration, GSD methodology, and devcontainer isolation.

---

## Core Architecture

ZERG combines three systems:

1. **Claude Code Tasks** — The tracking and coordination layer. Tasks persist across sessions, support dependencies, and enable parallel execution.
2. **GSD Methodology** — Spec-driven development with fresh subagent contexts per task, eliminating context rot.
3. **Devcontainers + Git Worktrees** — Isolated execution environments preventing merge conflicts and ensuring reproducibility.

```
┌─────────────────────────────────────────────────────────────┐
│                    ZERG ORCHESTRATOR                        │
│  (.zerg/orchestrator.py)                                    │
├─────────────────────────────────────────────────────────────┤
│  Claude Code Task List (CLAUDE_CODE_TASK_LIST_ID)           │
│  ├── Task: L0-001 (pending → in_progress → completed)       │
│  ├── Task: L0-002 (pending → in_progress → blocked)         │
│  └── Task: L1-001 (pending, depends: L0-*)                  │
├─────────────────────────────────────────────────────────────┤
│  Git Worktrees              │  Devcontainer Instances       │
│  .zerg-worktrees/           │  worker-001 (port 49200)      │
│  ├── feature-x/worker-001/  │  worker-002 (port 49201)      │
│  └── feature-x/worker-002/  │  worker-003 (port 49202)      │
└─────────────────────────────────────────────────────────────┘
```

---

## Directory Structure

ZERG creates and manages these directories:

```
project-root/
├── .zerg/
│   ├── orchestrator.py          # Worker fleet management
│   ├── config.yaml              # ZERG configuration
│   └── worktrees/               # Git worktree mount points
│       └── {feature}/
│           └── worker-{N}/      # Each worker's isolated checkout
│
├── .gsd/
│   ├── PROJECT.md               # Project charter and vision
│   ├── INFRASTRUCTURE.md        # Stack detection results
│   ├── specs/
│   │   └── {feature}/
│   │       ├── REQUIREMENTS.md  # User stories and acceptance criteria
│   │       ├── ARCHITECTURE.md  # Technical design and interfaces
│   │       ├── tasks/
│   │       │   ├── L0-001.md    # Level 0 task specification
│   │       │   ├── L0-002.md
│   │       │   └── L1-001.md    # Level 1 task (depends on L0)
│   │       └── COMPLETION.md    # Post-execution summary
│   └── STATE.md                 # Living memory across sessions
│
├── .claude/
│   ├── commands/
│   │   ├── zerg:init.md         # Initialize ZERG infrastructure
│   │   ├── zerg:plan.md         # Requirements elicitation
│   │   ├── zerg:design.md       # Architecture and task generation
│   │   ├── zerg:rush.md         # Launch parallel workers
│   │   ├── zerg:status.md       # Check worker progress
│   │   └── zerg:worker.md       # Worker execution protocol
│   ├── agents/
│   │   ├── scout.md             # Read-only reconnaissance
│   │   ├── architect.md         # Design and task decomposition
│   │   ├── worker.md            # Implementation specialist
│   │   └── gatekeeper.md        # Quality verification
│   └── rules/
│       ├── security-python.md   # Stack-specific security rules
│       ├── security-node.md
│       └── security-general.md
│
└── .devcontainer/
    ├── devcontainer.json        # Container configuration
    ├── Dockerfile               # Worker image definition
    └── docker-compose.yaml      # Multi-worker orchestration
```

---

## Phase 1: Initialization (`/zerg:init`)

### Purpose
Initialize ZERG for a project. Operates in two modes based on directory state.

### Mode Detection

The `is_empty_project()` function in `zerg/commands/init.py` determines the initialization mode:

```python
# Project indicators that trigger Discovery Mode
PROJECT_INDICATORS = {
    ".git", "pyproject.toml", "package.json", "go.mod", "Cargo.toml",
    "src", "lib", "app", "pom.xml", "Gemfile", "*.csproj", "*.sln"
}

def is_empty_project(path: Path | None = None) -> bool:
    """Check if directory is empty (no code/config files)."""
    # Returns True for Inception Mode, False for Discovery Mode
```

### Inception Mode (Empty Directory)

When `is_empty_project()` returns `True`, ZERG runs the Inception Mode workflow:

1. **Requirements Gathering** (`gather_requirements()`) - Interactive prompts via Rich console
2. **Technology Selection** (`select_technology()`) - Recommends and confirms language/framework
3. **Project Scaffolding** (`scaffold_project()`) - Generates project structure from templates
4. **Git Initialization** - Creates initial commit

**Key files:**
- `zerg/charter.py` - `ProjectCharter` dataclass, `gather_requirements()`, `write_project_md()`
- `zerg/tech_selector.py` - `TechStack` dataclass, `recommend_stack()`, `select_technology()`
- `zerg/inception.py` - `scaffold_project()`, `run_inception_mode()` orchestrator
- `zerg/scaffolds/{language}/` - Template files for each supported language

**Supported Languages:**
- Python (fastapi, flask, typer, click)
- TypeScript (fastify, express, hono, commander)
- Go (gin, echo, cobra)
- Rust (axum, actix-web, clap)

### Discovery Mode (Existing Project)

When `is_empty_project()` returns `False`, ZERG runs Discovery Mode.

### Execution Model
Spawn a **read-only scout subagent** using Claude's Task tool. The scout cannot modify files.

```xml
<subagent name="scout" tools="Read, Glob, Grep" model="haiku">
  Scan the project directory for infrastructure markers.
  Return a structured assessment of what exists.
  Do not create or modify any files.
</subagent>
```

### Fork: Empty Directory vs Existing Project

**Empty Directory Path:**
1. Scout returns empty assessment
2. Orchestrator initiates conversational requirements gathering
3. Questions focus on: problem domain, users, constraints, integrations
4. Capture responses in `.gsd/PROJECT.md`
5. Select technology stack based on requirements
6. Generate project scaffold atomically
7. Generate devcontainer matching selected stack
8. Inject secure coding rules from `TikiTribe/claude-secure-coding-rules`
9. Initialize git repository with inception commit

**Existing Project Path:**
1. Scout returns populated assessment
2. Spawn parallel discovery subagents (up to 10 concurrent):

```xml
<task id="discovery-stack" type="background">
  <agent>scout</agent>
  <objective>Analyze technology stack and dependencies</objective>
  <output>.gsd/INFRASTRUCTURE.md#stack</output>
</task>

<task id="discovery-arch" type="background">
  <agent>scout</agent>
  <objective>Map architecture patterns and directory structure</objective>
  <output>.gsd/INFRASTRUCTURE.md#architecture</output>
</task>

<task id="discovery-quality" type="background">
  <agent>scout</agent>
  <objective>Identify test coverage, linting, CI configuration</objective>
  <output>.gsd/INFRASTRUCTURE.md#quality</output>
</task>

<task id="discovery-security" type="background">
  <agent>scout</agent>
  <objective>Audit security configurations and secret handling</objective>
  <output>.gsd/INFRASTRUCTURE.md#security</output>
</task>
```

3. Wait for all discovery tasks to complete
4. Synthesize findings into `.gsd/INFRASTRUCTURE.md`
5. Generate devcontainer matching detected stack
6. Inject stack-appropriate secure coding rules
7. Preserve existing tooling configuration

### Outputs
- `.gsd/PROJECT.md` — Project charter (new projects)
- `.gsd/INFRASTRUCTURE.md` — Infrastructure assessment (existing projects)
- `.devcontainer/` — Configured development container
- `.claude/rules/` — Security constraints for workers

### Verification
```bash
# Devcontainer builds successfully
docker build -f .devcontainer/Dockerfile -t zerg-worker .

# Security rules present
test -f .claude/rules/security-*.md

# Project documentation exists
test -f .gsd/PROJECT.md || test -f .gsd/INFRASTRUCTURE.md
```

---

## Phase 2: Planning (`/zerg:plan`)

### Purpose
Transform a feature request into a precise specification with acceptance criteria and verification commands.

### Execution Model
Spawn a **product owner subagent** for requirements elicitation.

```xml
<subagent name="product-owner" tools="Read, Write" model="sonnet">
  You are a product owner conducting requirements elicitation.
  
  Given the user's feature description:
  1. Ask clarifying questions to resolve ambiguity
  2. Identify edge cases and error conditions
  3. Extract measurable acceptance criteria
  4. Define verification commands that prove completion
  
  Produce a REQUIREMENTS.md following the GSD specification format.
</subagent>
```

### Requirements Document Format

```markdown
# Feature: {feature-name}

## Problem Statement
{Why this feature exists. What user need it addresses.}

## User Stories

### Story 1: {Actor} can {action}
**As a** {role}
**I want** {capability}
**So that** {benefit}

**Acceptance Criteria:**
- [ ] {Specific, measurable criterion}
- [ ] {Another criterion}

**Verification:**
```bash
{Command that proves this story is complete}
```

## Constraints
- {Technical constraint}
- {Business constraint}

## Out of Scope
- {Explicitly excluded functionality}

## Dependencies
- {External system or feature this depends on}
```

### Outputs
- `.gsd/specs/{feature}/REQUIREMENTS.md`
- Updated `.gsd/STATE.md` with planning checkpoint

### Verification
```bash
# Requirements document exists and is non-empty
test -s .gsd/specs/{feature}/REQUIREMENTS.md

# All acceptance criteria have verification commands
grep -c "Verification:" .gsd/specs/{feature}/REQUIREMENTS.md
```

---

## Phase 3: Design (`/zerg:design`)

### Purpose
Transform requirements into a technical architecture and decompose into atomic, parallelizable tasks with exclusive file ownership.

### Execution Model
Spawn an **architect subagent** to produce the design.

```xml
<subagent name="architect" tools="Read, Write, Glob" model="sonnet">
  You are a software architect designing for parallel execution.
  
  Given REQUIREMENTS.md:
  1. Determine file structure and component boundaries
  2. Define interfaces between components
  3. Generate stub files with signatures but no implementation
  4. Decompose into atomic tasks with exclusive file ownership
  5. Assign dependency levels (L0, L1, L2, L3, L4)
  
  Critical constraint: No two tasks may modify the same file.
</subagent>
```

### Task Specification Format

Each task is a separate markdown file following GSD's XML structure:

```markdown
# Task: {task-id}

## Metadata
- **Level:** {0-4}
- **Dependencies:** {comma-separated task IDs or "none"}
- **Files (exclusive):** {files this task owns}
- **Estimated tokens:** {rough implementation size}

## Specification

<task type="auto" id="{task-id}">
  <name>{Descriptive task name}</name>
  <level>{0-4}</level>
  <depends>{task-ids or empty}</depends>
  <files>{exclusive file list}</files>
  
  <context>
    {What the worker needs to understand before implementing}
  </context>
  
  <action>
    {Precise implementation instructions}
  </action>
  
  <verify>
    {Bash command that returns 0 on success}
  </verify>
  
  <done>
    {Human-readable completion criteria}
  </done>
</task>

## Interface Contract
{TypeScript/Python interface this task must implement}

## Security Requirements
{Specific security constraints from .claude/rules/}
```

### Level Definitions

| Level | Purpose | Dependencies | Parallelism |
|-------|---------|--------------|-------------|
| L0 | Foundations | None | All L0 tasks run in parallel |
| L1 | Core logic | L0 complete | All L1 tasks run in parallel |
| L2 | Integration | L1 complete | All L2 tasks run in parallel |
| L3 | Consumers | L2 complete | All L3 tasks run in parallel |
| L4 | Verification | L3 complete | All L4 tasks run in parallel |

### Stub Generation

The architect generates stub files that:
- Compile and type-check
- Define interfaces workers implement against
- Allow workers to import dependencies before peers complete

```python
# Example stub: src/services/auth.py
from typing import Protocol

class AuthService(Protocol):
    """Authentication service interface. Implementation in L1-003."""
    
    async def authenticate(self, credentials: Credentials) -> AuthResult:
        """Validate credentials and return auth result."""
        ...
    
    async def refresh_token(self, token: str) -> str:
        """Refresh an expired token."""
        ...
```

### Outputs
- `.gsd/specs/{feature}/ARCHITECTURE.md`
- `.gsd/specs/{feature}/tasks/L{N}-{NNN}.md` for each task
- Stub files in source tree
- Updated `.gsd/STATE.md` with design checkpoint

### Verification
```bash
# Architecture document exists
test -s .gsd/specs/{feature}/ARCHITECTURE.md

# Task files exist for each level
ls .gsd/specs/{feature}/tasks/L*.md | wc -l

# No file appears in multiple tasks
find .gsd/specs/{feature}/tasks/ -name "*.md" -exec grep -h "<files>" {} \; | \
  tr ',' '\n' | sort | uniq -d | wc -l  # Should be 0

# Stubs compile
{language-specific-compile-check}
```

---

## Phase 4: Execution (`/zerg:rush`)

### Purpose
Launch parallel workers to implement all tasks in a level, enforce quality gates at level boundaries, and merge completed work.

### Execution Model

The orchestrator coordinates workers through Claude's Task tool and isolated devcontainers.

```
┌─────────────────────────────────────────────────────────────┐
│  /zerg:rush {feature}                                       │
├─────────────────────────────────────────────────────────────┤
│  1. Read task graph from .gsd/specs/{feature}/tasks/        │
│  2. Identify all L0 tasks                                   │
│  3. For each L0 task:                                       │
│     a. Create git worktree                                  │
│     b. Launch devcontainer instance                         │
│     c. Create Claude Task with worker subagent              │
│     d. Inject task specification as initial prompt          │
│  4. Monitor Task status via /tasks                          │
│  5. When all L0 complete: run quality gates                 │
│  6. If gates pass: merge to staging, proceed to L1          │
│  7. Repeat until all levels complete                        │
└─────────────────────────────────────────────────────────────┘
```

### Worker Provisioning Sequence

For each task in the current level:

```bash
# 1. Create git worktree
git worktree add .zerg/worktrees/{feature}/worker-{N} \
  -b zerg/{feature}/worker-{N}

# 2. Launch devcontainer with worker identity
ZERG_WORKER_ID={N} \
ZERG_FEATURE={feature} \
ZERG_TASK_ID={task-id} \
CLAUDE_CODE_TASK_LIST_ID={feature} \
docker-compose -f .devcontainer/docker-compose.yaml up -d worker-{N}

# 3. Execute Claude Code inside container with worker agent
docker exec worker-{N} claude --agent worker \
  "Execute task {task-id} per .gsd/specs/{feature}/tasks/{task-id}.md"
```

### Worker Execution Protocol

Each worker follows this protocol (defined in `.claude/agents/worker.md`):

```xml
<agent name="worker">
  <description>Implementation specialist executing atomic tasks</description>
  <tools>Read, Write, Edit, Bash, Grep, Glob</tools>
  <model>sonnet</model>
  
  <protocol>
    1. Read task specification from .gsd/specs/{feature}/tasks/{task-id}.md
    2. Read any dependency stubs from the stub files
    3. Read security rules from .claude/rules/
    4. Implement the solution in the files listed in <files>
    5. Write tests that verify acceptance criteria
    6. Run the <verify> command
    7. If verification fails:
       a. Analyze the failure
       b. Fix the implementation
       c. Retry (max 3 attempts)
    8. If verification passes:
       a. Commit to worker branch with message: "feat({task-id}): {name}"
       b. Update Claude Task status to "completed"
    9. If all retries exhausted:
       a. Update Claude Task status to "blocked"
       b. Write failure analysis to task file
  </protocol>
  
  <constraints>
    - Modify ONLY files listed in task <files> section
    - Do NOT spawn subagents (no nesting allowed)
    - Do NOT access network except for package installation
    - Follow all security rules in .claude/rules/
  </constraints>
</agent>
```

### Task Status Management

Workers update Claude Task status throughout execution:

| Status | Meaning |
|--------|---------|
| `pending` | Task created, worker not yet assigned |
| `in_progress` | Worker actively implementing |
| `completed` | Verification passed, committed |
| `blocked` | Failed after max retries |

The orchestrator queries task status via `/tasks` command:

```bash
# Check all tasks for feature
claude "/tasks" --filter "list_id={feature}"
```

### Quality Gates at Level Boundaries

When all tasks in a level reach `completed` or `blocked`:

```bash
# 1. Merge worker branches to staging
git checkout -b staging/{feature}
for branch in $(git branch --list "zerg/{feature}/worker-*"); do
  git merge --no-ff $branch -m "Merge $branch"
done

# 2. Run quality checks
npm run lint          # or: ruff check, cargo clippy
npm run typecheck     # or: mypy, cargo check  
npm run test          # all tests, coverage threshold
semgrep --config=auto # security scan

# 3. Evaluate gate results
if [ $? -eq 0 ]; then
  git checkout main
  git merge --no-ff staging/{feature} -m "Level {N}: {feature}"
  # Proceed to next level
else
  # Spawn remediation workers for failing checks
  # Re-run gates after remediation
fi
```

### Gate Failure Remediation

If gates fail, the orchestrator:

1. Identifies which worker produced failing code
2. Extracts the specific failure (lint error, test failure, security finding)
3. Spawns a remediation subagent with failure context:

```xml
<task id="remediate-{task-id}" type="foreground">
  <agent>worker</agent>
  <context>
    Task {task-id} failed quality gate.
    Failure: {specific error message}
    File: {affected file}
  </context>
  <action>Fix the quality gate failure</action>
  <verify>{re-run the failing check}</verify>
</task>
```

### Outputs
- Atomic commits per task on worker branches
- Merged commits per level on main
- `.gsd/specs/{feature}/COMPLETION.md` with execution summary

### Verification
```bash
# All tasks completed or explicitly blocked
claude "/tasks" --filter "list_id={feature}" | grep -v "completed\|blocked" | wc -l
# Should be 0

# Main branch contains all merged work
git log --oneline main | grep "Level.*{feature}"

# All tests pass on main
git checkout main && npm test
```

---

## Coordination via Claude Tasks

### Task List Configuration

All workers in a feature share a task list:

```bash
export CLAUDE_CODE_TASK_LIST_ID="{feature}"
```

This enables:
- Shared state across terminal sessions
- Status visibility via `/tasks`
- Dependency tracking between tasks

### Task Creation

The orchestrator creates Claude Tasks for each ZERG task:

```javascript
// Conceptual - orchestrator creates tasks via Claude Code
{
  id: "L0-001",
  list_id: "{feature}",
  status: "pending",
  dependencies: [],
  metadata: {
    level: 0,
    files: ["src/types/auth.ts"],
    worker_id: null
  }
}
```

### Parallelism Limits

Claude Code supports up to 10 concurrent background tasks. The orchestrator:
- Launches tasks in batches of 10
- Queues remaining tasks
- Promotes queued tasks as slots free up

For features with >10 tasks per level, execution is batched:

```
L0 tasks: [1,2,3,4,5,6,7,8,9,10] → [11,12,13,14,15] → ...
                 batch 1                  batch 2
```

### Background vs Foreground Execution

| Mode | When to Use |
|------|-------------|
| Background (`Ctrl+B`) | Independent implementation tasks |
| Foreground | Tasks requiring user interaction or MCP tools |

**Note:** MCP tools do not work in background agents. If a task requires MCP access (e.g., database operations), it must run in foreground.

---

## Devcontainer Isolation

### Container Configuration

Each worker runs in an isolated devcontainer:

```json
// .devcontainer/devcontainer.json
{
  "name": "zerg-worker",
  "dockerComposeFile": "docker-compose.yaml",
  "service": "worker",
  "workspaceFolder": "/workspace",
  
  "containerEnv": {
    "ZERG_WORKER_ID": "${localEnv:ZERG_WORKER_ID}",
    "ZERG_FEATURE": "${localEnv:ZERG_FEATURE}",
    "ZERG_TASK_ID": "${localEnv:ZERG_TASK_ID}",
    "CLAUDE_CODE_TASK_LIST_ID": "${localEnv:CLAUDE_CODE_TASK_LIST_ID}"
  },
  
  "mounts": [
    "source=${localWorkspaceFolder}/.gsd/specs,target=/specs,type=bind,readonly",
    "source=${localWorkspaceFolder}/.claude/rules,target=/rules,type=bind,readonly"
  ],
  
  "features": {
    "ghcr.io/devcontainers/features/git:1": {},
    "ghcr.io/devcontainers/features/node:1": {},
    "ghcr.io/devcontainers/features/python:1": {}
  }
}
```

### Docker Compose for Multi-Worker

```yaml
# .devcontainer/docker-compose.yaml
version: '3.8'

services:
  worker:
    build:
      context: .
      dockerfile: Dockerfile
    volumes:
      - ../:/workspace:cached
      - specs:/specs:ro
      - rules:/rules:ro
    environment:
      - ZERG_WORKER_ID
      - ZERG_FEATURE
      - ZERG_TASK_ID
      - CLAUDE_CODE_TASK_LIST_ID
    networks:
      - zerg-net
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G

networks:
  zerg-net:
    driver: bridge

volumes:
  specs:
  rules:
```

### Port Assignment

Workers requiring network access receive ports from the ephemeral range:

```python
# .zerg/orchestrator.py (excerpt)
import random

class PortAllocator:
    EPHEMERAL_START = 49152
    EPHEMERAL_END = 65535
    
    def __init__(self):
        self.allocated = set()
    
    def allocate(self) -> int:
        while True:
            port = random.randint(self.EPHEMERAL_START, self.EPHEMERAL_END)
            if port not in self.allocated:
                self.allocated.add(port)
                return port
    
    def release(self, port: int):
        self.allocated.discard(port)
```

---

## Security Integration

### Rule Injection

During initialization, ZERG injects security rules based on detected stack:

| Stack | Rules Source |
|-------|--------------|
| Python | `security-python.md`: OWASP Top 10, SQL injection, auth patterns |
| Node.js | `security-node.md`: XSS prevention, CSP, dependency auditing |
| General | `security-general.md`: Secret handling, input validation |

Rules are mounted read-only in worker containers at `/rules/`.

### Worker Security Constraints

Workers inherit security constraints via their agent definition:

```markdown
<!-- .claude/agents/worker.md (security section) -->

## Security Requirements

Before implementing any task, read and internalize:
- /rules/security-general.md
- /rules/security-{stack}.md

You MUST:
- Never hardcode secrets, API keys, or credentials
- Validate all user input at system boundaries
- Use parameterized queries for all database operations
- Escape output in HTML/template contexts
- Apply principle of least privilege for file/network access

You MUST NOT:
- Disable security linters or static analysis
- Suppress security warnings without documented justification
- Use eval(), exec(), or dynamic code execution
- Store sensitive data in logs or error messages
```

### Gate Enforcement

Quality gates include security scanning:

```bash
# Security gate checks
semgrep --config=p/security-audit --error
npm audit --audit-level=high  # or: pip-audit, cargo audit
gitleaks detect --source .
```

---

## State Management

### Spec Files as Memory

Workers are stateless. All coordination flows through spec files:

| File | Purpose | Writer | Readers |
|------|---------|--------|---------|
| `PROJECT.md` | Vision and constraints | User/Init | All agents |
| `REQUIREMENTS.md` | Acceptance criteria | Planner | Architect, Workers |
| `ARCHITECTURE.md` | Technical design | Architect | Workers |
| `tasks/*.md` | Implementation specs | Architect | Workers |
| `STATE.md` | Progress and decisions | Orchestrator | All agents |

### Session Resumption

If execution is interrupted:

```bash
# Check current state
claude "/zerg:status"

# Resume from last checkpoint
claude "/zerg:rush {feature} --resume"
```

The orchestrator:
1. Reads `.gsd/STATE.md` for last completed level
2. Queries Claude Task list for task statuses
3. Resumes workers for `pending` or `in_progress` tasks
4. Skips `completed` tasks

### STATE.md Format

```markdown
# ZERG State: {feature}

## Current Phase
- **Phase:** Execution
- **Level:** 2 of 4
- **Started:** 2026-01-26T10:30:00Z
- **Last Update:** 2026-01-26T11:45:00Z

## Task Progress

| Task ID | Status | Worker | Duration | Notes |
|---------|--------|--------|----------|-------|
| L0-001 | completed | 1 | 2m 34s | |
| L0-002 | completed | 2 | 3m 12s | |
| L1-001 | completed | 3 | 4m 01s | |
| L1-002 | blocked | 4 | - | Type error in interface |
| L2-001 | pending | - | - | Blocked by L1-002 |

## Decisions
- 2026-01-26: Selected PostgreSQL over SQLite for concurrent access
- 2026-01-26: Using bcrypt for password hashing per security rules

## Blockers
- L1-002: Interface mismatch between AuthService and UserRepository
  - Root cause: Missing async annotation in stub
  - Resolution: Manual fix applied, re-running worker
```

---

## Command Reference

### `/zerg:init`
Initialize ZERG infrastructure for a project.

```
Usage: /zerg:init [--force]

Options:
  --force    Reinitialize even if .zerg/ exists

Outputs:
  .zerg/           Orchestrator and configuration
  .gsd/            Spec directory structure
  .claude/         Commands, agents, and rules
  .devcontainer/   Worker container configuration
```

### `/zerg:plan`
Elicit requirements for a feature.

```
Usage: /zerg:plan {feature-name}

Arguments:
  feature-name    Identifier for the feature (kebab-case)

Outputs:
  .gsd/specs/{feature}/REQUIREMENTS.md
```

### `/zerg:design`
Generate architecture and task decomposition.

```
Usage: /zerg:design {feature-name}

Arguments:
  feature-name    Feature to design (must have REQUIREMENTS.md)

Outputs:
  .gsd/specs/{feature}/ARCHITECTURE.md
  .gsd/specs/{feature}/tasks/L*.md
  Stub files in source tree
```

### `/zerg:rush`
Launch parallel workers for a feature.

```
Usage: /zerg:rush {feature-name} [--level N] [--resume] [--dry-run]

Arguments:
  feature-name    Feature to execute

Options:
  --level N       Start from specific level (default: 0)
  --resume        Resume from last checkpoint
  --dry-run       Show execution plan without running

Outputs:
  Git commits on worker branches
  Merged commits on main
  .gsd/specs/{feature}/COMPLETION.md
```

### `/zerg:status`
Check worker and task status.

```
Usage: /zerg:status [--feature {name}] [--verbose]

Options:
  --feature       Filter to specific feature
  --verbose       Show detailed worker logs

Outputs:
  Task status table
  Active worker count
  Current level progress
```

### `/zerg:worker`
Worker execution protocol (invoked by orchestrator, not directly).

```
Usage: /zerg:worker {task-id}

Arguments:
  task-id    Task specification to execute

Protocol:
  1. Read task spec
  2. Implement solution
  3. Run verification
  4. Commit or report blocked
```

---

## Error Handling

### Worker Failure

If a worker fails verification 3 times:

1. Task status set to `blocked`
2. Failure analysis written to task file
3. Orchestrator continues with remaining tasks
4. Level completion waits for manual intervention or skip

### Merge Conflict

Merge conflicts indicate task decomposition failure (overlapping file ownership):

1. Orchestrator halts execution
2. Conflict details written to `.gsd/STATE.md`
3. User must resolve conflict or regenerate tasks

### Container Crash

If a worker container crashes:

1. Orchestrator detects via health check failure
2. Task status remains `in_progress`
3. Orchestrator spawns replacement worker
4. New worker resumes from last committed state

---

## Verification Checklist

Before reporting a feature complete:

- [ ] All tasks in `completed` status
- [ ] All quality gates passed
- [ ] All levels merged to main
- [ ] Tests pass on main branch
- [ ] COMPLETION.md generated
- [ ] No `blocked` tasks without resolution

---

## Version

- **Spec Version:** 2.0
- **Last Updated:** 2026-01-26
- **Maintainer:** ZERG Development Team
