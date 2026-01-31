# ZERG Architecture

**Zero-Effort Rapid Growth** - Parallel Claude Code Execution System

ZERG is a distributed software development system that coordinates multiple Claude Code instances to build features in parallel. It combines spec-driven development (GSD methodology), level-based task execution, and git worktrees for isolated execution.

---

## Table of Contents

- [Core Principles](#core-principles)
- [System Layers](#system-layers)
- [Execution Flow](#execution-flow)
- [Module Reference](#module-reference)
- [Zergling Execution Model](#zergling-execution-model)
- [State Management](#state-management)
- [Claude Code Task Integration](#claude-code-task-integration)
- [Context Engineering](#context-engineering)
- [Quality Gates](#quality-gates)
- [Pre-commit Hooks](#pre-commit-hooks)
- [Security Model](#security-model)
- [Configuration](#configuration)

---

## Core Principles

### Spec as Memory

Zerglings do not share conversation context. They share:
- `requirements.md` — what to build
- `design.md` — how to build it
- `task-graph.json` — atomic work units

This makes zerglings **stateless**. Any zergling can pick up any task. Crash recovery is trivial.

### Exclusive File Ownership

Each task declares which files it creates or modifies. The design phase ensures no overlap within a level. This eliminates merge conflicts without runtime locking.

```json
{
  "id": "TASK-001",
  "files": {
    "create": ["src/models/user.py"],
    "modify": [],
    "read": ["src/config.py"]
  }
}
```

### Level-Based Execution

Tasks are organized into dependency levels:

| Level | Name | Description |
|-------|------|-------------|
| 1 | Foundation | Types, schemas, config |
| 2 | Core | Business logic, services |
| 3 | Integration | Wiring, endpoints |
| 4 | Testing | Unit and integration tests |
| 5 | Quality | Docs, cleanup |

All zerglings complete Level N before any proceed to N+1. The orchestrator merges all branches, runs quality gates, then signals zerglings to continue.

### Git Worktrees for Isolation

Each zergling operates in its own git worktree with its own branch:

```
.zerg-worktrees/{feature}/worker-0/  ->  branch: zerg/{feature}/worker-0
.zerg-worktrees/{feature}/worker-1/  ->  branch: zerg/{feature}/worker-1
```

Zerglings commit independently. No filesystem conflicts.

---

## System Layers

```
+---------------------------------------------------------------------+
|                     Layer 1: Planning                                |
|          requirements.md + INFRASTRUCTURE.md                        |
+---------------------------------------------------------------------+
                              |
                              v
+---------------------------------------------------------------------+
|                     Layer 2: Design                                  |
|              design.md + task-graph.json                             |
+---------------------------------------------------------------------+
                              |
                              v
+---------------------------------------------------------------------+
|                  Layer 3: Orchestration                              |
|   Zergling lifecycle - Level sync - Branch merging - Monitoring     |
+---------------------------------------------------------------------+
          |                   |                   |
          v                   v                   v
+-------------+     +-------------+     +-------------+
| Zergling 0  |     | Zergling 1  |     | Zergling N  |
|  (worktree) |     |  (worktree) |     |  (worktree) |
+-------------+     +-------------+     +-------------+
          |                   |                   |
          +-------------------+-------------------+
                              |
                              v
+---------------------------------------------------------------------+
|                  Layer 4: Quality Gates                              |
|           Lint - Type-check - Test - Merge to main                  |
+---------------------------------------------------------------------+
```

### Plugin System

ZERG's plugin architecture provides three extension points via abstract base classes:

```
PluginRegistry
+-- hooks: dict[str, list[Callable]]     # LifecycleHookPlugin callbacks
+-- gates: dict[str, QualityGatePlugin]  # Named quality gate plugins
+-- launchers: dict[str, LauncherPlugin] # Named launcher plugins

QualityGatePlugin (ABC)
+-- name: str
+-- run(ctx: GateContext) -> GateRunResult

LifecycleHookPlugin (ABC)
+-- name: str
+-- on_event(event: LifecycleEvent) -> None

LauncherPlugin (ABC)
+-- name: str
+-- create_launcher(config) -> WorkerLauncher
```

**PluginHookEvent** lifecycle (8 events): `TASK_STARTED`, `TASK_COMPLETED`, `LEVEL_COMPLETE`, `MERGE_COMPLETE`, `RUSH_FINISHED`, `QUALITY_GATE_RUN`, `WORKER_SPAWNED`, `WORKER_EXITED`

**Integration points**:
- `orchestrator.py` — emits lifecycle events, runs plugin gates after merge
- `worker_protocol.py` — emits `TASK_STARTED`/`TASK_COMPLETED` events
- `gates.py` — delegates to plugin gates registered in the registry
- `launcher.py` — resolves launcher plugins by name via `get_plugin_launcher()`

**Discovery**: Plugins are loaded via `importlib.metadata` entry points (group: `zerg.plugins`) or YAML-configured shell command hooks in `.zerg/config.yaml`.

Configuration models: `PluginsConfig` -> `HookConfig`, `PluginGateConfig`, `LauncherPluginConfig` (see `zerg/plugin_config.py`).

---

## Execution Flow

### Planning Phase (`/zerg:plan`)

```
User Requirements -> [Socratic Discovery] -> requirements.md
                                                |
                                                v
                                    .gsd/specs/{feature}/requirements.md
```

### Design Phase (`/zerg:design`)

```
requirements.md -> [Architecture Analysis] -> task-graph.json + design.md
                                                |
                    +---------------------------+---------------------------+
                    v                           v                           v
            Level 1 Tasks              Level 2 Tasks              Level N Tasks
```

### Rush Phase (`/zerg:rush`)

```
[Orchestrator Start]
        |
        v
[Load task-graph.json] -> [Assign tasks to zerglings]
        |
        v
[Create git worktrees]
        |
        v
[Spawn N zergling processes]
        |
        v
+---------------------------------------------------------------------+
|  FOR EACH LEVEL:                                                    |
|    1. Zerglings execute tasks in PARALLEL                           |
|    2. Poll until all level tasks complete                           |
|    3. MERGE PROTOCOL:                                               |
|       - Merge all zergling branches -> staging                      |
|       - Run quality gates                                           |
|       - Promote staging -> main                                     |
|    4. Rebase zergling branches                                      |
|    5. Advance to next level                                         |
+---------------------------------------------------------------------+
        |
        v
[All tasks complete]
```

### Zergling Protocol

Each zergling:

1. Loads `requirements.md`, `design.md`, `task-graph.json`
2. Reads `worker-assignments.json` for its tasks
3. For each level:
   - Pick next assigned task at current level
   - Read all dependency files
   - Implement the task
   - Run verification command
   - On pass: commit, mark complete
   - On fail: retry 3x, then mark blocked
4. After level complete: wait for merge signal
5. Pull merged changes
6. Continue to next level
7. At 70% context: commit WIP, exit (orchestrator restarts)

---

## Module Reference

ZERG is composed of 80+ Python modules organized into functional groups.

### Core Modules (`zerg/`)

| Module | Purpose |
|--------|---------|
| `orchestrator.py` | Fleet management, level transitions, merge triggers |
| `levels.py` | Level-based execution control, dependency enforcement |
| `state.py` | Thread-safe file-based state persistence |
| `worker_protocol.py` | Zergling-side execution, Claude Code invocation |
| `launcher.py` | Abstract worker spawning (subprocess/container) |
| `launcher_configurator.py` | Launcher mode detection and configuration |
| `worker_manager.py` | Worker lifecycle management, health tracking |
| `level_coordinator.py` | Cross-level coordination and synchronization |

### Task Management

| Module | Purpose |
|--------|---------|
| `assign.py` | Task-to-zergling assignment with load balancing |
| `parser.py` | Parse and validate task graphs |
| `verify.py` | Execute task verification commands |
| `task_sync.py` | ClaudeTask model, TaskSyncBridge (JSON state to Claude Tasks) |
| `task_retry_manager.py` | Retry policy and management for failed tasks |
| `backlog.py` | Backlog generation and tracking |

### Resilience & Flow Control

| Module | Purpose |
|--------|---------|
| `backpressure.py` | Load shedding and flow control under pressure |
| `circuit_breaker.py` | Circuit breaker pattern for failing operations |
| `retry_backoff.py` | Exponential backoff for retry strategies |
| `risk_scoring.py` | Risk assessment for task and merge operations |
| `whatif.py` | What-if analysis for execution planning |
| `preflight.py` | Pre-execution validation checks |

### Git & Merge

| Module | Purpose |
|--------|---------|
| `git_ops.py` | Low-level git operations |
| `worktree.py` | Git worktree management for zergling isolation |
| `merge.py` | Branch merging after each level |

### Quality & Security

| Module | Purpose |
|--------|---------|
| `gates.py` | Execute quality gates (lint, typecheck, test) |
| `security.py` | Security validation, hook patterns |
| `validation.py` | Task graph and ID validation |
| `command_executor.py` | Safe command execution with argument parsing |

### Configuration & Types

| Module | Purpose |
|--------|---------|
| `config.py` | Pydantic configuration management |
| `constants.py` | Enumerations (TaskStatus, WorkerStatus, GateResult) |
| `types.py` | TypedDict and dataclass definitions |
| `schemas/` | JSON schema definitions |

### Plugin System

| Module | Purpose |
|--------|---------|
| `plugins.py` | Plugin ABCs (QualityGatePlugin, LifecycleHookPlugin, LauncherPlugin), PluginRegistry |
| `plugin_config.py` | Pydantic models for plugin YAML configuration |

### Logging & Metrics

| Module | Purpose |
|--------|---------|
| `log_writer.py` | StructuredLogWriter (per-worker JSONL), TaskArtifactCapture |
| `log_aggregator.py` | Read-side aggregation, time-sorted queries across workers |
| `logging.py` | Logging setup, Python logging bridge, LogPhase/LogEvent enums |
| `metrics.py` | Duration, percentile calculations, metric type definitions |
| `worker_metrics.py` | Per-task execution metrics (timing, context usage, retries) |
| `render_utils.py` | Output formatting and display utilities |

### Container Management

| Module | Purpose |
|--------|---------|
| `containers.py` | ContainerManager, ContainerInfo for Docker lifecycle |

### Context & Execution

| Module | Purpose |
|--------|---------|
| `context_tracker.py` | Heuristic token counting, checkpoint decisions |
| `spec_loader.py` | Load and truncate GSD specs (requirements.md, design.md) |
| `dryrun.py` | Dry-run simulation for `/zerg:rush --dry-run` |
| `worker_main.py` | Worker process entry point |
| `ports.py` | Port allocation for worker processes (range 49152-65535) |
| `exceptions.py` | Exception hierarchy (ZergError -> Task/Worker/Git/Gate errors) |
| `state_sync_service.py` | State synchronization across distributed workers |

### Project Initialization

| Module | Purpose |
|--------|---------|
| `backlog.py` | Backlog management and generation |
| `charter.py` | Project charter generation |
| `inception.py` | Inception mode (empty directory -> project scaffold) |
| `tech_selector.py` | Technology stack recommendation |
| `devcontainer_features.py` | Devcontainer feature configuration |
| `security_rules.py` | Security rules fetching from TikiTribe |

### Diagnostics (`zerg/diagnostics/`)

| Module | Purpose |
|--------|---------|
| `error_intel.py` | Multi-language error parsing, fingerprinting, chain analysis |
| `hypothesis_engine.py` | Bayesian hypothesis testing with prior/posterior scoring |
| `knowledge_base.py` | 30+ known failure patterns with calibrated probabilities |
| `log_correlator.py` | Cross-worker log correlation, temporal clustering |
| `log_analyzer.py` | Log pattern analysis and trend detection |
| `code_fixer.py` | Code-aware fix suggestions, import chain analysis |
| `recovery.py` | Recovery plan generation with risk-rated steps |
| `env_diagnostics.py` | Environment checks (Python, Docker, resources, config) |
| `state_introspector.py` | Deep state file analysis and corruption detection |
| `system_diagnostics.py` | System-level checks (disk, ports, worktrees) |
| `types.py` | Diagnostic type definitions |

### Performance Analysis (`zerg/performance/`)

| Module | Purpose |
|--------|---------|
| `stack_detector.py` | Auto-detect project language and framework |
| `tool_registry.py` | Registry of available analysis tools |
| `catalog.py` | Tool catalog with install instructions |
| `aggregator.py` | Combine results from multiple analysis tools |
| `formatters.py` | Format analysis output (markdown, SARIF, JSON) |
| `types.py` | Performance analysis type definitions |

#### Tool Adapters (`zerg/performance/adapters/`)

| Adapter | Tool | Analysis Type |
|---------|------|---------------|
| `radon_adapter.py` | radon | Cyclomatic complexity |
| `lizard_adapter.py` | lizard | Multi-language complexity |
| `vulture_adapter.py` | vulture | Dead code detection |
| `jscpd_adapter.py` | jscpd | Copy-paste detection |
| `cloc_adapter.py` | cloc | Lines of code counting |
| `semgrep_adapter.py` | semgrep | Semantic code analysis |
| `trivy_adapter.py` | trivy | Vulnerability scanning |
| `deptry_adapter.py` | deptry | Dependency health |
| `pipdeptree_adapter.py` | pipdeptree | Dependency tree analysis |
| `hadolint_adapter.py` | hadolint | Dockerfile linting |
| `dive_adapter.py` | dive | Docker image analysis |

### CLI

| Module | Purpose |
|--------|---------|
| `cli.py` | CLI entry point (`zerg` command), install/uninstall subcommands |
| `__main__.py` | Package entry point for `python -m zerg` |

### CLI Commands (`zerg/commands/`)

| Command | Module | Purpose |
|---------|--------|---------|
| `/zerg:init` | `init.py` | Project initialization (Inception/Discovery modes) |
| `/zerg:plan` | `plan.py` | Capture requirements (Socratic discovery) |
| `/zerg:design` | `design.py` | Generate architecture and task graph |
| `/zerg:rush` | `rush.py` | Launch parallel zerglings |
| `/zerg:status` | `status.py` | Progress monitoring dashboard |
| `/zerg:stop` | `stop.py` | Stop zerglings (graceful/force) |
| `/zerg:retry` | `retry.py` | Retry failed tasks |
| `/zerg:logs` | `logs.py` | View and aggregate zergling logs |
| `/zerg:merge` | `merge_cmd.py` | Manual merge control |
| `/zerg:cleanup` | `cleanup.py` | Remove artifacts |
| `/zerg:debug` | `debug.py` | Deep diagnostic investigation |
| `/zerg:build` | `build.py` | Build orchestration with error recovery |
| `/zerg:test` | `test_cmd.py` | Test execution with coverage |
| `/zerg:analyze` | `analyze.py` | Static analysis and metrics |
| `/zerg:review` | `review.py` | Code review (spec compliance + quality) |
| `/zerg:security` | `security_rules_cmd.py` | Vulnerability scanning |
| `/zerg:refactor` | `refactor.py` | Automated code improvement |
| `/zerg:git` | `git_cmd.py` | Intelligent git operations |
| `/zerg:plugins` | (command spec) | Plugin system management |
| `install_commands.py` | | Install/uninstall slash commands |

---

## Zergling Execution Model

### Isolation Strategy

```
+---------------------------------------------------------------------+
|                    ZERGLING ISOLATION LAYERS                         |
+---------------------------------------------------------------------+
| 1. Git Worktree: .zerg-worktrees/{feature}-worker-{id}/             |
|    - Independent file system                                        |
|    - Separate git history                                           |
|    - Own branch: zerg/{feature}/worker-{id}                         |
+---------------------------------------------------------------------+
| 2. Process Isolation                                                |
|    - Separate process per zergling                                  |
|    - Independent memory space                                       |
|    - Communication via state files                                  |
+---------------------------------------------------------------------+
| 3. Spec-Driven Execution                                            |
|    - No conversation history sharing                                |
|    - Read specs fresh each time                                     |
|    - Stateless, restartable                                         |
+---------------------------------------------------------------------+
```

### Launcher Abstraction

```
WorkerLauncher (ABC)
+-- SubprocessLauncher
|   +-- spawn() -> subprocess.Popen
|   +-- monitor() -> Check process status
|   +-- terminate() -> Kill process
|
+-- ContainerLauncher
|   +-- spawn() -> docker run
|   +-- monitor() -> Check container status
|   +-- terminate() -> Stop/kill container
|
+-- LauncherConfigurator
    +-- detect_mode() -> auto-select launcher
    +-- configure() -> build launcher with settings
```

### Execution Modes

| Mode | Launcher Class | How Workers Run |
|------|---------------|-----------------|
| `subprocess` | `SubprocessLauncher` | Local processes running `zerg.worker_main` |
| `container` | `ContainerLauncher` | Docker containers with mounted worktrees |
| `task` | Plugin-provided | Claude Code Task sub-agents (slash command context) |

**Auto-detection logic** (in `launcher_configurator.py`):
1. If `--mode` is explicitly set -> use that mode
2. If `.devcontainer/devcontainer.json` exists AND Docker is available -> `container`
3. If running inside a Claude Code slash command context -> `task`
4. Otherwise -> `subprocess`

Plugin launchers are resolved via `get_plugin_launcher(name, registry)` which delegates to a `LauncherPlugin.create_launcher()` call.

### Context Management

- Monitor token usage via `ContextTracker`
- Checkpoint at 70% context threshold (configurable)
- Zergling exits gracefully (code 2)
- Orchestrator restarts zergling from checkpoint

### Resilience Features

ZERG includes several resilience mechanisms:

**Backpressure** (`backpressure.py`): When the system detects excessive load (too many failures, resource exhaustion), it applies flow control to prevent cascading failures.

**Circuit Breaker** (`circuit_breaker.py`): Operations that fail repeatedly are short-circuited to avoid wasting resources on known-broken paths. The circuit opens after a threshold of failures and closes again after a cooldown period.

**Retry with Backoff** (`retry_backoff.py`): Failed operations are retried with exponential backoff. The `task_retry_manager.py` module provides task-specific retry policies.

**Risk Scoring** (`risk_scoring.py`): Tasks and merge operations are assessed for risk based on factors like file count, complexity, and dependency depth. High-risk operations receive additional validation.

**What-If Analysis** (`whatif.py`): Before execution, ZERG can simulate the impact of task assignments and level transitions to identify potential issues.

**Preflight Checks** (`preflight.py`): Pre-execution validation ensures the environment is ready (git state clean, dependencies installed, ports available).

---

## State Management

### State File Structure

Location: `.zerg/state/{feature}.json`

```json
{
  "feature": "user-auth",
  "started_at": "2026-01-26T10:00:00",
  "current_level": 2,

  "tasks": {
    "TASK-001": {
      "status": "complete",
      "worker_id": 0,
      "started_at": "...",
      "completed_at": "...",
      "retry_count": 0
    }
  },

  "workers": {
    "0": {
      "status": "running",
      "current_task": "TASK-003",
      "tasks_completed": 2,
      "branch": "zerg/user-auth/worker-0"
    }
  },

  "levels": {
    "1": { "status": "complete", "merge_status": "complete" },
    "2": { "status": "running", "merge_status": "pending" }
  }
}
```

### Task Status Transitions

```
pending -> claimed -> in_progress -> verifying -> complete
                                              \-> failed -> retry?
```

### Thread Safety

- **RLock**: Guards all state mutations
- **Atomic writes**: Full file replacement
- **Timestamps**: Enable recovery and debugging

### State Synchronization

The `state_sync_service.py` module keeps distributed state consistent across workers. It bridges the file-based state JSON with the Claude Code Task system, ensuring both remain synchronized. When conflicts arise, the Claude Code Task system is authoritative.

---

## Claude Code Task Integration

The Claude Code Task system is the **authoritative backbone** for all ZERG task coordination.

### How Tasks Flow

```
/zerg:design -> TaskCreate for each task (subject: "[L{level}] {title}")
                     |
                     v
/zerg:rush   -> TaskUpdate (in_progress) when worker claims task
                     |
                     v
Worker       -> TaskUpdate (completed) on success
                TaskUpdate (failed) on failure
                     |
                     v
/zerg:status -> TaskList to read current state
```

### Subject Convention

All ZERG tasks use bracketed prefixes for discoverability:

| Prefix | Used By | Example |
|--------|---------|---------|
| `[Plan]` | `/zerg:plan` | `[Plan] Capture requirements: user-auth` |
| `[Design]` | `/zerg:design` | `[Design] Architecture for user-auth` |
| `[L1]`..`[L5]` | `/zerg:rush` | `[L2] Implement auth service` |
| `[Init]` | `/zerg:init` | `[Init] Initialize project` |
| `[Debug]` | `/zerg:debug` | `[Debug] Diagnose WORKER_FAILURE` |
| `[Build]` | `/zerg:build` | `[Build] Build project` |
| `[Test]` | `/zerg:test` | `[Test] Run test suite` |
| `[Review]` | `/zerg:review` | `[Review] Code review` |
| `[Security]` | `/zerg:security` | `[Security] Vulnerability scan` |
| `[Cleanup]` | `/zerg:cleanup` | `[Cleanup] Remove artifacts` |

### Task Dependencies

Dependencies from `task-graph.json` are wired into the Claude Code Task system using `blocks` and `blockedBy` fields via `TaskUpdate`. This enables `/zerg:status` to show dependency state without reading the task graph.

### State JSON as Fallback

State JSON files (`.zerg/state/{feature}.json`) supplement the Task system. They provide:
- Worker-level state not tracked by Tasks (context usage, branch names)
- Fast local reads without Task API calls
- Backup coordination if the Task system is temporarily unavailable

If Task system and state JSON disagree, the **Task system wins**.

---

## Context Engineering

ZERG includes a context engineering plugin that reduces per-worker token usage by 30-50%. See [Context Engineering](docs/context-engineering.md) for configuration details.

### Architecture

```
/zerg:design phase:
  requirements.md + design.md
      |
      v
  [Section Parser] → Extract relevant paragraphs per task
      |
      v
  [Security Filter] → Match .py → Python rules, .js → JS rules
      |
      v
  [Context Assembler] → Combine within token budget (default: 4000)
      |
      v
  task-graph.json (each task has a "context" field)

/zerg:rush phase:
  Worker receives task assignment
      |
      v
  Load .core.md (not full command file)
      |
      v
  Load task.context (not full spec files)
      |
      v
  Load filtered security rules (not all rules)
      |
      v
  Execute task with scoped context
```

### Three Subsystems

| Subsystem | What It Does | Savings |
|-----------|-------------|---------|
| **Command Splitting** | Split 9 large commands into `.core.md` (~30%) + `.details.md` (~70%) | ~2,000-5,000 tokens/worker |
| **Security Rule Filtering** | Load only rules matching task file extensions | ~1,000-4,000 tokens/task |
| **Task-Scoped Context** | Spec excerpts + dependency context per task | ~2,000-5,000 tokens/task |

### Fallback Strategy

If context engineering fails for any reason and `fallback_to_full: true` (default), workers load full files. A worker with full context is better than a worker that fails to load instructions.

---

## Quality Gates

### Task Verification (Per-Task)

```json
{
  "id": "TASK-001",
  "verification": {
    "command": "python -c \"from src.models.user import User\"",
    "timeout_seconds": 60
  }
}
```

### Level Quality Gates (Per-Level)

Configuration in `.zerg/config.yaml`:

```yaml
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

### Gate Results

| Result | Description | Action |
|--------|-------------|--------|
| `pass` | Exit code 0 | Continue |
| `fail` | Non-zero exit | Block if required |
| `timeout` | Exceeded limit | Treat as failure |
| `error` | Could not run | Pause for intervention |

---

## Pre-commit Hooks

ZERG includes comprehensive pre-commit hooks at `.zerg/hooks/pre-commit`.

### Security Checks (Block Commit)

| Check | Description |
|-------|-------------|
| AWS Keys | Detects AWS Access Key ID patterns |
| GitHub PATs | Detects Personal Access Tokens |
| OpenAI Keys | Detects OpenAI API Key patterns |
| Anthropic Keys | Detects Anthropic API Key patterns |
| Private Keys | Detects PEM key file headers |
| Dangerous subprocess usage | Detects unsafe process spawning patterns |
| Dynamic code patterns | Detects unsafe dynamic code invocation |
| Unsafe deserialization | Detects risky deserialization calls |
| Sensitive Files | Blocks `.env`, `credentials.json` from commits |

### Quality Checks (Warn Only)

| Check | Description |
|-------|-------------|
| Ruff Lint | Style issues in Python files |
| Debugger | Leftover breakpoints and debugger calls |
| Merge Markers | Unresolved conflict markers |
| Large Files | Files over 5MB |

### ZERG-Specific Checks (Warn Only)

| Check | Validation |
|-------|------------|
| Branch Naming | `zerg/{feature}/worker-{N}` format |
| Print Statements | print calls in `zerg/` directory |
| Hardcoded URLs | `localhost:PORT` outside tests |

### Exempt Paths

- `tests/`, `fixtures/`
- `*_test.py`, `test_*.py`
- `conftest.py`

---

## Security Model

### Environment Variable Filtering

Workers receive a controlled set of environment variables:

**Allowed**: `ZERG_WORKER_ID`, `ZERG_FEATURE`, `ZERG_WORKTREE`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `CI`, `DEBUG`, `LOG_LEVEL`

**Blocked**: `LD_PRELOAD`, `DYLD_INSERT_LIBRARIES`, `PYTHONPATH`, `HOME`, `USER`, `SHELL`

### Command Execution Safety

| Protection | Implementation |
|------------|----------------|
| No direct shell invocation | Commands parsed with shlex, no shell passthrough |
| Allowlist | Commands checked against config |
| Timeout | Every command has max duration |
| Output capture | Separate stdout/stderr |

### Task ID Validation

```
Pattern: [A-Za-z][A-Za-z0-9_-]{0,63}

Rejects:
  - Shell metacharacters
  - Path traversal sequences
  - Excessive length (>64 chars)
```

---

## Logging Architecture

ZERG uses structured JSONL logging with two complementary outputs:

**Per-worker logs** (`.zerg/logs/workers/worker-{id}.jsonl`):
- Thread-safe writes via `StructuredLogWriter`
- Auto-rotation at 50 MB (renames to `.jsonl.1`)
- Each entry: `ts`, `level`, `worker_id`, `feature`, `message`, `task_id`, `phase`, `event`, `data`, `duration_ms`

**Per-task artifacts** (`.zerg/logs/tasks/{task-id}/`):
- `execution.jsonl` — structured execution events
- `claude_output.txt` — Claude CLI stdout/stderr
- `verification_output.txt` — verification command output
- `git_diff.patch` — diff of task changes

**Enums**:
- `LogPhase`: CLAIM, EXECUTE, VERIFY, COMMIT, CLEANUP
- `LogEvent`: TASK_STARTED, TASK_COMPLETED, TASK_FAILED, VERIFICATION_PASSED, VERIFICATION_FAILED, ARTIFACT_CAPTURED, LEVEL_STARTED, LEVEL_COMPLETE, MERGE_STARTED, MERGE_COMPLETE

**Aggregation**: `LogAggregator` provides read-side merging of JSONL files by timestamp at query time. No pre-built aggregate file exists on disk. Supports filtering by worker, task, level, phase, event, time range, and text search.

---

## Diagnostics Engine

The `zerg/diagnostics/` package provides deep investigation capabilities for `/zerg:debug`:

### Components

| Component | Module | Capability |
|-----------|--------|------------|
| Error Intelligence | `error_intel.py` | Multi-language error parsing, fingerprinting, chain analysis |
| Hypothesis Engine | `hypothesis_engine.py` | Bayesian scoring with prior/posterior probability calculation |
| Knowledge Base | `knowledge_base.py` | 30+ known failure patterns with calibrated probabilities |
| Log Correlator | `log_correlator.py` | Cross-worker correlation, temporal clustering, Jaccard similarity |
| Log Analyzer | `log_analyzer.py` | Pattern analysis and trend detection |
| Code Fixer | `code_fixer.py` | Import chain analysis, fix templates, git blame integration |
| Recovery | `recovery.py` | Risk-rated recovery plans (SAFE/MODERATE/DESTRUCTIVE) |
| Environment | `env_diagnostics.py` | Python venv, Docker, resources, config validation |
| State Introspector | `state_introspector.py` | State file analysis and corruption detection |
| System Diagnostics | `system_diagnostics.py` | Disk, ports, worktrees, Docker health |

### Diagnostic Flow

```
Error -> Parse (multi-language) -> Fingerprint -> Classify
                                                    |
                                                    v
         Correlate logs across workers -> Build timeline
                                                    |
                                                    v
         Generate hypotheses -> Bayesian scoring -> Test
                                                    |
                                                    v
         Root cause determination -> Recovery plan -> Execute (with --fix)
```

---

## Performance Analysis

The `zerg/performance/` package powers `/zerg:analyze` with pluggable tool adapters:

### Architecture

```
Stack Detector -> Tool Registry -> Adapter Selection -> Execution -> Aggregator -> Formatter
```

### Adapters

Each adapter wraps an external analysis tool:

| Adapter | Tool | Analysis |
|---------|------|----------|
| `radon_adapter` | radon | Cyclomatic complexity (Python) |
| `lizard_adapter` | lizard | Multi-language complexity |
| `vulture_adapter` | vulture | Dead code detection |
| `jscpd_adapter` | jscpd | Copy-paste / duplication |
| `cloc_adapter` | cloc | Lines of code |
| `semgrep_adapter` | semgrep | Semantic analysis |
| `trivy_adapter` | trivy | Vulnerability scanning |
| `deptry_adapter` | deptry | Dependency health |
| `pipdeptree_adapter` | pipdeptree | Dependency trees |
| `hadolint_adapter` | hadolint | Dockerfile linting |
| `dive_adapter` | dive | Docker image efficiency |

Output formats: Markdown tables, SARIF, JSON.

---

## Configuration

### Configuration File

Location: `.zerg/config.yaml`

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
  test:
    command: "pytest"
    required: true

hooks:
  pre_commit:
    enabled: true
    security_checks:
      secrets_detection: true
      block_on_violation: true
    quality_checks:
      ruff_lint: true
      warn_on_violation: true

mcp_servers:
  - name: filesystem
    command: npx
    args: ["-y", "@anthropic/mcp-filesystem"]
```

---

## Directory Structure

```
project/
+-- .zerg/
|   +-- config.yaml          # ZERG configuration
|   +-- hooks/
|   |   +-- pre-commit       # Pre-commit hook script
|   +-- state/               # Runtime state
|   |   +-- {feature}.json
|   +-- logs/                # Zergling logs
|       +-- workers/         # Structured JSONL per-worker
|       |   +-- worker-{id}.jsonl
|       +-- tasks/           # Per-task artifacts
|           +-- {task-id}/
|
+-- .zerg-worktrees/         # Git worktrees (gitignored)
|   +-- {feature}-worker-N/
|
+-- .gsd/
|   +-- PROJECT.md
|   +-- STATE.md             # Human-readable progress
|   +-- specs/{feature}/
|       +-- requirements.md
|       +-- design.md
|       +-- task-graph.json
|
+-- .devcontainer/
|   +-- devcontainer.json
|   +-- Dockerfile
|
+-- tests/
|   +-- unit/                # ~101 test files
|   +-- integration/         # ~41 test files
|   +-- e2e/                 # ~13 test files
|       +-- harness.py       # E2E test harness
|       +-- mock_worker.py   # Simulated worker
|
+-- zerg/                    # Source code (80+ modules)
    +-- commands/            # 20 CLI command implementations
    +-- diagnostics/         # Debug investigation engine
    +-- performance/         # Analysis tool adapters
    +-- schemas/             # JSON schema definitions
    +-- plugins.py           # Plugin ABCs + registry
    +-- orchestrator.py      # Core orchestration
    +-- ...                  # See Module Reference
```

---

## Error Handling

| Scenario | Response |
|----------|----------|
| Task verification fails | Retry 3x (with backoff), then mark blocked |
| Zergling crashes | Orchestrator detects, respawns from checkpoint |
| Merge conflict | Pause for human intervention |
| All zerglings blocked | Pause ZERG, alert human |
| Context limit (70%) | Commit WIP, exit for restart |
| Cascading failures | Circuit breaker opens, backpressure applied |

---

## Test Infrastructure

ZERG uses a three-tier testing strategy:

| Category | Files | Scope |
|----------|-------|-------|
| Unit | ~101 | Individual modules, pure logic, mocked dependencies |
| Integration | ~41 | Module interactions, real git operations, state management |
| E2E | ~13 | Full pipeline: orchestrator -> workers -> merge -> gates |

**E2E Harness** (`tests/e2e/harness.py`):
- `E2EHarness` creates real git repos with complete `.zerg/` directory structure
- Supports two modes: `mock` (simulated workers via `MockWorker`) and `real` (actual Claude CLI)
- Returns `E2EResult` with tasks_completed, tasks_failed, levels_completed, merge_commits, duration

**Mock Worker** (`tests/e2e/mock_worker.py`):
- Patches `WorkerProtocol.invoke_claude_code` for deterministic execution
- Generates syntactically valid Python for `.py` files
- Supports configurable failure via `fail_tasks` set

---

## Scaling Guidelines

| Zerglings | Use Case |
|-----------|----------|
| 1-2 | Small features, learning |
| 3-5 | Medium features, balanced |
| 6-10 | Large features, max throughput |

Diminishing returns beyond the widest level's parallelizable tasks.

---

## Summary

ZERG enables rapid parallel development through:

1. **Spec-driven execution** — Zerglings read specifications, not conversation history
2. **Exclusive file ownership** — No merge conflicts possible within levels
3. **Level-based dependencies** — Proper sequencing guaranteed
4. **Context engineering** — 30-50% token reduction per worker via command splitting, security rule filtering, and task-scoped context
5. **Resilient zerglings** — Circuit breakers, backpressure, retry with backoff
6. **Quality gates** — Automated verification at every stage
7. **Deep diagnostics** — Bayesian hypothesis testing, cross-worker log correlation
8. **Plugin extensibility** — Custom gates, hooks, and launchers
9. **Claude Code Task backbone** — Authoritative coordination across parallel instances
10. **Security by design** — Auto-fetched OWASP/language/Docker rules, environment filtering, pre-commit hooks
