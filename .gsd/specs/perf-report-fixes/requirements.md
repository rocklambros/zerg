# Requirements: perf-report-fixes

**Status**: APPROVED
**Created**: 2026-01-31

## Goal
Address all actionable issues from `claudedocs/performance-report.md` (score 86/100, 961 findings).
Target: eliminate false positives via tool configuration, fix real issues in production code, clean up legacy artifacts.

## Scope

### In Scope
1. Fix Dockerfile security/lint issues (Container Runtime: 0 → 100)
2. Remove unused variables/imports in production + test code
3. Delete legacy `.zerg/*.py` scripts duplicating `zerg/commands/`
4. Clean `htmlcov/` from git + gitignore it
5. Configure vulture adapter to exclude test files (eliminate ~160 false positives)
6. Configure jscpd adapter with ignore patterns (eliminate ~100 false positives)
7. Refactor oversized functions: `debug()` (334 LOC), `generate_backlog_markdown()` (205 LOC)

### Out of Scope
- Test file internal duplication (LOW severity, test-specific patterns)
- Test file maintainability indices (MEDIUM, inherent to test structure)
- Transitive dependency count (informational, not actionable)
- `.claude/commands/` ↔ `zerg/data/commands/` duplication (by design — install_commands.py)
- Pytest fixture parameter count (inherent to DI pattern)
