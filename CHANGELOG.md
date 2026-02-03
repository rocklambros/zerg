# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- `/zerg:status` missing documented flags `--tasks`, `--workers`, `--commits` (#103)
- Flaky CI tests: hardcoded path in `test_container_e2e_live.py`, missing schema assertion in `test_full_rush_cycle.py` (#113)
- `pip-audit` failure on local package by using `--skip-editable` flag (#113)

### Added

- Container mode resilience: spawn retry with exponential backoff, task timeout watchdog, state reconciliation (#102)
- Worker crash recovery with automatic task reassignment (#102)
- Auto-respawn of failed workers to maintain target worker count (#102)
- Structured resilience logging to `.zerg/monitor.log` with ISO8601 timestamps (#102)
- `StateReconciler` class for periodic and level-transition state reconciliation (#102)
- `ResilienceEvent` enum constants for structured event logging (#102)
- `ResilienceConfig` and extended `WorkersConfig` with spawn retry, task timeout, and heartbeat settings (#102)
- `MonitorLogWriter` class for resilience event logging (#102)
- Enhanced heartbeat system with `progress_pct` field for task progress tracking (#102)
- 6 new `/z:analyze` check types: `dead-code`, `wiring`, `cross-file`, `conventions`, `import-chain`, `context-engineering`
- `--check all` now runs all 11 checkers with no exclusions (FR-8)
- `--check wiring` wraps `validate_module_wiring()` for orphaned module detection
- `--check cross-file` detects exported symbols never imported by other modules
- `--check import-chain` detects circular imports and deep import chains via DFS
- `--check conventions` validates snake_case naming, bracketed Task prefixes, file organization
- `--check context-engineering` wraps all 7 `validate_commands.py` checks
- AST cache module (`zerg/ast_cache.py`) shared between cross-file and import-chain checkers
- Graph property validation (`zerg/graph_validation.py`) for task dependency/consumer/reachability checks
- Graph validation integrated into `load_and_validate_task_graph()` as 4th validation step
- `CLAUDE_CODE_TASK_LIST_ID` printed in `/zerg:rush` and `/zerg:design` for worker coordination visibility
- Mandatory L5 final analysis task validation in `design.py`
- Analyze config section in `.zerg/config.yaml` with per-checker settings
- Unit and integration tests for all new checkers and graph validation
- CHANGELOG enforcement: `/zerg:design` always includes a CHANGELOG.md update task in the quality level
- CHANGELOG enforcement: `/zerg:git --action ship` validates CHANGELOG.md changes before pushing, warns if missing
- Post-approval handoff prompt in `/zerg:plan` — AskUserQuestion with 3 next-step options after requirements approval (#94)
- Documentation section (Section 10) added to requirements.md template referencing `/zerg:document` (#94)
- Missing `/zerg:git` flags added to `docs/commands.md`: `--no-docker`, `--include-stashes`, `--limit`, `--priority` (#94)
- Worker intelligence subsystem: heartbeat health monitoring with auto-restart for stalled workers (#67, #27, #30)
- Three-tier verification (syntax/correctness/quality) with configurable blocking and escalation for ambiguous failures (#67)
- Escalation protocol: workers report ambiguous failures to orchestrator with terminal alerts (#67)
- Structured progress reporting per worker with tier-level granularity (#67)
- Repository symbol map: Python AST + JS/TS regex extractor injected into worker context prompts (#67)
- New config sections: `heartbeat`, `escalation`, `verification_tiers`, `repo_map` in ZergConfig (#67)
- Documentation updates for worker intelligence: `docs/commands.md`, `docs/configuration.md`, `README.md`, wiki pages (#67)
- `STALLED` worker status and `ESCALATION` exit code (4) for worker state machine (#67)
- Worker health dashboard in `/zerg:status` with per-worker HEALTH table showing status, task, step, progress, restarts (#27)
- Incremental repo map indexing with MD5-based staleness detection and selective re-parse (#30)
- Token usage metrics subsystem: TokenCounter (API + heuristic), TokenTracker (per-worker), TokenAggregator (cumulative) (#24)
- REPOSITORY MAP and TOKEN USAGE sections in `/zerg:status` dashboard
- Optional `anthropic` dependency for exact token counting (`pip install zerg[metrics]`)
- `TokenMetricsConfig` with configurable api_counting (off by default), caching, and heuristic fallback
- StatusFormatter module for ASCII table formatting across all dashboard sections
- Automated PyPI release workflow with trusted publishing (OIDC), TestPyPI pre-release support, and SLSA provenance attestation (#23)
- `cleanup` action for `/zerg:git`: prune merged branches, stale remote refs, orphaned worktrees, Docker containers/images
- `issue` action for `/zerg:git`: create AI-optimized GitHub issues from codebase scan or user description with strict 8-section template
- `/zerg:git` now has 14 actions (was 12)
- `pip-audit` added to dev dependencies and CI workflow for supply chain security (#88)
- Routing telemetry wired into `MCPRouter` with configurable `telemetry_enabled` flag (#79)
- `GatePipeline` wired into orchestrator merge quality gates with artifact storage and staleness caching (#78)
- `ModeContext` wired into orchestrator for mode-aware gate strictness (#78)
- `CompactFormatter` wired into context plugin for token-efficient output when `ZERG_COMPACT_MODE` is set (#78)

### Changed

- Wiki files renamed from `Command-*.md` to `zerg-*.md` for consistency with `/zerg:` command prefix
- Wiki sidebar displays `/zerg:init` format instead of bare `init` names
- Global CLI Flags documentation updated: `--no-compact` (ON by default), `--no-loop` (ON by default), `--iterations N`
- `sidebar.py` references updated to match new wiki file naming
- All deprecated `--uc`/`--compact` flag references removed from documentation
- CI workflow now configures `git init.defaultBranch main` and user identity for test stability (#85)
- `conftest.py` fixture uses explicit `git init -b main` (#85)

### Fixed

- `ast.Str` deprecation warning removed from `extractor.py` — only `ast.Constant` used now (#87)
- Unawaited coroutine `RuntimeWarning` in `test_launcher_coverage.py` async mock setup (#91)
- 51 CI test failures caused by missing git config in GitHub Actions runners (#85)
- Duplicate `tmp_repo` fixtures removed from `test_worktree.py` and `test_worktree_extended.py` (#85)

### Removed

- Deprecated `--uc`/`--compact` and `--loop` hidden CLI flags and their deprecation callbacks (#84)
- Deprecated `--verbose`/`--quiet` global CLI flags (unused since project inception) (#81)
- Deprecated `--files` option from `refactor` and `analyze` commands — use positional PATH (#90)

### Previously Added

- Cross-cutting capability wiring: CLI flags now flow through to worker processes via `CapabilityResolver` (#78)
- `--no-compact` flag (compact output is now ON by default)
- `--no-loop` flag (improvement loops are now ON by default)
- `--iterations N` flag to override max loop iterations
- Context plugin capability sections: depth, mode, TDD, and efficiency guidance injected into worker prompts
- `WorkerContext` capability fields for cross-cutting capability awareness
- Unit and integration tests for capability resolver and wiring
- Integration wiring enforcement across the ZERG pipeline (#78, #79, #80, #81):
  - **Module wiring validator** (`validate_module_wiring()` in `validate_commands.py`): Detects orphaned Python modules with zero production imports; allowlists `__init__.py`, `__main__.py`, entry points; `--strict-wiring` CLI flag
  - **CI pytest workflow** (`.github/workflows/pytest.yml`): Runs unit tests, integration tests, and `validate_commands` on every PR
  - **Consumer matrix** in `design.md`/`design.core.md`: Tasks declare `consumers` and `integration_test` fields at design time
  - **Integration verification step** in `worker.core.md`: Workers run both isolation AND integration tests before commit
  - **Wiring quality gate** in `merge.core.md`: Detects new orphaned modules at merge time
  - **Anti-drift rules** #6 and #7 in `CLAUDE.md`: Every new module needs a production caller and an integration test
- 58 new tests (10 unit + 13 integration) for wiring enforcement
- Cross-cutting capabilities framework with 8 new subsystems (#76):
  - **Engineering Rules Framework** (`zerg/rules/`): YAML-based rule engine with loader, validator, and injector; ships with 25 rules across safety, quality, and efficiency rulesets
  - **Analysis Depth Tiers** (`zerg/depth_tiers.py`): 5-tier depth system (QUICK → ULTRATHINK) with `--quick`, `--think`, `--think-hard`, `--ultrathink` CLI flags; auto-detection from task descriptions
  - **Token Efficiency Mode** (`zerg/efficiency.py`): GREEN/YELLOW/RED zone detection with `--uc`/`--compact` CLI flag; symbol system and abbreviation engine for 30-50% token reduction
  - **Iterative Improvement Loops** (`zerg/loops.py`): LoopController with convergence detection, plateau threshold, regression rollback; `--loop`, `--iterations`, `--convergence` CLI options
  - **Verification Gates** (`zerg/verification_gates.py`): Gate pipeline with artifact storage, staleness detection, fresh-cache reuse, and stop-on-required-failure semantics
  - **Behavioral Mode Auto-Trigger** (`zerg/modes.py`): 5 modes (PRECISION, SPEED, EXPLORATION, REFACTOR, DEBUG) with `--mode` CLI flag; priority-based detection from keywords, efficiency zones, and depth tiers
  - **MCP Auto-Routing** (`zerg/mcp_router.py`, `zerg/mcp_telemetry.py`): Capability-based server matching with cost optimization, `--mcp`/`--no-mcp` CLI flags, routing telemetry
  - **TDD Enforcement** (`zerg/tdd.py`): Red-green-refactor protocol with `--tdd` CLI flag; anti-pattern detection (mock_heavy, testing_impl, no_assertions, large_tests)
- 8 new config sections in `ZergConfig`: `rules`, `efficiency`, `improvement_loops`, `verification`, `behavioral_modes`, `mcp_routing`, `tdd`, `error_recovery`
- Context engineering plugin now injects MCP routing hints and engineering rules into task-scoped context (budget: 15% rules, 15% security, 35% spec, 15% MCP)
- ~490 new tests across 8 test files for cross-cutting capabilities
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
- `--socratic` flag for `/zerg:brainstorm`: single-question interactive mode with 6 domain question trees, dynamic follow-ups, and saturation detection (#69)
- Trade-off Exploration phase (Phase 2.5): present architectural alternatives with pros/cons via AskUserQuestion (#70)
- Design Validation phase (Phase 2.6): 4-checkpoint validation loop (Scope, Entities, Workflows, NFRs) with revision support (#71)
- YAGNI Gate phase (Phase 2.7): multi-select feature filter to defer non-essential scope before issue generation (#72)
- 6 Socratic domain question trees: Auth, API Design, Data Pipeline, UI/Frontend, Infrastructure, General (#73)

### Changed

- `--uc`/`--compact` deprecated (compact is now default behavior)
- `--loop` deprecated (loops are now default behavior)
- Context plugin budget rebalanced: rules 10%, security 10%, spec 25%, MCP 10%, depth 10%, mode 10%, TDD 10%, efficiency 5%, buffer 10%
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

### Deprecated

- `--uc`, `--compact` flags (use `--no-compact` to disable instead)
- `--loop` flag (use `--no-loop` to disable instead)

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
