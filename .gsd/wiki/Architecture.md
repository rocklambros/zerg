# Architecture

> System design overview for ZERG - Zero-Effort Rapid Growth parallel execution system.

---

## Overview

ZERG is a distributed software development system that coordinates multiple Claude Code instances ("zerglings") to build features in parallel. It combines:

- **Spec-driven development** (GSD methodology) - Zerglings read specs, not conversation history
- **Level-based task execution** - Dependencies enforced through level groupings
- **Git worktrees** - Each worker operates in isolated filesystem + branch
- **Claude Code Tasks** - Authoritative coordination backbone

The system transforms requirements into executable task graphs, then orchestrates parallel workers through a multi-phase build cycle with quality gates at each level transition.

---

## System Layers

```
+---------------------------------------------------------------------+
|                        Layer 1: Planning                             |
|                 requirements.md + INFRASTRUCTURE.md                  |
|                    (/zerg:plan, /zerg:brainstorm)                   |
+---------------------------------------------------------------------+
                                |
                                v
+---------------------------------------------------------------------+
|                        Layer 2: Design                               |
|                  design.md + task-graph.json                        |
|                         (/zerg:design)                              |
+---------------------------------------------------------------------+
                                |
                                v
+---------------------------------------------------------------------+
|                     Layer 3: Orchestration                           |
|    Zergling lifecycle - Level sync - Branch merging - Monitoring    |
|                          (/zerg:rush)                               |
+---------------------------------------------------------------------+
          |                     |                     |
          v                     v                     v
+-------------+       +-------------+       +-------------+
| Zergling 0  |       | Zergling 1  |       | Zergling N  |
|  (worktree) |       |  (worktree) |       |  (worktree) |
+-------------+       +-------------+       +-------------+
          |                     |                     |
          +---------------------+---------------------+
                                |
                                v
+---------------------------------------------------------------------+
|                     Layer 4: Quality Gates                           |
|             Lint - Type-check - Test - Merge to main                |
|                        (/zerg:merge)                                |
+---------------------------------------------------------------------+
```

### Layer Responsibilities

| Layer | Phase | Artifacts | Commands |
|-------|-------|-----------|----------|
| **Planning** | Requirements capture | `requirements.md` | `/zerg:plan`, `/zerg:brainstorm` |
| **Design** | Architecture & task breakdown | `design.md`, `task-graph.json` | `/zerg:design` |
| **Orchestration** | Parallel execution | State files, logs, worktrees | `/zerg:rush`, `/zerg:status` |
| **Quality** | Verification & integration | Merged branches, gate results | `/zerg:merge`, `/zerg:test` |

---

## Module Reference

ZERG comprises 80+ Python modules organized into functional groups.

### Core Orchestration

| Module | Path | Responsibility |
|--------|------|----------------|
| `orchestrator` | `zerg/orchestrator.py` | Fleet management, level transitions, merge triggers |
| `levels` | `zerg/levels.py` | Level-based execution control, dependency enforcement |
| `state` | `zerg/state.py` | Thread-safe file-based state persistence |
| `worker_protocol` | `zerg/worker_protocol.py` | Zergling-side execution, Claude Code invocation |
| `launcher` | `zerg/launcher.py` | Abstract worker spawning (subprocess/container/task) |
| `launcher_configurator` | `zerg/launcher_configurator.py` | Launcher mode detection and configuration |
| `worker_manager` | `zerg/worker_manager.py` | Worker lifecycle management, health tracking |
| `level_coordinator` | `zerg/level_coordinator.py` | Cross-level coordination and synchronization |

### Task Management

| Module | Path | Responsibility |
|--------|------|----------------|
| `assign` | `zerg/assign.py` | Task-to-zergling assignment with load balancing |
| `parser` | `zerg/parser.py` | Parse and validate task graphs |
| `verify` | `zerg/verify.py` | Execute task verification commands |
| `task_sync` | `zerg/task_sync.py` | ClaudeTask model, TaskSyncBridge (JSON to Tasks) |
| `task_retry_manager` | `zerg/task_retry_manager.py` | Retry policy and management for failed tasks |

### Resilience

| Module | Path | Responsibility |
|--------|------|----------------|
| `backpressure` | `zerg/backpressure.py` | Load shedding and flow control under pressure |
| `circuit_breaker` | `zerg/circuit_breaker.py` | Circuit breaker pattern for failing operations |
| `retry_backoff` | `zerg/retry_backoff.py` | Exponential backoff for retry strategies |
| `risk_scoring` | `zerg/risk_scoring.py` | Risk assessment for task and merge operations |
| `preflight` | `zerg/preflight.py` | Pre-execution validation checks |

### Git Operations

| Module | Path | Responsibility |
|--------|------|----------------|
| `git_ops` | `zerg/git_ops.py` | Low-level git operations |
| `worktree` | `zerg/worktree.py` | Git worktree management for zergling isolation |
| `merge` | `zerg/merge.py` | Branch merging after each level |

### Quality & Security

