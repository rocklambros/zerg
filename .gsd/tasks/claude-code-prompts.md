# ZERG Implementation: Claude Code Prompts

Copy each prompt into Claude Code in sequence. Wait for completion before proceeding to next.

---

## SESSION 1

```
/sc:implement Implement ZERG Level 1 Foundation tasks (Part 1).

Read specs: .gsd/specs/phase3/implementation_backlog.md, .gsd/specs/phase2/architecture_synthesis.md

Execute in order:

1. ZERG-L1-001: Create zerg/__init__.py (with __version__="0.1.0"), zerg/py.typed, pyproject.toml (click>=8.0, pydantic>=2.0, pyyaml>=6.0, rich>=13.0), requirements.txt
   Verify: python -c "import zerg; print(zerg.__version__)"

2. ZERG-L1-004: Create zerg/constants.py with Level(IntEnum), TaskStatus(Enum), GateResult(Enum), WorkerStatus(Enum)
   Verify: python -c "from zerg.constants import Level, TaskStatus, GateResult"

3. ZERG-L1-006: Create zerg/exceptions.py with ZergError, ConfigurationError, TaskVerificationFailed, MergeConflict, WorkerError, GateFailure, WorktreeError
   Verify: python -c "from zerg.exceptions import ZergError, TaskVerificationFailed, MergeConflict"

4. ZERG-L1-002: Create zerg/types.py with TypedDict/dataclass: Task, TaskGraph, WorkerState, LevelStatus, GateConfig, MergeResult
   Verify: python -c "from zerg.types import TaskGraph, WorkerState, LevelStatus"

Update .gsd/tasks/session-tracker.md marking these COMPLETE. --ultrathink
```

---

## SESSION 2

```
/sc:implement Implement ZERG Level 1 Foundation tasks (Part 2).

Execute in order:

1. ZERG-L1-003: Create zerg/config.py with Pydantic models matching .zerg/config.yaml structure. Include ZergConfig.load() classmethod.
   Verify: python -c "from zerg.config import ZergConfig; c = ZergConfig.load(); print(c.workers.max_concurrent)"

2. ZERG-L1-007: Create zerg/schemas/__init__.py, zerg/schemas/task_graph.json (JSON Schema), zerg/validation.py with validate_task_graph(), validate_file_ownership(), validate_dependencies()
   Verify: python -c "from zerg.validation import validate_task_graph"

3. ZERG-L1-005: Create zerg/logging.py with get_logger(name, worker_id), setup_logging(), JsonFormatter for structured logs
   Verify: python -c "from zerg.logging import get_logger; log = get_logger('test'); log.info('works')"

4. ZERG-L1-008: Create zerg/cli.py with Click group and stub subcommands: init, plan, design, rush, status, stop, retry, logs, merge, cleanup. Add entry point to pyproject.toml.
   Verify: python -m zerg --help

Update .gsd/tasks/session-tracker.md marking Level 1 COMPLETE. --ultrathink
```

---

## SESSION 3

```
/sc:implement Implement ZERG Level 2 Core tasks (Part 1).

Execute in order:

1. ZERG-L2-001: Create zerg/worktree.py with WorktreeManager class: create(), delete(), list_worktrees(), get_branch_name(), exists(). Use subprocess for git worktree commands.
   Verify: python -c "from zerg.worktree import WorktreeManager; wm = WorktreeManager('.'); print(wm.list_worktrees())"

2. ZERG-L2-002: Create zerg/ports.py with PortAllocator class: allocate(), release(), is_available(). Use socket bind test for availability.
   Verify: python -c "from zerg.ports import PortAllocator; pa = PortAllocator(); print(pa.allocate(5))"

3. ZERG-L2-010: Create zerg/git_ops.py with GitOps class: current_branch(), create_branch(), delete_branch(), merge(), rebase(), has_conflicts(), commit(), create_staging_branch()
   Verify: python -c "from zerg.git_ops import GitOps; go = GitOps('.'); print(go.current_branch())"

Update .gsd/tasks/session-tracker.md marking these COMPLETE. --ultrathink
```

