# ZERG Implementation Task Backlog

**Phase**: 3 - Implementation Planning
**Date**: January 25, 2026
**Status**: ACTIVE
**Methodology**: ZERG self-application (manual execution)

---

## Executive Summary

This backlog contains 42 atomic tasks to build ZERG from the Phase 2 architecture specification. Tasks are organized by dependency level with exclusive file ownership to prevent conflicts. Estimated completion: 12-15 development sessions.

**Critical Path**: ZERG-L1-001 → ZERG-L1-003 → ZERG-L2-001 → ZERG-L2-004 → ZERG-L3-001 → ZERG-L3-004 → ZERG-L4-004 → ZERG-L5-003

---

## Progress Tracker

| Level | Name | Total | Complete | Blocked | Remaining |
|-------|------|-------|----------|---------|-----------|
| 1 | Foundation | 8 | 0 | 0 | 8 |
| 2 | Core | 10 | 0 | 0 | 10 |
| 3 | Integration | 9 | 0 | 0 | 9 |
| 4 | Commands | 10 | 0 | 0 | 10 |
| 5 | Quality | 5 | 0 | 0 | 5 |
| **Total** | | **42** | **0** | **0** | **42** |

**Last Updated**: 2026-01-25T20:00:00Z

---

## Level 1: Foundation

*Types, schemas, configuration, and package structure. No dependencies.*

### ZERG-L1-001: Python Package Structure ⭐ CRITICAL PATH

| Attribute | Value |
|-----------|-------|
| **Description** | Create Python package skeleton with proper module layout |
| **Files Create** | `zerg/__init__.py`, `zerg/py.typed`, `pyproject.toml`, `requirements.txt` |
| **Files Modify** | None |
| **Files Read** | `.zerg/config.yaml` |
| **Dependencies** | None |
| **Verification** | `python -c "import zerg; print(zerg.__version__)"` |
| **Estimate** | 15 min |
| **Status** | TODO |

---

### ZERG-L1-002: Type Definitions

| Attribute | Value |
|-----------|-------|
| **Description** | Define TypedDict and dataclass types for all domain objects |
| **Files Create** | `zerg/types.py` |
| **Files Modify** | None |
| **Files Read** | `.gsd/specs/phase2/architecture_synthesis.md` |
| **Dependencies** | ZERG-L1-001 |
| **Verification** | `python -c "from zerg.types import TaskGraph, WorkerState, LevelStatus"` |
| **Estimate** | 25 min |
| **Status** | TODO |

---

### ZERG-L1-003: Configuration Schema ⭐ CRITICAL PATH

| Attribute | Value |
|-----------|-------|
| **Description** | Config loader with Pydantic validation, defaults from config.yaml |
| **Files Create** | `zerg/config.py` |
| **Files Modify** | None |
| **Files Read** | `.zerg/config.yaml`, `zerg/types.py` |
| **Dependencies** | ZERG-L1-002 |
| **Verification** | `python -c "from zerg.config import ZergConfig; c = ZergConfig.load(); print(c.workers.max_concurrent)"` |
| **Estimate** | 20 min |
| **Status** | TODO |

---

### ZERG-L1-004: Constants and Enums

| Attribute | Value |
|-----------|-------|
| **Description** | Define level names, task statuses, gate results, error codes |
| **Files Create** | `zerg/constants.py` |
| **Files Modify** | None |
| **Files Read** | None |
| **Dependencies** | ZERG-L1-001 |
| **Verification** | `python -c "from zerg.constants import Level, TaskStatus, GateResult"` |
| **Estimate** | 10 min |
| **Status** | TODO |

---

### ZERG-L1-005: Logging Setup

| Attribute | Value |
|-----------|-------|
| **Description** | Structured JSON logging with worker ID context, file rotation |
| **Files Create** | `zerg/logging.py` |
| **Files Modify** | None |
| **Files Read** | `zerg/config.py` |
| **Dependencies** | ZERG-L1-003 |
| **Verification** | `python -c "from zerg.logging import get_logger; log = get_logger('test'); log.info('works')"` |
| **Estimate** | 15 min |
| **Status** | TODO |

---

### ZERG-L1-006: Exception Hierarchy

| Attribute | Value |
|-----------|-------|
| **Description** | Define ZergError base and specific exceptions for each failure mode |
| **Files Create** | `zerg/exceptions.py` |
| **Files Modify** | None |
| **Files Read** | None |
| **Dependencies** | ZERG-L1-001 |
| **Verification** | `python -c "from zerg.exceptions import ZergError, TaskVerificationFailed, MergeConflict"` |
| **Estimate** | 10 min |
| **Status** | TODO |

---

### ZERG-L1-007: Task Graph Schema Validator

