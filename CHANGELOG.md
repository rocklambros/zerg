# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-01-31

### Added

- Parallel Claude Code execution system with orchestrator, workers, and task graphs
- 25 slash commands (`/zerg:init`, `/zerg:plan`, `/zerg:design`, `/zerg:rush`, `/zerg:status`, `/zerg:merge`, `/zerg:stop`, `/zerg:retry`, `/zerg:cleanup`, `/zerg:worker`, `/zerg:debug`, `/zerg:build`, `/zerg:test`, `/zerg:review`, `/zerg:analyze`, `/zerg:refactor`, `/zerg:security`, `/zerg:git`, `/zerg:logs`, `/zerg:document`, `/zerg:estimate`, `/zerg:explain`, `/zerg:index`, `/zerg:select-tool`, `/zerg:plugins`)
- Shortcut aliases (`/z:*`) for all commands
- Dual execution modes: subprocess and Docker container
- Git worktree-based branch isolation for parallel workers
- Level-based task dependency system with automatic merge between levels
- Two-stage quality gates (per-task verification + per-level merge gates)
- State persistence with atomic writes and crash-safe recovery
- Claude Code Task ecosystem integration for cross-session coordination
- Context engineering plugin with command splitting and task-scoped context
- Doc engine with wiki generation, cross-references, and Mermaid diagrams
- Performance analysis adapters (semgrep, trivy, hadolint, lizard, radon, vulture, jscpd, cloc, deptry, pipdeptree, dive)
- Risk scoring, dry-run simulation, and what-if analysis
- Structured logging with per-worker JSONL output and log correlation
- Plugin system with lifecycle hooks and custom quality gates
- Security rules auto-fetched from OWASP 2025 and language-specific rulesets
- 5,953 tests at 97% coverage

### Fixed

- Reject unknown launcher modes instead of silent fallback to subprocess
- Show human-friendly launcher mode and worker count in rush output
- Audit skipped tests and convert unconditional skips to conditional skipif decorators