---

## SESSION 4

```
/sc:implement Implement ZERG Level 2 Core tasks (Part 2).

Execute in order:

1. ZERG-L2-004: Create zerg/levels.py with LevelController class: start_level(), get_tasks_for_level(), mark_task_complete(), mark_task_failed(), is_level_complete(), can_advance(), advance_level(), get_status()
   Verify: python -c "from zerg.levels import LevelController"

2. ZERG-L2-003: Create zerg/parser.py with TaskParser class: parse(), parse_dict(), get_task(), get_dependencies(), topological_sort(). Validate with zerg.validation.
   Verify: python -c "from zerg.parser import TaskParser"

3. ZERG-L2-006: Create zerg/gates.py with GateRunner class: run_gate(), run_all_gates(). Handle timeouts, capture stdout/stderr.
   Verify: python -c "from zerg.gates import GateRunner"

4. ZERG-L2-007: Create zerg/verify.py with VerificationExecutor class: verify(), verify_task(). Return VerificationResult with success, exit_code, stdout, stderr, duration_ms.
   Verify: python -c "from zerg.verify import VerificationExecutor"

Update .gsd/tasks/session-tracker.md marking these COMPLETE. --ultrathink
```

---

## SESSION 5

```
/sc:implement Implement ZERG Level 2 Core tasks (Part 3).

Execute in order:

1. ZERG-L2-005: Create zerg/state.py with StateManager class: load(), save(), get_task_status(), set_task_status(), get_worker_state(), set_worker_state(), claim_task(), release_task(), append_event(). File-based with .zerg/state/{feature}.json.
   Verify: python -c "from zerg.state import StateManager"

2. ZERG-L2-008: Create zerg/assign.py with WorkerAssignment class: assign(), get_worker_tasks(), get_task_worker(), rebalance(). Balance tasks per level, respect file ownership.
   Verify: python -c "from zerg.assign import WorkerAssignment"

3. ZERG-L2-009: Create zerg/containers.py with ContainerManager class: build(), start_worker(), stop_worker(), stop_all(), get_status(), get_logs(), health_check(), exec_in_worker(). Use docker/docker-compose.
   Verify: python -c "from zerg.containers import ContainerManager"

Update .gsd/tasks/session-tracker.md marking Level 2 COMPLETE. --ultrathink
```

---

## SESSION 6

```
/sc:implement Implement ZERG Level 3 Integration tasks (Part 1).

Execute in order:

1. ZERG-L3-001: Create zerg/orchestrator.py with Orchestrator class: start(), stop(), status(), _main_loop(), _start_level(), _on_level_complete(), _on_task_complete(), _spawn_worker(), _terminate_worker(). Coordinate LevelController, StateManager, ContainerManager, WorktreeManager.
   Verify: python -c "from zerg.orchestrator import Orchestrator"

2. ZERG-L3-002: Create zerg/merge.py with MergeCoordinator class: prepare_merge(), run_pre_merge_gates(), execute_merge(), run_post_merge_gates(), finalize(), abort(), full_merge_flow().
   Verify: python -c "from zerg.merge import MergeCoordinator"

3. ZERG-L3-003: Create zerg/worker_protocol.py with WorkerProtocol class: start(), claim_next_task(), execute_task(), report_complete(), report_failed(), check_context_usage(), should_checkpoint(), checkpoint_and_exit(). Exit codes: 0=done, 1=error, 2=checkpoint, 3=blocked.
   Verify: python -c "from zerg.worker_protocol import WorkerProtocol"

Update .gsd/tasks/session-tracker.md marking these COMPLETE. --ultrathink
```

---

## SESSION 7