| Attribute | Value |
|-----------|-------|
| **Description** | JSON Schema for task-graph.json with validation functions |
| **Files Create** | `zerg/schemas/task_graph.json`, `zerg/schemas/__init__.py`, `zerg/validation.py` |
| **Files Modify** | None |
| **Files Read** | `.gsd/specs/phase2/architecture_synthesis.md` |
| **Dependencies** | ZERG-L1-002 |
| **Verification** | `python -c "from zerg.validation import validate_task_graph; validate_task_graph({'feature': 'test', 'tasks': []})"` |
| **Estimate** | 25 min |
| **Status** | TODO |

---

### ZERG-L1-008: CLI Entry Point Skeleton

| Attribute | Value |
|-----------|-------|
| **Description** | Click-based CLI with subcommand structure, no implementation |
| **Files Create** | `zerg/cli.py` |
| **Files Modify** | `pyproject.toml` (add entry point) |
| **Files Read** | None |
| **Dependencies** | ZERG-L1-001, ZERG-L1-005 |
| **Verification** | `python -m zerg --help` |
| **Estimate** | 20 min |
| **Status** | TODO |

---

## Level 2: Core

*Business logic components. Depend on Level 1 foundation.*

### ZERG-L2-001: Worktree Manager ⭐ CRITICAL PATH

| Attribute | Value |
|-----------|-------|
| **Description** | Git worktree create/delete/list, branch management, path resolution |
| **Files Create** | `zerg/worktree.py` |
| **Files Modify** | None |
| **Files Read** | `zerg/config.py`, `zerg/types.py`, `zerg/exceptions.py` |
| **Dependencies** | ZERG-L1-003, ZERG-L1-006 |
| **Verification** | `python -c "from zerg.worktree import WorktreeManager; wm = WorktreeManager('.'); print(wm.list_worktrees())"` |
| **Estimate** | 45 min |
| **Status** | TODO |

---

### ZERG-L2-002: Port Allocator

| Attribute | Value |
|-----------|-------|
| **Description** | Random port selection in ephemeral range, collision detection, tracking |
| **Files Create** | `zerg/ports.py` |
| **Files Modify** | None |
| **Files Read** | `zerg/config.py`, `zerg/types.py` |
| **Dependencies** | ZERG-L1-003 |
| **Verification** | `python -c "from zerg.ports import PortAllocator; pa = PortAllocator(); print(pa.allocate(5))"` |
| **Estimate** | 20 min |
| **Status** | TODO |

---

### ZERG-L2-003: Task Parser

| Attribute | Value |
|-----------|-------|
| **Description** | Load task-graph.json, parse into domain objects, validate dependencies |
| **Files Create** | `zerg/parser.py` |
| **Files Modify** | None |
| **Files Read** | `zerg/types.py`, `zerg/validation.py`, `zerg/exceptions.py` |
| **Dependencies** | ZERG-L1-002, ZERG-L1-007, ZERG-L1-006 |
| **Verification** | `python -c "from zerg.parser import TaskParser; tp = TaskParser(); print(tp.parse('.gsd/specs/test/task-graph.json'))"` |
| **Estimate** | 30 min |
| **Status** | TODO |

---

### ZERG-L2-004: Level Controller ⭐ CRITICAL PATH

| Attribute | Value |
|-----------|-------|
| **Description** | Track level completion, block N+1 until N done, emit level events |
| **Files Create** | `zerg/levels.py` |
| **Files Modify** | None |
| **Files Read** | `zerg/types.py`, `zerg/constants.py`, `zerg/logging.py` |
| **Dependencies** | ZERG-L1-002, ZERG-L1-004, ZERG-L1-005 |
| **Verification** | `python -c "from zerg.levels import LevelController; lc = LevelController(); lc.start_level(1)"` |
| **Estimate** | 35 min |
| **Status** | TODO |

---

### ZERG-L2-005: State Manager (Claude Tasks Integration)

| Attribute | Value |
|-----------|-------|
| **Description** | Adapter for Claude Native Tasks API, state persistence, polling |
| **Files Create** | `zerg/state.py` |
| **Files Modify** | None |
| **Files Read** | `zerg/types.py`, `zerg/config.py`, `zerg/logging.py` |
| **Dependencies** | ZERG-L1-002, ZERG-L1-003, ZERG-L1-005 |
| **Verification** | `python -c "from zerg.state import StateManager; sm = StateManager('test-feature')"` |
| **Estimate** | 40 min |
| **Status** | TODO |

---

### ZERG-L2-006: Quality Gate Runner

| Attribute | Value |
|-----------|-------|
| **Description** | Execute gate commands, capture output, determine pass/fail, timeout handling |
| **Files Create** | `zerg/gates.py` |
| **Files Modify** | None |
| **Files Read** | `zerg/config.py`, `zerg/types.py`, `zerg/logging.py`, `zerg/exceptions.py` |
| **Dependencies** | ZERG-L1-003, ZERG-L1-005, ZERG-L1-006 |
| **Verification** | `python -c "from zerg.gates import GateRunner; gr = GateRunner(); gr.run_gate('echo pass', timeout=10)"` |
| **Estimate** | 30 min |
| **Status** | TODO |

