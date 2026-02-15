# Requirements: Multi-Epic Isolation

## Metadata
- **Feature**: multi-epic-isolation
- **Status**: APPROVED
- **Created**: 2026-02-11
- **Priority**: Critical — data corruption in production workflows

---

## 1. Problem Statement

ZERG cannot safely run two independent epics in parallel across separate terminal sessions. Six root causes combine to produce cross-epic stomping of plans, designs, task graphs, worker execution, and git PRs.

### Symptoms Reported
- Terminal 2's `/z:plan` overwrites Terminal 1's active feature
- `/z:design` and `/z:rush` operate on the wrong epic after context switch
- `/z:git --action ship` creates PRs mixing commits from both epics
- Workers claim tasks from wrong levels (premature execution)
- `/z:plan` starts implementing after user types "APPROVE" instead of stopping

---

## 2. Root Cause Analysis

### RC1: `.gsd/.current-feature` is a global singleton (CRITICAL)
- **15 command markdown files** read `FEATURE=$(cat .gsd/.current-feature 2>/dev/null)`
- `/z:plan` writes `echo "$FEATURE" > .gsd/.current-feature`
- **5 Python CLI modules** use `detect_feature()` from `zerg/commands/_utils.py` which reads the same file
- When Terminal 2 plans a new epic, it overwrites Terminal 1's feature pointer
- ALL subsequent commands in Terminal 1 now operate on Terminal 2's epic

### RC2: `/z:git --action ship` is not feature-scoped
- Ship pipeline operates on current git branch, not feature-specific branches
- No `--feature` flag to scope commit/PR/merge to a specific epic
- If both epics have merged work, ship picks up commits from both
- PR body, title, and diff include cross-epic changes

### RC3: Claude Code Task list co-mingling
- Task list ID defaults to feature name: `${CLAUDE_CODE_TASK_LIST_ID:-$FEATURE}`
- But `$FEATURE` comes from `.current-feature` (RC1), so if RC1 is wrong, task list ID is wrong
- `TaskList` returns ALL tasks without feature filtering
- `/z:status` shows mixed tasks from both epics

### RC4: Workers don't enforce level boundaries during task claiming
- `protocol_state.py:371` calls `claim_task()` WITHOUT `current_level` parameter
- `task_repo.py:113-118` has level enforcement code but it's BYPASSED (only runs when `current_level is not None`)
- Workers call `get_tasks_by_status(TaskStatus.PENDING)` which returns ALL pending tasks across ALL levels
- `state.get_current_level()` exists but is never used in the claim path
- Result: workers can claim Level N+1 tasks before Level N completes

### RC5: No process-level mutex between terminal sessions
- No mechanism to detect concurrent ZERG operations on the same repo
- No lockfile for exclusive feature access
- No session ID to track which terminal owns which epic

### RC6: `/z:plan` approval gate has structural weaknesses
- Phase 5 says `"APPROVED" — proceed to design phase` — affirmative action instruction
- LLM interprets "proceed to design phase" as "start designing now"
- Approval captured via free-text conversation, not `AskUserQuestion` structured gate
- Phase 5.5 guards (⛔ banners, "STOP" instructions) are post-hoc negations fighting the Phase 5 affirmative
- In LLM prompts, affirmative instructions almost always win against later negations
- No mechanical barrier (plan mode not enforced) prevents tool calls after "APPROVE"

---

## 3. Functional Requirements

### FR1: Environment-based feature context (fixes RC1)
**Replace `.current-feature` singleton with `ZERG_FEATURE` environment variable as primary source.**

- `detect_feature()` in `zerg/commands/_utils.py` priority order becomes:
  1. `ZERG_FEATURE` env var (terminal-session-scoped, cannot be stomped by other terminals)
  2. `--feature` CLI flag (explicit override)
  3. `.gsd/.current-feature` file (fallback for backward compat, last resort)
- `/z:plan` MUST set `ZERG_FEATURE` via instructing user to export, AND still write `.current-feature` for backward compat
- All 15 command markdown files update pre-flight to: `FEATURE=${ZERG_FEATURE:-$(cat .gsd/.current-feature 2>/dev/null)}`
- All 5 Python CLI modules already use `detect_feature()` — updating the one function fixes them all

