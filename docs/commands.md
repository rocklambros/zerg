# ZERG Command Reference

Complete documentation for all 20 ZERG slash commands. Each command is available inside Claude Code sessions after running `zerg install`.

Commands can be invoked in two ways:
- **Slash command**: `/zerg:rush --workers=5` (inside Claude Code)
- **CLI**: `zerg rush --workers=5` (from the terminal)

---

## Table of Contents

- **Core Workflow**
  - [/zerg:init](#zerginit) — Initialize project
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
```

#### Flags

| Flag | Short | Description | Default |
|------|-------|-------------|---------|
| `--feature TEXT` | `-f` | Feature to show status for | Auto-detected |
| `--watch` | `-w` | Continuous update mode | Off |
| `--interval N` | — | Watch refresh interval in seconds | 5 |
| `--level N` | `-l` | Filter to specific level | All |
| `--json` | — | Output as JSON | Off |

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

Git operations with intelligent commits and finish workflow.

**When to use**: For commit, branch, merge, sync, history, or to finish a development branch.

#### Usage

```bash
/zerg:git --action commit            # Intelligent commit message
/zerg:git --action commit --push     # Commit and push
/zerg:git --action branch --name feature/auth
/zerg:git --action merge --branch feature/auth --strategy squash
/zerg:git --action sync              # Synchronize with remote
/zerg:git --action history --since v1.0.0
/zerg:git --action finish            # Complete development branch
```

#### Flags

| Flag | Description |
|------|-------------|
| `--action TEXT` | Action: `commit`, `branch`, `merge`, `sync`, `history`, `finish` |
| `--push` | Push after commit |
| `--base TEXT` | Base branch for merge/finish (default: `main`) |
| `--name TEXT` | Branch name (for branch action) |
| `--branch TEXT` | Branch to merge (for merge action) |
| `--strategy TEXT` | Merge strategy (for merge action) |
| `--since TEXT` | Starting point for history |

#### Finish Workflow

The `finish` action presents four options after verifying tests pass:

1. **Merge back to main locally**
2. **Push and create a Pull Request**
3. **Keep the branch as-is** (handle it later)
4. **Discard this work**

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

## Exit Codes

All ZERG commands follow a consistent exit code convention:

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Failure (check output for details) |
| 2 | Configuration error or special state (checkpoint for workers) |
