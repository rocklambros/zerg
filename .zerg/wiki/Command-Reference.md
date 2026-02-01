# ZERG Command Reference

This page provides an index of all 26 ZERG commands. Each command has its own detailed reference page.

## Workflow Overview

ZERG commands follow a sequential workflow. The typical order of operations is:

```
brainstorm (optional) --> init --> plan --> design --> rush --> status/logs --> merge --> cleanup
```

During execution, use `stop` to halt workers, `retry` to re-run failed tasks, and `logs` to inspect worker output.

## Command Index

| Command | Purpose | Phase |
|---------|---------|-------|
| [[/zerg:init|Command-init]] | Initialize ZERG for a new or existing project | Setup |
| [[/zerg:brainstorm|Command-brainstorm]] | Feature discovery and GitHub issue creation | Planning |
| [[/zerg:plan|Command-plan]] | Capture requirements for a feature | Planning |
| [[/zerg:design|Command-design]] | Generate architecture and task graph for parallel execution | Design |
| [[/zerg:rush|Command-rush]] | Launch parallel workers to execute the task graph | Execution |
| [[/zerg:status|Command-status]] | Display current execution status and progress | Monitoring |
| [[/zerg:logs|Command-logs]] | Stream, filter, and aggregate worker logs | Monitoring |
| [[/zerg:stop|Command-stop]] | Stop workers gracefully or forcefully | Control |
| [[/zerg:retry|Command-retry]] | Retry failed or blocked tasks | Recovery |
| [[/zerg:merge|Command-merge]] | Trigger or manage level merge operations | Integration |
| [[/zerg:cleanup|Command-cleanup]] | Remove ZERG artifacts and clean up resources | Teardown |
| [[/zerg:build|Command-build]] | Build orchestration with error recovery | Quality |
| [[/zerg:test|Command-test]] | Execute tests with coverage and generation | Quality |
| [[/zerg:analyze|Command-analyze]] | Static analysis, complexity metrics, quality assessment | Quality |
| [[/zerg:review|Command-review]] | Two-stage code review (spec compliance + quality) | Quality |
| [[/zerg:security|Command-security]] | Vulnerability scanning and secure coding rules | Quality |
| [[/zerg:refactor|Command-refactor]] | Automated code improvement and cleanup | Quality |
| [[/zerg:git|Command-git]] | Git operations: commits, PRs, releases, rescue, review, bisect, ship (12 actions) | Utility |
| [[/zerg:debug|Command-debug]] | Deep diagnostic investigation with Bayesian hypothesis testing | Utility |
| [[/zerg:worker|Command-worker]] | Internal: zergling execution protocol | Utility |
| [[/zerg:plugins|Command-plugins]] | Plugin system management | Utility |
| [[/zerg:document|Command-document]] | Generate documentation for a specific component | Documentation |
| [[/zerg:index|Command-index]] | Generate a complete project documentation wiki | Documentation |
| [[/zerg:estimate|Command-estimate]] | Effort estimation with PERT intervals and cost projection | AI & Analysis |
| [[/zerg:explain|Command-explain]] | Educational code explanations with progressive depth | AI & Analysis |
| [[/zerg:select-tool|Command-select-tool]] | Intelligent tool routing for MCP servers and agents | AI & Analysis |

## Command Categories

### Setup

- **[[/zerg:init|Command-init]]** -- Run once per project to detect languages, generate configuration, and create the `.zerg/` directory structure.

### Planning and Design

- **[[/zerg:brainstorm|Command-brainstorm]]** -- Open-ended feature discovery through competitive research, Socratic questioning, and automated issue creation.
- **[[/zerg:plan|Command-plan]]** -- Interactive requirements gathering. Produces `requirements.md` in the spec directory.
- **[[/zerg:design|Command-design]]** -- Generates `design.md` and `task-graph.json`. Breaks work into parallelizable tasks with exclusive file ownership.

### Execution

- **[[/zerg:rush|Command-rush]]** -- Launches worker containers or processes. Assigns tasks by level and monitors execution.
- **[[/zerg:stop|Command-stop]]** -- Graceful or forced shutdown of running workers.
- **[[/zerg:retry|Command-retry]]** -- Re-queues failed tasks for execution.

### Monitoring

- **[[/zerg:status|Command-status]]** -- Snapshot of progress across all levels, workers, and tasks.
- **[[/zerg:logs|Command-logs]]** -- Access structured JSONL logs, filter by worker, task, level, phase, or event type.

### Integration and Teardown

- **[[/zerg:merge|Command-merge]]** -- Merges worker branches after each level, runs quality gates (lint, test, typecheck).
- **[[/zerg:cleanup|Command-cleanup]]** -- Removes worktrees, branches, containers, and state files. Preserves spec files and merged code.

### Quality and Analysis

- **[[/zerg:build|Command-build]]** -- Build orchestration with automatic error recovery and watch mode.
- **[[/zerg:test|Command-test]]** -- Test execution with coverage reporting, parallel runs, and test generation.
- **[[/zerg:analyze|Command-analyze]]** -- Static analysis including linting, complexity metrics, coverage, and security checks.
- **[[/zerg:review|Command-review]]** -- Two-stage code review: spec compliance verification followed by quality assessment.
- **[[/zerg:security|Command-security]]** -- Vulnerability scanning with OWASP, PCI, HIPAA, and SOC2 presets.
- **[[/zerg:refactor|Command-refactor]]** -- Automated code improvement: dead code removal, simplification, type additions, naming fixes.

### Utilities

- **[[/zerg:git|Command-git]]** -- Git operations: commit, branch, merge, sync, history, finish, pr, release, review, rescue, bisect, ship.
- **[[/zerg:debug|Command-debug]]** -- Deep diagnostic investigation with Bayesian hypothesis testing and recovery plans.
- **[[/zerg:worker|Command-worker]]** -- Internal zergling execution protocol. Not invoked directly by users.
- **[[/zerg:plugins|Command-plugins]]** -- Plugin system management: quality gates, lifecycle hooks, and custom launchers.

### Documentation and AI

- **[[/zerg:document|Command-document]]** -- Generate documentation for a specific component, module, or command using the doc_engine pipeline.
- **[[/zerg:index|Command-index]]** -- Generate a complete project documentation wiki with cross-references and sidebar.
- **[[/zerg:estimate|Command-estimate]]** -- Full-lifecycle effort estimation with PERT intervals, post-execution comparison, and calibration.
- **[[/zerg:explain|Command-explain]]** -- Educational code explanations with four progressive depth layers.
- **[[/zerg:select-tool|Command-select-tool]]** -- Intelligent tool routing across MCP servers, native tools, and Task agent subtypes.

## Global Concepts

### Feature Name

Most commands auto-detect the active feature from `.gsd/.current-feature`. You can override this with `--feature <name>` where supported.

### Task System

All commands integrate with Claude Code's Task system for coordination and state tracking. The Task system is the authoritative source of truth; state JSON files in `.zerg/state/` are supplementary.

### Levels

Tasks are grouped into dependency levels. All tasks in Level N must complete before any Level N+1 task begins. Within a level, tasks run in parallel.

### File Ownership

Each task exclusively owns specific files. No two tasks modify the same file, which eliminates merge conflicts during parallel execution.
