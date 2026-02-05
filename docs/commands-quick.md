# ZERG Command Quick Reference

Fast lookup for experienced users. For detailed explanations, see [Command Guide](commands-deep.md).

---

## Global Flags

### Analysis Depth (mutually exclusive)

| Flag | Tokens | Description |
|------|--------|-------------|
| `--quick` | ~1K | Surface-level, fast execution |
| `--think` | ~4K | Structured multi-step analysis |
| `--think-hard` | ~10K | Deep architectural analysis |
| `--ultrathink` | ~32K | Maximum depth, all MCP servers |

### Output & Efficiency

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--no-compact` | bool | false | Disable compact output |

### Behavioral Mode

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--mode` | string | auto | Override mode: `precision`, `speed`, `exploration`, `refactor`, `debug` |

### MCP Routing

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--mcp` | bool | true | Enable MCP auto-routing |
| `--no-mcp` | bool | false | Disable all MCP servers |

### Improvement Loops

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--no-loop` | bool | false | Disable improvement loops |
| `--iterations` | int | config | Max loop iterations |

### TDD & Standard

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--tdd` | bool | false | Enable TDD enforcement |
| `--verbose` / `-v` | bool | false | Verbose output |
| `--quiet` / `-q` | bool | false | Suppress non-essential output |
| `--version` | bool | false | Show version |
| `--help` | bool | false | Show help |

---

## Core Workflow

### /zerg:brainstorm

Open-ended feature discovery with competitive research and GitHub issue creation.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--rounds` | int | 3 | Socratic discovery rounds (max 5) |
| `--socratic` | bool | false | Single-question mode with domain trees |
| `--skip-research` | bool | false | Skip web research phase |
| `--skip-issues` | bool | false | Don't create GitHub issues |
| `--dry-run` | bool | false | Preview issues only |
| `--resume` | bool | false | Resume from checkpoint |

### /zerg:design

Generate architecture and task graph for parallel execution.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--help` | bool | false | Show help |

Prerequisite: `.gsd/specs/{feature}/requirements.md` with APPROVED status.

### /zerg:init

Initialize ZERG for a project. Inception mode (empty dir) or Discovery mode (existing project).

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--workers` | int | 5 | Default worker count |
| `--security` | string | "" | Security level (e.g., `strict`) |
| `--no-security-rules` | bool | false | Skip TikiTribe security rules |
| `--with-containers` | bool | false | Build devcontainer after init |

### /zerg:plan

Capture requirements through interactive questioning.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--socratic` / `-s` | bool | false | Structured 3-round discovery |
| `--rounds` | int | 3 | Socratic rounds (max 5) |

### /zerg:rush

Launch parallel workers to execute task graph.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--workers` / `-w` | int | 5 | Parallel workers (max 10) |
| `--feature` / `-f` | string | auto | Feature name |
| `--level` / `-l` | int | 1 | Start from level |
| `--task-graph` / `-g` | string | auto | Path to task-graph.json |
| `--mode` / `-m` | string | task | Mode: `subprocess`, `container`, `task` |
| `--dry-run` | bool | false | Show plan only |
| `--resume` | bool | false | Continue previous run |
| `--timeout` | int | 3600 | Max seconds |

---

## Monitoring & Control

### /zerg:cleanup

Remove ZERG artifacts and free resources.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--feature` / `-f` | string | "" | Feature to clean (required unless `--all`) |
| `--all` | bool | false | Clean all features |
| `--keep-logs` | bool | false | Preserve logs |
| `--keep-branches` | bool | false | Preserve git branches |
| `--dry-run` | bool | false | Preview only |

### /zerg:logs

Stream, filter, and aggregate worker logs.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `WORKER_ID` | int | all | Filter to worker (positional) |
| `--feature` / `-f` | string | auto | Feature name |
| `--tail` / `-n` | int | 100 | Lines to show |
| `--follow` | bool | false | Stream continuously |
| `--level` / `-l` | string | all | Filter: `debug`, `info`, `warn`, `error` |
| `--json` | bool | false | Raw JSON output |
| `--aggregate` | bool | false | Merge all logs by timestamp |
| `--task` | string | "" | Filter to task ID |
| `--artifacts` | string | "" | Show task artifacts |
| `--phase` | string | "" | Filter: `claim`, `execute`, `verify`, `commit`, `cleanup` |
| `--event` | string | "" | Filter by event type |
| `--since` | string | "" | After ISO8601 timestamp |
| `--until` | string | "" | Before ISO8601 timestamp |
| `--search` | string | "" | Text search |

### /zerg:merge

Manually trigger level merge operations.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--level` / `-l` | int | current | Merge specific level |
| `--force` / `-f` | bool | false | Force despite conflicts |
| `--abort` | bool | false | Abort in-progress merge |
| `--dry-run` | bool | false | Preview only |
| `--skip-gates` | bool | false | Skip quality gates |
| `--no-rebase` | bool | false | Don't rebase after merge |

