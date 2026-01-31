# ZERG Implementation Task Backlog

**Phase**: 3 - Implementation Planning
**Date**: January 25, 2026
**Status**: COMPLETE
**Methodology**: ZERG self-application (manual execution)
**Completed**: January 31, 2026

---

## Executive Summary

This backlog contained 42 atomic tasks to build ZERG from the Phase 2 architecture specification. All 42 tasks are now complete. Implementation exceeded the original specification — the codebase includes additional components not in Phase 3 scope (worker_metrics, task_sync, context_engineering plugin, harness, TUI dashboard).

**Critical Path**: ZERG-L1-001 → ZERG-L1-003 → ZERG-L2-001 → ZERG-L2-004 → ZERG-L3-001 → ZERG-L3-004 → ZERG-L4-004 → ZERG-L5-003

---

## Progress Tracker

| Level | Name | Total | Complete | Blocked | Remaining |
|-------|------|-------|----------|---------|-----------|
| 1 | Foundation | 8 | 8 | 0 | 0 |
| 2 | Core | 10 | 10 | 0 | 0 |
| 3 | Integration | 9 | 9 | 0 | 0 |
| 4 | Commands | 10 | 10 | 0 | 0 |
| 5 | Quality | 5 | 5 | 0 | 0 |
| **Total** | | **42** | **42** | **0** | **0** |

**Last Updated**: 2026-01-31T12:00:00Z

---

## Level 1: Foundation

*Types, schemas, configuration, and package structure. No dependencies.*

### ZERG-L1-001: Python Package Structure ⭐ CRITICAL PATH

| Attribute | Value |
|-----------|-------|
| **Description** | Create Python package skeleton with proper module layout |
| **Files Create** | `zerg/__init__.py`, `zerg/py.typed`, `pyproject.toml`, `requirements.txt` |
| **Verification** | `python -c "import zerg; print(zerg.__version__)"` |
| **Status** | DONE |

---

### ZERG-L1-002: Type Definitions

| Attribute | Value |
|-----------|-------|
| **Description** | Define TypedDict and dataclass types for all domain objects |
| **Files Create** | `zerg/types.py` |
| **Verification** | `python -c "from zerg.types import TaskGraph, WorkerState, LevelStatus"` |
| **Status** | DONE |

---

### ZERG-L1-003: Configuration Schema ⭐ CRITICAL PATH

| Attribute | Value |
|-----------|-------|
| **Description** | Config loader with Pydantic validation, defaults from config.yaml |
| **Files Create** | `zerg/config.py` |
| **Verification** | `python -c "from zerg.config import ZergConfig; c = ZergConfig.load(); print(c.workers.max_concurrent)"` |
| **Status** | DONE |

---

### ZERG-L1-004: Constants and Enums

| Attribute | Value |
|-----------|-------|
| **Description** | Define level names, task statuses, gate results, error codes |
| **Files Create** | `zerg/constants.py` |
| **Verification** | `python -c "from zerg.constants import Level, TaskStatus, GateResult"` |
| **Status** | DONE |

---

### ZERG-L1-005: Logging Setup

| Attribute | Value |
|-----------|-------|
| **Description** | Structured JSON logging with worker ID context, file rotation |
| **Files Create** | `zerg/logging.py` |
| **Verification** | `python -c "from zerg.logging import get_logger; log = get_logger('test'); log.info('works')"` |
| **Status** | DONE |

---

### ZERG-L1-006: Exception Hierarchy

| Attribute | Value |
|-----------|-------|
| **Description** | Define ZergError base and specific exceptions for each failure mode |
| **Files Create** | `zerg/exceptions.py` |
| **Verification** | `python -c "from zerg.exceptions import ZergError, TaskVerificationFailed, MergeConflict"` |
| **Status** | DONE |

---

### ZERG-L1-007: Task Graph Schema Validator

