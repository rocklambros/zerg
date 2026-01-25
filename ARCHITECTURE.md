# ZERG Architecture

## Overview

ZERG is a distributed software development system that coordinates multiple Claude Code instances to build features in parallel. It combines spec-driven development (GSD methodology), Claude Code's native Tasks for coordination, and devcontainers for isolated execution.

## Core Principles

### Spec as Memory
Workers do not share conversation context. They share:
- `requirements.md` — what to build
- `design.md` — how to build it
- `task-graph.json` — atomic work units

This makes workers stateless. Any worker can pick up any task. Crash recovery is trivial.

### Exclusive File Ownership
Each task declares which files it creates or modifies. The design phase ensures no overlap. This eliminates merge conflicts without runtime locking.

### Level-Based Execution
Tasks are organized into dependency levels:
- Level 1: Foundation (types, schemas, config)
- Level 2: Core (business logic)
- Level 3: Integration (wiring)
- Level 4: Testing
- Level 5: Quality (docs, cleanup)

All workers complete Level N before any proceed to N+1. The orchestrator merges all branches, runs quality gates, then signals workers to continue.

### Git Worktrees for Isolation
Each worker operates in its own git worktree with its own branch:
```
.zerg-worktrees/{feature}/worker-0/  →  branch: zerg/{feature}/worker-0
.zerg-worktrees/{feature}/worker-1/  →  branch: zerg/{feature}/worker-1
```

Workers commit independently. No filesystem conflicts.

## System Layers

### Layer 1: Planning
Captures requirements AND infrastructure needs. Outputs:
- `requirements.md` — problem, stories, acceptance criteria
- `INFRASTRUCTURE.md` — runtimes, databases, services needed

### Layer 2: Design
Produces architecture and task breakdown. Outputs:
- `design.md` — components, data flow, decisions
- `task-graph.json` — atomic tasks with dependencies and verification

### Layer 3: Task Coordination
Uses Claude Code's native Tasks feature:
- All workers share `CLAUDE_CODE_TASK_LIST_ID={feature}`
- Task status stored in `~/.claude/tasks/{feature}/`
- Shared via Docker volume mount

### Layer 4: Execution
N parallel containers, each running Claude Code:
- Random port allocation (49152-65535)
- Shared workspace volume (read spec files)
- Individual worktrees (write code)
- Health monitoring by orchestrator

### Layer 5: Orchestration
Python script managing the fleet:
- Worker lifecycle (start, monitor, restart)
- Level synchronization
- Branch merging with quality gates
- Progress reporting

## Task Graph Format

```json
{
  "id": "TASK-001",
  "title": "Create authentication types",
  "description": "Define TypeScript interfaces for auth domain",
  "level": 1,
  "dependencies": [],
  "files": {
    "create": ["src/auth/types.ts"],
    "modify": [],
    "read": ["src/shared/types.ts"]
  },
  "verification": {
    "command": "npx tsc --noEmit src/auth/types.ts",
    "timeout_seconds": 60
  },
  "estimate_minutes": 15
}
```

Verification must be automated pass/fail. No human judgment.

## Worker Protocol

Each worker:
1. Loads requirements.md, design.md, task-graph.json
2. Reads worker-assignments.json for its tasks
3. For each level:
   - Pick next assigned task at current level
   - Check dependencies complete (via Native Tasks)
   - Read all dependency files
   - Implement the task
   - Run verification command
   - On pass: commit, mark complete
   - On fail: retry 3x, then mark blocked
4. After level complete: wait for merge signal
5. Pull merged changes
6. Continue to next level
7. At 70% context: commit WIP, exit (orchestrator restarts)

## Merge Protocol

After all workers complete a level:
1. Create staging branch from base
2. Merge each worker branch into staging
3. Run quality gates (lint, typecheck, test, build)
4. If pass: fast-forward base to staging
5. If fail: identify failing worker, pause for human intervention
6. Rebase all worker branches onto new base
7. Signal workers to continue

## Port Allocation

Workers pick random ports in ephemeral range:
- Range: 49152-65535
- Each worker gets 10 ports (for services)
- Orchestrator tracks assignments
- Collision check via socket bind test

## Error Handling

| Scenario | Response |
|----------|----------|
| Task verification fails | Retry 3x, then mark blocked |
| Worker crashes | Orchestrator detects, respawns |
| Merge conflict | Re-run affected tasks on merged base |
| All workers blocked | Pause ZERG, alert human |
| Context limit (70%) | Commit WIP, exit for restart |

## Directory Structure

