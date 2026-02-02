# /zerg:refactor

Automated code improvement and cleanup with configurable transforms.

## Synopsis

```
/zerg:refactor [--transforms dead-code,simplify,types,patterns,naming]
               [--dry-run]
               [--interactive]
```

## Description

The `refactor` command analyzes the codebase and applies automated code improvements. Each transform targets a specific category of improvement and can be run individually or in combination. By default, suggestions are reported but not applied unless confirmed.

### Transforms

**dead-code** -- Remove unused imports, variables, and functions.

**simplify** -- Simplify complex or redundant expressions:

- `if x == True:` becomes `if x:`
- `if x == None:` becomes `if x is None:`
- Removes redundant parentheses
- Eliminates unnecessary `else` after `return`

**types** -- Strengthen type annotations:

- Add missing type hints to function parameters and return values
- Replace `Any` with specific types where inferable
- Add return type annotations to untyped functions

**patterns** -- Apply common design patterns:

- Extract repeated code into shared functions
- Apply guard clauses for early exits
- Convert nested conditions to early returns

**naming** -- Improve variable and function names:

- Replace single-letter variable names with descriptive alternatives
- Fix casing convention violations
- Make names more descriptive based on usage context

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--transforms` | all | Comma-separated list of transforms to apply. Accepts `dead-code`, `simplify`, `types`, `patterns`, `naming`. |
| `--dry-run` | off | Report suggestions without applying any changes. |
| `--interactive` | off | Prompt for confirmation before applying each suggestion. |

## Examples

Preview dead-code and simplify transforms without applying:

```
/zerg:refactor --transforms dead-code,simplify --dry-run
```

Run in interactive mode to approve changes one by one:

```
/zerg:refactor --interactive
```

Apply only type and naming improvements:

```
/zerg:refactor --transforms types,naming
```

## Sample Output

```
Refactor Results
========================================
Files Analyzed: 15
Suggestions: 23
Applied: 0

Suggestions:
  simplify:
    auth.py:42
      - if authenticated == True:
      + if authenticated:
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | No issues found (or all suggestions applied) |
| 1 | Suggestions available (not yet applied) |
| 2 | Error during analysis |

## Task Tracking

This command creates a Claude Code Task with the subject prefix `[Refactor]` on invocation, updates it to `in_progress` immediately, and marks it `completed` on success.

## See Also

- [[zerg-analyze]] -- Static analysis to identify areas needing refactoring
- [[zerg-review]] -- Review refactored code before committing
- [[zerg-test]] -- Verify tests still pass after refactoring
