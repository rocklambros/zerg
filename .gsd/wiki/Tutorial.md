# Tutorial: Building "Minerals Store" with ZERG

This tutorial guides you through building a complete application using ZERG's parallel execution system. By the end, you'll understand not just what commands to run, but why each phase exists and how they work together.

## What You'll Build

A Starcraft 2 themed ecommerce store called "Minerals Store" - a REST API with a web frontend where players from different factions (Protoss, Terran, Zerg) can browse and purchase mineral products.

## What You'll Learn

| Phase | Concept | Skill |
|-------|---------|-------|
| Init | Project scaffolding | How ZERG bootstraps a new codebase |
| Brainstorm | Requirements discovery | How to capture what you actually need |
| Plan | Structured requirements | How ZERG turns ideas into specifications |
| Design | Architecture generation | How tasks get created with file ownership |
| Rush | Parallel execution | How workers coordinate without conflicts |
| Monitor | Progress tracking | How to see what's happening |
| Ship | Integration | How branches merge safely |

---

## Prerequisites

Before starting, let's verify your environment. Each tool serves a specific purpose in the ZERG workflow:

| Requirement | Check Command | Why You Need It |
|-------------|---------------|-----------------|
| Python 3.12+ | `python --version` | ZERG's orchestration is written in Python |
| Git 2.x+ | `git --version` | Workers use git worktrees for isolation |
| Claude Code CLI | `claude --version` | Each worker is a Claude Code instance |
| Docker 20.x+ | `docker info` | Container mode provides full isolation |
| API Key | `echo $ANTHROPIC_API_KEY` | Workers authenticate to Claude API |

**Install ZERG:**

```bash
git clone https://github.com/rocklambros/zerg.git
cd zerg && pip install -e ".[dev]"
zerg --help
```

---

## Phase 1: Initialize Project

### Concept

Initialization creates the infrastructure ZERG needs to coordinate parallel workers. Think of it as setting up a construction site before any building starts - you need roads, utilities, and a site office before workers arrive.

### Narrative

Without initialization, workers would have nowhere to store their state, no configuration to read, and no security rules to follow. The init phase detects your project type, creates appropriate scaffolding, and sets up the coordination infrastructure.

### Diagram

```
Empty Directory                     Initialized Project
      |                                    |
      v                                    v
+------------+                    +------------------+
|            |    /zerg:init      | minerals-store/  |
|   (empty)  | =================> |   .zerg/         | <-- Worker coordination
|            |                    |   .gsd/          | <-- Specs and docs
+------------+                    |   .claude/rules/ | <-- Security rules
                                  |   .devcontainer/ | <-- Container configs
                                  |   CLAUDE.md      | <-- Project context
                                  +------------------+
```

### Command

Create your project directory and initialize ZERG:

```bash
mkdir minerals-store && cd minerals-store
```

Inside Claude Code:

```
/zerg:init --security standard
```

**What happens:**

1. ZERG detects an empty directory and enters "Inception Mode"
2. An interactive wizard gathers your project requirements
3. Technology stack recommendation is generated based on your answers
4. Project scaffold is created with appropriate structure
5. Security rules are fetched for your detected stack
6. Configuration files are written

**Expected output:**

```
ZERG Init - Inception Mode
Empty directory detected. Starting new project wizard...

Project name: minerals-store
Description: Starcraft 2 themed ecommerce API
Platforms: api, web
Architecture: monolith

+-- Recommended Stack ----------------------------------------+
| Backend: Python 3.12, FastAPI, SQLAlchemy async, PostgreSQL |
| Frontend: Vanilla JS, Vite, Tailwind CSS                    |
| Testing: pytest, Playwright                                 |
+------------------------------------------------------------+

Accept? [Y/n]: y

OK Created 8 scaffold files
OK Created .gsd/PROJECT.md
OK Initialized git repository
OK Created initial commit

Continuing to Discovery Mode...

OK Created .zerg/config.yaml
OK Created .devcontainer/
OK Fetched security rules: owasp-2025.md, python.md, javascript.md
OK Updated CLAUDE.md

ZERG initialized!
```

---

## Phase 2: Brainstorm (Optional)

### Concept

