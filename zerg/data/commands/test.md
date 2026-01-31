# ZERG Test

Execute tests with coverage analysis and test generation.

## Usage

```bash
/zerg:test [--generate]      # Generate test stubs
           [--coverage]      # Report coverage
           [--watch]         # Watch mode
           [--parallel N]    # Parallel execution
           [--framework pytest|jest|cargo|go]
```

## Capabilities

### Framework Detection
Automatically detects: pytest, jest, cargo test, go test, mocha, vitest

### Test Execution
- Parallel execution for faster runs
- Watch mode for continuous testing
- Coverage tracking per file/function

### Test Generation
Generate test stubs for uncovered code.

## Examples

```bash
# Run all tests
/zerg:test

# Run with coverage
/zerg:test --coverage

# Watch mode
/zerg:test --watch

# Parallel with 8 workers
/zerg:test --parallel 8

# Generate stubs for uncovered code
/zerg:test --generate
```

## Output

```
Test Results
========================================
Total: 285
Passed: 285
Failed: 0
Skipped: 0

Pass Rate: 100.0%
Duration: 4.88s
```

## Task Tracking

On invocation, create a Claude Code Task to track this command:

Call TaskCreate:
  - subject: "[Test] Execute test suite"
  - description: "Running tests. Framework: {framework}. Coverage: {coverage}. Parallel: {parallel}."
  - activeForm: "Running tests"

Immediately call TaskUpdate:
  - taskId: (the Claude Task ID)
  - status: "in_progress"

On completion, call TaskUpdate:
  - taskId: (the Claude Task ID)
  - status: "completed"

## Exit Codes

- 0: All tests passed
- 1: Some tests failed
- 2: Configuration error

## Help

When `--help` is passed in `$ARGUMENTS`, display usage and exit:

```
/zerg:test — Execute tests with coverage analysis and test generation.

Flags:
  --generate             Generate test stubs for uncovered code
  --coverage             Report coverage
  --watch                Watch mode for continuous testing
  --parallel N           Parallel execution with N workers
  --framework <value>    Test framework: pytest|jest|cargo|go
  --help                 Show this help message
```
