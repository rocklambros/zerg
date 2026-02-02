# /zerg:test

Execute tests with coverage analysis, parallel execution, and test stub generation.

## Synopsis

```
/zerg:test [--generate]
           [--coverage]
           [--watch]
           [--parallel N]
           [--framework pytest|jest|cargo|go]
```

## Description

The `test` command runs the project test suite using an auto-detected or explicitly specified test framework. It supports parallel execution for faster runs, watch mode for continuous testing during development, coverage tracking per file and function, and automatic generation of test stubs for uncovered code.

### Framework Detection

ZERG automatically detects the test framework from the project structure:

- pytest
- jest
- cargo test
- go test
- mocha
- vitest

### Test Generation

When invoked with `--generate`, the command inspects the codebase for functions and methods that lack test coverage and creates test stubs. These stubs follow the conventions of the detected framework and include placeholder assertions.

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--generate` | off | Generate test stubs for uncovered code. |
| `--coverage` | off | Report test coverage per file and function. |
| `--watch` | off | Re-run tests automatically when source files change. |
| `--parallel` | 1 | Number of parallel test workers. |
| `--framework` | auto | Override the auto-detected test framework. Accepts `pytest`, `jest`, `cargo`, or `go`. |

## Examples

Run all tests with default settings:

```
/zerg:test
```

Run tests with coverage reporting:

```
/zerg:test --coverage
```

Enable watch mode for continuous feedback:

```
/zerg:test --watch
```

Run tests in parallel with 8 workers:

```
/zerg:test --parallel 8
```

Generate stubs for uncovered code:

```
/zerg:test --generate
```

## Sample Output

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

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | All tests passed |
| 1 | Some tests failed |
| 2 | Configuration error |

## Task Tracking

This command creates a Claude Code Task with the subject prefix `[Test]` on invocation, updates it to `in_progress` immediately, and marks it `completed` on success.

## See Also

- [[zerg-build]] -- Build the project before testing
- [[zerg-analyze]] -- Static analysis including coverage thresholds
- [[zerg-review]] -- Code review with test verification