```
/sc:implement Implement ZERG Level 3 Integration tasks (Part 2).

Execute in order:

1. ZERG-L3-004: Create zerg/commands/__init__.py and zerg/commands/rush.py with Click command: rush(workers, feature, dry_run, resume). Load task graph, validate, create assignment, start orchestrator, display progress with rich. Update zerg/cli.py to register.
   Verify: python -m zerg rush --help

2. ZERG-L3-005: Create zerg/commands/status.py with Click command: status(feature, watch, json_output). Display progress, level breakdown, worker table with rich. Update zerg/cli.py.
   Verify: python -m zerg status --help

3. ZERG-L3-006: Create zerg/commands/stop.py with Click command: stop(feature, worker_id, force). Graceful checkpoint or force terminate. Update zerg/cli.py.
   Verify: python -m zerg stop --help

Update .gsd/tasks/session-tracker.md marking these COMPLETE. --ultrathink
```

---

## SESSION 8

```
/sc:implement Implement ZERG Level 3 Integration tasks (Part 3).

Execute in order:

1. ZERG-L3-007: Create zerg/commands/retry.py with Click command: retry(task_id, feature, all_failed). Reset task status, clear assignment. Update zerg/cli.py.
   Verify: python -m zerg retry --help

2. ZERG-L3-008: Create zerg/commands/logs.py with Click command: logs(worker_id, feature, tail, follow, level). Stream from .zerg/logs/ or container, colorize with rich. Update zerg/cli.py.
   Verify: python -m zerg logs --help

3. ZERG-L3-009: Create zerg/commands/cleanup.py with Click command: cleanup(feature, all_features, keep_logs, dry_run). Remove worktrees, branches, containers. Update zerg/cli.py.
   Verify: python -m zerg cleanup --help

Update .gsd/tasks/session-tracker.md marking Level 3 COMPLETE. --ultrathink
```

## SESSION 9

```
/sc:implement Implement ZERG Level 4 Command tasks (Part 1).

Execute in order:

1. ZERG-L4-001: Create zerg/commands/init.py with detection logic for project type. Update .claude/commands/zerg:init.md with complete prompt. Register in cli.py.
   Verify: python -m zerg init --help

2. ZERG-L4-002: Update .claude/commands/zerg:plan.md with structured requirements template, APPROVED/REJECTED markers, example output.
   Verify: grep -q "APPROVED" .claude/commands/zerg:plan.md

3. ZERG-L4-003: Update .claude/commands/zerg:design.md with task decomposition guidelines, file ownership rules, level criteria, task-graph.json schema.
   Verify: grep -q "task-graph.json" .claude/commands/zerg:design.md

4. ZERG-L4-004: Update .claude/commands/zerg:rush.md with flag docs, worker-assignments.json format, progress display, resume instructions.
   Verify: grep -q "worker-assignments" .claude/commands/zerg:rush.md

5. ZERG-L4-005: Update .claude/commands/zerg:status.md with output examples, watch mode, JSON schema, worker state meanings.
   Verify: grep -q "Progress:" .claude/commands/zerg:status.md

Update .gsd/tasks/session-tracker.md marking these COMPLETE. --ultrathink
```

## SESSION 10

```
/sc:implement Implement ZERG Level 4 Command tasks (Part 2).

Execute in order:

1. ZERG-L4-006: Update .claude/commands/zerg:worker.md with protocol spec, 70% context threshold, exit codes, task claiming, WIP commit format.
   Verify: grep -q "70%" .claude/commands/zerg:worker.md

2. ZERG-L4-007: Create zerg/commands/merge_cmd.py with merge(feature, target, skip_gates, dry_run). Create .claude/commands/zerg:merge.md. Register in cli.py.
   Verify: python -m zerg merge --help

3. ZERG-L4-008: Create .claude/commands/zerg:logs.md with flag docs, log format, filtering examples.
   Verify: test -f .claude/commands/zerg:logs.md

4. ZERG-L4-009: Create .claude/commands/zerg:stop.md with graceful vs force, checkpoint behavior, recovery.
   Verify: test -f .claude/commands/zerg:stop.md

5. ZERG-L4-010: Create .claude/commands/zerg:cleanup.md with cleanup scope, dry-run usage, recovery.
   Verify: test -f .claude/commands/zerg:cleanup.md

Update .gsd/tasks/session-tracker.md marking Level 4 COMPLETE. --ultrathink
```

