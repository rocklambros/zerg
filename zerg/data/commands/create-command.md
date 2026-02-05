# ZERG Create-Command

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

| Flag | Default | Description |
|------|---------|-------------|
| `<name>` | (required) | Command name (e.g., "my-command") |
| `--interactive` | `false` | Enable interactive wizard for prompts |
| `--help` | | Show usage and exit |

## Pre-Flight

```bash
# 1. Validate name was provided
if [ -z "$ARGUMENTS" ]; then
  echo "ERROR: Command name required"
  echo "Usage: /zerg:create-command <name> [--interactive]"
  exit 1
fi

# 2. Parse arguments
NAME=$(echo "$ARGUMENTS" | awk '{print $1}')
INTERACTIVE=$(echo "$ARGUMENTS" | grep -q -- "--interactive" && echo "true" || echo "false")

# 3. Validate name format (lowercase, hyphens allowed)
if ! echo "$NAME" | grep -qE '^[a-z][a-z0-9-]*$'; then
  echo "ERROR: Invalid command name: $NAME"
  echo "Name must start with lowercase letter, contain only lowercase letters, numbers, and hyphens"
  exit 1
fi

# 4. Check command doesn't already exist
COMMAND_FILE="zerg/data/commands/${NAME}.md"
if [ -f "$COMMAND_FILE" ]; then
  echo "ERROR: Command already exists: $COMMAND_FILE"
  exit 1
fi

# 5. Verify template exists
TEMPLATE_FILE="zerg/data/commands/_template.md"
if [ ! -f "$TEMPLATE_FILE" ]; then
  echo "ERROR: Template not found: $TEMPLATE_FILE"
  exit 1
fi
```

## Task Tracking

On invocation, create a Claude Code Task to track this command:

Call TaskCreate:
  - subject: "[Create-Command] Scaffold {name}"
  - description: "Creating new ZERG command: {name}. Mode: {quick|interactive}."
  - activeForm: "Scaffolding {name} command"

Immediately call TaskUpdate:
  - taskId: (the Claude Task ID)
  - status: "in_progress"

On completion, call TaskUpdate:
  - taskId: (the Claude Task ID)
  - status: "completed"

## Execution

### Quick Mode (Default)

Quick mode generates files from templates with sensible defaults.

```bash
# 1. Use ScaffoldGenerator to create command file
from zerg.validate_commands import ScaffoldGenerator

generator = ScaffoldGenerator()
command_path = generator.scaffold(
    name=NAME,
    description="Short description of the {name} command's purpose.",
    flags=None,  # Uses template defaults
)
print(f"Created: {command_path}")
```

```bash
# 2. Use DocGenerator to create documentation
from zerg.validate_commands import DocGenerator

doc_gen = DocGenerator()
doc_path = doc_gen.generate_command_doc(NAME)
doc_gen.update_wiki_index(NAME, "Short description of the {name} command's purpose.")
print(f"Created: {doc_path}")
print(f"Updated: docs/commands-quick.md index")
```

```bash
# 3. Generate pressure test scaffold
PRESSURE_TEST_FILE="tests/pressure/test_${NAME//-/_}.py"
mkdir -p tests/pressure

cat > "$PRESSURE_TEST_FILE" << 'EOF'
"""Pressure tests for /zerg:{name} command."""

import pytest
from pathlib import Path

COMMAND_FILE = Path("zerg/data/commands/{name}.md")


class TestCommand{ClassName}:
    """Verify /zerg:{name} command behavior."""

    def test_command_file_exists(self):
        """Command file must exist."""
        assert COMMAND_FILE.exists()

    def test_passes_validation(self):
        """Command must pass validate_commands checks."""
        from zerg.validate_commands import validate_task_references
        passed, errors = validate_task_references(COMMAND_FILE.parent)
        # Filter to just this command
        relevant = [e for e in errors if "{name}" in e]
        assert not relevant, relevant

    def test_has_required_sections(self):
        """Command must have Pre-Flight, Task Tracking, Help."""
        content = COMMAND_FILE.read_text()
        assert "## Pre-Flight" in content or "## Pre-flight" in content
        assert "## Task Tracking" in content
        assert "## Help" in content

    @pytest.mark.skip(reason="Pressure test - manual verification")
    def test_execution_without_command(self):
        """Verify behavior when command not loaded."""
        # TODO: Implement pressure test
        pass

    @pytest.mark.skip(reason="Pressure test - manual verification")
    def test_execution_with_command(self):
        """Verify behavior when command is loaded."""
        # TODO: Implement pressure test
        pass
EOF

# Replace placeholders in pressure test
sed -i '' "s/{name}/$NAME/g" "$PRESSURE_TEST_FILE"
sed -i '' "s/{ClassName}/$(echo $NAME | sed 's/-/ /g' | awk '{for(i=1;i<=NF;i++) $i=toupper(substr($i,1,1)) tolower(substr($i,2))}1' | tr -d ' ')/g" "$PRESSURE_TEST_FILE"

print(f"Created: {PRESSURE_TEST_FILE}")
```

```bash
# 4. Report what was created
echo ""
echo "Created:"
echo "  - zerg/data/commands/${NAME}.md"
echo "  - tests/pressure/test_${NAME//-/_}.py"
echo "  - docs/commands/${NAME}.md"
echo "  - Updated docs/commands-quick.md index"
echo ""
echo "Run validation:"
echo "  python -m zerg.validate_commands"
```

### Interactive Mode (--interactive)

Interactive mode prompts for command metadata before scaffolding.

```bash
# 1. Prompt for description
echo "Enter command description (one line):"
read DESCRIPTION
if [ -z "$DESCRIPTION" ]; then
  DESCRIPTION="Short description of the ${NAME} command's purpose."
fi

# 2. Prompt for flags
FLAGS=()
echo ""
echo "Define command flags (enter empty name to finish):"
while true; do
  echo "Flag name (e.g., --verbose):"
  read FLAG_NAME
  if [ -z "$FLAG_NAME" ]; then
    break
  fi
  echo "Default value (or 'none'):"
  read FLAG_DEFAULT
  echo "Description:"
  read FLAG_DESC
  FLAGS+=("{\"name\": \"$FLAG_NAME\", \"default\": \"$FLAG_DEFAULT\", \"description\": \"$FLAG_DESC\"}")
done

# 3. Use ScaffoldGenerator with collected metadata
from zerg.validate_commands import ScaffoldGenerator

generator = ScaffoldGenerator()
command_path = generator.scaffold(
    name=NAME,
    description=DESCRIPTION,
    flags=FLAGS if FLAGS else None,
)
print(f"Created: {command_path}")
```

Then continue with steps 2-4 from Quick Mode above.

## Output Example

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

## Exit Codes

- 0: Command scaffolded successfully
- 1: Scaffolding failed (name conflict, template missing, etc.)
- 2: Invalid arguments or configuration error

## Help

When `--help` is passed in `$ARGUMENTS`, display usage and exit:

```
/zerg:create-command — Scaffold new ZERG slash commands with Task ecosystem integration.

Usage:
  /zerg:create-command <name> [--interactive]

Arguments:
  <name>          Command name (lowercase, hyphens allowed, e.g., "my-command")

Flags:
  --interactive   Enable interactive wizard for description and flags prompts
  --help          Show this help message

Examples:
  /zerg:create-command my-command             # Quick scaffold
  /zerg:create-command my-command --interactive  # Wizard mode

Generated files:
  - zerg/data/commands/{name}.md      Command file
  - tests/pressure/test_{name}.py     Pressure test scaffold
  - docs/commands/{name}.md           Documentation
  - docs/commands-quick.md            Index (updated)
```
