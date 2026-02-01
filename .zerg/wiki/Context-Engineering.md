# Context Engineering

ZERG includes a context engineering system that minimizes token usage across workers. Each Claude Code worker has a finite context window. By giving each worker only the context relevant to its task -- rather than loading the full spec and all security rules -- ZERG reduces per-worker token consumption by an estimated 2,000 to 5,000 tokens.

The system has three subsystems: command splitting, task-scoped context, and security rule filtering. For implementation details, see [[Context Engineering Internals]].

---

## Why Context Engineering Matters

Each ZERG worker is a Claude Code session that receives:

1. The task description and verification command from task-graph.json.
2. Feature specs (requirements.md, design.md).
3. Security rules relevant to the project.
4. The command file for the current operation.

Without context engineering, every worker loads the full spec files and all security rules regardless of what the task actually needs. For a project with 3,000 tokens of specs and 2,000 tokens of security rules, that is 5,000 tokens of context per worker -- most of which is irrelevant to any individual task.

Context engineering solves this by scoping each piece of context to the specific task.

---

## Subsystem 1: Command Splitting

Large command files (those exceeding 300 lines) are split into two parts:

| File | Content | Size |
|------|---------|------|
| `{command}.core.md` | Essential instructions needed for every invocation | ~30% of original |
| `{command}.details.md` | Extended examples, templates, and edge cases | ~70% of original |

Workers load the `.core.md` file by default. The `.details.md` content is loaded on demand only when the worker needs reference material.

### Currently Split Commands

The following 10 command files have been split:

| Command | Core File | Details File |
|---------|-----------|-------------|
| `zerg:init` | `zerg:init.core.md` | `zerg:init.details.md` |
| `zerg:design` | `zerg:design.core.md` | `zerg:design.details.md` |
| `zerg:rush` | `zerg:rush.core.md` | `zerg:rush.details.md` |
| `zerg:plugins` | `zerg:plugins.core.md` | `zerg:plugins.details.md` |
| `zerg:debug` | `zerg:debug.core.md` | `zerg:debug.details.md` |
| `zerg:plan` | `zerg:plan.core.md` | `zerg:plan.details.md` |
| `zerg:worker` | `zerg:worker.core.md` | `zerg:worker.details.md` |
| `zerg:merge` | `zerg:merge.core.md` | `zerg:merge.details.md` |
| `zerg:status` | `zerg:status.core.md` | `zerg:status.details.md` |
| `zerg:brainstorm` | `zerg:brainstorm.core.md` | `zerg:brainstorm.details.md` |

The original `.md` file is preserved with core content plus a reference comment pointing to the details file. This maintains backward compatibility with existing symlinks.

---

## Subsystem 2: Task-Scoped Context

Each task in `task-graph.json` can receive scoped context instead of the full feature spec. The context engineering plugin extracts only the sections relevant to the task's files and description.

### How Scoping Works

1. **Keyword extraction.** The plugin parses the task's title, description, and file paths to build a keyword set.
2. **Section matching.** The plugin searches requirements.md and design.md for paragraphs containing those keywords.
3. **Relevance ranking.** Matching paragraphs are scored by keyword density and the top 5 are selected.
4. **Token budgeting.** The selected content is truncated to fit within the configured token budget.

### Example

Given a task that creates `zerg/auth_middleware.py` with the description "Implement JWT authentication middleware":

- Keywords extracted: `implement`, `authentication`, `middleware`, `auth`
- Relevant spec sections: paragraphs mentioning "authentication", "middleware", "JWT"
- Irrelevant sections (skipped): database schema, frontend routing, deployment config

The worker receives a focused context of 500-1,500 tokens instead of the full 3,000-token spec.

### Budget Allocation

The default token budget for task context is 4,000 tokens, allocated as:

| Component | Budget Share | Purpose |
|-----------|:-----------:|---------|
| Security rules | 30% (1,200 tokens) | Filtered rules relevant to task files |
| Spec excerpts | 50% (2,000 tokens) | Relevant paragraphs from requirements and design |
| Buffer | 20% (800 tokens) | Overhead and formatting |

---

## Subsystem 3: Security Rule Filtering

Instead of loading all project security rules into every worker, the context engineering plugin filters rules by file extension.

### Filtering Logic

| Task File Extension | Rules Loaded |
|--------------------|--------------|
| `.py`, `.pyx`, `.pyi` | `_core/owasp-2025.md` + `languages/python/CLAUDE.md` |
| `.js`, `.mjs`, `.ts`, `.tsx`, `.jsx` | `_core/owasp-2025.md` + `languages/javascript/CLAUDE.md` |
| `Dockerfile`, `docker-compose.*` | `_core/owasp-2025.md` + `containers/docker/CLAUDE.md` |
| Mixed extensions | Union of all matching rule sets |

Rules are summarized (headers and level indicators only, code blocks stripped) to fit within the security budget.

A task that only touches Python files will not receive JavaScript or Docker security rules. This typically saves 1,000-3,000 tokens per worker.

---

## Configuration

All context engineering settings are under `plugins.context_engineering` in `.zerg/config.yaml`:

```yaml
plugins:
  context_engineering:
    enabled: true
    command_splitting: true
    security_rule_filtering: true
    task_context_budget_tokens: 4000
    fallback_to_full: true
```

| Option | Type | Default | Range | Description |
|--------|------|---------|-------|-------------|
| `enabled` | bool | `true` | -- | Master switch for the context engineering plugin |
| `command_splitting` | bool | `true` | -- | Use `.core.md` files when available |
| `security_rule_filtering` | bool | `true` | -- | Filter security rules by task file extensions |
| `task_context_budget_tokens` | int | `4000` | 500-20000 | Maximum tokens for per-task context |
| `fallback_to_full` | bool | `true` | -- | On error, fall back to loading full/unscoped context |

### When to Adjust the Token Budget

| Scenario | Recommended Budget | Reasoning |
|----------|-------------------:|-----------|
| Small spec, few files | 2000 | Less content to scope; lower budget avoids waste |
| Medium spec, typical tasks | 4000 | Default; good balance |
| Large spec, complex tasks | 6000-8000 | Tasks need more context to understand requirements |
| Very large spec (10k+ tokens) | 10000-15000 | Prevents excessive truncation |

---

## Monitoring

Use `/zerg:status` to view the CONTEXT BUDGET section, which shows:

- **Split command count** -- number of commands using `.core.md` files and estimated token savings.
- **Per-task context population** -- percentage of tasks that received scoped context vs. full context.
- **Security rule filtering** -- which rule files were loaded and how many tokens each consumed.

---

## Disabling Context Engineering

To disable the entire system and have workers load full context:

```yaml
plugins:
  context_engineering:
    enabled: false
```

To disable individual subsystems:

```yaml
plugins:
  context_engineering:
    enabled: true
    command_splitting: false         # Use full command files
    security_rule_filtering: false   # Load all security rules
```

---

## See Also

- [[Context Engineering Internals]] -- Implementation details: splitting algorithm, token estimation, fallback behavior
- [[Configuration]] -- Full YAML reference
- [[Tuning Guide]] -- Performance tuning guidance
- [[Plugin System]] -- How context engineering fits into the plugin architecture
