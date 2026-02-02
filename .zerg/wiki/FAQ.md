# FAQ

Frequently asked questions about ZERG. Questions are grouped by topic.

---

## General

### What is ZERG?

ZERG is a parallel execution system for Claude Code. It coordinates multiple Claude Code instances (workers) to build features concurrently. You describe what to build, ZERG breaks the work into tasks with exclusive file ownership, and workers execute those tasks in parallel across dependency levels.

### How is ZERG different from just running Claude Code?

A single Claude Code session executes tasks sequentially. ZERG launches multiple sessions that work on different parts of a feature simultaneously. A feature that takes 3 hours with one session might take 1 hour with 3 parallel workers. ZERG handles the coordination: splitting work, preventing file conflicts, merging results, and running quality checks.

### What does the name mean?

ZERG references the "Zerg rush" strategy from StarCraft -- overwhelming an objective with many coordinated units. In ZERG's case, the units are Claude Code instances (called workers or zerglings) and the objective is a feature implementation.

### Do I need Docker to use ZERG?

No. The default execution mode (subprocess) runs workers as local processes. Docker is only required for container mode (`--mode container`), which provides additional isolation.

---

## Setup and Requirements

### What are the prerequisites?

- Claude Code installed and authenticated
- Python 3.10 or later
- Git initialized in your project
- An `ANTHROPIC_API_KEY` or active Claude Pro/Team OAuth session

See [[Installation]] for full setup instructions.

### How do I install ZERG?

```bash
pip install zerg
```

Then initialize your project:

```
/zerg:init
```

See [[Installation]] for detailed steps.

### Does ZERG work with any programming language?

Yes. ZERG is language-agnostic. It coordinates Claude Code sessions and manages git branches. The workers themselves can generate code in any language that Claude Code supports. Quality gates and verification commands in your configuration should match your project's toolchain.

---

## Workflow

### What is the typical workflow?

Four stages, each requiring explicit approval:

0. **Brainstorm** (`/zerg:brainstorm`) -- (Optional) Discover features through competitive research and Socratic questioning.
1. **Plan** (`/zerg:plan <feature>`) -- Capture requirements through interactive questions.
2. **Design** (`/zerg:design`) -- Generate architecture and task graph.
3. **Rush** (`/zerg:rush --workers=N`) -- Execute tasks in parallel.
4. **Merge** (automatic or `/zerg:merge`) -- Merge branches and run quality gates.

See [[Quick Start]] for a step-by-step walkthrough.

### Can I skip the plan phase?

The plan phase produces `requirements.md`, which the design phase reads. If you already have a requirements document or want to write one manually, you can place it at `.gsd/specs/<feature>/requirements.md` and proceed directly to `/zerg:design`. The file should follow the format described in [[zerg-plan]].

### How do I resume an interrupted rush?

```
/zerg:rush --resume
```

The `--resume` flag calls `TaskList` first and only creates tasks that do not already exist. Workers pick up from where they left off.

### How many workers should I use?

Start with the maximum parallelization reported by `/zerg:design`. Using more workers than tasks at the widest level provides no benefit. For most features, 3 to 5 workers is practical. Consider your API rate limits and system resources when choosing.

See [[Tuning Guide]] for detailed guidance.

### What happens if a worker fails?

The failed task is marked in both the Claude Code Task system and the state JSON. Other workers at the same level continue unaffected. You can retry the failed task with `/zerg:retry <task-id>`. The orchestrator will not advance to the next level until all tasks at the current level succeed.

### Can I modify the task graph after design?

Yes. The task graph is a JSON file at `.gsd/specs/<feature>/task-graph.json`. You can edit it directly to adjust file ownership, change verification commands, or reorder dependencies. After editing, run `/zerg:rush --resume` to apply changes.

Be careful with file ownership -- every file must be owned by exactly one task per level, or merge conflicts will occur.

---

## Architecture

### How does ZERG prevent merge conflicts?

Through **file ownership**. The design phase assigns every file to exactly one task per level. No two workers modify the same file simultaneously. After all tasks at a level complete, branches are merged. Since each branch touched different files, the merge is conflict-free.

