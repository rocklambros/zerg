# /zerg:index

Generate a complete documentation wiki for the ZERG project.

## Synopsis

```
/zerg:index [--full]
            [--push]
            [--dry-run]
            [--output .zerg/wiki/]
```

## Description

The `index` command generates a full project wiki by discovering all documentable components, running them through the documentation pipeline, cross-referencing pages, generating architecture diagrams, and assembling a navigable wiki with a sidebar.

By default the command operates in incremental mode, only regenerating pages for source files that have changed since the last generation. Use `--full` to regenerate everything from scratch.

### Generation Pipeline

1. **Discover** -- Scan the project for all documentable components.
2. **Detect** -- ComponentDetector classifies each component by type.
3. **Extract** -- SymbolExtractor gathers symbols from all components.
4. **Map** -- DependencyMapper builds a project-wide import graph.
5. **Generate** -- DocRenderer produces markdown for each component.
6. **Cross-ref** -- CrossRefBuilder links pages together with glossary entries and "See also" sections.
7. **Diagram** -- MermaidGenerator creates architecture and dependency diagrams.
8. **Sidebar** -- SidebarGenerator creates `_Sidebar.md` with the page hierarchy.
9. **Publish** -- WikiPublisher handles git operations when `--push` is used.

### Wiki Structure

The generated wiki follows this hierarchy:

```
.zerg/wiki/
  Home.md
  Getting-Started.md
  Tutorial.md
  zerg-Reference/
    zerg-init.md
    zerg-plan.md
    zerg-design.md
    zerg-rush.md
    ...
  Architecture/
    Overview.md
    Launcher.md
    Task-Graph.md
    Context-Engineering.md
  Configuration/
    Config-Reference.md
    Plugins.md
  Troubleshooting.md
  Contributing.md
  Glossary.md
  _Sidebar.md
  _Footer.md
```

### Incremental Mode

Without `--full`, the command:

1. Checks file modification times against the last generation timestamp.
2. Only regenerates pages for changed source files.
3. Always regenerates `_Sidebar.md` and cross-references.
4. Reports progress: "Updated 3/24 pages (21 unchanged)".

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--full` | off | Regenerate all pages from scratch instead of incremental updates. |
| `--push` | off | Push the generated wiki to `{repo}.wiki.git` after generation. |
| `--dry-run` | off | Preview what would be generated without writing any files. |
| `--output` | `.zerg/wiki/` | Output directory for the generated wiki pages. |

## Examples

Generate a full wiki from scratch:

```
/zerg:index --full
```

Preview what would be generated:

```
/zerg:index --dry-run
```

Generate and push to the GitHub Wiki:

```
/zerg:index --full --push
```

Write to a custom output directory:

```
/zerg:index --output docs/wiki/
```

## Error Handling

- If the output directory does not exist, the command creates it.
- If `--push` fails because no wiki repository is configured, the command reports an error with setup instructions.
- If individual page generation fails, the command logs a warning and continues with the remaining pages.

## Task Tracking

This command creates a Claude Code Task with the subject prefix `[Index]` on invocation, updates it to `in_progress` immediately, and marks it `completed` on success.

## See Also

- [[zerg-document]] -- Generate documentation for a single component
- [[zerg-plugins]] -- Plugin configuration documented in the generated wiki
- [[zerg-review]] -- Review generated documentation