| Module | Path | Responsibility |
|--------|------|----------------|
| `gates` | `zerg/gates.py` | Execute quality gates (lint, typecheck, test) |
| `security` | `zerg/security.py` | Security validation, hook patterns |
| `validation` | `zerg/validation.py` | Task graph and ID validation |
| `command_executor` | `zerg/command_executor.py` | Safe command execution with argument parsing |

### Plugin System

| Module | Path | Responsibility |
|--------|------|----------------|
| `plugins` | `zerg/plugins.py` | Plugin ABCs (QualityGatePlugin, LifecycleHookPlugin, LauncherPlugin), PluginRegistry |
| `plugin_config` | `zerg/plugin_config.py` | Pydantic models for plugin YAML configuration |

### Diagnostics

| Module | Path | Responsibility |
|--------|------|----------------|
| `error_intel` | `zerg/diagnostics/error_intel.py` | Multi-language error parsing, fingerprinting |
| `hypothesis_engine` | `zerg/diagnostics/hypothesis_engine.py` | Bayesian hypothesis testing |
| `knowledge_base` | `zerg/diagnostics/knowledge_base.py` | 30+ known failure patterns |
| `log_correlator` | `zerg/diagnostics/log_correlator.py` | Cross-worker log correlation |
| `recovery` | `zerg/diagnostics/recovery.py` | Recovery plan generation |

### CLI Commands

| Command | Module | Purpose |
|---------|--------|---------|
| `/zerg:init` | `zerg/commands/init.py` | Project initialization |
| `/zerg:plan` | `zerg/commands/plan.py` | Requirements capture |
| `/zerg:design` | `zerg/commands/design.py` | Architecture and task graph |
| `/zerg:rush` | `zerg/commands/rush.py` | Launch parallel workers |
| `/zerg:status` | `zerg/commands/status.py` | Progress monitoring |
| `/zerg:worker` | `zerg/commands/worker.py` | Zergling execution protocol |
| `/zerg:merge` | `zerg/commands/merge_cmd.py` | Manual merge control |
| `/zerg:debug` | `zerg/commands/debug.py` | Diagnostic investigation |

---

## Execution Model

### Three Execution Modes

| Mode | Launcher Class | How Workers Run |
|------|---------------|-----------------|
| `task` | Plugin-provided | Claude Code Task sub-agents (default) |
| `subprocess` | `SubprocessLauncher` | Local processes running `zerg.worker_main` |
| `container` | `ContainerLauncher` | Docker containers with mounted worktrees |

### Auto-Detection Logic

The `launcher_configurator.py` module selects execution mode:

1. If `--mode` flag is explicitly set -> use that mode
2. If `.devcontainer/devcontainer.json` exists AND Docker available -> `container`
3. If running inside Claude Code slash command context -> `task`
4. Otherwise -> `subprocess`

### Worker Lifecycle

```
[Orchestrator]
      |
      v
[Spawn N workers] --> [Assign tasks from task-graph.json]
      |
      v
+---------------------------------------------------------------------+
|  FOR EACH LEVEL:                                                     |
|    1. Workers execute assigned tasks in PARALLEL                     |
|    2. Each worker: claim -> execute -> verify -> commit              |
|    3. Orchestrator polls until all level tasks complete              |
|    4. MERGE PROTOCOL:                                                |
|       - Merge all worker branches -> staging branch                  |
|       - Run quality gates (lint, typecheck, test)                    |
|       - Promote staging -> feature branch                            |
|    5. Rebase worker branches onto merged state                       |
|    6. Advance to next level                                          |
+---------------------------------------------------------------------+
      |
      v
[All levels complete] --> [Feature branch ready for PR]
```

### Worker Protocol (per task)

1. **Claim**: Mark task `in_progress` via TaskUpdate
2. **Load**: Read `requirements.md`, `design.md`, task context
3. **Execute**: Implement according to task specification
4. **Verify**: Run verification command from task-graph.json
5. **Commit**: Stage owned files, commit with task ID
6. **Report**: Mark task `completed` or `failed` via TaskUpdate

### Context Management

Workers track token usage via `ContextTracker`:
- Checkpoint at 70% context threshold (configurable)
- Worker exits gracefully with code 2
- Orchestrator respawns worker from checkpoint

---

## Claude Code Task Integration

The Claude Code Task system is the **authoritative backbone** for ZERG coordination.

### Task Flow

```
/zerg:design
    |
    v
TaskCreate for each task --> Subject: "[L{level}] {title}"
    |
    v
/zerg:rush
    |
    v
TaskUpdate (in_progress) --> Worker claims task
    |
    v
Worker executes
    |
    v
TaskUpdate (completed/failed) --> Worker reports result
    |
    v
/zerg:status
    |
    v
TaskList --> Read current state across all workers
```

### Subject Convention

All ZERG tasks use bracketed prefixes for discoverability:

