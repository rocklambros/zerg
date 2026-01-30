# Technical Design: design-task-manifest

## Status: APPROVED

## Overview

Add a manifest file (`design-tasks-manifest.json`) that `design.py` writes for every execution path. This manifest bridges the CLI (which cannot call Claude Task tools) with the rush orchestrator (which can register Claude Tasks).

## Architecture

```
design.py → writes design-tasks-manifest.json
                      ↓
task_sync.py → load_design_manifest() reads it
                      ↓
level_coordinator.py → logs presence when starting level
```

## Key Decisions

1. Manifest is written to `.gsd/specs/{feature}/design-tasks-manifest.json` alongside task-graph.json
2. Format mirrors Claude Task fields: subject, description, active_form, dependencies
3. All 3 CLI paths write the manifest (full gen, validate-only, update-backlog)
4. `load_design_manifest()` returns None if file missing (graceful degradation)
