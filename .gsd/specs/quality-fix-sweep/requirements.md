# Requirements: quality-fix-sweep

**Status: APPROVED**

## Summary

Fix 182 mypy errors across 38 files and 19 ruff lint violations. Errors break into 3 tiers:
- **P0 (Broken Code Paths)**: 34 attr-defined/name-defined errors — methods called on wrong types, missing attributes, undefined names
- **P1 (Type Mismatches)**: 60 errors — no-any-return, assignment mismatches, return type errors, missing annotations
- **P2 (Missing Type Params)**: 88 `dict`/`list`/`Callable` without generic params across 26 files

## Bug Categories

### P0: Broken Code Paths (attr-defined / name-defined)

1. **cleanup.py** — `BranchInfo.startswith/split` (lines 134,135,184,185) — should use `.name` attribute
2. **cleanup.py** — `WorktreeManager.remove()` (line 281) — should be `.delete()`
3. **cleanup.py** — `ContainerManager.stop_matching()` (line 306) — method doesn't exist
4. **stop.py** — `ContainerManager.signal_container/stop_container` (lines 189,254) — should use `stop_worker()`
5. **stop.py** — `StateManager.update_worker()` (lines 193,258) — use get/set pattern
6. **retry.py** — `StateManager.assign_task()` (lines 216,230) — should be `claim_task()`
7. **merge_cmd.py** — `MergeFlowResult.conflicts` (lines 129,131) — field doesn't exist
8. **merge_cmd.py** — `MergeCoordinator.merge_level()` (line 139) — method doesn't exist
9. **merge_cmd.py** — `list[QualityGate].items()` (line 265) — list treated as dict
10. **merge_cmd.py** — `GateRunResult == GateResult.PASS` (line 276) — wrong comparison
11. **rush.py** — `WhatIfReport.has_errors` (line 140) — DryRunReport assigned to wrong type
12. **rush.py** — `RiskReport` undefined (line 226) — forward ref without TYPE_CHECKING import
13. **review.py** — `str.file/line/message` (lines 516-527) — ReviewItem assigned to str-typed variable
14. **plan.py** — `Collection[str].append()` (lines 421,434,448) — dict value typed too narrowly

### P1: Type Mismatches & Missing Annotations

15. **state.py** — 9 errors: no-any-return (7), missing return type (1), missing annotation
16. **logging.py** — 3 errors: override mismatch, int/str assignment, arg-type
17. **launcher.py** — 3 errors: no-any-return, CompletedProcess type, str-bytes-safe
18. **security.py** — 2 errors: TextIOWrapper assigned to str, object not indexable
19. **review.py** — 6 errors: object not indexable (lines 150-168), missing annotation
20. **parser.py** — 3 errors: return-value mismatches, arg-type
21. **metrics.py** — 2 errors: list[int] vs list[int|float]
22. **command_executor.py** — 1 error: bytes|str vs str
23. **orchestrator.py** — 2 errors: no-any-return, arg-type
24. **ports.py** — 1 error: missing annotation
25. **validation.py** — 1 error: no-any-return
26. **retry_backoff.py** — 1 error: no-any-return
27. **plugins.py** — 2 errors: no-any-return, unused type-ignore
28. **config.py** — 1 error: (to investigate)
29. **dryrun.py** — unused import
30. **design.py** — missing annotation
31. **status.py** — Panel box arg

### P2: Missing Generic Type Parameters (88 errors)

32. **types.py** — 18 bare `dict` annotations
33. **backlog.py** — 11 bare `dict`
34. **diagnostics/** — 15 bare `dict` across 3 files
35. **commands/** — 32 bare `dict`/`list`/`Callable` across 10 command files
36. **Core modules** — 12 bare `dict` across plugins, risk_scoring, dryrun, whatif, etc.

### P3: Ruff Lint (19 issues)

37. **Line too long** — 11 files over 100 chars
38. **SIM115** — 3 open() without context manager in state.py
39. **SIM102** — 1 collapsible if in orchestrator.py
40. **B007** — 1 unused loop variable in orchestrator.py
41. **F821+F401** — RiskReport forward ref + unused import in rush.py
42. **F401** — unused import in dryrun.py
