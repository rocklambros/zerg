# Requirements: Z Shortcut & Rename Troubleshoot → Debug

**Feature**: z-shortcut-and-rename
**Status**: APPROVED
**Created**: 2026-01-30

## Goal

Two coordinated changes:
1. Create `/z` as a shortcut alias for all `/zerg` commands (e.g., `/z:rush`, `/z:status`, `/z:debug`)
2. Rename `troubleshoot` to `debug` across all code, commands, docs, tests, and references

## Functional Requirements

### FR-1: `/z` Shortcut Alias (Slash Commands)
- Create `z:*.md` command files that mirror every `zerg:*.md` command
- Each `z:*.md` file is a thin redirect: reads and includes the corresponding `zerg:*.md` content
- `zerg install-commands` installs both `zerg:*.md` AND `z:*.md` files
- `zerg uninstall-commands` removes both prefixes
- Full autocomplete parity: `/z:rush` works identically to `/zerg:rush`

### FR-2: Rename troubleshoot → debug (CLI)
- `zerg/commands/troubleshoot.py` → `zerg/commands/debug.py`
- Click command name changes from `troubleshoot` to `debug`
- `zerg debug` works at CLI; `zerg troubleshoot` no longer exists
- All imports/exports updated in `__init__.py` and `cli.py`

### FR-3: Rename troubleshoot → debug (Slash Commands)
- `zerg:troubleshoot.md` → `zerg:debug.md`
- New `z:debug.md` shortcut also created
- All internal references updated

### FR-4: Rename troubleshoot → debug (Code)
- Class names: TroubleshootPhase → DebugPhase, TroubleshootConfig → DebugConfig, TroubleshootCommand → DebugCommand
- Logger name: `get_logger("troubleshoot")` → `get_logger("debug")`
- All string literals referencing "troubleshoot" updated
- Diagnostics package docstrings and references updated

### FR-5: Rename troubleshoot → debug (Tests)
- `test_troubleshoot_cmd.py` → `test_debug_cmd.py`
- `test_troubleshoot.py` (integration) → `test_debug.py`
- All imports and string assertions updated

### FR-6: Rename troubleshoot → debug (Documentation)
- README.md references updated
- Backlog, dogfood-bugs, session docs updated
- CLAUDE.md references updated
- PROJECT_INSTRUCTIONS.md updated

## Non-Functional Requirements

- Zero behavioral change: all existing functionality preserved
- `zerg install-commands --force` must re-install with new names
- All existing tests pass (renamed but functionally identical)
- ruff and mypy clean
