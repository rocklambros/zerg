# /zerg:explain

Educational code explanations with progressive depth layers, powered by doc_engine AST extractors.

## Synopsis

```
/zerg:explain <target> [--scope function|file|module|system]
                       [--save]
                       [--format text|md|json]
                       [--no-diagrams]
```

## Description

The `explain` command generates structured educational explanations of code at any scope level. It uses the doc_engine AST extractors to analyze code structure and produces layered explanations that progressively increase in depth.

### Target Resolution

The target argument is resolved in this order:

1. **Function reference** (`path/to/file.py:function_name`) — Explains a specific function or method.
2. **File path** (`path/to/file.py`) — Explains an entire file.
3. **Directory path** (`path/to/module/`) — Explains a module.
4. **Dotted module** (`zerg.launcher`) — Resolved to a file path.

If `--scope` is not provided, the scope is auto-detected from the target format.

### Explanation Layers

Each explanation builds through four progressive layers:

**Layer 1 — Summary**: A concise overview of what the code does, who calls it, and why it exists. Suitable for quick orientation.

**Layer 2 — Logic Flow**: Step-by-step walkthrough of the execution path. Includes a Mermaid flowchart (unless `--no-diagrams`).

**Layer 3 — Implementation Details**: Internal mechanics, data structures, algorithms, error handling, and edge cases.

**Layer 4 — Design Decisions**: Architectural rationale, trade-offs, alternatives considered, and relationship to the broader system.

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `<target>` | (required) | File, function, module, or dotted path to explain. |
| `--scope` | auto-detect | Override scope detection: `function`, `file`, `module`, or `system`. |
| `--save` | off | Write output to `claudedocs/explanations/{target}.md`. |
| `--format` | `text` | Output format: `text`, `md` (default when `--save`), or `json`. |
| `--no-diagrams` | off | Skip Mermaid diagram generation. |

## Examples

Explain a single file:

```
/zerg:explain zerg/launcher.py
```

Explain a specific function:

```
/zerg:explain zerg/launcher.py:spawn_worker
```

Explain an entire module:

```
/zerg:explain zerg/doc_engine/ --scope module
```

Save explanation to a file:

```
/zerg:explain zerg/launcher.py --save
```

System-level explanation without diagrams:

```
/zerg:explain zerg/ --scope system --no-diagrams
```

## Error Handling

- If the target file or directory is not found, the command reports an error and suggests similar paths.
- If AST parsing fails for a file, the command falls back to regex-based analysis with a warning.
- If the target is ambiguous (e.g., a dotted path that matches multiple files), the command prompts for clarification.

## Task Tracking

This command creates a Claude Code Task with the subject prefix `[Explain]` on invocation, updates it to `in_progress` immediately, and marks it `completed` on success.

## See Also

- [[zerg-document]] -- Generate formal documentation (vs educational explanation)
- [[zerg-analyze]] -- Static analysis that complements explanations
- [[zerg-review]] -- Review code rather than explain it
