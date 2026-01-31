# ZERG Index

Generate a complete documentation wiki for the ZERG project.

## Usage

```bash
/zerg:index [--full]
            [--push]
            [--dry-run]
            [--output .zerg/wiki/]
```

## Flags

- `--full`: Regenerate all pages from scratch (default: incremental, skip unchanged)
- `--push`: Push generated wiki to {repo}.wiki.git after generation
- `--dry-run`: Preview what would be generated without writing files
- `--output`: Output directory for wiki pages. Default: `.zerg/wiki/`

## Pipeline

1. **Discover**: Scan project for all documentable components
2. **Detect**: ComponentDetector classifies each component
3. **Extract**: SymbolExtractor gathers symbols from all components
4. **Map**: DependencyMapper builds project-wide import graph
5. **Generate**: DocRenderer produces markdown for each component
6. **Cross-ref**: CrossRefBuilder links pages together with glossary and "See also"
7. **Diagram**: MermaidGenerator creates architecture and dependency diagrams
8. **Sidebar**: SidebarGenerator creates _Sidebar.md with page hierarchy
9. **Publish**: WikiPublisher handles git operations (if --push)

## Wiki Structure

Generated wiki follows this hierarchy:

```
.zerg/wiki/
├── Home.md                    # Project overview
├── Getting-Started.md         # Quick start guide
├── Tutorial.md                # Step-by-step tutorial
├── Command-Reference/
│   ├── zerg-init.md
│   ├── zerg-plan.md
│   ├── zerg-design.md
│   ├── zerg-rush.md
│   └── ...
├── Architecture/
│   ├── Overview.md
│   ├── Launcher.md
│   ├── Task-Graph.md
│   └── Context-Engineering.md
├── Configuration/
│   ├── Config-Reference.md
│   └── Plugins.md
├── Troubleshooting.md
├── Contributing.md
├── Glossary.md
├── _Sidebar.md
└── _Footer.md
```

## Examples

```bash
# Generate full wiki
/zerg:index --full

# Preview without writing
/zerg:index --dry-run

# Generate and push to GitHub Wiki
/zerg:index --full --push

# Custom output directory
/zerg:index --output docs/wiki/
```

## Incremental Mode

By default (without --full), the index command:
1. Checks file modification times against last generation
2. Only regenerates pages for changed source files
3. Always regenerates _Sidebar.md and cross-references
4. Reports: "Updated 3/24 pages (21 unchanged)"

## Task Tracking

On invocation, create a Claude Code Task to track this command:

Call TaskCreate:
  - subject: "[Index] Generate wiki documentation"
  - description: "Generating wiki. Mode: {full|incremental}. Output: {output}. Push: {push}."
  - activeForm: "Generating wiki"

Immediately call TaskUpdate:
  - taskId: (the Claude Task ID)
  - status: "in_progress"

On completion, call TaskUpdate:
  - taskId: (the Claude Task ID)
  - status: "completed"

## Error Handling

- If output directory doesn't exist: create it
- If --push fails (no wiki repo): report error with setup instructions
- If individual page generation fails: log warning, continue with remaining pages

## Help

When `--help` is passed in `$ARGUMENTS`, display usage and exit:

```
/zerg:index — Generate a complete documentation wiki for the ZERG project.

Flags:
  --full            Regenerate all pages from scratch (default: incremental)
  --push            Push generated wiki to {repo}.wiki.git after generation
  --dry-run         Preview what would be generated without writing files
  --output PATH     Output directory for wiki pages (default: .zerg/wiki/)
  --help            Show this help message
```
