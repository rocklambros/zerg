<!-- SPLIT: details, parent: select-tool.md -->

# ZERG Select Tool — Details Reference

## Scoring Formulas

Five axes scored 0.0–1.0, combined into a composite for tool selection.

### File Count (weight: 0.20)

| Files | Score | Keyword Triggers |
|-------|-------|------------------|
| 1 | 0.1 | "this file", "single file", "one file" |
| 2–3 | 0.3 | "a couple files", "these files" |
| 4–5 | 0.5 | "several files", "multiple files" |
| 6–10 | 0.7 | "across files", "many files" |
| 10+ | 0.9 | "project-wide", "all files", "entire codebase" |

### Analysis Depth (weight: 0.30)

| Depth | Score | Keyword Triggers |
|-------|-------|------------------|
| Shallow | 0.2 | "read", "check", "list", "show", "print" |
| Medium | 0.5 | "find", "search", "trace", "follow", "locate" |
| Deep | 0.8 | "debug", "analyze", "architect", "redesign", "root cause", "investigate" |

### Domain (weight: 0.20)

| Domain | Score | Keyword Triggers |
|--------|-------|------------------|
| Config/docs | 0.2 | "config", "documentation", "readme", "yaml", "toml" |
| Backend/API | 0.5 | "api", "endpoint", "server", "route", "handler", "database" |
| UI | 0.8 | "component", "form", "button", "modal", "responsive", "layout" |
| Security | 0.8 | "vulnerability", "auth", "injection", "CVE", "permissions" |
| Performance | 0.8 | "slow", "optimize", "latency", "memory", "profil" |

### Parallelism (weight: 0.15)

| Pattern | Score | Keyword Triggers |
|---------|-------|------------------|
| Sequential | 0.1 | "this function", "this line", "single" |
| Some parallel | 0.4 | "a few", "some files", "module" |
| Highly parallel | 0.8 | "each", "every", "all files", "batch", "project-wide" |

### Interactivity (weight: 0.15)

| Level | Score | Keyword Triggers |
|-------|-------|------------------|
| Non-interactive | 0.1 | "check", "lint", "validate", "parse" |
| Some input | 0.4 | "confirm", "prompt", "choose" |
| Browser/visual | 0.8 | "click", "browse", "screenshot", "form", "login flow", "E2E" |

### Composite Formula

```
composite = (file × 0.20) + (depth × 0.30) + (domain × 0.20) + (parallel × 0.15) + (interactive × 0.15)
```

---

## Tool Capability Matrix

### MCP Servers

| Server | Best For | Triggers | Score Range | Fallback |
|--------|----------|----------|-------------|----------|
| Context7 | Library docs, framework patterns | imports, "latest", version-specific | 0.3–0.6 | WebSearch |
| Sequential | Complex debugging, architecture | multi-component, hypothesis testing | 0.5–0.8 | Native reasoning |
| Magic | UI components, design system | `/ui`, responsive, accessible | 0.4–0.7 | Manual coding |
| Morphllm | Bulk edits, pattern enforcement | multi-file, rename, style guide | 0.5–0.7 | Individual Edit |
| Serena | Symbol ops, project memory | rename symbol, references, LSP | 0.4–0.7 | Manual search |
| Playwright | Browser testing, E2E, visual | login flow, form test, screenshot | 0.6–0.9 | Unit tests |

### Native Tools

| Tool | Best For | Score Range |
|------|----------|-------------|
| Read / Glob / Grep | File exploration, code search | 0.0–0.3 |
| Edit / Write | File modification | 0.0–0.3 |
| Task (Explore) | Codebase understanding | 0.2–0.4 |
| Task (Plan) | Implementation design | 0.4–0.6 |
| Task (general-purpose) | Complex multi-step operations | 0.6+ |
| WebSearch / WebFetch | Current info, external docs | 0.2–0.5 |

### Task Agent Subtypes

| Agent | Best For | Composite | Domain Fit |
|-------|----------|-----------|------------|
| Explore | Quick codebase understanding | 0.2–0.4 | any |
| Plan | Implementation design | 0.4–0.6 | any |
| general-purpose | Complex multi-step | 0.6+ | any |
| feature-dev:code-architect | Feature design | 0.7+ | backend |
| feature-dev:code-reviewer | Code review | 0.5+ | any (depth=high) |
| quality-engineer | Testing strategy | 0.5+ | test |
| security-engineer | Security audit | 0.6+ | security |
| performance-engineer | Perf optimization | 0.6+ | perf |
| refactoring-expert | Code cleanup | 0.5+ | any (files=high) |

---

## Tier Mapping

| Composite | Tier | Recommendation |
|-----------|------|----------------|
| 0.0–0.3 | Native | Read, Grep, Edit, Write sufficient |
| 0.3–0.6 | Single Tool | One MCP server or one Task agent |
| 0.6–0.8 | Combination | MCP server + Task agent recommended |
| 0.8–1.0 | Full Stack | Multi-MCP + delegation (`--delegate`) |

---

## Fallback Chains

When a preferred tool is unavailable, degrade gracefully:

| Primary | Fallback 1 | Fallback 2 |
|---------|-----------|-----------|
| Context7 | WebSearch | Native knowledge |
| Sequential | Native reasoning (extended thinking) | — |
| Magic | Manual frontend coding | — |
| Morphllm | Individual Edit calls | — |
| Serena | Grep + manual search | — |
| Playwright | Unit tests + manual verification | — |

---

## Config Schema

