# ZERG Development Backlog

**Updated**: 2026-01-30

## Completed

| # | Item | Completed | Commit |
|---|------|-----------|--------|
| 1 | State file IPC: Workers write WorkerState, orchestrator reloads in poll loop | 2026-01-28 | a189fc7 |
| 2 | Container execution: Docker image, ContainerLauncher, resource limits, health checks, security hardening | 2026-01-28 | ce7d58e |
| 4 | Debug cleanup: Gate verbose diagnostic details behind `--verbose` in troubleshoot.py | 2026-01-28 | 763ef8c |
| 3 | Test coverage: 96.53% coverage across 64 modules (4468 tests), P0 files all at 100% | 2026-01-28 | 06abc7c + 1dc4f8e |
| 6 | Log aggregation: Structured JSONL logging per worker, per-task artifact capture, read-side aggregation, CLI query/filter | 2026-01-29 | a0b6e66 |
| 5 | Production dogfooding: Real Docker E2E tests against ContainerManager and ContainerLauncher | 2026-01-29 | — |
| 7 | Task retry logic: Auto-retry failed tasks with backoff, max attempts | 2026-01-29 | — |
| 8 | Dry-run improvements: Pre-flight checks, risk scoring, what-if analysis, Gantt timeline, projected snapshots | 2026-01-29 | — |
| 9 | Troubleshoot enhancement: World-class debugger — multi-language error intel (Python/JS/Go/Rust/Java/C++), Bayesian hypothesis engine (33 patterns), cross-worker log correlation, code-aware recovery, environment diagnostics. 7 new modules, 383 tests. | 2026-01-30 | 53a0a97..4d1e407 |

## Backlog

| # | Area | Description | Effort | Status |
|---|------|-------------|--------|--------|
| 10 | `/z` shortcut alias | Create `/z` shortcut for all `/zerg` commands (e.g., `/z:rush`, `/z:status`). Support both prefixes with full autocomplete parity | Medium | Open |
| 11 | Rename troubleshoot → debug | Rename `/zerg:troubleshoot` to `/zerg:debug` (and `zerg troubleshoot` to `zerg debug`). Cascade rename across all code, commands, docs, tests, and references project-wide | Medium | Open |
| 12 | Performance analysis for `zerg analyze --performance` | Add `--performance` option to `zerg analyze` and `/zerg:analyze` that runs a comprehensive performance audit covering 140 factors across 16 categories (CPU/compute, memory, disk I/O, network I/O, database, caching, concurrency, code-level patterns, abstraction/structure, dependencies, code volume, error handling, container image, container runtime, orchestration, observability, architecture, AI code detection, security patterns). Static analysis via `radon` (cyclomatic complexity, maintainability index), `lizard` (function complexity/LOC), `vulture` (dead code), `semgrep` (perf anti-patterns: blocking I/O in async, N+1 queries, string concat in loops, regex in hot paths, missing timeouts, swallowed exceptions, sequential awaits, collection type mismatches, unbounded collections, etc.), `jscpd`/PMD CPD (copy-paste detection), `deptry` (unused/missing deps), `pipdeptree` (transitive dep analysis). Container analysis via `dive` (layer efficiency, image size), `hadolint` (Dockerfile linting), `trivy` (CVE scanning, secrets, misconfig). For factors not coverable by static tools (cache locality, branch prediction, NUMA, lock contention, etc.), generate an advisory checklist with descriptions and manual review guidance. Output: structured JSON report + rich CLI summary with severity ratings per category. See `claudedocs/performance_evaluation_factors.json` for the full factor catalog. | Large | Open |
