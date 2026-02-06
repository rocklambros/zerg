# Technical Design: CI Streamline

## Metadata
- **Feature**: ci-streamline
- **Status**: APPROVED
- **Created**: 2026-02-05
- **Source**: .zerg/specs/ci-streamline/requirements.md

---

## 1. Overview

### 1.1 Summary

Consolidate 4 GitHub Actions workflows (pytest, changelog-check, command-validation, release) into 2 (ci, release). The new `ci.yml` replaces 3 PR-triggered workflows with a single workflow containing 4 jobs: `quality`, `test` (2 shards), and `audit`. This halves runner startups, eliminates sequential gating overhead, and removes duplicate command validation.

### 1.2 Goals
- Reduce PR check suites from 3 to 1
- Reduce total jobs from 8 to 4
- Eliminate sequential gating overhead (~30s per gate)
- Remove duplicate `validate_commands` execution
- Maintain all existing test coverage and quality gates

### 1.3 Non-Goals
- Changes to `release.yml`
- Promoting `audit` to blocking
- Branch protection rule configuration (manual post-merge)
- Adding new test infrastructure

---

## 2. Architecture

### 2.1 High-Level Design

```
BEFORE (3 workflows, 8 jobs):

  pytest.yml                    changelog-check.yml    command-validation.yml
  ┌────────┐                    ┌───────────────┐      ┌──────────────┐
  │ smoke  │                    │ check-changelog│      │   validate   │
  └───┬────┘                    └───────────────┘      └──────────────┘
      │
  ┌───┴────┐
  │  lint  │
  └───┬────┘
      │
  ┌───┴──────────┬──────────┬──────────┬──────────┐
  │ test(1)│test(2)│test(3)│test(4)│integration│
  └────────┴──────┴──────┴──────┴───────────┘
  │ audit  │ (parallel, no deps)
  └────────┘

AFTER (1 workflow, 4 jobs):

  ci.yml
  ┌─────────────────┐     ┌─────────┐
  │     quality      │     │  audit  │  (parallel, no deps)
  │ lint+validate+cl │     └─────────┘
  └────────┬────────┘
           │
    ┌──────┴──────┐
    │             │
  ┌─┴──────┐  ┌──┴─────┐
  │test(1) │  │test(2) │
  │unit+int│  │unit+int│
  └────────┘  └────────┘
```

### 2.2 Component Breakdown

| Component | Responsibility | File |
|-----------|---------------|------|
| `ci.yml` | Single CI workflow with quality gate, test shards, audit | `.github/workflows/ci.yml` |
| `quality` job | Lint, validate_commands, changelog check | (inside ci.yml) |
| `test` job (matrix) | Run all tests across 2 shards using pytest-split | (inside ci.yml) |
| `audit` job | pip-audit for dependency vulnerabilities | (inside ci.yml) |
| `.test_durations` | Duration data for optimal pytest-split sharding | `.test_durations` |

### 2.3 Data Flow

1. PR opened/updated → `ci.yml` triggers
2. `quality` job starts immediately + `audit` job starts immediately (parallel)
3. `quality` runs lint → validate_commands → changelog check (sequential within job)
4. On `quality` success → 2 `test` shards start (parallel)
5. Each shard runs `pytest tests/ -m "not slow" --splits 2 --group N`
6. All 4 jobs report status to GitHub checks

---

## 3. Detailed Design

### 3.1 `quality` Job

```yaml
quality:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
      with:
        fetch-depth: 0  # needed for changelog diff

    - uses: actions/setup-python@v5
      with:
        python-version: '3.12'
        cache: 'pip'

    - name: Install package with dev dependencies
      run: pip install -e ".[dev]"

    - name: Lint check
      run: ruff check . && ruff format --check .

    - name: Validate command files
      run: python -m zerg.validate_commands

    - name: Check CHANGELOG.md updated
      if: github.event_name == 'pull_request' && !contains(github.event.pull_request.labels.*.name, 'skip-changelog')
      env:
        BASE_SHA: ${{ github.event.pull_request.base.sha }}
        HEAD_SHA: ${{ github.event.pull_request.head.sha }}
      run: |
        if git diff --name-only "$BASE_SHA" "$HEAD_SHA" | grep -q '^CHANGELOG.md$'; then
          echo "CHANGELOG.md was updated."
        else
          echo "::error::CHANGELOG.md was not updated. Add an entry under [Unreleased] or apply the 'skip-changelog' label."
          exit 1
        fi
```

