# ZERG Command Reference

This page provides an index of all 26 ZERG commands. Each command has its own detailed reference page.

## Workflow Overview

ZERG commands follow a sequential workflow. The typical order of operations is:

```
brainstorm (optional) --> init --> plan --> design --> rush --> status/logs --> merge --> cleanup
```

During execution, use `stop` to halt workers, `retry` to re-run failed tasks, and `logs` to inspect worker output.

## Global CLI Flags

These flags apply to all ZERG commands:

| Flag | Description |
|------|-------------|
| `--quick` | Surface-level analysis |
| `--think` | Structured multi-step analysis |
| `--think-hard` | Deep architectural analysis |
| `--ultrathink` | Maximum depth, all MCP servers |
| `--no-compact` | Disable compact output (compact is ON by default) |
| `--no-loop` | Disable improvement loops (loops are ON by default) |
| `--iterations N` | Override loop iteration count |
| `--mode MODE` | Behavioral mode: precision, speed, exploration, refactor, debug |
| `--mcp` / `--no-mcp` | Enable/disable MCP auto-routing |
| `--tdd` | Enable TDD enforcement |
| `-v` / `--verbose` | Verbose output |
| `-q` / `--quiet` | Suppress non-essential output |

## Command Index

| Command | Purpose | Phase |
|---------|---------|-------|
| [[/zerg:init|zerg-init]] | Initialize ZERG for a new or existing project | Setup |
| [[/zerg:brainstorm|zerg-brainstorm]] | Feature discovery with Socratic dialogue, `--socratic` mode, trade-off exploration, and YAGNI filtering | Planning |
| [[/zerg:plan|zerg-plan]] | Capture requirements for a feature | Planning |
| [[/zerg:design|zerg-design]] | Generate architecture and task graph for parallel execution | Design |
| [[/zerg:rush|zerg-rush]] | Launch parallel workers to execute the task graph | Execution |
| [[/zerg:status|zerg-status]] | Display current execution status and progress | Monitoring |
| [[/zerg:logs|zerg-logs]] | Stream, filter, and aggregate worker logs | Monitoring |
| [[/zerg:stop|zerg-stop]] | Stop workers gracefully or forcefully | Control |
| [[/zerg:retry|zerg-retry]] | Retry failed or blocked tasks | Recovery |
| [[/zerg:merge|zerg-merge]] | Trigger or manage level merge operations | Integration |
| [[/zerg:cleanup|zerg-cleanup]] | Remove ZERG artifacts and clean up resources | Teardown |
| [[/zerg:build|zerg-build]] | Build orchestration with error recovery | Quality |
| [[/zerg:test|zerg-test]] | Execute tests with coverage and generation | Quality |
| [[/zerg:analyze|zerg-analyze]] | Static analysis, complexity metrics, quality assessment | Quality |
| [[/zerg:review|zerg-review]] | Two-stage code review (spec compliance + quality) | Quality |
| [[/zerg:security|zerg-security]] | Vulnerability scanning and secure coding rules | Quality |
| [[/zerg:refactor|zerg-refactor]] | Automated code improvement and cleanup | Quality |
| [[/zerg:git|zerg-git]] | Git operations: commits, PRs, releases, rescue, review, bisect, ship, cleanup, issue (14 actions) | Utility |
| [[/zerg:debug|zerg-debug]] | Deep diagnostic investigation with Bayesian hypothesis testing | Utility |
| [[/zerg:worker|zerg-worker]] | Internal: zergling execution protocol | Utility |
| [[/zerg:plugins|zerg-plugins]] | Plugin system management | Utility |
| [[/zerg:document|zerg-document]] | Generate documentation for a specific component | Documentation |
| [[/zerg:index|zerg-index]] | Generate a complete project documentation wiki | Documentation |
| [[/zerg:estimate|zerg-estimate]] | Effort estimation with PERT intervals and cost projection | AI & Analysis |
| [[/zerg:explain|zerg-explain]] | Educational code explanations with progressive depth | AI & Analysis |
| [[/zerg:select-tool|zerg-select-tool]] | Intelligent tool routing for MCP servers and agents | AI & Analysis |

## Command Categories

### Setup

