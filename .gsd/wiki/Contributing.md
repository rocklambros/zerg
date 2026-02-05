# Contributing

This guide covers everything you need to contribute to ZERG. For a quick introduction to the project, see [Home](Home).

---

## Development Setup

### Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.12+ | ZERG targets `py312` exclusively |
| Git | Latest | Worktree support used internally by ZERG workers |
| Docker | Latest | Optional, required for `--mode container` execution |

### Clone and Install

```bash
# Clone the repository
git clone https://github.com/rocklambros/zerg.git
cd zerg

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install with dev dependencies
pip install -e ".[dev]"

# Install pre-commit hooks (required)
pre-commit install
```

This installs:
- **Core dependencies**: `click`, `pydantic`, `pyyaml`, `rich`
- **Dev tooling**: `pytest`, `pytest-cov`, `pytest-asyncio`, `mypy`, `ruff`, `pre-commit`

### IDE Setup Recommendations

| IDE | Setup |
|-----|-------|
| **VS Code** | Install Python extension, enable Ruff extension, set interpreter to `.venv/bin/python` |
| **PyCharm** | Mark `zerg/` as Sources Root, configure Python 3.12 interpreter, enable Ruff plugin |
| **Vim/Neovim** | Use `pyright` or `pylsp` for LSP, configure `ruff` as linter/formatter |

---

## Code Style

ZERG enforces consistent style through pre-commit hooks and CI checks.

### Pre-commit Hooks (Required)

All commits must pass pre-commit hooks. Install once after cloning:

```bash
pre-commit install
```

Hooks run automatically on every commit. To run manually:

```bash
pre-commit run --all-files
```

### Ruff (Linting & Formatting)

Ruff handles both linting and formatting. Configuration in `pyproject.toml`:

| Setting | Value |
|---------|-------|
| Target | `py312` |
| Line length | 120 |
| Selected rules | `E`, `F`, `I`, `UP` |
| Exclusions | `.zerg/`, `tests/fixtures/` |

```bash
# Run linting
ruff check .

# Run linting with auto-fix
ruff check . --fix

# Check formatting
ruff format --check .

# Apply formatting
ruff format .
```

### Mypy (Type Checking)

Mypy runs in **strict mode**. All function signatures require type annotations.

```bash
mypy zerg/
```

### Quick Style Check

Run all style checks at once:

```bash
ruff check . && ruff format --check . && mypy zerg/
```

---

## Test Requirements

### Running Tests

```bash
# Full test suite
pytest

# With coverage report
pytest --cov=zerg

# Verbose output
pytest -v
```

### Coverage Threshold

ZERG maintains a **97% coverage threshold**. All new code must include tests.

### Test Markers

Some tests require specific environments. Use markers to include or exclude:

| Marker | Description | Command |
|--------|-------------|---------|
| `@pytest.mark.slow` | Long-running tests | `pytest -m "not slow"` |
| `@pytest.mark.docker` | Requires Docker daemon | `pytest -m docker` |
| `@pytest.mark.e2e` | End-to-end tests | `pytest -m e2e` |
| `@pytest.mark.real_e2e` | Requires real Claude API | `pytest -m real_e2e` |

For local development, skip environment-dependent tests:

```bash
pytest -m "not docker and not e2e and not real_e2e"
```

### Test Organization

- **Unit tests**: `tests/unit/` — Fast, isolated, no external dependencies
- **Integration tests**: `tests/integration/` — Module interactions, may use fixtures
- **E2E tests**: Marked with `@pytest.mark.e2e` or `@pytest.mark.real_e2e`

### Writing Tests

1. Every new module must have unit tests
2. Every new module must have at least one integration test with a production caller
3. Test files mirror source structure: `zerg/foo.py` -> `tests/unit/test_foo.py`
4. Use fixtures from `tests/conftest.py` where available

---

## PR Process

### 1. Create a Feature Branch

Branch from `main` with a descriptive name:

```bash
git checkout -b feature/worker-retry-logic
git checkout -b fix/state-recovery
git checkout -b docs/wiki-improvements
```