---

### ZERG-L2-007: Verification Executor

| Attribute | Value |
|-----------|-------|
| **Description** | Run task verification commands, handle timeouts, capture results |
| **Files Create** | `zerg/verify.py` |
| **Files Modify** | None |
| **Files Read** | `zerg/types.py`, `zerg/logging.py`, `zerg/exceptions.py` |
| **Dependencies** | ZERG-L1-002, ZERG-L1-005, ZERG-L1-006 |
| **Verification** | `python -c "from zerg.verify import VerificationExecutor; ve = VerificationExecutor(); ve.verify('echo ok', 60)"` |
| **Estimate** | 25 min |
| **Status** | TODO |

---

### ZERG-L2-008: Worker Assignment Calculator

| Attribute | Value |
|-----------|-------|
| **Description** | Distribute tasks to workers, balance by level, respect file ownership |
| **Files Create** | `zerg/assign.py` |
| **Files Modify** | None |
| **Files Read** | `zerg/types.py`, `zerg/parser.py` |
| **Dependencies** | ZERG-L1-002, ZERG-L2-003 |
| **Verification** | `python -c "from zerg.assign import WorkerAssignment; wa = WorkerAssignment(workers=5)"` |
| **Estimate** | 30 min |
| **Status** | TODO |

---

### ZERG-L2-009: Container Manager

| Attribute | Value |
|-----------|-------|
| **Description** | Docker/devcontainer lifecycle: build, start, stop, health check |
| **Files Create** | `zerg/containers.py` |
| **Files Modify** | None |
| **Files Read** | `zerg/config.py`, `zerg/types.py`, `zerg/ports.py`, `zerg/logging.py` |
| **Dependencies** | ZERG-L1-003, ZERG-L2-002, ZERG-L1-005 |
| **Verification** | `python -c "from zerg.containers import ContainerManager; cm = ContainerManager()"` |
| **Estimate** | 45 min |
| **Status** | TODO |

---

### ZERG-L2-010: Git Operations

| Attribute | Value |
|-----------|-------|
| **Description** | Branch create/delete, merge, rebase, conflict detection, staging branch |
| **Files Create** | `zerg/git_ops.py` |
| **Files Modify** | None |
| **Files Read** | `zerg/types.py`, `zerg/logging.py`, `zerg/exceptions.py` |
| **Dependencies** | ZERG-L1-002, ZERG-L1-005, ZERG-L1-006 |
| **Verification** | `python -c "from zerg.git_ops import GitOps; go = GitOps('.'); print(go.current_branch())"` |
| **Estimate** | 40 min |
| **Status** | TODO |

---

## Level 3: Integration

*Wire components together into working subsystems. Depend on Level 2.*

### ZERG-L3-001: Orchestrator Core ⭐ CRITICAL PATH

| Attribute | Value |
|-----------|-------|
| **Description** | Main event loop: worker lifecycle, level transitions, status polling |
| **Files Create** | `zerg/orchestrator.py` |
| **Files Modify** | None |
| **Files Read** | `zerg/config.py`, `zerg/types.py`, `zerg/levels.py`, `zerg/state.py`, `zerg/containers.py`, `zerg/logging.py` |
| **Dependencies** | ZERG-L2-004, ZERG-L2-005, ZERG-L2-009 |
| **Verification** | `python -c "from zerg.orchestrator import Orchestrator; o = Orchestrator('test'); print(o.status())"` |
| **Estimate** | 60 min |
| **Status** | TODO |

---

### ZERG-L3-002: Merge Gate Integration

| Attribute | Value |
|-----------|-------|
| **Description** | Combine git ops + quality gates + level controller for merge workflow |
| **Files Create** | `zerg/merge.py` |
| **Files Modify** | None |
| **Files Read** | `zerg/git_ops.py`, `zerg/gates.py`, `zerg/levels.py`, `zerg/logging.py` |
| **Dependencies** | ZERG-L2-006, ZERG-L2-010, ZERG-L2-004 |
| **Verification** | `python -c "from zerg.merge import MergeCoordinator; mc = MergeCoordinator()"` |
| **Estimate** | 45 min |
| **Status** | TODO |

---

### ZERG-L3-003: Worker Protocol Handler

| Attribute | Value |
|-----------|-------|
| **Description** | Worker startup sequence, task claiming, completion reporting, exit handling |
| **Files Create** | `zerg/worker_protocol.py` |
| **Files Modify** | None |
| **Files Read** | `zerg/state.py`, `zerg/verify.py`, `zerg/worktree.py`, `zerg/logging.py` |
| **Dependencies** | ZERG-L2-005, ZERG-L2-007, ZERG-L2-001 |
| **Verification** | `python -c "from zerg.worker_protocol import WorkerProtocol; wp = WorkerProtocol(worker_id=0)"` |
| **Estimate** | 50 min |
| **Status** | TODO |

