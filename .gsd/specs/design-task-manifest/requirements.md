# Requirements: design-task-manifest

## Status: APPROVED

## Summary

Add Claude Task ecosystem integration to `zerg design` CLI and validate the `/zerg:design` slash command spec.

The CLI (`design.py`) writes a `design-tasks-manifest.json` so rush can register Claude Tasks. The slash command spec already documents Phases 4.5/4.6 correctly.

## Requirements

1. `design.py` writes `design-tasks-manifest.json` in all 3 execution paths (full generation, validate-only, update-backlog)
2. Manifest contains task metadata: subject `[L{level}] {title}`, description, activeForm, dependencies
3. `task_sync.py` gains `load_design_manifest()` to read the manifest
4. `level_coordinator.py` logs manifest presence when starting a level
5. Full test coverage for manifest creation and loading