Brainstorming is a structured discovery process where ZERG asks questions to help you clarify what you're building. It's optional - skip it if your requirements are already clear.

### Narrative

Many projects fail not from bad code but from misunderstood requirements. Brainstorming forces you to think through the problem space before writing solutions. ZERG uses Socratic questioning - asking probing questions that reveal hidden assumptions.

### Diagram

```
         +-------------+
         |   Vague     |
         |   Idea      |
         +------+------+
                |
                v
+--------------------------------+
|   ROUND 1: Problem Space       |
|   - What problem exists?       |
|   - Who has this problem?      |
|   - How do they cope today?    |
+---------------+----------------+
                |
                v
+--------------------------------+
|   ROUND 2: Solution Space      |
|   - What would ideal look like?|
|   - What constraints exist?    |
|   - What's non-negotiable?     |
+---------------+----------------+
                |
                v
+--------------------------------+
|   ROUND 3: Implementation      |
|   - What technologies fit?     |
|   - What risks exist?          |
|   - How will you verify?       |
+---------------+----------------+
                |
                v
         +------+------+
         |  Structured |
         |  Insights   |
         +-------------+
```

### Simulated Dialogue

When you run `/zerg:brainstorm --socratic`, ZERG asks questions and you provide answers. Here's how a typical session looks:

```
ROUND 1: PROBLEM SPACE

ZERG: What specific problem does the minerals store solve for users?
YOU:  Players need a marketplace for trading minerals and vespene gas between factions.

ZERG: Who are the primary users and what makes them different?
YOU:  Three factions: Protoss prefer high-value items, Terrans want bulk deals,
      Zerg need rapid resource acquisition. Each has different discount structures.

ZERG: How do users currently solve this problem?
YOU:  They don't - there's no themed marketplace. Generic stores exist but lack
      faction-specific features and the SC2 aesthetic.

ROUND 2: SOLUTION SPACE

ZERG: What would the ideal solution look like from a user's perspective?
YOU:  Browse products by category, see faction-specific pricing, add to cart,
      checkout with faction loyalty applied. Fast, themed, no account required
      for browsing.

ZERG: What are the absolute non-negotiables for this solution?
YOU:  Faction discounts must apply automatically. Passwords must be hashed.
      No raw SQL queries - everything parameterized.

ZERG: What is explicitly OUT of scope?
YOU:  Real payment processing, email notifications, admin dashboard, mobile app.

ROUND 3: IMPLEMENTATION SPACE

ZERG: What technology constraints or preferences exist?
YOU:  Python backend (team knows it), REST API, PostgreSQL, simple vanilla JS
      frontend - no React complexity.

ZERG: What's the verification strategy?
YOU:  Unit tests for business logic, integration tests for API, E2E with
      Playwright for critical user flows.
```

### Command

```
/zerg:brainstorm --socratic
```

**Output location:** `.gsd/specs/brainstorm-session.md`

---

## Phase 3: Plan Feature

### Concept

Planning transforms brainstorm insights (or your direct input) into a structured requirements document. This document becomes the contract that workers follow - they don't improvise, they implement exactly what the spec says.

### Narrative

The plan phase exists to create a single source of truth. Without it, four parallel workers might each interpret "shopping cart" differently. The requirements document removes ambiguity by explicitly stating what "done" looks like.

### Diagram

```
+------------------+       +-------------------+       +------------------+
|  Your Answers    |  ==>  |   requirements.md |  ==>  |  Worker Contract |
|  (interactive)   |       |   Status: DRAFT   |       |  "Build THIS"    |
+------------------+       +-------------------+       +------------------+
                                    |
                                    v
                           +-------------------+
                           |   Status: APPROVED|
                           |   (you edit file) |
                           +-------------------+
                                    |
                                    v
                           Workers can execute
```

### Simulated Dialogue

Running `/zerg:plan minerals-store` starts an interactive session:

