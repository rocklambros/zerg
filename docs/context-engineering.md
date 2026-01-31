# Context Engineering

ZERG's context engineering plugin minimizes token usage across parallel workers. Instead of every worker loading the full set of command files, security rules, and spec documents, ZERG scopes context to what each task actually needs.

---

## Table of Contents

- [Why Context Engineering Matters](#why-context-engineering-matters)
- [Three Subsystems](#three-subsystems)
  - [Command Splitting](#command-splitting)
  - [Security Rule Filtering](#security-rule-filtering)
  - [Task-Scoped Context](#task-scoped-context)
- [Configuration](#configuration)
- [Monitoring](#monitoring)
- [How It Integrates](#how-it-integrates)

---

## Why Context Engineering Matters

Claude Code has a finite context window. When you run 5-10 parallel workers, each one loads:
- Command instructions (~500-2000 tokens per command file)
- Security rules (~3000-8000 tokens depending on stack)
- Spec documents (requirements.md, design.md, task-graph.json)
- CLAUDE.md project instructions

Without optimization, each worker might consume 15,000-30,000 tokens on instructions alone before writing a single line of code. Multiply that by 10 workers and you're burning through context at scale.

Context engineering reduces this overhead by 30-50% per worker while preserving the information each task actually needs.

---

## Three Subsystems

### Command Splitting

Large command files (>300 lines) are split into two parts:

| Part | Content | Size |
|------|---------|------|
| `.core.md` | Essential instructions, behavioral flow, critical rules | ~30% of original |
| `.details.md` | Reference tables, examples, edge cases, extended options | ~70% of original |

The original command file retains core content for backward compatibility. Workers load `.core.md` by default and reference `.details.md` only when they encounter situations that need it.

**Split commands** (9 total): init, design, rush, plugins, debug, plan, worker, merge, status.

**Token savings**: ~2,000-5,000 tokens per worker per command invocation.

### Security Rule Filtering

ZERG detects which file types each task will create or modify, then loads only the relevant security rules:

| File Extension | Security Rules Loaded |
|---------------|----------------------|
| `.py` | Python security rules, OWASP core |
| `.js`, `.ts` | JavaScript security rules, OWASP core |
| `Dockerfile`, `docker-compose.yml` | Docker security rules, OWASP core |
| `.go` | Go security rules (if available), OWASP core |
| `.rs` | Rust security rules (if available), OWASP core |

A task that only modifies Python files never sees Docker or JavaScript rules. A task that only creates a Dockerfile never sees Python deserialization rules.

**Token savings**: ~1,000-4,000 tokens per task depending on how many rule files your project has.

### Task-Scoped Context

Each task in `task-graph.json` can include a `context` field populated during the design phase:

```json
{
  "id": "AUTH-L2-001",
  "title": "Implement JWT auth service",
  "context": {
    "spec_excerpt": "Authentication uses JWT with RS256...",
    "dependency_context": "User model from AUTH-L1-001 exports...",
    "security_rules": "## Password Hashing\n...",
    "budget_tokens": 4000
  }
}
```

Instead of workers loading the entire `requirements.md` (often 2,000+ tokens) and `design.md` (often 5,000+ tokens), they receive a scoped excerpt relevant to their specific task.

**Components of task context**:
- **Spec excerpts**: Paragraphs from requirements.md and design.md that mention the task's files or topic
- **Dependency context**: Exported interfaces and types from upstream tasks (Level N-1)
- **Security rules**: Filtered by the task's file extensions
- **Budget enforcement**: Total context stays within the configured token budget (default: 4,000)

**Token savings**: ~2,000-5,000 tokens per task compared to loading full specs.

---

## Configuration

```yaml
# .zerg/config.yaml
plugins:
  context_engineering:
    enabled: true                    # Master switch
    command_splitting: true          # Split large commands into core/details
    security_rule_filtering: true    # Filter rules by file extension
    task_context_budget_tokens: 4000 # Max tokens per task context
    fallback_to_full: true           # Fall back to full context on errors
```

| Setting | Default | Description |
|---------|---------|-------------|
| `enabled` | `true` | Enable/disable all context engineering |
| `command_splitting` | `true` | Split commands into .core.md and .details.md |
| `security_rule_filtering` | `true` | Filter security rules by task file types |
| `task_context_budget_tokens` | `4000` | Maximum tokens for task-scoped context |
| `fallback_to_full` | `true` | If context engineering fails, load full context |

### Disabling

To disable context engineering entirely:

```yaml
plugins:
  context_engineering:
    enabled: false
```

Workers will load full command files, all security rules, and entire spec documents — the same behavior as ZERG without the plugin.

---

## Monitoring

`/zerg:status` includes a **CONTEXT BUDGET** section when context engineering is active:

```
CONTEXT BUDGET
  Split commands:       9/19 (47%)
  Est. token savings:   ~18,000 per worker
  Task context rate:    24/24 tasks populated (100%)
  Security filtering:   3 rule files → 1.2 avg per task
```

| Metric | What It Means |
|--------|---------------|
| **Split commands** | How many command files have core/details splits |
| **Est. token savings** | Approximate tokens saved per worker from splitting |
| **Task context rate** | Percentage of tasks with populated context fields |
| **Security filtering** | Total rule files vs. average loaded per task |

---

## How It Integrates

### During `/zerg:design`

The design phase populates task context:

1. Parse `requirements.md` and `design.md` into sections
2. For each task in the task graph:
   - Match spec sections to the task's title, description, and file list
   - Extract relevant paragraphs within the token budget
   - Identify upstream task outputs (types, interfaces, exports)
   - Filter security rules by the task's file extensions
3. Write the `context` field into `task-graph.json`

### During `/zerg:rush`

The orchestrator passes task context to workers:

1. Worker receives task assignment with context field
2. Worker loads `.core.md` version of command instructions
3. Worker loads task-scoped security rules (not all rules)
4. Worker loads task context excerpt (not full spec files)
5. If any context loading fails and `fallback_to_full: true`, worker loads full files

### During `/zerg:status`

Status reads context engineering metrics from:
- Split command file counts in `zerg/data/commands/`
- Task context population from `task-graph.json`
- Security rule filtering stats from the plugin registry

---

## Best Practices

**Keep task descriptions specific.** The more specific a task's `title` and `description`, the better the spec excerpt matching works. Vague descriptions lead to broader (less efficient) context excerpts.

**Use the default budget.** 4,000 tokens covers most task contexts well. Increase it only if workers are missing context they need. Decrease it only if you're running many workers and need to minimize total token usage.

**Monitor the context rate.** If the "Task context rate" in `/zerg:status` shows less than 80% populated, your spec documents may not have enough section structure for effective matching. Adding headers and clear section breaks to requirements.md helps.

**Let fallback work.** Keep `fallback_to_full: true` unless you have a specific reason to disable it. A worker that falls back to full context is better than a worker that fails because it couldn't load its instructions.
