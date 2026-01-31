# ZERG Document

Generate documentation for a specific component, module, or command.

## Usage

```bash
/zerg:document <target> [--type auto|module|command|config|api|types]
                        [--output PATH]
                        [--depth shallow|standard|deep]
                        [--update]
```

## Arguments

- `<target>`: Path to file or module to document (required)

## Flags

- `--type`: Component type override. Default: `auto` (uses ComponentDetector)
  - `auto` - Auto-detect from file structure
  - `module` - Python module documentation
  - `command` - ZERG command file documentation
  - `config` - Configuration file documentation
  - `api` - API endpoint documentation
  - `types` - Type definitions documentation
- `--output`: Output path for generated docs. Default: stdout
- `--depth`: Documentation depth. Default: `standard`
  - `shallow` - Public API only
  - `standard` - Public API + key internals
  - `deep` - Full documentation with examples
- `--update`: Update existing documentation in-place

## Pipeline

1. **Detect**: ComponentDetector identifies component type (or use --type override)
2. **Extract**: SymbolExtractor parses AST for classes, functions, imports, docstrings
3. **Map**: DependencyMapper resolves import relationships
4. **Diagram**: MermaidGenerator creates relevant diagrams
5. **Render**: DocRenderer applies type-specific template
6. **Cross-ref**: CrossRefBuilder injects glossary links and "See also" sections
7. **Output**: Write to --output path or stdout

## Examples

```bash
# Auto-detect and document a module
/zerg:document zerg/launcher.py

# Document a command file explicitly
/zerg:document zerg/data/commands/zerg:rush.md --type command

# Deep documentation to file
/zerg:document zerg/doc_engine/extractor.py --depth deep --output docs/extractor.md

# Update existing docs
/zerg:document zerg/launcher.py --output docs/launcher.md --update
```

## Depth Levels

### Shallow
- Public classes and functions
- Parameter types and return types
- One-line descriptions

### Standard
- Everything in shallow
- Key internal methods
- Import relationships
- Basic Mermaid diagram

### Deep
- Everything in standard
- All methods including private
- Usage examples from codebase
- Full dependency graph
- Cross-references to related components

## Task Tracking

On invocation, create a Claude Code Task to track this command:

Call TaskCreate:
  - subject: "[Document] Generate docs: {target}"
  - description: "Generating {depth} documentation for {target}. Type: {type}."
  - activeForm: "Generating documentation"

Immediately call TaskUpdate:
  - taskId: (the Claude Task ID)
  - status: "in_progress"

On completion, call TaskUpdate:
  - taskId: (the Claude Task ID)
  - status: "completed"

## Error Handling

- If target file not found: report error, suggest similar paths
- If AST parse fails: fall back to regex-based extraction with warning
- If type detection is ambiguous: use --type flag or prompt user

## Help

When `--help` is passed in `$ARGUMENTS`, display usage and exit:

```
/zerg:document — Generate documentation for a specific component, module, or command.

Flags:
  --type auto|module|command|config|api|types
                    Component type override (default: auto)
  --output PATH     Output path for generated docs (default: stdout)
  --depth shallow|standard|deep
                    Documentation depth (default: standard)
  --update          Update existing documentation in-place
  --help            Show this help message
```
