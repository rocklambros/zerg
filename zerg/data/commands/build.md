# ZERG Build

Build orchestration with error recovery.

## Usage

```bash
/zerg:build [--target all]
            [--mode dev|staging|prod]
            [--clean]
            [--watch]
            [--retry 3]
```

## Auto-Detection

Supported build systems:
- npm (package.json)
- cargo (Cargo.toml)
- make (Makefile)
- gradle (build.gradle)
- go (go.mod)
- python (pyproject.toml)

## Error Recovery

| Category | Action |
|----------|--------|
| missing_dependency | Install dependencies |
| type_error | Suggest fix |
| resource_exhaustion | Reduce parallelism |
| network_timeout | Retry with backoff |

## Examples

```bash
# Build with defaults
/zerg:build

# Production build
/zerg:build --mode prod

# Clean build
/zerg:build --clean

# Watch mode
/zerg:build --watch
```

## Task Tracking

On invocation, create a Claude Code Task to track this command:

Call TaskCreate:
  - subject: "[Build] Build {target}"
  - description: "Build orchestration for {target}. Mode: {mode}. Clean: {clean}."
  - activeForm: "Building {target}"

Immediately call TaskUpdate:
  - taskId: (the Claude Task ID)
  - status: "in_progress"

On completion, call TaskUpdate:
  - taskId: (the Claude Task ID)
  - status: "completed"

## Exit Codes

- 0: Build successful
- 1: Build failed
- 2: Configuration error

## Help

When `--help` is passed in `$ARGUMENTS`, display usage and exit:

```
/zerg:build — Build orchestration with error recovery.

Flags:
  --target <name>     Build target (default: all)
  --mode <dev|staging|prod>
                      Build mode
  --clean             Clean before building
  --watch             Watch mode for continuous builds
  --retry <n>         Number of retries on failure (default: 3)
  --help              Show this help message
```
