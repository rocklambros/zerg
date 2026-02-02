# /zerg:select-tool

Intelligent tool routing across MCP servers, native tools, and Task agent subtypes.

## Synopsis

```
/zerg:select-tool <task description> [--domain ui|backend|infra|docs|test|security|perf]
                                     [--format text|json|md]
                                     [--verbose]
                                     [--no-agents]
                                     [--no-mcp]
```

## Description

The `select-tool` command analyzes a task description and recommends the optimal combination of tools, MCP servers, and Task agent subtypes. It uses a multi-axis scoring system to match tasks to the most effective execution strategy.

### Scoring Axes

The command evaluates tasks across five dimensions:

| Axis | Range | What It Measures |
|------|-------|------------------|
| `file_count` | 0–1 | Number of files likely involved |
| `analysis_depth` | 0–1 | Depth of reasoning required |
| `domain` | categorical | Technical domain (ui, backend, infra, docs, test, security, perf) |
| `parallelism` | 0–1 | Opportunity for parallel execution |
| `interactivity` | 0–1 | Need for user interaction during execution |

### Recommendation Categories

Based on the composite score, the command recommends tools from three categories:

**Native Tools**: Built-in Claude Code tools (Read, Write, Edit, Grep, Glob, Bash). Recommended for simple, focused tasks.

**MCP Servers**: Specialized servers like Context7 (documentation), Sequential (analysis), Playwright (browser testing), Magic (UI), Morphllm (bulk edits), Serena (symbols). Recommended for domain-specific tasks.

**Task Agents**: Specialized subagent types (Explore, Plan, general-purpose, python-expert, etc.). Recommended for complex multi-step operations.

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `<task description>` | (required) | Free-text description of the task to route. |
| `--domain` | auto-detect | Override domain detection: `ui`, `backend`, `infra`, `docs`, `test`, `security`, `perf`. |
| `--format` | `text` | Output format: `text`, `json`, or `md`. |
| `--verbose` | off | Show per-dimension scoring breakdown. |
| `--no-agents` | off | Exclude Task agent recommendations. |
| `--no-mcp` | off | Exclude MCP server recommendations. |

## Examples

Get tool recommendations for a task:

```
/zerg:select-tool "refactor the authentication module across 12 files"
```

Force a specific domain:

```
/zerg:select-tool "optimize the query layer" --domain perf
```

See detailed scoring:

```
/zerg:select-tool "add a responsive navbar with accessibility" --verbose
```

Exclude MCP servers from recommendations:

```
/zerg:select-tool "fix the login bug" --no-mcp
```

Output as JSON for automation:

```
/zerg:select-tool "migrate database schema" --format json
```

## Error Handling

- If no task description is provided, the command reports usage instructions.
- If the domain cannot be auto-detected, it defaults to `backend` with a note.
- If MCP servers are unavailable, they are excluded from recommendations with a warning.

## Task Tracking

This command creates a Claude Code Task with the subject prefix `[Select-Tool]` on invocation, updates it to `in_progress` immediately, and marks it `completed` on success.

## See Also

- [[zerg-plugins]] -- Plugin system that extends available tools
- [[zerg-debug]] -- Deep diagnostics that select-tool may recommend
- [[zerg-analyze]] -- Analysis tools that select-tool routes to