Key decisions:
- `fetch-depth: 0` needed for changelog diff (shallow clone can't see base SHA)
- Changelog check is conditional: only on PRs, only without `skip-changelog` label
- On `push` to main, changelog check is skipped entirely (no PR context)

### 3.2 `test` Job (Matrix)

```yaml
test:
  needs: quality
  runs-on: ubuntu-latest
  strategy:
    fail-fast: false
    matrix:
      shard: [1, 2]
  steps:
    - uses: actions/checkout@v4

    - name: Configure Git for tests
      run: |
        git config --global init.defaultBranch main
        git config --global user.email "ci@test.com"
        git config --global user.name "CI Test"

    - uses: actions/setup-python@v5
      with:
        python-version: '3.12'
        cache: 'pip'

    - name: Install package with dev dependencies
      run: pip install -e ".[dev]"

    - name: Run tests (shard ${{ matrix.shard }}/2)
      run: pytest tests/ -m "not slow" -v --tb=short --splits 2 --group ${{ matrix.shard }}
```

Key decisions:
- `tests/` (not `tests/unit`) — includes both unit and integration
- `-m "not slow"` excludes slow/docker/e2e tests (same as before)
- `fail-fast: false` so both shards report results even if one fails
- `.test_durations` at repo root is auto-detected by pytest-split

### 3.3 `audit` Job

```yaml
audit:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4

    - uses: actions/setup-python@v5
      with:
        python-version: '3.12'
        cache: 'pip'

    - name: Install dependencies
      run: |
        pip install --upgrade pip
        pip install ".[dev]"
        pip install pip-audit

    - name: Audit dependencies
      run: pip-audit --desc
```

Unchanged from current `pytest.yml`. No `needs:` — runs parallel with everything.

---

## 4. Key Decisions

### 4.1 Combined test directory for sharding

**Context**: Currently unit tests (4 shards) and integration tests (1 unsharded job) run separately.

**Options**:
1. Keep separate: 2 unit shards + 1 integration shard = 3 test jobs
2. Combine all tests into 2 shards via pytest-split

**Decision**: Option 2 — combine into 2 shards.

**Rationale**: pytest-split uses duration data to balance work evenly across shards regardless of directory. Fewer jobs = fewer runner startups. Integration tests are currently unsharded (~2min bottleneck), combining them lets pytest-split distribute them.

**Consequences**: Need `.test_durations` file for optimal splitting.

### 4.2 Changelog check inlined vs. reusable action

**Context**: Changelog check is currently a standalone workflow with 7 lines of logic.

**Options**:
1. Create a reusable composite action
2. Inline the shell script in the `quality` job

**Decision**: Option 2 — inline.

**Rationale**: 7 lines of shell isn't worth the abstraction of a reusable action. Keeps everything visible in one file.

### 4.3 Trigger events include labeled/unlabeled

**Context**: `changelog-check.yml` triggers on `labeled`/`unlabeled` to re-evaluate when `skip-changelog` is added/removed.

**Decision**: Include `labeled` and `unlabeled` in `pull_request` types for `ci.yml`.

**Consequence**: Entire CI re-runs when labels change. Acceptable because quality job is fast (~20s) and test re-runs catch any regressions.

---

## 5. Implementation Plan

### 5.1 Phase Summary

| Phase | Tasks | Parallel | Est. Time |
|-------|-------|----------|-----------|
| Level 1: Foundation | 2 | Yes | 5 min |
| Level 2: Core | 1 | No | 10 min |
| Level 3: Cleanup | 1 | No | 5 min |

**Total**: 4 tasks, ~20 min single worker, ~15 min with 2 workers

### 5.2 File Ownership

| File | Task ID | Operation |
|------|---------|-----------|
| `.test_durations` | TASK-001 | create |
| `.github/workflows/ci.yml` | TASK-002 | create |
| `.github/workflows/pytest.yml` | TASK-002 | delete |
| `.github/workflows/changelog-check.yml` | TASK-003 | delete |
| `.github/workflows/command-validation.yml` | TASK-003 | delete |
| `tests/unit/test_validation.py` | TASK-004 | modify |
| `tests/unit/test_constants.py` | TASK-004 | modify |
| `tests/unit/test_ast_analyzer.py` | TASK-004 | modify |
| `tests/unit/test_state.py` | TASK-004 | modify |
| `tests/unit/test_config.py` | TASK-004 | modify |

### 5.3 Dependency Graph

```
Level 1 (parallel):
  TASK-001: Generate .test_durations
  TASK-002: Create ci.yml workflow

Level 2 (depends on TASK-002):
  TASK-003: Delete old workflows

Level 3 (no hard dependency, but logically last):
  TASK-004: Remove smoke markers from tests
```

---

## 6. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| pytest-split durations stale | Low | Low | CI can update on main; round-robin fallback works |
| Test flakes from new sharding | Low | Med | `fail-fast: false`, re-run individual shards |
| Missing `labeled`/`unlabeled` events | Low | Med | Verified in requirements, included in triggers |

---

## 7. Testing Strategy

### 7.1 Verification Commands

| Task | Verification |
|------|-------------|
| TASK-001 | `python -c "import json; json.load(open('.test_durations'))"` |
| TASK-002 | `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"` |
| TASK-003 | `test ! -f .github/workflows/changelog-check.yml && test ! -f .github/workflows/command-validation.yml` |
| TASK-004 | `! grep -r "pytest.mark.smoke" tests/unit/test_validation.py tests/unit/test_constants.py tests/unit/test_ast_analyzer.py tests/unit/test_state.py tests/unit/test_config.py` |

### 7.2 Integration Test

After all tasks: push branch, open PR, verify GitHub Actions shows exactly 4 jobs: `quality`, `test (1)`, `test (2)`, `audit`.

---

## 8. Parallel Execution Notes

### 8.1 Safe Parallelization
- TASK-001 and TASK-002 have no shared files → fully parallel
- TASK-003 depends on TASK-002 (must delete old workflows after new one exists)
- TASK-004 is independent but logically last (cleanup)

### 8.2 Recommended Workers
- Minimum: 1 worker (sequential, ~20 min)
- Optimal: 2 workers (TASK-001 + TASK-002 parallel, ~15 min)
- Maximum: 2 workers (only 2 Level 1 tasks)

### 8.3 Estimated Duration
- Single worker: ~20 min
- With 2 workers: ~15 min
- Speedup: 1.3x
