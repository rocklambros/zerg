# /zerg:review

Two-stage code review workflow with spec compliance and quality checks.

## Synopsis

```
/zerg:review [--mode prepare|self|receive|full]
```

## Description

The `review` command provides a structured code review process. It operates in four modes that cover the full lifecycle of a review, from self-review through PR preparation, receiving feedback, and a comprehensive two-stage review that checks both specification compliance and code quality.

### Review Modes

**prepare** -- Prepares a pull request for review by generating a change summary, verifying spec compliance, and creating a review checklist.

**self** -- Runs through a self-review checklist to catch common issues before requesting review from others. The checklist covers:

- Code compiles without errors
- All tests pass locally
- No hardcoded values or secrets
- Error handling is appropriate
- Edge cases are handled
- Code is readable and well-named

**receive** -- Processes incoming review feedback by parsing review comments, tracking which items have been addressed, and generating a response summary.

**full** (default) -- Executes a complete two-stage review:

1. **Stage 1 -- Spec compliance**: Verifies that the implementation matches the feature specification.
2. **Stage 2 -- Code quality**: Reviews code quality, patterns, naming, and maintainability.

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--mode` | `full` | Review mode to execute. Accepts `prepare`, `self`, `receive`, or `full`. |

## Examples

Run the full two-stage review:

```
/zerg:review
```

Prepare a PR for review:

```
/zerg:review --mode prepare
```

Run the self-review checklist:

```
/zerg:review --mode self
```

## Sample Output

```
Code Review Results
========================================
Status: PASSED
Files Reviewed: 5

Stage 1 (Spec): PASS
Stage 2 (Quality): PASS
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Review passed |
| 1 | Issues found |
| 2 | Review error |

## Task Tracking

This command creates a Claude Code Task with the subject prefix `[Review]` on invocation, updates it to `in_progress` immediately, and marks it `completed` on success.

## See Also

- [[zerg-git]] -- Git operations including the finish workflow for merging reviewed code
- [[zerg-analyze]] -- Static analysis to supplement manual review
- [[zerg-security]] -- Security-focused scanning
