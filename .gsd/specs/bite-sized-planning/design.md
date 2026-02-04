# Technical Design: Bite-Sized Task Planning

## Metadata
- **Feature**: bite-sized-planning
- **Status**: DRAFT
- **Created**: 2026-02-04
- **GitHub Issues**: #65, #119

---

## 1. Overview

### 1.1 Summary

Add step-level granularity to ZERG task planning. Each task can contain ordered steps following TDD methodology. Workers execute steps strictly in sequence with exit-code verification. Includes auto-detection of project formatters to ensure clean commits.

### 1.2 Goals

- Enable bite-sized, mechanically executable task steps
- Enforce TDD workflow (test-first, verify failure, implement, verify pass)
- Auto-detect and run formatters before commits
- Track step-level progress in status UI
- Adapt detail level based on worker familiarity

### 1.3 Non-Goals

- LLM-generated code snippets (AST patterns only)
- Regex matching on command output
- Worker deviation from step sequence

---

## 2. Architecture

### 2.1 High-Level Design

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  /zerg:design   │────▶│  StepGenerator   │────▶│ task-graph.json │
│  --detail high  │     │  + ASTAnalyzer   │     │ (with steps[])  │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                │
                                ▼
                        ┌──────────────────┐
                        │ FormatterDetector│
                        │ (pyproject, etc) │
                        └──────────────────┘

┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│     Worker      │────▶│  StepExecutor    │────▶│   Heartbeat     │
│   (strict)      │     │  (verify exit)   │     │ (step progress) │
└─────────────────┘     └──────────────────┘     └─────────────────┘

┌─────────────────┐     ┌──────────────────┐
│  /zerg:status   │────▶│ StepProgressUI   │
│                 │     │ [✅✅🔄⏳⏳]     │
└─────────────────┘     └──────────────────┘
```

### 2.2 Component Breakdown

| Component | Responsibility | Files |
|-----------|---------------|-------|
| StepGenerator | Generate TDD steps for tasks | `zerg/step_generator.py` |
| ASTAnalyzer | Extract codebase patterns for snippets | `zerg/ast_analyzer.py` |
| FormatterDetector | Detect project formatters from config | `zerg/formatter_detector.py` |
| StepExecutor | Execute steps with exit-code verification | `zerg/step_executor.py` |
| AdaptiveDetail | Track familiarity/success for detail adjustment | `zerg/adaptive_detail.py` |
| StepProgressUI | Render step progress in status | `zerg/commands/status.py` |
| PlanningConfig | Config model for planning options | `zerg/config.py` |

### 2.3 Data Flow

1. User runs `/zerg:design --detail high`
2. `StepGenerator` loads task-graph template
3. For each task:
   - `ASTAnalyzer` extracts patterns from related files
   - `StepGenerator` creates TDD step sequence
   - `FormatterDetector` adds format step with detected tool
4. Output: task-graph.json with `steps[]` per task
5. Worker loads task, `StepExecutor` runs each step
6. Heartbeat updates with current step number
7. `/zerg:status` renders step progress visually

---

## 3. Detailed Design

### 3.1 Step Schema (JSON Schema Extension)

```json
{
  "step": {
    "type": "object",
    "required": ["step", "action", "run"],
    "properties": {
      "step": {
        "type": "integer",
        "minimum": 1,
        "description": "Step number in sequence"
      },
      "action": {
        "type": "string",
        "enum": ["write_test", "verify_fail", "implement", "verify_pass", "format", "commit"],
        "description": "Step action type"
      },
      "file": {
        "type": "string",
        "description": "Primary file for this step"
      },
      "code_snippet": {
        "type": "string",
        "description": "AST-generated code hint (high detail only)"
      },
      "run": {
        "type": "string",
        "description": "Command to execute"
      },
      "verify": {
        "type": "string",
        "enum": ["exit_code", "exit_code_nonzero", "none"],
        "default": "exit_code",
        "description": "Verification method"
      }
    }
  }
}
```

### 3.2 TDD Step Template

For each task, generate 6 steps:

| Step | Action | Verify | Description |
|------|--------|--------|-------------|
| 1 | write_test | none | Create test file with failing test |
| 2 | verify_fail | exit_code_nonzero | Run test, expect failure |
| 3 | implement | none | Write implementation code |
| 4 | verify_pass | exit_code | Run test, expect success |
| 5 | format | exit_code | Run detected formatter |
| 6 | commit | exit_code | Stage and commit |

### 3.3 FormatterDetector API

```python
@dataclass
class FormatterConfig:
    name: str              # e.g., "ruff"
    format_cmd: str        # e.g., "ruff format {files}"
    fix_cmd: str | None    # e.g., "ruff check --fix {files}"
    file_patterns: list[str]  # e.g., ["*.py"]