---

### ZERG-L3-004: Rush Command Implementation ⭐ CRITICAL PATH

| Attribute | Value |
|-----------|-------|
| **Description** | Full /zerg rush flow: parse graph, assign workers, launch containers, monitor |
| **Files Create** | `zerg/commands/rush.py` |
| **Files Modify** | `zerg/cli.py` (add rush subcommand) |
| **Files Read** | `zerg/orchestrator.py`, `zerg/parser.py`, `zerg/assign.py`, `zerg/worktree.py` |
| **Dependencies** | ZERG-L3-001, ZERG-L2-003, ZERG-L2-008, ZERG-L2-001 |
| **Verification** | `python -m zerg rush --help` |
| **Estimate** | 45 min |
| **Status** | TODO |

---

### ZERG-L3-005: Status Command Implementation

| Attribute | Value |
|-----------|-------|
| **Description** | /zerg status output: progress bars, worker table, event log |
| **Files Create** | `zerg/commands/status.py` |
| **Files Modify** | `zerg/cli.py` (add status subcommand) |
| **Files Read** | `zerg/state.py`, `zerg/orchestrator.py`, `zerg/types.py` |
| **Dependencies** | ZERG-L3-001, ZERG-L2-005 |
| **Verification** | `python -m zerg status --help` |
| **Estimate** | 30 min |
| **Status** | TODO |

---

### ZERG-L3-006: Stop Command Implementation

| Attribute | Value |
|-----------|-------|
| **Description** | /zerg stop flow: graceful shutdown, checkpoint, container cleanup |
| **Files Create** | `zerg/commands/stop.py` |
| **Files Modify** | `zerg/cli.py` (add stop subcommand) |
| **Files Read** | `zerg/orchestrator.py`, `zerg/containers.py`, `zerg/state.py` |
| **Dependencies** | ZERG-L3-001, ZERG-L2-009 |
| **Verification** | `python -m zerg stop --help` |
| **Estimate** | 25 min |
| **Status** | TODO |

---

### ZERG-L3-007: Retry Command Implementation

| Attribute | Value |
|-----------|-------|
| **Description** | /zerg retry flow: reset task state, re-queue for execution |
| **Files Create** | `zerg/commands/retry.py` |
| **Files Modify** | `zerg/cli.py` (add retry subcommand) |
| **Files Read** | `zerg/state.py`, `zerg/orchestrator.py` |
| **Dependencies** | ZERG-L3-001, ZERG-L2-005 |
| **Verification** | `python -m zerg retry --help` |
| **Estimate** | 20 min |
| **Status** | TODO |

---

### ZERG-L3-008: Logs Command Implementation

| Attribute | Value |
|-----------|-------|
| **Description** | /zerg logs: stream worker logs, filtering, tail/follow modes |
| **Files Create** | `zerg/commands/logs.py` |
| **Files Modify** | `zerg/cli.py` (add logs subcommand) |
| **Files Read** | `zerg/logging.py`, `zerg/containers.py` |
| **Dependencies** | ZERG-L1-005, ZERG-L2-009 |
| **Verification** | `python -m zerg logs --help` |
| **Estimate** | 25 min |
| **Status** | TODO |

---

### ZERG-L3-009: Cleanup Command Implementation

| Attribute | Value |
|-----------|-------|
| **Description** | /zerg cleanup: remove worktrees, branches, logs, containers |
| **Files Create** | `zerg/commands/cleanup.py` |
| **Files Modify** | `zerg/cli.py` (add cleanup subcommand) |
| **Files Read** | `zerg/worktree.py`, `zerg/git_ops.py`, `zerg/containers.py` |
| **Dependencies** | ZERG-L2-001, ZERG-L2-010, ZERG-L2-009 |
| **Verification** | `python -m zerg cleanup --help` |
| **Estimate** | 20 min |
| **Status** | TODO |

---

## Level 4: Commands

*Slash command prompt refinement and integration. Depend on Level 3.*

### ZERG-L4-001: Init Command Refinement

| Attribute | Value |
|-----------|-------|
| **Description** | Update /zerg init prompt with detection logic, generate config |
| **Files Create** | `zerg/commands/init.py` |
| **Files Modify** | `.claude/commands/zerg:init.md`, `zerg/cli.py` |
| **Files Read** | `zerg/config.py` |
| **Dependencies** | ZERG-L1-003, ZERG-L1-008 |
| **Verification** | `python -m zerg init --help` |
| **Estimate** | 30 min |
| **Status** | TODO |

---

### ZERG-L4-002: Plan Command Refinement

