# Technical Design: perf-report-fixes

## Metadata
- **Feature**: perf-report-fixes
- **Status**: APPROVED
- **Created**: 2026-01-31

## 1. Overview

Address all actionable findings from the performance analysis report. Three strategies:
1. **Fix real issues**: Dockerfile lint, unused code, oversized functions
2. **Eliminate false positives**: Configure vulture + jscpd adapters to exclude non-actionable paths
3. **Clean artifacts**: Remove legacy scripts and generated HTML coverage from git

## 2. Architecture

No new components. All changes are modifications to existing files.

### 2.1 Component Breakdown

| Component | Changes | Files |
|-----------|---------|-------|
| Dockerfile | Add `--no-install-recommends`, non-root user | `.devcontainer/Dockerfile` |
| Production code | Remove unused var, refactor long functions | `design.py`, `debug.py`, `backlog.py` |
| Test code | Remove unused imports | 6 test files |
| Vulture adapter | Exclude test dirs | `vulture_adapter.py` |
| jscpd adapter | Add ignore patterns | `jscpd_adapter.py` |
| Git hygiene | Delete legacy scripts, gitignore htmlcov | `.gitignore`, `.zerg/*.py` |

## 3. Key Decisions

### Decision: Exclude test dirs from vulture rather than whitelist
**Rationale**: Pytest fixtures appear as "unused variables" to vulture. Excluding `tests/` is simpler and more maintainable than maintaining a whitelist of every fixture name. Production dead code detection remains active.

### Decision: Configure jscpd via CLI flags, not `.jscpd.json`
**Rationale**: Keep adapter self-contained. Adding `--ignore` flags to the adapter's subprocess call is cleaner than requiring a project-level config file.

### Decision: Drop shared-utility extraction (status/stop/retry/logs)
**Rationale**: The duplicated `detect_feature()` function is 24 lines across 4 files. Extracting to a shared module adds coupling and import complexity for minimal gain. MEDIUM severity, low ROI.

## 4. Implementation Plan

### Level 1 — Independent cleanups (5 parallel)
| Task | Description | Files |
|------|-------------|-------|
| PRF-L1-001 | Fix Dockerfile lint/security | `.devcontainer/Dockerfile` |
| PRF-L1-002 | Remove unused vars/imports | `design.py` + 6 test files |
| PRF-L1-003 | Delete legacy .zerg scripts | 5 `.zerg/*.py` files |
| PRF-L1-004 | gitignore + remove htmlcov | `.gitignore`, `htmlcov/` |
| PRF-L1-005 | Configure vulture to exclude tests | `vulture_adapter.py` |

### Level 2 — Adapter config + refactors (3 parallel, depends on L1)
| Task | Description | Files |
|------|-------------|-------|
| PRF-L2-001 | Configure jscpd ignore patterns | `jscpd_adapter.py` |
| PRF-L2-002 | Refactor debug.py long functions | `zerg/commands/debug.py` |
| PRF-L2-003 | Refactor backlog.py long function | `zerg/backlog.py` |

### Level 3 — Verification (1 task, depends on L2)
| Task | Description | Files |
|------|-------------|-------|
| PRF-L3-001 | Full test suite + ruff + mypy | None (read-only) |

## 5. File Ownership

| File | Task | Operation |
|------|------|-----------|
| `.devcontainer/Dockerfile` | PRF-L1-001 | modify |
| `zerg/commands/design.py` | PRF-L1-002 | modify |
| `tests/integration/test_orchestrator_fixes.py` | PRF-L1-002 | modify |
| `tests/unit/test_build_cmd.py` | PRF-L1-002 | modify |
| `tests/unit/test_log_aggregator.py` | PRF-L1-002 | modify |
| `tests/unit/test_orchestrator_timeout.py` | PRF-L1-002 | modify |
| `tests/unit/test_state_sync.py` | PRF-L1-002 | modify |
| `tests/unit/test_worker_protocol.py` | PRF-L1-002 | modify |
| `.zerg/analyze.py` | PRF-L1-003 | delete |
| `.zerg/build.py` | PRF-L1-003 | delete |
| `.zerg/refactor.py` | PRF-L1-003 | delete |
| `.zerg/review.py` | PRF-L1-003 | delete |
| `.zerg/test_runner.py` | PRF-L1-003 | delete |
| `.gitignore` | PRF-L1-004 | modify |
| `htmlcov/` | PRF-L1-004 | git rm |
| `zerg/performance/adapters/vulture_adapter.py` | PRF-L1-005 | modify |
| `zerg/performance/adapters/jscpd_adapter.py` | PRF-L2-001 | modify |
| `zerg/commands/debug.py` | PRF-L2-002 | modify |
| `zerg/backlog.py` | PRF-L2-003 | modify |

## 6. Parallel Execution Notes

- Max parallelization: 5 workers (Level 1)
- Level 2: 3 parallel tasks
- Level 3: 1 verification task
- Total: 9 tasks across 3 levels