```
ZERG: Describe your ideal solution in 2-3 sentences.
YOU:  A FastAPI backend serving product data with faction-based pricing.
      Vanilla JS frontend with Starcraft 2 theming. Cart persists in
      localStorage, checkout creates orders in PostgreSQL.

ZERG: What are the non-negotiable requirements?
YOU:  1. Faction discounts (Protoss: 10%, Terran: 15% bulk, Zerg: 5% speed)
      2. bcrypt for password hashing, never plaintext
      3. All SQL through ORM, parameterized queries only
      4. Products have name, description, price, faction_affinity

ZERG: What is explicitly OUT of scope for this feature?
YOU:  Real payment gateway (use mock). Email notifications. Admin panel.
      User reviews. Inventory management. Mobile app.

ZERG: How will you verify the feature works correctly?
YOU:  - Unit tests for pricing calculations
      - Integration tests for API endpoints
      - E2E tests for browse -> cart -> checkout flow
      - Security scan for OWASP Top 10

ZERG: What existing code or patterns should workers follow?
YOU:  None - greenfield. But follow FastAPI best practices from docs.
      Use Pydantic for validation. SQLAlchemy 2.0 async style.
```

### Command

```
/zerg:plan minerals-store
```

**What happens:**

1. ZERG asks structured questions about your feature
2. Answers are synthesized into `.gsd/specs/minerals-store/requirements.md`
3. Status is set to `DRAFT` - workers will not execute yet

**After planning, approve the requirements:**

Open `.gsd/specs/minerals-store/requirements.md` and change:
```
Status: DRAFT
```
to:
```
Status: APPROVED
```

Workers will not start until you approve. This is your last chance to review before parallel execution begins.

---

## Phase 4: Design Architecture

### Concept

Design reads your approved requirements and generates two things: an architecture document explaining how the system fits together, and a task graph that breaks work into atomic pieces with exclusive file ownership.

### Narrative

This is where ZERG's parallel execution magic happens. The design phase doesn't just plan code structure - it plans how to divide work so multiple workers can execute simultaneously without stepping on each other's toes. Each task "owns" specific files, eliminating merge conflicts by design.

### Diagram

```
requirements.md                    design.md
     |                                 |
     |   /zerg:design                  |  Components, APIs,
     +----------+----------+           |  Data Models, Security
                |                      |
                v                      v
     +--------------------+     +-------------+
     |   task-graph.json  |     | How system  |
     |                    |     | fits together|
     | Level 1: [A, B, C] |     +-------------+
     | Level 2: [D, E, F] |
     | Level 3: [G, H]    |
     +--------------------+
              |
              v
     +--------------------+
     | Each task owns:    |
     | - Files to create  |
     | - Files to modify  |
     | - Files to read    |
     | - Verification cmd |
     +--------------------+
```

### Simulated Dialogue

The design phase is less interactive but still involves key decisions:

```
ZERG: I've analyzed the requirements. The system has these major components:
      - Product catalog (CRUD operations)
      - Cart management (session-based)
      - Order processing (checkout flow)
      - User authentication (optional, for saved carts)

      Should I generate detailed architecture for all components?
YOU:  Yes, all components. Authentication is optional - users can checkout
      as guest.

ZERG: For the task breakdown, I can parallelize at these levels:
      - Level 1: Database models, config, base types (foundation)
      - Level 2: Services (cart, product, order, auth) - all independent
      - Level 3: API endpoints that use services
      - Level 4: Frontend components
      - Level 5: Integration tests and E2E

      This gives 4-way parallelization at peak. Acceptable?
YOU:  Yes, that structure works. Make sure cart service doesn't depend on
      auth - guest checkout is a requirement.

ZERG: File ownership analysis complete. No conflicts detected.
      Each task has exclusive create/modify rights.
      19 tasks total across 5 levels.
      Ready to generate task-graph.json?
YOU:  Generate it.
```

### Command

```
/zerg:design --feature minerals-store
```

**Generated files:**

| File | Purpose |
|------|---------|
| `.gsd/specs/minerals-store/design.md` | Architecture document with components, data models, API specs |
| `.gsd/specs/minerals-store/task-graph.json` | Atomic tasks with dependencies and file ownership |

**Task structure example:**

