# Requirements: worker-observability

## Metadata
- **Feature**: worker-observability
- **Status**: APPROVED
- **Created**: 2026-02-02
- **Issues**: #27, #30, #24

## Summary

Close remaining gaps on worker intelligence (#27, #30) and build token usage metrics (#24). PR #95 delivered ~85-90% of #27/#30 code. This feature wires existing modules into `/zerg:status`, adds incremental repo map indexing, and builds the token metrics subsystem.

## Functional Requirements

### FR-1: Wire health data into /zerg:status (closes #27)
- Per-worker HEALTH table: worker ID, status, current task, step, progress, restart count
- Escalation summary: unresolved count, details
- Data sources: heartbeat-{id}.json, escalations.json, progress-{id}.json

### FR-2: Incremental repo map indexing (closes #30)
- MD5 hash-based staleness detection per file
- Selective re-parse only changed files
- Persist index in .zerg/state/repo-index.json
- Wire stats into /zerg:status REPO MAP section

### FR-3: Token usage metrics (closes #24)
- TokenCounter: optional Anthropic SDK API counting (OFF by default), heuristic fallback
- TokenTracker: per-worker JSON files with per-task breakdown
- TokenAggregator: cumulative totals, savings calculation, efficiency ratio
- TOKEN USAGE dashboard section with per-worker table
- Never fail anything if token count unavailable — informational only

## Non-Functional Requirements

- anthropic is an optional dependency (pip install zerg[metrics])
- All token counting errors caught silently, fall back to heuristic
- Dashboard labels "(estimated)" vs "(exact)" to indicate counting mode
- Atomic file writes for all state JSON (tempfile + rename pattern)
