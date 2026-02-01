# Tutorial: Building "Minerals & Vespene Gas" Store with ZERG

> **Welcome, Commander!** In this tutorial, you'll learn ZERG by building a Starcraft 2 themed ecommerce store — complete with API **and** web UI. By the end, you'll understand not just WHAT each command does, but WHY the system works this way — and you'll have a working store you can actually use.

## What We're Building

We're creating **Minerals & Vespene Gas**, a fictional ecommerce store where Starcraft 2 players can purchase game resources. The store will include:

- **Backend API**: FastAPI REST endpoints for all operations
- **Web UI**: A themed storefront where you can browse, add to cart, and checkout
- **Products**: Minerals, Vespene Gas, and special bundles
- **Factions**: Protoss, Terran, and Zerg customers with faction-specific discounts
- **Shopping Cart**: Add items, see discounts applied in real-time
- **Orders**: Process mock payments and see your order confirmation

**The best part?** You'll actually see your store come to life — a dark-themed Starcraft interface where faction colors glow and your discount gets applied as you shop.

More importantly, we'll build this using **parallel Claude Code workers** — multiple AI instances working simultaneously on different parts of the codebase.

## Why This Tutorial?

Most tutorials show you the happy path. This one shows you:
- What's happening **under the hood** at each step
- **Why** ZERG makes certain design decisions
- How to **recover** when things go wrong
- The **mental model** you need to use ZERG effectively

---

## Prerequisites

Before we begin, make sure you have:

| Requirement | How to Check | Why It's Needed |
|-------------|--------------|-----------------|
| Python 3.12+ | `python --version` | ZERG and our API are Python-based |
| Git 2.x+ | `git --version` | ZERG uses git worktrees for worker isolation |
| Docker 20.x+ | `docker info` | Optional but recommended for container mode |
| Claude Code CLI | `claude --version` | Workers are Claude Code instances |
| API Key | `echo $ANTHROPIC_API_KEY` | Authentication for the Claude API |

If any of these fail, install them before continuing.

---

## Part 1: Understanding ZERG Before We Start

Before typing any commands, let's understand what makes ZERG different from just using Claude Code directly.

### The Problem ZERG Solves

Imagine asking Claude Code to build an entire ecommerce API in one conversation:

1. You'd hit context limits partway through
2. Debugging one part might confuse work on another
3. Everything happens sequentially — no parallelism
4. If something goes wrong, you might lose work

### ZERG's Approach

ZERG takes a different path:

1. **Write specs first**: Requirements and design go into files, not conversation history
2. **Break work into tasks**: Each task is small enough to complete without context issues
3. **Assign file ownership**: Each file belongs to exactly one task — no merge conflicts
4. **Execute in parallel**: Multiple Claude Code instances work simultaneously
5. **Merge automatically**: Workers commit to branches, ZERG merges them

**The key insight**: Workers don't need conversation history because they read spec files instead. This means workers can be stateless, restartable, and parallelizable.

---

## Part 2: Project Setup with Inception Mode

Let's create our project. We'll start with an empty directory and let ZERG guide us through setup.

### Step 2.1: Create the Project Directory

```bash
# Create and enter an empty directory
mkdir minerals-store
cd minerals-store

# Verify it's empty
ls -la
# Should show only . and ..
```

**Why an empty directory?** ZERG has two initialization modes:
- **Inception Mode**: Activates in empty directories, creates project from scratch
- **Discovery Mode**: Activates in existing projects, adds ZERG configuration

Since we're starting fresh, we want Inception Mode.

### Step 2.2: Run ZERG Init

```bash
# Initialize ZERG with standard security
/zerg:init --security standard

# Or using the CLI directly:
zerg init --security standard
```

**What you'll see:**

```
ZERG Init - Inception Mode
Empty directory detected. Starting new project wizard...

+-- New Project ---------------------------------------------------+
|  Let's gather some information about your new project.           |
|  Answer these questions to help me recommend a technology        |
|  stack and generate your project scaffold.                       |
+------------------------------------------------------------------+
```

### Step 2.3: Answer the Wizard Questions

ZERG will ask you several questions. Here's what to answer for our minerals store:

**Project name:**
```
minerals-store
```

**Brief description:**
```
Starcraft 2 themed ecommerce API for trading minerals and vespene gas
```