```json
{
  "id": "MINE-L2-003",
  "title": "Cart service",
  "description": "Implement cart management with session persistence",
  "files": {
    "create": ["minerals_store/services/cart.py"],
    "modify": ["minerals_store/services/__init__.py"],
    "read": ["minerals_store/models.py", "minerals_store/config.py"]
  },
  "dependencies": ["MINE-L1-001", "MINE-L1-002"],
  "verification": {
    "command": "pytest tests/unit/test_cart_service.py -v",
    "expected": "All tests pass"
  }
}
```

**Validate before rushing:**

```
/zerg:design --validate-only
```

This checks for orphan tasks, dependency cycles, and file ownership conflicts.

---

## Phase 5: Rush (Execute)

### Concept

Rush launches multiple Claude Code instances (workers) that execute tasks in parallel. Workers are coordinated through the task graph - they claim tasks, execute them in isolation, and report completion.

### Narrative

This is where ZERG shines. Instead of one developer working sequentially through 19 tasks, four workers tackle them simultaneously. Level 1 tasks run in parallel. When all complete, workers rebase to get each other's changes, then start Level 2. The coordination happens through git worktrees and the Task system - workers never directly communicate.

### Diagram

```
                    /zerg:rush --workers 4
                            |
                            v
         +------------------+------------------+
         |                  |                  |
         v                  v                  v
    +---------+        +---------+        +---------+
    | Worker 0|        | Worker 1|        | Worker 2|
    | worktree|        | worktree|        | worktree|
    +---------+        +---------+        +---------+
         |                  |                  |
         | LEVEL 1          |                  |
         v                  v                  v
    [MINE-L1-001]     [MINE-L1-002]     [MINE-L1-003]
         |                  |                  |
         +--------+---------+---------+--------+
                  |                   |
                  v                   v
            Quality Gates       Merge to Staging
                  |                   |
                  v                   v
         +------------------+------------------+
         |                  |                  |
         v                  v                  v
    [MINE-L2-001]     [MINE-L2-002]     [MINE-L2-003]
         |                  |                  |
         v                  v                  v
                    ... continues ...
```

### Command

**Preview first (recommended):**

```
/zerg:rush --dry-run --workers 4
```

This shows what would happen without starting workers.

**Launch the swarm:**

```
/zerg:rush --workers 4
```

**Execution modes:**

| Mode | Flag | When to Use |
|------|------|-------------|
| subprocess | `--mode subprocess` | Development, local testing |
| container | `--mode container` | Production, full isolation |
| task | `--mode task` | Claude Code slash command execution |

**Real output:**

```
ZERG Rush

Feature: minerals-store
Workers: 4
Mode: subprocess

Creating worktrees...
  OK .zerg/worktrees/minerals-store-worker-0
  OK .zerg/worktrees/minerals-store-worker-1
  OK .zerg/worktrees/minerals-store-worker-2
  OK .zerg/worktrees/minerals-store-worker-3

=================== LEVEL 1: FOUNDATION ===================

Worker 0: MINE-L1-001 (Data models)           RUNNING
Worker 1: MINE-L1-002 (Configuration)         RUNNING
Worker 2: MINE-L1-003 (Types and enums)       RUNNING
Worker 3:                                     IDLE

[10:52:15] Worker 2 completed MINE-L1-003     OK
[10:55:18] Worker 0 completed MINE-L1-001     OK
[10:55:42] Worker 1 completed MINE-L1-002     OK

Level 1 complete! (3/3 tasks)

Running quality gates...
  OK ruff check . (0 issues)
  OK pytest (3 passed)

Merging Level 1...
  OK Merged all branches to staging
  OK Merged staging to main

=================== LEVEL 2: SERVICES =====================

Worker 0: MINE-L2-001 (Auth service)          RUNNING
Worker 1: MINE-L2-002 (Product service)       RUNNING
Worker 2: MINE-L2-003 (Cart service)          RUNNING
Worker 3: MINE-L2-004 (Order service)         RUNNING

[11:02:33] Worker 1 completed MINE-L2-002     OK
[11:04:15] Worker 3 completed MINE-L2-004     OK
[11:05:42] Worker 2 completed MINE-L2-003     OK
[11:06:18] Worker 0 completed MINE-L2-001     OK

Level 2 complete! (4/4 tasks)

Running quality gates...
  OK ruff check . (0 issues)
  OK pytest (12 passed)
  OK mypy (no errors)

Merging Level 2...
```

