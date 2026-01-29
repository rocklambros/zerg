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
.zerg-worktrees/{feature}/worker-0/  →  branch: zerg/{feature}/worker-0
.zerg-worktrees/{feature}/worker-1/  →  branch: zerg/{feature}/worker-1
```

Zerglings commit independently. No filesystem conflicts.

---

## System Layers

```
┌─────────────────────────────────────────────────────────────────┐
│                     Layer 1: Planning                           │
│          requirements.md + INFRASTRUCTURE.md                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Layer 2: Design                             │
│              design.md + task-graph.json                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Layer 3: Orchestration                         │
│   Zergling lifecycle • Level sync • Branch merging • Monitoring  │
└─────────────────────────────────────────────────────────────────┘
          │                   │                   │
          ▼                   ▼                   ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Zergling 0  │     │ Zergling 1  │     │ Zergling N  │
│  (worktree) │     │  (worktree) │     │  (worktree) │
└─────────────┘     └─────────────┘     └─────────────┘
          │                   │                   │
          └───────────────────┴───────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Layer 4: Quality Gates                         │
│           Lint • Type-check • Test • Merge to main              │
└─────────────────────────────────────────────────────────────────┘
```

### Plugin System

ZERG's plugin architecture provides three extension points via abstract base classes:

```
PluginRegistry
├── hooks: dict[str, list[Callable]]     # LifecycleHookPlugin callbacks
├── gates: dict[str, QualityGatePlugin]  # Named quality gate plugins
└── launchers: dict[str, LauncherPlugin] # Named launcher plugins

QualityGatePlugin (ABC)
├── name: str
└── run(ctx: GateContext) → GateRunResult

LifecycleHookPlugin (ABC)
├── name: str
└── on_event(event: LifecycleEvent) → None

LauncherPlugin (ABC)
├── name: str
└── create_launcher(config) → WorkerLauncher
```

**PluginHookEvent** lifecycle (8 events): `TASK_STARTED`, `TASK_COMPLETED`, `LEVEL_COMPLETE`, `MERGE_COMPLETE`, `RUSH_FINISHED`, `QUALITY_GATE_RUN`, `WORKER_SPAWNED`, `WORKER_EXITED`

**Integration points**:
- `orchestrator.py` — emits lifecycle events, runs plugin gates after merge
- `worker_protocol.py` — emits `TASK_STARTED`/`TASK_COMPLETED` events
- `gates.py` — delegates to plugin gates registered in the registry
- `launcher.py` — resolves launcher plugins by name via `get_plugin_launcher()`

**Discovery**: Plugins are loaded via `importlib.metadata` entry points (group: `zerg.plugins`) or YAML-configured shell command hooks in `.zerg/config.yaml`.

Configuration models: `PluginsConfig` → `HookConfig`, `PluginGateConfig`, `LauncherPluginConfig` (see `zerg/plugin_config.py`).

---

## Execution Flow

### Planning Phase (`/zerg:plan`)

```
User Requirements → [Socratic Discovery] → requirements.md
                                                │
                                                ▼
                                    .gsd/specs/{feature}/requirements.md
```

### Design Phase (`/zerg:design`)

```
requirements.md → [Architecture Analysis] → task-graph.json + design.md
                                                │
                    ┌───────────────────────────┼───────────────────────────┐
                    ▼                           ▼                           ▼
            Level 1 Tasks              Level 2 Tasks              Level N Tasks
```

### Rush Phase (`/zerg:rush`)

```
[Orchestrator Start]
        │
        ▼
[Load task-graph.json] → [Assign tasks to zerglings]
        │
        ▼
[Create git worktrees]
        │
        ▼
[Spawn N zergling processes]
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│  FOR EACH LEVEL:                                                │
│    1. Zerglings execute tasks in PARALLEL                       │
│    2. Poll until all level tasks complete                       │
│    3. MERGE PROTOCOL:                                           │
│       • Merge all zergling branches → staging                   │
│       • Run quality gates                                       │
│       • Promote staging → main                                  │
│    4. Rebase zergling branches                                  │
│    5. Advance to next level                                     │
└─────────────────────────────────────────────────────────────────┘
        │
        ▼
[All tasks complete] ✓
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

### Core Modules (`zerg/`)

| Module | Lines | Purpose |
|--------|-------|---------|
| `orchestrator.py` | ~850 | Fleet management, level transitions, merge triggers |
| `levels.py` | ~350 | Level-based execution control, dependency enforcement |
| `state.py` | ~700 | Thread-safe file-based state persistence |
| `worker_protocol.py` | ~600 | Zergling-side execution, Claude Code invocation |
| `launcher.py` | ~450 | Abstract worker spawning (subprocess/container) |

