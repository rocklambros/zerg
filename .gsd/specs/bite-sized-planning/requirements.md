# Requirements: Bite-Sized Task Planning

## Metadata
- **Feature**: bite-sized-planning
- **Status**: APPROVED
- **GitHub Issues**: #65, #119
- **Created**: 2026-02-04
- **Discovery**: Socratic (11 rounds)

---

## Summary

Enhance `/zerg:design` with fine-grained planning mode that generates bite-sized implementation steps within each task. Includes auto-detection of project formatters to ensure pre-commit hooks pass on first attempt.

---

## Decisions from Discovery

| Question | Decision |
|----------|----------|
| Combined or separate features? | **Combined** — #119 fits as a step in #65 |
| MVP scope | **All capabilities** — no deferrals |
| Step verification | **Exit code only** — no regex matching |
| Worker execution model | **Strict protocol** — follow steps exactly |
| Code snippet generation | **AST-aware** — extract real patterns |
| Adaptive detail triggers | **File familiarity + Success rate** |
| Detail levels | standard (no steps) / medium (steps, no snippets) / high (steps + snippets) |
| Formatter placement | **Before commit only** — single call per task |
| Formatter detection | **Auto-detected** from project config files |
| Status display | **Step + verification** — `[Step 3/5: ✅✅🔄⏳⏳]` |

---

## Functional Requirements

### FR-1: Detail Level Flag

Add `--detail` flag to `/zerg:design`:
- `--detail standard` — Current behavior (task-level only)
- `--detail medium` — Steps without code snippets
- `--detail high` — Steps with AST-generated code snippets

Default: `standard` (backward compatible)

### FR-2: Step-Level Task Structure

Extend task-graph.json schema with optional `steps` array per task:

```json
{
  "id": "TASK-003",
  "title": "Implement auth service",
  "steps": [
    {
      "step": 1,
      "action": "Write failing test",
      "file": "tests/unit/test_auth.py",
      "code_snippet": "def test_login_returns_token():...",
      "run": "pytest tests/unit/test_auth.py::test_login_returns_token -v",
      "verify": "exit_code"
    },
    {
      "step": 2,
      "action": "Verify test fails",
      "run": "pytest tests/unit/test_auth.py::test_login_returns_token -v",
      "verify": "exit_code_nonzero"
    },
    ...
  ]
}
```

### FR-3: TDD Step Ordering

In medium/high detail modes, enforce TDD sequence for each task:
1. Write failing test
2. Verify failure (exit code non-zero)
3. Write minimal implementation
4. Verify pass (exit code 0)
5. Format code
6. Commit

### FR-4: AST-Aware Code Snippet Generation

For `--detail high`, analyze codebase to generate realistic snippets:
- Extract import patterns from existing files
- Use actual base classes, utility functions
- Match project naming conventions
- Snippets are hints, not rigid prescriptions

### FR-5: Formatter Auto-Detection

Detect project formatter from config files:
- `pyproject.toml` → ruff, black, isort
- `.prettierrc` / `package.json` → prettier
- `rustfmt.toml` → rustfmt
- `.clang-format` → clang-format
- `gofmt` → go fmt

Generate format step command based on detected tooling.

### FR-6: Format Step Integration

Insert format step before commit in TDD sequence:
- Run detected formatter on modified files
- Run linter auto-fix if available (e.g., `ruff check --fix`)
- Single invocation per task commit

### FR-7: Step-Level Progress Tracking

Extend `/zerg:status` to show step progress:

```
TASK-003: Implement auth service [Step 3/5: ✅✅🔄⏳⏳]
TASK-004: Add user validation [Step 1/5: 🔄⏳⏳⏳⏳]
```

Symbols: ✅ completed, 🔄 in progress, ⏳ pending, ❌ failed

### FR-8: Adaptive Detail

Automatically reduce detail level when:
- **File familiarity**: Worker has modified this file/module before in the same rush
- **Success rate**: Previous tasks in same area succeeded without step guidance

Track metrics in `.zerg/state/adaptive-detail.json`.

### FR-9: Worker Protocol Update

Update worker.md to execute steps strictly:
- Load steps from task
- Execute each step in order
- Verify exit code after each `run` command
- Fail task if any step verification fails
- No deviation from step sequence

### FR-10: Configuration

Add to `.zerg/config.yaml`:

```yaml
planning:
  default_detail: standard  # standard | medium | high
  include_code_snippets: true
  include_test_first: true
  step_verification: true
  adaptive_detail: true
  adaptive_familiarity_threshold: 2  # modifications before reducing detail
  adaptive_success_threshold: 0.8    # success rate before reducing detail
```

---

## Non-Functional Requirements

### NFR-1: Backward Compatibility

- `--detail standard` (default) produces identical output to current behavior
- Existing task-graph.json files without `steps` work unchanged
- Workers handle tasks with or without steps

### NFR-2: Performance

- AST analysis for snippet generation < 5 seconds for 1000-file codebase
- Use existing `ASTCache` class for parsed AST reuse

### NFR-3: Schema Validation

- Extend `zerg/schemas/task_graph.json` with step definitions
- Validate step structure in `zerg design --validate-only`

---

## Acceptance Criteria

- [ ] `--detail` flag on `/zerg:design` (standard/medium/high)
- [ ] Step-level task definitions in task-graph.json
- [ ] TDD step ordering enforced (test → verify-fail → implement → verify-pass → format → commit)
- [ ] AST-aware code snippet generation for `--detail high`
- [ ] Formatter auto-detection from project config files
- [ ] Format step inserted before commit
- [ ] Step-level progress in `/zerg:status` with visual indicators
- [ ] Adaptive detail based on file familiarity and success rate
- [ ] Worker protocol updated for strict step execution
- [ ] Config section for planning options
- [ ] Unit tests for step generation, formatter detection, adaptive logic
- [ ] Integration tests for end-to-end step execution
- [ ] Schema updated and validated

---

## Out of Scope

- LLM-generated code snippets (use AST patterns only)
- Regex matching on command output (exit code only)
- Worker autonomy to deviate from steps (strict protocol)
- Pattern-based detail reduction (only file familiarity + success rate)
