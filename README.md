# ZERG

<p align="center">
  <img src="logo/zerg_logo.png" alt="ZERG Logo" width="450">
</p>

**Zero-Effort Rapid Growth** — Parallel Claude Code execution system. Overwhelm features with coordinated zergling swarms.

ZERG coordinates multiple Claude Code instances to build software features in parallel. You describe what to build, ZERG breaks the work into atomic tasks with exclusive file ownership, then launches a swarm of zerglings to execute them simultaneously across dependency levels.

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

## Table of Contents

- **Getting Started**
  - [Installation](#installation)
  - [Quick Start](#quick-start)
  - [How It Works](#how-it-works)
- **Key Features**
  - [Worker Intelligence](#worker-intelligence)
  - [Cross-Cutting Capabilities](#cross-cutting-capabilities)
  - [Context Engineering](#context-engineering)
  - [Security Rules](#security-rules)
  - [Dev Containers](#dev-containers)
  - [Plugin System](#plugin-system)
  - [Diagnostics Engine](#diagnostics-engine)
  - [Resilience](#resilience)
- **Detailed Documentation**
  - [Command Reference](docs/commands.md) — All 26 commands with every flag and option
  - [Configuration Guide](docs/configuration.md) — Config files, tuning, environment variables
  - [Architecture](ARCHITECTURE.md) — System design, module reference, execution model
  - [Tutorial: Minerals Store](docs/tutorial-minerals-store.md) — Build a Starcraft 2 themed store from scratch
  - [Plugin System](docs/plugins.md) — Extend ZERG with custom gates, hooks, and launchers
  - [Context Engineering](docs/context-engineering.md) — How ZERG minimizes worker token usage

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
git clone https://github.com/rocklambros/zerg.git
cd zerg

# Install in development mode
pip install -e ".[dev]"

# Install pre-commit hooks (required for contributors)
pre-commit install

# Verify installation
zerg --help
```

### Install Slash Commands

ZERG ships with 26 slash commands for Claude Code. Install them into your project:

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
/zerg:brainstorm                   # Feature discovery (add --socratic for enhanced questioning)
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

# 5. Monitor progress (in a separate terminal):
zerg status --dashboard
```

### What Happens When You Run `zerg init`

This is where ZERG earns the "Zero-Effort" in its name. A single command:

1. **Detects your tech stack** — languages, frameworks, databases, infrastructure
2. **Fetches security rules** — OWASP Top 10 2025, plus language-specific rules for every detected language (Python, JavaScript, Go, Rust, etc.)
3. **Generates dev containers** — Dockerfile, devcontainer.json, MCP server configs, post-create scripts
4. **Creates project config** — `.zerg/config.yaml` with quality gates, worker settings, logging
5. **Installs pre-commit hooks** — secret detection, shell injection prevention, lint checks
6. **Sets up spec directories** — `.gsd/` structure for requirements, designs, and task graphs

No manual CLAUDE.md editing. No copy-pasting security rules. No Dockerfile authoring. One command.

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

## Worker Intelligence

ZERG workers include three health and monitoring subsystems that enable self-healing, structured progress tracking, and intelligent failure handling.

### Heartbeat Health Monitoring

Workers write a heartbeat file every 15 seconds with their current task, step, and progress percentage. The orchestrator continuously monitors heartbeats and detects stalled workers (no heartbeat for 120s by default). Stalled workers are auto-restarted — first stall resumes the same task, second stall reassigns to a fresh worker.

```yaml
heartbeat:
  interval_seconds: 15
  stall_timeout_seconds: 120
  max_restarts: 2
```

### Three-Tier Verification with Escalation

Instead of a single pass/fail verification, workers execute three tiers:

| Tier | Name | Blocking | Purpose |
|------|------|----------|---------|
| 1 | Syntax | Yes | Lint, type check, compilation errors |
| 2 | Correctness | Yes | Task verification command + integration tests |
| 3 | Quality | No | Code quality, style, best practices |

When a failure is ambiguous (unclear spec, missing dependency, unclear verification criteria), workers **escalate** to the orchestrator instead of retrying blindly. The orchestrator alerts the terminal with escalation details so users can intervene.

### Repository Symbol Map

At rush start, ZERG builds a symbol graph of the codebase using Python AST for `.py` files and regex extraction for `.js`/`.ts` files. Per-task context includes relevant symbols (functions, classes, imports) from the repo map, giving workers awareness of nearby code without reading full source files. Zero external dependencies — no tree-sitter required.

### Structured Progress Reporting

Each worker writes structured progress to `.zerg/state/progress-{id}.json` with tasks completed/total, current step, and per-tier verification results. `/zerg:status` aggregates this into a Worker Intelligence panel showing heartbeat status, escalations, and per-worker progress bars.

### Token Usage Metrics

ZERG tracks token consumption per worker and per task. By default, counts use a heuristic estimator (zero dependencies). Install `zerg[metrics]` for exact counting via the Anthropic SDK. `/zerg:status` displays a TOKEN USAGE section with per-worker totals and context engineering savings.

### Incremental Repo Map Indexing

The repository symbol map uses MD5-based staleness detection to re-parse only files that changed since the last index. `/zerg:status` shows a REPOSITORY MAP section with indexed file counts and stale entry tracking.

---

## Cross-Cutting Capabilities

ZERG includes 8 cross-cutting capabilities that enhance worker intelligence, enforce quality, and optimize resource usage. These are controlled via CLI flags and `.zerg/config.yaml`.

### Analysis Depth Tiers

Control how deeply workers analyze tasks with mutually exclusive flags:

```bash
/zerg:rush --quick          # Surface-level, fast execution
/zerg:rush --think          # Structured multi-step analysis
/zerg:rush --think-hard     # Deep architectural analysis
/zerg:rush --ultrathink     # Maximum depth (enables all MCP servers)
```

### Token Efficiency Mode

Compact output is enabled by default. Disable it when you need full verbosity:

```bash
/zerg:rush --no-compact     # Disable compact output (full verbosity)
```

Three zones: GREEN (0-75%, full output), YELLOW (75-85%, reduced verbosity), RED (85%+, essential operations only). Auto-activates based on context usage.

### Behavioral Modes

Workers adapt their execution strategy based on task characteristics:

```bash
/zerg:rush --mode precision   # Careful, thorough (default)
/zerg:rush --mode speed       # Fast execution, minimal output
/zerg:rush --mode exploration # Creative, try alternatives
/zerg:rush --mode refactor    # Code improvement focus
/zerg:rush --mode debug       # Diagnostic investigation
```

Auto-detected from task keywords when `--mode` is not set.

### MCP Auto-Routing

Intelligent MCP server selection based on task type and file extensions:

```bash
/zerg:rush --mcp              # Enable auto-routing (default)
/zerg:rush --no-mcp           # Disable MCP servers
```

Routes tasks to the right servers: Sequential for analysis, Context7 for docs, Playwright for testing, etc. Cost-aware optimization limits to 3 servers per task.

### Additional Capabilities

| Capability | Config Section | Description |
|------------|---------------|-------------|
| Engineering Rules | `rules` | 25 YAML rules (safety, quality, efficiency) injected into worker context |
| Iterative Loops | `improvement_loops` | `--no-loop` to disable (on by default), `--iterations N` to set max cycles |
| Verification Gates | `verification` | Artifact storage, staleness detection, pipeline orchestration |
| TDD Enforcement | `tdd` | `--tdd` flag for red-green-refactor protocol with anti-pattern detection |

### Configuration

```yaml
# .zerg/config.yaml (new sections)
rules:
  enabled: true
  base_rules: true
  custom_rules: true

efficiency:
  auto_compact_threshold: 0.75
  symbol_system: true
  abbreviations: true

behavioral_modes:
  auto_detect: true
  default_mode: precision

mcp_routing:
  auto_detect: true
  cost_aware: true
  max_servers: 3

improvement_loops:
  max_iterations: 5
  plateau_threshold: 2
  rollback_on_regression: true

verification:
  require_before_completion: true
  staleness_threshold_seconds: 300
  store_artifacts: true

tdd:
  enabled: false
  enforce_red_green: true
```

---

## Context Engineering

ZERG includes a context engineering plugin that minimizes token usage across workers. Instead of loading entire spec files and all security rules into every worker, ZERG scopes context to each task.

### How It Works

**Command Splitting**: Large command files (>300 lines) are split into `.core.md` (~30%, essential instructions) and `.details.md` (~70%, reference material). Workers load the core by default and pull in details only when needed. 9 commands are split this way, saving thousands of tokens per worker.

**Security Rule Filtering**: Instead of loading every security rule into every worker, ZERG filters by file extension. A worker editing `.py` files gets Python security rules. A worker editing `.js` files gets JavaScript rules. A worker editing `Dockerfile` gets Docker rules. No wasted tokens on irrelevant rules.

**Task-Scoped Context**: Each task in the task graph gets a `context` field with:
- Spec excerpts relevant to the task's description and owned files
- Dependency context from upstream tasks
- Filtered security rules matching the task's file types

Workers load their task context instead of the full spec, saving ~2,000-5,000 tokens per task.

### Configuration

```yaml
# .zerg/config.yaml
plugins:
  context_engineering:
    enabled: true
    command_splitting: true
    security_rule_filtering: true
    task_context_budget_tokens: 4000
    fallback_to_full: true
```

### Monitoring

Use `/zerg:status` to view the CONTEXT BUDGET section showing:
- Split command count and token savings
- Per-task context population rate
- Security rule filtering stats

For full details, see [Context Engineering](docs/context-engineering.md).

---

## Security Rules

ZERG automatically integrates stack-specific secure coding rules from [TikiTribe/claude-secure-coding-rules](https://github.com/TikiTribe/claude-secure-coding-rules).

### What Gets Installed

When you run `zerg init`, ZERG:

1. **Detects your stack** — scans for `pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`, `Dockerfile`, etc.
2. **Fetches matching rules** — downloads OWASP Top 10 2025 core rules plus language/infrastructure-specific rules
3. **Installs to `.claude/rules/security/`** — Claude Code auto-loads everything under `.claude/rules/`
4. **Adds summary to CLAUDE.md** — informational reference showing which rules are active

### Coverage

| Category | What's Covered |
|----------|----------------|
| **OWASP Top 10 2025** | Broken Access Control, Security Misconfiguration, Supply Chain, Crypto Failures, Injection, Insecure Design, Auth Failures, Integrity Failures, Logging Failures, Error Handling |
| **Python** | Deserialization, subprocess safety, path traversal, secure randomness, password hashing, parameterized queries, URL validation, cookies, error handling |
| **JavaScript** | Prototype pollution, DOM sanitization, URL validation, command injection, path traversal, dependency management, crypto, CORS, security headers |
| **Docker** | Minimal base images, non-root users, multi-stage builds, no secrets in layers, vulnerability scanning, content trust, read-only filesystems, capability dropping, resource limits |

### CLI Management

```bash
zerg security-rules detect       # Show detected stack
zerg security-rules list         # Show rules for your stack
zerg security-rules fetch        # Download rules
zerg security-rules integrate    # Full integration with CLAUDE.md
```

---

## Dev Containers

ZERG generates complete dev container configurations so workers can run in isolated Docker environments.

### What Gets Generated

```
.devcontainer/
├── devcontainer.json       # Container config with mounts, env vars, extensions
├── Dockerfile              # Multi-stage image with detected languages
├── post-create.sh          # Dependency installation, tool setup
├── post-start.sh           # Runtime configuration
└── mcp-servers/            # MCP server configs for workers
    └── config.json
```

### Authentication

Container workers authenticate via two methods:

| Method | How | Best For |
|--------|-----|----------|
| **OAuth** | Mount `~/.claude` into container | Claude Pro/Team accounts |
| **API Key** | Pass `ANTHROPIC_API_KEY` env var | API key authentication |

### Usage

```bash
# Initialize with container support
zerg init --with-containers

# Build the devcontainer image
devcontainer build --workspace-folder .

# Launch workers in containers
/zerg:rush --mode container --workers=5
```

---

## Plugin System

Extend ZERG with three types of plugins:

| Type | Purpose | Example |
|------|---------|---------|
| **Quality Gate** | Custom validation after merges | SonarQube scans, security gates |
| **Lifecycle Hook** | React to events (non-blocking) | Slack notifications, metrics collection |
| **Launcher** | Custom worker execution environments | Kubernetes pods, SSH clusters, cloud VMs |

### Quick Example (YAML)

```yaml
# .zerg/config.yaml
plugins:
  hooks:
    - event: level_complete
      command: ./scripts/notify-slack.sh "Level {level} done"
      timeout: 60
  quality_gates:
    - name: security-scan
      command: bandit -r src/ --severity medium
      required: false
```

### Quick Example (Python)

```python
from zerg.plugins import QualityGatePlugin, GateContext
from zerg.types import GateRunResult
from zerg.constants import GateResult

class SonarQubeGate(QualityGatePlugin):
    @property
    def name(self) -> str:
        return "sonarqube"

    def run(self, ctx: GateContext) -> GateRunResult:
        # Your custom validation logic
        return GateRunResult(
            gate_name=self.name,
            result=GateResult.PASS,
            command="sonar-scanner",
            exit_code=0,
            stdout="Quality gate passed",
        )
```

Plugins are auto-discovered via Python entry points. See [Plugin System](docs/plugins.md) for the full reference.

---

## Diagnostics Engine

When things go wrong, `/zerg:debug` provides deep investigation capabilities:

- **Multi-language error parsing** — Python, JavaScript/TypeScript, Go, Rust, Java, C++
- **Bayesian hypothesis testing** — 30+ known failure patterns with calibrated probabilities
- **Cross-worker log correlation** — temporal clustering, Jaccard similarity scoring
- **Code-aware recovery plans** — import chain analysis, git blame context, fix templates with risk ratings (`[SAFE]`, `[MODERATE]`, `[DESTRUCTIVE]`)
- **Design escalation detection** — recognizes when failures indicate architectural problems and recommends `/zerg:design`

```bash
# Auto-detect and diagnose
/zerg:debug

# Specific error investigation
/zerg:debug --error "ModuleNotFoundError: No module named 'requests'"

# Full system diagnostics
/zerg:debug --deep --env

# Generate and execute recovery plan
/zerg:debug --fix
```

---

## Resilience

ZERG includes automatic failure recovery for container mode execution. When workers crash, tasks stall, or spawns fail, ZERG recovers without manual intervention.

### Spawn Retry with Backoff

Worker spawning retries automatically on transient failures:

- Retries up to 3 attempts (configurable)
- Exponential backoff: 2s → 4s → 8s (capped at 30s)
- Logs each retry with timestamp and reason
- Fails gracefully with actionable error after exhausting retries

### Task Timeout Watchdog

Tasks stuck in `in_progress` are auto-failed and retried:

- Default timeout: 10 minutes (600 seconds)
- Timeout triggers task failure with reason "timeout"
- Task immediately requeued for reassignment
- Prevents single stuck task from blocking level progression

### Worker Crash Recovery

When a worker crashes mid-task:

1. Task marked `failed` with reason "worker_crash"
2. Retry count NOT incremented (crash ≠ task bug)
3. Task reassigned to healthy worker within one heartbeat interval
4. If no healthy workers available, task queued for when workers recover

### Auto-Respawn

Failed workers are automatically replaced:

- Orchestrator maintains target worker count from `--workers` flag
- Replacement spawns use the same retry logic as initial spawns
- Respawn capped at 5 attempts per worker to prevent infinite loops

### State Reconciliation

Periodic checks prevent state drift:

- **Light check (every 60s)**: Compares task states, logs divergence
- **Thorough check (on level transitions)**: Full reconciliation before advancing
- Auto-fixes:
  - Tasks `in_progress` with dead workers → mark failed, requeue
  - Level marked "done" with incomplete tasks → recalculate status
  - Task with `level=None` → parse from ID pattern `*-L{level}-*`

### Structured Logging

All resilience events written to `.zerg/monitor.log`:

```
2026-02-03T05:41:55.123Z [W0] [INFO] Worker 0 claimed task A-L1-002
2026-02-03T05:42:30.789Z [W0] [ERROR] Claude Code failed: exit code 1
2026-02-03T05:42:31.001Z [ORCH] [INFO] Task A-L1-002 reassigned to W1
```

Events logged: worker lifecycle (spawn/ready/exit/crash/respawn), task lifecycle (claim/start/complete/fail/timeout/reassign), heartbeat (stale detection), state reconciliation (divergence/fixes).

### Configuration

```yaml
# .zerg/config.yaml
resilience:
  enabled: true                    # Master toggle (default: true)

workers:
  # Spawn retry
  spawn_retry_attempts: 3
  spawn_backoff_strategy: exponential  # exponential|linear|fixed
  spawn_backoff_base_seconds: 2
  spawn_backoff_max_seconds: 30

  # Task timeout
  task_stale_timeout_seconds: 600  # 10 minutes

  # Heartbeat
  heartbeat_interval_seconds: 30
  heartbeat_stale_threshold: 120   # 2 minutes

  # Worker management
  auto_respawn: true
  max_respawn_attempts: 5
```

### Troubleshooting Resilience Issues

| Problem | Diagnosis | Solution |
|---------|-----------|----------|
| Workers failing to spawn | Check Docker daemon, image availability | `docker info`, rebuild image |
| Tasks stuck in progress | Check heartbeat files, worker health | `/zerg:status`, inspect `.zerg/state/heartbeat-*.json` |
| Level not advancing | State reconciliation may have found issues | Check `.zerg/monitor.log` for reconciliation events |
| High respawn count | Systemic issue causing repeated crashes | Check worker logs, verify task verification commands |

---

## Command Overview

ZERG provides 26 slash commands organized into five categories. See the [Command Reference](docs/commands.md) for complete documentation.

### Core Workflow

| Command | Purpose |
|---------|---------|
| `/zerg:init` | Initialize ZERG for a project (Inception or Discovery mode) |
| `/zerg:brainstorm` | Feature discovery with interactive questioning (--socratic for enhanced Socratic methodology) |
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
| `/zerg:git` | Git operations: commits, PRs, releases, rescue, review, bisect, ship, cleanup, issue (14 actions) |
| `/zerg:debug` | Deep diagnostic investigation with Bayesian hypothesis testing |
| `/zerg:worker` | Internal: zergling execution protocol |
| `/zerg:plugins` | Plugin system management |

### Documentation & AI

| Command | Purpose |
|---------|---------|
| `/zerg:document` | Generate documentation for a specific component |
| `/zerg:index` | Generate a complete project documentation wiki |
| `/zerg:estimate` | Effort estimation with PERT intervals and cost projection |
| `/zerg:explain` | Educational code explanations with progressive depth |
| `/zerg:select-tool` | Intelligent tool routing for MCP servers and agents |

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
  context_engineering:
    enabled: true
    command_splitting: true
    security_rule_filtering: true
    task_context_budget_tokens: 4000
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
│   ├── Dockerfile
│   ├── post-create.sh
│   └── mcp-servers/
│
├── .claude/
│   ├── commands/             # Installed slash commands
│   │   └── zerg:*.md
│   └── rules/security/      # Auto-fetched security rules
│       ├── _core/owasp-2025.md
│       ├── languages/python/
│       ├── languages/javascript/
│       └── containers/docker/
│
└── CLAUDE.md                 # Updated with security rules summary
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

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, code style, PR process, and how to add new commands.

## Security

See [SECURITY.md](SECURITY.md) for vulnerability reporting and security architecture.

## License

MIT — see [LICENSE](LICENSE) for full text.

---

## Documentation

| Document | Description |
|----------|-------------|
| [Command Reference](docs/commands.md) | Complete documentation for all 26 commands |
| [Configuration Guide](docs/configuration.md) | Config files, tuning, environment variables, plugins |
| [Architecture](ARCHITECTURE.md) | System design, module reference, execution model |
| [Context Engineering](docs/context-engineering.md) | How ZERG minimizes worker token usage |
| [Tutorial](docs/tutorial-minerals-store.md) | Build a Starcraft 2 themed ecommerce store |
| [Plugin System](docs/plugins.md) | Extend ZERG with custom gates, hooks, and launchers |
| [Design Principles](docs/design-principles.md) | Context management and token minimization guidelines |
| [Contributing](CONTRIBUTING.md) | Development setup, code style, and PR process |
| [Security Policy](SECURITY.md) | Vulnerability reporting and security architecture |
