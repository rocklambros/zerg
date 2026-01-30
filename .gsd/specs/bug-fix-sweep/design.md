# Technical Design: bug-fix-sweep

## Metadata
- **Feature**: bug-fix-sweep
- **Status**: DRAFT
- **Created**: 2026-01-30

## 1. Overview

Fix 11 outstanding bugs. Most are independent single-file changes. The key architectural decisions:

- **Bug 1 (NotImplementedError)**: Convert `BaseChecker` and `BaseTransform` to use `abc.ABC` + `@abstractmethod`. This is the correct Python pattern — the current code uses concrete classes with `raise NotImplementedError` which is fragile.
- **Bug 2 (bare except)**: Replace `except Exception: pass` with `except Exception as e: logger.debug(...)` in non-critical paths, keeping the control flow identical. Only the 4 `state.py` lock releases and similar best-effort blocks need this treatment. The many `except Exception as e: logger.error(...)` patterns are already correct.
- **Bug 3 (.gitignore)**: Add entries and remove committed artifacts from git tracking.
- **Bug 4 (STATE.md)**: Regenerate from current state JSON.
- **Bug 5 (flaky test)**: Add explicit state isolation in test setup.
- **Bug 6 (hanging tests)**: Patch `time.sleep` and set `max_wait=0` in the 5 hanging tests.
- **Bug 7-8 (E2E timeouts)**: Add `@pytest.mark.timeout(120)` to Docker E2E tests.
- **Bug 9 (hardcoded paths)**: Extract to `ContainerConfig` dataclass constants.
- **Bug 10 (lock release)**: Add `logger.debug` to the 4 bare except blocks in state.py lock operations.
- **Bug 11 (debug prints)**: Already uses `console.print` for Rich CLI output — this is intentional for a CLI status command. No change needed (false positive).

## 2. Key Decisions

### Decision: ABC for base classes
- **Context**: `BaseChecker.check()` and `BaseTransform.analyze()/apply()` use `raise NotImplementedError`
- **Decision**: Use `abc.ABC` + `@abstractmethod`
- **Rationale**: Prevents instantiation of base class, catches missing implementations at import time

### Decision: Scope of bare-except fixes
- **Context**: 80+ `except Exception` blocks found. Most already log with `logger.error/warning`.
- **Decision**: Only fix the ~12 truly silent ones (`except Exception: pass` or `except Exception:` with no logging)
- **Rationale**: The logged ones are correct error handling. Only silent swallowing is a bug.

### Decision: Bug 11 is a false positive
- **Context**: `status.py` uses `console.print()` — these are Rich console outputs for CLI display, not debug statements
- **Rationale**: The review.md flagged them because the pattern-matcher saw `console.print` but Rich console output is the correct approach for a CLI status command

## 3. Implementation Plan

| Phase | Tasks | Parallel |
|-------|-------|----------|
| L1: Foundation | 5 | Yes |
| L2: Testing | 3 | Yes |

Max parallelization: 5 (widest level = L1)

## 4. File Ownership

| File | Task | Operation |
|------|------|-----------|
| zerg/commands/analyze.py | BF-L1-001 | modify |
| zerg/commands/refactor.py | BF-L1-001 | modify |
| .gitignore | BF-L1-002 | modify |
| .gsd/STATE.md | BF-L1-003 | modify |
| zerg/state.py | BF-L1-004 | modify |
| zerg/worker_protocol.py | BF-L1-004 | modify |
| zerg/commands/cleanup.py | BF-L1-004 | modify |
| zerg/commands/review.py | BF-L1-004 | modify |
| zerg/commands/troubleshoot.py | BF-L1-004 | modify |
| zerg/commands/test_cmd.py | BF-L1-004 | modify |
| zerg/commands/install_commands.py | BF-L1-004 | modify |
| zerg/commands/build.py | BF-L1-004 | modify |
| zerg/commands/logs.py | BF-L1-004 | modify |
| zerg/orchestrator.py | BF-L1-004 | modify |
| zerg/plugins.py | BF-L1-004 | modify |
| zerg/launcher.py | BF-L1-005 | modify |
| tests/unit/test_worker_protocol.py | BF-L2-001 | modify |
| tests/unit/test_assign.py | BF-L2-002 | modify |
| tests/e2e/test_docker_real.py | BF-L2-003 | modify |
| tests/e2e/test_bugfix_e2e.py | BF-L2-003 | modify |