### Task Management

| Module | Lines | Purpose |
|--------|-------|---------|
| `assign.py` | ~200 | Task-to-zergling assignment with load balancing |
| `parser.py` | ~195 | Parse and validate task graphs |
| `verify.py` | ~280 | Execute task verification commands |

### Git & Merge

| Module | Lines | Purpose |
|--------|-------|---------|
| `git_ops.py` | ~380 | Low-level git operations |
| `worktree.py` | ~300 | Git worktree management for zergling isolation |
| `merge.py` | ~280 | Branch merging after each level |

### Quality & Security

| Module | Lines | Purpose |
|--------|-------|---------|
| `gates.py` | ~280 | Execute quality gates (lint, typecheck, test) |
| `security.py` | ~380 | Security validation, hook patterns |
| `validation.py` | ~340 | Task graph and ID validation |
| `command_executor.py` | ~530 | Safe command execution (no shell=True) |

### Configuration & Types

| Module | Lines | Purpose |
|--------|-------|---------|
| `config.py` | ~200 | Pydantic configuration management |
| `constants.py` | ~114 | Enumerations (TaskStatus, WorkerStatus, GateResult) |
| `types.py` | ~388 | TypedDict and dataclass definitions |

### Plugin System

| Module | Lines | Purpose |
|--------|-------|---------|
| `plugins.py` | ~241 | Plugin ABCs (QualityGatePlugin, LifecycleHookPlugin, LauncherPlugin), PluginRegistry |
| `plugin_config.py` | ~37 | Pydantic models for plugin YAML configuration |

### Container Management

| Module | Lines | Purpose |
|--------|-------|---------|
| `containers.py` | ~60 | ContainerManager, ContainerInfo for Docker lifecycle |

### Logging

| Module | Lines | Purpose |
|--------|-------|---------|
| `log_writer.py` | ~241 | StructuredLogWriter (per-worker JSONL), TaskArtifactCapture |
| `log_aggregator.py` | ~220 | Read-side aggregation, time-sorted queries across workers |
| `logging.py` | ~322 | Logging setup, Python logging bridge, LogPhase/LogEvent enums |

### Metrics

| Module | Lines | Purpose |
|--------|-------|---------|
| `metrics.py` | ~80 | Duration, percentile calculations, metric type definitions |
| `worker_metrics.py` | ~40 | Per-task execution metrics (timing, context usage, retries) |

### Task Coordination

| Module | Lines | Purpose |
|--------|-------|---------|
| `task_sync.py` | ~60 | ClaudeTask model, TaskSyncBridge (JSON state → Claude Tasks) |

### Supporting Modules

| Module | Lines | Purpose |
|--------|-------|---------|
| `ports.py` | ~60 | Port allocation for worker processes (range 49152-65535) |
| `exceptions.py` | ~223 | Exception hierarchy (ZergError → Task/Worker/Git/Gate errors) |
| `spec_loader.py` | ~40 | Load and truncate GSD specs (requirements.md, design.md) |
| `context_tracker.py` | ~60 | Heuristic token counting, checkpoint decisions |
| `dryrun.py` | ~60 | Dry-run simulation for `/zerg:rush --dry-run` |
| `worker_main.py` | ~60 | Worker process entry point |

### Project Initialization

| Module | Lines | Purpose |
|--------|-------|---------|
| `backlog.py` | - | Backlog management |
| `charter.py` | - | Project charter generation |
| `inception.py` | - | Inception mode (empty directory → project scaffold) |
| `tech_selector.py` | - | Technology stack recommendation |
| `devcontainer_features.py` | - | Devcontainer feature configuration |
| `security_rules.py` | - | Security rules fetching from TikiTribe |

### CLI

| Module | Lines | Purpose |
|--------|-------|---------|
| `cli.py` | - | CLI entry point (`zerg` command), install/uninstall subcommands |

### CLI Commands (`zerg/commands/`)

| Command | Module | Purpose |
|---------|--------|---------|
| `/zerg:init` | `init.py` | Project initialization |
| `/zerg:plan` | `plan.py` | Capture requirements |
| `/zerg:design` | `design.py` | Generate architecture |
| `/zerg:rush` | `rush.py` | Launch parallel zerglings |
| `/zerg:status` | `status.py` | Progress monitoring |
| `/zerg:stop` | `stop.py` | Stop zerglings |
| `/zerg:retry` | `retry.py` | Retry failed tasks |
| `/zerg:logs` | `logs.py` | View zergling logs |
| `/zerg:merge` | `merge_cmd.py` | Manual merge control |
| `/zerg:cleanup` | `cleanup.py` | Remove artifacts |

