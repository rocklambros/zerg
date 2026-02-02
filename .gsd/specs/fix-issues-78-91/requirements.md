# Requirements: fix-issues-78-91

## Metadata
- **Feature**: fix-issues-78-91
- **Status**: REVIEW
- **Created**: 2026-02-02
- **Author**: /zerg:plan

---

## Scope: 11 Open Issues → 9 Actionable (2 to close)

### Issues to CLOSE (not real bugs)

| # | Title | Reason |
|---|-------|--------|
| #80 | worker_main.py not used by launcher | FALSE POSITIVE — invoked dynamically via `python -m zerg.worker_main` at launcher.py:493 and :764 |
| #89 | TODO stubs in test_cmd.py | BY DESIGN — these are template strings for generated test files, not incomplete code |

### Issues to FIX (grouped by size)

#### Trivial (1-line to ~10-line fixes)

| # | Title | Files | Fix |
|---|-------|-------|-----|
| #87 | ast.Str deprecation | `extractor.py:73` | Remove `ast.Str` from isinstance check |
| #91 | Unawaited coroutine warning | `test_launcher_coverage.py:~1064` | Fix mock setup in async test |

#### Small (single-file or 2-3 file changes)

| # | Title | Files | Fix |
|---|-------|-------|-----|
| #84 | Remove deprecated --uc/--compact/--loop | `cli.py:44,49,93-105` | Remove hidden options + deprecation callbacks |
| #90 | Remove deprecated --files flag | `refactor.py:443`, `analyze.py:390` | Remove option definitions + any shim code |
| #79 | mcp_telemetry.py orphaned | `mcp_router.py`, `mcp_telemetry.py` | Wire RoutingTelemetry into MCPRouter + add tests |
| #88 | Add pip-audit to CI | `.github/workflows/pytest.yml`, `pyproject.toml` | Add pip-audit step + dev dep |

#### Medium (multi-file, test fixture overhaul)

| # | Title | Files | Fix |
|---|-------|-------|-----|
| #85 | 51 CI test failures | `pytest.yml`, `conftest.py`, 3 test files | Add git config to CI, fix fixtures with explicit branch name, deduplicate |
| #81 | --verbose/--quiet unused | `cli.py`, `capability_resolver.py` | Wire global flags into CapabilityResolver → context plugin, or remove |

#### Large (cross-cutting wiring)

| # | Title | Files | Fix |
|---|-------|-------|-----|
| #78 | Wire capabilities into execution | `orchestrator.py`, `context_plugin.py`, multiple command files | Wire GatePipeline, CompactFormatter, ModeContext into execution path |

---

## Functional Requirements

### FR-1: Close false-positive issues (#80, #89)
Close issues with explanatory comments.

### FR-2: Fix ast.Str deprecation (#87)
Remove `ast.Str` from isinstance check in `extractor.py:73`. Only `ast.Constant` needed (Python 3.8+).

### FR-3: Fix unawaited coroutine warning (#91)
Fix async mock setup in `test_launcher_coverage.py` to eliminate RuntimeWarning.

### FR-4: Remove deprecated CLI flags (#84)
Remove `--uc`, `--compact`, `--loop` hidden options and deprecation warning callbacks from `cli.py`.

### FR-5: Remove deprecated --files flag (#90)
Remove `--files` option from `refactor.py` and `analyze.py`. Migrate any `args.files` references to positional PATH.

### FR-6: Wire mcp_telemetry (#79)
- `mcp_router.py` imports and uses `RoutingTelemetry` after each `route()` call
- Telemetry respects `config.mcp_routing.telemetry` flag
- Add `tests/unit/test_mcp_telemetry.py`
- Add integration test proving telemetry records real routing decisions

### FR-7: Add pip-audit to CI (#88)
- Add `pip-audit` as dev dependency
- Add audit step to `.github/workflows/pytest.yml` after dependency install

### FR-8: Fix CI test failures (#85)
- Add `git config --global init.defaultBranch main` to CI workflow
- Add `git config --global user.email/name` to CI workflow
- Fix `tests/conftest.py` `tmp_repo` fixture: explicit `git init -b main`
- Remove duplicate `tmp_repo` fixtures from `test_worktree.py` and `test_worktree_extended.py`
- Verify all 51 tests pass in CI

### FR-9: Wire --verbose/--quiet (#81)
- CapabilityResolver reads `ctx.obj["verbose"]` and `ctx.obj["quiet"]`
- Context plugin adjusts output detail level based on flags
- OR: Remove global flags since commands define their own (simpler option)

### FR-10: Complete capability wiring (#78)
Current state: resolver → env vars → launcher → context plugin guidance (text only). Missing:
- **GatePipeline**: Wire into orchestrator merge quality gates (replace/augment GateRunner)
- **CompactFormatter**: Wire into status command and worker prompt generation
- **ModeContext**: Wire mode.verification_level into gate strictness
- **LoopController**: Already instantiated but verify `.run()` is called
- **Depth/MCP/TDD**: Already flow as env vars → context plugin text guidance (sufficient for prompt-based commands)

---

## Non-Functional Requirements

### NFR-1: Zero test regressions
All 7218 existing tests must continue to pass.

### NFR-2: validate_commands passes
`python -m zerg.validate_commands` must pass (no orphaned modules, no drift).

### NFR-3: CI compatibility
All fixes must work in both local (macOS) and CI (Ubuntu) environments.

---

## Issue Dependency Order

```
Trivial (no deps):     #87, #91, #80-close, #89-close
Small (no deps):       #84, #90, #88
Small (depends on #78): #79 (mcp_telemetry wiring is part of capability wiring)
Medium (no deps):      #85
Medium (depends on #78): #81 (verbose/quiet feeds into capability resolver)
Large:                 #78
```

---

## Decision: --verbose/--quiet (#81)

**Recommendation**: Remove global `--verbose`/`--quiet` from `cli.py` since every command that needs it already defines its own. This is simpler and avoids adding dead plumbing. The global flags have never been consumed since project inception.

**Alternative**: Wire into CapabilityResolver. More complex, unclear benefit since commands already have their own verbose flags.

---

## Acceptance Criteria

- [ ] Issues #80, #89 closed with comments
- [ ] `grep -rn 'ast\.Str' zerg/` returns empty
- [ ] `pytest tests/ -W error::RuntimeWarning -q` passes (no unawaited coroutine)
- [ ] `--uc`, `--compact`, `--loop` rejected by CLI (not accepted at all)
- [ ] `--files` rejected by refactor and analyze commands
- [ ] `mcp_router.py` imports and calls `RoutingTelemetry`
- [ ] `tests/unit/test_mcp_telemetry.py` exists with coverage
- [ ] `pip audit` step in CI workflow
- [ ] All 51 previously-failing CI tests pass in GitHub Actions
- [ ] GatePipeline instantiated in orchestrator for merge quality gates
- [ ] CompactFormatter used in at least one command output path
- [ ] 7218+ tests pass, validate_commands clean