## SESSION 11

```
/sc:implement Implement ZERG Level 5 Quality tasks (Part 1).

Execute in order:

1. ZERG-L5-001: Create tests/__init__.py, tests/conftest.py (fixtures: tmp_repo, sample_config, sample_task_graph, mock_container_manager), tests/test_config.py, tests/test_types.py. Add pytest to pyproject.toml.
   Verify: pytest tests/test_config.py -v

2. ZERG-L5-002: Create tests/test_worktree.py, tests/test_levels.py, tests/test_gates.py, tests/test_git_ops.py with unit tests for each component.
   Verify: pytest tests/test_worktree.py tests/test_levels.py -v

Update .gsd/tasks/session-tracker.md marking these COMPLETE. --ultrathink
```

## SESSION 12

```
/sc:implement Implement ZERG Level 5 Quality tasks (Part 2).

Execute in order:

1. ZERG-L5-003: Create tests/integration/__init__.py, tests/integration/test_rush_flow.py (dry_run, single_level, multi_level, task_failure, checkpoint), tests/integration/test_merge_flow.py (clean, conflict, gate_failure).
   Verify: pytest tests/integration/ -v

2. ZERG-L5-004: Create .zerg/hooks/pre-commit (non-ASCII check, secrets check, commit message validation) and zerg/security.py with check functions and install_hooks().
   Verify: bash .zerg/hooks/pre-commit

3. ZERG-L5-005: Update README.md with installation (pip install -e .), quick start, command reference. Update ARCHITECTURE.md with final component list and data flow.
   Verify: grep -q "pip install" README.md

Update .gsd/tasks/session-tracker.md marking Level 5 COMPLETE. --ultrathink
```

## SESSION 13: Final Verification

```
/sc:implement Run final verification for ZERG implementation.

1. Run full test suite with coverage:
   pytest --cov=zerg --cov-report=term-missing

2. Verify all CLI commands work:
   python -m zerg --help
   python -m zerg init --help
   python -m zerg rush --help
   python -m zerg status --help

3. Verify imports:
   python -c "from zerg.orchestrator import Orchestrator; from zerg.merge import MergeCoordinator; from zerg.worker_protocol import WorkerProtocol"

4. Validate task graph schema:
   python -c "from zerg.validation import validate_task_graph; import json; validate_task_graph(json.load(open('.gsd/tasks/task-graph.json')))"

5. Check documentation:
   test -f README.md && grep -q "pip install" README.md
   test -f ARCHITECTURE.md

Report final status and any failures. Update .gsd/tasks/session-tracker.md with IMPLEMENTATION COMPLETE. --ultrathink
```

---

## Quick Reference

| Session | Tasks | Focus |
|---------|-------|-------|
| 1 | L1-001, L1-002, L1-004, L1-006 | Package, types, constants, exceptions |
| 2 | L1-003, L1-005, L1-007, L1-008 | Config, logging, validation, CLI |
| 3 | L2-001, L2-002, L2-010 | Worktree, ports, git ops |
| 4 | L2-003, L2-004, L2-006, L2-007 | Parser, levels, gates, verify |
| 5 | L2-005, L2-008, L2-009 | State, assignment, containers |
| 6 | L3-001, L3-002, L3-003 | Orchestrator, merge, worker protocol |
| 7 | L3-004, L3-005, L3-006 | Rush, status, stop commands |
| 8 | L3-007, L3-008, L3-009 | Retry, logs, cleanup commands |
| 9 | L4-001 to L4-005 | Init, plan, design, rush, status prompts |
| 10 | L4-006 to L4-010 | Worker, merge, logs, stop, cleanup prompts |
| 11 | L5-001, L5-002 | Unit tests |
| 12 | L5-003, L5-004, L5-005 | Integration tests, security, docs |
| 13 | - | Final verification |