| Attribute | Value |
|-----------|-------|
| **Description** | Update /zerg plan prompt with requirements template, approval flow |
| **Files Create** | None |
| **Files Modify** | `.claude/commands/zerg:plan.md` |
| **Files Read** | `.gsd/specs/phase2/architecture_synthesis.md` |
| **Dependencies** | ZERG-L3-001 |
| **Verification** | `cat .claude/commands/zerg:plan.md | grep -q "APPROVED"` |
| **Estimate** | 20 min |
| **Status** | TODO |

---

### ZERG-L4-003: Design Command Refinement

| Attribute | Value |
|-----------|-------|
| **Description** | Update /zerg design prompt with task graph generation, validation |
| **Files Create** | None |
| **Files Modify** | `.claude/commands/zerg:design.md` |
| **Files Read** | `zerg/validation.py`, `.gsd/specs/phase2/architecture_synthesis.md` |
| **Dependencies** | ZERG-L1-007 |
| **Verification** | `cat .claude/commands/zerg:design.md | grep -q "task-graph.json"` |
| **Estimate** | 25 min |
| **Status** | TODO |

---

### ZERG-L4-004: Rush Command Prompt Update ⭐ CRITICAL PATH

| Attribute | Value |
|-----------|-------|
| **Description** | Sync /zerg rush prompt with Python implementation, add examples |
| **Files Create** | None |
| **Files Modify** | `.claude/commands/zerg:rush.md` |
| **Files Read** | `zerg/commands/rush.py` |
| **Dependencies** | ZERG-L3-004 |
| **Verification** | `cat .claude/commands/zerg:rush.md | grep -q "worker-assignments.json"` |
| **Estimate** | 20 min |
| **Status** | TODO |

---

### ZERG-L4-005: Status Command Prompt Update

| Attribute | Value |
|-----------|-------|
| **Description** | Sync /zerg status prompt with Python implementation, add output examples |
| **Files Create** | None |
| **Files Modify** | `.claude/commands/zerg:status.md` |
| **Files Read** | `zerg/commands/status.py` |
| **Dependencies** | ZERG-L3-005 |
| **Verification** | `cat .claude/commands/zerg:status.md | grep -q "Progress:"` |
| **Estimate** | 15 min |
| **Status** | TODO |

---

### ZERG-L4-006: Worker Command Refinement

| Attribute | Value |
|-----------|-------|
| **Description** | Update /zerg worker prompt with protocol, context handling, exit codes |
| **Files Create** | None |
| **Files Modify** | `.claude/commands/zerg:worker.md` |
| **Files Read** | `zerg/worker_protocol.py` |
| **Dependencies** | ZERG-L3-003 |
| **Verification** | `cat .claude/commands/zerg:worker.md | grep -q "70%"` |
| **Estimate** | 25 min |
| **Status** | TODO |

---

### ZERG-L4-007: Merge Command Creation

| Attribute | Value |
|-----------|-------|
| **Description** | Create /zerg merge prompt for manual gate triggering |
| **Files Create** | `.claude/commands/zerg:merge.md`, `zerg/commands/merge_cmd.py` |
| **Files Modify** | `zerg/cli.py` |
| **Files Read** | `zerg/merge.py` |
| **Dependencies** | ZERG-L3-002 |
| **Verification** | `python -m zerg merge --help` |
| **Estimate** | 20 min |
| **Status** | TODO |

---

### ZERG-L4-008: Logs Command Prompt Creation

| Attribute | Value |
|-----------|-------|
| **Description** | Create /zerg logs prompt with filtering, streaming examples |
| **Files Create** | `.claude/commands/zerg:logs.md` |
| **Files Modify** | None |
| **Files Read** | `zerg/commands/logs.py` |
| **Dependencies** | ZERG-L3-008 |
| **Verification** | `test -f .claude/commands/zerg:logs.md` |
| **Estimate** | 15 min |
| **Status** | TODO |

---

### ZERG-L4-009: Stop Command Prompt Creation

| Attribute | Value |
|-----------|-------|
| **Description** | Create /zerg stop prompt with graceful/force options |
| **Files Create** | `.claude/commands/zerg:stop.md` |
| **Files Modify** | None |
| **Files Read** | `zerg/commands/stop.py` |
| **Dependencies** | ZERG-L3-006 |
| **Verification** | `test -f .claude/commands/zerg:stop.md` |
| **Estimate** | 15 min |
| **Status** | TODO |

---

### ZERG-L4-010: Cleanup Command Prompt Creation

| Attribute | Value |
|-----------|-------|
| **Description** | Create /zerg cleanup prompt with options documentation |
| **Files Create** | `.claude/commands/zerg:cleanup.md` |
| **Files Modify** | None |
| **Files Read** | `zerg/commands/cleanup.py` |
| **Dependencies** | ZERG-L3-009 |
| **Verification** | `test -f .claude/commands/zerg:cleanup.md` |
| **Estimate** | 15 min |
| **Status** | TODO |

