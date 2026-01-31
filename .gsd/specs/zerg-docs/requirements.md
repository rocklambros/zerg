# Requirements: zerg-docs

**Status**: APPROVED
**Created**: 2026-01-31
**Feature**: zerg-docs

## Summary

Build a complete documentation system for the ZERG project, including:

1. A `doc_engine` package with 7 modules for automated documentation generation
2. CLI commands (`zerg document`, `zerg wiki`) for generating docs
3. A complete GitHub Wiki with 50 pages covering all aspects of the project
4. Unit tests for the doc_engine package

## Functional Requirements

### FR-1: Doc Engine Package
- ComponentDetector: auto-detect component type via AST analysis
- SymbolExtractor: extract classes, functions, imports, docstrings
- DependencyMapper: map import relationships between modules
- MermaidGenerator: generate Mermaid diagrams from dependency data
- DocRenderer: render markdown documentation using templates
- CrossRefBuilder: build glossary and cross-reference index
- SidebarGenerator: generate GitHub Wiki sidebar navigation

### FR-2: CLI Commands
- `zerg document <target>`: generate docs for a single file/module
- `zerg wiki`: generate complete wiki with all pages

### FR-3: Wiki Content
- Getting started guides (Home, Installation, Quick Start, First Feature)
- Tutorials (Minerals Store, Container Mode)
- Command reference for all 22 commands
- Architecture documentation (overview, execution flow, modules, state, dependencies)
- Configuration and tuning guides
- Plugin system and context engineering documentation
- Development guides (contributing, testing, troubleshooting, debug)
- Reference pages (glossary, FAQ, sidebar, footer)

### FR-4: Quality
- Unit tests for all doc_engine modules
- All internal wiki links validate
- Backlog items #1 and #2 marked DONE

## Completion

All requirements delivered across 24 tasks in 5 levels.