---

## Zergling Execution Model

### Isolation Strategy

```
┌─────────────────────────────────────────────────────────────────┐
│                    ZERGLING ISOLATION LAYERS                    │
├─────────────────────────────────────────────────────────────────┤
│ 1. Git Worktree: .zerg-worktrees/{feature}-worker-{id}/         │
│    • Independent file system                                     │
│    • Separate git history                                        │
│    • Own branch: zerg/{feature}/worker-{id}                     │
├─────────────────────────────────────────────────────────────────┤
│ 2. Process Isolation                                            │
│    • Separate process per zergling                              │
│    • Independent memory space                                    │
│    • Communication via state files                               │
├─────────────────────────────────────────────────────────────────┤
│ 3. Spec-Driven Execution                                        │
│    • No conversation history sharing                            │
│    • Read specs fresh each time                                 │
│    • Stateless, restartable                                     │
└─────────────────────────────────────────────────────────────────┘
```

### Launcher Abstraction

```
WorkerLauncher (ABC)
├── SubprocessLauncher
│   ├── spawn() → subprocess.Popen
│   ├── monitor() → Check process status
│   └── terminate() → Kill process
│
└── ContainerLauncher
    ├── spawn() → docker run
    ├── monitor() → Check container status
    └── terminate() → Stop/kill container
```

Auto-detection: Uses `ContainerLauncher` if devcontainer.json exists and Docker is available, otherwise `SubprocessLauncher`.

### Context Management

- Monitor token usage via `ContextTracker`
- Checkpoint at 70% context threshold
- Zergling exits gracefully (code 2)
- Orchestrator restarts zergling from checkpoint

### Execution Modes

| Mode | Launcher Class | How Workers Run |
|------|---------------|-----------------|
| `subprocess` | `SubprocessLauncher` | Local `subprocess.Popen` running `zerg.worker_main` |
| `container` | `ContainerLauncher` | Docker containers with mounted worktrees |
| `task` | Plugin-provided | Claude Code Task sub-agents (slash command context) |

**Auto-detection logic**:
1. If `--mode` is explicitly set → use that mode
2. If `.devcontainer/devcontainer.json` exists AND Docker is available → `container`
3. If running inside a Claude Code slash command context → `task`
4. Otherwise → `subprocess`

Plugin launchers are resolved via `get_plugin_launcher(name, registry)` which delegates to a `LauncherPlugin.create_launcher()` call.

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
pending → claimed → in_progress → verifying → complete
                                           ↘ failed → retry?
```

### Thread Safety

- **RLock**: Guards all state mutations
- **Atomic writes**: Full file replacement
- **Timestamps**: Enable recovery and debugging

### Logging Architecture

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
| `error` | Couldn't execute | Pause for intervention |

---

## Pre-commit Hooks

ZERG includes comprehensive pre-commit hooks at `.zerg/hooks/pre-commit`.

### Security Checks (Block Commit)

| Check | Pattern | Description |
|-------|---------|-------------|
| AWS Keys | `AKIA[0-9A-Z]{16}` | AWS Access Key IDs |
| GitHub PATs | `ghp_[a-zA-Z0-9]{36}` | Personal Access Tokens |
| OpenAI Keys | `sk-[a-zA-Z0-9]{48}` | OpenAI API Keys |
| Anthropic Keys | `sk-ant-[a-zA-Z0-9_-]+` | Anthropic API Keys |
| Private Keys | `-----BEGIN * PRIVATE KEY-----` | Key headers |
| Shell Injection | `shell=True`, `os.system()` | Dangerous patterns |
| Code Injection | `eval()`, `exec()` | Dynamic code execution |
| Pickle | `pickle.load()` | Unsafe deserialization |
| Sensitive Files | `.env`, `credentials.json` | Credential files |

### Quality Checks (Warn Only)

| Check | Description |
|-------|-------------|
| Ruff Lint | Style issues in Python files |
| Debugger | `breakpoint()`, `pdb.set_trace()` |
| Merge Markers | Unresolved `<<<<<<<` conflicts |
| Large Files | Files >5MB |

### ZERG-Specific Checks (Warn Only)

| Check | Validation |
|-------|------------|
| Branch Naming | `zerg/{feature}/worker-{N}` format |
| Print Statements | `print()` in `zerg/` directory |
| Hardcoded URLs | `localhost:PORT` outside tests |

### Exempt Paths

- `tests/`, `fixtures/`
- `*_test.py`, `test_*.py`
- `conftest.py`

### Hook Patterns in Code

Patterns are defined in `zerg/security.py`:

```python
HOOK_PATTERNS = {
    "security": {
        "aws_key": r"AKIA[0-9A-Z]{16}",
        "github_pat": r"(ghp_[a-zA-Z0-9]{36}|github_pat_...)",
        ...
    },
    "quality": {
        "debugger": r"(breakpoint\s*\(\)|pdb\.set_trace\s*\(\))",
        ...
    }
}
```

---

## Security Model

### Environment Variable Filtering

```python
ALLOWED_ENV_VARS = {
    "ZERG_WORKER_ID", "ZERG_FEATURE", "ZERG_WORKTREE",
    "ANTHROPIC_API_KEY", "OPENAI_API_KEY",
    "CI", "DEBUG", "LOG_LEVEL"
}

