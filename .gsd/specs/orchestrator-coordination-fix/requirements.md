# Requirements: Orchestrator Coordination Fix

## Metadata
- **Feature**: orchestrator-coordination-fix
- **Status**: APPROVED
- **Created**: 2026-02-04
- **Discovery**: Debug analysis of bite-sized-planning rush failures

---

## Summary

Fix 6 critical orchestrator bugs that cause merge conflicts, level violations, and redundant gate runs during parallel rush execution.

---

## Problem Statement

The orchestrator currently:
1. Merges to main after EVERY level completion (should defer to ship)
2. Allows workers to claim tasks from any level (should enforce current level)
3. Allows workers to claim tasks with incomplete dependencies
4. Locks staging branch in main worktree causing branch deletion failures
5. Provides no live status updates during rush
6. Runs quality gates after each level (should run once at ship)

Evidence: During the `bite-sized-planning` rush, workers executed L3/L4 tasks while L1 wasn't merged, causing conflicts and failures despite exclusive file ownership.

---

## Functional Requirements

### FR-1: Defer Merge to Ship

Remove merge-to-main from level completion. Merging should ONLY happen during `/z:git --action ship`.

- Level completion → mark complete, advance to next level (NO MERGE)
- Ship command → merge all worker branches to staging → run gates → merge to main

### FR-2: Level Enforcement at Task Claim

`claim_task()` MUST verify `task.level == current_level` before allowing claim.

- Return False if task level != current level
- Log warning with task ID and level mismatch

### FR-3: Dependency Enforcement at Runtime

`claim_task()` MUST verify all task dependencies are COMPLETE before allowing claim.

- Return False if any dependency is not COMPLETE
- Helper: `are_dependencies_met(task_id) -> bool`
- Helper: `get_incomplete_dependencies(task_id) -> list[str]`

### FR-4: Fix Staging Branch Worktree Lock

`finalize()` must not checkout target branch if it's the current worktree branch.

- Use detached HEAD for merge operations
- Prevents "cannot delete branch used by worktree" errors

### FR-5: Live Status Streaming

Add event streaming for `/z:status --live`.

- EventEmitter writes JSONL to `.zerg/state/{feature}-events.jsonl`
- Events: level_start, task_claim, task_complete, task_fail, level_complete
- `--live` flag tails event file and displays with Rich

### FR-6: Gates at Ship Only

Quality gates should run ONCE at ship time, not after each level.

- Add `skip_gates_until_ship` parameter to `full_merge_flow()`
- Ship command calls `run_pre_merge_gates()` + `run_post_merge_gates()` explicitly

---

## Non-Functional Requirements

### NFR-1: Backward Compatibility

- Config flags control new behavior: `defer_merge_to_ship`, `gates_at_ship_only`
- Default: TRUE (new behavior)
- Set to FALSE to restore legacy per-level merge

### NFR-2: Existing Tests Pass

All existing tests must continue to pass after changes.

---

## Acceptance Criteria

- [ ] Level completion does not touch main branch
- [ ] `claim_task()` rejects tasks from wrong level
- [ ] `claim_task()` rejects tasks with incomplete dependencies
- [ ] No "cannot delete branch" errors during merge
- [ ] `/z:status --live` shows streaming updates
- [ ] Gates run once at ship, not per level
- [ ] Config flags enable/disable new behavior
- [ ] All existing tests pass
- [ ] New unit tests for enforcement logic
- [ ] New integration tests for deferred merge

---

## Out of Scope

- Changing the ship command's PR creation flow
- Adding new merge strategies
- Changing worker spawn logic