### /zerg:retry

Retry failed or blocked tasks.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `TASK_IDS` | string[] | [] | Task IDs to retry (positional) |
| `--level` / `-l` | int | 0 | Retry all failed in level |
| `--all` / `-a` | bool | false | Retry all failed |
| `--force` / `-f` | bool | false | Bypass retry limit |
| `--timeout` / `-t` | int | config | Override timeout |
| `--reset` | bool | false | Reset retry counters |
| `--dry-run` | bool | false | Preview only |

### /zerg:status

Display real-time execution progress.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--feature` / `-f` | string | auto | Feature to show |
| `--watch` / `-w` | bool | false | Continuous update |
| `--interval` / `-i` | int | 5 | Watch refresh seconds |
| `--level` / `-l` | int | all | Filter to level |
| `--json` | bool | false | JSON output |
| `--dashboard` / `-d` | bool | false | TUI dashboard (CLI only) |
| `--tasks` | bool | false | Show all tasks |
| `--workers` | bool | false | Detailed worker info |
| `--commits` | bool | false | Recent commits per branch |

### /zerg:stop

Stop workers gracefully or forcefully.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--feature` / `-f` | string | auto | Feature to stop |
| `--worker` / `-w` | int | all | Stop specific worker |
| `--force` | bool | false | Immediate termination |
| `--timeout` | int | 30 | Graceful shutdown seconds |

---

## Quality & Analysis

### /zerg:analyze

Static analysis, complexity metrics, and quality assessment.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--check` | string | all | Check: `lint`, `complexity`, `coverage`, `security`, `all` |
| `--format` | string | text | Output: `text`, `json`, `sarif` |
| `--threshold` | string | defaults | Custom thresholds |
| `--files` | string | all | Restrict to files |

### /zerg:build

Build orchestration with auto-detection and error recovery.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--target` | string | all | Build target |
| `--mode` | string | dev | Mode: `dev`, `staging`, `prod` |
| `--clean` | bool | false | Clean build |
| `--watch` | bool | false | Rebuild on changes |
| `--retry` | int | 3 | Retries on failure |

### /zerg:refactor

Automated code improvement and cleanup.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--transforms` | string | all | Transforms: `dead-code`, `simplify`, `types`, `patterns`, `naming` |
| `--dry-run` | bool | false | Preview only |
| `--interactive` | bool | false | Approve one by one |

### /zerg:review

Two-stage code review workflow.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--mode` | string | full | Mode: `prepare`, `self`, `receive`, `full` |

### /zerg:security

Security scanning and rules management.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--preset` | string | owasp | Compliance: `owasp`, `pci`, `hipaa`, `soc2` |
| `--autofix` | bool | false | Generate fix suggestions |
| `--format` | string | text | Output: `text`, `json`, `sarif` |

CLI subcommand: `zerg security-rules detect|list|fetch|integrate`

### /zerg:test

Execute tests with coverage and generation.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--generate` | bool | false | Generate test stubs |
| `--coverage` | bool | false | Report coverage |
| `--watch` | bool | false | Continuous testing |
| `--parallel` | int | auto | Test workers |
| `--framework` | string | auto | Force: `pytest`, `jest`, `cargo`, `go` |

---

## Utilities

### /zerg:create-command

Scaffold new ZERG commands with Task integration and tests.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `<name>` | string | required | Command name |
| `--interactive` | bool | false | Enable wizard |

### /zerg:debug

