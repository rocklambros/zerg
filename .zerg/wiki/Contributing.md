# Contributing

This guide covers how to contribute to the ZERG project: setting up your development environment, understanding the project structure, following coding standards, and submitting changes.

---

## Table of Contents

- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Coding Standards](#coding-standards)
- [Making Changes](#making-changes)
- [Pull Request Process](#pull-request-process)
- [Testing Requirements](#testing-requirements)
- [Command File Guidelines](#command-file-guidelines)

---

## Development Setup

### Prerequisites

- Python 3.10 or later
- Git
- Docker (required for container mode development and testing)
- Claude Code (for running ZERG commands during development)

### Clone and Install

```bash
git clone <repository-url>
cd ZERG
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Verify the Setup

```bash
# Run the test suite
pytest

# Run with coverage
pytest --cov=zerg --cov-report=term-missing

# Check types (if configured)
# mypy zerg/
```

### Docker Setup (for container mode)

If you are working on container-related features:

```bash
docker info   # Verify Docker is running
```

---

## Project Structure

```
ZERG/
├── zerg/                       # Main package
│   ├── __init__.py
│   ├── __main__.py             # Entry point
│   ├── cli.py                  # CLI argument parsing
│   ├── orchestrator.py         # Core orchestration logic
│   ├── launcher.py             # Worker process/container spawning
│   ├── state.py                # State management
│   ├── config.py               # Configuration loading
│   ├── levels.py               # Level coordination
│   ├── merge.py                # Branch merging
│   ├── git_ops.py              # Git operations
│   ├── worktree.py             # Git worktree management
│   ├── ports.py                # Port allocation
│   ├── containers.py           # Docker container management
│   ├── verify.py               # Task verification runner
│   ├── security.py             # Security validation
│   ├── context_plugin.py       # Context engineering plugin
│   ├── context_tracker.py      # Token/context tracking
│   ├── types.py                # Shared type definitions
│   ├── constants.py            # Project constants
│   ├── exceptions.py           # Custom exceptions
│   ├── data/
│   │   └── commands/           # Slash command definitions (26 commands)
│   │       ├── zerg:init.md
│   │       ├── zerg:plan.md
│   │       ├── zerg:design.md
│   │       ├── zerg:rush.md
│   │       ├── zerg:worker.md
│   │       ├── zerg:merge.md
│   │       ├── zerg:status.md
│   │       ├── zerg:debug.md
│   │       ├── zerg:test.md
│   │       └── ...
│   ├── diagnostics/            # Debug and diagnostic tools
│   ├── doc_engine/             # Documentation generation
│   ├── performance/            # Performance monitoring
│   └── schemas/                # JSON schemas for validation
├── tests/
│   ├── unit/                   # Isolated unit tests
│   ├── integration/            # Component interaction tests
│   ├── e2e/                    # End-to-end workflow tests
│   ├── fixtures/               # Shared test data
│   ├── helpers/                # Test utility functions
│   ├── mocks/                  # Shared mock objects
│   ├── conftest.py             # Root pytest configuration
│   └── test_*.py               # Legacy/core tests
├── .zerg/
│   ├── config.yaml             # Runtime configuration
│   ├── state/                  # Runtime state files
│   ├── logs/                   # Worker and merge logs
│   ├── wiki/                   # Project wiki pages
│   └── ...
├── .gsd/
│   └── specs/                  # Feature spec files and task graphs
├── CLAUDE.md                   # Project instructions for Claude Code
└── claudedocs/                 # Generated reports and analysis
```

### Key Modules

| Module | Responsibility |
|--------|---------------|
| `orchestrator.py` | Coordinates the full rush workflow: level iteration, worker dispatch, merge triggers |
| `launcher.py` | Spawns workers as subprocesses or Docker containers. Handles authentication passthrough |
| `state.py` | Manages task and worker state. Reads/writes `.zerg/state/` files |
| `levels.py` | Controls level advancement. Determines when all tasks at a level are complete |
| `merge.py` | Merges worker branches after each level. Runs quality gates |
| `worktree.py` | Creates and cleans up git worktrees for each worker |
| `config.py` | Loads and validates `.zerg/config.yaml` |
| `verify.py` | Runs task verification commands and reports results |
| `context_plugin.py` | Context engineering: command splitting, task-scoped context, security rule filtering |

---

## Coding Standards

### Python Style

- Follow PEP 8 for all Python code.
- Use type annotations on all function signatures.
- Use `pathlib.Path` over `os.path` for file path operations.
- Prefer `subprocess.run` with argument lists over `shell=True`.

### Naming Conventions

- **Files:** `snake_case.py`
- **Classes:** `PascalCase`
- **Functions and variables:** `snake_case`
- **Constants:** `UPPER_SNAKE_CASE`
- **Test files:** `test_<module>.py` in the appropriate test directory

### Type Annotations

All public functions must have type annotations:

```python
def get_task_status(task_id: str, feature: str) -> TaskStatus:
    """Return the current status of a task.

    Args:
        task_id: The unique task identifier.
        feature: The feature name.

    Returns:
        The current task status.

    Raises:
        TaskNotFoundError: If the task does not exist.
    """
    ...
```

### Error Handling

- Define custom exceptions in `zerg/exceptions.py`.
- Raise specific exceptions, not generic `Exception`.
- Log errors before re-raising when context would be lost.
- Never expose stack traces or internal paths in user-facing output.

### Security

The project follows OWASP 2025 guidelines. Key rules:

- Never use `shell=True` in subprocess calls.
- Never use unsafe deserialization (use `json` or `yaml.safe_load` instead).
- Validate all file paths to prevent traversal.
- Do not hardcode secrets or API keys.
- See `.claude/rules/security/` for the full security ruleset.

---

## Making Changes

### Branch Strategy

Always work on a feature branch. Never commit directly to `main`.

```bash
git checkout main
git pull
git checkout -b feature/your-feature-name
```

### Commit Messages

Use conventional commit format:

```
type(scope): description

Examples:
feat(launcher): add container health check support
fix(state): resolve race condition in task claiming
test(merge): add integration test for quality gates
docs(wiki): add troubleshooting guide
refactor(levels): simplify level advancement logic
```

Types: `feat`, `fix`, `test`, `docs`, `refactor`, `chore`, `perf`.

### What to Include in a Commit

- Source code changes and their corresponding tests.
- Documentation updates if the change affects user-facing behavior.
- Configuration changes if defaults are modified.

### What Not to Include

- IDE configuration files (`.idea/`, `.vscode/`).
- Local environment files (`.env`).
- Build artifacts or coverage reports.
- Debug scripts or temporary files.

---

## Pull Request Process

### Before Submitting

1. **Run the full test suite** and verify it passes:
   ```bash
   pytest
   ```

2. **Run tests with coverage** and verify no regressions:
   ```bash
   pytest --cov=zerg --cov-report=term-missing
   ```

3. **Check for lint issues** if a linter is configured.

4. **Review your changes** with `git diff` before committing.

5. **Write tests** for all new functionality. See [[Testing]] for guidelines.

### PR Description

Include:
- A summary of what the change does and why.
- How to test the change.
- Any breaking changes or migration steps.
- Related issue numbers if applicable.

### Review Checklist

Reviewers will check:

- [ ] Tests pass and cover the new code.
- [ ] Type annotations are present on public functions.
- [ ] No hardcoded secrets or credentials.
- [ ] Error handling follows project conventions.
- [ ] Command files include Task ecosystem integration (if applicable).
- [ ] Documentation is updated for user-facing changes.

---

## Testing Requirements

All contributions must include tests. See [[Testing]] for full details on the testing approach.

Summary of requirements:

- **New modules:** Add unit tests in `tests/unit/test_<module>.py`.
- **New features:** Add integration tests demonstrating the feature works end-to-end.
- **Bug fixes:** Add a test that reproduces the bug and verifies the fix.
- **Command changes:** Verify Task ecosystem integration is preserved (see below).

### Running Tests

```bash
# Full suite
pytest

# Specific category
pytest tests/unit/
pytest tests/integration/
pytest tests/e2e/

# Single file
pytest tests/unit/test_launcher.py -v

# Parallel execution
pytest -n auto
```

---

## Command File Guidelines

ZERG slash commands are defined as markdown files in `zerg/data/commands/`. These files have specific requirements that must be maintained.

### Task Ecosystem Integration

Every command file must include Claude Code Task tracking. This is non-negotiable. The minimum pattern is:

```
On invocation:  TaskCreate (subject with [Bracketed] prefix)
Immediately:    TaskUpdate status "in_progress"
On completion:  TaskUpdate status "completed"
```

### Subject Naming Convention

All tasks use bracketed prefixes:

```
[Plan] Capture requirements: {feature}
[Design] Architecture for {feature}
[L{level}] {task title}
[Init], [Cleanup], [Review], [Build], [Test], [Debug], [Security]
```

### Backbone Commands

Five commands have deeper Task integration requirements beyond the minimum. Do not reduce these to the minimum pattern:

| Command | Additional Requirements |
|---------|------------------------|
| `zerg:worker.md` | TaskUpdate to claim tasks, TaskUpdate for failures/checkpoints, TaskList at completion |
| `zerg:status.md` | TaskList as primary data source, cross-reference with state JSON, flag mismatches |
| `zerg:merge.md` | TaskUpdate after quality gates per level, TaskList verification at finalize |
| `zerg:stop.md` | TaskUpdate with PAUSED/FORCE STOPPED annotations |
| `zerg:retry.md` | TaskGet to read state, TaskUpdate to reset to pending, TaskUpdate on reassignment |

### Command Splitting

Large command files (over 300 lines) are split into two files:

- `zerg:<command>.core.md` -- Essential instructions (~30% of content)
- `zerg:<command>.details.md` -- Reference material (~70% of content)

The original file retains core content for backward compatibility. If you are modifying a split command, update both the core and details files.

### Drift Detection

Before committing changes to any command file, run the drift detection checklist from `CLAUDE.md`:

```bash
# All 26 command files must reference Task tools
grep -rL "TaskCreate\|TaskUpdate\|TaskList\|TaskGet" zerg/data/commands/zerg:*.md

# Expected output: empty (no files missing Task references)
```

If any command file is missing Task references, add them before committing.

---

## See Also

- [[Testing]] -- Detailed testing approach and guidelines
- [[Debug Guide]] -- Debugging ZERG during development
- [[Troubleshooting]] -- Common issues and solutions
- [[Command Reference]] -- Full command documentation
