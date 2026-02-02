# /zerg:document

Generate documentation for a specific component, module, or command.

## Synopsis

```
/zerg:document <target> [--type auto|module|command|config|api|types]
                        [--output PATH]
                        [--depth shallow|standard|deep]
                        [--update]
```

## Description

The `document` command generates structured documentation for a single target file or module. It runs through a multi-step pipeline that detects the component type, extracts symbols from the AST, maps dependencies, generates diagrams, and renders the output using a type-specific template.

### Documentation Pipeline

1. **Detect** -- ComponentDetector identifies the component type from file structure (or use `--type` to override).
2. **Extract** -- SymbolExtractor parses the AST for classes, functions, imports, and docstrings.
3. **Map** -- DependencyMapper resolves import relationships.
4. **Diagram** -- MermaidGenerator creates relevant Mermaid diagrams.
5. **Render** -- DocRenderer applies a type-specific template to produce markdown.
6. **Cross-ref** -- CrossRefBuilder injects glossary links and "See also" sections.
7. **Output** -- Write to the path specified by `--output` or print to stdout.

### Depth Levels

**shallow** -- Public classes and functions only. Parameter types, return types, and one-line descriptions.

**standard** (default) -- Everything in shallow, plus key internal methods, import relationships, and a basic Mermaid diagram.

**deep** -- Everything in standard, plus all methods (including private), usage examples discovered in the codebase, full dependency graph, and cross-references to related components.

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `<target>` | (required) | Path to the file or module to document. |
| `--type` | `auto` | Component type override. Accepts `auto`, `module`, `command`, `config`, `api`, or `types`. |
| `--output` | stdout | Output path for the generated documentation. |
| `--depth` | `standard` | Documentation depth. Accepts `shallow`, `standard`, or `deep`. |
| `--update` | off | Update existing documentation in-place rather than overwriting. |

### Component Types

| Type | Description |
|------|-------------|
| `auto` | Auto-detect from file structure. |
| `module` | Python module documentation. |
| `command` | ZERG command file documentation. |
| `config` | Configuration file documentation. |
| `api` | API endpoint documentation. |
| `types` | Type definitions documentation. |

## Examples

Auto-detect and document a module:

```
/zerg:document zerg/launcher.py
```

Document a command file with explicit type:

```
/zerg:document zerg/data/commands/zerg:rush.md --type command
```

Generate deep documentation to a file:

```
/zerg:document zerg/doc_engine/extractor.py --depth deep --output docs/extractor.md
```

Update existing documentation in-place:

```
/zerg:document zerg/launcher.py --output docs/launcher.md --update
```

## Error Handling

- If the target file is not found, the command reports an error and suggests similar paths.
- If AST parsing fails, the command falls back to regex-based extraction with a warning.
- If type detection is ambiguous, the command prompts the user to specify `--type` explicitly.

## Task Tracking

This command creates a Claude Code Task with the subject prefix `[Document]` on invocation, updates it to `in_progress` immediately, and marks it `completed` on success.

## See Also

- [[zerg-index]] -- Generate a complete project wiki using the same pipeline
- [[zerg-analyze]] -- Static analysis that feeds into documentation quality
- [[zerg-review]] -- Review generated documentation for accuracy
