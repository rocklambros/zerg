# Phase 0 Blockers — Requirements

**Feature**: Pre-release preparation for ZERG public release as `zerg-ai` on PyPI
**Epic**: #179 | **Issues**: #180, #181, #182, #183, #184
**Status**: APPROVED

## Problem Statement

ZERG is ready for public release but the PyPI package name `zerg` is taken. The package must be renamed to `zerg-ai`, the CHANGELOG frozen, WIP files cleaned, GitHub infrastructure configured, and the release pipeline validated end-to-end via TestPyPI.

## Scope

### In Scope
- Rename PyPI distribution name from `zerg` to `zerg-ai` (issues #180)
- Create GitHub environments (`pypi`, `testpypi`) via `gh api` (#181)
- Add required CI status checks to branch protection (#181)
- Freeze CHANGELOG [Unreleased] → [0.2.0] with comparison links (#182)
- Bump version 0.1.0 → 0.2.0 in pyproject.toml + __init__.py (#182)
- Clean up WIP files, update .gitignore (#184)
- TestPyPI dry run with pre-release tag (#183)
- Close all 5 issues via `gh issue close`

### Out of Scope
- Renaming the GitHub repo (stays `rocklambros/zerg`)
- Changing Python imports (`import zerg` unchanged)
- Changing CLI command (`zerg --help` unchanged)
- Phase 1-3 community/CI/polish work

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| PyPI name | `zerg-ai` | `zerg` taken; brandable, search-friendly |
| Release version | `0.2.0` | 200+ changes since 0.1.0; stays 0.x |
| Branch strategy | Feature branch + PR | Formal review, CI validation |
| PyPI OIDC | Already registered | User confirmed done |

## Acceptance Criteria

1. `python -m build` produces `zerg_ai-0.2.0*.whl`
2. `pip install zerg-ai` works from TestPyPI
3. `zerg --help` works after install
4. No stale `pip install zerg` refs (only `zerg-ai`)
5. GitHub environments `pypi` + `testpypi` exist
6. Branch protection requires 5 CI checks
7. CHANGELOG has [0.2.0] section with comparison links
8. `git status` clean on main
9. Issues #180-#184 closed
