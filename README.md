# ZERG

Parallel Claude Code execution system for spec-driven development.

> "Zerg rush your codebase." - Overwhelm features with coordinated worker instances.

## Table of Contents

- [Overview](#overview)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Command Reference](#command-reference)
  - [Workflow Commands](#workflow-commands)
  - [Monitoring Commands](#monitoring-commands)
  - [Task Commands](#task-commands)
  - [Quality Commands](#quality-commands)
  - [Infrastructure Commands](#infrastructure-commands)
- [Configuration](#configuration)
- [How It Works](#how-it-works)
- [Troubleshooting](#troubleshooting)

---

## Overview

ZERG combines three approaches:
1. **GSD Methodology**: Spec-first development, fresh agents per task, max 3 tasks per context
2. **Claude Code Skills**: `/zerg:*` skills invoke CLI commands with structured prompts
3. **Devcontainers**: Isolated parallel execution environments

You write specs. ZERG spawns multiple Claude Code instances. They build your feature in parallel.

---

## Installation

### Requirements

- Python 3.11+
- Docker (for container mode)
- Claude Code CLI
- Git
- `ANTHROPIC_API_KEY` environment variable

### Install from Source

```bash
git clone https://github.com/yourname/zerg.git
cd zerg
pip install -e .

# Verify
zerg --help
```

### Install in Your Project

```bash
cd your-project
pip install zerg

# Initialize ZERG
zerg init
```

---

## Quick Start

ZERG operates in two modes depending on your starting point:

### Inception Mode (New Project)

Start a project from scratch with guided setup:

```bash
# Create empty directory
mkdir my-new-api && cd my-new-api

# Run ZERG init - detects empty directory, starts Inception Mode
zerg init --security standard

# Follow the interactive prompts:
#   - Project name and description
#   - Target platform (api, cli, web, library)
#   - Technology stack recommendation
#   - Project scaffolding
```

Inception Mode:
1. **Gathers Requirements** - Interactive prompts capture project goals
2. **Recommends Technology** - Suggests language, framework, tools
3. **Scaffolds Project** - Generates complete project structure
4. **Initializes Git** - Creates initial commit

### Discovery Mode (Existing Project)

Add ZERG to an existing codebase:

```bash
# Navigate to your existing project
cd your-existing-project

# Initialize ZERG - detects existing project, runs Discovery Mode
zerg init --security standard

# ZERG analyzes your project and configures itself
```

### After Initialization

```bash
# 1. Plan a feature (captures requirements)
zerg plan user-authentication --socratic

# 2. Design the implementation (creates task graph)
zerg design --feature user-authentication

# 3. Launch parallel workers
zerg rush --workers 5

# 5. Monitor progress
zerg status --watch
```

### Using Claude Code Skills

In Claude Code, use slash commands:

| Command | Description |
|---------|-------------|
| `/zerg:init` | Initialize ZERG for the project |
| `/zerg:plan <feature>` | Capture feature requirements |
| `/zerg:design` | Generate architecture and task graph |
| `/zerg:rush` | Launch parallel worker execution |
| `/zerg:status` | Show execution progress |
| `/zerg:stop` | Stop workers gracefully or forcefully |
| `/zerg:logs` | Stream worker logs |
| `/zerg:worker` | Enter worker execution mode (internal) |
| `/zerg:retry` | Retry failed or blocked tasks |
| `/zerg:merge` | Merge completed level branches |
| `/zerg:cleanup` | Remove ZERG artifacts |
| `/zerg:test` | Run tests with coverage |
| `/zerg:build` | Build with error recovery |
| `/zerg:analyze` | Static analysis and metrics |
| `/zerg:review` | Two-stage code review |
| `/zerg:troubleshoot` | Debug with root cause analysis |
| `/zerg:refactor` | Automated code improvement |
| `/zerg:git` | Git operations and workflow |
| `/zerg:security` | Security rules management |

---

## Command Reference

### Workflow Commands

Commands for the main ZERG workflow: initialize, plan, design, and execute.

---

#### `zerg init`

Initialize ZERG for the current project. Creates `.zerg/` configuration and `.devcontainer/` setup.

**Usage:**
```bash
zerg init [OPTIONS]
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--detect/--no-detect` | `--detect` | Auto-detect project type |
| `--workers`, `-w` | `5` | Default worker count |
| `--security` | `standard` | Security level: `minimal`, `standard`, `strict` |
| `--with-security-rules/--no-security-rules` | `--with-security-rules` | Fetch secure coding rules |
| `--with-containers/--no-containers` | `--no-containers` | Build devcontainer image |
| `--force` | `false` | Overwrite existing configuration |

**Examples:**
```bash
# Basic initialization
zerg init

# Strict security with 3 workers
zerg init --workers 3 --security strict

# Force reinitialize with container build
zerg init --force --with-containers
```

---

#### `zerg plan`

Capture feature requirements. Creates `.gsd/specs/{feature}/requirements.md`.

**Usage:**
```bash
zerg plan [FEATURE] [OPTIONS]
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--template`, `-t` | `default` | Template: `default`, `minimal`, `detailed` |
| `--interactive/--no-interactive` | `--interactive` | Interactive mode |
| `--from-issue` | - | Import from GitHub issue URL |
| `--socratic`, `-s` | `false` | Use structured 3-round discovery mode |
| `--rounds` | `3` | Number of rounds for socratic mode (max: 5) |
| `--verbose`, `-v` | `false` | Verbose output |

**Examples:**
```bash
# Interactive planning
zerg plan user-auth

# Socratic discovery (recommended)
zerg plan user-auth --socratic

# Import from GitHub issue
zerg plan --from-issue https://github.com/org/repo/issues/123

# Non-interactive with minimal template
zerg plan user-auth --template minimal --no-interactive
```

---

#### `zerg design`

Generate architecture and task graph. Creates `design.md` and `task-graph.json`.

**Usage:**
```bash
zerg design [OPTIONS]
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--feature`, `-f` | current | Feature name (uses current if not specified) |
| `--max-task-minutes` | `30` | Maximum minutes per task |
| `--min-task-minutes` | `5` | Minimum minutes per task |
| `--validate-only` | `false` | Validate existing task graph only |
| `--verbose`, `-v` | `false` | Verbose output |

**Examples:**
```bash
# Design current feature
zerg design

# Design specific feature
zerg design --feature user-auth

# Validate existing task graph
zerg design --validate-only

# Custom task duration bounds
zerg design --max-task-minutes 45 --min-task-minutes 10
```

---

#### `zerg rush`

Launch parallel worker execution. Spawns workers, assigns tasks, monitors progress.

**Usage:**
```bash
zerg rush [OPTIONS]
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--workers`, `-w` | `5` | Number of workers to launch |
| `--feature`, `-f` | auto-detect | Feature name |
| `--level`, `-l` | - | Start from specific level |
| `--dry-run` | `false` | Show plan without executing |
| `--resume` | `false` | Continue from previous run |
| `--timeout` | `3600` | Max execution time (seconds) |
| `--task-graph`, `-g` | - | Path to task-graph.json |
| `--mode`, `-m` | `auto` | Worker mode: `subprocess`, `container`, `auto` |
| `--verbose`, `-v` | `false` | Verbose output |

**Examples:**
```bash
# Launch 5 workers
zerg rush --workers 5

# Preview execution plan
zerg rush --feature user-auth --dry-run

# Resume previous execution with 3 workers
zerg rush --resume --workers 3

# Use container mode
zerg rush --mode container --workers 5

# Start from level 2
zerg rush --level 2
```

---

### Monitoring Commands

Commands for monitoring and controlling execution.

---

#### `zerg status`

Show execution progress. Displays worker status, level progress, and recent events.

**Usage:**
```bash
zerg status [OPTIONS]
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--feature`, `-f` | auto-detect | Feature to show status for |
| `--watch`, `-w` | `false` | Continuous update mode |
| `--json` | `false` | Output as JSON |
| `--level`, `-l` | - | Filter to specific level |
| `--interval` | `5` | Watch interval (seconds) |

**Examples:**
```bash
# Show current status
zerg status

# Watch with live updates
zerg status --watch

# JSON output for scripting
zerg status --feature user-auth --json

# Filter to level 2
zerg status --level 2
```

---

#### `zerg stop`

Stop execution gracefully or forcefully. Sends checkpoint signal for graceful shutdown.

**Usage:**
```bash
zerg stop [OPTIONS]
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--feature`, `-f` | auto-detect | Feature to stop |
| `--worker`, `-w` | - | Stop specific worker |
| `--force` | `false` | Force immediate termination |
| `--timeout` | `30` | Graceful shutdown timeout (seconds) |

**Examples:**
```bash
# Graceful stop all workers
zerg stop

# Stop specific feature
zerg stop --feature user-auth

# Force kill specific worker
zerg stop --worker 3 --force
```

---

#### `zerg logs`

Stream worker logs with optional filtering.

**Usage:**
```bash
zerg logs [WORKER_ID] [OPTIONS]
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--feature`, `-f` | auto-detect | Feature name |
| `--tail`, `-n` | `100` | Lines to show |
| `--follow` | `false` | Stream new logs |
| `--level`, `-l` | `info` | Log level filter: `debug`, `info`, `warn`, `error` |
| `--json` | `false` | Raw JSON output |

**Examples:**
```bash
# Show recent logs from all workers
zerg logs

# Show logs from worker 1
zerg logs 1

# Stream logs in real-time
zerg logs --follow --level debug

# Last 50 lines with feature filter
zerg logs --tail 50 --feature user-auth
```

---

### Task Commands

Commands for managing individual tasks.

---

#### `zerg retry`

Retry failed or blocked tasks. Re-queues tasks for execution.

**Usage:**
```bash
zerg retry [TASK_ID] [OPTIONS]
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--feature`, `-f` | auto-detect | Feature name |
| `--all-failed` | `false` | Retry all failed tasks |
| `--reset` | `false` | Reset task to fresh state |
| `--worker`, `-w` | - | Assign to specific worker |

**Examples:**
```bash
# Retry specific task
zerg retry TASK-001

# Retry all failed tasks
zerg retry --all-failed

# Reset and assign to worker 2
zerg retry TASK-001 --reset --worker 2
```

---

#### `zerg merge`

Trigger merge gate execution. Merges worker branches after quality gates pass.

**Usage:**
```bash
zerg merge [OPTIONS]
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--feature`, `-f` | auto-detect | Feature to merge |
| `--level`, `-l` | current | Level to merge |
| `--target`, `-t` | `main` | Target branch |
| `--skip-gates` | `false` | Skip quality gates |
| `--dry-run` | `false` | Show merge plan only |

**Examples:**
```bash
# Merge current level
zerg merge

# Merge specific level
zerg merge --level 2

# Merge to develop branch, skip gates
zerg merge --target develop --skip-gates

# Preview merge plan
zerg merge --dry-run
```

---

#### `zerg cleanup`

Remove ZERG artifacts. Cleans worktrees, branches, containers, and logs.

**Usage:**
```bash
zerg cleanup [OPTIONS]
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--feature`, `-f` | - | Feature to clean |
| `--all` | `false` | Clean all features |
| `--keep-logs` | `false` | Preserve log files |
| `--keep-branches` | `false` | Preserve git branches |
| `--dry-run` | `false` | Show cleanup plan only |

**Examples:**
```bash
# Clean specific feature
zerg cleanup --feature user-auth

# Clean all features
zerg cleanup --all

# Preview cleanup, keep logs
zerg cleanup --all --keep-logs --dry-run
```

---

### Quality Commands

Commands for testing, building, and analyzing code.

---

#### `zerg test`

Execute tests with coverage analysis. Auto-detects framework (pytest, jest, cargo, go, mocha, vitest).

**Usage:**
```bash
zerg test [OPTIONS]
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--generate`, `-g` | `false` | Generate test stubs |
| `--coverage`, `-c` | `false` | Report coverage |
| `--watch`, `-w` | `false` | Watch mode |
| `--parallel`, `-p` | - | Number of parallel workers |
| `--framework`, `-f` | auto-detect | Framework: `pytest`, `jest`, `cargo`, `go`, `mocha`, `vitest` |
| `--path` | `.` | Path to test files |
| `--dry-run` | `false` | Show what would be run |
| `--json` | `false` | Output as JSON |

**Examples:**
```bash
# Run tests
zerg test

# Run with coverage
zerg test --coverage

# Watch mode with parallel workers
zerg test --watch --parallel 8

# Generate test stubs
zerg test --generate

# Preview test command
zerg test --dry-run
```

---

#### `zerg build`

Build orchestration with error recovery. Auto-detects build system (npm, cargo, make, gradle, go, python).

**Usage:**
```bash
zerg build [OPTIONS]
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--target`, `-t` | `all` | Build target |
| `--mode`, `-m` | `dev` | Build mode: `dev`, `staging`, `prod` |
| `--clean` | `false` | Clean build artifacts first |
| `--watch`, `-w` | `false` | Watch mode for continuous builds |
| `--retry`, `-r` | `3` | Number of retries on failure |
| `--dry-run` | `false` | Show what would be built |
| `--json` | `false` | Output as JSON |

**Examples:**
```bash
# Development build
zerg build

# Production build
zerg build --mode prod

# Clean build with watch
zerg build --clean --watch

# Preview build command
zerg build --dry-run
```

---

#### `zerg analyze`

Static analysis, complexity metrics, and quality assessment.

**Usage:**
```bash
zerg analyze [PATH] [OPTIONS]
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--check`, `-c` | `all` | Check type: `lint`, `complexity`, `coverage`, `security`, `all` |
| `--format`, `-f` | `text` | Output format: `text`, `json`, `sarif` |
| `--threshold`, `-t` | - | Thresholds (e.g., `complexity=10`) |
| `--files`, `-p` | - | Path to files (deprecated, use PATH) |

**Examples:**
```bash
# Run all checks
zerg analyze

# Lint check only
zerg analyze . --check lint

# JSON output for CI
zerg analyze --check all --format json

# Custom complexity threshold
zerg analyze --check complexity --threshold complexity=15
```

---

#### `zerg review`

Two-stage code review workflow.

**Usage:**
```bash
zerg review [OPTIONS]
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--mode`, `-m` | `full` | Review mode: `prepare`, `self`, `receive`, `full` |
| `--files`, `-f` | - | Specific files to review |
| `--output`, `-o` | - | Output file for review results |
| `--json` | `false` | Output as JSON |

**Modes:**
- `prepare`: Generate change summary and review checklist
- `self`: Self-review checklist and automated analysis
- `receive`: Process code quality review
- `full`: Complete two-stage review (spec + quality)

**Examples:**
```bash
# Full review
zerg review

# Generate review checklist
zerg review --mode prepare

# Self-review before PR
zerg review --mode self

# Save review to file
zerg review --output review.md
```

---

#### `zerg troubleshoot`

Systematic debugging with root cause analysis.

**Usage:**
```bash
zerg troubleshoot [OPTIONS]
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--error`, `-e` | - | Error message to analyze |
| `--stacktrace`, `-s` | - | Path to stack trace file |
| `--verbose`, `-v` | `false` | Verbose output |
| `--output`, `-o` | - | Output file for diagnostic report |
| `--json` | `false` | Output as JSON |

**Examples:**
```bash
# Analyze error message
zerg troubleshoot --error "ValueError: invalid literal"

# Analyze stack trace file
zerg troubleshoot --stacktrace trace.txt

# Verbose analysis
zerg troubleshoot --error "Error" --verbose

# JSON output
zerg troubleshoot --error "ImportError" --json
```

---

#### `zerg refactor`

Automated code improvement and cleanup.

**Usage:**
```bash
zerg refactor [PATH] [OPTIONS]
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--transforms`, `-t` | `dead-code,simplify` | Transforms: `dead-code`, `simplify`, `types`, `patterns`, `naming` |
| `--dry-run` | `false` | Show suggestions without applying |
| `--interactive`, `-i` | `false` | Interactive mode |
| `--files`, `-f` | - | Path to files (deprecated, use PATH) |
| `--json` | `false` | Output as JSON |

**Examples:**
```bash
# Apply default transforms
zerg refactor

# Preview dead-code and simplify changes
zerg refactor --transforms dead-code,simplify --dry-run

# Interactive mode
zerg refactor --interactive

# Type and naming improvements
zerg refactor --transforms types,naming
```

---

### Infrastructure Commands

Commands for git operations and security integration.

---

#### `zerg git`

Git operations with intelligent commits and workflow management.

**Usage:**
```bash
zerg git [OPTIONS]
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--action`, `-a` | `commit` | Action: `commit`, `branch`, `merge`, `sync`, `history`, `finish` |
| `--push`, `-p` | `false` | Push after commit |
| `--base`, `-b` | `main` | Base branch for operations |
| `--name`, `-n` | - | Branch name (for branch action) |
| `--branch` | - | Branch to merge (for merge action) |
| `--strategy` | `squash` | Merge strategy: `merge`, `squash`, `rebase` |
| `--since` | - | Starting point for history |

**Actions:**
- `commit`: Stage and commit with auto-generated message
- `branch`: Create or list branches
- `merge`: Merge branches with strategy
- `sync`: Sync with remote and base
- `history`: Show commit history
- `finish`: Interactive finish workflow

**Examples:**
```bash
# Commit and push
zerg git --action commit --push

# Create feature branch
zerg git --action branch --name feature/auth

# Finish feature branch
zerg git --action finish --base main
```

---

#### `zerg security-rules`

Manage secure coding rules from TikiTribe/claude-secure-coding-rules.

**Subcommands:**

```bash
# Detect project stack
zerg security-rules detect [--path PATH] [--json-output]

# List applicable rules
zerg security-rules list [--path PATH]

# Fetch rules
zerg security-rules fetch [--path PATH] [--output DIR] [--no-cache]

# Full integration
zerg security-rules integrate [--path PATH] [--output DIR] [--no-update-claude-md]
```

**Examples:**
```bash
# Detect and show project stack
zerg security-rules detect

# Fetch and integrate rules
zerg security-rules integrate

# Fetch without updating CLAUDE.md
zerg security-rules fetch --output .claude/security-rules/
```

---

## Configuration

Edit `.zerg/config.yaml`:

```yaml
version: "1.0"
project_type: python

workers:
  default_count: 5
  max_count: 10
  context_threshold: 0.7
  timeout_seconds: 3600

security:
  network_isolation: true
  filesystem_sandbox: true
  secrets_scanning: true

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

mcp_servers:
  - name: filesystem
    command: npx
    args: ["-y", "@anthropic/mcp-filesystem"]
```

### Scaling Guidelines

| Workers | Use Case |
|---------|----------|
| 1-2 | Small features, learning the system |
| 3-5 | Medium features, balanced throughput |
| 6-10 | Large features, maximum parallelism |

---

## How It Works

### Phase 1: Init
Analyzes your codebase. Detects languages, frameworks, databases. Generates devcontainer configuration.

### Phase 2: Plan
Captures requirements in `requirements.md`. Problem statement, user stories, acceptance criteria, scope boundaries. You approve before proceeding.

### Phase 3: Design
Generates architecture in `design.md`. Breaks implementation into a task graph with:
- Dependency levels (foundation -> core -> integration -> testing)
- Exclusive file ownership (no conflicts)
- Automated verification commands

### Phase 4: Rush
Creates git worktrees for each worker. Spawns N containers. Each worker:
- Picks tasks at current level
- Implements and verifies
- Commits to its branch
- Waits for level merge
- Continues to next level

### Phase 5: Orchestration
The orchestrator manages:
- Worker health monitoring
- Level synchronization
- Branch merging with quality gates
- Conflict resolution

---

## Troubleshooting

### Workers not starting
- Check Docker is running: `docker info`
- Verify `ANTHROPIC_API_KEY` is set
- Check port availability in 49152-65535 range

### Tasks failing verification
- Review the verification command in task-graph.json
- Check worker logs: `zerg logs --follow`
- Use troubleshoot: `zerg troubleshoot --error "..."`

### Merge conflicts
- Should not happen with exclusive file ownership
- If they do, check task-graph.json for file overlap
- Use `zerg retry --reset` on affected tasks

### Need to restart?
ZERG is crash-safe. Run `zerg rush --resume` to continue.

---

## Directory Structure

```
.zerg/
  config.yaml           # ZERG configuration
  state/                # Execution state
  logs/                 # Worker logs
  worktrees/            # Git worktrees

.devcontainer/
  devcontainer.json     # Container definition

.gsd/
  specs/{feature}/
    requirements.md     # What to build
    design.md           # How to build it
    task-graph.json     # Atomic work units
```

---

## Tutorial

For a step-by-step walkthrough, see [Tutorial: Building a Minerals Store](docs/tutorial-minerals-store.md).

---

## License

MIT