class FormatterDetector:
    def detect(self, repo_path: Path) -> list[FormatterConfig]:
        """Detect formatters from project config files."""

    def detect_for_files(self, files: list[str]) -> FormatterConfig | None:
        """Get formatter for specific file extensions."""
```

Detection sources:
- `pyproject.toml`: `[tool.ruff]`, `[tool.black]`, `[tool.isort]`
- `package.json`: `prettier`, `eslint`
- `.prettierrc`, `.prettierrc.json`, `.prettierrc.yaml`
- `rustfmt.toml`, `.rustfmt.toml`
- `.clang-format`
- Presence of `go.mod` → `gofmt`

### 3.4 ASTAnalyzer API

```python
class ASTAnalyzer:
    def __init__(self, cache: ASTCache):
        self.cache = cache

    def extract_patterns(self, file_path: Path) -> CodePatterns:
        """Extract import patterns, base classes, utilities from a file."""

    def generate_test_snippet(self,
                              target_file: Path,
                              function_name: str) -> str:
        """Generate test snippet matching project conventions."""

    def generate_impl_snippet(self,
                              target_file: Path,
                              based_on: list[Path]) -> str:
        """Generate implementation snippet using patterns from similar files."""
```

### 3.5 AdaptiveDetail Logic

```python
@dataclass
class DetailMetrics:
    file_modifications: dict[str, int]  # file -> modification count
    task_results: dict[str, bool]       # task_id -> success

class AdaptiveDetail:
    def should_reduce_detail(self,
                             task: Task,
                             metrics: DetailMetrics,
                             config: PlanningConfig) -> bool:
        # Check file familiarity
        for file in task.files.modify + task.files.create:
            if metrics.file_modifications.get(file, 0) >= config.adaptive_familiarity_threshold:
                return True

        # Check success rate in same directory
        related_tasks = [t for t in metrics.task_results
                        if self._same_area(t, task)]
        if related_tasks:
            success_rate = sum(related_tasks.values()) / len(related_tasks)
            if success_rate >= config.adaptive_success_threshold:
                return True

        return False
```

### 3.6 StepExecutor Protocol

```python
class StepExecutor:
    def execute_task(self, task: Task, worker_id: int) -> TaskResult:
        if not task.steps:
            return self._execute_classic(task)

        for step in task.steps:
            self._update_heartbeat(worker_id, task.id, step.step, len(task.steps))

            if step.action == "write_test":
                self._write_file(step.file, step.code_snippet)
            elif step.action == "implement":
                self._write_file(step.file, step.code_snippet)

            if step.run:
                result = subprocess.run(step.run, shell=True)

                if step.verify == "exit_code" and result.returncode != 0:
                    return TaskResult(success=False, failed_step=step.step)
                elif step.verify == "exit_code_nonzero" and result.returncode == 0:
                    return TaskResult(success=False, failed_step=step.step,
                                     error="Expected failure but got success")

        return TaskResult(success=True)
