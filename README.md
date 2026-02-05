# ZERG

<p align="center">
  <img src="logo/zerg_logo.png" alt="ZERG Logo" width="450">
</p>

**Zero-Effort Rapid Growth** — A parallel Claude Code execution system that coordinates multiple Claude Code instances to build software features simultaneously. ZERG auto-detects your tech stack, fetches security rules, generates dev containers, breaks features into atomic tasks with exclusive file ownership, and launches a swarm of zerglings to execute them in parallel.

---

## Quick Start (5 minutes)

```bash
# Install ZERG
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

### Step 1: Clone and Install

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

This tutorial walks through building a "Minerals Store" — a Starcraft 2 themed ecommerce API — using all ZERG phases.

### Step 1: Initialize Project

Create a new directory and initialize ZERG:

```bash
mkdir minerals-store && cd minerals-store
```

Inside Claude Code:

```
/zerg:init
```

**What happens:**
- Detects your tech stack (or runs Inception wizard for empty projects)
- Creates `.zerg/config.yaml` with quality gates and worker settings
- Generates `.devcontainer/` for container mode execution
- Fetches security rules (OWASP Top 10, language-specific rules)
- Sets up `.gsd/` directory for specs and task graphs

### Step 2: Brainstorm (Optional)

If requirements are unclear, use brainstorming to discover what to build:

```
/zerg:brainstorm --socratic
```

**What happens:**
- Socratic discovery mode asks probing questions in three rounds
- Synthesizes answers into structured requirements insights
- Outputs to `.gsd/specs/brainstorm-session.md`

### Step 3: Plan Your Feature

Capture requirements through interactive questioning:

```
/zerg:plan minerals-store
```

**What happens:**
- Interactive prompts gather requirements (ideal solution, non-negotiables, non-goals)
- Generates `.gsd/specs/minerals-store/requirements.md`
- Status set to `DRAFT` — edit the file to change to `APPROVED` when ready

### Step 4: Design Architecture

Generate technical architecture and task graph:

```
/zerg:design
```

**What happens:**
- Reads approved requirements and analyzes codebase
- Generates `design.md` with components, data models, APIs
- Creates `task-graph.json` with atomic tasks, file ownership, verification commands

Each task declares exclusive ownership:
- `create`: Files this task creates
- `modify`: Files this task modifies (no overlap within a level)
- `read`: Read-only access

### Step 5: Launch the Swarm

Execute tasks in parallel:

```
/zerg:rush --workers=4
```

**What happens:**
- Creates git worktrees for each worker
- Workers claim tasks via Claude Code Task system
- Level 1 executes in parallel
- Quality gates run after each level
- Branches merge, workers proceed to next level

**Execution modes:**

| Mode | Flag | Use Case |
|------|------|----------|
| subprocess | `--mode subprocess` | Development, no Docker |
| container | `--mode container` | Production, full isolation |
| task | `--mode task` | Claude Code slash commands |

### Step 6: Monitor Progress

Track execution in real-time:

```
/zerg:status --watch
```

View worker logs:

```
/zerg:logs --follow              # Stream all workers
/zerg:logs --worker 2            # Specific worker
/zerg:logs --aggregate           # All workers sorted by time
```

### Step 7: Quality Checks

Review code against spec and quality standards:

```
/zerg:review --mode full
```

Run tests:

```
/zerg:test --coverage
```

Security scan:

```
/zerg:security --preset owasp
```

### Step 8: Ship It

After all levels complete:

```
/zerg:git --action ship
```

This merges your feature branch to main after final verification.

**Other git actions:**

| Action | Command |
|--------|---------|
| Commit | `/zerg:git commit` |
| Create PR | `/zerg:git --action pr` |
| Ship | `/zerg:git --action ship` |
| Full workflow | `/zerg:git --action finish` |

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
| `/zerg:document` | Generate component documentation |
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
