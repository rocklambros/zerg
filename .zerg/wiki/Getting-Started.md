# Getting Started

This page explains the core concepts behind ZERG. Understanding these concepts will help you use the system effectively and debug issues when they arise.

**Prerequisites:** You should be familiar with Claude Code, git branching, and basic terminal usage.

---

## Table of Contents

- [Overview](#overview)
- [Levels](#levels)
- [File Ownership](#file-ownership)
- [Spec as Memory](#spec-as-memory)
- [Verification](#verification)
- [The Task Ecosystem](#the-task-ecosystem)
- [Context Engineering](#context-engineering)
- [Execution Modes](#execution-modes)

---

## Overview

ZERG turns a feature request into parallel work by following a strict pipeline:

| Stage | Command | Output |
|-------|---------|--------|
| 0. Brainstorm (optional) | `/zerg:brainstorm` (--socratic mode) | GitHub issues |
| 1. Plan | `/zerg:plan <feature>` | `requirements.md` |
| 2. Design | `/zerg:design` | `design.md` + `task-graph.json` |
| 3. Rush | `/zerg:rush --workers=N` | Parallel worker sessions |
| 4. Merge | `/zerg:merge` (or automatic) | Merged branches + quality gate results |

Each stage produces artifacts that the next stage consumes. The artifacts live in `.gsd/specs/<feature>/` and serve as the single source of truth for all workers.

---

## Levels

Tasks are organized into dependency levels. A level is a group of tasks that can all execute in parallel because none of them depend on each other.

```
Level 1 (Foundation)     Level 2 (Core)         Level 3 (Integration)
+-----------+           +-----------+           +-----------+
| TASK-001  |           | TASK-003  |           | TASK-005  |
| types.ts  |--+------->| service.ts|--+------->| routes.ts |
+-----------+  |        +-----------+  |        +-----------+
               |                       |
+-----------+  |        +-----------+  |        +-----------+
| TASK-002  |--+------->| TASK-004  |--+------->| TASK-006  |
| schema.ts |           | utils.ts  |           | middleware |
+-----------+           +-----------+           +-----------+
```

**Rules:**

- All tasks within a level run simultaneously across workers.
- All tasks at Level N must complete before any task at Level N+1 begins.
- After each level completes, ZERG merges worker branches and runs quality gates.
- If quality gates fail, execution stops until the issues are resolved.

The design phase automatically assigns levels based on the dependency graph. Foundation tasks (types, interfaces, schemas) go in Level 1. Tasks that depend on foundation outputs go in Level 2, and so on.

---

## File Ownership

Every file in the task graph is owned by exactly one task. No two tasks create or modify the same file. This is what makes conflict-free parallel execution possible.

| File | Owner | Operation |
|------|-------|-----------|
| `src/auth/types.ts` | TASK-001 | create |
| `src/auth/schema.ts` | TASK-002 | create |
| `src/auth/service.ts` | TASK-003 | create |
| `src/db/schema/index.ts` | TASK-002 | modify |

**The ownership rules:**

1. **Create** -- The task creates a new file. Only this task may write to it.
2. **Modify** -- The task modifies an existing file. Only this task may change it during this feature.
3. **Read** -- Any task can read any file. Read access does not require ownership.

The design phase enforces exclusive ownership. If the task graph contains two tasks that modify the same file, the design phase must either merge them into one task or split the file so each task owns a distinct part.

---

## Spec as Memory

Workers are stateless. They do not share conversation history with the orchestrator or with each other. Instead, workers read spec files to understand what to build.

```
.gsd/specs/<feature>/
  requirements.md       <-- What to build (from /zerg:plan)
  design.md             <-- How to build it (from /zerg:design)
  task-graph.json       <-- Task definitions, dependencies, file ownership
  worker-assignments.json  <-- Which worker gets which tasks
```

When a worker starts, it reads the spec files, finds its assigned tasks, and executes them. If a worker crashes and restarts, it reads the same spec files and picks up where it left off. No conversation context is lost because no conversation context was needed.

**Implications:**

- Spec files must be complete and unambiguous. Workers cannot ask clarifying questions.
- The design phase is where ambiguity gets resolved. A vague design produces vague implementations.
- Workers can be restarted at any time without coordination overhead.

---

## Verification

Every task in the task graph includes a verification command -- an automated check that proves the task was completed correctly.

```json
{
  "id": "TASK-003",
  "title": "Implement authentication service",
  "verification": {
    "command": "npm test -- --testPathPattern=auth/service",
    "timeout_seconds": 120
  }
}
```

**Verification principles:**

- Commands are objective. They either pass (exit code 0) or fail (non-zero exit code).
- Workers run the verification command after finishing their work. If it fails, the task is marked as failed.
- The orchestrator also runs verification during merge to confirm results in the integrated codebase.
- There is no subjective review step. If the verification passes, the task is done.

Good verification commands test behavior, not just syntax:

| Task Type | Good Verification | Weak Verification |
|-----------|-------------------|-------------------|
| Service implementation | `pytest tests/test_auth.py -x` | `python -c "import auth"` |
| API route | `pytest tests/test_routes.py -x` | `ruff check src/routes.py` |
| Type definitions | `mypy src/types.py --strict` | `python -m py_compile src/types.py` |
| Database schema | `alembic check` | `cat src/schema.py` |

---

## The Task Ecosystem

ZERG uses Claude Code's built-in Task system as the authoritative source of truth for all task state. Tasks persist in `~/.claude/tasks/` and survive session restarts.

**How tasks flow through the system:**

```
/zerg:design creates tasks    -->  TaskCreate("[L1] Create types")
/zerg:rush claims tasks       -->  TaskUpdate(status: "in_progress")
Worker completes task         -->  TaskUpdate(status: "completed")
/zerg:status reads tasks      -->  TaskList() to show progress
/zerg:merge verifies tasks    -->  TaskList() to confirm level completion
```

All tasks use bracketed subject prefixes for discoverability:

| Prefix | Meaning |
|--------|---------|
| `[Plan]` | Planning phase task |
| `[Design]` | Design phase task |
| `[L1]`, `[L2]`, etc. | Execution task at a specific level |
| `[Init]` | Initialization task |
| `[Status]` | Status check task |

State JSON files in `.zerg/state/` serve as a supplementary cache. If the Task system and state JSON disagree, the Task system wins.

---

## Context Engineering

ZERG includes a context engineering system that reduces token usage across workers. This matters because each worker is a separate Claude Code session with its own context window.

### Command Splitting

Large command files are split into `.core.md` (essential instructions, roughly 30%) and `.details.md` (reference material, roughly 70%). Workers load only the core file unless they need the details.

### Task-Scoped Context

Each task in the task graph can include a `context` field with content scoped to that specific task:

- Security rules filtered by file extension (`.py` files get Python rules, `.js` files get JavaScript rules).
- Spec excerpts relevant to the task's description and files.
- Dependency context describing what upstream tasks produce.

Workers use task-scoped context instead of loading full spec files, saving approximately 2,000 to 5,000 tokens per task.

### Configuration

Context engineering is configured in `.zerg/config.yaml`:

```yaml
plugins:
  context_engineering:
    enabled: true
    command_splitting: true
    security_rule_filtering: true
    task_context_budget_tokens: 4000
    fallback_to_full: true
```

---

## Execution Modes

ZERG supports two modes for launching workers.

### Subprocess Mode (Default)

Workers run as local Claude Code processes. This is the simplest setup and requires no Docker installation.

```
/zerg:rush --workers=5
```

### Container Mode

Workers run inside Docker containers. This provides isolation and reproducible environments.

```
/zerg:rush --workers=5 --mode container
```

Container mode requires Docker and supports two authentication methods:

| Method | How It Works | Best For |
|--------|-------------|----------|
| OAuth | Mounts `~/.claude` into container | Claude Pro/Team accounts |
| API Key | Passes `ANTHROPIC_API_KEY` env var | API key accounts |

---

## Next Steps

- [[Installation]] -- Set up ZERG on your machine.
- [[Quick Start]] -- Run through the full workflow end to end.
- [[Your First Feature]] -- Build something real.
