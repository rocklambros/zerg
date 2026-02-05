# /zerg:create-command

Scaffold new ZERG slash commands with Task ecosystem integration, pressure tests, and documentation.

## Usage

```bash
# Quick mode (default) - scaffold from template
/zerg:create-command my-command

# Interactive wizard mode - prompts for metadata
/zerg:create-command my-command --interactive

# Show help
/zerg:create-command --help
```

## Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `<name>` | Yes | Command name (lowercase, hyphens allowed, e.g., "my-command") |

## Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--interactive` | `false` | Enable interactive wizard for description and flags prompts |
| `--help` | | Show usage and exit |

## Modes

### Quick Mode (Default)

Quick mode generates files from templates with sensible defaults:

1. Creates command file from `_template.md`
2. Generates documentation reference
3. Creates pressure test scaffold
4. Updates the commands index

### Interactive Mode (`--interactive`)

Interactive mode prompts for command metadata before scaffolding:

1. **Description prompt** — Enter a one-line description
2. **Flags prompt** — Define command flags (name, default, description) in a loop
3. Proceeds with scaffolding using collected metadata

## Generated Files

| File | Purpose |
|------|---------|
| `zerg/data/commands/{name}.md` | Command file with Task ecosystem integration |
| `tests/pressure/test_{name}.py` | Pressure test scaffold |
| `docs/commands/{name}.md` | Documentation reference |
| `docs/commands-quick.md` | Index (updated with new entry) |

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Command scaffolded successfully |
| 1 | Scaffolding failed (name conflict, template missing, etc.) |
| 2 | Invalid arguments or configuration error |

## Examples

### Quick scaffold

```bash
/zerg:create-command my-command
```

Output:
```
[Create-Command] Scaffold my-command

Created:
  - zerg/data/commands/my-command.md
  - tests/pressure/test_my_command.py
  - docs/commands/my-command.md
  - Updated docs/commands-quick.md index

Run validation:
  python -m zerg.validate_commands

Task completed: [Create-Command] Scaffold my-command
```

### Interactive mode

```bash
/zerg:create-command my-command --interactive
```

Prompts for description and flags before generating files.

## Validation

After scaffolding, run validation to ensure the new command passes all checks:

```bash
python -m zerg.validate_commands
```

## See Also

- [Commands Reference](../commands.md) — All ZERG commands
- [/zerg:plugins](../commands.md#zergplugins) — Plugin management
