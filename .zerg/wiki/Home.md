# ZERG Wiki

**Parallel Claude Code execution system.** Overwhelm features with coordinated zergling instances.

ZERG coordinates multiple Claude Code sessions to build features in parallel. You describe what to build, ZERG breaks the work into atomic tasks with exclusive file ownership, and multiple workers execute those tasks simultaneously -- organized by dependency levels so nothing conflicts.

---

## Navigation

| Section | Description |
|---------|-------------|
| [[Getting Started]] | Core concepts: levels, file ownership, spec-as-memory, verification |
| [[Installation]] | pip install, requirements, Claude Code setup, Docker configuration |
| [[Quick Start]] | Step-by-step first run through the full ZERG workflow |
| [[Your First Feature]] | Guided walkthrough building a real feature with ZERG |

### Reference

| Section | Description |
|---------|-------------|
| [[Command Reference]] | All `/zerg:*` slash commands with flags and examples |
| [[Architecture Overview]] | System internals: orchestrator, launcher, task graph, state management |
| [[Configuration]] | `.zerg/config.yaml` options: workers, quality gates, resources, plugins |
| [[Tuning Guide]] | Performance tuning: worker count, timeouts, resource limits |
| [[Troubleshooting]] | Common issues, error messages, and recovery procedures |
| [[Debug Guide]] | Using `/zerg:debug`, reading logs, inspecting task state |
| [[Contributing]] | Development setup, coding standards, testing, PR workflow |
| [[Testing]] | Test organization, running tests, coverage targets, writing new tests |

### Cross-Cutting Capabilities

| Capability | CLI Flags | Description |
|------------|-----------|-------------|
| Analysis Depth | `--quick/--think/--think-hard/--ultrathink` | 5-tier depth control for worker analysis |
| Token Efficiency | `--uc/--compact` | Automatic compact mode with symbol/abbreviation system |
| Behavioral Modes | `--mode` | 5 modes (precision, speed, exploration, refactor, debug) with auto-detection |
| MCP Auto-Routing | `--mcp/--no-mcp` | Capability-based MCP server selection with cost optimization |
| Engineering Rules | via config | 25 YAML rules injected into worker context by file type |
| Improvement Loops | `--loop` | Convergence-based iterative improvement cycles |
| Verification Gates | via config | Artifact storage, staleness detection, pipeline orchestration |
| TDD Enforcement | `--tdd` | Red-green-refactor protocol with anti-pattern detection |

### Plugins and Context Engineering

| Section | Description |
|---------|-------------|
| [[Plugin System]] | Overview of quality gates, lifecycle hooks, and launcher plugins |
| [[Plugin API Reference]] | Abstract base classes, dataclasses, and registry methods |
| [[Context Engineering]] | Command splitting, task-scoped context, security rule filtering |
| [[Context Engineering Internals]] | Implementation details: splitting algorithm, token budgets, fallback behavior |

---

## How ZERG Works

The workflow has four stages. Each stage requires explicit user approval before proceeding to the next.

```
Brainstorm       Plan  -->  Design  -->  Rush  -->  Merge
(optional)        |           |           |          |
    |             v           v           v          v
    v          Capture    Generate    Launch     Merge
 Discover      requirements  task      parallel   branches,
 features,     and specs    graph     workers    run quality
 create                    with file            gates
 issues                    ownership
```

**Plan.** You describe what to build. ZERG captures requirements through structured questions and writes them to a spec file.

**Design.** ZERG generates a technical architecture and breaks the work into a task graph. Each task owns specific files -- no two tasks touch the same file.

**Rush.** Multiple Claude Code instances (workers) execute tasks in parallel. Workers within the same dependency level run simultaneously. After all workers at a level finish, ZERG merges their branches before the next level begins.

**Merge.** The orchestrator merges worker branches after each level, runs quality gates (lint, typecheck, tests), and advances to the next level.

---

## Key Commands

```
/zerg:init               Initialize ZERG for a project
/zerg:brainstorm           Discover features and create issues (optional)
/zerg:plan <feature>     Capture requirements for a feature
/zerg:design             Generate architecture and task graph
/zerg:rush --workers=5   Launch parallel workers
/zerg:status             Check execution progress
/zerg:merge              Manually trigger a level merge
/zerg:stop               Stop all workers
/zerg:retry <task-id>    Retry a failed task
```

See the Command Reference page for the full list of 26 commands.

---

## Quick Links

- **First time?** Start with [[Installation]] then [[Quick Start]].
- **Understand the concepts first?** Read [[Getting Started]].
- **Ready to build something?** Jump to [[Your First Feature]].