---

## Level 5: Quality

*Testing, security, and documentation. Depend on Level 4.*

### ZERG-L5-001: Unit Tests Foundation

| Attribute | Value |
|-----------|-------|
| **Description** | Pytest setup, fixtures, test utilities for core components |
| **Files Create** | `tests/__init__.py`, `tests/conftest.py`, `tests/test_config.py`, `tests/test_types.py` |
| **Files Modify** | `pyproject.toml` (add pytest config) |
| **Files Read** | `zerg/config.py`, `zerg/types.py` |
| **Dependencies** | ZERG-L1-002, ZERG-L1-003 |
| **Verification** | `pytest tests/test_config.py -v` |
| **Estimate** | 40 min |
| **Status** | TODO |

---

### ZERG-L5-002: Core Component Tests

| Attribute | Value |
|-----------|-------|
| **Description** | Tests for worktree, levels, gates, verification, git ops |
| **Files Create** | `tests/test_worktree.py`, `tests/test_levels.py`, `tests/test_gates.py`, `tests/test_git_ops.py` |
| **Files Modify** | None |
| **Files Read** | `zerg/worktree.py`, `zerg/levels.py`, `zerg/gates.py`, `zerg/git_ops.py` |
| **Dependencies** | ZERG-L2-001, ZERG-L2-004, ZERG-L2-006, ZERG-L2-010 |
| **Verification** | `pytest tests/test_worktree.py tests/test_levels.py tests/test_gates.py tests/test_git_ops.py -v` |
| **Estimate** | 60 min |
| **Status** | TODO |

---

### ZERG-L5-003: Integration Tests ⭐ CRITICAL PATH

| Attribute | Value |
|-----------|-------|
| **Description** | End-to-end tests: rush with mock containers, level progression, merge flow |
| **Files Create** | `tests/integration/__init__.py`, `tests/integration/test_rush_flow.py`, `tests/integration/test_merge_flow.py` |
| **Files Modify** | None |
| **Files Read** | `zerg/orchestrator.py`, `zerg/merge.py` |
| **Dependencies** | ZERG-L3-001, ZERG-L3-002 |
| **Verification** | `pytest tests/integration/ -v` |
| **Estimate** | 90 min |
| **Status** | TODO |

---

### ZERG-L5-004: Security Hooks

| Attribute | Value |
|-----------|-------|
| **Description** | Pre-commit hook for non-ASCII detection, commit message validation |
| **Files Create** | `.zerg/hooks/pre-commit`, `zerg/security.py` |
| **Files Modify** | None |
| **Files Read** | `.gsd/specs/phase2/architecture_synthesis.md` |
| **Dependencies** | ZERG-L3-001 |
| **Verification** | `bash .zerg/hooks/pre-commit` |
| **Estimate** | 30 min |
| **Status** | TODO |

---

### ZERG-L5-005: Documentation Update

| Attribute | Value |
|-----------|-------|
| **Description** | Update README, ARCHITECTURE.md with final implementation details |
| **Files Create** | None |
| **Files Modify** | `README.md`, `ARCHITECTURE.md` |
| **Files Read** | `zerg/*.py`, `.claude/commands/*.md` |
| **Dependencies** | ZERG-L4-004, ZERG-L4-005 |
| **Verification** | `grep -q "pip install" README.md` |
| **Estimate** | 45 min |
| **Status** | TODO |

---

## Critical Path Analysis

The critical path determines minimum completion time:

```
ZERG-L1-001 (15m) Python Package
    ↓
ZERG-L1-003 (20m) Config Schema
    ↓
ZERG-L2-001 (45m) Worktree Manager
    ↓
ZERG-L2-004 (35m) Level Controller
    ↓
ZERG-L3-001 (60m) Orchestrator Core
    ↓
ZERG-L3-004 (45m) Rush Command
    ↓
ZERG-L4-004 (20m) Rush Prompt Update
    ↓
ZERG-L5-003 (90m) Integration Tests

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Critical Path Total: 330 minutes (5.5 hours)
```

**Non-Critical Path Parallelization**: With ZERG, 27 additional tasks could execute in parallel across the 5.5 hour critical path, reducing total elapsed time by approximately 60%.

---

## Session Planning

### Session Estimates

