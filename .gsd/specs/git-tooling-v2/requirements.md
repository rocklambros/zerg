# Requirements: git-tooling-v2

**Status**: REVIEW
**Parent Issue**: #16
**Sub-Issues**: #42, #43, #44, #45, #46, #47, #48, #49

## Problem Statement
Current `/zerg:git` has 6 basic actions with naive commit message generation. The entire git workflow pipeline — from commit through PR to release — lacks AI intelligence, safety nets, and project-context awareness. No competing tool offers a unified solution.

## Functional Requirements

### FR-1: Smart Commit Engine (#42) — P0
- Multi-mode: auto / confirm (default) / suggest, configurable per-project
- Semantic diff analysis to detect commit type (feat/fix/refactor/etc.)
- Conventional commit format enforcement
- Smart staging suggestions (related unstaged files)
- Pre-commit message validation
- Multi-line body for complex changes (>3 files)

### FR-2: PR Creation (#43) — P0
- Full context assembly: commits + linked issues + CLAUDE.md + specs + test results
- Structured PR body: summary, change breakdown, test plan, linked issues
- Auto-labeling from conventional commit types
- Reviewer suggestion from CODEOWNERS + git blame
- Size warning at configurable LOC threshold (default: 400)
- Draft mode support

### FR-3: Release Workflow (#44) — P1
- Auto semver from conventional commits since last tag
- CHANGELOG.md generation grouped by type
- Annotated git tag with release notes
- GitHub release via `gh release create`
- Version file auto-detection and update (package.json, pyproject.toml)
- Dry-run and pre-release support

### FR-4: AI Bisect (#45) — P2
- Predictive phase: rank commits by probability of causing symptom
- Semantic good/bad from test output analysis (not just exit codes)
- Root cause explanation for offending commit
- Fix suggestions with confidence levels
- Fallback to manual bisect if AI confidence low

### FR-5: Rescue System (#46) — P1
- Layer 1: Enhanced reflog with human-readable descriptions
- Layer 2: Operation log (.zerg/git-ops.log) with full context
- Layer 3: Auto-snapshots (lightweight tags) before risky operations
- Commands: --list, --undo, --restore, --recover-branch
- Risk detection for rebase/merge/reset/force-push

### FR-6: History Intelligence (#47) — P1
- Smart squash: identify WIP/fixup/related commits
- Logical reorder by change domain
- Message rewriting to conventional format
- Interactive before/after preview
- Non-destructive: new branch created, original preserved

### FR-7: AI Pre-Review (#48) — P1
- Domains: security, performance, quality, architecture
- Pattern-based heuristic analysis (no LLM API calls)
- Confidence filtering (>80% threshold, configurable)
- Actionable fix suggestions per finding
- Report saved to .zerg/review-reports/

### FR-8: Architecture + Config (#49) — P0
- `zerg/git/` package with 7 engine modules
- GitRunner base class extracted from GitOps
- GitOps backward-compatible via shim in `zerg/git_ops.py`
- GitConfig Pydantic model in `.zerg/config.yaml`
- Context detection: solo / team / swarm

## Non-Functional Requirements

- **Backward compatibility**: `from zerg.git_ops import GitOps` must keep working
- **Performance**: All operations complete in <5s (excluding network I/O)
- **Test coverage**: >80% per engine module
- **No new dependencies**: Use stdlib + existing deps (click, rich, pydantic, pyyaml)
- **Command validation**: `python -m zerg.validate_commands` must pass
- **Split compliance**: git.md → git.core.md + git.details.md when >300 lines

## Scope Boundaries

**In scope**: All 8 features above, tests, config, CLI expansion, command file split
**Out of scope**: LLM-assisted review (future), IDE integrations, git hooks installation, CI/CD pipeline generation

## Dependencies
- `gh` CLI for PR creation and GitHub releases (graceful degradation if absent)
- Existing `zerg/git_ops.py` GitOps class (migrated, not rewritten)

## Acceptance Criteria
- [ ] `zerg/git/` package with all 7 engines + base + types + config
- [ ] `zerg/git_ops.py` is a backward-compatible shim
- [ ] 11 actions in CLI: commit, branch, merge, sync, history, finish, pr, release, review, rescue, bisect
- [ ] GitConfig in .zerg/config.yaml with all sections
- [ ] git.core.md + git.details.md split
- [ ] ~140 new tests across 10 test files, all passing
- [ ] `python -m zerg.validate_commands` passes
- [ ] All 4 existing GitOps consumers work without changes
