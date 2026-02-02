# Technical Design: fix-issues-78-91

## Metadata
- **Feature**: fix-issues-78-91
- **Status**: DRAFT
- **Created**: 2026-02-02
- **Author**: /zerg:design

---

## 1. Overview

### 1.1 Summary
Fix 9 open issues (#78, #79, #81, #84, #85, #87, #88, #90, #91), close 2 false positives (#80, #89), remove unused --verbose/--quiet flags, push wiki to GitHub, and update CHANGELOG.

### 1.2 Goals
- Complete cross-cutting capability wiring (#78): GatePipeline, CompactFormatter, ModeContext
- Fix all CI test failures (#85) via git fixture overhaul
- Remove all deprecated flags (#84, #90) and dead flags (#81)
- Wire orphaned mcp_telemetry module (#79)
- Add pip-audit to CI (#88)
- Fix trivial warnings (#87, #91)
- Push updated wiki to live GitHub Wiki (fixes user's recurring "command-init" complaint)

### 1.3 Non-Goals
- Runtime Python changes to depth_tiers, mcp_router, tdd, modes (already wired via env vars → context plugin)
- Adding new capabilities beyond what's in the existing modules
- Refactoring the context plugin budget system

---

## 2. Architecture

### 2.1 Capability Wiring (Issue #78)

Current state (55% wired):
```
CLI flags → CapabilityResolver → ResolvedCapabilities → env vars → launcher → workers
                                                                         ↓
                                                              context_plugin reads env vars
                                                              → builds guidance text ✅
                                                              → GatePipeline ❌
                                                              → CompactFormatter ❌
                                                              → ModeContext ❌
```

Target state (100%):
```
orchestrator.py:
  - Import GatePipeline from verification_gates
  - Instantiate with capabilities.gates_enabled
  - Use GatePipeline.run() in merge quality gates (alongside existing GateRunner)

  - Import ModeContext from modes
  - Use mode.verification_level to set gate strictness

context_plugin.py:
  - Import CompactFormatter from efficiency
  - When ZERG_COMPACT_MODE=true, apply CompactFormatter to task context output

mcp_router.py:
  - Import RoutingTelemetry from mcp_telemetry
  - Record routing decisions after each route() call
```

### 2.2 CI Fix (Issue #85)

```
.github/workflows/pytest.yml:
  + git config --global init.defaultBranch main
  + git config --global user.email "ci@test.com"
  + git config --global user.name "CI"

tests/conftest.py:
  - git init -q
  + git init -q -b main

tests/unit/test_worktree.py:       DELETE local tmp_repo fixture (use global)
tests/unit/test_worktree_extended.py: DELETE local tmp_repo fixture (use global)
```

### 2.3 Component Breakdown

| Component | Files | Issues |
|-----------|-------|--------|
| Capability wiring | orchestrator.py, context_plugin.py | #78 |
| MCP telemetry wiring | mcp_router.py, test_mcp_telemetry.py | #79 |
| Flag removal | cli.py, refactor.py, analyze.py | #81, #84, #90 |
| CI fixtures | pytest.yml, conftest.py, 2 test files | #85 |
| Trivial fixes | extractor.py, test_launcher_coverage.py | #87, #91 |
| CI enhancement | pytest.yml, pyproject.toml | #88 |
| Wiki publish | (manual command, no code change) | user complaint |
| Housekeeping | CHANGELOG.md, close 2 issues | #80, #89 |

---

## 3. Key Decisions

### 3.1 Remove --verbose/--quiet Instead of Wiring

**Context**: Global --verbose/--quiet are stored in ctx.obj but never read. Commands define their own.

**Decision**: Remove from cli.py entirely.

**Rationale**: Zero consumers since project inception. Commands already have their own --verbose. Adding plumbing for dead flags adds complexity for no benefit.

### 3.2 GatePipeline Augments (Not Replaces) GateRunner

**Context**: orchestrator.py uses GateRunner for merge gates. GatePipeline exists but is disconnected.

**Decision**: GatePipeline wraps existing gate execution, adding artifact storage, staleness detection, and fresh-cache reuse. GateRunner continues to run the actual gate commands.

**Rationale**: GateRunner works. GatePipeline adds value-add features (caching, staleness) without breaking the working gate execution.

### 3.3 Wiki Push as Manual Step

**Context**: Local wiki files are correct but the live GitHub Wiki hasn't been updated.

**Decision**: Run `zerg wiki --push` as part of this feature delivery. No CI automation added.

**Rationale**: Wiki publishing is already implemented as a manual command. Automating it is a separate feature request.

---

## 4. Implementation Plan

### 4.1 Phase Summary

| Phase | Level | Tasks | Parallel |
|-------|-------|-------|----------|
| Trivial fixes | L0 | 5 | Yes (all 5) |
| Medium fixes | L1 | 3 | Yes (all 3) |
| Capability wiring | L2 | 2 | Yes |
| Finalize | L3 | 2 | Sequential |

### 4.2 File Ownership

| File(s) | Task | Op |
|---------|------|----|
| zerg/doc_engine/extractor.py | T-001 | modify |
| tests/unit/test_launcher_coverage.py | T-002 | modify |
| zerg/cli.py (deprecated flags) | T-003 | modify |
| zerg/commands/refactor.py, analyze.py | T-004 | modify |
| (close issues #80, #89 via gh) | T-005 | gh CLI |
| .github/workflows/pytest.yml | T-006 | modify |
| tests/conftest.py, test_worktree.py, test_worktree_extended.py | T-006 | modify |
| pyproject.toml, .github/workflows/pytest.yml | T-007 | modify |
| zerg/mcp_router.py, zerg/mcp_telemetry.py, tests/unit/test_mcp_telemetry.py | T-008 | modify+create |
| zerg/orchestrator.py | T-009 | modify |
| zerg/context_plugin.py | T-010 | modify |
| CHANGELOG.md | T-011 | modify |
| (wiki push via zerg wiki --push) | T-012 | command |

### 4.3 Dependency Graph

```
L0: T-001 + T-002 + T-003 + T-004 + T-005    [parallel, no deps]
L1: T-006 + T-007 + T-008                      [parallel, depends on L0]
L2: T-009 + T-010                               [parallel, depends on L1]
L3: T-011 → T-012                               [sequential, depends on L2]
```

---

## 5. Task Details

### T-001: Fix ast.Str deprecation (#87)
- Remove `ast.Str` from isinstance check in `extractor.py:73`
- Verify: `grep -rn 'ast\.Str' zerg/` returns empty
- Verify: `pytest tests/unit/test_extractor*.py -v` passes

### T-002: Fix unawaited coroutine warning (#91)
- Fix async mock setup in `test_launcher_coverage.py` class `TestContainerStartContainerAsync`
- Verify: `pytest tests/unit/test_launcher_coverage.py -v -W error::RuntimeWarning` passes

### T-003: Remove deprecated CLI flags (#84, #81)
- Remove `--uc`, `--compact` hidden option (cli.py:44) and deprecation callback (cli.py:93-95)
- Remove `--loop` hidden option (cli.py:49) and deprecation callback (cli.py:103-105)
- Remove `--verbose`, `--quiet` options (cli.py:37-38) and ctx.obj storage (cli.py:74-75)
- Update tests that reference these flags
- Verify: `pytest tests/unit/test_cli*.py -v` passes

### T-004: Remove deprecated --files flag (#90)
- Remove `--files/-f` from `refactor.py:443`
- Remove `--files/-p` from `analyze.py:390`
- Migrate any `args.files` references to PATH argument
- Verify: `pytest tests/unit/test_refactor*.py tests/unit/test_analyze*.py -v` passes

### T-005: Close false-positive issues (#80, #89)
- `gh issue close 80 --comment "..."` (worker_main.py is invoked dynamically)
- `gh issue close 89 --comment "..."` (TODOs are template stubs by design)
- No code changes

### T-006: Fix CI test failures (#85)
- Add git config steps to `.github/workflows/pytest.yml`
- Fix `tests/conftest.py` tmp_repo fixture: `git init -q -b main`
- Remove duplicate tmp_repo from `test_worktree.py` and `test_worktree_extended.py`
- Verify: `pytest tests/unit/test_worktree.py tests/unit/test_worktree_extended.py tests/unit/test_merge_coordinator_init.py -v` passes

### T-007: Add pip-audit to CI (#88)
- Add `pip-audit>=2.7.0` to dev dependencies in pyproject.toml
- Add pip-audit step to `.github/workflows/pytest.yml` after dependency install
- Verify: CI workflow YAML is valid

### T-008: Wire mcp_telemetry into mcp_router (#79)
- `mcp_router.py` imports RoutingTelemetry, instantiates it, calls record() after route()
- Respect `config.mcp_routing.telemetry` flag
- Create `tests/unit/test_mcp_telemetry.py` with full coverage
- Add integration test proving telemetry records real routing decisions
- Verify: `pytest tests/unit/test_mcp_telemetry.py tests/unit/test_mcp_router.py -v` passes

### T-009: Wire GatePipeline + ModeContext into orchestrator (#78 part 1)
- Import GatePipeline from verification_gates
- Instantiate when capabilities.gates_enabled is true
- Wire GatePipeline into merge quality gate execution (augment GateRunner)
- Import ModeContext, use mode.verification_level for gate strictness
- Wire LoopController.run() call (already instantiated, verify it's invoked)
- Verify: `pytest tests/unit/test_orchestrator*.py -v` passes

### T-010: Wire CompactFormatter into context_plugin (#78 part 2)
- Import CompactFormatter from efficiency
- When ZERG_COMPACT_MODE env var is true, apply CompactFormatter to built context
- Verify: `pytest tests/unit/test_context_plugin*.py -v` passes

### T-011: CHANGELOG + documentation update
- Update CHANGELOG.md [Unreleased] section with all changes
- Verify: `python -m zerg.validate_commands` passes
- Verify: `pytest tests/ -q` shows 7218+ pass, 0 fail

### T-012: Push wiki + final validation
- Run `zerg wiki --push` to publish updated wiki to GitHub
- Verify live wiki at github.com/rocklambros/zerg/wiki shows /zerg: prefix format
- Close issues #78, #79, #81, #84, #85, #87, #88, #90, #91 via `gh issue close`

---

## 6. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Removing --verbose breaks user scripts | Low | Low | Flag was never consumed, hidden |
| GatePipeline conflicts with GateRunner | Medium | Medium | Augment pattern, don't replace |
| CI fixture changes break local tests | Low | High | Test both local and CI |
| pip-audit finds vulnerabilities | Medium | Low | Document exceptions if needed |

---

## 7. Parallel Execution Notes

### 7.1 Recommended Workers
- Optimal: 5 workers (matches L0 width)
- Maximum useful: 5

### 7.2 Estimated Duration
- Sequential: ~90 min
- With 5 workers: ~40 min
- Speedup: ~2.2x
