# Design: Issue #4 — Increase Test Coverage to ≥95%

## Current State

- **Overall**: 83% (17289 stmts, 2903 uncovered)
- **Target**: ≥95% (need ≤864 uncovered lines)
- **Must cover**: ~2039 additional lines
- **Test infrastructure**: Already built (helpers, fixtures, mocks)

## Coverage Gap by Impact

### Tier 1: doc_engine (0% → ≥80%) — 930 lines uncovered

| File | Stmts | Uncovered |
|------|-------|-----------|
| `zerg/doc_engine/renderer.py` | 210 | 210 |
| `zerg/doc_engine/extractor.py` | 135 | 135 |
| `zerg/doc_engine/crossref.py` | 134 | 134 |
| `zerg/doc_engine/dependencies.py` | 112 | 112 |
| `zerg/doc_engine/mermaid.py` | 99 | 99 |
| `zerg/doc_engine/publisher.py` | 92 | 92 |
| `zerg/doc_engine/detector.py` | 91 | 91 |
| `zerg/doc_engine/sidebar.py` | 47 | 47 |
| `zerg/doc_engine/templates.py` | 7 | 7 |
| `zerg/doc_engine/__init__.py` | 3 | 3 |

### Tier 2: Core infrastructure (67-71%) — 446 lines uncovered

| File | Stmts | Uncovered | Coverage |
|------|-------|-----------|----------|
| `zerg/launcher.py` | 688 | 226 | 67% |
| `zerg/orchestrator.py` | 503 | 152 | 70% |
| `zerg/containers.py` | 232 | 68 | 71% |

### Tier 3: Commands (16-76%) — 528 lines uncovered

| File | Stmts | Uncovered | Coverage |
|------|-------|-----------|----------|
| `zerg/commands/debug.py` | 731 | 172 | 76% |
| `zerg/commands/install_commands.py` | 154 | 122 | 21% |
| `zerg/commands/wiki.py` | 90 | 76 | 16% |
| `zerg/commands/cleanup.py` | 256 | 72 | 72% |
| `zerg/commands/rush.py` | 190 | 46 | 76% |
| `zerg/commands/document.py` | 54 | 40 | 26% |

### Tier 4: Adapters & utilities (25-73%) — 350 lines uncovered

| File | Stmts | Uncovered | Coverage |
|------|-------|-----------|----------|
| `zerg/performance/adapters/jscpd_adapter.py` | 66 | 47 | 29% |
| `zerg/performance/adapters/pipdeptree_adapter.py` | 60 | 45 | 25% |
| `zerg/performance/adapters/cloc_adapter.py` | 47 | 33 | 30% |
| `zerg/performance/adapters/deptry_adapter.py` | 42 | 26 | 38% |
| `zerg/performance/stack_detector.py` | 103 | 28 | 73% |
| `zerg/spec_loader.py` | 129 | 43 | 67% |
| `zerg/gates.py` | 120 | 41 | 66% |
| `zerg/env_diagnostics.py` | 254 | 58 | 77% |
| `zerg/render_utils.py` | 61 | 20 | 67% |
| `zerg/retry_backoff.py` | 15 | 5 | 67% |

### Tier 5: Near-complete (77-92%) — ~200 lines uncovered

Remaining files at 77-92%: worker_manager, worker_protocol, state, logging, dryrun, log_correlator, claude_tasks_reader, ports, etc.

## Task Graph

All tasks are Level 1 (independent — each tests different source files). Only the validation task depends on all others.

| ID | Title | Test File | Source Files | Uncovered Lines |
|----|-------|-----------|-------------|-----------------|
| COV-001 | doc_engine: renderer + templates | `tests/unit/test_doc_engine_renderer.py` | renderer.py, templates.py | 217 |
| COV-002 | doc_engine: extractor + detector | `tests/unit/test_doc_engine_extractor.py` | extractor.py, detector.py | 226 |
| COV-003 | doc_engine: crossref + dependencies | `tests/unit/test_doc_engine_crossref.py` | crossref.py, dependencies.py | 246 |
| COV-004 | doc_engine: mermaid + publisher + sidebar + init | `tests/unit/test_doc_engine_misc.py` | mermaid.py, publisher.py, sidebar.py, __init__.py | 241 |
| COV-005 | launcher.py uncovered paths | `tests/unit/test_launcher_coverage.py` | launcher.py | 226 |
| COV-006 | orchestrator.py uncovered paths | `tests/unit/test_orchestrator_coverage.py` | orchestrator.py | 152 |
| COV-007 | containers.py uncovered paths | `tests/unit/test_containers_coverage.py` | containers.py | 68 |
| COV-008 | commands/debug.py uncovered paths | `tests/unit/test_debug_coverage.py` | commands/debug.py | 172 |
| COV-009 | commands/install_commands.py | `tests/unit/test_install_commands.py` | commands/install_commands.py | 122 |
| COV-010 | commands/wiki.py + document.py | `tests/unit/test_wiki_document.py` | commands/wiki.py, commands/document.py | 116 |
| COV-011 | commands/cleanup.py + rush.py | `tests/unit/test_cleanup_rush_coverage.py` | commands/cleanup.py, commands/rush.py | 118 |
| COV-012 | Performance adapters (jscpd, pipdeptree, cloc, deptry) | `tests/unit/test_perf_adapters_coverage.py` | 4 adapter files | 151 |
| COV-013 | Utilities (spec_loader, gates, render_utils, retry_backoff, stack_detector) | `tests/unit/test_utils_coverage.py` | 5 utility files | 137 |
| COV-014 | Near-complete files (worker_manager, worker_protocol, state, logging, etc.) | `tests/unit/test_near_complete_coverage.py` | ~10 files at 77-92% | ~200 |
| COV-015 | Validation: full suite ≥95% | (run existing + new tests) | all | 0 |

## Execution Plan

```
Level 1 (max parallel):  COV-001 through COV-014  (14 independent tasks)
Level 2 (sequential):    COV-015 validation run
```

**Max parallelization**: 14 workers (but 5-7 is practical)
**Optimal workers**: 5 (widest useful parallelization)

## File Ownership

Each test file is created by exactly one task. No source files are modified — this is test-only work.

## Verification

Per-task: `python -m pytest {test_file} -v --cov={source_module} --cov-report=term-missing`
Final: `python -m pytest tests/ --cov=zerg --cov-report=term-missing | grep TOTAL`

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| doc_engine code may have complex dependencies | Med | Read source before writing tests, mock external deps |
| Some uncovered code may be dead code | Low | Flag for removal rather than testing |
| Mocking launcher/orchestrator subprocess calls | Med | Existing mock_launcher.py and async_helpers.py provide patterns |

## Approval

Status: DRAFT — awaiting review.