```
project/
├── .zerg/
│   ├── config.yaml          # ZERG configuration
│   ├── orchestrator.py      # Fleet manager
│   └── logs/                # Worker logs
├── .devcontainer/
│   ├── devcontainer.json    # Container definition
│   ├── Dockerfile           # Worker image
│   ├── docker-compose.yaml  # Multi-container setup
│   ├── post-create.sh       # Setup script
│   ├── post-start.sh        # Startup script
│   └── mcp-servers/         # MCP configuration
├── .claude/commands/
│   ├── zerg:init.md         # /zerg:init
│   ├── zerg:plan.md         # /zerg:plan
│   ├── zerg:design.md       # /zerg:design
│   ├── zerg:rush.md         # /zerg:rush
│   ├── zerg:worker.md       # /zerg:worker
│   └── zerg:status.md       # /zerg:status
├── .gsd/specs/{feature}/
│   ├── requirements.md      # What to build
│   ├── design.md            # How to build it
│   └── task-graph.json      # Work breakdown
└── .zerg-worktrees/         # Worker worktrees (gitignored)
```

## Comparison

| Aspect | Pure GSD | Native Tasks | ZERG |
|--------|----------|--------------|------|
| State storage | JSON files | ~/.claude/tasks | Native Tasks |
| Multi-session | Env var | Built-in | Built-in |
| Parallel exec | None | None | Orchestrated |
| Infrastructure | Not captured | Not captured | First-class |
| Isolation | None | None | Git worktrees |
| Throughput | 1x | 1x | 3-4x |

## Scaling

| Workers | Use Case |
|---------|----------|
| 1-2 | Small features, learning |
| 3-5 | Medium features, balanced |
| 6-10 | Large features, max throughput |

Diminishing returns beyond the widest level's parallelizable tasks.

## Python Package Components

### Core Modules (`zerg/`)

| Module | Purpose |
|--------|---------|
| `config.py` | Configuration loading and validation (ZergConfig, QualityGate) |
| `constants.py` | Enums and constants (Level, TaskStatus, GateResult, WorkerStatus) |
| `types.py` | Type definitions (Task, TaskGraph, WorkerState, LevelStatus) |
| `exceptions.py` | Exception hierarchy (ZergError and 15 specific exceptions) |
| `logging.py` | Structured logging with Rich formatting |
| `validation.py` | Task graph schema validation |

### Execution Modules

| Module | Purpose |
|--------|---------|
| `orchestrator.py` | Fleet management and coordination |
| `levels.py` | Level-based execution control |
| `gates.py` | Quality gate runner |
| `verify.py` | Task verification executor |
| `assign.py` | Worker assignment calculator |
| `parser.py` | Task graph parser |

### Infrastructure Modules

| Module | Purpose |
|--------|---------|
| `worktree.py` | Git worktree management |
| `git_ops.py` | Git operations (branch, merge, rebase) |
| `ports.py` | Port allocation for workers |
| `containers.py` | Docker container management |
| `state.py` | State persistence |

### Integration Modules

| Module | Purpose |
|--------|---------|
| `merge.py` | Merge coordination with conflict detection |
| `worker_protocol.py` | Worker communication protocol |
| `security.py` | Security checks and git hooks |

### CLI Commands (`zerg/commands/`)

| Command | Module | Purpose |
|---------|--------|---------|
| `init` | `init.py` | Project initialization |
| `rush` | `rush.py` | Launch parallel workers |
| `status` | `status.py` | Progress monitoring |
| `stop` | `stop.py` | Stop workers |
| `retry` | `retry.py` | Retry failed tasks |
| `logs` | `logs.py` | View worker logs |
| `cleanup` | `cleanup.py` | Remove artifacts |
| `merge` | `merge_cmd.py` | Manual merge control |

## Data Flow

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  /zerg:plan │ -> │  /zerg:design│ -> │  /zerg:rush │
└─────────────┘    └─────────────┘    └─────────────┘
       │                  │                  │
       v                  v                  v
  requirements.md    design.md         task-graph.json
                     task-graph.json         │
                                            v
                                    ┌───────────────┐
                                    │  Orchestrator │
                                    └───────────────┘
                                            │
                    ┌───────────────────────┼───────────────────────┐
                    v                       v                       v
            ┌───────────┐           ┌───────────┐           ┌───────────┐
            │ Worker 0  │           │ Worker 1  │           │ Worker N  │
            │ (worktree)│           │ (worktree)│           │ (worktree)│
            └───────────┘           └───────────┘           └───────────┘
                    │                       │                       │
                    └───────────────────────┼───────────────────────┘
                                            v
                                    ┌───────────────┐
                                    │ Level Merge   │
                                    │ Quality Gates │
                                    └───────────────┘
                                            │
                                            v
                                    ┌───────────────┐
                                    │  Main Branch  │
                                    └───────────────┘
```

## Future Considerations

- **Dashboard**: Web UI for real-time progress
- **Dynamic scaling**: Add workers when graph widens
- **Cost tracking**: Monitor API usage per worker
- **Remote execution**: Run workers on cloud instances
- **Caching**: Skip unchanged verification commands