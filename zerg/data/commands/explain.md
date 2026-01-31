<!-- SPLIT: core=explain.core.md details=explain.details.md -->
# ZERG Explain

Educational code explanations with 4 progressive depth layers, powered by doc_engine AST extractors.

## Flags

- `--scope function|file|module|system`: Override auto-detection of explanation scope
- `--save`: Write output to `claudedocs/explanations/{target}.md`
- `--format text|md|json`: Output format (default: text, md when --save)
- `--no-diagrams`: Skip Mermaid diagram generation

## Pre-Flight

```bash
TARGET="$ARGUMENTS"

# Strip flags from target
TARGET=$(echo "$TARGET" | sed 's/--[a-z-]*\s*[^ ]*//' | xargs)

if [ -z "$TARGET" ]; then
  echo "ERROR: No target specified. Usage: /zerg:explain <file|function|module>"
  exit 1
fi

# Resolve target to file path
if echo "$TARGET" | grep -q ':'; then
  # function reference: path/to/file.py:function_name
  TARGET_FILE=$(echo "$TARGET" | cut -d: -f1)
  TARGET_SYMBOL=$(echo "$TARGET" | cut -d: -f2)
  SCOPE="function"
elif [ -f "$TARGET" ]; then
  TARGET_FILE="$TARGET"
  SCOPE="file"
elif [ -d "$TARGET" ]; then
  TARGET_DIR="$TARGET"
  SCOPE="module"
else
  # Try as dotted module path
  TARGET_FILE=$(echo "$TARGET" | tr '.' '/' | sed 's/$/.py/')
  if [ -f "$TARGET_FILE" ]; then
    SCOPE="file"
  else
    echo "ERROR: Cannot resolve target '$TARGET'"
    exit 1
  fi
fi

# Override scope if --scope flag provided
# (Claude parses flags from $ARGUMENTS)

SAVE_DIR="claudedocs/explanations"
```

## Auto-Scope Detection

If no explicit `--scope` flag:

1. Target contains `:` (e.g., `file.py:func`) → **function** scope
2. Target is a file path → **file** scope
3. Target is a directory/package → **module** scope
4. `--scope system` explicitly → **system** scope (multi-module analysis)

## Workflow

Execute all 4 layers. See `explain.details.md` for full templates, python snippets, and output format.

### Step 1: Extract Structured Data

Run `python -c` snippets to extract AST data from target:
- **SymbolExtractor**: Classes, functions, args, return types, docstrings, decorators
- **ComponentDetector**: File role (MODULE, COMMAND, CONFIG, TYPES, API)
- **DependencyMapper**: Import graph, importers, dependency chains
- **MermaidGenerator**: Dependency/flow diagrams (unless `--no-diagrams`)

If `python -c` import fails, fall back to reading source code directly.

### Step 2: Read Source Code

Read the target file(s) to understand implementation beyond what AST provides.

### Step 3: Generate 4-Layer Explanation

Using extracted data + source code, generate all 4 layers:

1. **Layer 1: Summary** — What it does, responsibilities, public API surface
2. **Layer 2: Logic Flow** — Execution path, control flow, data transformations, Mermaid diagram
3. **Layer 3: Implementation Details** — Algorithms, data structures, type contracts, performance
4. **Layer 4: Design Decisions** — Patterns, abstractions, trade-offs, integration points

### Step 4: Output

Display explanation in terminal using structured section format.

If `--save` flag: also write to `$SAVE_DIR/{target_name}.md` in markdown format.

## Task Tracking

On invocation, create a Claude Code Task:

Call TaskCreate:
  - subject: "[Explain] {scope} explanation for {target}"
  - description: "Generating 4-layer explanation for {target}. Scope: {scope}. Save: {yes/no}."
  - activeForm: "Explaining {target}"

Immediately call TaskUpdate:
  - taskId: (the Claude Task ID)
  - status: "in_progress"

On completion, call TaskUpdate:
  - taskId: (the Claude Task ID)
  - status: "completed"

## Completion Criteria

- All 4 layers generated and displayed
- If `--save`: markdown file written to `claudedocs/explanations/`
- Structured data extracted via doc_engine (or fallback used)
- Mermaid diagram included (unless `--no-diagrams`)

## Exit Codes

- 0: Explanation completed successfully
- 1: Target not found or cannot be resolved
- 2: doc_engine import failure (warning only, falls back)

## Help

When `--help` is passed in `$ARGUMENTS`, display usage and exit:

```
/zerg:explain — Educational code explanations with 4 progressive depth layers, powered by doc_engine AST extractors.

Flags:
  --scope function|file|module|system
                    Override auto-detection of explanation scope
  --save            Write output to claudedocs/explanations/{target}.md
  --format text|md|json
                    Output format (default: text, md when --save)
  --no-diagrams     Skip Mermaid diagram generation
  --help            Show this help message
```

<!-- SPLIT: core=explain.core.md details=explain.details.md -->
