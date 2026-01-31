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

## Task Tracking

On invocation, create a Claude Code Task to track this command:

Call TaskCreate:
  - subject: "[Review] Code review {mode}"
  - description: "Running code review in {mode} mode for current feature."
  - activeForm: "Running code review"

Immediately call TaskUpdate:
  - taskId: (the Claude Task ID)
  - status: "in_progress"

On completion, call TaskUpdate:
  - taskId: (the Claude Task ID)
  - status: "completed"

## Help

When `--help` is passed in `$ARGUMENTS`, display usage and exit:

```
/zerg:review — Two-stage code review workflow.

Flags:
  --mode MODE           Review mode: prepare|self|receive|full (default: full)
  --help                Show this help message
```

## Exit Codes

- 0: Review passed
- 1: Issues found
- 2: Review error
