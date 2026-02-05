# Context Engineering

Token optimization system for ZERG parallel workers. Reduces per-worker context usage by 30-50% while preserving the information each task needs.

## Overview

When running 5-10 parallel workers, each one loads command instructions, security rules, and spec documents. Without optimization, each worker consumes 15,000-30,000 tokens on instructions alone before writing code. Multiply by 10 workers and context burns fast.

Context engineering addresses this through three subsystems (command splitting, security rule filtering, and task-scoped context):
- **Command Splitting**: Split large commands into core essentials and detailed reference
- **Security Rule Filtering**: Load only rules relevant to task file types
- **Task-Scoped Context**: Provide spec excerpts instead of full documents

## Why This Matters for Parallel Workers

ZERG workers are **stateless**. They read specs fresh each time, sharing no conversation history. This design enables crash recovery and restartability, but it means every worker must load its full instruction set independently.

| Without Optimization | With Optimization |
|---------------------|-------------------|
| Full command files (~2000 tokens each) | `.core.md` files (~600 tokens each) |
| All security rules (~8000 tokens) | Filtered rules (~2000 tokens avg) |
| Full requirements.md + design.md | Task-scoped excerpts (~1500 tokens) |
| **~25,000 tokens/worker** | **~10,000 tokens/worker** |

At 10 workers, that's 150,000 tokens saved per execution cycle.

## Command Splitting

Large command files (>300 lines) are split into two parts:

| Part | Content | Size |
|------|---------|------|
| `.core.md` | Essential instructions, behavioral flow, critical rules | ~30% of original |
| `.details.md` | Reference tables, examples, edge cases, extended options | ~70% of original |

The original command file retains core content for backward compatibility. Workers load `.core.md` by default and reference `.details.md` only when encountering situations that need it.

### Split Commands

The following 10 commands are split:

| Command | Original Lines | Core Lines | Details Lines |
|---------|---------------|------------|---------------|
| brainstorm | ~400 | ~120 | ~280 |
| init | ~500 | ~150 | ~350 |
| design | ~600 | ~180 | ~420 |
| rush | ~450 | ~135 | ~315 |
| plugins | ~350 | ~105 | ~245 |
| debug | ~400 | ~120 | ~280 |
| plan | ~350 | ~105 | ~245 |
| worker | ~500 | ~150 | ~350 |
| merge | ~300 | ~90 | ~210 |
| status | ~350 | ~105 | ~245 |

### Token Savings from Splitting

Per-worker per-command savings: **~2,000-5,000 tokens**

For a typical worker executing 3-5 commands during a task, splitting saves 6,000-25,000 tokens.

### How Splitting Works

During ZERG initialization, the `CommandSplitter` analyzes command files:

1. **Identify core content**: Sections marked with `<!-- CORE -->` or detected as essential (workflow steps, critical rules)
2. **Identify detail content**: Examples, edge cases, reference tables, extended options
3. **Generate `.core.md`**: Essential content only
4. **Generate `.details.md`**: Everything else

Run `python -m zerg.validate_commands --auto-split` to automatically split oversized files.

## Security Rule Filtering

ZERG detects which file types each task will create or modify, then loads only relevant security rules.

### Filtering by Extension

| File Extension | Security Rules Loaded |
|---------------|----------------------|
| `.py` | Python security rules, OWASP core |
| `.js`, `.ts` | JavaScript security rules, OWASP core |
| `Dockerfile`, `docker-compose.yml` | Docker security rules, OWASP core |
| `.go` | Go security rules (if available), OWASP core |
| `.rs` | Rust security rules (if available), OWASP core |

A task that only modifies Python files never sees Docker or JavaScript rules. A task creating only a Dockerfile never sees Python deserialization rules.

### Token Savings from Filtering

Per-task savings: **~1,000-4,000 tokens** depending on project rule count.

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

## Task-Scoped Context

Each task in `task-graph.json` includes a `context` field populated during the design phase.

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

### Token Savings from Task Context

Per-task savings: **~2,000-5,000 tokens** compared to loading full spec documents.

For a feature with 20 tasks, that's 40,000-100,000 tokens saved across all workers.

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

### Disabling Context Engineering

To disable entirely:

```yaml
plugins:
  context_engineering:
    enabled: false
```