### FR2: Feature-scoped git ship (fixes RC2)
- `/z:git --action ship` reads active feature (via FR1's updated detection)
- Ship scopes to the feature's integration branch: only includes commits from `zerg/{feature}/*` branches
- If no feature branch exists (user is on a manual branch), ship works as today (no change for non-ZERG workflows)
- PR title includes feature name: `feat({feature}): {summary}`

### FR3: Feature-scoped task list auto-export (fixes RC3)
- `/z:plan` pre-flight sets `CLAUDE_CODE_TASK_LIST_ID` to feature name if not already set
- `/z:design` and `/z:rush` propagate `CLAUDE_CODE_TASK_LIST_ID` to all workers
- `/z:status` filters displayed tasks by feature name from current context

### FR4: Level-aware task claiming (fixes RC4)
- `protocol_state.py:claim_next_task_async()` reads `self.state.get_current_level()` and passes it to `claim_task()`
- Workers cannot claim tasks above the current orchestrator level
- This is a one-line code change: add `current_level=self.state.get_current_level()` to the `claim_task()` call

### FR5: Per-feature advisory lockfile (fixes RC5)
- When `/z:rush` starts, create `.gsd/specs/{feature}/.lock` with PID and timestamp
- When `/z:rush` in another terminal detects lock, warn user: "Another session is running {feature}. Continue? (y/n)"
- Lock is advisory (can be overridden) — not blocking
- Lock auto-expires after configurable timeout (default: 2 hours)
- `/z:cleanup` removes stale locks

### FR6: Structured approval gate in plan command (fixes RC6)
Three changes to `plan.core.md` and `plan.md`:

1. **Phase 5**: Remove "proceed to design phase" wording. Replace with:
   ```
   - "APPROVED" — requirements are complete and locked
   ```
2. **Phase 5**: Add explicit `AskUserQuestion` to capture approval:
   ```
   Call AskUserQuestion:
     - question: "Do you approve these requirements?"
     - header: "Approval"
     - options:
       - label: "Approve"
         description: "Lock requirements and stop. You will run /z:design separately."
       - label: "Request changes"
         description: "Describe what needs to change"
   ```
3. **Phase 5.5**: Move the ⛔ PLANNING COMPLETE banner to be the FIRST thing after approval, BEFORE any other operations (TaskUpdate, requirements.md update). The banner must be output before any tool calls to prevent the LLM from "continuing" after seeing approval.

---

## 4. Non-Functional Requirements

### NFR1: Backward Compatibility
- `.current-feature` file continues to work as fallback
- Users who don't export `ZERG_FEATURE` get same behavior as today
- Existing task-graph.json format unchanged

### NFR2: Zero-Config for Single-Epic Usage
- Single-epic users see no behavior change
- Multi-epic isolation is automatic when `ZERG_FEATURE` is set per terminal

### NFR3: Minimal Blast Radius
- RC4 fix (level enforcement) is a one-line change
- RC6 fix (plan approval) changes only plan.core.md and plan.md
- RC1 fix (detect_feature) changes one Python function + 15 markdown pre-flights
- No database schema changes, no new dependencies, no config format changes

---

## 5. Scope Boundaries

### In Scope
- Fix all 6 root causes
- Update command markdown files (15 files)
- Update `detect_feature()` (1 Python function, propagates to 5 CLI modules)
- Update `protocol_state.py` (1 line)
- Update `plan.core.md` and `plan.md` (approval gate restructure)
- Update `git.details.md` (ship feature-scoping)
- Add advisory lockfile logic
- Unit tests for all changes
- Integration test for concurrent feature detection

### Out of Scope
- Cross-epic file ownership validation at design time
- Multi-repo orchestration
- GUI/TUI for multi-epic management
- Changes to Docker/container launcher (already isolated)

---

## 6. Acceptance Criteria

- [ ] Two terminals can run `/z:plan epic-1` and `/z:plan epic-2` without overwriting each other's context (when `ZERG_FEATURE` is exported)
- [ ] `/z:design` reads correct feature from env var, not stomped `.current-feature`
- [ ] `/z:rush` workers cannot claim Level 2 tasks while Level 1 is incomplete
- [ ] `/z:git --action ship` only includes commits from the active feature's branches
- [ ] `/z:plan` stops after approval and prompts user via `AskUserQuestion` — does NOT start designing
- [ ] `/z:rush` warns if another session holds the feature lock
- [ ] All existing tests pass (no regressions)
- [ ] `python -m zerg.validate_commands` passes

---

## 7. Files to Modify

### Python Source
| File | Change |
|------|--------|
| `zerg/commands/_utils.py` | Add `ZERG_FEATURE` env var as priority 1 in `detect_feature()` |
| `zerg/protocol_state.py` | Add `current_level=self.state.get_current_level()` to `claim_task()` call |

### Command Markdown (15 files)
| File | Change |
|------|--------|
| `zerg/data/commands/plan.core.md` | Restructure Phase 5 approval gate, add AskUserQuestion |
| `zerg/data/commands/plan.md` | Same as plan.core.md |
| `zerg/data/commands/design.core.md` | Update pre-flight: `FEATURE=${ZERG_FEATURE:-$(cat ...)}` |
| `zerg/data/commands/design.md` | Same |
| `zerg/data/commands/rush.core.md` | Update pre-flight + add lock check |
| `zerg/data/commands/rush.md` | Same |
| `zerg/data/commands/merge.core.md` | Update pre-flight |
| `zerg/data/commands/merge.md` | Same |
| `zerg/data/commands/status.core.md` | Update pre-flight |
| `zerg/data/commands/status.md` | Same |
| `zerg/data/commands/git.details.md` | Scope ship action to feature branches |
| `zerg/data/commands/stop.md` | Update pre-flight |
| `zerg/data/commands/cleanup.md` | Update pre-flight + add lock cleanup |
| `zerg/data/commands/retry.md` | Update pre-flight |
| `zerg/data/commands/debug.core.md` | Update pre-flight |
| `zerg/data/commands/debug.md` | Same |
| `zerg/data/commands/estimate.core.md` | Update pre-flight |
| `zerg/data/commands/estimate.md` | Same |

### Tests
| File | Change |
|------|--------|
| `tests/unit/test_utils.py` (new or existing) | Test `detect_feature()` priority order |
| `tests/unit/test_protocol_state.py` | Test level-aware claiming |
| `tests/integration/test_concurrent_features.py` (new) | Test two features don't stomp |

---

## 8. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Breaking backward compat for `.current-feature` | Low | High | Keep as fallback in priority chain |
| Plan approval gate still bypassed by creative LLM | Medium | Medium | Use AskUserQuestion (mechanical gate) + remove affirmative language |
| Lock file left stale after crash | Low | Low | Auto-expiry + cleanup command |
| Level enforcement too strict (blocks valid claims) | Low | Medium | Only enforces `task_level <= current_level`, not exact match |

---

## 9. Dependencies

- No external dependencies
- No new Python packages
- No config schema changes
- Requires: existing `state.get_current_level()` API (already exists)

---

## 10. Implementation Priority

1. **RC4** (level enforcement) — one-line fix, highest safety impact
2. **RC6** (plan approval gate) — two file changes, fixes user-facing workflow bug
3. **RC1** (detect_feature env var) — one function + 15 markdown pre-flights, foundational fix
4. **RC3** (task list scoping) — downstream of RC1, automatic once feature detection works
5. **RC2** (ship feature-scoping) — git.details.md change
6. **RC5** (advisory lockfile) — new feature, lowest priority

---

## 11. Documentation Impact Analysis

| Document | Update Needed |
|----------|--------------|
| `CLAUDE.md` | Add `ZERG_FEATURE` env var documentation |
| `ARCHITECTURE.md` | Update "State Management" section re: feature detection priority |
| `CHANGELOG.md` | Add entries under [Unreleased] for all fixes |
| `README.md` | Add multi-epic usage section |
| `.gsd/wiki/Tutorial.md` | Add parallel epic workflow example |
