# Requirements: test-suite-reduction

**Status: APPROVED**
**Created**: 2026-02-06
**Feature**: Test Suite Reduction

## Problem Statement

After test-suite-cleanup (PR #155) removed ~2,800 LOC of broken/duplicate tests and test-suite-optimization (phases 1-2) added sharding + partial parameterization, the following issues remain:

1. **No smoke coverage**: 0 tests marked `@pytest.mark.smoke` despite marker+gate being defined
2. **No smoke CI job**: ci.yml lacks a fast-fail gate before the 2-minute test shards
3. **Launcher test fragmentation**: 8 files, ~355 tests, 7+ duplicated test classes across files
4. **Wasted CI budget**: Every push runs 2 full shards with no fast-fail path

## Functional Requirements

### FR-1: Smoke Test Marking

Add `@pytest.mark.smoke` to 25-30 fastest critical-path unit tests.

**Target files**:
- test_config.py, test_types.py, test_exceptions.py, test_graph_validation.py
- test_state.py, test_cli.py, test_launcher.py, test_parser.py, test_constants.py

**Acceptance Criteria**:
- `pytest -m smoke` collects >= 20 tests
- Smoke suite completes in < 30s
- Only unit tests marked (no integration/e2e)

### FR-2: Launcher Test Consolidation

Reduce 8 launcher test files to 4 by merging along source-module boundaries:

| Target File | Merges From | Tests Source Module |
|-------------|-------------|-------------------|
| test_launcher.py | + test_launcher_extended.py | launcher_types, env_validator |
| test_launcher_container_ops.py | test_launcher_errors + process + network + exec | container_launcher |
| test_launcher_coverage.py | (keep as-is) | base.py async, subprocess edge cases |
| test_launcher_configurator.py | (keep as-is) | launcher_configurator |

Deduplicate 7+ classes appearing in multiple files.

**Acceptance Criteria**:
- 8 files reduced to 4
- ~75 duplicate tests removed
- All unique assertions preserved
- pytest passes on all remaining launcher test files

### FR-3: Smoke CI Job

Add dedicated smoke job to `.github/workflows/ci.yml`:

```
quality -> smoke -> test (2 shards)
                 -> audit
```

**Acceptance Criteria**:
- Smoke job runs `pytest -m smoke -x --timeout=5 -q`
- Test shards depend on smoke (`needs: smoke`)
- Audit job unchanged (depends on quality)

### FR-4: CHANGELOG + Verification

- CHANGELOG.md updated under [Unreleased]
- .test_durations regenerated
- Full test suite passes with no regressions

## Non-Functional Requirements

- Coverage threshold 80% unchanged
- No security tests removed
- Smoke suite < 30s execution time

## Scope Boundaries

### In Scope
- Smoke marker application (25-30 tests)
- Launcher test file consolidation (8 -> 4)
- Smoke CI job addition
- CHANGELOG + verification

### Out of Scope
- test_worker_protocol.py consolidation (future)
- Further test_debug_cmd.py parameterization (StackTraceAnalyzer already done)
- E2E/pressure test changes
- Smart test selection based on changed files

## Dependencies

No new dependencies. All infrastructure already in place:
- `pytest-split>=0.8` (installed)
- `pytest-xdist>=3.0` (installed)
- Smoke marker registered in pyproject.toml
- Smoke quality gate defined in .zerg/config.yaml
