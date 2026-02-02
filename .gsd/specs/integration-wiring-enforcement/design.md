# Technical Design: integration-wiring-enforcement

## Metadata
- **Feature**: integration-wiring-enforcement
- **Status**: DRAFT
- **Created**: 2026-02-02
- **Issue**: #78 (primary), #79, #80, #81 (related)

---

## 1. Overview

### 1.1 Summary

Add wiring enforcement to ZERG's feature delivery pipeline so that every module delivered has at least one production caller and an integration test proving end-to-end behavior. Changes touch 4 command files, 1 validation module, 1 CI workflow, and CLAUDE.md.

### 1.2 Goals
- Every task-graph task that creates a module specifies its `consumers`
- Workers run integration verification alongside isolation verification
- `validate_commands.py` detects orphaned modules (production imports = 0)
- CI runs pytest on every PR
- CLAUDE.md codifies the wiring rule in anti-drift section

### 1.3 Non-Goals
- Runtime wiring of cross-cutting capabilities (#78 tracks that separately)
- Refactoring existing orphaned modules (separate cleanup work)
- Full TDD enforcement in workers (covered by `--tdd` flag wiring in #78)

---

## 2. Architecture

### 2.1 High-Level Design

```
DESIGN PHASE                    EXECUTION PHASE                 VALIDATION PHASE
┌──────────────┐               ┌──────────────┐               ┌──────────────────┐
│  design.md   │               │  worker.md   │               │ validate_cmds.py │
│  + consumers │──task-graph──▶│  + integ.    │──commit──────▶│ + module_wiring  │
│  + integ_test│   .json       │    verify    │               │   check          │
└──────────────┘               └──────────────┘               └──────────────────┘
                                      │                               │
                                      ▼                               ▼
                               ┌──────────────┐               ┌──────────────────┐
                               │  merge.md    │               │  CI: pytest.yml  │
                               │  + wiring    │               │  runs tests +    │
                               │    gate      │               │  import check    │
                               └──────────────┘               └──────────────────┘
```

### 2.2 Component Breakdown

| Component | Responsibility | Files |
|-----------|---------------|-------|
| Task graph schema | Add `consumers` + `integration_test` fields | design.md |
| Integration verify | Run integration commands before task completion | worker.core.md |
| Wiring quality gate | Check all new modules are imported in production | merge.core.md |
| Module wiring validator | Detect orphaned modules via AST import analysis | validate_commands.py |
| CI pytest workflow | Run full test suite on PRs | .github/workflows/pytest.yml |
| Anti-drift rule | Document wiring requirement | CLAUDE.md |

---

## 3. Detailed Design

### 3.1 Task Graph Schema Changes

Add two optional fields per task in task-graph.json:

```json
{
  "id": "TASK-003",
  "title": "Implement auth service",
  "files": {
    "create": ["zerg/auth_service.py"],
    "modify": [],
    "read": ["zerg/types.py"]
  },
  "verification": {
    "command": "pytest tests/unit/test_auth_service.py -v",
    "timeout_seconds": 120
  },
  "consumers": ["TASK-005"],
  "integration_test": "tests/integration/test_auth_wiring.py"
}
```

**Rules:**
- `consumers`: List of task IDs that will import/call this task's output. If empty, the task is a leaf (e.g., CLI entry point, test file). Leaf tasks don't need consumers.
- `integration_test`: File path for the integration test that proves this module works with its consumers. Required if `consumers` is non-empty.

### 3.2 Design.md Command Changes

Add to Phase 2 (Implementation Plan) after File Ownership Matrix:

```markdown
### Consumer Matrix

Every task that creates a module must declare who calls it.

| Task | Creates | Consumed By | Integration Test |
|------|---------|-------------|-----------------|
| TASK-001 | zerg/types.py | TASK-003, TASK-004 | tests/integration/test_types_wiring.py |
| TASK-003 | zerg/service.py | TASK-005 | tests/integration/test_service_wiring.py |
| TASK-005 | zerg/routes.py | (leaf: CLI entry) | — |
```

Add validation rule to Phase 5 (Validate Task Graph):

```bash
# Verify every task with consumers has an integration_test
# Verify every integration_test file is owned by a task
# Verify consumer references point to real task IDs
```

### 3.3 Worker.core.md Changes

Add Step 4.3.5 between "Implement" and "Verify Task":

```markdown
#### 4.3.5 Integration Verification (if applicable)

If the task has an `integration_test` field in task-graph.json:

1. Create the integration test file specified
2. The test must:
   - Import the module created by this task
   - Import or mock the consumer's expected interface
   - Prove the module is callable in its intended context
3. Run the integration test:
   ```bash
   pytest "$INTEGRATION_TEST" -v
   ```
4. Both isolation AND integration verification must pass before commit
```

Modify Step 4.4 to run both:

```bash
# Isolation verification (existing)
eval "$VERIFICATION"

# Integration verification (new, if applicable)
if [ -n "$INTEGRATION_TEST" ]; then
  pytest "$INTEGRATION_TEST" -v
fi

# Both must pass
```

### 3.4 Merge.core.md Changes

Add Step 5.5 (after quality gates, before Task update):

```markdown
### Step 5.5: Wiring Verification

After quality gates pass, verify all new modules are wired:

```bash
# Find all .py files created in this level's commits
NEW_FILES=$(git diff --name-only --diff-filter=A HEAD~$TASK_COUNT HEAD -- '*.py')

for FILE in $NEW_FILES; do
  MODULE=$(echo $FILE | sed 's|/|.|g' | sed 's|.py$||')
  # Check if any other production file imports this module
  IMPORTERS=$(grep -rl "from $MODULE import\|import $MODULE" zerg/ --include="*.py" | grep -v "tests/" | grep -v "$FILE")
  if [ -z "$IMPORTERS" ] && ! echo "$FILE" | grep -q "tests/"; then
    echo "WARNING: $FILE has no production imports (orphaned module)"
    WIRING_WARNINGS+=("$FILE")
  fi
done

if [ ${#WIRING_WARNINGS[@]} -gt 0 ]; then
  echo "Wiring warnings: ${#WIRING_WARNINGS[@]} modules have no production callers"
  # Warning, not failure — some modules are legitimately standalone (CLI entry points)
fi
```

### 3.5 validate_commands.py Changes

Add new validation function:

```python
def validate_module_wiring(
    package_dir: Path | None = None,
    tests_dir: Path | None = None,
) -> tuple[bool, list[str]]:
    """Verify all modules in zerg/ have at least one production import.

    Scans for .py files with zero production imports (only test imports
    don't count). Allowlisted patterns: __init__.py, __main__.py,
    conftest.py, and files with if __name__ == "__main__".

    Args:
        package_dir: Path to zerg/ package. Defaults to zerg/.
        tests_dir: Path to tests/ directory. Defaults to tests/.

    Returns:
        Tuple of (all_valid, list of warning messages).
    """
```

**Implementation approach:**
1. Walk all `.py` files in `zerg/`
2. For each file, search all other `.py` files in `zerg/` for import statements referencing it
3. Exclude `tests/` imports — only count production imports
4. Allowlist: `__init__.py`, `__main__.py`, `conftest.py`, CLI entry points, files with `if __name__`
5. Report modules with zero production imports as warnings

**Add to `validate_all()`** as a new check.

### 3.6 CI Workflow

Create `.github/workflows/pytest.yml`:

```yaml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install -e ".[dev]"
      - run: pytest tests/unit tests/integration -v --tb=short
      - run: python -m zerg.validate_commands
```

### 3.7 CLAUDE.md Anti-Drift Addition

Add to the "Anti-Drift Rules" section:

```markdown
6. **Every new module must have a production caller.** If a PR creates a new `.py`
   file in `zerg/`, at least one other production file must import it. Test-only
   imports don't count. If the module is a standalone entry point
   (CLI, `__main__`), it's exempt. Run `python -m zerg.validate_commands` to check.

7. **Every new module must have an integration test.** Unit tests prove the module
   works in isolation. Integration tests prove it works with its callers. A module
   with unit tests but no integration test is incomplete.
```

Add to drift detection checklist:

```bash
# 6. No orphaned modules (production imports only)
python -m zerg.validate_commands  # includes module wiring check

# 7. Integration test coverage
for f in $(git diff --name-only --diff-filter=A HEAD~1 -- 'zerg/*.py'); do
  stem=$(basename "$f" .py)
  if ! find tests/integration -name "*${stem}*" | grep -q .; then
    echo "DRIFT: $f has no integration test"
  fi
done
```

---

## 4. Key Decisions

### 4.1 Warnings vs Failures for Wiring Check

**Context**: Module wiring check could be strict (fail) or advisory (warn).

**Options**:
1. **Strict failure**: Block merge/commit if orphaned module detected
2. **Warning only**: Report but don't block
3. **Configurable**: Default warn, `--strict-wiring` to fail

**Decision**: Option 3 — Configurable

**Rationale**: Some modules are legitimately standalone (CLI entry points, `__main__` files). Strict mode would require an allowlist. Starting with warnings prevents false positives while still surfacing the problem. Teams can enable strict mode when ready.

### 4.2 Consumer Field: Required vs Optional

**Context**: Should `consumers` be required for every task?

**Decision**: Optional with validation rule — if a task creates files and has no `consumers` and no `integration_test`, emit a design-time warning. Leaf tasks (tests, CLI entry points, docs) are exempt.

### 4.3 Integration Test Ownership

**Context**: Who creates the integration test — the producer task or the consumer task?

**Decision**: The **producer** task creates the integration test skeleton. The **consumer** task extends it if needed. This ensures the integration test exists before the consumer starts work.

---

## 5. Implementation Plan

### 5.1 Phase Summary

| Phase | Tasks | Parallel | Description |
|-------|-------|----------|-------------|
| Foundation | 2 | Yes | Schema + CI workflow |
| Core | 2 | Yes | Command file updates |
| Integration | 2 | Yes | Validation + CLAUDE.md |
| Testing | 1 | No | Integration tests for the feature itself |

### 5.2 File Ownership

| File | Task ID | Operation |
|------|---------|-----------|
| .github/workflows/pytest.yml | TASK-001 | create |
| zerg/validate_commands.py | TASK-002 | modify |
| zerg/data/commands/design.md | TASK-003 | modify |
| zerg/data/commands/design.core.md | TASK-003 | modify |
| zerg/data/commands/worker.core.md | TASK-004 | modify |
| zerg/data/commands/merge.core.md | TASK-005 | modify |
| CLAUDE.md | TASK-006 | modify |
| tests/unit/test_validate_commands.py | TASK-007 | modify |
| tests/integration/test_wiring_enforcement.py | TASK-007 | create |

### 5.3 Dependency Graph

```
Level 1 (parallel):
  TASK-001: CI pytest workflow
  TASK-002: Module wiring validator

Level 2 (parallel, depends on L1):
  TASK-003: Design command — consumer matrix + schema
  TASK-004: Worker command — integration verification step

Level 3 (parallel, depends on L2):
  TASK-005: Merge command — wiring quality gate
  TASK-006: CLAUDE.md — anti-drift rules

Level 4 (depends on all):
  TASK-007: Tests — unit + integration tests for all changes
```

---

## 6. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| False positives in wiring check | Medium | Low | Allowlist + configurable strict mode |
| Existing orphaned modules flagged | High | Low | Warning-only default, not failure |
| Worker overhead from integration tests | Low | Medium | Integration tests are fast (import + basic call) |
| Design complexity increase | Low | Low | Consumer matrix is one extra column in existing table |

---

## 7. Testing Strategy

### 7.1 Unit Tests
- `test_validate_commands.py`: Add tests for `validate_module_wiring()`
  - Module with production imports → passes
  - Module with only test imports → warns
  - `__init__.py` / `__main__.py` → exempt
  - CLI entry point with `if __name__` → exempt

### 7.2 Integration Tests
- `test_wiring_enforcement.py`: End-to-end test proving:
  - A task-graph with `consumers` field is parsed correctly
  - `validate_module_wiring()` detects real orphaned modules in zerg/
  - CI workflow YAML is valid

### 7.3 Verification Commands
- `python -m zerg.validate_commands` passes
- `pytest tests/unit/test_validate_commands.py -v` passes
- `pytest tests/integration/test_wiring_enforcement.py -v` passes

---

## 8. Parallel Execution Notes

### 8.1 Safe Parallelization
- Level 1: CI workflow and validator are independent files
- Level 2: design.md and worker.core.md don't overlap
- Level 3: merge.core.md and CLAUDE.md don't overlap
- Level 4: Tests depend on all production code

### 8.2 Recommended Workers
- Minimum: 1 (sequential)
- Optimal: 2 (widest level is 2)
- Maximum: 2

### 8.3 Estimated Duration
- Single worker: 7 tasks sequential
- With 2 workers: 4 levels
