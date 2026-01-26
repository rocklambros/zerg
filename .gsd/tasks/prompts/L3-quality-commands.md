# L3-TASK-001: Two-Stage Quality Gates

## Objective

Implement spec compliance (Stage 1) and code quality (Stage 2) gates between levels.

## Context

**Depends on**: L0-TASK-001, L0-TASK-003

Quality gates run after each level completes. Stage 1 catches requirements misses early. Stage 2 ensures code quality.

## Files to Create

```
.zerg/
└── gates/
    ├── __init__.py           # Gate runner
    ├── spec_compliance.py    # Stage 1 checks
    └── code_quality.py       # Stage 2 checks
```

## Stage 1: Spec Compliance

```python
class SpecComplianceGate:
    """Stage 1: Verify implementation matches spec."""
    
    def run(self, level: int, tasks: list[Task]) -> GateResult:
        checks = [
            self._check_requirements_met,
            self._check_acceptance_criteria,
            self._check_file_ownership,
            self._check_dependencies_respected
        ]
        
        failures = []
        for check in checks:
            result = check(level, tasks)
            if not result.passed:
                failures.extend(result.issues)
        
        return GateResult(
            stage=1,
            passed=len(failures) == 0,
            failures=failures
        )
```

## Stage 2: Code Quality

```python
class CodeQualityGate:
    """Stage 2: Verify code quality standards."""
    
    def run(self, level: int, changed_files: list[str]) -> GateResult:
        checks = [
            self._run_linter,
            self._check_coverage,
            self._run_security_scan,
            self._check_documentation
        ]
        # Only run if Stage 1 passed
```

## Verification

```bash
cd .zerg && python -c "
from gates import run_spec_compliance, run_code_quality

# Test gates exist and are callable
print('OK: Quality gates ready')
"
```

## Definition of Done

1. Stage 1 checks implemented
2. Stage 2 checks implemented
3. Configurable thresholds
4. Results in execution state

---

# L3-TASK-002: /zerg:analyze Command

## Objective

Implement static analysis, complexity metrics, and quality assessment.

## Context

**Depends on**: L3-TASK-001

Analyze provides deep code quality insights beyond basic linting.

## Files to Create

```
.claude/commands/
└── zerg:analyze.md

.zerg/
└── analyze.py
```

## Capabilities

1. **Linting**: Language-specific (ruff, eslint, clippy)
2. **Complexity**: Cyclomatic, cognitive
3. **Coverage**: Line, branch, function
4. **Security**: SAST via semgrep
5. **Output**: text, JSON, SARIF

## Usage

```bash
/zerg:analyze [--check lint|complexity|coverage|security|all]
              [--format text|json|sarif]
              [--threshold complexity=10]
```

## Verification

```bash
cd .zerg && python -c "
from analyze import AnalyzeCommand
ac = AnalyzeCommand()
print(ac.supported_checks())
"
```

---

# L3-TASK-003: /zerg:test Command

## Objective

Implement test generation, execution, and coverage analysis.

## Files to Create

```
.claude/commands/
└── zerg:test.md

.zerg/
└── test_runner.py
```

## Capabilities

1. **Detect Framework**: pytest, jest, cargo test, go test
2. **Generate Tests**: Stub generation for uncovered code
3. **Coverage Tracking**: Per file/function
4. **Watch Mode**: Re-run on changes
5. **Parallel Execution**: Speed up large suites

## Usage

```bash
/zerg:test [--generate]      # Generate test stubs
           [--coverage]      # Report coverage
           [--watch]         # Watch mode
           [--parallel N]    # Parallel execution
```

---

# L3-TASK-004: /zerg:security Command

## Objective

Implement security review, vulnerability scanning, and hardening.

## Files to Create

```
.claude/commands/
└── zerg:security.md

.zerg/
└── security.py
```

## Capabilities

1. **OWASP Top 10**: Scan for common vulnerabilities
2. **Dependency CVE**: Check dependencies for known CVEs
3. **Secret Detection**: Find hardcoded secrets (gitleaks)
4. **Rule Presets**: owasp, pci, hipaa
5. **Auto-fix**: Where possible

## Usage

```bash
/zerg:security [--preset owasp|pci|hipaa]
               [--autofix]
               [--format text|sarif]
```

---

# L3-TASK-005: /zerg:refactor Command

## Objective

Implement automated code improvement and cleanup.

## Files to Create

```
.claude/commands/
└── zerg:refactor.md

.zerg/
└── refactor.py
```

## Transforms

1. **dead-code**: Remove unused code
2. **simplify**: Reduce complexity
3. **types**: Strengthen type annotations
4. **patterns**: Apply common patterns
5. **naming**: Improve variable/function names

## Usage

```bash
/zerg:refactor [--transforms dead-code,simplify]
               [--dry-run]
               [--interactive]
```

---

# L3-TASK-006: /zerg:review Command

## Objective

Implement two-stage code review workflow.

## Files to Create

```
.claude/commands/
└── zerg:review.md

.zerg/
└── review.py
```

## Modes

1. **prepare**: Prepare PR for review
2. **self**: Self-review checklist
3. **receive**: Process review feedback
4. **full**: Complete two-stage review

## Workflow

```
/zerg:review --mode prepare  # Prepare changes for review
/zerg:review --mode full     # Run both spec and quality checks
```

---

# L3-TASK-007: /zerg:troubleshoot Command

## Objective

Implement systematic debugging with root cause analysis.

## Files to Create

```
.claude/commands/
└── zerg:troubleshoot.md

.zerg/
└── troubleshoot.py
```

## Four-Phase Process

1. **Symptom**: What's happening?
2. **Hypothesis**: Why might it happen?
3. **Test**: How do we verify?
4. **Root Cause**: What's the actual cause?

## Capabilities

- Error message parsing
- Stack trace analysis
- Diagnostic report generation
- Fix recommendations

## Usage

```bash
/zerg:troubleshoot [--error "error message"]
                   [--stacktrace path/to/trace]
                   [--verbose]
```