DANGEROUS_ENV_VARS = {
    "LD_PRELOAD", "DYLD_INSERT_LIBRARIES",
    "PYTHONPATH", "HOME", "USER", "SHELL"
}
```

### Command Execution Safety

| Protection | Implementation |
|------------|----------------|
| No shell=True | Commands parsed explicitly |
| Allowlist | Commands checked against config |
| Timeout | Every command has max duration |
| Output capture | Separate stdout/stderr |

### Task ID Validation

```
Pattern: [A-Za-z][A-Za-z0-9_-]{0,63}

Rejects:
  • Shell metacharacters (;|&`$)
  • Path traversal (../)
  • Excessive length (>64 chars)
```

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
      shell_injection: true
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
├── .zerg/
│   ├── config.yaml          # ZERG configuration
│   ├── hooks/
│   │   └── pre-commit       # Pre-commit hook script
│   ├── state/               # Runtime state
│   │   └── {feature}.json
│   └── logs/                # Zergling logs
│       ├── workers/         # Structured JSONL per-worker
│       │   └── worker-{id}.jsonl
│       └── tasks/           # Per-task artifacts
│           └── {task-id}/
│
├── .zerg-worktrees/         # Git worktrees (gitignored)
│   └── {feature}-worker-N/
│
├── .gsd/
│   ├── PROJECT.md
│   ├── STATE.md             # Human-readable progress
│   └── specs/{feature}/
│       ├── requirements.md
│       ├── design.md
│       └── task-graph.json
│
├── .devcontainer/
│   ├── devcontainer.json
│   └── Dockerfile
│
├── tests/
│   ├── unit/                # ~101 test files
│   ├── integration/         # ~41 test files
│   └── e2e/                 # ~13 test files
│       ├── harness.py       # E2E test harness
│       └── mock_worker.py   # Simulated worker
│
└── zerg/                    # Source code (42+ modules)
    ├── plugins.py           # Plugin ABCs + registry
    ├── plugin_config.py     # Plugin config models
    ├── log_writer.py        # Structured JSONL logging
    ├── log_aggregator.py    # Read-side log queries
    └── ...                  # See Module Reference
```

---

## Error Handling

| Scenario | Response |
|----------|----------|
| Task verification fails | Retry 3x, then mark blocked |
| Zergling crashes | Orchestrator detects, respawns |
| Merge conflict | Pause for human intervention |
| All zerglings blocked | Pause ZERG, alert human |
| Context limit (70%) | Commit WIP, exit for restart |

### Test Infrastructure

ZERG uses a three-tier testing strategy:

| Category | Files | Scope |
|----------|-------|-------|
| Unit | ~101 | Individual modules, pure logic, mocked dependencies |
| Integration | ~41 | Module interactions, real git operations, state management |
| E2E | ~13 | Full pipeline: orchestrator → workers → merge → gates |

**E2E Harness** (`tests/e2e/harness.py`):
- `E2EHarness` creates real git repos with complete `.zerg/` directory structure
- Supports two modes: `mock` (simulated workers via `MockWorker`) and `real` (actual Claude CLI)
- Returns `E2EResult` with tasks_completed, tasks_failed, levels_completed, merge_commits, duration

**Mock Worker** (`tests/e2e/mock_worker.py`):
- Patches `WorkerProtocol.invoke_claude_code` for deterministic execution
- Generates syntactically valid Python for `.py` files
- Supports configurable failure via `fail_tasks` set

**Plugin Lifecycle Tests** (`tests/integration/test_plugin_lifecycle.py`, `tests/unit/test_plugins.py`):
- Verify plugin registration, event dispatch, gate execution, and YAML hook loading

---

## Scaling Guidelines

| Zerglings | Use Case |
|---------|----------|
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
4. **Resilient zerglings** — Automatic retry and checkpoint recovery
5. **Quality gates** — Automated verification at every stage
6. **Security by design** — Strict validation and pre-commit hooks

The result: Complex features developed rapidly through coordinated parallel execution while maintaining code quality and preventing conflicts.