---

## Phase 6: Monitor Progress

### Concept

Monitoring shows you what's happening across all workers in real-time. You can see which tasks are running, completed, or failed, and drill into individual worker logs.

### Narrative

Parallel execution is powerful but opaque. Without monitoring, you'd have no idea if a worker is stuck, failed, or making progress. The status command aggregates state from all workers into a single dashboard.

### Diagram

```
+-----------------------------------------------------------+
|                    ZERG Status Dashboard                   |
+-----------------------------------------------------------+
|  Progress: [##############--------] 70%  (14/20 tasks)    |
|  Level: 3 of 5  |  Workers: 4 active  |  Elapsed: 45m     |
+-----------------------------------------------------------+
|  Worker | Current Task              | Status   | Time     |
+-----------------------------------------------------------+
|  W-0    | MINE-L3-001: Product API  | VERIFY   | 8m 23s   |
|  W-1    | MINE-L3-002: Cart API     | RUNNING  | 6m 45s   |
|  W-2    | MINE-L3-003: Order API    | DONE     | --       |
|  W-3    | MINE-L3-004: Auth API     | RUNNING  | 5m 12s   |
+-----------------------------------------------------------+
|  Quality Gates: lint OK | typecheck OK | tests 47 passed  |
+-----------------------------------------------------------+
```

### Command

**Real-time dashboard:**

```
/zerg:status --watch --interval 2
```

**Real output:**

```
=================== ZERG Status: minerals-store ===================

Progress: ############------------ 60% (9/15 tasks)

Level 2 of 4 | Workers: 4 active | Elapsed: 23m 15s

+--------+---------------------------------+----------+---------+
| Worker | Current Task                    | Progress | Status  |
+--------+---------------------------------+----------+---------+
| W-0    | MINE-L2-001: Auth service       | ######## | VERIFY  |
| W-1    | MINE-L2-002: Product service    | ######## | DONE    |
| W-2    | MINE-L2-003: Cart service       | ######-- | RUNNING |
| W-3    | MINE-L2-004: Order service      | ######## | DONE    |
+--------+---------------------------------+----------+---------+

Quality Gates (Level 1):
  OK ruff check . (0 issues)
  OK pytest (3 passed)
```

**View worker logs:**

```
/zerg:logs --tail 50              # Recent logs from all workers
/zerg:logs --worker 2             # Specific worker only
/zerg:logs --follow               # Stream in real-time
/zerg:logs --artifacts MINE-L2-003  # Files created by a task
```

**JSON output for scripting:**

```
/zerg:status --json
```

---

## Phase 7: Quality Gates

### Concept

Quality gates are automated checks that run after each level completes. If a gate fails, merging stops until the issue is fixed. Gates ensure that parallel work integrates cleanly.

### Narrative

Without quality gates, workers might produce code that individually passes tests but breaks when combined. Gates run lint, type checks, and tests on the merged code - catching integration issues before they compound.

### Diagram

```
Level 1 Complete
       |
       v
+------------------+
|   Quality Gates  |
+------------------+
|  [X] ruff check  |---> FAIL --> Fix required
|  [X] mypy        |             before Level 2
|  [X] pytest      |
+------------------+
       |
       | All pass
       v
  Merge to main
       |
       v
  Start Level 2
```

### Configuration

Quality gates are configured in `.zerg/config.yaml`:

```yaml
quality_gates:
  lint:
    command: "ruff check ."
    required: true    # Merge blocked if this fails
  typecheck:
    command: "mypy ."
    required: false   # Warning only, doesn't block
  test:
    command: "pytest"
    required: true
```

### Manual Quality Commands

**Code review:**

```
/zerg:review --mode full
```

Two-stage review: spec compliance check, then code quality check.

**Run tests:**

```
/zerg:test --coverage
/zerg:test --unit
/zerg:test --e2e
```

**Security scanning:**

```
/zerg:security --preset owasp
```

Scans using the security rules fetched during init.

---

## Phase 8: Ship

### Concept

Shipping integrates completed work into main and optionally creates a pull request. After all levels complete and quality gates pass, the feature is ready for release.

### Narrative

