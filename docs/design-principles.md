# Design Principles

## Core Constraint: Context Management

Every ZERG feature must prioritize context management and minimize token utilization. This is not a suggestion — it is the primary design constraint that shapes all architectural decisions.

Workers (parallel Claude Code instances) have finite context windows. Every unnecessary token loaded into a worker reduces its capacity for actual work. ZERG's architecture exists to solve this problem.

## Token Budget Guidelines

| Component | Budget | Rationale |
|-----------|--------|-----------|
| Task-scoped context | ~4,000 tokens | Per-task context in task-graph.json replaces loading full spec files |
| Command core file | ~30% of total | Essential instructions only — workflow, flags, task tracking |
| Command details file | ~70% of total | Reference material — templates, schemas, examples |
| Security rules | Filtered by file type | .py workers get Python rules only, not JS or Docker |

## Architectural Principles

### 1. Spec-as-Memory

Workers read spec files (`requirements.md`, `design.md`, `task-graph.json`), not conversation history. This makes workers stateless and restartable. If a worker crashes, another can pick up the same task from the same spec files.

### 2. Command Splitting

Command files over 300 lines are split into `.core.md` and `.details.md`. Workers receive only the core file by default. The details file is loaded on-demand when reference material is needed. Currently 10 commands are split: brainstorm, init, design, rush, plugins, debug, plan, worker, merge, status.

### 3. Task-Scoped Context

Each task in `task-graph.json` includes a `context` field with:

- Relevant spec excerpts (not the full spec)
- Security rules filtered by the task's file extensions
- Dependency summaries from upstream tasks

This replaces loading full spec files into every worker, saving 2,000-5,000 tokens per task.

### 4. Security Rule Filtering

Instead of loading all security rules into every worker, ZERG filters by file extension:

- `.py` files get Python security rules
- `.js`/`.ts` files get JavaScript rules
- `Dockerfile` gets Docker rules
- All workers get OWASP core rules

### 5. File Ownership

Each task owns specific files exclusively. No two tasks modify the same file. This eliminates merge conflicts by design and allows maximum parallelization without coordination overhead.

### 6. Level-Based Execution

Tasks are grouped into levels by dependency. All tasks in Level N must complete before any task in Level N+1 begins. Within a level, all tasks run in parallel.

## Anti-Patterns

These patterns violate ZERG's design principles. Avoid them.

| Anti-Pattern | Why It's Wrong | Do This Instead |
|-------------|----------------|-----------------|
| Loading full spec files into workers | Wastes 5,000+ tokens on irrelevant content | Use task-scoped context field |
| Unbounded WebSearch queries | Unpredictable token consumption | Scope to 3-5 targeted queries, cache results |
| Reading entire files when searching | Wastes tokens on irrelevant lines | Use Grep/Glob tools for targeted search |
| Loading all security rules | Most rules irrelevant to specific file types | Filter by file extension |
| Single monolithic command files | 500+ line files consume full context | Split into .core.md + .details.md |
| Workers loading conversation history | Non-deterministic, unreproducible | Workers read specs only (spec-as-memory) |

## Further Reading

- [Context Engineering Guide](context-engineering.md) — Implementation details for all three subsystems
- [ARCHITECTURE.md](../ARCHITECTURE.md) — System architecture overview
- [CLAUDE.md](../CLAUDE.md) — Claude Code integration and task ecosystem rules