**Target platforms:**
```
api, web
```
(Both `api` and `web` — we're building a backend API and a frontend web UI)

**Architecture style:**
```
monolith
```
(A microservices architecture would be overkill for a tutorial)

**Data storage:**
```
postgresql
```
(We'll use PostgreSQL with SQLAlchemy ORM)

**Authentication:**
```
jwt
```
(JSON Web Tokens for stateless auth)

### Step 2.4: Review the Technology Recommendation

After your answers, ZERG recommends a stack:

```
+-- Recommended Stack -------------------------------------------------+

+--------------------+------------------------------------------------+
| Component          | Recommendation                                 |
+--------------------+------------------------------------------------+
| Backend            |                                                |
|   Language         | python (3.12)                                  |
|   Package Manager  | uv                                             |
|   Web Framework    | fastapi                                        |
|   ORM              | sqlalchemy (async)                             |
|   Database         | asyncpg (PostgreSQL)                           |
|   Auth Library     | python-jose                                    |
+--------------------+------------------------------------------------+
| Frontend           |                                                |
|   Framework        | vanilla (HTML/CSS/JS)                          |
|   Build Tool       | vite                                           |
|   Styling          | tailwindcss                                    |
+--------------------+------------------------------------------------+
| Testing            | pytest, playwright                             |
| Linter             | ruff                                           |
+--------------------+------------------------------------------------+

Accept this stack? [Y/n]:
```

**Why these choices?**

- **FastAPI**: Modern async Python framework, great for APIs
- **SQLAlchemy async**: Production-grade ORM with async support
- **asyncpg**: High-performance PostgreSQL driver
- **Vanilla JS + Vite**: Simple, fast frontend with no framework overhead
- **Tailwind CSS**: Utility-first CSS for rapid theming (perfect for our Starcraft look)
- **ruff**: Fast Python linter (replaces flake8, isort, etc.)
- **python-jose**: Industry-standard JWT library
- **Playwright**: End-to-end browser testing

Press `Y` to accept (or customize if you prefer different tools).

### Step 2.5: Understand What Got Created

After accepting, ZERG generates your project:

```
OK Created 8 scaffold files
OK Created .gsd/PROJECT.md
OK Initialized git repository
OK Created initial commit

OK Inception complete!

Continuing to Discovery Mode to add ZERG infrastructure...
```

**Let's look at what was created:**

```bash
ls -la
```

```
minerals-store/
+-- minerals_store/
|   +-- __init__.py         # Package marker
|   +-- main.py             # FastAPI app entry point
+-- frontend/
|   +-- index.html          # Main HTML entry point
|   +-- src/
|   |   +-- main.js         # JavaScript entry
|   |   +-- style.css       # Tailwind imports
|   +-- package.json        # Frontend dependencies
|   +-- vite.config.js      # Vite configuration
+-- tests/
|   +-- __init__.py
|   +-- test_main.py        # Initial test
+-- .gsd/
|   +-- PROJECT.md          # Project documentation
+-- pyproject.toml          # Python project config
+-- README.md               # Project README
+-- .gitignore              # Git ignore rules
+-- .git/                   # Git repository
```

**Why this structure?**

- `minerals_store/`: Your backend API code goes here
- `frontend/`: Your web UI code goes here (Vite project)
- `tests/`: Test files go here (ZERG workers will create more)
- `.gsd/`: "Get Stuff Done" - ZERG's spec directory
- `pyproject.toml`: Modern Python packaging standard

### Step 2.6: Observe Discovery Mode

Inception Mode automatically continues into Discovery Mode:

```
ZERG Init - Discovery Mode

Analyzing project...
  Detected languages: python
  Detected frameworks: fastapi
  Detected package manager: uv

Creating ZERG configuration...
  OK Created .zerg/config.yaml
  OK Created .devcontainer/devcontainer.json
  OK Created .devcontainer/Dockerfile

Fetching security rules...
  OK Fetched rules for: python, fastapi
  OK Downloaded: owasp-2025.md, python.md, fastapi.md
  OK Updated CLAUDE.md with security rules

OK ZERG initialized!

Next steps:
  1. Run: /zerg:plan <feature-name>
  2. Run: /zerg:design
  3. Run: /zerg:rush
```

### Step 2.7: Explore the New Files

Let's understand what Discovery Mode added:

**`.zerg/config.yaml`** - ZERG configuration:
```yaml
version: "1.0"
project_type: python

workers:
  default_count: 5
  max_count: 10
  timeout_seconds: 3600

security:
  network_isolation: true     # Workers can't make arbitrary network calls
  filesystem_sandbox: true    # Workers can only access project directory
  secrets_scanning: true      # Scans for accidentally committed secrets

quality_gates:
  lint:
    command: "ruff check ."
    required: true
  typecheck:
    command: "mypy ."
    required: false
  test:
    command: "pytest"
    required: true
```

**Why these settings?**

- **network_isolation**: Prevents workers from accessing external resources (security)
- **filesystem_sandbox**: Workers can't read/write outside the project (security)
- **quality_gates**: Automated checks that run after each level merges

**`.devcontainer/devcontainer.json`** - Container configuration for workers:
```json
{
  "name": "ZERG Worker - minerals-store",
  "build": {
    "dockerfile": "Dockerfile"
  },
  "features": {
    "ghcr.io/devcontainers/features/git:1": {}
  },
  "postCreateCommand": "pip install -e .",
  "remoteUser": "vscode"
}
```

**Why containers?**

Each worker runs in its own container for isolation. If one worker somehow corrupts its environment, it doesn't affect others.

**`CLAUDE.md`** - Instructions for Claude Code:
```markdown
# minerals-store

Starcraft 2 themed ecommerce API for trading minerals and vespene gas.

<!-- SECURITY_RULES_START -->
# Security Rules

Auto-generated from TikiTribe/claude-secure-coding-rules

## Detected Stack
- **Languages**: python
- **Frameworks**: fastapi

## Fetched Rules
- `_core/owasp-2025.md`
- `languages/python/CLAUDE.md`
- `backend/fastapi/CLAUDE.md`

<!-- SECURITY_RULES_END -->
```

**Why security rules?**

Rules are stored in `.claude/rules/security/`, which Claude Code auto-loads into context. Workers automatically follow secure coding practices — like parameterized queries, input validation, and secure password handling — without needing explicit `@-imports`.

---

## Part 3: Planning with Socratic Discovery

Now we'll capture requirements. This is crucial because **workers don't have access to our conversation** — they only read spec files.

### Step 3.1: Start the Planning Session

```bash
/zerg:plan minerals-store --socratic
```

**Why `--socratic`?**

The Socratic flag triggers a structured discovery session. Instead of you writing requirements (which might miss edge cases), ZERG asks you targeted questions across three rounds:

1. **Problem Space** — What problem are we solving?
2. **Solution Space** — What are the boundaries?
3. **Implementation Space** — How do we build it?

**What you'll see:**

```
ZERG Plan - Socratic Discovery

Feature: minerals-store
Rounds: 3

====================================================================
                    ROUND 1: PROBLEM SPACE
====================================================================

These questions help us understand WHAT problem we're solving.
```

### Step 3.2: Answer Problem Space Questions

ZERG asks 5 questions about the problem. Here's how to answer for our minerals store:

**Q1: What specific problem does this feature solve?**
```
Starcraft 2 players need a way to purchase in-game resources (minerals and
vespene gas) through a structured API. Currently there's no marketplace for
trading these resources.
```

**Q2: Who are the primary users affected by this problem?**
```
Three factions of players: Protoss, Terran, and Zerg. Each faction has
different resource preferences and should receive faction-specific discounts.
```

**Q3: What happens today without this feature?**
```
Players have no programmatic way to acquire resources. They must manually
gather them in-game, which is time-consuming.
```

**Q4: Why is solving this problem important now?**
```
The player base is growing and demanding a marketplace. A well-designed API
would also allow third-party integrations.
```

**Q5: How will we know when the problem is solved?**
```
Users can:
1. Visit a themed web store and browse products visually
2. Register and login, selecting their faction (with faction-colored UI)
3. See faction discounts applied in real-time as they shop
4. Add items to cart and see the total update instantly
5. Complete checkout and see a confirmation with order details
6. All of this through an actual web interface they can use
```

### Step 3.3: Answer Solution Space Questions

```
====================================================================
                    ROUND 2: SOLUTION SPACE
====================================================================

These questions help us understand the BOUNDARIES of our solution.
```

**Q1: What does the ideal solution look like?**
```
A full-stack ecommerce application with:

Backend (FastAPI):
- Product catalog with CRUD operations
- User registration/authentication with JWT
- Shopping cart with faction-based discounts
- Order processing with mock payments
- PostgreSQL database with async operations

Frontend (Vanilla JS + Vite):
- Dark Starcraft-themed UI with faction colors
- Product grid with images and prices
- Live cart sidebar showing discounts
- Checkout flow with order confirmation
- Responsive design for all screen sizes
```

**Q2: What constraints must we work within?**
```
Backend:
- Python 3.12 with FastAPI
- PostgreSQL with SQLAlchemy (async)
- JWT authentication (no session-based auth)
- REST API only (no GraphQL)

Frontend:
- Vanilla JavaScript (no React/Vue framework)
- Vite for bundling and dev server
- Tailwind CSS for styling
- Must work in modern browsers (Chrome, Firefox, Safari)
```

**Q3: What are the non-negotiable requirements?**
```
- Faction discounts MUST apply automatically (Protoss gets mineral discounts,
  Zerg gets vespene discounts, Terran gets balanced discounts)
- All passwords MUST be hashed with bcrypt
- All database operations MUST use parameterized queries
- Input validation on all endpoints
- UI MUST show the discount breakdown (original price, discount, final price)
- Faction selection MUST change UI colors (blue=Protoss, red=Terran, purple=Zerg)
```

**Q4: What similar solutions exist? What can we learn?**
```
Standard ecommerce patterns like Shopify's API. Key learnings:
- Separate cart from orders (cart is mutable, orders are immutable)
- Use database transactions for checkout
- Idempotency keys for payment processing
```

**Q5: What should this solution explicitly NOT do?**
```
- No real payment processing (mock only)
- No email notifications (out of scope)
- No admin dashboard (API only)
- No rate limiting (would add complexity)
- No OAuth (JWT is sufficient for this use case)
```

### Step 3.4: Answer Implementation Space Questions

```
====================================================================
                    ROUND 3: IMPLEMENTATION SPACE
====================================================================

These questions help us plan HOW to build this.
```

**Q1: What is the minimum viable version?**
```
MVP must include:

Backend:
1. User registration and login (JWT auth)
2. Product catalog (list, view products)
3. Shopping cart (add, remove, view cart)
4. Basic checkout (create order from cart)

Frontend:
5. Login/register page with faction selector
6. Product catalog page with grid layout
7. Cart sidebar with live discount calculation
8. Checkout page with order confirmation
```

**Q2: What can be deferred to future iterations?**
```
- Order history page
- Product search and filtering
- Inventory management
- Bundle products
- Animations and transitions
- Mobile-specific optimizations
```

**Q3: What are the biggest technical risks?**
```
1. Concurrent cart updates (two requests modifying same cart)
2. Database transaction handling during checkout
3. Correct discount calculation with floating point math
4. JWT token refresh handling in the frontend
5. CORS configuration between frontend and backend
```

**Q4: How should we verify this works correctly?**
```
- Unit tests for all backend services
- Integration tests for API endpoints
- E2E tests with Playwright (register, browse, add to cart, checkout)
- Pytest with coverage reporting (>80% backend coverage)
- Visual verification: can see products, add to cart, complete checkout
```

**Q5: What documentation or training is needed?**
```
- API documentation via FastAPI's auto-generated OpenAPI/Swagger
- README with setup instructions
- Example requests for each endpoint
```

### Step 3.5: Review the Generated Requirements

After the Socratic session, ZERG generates `.gsd/specs/minerals-store/requirements.md`:

```markdown
# Feature Requirements: minerals-store

## Metadata
- **Feature**: minerals-store
- **Status**: DRAFT
- **Created**: 2026-01-26T10:30:00
- **Method**: Socratic Discovery (3 rounds)

---

## 1. Problem Statement

### 1.1 Core Problem
Starcraft 2 players need a marketplace API for trading minerals and vespene gas.

### 1.2 Users
Three factions: Protoss (mineral preference), Terran (balanced), Zerg (vespene preference)

### 1.3 Success Criteria
- Browse product catalog
- Register/authenticate with faction
- Shopping cart with automatic faction discounts
- Checkout with mock payments

---

## 2. Solution Requirements

### 2.1 Technical Stack
- Python 3.12, FastAPI
- PostgreSQL, SQLAlchemy (async)
- JWT authentication
- REST API

### 2.2 Non-Negotiable Requirements
- [ ] Automatic faction discounts
- [ ] Password hashing with bcrypt
- [ ] Parameterized database queries
- [ ] Input validation on all endpoints

### 2.3 Explicit Non-Goals
- Real payment processing
- Email notifications
- Admin dashboard
- Rate limiting

---

## 3. Acceptance Criteria

- [ ] Core problem addressed
- [ ] All non-negotiable requirements met
- [ ] All tests passing
- [ ] Coverage > 80%
- [ ] OpenAPI documentation generated

---

## 4. Approval

| Role | Status | Date |
|------|--------|------|
| Product | PENDING | |
| Engineering | PENDING | |
```

### Step 3.6: Approve the Requirements

**Important**: Workers won't start until requirements are approved. This is intentional — it forces you to review before building.

Edit the file to change status to APPROVED:

```bash
# Open in your editor and change Status from DRAFT to APPROVED
# Or use sed:
sed -i '' 's/Status: DRAFT/Status: APPROVED/' .gsd/specs/minerals-store/requirements.md
```

**Why approval matters:**

- Forces human review before AI implementation
- Creates a clear checkpoint in the workflow
- Prevents building the wrong thing
- Documents who approved and when

---

## Part 4: Design and Task Graph Generation

Now we'll generate the technical architecture and break work into parallelizable tasks.

### Step 4.1: Run the Design Command

```bash
/zerg:design --feature minerals-store
```

**What you'll see:**

```
ZERG Design

Feature: minerals-store
Requirements: .gsd/specs/minerals-store/requirements.md (APPROVED)

Analyzing requirements...
  OK Parsed 6 core requirements (backend + frontend)
  OK Identified 5 technical risks
  OK Extracted 8 acceptance criteria

Generating architecture...
  OK Identified 10 components (6 backend, 4 frontend)
  OK Mapped 16 dependencies

Creating task graph...
  OK Generated 19 tasks across 5 levels
  OK Maximum parallelization: 4 tasks

Design Artifacts
+---------------------+---------------------------------------------+
| Artifact            | Path                                        |
+---------------------+---------------------------------------------+
| Design Document     | .gsd/specs/minerals-store/design.md         |
| Task Graph          | .gsd/specs/minerals-store/task-graph.json   |
+---------------------+---------------------------------------------+

OK Design complete!

Next: Review the design and task graph, then run /zerg:rush
```

### Step 4.2: Understand the Design Document

ZERG generates a comprehensive architecture document covering:

- **System components** with an ASCII diagram showing Frontend, API Layer, Service Layer, Data Layer, and Database
- **Component descriptions** with responsibilities and dependencies
- **Data models** for User, Product, Cart, CartItem, Order, and OrderItem
- **Key algorithms** like the faction discount calculation
- **API endpoint listing** for all routes

### Step 4.3: Deep Dive into the Task Graph

The task graph is where ZERG's parallel execution model really shows:

```json
{
  "feature": "minerals-store",
  "version": "2.0",
  "generated": "2026-01-26T10:45:00Z",
  "total_tasks": 19,
  "estimated_duration_minutes": 120,
  "max_parallelization": 4,

  "levels": {
    "1": {
      "name": "foundation",
      "tasks": ["MINE-L1-001", "MINE-L1-002", "MINE-L1-003"],
      "parallel": true,
      "depends_on_levels": []
    },
    "2": {
      "name": "services",
      "tasks": ["MINE-L2-001", "MINE-L2-002", "MINE-L2-003", "MINE-L2-004"],
      "parallel": true,
      "depends_on_levels": [1]
    },
    "3": { ... },
    "4": { ... },
    "5": { ... }
  }
}
```

**Why this level structure?**

```
Level 1 (Foundation):
+-- MINE-L1-001: Create data models (User, Product, Cart, Order)
+-- MINE-L1-002: Create configuration (settings, database)
+-- MINE-L1-003: Create enums and types (Faction, ProductCategory, OrderStatus)

    All Level 1 must complete before Level 2 starts

Level 2 (Services):
+-- MINE-L2-001: Auth service (needs User model)
+-- MINE-L2-002: Product service (needs Product model)
+-- MINE-L2-003: Cart service (needs Cart, Product models)
+-- MINE-L2-004: Order service (needs Order, Cart models)

    All Level 2 must complete before Level 3 starts

Level 3 (API):
+-- MINE-L3-001: Auth endpoints (needs Auth service)
+-- MINE-L3-002: Product endpoints (needs Product service)
+-- MINE-L3-003: Cart endpoints (needs Cart service)
+-- MINE-L3-004: Order endpoints (needs Order service)

    All Level 3 must complete before Level 4 starts

Level 4 (Frontend):
+-- MINE-L4-001: Auth pages (login, register with faction selector)
+-- MINE-L4-002: Catalog page (product grid, add to cart)
+-- MINE-L4-003: Cart sidebar (live totals, discount breakdown)
+-- MINE-L4-004: Checkout page (order summary, confirmation)

    All Level 4 must complete before Level 5 starts

Level 5 (Testing):
+-- MINE-L5-001: Backend integration tests
+-- MINE-L5-002: E2E tests with Playwright (full user journey)
+-- MINE-L5-003: Accessibility tests
```

**Key insight**: Each level's tasks can run in parallel because they don't depend on each other — only on the previous level.

### Step 4.4: Examine a Single Task

Let's look at one task in detail:

```json
{
  "id": "MINE-L2-003",
  "title": "Implement cart service",
  "description": "Cart management with faction-based discounts",
  "level": 2,
  "dependencies": ["MINE-L1-001", "MINE-L1-002", "MINE-L1-003"],

  "files": {
    "create": [
      "minerals_store/services/cart.py"
    ],
    "modify": [
      "minerals_store/services/__init__.py"
    ],
    "read": [
      "minerals_store/models.py",
      "minerals_store/config.py",
      "minerals_store/types.py"
    ]
  },

  "acceptance_criteria": [
    "get_cart() returns user's current cart or creates empty one",
    "add_item() adds product with quantity, validates stock",
    "remove_item() removes item from cart",
    "calculate_total() applies faction discounts correctly",
    "clear_cart() empties the cart"
  ],

  "verification": {
    "command": "pytest tests/unit/test_cart_service.py -v",
    "timeout_seconds": 60
  },

  "estimate_minutes": 20
}
```

**Understanding file ownership:**

| Field | Files | What It Means |
|-------|-------|---------------|
| `create` | `services/cart.py` | This task will CREATE this file. No other task can create it. |
| `modify` | `services/__init__.py` | This task will MODIFY this file. No other Level 2 task can modify it. |
| `read` | `models.py`, `config.py`, `types.py` | This task can READ these. Other tasks can also read them. |

### Step 4.5: Validate the Task Graph

Before rushing, validate the design:

```bash
/zerg:design --validate-only
```

**What validation checks:**

1. **No orphan tasks**: Every task ID in levels exists in tasks array
2. **Dependency order**: Tasks only depend on lower-level tasks
3. **File ownership**: No two tasks at same level create/modify same file
4. **Verification commands**: Every task has a verification command
5. **Circular dependencies**: No circular task dependencies

---

## Part 5: Parallel Execution with Rush

Now the exciting part — launching multiple workers to build our API simultaneously.

### Step 5.1: Preview the Execution Plan

**Always preview first!**

```bash
/zerg:rush --dry-run --workers 5
```

This shows you the full execution plan without starting any workers: which tasks go to which workers, critical path tasks, estimated speedup, and idle worker slots.

### Step 5.2: Choose Your Execution Mode

ZERG supports three execution modes:

| Mode | How It Works | Best For |
|------|-------------|----------|
| `subprocess` | Local Python processes | Development, no Docker needed |
| `container` | Docker containers per worker | Production, full isolation |
| `task` | Claude Code Task sub-agents | Running from slash commands |

```bash
# Auto-detect best mode (default)
/zerg:rush --workers 4

# Force a specific mode
/zerg:rush --workers 4 --mode subprocess
/zerg:rush --workers 4 --mode container
/zerg:rush --workers 4 --mode task
```

**Auto-detection logic**: If Docker is available with a built image, use containers. If running as a slash command, use task mode. Otherwise, use subprocess.

### Step 5.3: Run Preflight Checks

Before launching, ZERG runs preflight validation automatically:

- Git working tree is clean
- Required tools are installed
- Ports are available (for subprocess/container modes)
- Dependencies are satisfied
- Task graph is valid

If any check fails, ZERG tells you exactly what to fix.

### Step 5.4: Launch the Rush

Let's do it for real:

```bash
/zerg:rush --workers 4
```

**Why 4 workers?**

The dry run showed max parallelization is 4 (Level 2 has 4 tasks). Using 5 workers means one is always idle. Using 4 maximizes parallelism without waste.

**What you'll see:**

```
ZERG Rush

Feature: minerals-store
Workers: 4
Mode: subprocess

Preparing execution environment...
  OK Created git worktree: .zerg/worktrees/minerals-store-worker-0
  OK Created git worktree: .zerg/worktrees/minerals-store-worker-1
  OK Created git worktree: .zerg/worktrees/minerals-store-worker-2
  OK Created git worktree: .zerg/worktrees/minerals-store-worker-3

Start execution? [Y/n]: y

====================================================================
                    LEVEL 1: FOUNDATION
====================================================================

Starting 3 workers for Level 1...

Worker 0: MINE-L1-001 (Create data models)         RUNNING
Worker 1: MINE-L1-002 (Create configuration)       RUNNING
Worker 2: MINE-L1-003 (Create enums and types)     RUNNING
Worker 3:                                          IDLE

[10:52:15] Worker 2 completed MINE-L1-003          OK
[10:53:42] Worker 1 completed MINE-L1-002          OK
[10:55:18] Worker 0 completed MINE-L1-001          OK

Level 1 complete! (3/3 tasks)

Running quality gates...
  OK ruff check . (0 issues)
  -- mypy . (skipped - not required)
  OK pytest (3 passed)

Merging Level 1 branches...
  OK Merged zerg/minerals-store/worker-0 -> staging
  OK Merged zerg/minerals-store/worker-1 -> staging
  OK Merged zerg/minerals-store/worker-2 -> staging
  OK Merged staging -> main
  OK Rebased worker branches from main

====================================================================
                    LEVEL 2: SERVICES
====================================================================

Starting 4 workers for Level 2...

[... continues for each level ...]
```

### Step 5.5: What's Happening Behind the Scenes

While the rush runs, let's understand what each worker is doing.

**Each worker:**

1. **Runs in its own directory** (`.zerg/worktrees/minerals-store-worker-N/`)
2. **Has its own git branch** (`zerg/minerals-store/worker-N`)
3. **Reads the task spec** (from `task-graph.json`)
4. **Reads feature context** (from `requirements.md` and `design.md`)
5. **Implements the task** (writes code to fulfill acceptance criteria)
6. **Commits changes** (to its branch)
7. **Runs verification** (executes the verification command)
8. **Reports status** (to the orchestrator via the Claude Code Task system)

**The orchestrator:**

1. **Monitors all workers** (tracks task status)
2. **Handles level transitions** (waits for all tasks, then merges)
3. **Runs quality gates** (lint, typecheck, test)
4. **Manages git operations** (merge to staging, then main)
5. **Coordinates rebasing** (workers get latest main before next level)

### Step 5.6: Monitor Progress

Open a new terminal to watch the rush:

```bash
/zerg:status --watch --interval 2
```

**What you'll see:**

```
====================================================================
           ZERG Status: minerals-store
====================================================================

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

Recent Events (newest first):
  [11:15:42] OK MINE-L2-004 completed by W-3 (verification passed)
  [11:15:38] OK MINE-L2-002 completed by W-1 (verification passed)
  [11:15:35] W-0 running verification for MINE-L2-001
  [11:14:28] W-2 implementing MINE-L2-003 (cart service)

Press Ctrl+C to stop watching (rush continues in background)
====================================================================
```

You can also get status as JSON for programmatic use:

```bash
/zerg:status --json
```

### Step 5.7: View Worker Logs

If you need more detail, check the logs:

```bash
# All workers, recent logs
/zerg:logs --tail 50

# Specific worker, debug level
/zerg:logs --worker 2 --level debug

# Stream logs in real-time
/zerg:logs --follow

# Filter by phase (claim, execute, verify, commit)
/zerg:logs --phase verify

# Filter by time range
/zerg:logs --since "10 minutes ago"

# Aggregate across all workers, sorted by time
/zerg:logs --aggregate

# View task-specific artifacts
/zerg:logs --artifacts MINE-L2-003
```

---

## Part 6: Handling Issues

Things don't always go perfectly. Let's learn how to handle common issues.

### Scenario 1: Task Fails Verification

**What you might see:**

```
[11:20:15] FAIL MINE-L2-003 verification FAILED

Verification output:
  FAILED tests/unit/test_cart_service.py::test_faction_discount
  AssertionError: Expected 85.0, got 100.0

Worker 2 status: FAILED
```

**How to diagnose:**

```bash
# Quick check with logs
/zerg:logs --worker 2 --level error --tail 20

# Deep diagnosis with the debug command
/zerg:debug --error "AssertionError: Expected 85.0, got 100.0"
```

The debug command runs a full diagnostic:
1. **Error Intelligence** parses the error and classifies it
2. **Hypothesis Engine** generates probable causes with Bayesian scoring
3. **Recovery Plan** suggests specific fix steps

**How to fix and retry:**

```bash
# Let ZERG retry automatically (fresh implementation attempt)
/zerg:retry MINE-L2-003

# Retry with a clean slate (discards previous work)
/zerg:retry MINE-L2-003 --reset

# Retry all failed tasks at a specific level
/zerg:retry --level 2

# Retry all failed tasks everywhere
/zerg:retry --all
```

### Scenario 2: Worker Hits Context Limit

**What you might see:**

```
[11:25:00] Worker 2 checkpoint: context limit reached
[11:25:01] Worker 2 status: CHECKPOINT (exit code 2)
```

**This is normal!** Workers checkpoint when they're running low on context space. The work is saved.

**How to continue:**

```bash
# Resume the rush -- workers will continue from checkpoints
/zerg:rush --resume
```

### Scenario 3: Multiple Workers Failing

If many workers fail simultaneously, use the debug command for cross-worker analysis:

```bash
/zerg:debug --deep
```

This runs **log correlation** across all workers, builds a unified timeline, and identifies if failures share a common root cause (like a missing dependency or infrastructure issue).

### Scenario 4: Need to Stop Everything

**Graceful stop** (checkpoints work in progress):

```bash
/zerg:stop
```

**Force stop** (if graceful hangs):

```bash
/zerg:stop --force
```

**Later, resume from where you left off:**

```bash
/zerg:rush --resume
```

---

## Part 7: Quality Gates and Merge

After each level completes, ZERG runs quality gates before merging.

### Step 7.1: Understanding Quality Gates

Quality gates are defined in `.zerg/config.yaml`:

```yaml
quality_gates:
  lint:
    command: "ruff check ."
    required: true        # Merge fails if this fails
  typecheck:
    command: "mypy ."
    required: false       # Warning only
  test:
    command: "pytest"
    required: true
```

**Why quality gates?**

Even with exclusive file ownership, merged code might have issues:
- Import errors (one task imports something another task didn't create)
- Type mismatches (services disagree on types)
- Integration bugs (components don't work together)

Gates catch these **before** code reaches main.

### Step 7.2: Manual Merge (If Needed)

Usually ZERG handles merges automatically. But you can trigger manually:

```bash
# Preview what would be merged
/zerg:merge --dry-run --level 2

# Merge Level 2
/zerg:merge --level 2
```

**What happens during merge:**

1. **Collect branches**: Identify all `zerg/{feature}/worker-N` branches
2. **Sequential merge to staging**: Merge each branch into `zerg/{feature}/staging`
3. **Run quality gates**: Run lint, typecheck, test on staging
4. **Promote to main**: If gates pass, merge staging to main
5. **Rebase workers**: Update worker branches from new main
6. **Clean up**: Remove merged commits from worker branches

### Step 7.3: Run Quality Analysis

After all levels complete, use the analysis and quality commands:

```bash
# Full analysis (lint + complexity + coverage + security)
/zerg:analyze

# Just specific checks
/zerg:analyze --check lint
/zerg:analyze --check security
/zerg:analyze --check complexity

# Security scan with OWASP preset
/zerg:security --preset owasp

# Code review (spec compliance + quality)
/zerg:review --mode full
```

### Step 7.4: Run All Tests

```bash
# Run tests with coverage
/zerg:test --coverage

# Run only specific test types
/zerg:test --unit
/zerg:test --integration
/zerg:test --e2e

# Watch mode (re-run on file changes)
/zerg:test --watch
```

### Step 7.5: Build the Project

```bash
# Build with auto-detection
/zerg:build

# Verbose output for debugging build issues
/zerg:build --verbose
```

---

## Part 8: Advanced Commands

Now that we have a working store, let's explore ZERG's utility commands.

### Refactoring

After the initial build, you might want to clean things up:

```bash
# Dead code removal
/zerg:refactor --transform dead-code

# Simplify complex code
/zerg:refactor --transform simplify

# Add type annotations
/zerg:refactor --transform types

# Apply naming conventions
/zerg:refactor --transform naming

# Preview without applying
/zerg:refactor --transform dead-code --dry-run
```

### Git Operations

ZERG provides intelligent git operations:

```bash
# Smart commit (analyzes changes, generates message)
/zerg:git commit

# Branch management
/zerg:git branch

# Sync with remote
/zerg:git sync

# View history
/zerg:git history

# Finish workflow (merge feature to main)
/zerg:git finish
```

### Plugin System

You can extend ZERG with plugins:

```bash
# List installed plugins
/zerg:plugins --list

# Check plugin status
/zerg:plugins --status

# Enable/disable plugins
/zerg:plugins --enable slack-notifier
/zerg:plugins --disable slack-notifier
```

See the [Plugin System](plugins.md) documentation for writing custom plugins.

---

## Part 9: Cleanup and Final Result

### Step 9.1: Review What Was Built

Let's see the final project structure:

```
minerals-store/
+-- minerals_store/                  # Backend
|   +-- __init__.py
|   +-- main.py                      # FastAPI app with router mounts
|   +-- config.py                    # Settings, database connection
|   +-- types.py                     # Enums: Faction, ProductCategory, OrderStatus
|   +-- models.py                    # SQLAlchemy models
|   +-- services/
|   |   +-- __init__.py
|   |   +-- auth.py                  # JWT auth, password hashing
|   |   +-- product.py               # Product CRUD
|   |   +-- cart.py                  # Cart management, discount calculation
|   |   +-- order.py                 # Checkout, order processing
|   +-- api/
|       +-- __init__.py
|       +-- auth.py                  # /auth/* endpoints
|       +-- products.py              # /products/* endpoints
|       +-- cart.py                  # /cart/* endpoints
|       +-- orders.py                # /orders/* endpoints
+-- frontend/                        # Web UI
|   +-- index.html                   # App shell
|   +-- package.json                 # npm dependencies
|   +-- vite.config.js               # Vite build configuration
|   +-- tailwind.config.js           # Tailwind with faction colors
|   +-- src/
|       +-- main.js                  # App entry, routing, state
|       +-- api.js                   # API client with JWT handling
|       +-- style.css                # Tailwind imports + custom styles
|       +-- pages/
|           +-- auth.js              # Login/register with faction picker
|           +-- catalog.js           # Product grid with add-to-cart
|           +-- cart.js              # Cart sidebar component
|           +-- checkout.js          # Order summary and confirmation
+-- tests/
|   +-- unit/                        # Backend unit tests
|   +-- integration/                 # API integration tests
|   +-- e2e/                         # Playwright E2E tests
|       +-- shopping.spec.js         # Full user journey test
+-- pyproject.toml
+-- README.md
```

### Step 9.2: Start the Application

You'll need two terminals — one for the backend, one for the frontend.

**Terminal 1 - Backend:**

```bash
# Install Python dependencies
uv sync  # or pip install -e .

# Run the API server
uvicorn minerals_store.main:app --reload --port 8000
```

**Terminal 2 - Frontend:**

```bash
# Install JavaScript dependencies
cd frontend
npm install

# Run the dev server
npm run dev  # Starts on http://localhost:5173
```

**Backend API is available at:**
- `http://localhost:8000` - API endpoints
- `http://localhost:8000/docs` - Interactive Swagger documentation

**Frontend is available at:**
- `http://localhost:5173` - Your Starcraft-themed store

### Step 9.3: See Your Store in Action

Open `http://localhost:5173` in your browser. Here's what you'll see:

**Login/Register Page** — A dark-themed form with three glowing faction buttons (blue for Protoss, red for Terran, purple for Zerg).

**Product Catalog (after login as Zerg)** — The entire UI shifts to your faction's color scheme. Products show original prices, and Vespene Gas shows a "15% OFF!" badge since Zerg gets vespene discounts.

**Cart Sidebar** — Shows each item with original price, discount amount, and subtotal. The total savings and final price update in real-time.

**Checkout Confirmation** — Order number, itemized receipt with discount breakdown, and a faction-themed confirmation message.

### Step 9.4: Test the API Directly

If you prefer testing the API without the UI:

```bash
# Register a Zerg user
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "zergling@swarm.net", "password": "f0rTheSwArm!", "faction": "ZERG"}'

# Login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "zergling@swarm.net", "password": "f0rTheSwArm!"}'
# Returns: {"access_token": "eyJ...", "token_type": "bearer"}

# List products
curl http://localhost:8000/products

# Add vespene gas to cart (Zerg gets 15% discount!)
curl -X POST http://localhost:8000/cart/items \
  -H "Authorization: Bearer eyJ..." \
  -H "Content-Type: application/json" \
  -d '{"product_id": "...", "quantity": 100}'

# View cart (discount applied automatically)
curl http://localhost:8000/cart \
  -H "Authorization: Bearer eyJ..."
```

### Step 9.5: Clean Up ZERG Artifacts

```bash
/zerg:cleanup --feature minerals-store
```

This removes:
- Git worktrees (`.zerg/worktrees/minerals-*`)
- Worker branches (`zerg/minerals-store/*`)
- State files (`.zerg/state/minerals-store.json`)
- Log files (`worker-*.jsonl`)

**What's preserved:**
- All merged code (on main branch)
- Spec files (`.gsd/specs/minerals-store/`)
- ZERG configuration (`.zerg/config.yaml`)

**Why preserve specs?**

The spec files (requirements.md, design.md, task-graph.json) are valuable documentation. They record what was built, the architectural decisions made, and how work was decomposed. Keep them for future reference or onboarding new team members.

Use `--dry-run` to preview what would be removed without actually deleting anything.

---

## Summary: What You Learned

You've built a **complete full-stack ecommerce application** using ZERG — both a FastAPI backend AND a themed web UI. Let's recap the key concepts:

### The ZERG Mental Model

1. **Specs are the source of truth**: Workers read files, not conversations
2. **Exclusive file ownership**: No merge conflicts, safe parallel execution
3. **Level-based dependencies**: Each level depends only on previous levels
4. **Workers are stateless**: They can be killed and restarted without losing work
5. **Claude Code Tasks coordinate**: The Task system is the backbone for multi-worker state

### The Workflow

| Phase | Command | What Happens |
|-------|---------|--------------|
| Setup | `/zerg:init` | Create project, configure ZERG |
| Plan | `/zerg:plan --socratic` | Capture requirements through dialogue |
| Design | `/zerg:design` | Generate architecture and task graph |
| Execute | `/zerg:rush --workers 4` | Launch parallel workers |
| Monitor | `/zerg:status --watch` | Track progress in real-time |
| Debug | `/zerg:debug` | Deep diagnostic investigation |
| Logs | `/zerg:logs --follow` | Stream worker output |
| Retry | `/zerg:retry` | Handle failures |
| Quality | `/zerg:analyze` | Static analysis and metrics |
| Test | `/zerg:test --coverage` | Run tests with coverage |
| Review | `/zerg:review` | Code review for quality |
| Security | `/zerg:security` | Vulnerability scanning |
| Refactor | `/zerg:refactor` | Automated code improvement |
| Build | `/zerg:build` | Build with error recovery |
| Git | `/zerg:git commit` | Intelligent git operations |
| Cleanup | `/zerg:cleanup` | Remove ZERG artifacts |

### Key Flags to Remember

| Flag | Purpose |
|------|---------|
| `--dry-run` | Preview without executing |
| `--resume` | Continue from checkpoint |
| `--watch` | Continuous updates |
| `--follow` | Stream output |
| `--socratic` | Structured discovery |
| `--validate-only` | Check without regenerating |
| `--mode` | Choose execution mode (subprocess/container/task) |
| `--json` | Machine-readable output |

### Troubleshooting Checklist

| Problem | Solution |
|---------|----------|
| Task fails verification | Check logs, fix code, `/zerg:retry` |
| Context limit reached | `/zerg:rush --resume` |
| Need to stop | `/zerg:stop` (graceful) or `/zerg:stop --force` |
| Merge conflict | Check task graph for file ownership overlap |
| Worker crashed | Check logs, `/zerg:retry --reset` |
| Multiple failures | `/zerg:debug --deep` for cross-worker analysis |
| Environment issues | `/zerg:debug --env` for full diagnostics |
| Build errors | `/zerg:build --verbose` then `/zerg:debug --error "..."` |

---

## Next Steps

Now that you understand ZERG, try these:

1. **Add features to your minerals store**: Order history, product search, bundles
2. **Try container mode**: `/zerg:rush --mode container` for full isolation
3. **Customize quality gates**: Add more checks to `.zerg/config.yaml`
4. **Add plugins**: Create a Slack notifier or custom quality gate
5. **Build something new**: Use ZERG on your own project

For more details, see:
- [Command Reference](commands.md) — Complete documentation for all 26 commands
- [Configuration Guide](configuration.md) — Config files, tuning, environment variables
- [Architecture](../ARCHITECTURE.md) — System design, module reference, execution model
- [Plugin System](plugins.md) — Extend ZERG with custom gates, hooks, and launchers

**Happy rushing!**