| Attribute | Value |
|-----------|-------|
| **Description** | JSON Schema for task-graph.json with validation functions |
| **Files Create** | `zerg/schemas/task_graph.json`, `zerg/schemas/__init__.py`, `zerg/validation.py` |
| **Verification** | `python -c "from zerg.validation import validate_task_graph"` |
| **Status** | DONE |
| **Notes** | Schema in `zerg/schemas/`, validation in `zerg/validation.py` |

---

### ZERG-L1-008: CLI Entry Point Skeleton

| Attribute | Value |
|-----------|-------|
| **Description** | Click-based CLI with subcommand structure |
| **Files Create** | `zerg/cli.py` |
| **Verification** | `python -m zerg --help` |
| **Status** | DONE |

---

## Level 2: Core

*Business logic components. Depend on Level 1 foundation.*

### ZERG-L2-001: Worktree Manager ⭐ CRITICAL PATH

| Attribute | Value |
|-----------|-------|
| **Description** | Git worktree create/delete/list, branch management, path resolution |
| **Files Create** | `zerg/worktree.py` |
| **Verification** | `python -c "from zerg.worktree import WorktreeManager"` |
| **Status** | DONE |

---

### ZERG-L2-002: Port Allocator

| Attribute | Value |
|-----------|-------|
| **Description** | Random port selection in ephemeral range, collision detection, tracking |
| **Files Create** | `zerg/ports.py` |
| **Verification** | `python -c "from zerg.ports import PortAllocator"` |
| **Status** | DONE |

---

### ZERG-L2-003: Task Parser

| Attribute | Value |
|-----------|-------|
| **Description** | Load task-graph.json, parse into domain objects, validate dependencies |
| **Files Create** | `zerg/parser.py` |
| **Verification** | `python -c "from zerg.parser import TaskParser"` |
| **Status** | DONE |

---

### ZERG-L2-004: Level Controller ⭐ CRITICAL PATH

| Attribute | Value |
|-----------|-------|
| **Description** | Track level completion, block N+1 until N done, emit level events |
| **Files Create** | `zerg/levels.py` |
| **Verification** | `python -c "from zerg.levels import LevelController"` |
| **Status** | DONE |
| **Notes** | Includes `is_level_complete()` (success-only) and `is_level_resolved()` (all-terminal) split. Fixed in commit 2451f86. |

---

### ZERG-L2-005: State Manager (Claude Tasks Integration)

| Attribute | Value |
|-----------|-------|
| **Description** | Adapter for Claude Native Tasks API, state persistence, polling |
| **Files Create** | `zerg/state.py` |
| **Verification** | `python -c "from zerg.state import StateManager"` |
| **Status** | DONE |

---

### ZERG-L2-006: Quality Gate Runner

| Attribute | Value |
|-----------|-------|
| **Description** | Execute gate commands, capture output, determine pass/fail, timeout handling |
| **Files Create** | `zerg/gates.py` |
| **Verification** | `python -c "from zerg.gates import GateRunner"` |
| **Status** | DONE |

---

### ZERG-L2-007: Verification Executor

| Attribute | Value |
|-----------|-------|
| **Description** | Run task verification commands, handle timeouts, capture results |
| **Files Create** | `zerg/verify.py` |
| **Verification** | `python -c "from zerg.verify import VerificationExecutor"` |
| **Status** | DONE |

---

### ZERG-L2-008: Worker Assignment Calculator

| Attribute | Value |
|-----------|-------|
| **Description** | Distribute tasks to workers, balance by level, respect file ownership |
| **Files Create** | `zerg/assign.py` |
| **Verification** | `python -c "from zerg.assign import WorkerAssignment"` |
| **Status** | DONE |

---

### ZERG-L2-009: Container Manager

| Attribute | Value |
|-----------|-------|
| **Description** | Docker/devcontainer lifecycle: build, start, stop, health check |
| **Files Create** | `zerg/containers.py` |
| **Verification** | `python -c "from zerg.containers import ContainerManager"` |
| **Status** | DONE |
| **Notes** | Integrated into `zerg/launcher.py` as `ContainerLauncher` class |