- **[[/zerg:init|zerg-init]]** -- Run once per project to detect languages, generate configuration, and create the `.zerg/` directory structure.

### Planning and Design

- **[[/zerg:brainstorm|zerg-brainstorm]]** -- Open-ended feature discovery through competitive research, Socratic questioning with `--socratic` mode, trade-off exploration, YAGNI filtering, and automated issue creation.
- **[[/zerg:plan|zerg-plan]]** -- Interactive requirements gathering. Produces `requirements.md` in the spec directory.
- **[[/zerg:design|zerg-design]]** -- Generates `design.md` and `task-graph.json`. Breaks work into parallelizable tasks with exclusive file ownership.

### Execution

- **[[/zerg:rush|zerg-rush]]** -- Launches worker containers or processes. Assigns tasks by level and monitors execution.
- **[[/zerg:stop|zerg-stop]]** -- Graceful or forced shutdown of running workers.
- **[[/zerg:retry|zerg-retry]]** -- Re-queues failed tasks for execution.

### Monitoring

- **[[/zerg:status|zerg-status]]** -- Snapshot of progress across all levels, workers, and tasks.
- **[[/zerg:logs|zerg-logs]]** -- Access structured JSONL logs, filter by worker, task, level, phase, or event type.

### Integration and Teardown

- **[[/zerg:merge|zerg-merge]]** -- Merges worker branches after each level, runs quality gates (lint, test, typecheck).
- **[[/zerg:cleanup|zerg-cleanup]]** -- Removes worktrees, branches, containers, and state files. Preserves spec files and merged code.

### Quality and Analysis

- **[[/zerg:build|zerg-build]]** -- Build orchestration with automatic error recovery and watch mode.
- **[[/zerg:test|zerg-test]]** -- Test execution with coverage reporting, parallel runs, and test generation.
- **[[/zerg:analyze|zerg-analyze]]** -- Static analysis including linting, complexity metrics, coverage, and security checks.
- **[[/zerg:review|zerg-review]]** -- Two-stage code review: spec compliance verification followed by quality assessment.
- **[[/zerg:security|zerg-security]]** -- Vulnerability scanning with OWASP, PCI, HIPAA, and SOC2 presets.
- **[[/zerg:refactor|zerg-refactor]]** -- Automated code improvement: dead code removal, simplification, type additions, naming fixes.

### Utilities

- **[[/zerg:git|zerg-git]]** -- Git operations: commit, branch, merge, sync, history, finish, pr, release, review, rescue, bisect, ship, cleanup, issue (14 actions).
- **[[/zerg:debug|zerg-debug]]** -- Deep diagnostic investigation with Bayesian hypothesis testing and recovery plans.
- **[[/zerg:worker|zerg-worker]]** -- Internal zergling execution protocol. Not invoked directly by users.
- **[[/zerg:plugins|zerg-plugins]]** -- Plugin system management: quality gates, lifecycle hooks, and custom launchers.

### Documentation and AI

- **[[/zerg:document|zerg-document]]** -- Generate documentation for a specific component, module, or command using the doc_engine pipeline.
- **[[/zerg:index|zerg-index]]** -- Generate a complete project documentation wiki with cross-references and sidebar.
- **[[/zerg:estimate|zerg-estimate]]** -- Full-lifecycle effort estimation with PERT intervals, post-execution comparison, and calibration.
- **[[/zerg:explain|zerg-explain]]** -- Educational code explanations with four progressive depth layers.
- **[[/zerg:select-tool|zerg-select-tool]]** -- Intelligent tool routing across MCP servers, native tools, and Task agent subtypes.

## Global Concepts

### Feature Name

Most commands auto-detect the active feature from `.gsd/.current-feature`. You can override this with `--feature <name>` where supported.

### Task System

All commands integrate with Claude Code's Task system for coordination and state tracking. The Task system is the authoritative source of truth; state JSON files in `.zerg/state/` are supplementary.

### Levels

Tasks are grouped into dependency levels. All tasks in Level N must complete before any Level N+1 task begins. Within a level, tasks run in parallel.

### File Ownership

Each task exclusively owns specific files. No two tasks modify the same file, which eliminates merge conflicts during parallel execution.