| Session | Tasks | Focus Area | Est. Time |
|---------|-------|------------|-----------|
| 1 | ZERG-L1-001 through L1-004 | Package structure, types, config | 70 min |
| 2 | ZERG-L1-005 through L1-008 | Logging, exceptions, CLI | 70 min |
| 3 | ZERG-L2-001, L2-002 | Worktree, ports | 65 min |
| 4 | ZERG-L2-003, L2-004 | Parser, level controller | 65 min |
| 5 | ZERG-L2-005, L2-006, L2-007 | State, gates, verify | 95 min |
| 6 | ZERG-L2-008, L2-009, L2-010 | Assign, containers, git | 115 min |
| 7 | ZERG-L3-001, L3-002 | Orchestrator, merge | 105 min |
| 8 | ZERG-L3-003, L3-004 | Worker protocol, rush | 95 min |
| 9 | ZERG-L3-005 through L3-009 | Remaining commands | 120 min |
| 10 | ZERG-L4-001 through L4-005 | Prompt refinements | 110 min |
| 11 | ZERG-L4-006 through L4-010 | New prompts | 90 min |
| 12 | ZERG-L5-001, L5-002 | Unit tests | 100 min |
| 13 | ZERG-L5-003 | Integration tests | 90 min |
| 14 | ZERG-L5-004, L5-005 | Security, docs | 75 min |

**Total Sessions**: 12-14 (accounting for debugging and iteration)

---

## Dependency Graph

```
Level 1 (Foundation)
├── L1-001 Package ─────────┬──────────────────────────────────────┐
│   ├── L1-002 Types ───────┼──────────────┬───────────────────────┤
│   │   ├── L1-003 Config ──┼──────────────┼───────────────────────┤
│   │   └── L1-007 Schema ──┘              │                       │
│   ├── L1-004 Constants ───────────────────┤                       │
│   ├── L1-005 Logging ─────────────────────┤                       │
│   ├── L1-006 Exceptions ──────────────────┤                       │
│   └── L1-008 CLI ─────────────────────────┘                       │
│                                                                   │
Level 2 (Core)                                                      │
├── L2-001 Worktree ────────┬───────────────────────────────────────┤
├── L2-002 Ports ───────────┤                                       │
├── L2-003 Parser ──────────┤                                       │
├── L2-004 Levels ──────────┼───────────────────────────────────────┤
├── L2-005 State ───────────┤                                       │
├── L2-006 Gates ───────────┤                                       │
├── L2-007 Verify ──────────┤                                       │
├── L2-008 Assign ──────────┤                                       │
├── L2-009 Containers ──────┤                                       │
└── L2-010 Git Ops ─────────┘                                       │
                                                                    │
Level 3 (Integration)                                               │
├── L3-001 Orchestrator ────┬───────────────────────────────────────┤
├── L3-002 Merge ───────────┤                                       │
├── L3-003 Worker Protocol ─┤                                       │
├── L3-004 Rush Cmd ────────┤                                       │
├── L3-005 Status Cmd ──────┤                                       │
├── L3-006 Stop Cmd ────────┤                                       │
├── L3-007 Retry Cmd ───────┤                                       │
├── L3-008 Logs Cmd ────────┤                                       │
└── L3-009 Cleanup Cmd ─────┘                                       │
                                                                    │
Level 4 (Commands)                                                  │
├── L4-001 Init ────────────┬───────────────────────────────────────┤
├── L4-002 Plan ────────────┤                                       │
├── L4-003 Design ──────────┤                                       │
├── L4-004 Rush Prompt ─────┤                                       │
├── L4-005 Status Prompt ───┤                                       │
├── L4-006 Worker Prompt ───┤                                       │
├── L4-007 Merge Prompt ────┤                                       │
├── L4-008 Logs Prompt ─────┤                                       │
├── L4-009 Stop Prompt ─────┤                                       │
└── L4-010 Cleanup Prompt ──┘                                       │
                                                                    │
Level 5 (Quality)                                                   │
├── L5-001 Unit Tests Foundation ───────────────────────────────────┤
├── L5-002 Core Tests ──────────────────────────────────────────────┤
├── L5-003 Integration Tests ───────────────────────────────────────┤
├── L5-004 Security ────────────────────────────────────────────────┤
└── L5-005 Documentation ───────────────────────────────────────────┘
```

---

## File Ownership Matrix

