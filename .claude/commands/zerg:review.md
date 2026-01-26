# ZERG Review

Two-stage code review workflow.

## Usage

```bash
/zerg:review [--mode prepare|self|receive|full]
```

## Modes

### prepare
Prepare PR for review:
- Generate change summary
- Check spec compliance
- Create review checklist

### self
Self-review checklist:
- Code compiles without errors
- All tests pass locally
- No hardcoded values or secrets
- Error handling is appropriate
- Edge cases are handled
- Code is readable and well-named

### receive
Process review feedback:
- Parse review comments
- Track addressed items
- Generate response

### full (default)
Complete two-stage review:
1. Spec compliance check
2. Code quality review

## Examples

```bash
# Full two-stage review
/zerg:review

# Prepare for PR
/zerg:review --mode prepare

# Self-review checklist
/zerg:review --mode self
```

## Output

```
Code Review Results
========================================
Status: PASSED
Files Reviewed: 5

Stage 1 (Spec): ✓
Stage 2 (Quality): ✓
```

## Exit Codes

- 0: Review passed
- 1: Issues found
- 2: Review error