---

### ZERG-L2-010: Git Operations

| Attribute | Value |
|-----------|-------|
| **Description** | Branch create/delete, merge, rebase, conflict detection, staging branch |
| **Files Create** | `zerg/git_ops.py` |
| **Verification** | `python -c "from zerg.git_ops import GitOps"` |
| **Status** | DONE |

---

## Level 3: Integration

*Wire components together into working subsystems. Depend on Level 2.*

### ZERG-L3-001: Orchestrator Core ⭐ CRITICAL PATH

| Attribute | Value |
|-----------|-------|
| **Description** | Main event loop: worker lifecycle, level transitions, status polling |
| **Files Create** | `zerg/orchestrator.py` |
| **Verification** | `python -c "from zerg.orchestrator import Orchestrator"` |
| **Status** | DONE |
| **Notes** | ~1500 lines. Uses `is_level_resolved()` for advancement. Includes level_coordinator delegation. |

---

### ZERG-L3-002: Merge Gate Integration

| Attribute | Value |
|-----------|-------|
| **Description** | Combine git ops + quality gates + level controller for merge workflow |
| **Files Create** | `zerg/merge.py` |
| **Verification** | `python -c "from zerg.merge import MergeCoordinator"` |
| **Status** | DONE |

---

### ZERG-L3-003: Worker Protocol Handler

| Attribute | Value |
|-----------|-------|
| **Description** | Worker startup sequence, task claiming, completion reporting, exit handling |
| **Files Create** | `zerg/worker_protocol.py` |
| **Verification** | `python -c "from zerg.worker_protocol import WorkerProtocol"` |
| **Status** | DONE |

---

### ZERG-L3-004: Rush Command Implementation ⭐ CRITICAL PATH

| Attribute | Value |
|-----------|-------|
| **Description** | Full /zerg rush flow: parse graph, assign workers, launch containers, monitor |
| **Files Create** | `zerg/commands/rush.py` |
| **Verification** | `python -m zerg rush --help` |
| **Status** | DONE |
| **Notes** | Supports subprocess, container, and task modes |

---

### ZERG-L3-005: Status Command Implementation

| Attribute | Value |
|-----------|-------|
| **Description** | /zerg status output: progress bars, worker table, event log |
| **Files Create** | `zerg/commands/status.py` |
| **Verification** | `python -m zerg status --help` |
| **Status** | DONE |

---

### ZERG-L3-006: Stop Command Implementation

| Attribute | Value |
|-----------|-------|
| **Description** | /zerg stop flow: graceful shutdown, checkpoint, container cleanup |
| **Files Create** | `zerg/commands/stop.py` |
| **Verification** | `python -m zerg stop --help` |
| **Status** | DONE |

---

### ZERG-L3-007: Retry Command Implementation

| Attribute | Value |
|-----------|-------|
| **Description** | /zerg retry flow: reset task state, re-queue for execution |
| **Files Create** | `zerg/commands/retry.py` |
| **Verification** | `python -m zerg retry --help` |
| **Status** | DONE |

---

### ZERG-L3-008: Logs Command Implementation

| Attribute | Value |
|-----------|-------|
| **Description** | /zerg logs: stream worker logs, filtering, tail/follow modes |
| **Files Create** | `zerg/commands/logs.py` |
| **Verification** | `python -m zerg logs --help` |
| **Status** | DONE |

---

### ZERG-L3-009: Cleanup Command Implementation

| Attribute | Value |
|-----------|-------|
| **Description** | /zerg cleanup: remove worktrees, branches, logs, containers |
| **Files Create** | `zerg/commands/cleanup.py` |
| **Verification** | `python -m zerg cleanup --help` |
| **Status** | DONE |

---

## Level 4: Commands

*Slash command prompt refinement and integration. Depend on Level 3.*

**Note**: Command files relocated from `.claude/commands/` to `zerg/data/commands/` during implementation. All 19 command files exist at the new path.

