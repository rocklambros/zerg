# Technical Design: git-tooling-v2

## Metadata
- **Feature**: git-tooling-v2
- **Status**: REVIEW
- **Parent Issue**: #16
- **Sub-Issues**: #42-#50

---

## 1. Overview

### 1.1 Summary
Create a `zerg/git/` package with 7 engine modules that extend `/zerg:git` from 6 to 11 actions. Each engine is a standalone module with its own types, config section, and test file. The existing `GitOps` class is decomposed into `GitRunner` (base) + `GitOps` (operations), with a backward-compatible shim at the original import path. A unified `GitConfig` Pydantic model adds per-project configuration to `.zerg/config.yaml`.

### 1.2 Goals
- 11 git actions: commit, branch, merge, sync, history, finish, pr, release, review, rescue, bisect
- Backward-compatible migration of `zerg/git_ops.py` → `zerg/git/`
- Per-project configuration with sensible defaults
- Exclusive file ownership for ZERG rush parallelization
- >80% test coverage per engine

### 1.3 Non-Goals
- LLM API calls from engines (pre-review uses Claude Code's native context)
- IDE integrations
- Git hooks installation
- CI/CD pipeline generation

---

## 2. Architecture

### 2.1 High-Level Design

```
zerg/git_ops.py (shim)
    │
    ▼
zerg/git/
├── __init__.py          ◄── Re-exports GitOps, BranchInfo, all engines
├── base.py              ◄── GitRunner: _run(), _validate_repo(), current_branch()
├── ops.py               ◄── GitOps(GitRunner): branch, merge, commit, push, fetch
├── types.py             ◄── CommitInfo, DiffAnalysis, ReviewFinding, CommitType
├── config.py            ◄── GitConfig + sub-models, context detection
│
├── commit_engine.py     ◄── DiffAnalyzer, CommitMessageGenerator, StagingSuggester
├── rescue.py            ◄── OperationLogger, SnapshotManager, RescueEngine
├── pr_engine.py         ◄── ContextAssembler, PRGenerator, PRCreator
├── release_engine.py    ◄── SemverCalculator, ChangelogGenerator, ReleaseCreator
├── history_engine.py    ◄── HistoryAnalyzer, RewritePlanner, SafeRewriter
├── prereview.py         ◄── ContextPreparer, DomainFilter, ReviewReporter
└── bisect_engine.py     ◄── CommitRanker, SemanticTester, BisectRunner

zerg/commands/git_cmd.py ◄── Thin router: action → engine.run()
zerg/config.py           ◄── ZergConfig.git: GitConfig (added field)
```

### 2.2 Component Breakdown

| Component | Responsibility | Issue | Files |
|-----------|---------------|-------|-------|
| GitRunner | Low-level git command execution | #49 | base.py |
| GitOps | Branch/merge/commit operations | #49 | ops.py |
| Types | Shared dataclasses and enums | #49 | types.py |
| GitConfig | Configuration + context detection | #49 | config.py |
| CommitEngine | Smart commit message generation | #42 | commit_engine.py |
| RescueEngine | Undo/recovery/snapshots | #46 | rescue.py |
| PREngine | PR creation with context | #43 | pr_engine.py |
| ReleaseEngine | Semver + changelog + release | #44 | release_engine.py |
| HistoryEngine | Squash/reorder/rewrite | #47 | history_engine.py |
| PreReview | Context assembly for AI review | #48 | prereview.py |
| BisectEngine | Predictive + semantic bisect | #45 | bisect_engine.py |
| CLI Router | Action dispatch | #50 | git_cmd.py |

### 2.3 Data Flow

```
User invokes: zerg git --action <ACTION> [flags]
    │
    ▼
git_cmd.py: parse flags → load GitConfig → instantiate GitRunner
    │
    ▼
Engine.run(runner, config, flags)
    │
    ├── commit_engine: staged diff → analyze → generate message → commit
    ├── pr_engine: commits → assemble context → format body → gh pr create
    ├── release_engine: tags → semver calc → changelog → tag → gh release
    ├── rescue: before risky op → snapshot; on --undo → restore
    ├── history_engine: commit log → analyze → plan rewrite → new branch
    ├── prereview: changed files → filter rules → assemble context → report
    └── bisect_engine: symptom → rank commits → run bisect → report
    │
    ▼
Output: Rich console output + optional file artifacts (.zerg/*)
```

---

## 3. Detailed Design

### 3.1 Data Models (types.py)

```python
from dataclasses import dataclass, field
from enum import Enum

class CommitType(str, Enum):
    FEAT = "feat"
    FIX = "fix"
    DOCS = "docs"
    STYLE = "style"
    REFACTOR = "refactor"
    TEST = "test"
    CHORE = "chore"
    PERF = "perf"
    CI = "ci"
    BUILD = "build"
    REVERT = "revert"

@dataclass(frozen=True)
class CommitInfo:
    sha: str
    message: str
    author: str
    date: str
    files: list[str] = field(default_factory=list)
    commit_type: CommitType | None = None

@dataclass
class DiffAnalysis:
    files_changed: list[str]
    insertions: int
    deletions: int
    by_extension: dict[str, list[str]]  # {".py": ["a.py", "b.py"]}
    by_directory: dict[str, list[str]]  # {"src/auth": ["login.py"]}

@dataclass
class ReviewFinding:
    domain: str          # security, performance, quality, architecture
    severity: str        # critical, warning, info
    file: str
    line: int | None
    message: str
    suggestion: str
    rule_id: str | None = None

@dataclass
class RescueSnapshot:
    timestamp: str
    branch: str
    commit: str
    operation: str
    tag: str
    description: str
```

### 3.2 Configuration (config.py)

```python
from pydantic import BaseModel, Field

class GitCommitConfig(BaseModel):
    mode: str = Field(default="confirm", pattern="^(auto|confirm|suggest)$")
    conventional: bool = True
    sign: bool = False

class GitPRConfig(BaseModel):
    context_depth: str = Field(default="full", pattern="^(diffs|issues|full)$")
    auto_label: bool = True
    size_warning_loc: int = Field(default=400, ge=100, le=5000)
    reviewer_suggestion: bool = True

class GitReleaseConfig(BaseModel):
    changelog_file: str = "CHANGELOG.md"
    tag_prefix: str = "v"
    github_release: bool = True

class GitRescueConfig(BaseModel):
    auto_snapshot: bool = True
    ops_log: str = ".zerg/git-ops.log"
    max_snapshots: int = Field(default=20, ge=1, le=100)

class GitReviewConfig(BaseModel):
    domains: list[str] = Field(default_factory=lambda: ["security", "performance", "quality", "architecture"])
    confidence_threshold: float = Field(default=0.8, ge=0.5, le=1.0)

class GitConfig(BaseModel):
    commit: GitCommitConfig = Field(default_factory=GitCommitConfig)
    pr: GitPRConfig = Field(default_factory=GitPRConfig)
    release: GitReleaseConfig = Field(default_factory=GitReleaseConfig)
    rescue: GitRescueConfig = Field(default_factory=GitRescueConfig)
    review: GitReviewConfig = Field(default_factory=GitReviewConfig)
    context_mode: str = Field(default="auto", pattern="^(solo|team|swarm|auto)$")

def detect_context(runner: "GitRunner") -> str:
    """Detect solo/team/swarm context.
    solo = no remote configured
    team = remote exists
    swarm = .zerg/state/ directory exists
    """
```

### 3.3 Base Module (base.py)

Extract from `GitOps`:
- `GitRunner.__init__(repo_path)` — resolve path, validate repo
- `GitRunner._validate_repo()` — check .git exists
- `GitRunner._run(*args, check, capture, timeout)` — subprocess wrapper
- `GitRunner.current_branch()` — rev-parse --abbrev-ref HEAD
- `GitRunner.current_commit()` — rev-parse HEAD
- `GitRunner.has_changes()` — status --porcelain

### 3.4 Engine Interfaces

Each engine follows:
```python
class XEngine:
    def __init__(self, runner: GitRunner, config: GitConfig): ...
    def run(self, **kwargs) -> int:  # 0=success, 1=failure
```

### 3.5 Pre-Review Context Assembly (prereview.py)

The prereview engine is a **context assembler**, not an analyzer. It:
1. Gets changed files from `git diff --name-only`
2. Filters security rules by file extension (.py → Python rules, .js → JS rules)
3. Extracts only the changed hunks (not full files)
4. Assembles a minimal, scoped context document
5. Outputs structured markdown to `.zerg/review-reports/`

The Claude Code AI assistant then reads the report and performs the actual analysis. This avoids separate API calls and leverages the AI's existing context window.

---

## 4. Key Decisions

### 4.1 Facade Migration (not Rewrite)
**Context**: Need to move GitOps into zerg/git/ package.
**Decision**: Move code → leave shim at original path.
**Rationale**: 4 existing consumers import from `zerg.git_ops`. Shim preserves backward compat with zero consumer changes.

### 4.2 Context Assembler Pattern for Pre-Review
**Context**: Pre-review could use heuristics, LLM API, or Claude Code context.
**Decision**: Engine assembles scoped context; Claude Code AI analyzes.
**Rationale**: No additional API cost, leverages AI already present in the session, extreme token efficiency through scoped diffs + filtered rules.

### 4.3 Bisect as Standalone Action
**Context**: Could nest bisect under review or make standalone.
**Decision**: Standalone `--action bisect`.
**Rationale**: Different UX (long-running, interactive), different inputs (--symptom), clearer CLI surface.

### 4.4 Config over Convention
**Context**: AI aggression level could be hardcoded or configurable.
**Decision**: Per-project config in `.zerg/config.yaml` with defaults.
**Rationale**: Different projects have different trust levels. Open source: suggest mode. Personal: auto mode. Team: confirm mode.

---

## 5. Implementation Plan

### 5.1 Phase Summary

| Phase | Level | Tasks | Workers | Issues |
|-------|-------|-------|---------|--------|
| Foundation | 0 | 1 | 1 | #49 |
| Core | 1 | 2 | 2 | #42, #46 |
| Features | 2 | 4 | 4 | #43, #44, #47, #48 |
| Advanced + Integration | 3 | 2 | 2 | #45, #50 |

### 5.2 File Ownership Matrix

| File | Task | Issue | Operation |
|------|------|-------|-----------|
| `zerg/git/__init__.py` | TASK-001 | #49 | create |
| `zerg/git/types.py` | TASK-001 | #49 | create |
| `zerg/git/config.py` | TASK-001 | #49 | create |
| `zerg/git/base.py` | TASK-001 | #49 | create |
| `zerg/git/ops.py` | TASK-001 | #49 | create |
| `zerg/git_ops.py` | TASK-001 | #49 | modify (shim) |
| `zerg/config.py` | TASK-001 | #49 | modify (add GitConfig) |
| `tests/unit/test_git_base.py` | TASK-001 | #49 | create |
| `tests/unit/test_git_config.py` | TASK-001 | #49 | create |
| `tests/unit/test_git_types.py` | TASK-001 | #49 | create |
| `zerg/git/commit_engine.py` | TASK-002 | #42 | create |
| `tests/unit/test_git_commit_engine.py` | TASK-002 | #42 | create |
| `zerg/git/rescue.py` | TASK-003 | #46 | create |
| `tests/unit/test_git_rescue.py` | TASK-003 | #46 | create |
| `zerg/git/pr_engine.py` | TASK-004 | #43 | create |
| `tests/unit/test_git_pr_engine.py` | TASK-004 | #43 | create |
| `zerg/git/release_engine.py` | TASK-005 | #44 | create |
| `tests/unit/test_git_release_engine.py` | TASK-005 | #44 | create |
| `zerg/git/history_engine.py` | TASK-006 | #47 | create |
| `tests/unit/test_git_history_engine.py` | TASK-006 | #47 | create |
| `zerg/git/prereview.py` | TASK-007 | #48 | create |
| `tests/unit/test_git_prereview.py` | TASK-007 | #48 | create |
| `zerg/git/bisect_engine.py` | TASK-008 | #45 | create |
| `tests/unit/test_git_bisect_engine.py` | TASK-008 | #45 | create |
| `zerg/commands/git_cmd.py` | TASK-009 | #50 | modify |
| `zerg/data/commands/git.md` | TASK-009 | #50 | modify |
| `zerg/data/commands/git.core.md` | TASK-009 | #50 | create |
| `zerg/data/commands/git.details.md` | TASK-009 | #50 | create |

### 5.3 Dependency Graph

```
TASK-001 (#49 Architecture)
    ├──► TASK-002 (#42 Commit Engine)
    │       ├──► TASK-004 (#43 PR Creation)
    │       ├──► TASK-005 (#44 Release)
    │       ├──► TASK-006 (#47 History)
    │       └──► TASK-007 (#48 Pre-Review)
    │                └──► TASK-008 (#45 Bisect)
    └──► TASK-003 (#46 Rescue)

TASK-002..008 ──► TASK-009 (#50 Integration)
```

---

## 6. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Shim breaks existing imports | Low | High | Test all 4 consumers in TASK-001 verification |
| Command file split fails validation | Low | Medium | Run `python -m zerg.validate_commands` in TASK-009 |
| `gh` CLI not available | Medium | Low | Graceful degradation: save PR/release artifacts locally |
| File ownership conflict during rush | Low | High | Matrix validated in task-graph.json; no shared files |
| Pre-review context too large | Medium | Medium | Budget cap of 4000 tokens per domain; truncate hunks |

---

## 7. Testing Strategy

### 7.1 Unit Tests
Each engine has a dedicated test file using:
- `tmp_repo` fixture from `tests/conftest.py` (creates real git repo in tmp_path)
- `unittest.mock.patch` for subprocess isolation when testing logic
- Pytest classes grouped by functionality

### 7.2 Test Counts (estimated)
| File | Test Count |
|------|------------|
| test_git_base.py | ~10 |
| test_git_config.py | ~12 |
| test_git_types.py | ~8 |
| test_git_commit_engine.py | ~20 |
| test_git_rescue.py | ~15 |
| test_git_pr_engine.py | ~15 |
| test_git_release_engine.py | ~15 |
| test_git_history_engine.py | ~15 |
| test_git_prereview.py | ~15 |
| test_git_bisect_engine.py | ~15 |
| **Total** | **~140** |

### 7.3 Verification Commands (per task)
All listed in task-graph.json. Global verification:
```bash
pytest tests/unit/test_git_*.py -x -v
python -c "from zerg.git_ops import GitOps, BranchInfo"
python -m zerg.validate_commands
python -m zerg git --help
```

---

## 8. Parallel Execution Notes

### 8.1 Safe Parallelization
- Level 0: 1 task (foundation must complete first)
- Level 1: 2 tasks in parallel (#42, #46) — zero file overlap
- Level 2: 4 tasks in parallel (#43, #44, #47, #48) — zero file overlap
- Level 3: 2 tasks in parallel (#45, #50) — zero file overlap

### 8.2 Recommended Workers
- Minimum: 1 worker (sequential, 9 tasks)
- Optimal: 4 workers (matches widest level)
- Maximum: 4 workers (no benefit beyond level 2 width)

---

## 9. Approval

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Architecture | | | PENDING |
| Engineering | | | PENDING |
