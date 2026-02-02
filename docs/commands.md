# ZERG Command Reference

Complete documentation for all 26 ZERG slash commands. Each command is available inside Claude Code sessions after running `zerg install`.

Commands can be invoked in two ways:
- **Slash command**: `/zerg:rush --workers=5` (inside Claude Code)
- **CLI**: `zerg rush --workers=5` (from the terminal)

---

## Table of Contents

- **Core Workflow**
  - [/zerg:init](#zerginit) — Initialize project
  - [/zerg:brainstorm](#zergbrainstorm) — Feature discovery and ideation
  - [/zerg:plan](#zergplan) — Capture requirements
  - [/zerg:design](#zergdesign) — Design architecture
  - [/zerg:rush](#zergrush) — Launch parallel execution
- **Monitoring & Control**
  - [/zerg:status](#zergstatus) — Progress dashboard
  - [/zerg:logs](#zerglogs) — View worker logs
  - [/zerg:stop](#zergstop) — Stop workers
  - [/zerg:retry](#zergretry) — Retry failed tasks
  - [/zerg:merge](#zergmerge) — Manual merge control
  - [/zerg:cleanup](#zergcleanup) — Remove artifacts
- **Quality & Analysis**
  - [/zerg:build](#zergbuild) — Build orchestration
  - [/zerg:test](#zergtest) — Test execution
  - [/zerg:analyze](#zerganalyze) — Static analysis
  - [/zerg:review](#zergreview) — Code review
  - [/zerg:security](#zergsecurity) — Security scanning
  - [/zerg:refactor](#zergrefactor) — Automated refactoring
- **Utilities**
  - [/zerg:git](#zerggit) — Git operations
  - [/zerg:debug](#zergdebug) — Deep diagnostics
  - [/zerg:worker](#zergworker) — Worker execution protocol
  - [/zerg:plugins](#zergplugins) — Plugin management
- **Documentation & AI**
  - [/zerg:document](#zergdocument) — Component documentation
  - [/zerg:index](#zergindex) — Project wiki generation
  - [/zerg:estimate](#zergestimate) — Effort estimation
  - [/zerg:explain](#zergexplain) — Educational explanations
  - [/zerg:select-tool](#zergselect-tool) — Intelligent tool routing

---

## Core Workflow

---

### /zerg:init

Initialize ZERG for a project. Operates in two modes depending on directory state.

**When to use**: At the start of any project, before any other ZERG commands.

#### Modes

| Mode | Trigger | What It Does |
|------|---------|-------------|
| **Inception** | Empty directory | Interactive wizard: requirements, tech selection, project scaffolding, git init |
| **Discovery** | Existing code | Auto-detect languages/frameworks, generate `.zerg/` and `.devcontainer/` configs |

#### Usage

```bash
# Empty directory → Inception Mode wizard
mkdir my-project && cd my-project
zerg init

# Existing project → Discovery Mode
cd my-existing-project
zerg init

# With options
zerg init --workers 3 --security strict
zerg init --no-security-rules
zerg init --with-containers
```

#### Flags

| Flag | Description |
|------|-------------|
| `--workers N` | Set default worker count |
| `--security strict` | Enable strict security rules |
| `--no-security-rules` | Skip fetching security rules from TikiTribe |
| `--with-containers` | Build devcontainer image after init |

#### What Gets Created

| File/Directory | Purpose |
|---------------|---------|
| `.zerg/config.yaml` | ZERG configuration |
| `.devcontainer/devcontainer.json` | Container configuration |
| `.devcontainer/Dockerfile` | Worker container image |
| `.devcontainer/post-create.sh` | Post-create setup script |
| `.devcontainer/post-start.sh` | Post-start setup script |
| `.devcontainer/mcp-servers/` | MCP server configuration |
| `.gsd/PROJECT.md` | Project overview |
| `.gsd/INFRASTRUCTURE.md` | Infrastructure requirements |
| `.claude/rules/security/` | Stack-specific security rules (auto-loaded by Claude Code) |
| `CLAUDE.md` (updated) | Security rules summary |

#### Multi-Language Detection

ZERG automatically detects all languages in your project:

| Language | Detection | Default Framework |
|----------|-----------|-------------------|
| Python | `pyproject.toml`, `requirements.txt`, `setup.py` | FastAPI / Typer |
| TypeScript | `package.json` with TS deps | Fastify / Commander |
| Go | `go.mod` | Gin / Cobra |
| Rust | `Cargo.toml` | Axum / Clap |
| Java | `pom.xml`, `build.gradle` | — |
| Ruby | `Gemfile` | — |
| C#/.NET | `*.csproj` | — |

#### Security Rules Integration

ZERG automatically fetches stack-specific security rules from [TikiTribe/claude-secure-coding-rules](https://github.com/TikiTribe/claude-secure-coding-rules) and stores them in `.claude/rules/security/`. Claude Code auto-loads all files under `.claude/rules/`, so no `@-imports` are needed. An informational summary is added to `CLAUDE.md`.

---

### /zerg:brainstorm

Open-ended feature discovery through competitive research, Socratic questioning, and automated GitHub issue creation. Supports both batch questioning (multiple questions per round) and single-question Socratic mode with domain-specific question trees.

**When to use**: Before `/zerg:plan`, when you don't yet know what feature to build or want to explore the competitive landscape. Brainstorm produces prioritized GitHub issues; plan takes one of those issues and captures detailed requirements.

#### Usage

```bash
/zerg:brainstorm mobile-app-features
/zerg:brainstorm user-auth --socratic
/zerg:brainstorm --skip-research
/zerg:brainstorm --rounds 5 --dry-run
```

#### Flags

| Flag | Short | Description | Default |
|------|-------|-------------|---------|
| `--rounds N` | | Number of Socratic discovery rounds | `3` |
| `--socratic` | | Enable single-question Socratic mode with domain question trees | off |
| `--skip-research` | | Skip competitive analysis web research | off |
| `--skip-issues` | | Ideate only, don't create GitHub issues | off |
| `--dry-run` | | Preview issues without creating them | off |
| `--resume` | | Resume previous brainstorm session | off |

#### Workflow

1. **Research** — WebSearch for competitors, market gaps, trends (3-5 queries)
2. **Socratic Discovery** — Structured questioning with dynamic question count and saturation detection. In batch mode, asks multiple questions per round. In `--socratic` mode, asks one question at a time drawn from 6 domain question trees (Auth, API, Data Pipeline, UI/Frontend, Infrastructure, General).
3. **Trade-off Exploration** — Surfaces key trade-offs (build vs buy, consistency vs availability, etc.) and asks the user to state preferences. Runs in both batch and socratic modes.
4. **Design Validation** — Validates proposed architecture against stated requirements and constraints, flagging contradictions or gaps. Runs in both batch and socratic modes.
5. **YAGNI Gate** — Reviews all captured requirements and challenges each one: "Do you need this for MVP?" Prunes speculative features before handoff. Runs in both batch and socratic modes.
6. **Issue Generation** — Creates GitHub issues with acceptance criteria and priority labels
7. **Handoff** — Presents ranked recommendations and suggests `/z:plan` for the top pick

#### What Gets Created

```
.gsd/specs/brainstorm-{timestamp}/
  research.md         # Competitive analysis findings
  transcript.md       # Full Q&A transcript from discovery
  tradeoffs.md        # Trade-off decisions and reasoning
  validated-design.md # User-confirmed scope from Design Validation
  deferred.md         # Features deferred by YAGNI Gate
  brainstorm.md       # Session summary with recommendations
  issues.json         # Machine-readable issue manifest
```

#### Context Management

Uses command splitting (`.core.md` + `.details.md`), scoped context loading, and session resumability.

---

### /zerg:plan

Capture complete requirements for a feature through interactive questioning.

**When to use**: When starting a new feature. This is always the first step before `/zerg:design`.

#### Usage

```bash
# Plan a feature (interactive mode)
/zerg:plan user-authentication

# Use Socratic discovery mode (structured 3-round questioning)
/zerg:plan user-authentication --socratic

# More rounds of questioning
/zerg:plan user-authentication --socratic --rounds 5
```

#### Flags

| Flag | Short | Description |
|------|-------|-------------|
| `--socratic` | `-s` | Structured 3-round discovery mode |
| `--rounds N` | — | Number of Socratic rounds (default: 3, max: 5) |

#### Socratic Mode

When `--socratic` is used, the plan follows three structured rounds:

1. **Round 1: Problem Space** — What problem? Who are the users? Why now?
2. **Round 2: Solution Space** — What's the ideal? What constraints? What's out of scope?
3. **Round 3: Implementation Space** — MVP version? Technical risks? How to verify?

Each round asks up to 5 questions and waits for responses before proceeding.

#### What Gets Created

| File | Purpose |
|------|---------|
| `.gsd/specs/{feature}/requirements.md` | Structured requirements document |
| `.gsd/.current-feature` | Active feature marker |

#### Status Markers

The requirements document has a status field:

| Status | Meaning |
|--------|---------|
| `DRAFT` | Still gathering requirements |
| `REVIEW` | Requirements complete, awaiting approval |
| `APPROVED` | Ready for `/zerg:design` |
| `REJECTED` | Needs revision |

#### Completion

After generating requirements, ZERG presents them for review. Reply with:
- **"APPROVED"** — Proceed to design phase
- **"REJECTED"** — Describe what needs to change

---

### /zerg:design

Generate technical architecture and task graph for parallel execution.

**When to use**: After requirements are approved via `/zerg:plan`. This generates the blueprint that `/zerg:rush` executes.

**Prerequisite**: `.gsd/specs/{feature}/requirements.md` must exist with status APPROVED.

#### What It Does

1. **Architecture Design** — Component analysis, data flow, interface design, key decisions
2. **Implementation Plan** — Break work into phases that enable parallel execution
3. **Task Graph Generation** — Atomic tasks with exclusive file ownership and verification commands
4. **Claude Task Registration** — Creates tracking tasks in the Claude Code Task system
5. **Validation** — Checks for circular dependencies, file ownership conflicts
6. **User Approval** — Presents design for review

#### What Gets Created

| File | Purpose |
|------|---------|
| `.gsd/specs/{feature}/design.md` | Technical architecture document |
| `.gsd/specs/{feature}/task-graph.json` | Task definitions in v2.0 schema |

#### Task Graph Schema (v2.0)

Each task in the graph includes:

```json
{
  "id": "FEATURE-L1-001",
  "title": "Create user types",
  "description": "Define TypeScript interfaces for user domain",
  "phase": "foundation",
  "level": 1,
  "dependencies": [],
  "files": {
    "create": ["src/types/user.ts"],
    "modify": [],
    "read": ["src/types/common.ts"]
  },
  "acceptance_criteria": ["Types compile without errors"],
  "verification": {
    "command": "npx tsc --noEmit src/types/user.ts",
    "timeout_seconds": 60
  }
}
```

#### Level Structure

| Level | Name | Characteristics |
|-------|------|-----------------|
| 1 | Foundation | No dependencies — types, schemas, config |
| 2 | Core | Depends on L1 — business logic, services |
| 3 | Integration | Depends on L2 — APIs, routes, handlers |
| 4 | Testing | Depends on L3 — unit and integration tests |
| 5 | Quality | Depends on L4 — docs, cleanup, polish |

#### File Ownership Rules

1. **Exclusive Create**: Each file created by exactly ONE task
2. **Exclusive Modify**: Each file modified by ONE task per level
3. **Read is Shared**: Multiple tasks can read the same file
4. **Level Boundaries**: A file modified in level N cannot be modified again until level N+1

---

### /zerg:rush

Launch parallel zerglings to execute the task graph.

**When to use**: After architecture is approved via `/zerg:design`. This is the main execution command.

**Prerequisite**: `.gsd/specs/{feature}/task-graph.json` must exist.

#### Usage

```bash
# Launch with default settings (5 workers, auto mode)
/zerg:rush

# Specify worker count
/zerg:rush --workers=3

# Choose execution mode
/zerg:rush --mode container
/zerg:rush --mode subprocess
/zerg:rush --mode task

# Resume interrupted execution
/zerg:rush --resume

# Preview execution plan
/zerg:rush --dry-run

# Start from specific level
/zerg:rush --resume --level 3

# Set timeout
/zerg:rush --timeout 7200
```

#### Flags

| Flag | Short | Description | Default |
|------|-------|-------------|---------|
| `--workers N` | `-w` | Number of parallel workers | 5 |
| `--feature TEXT` | `-f` | Feature name (auto-detected) | Current feature |
| `--level N` | `-l` | Start from specific level | 1 |
| `--task-graph PATH` | `-g` | Path to task-graph.json | Auto-detected |
| `--mode TEXT` | `-m` | Execution mode: `subprocess`, `container`, `task`, `auto` | `auto` |
| `--dry-run` | — | Show execution plan without starting | — |
| `--resume` | — | Continue from previous run | — |
| `--timeout N` | — | Max execution time in seconds | 3600 |
| `--verbose` | `-v` | Enable verbose output | — |

#### Execution Modes

| Mode | How Workers Run | Isolation | Requirements |
|------|----------------|-----------|--------------|
| `subprocess` | Local Python subprocesses | Git worktrees | Python 3.12+ |
| `container` | Docker containers with worktrees | Full container isolation | Docker, built devcontainer |
| `task` | Claude Code Task sub-agents | Shared workspace, file ownership | Inside Claude Code session |
| `auto` | Auto-detect best mode | — | — |

**Auto-detection logic**:
1. If `--mode` is explicitly set → use that mode
2. If `.devcontainer/devcontainer.json` exists AND Docker is available → `container`
3. If running inside a Claude Code slash command → `task`
4. Otherwise → `subprocess`

#### How Task Mode Works

When running as a slash command (`/zerg:rush`), the orchestrator (Claude Code itself) drives execution through Task tool sub-agents:

1. Collect all tasks at the current level
2. Launch tasks as parallel Task tool calls (one per task)
3. Wait for all to complete
4. Handle failures (retry once per failed task)
5. Run quality gates on the workspace
6. Proceed to next level

Each sub-agent receives a prompt with the task description, file ownership list, acceptance criteria, verification command, and design context.

#### Resume

Resume picks up where you left off:
1. Loads existing state from `.zerg/state/{feature}.json`
2. Identifies incomplete and failed tasks
3. Restores worker assignments
4. Continues from the last checkpoint

---

## Monitoring & Control

---

### /zerg:status

Display real-time execution progress.

**When to use**: While `/zerg:rush` is running, or after execution to see final state.

> **Note**: `/zerg:status` inside Claude Code produces a text snapshot. For live monitoring
> while `/zerg:rush` is running, open a separate terminal: `zerg status --dashboard`

#### Usage

```bash
# Show overall status
/zerg:status

# Watch mode (auto-refresh)
/zerg:status --watch
/zerg:status --watch --interval 2

# Filter to specific level
/zerg:status --level 3

# JSON output for scripting
/zerg:status --json

# Live TUI dashboard (CLI, separate terminal)
zerg status --dashboard
zerg status --dashboard --interval 2
```

#### Flags

| Flag | Short | Description | Default |
|------|-------|-------------|---------|
| `--feature TEXT` | `-f` | Feature to show status for | Auto-detected |
| `--watch` | `-w` | Continuous update mode | Off |
| `--interval N` | — | Watch refresh interval in seconds | 5 |
| `--level N` | `-l` | Filter to specific level | All |
| `--json` | — | Output as JSON | Off |
| `--dashboard` | `-d` | Real-time TUI dashboard (CLI only, requires terminal) | Off |

#### Detailed Views

| View | Flag | Shows |
|------|------|-------|
| Default | (none) | Progress bar, worker status, recent activity, blocked tasks |
| Tasks | `--tasks` | All tasks with status, level, and worker assignment |
| Workers | `--workers` | Detailed per-worker info (container, port, branch, current task) |
| Commits | `--commits` | Recent commits per worker branch |

#### Data Sources

Status pulls from multiple sources (Task system is authoritative):
- **Claude Code Tasks** — Primary source for task status
- **State JSON** — Supplementary worker details
- **Docker** — Container status
- **Git** — Commit counts per branch

Status mismatches between Task system and state JSON are flagged with warnings.

#### Worker State Icons

| Icon | Status | Meaning |
|------|--------|---------|
| 🟢 | Running | Actively executing a task |
| 🟡 | Idle | Waiting for dependencies |
| 🔵 | Verifying | Running verification command |
| 🟠 | Checkpoint | Saving context for restart |
| ⬜ | Stopped | Gracefully stopped |
| 🔴 | Crashed | Exited unexpectedly |

---

### /zerg:logs

Stream, filter, and aggregate worker logs for debugging and monitoring.

**When to use**: To debug task failures, monitor worker activity, or export logs for analysis.

#### Usage

```bash
# Recent logs from all workers
zerg logs

# Logs from specific worker
zerg logs 1

# Follow in real-time
zerg logs --follow

# Filter by level
zerg logs --level error

# Aggregate structured JSONL across all workers
zerg logs --aggregate

# Filter to specific task
zerg logs --task T1.1

# Show task artifacts (Claude output, verification, git diff)
zerg logs --artifacts T1.1

# Filter by execution phase and event
zerg logs --aggregate --phase verify --event verification_failed

# Time range filtering
zerg logs --aggregate --since 2026-01-28T10:00:00Z --until 2026-01-28T12:00:00Z

# Text search
zerg logs --aggregate --search "ImportError"

# Export for analysis
zerg logs --aggregate --json > logs.jsonl
```

#### Flags

| Flag | Short | Description | Default |
|------|-------|-------------|---------|
| `WORKER_ID` | — | Filter to specific worker (positional) | All workers |
| `--feature TEXT` | `-f` | Feature name | Auto-detected |
| `--tail N` | `-n` | Number of lines to show | 100 |
| `--follow` | — | Stream new logs continuously | Off |
| `--level LEVEL` | `-l` | Filter by level: `debug`, `info`, `warn`, `error` | All |
| `--json` | — | Output raw JSON format | Off |
| `--aggregate` | — | Merge all worker JSONL logs by timestamp | Off |
| `--task TEXT` | — | Filter to specific task ID | — |
| `--artifacts TEXT` | — | Show artifact contents for a task | — |
| `--phase TEXT` | — | Filter by phase: `claim`, `execute`, `verify`, `commit`, `cleanup` | — |
| `--event TEXT` | — | Filter by event type | — |
| `--since TEXT` | — | Only entries after this ISO8601 timestamp | — |
| `--until TEXT` | — | Only entries before this ISO8601 timestamp | — |
| `--search TEXT` | — | Text search in messages | — |

#### Execution Phases

| Phase | Description |
|-------|-------------|
| `claim` | Worker claiming a task |
| `execute` | Claude Code invocation |
| `verify` | Running verification command |
| `commit` | Git commit of changes |
| `cleanup` | Post-task cleanup |

#### Event Types

| Event | Description |
|-------|-------------|
| `task_started` | Task execution began |
| `task_completed` | Task finished successfully |
| `task_failed` | Task failed |
| `verification_passed` | Verification command succeeded |
| `verification_failed` | Verification command failed |
| `artifact_captured` | Artifact file written |
| `level_started` | Orchestrator began a level |
| `level_complete` | All tasks in level finished |
| `merge_started` | Branch merge began |
| `merge_complete` | Branch merge finished |

#### Log Locations

| Type | Path | Format |
|------|------|--------|
| Worker logs | `.zerg/logs/workers/worker-{id}.jsonl` | Structured JSONL |
| Task execution | `.zerg/logs/tasks/{TASK-ID}/execution.jsonl` | Structured JSONL |
| Claude output | `.zerg/logs/tasks/{TASK-ID}/claude_output.txt` | Plain text |
| Verification | `.zerg/logs/tasks/{TASK-ID}/verification_output.txt` | Plain text |
| Git diff | `.zerg/logs/tasks/{TASK-ID}/git_diff.patch` | Patch format |

---

### /zerg:stop

Stop ZERG workers gracefully or forcefully.

**When to use**: To pause execution (lunch break, resource issues) or terminate a run.

#### Usage

```bash
# Graceful stop (workers checkpoint)
zerg stop

# Stop specific worker
zerg stop --worker 2

# Force immediate termination
zerg stop --force

# Stop with extra time for checkpoint
zerg stop --timeout 60
```

#### Flags

| Flag | Short | Description | Default |
|------|-------|-------------|---------|
| `--feature TEXT` | `-f` | Feature to stop | Auto-detected |
| `--worker N` | `-w` | Stop specific worker only | All |
| `--force` | — | Force immediate termination (no checkpoint) | Off |
| `--timeout N` | — | Graceful shutdown timeout in seconds | 30 |

#### Graceful vs Force

| Behavior | Graceful (default) | Force (`--force`) |
|----------|-------------------|-------------------|
| WIP commits | Workers save progress | No commits made |
| Task state | Marked PAUSED | Marked FAILED |
| Containers | Clean shutdown | Immediately killed |
| Worktrees | Preserved | Preserved |
| State file | Updated | May be stale |
| Uncommitted work | Committed as WIP | Lost |

#### Recovery After Stop

```bash
# Resume from checkpoint
zerg rush --resume

# Resume with different worker count
zerg rush --resume --workers 3
```

---

### /zerg:retry

Retry failed or blocked tasks.

**When to use**: After tasks fail verification, workers crash, or dependencies are missing.

#### Usage

```bash
# Retry all failed tasks
zerg retry

# Retry specific task
zerg retry TASK-001

# Retry all failed tasks at a level
zerg retry --level 2

# Force retry (bypass retry limit)
zerg retry --force TASK-001

# Preview without executing
zerg retry --dry-run

# Reset retry counters
zerg retry --reset
```

#### Flags

| Flag | Short | Description | Default |
|------|-------|-------------|---------|
| `TASK_IDS` | — | Specific task IDs to retry (positional) | — |
| `--level N` | `-l` | Retry all failed tasks in level | — |
| `--all` | `-a` | Retry all failed tasks | — |
| `--force` | `-f` | Bypass retry limit | Off |
| `--timeout N` | `-t` | Override timeout for retry (seconds) | Config default |
| `--reset` | — | Reset retry counters | Off |
| `--dry-run` | — | Show what would be retried | Off |
| `--verbose` | `-v` | Verbose output | Off |

#### Retry Strategies

| Strategy | Command | Use Case |
|----------|---------|----------|
| Single task | `zerg retry TASK-001` | Known failing task |
| Level retry | `zerg retry --level 2` | Systemic issue at a level |
| Full retry | `zerg retry --all` | After config change |
| Force retry | `zerg retry --force TASK-001` | Fixed underlying issue |

---

### /zerg:merge

Manually trigger or manage level merge operations.

**When to use**: For manual merge control, conflict resolution, or when the orchestrator is not running.

#### Usage

```bash
# Merge current level
zerg merge

# Merge specific level
zerg merge --level 2

# Force merge despite conflicts
zerg merge --force

# Preview merge plan
zerg merge --dry-run

# Abort in-progress merge
zerg merge --abort
```

#### Flags

| Flag | Short | Description | Default |
|------|-------|-------------|---------|
| `--level N` | `-l` | Merge specific level | Current level |
| `--force` | `-f` | Force merge despite conflicts/failures | Off |
| `--abort` | — | Abort in-progress merge | — |
| `--dry-run` | — | Show merge plan without executing | Off |
| `--skip-gates` | — | Skip quality gate checks | Off |
| `--no-rebase` | — | Don't rebase worker branches after merge | Off |
| `--verbose` | `-v` | Verbose output | Off |

#### Merge Protocol

1. **Check completion** — All tasks at the level must be complete
2. **Collect branches** — Gather all worker branches
3. **Create staging** — Create staging branch from base
4. **Merge branches** — Merge each worker branch into staging
5. **Quality gates** — Run lint, test, typecheck
6. **Tag merge** — Tag the merge point
7. **Rebase workers** — Rebase worker branches onto merged result

#### Conflict Resolution

| Option | Command | Description |
|--------|---------|-------------|
| Manual | Edit conflicting files | Resolve by hand |
| Accept theirs | `git checkout --theirs <file>` | Keep worker's version |
| Accept ours | `git checkout --ours <file>` | Keep base version |
| Re-run task | `zerg retry TASK-ID --on-base` | Re-execute on merged base |

---

### /zerg:cleanup

Remove ZERG artifacts and free resources.

**When to use**: After a feature is complete, or to clean up a failed run.

#### Usage

```bash
# Clean specific feature
zerg cleanup --feature user-auth

# Clean all features
zerg cleanup --all

# Preview cleanup plan
zerg cleanup --all --dry-run

# Keep logs for debugging
zerg cleanup --feature user-auth --keep-logs

# Keep branches for inspection
zerg cleanup --feature user-auth --keep-branches
```

#### Flags

| Flag | Short | Description |
|------|-------|-------------|
| `--feature TEXT` | `-f` | Feature to clean (required unless `--all`) |
| `--all` | — | Clean all ZERG features |
| `--keep-logs` | — | Preserve log files |
| `--keep-branches` | — | Preserve git branches |
| `--dry-run` | — | Show cleanup plan without executing |

#### What Gets Removed vs Preserved

| Resource | Removed | Preserved |
|----------|---------|-----------|
| Worktrees | Yes | — |
| State files | Yes | — |
| Log files | Unless `--keep-logs` | — |
| Git branches | Unless `--keep-branches` | — |
| Docker containers | Yes | — |
| Spec files | — | Always preserved |
| Source code/commits | — | Always preserved |

---

## Quality & Analysis

---

### /zerg:build

Build orchestration with auto-detection and error recovery.

**When to use**: To build the project with intelligent error handling.

#### Usage

```bash
/zerg:build
/zerg:build --mode prod
/zerg:build --clean
/zerg:build --watch
/zerg:build --retry 3
```

#### Flags

| Flag | Description | Default |
|------|-------------|---------|
| `--target TEXT` | Build target | `all` |
| `--mode TEXT` | Build mode: `dev`, `staging`, `prod` | `dev` |
| `--clean` | Clean build (remove artifacts first) | Off |
| `--watch` | Watch mode (rebuild on changes) | Off |
| `--retry N` | Number of retries on failure | 3 |

#### Auto-Detected Build Systems

| System | Detection File |
|--------|---------------|
| npm | `package.json` |
| cargo | `Cargo.toml` |
| make | `Makefile` |
| gradle | `build.gradle` |
| go | `go.mod` |
| python | `pyproject.toml` |

#### Error Recovery

| Error Category | Automatic Action |
|----------------|-----------------|
| Missing dependency | Install dependencies |
| Type error | Suggest fix |
| Resource exhaustion | Reduce parallelism |
| Network timeout | Retry with backoff |

---

### /zerg:test

Execute tests with coverage analysis and test generation.

**When to use**: To run the project's test suite with enhanced reporting.

#### Usage

```bash
/zerg:test
/zerg:test --coverage
/zerg:test --watch
/zerg:test --parallel 8
/zerg:test --generate
/zerg:test --framework pytest
```

#### Flags

| Flag | Description | Default |
|------|-------------|---------|
| `--generate` | Generate test stubs for uncovered code | Off |
| `--coverage` | Report coverage | Off |
| `--watch` | Watch mode (re-run on changes) | Off |
| `--parallel N` | Parallel test execution | — |
| `--framework TEXT` | Force framework: `pytest`, `jest`, `cargo`, `go` | Auto-detect |

#### Auto-Detected Frameworks

pytest, jest, cargo test, go test, mocha, vitest

---

### /zerg:analyze

Run static analysis, complexity metrics, and quality assessment.

**When to use**: To assess code quality before committing or as part of a review.

#### Usage

```bash
/zerg:analyze --check all
/zerg:analyze --check lint --format json
/zerg:analyze --check complexity --threshold complexity=15
/zerg:analyze --check all --format sarif > results.sarif
```

#### Flags

| Flag | Description | Default |
|------|-------------|---------|
| `--check TEXT` | Check type: `lint`, `complexity`, `coverage`, `security`, `all` | `all` |
| `--format TEXT` | Output format: `text`, `json`, `sarif` | `text` |
| `--threshold TEXT` | Custom thresholds (e.g., `complexity=10,coverage=70`) | Defaults |
| `--files PATH` | Restrict to specific files | All |

#### Check Types

| Check | Description |
|-------|-------------|
| `lint` | Language-specific linting (ruff, eslint, etc.) |
| `complexity` | Cyclomatic and cognitive complexity analysis |
| `coverage` | Test coverage analysis and reporting |
| `security` | SAST scanning (bandit, semgrep) |

---

### /zerg:review

Two-stage code review workflow.

**When to use**: Before creating a PR, or to process review feedback.

#### Usage

```bash
/zerg:review                   # Full two-stage review (default)
/zerg:review --mode prepare    # Prepare PR for review
/zerg:review --mode self       # Self-review checklist
/zerg:review --mode receive    # Process review feedback
```

#### Flags

| Flag | Description | Default |
|------|-------------|---------|
| `--mode TEXT` | Review mode: `prepare`, `self`, `receive`, `full` | `full` |

#### Modes

| Mode | What It Does |
|------|-------------|
| `prepare` | Generate change summary, check spec compliance, create review checklist |
| `self` | Self-review: compiles? tests pass? no secrets? error handling? edge cases? |
| `receive` | Parse review comments, track addressed items, generate response |
| `full` | Stage 1 (spec compliance) + Stage 2 (code quality) |

---

### /zerg:security

Security review, vulnerability scanning, and secure coding rules management.

**When to use**: To scan for vulnerabilities, enforce compliance, or manage security rules.

#### Usage

```bash
# Vulnerability scanning
/zerg:security
/zerg:security --preset owasp
/zerg:security --preset pci
/zerg:security --autofix
/zerg:security --format sarif > security.sarif

# Security rules management (CLI)
zerg security-rules detect       # Detect project stack
zerg security-rules list         # List rules for your stack
zerg security-rules fetch        # Download rules
zerg security-rules integrate    # Full integration with CLAUDE.md
```

#### Scanning Flags

| Flag | Description | Default |
|------|-------------|---------|
| `--preset TEXT` | Compliance preset: `owasp`, `pci`, `hipaa`, `soc2` | `owasp` |
| `--autofix` | Generate auto-fix suggestions | Off |
| `--format TEXT` | Output format: `text`, `json`, `sarif` | `text` |

#### Compliance Presets

| Preset | Standard | Coverage |
|--------|----------|----------|
| `owasp` | OWASP Top 10 2025 | Injection, XSS, auth, access control, SSRF, etc. |
| `pci` | PCI-DSS | Payment card data security |
| `hipaa` | HIPAA | Healthcare data security |
| `soc2` | SOC 2 | Trust services criteria |

#### Capabilities

- **Secret detection**: API keys, passwords, tokens, private keys, AWS/GitHub/OpenAI/Anthropic credentials
- **Dependency CVE scanning**: Python, Node.js, Rust, Go
- **Code analysis**: Injection, XSS, authentication, access control patterns

#### Security Rules (CLI)

Manage stack-specific secure coding rules:

```bash
$ zerg security-rules detect
Detected Project Stack:
  Languages:      python
  Frameworks:     fastapi, langchain
  Databases:      pinecone
  Infrastructure: docker, github-actions
  AI/ML:          yes
```

Rules are fetched from [TikiTribe/claude-secure-coding-rules](https://github.com/TikiTribe/claude-secure-coding-rules) and integrated into `CLAUDE.md`.

---

### /zerg:refactor

Automated code improvement and cleanup.

**When to use**: To clean up code quality issues systematically.

#### Usage

```bash
/zerg:refactor --transforms dead-code,simplify --dry-run
/zerg:refactor --interactive
/zerg:refactor --transforms types,naming
```

#### Flags

| Flag | Description | Default |
|------|-------------|---------|
| `--transforms TEXT` | Comma-separated: `dead-code`, `simplify`, `types`, `patterns`, `naming` | All |
| `--dry-run` | Show suggestions without applying | Off |
| `--interactive` | Approve each suggestion individually | Off |

#### Transform Types

| Transform | Description | Examples |
|-----------|-------------|---------|
| `dead-code` | Remove unused imports, variables, functions | Unused imports |
| `simplify` | Simplify complex expressions | `if x == True:` → `if x:` |
| `types` | Strengthen type annotations | Add missing type hints, replace `Any` |
| `patterns` | Apply common design patterns | Guard clauses, early returns |
| `naming` | Improve variable and function names | Replace single-letter names |

---

## Utilities

---

### /zerg:git

Git operations with intelligent commits, PR creation, releases, rescue, review, and bisect.

**When to use**: For commit, branch, merge, sync, history, finish, PR creation, releases, code review, rescue/undo operations, or AI-powered bug bisection.

#### Usage

```bash
/zerg:git --action commit            # Intelligent commit message
/zerg:git --action commit --push     # Commit and push
/zerg:git --action commit --mode suggest  # Suggest message without committing
/zerg:git --action branch --name feature/auth
/zerg:git --action merge --branch feature/auth --strategy squash
/zerg:git --action sync              # Synchronize with remote
/zerg:git --action history --since v1.0.0
/zerg:git --action history --cleanup # Clean up commit history
/zerg:git --action finish            # Complete development branch
/zerg:git --action pr --draft        # Create a draft pull request
/zerg:git --action pr --reviewer octocat  # Create PR with reviewer
/zerg:git --action release --bump minor   # Minor version release
/zerg:git --action release --dry-run      # Preview release without executing
/zerg:git --action review --focus security  # Pre-review with security focus
/zerg:git --action rescue --list-ops       # List rescue operations
/zerg:git --action rescue --undo           # Undo last operation
/zerg:git --action rescue --restore v1.2.0 # Restore snapshot tag
/zerg:git --action rescue --recover-branch feature/lost  # Recover deleted branch
/zerg:git --action bisect --symptom "login returns 500" --test-cmd "pytest tests/auth" --good v1.0.0
/zerg:git --action ship              # Full pipeline: commit, push, PR, merge, cleanup
```

#### Flags

| Flag | Description |
|------|-------------|
| `--action, -a TEXT` | Action: `commit`, `branch`, `merge`, `sync`, `history`, `finish`, `pr`, `release`, `review`, `rescue`, `bisect`, `ship` |
| `--push, -p` | Push after commit/finish |
| `--base, -b TEXT` | Base branch (default: `main`) |
| `--name, -n TEXT` | Branch name (for branch action) |
| `--branch TEXT` | Branch to merge (for merge action) |
| `--strategy TEXT` | Merge strategy: `merge`, `squash`, `rebase` (default: `squash`) |
| `--since TEXT` | Starting point for history |
| `--mode TEXT` | Commit mode: `auto`, `confirm`, `suggest` |
| `--cleanup` | Run history cleanup (for history action) |
| `--draft` | Create draft PR (for pr action) |
| `--reviewer TEXT` | PR reviewer username (for pr action) |
| `--focus TEXT` | Review focus: `security`, `performance`, `quality`, `architecture` |
| `--bump TEXT` | Release bump type: `auto`, `major`, `minor`, `patch` (default: `auto`) |
| `--dry-run` | Preview release without executing (for release action) |
| `--symptom TEXT` | Bug symptom description (for bisect action) |
| `--test-cmd TEXT` | Test command for bisect verification |
| `--good TEXT` | Known good commit or tag (for bisect action) |
| `--list-ops` | List rescue operations (for rescue action) |
| `--undo` | Undo last operation (for rescue action) |
| `--restore TEXT` | Restore snapshot tag (for rescue action) |
| `--recover-branch TEXT` | Recover deleted branch (for rescue action) |
| `--no-merge` | Stop after PR creation (skip merge+cleanup, for ship action) |

#### Finish Workflow

The `finish` action presents four options after verifying tests pass:

1. **Merge back to main locally**
2. **Push and create a Pull Request**
3. **Keep the branch as-is** (handle it later)
4. **Discard this work**

#### PR Creation

The `pr` action creates a pull request with full context:

1. Analyzes all commits on the current branch vs base
2. Generates a descriptive title and body with summary and test plan
3. Supports `--draft` for work-in-progress PRs and `--reviewer` to request reviews

#### Release Workflow

The `release` action performs a semver release:

1. Determines next version from conventional commit history (`--bump auto` analyzes commits)
2. Updates CHANGELOG.md and version files
3. Creates a git tag and pushes (unless `--dry-run` is specified)

#### Rescue Operations

The `rescue` action provides undo and recovery:

- `--list-ops` — Show recent operations that can be undone
- `--undo` — Undo the last git operation
- `--restore TAG` — Restore a previously saved snapshot tag
- `--recover-branch NAME` — Recover a deleted branch from reflog

#### Review

The `review` action assembles pre-review context for the current branch:

1. Collects diff, commit history, and changed file summaries
2. Optionally focuses analysis on a domain with `--focus` (security, performance, quality, architecture)

#### Bisect

The `bisect` action performs AI-powered bug bisection:

1. Requires `--symptom` (description of the bug), `--test-cmd` (verification command), and `--good` (known working ref)
2. Automates `git bisect` using the test command to identify the first bad commit
3. Reports the offending commit with context about what changed

#### Ship

The `ship` action executes the full delivery pipeline in one shot:

1. **Commit** — Auto-generate conventional commit message and commit
2. **Push** — Push branch to remote
3. **Create PR** — Create pull request with full context
4. **Merge** — Squash merge the PR (falls back to `--admin` if blocked)
5. **Cleanup** — Switch to base, pull, delete feature branch

Use `--no-merge` to stop after PR creation (for team review workflows).

#### Conventional Commits

Auto-generated commit types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

---

### /zerg:debug

Deep diagnostic investigation for ZERG execution issues. Includes error intelligence, log correlation, Bayesian hypothesis testing, code-aware recovery, and environment diagnostics.

**When to use**: When workers crash, tasks fail, state is corrupt, or you can't figure out what went wrong.

#### Usage

```bash
# Auto-detect and diagnose
/zerg:debug

# Describe the problem
/zerg:debug workers keep crashing

# Focus on specific worker
/zerg:debug --worker 2

# Specific error message
/zerg:debug --error "ModuleNotFoundError: No module named 'requests'"

# Full system diagnostics
/zerg:debug --deep --env

# Generate and execute recovery plan
/zerg:debug --fix

# Write report to file
/zerg:debug --report diag.md
```

#### Flags

| Flag | Short | Description |
|------|-------|-------------|
| `--feature TEXT` | `-f` | Feature to investigate (auto-detected if omitted) |
| `--worker N` | `-w` | Focus on specific worker |
| `--deep` | — | Run system-level diagnostics (git, disk, docker, ports, worktrees) |
| `--fix` | — | Generate and execute recovery plan (with confirmation) |
| `--error TEXT` | `-e` | Specific error message to analyze |
| `--stacktrace PATH` | `-s` | Path to stack trace file |
| `--env` | — | Comprehensive environment diagnostics (venv, packages, Docker, resources, config) |
| `--interactive` | `-i` | Interactive debugging wizard mode |
| `--report PATH` | — | Write diagnostic markdown report to file |

#### Diagnostic Phases

| Phase | What It Does |
|-------|-------------|
| 1. Context Gathering | Read state files, logs, task graph, git status |
| 1.5. Error Intelligence | Multi-language error parsing (Python, JS/TS, Go, Rust, Java, C++), fingerprinting, chain analysis, semantic classification |
| 2. Symptom Classification | Classify into: WORKER_FAILURE, TASK_FAILURE, STATE_CORRUPTION, INFRASTRUCTURE, CODE_ERROR, DEPENDENCY, MERGE_CONFLICT, UNKNOWN |
| 2.5. Log Correlation | Timeline reconstruction, temporal clustering, cross-worker error correlation (Jaccard similarity), error evolution tracking |
| 3. Evidence Collection | Category-specific checklist (worker logs, file existence, state consistency, etc.) |
| 4. Hypothesis Testing | Bayesian probability scoring with prior knowledge base of 30+ failure patterns, automated test commands |
| 5. Root Cause Determination | Synthesize findings into root cause with confidence score |
| 6. Recovery Plan | Code-aware fix suggestions with dependency analysis, git blame context, import chain tracing, fix templates |
| 6.5. Design Escalation Check | Detect if issues require architectural changes → recommend `/zerg:design` |
| 7. Report & Integration | Save markdown report, create tracking task |
| 7.5. Environment Diagnostics | Python venv, packages, Docker, CPU/memory/disk, config validation (when `--env` is set) |

#### Error Categories

| Category | Indicators |
|----------|-----------|
| `WORKER_FAILURE` | Worker crashed, stopped unexpectedly, timeout |
| `TASK_FAILURE` | Task verification failed, code error |
| `STATE_CORRUPTION` | JSON parse error, orphaned tasks |
| `INFRASTRUCTURE` | Docker down, disk full, port conflict |
| `CODE_ERROR` | Import error, syntax error, runtime exception |
| `DEPENDENCY` | Missing package, version conflict |
| `MERGE_CONFLICT` | Git merge failure, file ownership violation |

#### Recovery Plan Risk Levels

| Level | Meaning |
|-------|---------|
| `[SAFE]` | Read-only or easily reversible |
| `[MODERATE]` | Writes data but can be undone |
| `[DESTRUCTIVE]` | Cannot be undone, requires explicit confirmation |

---

### /zerg:worker

Internal zergling execution protocol. You do not invoke this directly — the orchestrator uses it to give workers their execution instructions.

**When to use**: Automatically invoked by the orchestrator for each worker.

#### What Workers Do

1. **Load context** — Read requirements.md, design.md, task-graph.json, worker-assignments.json
2. **Claim task** — Atomically claim the next pending task at the current level via TaskUpdate
3. **Implement** — Create/modify files as specified, following design patterns
4. **Verify** — Run the task's verification command
5. **Commit** — Stage owned files, commit with task metadata
6. **Report** — Update task status in Claude Task system
7. **Repeat** — Pick next task, or wait for level merge, or checkpoint

#### Quality Standards

Every task must:
- Follow the design document exactly
- Match existing code patterns
- Be complete (no TODOs, no placeholders)
- Pass the verification command
- Include inline comments for complex logic
- Handle errors (not just the happy path)

#### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | All assigned tasks completed successfully |
| 1 | Unrecoverable error |
| 2 | Context limit reached (70%), needs restart |
| 3 | All remaining tasks blocked |
| 130 | Stop signal received, graceful shutdown |

---

### /zerg:plugins

Extend ZERG with custom quality gates, lifecycle hooks, and worker launchers.

**When to use**: To add custom validation, notifications, or execution environments.

See the [Plugin System](docs/plugins.md) documentation for complete details.

#### Three Plugin Types

| Type | Purpose | Example |
|------|---------|---------|
| `QualityGatePlugin` | Custom validation after merges | SonarQube scan, security scan |
| `LifecycleHookPlugin` | React to events (non-blocking) | Slack notifications, metrics |
| `LauncherPlugin` | Custom worker execution environments | Kubernetes, SSH clusters |

#### Configuration Methods

| Method | Complexity | How |
|--------|-----------|-----|
| YAML hooks | Simple | Shell commands in `.zerg/config.yaml` |
| YAML gates | Simple | Shell commands in `.zerg/config.yaml` |
| Python entry points | Advanced | Python classes registered via `pyproject.toml` |

---

## Documentation & AI

---

### /zerg:document

Generate structured documentation for a single component, module, or command.

**When to use**: To document a specific file or module with the doc_engine pipeline.

#### Usage

```
/zerg:document <target> [OPTIONS]
```

#### Flags

| Flag | Default | Description |
|------|---------|-------------|
| `<target>` | (required) | Path to the file or module to document |
| `--type` | `auto` | Component type: `auto`, `module`, `command`, `config`, `api`, `types` |
| `--output` | stdout | Output path for generated documentation |
| `--depth` | `standard` | Depth level: `shallow`, `standard`, `deep` |
| `--update` | off | Update existing documentation in-place |

#### Description

Runs a 7-step pipeline: Detect component type, Extract symbols from AST, Map dependencies, Generate Mermaid diagrams, Render with type-specific template, Cross-reference with glossary, Output to specified path.

**Depth levels**:
- `shallow` — Public classes and functions only
- `standard` — Public + internal methods, imports, basic diagram
- `deep` — All methods including private, usage examples, full dependency graph

#### Examples

```bash
# Document a module
/zerg:document zerg/launcher.py

# Deep documentation to a file
/zerg:document zerg/doc_engine/extractor.py --depth deep --output docs/extractor.md

# Update existing docs in-place
/zerg:document zerg/launcher.py --output docs/launcher.md --update
```

---

### /zerg:index

Generate a complete documentation wiki for the ZERG project.

**When to use**: To create or update the full project wiki with cross-references and sidebar navigation.

#### Usage

```
/zerg:index [OPTIONS]
```

#### Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--full` | off | Regenerate all pages from scratch (vs incremental) |
| `--push` | off | Push generated wiki to `{repo}.wiki.git` |
| `--dry-run` | off | Preview what would be generated without writing |
| `--output` | `.zerg/wiki/` | Output directory for generated pages |

#### Description

Discovers all documentable components, classifies them, extracts symbols, generates markdown pages, builds cross-references, creates architecture diagrams, and assembles a navigable wiki with sidebar.

By default operates in **incremental mode** — only regenerating pages for source files that changed since last generation. Use `--full` to regenerate everything.

#### Examples

```bash
# Generate full wiki
/zerg:index --full

# Preview changes
/zerg:index --dry-run

# Generate and push to GitHub Wiki
/zerg:index --full --push

# Custom output directory
/zerg:index --output docs/wiki/
```

---

### /zerg:estimate

Full-lifecycle effort estimation with PERT confidence intervals, post-execution comparison, and historical calibration.

**When to use**: Before `/zerg:rush` to project effort and cost, or after execution to compare actual vs estimated.

#### Usage

```
/zerg:estimate [<feature>] [OPTIONS]
```

#### Flags

| Flag | Default | Description |
|------|---------|-------------|
| `<feature>` | auto-detect | Feature to estimate (from `.gsd/.current-feature`) |
| `--pre` | auto | Force pre-execution estimation mode |
| `--post` | auto | Force post-execution comparison mode |
| `--calibrate` | off | Show historical accuracy and compute bias factors |
| `--workers N` | config | Worker count for wall-clock projection |
| `--format` | `text` | Output format: `text`, `json`, `md` |
| `--verbose` | off | Show per-task breakdown |
| `--history` | off | Show past estimates for this feature |
| `--no-calibration` | off | Skip applying calibration bias |

#### Description

Operates in three modes:

- **Pre-execution**: Analyzes task graph, scores complexity, calculates PERT estimates, projects wall-clock time and API cost
- **Post-execution**: Compares actual vs estimated duration/tokens/cost, calculates accuracy percentage
- **Calibration**: Analyzes historical accuracy across features, computes per-task-type bias factors

#### Examples

```bash
# Estimate before launching
/zerg:estimate user-auth

# Compare actual vs estimated
/zerg:estimate user-auth --post

# Per-task breakdown
/zerg:estimate --verbose

# Historical calibration
/zerg:estimate --calibrate
```

---

### /zerg:explain

Educational code explanations with four progressive depth layers, powered by doc_engine AST extractors.

**When to use**: To understand unfamiliar code at any scope — from a single function to an entire system.

#### Usage

```
/zerg:explain <target> [OPTIONS]
```

#### Flags

| Flag | Default | Description |
|------|---------|-------------|
| `<target>` | (required) | File, function (`file:func`), directory, or dotted module path |
| `--scope` | auto-detect | Override: `function`, `file`, `module`, `system` |
| `--save` | off | Write to `claudedocs/explanations/{target}.md` |
| `--format` | `text` | Output format: `text`, `md`, `json` |
| `--no-diagrams` | off | Skip Mermaid diagram generation |

#### Description

Generates layered explanations through four progressive depth levels:

1. **Summary** — What the code does, who calls it, why it exists
2. **Logic Flow** — Step-by-step execution walkthrough with flowchart
3. **Implementation Details** — Data structures, algorithms, edge cases
4. **Design Decisions** — Architectural rationale, trade-offs, alternatives

Auto-detects scope from target format: `file:func` → function, file path → file, directory → module.

#### Examples

```bash
# Explain a file
/zerg:explain zerg/launcher.py

# Explain a specific function
/zerg:explain zerg/launcher.py:spawn_worker

# Explain a module
/zerg:explain zerg/doc_engine/ --scope module

# Save explanation
/zerg:explain zerg/launcher.py --save
```

---

### /zerg:select-tool

Intelligent tool routing across MCP servers, native tools, and Task agent subtypes.

**When to use**: To determine the optimal tool combination for a given task before starting work.

#### Usage

```
/zerg:select-tool <task description> [OPTIONS]
```

#### Flags

| Flag | Default | Description |
|------|---------|-------------|
| `<task description>` | (required) | Free-text description of the task |
| `--domain` | auto-detect | Override: `ui`, `backend`, `infra`, `docs`, `test`, `security`, `perf` |
| `--format` | `text` | Output format: `text`, `json`, `md` |
| `--verbose` | off | Show per-dimension scoring breakdown |
| `--no-agents` | off | Exclude Task agent recommendations |
| `--no-mcp` | off | Exclude MCP server recommendations |

#### Description

Evaluates tasks across five scoring axes (file_count, analysis_depth, domain, parallelism, interactivity) and recommends tools from three categories:

- **Native Tools** — Read, Write, Edit, Grep, Glob, Bash
- **MCP Servers** — Context7, Sequential, Playwright, Magic, Morphllm, Serena
- **Task Agents** — Explore, Plan, general-purpose, python-expert, etc.

#### Examples

```bash
# Get recommendations
/zerg:select-tool "refactor the authentication module across 12 files"

# Force domain
/zerg:select-tool "optimize the query layer" --domain perf

# Detailed scoring
/zerg:select-tool "add a responsive navbar with accessibility" --verbose
```

---

## Exit Codes

All ZERG commands follow a consistent exit code convention:

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Failure (check output for details) |
| 2 | Configuration error or special state (checkpoint for workers) |
