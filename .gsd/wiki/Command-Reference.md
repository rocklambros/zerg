# Command Reference

Complete documentation for all 26 ZERG slash commands. Each command is available inside Claude Code sessions after running `zerg install`.

Commands can be invoked in two ways:
- **Slash command**: `/zerg:rush --workers=5` (inside Claude Code)
- **CLI**: `zerg rush --workers=5` (from the terminal)

---

## Table of Contents

- [Global Flags](#global-flags)
- [Core Workflow](#core-workflow)
  - [/zerg:brainstorm](#zergbrainstorm)
  - [/zerg:design](#zergdesign)
  - [/zerg:init](#zerginit)
  - [/zerg:plan](#zergplan)
  - [/zerg:rush](#zergrush)
- [Monitoring & Control](#monitoring--control)
  - [/zerg:cleanup](#zergcleanup)
  - [/zerg:logs](#zerglogs)
  - [/zerg:merge](#zergmerge)
  - [/zerg:retry](#zergretry)
  - [/zerg:status](#zergstatus)
  - [/zerg:stop](#zergstop)
- [Quality & Analysis](#quality--analysis)
  - [/zerg:analyze](#zerganalyze)
  - [/zerg:build](#zergbuild)
  - [/zerg:refactor](#zergrefactor)
  - [/zerg:review](#zergreview)
  - [/zerg:security](#zergsecurity)
  - [/zerg:test](#zergtest)
- [Utilities](#utilities)
  - [/zerg:create-command](#zergcreate-command)
  - [/zerg:debug](#zergdebug)
  - [/zerg:git](#zerggit)
  - [/zerg:plugins](#zergplugins)
  - [/zerg:worker](#zergworker)
- [Documentation & AI](#documentation--ai)
  - [/zerg:document](#zergdocument)
  - [/zerg:estimate](#zergestimate)
  - [/zerg:explain](#zergexplain)
  - [/zerg:index](#zergindex)
  - [/zerg:select-tool](#zergselect-tool)
- [Exit Codes](#exit-codes)

---

## Global Flags

These flags apply to all ZERG commands when invoked via the CLI (`zerg <command>`).

### Analysis Depth

Mutually exclusive flags controlling analysis depth:

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--quick` | boolean | false | Surface-level, fast execution (~1K tokens) |
| `--think` | boolean | false | Structured multi-step analysis (~4K tokens) |
| `--think-hard` | boolean | false | Deep architectural analysis (~10K tokens) |
| `--ultrathink` | boolean | false | Maximum depth, all MCP servers (~32K tokens) |

### Output & Efficiency

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--no-compact` | boolean | false | Disable compact output (compact is ON by default) |

### Behavioral Mode

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--mode` | string | auto | Override auto-detected behavioral mode (`precision`, `speed`, `exploration`, `refactor`, `debug`) |

### MCP Routing

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--mcp` | boolean | true | Enable MCP auto-routing |
| `--no-mcp` | boolean | false | Disable all MCP server recommendations |

### Improvement Loops

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--no-loop` | boolean | false | Disable improvement loops (loops are ON by default) |
| `--iterations` | integer | config | Set max loop iterations (overrides config default) |

### TDD Enforcement

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--tdd` | boolean | false | Enable TDD enforcement (red-green-refactor protocol) |

### Standard Flags

| Flag | Short | Type | Default | Description |
|------|-------|------|---------|-------------|
| `--verbose` | `-v` | boolean | false | Enable verbose output |
| `--quiet` | `-q` | boolean | false | Suppress non-essential output |
| `--version` | | boolean | false | Show version and exit |
| `--help` | | boolean | false | Show help message and exit |

---

## Core Workflow

---

### /zerg:brainstorm

Open-ended feature discovery through competitive research, Socratic questioning, and automated GitHub issue creation.

**When to use**: Before `/zerg:plan`, when you don't yet know what feature to build or want to explore the competitive landscape.

#### Usage

```bash
/zerg:brainstorm <domain-or-topic> [flags]
```

#### Flags

| Flag | Short | Type | Default | Description |
|------|-------|------|---------|-------------|
| `--rounds` | | integer | 3 | Number of Socratic discovery rounds (max: 5) |
| `--socratic` | | boolean | false | Enable single-question Socratic mode with domain question trees |
| `--skip-research` | | boolean | false | Skip competitive analysis web research phase |
| `--skip-issues` | | boolean | false | Ideate only, don't create GitHub issues |
| `--dry-run` | | boolean | false | Preview issues without creating them |
| `--resume` | | boolean | false | Resume previous session from checkpoint |
| `--help` | | boolean | false | Show usage |

#### Description

Brainstorm operates in four phases. **Phase 1: Research** performs WebSearch for competitors, market gaps, and trends (3-5 queries). **Phase 2: Socratic Discovery** conducts structured questioning with dynamic question count and saturation detection. In batch mode (default), it asks multiple questions per round. In `--socratic` mode, it asks one question at a time drawn from 6 domain question trees (Auth, API, Data Pipeline, UI/Frontend, Infrastructure, General).

**Phase 2.5-2.7** includes Trade-off Exploration (architectural decision alternatives), Design Validation (4 validation checkpoints for scope, entities, workflows, NFRs), and YAGNI Gate (filters features by MVP necessity).

**Phase 3: Issue Generation** creates GitHub issues with acceptance criteria and priority labels for features that passed the YAGNI Gate. **Phase 4: Handoff** presents ranked recommendations and suggests `/z:plan` for the top pick.

All findings are saved to `.gsd/specs/brainstorm-{timestamp}/` including `research.md`, `transcript.md`, `tradeoffs.md`, `validated-design.md`, `deferred.md`, `brainstorm.md`, and `issues.json`.

#### Examples

1. **Basic brainstorm session**: `/zerg:brainstorm user-authentication`
2. **Extended discovery with more rounds**: `/zerg:brainstorm payment-processing --rounds 5`
3. **Preview issues without creating them**: `/zerg:brainstorm api-redesign --skip-research --dry-run`
4. **Single-question Socratic mode**: `/zerg:brainstorm user-auth --socratic`
5. **Resume interrupted session**: `/zerg:brainstorm --resume`

#### Related Commands

- `/zerg:plan` — Takes brainstorm output and captures detailed requirements
- `/zerg:git --action issue` — Alternative way to create GitHub issues

#### Notes

- This command never automatically proceeds to `/zerg:plan`; the user must manually invoke it
- Requires `gh` CLI for GitHub issue creation; issues are saved locally if `gh` is unavailable
- Sessions are resumable via checkpoint files saved after each phase

---

### /zerg:design

Generate technical architecture and task graph for parallel execution.

**When to use**: After requirements are approved via `/zerg:plan`. This generates the blueprint that `/zerg:rush` executes.

#### Usage

```bash
/zerg:design [flags]
```

#### Flags

| Flag | Short | Type | Default | Description |
|------|-------|------|---------|-------------|
| `--help` | | boolean | false | Show help message |

#### Description

Design operates in six phases. **Phase 1: Architecture Design** performs component analysis, data flow mapping, interface design, and documents key decisions with rationale. **Phase 2: Implementation Plan** breaks work into phases that enable parallel execution across 5 levels: Foundation (types, schemas, config), Core (business logic, services), Integration (APIs, routes, handlers), Testing (unit and integration tests), and Quality (docs, cleanup, polish).

**Phase 2.5: Context Engineering** populates optional `context` fields in the task graph with scoped content (security rules filtered by file extension, spec excerpts, dependency context) to minimize worker token usage (~2000-5000 tokens saved per task).

**Phase 3: Task Graph Generation** creates `task-graph.json` with exclusive file ownership, verification commands, and dependency chains. **Phase 4: Generate design.md** documents the complete technical design. **Phase 4.5-4.6** registers all tasks in the Claude Code Task system with correct dependency wiring. **Phase 5: Validate Task Graph** checks for circular dependencies and file ownership conflicts.

#### Examples

1. **Generate design for current feature**: `/zerg:design`
2. **After planning a specific feature**: `/zerg:plan user-auth` (approve) then `/zerg:design`
3. **Re-run design after requirements change**: Modify `requirements.md`, then `/zerg:design`

#### Related Commands

- `/zerg:plan` — Prerequisite; captures requirements before design
- `/zerg:rush` — Executes the task graph generated by design
- `/zerg:estimate` — Projects effort and cost from the task graph

#### Notes

- Prerequisite: `.gsd/specs/{feature}/requirements.md` must exist with status APPROVED
- File ownership is exclusive: each file is created or modified by exactly ONE task per level
- The task graph uses v2.0 schema with `files.create`, `files.modify`, and `files.read` arrays

---

### /zerg:init

Initialize ZERG for a project. Operates in two modes depending on directory state.

**When to use**: At the start of any project, before any other ZERG commands.

#### Usage

```bash
zerg init [flags]
```

#### Flags

| Flag | Short | Type | Default | Description |
|------|-------|------|---------|-------------|
| `--workers` | | integer | 5 | Set default worker count |
| `--security` | | string | "" | Security level (e.g., `strict`) |
| `--no-security-rules` | | boolean | false | Skip fetching security rules from TikiTribe |
| `--with-containers` | | boolean | false | Build devcontainer image after init |
| `--help` | | boolean | false | Show help message |

#### Description

Init detects the directory state and operates in one of two modes. **Inception Mode** (empty directory) runs an interactive wizard covering requirements gathering, technology selection, project scaffolding, and git initialization. **Discovery Mode** (existing project) performs language/framework detection, infrastructure analysis, and configuration generation.

Multi-language projects are automatically detected and configured with devcontainer features. Supported languages include Python, TypeScript, Go, Rust, Java, Ruby, and C#/.NET.

Security rules are automatically fetched from [TikiTribe/claude-secure-coding-rules](https://github.com/TikiTribe/claude-secure-coding-rules) and stored in `.claude/rules/security/`. Claude Code auto-loads all files under `.claude/rules/`.

Created files include `.zerg/config.yaml`, `.devcontainer/` configuration, `.gsd/PROJECT.md`, `.gsd/INFRASTRUCTURE.md`, and `.claude/rules/security/` rules.

#### Examples

1. **New project (Inception Mode)**: `mkdir my-project && cd my-project && zerg init`
2. **Existing project (Discovery Mode)**: `cd my-existing-project && zerg init`
3. **With custom worker count and strict security**: `zerg init --workers 3 --security strict`
4. **Skip security rules**: `zerg init --no-security-rules`
5. **Build containers after init**: `zerg init --with-containers`

#### Related Commands

- `/zerg:plan` — Next step after init for new features
- `/zerg:security` — Manage security rules after init

#### Notes

- Must be run in a git repository (or init will create one in Inception Mode)
- Security rules are stack-specific; only rules matching detected languages are fetched

---

### /zerg:plan

Capture complete requirements for a feature through interactive questioning.

**When to use**: When starting a new feature. This is always the first step before `/zerg:design`.

#### Usage

```bash
/zerg:plan <feature-name> [flags]
```

#### Flags

| Flag | Short | Type | Default | Description |
|------|-------|------|---------|-------------|
| `--socratic` | `-s` | boolean | false | Use structured 3-round discovery mode |
| `--rounds` | | integer | 3 | Number of Socratic rounds (max: 5) |
| `--help` | | boolean | false | Show help message |

#### Description

Plan operates in five phases. **Phase 1: Context Gathering** reads PROJECT.md, INFRASTRUCTURE.md, explores the codebase, and searches for similar patterns. **Phase 2: Requirements Elicitation** asks clarifying questions covering problem space, functional requirements, non-functional requirements, scope boundaries, dependencies, and acceptance criteria.

When `--socratic` is used, three structured rounds occur: Round 1 (Problem Space), Round 2 (Solution Space), Round 3 (Implementation Space), each with up to 5 questions.

**Phase 3** generates `requirements.md` to `.gsd/specs/{feature}/`. **Phase 4** identifies infrastructure requirements and updates `.gsd/INFRASTRUCTURE.md` if needed. **Phase 5** presents requirements for approval with status markers: DRAFT, REVIEW, APPROVED, or REJECTED.

After approval, the command prompts for next steps but never automatically runs `/zerg:design`.

#### Examples

1. **Plan a new feature**: `/zerg:plan user-authentication`
2. **Structured Socratic mode**: `/zerg:plan user-authentication --socratic`
3. **Extended questioning**: `/zerg:plan user-authentication --socratic --rounds 5`
4. **Resume after rejection**: Modify requirements, re-run `/zerg:plan user-authentication`

#### Related Commands

- `/zerg:brainstorm` — Optional discovery before planning
- `/zerg:design` — Next step after requirements are approved

#### Notes

- Feature name is sanitized to lowercase with hyphens only
- The command never proceeds automatically to design; user must reply "APPROVED" then manually invoke `/zerg:design`
- Requirements document has explicit status markers for workflow tracking

---

### /zerg:rush

Launch parallel workers to execute the task graph.

**When to use**: After architecture is approved via `/zerg:design`. This is the main execution command.

#### Usage

```bash
/zerg:rush [flags]
```

#### Flags

| Flag | Short | Type | Default | Description |
|------|-------|------|---------|-------------|
| `--workers` | `-w` | integer | 5 | Number of parallel workers (max: 10) |
| `--feature` | `-f` | string | auto | Feature name (auto-detected from `.gsd/.current-feature`) |
| `--level` | `-l` | integer | 1 | Start from specific level |
| `--task-graph` | `-g` | string | auto | Path to task-graph.json |
| `--mode` | `-m` | string | task | Execution mode: `subprocess`, `container`, `task` |
| `--dry-run` | | boolean | false | Show execution plan without starting |
| `--resume` | | boolean | false | Continue from previous run |
| `--timeout` | | integer | 3600 | Max execution time in seconds |
| `--verbose` | `-v` | boolean | false | Enable verbose output |
| `--help` | | boolean | false | Show help message |

#### Description

Rush executes the task graph generated by `/zerg:design`. It supports three execution modes:

**Task mode** (default for slash commands): The orchestrator drives execution directly through Task tool sub-agents. Each task is launched as a parallel Task tool call with the task description, file ownership list, acceptance criteria, and verification command.

**Container mode** (`--mode container`): Workers run in Docker containers with git worktrees for full isolation. Requires Docker and a built devcontainer.

**Subprocess mode** (`--mode subprocess`): Workers run as local Python subprocesses with git worktrees.

Execution proceeds level-by-level: all tasks at Level 1 complete before any start Level 2. Failed tasks are retried once with error context. Quality gates (lint, typecheck) run after each level.

Resume (`--resume`) loads existing state from `.zerg/state/{feature}.json` and continues from the last checkpoint.

#### Examples

1. **Launch with defaults (5 workers, task mode)**: `/zerg:rush`
2. **Specify worker count**: `/zerg:rush --workers=3`
3. **Use container mode**: `/zerg:rush --mode container`
4. **Resume interrupted execution**: `/zerg:rush --resume`
5. **Preview execution plan**: `/zerg:rush --dry-run`

#### Related Commands

- `/zerg:design` — Prerequisite; generates the task graph
- `/zerg:status` — Monitor progress during execution
- `/zerg:stop` — Stop workers gracefully
- `/zerg:retry` — Retry failed tasks

#### Notes

- Prerequisite: `.gsd/specs/{feature}/task-graph.json` must exist
- Task mode is default for slash commands; container mode requires explicit `--mode container`
- For live monitoring during rush, open a separate terminal and run `zerg status --dashboard`

---

## Monitoring & Control

---

### /zerg:cleanup

Remove ZERG artifacts and free resources.

**When to use**: After a feature is complete, or to clean up a failed run.

#### Usage

```bash
zerg cleanup [flags]
```

#### Flags

| Flag | Short | Type | Default | Description |
|------|-------|------|---------|-------------|
| `--feature` | `-f` | string | "" | Feature to clean (required unless `--all`) |
| `--all` | | boolean | false | Clean all ZERG features |
| `--keep-logs` | | boolean | false | Preserve log files |
| `--keep-branches` | | boolean | false | Preserve git branches |
| `--dry-run` | | boolean | false | Show cleanup plan without executing |
| `--help` | | boolean | false | Show help message |

#### Description

Cleanup removes ZERG artifacts while preserving source code, commits, and spec files. Removed resources include worktrees (`.zerg/worktrees/`), state files (`.zerg/state/`), log files (unless `--keep-logs`), git branches (unless `--keep-branches`), and Docker containers.

Preserved resources include source code and commits on main branch, merged changes, spec files (`.gsd/specs/`), and task history in `.zerg/archive/`.

Before cleanup, the task list is archived to `.zerg/archive/{feature}/tasks-{timestamp}.json`. After cleaning artifacts, the user is prompted whether to delete task history from the Claude Code Task system.

#### Examples

1. **Clean specific feature**: `zerg cleanup --feature user-auth`
2. **Preview cleanup plan**: `zerg cleanup --all --dry-run`
3. **Keep logs for debugging**: `zerg cleanup --feature user-auth --keep-logs`
4. **Keep branches for inspection**: `zerg cleanup --feature user-auth --keep-branches`
5. **Full cleanup of all features**: `zerg cleanup --all`

#### Related Commands

- `/zerg:status` — Verify feature state before cleanup
- `/zerg:logs` — Export logs before cleanup
- `/zerg:git --action cleanup` — Alternative for branch cleanup only

#### Notes

- Always run `--dry-run` first to preview what will be cleaned
- Branches can be recovered from git reflog for 30 days after deletion
- Spec files are never deleted; they serve as documentation

---

### /zerg:logs

Stream, filter, and aggregate worker logs for debugging and monitoring.

**When to use**: To debug task failures, monitor worker activity, or export logs for analysis.

#### Usage

```bash
zerg logs [WORKER_ID] [flags]
```

#### Flags

| Flag | Short | Type | Default | Description |
|------|-------|------|---------|-------------|
| `WORKER_ID` | | integer | all | Filter to specific worker (positional argument) |
| `--feature` | `-f` | string | auto | Feature name |
| `--tail` | `-n` | integer | 100 | Number of lines to show |
| `--follow` | | boolean | false | Stream new logs continuously |
| `--level` | `-l` | string | all | Filter by level: `debug`, `info`, `warn`, `error` |
| `--json` | | boolean | false | Output raw JSON format |
| `--aggregate` | | boolean | false | Merge all worker JSONL logs by timestamp |
| `--task` | | string | "" | Filter to specific task ID |
| `--artifacts` | | string | "" | Show artifact contents for a task |
| `--phase` | | string | "" | Filter by phase: `claim`, `execute`, `verify`, `commit`, `cleanup` |
| `--event` | | string | "" | Filter by event type |
| `--since` | | string | "" | Only entries after this ISO8601 timestamp |
| `--until` | | string | "" | Only entries before this ISO8601 timestamp |
| `--search` | | string | "" | Text search in messages |
| `--help` | | boolean | false | Show help message |

#### Description

Logs provides access to worker log files in multiple formats. Workers write structured JSON lines to `.zerg/logs/workers/worker-{id}.jsonl`. Task artifacts are stored in `.zerg/logs/tasks/{TASK-ID}/` including `execution.jsonl`, `claude_output.txt`, `verification_output.txt`, and `git_diff.patch`.

Aggregation mode (`--aggregate`) merges all worker JSONL files by timestamp for a unified view. This performs read-side aggregation without writing an aggregated file to disk.

Execution phases include: `claim` (worker claiming a task), `execute` (Claude Code invocation), `verify` (running verification command), `commit` (git commit of changes), and `cleanup` (post-task cleanup).

Event types include: `task_started`, `task_completed`, `task_failed`, `verification_passed`, `verification_failed`, `artifact_captured`, `level_started`, `level_complete`, `merge_started`, `merge_complete`.

#### Examples

1. **Recent logs from all workers**: `zerg logs`
2. **Logs from specific worker**: `zerg logs 1`
3. **Follow logs in real-time**: `zerg logs --follow`
4. **Filter by error level**: `zerg logs --level error`
5. **Show task artifacts**: `zerg logs --artifacts T1.1`

#### Related Commands

- `/zerg:status` — High-level progress view
- `/zerg:debug` — Deep diagnostic investigation
- `/zerg:retry` — Retry failed tasks identified in logs

#### Notes

- Use `--aggregate` to see a unified timeline across all workers
- Artifacts are captured per-task for post-mortem analysis
- Export logs with `zerg logs --aggregate --json > logs.jsonl`

---

### /zerg:merge

Manually trigger or manage level merge operations.

**When to use**: For manual merge control, conflict resolution, or when the orchestrator is not running.

#### Usage

```bash
zerg merge [flags]
```

#### Flags

| Flag | Short | Type | Default | Description |
|------|-------|------|---------|-------------|
| `--level` | `-l` | integer | current | Merge specific level |
| `--force` | `-f` | boolean | false | Force merge despite conflicts/failures |
| `--abort` | | boolean | false | Abort in-progress merge |
| `--dry-run` | | boolean | false | Show merge plan without executing |
| `--skip-gates` | | boolean | false | Skip quality gate checks |
| `--no-rebase` | | boolean | false | Don't rebase worker branches after merge |
| `--verbose` | `-v` | boolean | false | Verbose output |
| `--help` | | boolean | false | Show help message |

#### Description

Merge performs the level merge protocol: check level completion, collect worker branches, create staging branch from base, merge each worker branch into staging, run quality gates (lint, test, typecheck), tag the merge point, and rebase worker branches onto merged result.

All tasks at the level must be complete before merge proceeds. Quality gates run after merging; if any gate fails and `--force` is not set, the merge aborts.

Conflict resolution options include manual editing, accepting theirs (`git checkout --theirs <file>`), accepting ours (`git checkout --ours <file>`), or re-running the task on the merged base (`zerg retry TASK-ID --on-base`).

#### Examples

1. **Merge current level**: `zerg merge`
2. **Merge specific level**: `zerg merge --level 2`
3. **Force merge despite conflicts**: `zerg merge --force`
4. **Preview merge plan**: `zerg merge --dry-run`
5. **Abort in-progress merge**: `zerg merge --abort`

#### Related Commands

- `/zerg:rush` — Orchestrator performs merges automatically
- `/zerg:status` — View current level and task completion
- `/zerg:retry` — Re-execute tasks after conflict resolution

#### Notes

- Normally called automatically by the orchestrator; use manually for debugging
- Quality gates are critical; use `--skip-gates` only when you know gates will pass manually
- Creates git tags at `zerg/{feature}/level-{N}-complete`

---

### /zerg:retry

Retry failed or blocked tasks.

**When to use**: After tasks fail verification, workers crash, or dependencies are missing.

#### Usage

```bash
zerg retry [TASK_IDS...] [flags]
```

#### Flags

| Flag | Short | Type | Default | Description |
|------|-------|------|---------|-------------|
| `TASK_IDS` | | string[] | [] | Specific task IDs to retry (positional) |
| `--level` | `-l` | integer | 0 | Retry all failed tasks in level |
| `--all` | `-a` | boolean | false | Retry all failed tasks |
| `--force` | `-f` | boolean | false | Bypass retry limit |
| `--timeout` | `-t` | integer | config | Override timeout for retry (seconds) |
| `--reset` | | boolean | false | Reset retry counters |
| `--dry-run` | | boolean | false | Show what would be retried |
| `--verbose` | `-v` | boolean | false | Verbose output |
| `--help` | | boolean | false | Show help message |

#### Description

Retry identifies failed tasks, analyzes failure causes, resets task state to pending, checks retry limits (default: 3 attempts), and reassigns to available workers.

Retry strategies include: single task (`zerg retry TASK-001`), level retry (`zerg retry --level 2`), full retry (`zerg retry --all`), and force retry (`zerg retry --force TASK-001`).

Common failure patterns include verification failed (check verification command, run manually), worker crashed (check logs, may be resource exhaustion), dependency not found (check if dependency task completed), and timeout (increase with `--timeout` or break task into smaller pieces).

The Task system is updated alongside state JSON: tasks are marked as pending, then in_progress when reassigned.

#### Examples

1. **Retry specific task**: `zerg retry TASK-001`
2. **Retry all failed tasks at level 2**: `zerg retry --level 2`
3. **Retry all failed tasks**: `zerg retry --all`
4. **Force retry (bypass limit)**: `zerg retry --force TASK-001`
5. **Preview what would be retried**: `zerg retry --dry-run`

#### Related Commands

- `/zerg:logs` — Investigate failure causes before retry
- `/zerg:debug` — Deep diagnostic if retry keeps failing
- `/zerg:status` — View task states

#### Notes

- Default retry limit is 3 attempts per task; use `--force` to bypass
- Always investigate root cause before retrying; blind retries waste tokens
- `--reset` clears all retry counters

---

### /zerg:status

Display real-time execution progress.

**When to use**: While `/zerg:rush` is running, or after execution to see final state.

#### Usage

```bash
/zerg:status [flags]
```

#### Flags

| Flag | Short | Type | Default | Description |
|------|-------|------|---------|-------------|
| `--feature` | `-f` | string | auto | Feature to show status for |
| `--watch` | `-w` | boolean | false | Continuous update mode |
| `--interval` | `-i` | integer | 5 | Watch refresh interval in seconds |
| `--level` | `-l` | integer | all | Filter to specific level |
| `--json` | | boolean | false | Output as JSON |
| `--dashboard` | `-d` | boolean | false | Real-time TUI dashboard (CLI only) |
| `--tasks` | | boolean | false | Show all tasks with status |
| `--workers` | | boolean | false | Detailed per-worker info |
| `--commits` | | boolean | false | Recent commits per worker branch |
| `--help` | | boolean | false | Show help message |

#### Description

Status displays progress across levels, worker states, and task completion. Data sources include the Claude Code Task system (authoritative), state JSON (supplementary), Docker (container status), and Git (commit counts per branch).

Worker state icons: 🟢 Running, 🟡 Idle, 🔵 Verifying, 🟠 Checkpoint, ⬜ Stopped, 🔴 Crashed, ⚠️ Stalled.

When worker intelligence is active, additional panels show heartbeats (per-worker heartbeat age and status), escalations (unresolved issues from workers), and progress (per-worker progress bars with current step).

The Context Budget section shows command splitting stats, per-task context population rate, and security rule filtering savings.

Inside Claude Code, status produces a text snapshot. For live monitoring, use `zerg status --dashboard` in a separate terminal.

#### Examples

1. **Show overall status**: `/zerg:status`
2. **Watch mode (auto-refresh)**: `/zerg:status --watch --interval 2`
3. **Filter to specific level**: `/zerg:status --level 3`
4. **JSON output for scripting**: `/zerg:status --json`
5. **Live TUI dashboard (CLI)**: `zerg status --dashboard`

#### Related Commands

- `/zerg:logs` — Detailed log analysis
- `/zerg:rush` — Main execution command
- `/zerg:debug` — Deep investigation if issues detected

#### Notes

- Task system is authoritative; mismatches with state JSON are flagged as warnings
- Slash command status is a snapshot; use CLI `--dashboard` for live monitoring
- Stall threshold for heartbeats is configurable (default: 120 seconds)

---

### /zerg:stop

Stop ZERG workers gracefully or forcefully.

**When to use**: To pause execution (lunch break, resource issues) or terminate a run.

#### Usage

```bash
zerg stop [flags]
```

#### Flags

| Flag | Short | Type | Default | Description |
|------|-------|------|---------|-------------|
| `--feature` | `-f` | string | auto | Feature to stop |
| `--worker` | `-w` | integer | all | Stop specific worker only |
| `--force` | | boolean | false | Force immediate termination (no checkpoint) |
| `--timeout` | | integer | 30 | Graceful shutdown timeout in seconds |
| `--help` | | boolean | false | Show help message |

#### Description

Stop provides two modes. **Graceful stop** (default) sends checkpoint signal to workers, workers commit WIP changes, state is updated with checkpoint info, and containers stop cleanly. **Force stop** (`--force`) immediately terminates containers, no WIP commits are made, and in-progress tasks may lose uncommitted work.

After graceful stop, in-progress tasks are marked PAUSED in the Task system description. After force stop, tasks are annotated with "FORCE STOPPED" and a warning about potential data loss.

Recovery is straightforward: `zerg rush --resume` continues from the checkpoint.

#### Examples

1. **Graceful stop (lunch break)**: `zerg stop`
2. **Stop specific worker**: `zerg stop --worker 2`
3. **Force immediate termination**: `zerg stop --force`
4. **Stop with extra checkpoint time**: `zerg stop --timeout 60`
5. **Force stop specific worker**: `zerg stop --worker 3 --force`

#### Related Commands

- `/zerg:rush --resume` — Resume after stop
- `/zerg:status` — Check state after stop
- `/zerg:retry` — Retry failed tasks

#### Notes

- Graceful stop preserves work; force stop may lose uncommitted changes
- WIP commits include progress percentage and files modified
- Other workers continue if only specific worker is stopped

---

## Quality & Analysis

---

### /zerg:analyze

Run static analysis, complexity metrics, and quality assessment.

**When to use**: To assess code quality before committing or as part of a review.

#### Usage

```bash
/zerg:analyze [flags]
```

#### Flags

| Flag | Short | Type | Default | Description |
|------|-------|------|---------|-------------|
| `--check` | | string | all | Check type: `lint`, `complexity`, `coverage`, `security`, `all` |
| `--format` | | string | text | Output format: `text`, `json`, `sarif` |
| `--threshold` | | string | defaults | Custom thresholds (e.g., `complexity=10,coverage=70`) |
| `--files` | | string | all | Restrict to specific files |
| `--help` | | boolean | false | Show help message |

#### Description

Analyze runs multiple check types. **Lint** performs language-specific linting (ruff for Python, eslint for JS). **Complexity** analyzes cyclomatic and cognitive complexity. **Coverage** performs test coverage analysis and reporting. **Security** runs SAST scanning (bandit, semgrep).

Output formats include text (human-readable summary), json (machine-parseable), and sarif (Static Analysis Results Interchange Format for IDE integration).

#### Examples

1. **Run all checks**: `/zerg:analyze --check all`
2. **Lint only with JSON output**: `/zerg:analyze --check lint --format json`
3. **Custom complexity threshold**: `/zerg:analyze --check complexity --threshold complexity=15`
4. **SARIF for IDE integration**: `/zerg:analyze --check all --format sarif > results.sarif`
5. **Analyze specific files**: `/zerg:analyze --files src/auth/`

#### Related Commands

- `/zerg:security` — Focused security scanning
- `/zerg:review` — Code review workflow
- `/zerg:refactor` — Apply fixes for issues found

#### Notes

- Exit code 0 if all checks pass, 1 if any check fails
- SARIF output integrates with VS Code, GitHub code scanning, etc.
- Thresholds can be customized per check type

---

### /zerg:build

Build orchestration with auto-detection and error recovery.

**When to use**: To build the project with intelligent error handling.

#### Usage

```bash
/zerg:build [flags]
```

#### Flags

| Flag | Short | Type | Default | Description |
|------|-------|------|---------|-------------|
| `--target` | | string | all | Build target |
| `--mode` | | string | dev | Build mode: `dev`, `staging`, `prod` |
| `--clean` | | boolean | false | Clean build (remove artifacts first) |
| `--watch` | | boolean | false | Watch mode (rebuild on changes) |
| `--retry` | | integer | 3 | Number of retries on failure |
| `--help` | | boolean | false | Show help message |

#### Description

Build auto-detects build systems: npm (`package.json`), cargo (`Cargo.toml`), make (`Makefile`), gradle (`build.gradle`), go (`go.mod`), python (`pyproject.toml`).

Error recovery is automatic: missing dependency triggers dependency installation, type errors suggest fixes, resource exhaustion reduces parallelism, network timeout retries with backoff.

#### Examples

1. **Build with defaults**: `/zerg:build`
2. **Production build**: `/zerg:build --mode prod`
3. **Clean build**: `/zerg:build --clean`
4. **Watch mode**: `/zerg:build --watch`
5. **Extra retries**: `/zerg:build --retry 5`

#### Related Commands

- `/zerg:test` — Run tests after build
- `/zerg:analyze` — Static analysis of built code

#### Notes

- Exit code 0 on success, 1 on failure, 2 on configuration error
- Watch mode rebuilds on file changes; Ctrl+C to stop
- Build system is auto-detected; no manual configuration needed

---

### /zerg:refactor

Automated code improvement and cleanup.

**When to use**: To clean up code quality issues systematically.

#### Usage

```bash
/zerg:refactor [flags]
```

#### Flags

| Flag | Short | Type | Default | Description |
|------|-------|------|---------|-------------|
| `--transforms` | | string | all | Comma-separated transforms: `dead-code`, `simplify`, `types`, `patterns`, `naming` |
| `--dry-run` | | boolean | false | Preview changes without applying |
| `--interactive` | | boolean | false | Approve changes one by one |
| `--help` | | boolean | false | Show help message |

#### Description

Refactor applies automated transforms. **dead-code** removes unused imports, variables, and functions. **simplify** simplifies complex expressions (`if x == True:` to `if x:`, removes redundant parentheses). **types** strengthens type annotations (adds missing hints, replaces `Any`). **patterns** applies design patterns (guard clauses, early returns). **naming** improves variable and function names.

Interactive mode (`--interactive`) presents each suggestion for individual approval.

#### Examples

1. **Dry run with specific transforms**: `/zerg:refactor --transforms dead-code,simplify --dry-run`
2. **Interactive mode**: `/zerg:refactor --interactive`
3. **Type and naming improvements**: `/zerg:refactor --transforms types,naming`
4. **All transforms**: `/zerg:refactor`
5. **Preview all changes**: `/zerg:refactor --dry-run`

#### Related Commands

- `/zerg:analyze` — Identify issues before refactoring
- `/zerg:review` — Review changes after refactoring

#### Notes

- Always use `--dry-run` first to preview changes
- Interactive mode is recommended for unfamiliar codebases
- Commits should be made after reviewing applied changes

---

### /zerg:review

Two-stage code review workflow.

**When to use**: Before creating a PR, or to process review feedback.

#### Usage

```bash
/zerg:review [flags]
```

#### Flags

| Flag | Short | Type | Default | Description |
|------|-------|------|---------|-------------|
| `--mode` | | string | full | Review mode: `prepare`, `self`, `receive`, `full` |
| `--help` | | boolean | false | Show help message |

#### Description

Review operates in four modes. **prepare** generates change summary, checks spec compliance, and creates review checklist. **self** runs a self-review checklist: code compiles, tests pass, no secrets, error handling, edge cases, readability. **receive** parses review comments, tracks addressed items, and generates response. **full** (default) runs Stage 1 (spec compliance) + Stage 2 (code quality).

#### Examples

1. **Full two-stage review**: `/zerg:review`
2. **Prepare for PR**: `/zerg:review --mode prepare`
3. **Self-review checklist**: `/zerg:review --mode self`
4. **Process review feedback**: `/zerg:review --mode receive`

#### Related Commands

- `/zerg:git --action pr` — Create PR after review
- `/zerg:analyze` — Run analysis as part of review

#### Notes

- Exit code 0 if review passes, 1 if issues found
- Self-review is quick; use before every commit
- Receive mode helps track addressed feedback systematically

---

### /zerg:security

Security review, vulnerability scanning, and secure coding rules management.

**When to use**: To scan for vulnerabilities, enforce compliance, or manage security rules.

#### Usage

```bash
# Vulnerability scanning
/zerg:security [flags]

# Security rules management (CLI)
zerg security-rules detect|list|fetch|integrate
```

#### Flags

| Flag | Short | Type | Default | Description |
|------|-------|------|---------|-------------|
| `--preset` | | string | owasp | Compliance preset: `owasp`, `pci`, `hipaa`, `soc2` |
| `--autofix` | | boolean | false | Generate auto-fix suggestions |
| `--format` | | string | text | Output format: `text`, `json`, `sarif` |
| `--help` | | boolean | false | Show help message |

#### Description

Security performs vulnerability scanning with preset compliance frameworks. **OWASP** (default) covers Top 10 2025: Broken Access Control, Cryptographic Failures, Injection, Insecure Design, Security Misconfiguration, Vulnerable Components, Authentication Failures, Data Integrity Failures, Logging Failures, SSRF. **PCI-DSS** covers payment card data security. **HIPAA** covers healthcare data security. **SOC 2** covers trust services criteria.

Capabilities include secret detection (API keys, passwords, tokens, private keys, AWS/GitHub/OpenAI credentials), dependency CVE scanning (Python, Node.js, Rust, Go), and code analysis (injection, XSS, authentication, access control patterns).

Security rules management via CLI: `detect` identifies project stack, `list` shows available rules, `fetch` downloads rules, `integrate` updates CLAUDE.md with rules summary.

#### Examples

1. **Run OWASP scan**: `/zerg:security`
2. **PCI compliance check**: `/zerg:security --preset pci`
3. **With auto-fix suggestions**: `/zerg:security --autofix`
4. **SARIF for IDE integration**: `/zerg:security --format sarif > security.sarif`
5. **Detect stack for rules**: `zerg security-rules detect`

#### Related Commands

- `/zerg:analyze --check security` — Security as part of full analysis
- `/zerg:init` — Auto-fetches security rules on project init

#### Notes

- Exit code 0 if no vulnerabilities found, 1 if vulnerabilities detected
- Rules are stored in `.claude/rules/security/` and auto-loaded by Claude Code
- Stack-specific rules are fetched from TikiTribe/claude-secure-coding-rules

---

### /zerg:test

Execute tests with coverage analysis and test generation.

**When to use**: To run the project's test suite with enhanced reporting.

#### Usage

```bash
/zerg:test [flags]
```

#### Flags

| Flag | Short | Type | Default | Description |
|------|-------|------|---------|-------------|
| `--generate` | | boolean | false | Generate test stubs for uncovered code |
| `--coverage` | | boolean | false | Report coverage |
| `--watch` | | boolean | false | Watch mode for continuous testing |
| `--parallel` | | integer | auto | Parallel test execution workers |
| `--framework` | | string | auto | Force framework: `pytest`, `jest`, `cargo`, `go` |
| `--help` | | boolean | false | Show help message |

#### Description

Test auto-detects frameworks: pytest, jest, cargo test, go test, mocha, vitest. Features include parallel execution for faster runs, watch mode for continuous testing, coverage tracking per file/function, and test stub generation for uncovered code.

#### Examples

1. **Run all tests**: `/zerg:test`
2. **Run with coverage**: `/zerg:test --coverage`
3. **Watch mode**: `/zerg:test --watch`
4. **Parallel with 8 workers**: `/zerg:test --parallel 8`
5. **Generate stubs for uncovered code**: `/zerg:test --generate`

#### Related Commands

- `/zerg:build` — Build before testing
- `/zerg:analyze --check coverage` — Coverage as part of analysis

#### Notes

- Exit code 0 if all tests pass, 1 if some fail
- Test generation creates stubs; implementation still required
- Framework is auto-detected from project files

---

## Utilities

---

### /zerg:create-command

Scaffold new ZERG slash commands with Task ecosystem integration, pressure tests, and documentation.

**When to use**: To create a new ZERG command with proper structure and testing.

#### Usage

```bash
/zerg:create-command <name> [flags]
```

#### Flags

| Flag | Short | Type | Default | Description |
|------|-------|------|---------|-------------|
| `<name>` | | string | required | Command name (lowercase, hyphens allowed) |
| `--interactive` | | boolean | false | Enable interactive wizard for prompts |
| `--help` | | boolean | false | Show help message |

#### Description

Create-command scaffolds a new ZERG command with all required components. **Quick mode** (default) generates files from templates with sensible defaults. **Interactive mode** (`--interactive`) prompts for description and flags before scaffolding.

Generated files include: command file (`zerg/data/commands/{name}.md`), pressure test (`tests/pressure/test_{name}.py`), documentation (`docs/commands/{name}.md`), and updated index in `docs/commands.md`.

Command names must start with a lowercase letter and contain only lowercase letters, numbers, and hyphens.

#### Examples

1. **Quick scaffold**: `/zerg:create-command my-command`
2. **Interactive wizard mode**: `/zerg:create-command my-command --interactive`
3. **After creating, validate**: `python -m zerg.validate_commands`

#### Related Commands

- `/zerg:document` — Generate documentation for existing code
- `/zerg:plugins` — Extend ZERG with plugins (alternative to commands)

#### Notes

- Run `python -m zerg.validate_commands` after creation to verify
- Command must have Pre-Flight, Task Tracking, and Help sections
- Pressure tests are scaffolded but need manual implementation

---

### /zerg:debug

Deep diagnostic investigation for ZERG execution issues with error intelligence, log correlation, Bayesian hypothesis testing, code-aware recovery, and environment diagnostics.

**When to use**: When workers crash, tasks fail, state is corrupt, or you can't figure out what went wrong.

#### Usage

```bash
/zerg:debug [problem description] [flags]
```

#### Flags

| Flag | Short | Type | Default | Description |
|------|-------|------|---------|-------------|
| `--feature` | `-f` | string | auto | Feature to investigate |
| `--worker` | `-w` | integer | all | Focus on specific worker |
| `--deep` | | boolean | false | Run system-level diagnostics (git, disk, docker, ports, worktrees) |
| `--fix` | | boolean | false | Generate and execute recovery plan (with confirmation) |
| `--error` | `-e` | string | "" | Specific error message to analyze |
| `--stacktrace` | `-s` | string | "" | Path to stack trace file |
| `--env` | | boolean | false | Comprehensive environment diagnostics |
| `--interactive` | `-i` | boolean | false | Interactive debugging wizard mode |
| `--report` | | string | "" | Write diagnostic markdown report to file |
| `--help` | | boolean | false | Show help message |

#### Description

Debug operates in seven phases. **Phase 1: Context Gathering** reads ZERG state, logs, task-graph, design doc, and git state. **Phase 1.5: Error Intelligence** performs multi-language error parsing, fingerprinting, chain analysis, and semantic classification.

**Phase 2: Symptom Classification** classifies into categories: WORKER_FAILURE, TASK_FAILURE, STATE_CORRUPTION, INFRASTRUCTURE, CODE_ERROR, DEPENDENCY, MERGE_CONFLICT, or UNKNOWN. **Phase 2.5: Log Correlation** performs timeline reconstruction, temporal clustering, cross-worker correlation, and error evolution tracking.

**Phase 3-4** collect category-specific evidence and test hypotheses with Bayesian probability scoring. **Phase 5** determines root cause with confidence level. **Phase 6** generates code-aware recovery plan with risk levels: [SAFE], [MODERATE], [DESTRUCTIVE]. **Phase 6.5** checks if issues require architectural changes (design escalation). **Phase 7** saves report and integrates with Task system.

Environment diagnostics (`--env`) checks Python venv, packages, Docker, system resources, and config validation.

#### Examples

1. **Auto-detect and diagnose**: `/zerg:debug`
2. **Describe the problem**: `/zerg:debug workers keep crashing`
3. **Focus on specific worker**: `/zerg:debug --worker 2`
4. **Specific error message**: `/zerg:debug --error "ModuleNotFoundError: No module named 'requests'"`
5. **Full diagnostics with recovery**: `/zerg:debug --deep --env --fix`

#### Related Commands

- `/zerg:logs` — View raw logs
- `/zerg:status` — High-level state overview
- `/zerg:retry` — Retry after fixing issues

#### Notes

- If `$ARGUMENTS` contains no flags, entire string is treated as problem description
- Recovery plan steps have risk levels; [DESTRUCTIVE] requires explicit confirmation
- Report is saved to `claudedocs/debug-<timestamp>.md` or `--report` path

---

### /zerg:git

Git operations with intelligent commits, PR creation, releases, rescue, review, bisect, cleanup, and issue management.

**When to use**: For commit, branch, merge, sync, history, finish, PR creation, releases, code review, rescue/undo operations, AI-powered bug bisection, branch cleanup, or GitHub issue creation.

#### Usage

```bash
/zerg:git --action <action> [flags]
```

#### Flags

| Flag | Short | Type | Default | Description |
|------|-------|------|---------|-------------|
| `--action` | `-a` | string | commit | Action: `commit`, `branch`, `merge`, `sync`, `history`, `finish`, `pr`, `release`, `review`, `rescue`, `bisect`, `ship`, `cleanup`, `issue` |
| `--push` | `-p` | boolean | false | Push after commit/finish |
| `--base` | `-b` | string | main | Base branch |
| `--name` | `-n` | string | "" | Branch name (for branch action) |
| `--branch` | | string | "" | Branch to merge (for merge action) |
| `--strategy` | | string | squash | Merge strategy: `merge`, `squash`, `rebase` |
| `--since` | | string | "" | Starting point for history |
| `--mode` | | string | auto | Commit mode: `auto`, `confirm`, `suggest` |
| `--cleanup` | | boolean | false | Run history cleanup (for history action) |
| `--draft` | | boolean | false | Create draft PR |
| `--reviewer` | | string | "" | PR reviewer username |
| `--focus` | | string | "" | Review focus: `security`, `performance`, `quality`, `architecture` |
| `--bump` | | string | auto | Release bump: `auto`, `major`, `minor`, `patch` |
| `--dry-run` | | boolean | false | Preview without executing |
| `--symptom` | | string | "" | Bug symptom (for bisect) |
| `--test-cmd` | | string | "" | Test command (for bisect) |
| `--good` | | string | "" | Known good ref (for bisect) |
| `--list-ops` | | boolean | false | List rescue operations |
| `--undo` | | boolean | false | Undo last operation |
| `--restore` | | string | "" | Restore snapshot tag |
| `--recover-branch` | | string | "" | Recover deleted branch |
| `--no-merge` | | boolean | false | Stop after PR creation |
| `--stale-days` | | integer | 30 | Branch age threshold for cleanup |
| `--title` | | string | "" | Issue title |
| `--label` | | string | "" | Issue label (repeatable) |
| `--assignee` | | string | "" | Issue assignee |
| `--no-docker` | | boolean | false | Skip Docker cleanup |
| `--include-stashes` | | boolean | false | Clear git stashes |
| `--limit` | | integer | 10 | Max issues to create |
| `--priority` | | string | "" | Filter by priority: `P0`, `P1`, `P2` |
| `--help` | | boolean | false | Show help message |

#### Description

Git provides 14 actions. **commit** generates intelligent conventional commit messages. **branch** creates branches. **merge** merges with conflict detection. **sync** synchronizes with remote. **history** shows commit history or runs cleanup. **finish** completes feature branch workflow.

**pr** creates pull requests with full context. **release** performs semver release with CHANGELOG update. **review** assembles pre-review context. **rescue** provides undo and recovery operations. **bisect** performs AI-powered bug bisection. **ship** runs the full delivery pipeline (commit, push, PR, merge, cleanup) in one shot. **cleanup** prunes merged and stale branches. **issue** creates GitHub issues.

Conventional commit types: feat, fix, docs, style, refactor, test, chore.

#### Examples

1. **Intelligent commit**: `/zerg:git --action commit`
2. **Commit and push**: `/zerg:git --action commit --push`
3. **Create branch**: `/zerg:git --action branch --name feature/auth`
4. **Create PR with reviewer**: `/zerg:git --action pr --reviewer octocat`
5. **AI-powered bisect**: `/zerg:git --action bisect --symptom "login returns 500" --test-cmd "pytest tests/auth" --good v1.0.0`

#### Related Commands

- `/zerg:review` — Code review before commit
- `/zerg:brainstorm` — Generate issues during ideation

#### Notes

- Ship action runs the full pipeline; use `--no-merge` for team review workflows
- Rescue undo operations work via git reflog
- Bisect requires `--symptom`, `--test-cmd`, and `--good`

---

### /zerg:plugins

Extend ZERG with custom quality gates, lifecycle hooks, and worker launchers.

**When to use**: To add custom validation, notifications, or execution environments.

#### Usage

```bash
/zerg:plugins [flags]
```

#### Flags

| Flag | Short | Type | Default | Description |
|------|-------|------|---------|-------------|
| `--help` | | boolean | false | Show help message |

#### Description

The plugin system provides three extension points. **QualityGatePlugin** runs custom validation after merges (lint, security scans, benchmarks). **LifecycleHookPlugin** reacts to events (task starts/completes, level finishes, merges) without blocking execution. **LauncherPlugin** provides custom worker execution environments (Kubernetes, SSH clusters).

Configuration methods include YAML hooks (simple shell commands), YAML gates (shell-based quality checks), and Python entry points (advanced plugins with custom logic).

YAML hooks are configured in `.zerg/config.yaml` under `plugins.hooks` with event, command, and timeout fields. Variable substitution includes `{level}`, `{feature}`, `{task_id}`, `{worker_id}`.

YAML gates are configured under `plugins.quality_gates` with name, command, required, and timeout fields.

All plugins are additive only; they cannot mutate orchestrator state. Plugin failures never crash the orchestrator.

#### Examples

1. **View plugin documentation**: `/zerg:plugins`
2. **Configure YAML hook** (in config.yaml):
   ```yaml
   plugins:
     hooks:
       - event: task_completed
         command: echo "Task completed"
         timeout: 60
   ```
3. **Configure quality gate** (in config.yaml):
   ```yaml
   plugins:
     quality_gates:
       - name: security-scan
         command: bandit -r src/
         required: false
         timeout: 300
   ```

#### Related Commands

- `/zerg:create-command` — Create commands (alternative to plugins)
- `/zerg:merge` — Quality gates run during merge

#### Notes

- Plugins are isolated; failures are logged but don't crash the orchestrator
- Available events: task_started, task_completed, level_complete, merge_complete, worker_spawned, quality_gate_run, rush_started, rush_finished
- See docs/plugins.md for Python entry point examples

---

### /zerg:worker

Internal zergling execution protocol. You do not invoke this directly.

**When to use**: Automatically invoked by the orchestrator for each worker.

#### Usage

```bash
# Invoked automatically by orchestrator
ZERG_WORKER_ID=0 ZERG_FEATURE=my-feature /zerg:worker
```

#### Flags

| Flag | Short | Type | Default | Description |
|------|-------|------|---------|-------------|
| `WORKER_ID` | | env | 0 | Set via ZERG_WORKER_ID environment variable |
| `FEATURE` | | env | unknown | Set via ZERG_FEATURE environment variable |
| `BRANCH` | | env | main | Set via ZERG_BRANCH environment variable |
| `--help` | | boolean | false | Show help message |

#### Description

Workers execute the following protocol. **Step 1: Load Context** reads requirements.md, design.md, task-graph.json, worker-assignments.json. **Step 2: Identify Tasks** from worker-assignments.json at each level. **Step 3: Execute Task Loop** processes tasks level by level, waiting for all workers at each level before proceeding.

**Step 4: Task Execution** includes claiming the task via TaskUpdate, loading task details, executing steps (if bite-sized planning is used), creating/modifying files, running verification, committing on success, and updating Task status.

Tasks may have an optional `steps` array for TDD workflow: write_test, verify_fail, implement, verify_pass, format, commit.

**Three-Tier Verification**: Tier 1 (Syntax, blocking), Tier 2 (Correctness, blocking), Tier 3 (Quality, non-blocking).

**Worker Intelligence** includes heartbeat monitoring (15-second updates), progress reporting, and escalation protocol for ambiguous failures.

**Context Management**: At 70% threshold, workers commit WIP, log handoff state, and exit cleanly (exit code 2) for restart.

#### Examples

1. **Workers are invoked by the orchestrator, not manually**
2. **Exit code 0**: All assigned tasks completed
3. **Exit code 2**: Context limit reached, needs restart
4. **Exit code 4**: Worker escalated an ambiguous failure

#### Related Commands

- `/zerg:rush` — Invokes workers
- `/zerg:status` — View worker states

#### Notes

- Workers follow design document exactly and match existing code patterns
- No TODOs, no placeholders; code must be complete and working
- Heartbeat files: `.zerg/state/heartbeat-{id}.json`

---

## Documentation & AI

---

### /zerg:document

Generate structured documentation for a single component, module, or command.

**When to use**: To document a specific file or module with the doc_engine pipeline.

#### Usage

```bash
/zerg:document <target> [flags]
```

#### Flags

| Flag | Short | Type | Default | Description |
|------|-------|------|---------|-------------|
| `<target>` | | string | required | Path to file or module to document |
| `--type` | | string | auto | Component type: `auto`, `module`, `command`, `config`, `api`, `types` |
| `--output` | | string | stdout | Output path for generated documentation |
| `--depth` | | string | standard | Depth level: `shallow`, `standard`, `deep` |
| `--update` | | boolean | false | Update existing documentation in-place |
| `--help` | | boolean | false | Show help message |

#### Description

Document runs a 7-step pipeline: Detect component type, Extract symbols from AST, Map dependencies, Generate Mermaid diagrams, Render with type-specific template, Cross-reference with glossary, Output to specified path.

**Depth levels**: `shallow` includes public classes and functions only. `standard` adds internal methods, imports, and basic diagrams. `deep` includes all methods, usage examples, and full dependency graph.

If AST parse fails, the pipeline falls back to regex-based extraction with a warning.

#### Examples

1. **Document a module**: `/zerg:document zerg/launcher.py`
2. **Deep documentation to file**: `/zerg:document zerg/doc_engine/extractor.py --depth deep --output docs/extractor.md`
3. **Update existing docs in-place**: `/zerg:document zerg/launcher.py --output docs/launcher.md --update`
4. **Force command type**: `/zerg:document zerg/data/commands/rush.md --type command`

#### Related Commands

- `/zerg:index` — Generate full project wiki
- `/zerg:explain` — Educational explanations (different focus)

#### Notes

- Auto-detection works for most files; use `--type` for ambiguous cases
- Output to stdout by default; use `--output` to write to file
- Update mode preserves manual edits outside auto-generated sections

---

### /zerg:estimate

Full-lifecycle effort estimation with PERT confidence intervals, post-execution comparison, and historical calibration.

**When to use**: Before `/zerg:rush` to project effort and cost, or after execution to compare actual vs estimated.

#### Usage

```bash
/zerg:estimate [<feature>] [flags]
```

#### Flags

| Flag | Short | Type | Default | Description |
|------|-------|------|---------|-------------|
| `<feature>` | | string | auto | Feature to estimate (from `.gsd/.current-feature`) |
| `--pre` | | boolean | auto | Force pre-execution estimation mode |
| `--post` | | boolean | auto | Force post-execution comparison mode |
| `--calibrate` | | boolean | false | Show historical accuracy and compute bias factors |
| `--workers` | | integer | config | Worker count for wall-clock projection |
| `--format` | | string | text | Output format: `text`, `json`, `md` |
| `--verbose` | | boolean | false | Show per-task breakdown |
| `--history` | | boolean | false | Show past estimates for this feature |
| `--no-calibration` | | boolean | false | Skip applying calibration bias |
| `--help` | | boolean | false | Show help message |

#### Description

Estimate operates in three modes. **Pre-execution** analyzes task graph, scores complexity, calculates PERT estimates (P50, P80, P95), projects wall-clock time with worker simulation, and estimates API cost.

**Post-execution** loads pre-estimate and actuals from Task system, computes accuracy per task/level/total, flags outliers with >50% deviation, and appends post snapshot to history.

**Calibration** scans all estimate files with pre and post snapshots, computes bias factors per task grade, calculates mean absolute error, and saves calibration for auto-apply on future estimates.

Estimates are saved to `.gsd/estimates/{feature}-estimate.json`.

#### Examples

1. **Estimate before launching**: `/zerg:estimate user-auth`
2. **Compare actual vs estimated**: `/zerg:estimate user-auth --post`
3. **Per-task breakdown**: `/zerg:estimate --verbose`
4. **Historical calibration**: `/zerg:estimate --calibrate`
5. **JSON output**: `/zerg:estimate --format json`

#### Related Commands

- `/zerg:design` — Creates task graph for estimation
- `/zerg:rush` — Execute and measure actuals

#### Notes

- Auto-detects mode based on task completion state
- Calibration improves future estimates; run periodically
- PERT uses optimistic/most-likely/pessimistic derived from base estimate and risk score

---

### /zerg:explain

Educational code explanations with four progressive depth layers, powered by doc_engine AST extractors.

**When to use**: To understand unfamiliar code at any scope, from a single function to an entire system.

#### Usage

```bash
/zerg:explain <target> [flags]
```

#### Flags

| Flag | Short | Type | Default | Description |
|------|-------|------|---------|-------------|
| `<target>` | | string | required | File, function (`file:func`), directory, or dotted module path |
| `--scope` | | string | auto | Override: `function`, `file`, `module`, `system` |
| `--save` | | boolean | false | Write to `claudedocs/explanations/{target}.md` |
| `--format` | | string | text | Output format: `text`, `md`, `json` |
| `--no-diagrams` | | boolean | false | Skip Mermaid diagram generation |
| `--help` | | boolean | false | Show help message |

#### Description

Explain generates layered explanations through four progressive depth levels. **Layer 1: Summary** covers what the code does, who calls it, and why it exists. **Layer 2: Logic Flow** provides step-by-step execution walkthrough with flowchart. **Layer 3: Implementation Details** covers data structures, algorithms, and edge cases. **Layer 4: Design Decisions** explains patterns, abstractions, trade-offs, and integration points.

Auto-scope detection: `file:func` format indicates function scope, file path indicates file scope, directory indicates module scope.

Structured data is extracted via doc_engine (SymbolExtractor, ComponentDetector, DependencyMapper, MermaidGenerator). If import fails, falls back to reading source directly.

#### Examples

1. **Explain a file**: `/zerg:explain zerg/launcher.py`
2. **Explain a specific function**: `/zerg:explain zerg/launcher.py:spawn_worker`
3. **Explain a module**: `/zerg:explain zerg/doc_engine/ --scope module`
4. **Save explanation**: `/zerg:explain zerg/launcher.py --save`
5. **Without diagrams**: `/zerg:explain zerg/launcher.py --no-diagrams`

#### Related Commands

- `/zerg:document` — Generate reference documentation (different focus)
- `/zerg:index` — Generate project wiki

#### Notes

- Target can be file path, `path:function`, directory, or dotted module path
- Saved explanations go to `claudedocs/explanations/`
- All four layers are always generated; scope controls breadth

---

### /zerg:index

Generate a complete documentation wiki for the ZERG project.

**When to use**: To create or update the full project wiki with cross-references and sidebar navigation.

#### Usage

```bash
/zerg:index [flags]
```

#### Flags

| Flag | Short | Type | Default | Description |
|------|-------|------|---------|-------------|
| `--full` | | boolean | false | Regenerate all pages from scratch (vs incremental) |
| `--push` | | boolean | false | Push generated wiki to `{repo}.wiki.git` |
| `--dry-run` | | boolean | false | Preview what would be generated without writing |
| `--output` | | string | .gsd/wiki/ | Output directory for generated pages |
| `--help` | | boolean | false | Show help message |

#### Description

Index discovers all documentable components, classifies them, extracts symbols, generates markdown pages, builds cross-references, creates architecture diagrams, and assembles a navigable wiki with sidebar.

By default operates in **incremental mode**, only regenerating pages for source files that changed since last generation. Use `--full` to regenerate everything.

Wiki structure includes Home.md, Getting-Started.md, Tutorial.md, Command-Reference/, Architecture/, Configuration/, Troubleshooting.md, Contributing.md, Glossary.md, _Sidebar.md, and _Footer.md.

The `--push` option handles git operations to push the generated wiki to the GitHub wiki repository.

#### Examples

1. **Generate full wiki**: `/zerg:index --full`
2. **Preview changes**: `/zerg:index --dry-run`
3. **Generate and push to GitHub Wiki**: `/zerg:index --full --push`
4. **Custom output directory**: `/zerg:index --output docs/wiki/`
5. **Incremental update (default)**: `/zerg:index`

#### Related Commands

- `/zerg:document` — Document single component
- `/zerg:explain` — Educational explanations

#### Notes

- Incremental mode is faster; use `--full` when structure changes
- Push requires configured wiki repository access
- Individual page failures are logged but don't stop generation

---

### /zerg:select-tool

Intelligent tool routing across MCP servers, native tools, and Task agent subtypes.

**When to use**: To determine the optimal tool combination for a given task before starting work.

#### Usage

```bash
/zerg:select-tool <task description> [flags]
```

#### Flags

| Flag | Short | Type | Default | Description |
|------|-------|------|---------|-------------|
| `<task description>` | | string | required | Free-text description of the task |
| `--domain` | | string | auto | Override: `ui`, `backend`, `infra`, `docs`, `test`, `security`, `perf` |
| `--format` | | string | text | Output format: `text`, `json`, `md` |
| `--verbose` | | boolean | false | Show per-dimension scoring breakdown |
| `--no-agents` | | boolean | false | Exclude Task agent recommendations |
| `--no-mcp` | | boolean | false | Exclude MCP server recommendations |
| `--help` | | boolean | false | Show help message |

#### Description

Select-tool evaluates tasks across five scoring axes (file_count, analysis_depth, domain, parallelism, interactivity), each scored 0.0-1.0. The composite formula combines these with weights: file (0.2), depth (0.3), domain (0.2), parallel (0.15), interactive (0.15).

**Score tiers**: 0.0-0.3 recommends native tools (Read, Edit, Grep, Glob). 0.3-0.6 recommends single MCP server or Task agent. 0.6-0.8 recommends MCP + agent combo. 0.8-1.0 recommends multi-MCP + delegation.

Tool categories include Native Tools (Read, Write, Edit, Grep, Glob, Bash), MCP Servers (Context7, Sequential, Playwright, Magic, Morphllm, Serena), and Task Agents (Explore, Plan, general-purpose, python-expert).

Domain auto-detection uses keyword matching: ui/frontend/component keywords map to `ui`, api/database/backend to `backend`, docker/deploy/ci to `infra`, etc.

#### Examples

1. **Get recommendations**: `/zerg:select-tool "refactor the authentication module across 12 files"`
2. **Force domain**: `/zerg:select-tool "optimize the query layer" --domain perf`
3. **Detailed scoring**: `/zerg:select-tool "add a responsive navbar with accessibility" --verbose`
4. **Exclude agents**: `/zerg:select-tool "search for error handling patterns" --no-agents`
5. **JSON output**: `/zerg:select-tool "document the launcher module" --format json`

#### Related Commands

- `/zerg:plugins` — MCP server configuration
- `/zerg:explain` — Understanding code before tool selection

#### Notes

- Task description is required; flags are optional
- Domain auto-detection works for most cases; override with `--domain` if needed
- Verbose output shows per-axis scores for debugging recommendations

---

## Exit Codes

All ZERG commands follow a consistent exit code convention:

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Failure (check output for details) |
| 2 | Configuration error or special state (checkpoint for workers) |
| 4 | Worker escalated an ambiguous failure (escalation protocol) |
