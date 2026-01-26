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

## Exit Codes

- 0: Build successful
- 1: Build failed
- 2: Configuration error
