# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `zerg/git/` package with 7 engine modules: commit, rescue, PR, release, history, pre-review, bisect
- `GitRunner` base class extracted from `GitOps` for low-level git command execution
- `GitConfig` Pydantic model with per-project config sections (commit, pr, release, rescue, review)
- Smart commit engine with auto/confirm/suggest modes and conventional commit detection
- PR creation engine with full context assembly (commits, issues, specs) and auto-labeling
- Automated release workflow with semver calculation, changelog generation, and GitHub releases
- Git rescue system with triple-layer undo (reflog, ops log, snapshot tags)
- History intelligence engine for commit squash, reorder, and message rewriting
- Pre-review context assembler for Claude Code AI analysis with security rule filtering
- AI-powered bisect engine with predictive commit ranking and semantic test analysis
- 5 new CLI actions: `pr`, `release`, `review`, `rescue`, `bisect` (total: 11 actions)
- `git.core.md` and `git.details.md` command file split for context engineering
- 402 new tests across 12 test files for the git package
- `ship` action for `/zerg:git`: full delivery pipeline (commit → push → PR → merge → cleanup) with `--no-merge` flag

### Changed

- `zerg/git_ops.py` converted to backward-compatible shim re-exporting from `zerg/git/ops.py`
- `zerg/commands/git_cmd.py` expanded from 6 to 11 actions with engine delegation
- Context engineering guardrails: automated drift detection and command validation (`python -m zerg.validate_commands`)
- Command template (`_template.md`) for new commands to inherit CE patterns by default
- CI workflow and pre-commit hook for command file validation
- `/zerg:brainstorm` command for open-ended feature discovery with competitive research, Socratic ideation, and automated GitHub issue creation
- 8 new feature issues for open-source release roadmap
- GitHub Actions workflow to enforce CHANGELOG.md updates on PRs (skippable with `skip-changelog` label)
- Claude Code instruction in CLAUDE.md to proactively update changelog when creating PRs
- Updated README, `docs/commands.md`, wiki `Command-git.md`, and `Command-Reference.md` to document all 11 `/zerg:git` actions

### Fixed

- `zerg status` now distinguishes between planned, in-design, and designed-but-not-executing features instead of a single generic message
- `zerg status` now shows "planned but not yet executed" instead of cryptic error for features with specs but no state
- `zerg cleanup` now clears `.gsd/.current-feature` when it points to a cleaned feature
- `zerg cleanup` now removes orphaned `.gsd/specs/{feature}/` directories
- `zerg rush` now clears `.gsd/.current-feature` on successful completion to prevent stale pointers

## [0.1.0] - 2026-01-31

### Added

- Parallel Claude Code execution system with orchestrator, workers, and task graphs
- 26 slash commands (`/zerg:brainstorm`, `/zerg:init`, `/zerg:plan`, `/zerg:design`, `/zerg:rush`, `/zerg:status`, `/zerg:merge`, `/zerg:stop`, `/zerg:retry`, `/zerg:cleanup`, `/zerg:worker`, `/zerg:debug`, `/zerg:build`, `/zerg:test`, `/zerg:review`, `/zerg:analyze`, `/zerg:refactor`, `/zerg:security`, `/zerg:git`, `/zerg:logs`, `/zerg:document`, `/zerg:estimate`, `/zerg:explain`, `/zerg:index`, `/zerg:select-tool`, `/zerg:plugins`)
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
