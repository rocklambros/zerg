# Tutorial: Building "Minerals & Vespene Gas" Store with ZERG

> Learn ZERG by building a Starcraft 2 themed ecommerce store with parallel Claude Code workers.

## Prerequisites

- Python 3.11+
- Docker (for container mode)
- Claude Code CLI installed
- `ANTHROPIC_API_KEY` environment variable set

## Table of Contents

1. [Part 1: Project Setup & Devcontainer](#part-1-project-setup--devcontainer)
2. [Part 2: Planning with /zerg:plan](#part-2-planning-with-zergplan)
3. [Part 3: Architecture with /zerg:design](#part-3-architecture-with-zergdesign)
4. [Part 4: Parallel Execution with /zerg:rush](#part-4-parallel-execution-with-zergrush)
5. [Part 5: Monitoring & Troubleshooting](#part-5-monitoring--troubleshooting)
6. [Part 6: Quality Gates & Merge](#part-6-quality-gates--merge)

---

## Part 1: Project Setup & Devcontainer

In this part, we'll set up ZERG and prepare a new project for parallel development.

### 1.1 Installing ZERG

First, create a new project directory and install ZERG:

```bash
# Create project directory
mkdir minerals-store
cd minerals-store

# Initialize git repository
git init

# Install ZERG
pip install zerg

# Verify installation
zerg --help
```

You should see the ZERG help output showing all available commands.

### 1.2 Project Initialization

Initialize ZERG in your project:

```bash
zerg init --security standard --workers 5
```

**Expected output:**
```
ZERG Init

Detecting project type...
  Language: python (detected)
  Framework: none
  Database: none

Creating configuration...
  ✓ Created .zerg/config.yaml
  ✓ Created .devcontainer/devcontainer.json

Fetching security rules...
  ✓ Detected stack: python
  ✓ Fetched rules: python.md, owasp-2025.md
  ✓ Updated CLAUDE.md

✓ ZERG initialized!

Next steps:
  1. Review .zerg/config.yaml
  2. Run: zerg plan <feature-name>
```

### 1.3 Devcontainer Configuration

The init command creates a `.devcontainer/devcontainer.json` file. Here's what gets generated:

```json
{
  "name": "ZERG Worker",
  "image": "mcr.microsoft.com/devcontainers/python:3.11",
  "features": {
    "ghcr.io/devcontainers/features/git:1": {}
  },
  "customizations": {
    "vscode": {
      "extensions": ["ms-python.python"]
    }
  },
  "postCreateCommand": "pip install -e .",
  "remoteUser": "vscode"
}
```

This container image is used when you run workers in container mode (`--mode container`).

### 1.4 Security Rules Integration

ZERG integrates secure coding rules automatically. Check your `CLAUDE.md`:

```markdown
<!-- SECURITY_RULES_START -->
# Security Rules

Auto-generated from TikiTribe/claude-secure-coding-rules

## Detected Stack
- **Languages**: python

## Imported Rules
@security-rules/_core/owasp-2025.md

<!-- SECURITY_RULES_END -->
```

These rules ensure workers follow secure coding practices while implementing your feature.

**Key files created:**
- `.zerg/config.yaml` - ZERG configuration
- `.devcontainer/devcontainer.json` - Container definition
- `.claude/security-rules/` - Secure coding rules

---

## Part 2: Planning with /zerg:plan

Planning captures requirements before any code is written. This ensures all workers understand what to build.

### 2.1 Starting the Planning Process

Start planning your minerals store feature:

```bash
# Using CLI
zerg plan minerals-store --socratic

# Using Claude Code skill
/zerg:plan minerals-store --socratic
```

**Output:**
```
ZERG Plan

Feature: minerals-store

ROUND 1: PROBLEM SPACE
```

### 2.2 Socratic Discovery Mode

The Socratic mode asks structured questions in three rounds. Here's a sample session:

**Round 1: Problem Space**
```
Problem Q1: What specific problem does this feature solve?
> We need an ecommerce platform for trading Starcraft 2 resources

Problem Q2: Who are the primary users affected by this problem?
> Gamers in three factions: Protoss, Terran, and Zerg

Problem Q3: What happens today without this feature?
> Users have no way to purchase minerals or vespene gas

Problem Q4: Why is solving this problem important now?
> Growing user base needs a marketplace

Problem Q5: How will we know when the problem is solved?
> Users can browse products, add to cart, and checkout
```

**Round 2: Solution Space**
```
Solution Q1: What does the ideal solution look like?
> A web API with product catalog, shopping cart, and order processing

Solution Q2: What constraints must we work within?
> Python/FastAPI, PostgreSQL, REST API only

Solution Q3: What are the non-negotiable requirements?
> User authentication, faction-based discounts, secure payments

Solution Q4: What similar solutions exist? What can we learn?
> Standard ecommerce patterns, but with faction-specific features

Solution Q5: What should this solution explicitly NOT do?
> No real payment processing - mock payments only
```

**Round 3: Implementation Space**
```
Implementation Q1: What is the minimum viable version?
> Product listing, cart, checkout with mock payments

Implementation Q2: What can be deferred to future iterations?
> Inventory management, order history, email notifications

Implementation Q3: What are the biggest technical risks?
> Database performance, concurrent cart updates

Implementation Q4: How should we verify this works correctly?
> Unit tests, integration tests, API contract tests

Implementation Q5: What documentation or training is needed?
> API documentation, developer README
```

### 2.3 Requirements Document Structure

After discovery, ZERG creates `.gsd/specs/minerals-store/requirements.md`:

```markdown
# Feature Requirements: minerals-store

## Metadata
- **Feature**: minerals-store
- **Status**: DRAFT
- **Created**: 2026-01-26T10:30:00
- **Method**: Socratic Discovery

---

## Discovery Transcript

### Problem Space
**Q:** What specific problem does this feature solve?
**A:** We need an ecommerce platform for trading Starcraft 2 resources
...

---

## 1. Problem Statement

### 1.1 Problem
We need an ecommerce platform for trading Starcraft 2 resources

---

## 2. Solution Constraints

- **What does the ideal solution look like?**: A web API with product catalog...
- **What constraints must we work within?**: Python/FastAPI, PostgreSQL...
...

---

## 3. Implementation Notes

- **What is the minimum viable version?**: Product listing, cart, checkout...
...

---

## 4. Acceptance Criteria

- [ ] Core problem addressed
- [ ] All constraints satisfied
- [ ] Tests passing
- [ ] Documentation complete

---

## 5. Approval

| Role | Status |
|------|--------|
| Product | PENDING |
| Engineering | PENDING |
```

### 2.4 Example: Minerals Store Requirements

Review your requirements file and change Status to `APPROVED` when ready:

```markdown
- **Status**: APPROVED
```

Then proceed to design:

```bash
zerg design
```

---

## Part 3: Architecture with /zerg:design

Design generates the architecture and breaks work into parallelizable tasks.

### 3.1 Generating the Design

Run the design command:

```bash
zerg design --feature minerals-store
```

**Output:**
```
ZERG Design

Feature: minerals-store

Generating design artifacts...
  ✓ Created .gsd/specs/minerals-store/design.md
  ✓ Created .gsd/specs/minerals-store/task-graph.json

Design Summary
┌───────────────┬──────────────────────────────────────────┐
│ Item          │ Value                                    │
├───────────────┼──────────────────────────────────────────┤
│ Feature       │ minerals-store                           │
│ Spec Directory│ .gsd/specs/minerals-store                │
│ Requirements  │ .gsd/specs/minerals-store/requirements.md│
│ Design        │ .gsd/specs/minerals-store/design.md      │
│ Task Graph    │ .gsd/specs/minerals-store/task-graph.json│
└───────────────┴──────────────────────────────────────────┘

✓ Design artifacts created!

Next steps:
  1. Edit design.md with architecture details
  2. Populate task-graph.json with specific tasks
  3. Run zerg design --validate-only to check
  4. Run zerg rush to start execution
```

### 3.2 Understanding the Task Graph

The task graph (`task-graph.json`) defines:

1. **Tasks**: Atomic units of work
2. **Levels**: Dependency groups
3. **File ownership**: Which files each task owns
4. **Verification**: How to confirm task completion

Here's the structure:

```json
{
  "feature": "minerals-store",
  "version": "2.0",
  "total_tasks": 12,
  "max_parallelization": 4,

  "tasks": [
    {
      "id": "MINE-L1-001",
      "title": "Define domain models",
      "level": 1,
      "dependencies": [],
      "files": {
        "create": ["src/minerals_store/models.py"],
        "modify": [],
        "read": []
      },
      "verification": {
        "command": "python -c \"from src.minerals_store.models import *\""
      }
    }
  ],

  "levels": {
    "1": {
      "name": "foundation",
      "tasks": ["MINE-L1-001", "MINE-L1-002"],
      "parallel": true
    }
  }
}
```

### 3.3 Dependency Levels Explained

Tasks are organized into levels based on dependencies:

| Level | Name | Description | Example Tasks |
|-------|------|-------------|---------------|
| 1 | Foundation | No dependencies | Models, config, types |
| 2 | Core | Depends on L1 | Services, repositories |
| 3 | Integration | Depends on L2 | API endpoints, handlers |
| 4 | Testing | Depends on L3 | Unit tests, integration tests |

**Key rule:** All tasks in Level N must complete before any task in Level N+1 starts.

### 3.4 File Ownership Rules

Each file is owned by exactly one task per level:

```json
{
  "id": "MINE-L2-001",
  "files": {
    "create": ["src/minerals_store/services/cart.py"],
    "modify": ["src/minerals_store/__init__.py"],
    "read": ["src/minerals_store/models.py"]
  }
}
```

- **create**: Task creates these files exclusively
- **modify**: Task modifies these files exclusively at its level
- **read**: Task may read these files (no exclusivity)

This prevents merge conflicts when workers operate in parallel.

### 3.5 Example: Task Graph for Minerals Store

Here's a sample task graph for the minerals store:

```json
{
  "feature": "minerals-store",
  "version": "2.0",
  "total_tasks": 10,

  "tasks": [
    {
      "id": "MINE-L1-001",
      "title": "Define domain models",
      "description": "Create Product, User, Cart, Order models",
      "level": 1,
      "dependencies": [],
      "files": {
        "create": ["src/minerals_store/models.py"],
        "modify": [],
        "read": []
      },
      "acceptance_criteria": [
        "Product model with name, price, faction",
        "User model with faction membership",
        "Cart and Order models defined"
      ],
      "verification": {
        "command": "python -c \"from src.minerals_store.models import Product, User, Cart, Order\""
      }
    },
    {
      "id": "MINE-L1-002",
      "title": "Create configuration",
      "description": "Database settings, faction discounts",
      "level": 1,
      "dependencies": [],
      "files": {
        "create": ["src/minerals_store/config.py"],
        "modify": [],
        "read": []
      },
      "verification": {
        "command": "python -c \"from src.minerals_store.config import Settings\""
      }
    },
    {
      "id": "MINE-L2-001",
      "title": "Implement product service",
      "description": "CRUD operations for products",
      "level": 2,
      "dependencies": ["MINE-L1-001", "MINE-L1-002"],
      "files": {
        "create": ["src/minerals_store/services/product.py"],
        "modify": [],
        "read": ["src/minerals_store/models.py"]
      },
      "verification": {
        "command": "pytest tests/unit/test_product_service.py -v"
      }
    },
    {
      "id": "MINE-L2-002",
      "title": "Implement cart service",
      "description": "Cart operations with faction discounts",
      "level": 2,
      "dependencies": ["MINE-L1-001", "MINE-L1-002"],
      "files": {
        "create": ["src/minerals_store/services/cart.py"],
        "modify": [],
        "read": ["src/minerals_store/models.py", "src/minerals_store/config.py"]
      },
      "verification": {
        "command": "pytest tests/unit/test_cart_service.py -v"
      }
    }
  ],

  "levels": {
    "1": {
      "name": "foundation",
      "tasks": ["MINE-L1-001", "MINE-L1-002"],
      "parallel": true,
      "estimated_minutes": 15
    },
    "2": {
      "name": "core",
      "tasks": ["MINE-L2-001", "MINE-L2-002"],
      "parallel": true,
      "estimated_minutes": 30,
      "depends_on_levels": [1]
    }
  }
}
```

Validate your task graph:

```bash
zerg design --validate-only
```

---

## Part 4: Parallel Execution with /zerg:rush

Now we launch multiple workers to implement the feature in parallel.

### 4.1 Launching Workers

Start the rush:

```bash
zerg rush --workers 5
```

**Output:**
```
ZERG Rush - minerals-store

Execution Summary
┌──────────────────────┬───────────────┐
│ Metric               │ Value         │
├──────────────────────┼───────────────┤
│ Feature              │ minerals-store│
│ Total Tasks          │ 10            │
│ Levels               │ 4             │
│ Workers              │ 5             │
│ Mode                 │ auto          │
│ Max Parallelization  │ 4             │
│ Critical Path        │ 60 min        │
└──────────────────────┴───────────────┘

Start execution? [Y/n]: y

Starting 5 workers...

✓ Task MINE-L1-001 complete
✓ Task MINE-L1-002 complete

Level 1 complete!

✓ Task MINE-L2-001 complete
✓ Task MINE-L2-002 complete
...
```

### 4.2 Worker Execution Modes

ZERG supports three execution modes:

| Mode | Description | Use When |
|------|-------------|----------|
| `subprocess` | Workers run as processes | Development, debugging |
| `container` | Workers run in Docker | Production, isolation |
| `auto` | Auto-selects based on Docker | Default behavior |

```bash
# Force subprocess mode
zerg rush --mode subprocess --workers 3

# Force container mode
zerg rush --mode container --workers 5
```

### 4.3 Understanding Level Progression

Execution follows this pattern:

```
Level 1: All workers available
├─ Worker 1: MINE-L1-001 (models)
├─ Worker 2: MINE-L1-002 (config)
├─ Worker 3: idle
├─ Worker 4: idle
└─ Worker 5: idle

[SYNC POINT: Level 1 complete, merge branches]

Level 2: Workers pick up tasks
├─ Worker 1: MINE-L2-001 (product service)
├─ Worker 2: MINE-L2-002 (cart service)
├─ Worker 3: MINE-L2-003 (user service)
├─ Worker 4: MINE-L2-004 (order service)
└─ Worker 5: idle

[SYNC POINT: Level 2 complete, merge branches]
...
```

### 4.4 Example: Rush Output

Here's what a complete rush looks like:

```bash
zerg rush --workers 5 --dry-run
```

**Dry run output:**
```
Dry Run - Execution Plan

Level 1 - foundation
┌─────────────┬────────────────────────┬────────┬──────┐
│ Task        │ Title                  │ Worker │ Est. │
├─────────────┼────────────────────────┼────────┼──────┤
│ MINE-L1-001 │ ⭐ Define domain models│ 1      │ 15m  │
│ MINE-L1-002 │ Create configuration   │ 2      │ 10m  │
└─────────────┴────────────────────────┴────────┴──────┘

Level 2 - core
┌─────────────┬────────────────────────┬────────┬──────┐
│ Task        │ Title                  │ Worker │ Est. │
├─────────────┼────────────────────────┼────────┼──────┤
│ MINE-L2-001 │ ⭐ Product service     │ 1      │ 30m  │
│ MINE-L2-002 │ Cart service           │ 2      │ 30m  │
│ MINE-L2-003 │ User service           │ 3      │ 25m  │
│ MINE-L2-004 │ Order service          │ 4      │ 25m  │
└─────────────┴────────────────────────┴────────┴──────┘

⭐ = Critical path task

No workers will be started in dry-run mode
```

---

## Part 5: Monitoring & Troubleshooting

While workers are running, monitor progress and handle issues.

### 5.1 Checking Status

View current status:

```bash
zerg status
```

**Output:**
```
╭──────────────────────────────────────╮
│     ZERG Status: minerals-store      │
╰──────────────────────────────────────╯

Progress: ████████████░░░░░░░░ 60% (6/10 tasks)

Level Status:
┌───────┬─────────────┬───────┬──────────┬───────────┐
│ Level │ Name        │ Tasks │ Complete │ Status    │
├───────┼─────────────┼───────┼──────────┼───────────┤
│ 1     │ foundation  │ 2     │ 2        │ ✓ DONE    │
│ 2     │ core        │ 4     │ 4        │ ✓ DONE    │
│ 3     │ integration │ 3     │ 0        │ RUNNING   │
│ 4     │ testing     │ 1     │ 0        │ PENDING   │
└───────┴─────────────┴───────┴──────────┴───────────┘

Worker Status:
┌──────────┬──────┬─────────────┬────────────┬─────────┐
│ Worker   │ Port │ Task        │ Progress   │ Status  │
├──────────┼──────┼─────────────┼────────────┼─────────┤
│ worker-1 │ 49152│ MINE-L3-001 │ ████████░░ │ RUNNING │
│ worker-2 │ 49153│ MINE-L3-002 │ ██████░░░░ │ RUNNING │
│ worker-3 │ 49154│ MINE-L3-003 │ ████░░░░░░ │ RUNNING │
│ worker-4 │ 49155│ -           │ ░░░░░░░░░░ │ IDLE    │
│ worker-5 │ 49156│ -           │ ░░░░░░░░░░ │ IDLE    │
└──────────┴──────┴─────────────┴────────────┴─────────┘

Recent Events:
  [10:45:12] ✓ MINE-L2-004 completed by worker-4
  [10:45:08] ✓ MINE-L2-003 completed by worker-3
  [10:44:55] ✓ Level 2 complete
  [10:44:30] ✓ MINE-L2-002 completed by worker-2
  [10:44:25] ✓ MINE-L2-001 completed by worker-1
```

For continuous monitoring:

```bash
zerg status --watch --interval 3
```

### 5.2 Viewing Worker Logs

View logs from all workers:

```bash
zerg logs
```

View logs from a specific worker:

```bash
zerg logs 1 --tail 50
```

Stream logs in real-time:

```bash
zerg logs --follow --level debug
```

**Sample log output:**
```
[10:45:12] [INFO ] W1 Starting task MINE-L3-001
[10:45:13] [DEBUG] W1 Reading spec file task_id=MINE-L3-001
[10:45:15] [INFO ] W1 Implementing API endpoints
[10:45:30] [INFO ] W1 Running verification command
[10:45:32] [INFO ] W1 Task complete task_id=MINE-L3-001
```

### 5.3 Common Issues and Solutions

**Issue: Task fails verification**

```bash
# Check what went wrong
zerg logs 1 --level error

# Analyze the error
zerg troubleshoot --error "ImportError: cannot import name 'Product'"

# Fix and retry
zerg retry MINE-L2-001
```

**Issue: Worker crashes**

```bash
# Check status
zerg status

# View worker logs
zerg logs 3 --tail 100

# Restart just that worker's task
zerg retry MINE-L2-003 --worker 3
```

**Issue: Need to stop everything**

```bash
# Graceful stop
zerg stop

# Force stop if needed
zerg stop --force
```

### 5.4 Retrying Failed Tasks

Retry a specific task:

```bash
zerg retry MINE-L2-001
```

Retry all failed tasks:

```bash
zerg retry --all-failed
```

Reset and retry (clears retry count):

```bash
zerg retry MINE-L2-001 --reset
```

Assign to specific worker:

```bash
zerg retry MINE-L2-001 --worker 2
```

### 5.5 Stopping Workers

Graceful stop (checkpoints current work):

```bash
zerg stop
```

Stop specific worker:

```bash
zerg stop --worker 3
```

Force stop (immediate termination):

```bash
zerg stop --force
```

---

## Part 6: Quality Gates & Merge

After tasks complete, run quality gates and merge branches.

### 6.1 Running Analysis

Run static analysis on your code:

```bash
zerg analyze
```

**Output:**
```
ZERG Analyze

Running checks...
  ✓ lint: ruff check .
  ✓ complexity: radon cc . --average
  ⚠ coverage: 78% (threshold: 80%)
  ✓ security: bandit -r src/

Results:
┌────────────┬────────┬─────────┬───────────┐
│ Check      │ Status │ Score   │ Threshold │
├────────────┼────────┼─────────┼───────────┤
│ lint       │ PASS   │ 0 issues│ 0         │
│ complexity │ PASS   │ A (2.3) │ B         │
│ coverage   │ WARN   │ 78%     │ 80%       │
│ security   │ PASS   │ 0 high  │ 0         │
└────────────┴────────┴─────────┴───────────┘
```

Run specific checks:

```bash
zerg analyze --check lint,security
```

### 6.2 Running Tests

Execute tests with coverage:

```bash
zerg test --coverage
```

**Output:**
```
ZERG Test

Framework: pytest (detected)
Path: tests/

Running tests...
========================= test session starts ==========================
collected 42 items

tests/unit/test_models.py ....                                    [  9%]
tests/unit/test_product_service.py ........                       [ 28%]
tests/unit/test_cart_service.py ..........                        [ 52%]
tests/unit/test_user_service.py ......                            [ 66%]
tests/integration/test_api.py ..............                      [100%]

========================== 42 passed in 3.21s ==========================

Coverage Report:
Name                              Stmts   Miss  Cover
-----------------------------------------------------
src/minerals_store/models.py         45      2    96%
src/minerals_store/services/*.py    156     12    92%
src/minerals_store/api/*.py          89      8    91%
-----------------------------------------------------
TOTAL                               290     22    92%

✓ All tests passed (42/42)
✓ Coverage: 92% (threshold: 80%)
```

### 6.3 Merging Completed Levels

After a level completes, merge its branches:

```bash
zerg merge --level 2
```

**Output:**
```
ZERG Merge - minerals-store

Merge Plan
┌────────────────────┬──────────────────────────────┐
│ Setting            │ Value                        │
├────────────────────┼──────────────────────────────┤
│ Feature            │ minerals-store               │
│ Level              │ 2                            │
│ Target Branch      │ main                         │
│ Staging Branch     │ zerg/minerals-store/staging  │
│ Branches to Merge  │ 4                            │
│ Quality Gates      │ lint, typecheck, test        │
└────────────────────┴──────────────────────────────┘

Branches:
  🟢 zerg/minerals-store/worker-1
  🟢 zerg/minerals-store/worker-2
  🟢 zerg/minerals-store/worker-3
  🟢 zerg/minerals-store/worker-4

Running quality gates...
  Running lint...
    ✓ lint
  Running typecheck...
    ✓ typecheck
  Running test...
    ✓ test
✓ Quality gates passed

Proceed with merge? [Y/n]: y

Merging branches...

✓ Level 2 merged successfully
  Merge commit: a1b2c3d4
  Target: main
```

### 6.4 Cleanup

After all work is complete, clean up ZERG artifacts:

```bash
zerg cleanup --feature minerals-store
```

**Output:**
```
ZERG Cleanup

Cleanup Plan
┌───────────────────┬────────────────────────────────┬───────┐
│ Category          │ Items                          │ Count │
├───────────────────┼────────────────────────────────┼───────┤
│ Features          │ minerals-store                 │ 1     │
│ Worktrees         │ .zerg/worktrees/minerals-*     │ 5     │
│ Branches          │ zerg/minerals-store/*          │ 7     │
│ Container patterns│ zerg-worker-minerals-store-*   │ 1     │
│ State files       │ .zerg/state/minerals-store.json│ 1     │
│ Log files         │ 5 files                        │ 5     │
└───────────────────┴────────────────────────────────┴───────┘

Proceed with cleanup? [y/N]: y

Removing worktrees...
  ✓ .zerg/worktrees/minerals-store-worker-1
  ✓ .zerg/worktrees/minerals-store-worker-2
  ✓ .zerg/worktrees/minerals-store-worker-3
  ✓ .zerg/worktrees/minerals-store-worker-4
  ✓ .zerg/worktrees/minerals-store-worker-5

Removing branches...
  ✓ zerg/minerals-store/staging
  ✓ zerg/minerals-store/worker-1
  ✓ zerg/minerals-store/worker-2
  ✓ zerg/minerals-store/worker-3
  ✓ zerg/minerals-store/worker-4

Stopping containers...
  - No containers matching zerg-worker-minerals-store-*

Removing state files...
  ✓ .zerg/state/minerals-store.json

Removing log files...
  ✓ .zerg/logs/worker-1.log
  ✓ .zerg/logs/worker-2.log
  ✓ .zerg/logs/worker-3.log
  ✓ .zerg/logs/worker-4.log
  ✓ .zerg/logs/worker-5.log

✓ Cleanup complete
```

To keep logs for debugging:

```bash
zerg cleanup --feature minerals-store --keep-logs
```

### 6.5 Final Result

Your project now contains:

```
minerals-store/
├── src/
│   └── minerals_store/
│       ├── __init__.py
│       ├── models.py           # Domain models
│       ├── config.py           # Configuration
│       ├── services/
│       │   ├── product.py      # Product service
│       │   ├── cart.py         # Cart service
│       │   ├── user.py         # User service
│       │   └── order.py        # Order service
│       └── api/
│           ├── products.py     # Product endpoints
│           ├── cart.py         # Cart endpoints
│           └── orders.py       # Order endpoints
├── tests/
│   ├── unit/
│   │   └── ...
│   └── integration/
│       └── ...
├── .zerg/
│   └── config.yaml
├── .gsd/
│   └── specs/
│       └── minerals-store/
│           ├── requirements.md
│           ├── design.md
│           └── task-graph.json
└── README.md
```

All implemented by parallel workers, merged conflict-free, with quality gates passed.

---

## Summary

In this tutorial, you learned:

1. **Project Setup**: Initialize ZERG with `zerg init`, configure devcontainers and security rules
2. **Planning**: Use Socratic discovery with `zerg plan --socratic` to capture comprehensive requirements
3. **Design**: Generate task graphs with `zerg design` that define parallel work units with exclusive file ownership
4. **Execution**: Launch parallel workers with `zerg rush --workers 5` and watch them implement concurrently
5. **Monitoring**: Track progress with `zerg status --watch` and debug with `zerg logs`
6. **Quality**: Run analysis with `zerg analyze` and tests with `zerg test --coverage`
7. **Merge**: Merge completed levels with `zerg merge` after quality gates pass
8. **Cleanup**: Clean up artifacts with `zerg cleanup`

## Command Quick Reference

| Phase | Command | Description |
|-------|---------|-------------|
| Setup | `zerg init` | Initialize project |
| Plan | `zerg plan <feature> --socratic` | Capture requirements |
| Design | `zerg design` | Generate task graph |
| Execute | `zerg rush --workers 5` | Launch workers |
| Monitor | `zerg status --watch` | Track progress |
| Debug | `zerg logs --follow` | View worker logs |
| Quality | `zerg analyze && zerg test` | Run checks |
| Merge | `zerg merge --level N` | Merge branches |
| Cleanup | `zerg cleanup --feature <name>` | Remove artifacts |

## Next Steps

- Read the [Command Reference](../README.md#command-reference) for all available options
- Explore the [Configuration Guide](../README.md#configuration) for advanced settings
- Check out the [Troubleshooting Guide](../README.md#troubleshooting) for common issues
