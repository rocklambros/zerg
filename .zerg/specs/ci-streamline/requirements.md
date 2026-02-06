# Requirements: CI Streamline

**Status: APPROVED**
**Feature**: ci-streamline
**Source**: claudedocs/plan-ci-streamline.md
**Created**: 2026-02-05

## Problem Statement

The ZERG CI pipeline has 4 separate workflows triggering on PRs, producing 8 parallel jobs that compete for runners. Sequential gating (`smoke` -> `lint` -> `test`) adds ~30s overhead per gate. Command validation runs twice (own workflow + inside integration job). The smoke job runs 0 unique tests. This causes runner contention (observed as stuck `test(3)` on PR #153) and unnecessarily slow CI feedback.

## Functional Requirements

### FR-1: Merge 3 PR workflows into 1

- Delete `changelog-check.yml` and `command-validation.yml`
- Rename `pytest.yml` to `ci.yml` (name: "CI")
- Keep `release.yml` unchanged (different trigger: `release: published`)
- Triggers: `push: [main]`, `pull_request: [opened, synchronize, reopened, labeled, unlabeled]`
  - Note: `labeled`/`unlabeled` events needed for `skip-changelog` label detection

### FR-2: Create `quality` gate job

Single job replacing smoke + lint + changelog-check + command-validation:
1. `ruff check .` + `ruff format --check .`
2. `python -m zerg.validate_commands`
3. Inline changelog diff check (skip if `skip-changelog` label present)
   - Requires `fetch-depth: 0` for git diff
   - Uses `BASE_SHA`/`HEAD_SHA` from PR event context

### FR-3: Consolidate test sharding (4 unit + 1 integration -> 2 combined)

- Merge `tests/unit` and `tests/integration` into a single pytest run
- Use `pytest-split` with 2 shards: `pytest tests/ -m "not slow" --splits 2 --group N`
- Generate `.test_durations` file for optimal duration-based splitting (currently missing)
- Depends on: `quality` job
- Git config required: `init.defaultBranch`, `user.email`, `user.name`

### FR-4: Keep audit job as-is

- `pip-audit --desc` runs parallel with tests (no `needs:` dependency)
- Informational only (does not block merge)

### FR-5: Remove smoke job entirely

- The smoke job runs `pytest -m smoke` but those 5 marked test files (test_validation, test_constants, test_ast_analyzer, test_state, test_config) already run in the unit test suite
- Smoke job adds ~15s startup/teardown for zero unique coverage
- Remove `@pytest.mark.smoke` markers from the 5 files (cleanup, not blocking)

## Non-Functional Requirements

### NFR-1: CI speed

- Critical path time: ~1.5min (down from ~2.5min)
- Total runner startups: 4 (down from 8)
- Job start overhead: ~60s (down from ~120s)

### NFR-2: No broken merges

- Branch protection has no required status checks (`checks: []`), so renaming workflows/jobs is safe
- After merge, add required status checks for new job names if desired

### NFR-3: Backward compatibility

- `release.yml` must not change
- `skip-changelog` label behavior must be preserved
- All existing test coverage must pass (no tests removed or skipped)

## Scope Boundaries

### In Scope
- `.github/workflows/ci.yml` (new, from renamed `pytest.yml`)
- Delete `.github/workflows/changelog-check.yml`
- Delete `.github/workflows/command-validation.yml`
- Generate `.test_durations` for pytest-split
- Optionally remove `pytestmark = pytest.mark.smoke` from 5 test files

### Out of Scope
- Changes to `release.yml`
- Changes to test code (beyond removing smoke markers)
- Adding new test infrastructure (pytest-xdist already installed)
- Branch protection rule updates (manual post-merge step)
- Promoting audit to blocking

## Dependencies

- `pytest-split>=0.8` already in `pyproject.toml` dev deps
- `ruff>=0.14,<0.15` already available
- `pip-audit>=2.7.0` already available
- No new dependencies required

## Acceptance Criteria

1. Single `ci.yml` workflow replaces 3 PR workflows
2. PR triggers produce exactly 4 jobs: quality + test(1) + test(2) + audit
3. `quality` job runs lint, validate_commands, and changelog check
4. All existing tests pass under new sharding scheme
5. `release.yml` unchanged and functional
6. `skip-changelog` label still bypasses changelog check
7. No duplicate `validate_commands` execution

## Resolved Questions

1. **pytest-split vs pytest-xdist**: **RESOLVED** — Keep `pytest-split` (already installed, well-tested).
2. **Promote audit to blocking?**: **RESOLVED** — Out of scope for this change.
3. **Generate .test_durations**: **RESOLVED** — Commit the file; CI updates it via artifact on main branch pushes.
4. **Remove smoke markers?**: **RESOLVED** — Yes, include as minor cleanup task.

## Files Impact

| Action | File | Notes |
|--------|------|-------|
| DELETE | `.github/workflows/changelog-check.yml` | Absorbed into `quality` job |
| DELETE | `.github/workflows/command-validation.yml` | Absorbed into `quality` job |
| CREATE | `.github/workflows/ci.yml` | Renamed from `pytest.yml` |
| DELETE | `.github/workflows/pytest.yml` | Replaced by `ci.yml` |
| KEEP | `.github/workflows/release.yml` | Unchanged |
| CREATE | `.test_durations` | For pytest-split optimization |
| EDIT | `tests/unit/test_validation.py` | Remove smoke marker |
| EDIT | `tests/unit/test_constants.py` | Remove smoke marker |
| EDIT | `tests/unit/test_ast_analyzer.py` | Remove smoke marker |
| EDIT | `tests/unit/test_state.py` | Remove smoke marker |
| EDIT | `tests/unit/test_config.py` | Remove smoke marker |