MCP server capabilities in `.zerg/config.yaml`:

```yaml
mcp_servers:
  context7:
    enabled: true
    capabilities: [documentation, patterns, version-lookup]
    domains: [frontend, backend, devops]
  sequential:
    enabled: true
    capabilities: [analysis, debugging, architecture]
    domains: [any]
  magic:
    enabled: true
    capabilities: [ui-generation, design-system]
    domains: [frontend, ui]
  morphllm:
    enabled: true
    capabilities: [bulk-edit, pattern-enforcement, style]
    domains: [any]
  serena:
    enabled: true
    capabilities: [symbol-ops, project-memory, lsp]
    domains: [any]
  playwright:
    enabled: true
    capabilities: [browser-test, e2e, visual, accessibility]
    domains: [frontend, testing]
```

> **Note**: If config uses a simple string list (`mcp_servers: [context7, sequential]`), the selector applies hardcoded capability defaults matching the table above.

---

## Verbose Output Format

When `--verbose` is passed, the scoring breakdown is displayed:

```
╔══════════════════════════════════════════════╗
║          TOOL SELECTION SCORING              ║
╠══════════════════════════════════════════════╣
║ Task: "debug the authentication flow"        ║
╠──────────────┬───────┬────────┬─────────────╣
║ Axis         │ Raw   │ Weight │ Weighted    ║
╠──────────────┼───────┼────────┼─────────────╣
║ File Count   │  0.3  │  0.20  │  0.060      ║
║ Depth        │  0.8  │  0.30  │  0.240      ║
║ Domain       │  0.8  │  0.20  │  0.160      ║
║ Parallelism  │  0.1  │  0.15  │  0.015      ║
║ Interactivity│  0.1  │  0.15  │  0.015      ║
╠──────────────┴───────┴────────┼─────────────╣
║ COMPOSITE                     │  0.490      ║
╠───────────────────────────────┼─────────────╣
║ TIER                          │ Single Tool ║
╠═══════════════════════════════╧═════════════╣
║ Recommendations:                             ║
║  1. Sequential (analysis + debugging)        ║
║  2. Task:Explore (codebase understanding)    ║
║ Fallback: Native reasoning                   ║
╚══════════════════════════════════════════════╝
```

---

## Worked Examples

### Example 1: "debug the authentication flow in the API"

| Axis | Value | Rationale |
|------|-------|-----------|
| File Count | 0.3 | "flow" implies 2–3 files (handler, middleware, model) |
| Depth | 0.8 | "debug" → deep analysis |
| Domain | 0.8 | "authentication" → security domain |
| Parallelism | 0.1 | Sequential investigation required |
| Interactivity | 0.1 | Non-interactive code analysis |

**Composite**: `(0.3×0.2)+(0.8×0.3)+(0.8×0.2)+(0.1×0.15)+(0.1×0.15)` = **0.49**
**Tier**: Single Tool → **Sequential** (debugging + architecture analysis)
**Fallback**: Native reasoning with extended thinking

### Example 2: "update all React components to use hooks"

| Axis | Value | Rationale |
|------|-------|-----------|
| File Count | 0.9 | "all components" → 10+ files |
| Depth | 0.5 | "update" → medium (pattern transformation) |
| Domain | 0.8 | "React components" → UI domain |
| Parallelism | 0.8 | "all" → highly parallelizable |
| Interactivity | 0.1 | Non-interactive code transform |

**Composite**: `(0.9×0.2)+(0.5×0.3)+(0.8×0.2)+(0.8×0.15)+(0.1×0.15)` = **0.62**
**Tier**: Combination → **Morphllm** (bulk pattern edit) + **Context7** (React hook patterns)
**Fallback**: Individual Edit calls + native React knowledge

### Example 3: "test the login form in the browser"

| Axis | Value | Rationale |
|------|-------|-----------|
| File Count | 0.1 | "the login form" → single target |
| Depth | 0.5 | "test" → medium investigation |
| Domain | 0.8 | "login form" → UI + security |
| Parallelism | 0.1 | Sequential browser interaction |
| Interactivity | 0.8 | "browser", "login form" → high interactivity |

**Composite**: `(0.1×0.2)+(0.5×0.3)+(0.8×0.2)+(0.1×0.15)+(0.8×0.15)` = **0.47**
**Tier**: Single Tool → **Playwright** (browser automation + E2E)
**Fallback**: Unit tests + manual verification

---

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| No MCP servers configured | Recommend native tools only; tier capped at Native/Single Tool (Task agents) |
| `--no-agents` + `--no-mcp` | Only native tools (Read, Grep, Edit, Write, WebSearch) |
| Ambiguous domain | Default to `backend` (score 0.5); add note: "domain uncertain — override with `--focus`" |
| Empty task description | Error in pre-flight: "Task description required for scoring" |
| All axes score low (<0.15) | Suggest direct native tool usage without formal selection |
| Conflicting signals | Higher-weight axis wins; depth (0.30) dominates ties |

---

## Task Tracking

All `/zerg:select-tool` invocations are tracked via the Claude Code Task ecosystem:

```
TaskCreate  → subject: "[Select] Tool selection: {task_summary}"
TaskUpdate  → status: "in_progress" (scoring phase)
TaskUpdate  → status: "completed" (recommendation delivered)
```

Results are stored as task metadata for downstream commands (`/zerg:rush`, `/zerg:worker`) to reference when configuring MCP servers and agent types.

<!-- SPLIT: core=select-tool.core.md details=select-tool.details.md -->