| File | Task | Operation |
|------|------|-----------|
| `zerg/__init__.py` | ZERG-L1-001 | create |
| `zerg/py.typed` | ZERG-L1-001 | create |
| `pyproject.toml` | ZERG-L1-001, L1-008, L5-001 | create, modify, modify |
| `requirements.txt` | ZERG-L1-001 | create |
| `zerg/types.py` | ZERG-L1-002 | create |
| `zerg/config.py` | ZERG-L1-003 | create |
| `zerg/constants.py` | ZERG-L1-004 | create |
| `zerg/logging.py` | ZERG-L1-005 | create |
| `zerg/exceptions.py` | ZERG-L1-006 | create |
| `zerg/schemas/task_graph.json` | ZERG-L1-007 | create |
| `zerg/schemas/__init__.py` | ZERG-L1-007 | create |
| `zerg/validation.py` | ZERG-L1-007 | create |
| `zerg/cli.py` | ZERG-L1-008, L3-004-009, L4-001,007 | create, modify |
| `zerg/worktree.py` | ZERG-L2-001 | create |
| `zerg/ports.py` | ZERG-L2-002 | create |
| `zerg/parser.py` | ZERG-L2-003 | create |
| `zerg/levels.py` | ZERG-L2-004 | create |
| `zerg/state.py` | ZERG-L2-005 | create |
| `zerg/gates.py` | ZERG-L2-006 | create |
| `zerg/verify.py` | ZERG-L2-007 | create |
| `zerg/assign.py` | ZERG-L2-008 | create |
| `zerg/containers.py` | ZERG-L2-009 | create |
| `zerg/git_ops.py` | ZERG-L2-010 | create |
| `zerg/orchestrator.py` | ZERG-L3-001 | create |
| `zerg/merge.py` | ZERG-L3-002 | create |
| `zerg/worker_protocol.py` | ZERG-L3-003 | create |
| `zerg/commands/rush.py` | ZERG-L3-004 | create |
| `zerg/commands/status.py` | ZERG-L3-005 | create |
| `zerg/commands/stop.py` | ZERG-L3-006 | create |
| `zerg/commands/retry.py` | ZERG-L3-007 | create |
| `zerg/commands/logs.py` | ZERG-L3-008 | create |
| `zerg/commands/cleanup.py` | ZERG-L3-009 | create |
| `zerg/commands/init.py` | ZERG-L4-001 | create |
| `.claude/commands/zerg:init.md` | ZERG-L4-001 | modify |
| `.claude/commands/zerg:plan.md` | ZERG-L4-002 | modify |
| `.claude/commands/zerg:design.md` | ZERG-L4-003 | modify |
| `.claude/commands/zerg:rush.md` | ZERG-L4-004 | modify |
| `.claude/commands/zerg:status.md` | ZERG-L4-005 | modify |
| `.claude/commands/zerg:worker.md` | ZERG-L4-006 | modify |
| `.claude/commands/zerg:merge.md` | ZERG-L4-007 | create |
| `zerg/commands/merge_cmd.py` | ZERG-L4-007 | create |
| `.claude/commands/zerg:logs.md` | ZERG-L4-008 | create |
| `.claude/commands/zerg:stop.md` | ZERG-L4-009 | create |
| `.claude/commands/zerg:cleanup.md` | ZERG-L4-010 | create |
| `tests/__init__.py` | ZERG-L5-001 | create |
| `tests/conftest.py` | ZERG-L5-001 | create |
| `tests/test_config.py` | ZERG-L5-001 | create |
| `tests/test_types.py` | ZERG-L5-001 | create |
| `tests/test_worktree.py` | ZERG-L5-002 | create |
| `tests/test_levels.py` | ZERG-L5-002 | create |
| `tests/test_gates.py` | ZERG-L5-002 | create |
| `tests/test_git_ops.py` | ZERG-L5-002 | create |
| `tests/integration/__init__.py` | ZERG-L5-003 | create |
| `tests/integration/test_rush_flow.py` | ZERG-L5-003 | create |
| `tests/integration/test_merge_flow.py` | ZERG-L5-003 | create |
| `.zerg/hooks/pre-commit` | ZERG-L5-004 | create |
| `zerg/security.py` | ZERG-L5-004 | create |
| `README.md` | ZERG-L5-005 | modify |
| `ARCHITECTURE.md` | ZERG-L5-005 | modify |

---

## Blockers Log

*Record blockers as they arise. Update status when resolved.*

| Date | Task | Blocker | Resolution | Status |
|------|------|---------|------------|--------|
| - | - | - | - | - |

---

## Completion Checklist

### Level 1 Complete When:
- [ ] `python -c "import zerg"` succeeds
- [ ] `python -m zerg --help` shows commands
- [ ] Config loads from `.zerg/config.yaml`
- [ ] All types importable

### Level 2 Complete When:
- [ ] Worktree create/delete works in test repo
- [ ] Level controller blocks correctly
- [ ] Quality gate runner executes commands
- [ ] Container manager starts test container

### Level 3 Complete When:
- [ ] Orchestrator event loop runs
- [ ] `/zerg rush` launches workers (dry-run)
- [ ] `/zerg status` shows progress
- [ ] Merge gate executes quality checks

### Level 4 Complete When:
- [ ] All slash command prompts updated
- [ ] New commands (merge, logs, stop, cleanup) have prompts
- [ ] CLI subcommands match prompts

### Level 5 Complete When:
- [ ] `pytest` passes with >80% coverage
- [ ] Integration tests pass
- [ ] Pre-commit hook validates
- [ ] README has installation instructions

---

## Notes

*Session notes, decisions, and discoveries.*

### 2026-01-25
- Created initial task backlog from Phase 2 architecture
- Identified 42 atomic tasks across 5 levels
- Critical path: 5.5 hours minimum
- Total estimate: 12-14 sessions
