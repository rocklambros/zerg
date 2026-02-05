# ZERG Wiki

**Zero-Effort Rapid Growth** — A parallel Claude Code execution system that coordinates multiple Claude Code instances to build software features simultaneously. ZERG auto-detects your tech stack, fetches security rules, generates dev containers, breaks features into atomic tasks with exclusive file ownership, and launches a swarm of zerglings to execute them in parallel across dependency levels.

---

## Quick Start

```bash
# Install ZERG
git clone https://github.com/rocklambros/zerg.git && cd zerg
pip install -e ".[dev]"
zerg install  # Install slash commands

# Inside Claude Code session:
/zerg:init                    # Initialize project
/zerg:plan user-auth          # Plan a feature
/zerg:design                  # Generate architecture
/zerg:rush --workers=5        # Launch the swarm
/zerg:status                  # Monitor progress
```

---

## Installation

### Prerequisites

- Python 3.12+
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code)
- Git
- Docker (optional, for container mode)

### Steps

```bash
git clone https://github.com/rocklambros/zerg.git
cd zerg
pip install -e ".[dev]"
pre-commit install
zerg install
```

---

## Wiki Pages

| Page | Description |
|------|-------------|
| [Home](Home) | Project overview and quick start (this page) |
| [Command-Reference](Command-Reference) | All 26 commands with flags, examples, and usage |
| [Configuration](Configuration) | `.zerg/config.yaml`, environment variables, tuning |
| [Architecture](Architecture) | System design, module reference, execution model |
| [Tutorial](Tutorial) | Minerals-store walkthrough demonstrating all ZERG features |
| [Plugins](Plugins) | Quality gates, lifecycle hooks, custom launchers |
| [Security](Security) | Security rules integration, vulnerability reporting |
| [Context-Engineering](Context-Engineering) | Token optimization, command splitting, task context |
| [Troubleshooting](Troubleshooting) | Common issues, diagnostics, recovery procedures |
| [FAQ](FAQ) | Frequently asked questions |
| [Contributing](Contributing) | Development setup, code style, PR process |

---

## Core Workflow

1. **Plan** (`/zerg:plan`) — Capture requirements through interactive questioning
2. **Design** (`/zerg:design`) — Generate architecture and task graph with file ownership
3. **Rush** (`/zerg:rush`) — Launch parallel zerglings to execute tasks by level
4. **Merge** (`/zerg:merge`) — Quality gates and branch merging after each level

---

## Key Concepts

| Concept | Description |
|---------|-------------|
| **Spec as Memory** | Zerglings read spec files, not conversation history. Stateless and restartable. |
| **Exclusive File Ownership** | Each task owns specific files. No merge conflicts within a level. |
| **Levels** | Tasks grouped by dependencies. Level N completes before Level N+1 begins. |
| **Verification Commands** | Every task has an automated verification. Pass or fail, no subjectivity. |
| **Context Engineering** | Per-task context scoping minimizes token usage by 30-50%. |

---

## Command Categories

| Category | Commands |
|----------|----------|
| **Core Workflow** | `/zerg:init`, `/zerg:brainstorm`, `/zerg:plan`, `/zerg:design`, `/zerg:rush` |
| **Monitoring & Control** | `/zerg:status`, `/zerg:logs`, `/zerg:stop`, `/zerg:retry`, `/zerg:merge`, `/zerg:cleanup` |
| **Quality & Analysis** | `/zerg:build`, `/zerg:test`, `/zerg:analyze`, `/zerg:review`, `/zerg:security`, `/zerg:refactor` |
| **Utilities** | `/zerg:git`, `/zerg:debug`, `/zerg:worker`, `/zerg:plugins`, `/zerg:create-command` |
| **Documentation & AI** | `/zerg:document`, `/zerg:index`, `/zerg:estimate`, `/zerg:explain`, `/zerg:select-tool` |

See [Command-Reference](Command-Reference) for complete documentation.

---

## Resources

- [GitHub Repository](https://github.com/rocklambros/zerg)
- [README.md](https://github.com/rocklambros/zerg/blob/main/README.md) — Tutorial-focused getting started guide
- [ARCHITECTURE.md](https://github.com/rocklambros/zerg/blob/main/ARCHITECTURE.md) — System design details
- [Security Rules](https://github.com/TikiTribe/claude-secure-coding-rules) — Auto-fetched secure coding rules