**Naming conventions:**
- `feature/` — New functionality
- `fix/` — Bug fixes
- `docs/` — Documentation changes
- `refactor/` — Code restructuring
- `test/` — Test additions or fixes
- `chore/` — Maintenance tasks

### 2. Update CHANGELOG.md (Required)

A CHANGELOG update is **required** and enforced by CI. Add your entry under `[Unreleased]`:

```markdown
## [Unreleased]

### Added
- New feature description (#PR_NUMBER)

### Changed
- Modified behavior description (#PR_NUMBER)

### Fixed
- Bug fix description (#PR_NUMBER)
```

Follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format.

To skip the check (rare), apply the `skip-changelog` label to your PR.

### 3. Ensure CI Passes

All PRs must pass:
- `ruff check` — Linting
- `ruff format --check` — Formatting
- `mypy zerg/` — Type checking
- `pytest` — Test suite

### 4. PR Template Checklist

Your PR description should include:
- Summary of changes
- Link to related issue (if applicable)
- Test plan
- Screenshots (for UI changes)

### 5. Request Review

All PRs require review before merge. Tag maintainers if urgent.

---

## Commit Conventions

### Conventional Commits

Use conventional commit prefixes:

| Prefix | Use Case |
|--------|----------|
| `feat:` | New features |
| `fix:` | Bug fixes |
| `docs:` | Documentation changes |
| `refactor:` | Code restructuring without behavior change |
| `test:` | Test additions or modifications |
| `chore:` | Maintenance, dependencies, tooling |
| `perf:` | Performance improvements |
| `style:` | Code style changes (formatting, whitespace) |

### Examples

```bash
# New feature
feat(worker): add retry logic with exponential backoff

# Bug fix
fix(launcher): handle missing Docker daemon gracefully

# Documentation
docs(wiki): add troubleshooting page

# Multiple scopes
feat(design,task-graph): support circular dependency detection
```

### Claude Co-Authorship

When Claude assists with code, include the co-author trailer:

```bash
git commit -m "feat(worker): add checkpoint restoration

Implemented checkpoint restoration for interrupted workers.
Checkpoints are saved every 30 seconds during task execution.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Architecture Guidelines

### Module Structure

Every new Python module in `zerg/` must:

1. **Have a production caller** — At least one other production file must import it
2. **Have unit tests** — In `tests/unit/test_<module>.py`
3. **Have integration tests** — Prove the module works with its callers

Standalone entry points (`__main__.py`, files with `if __name__`) are exempt from the caller requirement.

### Consumer Matrix

During design phase, the `consumers` field in task specifications tracks who calls what. This prevents orphaned modules that pass unit tests but are never used.

### Validation

Run the validation script to check for orphaned modules:

```bash
python -m zerg.validate_commands
```

This runs in CI and pre-commit.

### Command Files

Commands in `zerg/data/commands/` have special requirements:

1. **Task ecosystem integration** — All commands must include TaskCreate/TaskUpdate calls
2. **Command splitting** — Commands >300 lines should be split into `.core.md` and `.details.md`
3. **Bracketed prefixes** — Task subjects use `[Plan]`, `[Design]`, `[L1]`, etc.

See the Anti-Drift Rules in `CLAUDE.md` for the full policy.

---

## Reporting Issues

### Bugs

Include:
- Steps to reproduce
- Expected vs. actual behavior
- Python version (`python --version`)
- OS and version
- ZERG version (check `pyproject.toml`)
- Relevant logs (`.zerg/logs/`)

### Feature Requests

Describe the **problem** you're solving, not just the solution. This helps maintainers evaluate alternatives.

### Security Vulnerabilities

Do **not** open public issues. See [Security](Security) for private reporting instructions.

---

## Resources

- [Architecture](Architecture) — System design and module reference
- [Command-Reference](Command-Reference) — All 26 commands with usage examples
- [Context-Engineering](Context-Engineering) — Token optimization techniques
- [CLAUDE.md](https://github.com/rocklambros/zerg/blob/main/CLAUDE.md) — Anti-drift rules and Task ecosystem details

---

## License

By contributing to ZERG, you agree that your contributions will be licensed under the [MIT License](https://github.com/rocklambros/zerg/blob/main/LICENSE).
