# Requirements: container-mode-bypass

## Metadata
- **Feature**: container-mode-bypass
- **Status**: APPROVED
- **Source**: GitHub Issue #2
- **Priority**: P0 Critical

## Problem

`--mode task` is accepted by CLI but has no launcher implementation. Unknown modes silently fall back to subprocess via config default. No user feedback confirms which launcher mode was actually used.

## Requirements

1. Remove unimplemented `"task"` from CLI mode choices
2. Raise `ValueError` for unknown modes instead of silent fallback
3. Log selected launcher mode after resolution
4. Print launcher type to console after Orchestrator init
5. Update slash command help text to match
6. Add tests for unknown mode rejection