```

---

## 4. Key Decisions

### 4.1 Decision: Exit Code Only for Verification

**Context**: Original proposal used regex matching on command output.

**Options Considered**:
1. Regex on stdout — flexible but brittle across tools
2. Exit code only — universal and reliable
3. Hybrid — exit code default, optional regex

**Decision**: Exit code only (Option 2)

**Rationale**: Test frameworks, linters, and build tools universally use exit codes. Regex patterns would need maintenance per tool version.

### 4.2 Decision: Strict Step Protocol

**Context**: Workers could follow steps strictly or use them as guidance.

**Options Considered**:
1. Strict — follow exactly, no deviation
2. Guidance — suggestions only, worker autonomy
3. Verified checkpoints — can deviate but must pass each step

**Decision**: Strict protocol (Option 1)

**Rationale**: Bite-sized steps are designed to be mechanical. Deviation introduces unpredictability. If steps are wrong, fix the generator.

### 4.3 Decision: AST-Based Snippet Generation

**Context**: Code snippets could be templates, AST-generated, or LLM-generated.

**Options Considered**:
1. Template — placeholders like `{class_name}`
2. AST-aware — extract real patterns from codebase
3. LLM — Claude generates snippets during design

**Decision**: AST-aware (Option 2)

**Rationale**: Templates are generic. LLM adds latency and cost to design phase. AST extraction produces realistic snippets without external calls.

---

## 5. Implementation Plan

### 5.1 Phase Summary

| Phase | Tasks | Parallel | Est. Time |
|-------|-------|----------|-----------|
| Foundation | 3 | Yes | 25m |
| Core | 4 | Partial | 60m |
| Integration | 3 | Yes | 40m |
| Testing | 2 | Yes | 30m |
| Quality | 1 | No | 15m |

### 5.2 File Ownership

| File | Task ID | Operation |
|------|---------|-----------|
| `zerg/step_generator.py` | BITE-L2-001 | create |
| `zerg/ast_analyzer.py` | BITE-L2-002 | create |
| `zerg/formatter_detector.py` | BITE-L1-001 | create |
| `zerg/adaptive_detail.py` | BITE-L2-003 | create |
| `zerg/step_executor.py` | BITE-L2-004 | create |
| `zerg/config.py` | BITE-L1-002 | modify |
| `zerg/schemas/task_graph.json` | BITE-L1-003 | modify |
| `zerg/commands/design.py` | BITE-L3-001 | modify |
| `zerg/commands/status.py` | BITE-L3-002 | modify |
| `zerg/data/commands/worker.core.md` | BITE-L3-003 | modify |
| `tests/unit/test_step_generator.py` | BITE-L4-001 | create |
| `tests/unit/test_formatter_detector.py` | BITE-L4-001 | create |
| `tests/integration/test_step_execution.py` | BITE-L4-002 | create |

### 5.3 Dependency Graph

```
BITE-L1-001 (FormatterDetector) ─┬─▶ BITE-L2-001 (StepGenerator) ─┬─▶ BITE-L3-001 (design.py)
BITE-L1-002 (PlanningConfig)    ─┤                                │
BITE-L1-003 (Schema)            ─┘                                ├─▶ BITE-L3-002 (status.py)
                                                                  │
BITE-L2-002 (ASTAnalyzer)      ──▶ BITE-L2-001                   ├─▶ BITE-L3-003 (worker.md)
                                                                  │
BITE-L2-003 (AdaptiveDetail)   ──▶ BITE-L2-001                   │
                                                                  │
BITE-L2-004 (StepExecutor)     ─────────────────────────────────▶┘
                                                                  │
                                                                  ▼
                                                            BITE-L4-001 (Unit Tests)
                                                                  │
                                                                  ▼
                                                            BITE-L4-002 (Integration)
                                                                  │
                                                                  ▼
                                                            BITE-L5-001 (Quality)
```

---

## 6. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| AST parsing fails on complex files | Low | Medium | Fallback to no-snippet mode |
| Formatter detection misses edge cases | Medium | Low | Manual override in config |
| Step generation too slow | Low | Medium | Use ASTCache, limit file scan |
| Workers confused by steps | Low | High | Clear protocol docs, strict mode |

---

## 7. Testing Strategy

### 7.1 Unit Tests

- `StepGenerator`: TDD sequence generation, step ordering
- `FormatterDetector`: Detection from each config file type
- `ASTAnalyzer`: Pattern extraction, snippet generation
- `AdaptiveDetail`: Threshold logic, metric tracking

### 7.2 Integration Tests

- End-to-end: design → rush → worker step execution
- Formatter integration: pre-commit hooks pass
- Status UI: step progress rendering

---

## 8. Parallel Execution Notes

### 8.1 Recommended Workers

- Minimum: 2 workers
- Optimal: 3 workers
- Maximum: 4 workers (L1 has 3 parallel tasks)

### 8.2 Estimated Duration

- Single worker: ~170m
- With 3 workers: ~85m
- Speedup: 2x

---

## 9. Approval

| Role | Status |
|------|--------|
| Architecture | PENDING |
| Engineering | PENDING |
