# ZERG

<p align="center">
  <img src="logo/zerg_logo.png" alt="ZERG Logo" width="450">
</p>

<p align="center">
  <a href="https://pypi.org/project/zerg-ai/"><img src="https://img.shields.io/pypi/v/zerg-ai" alt="PyPI version"></a>
  <a href="https://pypi.org/project/zerg-ai/"><img src="https://img.shields.io/pypi/pyversions/zerg-ai" alt="Python"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/rocklambros/zerg" alt="License"></a>
  <a href="https://github.com/rocklambros/zerg/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/rocklambros/zerg/ci.yml?branch=main&label=CI" alt="CI"></a>
  <a href="#"><img src="https://img.shields.io/badge/coverage-50%25-yellow" alt="Coverage"></a>
</p>

**Zero-Effort Rapid Growth** — A parallel Claude Code execution system that coordinates multiple Claude Code instances to build software features simultaneously. ZERG auto-detects your tech stack, fetches security rules, generates dev containers, breaks features into atomic tasks with exclusive file ownership, and launches a swarm of zerglings to execute them in parallel.

---

## Why I Built This

Every time I started a new project with Claude Code, I found myself doing the same setup work over and over:

- **Secure coding rules.** Manually writing OWASP guidelines, language-specific security patterns, and Docker hardening rules into CLAUDE.md so Claude would actually follow them. Every. Single. Time.
- **Dev containers.** Configuring Dockerfiles, devcontainer.json, MCP servers, and post-create scripts so workers could run in isolated environments.
- **Project scaffolding.** Setting up directory structures, config files, linting, pre-commit hooks — the same boilerplate for every repo.
- **Parallel execution.** Claude Code is powerful, but it's one instance. For any feature with 10+ files, I'd spend hours watching a single agent work sequentially through tasks that could run in parallel.
- **Context rot.** The bigger the feature, the more Claude forgets. By the time it's working on file 15, it's lost track of the decisions it made in file 3.

I got tired of the repetition. So I built a system that handles all of it:

**ZERG auto-detects your stack** and fetches stack-specific security rules (OWASP Top 10 2025, Python, JavaScript, Docker) from [TikiTribe/claude-secure-coding-rules](https://github.com/TikiTribe/claude-secure-coding-rules) — no manual CLAUDE.md maintenance.

**ZERG generates dev containers** with your detected languages, MCP server configs, and authentication baked in — workers spin up in isolated Docker environments with a single flag.

**ZERG breaks features into parallel tasks** with exclusive file ownership, so 5-10 Claude Code instances work simultaneously without merge conflicts. A feature that takes one agent 2 hours takes a swarm 20 minutes.

**ZERG solves context rot** through spec-driven execution. Workers read specification files, not conversation history. Every zergling is stateless — crash one, restart it, and it picks up exactly where it left off.

**ZERG engineers context** per worker. Large command files are split into core (~30%) and reference (~70%) segments. Security rules are filtered by file extension. Each task gets a scoped context budget instead of loading entire spec files. Workers use fewer tokens and stay focused.

The goal was simple: stop repeating myself and start shipping faster. ZERG is the result of wanting one command to set up security, containers, scaffolding, and parallel execution — then getting out of the way.

---

## Quick Start (5 minutes)

```bash
# Install ZERG
pip install zerg-ai

# Or install from source (contributors)
git clone https://github.com/rocklambros/zerg.git && cd zerg
pip install -e ".[dev]"
zerg install  # Install slash commands into your project

# Inside Claude Code:
/zerg:init                    # Initialize project
/zerg:plan my-feature         # Capture requirements
/zerg:design                  # Generate architecture
/zerg:rush --workers=5        # Launch the swarm
```

---

## Installation

### Prerequisites

| Requirement | Check Command | Purpose |
|-------------|---------------|---------|
| Python 3.12+ | `python --version` | ZERG runtime |
| Git 2.x+ | `git --version` | Worktrees, branching |
| Claude Code CLI | `claude --version` | Worker instances |
| Docker 20.x+ | `docker info` | Container mode (optional) |

### Step 1: Install

```bash
pip install zerg-ai
```

### Step 1b: Install from Source (Contributors)

```bash
git clone https://github.com/rocklambros/zerg.git
cd zerg
pip install -e ".[dev]"
```

### Step 2: Install Pre-commit Hooks (Contributors)

```bash
pre-commit install
```

### Step 3: Verify Installation

```bash
zerg --help
```

### Step 4: Install Slash Commands

ZERG ships with 26 slash commands. Install them into your project:

```bash
cd your-project
zerg install          # Install to .claude/commands/
```

Once installed, use `/zerg:*` commands inside any Claude Code session. Every command also has a `/z:` shortcut (e.g., `/z:plan`, `/z:rush`).

---

## Tutorial: Your First ZERG Project

This tutorial walks through building a "Minerals Store" — a Starcraft 2 themed ecommerce API — using all ZERG phases. You'll learn why each phase exists and see what the conversations with ZERG actually look like.

### Initialization: Setting Up Your Project

Before ZERG can coordinate parallel workers, it needs to understand your project and create the infrastructure for safe parallel execution. The initialization phase handles detection, configuration, and scaffolding automatically.

Create a new directory and enter it:

```bash
mkdir minerals-store && cd minerals-store
```

Inside Claude Code, run the init command:

```
/zerg:init
```

ZERG begins by analyzing your project:

```
ZERG: Scanning project structure...
      Detected: Empty project (no source files)
      Starting Inception wizard for new project setup.

ZERG: What type of project are you building?
YOU:  A Python REST API using FastAPI.

ZERG: What testing framework should I configure?
YOU:  pytest with coverage reporting.

ZERG: Creating infrastructure...
      ✓ .zerg/config.yaml — worker settings, quality gates
      ✓ .devcontainer/ — container mode configuration
      ✓ .gsd/ — specs and task graphs directory
      ✓ Security rules fetched (OWASP Top 10, Python rules)
```

Initialization matters because parallel workers need a shared understanding of project structure, coding standards, and quality gates. Without this foundation, workers would make inconsistent decisions about file organization, testing patterns, and error handling.

### Brainstorming: Discovering What to Build (Optional)

Sometimes you know exactly what you want to build. But often, especially for new features, you have a vague idea that needs refinement. The brainstorming phase helps you discover and articulate requirements before committing to implementation.

If your requirements are unclear, start with Socratic discovery:

```
/zerg:brainstorm --socratic
```

ZERG asks probing questions across three rounds:

```
ZERG: Let's discover what you want to build. I'll ask questions to help
      clarify your vision.

      ROUND 1 — Problem Space

ZERG: What problem does the minerals store solve for users?
YOU:  Users need to browse and purchase mineral products through a REST API.

ZERG: Who are the primary users? How will they interact with the system?
YOU:  Game developers integrating mineral purchases into their Starcraft-themed games.

ZERG: What happens if this problem isn't solved? What workarounds exist?
YOU:  Developers would build custom solutions, wasting time on commodity functionality.

      ROUND 2 — Solution Shape

ZERG: What would an ideal solution look like from a user's perspective?
YOU:  Simple REST endpoints for catalog browsing, cart management, and checkout.

ZERG: What are the absolute must-haves versus nice-to-haves?
YOU:  Must-have: products, cart, orders. Nice-to-have: recommendations, reviews.

ZERG: What should this explicitly NOT do?
YOU:  No payment processing — that's handled by a separate payment service.

      ROUND 3 — Constraints

ZERG: What technical constraints exist?
YOU:  Must use PostgreSQL for persistence. Stateless for horizontal scaling.

ZERG: What's the expected scale and performance requirement?
YOU:  100 requests/second initially, with room to scale to 1000.

ZERG: Synthesizing insights...
      ✓ Output: .gsd/specs/brainstorm-session.md
```

Brainstorming matters because unclear requirements lead to rework. By asking structured questions, ZERG helps you think through edge cases and constraints before any code is written. The output becomes input for the planning phase.

### Planning: Capturing What You Want to Build

Before ZERG can help build your feature, it needs to understand what you're trying to create in concrete terms. The planning phase transforms brainstorming insights (or your existing mental model) into a structured requirements document.

Start the planning conversation:

```
/zerg:plan minerals-store
```

ZERG begins capturing requirements:

```
ZERG: Let's capture the requirements for 'minerals-store'.

ZERG: What problem does the minerals store solve for users?
YOU:  Users need to browse and purchase mineral products through a REST API.

ZERG: Describe your ideal solution in 2-3 sentences.
YOU:  A FastAPI service with endpoints for products, cart, and orders.
      Products have names, descriptions, prices, and stock counts.
      Carts persist across sessions and convert to orders at checkout.

ZERG: What are the non-negotiable requirements?
YOU:  1. Product catalog with CRUD operations
      2. Shopping cart that persists items
      3. Order placement with stock validation
      4. All endpoints return JSON with proper error codes

ZERG: What should this feature explicitly NOT include?
YOU:  No payment processing, no user authentication (handled elsewhere),
      no email notifications.

ZERG: Generating requirements document...
      ✓ .gsd/specs/minerals-store/requirements.md (Status: DRAFT)

      Review and change status to APPROVED when ready for design.
```

Planning matters because ZERG workers are stateless — they don't remember previous conversations. The requirements document becomes the shared source of truth that every worker reads. Without clear requirements, workers would interpret the feature differently, leading to inconsistent implementations.

### Design: Creating the Architecture

With approved requirements, ZERG can design the technical architecture. This phase analyzes your codebase, creates component designs, and — critically — breaks work into atomic tasks with exclusive file ownership.

First, mark your requirements as approved by editing `.gsd/specs/minerals-store/requirements.md` and changing `Status: DRAFT` to `Status: APPROVED`.

Then generate the design:

```
/zerg:design
```

ZERG analyzes and generates architecture:

```
ZERG: Reading approved requirements...
      Feature: minerals-store
      Non-negotiables: 4 requirements identified
      Non-goals: 3 exclusions noted

ZERG: Analyzing existing codebase...
      Project type: Python (FastAPI)
      Patterns detected: Repository pattern, Pydantic models
      Test location: tests/

ZERG: Generating architecture...

      Components:
      ├── models/ — Pydantic schemas, SQLAlchemy models
      ├── routers/ — FastAPI route handlers
      ├── services/ — Business logic layer
      └── repositories/ — Data access layer

ZERG: Creating task graph...
      Level 1: Foundation (4 tasks, parallelizable)
        ├── TASK-001: Create Product model and schema
        ├── TASK-002: Create Cart model and schema
        ├── TASK-003: Create Order model and schema
        └── TASK-004: Create database migrations

      Level 2: Data Access (3 tasks, parallelizable)
        ├── TASK-005: Product repository
        ├── TASK-006: Cart repository
        └── TASK-007: Order repository

      Level 3: Business Logic (3 tasks, parallelizable)
        └── ...

      ✓ .gsd/specs/minerals-store/design.md
      ✓ .gsd/specs/minerals-store/task-graph.json
```

Design matters because parallel execution requires careful planning. Each task declares exclusive file ownership — which files it creates, modifies, and reads. This prevents merge conflicts when multiple workers run simultaneously. Without this upfront design, workers would step on each other's changes.

### Rush: Launching the Swarm

With the task graph ready, you can launch parallel workers. Each worker claims a task, executes it in an isolated git worktree, and reports results. The orchestrator manages task distribution and level progression.

Launch the swarm:

```
/zerg:rush --workers=4
```

Real output as workers execute:

```
ZERG: Starting rush execution...
      Feature: minerals-store
      Task graph: 12 tasks across 4 levels
      Workers requested: 4

      Creating git worktrees...
      ✓ .zerg/worktrees/worker-1
      ✓ .zerg/worktrees/worker-2
      ✓ .zerg/worktrees/worker-3
      ✓ .zerg/worktrees/worker-4

      === LEVEL 1 (4 tasks) ===

      [Worker-1] Claimed TASK-001: Create Product model
      [Worker-2] Claimed TASK-002: Create Cart model
      [Worker-3] Claimed TASK-003: Create Order model
      [Worker-4] Claimed TASK-004: Database migrations

      [Worker-1] ✓ TASK-001 complete (47s)
      [Worker-3] ✓ TASK-003 complete (52s)
      [Worker-2] ✓ TASK-002 complete (58s)
      [Worker-4] ✓ TASK-004 complete (63s)

      Running quality gates...
      ✓ ruff check . — passed
      ✓ pytest tests/ — passed (4 tests)

      Merging Level 1 branches...
      ✓ All branches merged to feature/minerals-store

      === LEVEL 2 (3 tasks) ===
      ...
```

Rush matters because parallel execution is ZERG's core value proposition. A feature that takes one agent 2 hours takes a swarm 20 minutes. But parallelism requires infrastructure — worktrees for isolation, task claiming for coordination, quality gates for verification, and automated merging for integration.

**Execution modes** let you choose the isolation level:

| Mode | Flag | When to Use |
|------|------|-------------|
| Task | `--mode task` | Default. Runs as Claude Code tasks. Fast, good for development. |
| Subprocess | `--mode subprocess` | Runs as separate processes. More isolation than task mode. |
| Container | `--mode container` | Full Docker isolation. Best for production or untrusted code. |

### Monitoring: Tracking Progress

While workers execute, you can monitor progress in real-time. The status command shows task states, worker assignments, and quality gate results.

Watch execution progress:

```
/zerg:status --watch
```

Real-time output:

```
╔══════════════════════════════════════════════════════════════╗
║  ZERG Status: minerals-store                                 ║
╠══════════════════════════════════════════════════════════════╣
║  Progress: Level 2 of 4  |  Tasks: 7/12 complete             ║
╠══════════════════════════════════════════════════════════════╣
║  WORKERS                                                     ║
║  ├── Worker-1: TASK-005 (Product repository) — running 23s   ║
║  ├── Worker-2: TASK-006 (Cart repository) — running 31s      ║
║  ├── Worker-3: TASK-007 (Order repository) — running 28s     ║
║  └── Worker-4: idle (no tasks at current level)              ║
╠══════════════════════════════════════════════════════════════╣
║  RECENT EVENTS                                               ║
║  14:23:07  Level 1 quality gates passed                      ║
║  14:23:12  Level 1 branches merged                           ║
║  14:23:15  Level 2 started (3 tasks)                         ║
╚══════════════════════════════════════════════════════════════╝
```

For detailed worker activity, use the logs command:

```
/zerg:logs --follow              # Stream all workers
/zerg:logs --worker 2            # Specific worker
/zerg:logs --aggregate           # All workers sorted by time
```

### Quality: Verifying the Implementation

After all levels complete, ZERG provides commands to verify the implementation meets requirements and quality standards.

Review code against the spec:

```
/zerg:review --mode full
```

Run tests with coverage:

```
/zerg:test --coverage
```

Scan for security vulnerabilities:

```
/zerg:security --preset owasp
```

Quality matters because parallel execution can introduce subtle bugs — especially at integration points between tasks. Automated review, testing, and security scanning catch issues before they reach production.

### Shipping: Getting Your Feature to Main

With quality verified, merge your feature branch to main:

```
/zerg:git --action ship
```

Output:

```
ZERG: Preparing to ship minerals-store...

      Pre-ship checks:
      ✓ All tasks complete (12/12)
      ✓ Quality gates passed
      ✓ No uncommitted changes

      Merging feature/minerals-store → main...
      ✓ Merge complete
      ✓ Feature branch cleaned up

      🎉 minerals-store shipped successfully!
```

Other git operations available:

| Action | Command | Purpose |
|--------|---------|---------|
| Commit | `/zerg:git commit` | Commit current changes with generated message |
| Create PR | `/zerg:git --action pr` | Open pull request for review |
| Ship | `/zerg:git --action ship` | Merge to main after verification (`--admin` to bypass branch protection) |
| Full workflow | `/zerg:git --action finish` | PR → review → merge in one command |

---

## Command Quick Reference

### Core Workflow

| Command | Purpose |
|---------|---------|
| `/zerg:init` | Initialize ZERG infrastructure |
| `/zerg:brainstorm` | Feature discovery with interactive questioning |
| `/zerg:plan <feature>` | Capture requirements |
| `/zerg:design` | Generate architecture and task graph |
| `/zerg:rush` | Launch parallel zerglings |

### Monitoring & Control

| Command | Purpose |
|---------|---------|
| `/zerg:status` | Real-time progress dashboard |
| `/zerg:logs` | Stream, filter, aggregate worker logs |
| `/zerg:stop` | Stop workers gracefully or forcefully |
| `/zerg:retry` | Retry failed or blocked tasks |
| `/zerg:merge` | Manually trigger level merge |
| `/zerg:cleanup` | Remove ZERG artifacts |

### Quality & Analysis

| Command | Purpose |
|---------|---------|
| `/zerg:build` | Build orchestration with error recovery |
| `/zerg:test` | Execute tests with coverage |
| `/zerg:analyze` | Static analysis, complexity metrics |
| `/zerg:review` | Two-stage code review |
| `/zerg:security` | Vulnerability scanning |
| `/zerg:refactor` | Automated code improvement |

### Utilities

| Command | Purpose |
|---------|---------|
| `/zerg:git` | Git operations (commit, PR, ship, bisect, etc.) |
| `/zerg:debug` | Deep diagnostic investigation |
| `/zerg:worker` | Internal zergling execution protocol |
| `/zerg:plugins` | Plugin system management |

### Documentation & AI

| Command | Purpose |
|---------|---------|
| `/zerg:document` | Generate component documentation (`--tone educational\|reference\|tutorial`) |
| `/zerg:index` | Generate project documentation wiki |
| `/zerg:estimate` | Effort estimation with PERT intervals |
| `/zerg:explain` | Educational code explanations |
| `/zerg:select-tool` | Intelligent MCP tool routing |

[Full Command Reference](https://github.com/rocklambros/zerg/wiki/Command-Reference)

---

## Configuration

ZERG is configured via `.zerg/config.yaml`:

```yaml
version: "1.0"
project_type: python

workers:
  default_count: 5
  max_count: 10
  timeout_seconds: 3600

quality_gates:
  lint:
    command: "ruff check ."
    required: true
  test:
    command: "pytest"
    required: true

plugins:
  context_engineering:
    enabled: true
    command_splitting: true
```

[Full Configuration Guide](https://github.com/rocklambros/zerg/wiki/Configuration)

---

## Documentation

| Resource | Description |
|----------|-------------|
| [Wiki: Home](https://github.com/rocklambros/zerg/wiki/Home) | Overview and quick navigation |
| [Wiki: Command Reference](https://github.com/rocklambros/zerg/wiki/Command-Reference) | All 26 commands with flags and examples |
| [Wiki: Tutorial](https://github.com/rocklambros/zerg/wiki/Tutorial) | Complete minerals-store walkthrough |
| [Wiki: Configuration](https://github.com/rocklambros/zerg/wiki/Configuration) | Config files and tuning options |
| [Wiki: Architecture](https://github.com/rocklambros/zerg/wiki/Architecture) | System design and module reference |
| [Wiki: Plugins](https://github.com/rocklambros/zerg/wiki/Plugins) | Quality gates, hooks, custom launchers |
| [Wiki: Context Engineering](https://github.com/rocklambros/zerg/wiki/Context-Engineering) | Token optimization techniques |
| [Wiki: Troubleshooting](https://github.com/rocklambros/zerg/wiki/Troubleshooting) | Common issues and solutions |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Detailed system architecture |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Development setup and PR process |
| [SECURITY.md](SECURITY.md) | Vulnerability reporting |
| [Discussions](https://github.com/rocklambros/zerg/discussions) | Questions, ideas, and community chat |

---

## Key Concepts

| Concept | Description |
|---------|-------------|
| **Spec as Memory** | Zerglings read spec files, not conversation history. Stateless and restartable. |
| **Exclusive File Ownership** | Each task owns specific files. No merge conflicts within a level. |
| **Levels** | Tasks grouped by dependencies. Level N completes before Level N+1. |
| **Verification Commands** | Every task has automated verification. Pass or fail, no subjectivity. |
| **Context Engineering** | Per-task context scoping minimizes token usage by 30-50%. |

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Zerglings not starting | Check Docker (`docker info`), API key, port availability |
| "No active feature" | Run `/zerg:plan <feature>` first |
| "Task graph not found" | Run `/zerg:design` first |
| Task stuck | `/zerg:debug` to diagnose, `/zerg:retry` to retry |
| Need to restart | `/zerg:rush --resume` continues from checkpoint |

[Full Troubleshooting Guide](https://github.com/rocklambros/zerg/wiki/Troubleshooting)

---

## License

MIT — see [LICENSE](LICENSE) for full text.