### ZERG-L4-001: Init Command Refinement

| Attribute | Value |
|-----------|-------|
| **Description** | Update /zerg init prompt with detection logic, generate config |
| **Files** | `zerg/data/commands/zerg:init.md` |
| **Status** | DONE |

---

### ZERG-L4-002: Plan Command Refinement

| Attribute | Value |
|-----------|-------|
| **Description** | Update /zerg plan prompt with requirements template, approval flow |
| **Files** | `zerg/data/commands/zerg:plan.md`, `zerg:plan.core.md` |
| **Status** | DONE |

---

### ZERG-L4-003: Design Command Refinement

| Attribute | Value |
|-----------|-------|
| **Description** | Update /zerg design prompt with task graph generation, validation |
| **Files** | `zerg/data/commands/zerg:design.md`, `zerg:design.core.md` |
| **Status** | DONE |

---

### ZERG-L4-004: Rush Command Prompt Update ⭐ CRITICAL PATH

| Attribute | Value |
|-----------|-------|
| **Description** | Sync /zerg rush prompt with Python implementation, add examples |
| **Files** | `zerg/data/commands/zerg:rush.md`, `zerg:rush.core.md` |
| **Status** | DONE |

---

### ZERG-L4-005: Status Command Prompt Update

| Attribute | Value |
|-----------|-------|
| **Description** | Sync /zerg status prompt with Python implementation |
| **Files** | `zerg/data/commands/zerg:status.md`, `zerg:status.core.md` |
| **Status** | DONE |

---

### ZERG-L4-006: Worker Command Refinement

| Attribute | Value |
|-----------|-------|
| **Description** | Update /zerg worker prompt with protocol, context handling, exit codes |
| **Files** | `zerg/data/commands/zerg:worker.md`, `zerg:worker.core.md` |
| **Status** | DONE |

---

### ZERG-L4-007: Merge Command Creation

| Attribute | Value |
|-----------|-------|
| **Description** | Create /zerg merge prompt for manual gate triggering |
| **Files** | `zerg/data/commands/zerg:merge.md`, `zerg:merge.core.md` |
| **Status** | DONE |

---

### ZERG-L4-008: Logs Command Prompt Creation

| Attribute | Value |
|-----------|-------|
| **Description** | Create /zerg logs prompt with filtering, streaming examples |
| **Files** | `zerg/data/commands/zerg:logs.md` |
| **Status** | DONE |

---

### ZERG-L4-009: Stop Command Prompt Creation

| Attribute | Value |
|-----------|-------|
| **Description** | Create /zerg stop prompt with graceful/force options |
| **Files** | `zerg/data/commands/zerg:stop.md` |
| **Status** | DONE |

---

### ZERG-L4-010: Cleanup Command Prompt Creation

| Attribute | Value |
|-----------|-------|
| **Description** | Create /zerg cleanup prompt with options documentation |
| **Files** | `zerg/data/commands/zerg:cleanup.md` |
| **Status** | DONE |

---

## Level 5: Quality

*Testing, security, and documentation. Depend on Level 4.*

### ZERG-L5-001: Unit Tests Foundation

| Attribute | Value |
|-----------|-------|
| **Description** | Pytest setup, fixtures, test utilities for core components |
| **Files Create** | `tests/__init__.py`, `tests/conftest.py`, `tests/test_config.py`, `tests/test_types.py` |
| **Verification** | `pytest tests/test_config.py tests/test_types.py -v` |
| **Status** | DONE |
| **Notes** | Test suite: 5418 passed, 0 failed, 1 skipped |

---

### ZERG-L5-002: Core Component Tests

| Attribute | Value |
|-----------|-------|
| **Description** | Tests for worktree, levels, gates, verification, git ops |
| **Files** | `tests/test_worktree.py`, `tests/test_levels.py`, `tests/test_gates.py`, `tests/test_git_ops.py` |
| **Verification** | `pytest tests/test_levels.py tests/test_gates.py tests/test_git_ops.py -v` |
| **Status** | DONE |