Deep diagnostic investigation with error intelligence.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--feature` / `-f` | string | auto | Feature to investigate |
| `--worker` / `-w` | int | all | Focus on worker |
| `--deep` | bool | false | System-level diagnostics |
| `--fix` | bool | false | Generate recovery plan |
| `--error` / `-e` | string | "" | Error message to analyze |
| `--stacktrace` / `-s` | string | "" | Path to stack trace |
| `--env` | bool | false | Environment diagnostics |
| `--interactive` / `-i` | bool | false | Wizard mode |
| `--report` | string | "" | Write report to file |

### /zerg:git

Git operations with intelligent commits, PRs, releases, and more.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--action` / `-a` | string | commit | Action (see below) |
| `--push` / `-p` | bool | false | Push after commit |
| `--base` / `-b` | string | main | Base branch |
| `--name` / `-n` | string | "" | Branch name |
| `--branch` | string | "" | Branch to merge |
| `--strategy` | string | squash | Merge: `merge`, `squash`, `rebase` |
| `--since` | string | "" | History start point |
| `--mode` | string | auto | Commit: `auto`, `confirm`, `suggest` |
| `--cleanup` | bool | false | History cleanup |
| `--draft` | bool | false | Draft PR |
| `--reviewer` | string | "" | PR reviewer |
| `--focus` | string | "" | Review: `security`, `performance`, `quality`, `architecture` |
| `--bump` | string | auto | Release: `auto`, `major`, `minor`, `patch` |
| `--dry-run` | bool | false | Preview only |
| `--symptom` | string | "" | Bug symptom (bisect) |
| `--test-cmd` | string | "" | Test command (bisect) |
| `--good` | string | "" | Known good ref (bisect) |
| `--list-ops` | bool | false | List rescue operations |
| `--undo` | bool | false | Undo last operation |
| `--restore` | string | "" | Restore snapshot |
| `--recover-branch` | string | "" | Recover deleted branch |
| `--no-merge` | bool | false | Stop after PR creation |
| `--stale-days` | int | 30 | Branch age for cleanup |
| `--title` | string | "" | Issue title |
| `--label` | string | "" | Issue label |
| `--assignee` | string | "" | Issue assignee |
| `--no-docker` | bool | false | Skip Docker cleanup |
| `--include-stashes` | bool | false | Clear stashes |
| `--limit` | int | 10 | Max issues |
| `--priority` | string | "" | Filter: `P0`, `P1`, `P2` |

**Actions**: `commit`, `branch`, `merge`, `sync`, `history`, `finish`, `pr`, `release`, `review`, `rescue`, `bisect`, `ship`, `cleanup`, `issue`

### /zerg:plugins

Extend ZERG with quality gates, hooks, and launchers.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--help` | bool | false | Show documentation |

### /zerg:worker

Internal worker protocol. Invoked by orchestrator.

| Env Var | Default | Description |
|---------|---------|-------------|
| `ZERG_WORKER_ID` | 0 | Worker ID |
| `ZERG_FEATURE` | unknown | Feature name |
| `ZERG_BRANCH` | main | Base branch |

---

## Documentation & AI

### /zerg:document

Generate documentation for a single component.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `<target>` | string | required | File or module to document |
| `--type` | string | auto | Type: `auto`, `module`, `command`, `config`, `api`, `types` |
| `--output` | string | stdout | Output path |
| `--depth` | string | standard | Depth: `shallow`, `standard`, `deep` |
| `--update` | bool | false | Update in-place |

### /zerg:estimate

PERT effort estimation with post-execution comparison.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `<feature>` | string | auto | Feature to estimate |
| `--pre` | bool | auto | Force pre-execution mode |
| `--post` | bool | auto | Force post-execution mode |
| `--calibrate` | bool | false | Show historical accuracy |
| `--workers` | int | config | Worker count for projection |
| `--format` | string | text | Output: `text`, `json`, `md` |
| `--verbose` | bool | false | Per-task breakdown |
| `--history` | bool | false | Show past estimates |
| `--no-calibration` | bool | false | Skip bias application |

### /zerg:explain

Educational code explanations with four depth layers.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `<target>` | string | required | File, `file:func`, directory, or module |
| `--scope` | string | auto | Override: `function`, `file`, `module`, `system` |
| `--save` | bool | false | Write to claudedocs/ |
| `--format` | string | text | Output: `text`, `md`, `json` |
| `--no-diagrams` | bool | false | Skip Mermaid diagrams |

### /zerg:index

Generate complete documentation wiki.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--full` | bool | false | Regenerate all pages |
| `--push` | bool | false | Push to wiki.git |
| `--dry-run` | bool | false | Preview only |
| `--output` | string | .gsd/wiki/ | Output directory |

### /zerg:select-tool

Intelligent tool routing across MCP, native tools, and agents.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `<task description>` | string | required | Task to analyze |
| `--domain` | string | auto | Override: `ui`, `backend`, `infra`, `docs`, `test`, `security`, `perf` |
| `--format` | string | text | Output: `text`, `json`, `md` |
| `--verbose` | bool | false | Per-dimension scoring |
| `--no-agents` | bool | false | Exclude agent recommendations |
| `--no-mcp` | bool | false | Exclude MCP recommendations |

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Failure |
| 2 | Configuration error / worker checkpoint |
| 4 | Worker escalated ambiguous failure |