| Prefix | Command | Example |
|--------|---------|---------|
| `[Plan]` | `/zerg:plan` | `[Plan] Capture requirements: user-auth` |
| `[Design]` | `/zerg:design` | `[Design] Architecture for user-auth` |
| `[L1]`..`[L5]` | `/zerg:rush` | `[L2] Implement auth service` |
| `[Init]` | `/zerg:init` | `[Init] Initialize project` |
| `[Debug]` | `/zerg:debug` | `[Debug] Diagnose WORKER_FAILURE` |
| `[Build]` | `/zerg:build` | `[Build] Build project` |
| `[Test]` | `/zerg:test` | `[Test] Run test suite` |
| `[Cleanup]` | `/zerg:cleanup` | `[Cleanup] Remove artifacts` |

### Task Dependencies

Dependencies from `task-graph.json` are wired via TaskUpdate using `blocks` and `blockedBy` fields:

```json
{
  "id": "TASK-002",
  "depends_on": ["TASK-001"]
}
```

Maps to: `TaskUpdate(taskId="TASK-002", addBlockedBy=["TASK-001"])`

### State JSON as Supplement

State files (`.zerg/state/{feature}.json`) supplement Tasks with:
- Worker-level state (context usage, branch names)
- Fast local reads without API calls
- Backup coordination if Task system unavailable

**Priority**: If Tasks and state JSON disagree, **Tasks win**.

---

## Data Flow

### Spec-to-Execution Pipeline

```
User Requirements
       |
       v
/zerg:plan --> requirements.md
       |            |
       v            v
/zerg:design --> design.md + task-graph.json
       |                          |
       v                          v
/zerg:rush --> Worker Assignments + State
       |              |
       +------+-------+
              |
              v
       [Worker 0]    [Worker 1]    [Worker N]
              |              |              |
              v              v              v
       [Task Execution in Isolated Worktrees]
              |              |              |
              +------+-------+------+-------+
                     |
                     v
              [Level Complete]
                     |
                     v
              [Merge Protocol]
                     |
                     v
              [Quality Gates]
                     |
                     v
              [Next Level or Done]
```

### File Locations

| Artifact | Path | Purpose |
|----------|------|---------|
| Requirements | `.gsd/specs/{feature}/requirements.md` | What to build |
| Design | `.gsd/specs/{feature}/design.md` | How to build it |
| Task Graph | `.gsd/specs/{feature}/task-graph.json` | Atomic work units |
| State | `.zerg/state/{feature}.json` | Runtime state |
| Worker Logs | `.zerg/logs/workers/worker-{id}.jsonl` | Structured events |
| Task Artifacts | `.zerg/logs/tasks/{task-id}/` | Per-task outputs |
| Worktrees | `.zerg-worktrees/{feature}-worker-{N}/` | Isolated filesystems |

---

## Key Concepts

### Levels

Tasks are organized into dependency levels:

| Level | Name | Description |
|-------|------|-------------|
| 1 | Foundation | Types, schemas, config |
| 2 | Core | Business logic, services |
| 3 | Integration | Wiring, endpoints |
| 4 | Testing | Unit and integration tests |
| 5 | Quality | Docs, cleanup |

**Rule**: All workers complete Level N before any proceed to Level N+1.

### File Ownership

Each task declares exclusive file ownership. No overlap within a level:

```json
{
  "id": "TASK-001",
  "files": {
    "create": ["src/models/user.py"],
    "modify": ["src/config.py"],
    "read": ["src/types.py"]
  }
}
```

Benefits:
- No merge conflicts within levels
- No runtime locking needed
- Any worker can pick up any task

### Verification

Every task includes a verification command:

```json
{
  "id": "TASK-001",
  "verification": {
    "command": "python -c \"from src.models.user import User\"",
    "timeout_seconds": 60
  }
}
```

Results:
- **Pass**: Exit code 0 -> task marked complete
- **Fail**: Non-zero exit -> retry up to 3x, then mark blocked
- **Timeout**: Exceeded limit -> treated as failure

### Worktree Isolation

Each worker operates in its own git worktree:

```
.zerg-worktrees/{feature}/worker-0/  ->  branch: zerg/{feature}/worker-0
.zerg-worktrees/{feature}/worker-1/  ->  branch: zerg/{feature}/worker-1
```

Isolation layers:
1. **Filesystem**: Independent working directory
2. **Git history**: Separate branch per worker
3. **Process**: Separate memory space
4. **Spec-driven**: No conversation sharing

---

## Quality Gates

### Per-Task Verification

Each task includes verification in `task-graph.json`. Workers run verification after implementation.

### Per-Level Quality Gates

After all tasks complete, before merge:

```yaml
# .zerg/config.yaml
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

| Result | Description | Action |
|--------|-------------|--------|
| `pass` | Exit code 0 | Continue to merge |
| `fail` | Non-zero exit | Block if required gate |
| `timeout` | Exceeded limit | Treat as failure |
| `error` | Could not run | Pause for intervention |

---

## Related Documentation

- [Commands](./Commands.md) - CLI command reference
- [Configuration](./Configuration.md) - Config file options
- [Troubleshooting](./Troubleshooting.md) - Common issues and fixes

---

*Generated from [ARCHITECTURE.md](/ARCHITECTURE.md)*
