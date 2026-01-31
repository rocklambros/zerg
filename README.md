# ZERG

<p align="center">
  <img src="logo/zerg_logo.png" alt="ZERG Logo" width="300">
</p>

**Zero-Effort Rapid Growth** — Parallel Claude Code execution system. Overwhelm features with coordinated zergling swarms.

ZERG coordinates multiple Claude Code instances to build software features in parallel. You describe what to build, ZERG breaks the work into atomic tasks with exclusive file ownership, then launches a swarm of zerglings to execute them simultaneously across dependency levels.

---

## Table of Contents

- **Getting Started**
  - [Installation](#installation)
  - [Quick Start](#quick-start)
  - [How It Works](#how-it-works)
- **Detailed Documentation**
  - [Command Reference](docs/commands.md) — All 20 commands with every flag and option
  - [Configuration Guide](docs/configuration.md) — Config files, tuning, environment variables
  - [Architecture](ARCHITECTURE.md) — System design, module reference, execution model
  - [Tutorial: Minerals Store](docs/tutorial-minerals-store.md) — Build a Starcraft 2 themed store from scratch
  - [Plugin System](docs/plugins.md) — Extend ZERG with custom gates, hooks, and launchers

---

## Installation

### Prerequisites

- Python 3.12+
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) installed
- Git
- Docker (optional, for container mode)

### Install ZERG

```bash
# Clone the repository
git clone https://github.com/zerg-dev/zerg.git
cd zerg

# Install in development mode
pip install -e ".[dev]"

# Verify installation
zerg --help
```

### Install Slash Commands

ZERG ships with 20 slash commands for Claude Code. Install them into your project:

```bash
# Install commands into .claude/commands/
zerg install

# Uninstall
zerg uninstall
```

Once installed, use `/zerg:*` commands inside any Claude Code session. Every command also has a `/z:` shortcut (e.g., `/z:plan`, `/z:rush`, `/z:status`).

---

## Quick Start

These are Claude Code slash commands. Use them inside a Claude Code session:

```
/zerg:init                         # Set up project infrastructure
/zerg:plan user-auth               # Plan a feature — capture requirements
/zerg:design                       # Design architecture and task graph
/zerg:rush --workers=5             # Launch the swarm
/zerg:status                       # Monitor progress
/zerg:logs --aggregate             # View logs across all workers
```

### Minimal Example

```bash
# 1. Initialize ZERG in your project
cd my-project
zerg init

# 2. Plan a feature (interactive requirements gathering)
#    Inside Claude Code:
/zerg:plan user-authentication

# 3. Review and approve requirements, then design:
/zerg:design

# 4. Review and approve architecture, then launch:
/zerg:rush --workers=5

# 5. Monitor progress:
/zerg:status
```

---

## How It Works

ZERG follows a four-phase workflow:

### 1. Plan (`/zerg:plan`)

You describe what to build. ZERG captures comprehensive requirements through interactive questioning (with an optional Socratic discovery mode). The output is a structured `requirements.md` spec file.

### 2. Design (`/zerg:design`)

ZERG reads the approved requirements and the existing codebase, then generates:

- **`design.md`** — Technical architecture document with component analysis, data flow, interface design, and key decisions
- **`task-graph.json`** — Atomic work units organized by dependency level, each with exclusive file ownership and a verification command

### 3. Rush (`/zerg:rush`)

The orchestrator launches parallel zerglings (Claude Code instances) to execute the task graph:

- **Level execution**: All zerglings complete Level 1 before any start Level 2
- **Exclusive file ownership**: Each task owns specific files — no merge conflicts possible
- **Quality gates**: After each level, branches are merged and gates run (lint, typecheck, test)
- **Crash recovery**: Zerglings are stateless — they read specs, not conversation history. Any zergling can resume any task.

### 4. Merge & Quality (`/zerg:merge`)

After each level completes, the orchestrator:
1. Merges all zergling branches into staging
2. Runs quality gates (configurable in `.zerg/config.yaml`)
3. Rebases zergling branches onto the merged result
4. Signals zerglings to proceed to the next level

### Key Concepts

| Concept | Description |
|---------|-------------|
| **Spec as Memory** | Zerglings read spec files, not conversation history. Stateless and restartable. |
| **Exclusive File Ownership** | Each task declares which files it creates or modifies. No overlap within a level. |
| **Levels** | Tasks grouped by dependencies. Level N must complete before Level N+1 begins. |
| **Verification Commands** | Every task has an automated verification command. Pass or fail, no subjectivity. |
| **Git Worktrees** | Each zergling operates in its own worktree with its own branch. |
| **Context Management** | At 70% context usage, zerglings checkpoint and exit for a fresh restart. |

### Execution Modes

ZERG supports three execution modes for zerglings:

| Mode | Description | When to Use |
|------|-------------|-------------|
| `subprocess` | Local Python subprocesses | Development, testing, no Docker needed |
| `container` | Isolated Docker containers | Production, full isolation, requires Docker |
| `task` | Claude Code Task sub-agents | Running from slash commands inside Claude Code |

Auto-detection: If `--mode` is not set, ZERG picks the best option based on your environment.

---

## Command Overview

ZERG provides 20 slash commands organized into four categories. See the [Command Reference](docs/commands.md) for complete documentation.

### Core Workflow

| Command | Purpose |
|---------|---------|
| `/zerg:init` | Initialize ZERG for a project (Inception or Discovery mode) |
| `/zerg:plan <feature>` | Capture requirements for a feature |
| `/zerg:design` | Generate architecture and task graph |
| `/zerg:rush` | Launch parallel zerglings to execute tasks |

### Monitoring & Control

| Command | Purpose |
|---------|---------|
| `/zerg:status` | Real-time execution progress dashboard |
| `/zerg:logs` | Stream, filter, and aggregate worker logs |
| `/zerg:stop` | Stop workers gracefully or forcefully |
| `/zerg:retry` | Retry failed or blocked tasks |
| `/zerg:merge` | Manually trigger level merge operations |
| `/zerg:cleanup` | Remove ZERG artifacts and free resources |

### Quality & Analysis

| Command | Purpose |
|---------|---------|
| `/zerg:build` | Build orchestration with error recovery |
| `/zerg:test` | Execute tests with coverage and generation |
| `/zerg:analyze` | Static analysis, complexity metrics, quality assessment |
| `/zerg:review` | Two-stage code review (spec compliance + quality) |
| `/zerg:security` | Vulnerability scanning and secure coding rules |
| `/zerg:refactor` | Automated code improvement and cleanup |

### Utilities

| Command | Purpose |
|---------|---------|
| `/zerg:git` | Intelligent commits, branch management, finish workflow |
| `/zerg:debug` | Deep diagnostic investigation with Bayesian hypothesis testing |
| `/zerg:worker` | Internal: zergling execution protocol |
| `/zerg:plugins` | Plugin system management |

---

## Configuration

ZERG is configured via `.zerg/config.yaml`. See the [Configuration Guide](docs/configuration.md) for the complete reference.

```yaml
version: "1.0"
project_type: python

workers:
  default_count: 5
  max_count: 10
  context_threshold: 0.7
  timeout_seconds: 3600

quality_gates:
  lint:
    command: "ruff check ."
    required: true
  test:
    command: "pytest"
    required: true

plugins:
  enabled: true
  hooks:
    - event: level_complete
      command: echo "Level {level} done"
      timeout: 60
```

---

## Project Structure

After initialization, ZERG creates the following directories:

```
project/
├── .zerg/                    # ZERG runtime
│   ├── config.yaml           # Configuration
│   ├── hooks/pre-commit      # Security & quality pre-commit hook
│   ├── state/{feature}.json  # Runtime state per feature
│   └── logs/                 # Structured JSONL logs
│       ├── workers/          # Per-worker log files
│       └── tasks/            # Per-task artifact directories
│
├── .gsd/                     # Spec-driven development files
│   ├── PROJECT.md            # Project overview
│   ├── INFRASTRUCTURE.md     # Infrastructure requirements
│   └── specs/{feature}/      # Per-feature specs
│       ├── requirements.md   # Requirements document
│       ├── design.md         # Technical architecture
│       └── task-graph.json   # Task definitions
│
├── .devcontainer/            # Container execution support
│   ├── devcontainer.json
│   └── Dockerfile
│
└── .claude/commands/         # Installed slash commands
    └── zerg:*.md
```

---

## Troubleshooting

### Zerglings Not Starting

1. Check Docker is running: `docker info`
2. Verify `ANTHROPIC_API_KEY` is set
3. Check port availability (ZERG uses ports 49152+)
4. Check disk space: `df -h .`
5. Run `/zerg:debug --env` for full environment diagnostics

### Tasks Failing Verification

1. Check the verification command: `jq '.tasks[] | select(.id=="TASK-ID") | .verification' .gsd/specs/FEATURE/task-graph.json`
2. Run the verification command manually
3. View task artifacts: `/zerg:logs --artifacts TASK-ID`
4. Use `/zerg:debug --error "error message"` for deep analysis

### Need to Restart

ZERG is crash-safe. Run `/zerg:rush --resume` to continue from where you left off. State is preserved in `.zerg/state/` and the Claude Code Task system.

### Common Issues

| Problem | Solution |
|---------|----------|
| "No active feature" | Run `/zerg:plan <feature>` first |
| "Task graph not found" | Run `/zerg:design` first |
| Merge conflicts | Check file ownership in task-graph.json |
| Worker crashed | Orchestrator auto-restarts; check `/zerg:logs` |
| All workers blocked | Run `/zerg:debug` to diagnose, `/zerg:retry --all` to retry |

---

## License

MIT

---

## Documentation

| Document | Description |
|----------|-------------|
| [Command Reference](docs/commands.md) | Complete documentation for all 20 commands |
| [Configuration Guide](docs/configuration.md) | Config files, tuning, environment variables, plugins |
| [Architecture](ARCHITECTURE.md) | System design, module reference, execution model |
| [Tutorial](docs/tutorial-minerals-store.md) | Build a Starcraft 2 themed ecommerce store |
| [Plugin System](docs/plugins.md) | Extend ZERG with custom gates, hooks, and launchers |
