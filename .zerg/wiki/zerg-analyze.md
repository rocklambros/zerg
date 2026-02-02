# /zerg:analyze

Run static analysis, complexity metrics, and quality assessment.

## Synopsis

```
/zerg:analyze [--check lint|complexity|coverage|security|all]
              [--format text|json|sarif]
              [--threshold complexity=10,coverage=70]
              [--files path/to/files]
```

## Description

The `analyze` command performs static analysis on the project codebase. It supports multiple check types that can be run individually or combined, with configurable thresholds and output formats suitable for both human review and CI/CD integration.

### Check Types

**lint** -- Language-specific linting using tools such as ruff for Python and eslint for JavaScript.

**complexity** -- Cyclomatic and cognitive complexity analysis. Functions exceeding the configured threshold are flagged.

**coverage** -- Test coverage analysis and reporting. Identifies files and functions below the coverage threshold.

**security** -- Static Application Security Testing (SAST) for vulnerability detection using tools such as bandit and semgrep.

**all** -- Runs all of the above checks in sequence.

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--check` | `all` | Type of analysis to run. Accepts `lint`, `complexity`, `coverage`, `security`, or `all`. |
| `--format` | `text` | Output format. Accepts `text`, `json`, or `sarif`. |
| `--threshold` | `complexity=10,coverage=70` | Comma-separated key=value thresholds for pass/fail determination. |
| `--files` | entire project | Restrict analysis to specific file paths or directories. |

### Output Formats

| Format | Use Case |
|--------|----------|
| `text` | Human-readable summary for terminal output. |
| `json` | Machine-parseable JSON for scripts and automation. |
| `sarif` | Static Analysis Results Interchange Format for IDE integration and GitHub Advanced Security. |

## Examples

Run all checks with default thresholds:

```
/zerg:analyze --check all
```

Run linting only with JSON output:

```
/zerg:analyze --check lint --format json
```

Set custom complexity threshold:

```
/zerg:analyze --check complexity --threshold complexity=15
```

Generate SARIF output for IDE integration:

```
/zerg:analyze --check all --format sarif > results.sarif
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | All checks passed |
| 1 | One or more checks failed |
| 2 | Configuration error |

## Task Tracking

This command creates a Claude Code Task with the subject prefix `[Analyze]` on invocation, updates it to `in_progress` immediately, and marks it `completed` on success.

## See Also

- [[zerg-security]] -- Dedicated security scanning with compliance presets
- [[zerg-test]] -- Test execution and coverage measurement
- [[zerg-refactor]] -- Automated code improvements based on analysis findings