See [[Getting Started#file-ownership]] for details.

### What is a "level"?

A level is a group of tasks that can execute in parallel because none depend on each other. Level 1 tasks have no dependencies. Level 2 tasks depend on Level 1, and so on. All tasks at level N must complete and merge before level N+1 begins.

See [[Getting Started#levels]].

### What is "spec as memory"?

Workers do not share conversation history. Instead, they read spec files (requirements, design, task graph) to understand their assignments. This makes workers stateless and restartable -- if a worker crashes, it can be relaunched and it will read the same spec files.

See [[Getting Started#spec-as-memory]].

### What is the Task system and why does it matter?

The Claude Code Task system (`TaskCreate`, `TaskUpdate`, `TaskList`, `TaskGet`) is the authoritative source of truth for task state in ZERG. Tasks persist in `~/.claude/tasks/` and survive session restarts. Workers claim tasks, report progress, and signal completion through this system. Without it, parallel workers could not coordinate.

See [[Getting Started#the-task-ecosystem]].

---

## Quality and Verification

### What are quality gates?

Quality gates are validation commands that run after each level merge. They are defined in `.zerg/config.yaml` and typically include linting, type checking, and tests. Required gates must pass before the next level begins. Non-required gates log warnings without blocking progress.

See [[Configuration#quality_gates]].

### What happens when a quality gate fails?

Execution pauses at the current level. The status dashboard shows which gate failed and its error output. You can fix the issue manually and then run `/zerg:merge` to retry. Alternatively, use `/zerg:retry <task-id>` to re-run a specific task that produced the failing code.

### How are tasks verified?

Every task includes a verification command -- a shell command that exits with code 0 on success and non-zero on failure. Workers run the verification command after finishing their work. Good verification commands test behavior (run tests, check types) rather than just syntax (compile check).

See [[Getting Started#verification]].

---

## Container Mode

### When should I use container mode?

Container mode is useful when you need:

- Filesystem isolation between workers
- Reproducible build environments
- Multi-user scenarios where workers should not share the host filesystem

For local development with a single user, subprocess mode (the default) is simpler.

See [[Tutorial-Container-Mode]].

### How do containers authenticate?

Two methods:

| Method | Mechanism | Best for |
|--------|-----------|----------|
| OAuth | Mounts `~/.claude` into the container | Claude Pro/Team accounts |
| API Key | Passes `ANTHROPIC_API_KEY` as an environment variable | API key accounts |

See [[Troubleshooting#docker-and-container-issues]] for common authentication problems.

---

## Context Engineering

### What is context engineering?

A system of optimizations that reduces token usage per worker by providing only the context relevant to each task. It has three subsystems: command splitting (loads smaller command files), task-scoped context (extracts relevant spec paragraphs), and security rule filtering (loads only applicable security rules).

See [[Context Engineering]].

### How much does context engineering save?

Estimated savings are 2,000 to 5,000 tokens per worker, depending on spec size and task complexity. Use `/zerg:status` to view the CONTEXT BUDGET section for actual savings in your project.

### Can I disable context engineering?

Yes. Set `plugins.context_engineering.enabled: false` in `.zerg/config.yaml`. Workers will load full, unscoped context. You can also disable individual subsystems while keeping the others active.

See [[Context Engineering#disabling-context-engineering]].

---

## Troubleshooting

### Workers launch but immediately exit

The most common cause is missing spec files. Verify that `.gsd/specs/<feature>/task-graph.json` exists and is valid JSON. Check worker logs at `.zerg/logs/worker-*.stderr.log` for the specific error.

See [[Troubleshooting#workers-not-starting]].

### I get "port already in use" errors

A previous ZERG run may not have cleaned up. Run `/zerg:stop` to terminate workers, then `/zerg:cleanup` to release resources. You can also expand the port range in `.zerg/config.yaml`.

See [[Troubleshooting#port-conflicts]].

### How do I clean up after a rush?

```
/zerg:cleanup
```

This removes worktrees, worker branches, and temporary state files. Your feature code remains on the `zerg/<feature>/base` branch.

### Where are the logs?

Worker logs are in `.zerg/logs/`. Each worker produces stdout and stderr log files. The orchestrator also writes to this directory. Use `/zerg:logs` to view logs or `/zerg:debug` for structured diagnostics.

See [[zerg-logs]], [[Debug Guide]].

---

## See Also

- [[Getting Started]] -- Core concepts explained
- [[Quick Start]] -- Step-by-step first run
- [[Troubleshooting]] -- Detailed problem resolution
- [[Glossary]] -- Definitions of all ZERG terms
