<!-- SPLIT: core, parent: select-tool.md -->

# ZERG Select Tool

Intelligent tool routing across MCP servers, native tools, and Task agent subtypes.

## Flags

| Flag | Description |
|------|-------------|
| `[task description]` | Free-text description of what needs to be done **(required)** |
| `--domain ui\|backend\|infra\|docs\|test\|security\|perf` | Override auto-detection |
| `--format text\|json\|md` | Output format (default: `text`) |
| `--verbose` | Show scoring breakdown per dimension |
| `--no-agents` | Exclude Task agent recommendations |
| `--no-mcp` | Exclude MCP server recommendations |

## Pre-Flight

```bash
# Parse task description (strip flags)
TASK_DESC=$(echo "$ARGUMENTS" | sed 's/--[a-z-]*\s*[a-z|]*//g' | xargs)

if [ -z "$TASK_DESC" ]; then
  echo "ERROR: Task description required. Usage: /zerg:select-tool <description> [flags]"
  exit 1
fi

# Auto-detect domain from keywords
detect_domain() {
  local desc=$(echo "$1" | tr '[:upper:]' '[:lower:]')
  case "$desc" in
    *ui*|*frontend*|*component*|*css*|*responsive*) echo "ui" ;;
    *api*|*database*|*backend*|*server*|*auth*)     echo "backend" ;;
    *docker*|*deploy*|*ci*|*infra*|*k8s*)           echo "infra" ;;
    *docs*|*readme*|*wiki*|*explain*)               echo "docs" ;;
    *test*|*e2e*|*coverage*|*assert*)               echo "test" ;;
    *vuln*|*security*|*xss*|*injection*)            echo "security" ;;
    *perf*|*optimize*|*slow*|*bottleneck*|*cache*)  echo "perf" ;;
    *)                                               echo "backend" ;;
  esac
}

DOMAIN=$(detect_domain "$TASK_DESC")

# Override if --domain flag provided
if echo "$ARGUMENTS" | grep -q '\-\-domain'; then
  DOMAIN=$(echo "$ARGUMENTS" | grep -oP '(?<=--domain\s)\S+')
fi

echo "Task: $TASK_DESC"
echo "Domain: $DOMAIN"
```

## Scoring Overview

Five axes scored 0.0-1.0, combined into a composite score:

| Axis | Low (0.0-0.3) | Medium (0.4-0.6) | High (0.7-1.0) |
|------|---------------|-------------------|-----------------|
| **file_count** | 1-2 files | 3-7 files | 8+ files |
| **analysis_depth** | Quick lookup | Multi-step reasoning | Architectural review |
| **domain** | General-purpose | Single-domain specialist | Cross-domain |
| **parallelism** | Sequential only | Some batching | Full parallel delegation |
| **interactivity** | Non-interactive | Light feedback | Browser/UI interaction |

**Composite formula:**

```
score = (file * 0.2) + (depth * 0.3) + (domain * 0.2) + (parallel * 0.15) + (interactive * 0.15)
```

**Score tiers:**

| Range | Recommendation |
|-------|---------------|
| 0.0-0.3 | Native tools (Read, Edit, Grep, Glob) |
| 0.3-0.6 | Single MCP server or Task agent |
| 0.6-0.8 | MCP + agent combo |
| 0.8-1.0 | Multi-MCP + delegation (`--delegate`) |

> See `select-tool.details.md` for full scoring formulas, keyword triggers, and capability database.

## Workflow

1. **Parse** -- Extract task description, detect domain from keywords
2. **Score** -- Evaluate 5 axes via keyword analysis (details.md has full triggers)
3. **Match** -- Look up tools from capability database ranked by axis fit (details.md)
4. **Output** -- Emit ranked recommendations with confidence and rationale

## Output Format

```
+==========================================+
| ZERG Select Tool                         |
+==========================================+
| Task:   {summary}                        |
| Domain: {domain}                         |
| Score:  {composite} -> {tier label}      |
+------------------------------------------+
| #1 {tool_name}  ({confidence}%)          |
|    Rationale: {why}                      |
|    Usage: {example command/invocation}   |
|                                          |
| #2 {tool_name}  ({confidence}%)          |
|    Rationale: {why}                      |
|    Usage: {example}                      |
|                                          |
| #3 {tool_name}  ({confidence}%)          |
|    Rationale: {why}                      |
|    Usage: {example}                      |
+==========================================+
```

If `--verbose`, append per-axis breakdown:

```
Scoring: file=0.2 depth=0.6 domain=0.4 parallel=0.1 interactive=0.0 -> 0.34
```

## Task Tracking

```
On invocation:  TaskCreate "[Select-Tool] Route: {TASK_DESC}"
Immediately:    TaskUpdate status "in_progress"
On completion:  TaskUpdate status "completed" with recommended tools in notes
```

## Completion Criteria

- [ ] Task description parsed and domain detected (or overridden)
- [ ] 5 axes scored with composite calculated
- [ ] 1-3 tools recommended with confidence % and rationale
- [ ] Output rendered in requested `--format`
- [ ] Task tracking lifecycle completed (create -> in_progress -> completed)

## Help

When `--help` is passed in `$ARGUMENTS`, display usage and exit:

```
/zerg:select-tool — Intelligent tool routing across MCP servers, native tools, and Task agent subtypes.

Flags:
  [task description]    Free-text description of what needs to be done (required)
  --domain <value>      Override auto-detection (ui|backend|infra|docs|test|security|perf)
  --format <value>      Output format: text|json|md (default: text)
  --verbose             Show scoring breakdown per dimension
  --no-agents           Exclude Task agent recommendations
  --no-mcp             Exclude MCP server recommendations
  --help                Show this help message
```

<!-- SPLIT: core=select-tool.core.md details=select-tool.details.md -->
