# Requirements: Quality Gates Lint Fix

**Status: APPROVED**
**Created:** 2026-02-03
**Feature:** quality-gates-fix

## Problem Statement

ZERG merge process fails due to lint gate running `ruff check .` on a codebase with 943 pre-existing lint errors. Workers also don't run lint before committing, allowing new errors to slip through until merge time.

## Goals

1. **Fix all existing lint errors** — Clean slate for the codebase
2. **Prevent new lint errors** — Early enforcement via pre-commit hooks
3. **Ensure merge gates pass** — Quality gates should succeed after cleanup

## Requirements

### R1: Ruff Configuration
- Line length: 120 characters (up from 100)
- Exclude paths: `.zerg/`, `tests/fixtures/`
- Select rules: E (errors), F (pyflakes), I (imports), UP (upgrades)
- All rules auto-fixable where possible

### R2: Fix Existing Errors
- Apply `ruff check . --fix` for 443 auto-fixable errors
- Apply `ruff check . --unsafe-fixes --select F841` for 90 unused variable errors (all in test files)
- Manually fix remaining ~50-100 errors after auto-fix
- Target: Zero lint errors after cleanup

### R3: Pre-commit Hook Setup
- Add `.pre-commit-config.yaml` with ruff hooks
- Hooks run `ruff check --fix` and `ruff format`
- Repo setup requirement (not auto-installed by workers)
- Document setup in CONTRIBUTING.md or README

### R4: Merge Gate Alignment
- Keep `ruff check .` as required gate in `.zerg/config.yaml`
- Gate should pass after cleanup (serves as safety net)
- No changes to gate command needed

## Non-Goals

- Fixing non-lint issues (type errors, test failures)
- Changing mypy or pytest gates
- Auto-installing pre-commit in worker containers

## Acceptance Criteria

1. `ruff check .` returns exit code 0 (no errors)
2. `.pre-commit-config.yaml` exists with ruff hooks
3. `pyproject.toml` contains ruff configuration
4. `/zerg:merge` lint gate passes
5. New commits automatically linted via pre-commit

## Technical Approach

### Phase 1: Configure ruff
Add to `pyproject.toml`:
```toml
[tool.ruff]
line-length = 120
exclude = [".zerg", "tests/fixtures"]

[tool.ruff.lint]
select = ["E", "F", "I", "UP"]
fixable = ["ALL"]
```

### Phase 2: Auto-fix errors
```bash
ruff check . --fix                          # 443 safe fixes
ruff check . --unsafe-fixes --select F841   # 90 unused vars (test files)
ruff format .                               # Format cleanup
```

### Phase 3: Manual fixes
- Fix remaining E501 (line-too-long) if any exceed 120 chars
- Fix E741 (ambiguous variable names) — usually just rename `l` to `length`
- Review and fix any F821 (undefined name) — potential bugs

### Phase 4: Add pre-commit
Create `.pre-commit-config.yaml`:
```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.4.4
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
```

### Phase 5: Verify
```bash
ruff check .           # Should return 0
pre-commit run --all-files  # Should pass
```

## Risks

| Risk | Mitigation |
|------|------------|
| Unsafe fixes break tests | All F841 are in test files, run tests after |
| Line length 120 too permissive | Still stricter than many projects (black=88, PEP8=79) |
| Pre-commit slows workers | Ruff is fast (<1s), auto-fix prevents blocking |

## Timeline

Single PR with all changes. Estimated scope:
- Config changes: 2 files
- Auto-fix: ~500 file touches (mostly import sorting)
- Manual fixes: ~20-30 lines across ~10 files
