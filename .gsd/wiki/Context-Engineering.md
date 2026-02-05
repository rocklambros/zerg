# Context Engineering

ZERG's token optimization system for parallel workers. Reduces per-worker context usage by 30-50% while preserving the information each task needs.

---

## Token Economics 101

Before diving into technical details, let's understand *why* context engineering exists and why it matters for parallel execution.

### What Are Tokens?

Tokens are how Large Language Models (LLMs) process text. Think of them as word fragments:

- "parallel" = 1 token
- "authentication" = 1 token
- "JWT" = 1 token
- "context-engineering" = 3 tokens (context, -, engineering)

Roughly: **1 token = 0.75 words** (or about 4 characters on average).

When you send instructions to Claude, every character counts toward a token budget.

### Why Are Tokens Limited?

LLMs have a **context window** - the maximum amount of text they can "see" at once. Think of it like working memory:

| Model | Context Window |
|-------|---------------|
| Claude Sonnet 4 | 200K tokens |
| Claude Opus 4 | 200K tokens |

That sounds like a lot - about 150,000 words, or a 500-page book. So why worry?

### Why Does This Matter for ZERG?

Here's the catch: **every ZERG worker is stateless**. Each worker starts fresh with no memory of previous conversations. To do its job, every worker must load:

1. **Command instructions** - How to execute the task
2. **Security rules** - Safe coding practices for the file types involved
3. **Spec documents** - Requirements and design context
4. **Task details** - Files to create/modify, verification commands

Now multiply that by 10 parallel workers.

```
Without optimization:
  1 worker  x 25,000 tokens = 25,000 tokens
  10 workers x 25,000 tokens = 250,000 tokens (EXCEEDS context window!)

With optimization:
  1 worker  x 10,000 tokens = 10,000 tokens
  10 workers x 10,000 tokens = 100,000 tokens (fits comfortably)
```

**Context engineering is how ZERG makes parallel execution practical.**

---

## Visual Budget Overview

Here's how a worker's context budget breaks down:

```
+---------------------------------------------------------------------+
|                    WORKER CONTEXT BUDGET                            |
|                       (~128K tokens)                                |
+---------------------------------------------------------------------+
| #################### | ########## | ################################ |
|    System prompt     |   Task     |      Available for work         |
|       (~20K)         |  context   |           (~100K)               |
|                      |   (~8K)    |                                 |
+---------------------------------------------------------------------+

System prompt includes:
  - Base Claude instructions
  - ZERG command file (.core.md)
  - Security rules (filtered)
  - Project CLAUDE.md

Task context includes:
  - Spec excerpts
  - Dependency context from upstream tasks
  - Task-specific security rules
```

Every token spent on instructions is a token *not* available for actual code generation and reasoning.

---

## Why ZERG Engineers Context

Before explaining *how* context engineering works, let's be clear about *why*:

### 1. Save Money

Every token costs money. At scale:

| Scenario | Tokens/Execution | Estimated Cost |
|----------|-----------------|----------------|
| 10 workers, no optimization | 250,000 | $0.75 |
| 10 workers, with optimization | 100,000 | $0.30 |
| 50 tasks over a sprint | 5,000,000 vs 2,000,000 | $15 vs $6 |

Context engineering cuts costs by 40-60%.

### 2. Focus Workers

A worker creating Python files doesn't need Docker security rules. A worker writing tests doesn't need deployment instructions.

**Relevant context = better output.** Workers with focused, task-specific context:
- Make fewer mistakes
- Ask fewer clarifying questions
- Complete tasks faster

### 3. Prevent Confusion

When workers load everything, they sometimes get conflicting signals:
- "Use bcrypt for passwords" (from Python rules)
- "Use Web Crypto API" (from JavaScript rules)

For a Python-only task, the JavaScript guidance is noise that can confuse the worker.

### 4. Enable More Parallelism

With optimized context, you can run more workers simultaneously without hitting budget limits.

---

## The Trade-Offs

Context engineering isn't free. Here's what you're trading:

| Benefit | Trade-off |
|---------|-----------|
| Lower token usage | Workers may miss context they need |
| Faster worker startup | More complexity in design phase |
| Focused instructions | Fallback needed when filtering fails |
| More parallelism possible | Configuration required |

**The default settings balance these trade-offs for most projects.** Only adjust if you're hitting specific problems.

---

## How It Works (Three Subsystems)

Context engineering uses three complementary techniques:

```
+------------------+     +---------------------+     +------------------+
|   COMMAND        |     |   SECURITY RULE     |     |   TASK-SCOPED    |
|   SPLITTING      |     |   FILTERING         |     |   CONTEXT        |
+------------------+     +---------------------+     +------------------+
| Split large      |     | Load only rules     |     | Provide spec     |
| command files    |     | matching task's     |     | excerpts, not    |
| into core +      |     | file extensions     |     | full documents   |
| details          |     |                     |     |                  |
+------------------+     +---------------------+     +------------------+
| Saves ~2,000-    |     | Saves ~1,000-       |     | Saves ~2,000-    |
| 5,000 tokens/cmd |     | 4,000 tokens/task   |     | 5,000 tokens/    |
|                  |     |                     |     | task             |
+------------------+     +---------------------+     +------------------+
```

Combined savings: **~10,000-15,000 tokens per worker**

---

## Command Splitting

Large command files (>300 lines) are split into two parts:

| Part | What It Contains | When Loaded |
|------|------------------|-------------|
| `.core.md` | Essential workflow, critical rules | Always (by workers) |
| `.details.md` | Examples, edge cases, reference tables | On-demand (when needed) |

### Why Split?

The `worker.md` command file is ~500 lines. But most of that is reference material a worker rarely needs. By splitting:

| Version | Tokens | Use Case |
|---------|--------|----------|
| Full `worker.md` | ~4,000 | Documentation, learning |
| `worker.core.md` | ~1,200 | Normal task execution |

### Split Commands

These 10 commands are split:

| Command | Core (~30%) | Details (~70%) |
|---------|-------------|----------------|
| brainstorm | ~120 lines | ~280 lines |
| init | ~150 lines | ~350 lines |
| design | ~180 lines | ~420 lines |
| rush | ~135 lines | ~315 lines |
| plugins | ~105 lines | ~245 lines |
| debug | ~120 lines | ~280 lines |
| plan | ~105 lines | ~245 lines |
| worker | ~150 lines | ~350 lines |
| merge | ~90 lines | ~210 lines |
| status | ~105 lines | ~245 lines |

### How Splitting Works

During ZERG initialization, the `CommandSplitter` analyzes command files:

1. **Identify core content**: Sections marked with `<!-- CORE -->` or detected as essential
2. **Identify detail content**: Examples, edge cases, reference tables
3. **Generate `.core.md`**: Essential content only
4. **Generate `.details.md`**: Everything else

Run `python -m zerg.validate_commands --auto-split` to automatically split oversized files.

---

## Security Rule Filtering

ZERG detects which file types each task will create/modify, then loads only relevant security rules.

### Why Filter?

A project might have security rules for:
- Python (~3,000 tokens)
- JavaScript (~2,500 tokens)
- Docker (~3,500 tokens)
- OWASP core (~2,000 tokens)

**Total: ~11,000 tokens**

A task creating only `auth_service.py` needs:
- Python rules (~3,000 tokens)
- OWASP core (~2,000 tokens)

**Filtered: ~5,000 tokens** (55% savings)

### Filtering by Extension

| File Extension | Security Rules Loaded |
|---------------|----------------------|
| `.py` | Python security rules, OWASP core |
| `.js`, `.ts` | JavaScript security rules, OWASP core |
| `Dockerfile`, `docker-compose.yml` | Docker security rules, OWASP core |
| `.go` | Go security rules, OWASP core |
| `.rs` | Rust security rules, OWASP core |

### Budget Allocation

When assembling task context, security rules receive a portion of the total budget:

| Category | Budget Share | Typical Tokens |
|----------|-------------|----------------|
| Security Rules | ~30% | ~1,200 |
| Spec Excerpts | ~50% | ~2,000 |
| Dependency Context | ~20% | ~800 |

### Available Rule Sets

ZERG auto-fetches security rules from [TikiTribe/claude-secure-coding-rules](https://github.com/TikiTribe/claude-secure-coding-rules):

- `_core/owasp-2025.md` - OWASP Top 10 2025 core rules
- `languages/python/CLAUDE.md` - Python-specific security
- `languages/javascript/CLAUDE.md` - JavaScript/Node.js security
- `containers/docker/CLAUDE.md` - Docker security

Rules are fetched during `/zerg:init` and stored in `.claude/rules/security/`.

---

## Task-Scoped Context

Each task in `task-graph.json` includes a `context` field populated during the design phase.

### Why Task-Scoped Context?

Instead of loading full spec documents (~10,000+ tokens), workers receive relevant excerpts (~1,500-2,000 tokens).

```
Full spec approach:
  requirements.md  (~5,000 tokens)
  design.md        (~8,000 tokens)
  --------------------------------
  Total:            ~13,000 tokens (mostly irrelevant to specific task)

Task-scoped approach:
  Spec excerpt      (~1,500 tokens) - just the auth section
  Dependency context  (~500 tokens) - upstream task outputs
  --------------------------------
  Total:              ~2,000 tokens (all relevant)
```

### Context Field Structure

```json
{
  "id": "AUTH-L2-001",
  "title": "Implement JWT auth service",
  "files": {
    "create": ["src/auth/jwt_service.py"],
    "modify": [],
    "read": ["src/models/user.py"]
  },
  "context": {
    "spec_excerpt": "Authentication uses JWT with RS256 signing...",
    "dependency_context": "User model from AUTH-L1-001 exports User class with id, email, password_hash fields...",
    "security_rules": "## Password Hashing\nUse bcrypt with cost factor 12...",
    "budget_tokens": 4000
  }
}
```

### What Goes in Task Context

| Component | Source | Content |
|-----------|--------|---------|
| **Spec Excerpts** | requirements.md, design.md | Paragraphs mentioning the task's files or topic |
| **Dependency Context** | Upstream tasks (Level N-1) | Exported interfaces, types, function signatures |
| **Security Rules** | Filtered by file extensions | Relevant security patterns and rules |

### Token Budget

Default budget: **4,000 tokens** (~16,000 characters)

The context assembler prioritizes content:
1. Security rules (always included if relevant)
2. Direct spec matches (paragraphs mentioning task files)
3. Topic-related spec content (semantic similarity)
4. Dependency exports (upstream task outputs)

If content exceeds budget, lower-priority items are truncated.

---

## Configuration

Configure context engineering in `.zerg/config.yaml`:

```yaml
plugins:
  context_engineering:
    enabled: true                    # Master switch
    command_splitting: true          # Split large commands into core/details
    security_rule_filtering: true    # Filter rules by file extension
    task_context_budget_tokens: 4000 # Max tokens per task context
    fallback_to_full: true           # Fall back to full context on errors
```

### Configuration Options

| Setting | Default | Description |
|---------|---------|-------------|
| `enabled` | `true` | Enable/disable all context engineering |
| `command_splitting` | `true` | Split commands into .core.md and .details.md |
| `security_rule_filtering` | `true` | Filter security rules by task file types |
| `task_context_budget_tokens` | `4000` | Maximum tokens for task-scoped context |
| `fallback_to_full` | `true` | If context engineering fails, load full context |

### When to Adjust Settings

**Increase `task_context_budget_tokens` to 5000-6000 when:**
- Workers frequently ask for clarification
- Tasks involve multiple interconnected components
- Spec documents are highly detailed

**Decrease `task_context_budget_tokens` to 2500-3000 when:**
- Running many workers (15+) simultaneously
- Tasks are simple and focused
- Cost optimization is critical

**Disable context engineering when:**
- Debugging worker behavior
- Workers are consistently missing context
- You need to compare optimized vs full context

```yaml
plugins:
  context_engineering:
    enabled: false  # Workers load everything
```

---

## Monitoring

`/zerg:status` includes a **CONTEXT BUDGET** section:

```
CONTEXT BUDGET
  Split commands:       9/19 (47%)
  Est. token savings:   ~18,000 per worker
  Task context rate:    24/24 tasks populated (100%)
  Security filtering:   3 rule files -> 1.2 avg per task
```

### Metrics Explained

| Metric | What It Means | Good Value |
|--------|---------------|------------|
| **Split commands** | Commands with core/details splits | 40-60% |
| **Est. token savings** | Tokens saved per worker from splitting | >5,000 |
| **Task context rate** | Tasks with populated context fields | >90% |
| **Security filtering** | Ratio of rules loaded vs available | <0.5 |

### Warning Signs

| Symptom | Likely Cause | Solution |
|---------|-------------|----------|
| Task context rate < 80% | Spec docs lack structure | Add section headers to requirements.md |
| Security filtering ratio = 1.0 | No filtering happening | Check file extensions in task definitions |
| Est. token savings < 5,000 | Few commands split | Run `--auto-split` on oversized commands |

---

## Integration Points

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

### Fallback Strategy

If context engineering fails, workers fall back to full context loading. A worker with full context is better than a worker that fails.

Fallback triggers:
- Missing `.core.md` file (uses original command file)
- Empty task context field (loads full spec documents)
- Security rule filtering error (loads all rules)

---

## Best Practices

### Write Specific Task Descriptions

The more specific a task's `title` and `description`, the better spec excerpt matching works.

| Quality | Example | Context Matching |
|---------|---------|------------------|
| Good | "Implement JWT token validation middleware for Express routes" | Precise - matches auth, JWT, middleware sections |
| Vague | "Add auth middleware" | Broad - may pull unrelated auth content |

### Structure Your Spec Documents

Well-structured specs enable precise excerpt extraction:

```markdown
## Authentication Requirements

### JWT Token Handling
- Tokens use RS256 signing
- Expiration: 1 hour for access, 7 days for refresh
...

### Password Policy
- Minimum 12 characters
- bcrypt with cost factor 12
...
```

If task context rate is below 80%, add clear headers and section breaks.

### Keep Fallback Enabled

Keep `fallback_to_full: true` unless you have a specific reason to disable it. A worker that falls back to full context is better than a worker that fails because it couldn't load instructions.

---

## Troubleshooting

### Workers Missing Context

**Symptom**: Workers ask for clarification or miss requirements.

**Solutions**:
1. Increase `task_context_budget_tokens` to 5000-6000
2. Make task descriptions more specific
3. Add section headers to spec documents

### Low Task Context Rate

**Symptom**: `/zerg:status` shows task context population below 80%.

**Solutions**:
1. Add clear section headers to requirements.md and design.md
2. Ensure task titles match terminology in specs
3. Check that design phase completed successfully

### Security Rules Not Filtering

**Symptom**: Filtering ratio = 1.0 in status output.

**Solutions**:
1. Verify tasks have correct file extensions in `files.create`/`files.modify`
2. Check that security rules exist in `.claude/rules/security/`
3. Run `/zerg:init` to fetch latest security rules

### Command Splitting Not Working

**Symptom**: Workers loading full command files despite splitting enabled.

**Solutions**:
1. Run `python -m zerg.validate_commands` to check split consistency
2. Use `--auto-split` to regenerate split files
3. Verify `.core.md` files exist in `zerg/data/commands/`

---

## Summary

Context engineering makes ZERG parallel execution practical by:

1. **Splitting commands** - Workers load core instructions, not reference material
2. **Filtering security rules** - Workers see rules for their file types only
3. **Scoping task context** - Workers get spec excerpts, not full documents

Combined savings: **~60% reduction in per-worker token usage**

This enables more parallel workers, lower costs, and focused execution.

---

## See Also

- [Architecture](Architecture.md) - Overall ZERG architecture
- [Configuration](Configuration.md) - Full configuration reference
- [Security](Security.md) - Security rules and scanning