Workers will load full command files, all security rules, and entire spec documents.

### Adjusting Token Budget

For complex tasks needing more context:

```yaml
plugins:
  context_engineering:
    task_context_budget_tokens: 6000
```

For maximum efficiency with simple tasks:

```yaml
plugins:
  context_engineering:
    task_context_budget_tokens: 2500
```

## Monitoring

`/zerg:status` includes a **CONTEXT BUDGET** section when context engineering is active:

```
CONTEXT BUDGET
  Split commands:       9/19 (47%)
  Est. token savings:   ~18,000 per worker
  Task context rate:    24/24 tasks populated (100%)
  Security filtering:   3 rule files -> 1.2 avg per task
```

### Metrics Explained

| Metric | What It Means |
|--------|---------------|
| **Split commands** | How many command files have core/details splits |
| **Est. token savings** | Approximate tokens saved per worker from splitting |
| **Task context rate** | Percentage of tasks with populated context fields |
| **Security filtering** | Total rule files vs. average loaded per task |

### Interpreting Metrics

**Good health indicators**:
- Split commands: 40-60% (large commands split)
- Task context rate: 90-100% (all tasks have context)
- Security filtering: ratio < 0.5 (significant filtering)

**Warning signs**:
- Task context rate < 80%: Spec documents may lack section structure
- Security filtering ratio = 1.0: No filtering happening (check file extensions)
- Est. token savings < 5,000: May not be benefiting from splitting

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

### Fallback Strategy

If context engineering fails for any reason, workers fall back to full context loading. A worker with full context is better than a worker that fails to load instructions.

Fallback triggers:
- Missing `.core.md` file (uses original command file)
- Empty task context field (loads full spec documents)
- Security rule filtering error (loads all rules)

## Best Practices

### Keep Task Descriptions Specific

The more specific a task's `title` and `description`, the better the spec excerpt matching works.

**Good**: "Implement JWT token validation middleware for Express routes"
**Vague**: "Add auth middleware"

Vague descriptions lead to broader, less efficient context excerpts.

### Use the Default Budget

4,000 tokens covers most task contexts well. Only adjust if:
- Workers are missing context they need (increase)
- Running many workers and need to minimize total usage (decrease)

### Add Structure to Spec Documents

If task context rate is below 80%, add clear headers and section breaks to `requirements.md`:

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

Well-structured specs enable precise excerpt extraction.

### Let Fallback Work

Keep `fallback_to_full: true` unless you have a specific reason to disable it. A worker that falls back to full context is better than a worker that fails because it couldn't load its instructions.

## Automated Validation

Run `python -m zerg.validate_commands` to check:

- **Split file pair consistency**: `.core.md`, `.details.md`, and parent `.md` all exist
- **Oversized unsplit files**: Files >= 300 lines without `.core.md` split
- **Task ecosystem integration**: Every command has Task tool calls

Use `--auto-split` to automatically split oversized files:

```bash
python -m zerg.validate_commands --auto-split
```

This runs in CI and as a pre-commit hook.

## Troubleshooting

### Workers missing context they need

**Symptom**: Workers ask for clarification or miss requirements.

**Solutions**:
1. Increase `task_context_budget_tokens` to 5000-6000
2. Make task descriptions more specific
3. Add section headers to spec documents

### Task context rate below 80%

**Symptom**: `/zerg:status` shows low task context population.

**Solutions**:
1. Add clear section headers to requirements.md and design.md
2. Ensure task titles match terminology in specs
3. Check that design phase completed successfully

### Security rules not filtering

**Symptom**: Filtering ratio = 1.0 in status output.

**Solutions**:
1. Verify tasks have correct file extensions in `files.create`/`files.modify`
2. Check that security rules exist in `.claude/rules/security/`
3. Run `/zerg:init` to fetch latest security rules

### Command splitting not working

**Symptom**: Workers loading full command files despite splitting enabled.

**Solutions**:
1. Run `python -m zerg.validate_commands` to check split consistency
2. Use `--auto-split` to regenerate split files
3. Verify `.core.md` files exist in `zerg/data/commands/`

## See Also

- [Architecture](Architecture.md) - Overall ZERG architecture
- [Configuration](Configuration.md) - Full configuration reference
- [Security](Security.md) - Security rules and scanning
