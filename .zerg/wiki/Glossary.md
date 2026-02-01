# Glossary

Key terms and concepts used throughout the ZERG documentation. Terms are listed alphabetically.

---

## B

### Brainstorm

An optional discovery phase before planning. The `/zerg:brainstorm` command performs competitive research via web search, conducts structured Socratic questioning, and creates prioritized GitHub issues. Feeds into `/zerg:plan` when a specific feature is selected.

See: [[Command-brainstorm]]

---

## C

### Claude Code Task System

The built-in task management API provided by Claude Code (`TaskCreate`, `TaskUpdate`, `TaskList`, `TaskGet`). ZERG uses this as the **authoritative source of truth** for all task state. Tasks persist in `~/.claude/tasks/` and survive session restarts. When the Task system and state JSON files disagree, the Task system wins.

See: [[Getting Started#the-task-ecosystem]], [[Architecture-State-Management]]

### Command Splitting

A context engineering optimization that divides large command files (over 300 lines) into a `.core.md` file containing essential instructions (~30%) and a `.details.md` file containing reference material (~70%). Workers load only the core file by default.

See: [[Context Engineering#subsystem-1-command-splitting]]

### Container Mode

An execution mode where workers run inside Docker containers instead of local subprocesses. Provides filesystem isolation and reproducible environments. Activated with the `--mode container` flag on `/zerg:rush`. Supports OAuth and API key authentication.

See: [[Tutorial-Container-Mode]], [[Configuration#workers]]

### Context Engineering

A system of optimizations that reduces token usage across workers by scoping context to each task. Includes three subsystems: command splitting, task-scoped context, and security rule filtering. Configured under `plugins.context_engineering` in `.zerg/config.yaml`.

See: [[Context Engineering]], [[Context Engineering Internals]]

---

## D

### Dependency Graph

The directed acyclic graph (DAG) of task dependencies defined in `task-graph.json`. Each task lists the tasks it depends on. The graph determines which tasks can run in parallel (same level) and which must wait for prior work to complete.

See: [[Architecture-Dependency-Graph]]

### Design Phase

The second stage of the ZERG workflow. Reads approved requirements, generates a technical architecture (`design.md`), and produces a task graph (`task-graph.json`) with exclusive file ownership. Invoked with `/zerg:design`.

See: [[Command-design]], [[Quick Start#step-3-design]]

---

## F

### Feature

A named unit of work that flows through the full ZERG pipeline (plan, design, rush, merge). Each feature has its own spec directory (`.gsd/specs/<feature>/`), task graph, state file, and worker branches.

### File Ownership

The mechanism that prevents merge conflicts during parallel execution. Every file in the task graph is assigned to exactly one task per level. A task may **create** a new file or **modify** an existing file. Any task can **read** any file without ownership. The design phase enforces exclusive ownership.

See: [[Getting Started#file-ownership]]

---

## L

### Level

A group of tasks that share the same position in the dependency graph and can execute in parallel. Level 1 tasks have no dependencies. Level 2 tasks depend only on Level 1 tasks, and so on. All tasks at level N must complete before any task at level N+1 begins.

See: [[Getting Started#levels]], [[Architecture-Execution-Flow]]

---

## M

### Merge

The process that occurs between levels. After all tasks at a level complete, the orchestrator collects worker branches, merges them into a staging branch, and runs quality gates. If gates pass, the next level begins. Triggered automatically by the orchestrator or manually with `/zerg:merge`.

See: [[Command-merge]], [[Quick Start#step-6-merge]]

---

## O

### Orchestrator

The central coordination component that manages the full execution lifecycle. The orchestrator reads the task graph, assigns tasks to workers, monitors progress, triggers merges between levels, runs quality gates, and handles failures. It runs in the primary Claude Code session that invoked `/zerg:rush`.

See: [[Architecture-Overview]], [[Architecture-Execution-Flow]]

---

## P

### Plan Phase

The first stage of the ZERG workflow. ZERG asks clarifying questions about the requested feature, then generates a `requirements.md` file from the answers. Requires explicit user approval before proceeding. Invoked with `/zerg:plan <feature>`.

See: [[Command-plan]], [[Quick Start#step-2-plan]]

---

## Q

### Quality Gate

A validation command that runs after each level merge to verify code quality. Gates are defined in `.zerg/config.yaml` under `quality_gates`. Each gate produces one of five results: `PASS`, `FAIL`, `SKIP`, `TIMEOUT`, or `ERROR`. Required gates that fail block the merge; non-required gates log warnings only.

Common gates include lint checks, type checking, unit tests, coverage thresholds, and security scans.

See: [[Configuration#quality_gates]], [[Plugin System]]

---

## R

### Rush

The third stage of the ZERG workflow and the primary execution phase. Multiple Claude Code workers execute tasks in parallel, organized by dependency levels. Invoked with `/zerg:rush --workers=N`. The rush occupies the current Claude Code session; use a separate terminal for monitoring.

See: [[Command-rush]], [[Quick Start#step-4-rush]]

---

## S

### Spec (Specification)

The collection of files that describe what to build and how. Stored in `.gsd/specs/<feature>/` and includes `requirements.md`, `design.md`, `task-graph.json`, and `worker-assignments.json`. Workers read spec files instead of conversation history -- this is the "spec as memory" pattern.

See: [[Getting Started#spec-as-memory]]

### Spec as Memory

The design principle that workers are stateless and derive all instructions from spec files rather than shared conversation context. A worker that crashes and restarts reads the same spec files and resumes from where it left off. This eliminates coordination overhead and makes workers restartable.

See: [[Getting Started#spec-as-memory]]

### State JSON

Supplementary state files stored in `.zerg/state/<feature>.json`. These cache task status, worker assignments, and progress data. State JSON is **not** the source of truth -- the Claude Code Task system is. If the two disagree, the Task system wins.

See: [[Architecture-State-Management]]

### Subprocess Mode

The default execution mode where workers run as local Claude Code processes on the host machine. Requires no Docker installation. Activated by default or explicitly with `--mode subprocess`.

See: [[Configuration#workers]]

---

## T

### Task

The atomic unit of work in ZERG. Each task has a unique ID, title, description, list of owned files, dependencies on other tasks, a level assignment, and a verification command. Tasks are defined in `task-graph.json` and tracked through the Claude Code Task system.

### Task Graph

The complete set of tasks for a feature, stored in `task-graph.json`. Produced by the design phase. Defines all tasks, their dependencies, file ownership, level assignments, and verification commands. The task graph is the blueprint that the orchestrator and workers follow during execution.

See: [[Architecture-Overview#task-graph]]

### Task-Scoped Context

A context engineering optimization that provides each worker with only the spec content relevant to its assigned task, rather than the full feature spec. The plugin extracts keywords from the task definition, matches relevant paragraphs from the spec, and delivers a focused context of 500-1,500 tokens instead of the full spec.

See: [[Context Engineering#subsystem-2-task-scoped-context]]

---

## V

### Verification

An automated check that proves a task was completed correctly. Every task in the task graph includes a verification command (a shell command that exits 0 on success, non-zero on failure). Workers run verification after finishing their work. The orchestrator also runs verification during merge.

See: [[Getting Started#verification]]

---

## W

### Worker

A Claude Code instance that executes assigned tasks. Each worker runs in its own git worktree on a dedicated branch. Workers are stateless -- they read spec files for instructions and communicate status through the Claude Code Task system and state JSON files. Multiple workers execute in parallel within a level.

See: [[Command-worker]], [[Architecture-Overview#worker-isolation]]

### Worktree

A git worktree created for each worker to provide filesystem isolation. Each worker operates on a separate branch in a separate directory, preventing file system conflicts between parallel workers. Worktrees are created by the launcher and cleaned up by `/zerg:cleanup`.

See: [[Architecture-Overview#worker-isolation]]

---

## Z

### Zergling

Informal name for a ZERG worker, drawn from the StarCraft game terminology. Used interchangeably with "worker" throughout the project.

### ZERG

The overall system. A parallel Claude Code execution framework that coordinates multiple worker instances to implement features concurrently. The name references the "Zerg rush" strategy from StarCraft -- overwhelming a problem with many coordinated units.