---

### ZERG-L5-003: Integration Tests ⭐ CRITICAL PATH

| Attribute | Value |
|-----------|-------|
| **Description** | End-to-end tests: rush with mock containers, level progression, merge flow |
| **Files** | `tests/integration/`, `tests/e2e/` |
| **Verification** | `pytest tests/integration/ tests/e2e/ -v` |
| **Status** | DONE |
| **Notes** | Includes test_rush_flow, test_merge_flow, test_full_pipeline, test_multilevel_execution, test_bugfix_e2e |

---

### ZERG-L5-004: Security Hooks

| Attribute | Value |
|-----------|-------|
| **Description** | Security rules and validation |
| **Files** | `.claude/rules/security/` |
| **Status** | DONE |
| **Notes** | Implemented as `.claude/rules/security/` directory with OWASP, Docker, JS, and Python rules |

---

### ZERG-L5-005: Documentation Update

| Attribute | Value |
|-----------|-------|
| **Description** | Update README, CLAUDE.md with final implementation details |
| **Files** | `README.md`, `CLAUDE.md` |
| **Status** | DONE |

---

## Completion Checklist

### Level 1 Complete When:
- [x] `python -c "import zerg"` succeeds
- [x] `python -m zerg --help` shows commands
- [x] Config loads from `.zerg/config.yaml`
- [x] All types importable

### Level 2 Complete When:
- [x] Worktree create/delete works in test repo
- [x] Level controller blocks correctly
- [x] Quality gate runner executes commands
- [x] Container manager starts test container

### Level 3 Complete When:
- [x] Orchestrator event loop runs
- [x] `/zerg rush` launches workers (dry-run)
- [x] `/zerg status` shows progress
- [x] Merge gate executes quality checks

### Level 4 Complete When:
- [x] All slash command prompts updated
- [x] New commands (merge, logs, stop, cleanup) have prompts
- [x] CLI subcommands match prompts

### Level 5 Complete When:
- [x] `pytest` passes (5418 passed, 0 failed, 1 skipped)
- [x] Integration tests pass
- [x] Security rules configured
- [x] README has installation instructions

---

## Implementation Notes

### File Location Change
Command files were relocated from `.claude/commands/zerg:*.md` to `zerg/data/commands/zerg:*.md` during implementation. The `zerg/data/` package serves command files programmatically.

### Beyond Phase 3 Scope
The implementation includes components not in the original 42-task backlog:
- `zerg/worker_metrics.py` — Worker performance metrics collection
- `zerg/task_sync.py` — TaskSyncBridge for Claude Task system coordination
- `zerg/level_coordinator.py` — Level completion delegation from orchestrator
- `zerg/context_engineering/` — Context engineering plugin (command splitting, task-scoped context)
- `tests/e2e/harness.py` — E2E test harness for mock pipeline execution
- `zerg/dashboard.py` — TUI dashboard for live monitoring
- `zerg/worker_main.py` — Worker entry point and subprocess management

### Key Bug Fixes (Post-Implementation)
- **Commit 2451f86**: Fixed `is_level_complete` vs `is_level_resolved` semantics, mock worker task ID mismatch, MetricsCollector patch location
- **Commit 5dda781**: Wired `CLAUDE_CODE_TASK_LIST_ID` through Python execution layer

### Test Results (2026-01-31)
```
5418 passed, 0 failed, 1 skipped (100% pass rate on non-skipped)
Duration: 5m55s
```

---

## Session Log

### 2026-01-25
- Created initial task backlog from Phase 2 architecture
- Identified 42 atomic tasks across 5 levels
- Critical path: 5.5 hours minimum

### 2026-01-25 through 2026-01-30
- All 42 tasks implemented across multiple sessions
- Additional components built beyond Phase 3 scope

### 2026-01-31
- Final audit: 42/42 tasks DONE
- All test failures resolved (5418 passed)
- Backlog marked COMPLETE
