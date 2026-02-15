# Requirements: test-coverage-improvement

**Status: APPROVED**
**Created**: 2026-02-07
**Feature**: Improve Test Coverage to >75% Using Streamlined Test Method

## Problem Statement

Current overall test coverage is **77%** (25,590 total lines, 5,972 uncovered). While the aggregate exceeds 75%, **26 modules are below 75%** — 11 critically below 50%. These low-coverage modules represent critical infrastructure (merge coordination, state reconciliation, subprocess launching, status rendering) where bugs are most likely to hide.

### Coverage Gap Summary

| Category | Modules | Uncovered Lines | Impact |
|----------|---------|-----------------|--------|
| Critical (<50%) | 11 | ~1,178 | Merge, state, rendering, launcher |
| Low (50-74%) | 15 | ~789 | Git engines, protocol, coordinators |
| **Total** | **26** | **~1,967** | Core execution paths |

## Goals

1. Raise overall coverage from 77% to **>80%** (stretch: 85%)
2. Eliminate all modules below 50% coverage
3. Raise all critical-path modules to ≥75%
4. Follow the streamlined test method: parameterized tests, consolidation, no gap-filling files

## Approach: Streamlined Test Method

Per our established methodology:
- **Parameterize** repetitive test cases with `@pytest.mark.parametrize`
- **Direct unit testing** of classes/functions, not through CLI wrappers
- **Focused assertions** — test behavior, not implementation details
- **Shared fixtures** via conftest.py, not duplicated setup
- **No gap-filling files** — enhance existing test files or create ONE file per module

## Scope

### In Scope
- Adding tests for 26 under-covered modules
- Creating new test files only where none exist
- Enhancing existing test files where coverage is partial

### Out of Scope
- Refactoring production code
- Changing CI configuration
- Adding new test infrastructure