ZERG doesn't just build code - it integrates it cleanly. The shipping phase ensures proper git hygiene: meaningful commit messages, clean merge history, and PR documentation.

### Diagram

```
All Levels Complete
        |
        v
+-------------------+
|  Final Quality    |
|  Gates            |
+-------------------+
        |
        | Pass
        v
+-------------------+
|  Smart Commit     |
|  (analyzes diff)  |
+-------------------+
        |
        v
+-------------------+
|  Create PR        |
|  (optional)       |
+-------------------+
        |
        v
+-------------------+
|  Merge to Main    |
+-------------------+
        |
        v
    Feature Live!
```

### Command

**Smart commit (analyzes changes and generates message):**

```
/zerg:git commit
```

**Create pull request:**

```
/zerg:git --action pr
```

**Merge to main after approval:**

```
/zerg:git --action ship
```

**Full workflow (commit + PR + merge):**

```
/zerg:git --action finish
```

---

## Handling Issues

### When a Task Fails Verification

Sometimes a task completes but fails its verification command (tests don't pass).

```
/zerg:debug --error "AssertionError: Expected 85.0"
/zerg:retry MINE-L2-003
/zerg:retry MINE-L2-003 --reset   # Fresh implementation attempt
```

### When a Worker Hits Context Limit

Workers checkpoint automatically. If one runs out of context:

```
/zerg:rush --resume
```

This continues from the last checkpoint rather than starting over.

### When You Need to Stop

```
/zerg:stop                # Graceful - workers checkpoint and exit
/zerg:stop --force        # Immediate termination
```

### When Multiple Tasks Fail

```
/zerg:debug --deep        # Cross-worker analysis
/zerg:retry --all         # Retry all failed tasks
```

---

## Cleanup

After the feature ships, remove ZERG artifacts:

```
/zerg:cleanup --feature minerals-store
```

**What gets removed:**
- Git worktrees (`.zerg/worktrees/`)
- Worker branches (`zerg/minerals-store/*`)
- State files (`.zerg/state/`)

**What stays:**
- Your merged code on main
- Spec files in `.gsd/specs/` (for documentation)
- ZERG configuration

Use `--dry-run` to preview what would be removed.

---

## Quick Reference

### Phase Summary

| Phase | Command | Input | Output |
|-------|---------|-------|--------|
| Init | `/zerg:init` | Empty directory | Project scaffold |
| Brainstorm | `/zerg:brainstorm --socratic` | Your answers | `brainstorm-session.md` |
| Plan | `/zerg:plan <feature>` | Your requirements | `requirements.md` |
| Design | `/zerg:design` | Approved requirements | `design.md`, `task-graph.json` |
| Rush | `/zerg:rush --workers N` | Task graph | Implemented code |
| Monitor | `/zerg:status --watch` | Running workers | Dashboard |
| Ship | `/zerg:git --action ship` | Completed code | Merged to main |
| Cleanup | `/zerg:cleanup` | Artifacts | Clean workspace |

### Key Flags

| Flag | Purpose |
|------|---------|
| `--dry-run` | Preview without executing |
| `--resume` | Continue from checkpoint |
| `--watch` | Continuous updates |
| `--workers N` | Set worker count |
| `--mode container` | Use Docker isolation |
| `--socratic` | Enhanced discovery questioning |
| `--json` | Machine-readable output |

### Troubleshooting

| Problem | Cause | Solution |
|---------|-------|----------|
| "No active feature" | No requirements exist | Run `/zerg:plan <feature>` |
| "Requirements not approved" | Status still DRAFT | Edit requirements.md, change to APPROVED |
| "Task graph not found" | Design not run | Run `/zerg:design` |
| Workers not starting | Docker/API issues | Check `docker info`, `echo $ANTHROPIC_API_KEY` |
| Task stuck | Complex implementation | `/zerg:debug`, `/zerg:retry` |
| Context limit | Large task | `/zerg:rush --resume` |
| Merge conflict | Shouldn't happen | Check file ownership in task-graph.json |

---

## Next Steps

- [Command Reference](Command-Reference.md) - Complete documentation for all commands
- [Configuration](Configuration.md) - Config files and tuning options
- [Architecture](Architecture.md) - How ZERG works internally
