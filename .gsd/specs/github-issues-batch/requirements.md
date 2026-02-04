# Requirements: GitHub Issues Batch (105-111)

## Status: APPROVED

## Overview

Address GitHub issues 105-111 related to ZERG quality gates and bug fixes.

## Issues Covered

- #105: Command files missing Task prefixes
- #106: Circular imports + deep import chains
- #108: Workers continue after orchestrator pause
- #109: Worker hang on Claude API calls
- #110: Tasks complete out of level order
- #111: Task state inconsistency

## Deferred

- #107: Unused exports (requires extensive refactoring, separate effort)

## Critical Requirement

**All workers MUST run `ruff format` and `ruff check --fix` before staging changes.**

This prevents pre-commit hook failures during task commits.
