<p align="center">
  <img src="logo/zerg_logo.png" alt="ZERG Logo" width="400">
</p>

# ZERG

**Zero-Effort Rapid Growth** - Parallel Claude Code execution system for spec-driven development.

> "Zerg rush your codebase." - Overwhelm features with coordinated zergling instances.

---

## Welcome to ZERG

Imagine you're building a house. Traditionally, you might have one contractor who does everything sequentially: foundation, then framing, then electrical, then plumbing. It works, but it's slow.

Now imagine you could have five contractors working simultaneously, each handling a different part of the house that doesn't depend on the others. The foundation crew works while the electrician preps materials. As soon as the foundation is done, multiple teams pour in to frame different sections in parallel.

**That's what ZERG does for software development.**

ZERG takes your feature requirements, breaks them into independent tasks, and assigns them to multiple Claude Code instances (we call them "zerglings") that execute in parallel. Each zergling operates in complete isolation with its own git branch, so there's never any conflict. When a level of tasks completes, ZERG automatically merges everything and starts the next level.

The result? Features that might take hours of sequential AI-assisted development can be completed in a fraction of the time.

---

## Table of Contents

- [How ZERG Thinks About Work](#how-zerg-thinks-about-work)
- [Installation](#installation)
- [Using ZERG](#using-zerg)
- [Your First ZERG Project](#your-first-zerg-project)
- [Understanding the Core Workflow](#understanding-the-core-workflow)
- [Complete Command Reference](#complete-command-reference)
- [Configuration Deep Dive](#configuration-deep-dive)
- [Architecture Explained](#architecture-explained)
- [When Things Go Wrong](#when-things-go-wrong)
- [Tutorial](#tutorial)

---

## How ZERG Thinks About Work

Before diving into commands, let's understand how ZERG approaches software development. This mental model will make everything else click.

### The Problem with Sequential Development

When you work with a single AI assistant on a complex feature, you encounter several bottlenecks:

1. **Context limits**: Long conversations hit token limits, losing important context
2. **Sequential execution**: Tasks that could run in parallel wait on each other
3. **Context pollution**: Debugging one issue can confuse work on another
4. **No isolation**: A mistake in one area can cascade to others

### ZERG's Solution: Spec-Driven Parallel Execution

ZERG solves these problems through three key principles:

**1. Specs as the Source of Truth**

Instead of relying on conversation history, ZERG writes everything to spec files. Zerglings don't remember previous conversations—they read their task specifications fresh each time. This means:
- No context limit issues (zerglings start fresh)
- Requirements are documented and versioned
- Any zergling can pick up any task

**2. Exclusive File Ownership**

Every file in your project is "owned" by exactly one task at a time. If Task A creates `models.py`, no other task at that level can touch it. This eliminates merge conflicts entirely—zerglings can work in parallel without stepping on each other's toes.

**3. Level-Based Dependency Management**

Tasks are organized into "levels" based on what they depend on:

```
Level 1: Foundation (no dependencies)
├── Create data models
├── Set up configuration
└── Define type schemas

Level 2: Core Logic (depends on Level 1)
├── Implement user service (needs models)
├── Implement product service (needs models)
└── Implement cart service (needs models, config)

Level 3: API Layer (depends on Level 2)
├── Create user endpoints (needs user service)
├── Create product endpoints (needs product service)
└── Create cart endpoints (needs cart service)
```

All Level 1 tasks run in parallel. When they're ALL done, ZERG merges their branches and starts Level 2. This ensures zerglings always have the dependencies they need.

### What Happens Under the Hood

When you run `/zerg:rush`, here's what actually happens:

1. **Orchestrator starts**: The main ZERG process loads your task graph
2. **Worktrees created**: Git worktrees give each zergling an isolated copy of the codebase
3. **Zerglings spawned**: Each zergling is a separate Claude Code process (or Docker container)
4. **Tasks assigned**: Zerglings claim tasks from the current level
5. **Parallel execution**: Zerglings implement their tasks simultaneously
6. **Verification**: Each task runs its verification command (tests, imports, etc.)
7. **Sync point**: When all Level N tasks complete, zergling branches merge
8. **Quality gates**: Linting, type checking, tests run on merged code
9. **Level advance**: If gates pass, Level N+1 begins
10. **Repeat**: Until all levels complete

This architecture means you can literally walk away while ZERG builds your feature. Come back to find everything implemented, tested, and merged.

---

## Installation

### What You'll Need

Before installing ZERG, make sure you have these prerequisites. Here's why each matters:

| Requirement | Version | Why It's Needed |
|-------------|---------|-----------------|
| **Python** | 3.11+ | ZERG is written in Python. Version 3.11+ provides the type hints and features we need |
| **Git** | 2.x+ | ZERG uses git worktrees extensively—each zergling gets its own isolated copy of your repo |
| **Docker** | 20.x+ | *Optional*. Enables container mode where zerglings run in isolated Docker containers |
| **Claude Code CLI** | Latest | Zerglings are Claude Code instances, so you need the CLI installed |
| **ANTHROPIC_API_KEY** | - | Environment variable that authenticates with Anthropic's API |

### Installing ZERG

```bash
# Clone the repository
git clone https://github.com/rocklambros/zerg.git
cd zerg

# Install in development mode
# The -e flag means "editable"—changes to the code take effect immediately
pip install -e .

# Or install with development dependencies (testing, linting, etc.)
pip install -e ".[dev]"

# Make /zerg:* commands available in ALL Claude Code sessions (any project)
zerg install-commands
```

The `install-commands` step symlinks ZERG's 19 command files into `~/.claude/commands/` so they work globally. Use `--force` to overwrite existing files, `--copy` to copy instead of symlink (auto-enabled on Windows), or `--target <dir>` for a custom location. To remove them later: `zerg uninstall-commands`.

### Verifying Your Installation

Let's make sure the prerequisites are working:

```bash
# Verify Python is installed
python --version

# Verify Git is installed
git --version

# Verify Claude Code CLI is installed
claude --version

# Verify your API key is set (you should see your key, not empty output)
echo $ANTHROPIC_API_KEY
```

Once those all check out, you're ready to go. To verify ZERG itself, open a Claude Code session in your project directory and use `/zerg:help` to see all available commands:

```claude
/zerg:help
```

**Expected output:**
```
Available ZERG commands:
  /zerg:analyze      Static analysis and quality metrics
  /zerg:build        Build with error recovery
  /zerg:cleanup      Remove ZERG artifacts
  /zerg:design       Generate architecture and task graph
  /zerg:git          Git operations and workflow
  /zerg:init         Initialize ZERG for a project
  /zerg:logs         Stream zergling logs
  /zerg:merge        Merge level branches
  /zerg:plan         Capture feature requirements
  /zerg:plugins      Inspect and validate plugins
  /zerg:refactor     Automated code improvement
  /zerg:retry        Retry failed tasks
  /zerg:review       Two-stage code review
  /zerg:rush         Launch parallel zerglings
  /zerg:security     Security rules management
  /zerg:status       Show execution status
  /zerg:stop         Stop zerglings
  /zerg:test         Run tests with coverage
  /zerg:debug Debug with root cause analysis
```

---

## Using ZERG

ZERG commands are **Claude Code slash commands**, not terminal/bash commands. They only work inside a Claude Code session. Here's how to get started:

First, open your terminal and navigate to your project directory, then launch Claude Code:

```bash
cd your-project
claude
```

Once you're inside the Claude Code session, you can use any `/zerg:*` command:

```claude
/zerg:init
/zerg:plan my-feature --socratic
/zerg:design
/zerg:rush --workers 5
```

Throughout this README, code blocks marked with `claude` contain Claude Code slash commands. Code blocks marked with `bash` contain regular terminal commands. Keep an eye on which is which -- it matters!

---

## Your First ZERG Project

Let's walk through the complete workflow by building something real. We'll create a simple REST API—nothing fancy, but enough to see ZERG in action.

### Step 1: Initialize Your Project

ZERG has two initialization modes that activate automatically based on your directory:

**Inception Mode** (empty directory): Creates a new project from scratch with guided setup
**Discovery Mode** (existing project): Analyzes your codebase and configures ZERG

Let's start fresh. In your terminal:

```bash
# Create and enter an empty directory
mkdir my-api && cd my-api
```

Then launch Claude Code and initialize ZERG:

```bash
claude
```

Inside Claude Code, run:

```claude
# Because the directory is empty, Inception Mode activates automatically
/zerg:init --security standard
```

**What's happening behind the scenes:**

1. ZERG detects the empty directory and enters Inception Mode
2. It asks you questions about your project (name, description, target platform)
3. Based on your answers, it recommends a technology stack
4. It generates a complete project scaffold with:
   - Source code structure
   - Test directory
   - Configuration files
   - Git repository with initial commit
5. Then it runs Discovery Mode to add ZERG infrastructure:
   - `.zerg/config.yaml` - ZERG configuration
   - `.devcontainer/` - Docker container definitions for zerglings
   - Security rules from TikiTribe/claude-secure-coding-rules

**Why the `--security standard` flag?**

This tells ZERG to configure zerglings with standard security isolation:
- Network isolation (zerglings can't make arbitrary network calls)
- Filesystem sandboxing (zerglings can only access the project directory)
- Secrets scanning (prevents accidental commit of API keys, etc.)

### Step 2: Plan Your Feature

Now let's plan a feature. Planning is crucial because it creates the specification documents that zerglings will read.

```claude
# Start planning with Socratic discovery mode
/zerg:plan user-auth --socratic
```

**What's happening:**

The `--socratic` flag triggers an interactive discovery session. Instead of you writing requirements, ZERG asks you structured questions in three rounds:

1. **Problem Space** (5 questions): What problem are we solving? Who's affected? Why now?
2. **Solution Space** (5 questions): What's the ideal solution? What constraints exist? What's out of scope?
3. **Implementation Space** (5 questions): What's the MVP? What can wait? How do we verify success?

This questioning technique (inspired by the Socratic method) helps you think through requirements you might have missed.

**Output created:**

After the session, ZERG creates `.gsd/specs/user-auth/requirements.md` containing:
- Your answers to all questions
- Structured problem statement
- Solution constraints
- Acceptance criteria

**Important:** Review this file! It's what zerglings will read. If something's wrong or missing, edit it now before proceeding.

### Step 3: Design the Architecture

With requirements captured, generate the technical design:

```claude
/zerg:design --feature user-auth
```

**What's happening:**

ZERG reads your requirements and generates:

1. **design.md**: Architecture document describing the technical approach
2. **task-graph.json**: The critical file that defines every task, its dependencies, file ownership, and verification commands

**Understanding task-graph.json:**

This file is the blueprint for parallel execution. Here's a simplified example:

```json
{
  "tasks": [
    {
      "id": "AUTH-L1-001",
      "title": "Create user models",
      "level": 1,
      "files": {
        "create": ["src/models/user.py"],  // This task OWNS this file
        "modify": [],
        "read": []
      },
      "verification": {
        "command": "python -c \"from src.models.user import User\""
      }
    }
  ]
}
```

Key things to understand:
- **Level**: Determines execution order. All level 1 tasks complete before any level 2 task starts
- **files.create**: Files this task will create. No other task at this level can create these files
- **files.modify**: Files this task will modify. Exclusive ownership at this level
- **files.read**: Files this task needs to read. Multiple tasks can read the same file
- **verification.command**: How ZERG knows the task succeeded. This command must exit with code 0

**Why file ownership matters:**

If two zerglings both try to edit `models.py` at the same time, you'd get merge conflicts. By giving each task exclusive ownership of specific files, ZERG guarantees conflict-free merges.

### Step 4: Launch the Rush

Time to build. This is where the magic happens:

```claude
# Preview what will happen (no actual execution)
/zerg:rush --dry-run

# When ready, launch for real
/zerg:rush --workers 5
```

**What's happening:**

1. ZERG creates 5 git worktrees (isolated copies of your repo)
2. Spawns 5 Claude Code zerglings (one per worktree)
3. Each zergling claims a task from Level 1
4. Zerglings implement their tasks in parallel
5. As tasks complete, zerglings claim more tasks
6. When all Level 1 tasks complete:
   - All zergling branches merge into a staging branch
   - Quality gates run (lint, typecheck, test)
   - If gates pass, staging merges to main
   - Zerglings rebase their worktrees
   - Level 2 begins
7. Repeat until all levels complete

**Why 5 zerglings?**

The `--workers 5` flag is a balance:
- More zerglings = more parallelism = faster completion
- But also = more API calls = higher cost
- And = more resource usage (memory, CPU)

Start with 3-5 zerglings for most features. You can adjust based on:
- How many tasks can actually run in parallel at each level
- Your API rate limits
- Your machine's resources

### Step 5: Monitor Progress

While zerglings are running:

```claude
# See current status (one-time snapshot)
/zerg:status

# Watch continuously with live updates
/zerg:status --watch

# View zergling logs in real-time
/zerg:logs --follow
```

**What the status shows:**

- Overall progress (tasks completed / total)
- Current level and zergling assignments
- Each zergling's current task and status
- Recent completions and any failures

### Step 6: Handle Issues (If Any)

If a task fails:

```claude
# See what went wrong
/zerg:logs 1 --level error  # Logs from zergling 1, errors only

# Retry the failed task
/zerg:retry AUTH-L2-003

# Or retry all failed tasks
/zerg:retry --all-failed
```

**Why tasks fail:**

- Verification command fails (tests don't pass, import errors)
- Zergling hits context limit (checkpoints and exits with code 2)
- Actual implementation error

For context limit issues, zerglings automatically checkpoint their progress. Just run `/zerg:rush --resume` to continue.

### Step 7: Cleanup

When everything's done:

```claude
/zerg:cleanup --feature user-auth
```

**What gets cleaned:**

- Git worktrees (`.zerg/worktrees/`)
- Zergling branches (`zerg/user-auth/worker-*`)
- State files (`.zerg/state/user-auth.json`)
- Log files (`.zerg/logs/worker-*.log`)

**What's preserved:**

- All your merged code (it's on main now)
- Spec files (`.gsd/specs/user-auth/`) - useful documentation
- ZERG configuration (`.zerg/config.yaml`)

---

## Understanding the Core Workflow

Now that you've seen the full workflow, let's understand each phase more deeply.

### Phase 1: Initialization (`/zerg:init`)

Initialization prepares your project for ZERG. It handles two scenarios:

**Inception Mode (Empty Directory)**

When you run `/zerg:init` in an empty directory, ZERG becomes a project bootstrapper:

1. **Gathers requirements**: Asks about project name, description, target platforms
2. **Recommends technology**: Suggests language, framework, package manager based on your needs
3. **Scaffolds project**: Generates complete project structure with:
   - Source directory with entry point
   - Test directory with initial tests
   - Configuration files (pyproject.toml, package.json, etc.)
   - README and .gitignore
4. **Initializes git**: Creates repo with initial commit
5. **Continues to Discovery Mode**: Adds ZERG infrastructure

**Discovery Mode (Existing Project)**

For existing projects, ZERG analyzes what you have:

1. **Detects stack**: Scans for package.json, pyproject.toml, Cargo.toml, etc.
2. **Identifies frameworks**: Recognizes FastAPI, Express, React, etc.
3. **Creates configuration**: Generates `.zerg/config.yaml` tailored to your stack
4. **Sets up containers**: Creates `.devcontainer/` for isolated zergling execution
5. **Fetches security rules**: Downloads secure coding rules for your languages

### Phase 2: Planning (`/zerg:plan`)

Planning captures requirements BEFORE any code is written. This is intentional—zerglings don't have access to your conversation history, only to spec files.

**Why Socratic Mode?**

The `--socratic` flag triggers structured discovery because:
- You might not know what you don't know
- Structured questions surface edge cases
- The transcript becomes documentation
- It forces clarity before implementation

**What Gets Created:**

`.gsd/specs/{feature}/requirements.md`:
```markdown
# Feature Requirements: user-auth

## Metadata
- **Feature**: user-auth
- **Status**: DRAFT  # Change to APPROVED when ready
- **Created**: 2026-01-26T10:30:00

## Discovery Transcript
### Problem Space
**Q:** What specific problem does this feature solve?
**A:** Users can't log in to the application...

## Acceptance Criteria
- [ ] Users can register with email/password
- [ ] Users can log in and receive JWT token
- [ ] Protected routes require valid token
```

**Important:** The Status field controls the workflow. Leave it as DRAFT while refining, change to APPROVED to signal "ready for design."

### Phase 3: Design (`/zerg:design`)

Design translates requirements into actionable tasks. This is where ZERG's parallel execution model comes to life.

**What Gets Created:**

1. **design.md**: High-level architecture document
2. **task-graph.json**: The execution blueprint

**Task Graph Deep Dive:**

The task graph is the heart of ZERG. Let's understand its structure:

```json
{
  "feature": "user-auth",
  "version": "2.0",
  "total_tasks": 12,
  "max_parallelization": 4,  // Most tasks that can run simultaneously

  "tasks": [...],  // Array of task definitions

  "levels": {
    "1": {
      "name": "foundation",
      "tasks": ["AUTH-L1-001", "AUTH-L1-002"],
      "parallel": true,
      "depends_on_levels": []  // No dependencies
    },
    "2": {
      "name": "services",
      "tasks": ["AUTH-L2-001", "AUTH-L2-002", "AUTH-L2-003"],
      "parallel": true,
      "depends_on_levels": [1]  // Needs level 1 complete
    }
  }
}
```

**Individual Task Structure:**

```json
{
  "id": "AUTH-L2-001",
  "title": "Implement auth service",
  "description": "JWT token generation and validation",
  "level": 2,
  "dependencies": ["AUTH-L1-001", "AUTH-L1-002"],

  "files": {
    "create": ["src/services/auth.py"],
    "modify": ["src/services/__init__.py"],
    "read": ["src/models/user.py", "src/config.py"]
  },

  "acceptance_criteria": [
    "generate_token() creates valid JWT",
    "verify_token() validates and decodes JWT",
    "Token expiration is configurable"
  ],

  "verification": {
    "command": "pytest tests/unit/test_auth_service.py -v",
    "timeout_seconds": 60
  }
}
```

**Why This Structure?**

- **id**: Unique identifier for tracking and retry
- **level**: Controls execution order
- **dependencies**: Explicit task-to-task dependencies (within level constraints)
- **files**: Enables conflict-free parallel execution
- **acceptance_criteria**: Zerglings know what "done" looks like
- **verification**: Automated pass/fail determination

### Phase 4: Execution (`/zerg:rush`)

The rush is where zerglings implement your feature in parallel.

**Execution Modes:**

| Mode | How Zerglings Run | When to Use |
|------|-----------------|-------------|
| `subprocess` | Local Python processes | Development, debugging, no Docker |
| `container` | Isolated Docker containers | Production, security, reproducibility |
| `task` | Claude Code Task sub-agents | Slash command execution (`/zerg:rush`) |
| `auto` | Prefers container, then subprocess, task if slash cmd | Default, recommended |

**What Each Zergling Does:**

1. **Claims a task**: Requests next available task from orchestrator
2. **Reads specs**: Loads task definition and feature specs
3. **Implements**: Writes code to fulfill acceptance criteria
4. **Commits**: Makes atomic commits to its branch
5. **Verifies**: Runs verification command
6. **Reports**: Signals completion (or failure) to orchestrator
7. **Repeats**: Claims next task

**Level Transitions:**

When all tasks at Level N complete:

1. **Collect**: Orchestrator gathers all zergling branches
2. **Merge**: Sequential merge into staging branch
3. **Gate**: Run quality checks (lint, typecheck, test)
4. **Promote**: If gates pass, merge staging to main
5. **Rebase**: Zerglings update their worktrees from main
6. **Advance**: Begin Level N+1 tasks

**Why Levels Matter:**

Levels enforce dependency order. If Level 2 tasks need Level 1 code:
- Zerglings at Level 2 can import from Level 1 files
- Those files exist because Level 1 completed first
- No import errors, no undefined references

### Phase 5: Monitoring (`/zerg:status`, `/zerg:logs`)

While zerglings execute, you need visibility into what's happening.

**Status Information:**

```
Progress: ████████████░░░░░░░░ 60% (24/40 tasks)

Level 3 of 5 │ Zerglings: 5 active

┌──────────┬────────────────────────────────┬──────────┬─────────┐
│ Zergling │ Current Task                   │ Progress │ Status  │
├──────────┼────────────────────────────────┼──────────┼─────────┤
│ Z-0      │ AUTH-L3-001: Create login API  │ ████░░   │ RUNNING │
│ Z-1      │ AUTH-L3-002: Create user API   │ ██████   │ VERIFY  │
│ Z-2      │ (waiting for dependency)       │ ░░░░░░   │ IDLE    │
└────────┴────────────────────────────────┴──────────┴─────────┘
```

**Status Meanings:**

| Status | What It Means | What's Happening |
|--------|---------------|------------------|
| RUNNING | Zergling actively coding | Claude Code is implementing the task |
| VERIFY | Running verification | Executing the verification command |
| IDLE | Waiting for work | No available tasks at current level |
| CHECKPOINT | Context limit hit | Zergling saving progress, will resume |
| CRASHED | Unexpected exit | Check logs for error details |

**Log Levels:**

| Level | What's Logged |
|-------|---------------|
| `debug` | Everything—very verbose, good for troubleshooting |
| `info` | Normal operations—task starts, completions, merges |
| `warn` | Potential issues—retry attempts, slow operations |
| `error` | Failures—task failures, verification failures |

---

## Complete Command Reference

Now let's cover every command with all its options. For each command, I'll explain not just WHAT each flag does, but WHY you'd use it.

### Workflow Commands

---

#### /zerg:init

**Purpose:** Initialize ZERG for a project—either creating a new project (Inception Mode) or configuring an existing one (Discovery Mode).

**When to use:** Once per project, at the very beginning.

```claude
/zerg:init [OPTIONS]
```

**Options Explained:**

| Flag | Type | Default | What It Does | When to Use It |
|------|------|---------|--------------|----------------|
| `--detect/--no-detect` | flag | `--detect` | Auto-detect project type from existing files | Use `--no-detect` if detection is wrong |
| `--workers`, `-w` | integer | `5` | Default zergling count for this project | Fewer for small projects, more for large ones |
| `--security` | choice | `standard` | Security isolation level | `strict` for production, `minimal` for debugging |
| `--with-security-rules/--no-security-rules` | flag | `--with-security-rules` | Download secure coding rules | Disable if offline or rules aren't needed |
| `--with-containers/--no-containers` | flag | `--no-containers` | Build devcontainer image immediately | Enable if you'll use container mode |
| `--force` | flag | `false` | Overwrite existing configuration | When reconfiguring a project |

**Security Levels Explained:**

| Level | What's Protected | Use Case |
|-------|------------------|----------|
| `minimal` | Nothing—zerglings have full access | Quick prototyping, debugging issues |
| `standard` | Network isolation, filesystem sandbox, secrets scanning | Normal development |
| `strict` | All above + read-only root filesystem, no privilege escalation | Production, sensitive codebases |

**Examples:**

```claude
# Basic initialization for most projects
/zerg:init

# Strict security for production codebase
/zerg:init --security strict

# Fast init without security rules (offline mode)
/zerg:init --no-security-rules

# Reconfigure an existing ZERG project
/zerg:init --force

# Prepare for container mode immediately
/zerg:init --with-containers
```

**What Gets Created:**

```
project/
├── .zerg/
│   ├── config.yaml          # ZERG settings
│   ├── state/               # Execution state (populated during rush)
│   ├── logs/                # Zergling logs (populated during rush)
│   └── worktrees/           # Git worktrees (populated during rush)
├── .devcontainer/
│   ├── devcontainer.json    # VS Code / container configuration
│   └── Dockerfile           # Multi-language zergling image
├── .gsd/
│   ├── PROJECT.md           # Project documentation
│   └── INFRASTRUCTURE.md    # Technical requirements
└── .claude/
    └── security-rules/      # Secure coding rules (if enabled)
```

---

#### /zerg:plan

**Purpose:** Capture comprehensive feature requirements before any code is written. This creates the specification documents that zerglings will read.

**When to use:** At the start of each new feature.

```claude
/zerg:plan [FEATURE] [OPTIONS]
```

**Arguments:**

| Argument | Required | What It Is |
|----------|----------|------------|
| `FEATURE` | Yes* | Feature name in kebab-case (e.g., `user-auth`, `payment-integration`). *Not required with `--from-issue` |

**Options Explained:**

| Flag | Type | Default | What It Does | When to Use It |
|------|------|---------|--------------|----------------|
| `--template`, `-t` | choice | `default` | Requirements document structure | `minimal` for prototypes, `detailed` for complex features |
| `--interactive/--no-interactive` | flag | `--interactive` | Enable/disable prompts | Disable for scripted/CI usage |
| `--from-issue` | string | - | Import from GitHub issue URL | When requirements are already in GitHub |
| `--socratic`, `-s` | flag | `false` | Use structured 3-round discovery | Recommended for complex features |
| `--rounds` | integer | `3` | Number of Socratic rounds | Increase for very complex features |
| `--verbose`, `-v` | flag | `false` | Show detailed output | When debugging planning issues |

**Understanding Socratic Mode:**

Socratic mode guides you through structured questions:

**Round 1 - Problem Space:**
These questions ensure you understand WHAT problem you're solving:
- What specific problem does this solve?
- Who are the users affected?
- What happens today without this feature?
- Why is solving this important now?
- How will we know when it's solved?

**Round 2 - Solution Space:**
These questions define the BOUNDARIES of your solution:
- What does the ideal solution look like?
- What constraints must we work within?
- What are non-negotiable requirements?
- What similar solutions exist?
- What should this explicitly NOT do?

**Round 3 - Implementation Space:**
These questions plan the HOW:
- What's the minimum viable version?
- What can be deferred to later?
- What are the biggest technical risks?
- How should we verify correctness?
- What documentation is needed?

**Examples:**

```claude
# Simple feature with minimal template
/zerg:plan caching --template minimal

# Complex feature with extended Socratic discovery
/zerg:plan user-authentication --socratic --rounds 5

# Import requirements from GitHub issue
/zerg:plan --from-issue https://github.com/org/repo/issues/42

# Non-interactive mode (for CI/scripts)
/zerg:plan api-v2 --no-interactive --template default
```

**What Gets Created:**

```
.gsd/
├── .current-feature              # Marks active feature
└── specs/
    └── {feature}/
        ├── requirements.md       # Requirements document
        └── .started              # Timestamp
```

---

#### /zerg:design

**Purpose:** Generate technical architecture and the task graph that defines parallel execution.

**When to use:** After requirements are approved and before rushing.

```claude
/zerg:design [OPTIONS]
```

**Options Explained:**

| Flag | Type | Default | What It Does | When to Use It |
|------|------|---------|--------------|----------------|
| `--feature`, `-f` | string | auto-detect | Which feature to design | When working on multiple features |
| `--max-task-minutes` | integer | `30` | Maximum duration per task | Decrease to create more, smaller tasks |
| `--min-task-minutes` | integer | `5` | Minimum duration per task | Increase to avoid tiny tasks |
| `--validate-only` | flag | `false` | Check existing task graph without regenerating | After manual edits to task-graph.json |
| `--verbose`, `-v` | flag | `false` | Show detailed output | When debugging design issues |

**Why Task Duration Matters:**

Task size affects parallelization:
- **Too large** (>45 min): Zerglings might hit context limits mid-task
- **Too small** (<5 min): Overhead of task setup exceeds value
- **Just right** (10-30 min): Enough work to be meaningful, not so much it risks timeout

**Examples:**

```claude
# Design current feature (auto-detected from .current-feature)
/zerg:design

# Design specific feature
/zerg:design --feature payment-system

# Validate task graph after manual edits
/zerg:design --validate-only

# Create smaller, more granular tasks
/zerg:design --max-task-minutes 15 --min-task-minutes 5
```

**What Gets Created:**

```
.gsd/specs/{feature}/
├── requirements.md      # (already existed)
├── design.md            # NEW: Architecture document
└── task-graph.json      # NEW: Task definitions
```

---

#### /zerg:rush

**Purpose:** Launch parallel zerglings to implement your feature. This is where the actual building happens.

**When to use:** After design is complete and you're ready to build.

```claude
/zerg:rush [OPTIONS]
```

**Options Explained:**

| Flag | Type | Default | What It Does | When to Use It |
|------|------|---------|--------------|----------------|
| `--workers`, `-w` | integer | `5` | Number of zerglings to spawn | Balance speed vs. cost |
| `--feature`, `-f` | string | auto-detect | Feature to build | When working on multiple features |
| `--level`, `-l` | integer | `1` | Starting level | Skip completed levels on resume |
| `--task-graph`, `-g` | path | auto-detect | Path to task-graph.json | Custom task graph location |
| `--mode`, `-m` | choice | `auto` | Zergling execution mode | Force subprocess or container |
| `--dry-run` | flag | `false` | Preview execution plan | Always run first to verify |
| `--resume` | flag | `false` | Continue from previous run | After interruption or failure |
| `--timeout` | integer | `3600` | Max execution time (seconds) | Increase for large features |
| `--verbose`, `-v` | flag | `false` | Show detailed output | When debugging execution |

**Understanding Execution Modes:**

| Mode | What Happens | Pros | Cons |
|------|--------------|------|------|
| `subprocess` | Zerglings run as local Python processes | Fast startup, easy debugging | Less isolation, shares resources |
| `container` | Zerglings run in Docker containers | Full isolation, reproducible | Slower startup, needs Docker |
| `auto` | Uses container if available, else subprocess | Best of both | Behavior depends on setup |

**Zergling Count Guidelines:**

| Zerglings | Best For | API Cost | Completion Speed |
|---------|----------|----------|------------------|
| 1-2 | Learning, small features | Low | Slow |
| 3-5 | Medium features, most use cases | Medium | Balanced |
| 6-10 | Large features, time-critical | High | Fast |

**Examples:**

```claude
# Preview execution plan first (always recommended)
/zerg:rush --dry-run

# Start with 5 zerglings (default)
/zerg:rush

# Resume after interruption
/zerg:rush --resume

# Force subprocess mode (no Docker)
/zerg:rush --mode subprocess --workers 3

# Skip to level 3 (levels 1-2 already done)
/zerg:rush --level 3 --resume

# Extended timeout for large feature
/zerg:rush --timeout 7200  # 2 hours
```

**What Gets Created During Rush:**

```
.zerg/
├── state/{feature}.json           # Execution state
├── logs/
│   ├── orchestrator.log           # Main process logs
│   ├── worker-{0-9}.log           # Individual zergling logs
│   ├── workers/
│   │   └── worker-{id}.jsonl      # Structured JSONL per-worker logs
│   └── tasks/
│       └── {task-id}/             # Per-task artifacts
│           ├── execution.jsonl    # Task execution events
│           ├── claude_output.txt  # Claude CLI output
│           ├── verification_output.txt
│           └── git_diff.patch     # Changes diff
└── worktrees/
    └── {feature}-worker-{0-9}/    # Git worktrees
```

---

### Monitoring Commands

---

#### /zerg:status

**Purpose:** Display current execution status and progress. Your window into what zerglings are doing.

```claude
/zerg:status [OPTIONS]
```

**Options Explained:**

| Flag | Type | Default | What It Does | When to Use It |
|------|------|---------|--------------|----------------|
| `--feature`, `-f` | string | auto-detect | Feature to show status for | Multiple features in progress |
| `--watch`, `-w` | flag | `false` | Continuous updates | During active rush |
| `--interval` | integer | `5` | Seconds between updates | Faster for more responsive display |
| `--level`, `-l` | integer | - | Filter to specific level | Focus on current level |
| `--json` | flag | `false` | JSON output | For scripting/CI |

**Understanding Status Display:**

```
═══════════════════════════════════════════════════════════════
Progress: ████████████░░░░░░░░ 60% (24/40 tasks)

Level 3 of 5 │ Zerglings: 5 active

┌──────────┬────────────────────────────────┬──────────┬─────────┐
│ Zergling │ Current Task                   │ Progress │ Status  │
├──────────┼────────────────────────────────┼──────────┼─────────┤
│ Z-0      │ TASK-015: Implement login API  │ ████░░   │ RUNNING │
│ Z-1      │ TASK-016: Create user service  │ ██████   │ VERIFY  │
│ Z-2      │ TASK-017: Add auth middleware  │ ██░░░░   │ RUNNING │
│ Z-3      │ (waiting for dependency)       │ ░░░░░░   │ IDLE    │
│ Z-4      │ TASK-018: Database migrations  │ ████░░   │ RUNNING │
└──────────┴────────────────────────────────┴──────────┴─────────┘

Recent: ✓ TASK-014 (Z-2) │ ✓ TASK-013 (Z-1) │ ✓ TASK-012 (Z-0)
═══════════════════════════════════════════════════════════════
```

**Status Icon Meanings:**

| Status | What Zergling Is Doing |
|--------|------------------------|
| RUNNING | Actively implementing task code |
| VERIFY | Running verification command |
| IDLE | No tasks available at current level |
| CHECKPOINT | Hit context limit, saving progress |
| CRASHED | Exited unexpectedly (check logs) |

**Examples:**

```claude
# Quick status check
/zerg:status

# Watch mode during active rush
/zerg:status --watch

# Faster refresh rate
/zerg:status --watch --interval 2

# JSON for scripting
/zerg:status --json
```

---

#### /zerg:logs

**Purpose:** View zergling and orchestrator logs. Essential for understanding what's happening and debugging issues.

```claude
/zerg:logs [WORKER_ID] [OPTIONS]
```

**Arguments:**

| Argument | Required | What It Is |
|----------|----------|------------|
| `WORKER_ID` | No | Specific zergling (0-9) to show logs for. Omit for all zerglings |

**Options Explained:**

| Flag | Type | Default | What It Does | When to Use It |
|------|------|---------|--------------|----------------|
| `--feature`, `-f` | string | auto-detect | Feature logs to show | Multiple features |
| `--tail`, `-n` | integer | `100` | Lines to show | Increase for more history |
| `--follow` | flag | `false` | Stream new logs in real-time | During active execution |
| `--level`, `-l` | choice | `info` | Log level filter | `debug` for troubleshooting |
| `--json` | flag | `false` | Raw JSON output | For log parsing |

**Log Levels Explained:**

| Level | What's Shown | When to Use |
|-------|--------------|-------------|
| `debug` | Everything including internal operations | Troubleshooting weird issues |
| `info` | Normal operations, task starts/completions | General monitoring |
| `warn` | Potential issues, retries, slow operations | Watching for problems |
| `error` | Failures only | Quick failure triage |

**Examples:**

```claude
# View recent logs from all zerglings
/zerg:logs

# Stream logs in real-time
/zerg:logs --follow

# Zergling 1's errors only
/zerg:logs 1 --level error

# Last 200 lines with debug detail
/zerg:logs --tail 200 --level debug
```

---

#### /zerg:stop

**Purpose:** Stop zergling execution, either gracefully (with checkpoint) or forcefully.

```claude
/zerg:stop [OPTIONS]
```

**Options Explained:**

| Flag | Type | Default | What It Does | When to Use It |
|------|------|---------|--------------|----------------|
| `--feature`, `-f` | string | auto-detect | Feature to stop | Multiple features |
| `--worker`, `-w` | integer | - | Stop only this zergling | One zergling having issues |
| `--force` | flag | `false` | Immediate termination | Graceful stop isn't working |
| `--timeout` | integer | `30` | Graceful shutdown timeout | Zerglings taking too long to stop |

**Graceful vs. Force:**

| Aspect | Graceful (default) | Force |
|--------|-------------------|-------|
| In-progress work | Checkpointed | Lost |
| State file | Updated | May be stale |
| Task status | PAUSED | FAILED |
| Can resume | Yes, from checkpoint | Yes, but may redo work |

**Examples:**

```claude
# Graceful stop all zerglings
/zerg:stop

# Stop one problematic zergling
/zerg:stop --worker 3

# Force stop when graceful hangs
/zerg:stop --force
```

---

### Task Management Commands

---

#### /zerg:retry

**Purpose:** Retry failed or blocked tasks. ZERG tracks retry counts to prevent infinite loops.

```claude
/zerg:retry [TASK_IDS...] [OPTIONS]
```

**Arguments:**

| Argument | Required | What It Is |
|----------|----------|------------|
| `TASK_IDS` | No | Specific task IDs to retry (e.g., `AUTH-L2-001`) |

**Options Explained:**

| Flag | Type | Default | What It Does | When to Use It |
|------|------|---------|--------------|----------------|
| `--feature`, `-f` | string | auto-detect | Feature containing tasks | Multiple features |
| `--level`, `-l` | integer | - | Retry all failed in level | Level-wide retry |
| `--all-failed`, `-a` | flag | `false` | Retry all failed tasks | After fixing systemic issue |
| `--force` | flag | `false` | Bypass 3-retry limit | Task keeps failing but you need it |
| `--timeout`, `-t` | integer | - | Override task timeout | Task needs more time |
| `--reset` | flag | `false` | Reset retry counters | Fresh start |
| `--dry-run` | flag | `false` | Show what would retry | Preview before action |
| `--worker`, `-w` | integer | - | Assign to specific zergling | Route to idle zergling |

**Why Retry Limits Exist:**

ZERG limits retries (default: 3) because:
- A task that keeps failing likely has a fundamental issue
- Infinite retries waste API credits
- Forces you to investigate and fix the root cause

Use `--force` or `--reset` sparingly, preferably after understanding why the task failed.

**Examples:**

```claude
# Retry specific task
/zerg:retry AUTH-L2-001

# Retry all failed tasks
/zerg:retry --all-failed

# Preview what would retry
/zerg:retry --all-failed --dry-run

# Force retry past limit (use sparingly)
/zerg:retry AUTH-L2-001 --force

# Reset all counters and retry
/zerg:retry --all-failed --reset
```

---

#### /zerg:merge

**Purpose:** Merge zergling branches after level completion. Usually automatic, but you can trigger manually.

```claude
/zerg:merge [OPTIONS]
```

**Options Explained:**

| Flag | Type | Default | What It Does | When to Use It |
|------|------|---------|--------------|----------------|
| `--feature`, `-f` | string | auto-detect | Feature to merge | Multiple features |
| `--level`, `-l` | integer | current | Specific level to merge | Manual level control |
| `--force` | flag | `false` | Merge despite conflicts | Last resort (not recommended) |
| `--abort` | flag | `false` | Abort in-progress merge | Merge went wrong |
| `--dry-run` | flag | `false` | Show merge plan only | Preview before merge |
| `--skip-gates` | flag | `false` | Skip quality checks | Debugging only |
| `--no-rebase` | flag | `false` | Don't rebase zergling branches | Preserve branch history |

**Merge Process Explained:**

1. **Collect**: Identify all zergling branches for the level
2. **Merge to staging**: Sequential merge into `zerg/{feature}/staging`
3. **Quality gates**: Run lint, typecheck, tests on staging
4. **Promote**: If gates pass, merge staging to main
5. **Rebase**: Update zergling branches from new main

**Why Quality Gates?**

Even with exclusive file ownership, merged code might have issues:
- Import errors (missing dependency between tasks)
- Type mismatches
- Integration test failures

Gates catch these before they hit main.

**Examples:**

```claude
# Preview merge plan
/zerg:merge --dry-run

# Merge specific level
/zerg:merge --level 2

# Abort failed merge
/zerg:merge --abort

# Skip gates for debugging (not for production)
/zerg:merge --skip-gates
```

---

#### /zerg:cleanup

**Purpose:** Remove ZERG artifacts after feature completion. Preserves your code, removes infrastructure.

```claude
/zerg:cleanup [OPTIONS]
```

**Options Explained:**

| Flag | Type | Default | What It Does | When to Use It |
|------|------|---------|--------------|----------------|
| `--feature`, `-f` | string | - | Feature to clean (required unless --all) | Normal cleanup |
| `--all` | flag | `false` | Clean all ZERG features | Fresh start |
| `--keep-logs` | flag | `false` | Preserve log files | Post-mortem analysis |
| `--keep-branches` | flag | `false` | Preserve git branches | Audit trail |
| `--dry-run` | flag | `false` | Preview without deleting | Safety check |

**What Gets Removed:**

| Category | What's Deleted | What's Preserved |
|----------|----------------|------------------|
| Worktrees | `.zerg/worktrees/{feature}-*` | - |
| Branches | `zerg/{feature}/*` | main, develop |
| State | `.zerg/state/{feature}.json` | - |
| Logs | `.zerg/logs/worker-*.log` | With --keep-logs |
| Containers | `zerg-worker-*` | - |
| Specs | - | `.gsd/specs/{feature}/` |
| Code | - | All merged changes |

**Examples:**

```claude
# Clean up completed feature
/zerg:cleanup --feature user-auth

# Preview cleanup first
/zerg:cleanup --feature user-auth --dry-run

# Keep logs for post-mortem
/zerg:cleanup --feature user-auth --keep-logs

# Clean everything
/zerg:cleanup --all
```

---

### Quality Commands

---

#### /zerg:test

**Purpose:** Run tests with coverage analysis. Auto-detects your test framework.

```claude
/zerg:test [OPTIONS]
```

**Options Explained:**

| Flag | Type | Default | What It Does | When to Use It |
|------|------|---------|--------------|----------------|
| `--generate`, `-g` | flag | `false` | Generate test stubs for uncovered code | Bootstrapping tests |
| `--coverage`, `-c` | flag | `false` | Report test coverage | Quality assessment |
| `--watch`, `-w` | flag | `false` | Rerun on file changes | TDD workflow |
| `--parallel`, `-p` | integer | - | Parallel test processes | Speed up large suites |
| `--framework` | choice | auto-detect | Test framework | Override detection |
| `--path` | path | `.` | Test file path | Run subset of tests |
| `--dry-run` | flag | `false` | Show command without running | Preview |
| `--json` | flag | `false` | JSON output | CI integration |

**Auto-Detected Frameworks:**

| Language | Frameworks Detected |
|----------|---------------------|
| Python | pytest, unittest |
| JavaScript/TypeScript | jest, mocha, vitest |
| Go | go test |
| Rust | cargo test |

**Examples:**

```claude
# Run all tests
/zerg:test

# With coverage report
/zerg:test --coverage

# Watch mode for TDD
/zerg:test --watch

# Parallel for speed
/zerg:test --parallel 4

# Specific test path
/zerg:test --path tests/unit/
```

---

#### /zerg:build

**Purpose:** Build orchestration with intelligent error recovery and retry logic.

```claude
/zerg:build [OPTIONS]
```

**Options Explained:**

| Flag | Type | Default | What It Does | When to Use It |
|------|------|---------|--------------|----------------|
| `--target`, `-t` | string | `all` | Build target | Specific component |
| `--mode`, `-m` | choice | `dev` | Build mode: dev/staging/prod | Environment-specific builds |
| `--clean` | flag | `false` | Clean before build | Fresh build |
| `--watch`, `-w` | flag | `false` | Rebuild on changes | Development |
| `--retry`, `-r` | integer | `3` | Retry attempts | Flaky builds |
| `--dry-run` | flag | `false` | Show build command | Preview |
| `--json` | flag | `false` | JSON output | CI integration |

**Examples:**

```claude
# Development build
/zerg:build

# Production build
/zerg:build --mode prod

# Clean build
/zerg:build --clean

# Watch mode
/zerg:build --watch
```

---

#### /zerg:analyze

**Purpose:** Static analysis, complexity metrics, and security scanning.

```claude
/zerg:analyze [PATH] [OPTIONS]
```

**Options Explained:**

| Flag | Type | Default | What It Does | When to Use It |
|------|------|---------|--------------|----------------|
| `--check`, `-c` | choice | `all` | Check type: lint, complexity, coverage, security | Focus on specific aspect |
| `--format`, `-f` | choice | `text` | Output format: text, json, sarif | IDE/CI integration |
| `--threshold`, `-t` | string | - | Custom thresholds | Project-specific standards |

**Check Types:**

| Check | What It Analyzes | Tools Used |
|-------|------------------|------------|
| `lint` | Code style, formatting | ruff, eslint, gofmt |
| `complexity` | Cyclomatic complexity | radon, plato |
| `coverage` | Test coverage | pytest-cov, istanbul |
| `security` | Vulnerabilities | bandit, semgrep |
| `all` | Everything | All above |

**Examples:**

```claude
# Full analysis
/zerg:analyze

# Lint only
/zerg:analyze --check lint

# Security scan
/zerg:analyze --check security

# Custom complexity threshold
/zerg:analyze --check complexity --threshold complexity=15

# SARIF for IDE
/zerg:analyze --format sarif
```

---

#### /zerg:review

**Purpose:** Two-stage code review workflow for spec compliance and quality.

```claude
/zerg:review [OPTIONS]
```

**Options Explained:**

| Flag | Type | Default | What It Does | When to Use It |
|------|------|---------|--------------|----------------|
| `--mode`, `-m` | choice | `full` | Review mode | Different review stages |
| `--files`, `-f` | string | - | Specific files | Focused review |
| `--output`, `-o` | path | - | Output file | Save review |
| `--json` | flag | `false` | JSON output | Automation |

**Review Modes:**

| Mode | What It Does | Output |
|------|--------------|--------|
| `prepare` | Generate PR description | Summary, checklist |
| `self` | Self-review checklist | Issues to address |
| `receive` | Process review feedback | Action items |
| `full` | Both stages | Complete review |

**Examples:**

```claude
# Full review
/zerg:review

# Prepare PR description
/zerg:review --mode prepare

# Self-review before PR
/zerg:review --mode self

# Save to file
/zerg:review --output review.md
```

---

### Development Commands

---

#### /zerg:refactor

**Purpose:** Automated code improvement and cleanup using various transforms.

```claude
/zerg:refactor [PATH] [OPTIONS]
```

**Options Explained:**

| Flag | Type | Default | What It Does | When to Use It |
|------|------|---------|--------------|----------------|
| `--transforms`, `-t` | string | all | Which improvements to apply | Target specific issues |
| `--dry-run` | flag | `false` | Show changes without applying | Preview before commit |
| `--interactive`, `-i` | flag | `false` | Approve each change | Careful refactoring |
| `--json` | flag | `false` | JSON output | Automation |

**Available Transforms:**

| Transform | What It Does | Example |
|-----------|--------------|---------|
| `dead-code` | Remove unused code | Delete unused imports |
| `simplify` | Simplify expressions | `if x == True:` → `if x:` |
| `types` | Strengthen type hints | `Any` → specific type |
| `patterns` | Apply design patterns | Extract repeated code |
| `naming` | Improve variable names | `x` → `user_count` |

**Examples:**

```claude
# All transforms, preview first
/zerg:refactor --dry-run

# Interactive mode
/zerg:refactor --interactive

# Just remove dead code
/zerg:refactor --transforms dead-code

# Type improvements
/zerg:refactor --transforms types
```

---

#### /zerg:debug

**Purpose:** Systematic debugging with root cause analysis using a four-phase diagnostic process.

```claude
/zerg:debug [OPTIONS]
```

**Options Explained:**

| Flag | Type | Default | What It Does | When to Use It |
|------|------|---------|--------------|----------------|
| `--error`, `-e` | string | - | Error message to analyze | Direct error input |
| `--stacktrace`, `-s` | path | - | Stack trace file | File-based input |
| `--verbose`, `-v` | flag | `false` | Detailed output | More diagnostic info |
| `--output`, `-o` | path | - | Save diagnostic report | Documentation |
| `--json` | flag | `false` | JSON output | Automation |

**Diagnostic Phases:**

1. **Symptom**: Parse error message/stack trace
2. **Hypothesis**: Generate possible causes
3. **Test**: Run diagnostic commands
4. **Root Cause**: Determine actual cause with confidence level

**Examples:**

```claude
# Analyze error message
/zerg:debug --error "ImportError: No module named 'foo'"

# Analyze stack trace file
/zerg:debug --stacktrace error.log

# Save diagnostic report
/zerg:debug --error "ConnectionError" --output diagnostic.md
```

---

#### /zerg:git

**Purpose:** Git operations with intelligent commit messages and workflow management.

```claude
/zerg:git [OPTIONS]
```

**Options Explained:**

| Flag | Type | Default | What It Does | When to Use It |
|------|------|---------|--------------|----------------|
| `--action`, `-a` | choice | `commit` | Git action | Different operations |
| `--push`, `-p` | flag | `false` | Push after commit | Quick push workflow |
| `--base`, `-b` | string | `main` | Base branch | Feature branches |
| `--name`, `-n` | string | - | Branch name | Creating branches |
| `--branch` | string | - | Branch to merge | Merge operations |
| `--strategy` | choice | `squash` | Merge strategy | How to merge |
| `--since` | string | - | Starting point | Changelog generation |

**Actions:**

| Action | What It Does |
|--------|--------------|
| `commit` | Analyze changes, generate conventional commit message |
| `branch` | Create feature branch with naming convention |
| `merge` | Merge with selected strategy |
| `sync` | Fetch and rebase from remote |
| `history` | Generate changelog from commits |
| `finish` | Complete feature branch workflow |

**Examples:**

```claude
# Commit with auto-generated message
/zerg:git --action commit

# Commit and push
/zerg:git --action commit --push

# Create feature branch
/zerg:git --action branch --name feature/auth

# Squash merge
/zerg:git --action merge --branch feature/auth --strategy squash
```

---

### Infrastructure Commands

---

#### /zerg:security

**Purpose:** Manage secure coding rules from TikiTribe/claude-secure-coding-rules.

```claude
/zerg:security COMMAND [OPTIONS]
```

**Subcommands:**

| Command | What It Does | When to Use |
|---------|--------------|-------------|
| `detect` | Detect your project's technology stack | See what ZERG found |
| `list` | Show applicable security rules | Review rules |
| `fetch` | Download rules for your stack | Initial setup |
| `integrate` | Full workflow: detect → fetch → integrate | One-command setup |

**Examples:**

```claude
# See detected stack
/zerg:security detect

# List applicable rules
/zerg:security list

# Full integration
/zerg:security integrate
```

---

#### /zerg:worker

**Purpose:** Zergling execution protocol. This is what runs INSIDE zerglings—you typically don't call it directly.

**Environment Variables Zerglings Use:**

| Variable | Purpose |
|----------|---------|
| `ZERG_WORKER_ID` | Zergling identifier (0-9) |
| `ZERG_FEATURE` | Feature being built |
| `ZERG_BRANCH` | Zergling's git branch |
| `ZERG_SPEC_DIR` | Path to spec files |

**Exit Codes:**

| Code | Meaning | What Happens Next |
|------|---------|-------------------|
| 0 | All tasks completed | Zergling done |
| 1 | Unrecoverable error | Task marked failed |
| 2 | Context limit reached | Checkpoint saved, can resume |
| 3 | All remaining tasks blocked | Zergling waits |
| 130 | Interrupted (SIGINT) | Graceful stop |

---

## Configuration Deep Dive

### The Configuration File

ZERG's behavior is controlled by `.zerg/config.yaml`:

```yaml
version: "1.0"
project_type: python  # Detected or specified

# Zergling settings
workers:
  default_count: 5      # Default for /zerg:rush
  max_count: 10         # Never spawn more than this
  context_threshold: 0.7  # Checkpoint at 70% context usage
  timeout_seconds: 3600   # 1 hour max per task

# Security settings
security:
  network_isolation: true      # Block external network
  filesystem_sandbox: true     # Restrict to project directory
  secrets_scanning: true       # Scan for leaked credentials

# Quality gates (run after each level merge)
quality_gates:
  lint:
    command: "ruff check ."
    required: true           # Fail merge if this fails
  typecheck:
    command: "mypy ."
    required: false          # Warning only
  test:
    command: "pytest"
    required: true

# MCP servers for zerglings
mcp_servers:
  - name: filesystem
    command: npx
    args: ["-y", "@anthropic/mcp-filesystem"]
```

### Tuning Zergling Count

| Scenario | Recommended Zerglings | Why |
|----------|------------------------|-----|
| Learning ZERG | 1-2 | See what's happening clearly |
| Small feature (<10 tasks) | 2-3 | Avoid idle zerglings |
| Medium feature (10-30 tasks) | 3-5 | Good balance |
| Large feature (30+ tasks) | 5-8 | Maximize parallelism |
| Very large feature | 8-10 | Maximum throughput |

**Considerations:**
- More zerglings = higher API cost (parallel calls)
- More zerglings = more memory usage (worktrees)
- Zerglings beyond max parallelization at any level are idle

### Container Worker Memory Requirements

When running in container mode (`--mode container`), each zergling runs in a Docker container with the following processes:

| Component | Typical Memory |
|-----------|---------------|
| Ubuntu base OS | ~150 MB |
| Node.js + Claude Code CLI | ~450 MB |
| MCP servers (filesystem, github, fetch) | ~300 MB |
| Python 3.12 + ZERG worker process | ~250 MB |
| Git operations | ~10 MB |
| Buffer/overhead | ~400 MB |
| **Total** | **~1.6 GB** |

**Recommended limits:**

| Setting | Memory | Use Case |
|---------|--------|----------|
| Minimum | `2g` | Simple tasks, tight resources, no MCP servers |
| Safe minimum | `3g` | Most workloads with comfortable headroom |
| **Default** | **`4g`** | **Recommended for production use** |
| Heavy workloads | `6g`-`8g` | Large file operations, complex tasks |

Configure in `.zerg/config.yaml`:

```yaml
resources:
  container_memory_limit: "4g"   # Docker --memory flag
  container_cpu_limit: 2.0       # Docker --cpus flag
```

**Planning total host memory:** Each zergling needs its own container. With 5 zerglings at 4 GB each, plan for ~20 GB available to Docker. The orchestrator itself runs on the host and uses minimal memory (~100 MB).

### Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `ANTHROPIC_API_KEY` | Yes | API authentication |
| `ZERG_LOG_LEVEL` | No | Logging verbosity: debug, info, warn, error |
| `ZERG_DEBUG` | No | Enable debug mode (very verbose) |

### Structured Logging

ZERG uses structured JSONL logging for machine-readable diagnostics alongside traditional text logs.

**Per-worker logs** are written to `.zerg/logs/workers/worker-{id}.jsonl`. Each line is a JSON object with fields: `ts`, `level`, `worker_id`, `feature`, `message`, `task_id`, `phase`, `event`, `data`, `duration_ms`. Log files auto-rotate at 50 MB.

**Per-task artifacts** are captured in `.zerg/logs/tasks/{task-id}/`:
- `execution.jsonl` — structured execution events
- `claude_output.txt` — Claude CLI stdout/stderr
- `verification_output.txt` — verification command output
- `git_diff.patch` — diff of changes made by the task

**Log phases**: `CLAIM`, `EXECUTE`, `VERIFY`, `COMMIT`, `CLEANUP`

**Log events**: `TASK_STARTED`, `TASK_COMPLETED`, `TASK_FAILED`, `VERIFICATION_PASSED`, `VERIFICATION_FAILED`, `ARTIFACT_CAPTURED`, `LEVEL_STARTED`, `LEVEL_COMPLETE`, `MERGE_STARTED`, `MERGE_COMPLETE`

**Querying**: The log aggregator (`zerg/log_aggregator.py`) provides read-side aggregation — no pre-built aggregate file. It merges JSONL files by timestamp at query time, with support for filtering by worker, task, level, phase, time range, and text search.

### Pre-commit Hooks

ZERG includes comprehensive pre-commit hooks that validate commits before creation. The hooks are located at `.zerg/hooks/pre-commit` and can be installed via `/zerg:init`.

**Security Checks (Block on Violation)**

| Check | What It Detects | Pattern Example |
|-------|-----------------|-----------------|
| AWS Keys | Access key IDs | `AKIA...` (20 chars) |
| GitHub PATs | Personal access tokens | `ghp_...`, `github_pat_...` |
| OpenAI Keys | API keys | `sk-...` (48 chars) |
| Anthropic Keys | API keys | `sk-ant-...` |
| Private Keys | RSA/DSA/EC/OPENSSH headers | `-----BEGIN RSA PRIVATE KEY-----` |
| Shell Injection | Dangerous subprocess patterns | `shell=True`, `os.system()` |
| Code Injection | Dynamic code execution | `eval()`, `exec()` |
| Unsafe Deserialization | Pickle vulnerabilities | `pickle.load()`, `pickle.loads()` |
| Sensitive Files | Credential files | `.env`, `credentials.json` |

**Quality Checks (Warn on Violation)**

| Check | What It Detects |
|-------|-----------------|
| Ruff Lint | Style and syntax issues in staged Python files |
| Debugger Statements | `breakpoint()`, `pdb.set_trace()`, `import pdb` |
| Merge Markers | Unresolved conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`) |
| Large Files | Files exceeding 5MB |

**ZERG-Specific Checks (Warn on Violation)**

| Check | What It Validates |
|-------|-------------------|
| Branch Naming | ZERG branches should follow `zerg/{feature}/worker-{N}` |
| Print Statements | Warns on `print()` in `zerg/` directory (use logging) |
| Hardcoded URLs | `localhost:PORT`, `127.0.0.1:PORT` outside tests |

**Exempt Paths**: Tests (`tests/`, `*_test.py`, `test_*.py`), fixtures, and `conftest.py` are exempt from security checks.

**Installation:**

Hooks are installed automatically when you run init inside Claude Code:

```claude
/zerg:init
```

Or you can manually copy them in your terminal:

```bash
cp .zerg/hooks/pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

**Configuration** (in `.zerg/config.yaml`):
```yaml
hooks:
  pre_commit:
    enabled: true
    security_checks:
      secrets_detection: true
      shell_injection: true
      code_injection: true
      block_on_violation: true  # Security issues block commits
    quality_checks:
      ruff_lint: true
      warn_on_violation: true  # Quality issues warn but don't block
    exempt_paths:
      - "tests/"
      - "fixtures/"
```

### Plugin System

ZERG supports three types of plugins for extending orchestration behavior:

| Plugin Type | Purpose | Example |
|-------------|---------|---------|
| **QualityGatePlugin** | Custom quality gates run after merge | Custom linter, license checker |
| **LifecycleHookPlugin** | React to execution events (observational) | Slack notifications, metrics export |
| **LauncherPlugin** | Custom worker launch strategies | Kubernetes, SSH, cloud VMs |

**Plugin Registry**: The `PluginRegistry` manages hooks, gates, and launchers. It dispatches lifecycle events, runs plugin gates, and resolves launcher plugins by name.

**Lifecycle Events** (8 hook points):

| Event | When Fired |
|-------|------------|
| `task_started` | Worker begins a task |
| `task_completed` | Task finishes (success or failure) |
| `level_complete` | All tasks in a level done |
| `merge_complete` | Branch merge finishes |
| `rush_finished` | Entire rush completes |
| `quality_gate_run` | A quality gate executes |
| `worker_spawned` | Worker process starts |
| `worker_exited` | Worker process ends |

**Configuration** in `.zerg/config.yaml`:

```yaml
plugins:
  enabled: true
  hooks:
    - event: task_completed
      command: "notify-slack --channel builds"
      timeout: 60
  quality_gates:
    - name: license-check
      command: "license-checker --verify"
      required: true
      timeout: 300
  launchers:
    - name: k8s
      entry_point: "mypackage.launchers:K8sLauncher"
```

**Entry Point Discovery**: Plugins can be auto-discovered via Python entry points under the `zerg.plugins` group:

```toml
# In your plugin's pyproject.toml
[project.entry-points."zerg.plugins"]
my-gate = "mypackage.gates:MyGate"
```

Use `/zerg:plugins` to list, inspect, and validate installed plugins.

---

## Architecture Explained

### Directory Structure

Understanding where things live helps troubleshoot issues:

```
project/
├── .zerg/                          # ZERG runtime (gitignored)
│   ├── config.yaml                 # Your configuration
│   ├── state/
│   │   └── {feature}.json          # Execution state
│   ├── logs/
│   │   ├── orchestrator.log        # Main process logs
│   │   ├── worker-{id}.log         # Per-zergling logs
│   │   ├── workers/                # Structured JSONL per-worker
│   │   │   └── worker-{id}.jsonl
│   │   └── tasks/                  # Per-task artifacts
│   │       └── {task-id}/
│   ├── worktrees/
│   │   └── {feature}-worker-N/     # Isolated zergling git worktrees
│   └── worker_entry.sh             # Zergling startup script
│
├── .devcontainer/                  # Container configuration
│   ├── devcontainer.json           # VS Code devcontainer
│   ├── Dockerfile                  # Zergling image definition
│   ├── post-create.sh              # Container setup script
│   └── post-start.sh               # Zergling initialization
│
├── .gsd/                           # GSD specification (committed)
│   ├── PROJECT.md                  # Project documentation
│   ├── INFRASTRUCTURE.md           # Infrastructure requirements
│   ├── STATE.md                    # Human-readable progress
│   ├── .current-feature            # Active feature marker
│   └── specs/
│       └── {feature}/
│           ├── requirements.md     # Feature requirements
│           ├── design.md           # Architecture
│           ├── task-graph.json     # Task definitions
│           └── worker-assignments.json  # Who's doing what
│
├── .claude/                        # Claude Code configuration
│   └── security-rules/             # Secure coding rules
│
└── CLAUDE.md                       # Project instructions for Claude
```

### Execution Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    YOU RUN: /zerg:rush                            │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR STARTS                           │
│  • Loads task-graph.json                                        │
│  • Creates git worktrees for each zergling                      │
│  • Spawns zergling processes/containers                         │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    LEVEL 1 BEGINS                                │
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐          │
│  │Zergling 0│  │Zergling 1│  │Zergling 2│  │Zergling 3│  ...    │
│  │Task 001  │  │Task 002  │  │Task 003  │  │  IDLE    │          │
│  │models.py │  │config.py │  │types.py  │  │          │          │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘          │
│       │            │            │                               │
│       ▼            ▼            ▼                               │
│  [commits]    [commits]    [commits]                           │
│  [verifies]   [verifies]   [verifies]                          │
│       │            │            │                               │
│       └────────────┴────────────┘                               │
│                    │                                             │
│                    ▼                                             │
│          ALL LEVEL 1 COMPLETE                                   │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SYNC POINT                                    │
│  • Merge all zergling branches → staging                        │
│  • Run quality gates (lint, typecheck, test)                    │
│  • If pass: merge staging → main                                │
│  • Rebase all zergling branches from main                       │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    LEVEL 2 BEGINS                                │
│  (Zerglings can now import from Level 1 code)                   │
│  ... repeat until all levels complete ...                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## When Things Go Wrong

### Zerglings Not Starting

**Symptoms:** `/zerg:rush` hangs or zerglings fail to spawn

**Diagnosis:**
```bash
# Check Docker is running (if using container mode)
docker info

# Check API key is set
echo $ANTHROPIC_API_KEY

# Check port availability (zerglings use 49152+)
netstat -an | grep 49152
```

**Solutions:**

Inside Claude Code, force subprocess mode:

```claude
/zerg:rush --mode subprocess
```

Or check the orchestrator logs from your terminal:

```bash
cat .zerg/logs/orchestrator.log
```

### Tasks Failing Verification

**Symptoms:** Tasks marked as failed, verification command errors

**Diagnosis:**

From your terminal, inspect the verification command:

```bash
cat .gsd/specs/{feature}/task-graph.json | jq '.tasks[] | select(.id == "TASK-001") | .verification'
```

Inside Claude Code, check zergling logs:

```claude
/zerg:logs 1 --level error
```

You can also run verification manually in the worktree from your terminal:

```bash
cd .zerg/worktrees/{feature}-worker-1
python -c "from src.models import User"  # Or whatever the command is
```

**Solutions:**

Inside Claude Code:

```claude
# Debug the error
/zerg:debug --error "ImportError: cannot import name 'User'"

# Retry with extended timeout
/zerg:retry TASK-001 --timeout 120

# If systemic issue, fix and retry all
/zerg:retry --all-failed --reset
```

### Merge Conflicts

**Symptoms:** Merge fails, conflict messages

**This should be rare** because of exclusive file ownership. If it happens:

**Diagnosis:**
```bash
# Check task graph for file overlap
cat .gsd/specs/{feature}/task-graph.json | jq '.tasks[].files'
```

**Solutions:**

Inside Claude Code:

```claude
# Abort and investigate
/zerg:merge --abort

# Check conflict details
/zerg:status --verbose

# If task graph has file overlap, fix it and restart
/zerg:design --validate-only
```

### Context Limit Reached (Exit Code 2)

**Symptoms:** Zergling exits with "context limit reached", status shows CHECKPOINT

**This is normal behavior**, not an error. Zerglings checkpoint when they're running low on context.

**Solution:**

Inside Claude Code:

```claude
# Simply resume -- zerglings will pick up from their checkpoints
/zerg:rush --resume
```

### Quick Recovery Commands

Inside Claude Code:

```claude
# Resume interrupted execution
/zerg:rush --resume

# Check current state
/zerg:status --json

# Reset and retry a level
/zerg:retry --level 2 --reset

# Nuclear option: clean and restart
/zerg:cleanup --all
/zerg:rush
```

You can also inspect the state JSON from your terminal:

```bash
cat .zerg/state/{feature}.json | jq '.levels'
```

---

## Tutorial

For a hands-on, step-by-step walkthrough building a real application with ZERG, see:

**[Tutorial: Building a Minerals Store with ZERG](docs/tutorial-minerals-store.md)**

This tutorial builds a Starcraft 2 themed ecommerce API and covers:
- Setting up a new project with Inception Mode
- Using Socratic discovery for requirements
- Understanding the task graph and file ownership
- Watching parallel execution in action
- Handling failures and retries
- Quality gates and merging
- Final cleanup

---

## Getting Help

- **GitHub Issues**: [github.com/rocklambros/zerg/issues](https://github.com/rocklambros/zerg/issues)
- **Command help**: `/zerg:<command> --help`
- **Verbose mode**: Add `--verbose` to any command for more detail

---

## License

MIT

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.
