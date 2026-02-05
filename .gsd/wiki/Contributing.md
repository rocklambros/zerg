# Contributing

Welcome to ZERG. This guide explains not just how to contribute, but why our processes exist. Understanding the philosophy behind our conventions will help you make contributions that strengthen the project.

---

## Project Philosophy

Before diving into the mechanics of contributing, it helps to understand what ZERG values and why.

### Parallel-First Thinking

ZERG exists to coordinate many Claude Code instances working simultaneously. This shapes everything we build:

- **Why file ownership matters**: When five workers edit the same file, merge conflicts explode. Our task system assigns exclusive file ownership because parallel execution demands clear boundaries.
- **Why specs are the source of truth**: Workers don't share conversation history. The spec file is their shared memory—without it, parallel execution falls apart.
- **Why levels exist**: Dependencies create ordering constraints. Levels let us say "all of L1 must complete before any L2 starts" without complex orchestration.

### Spec-Driven Development

Traditional projects communicate through conversation. ZERG can't—workers are stateless Claude instances. This led to spec-driven development:

- **The spec captures everything**: Requirements, architecture, task graph, file ownership. Workers read the spec; they don't ask questions.
- **Human approval gates**: Before design becomes tasks, humans review. This is our checkpoint against misaligned execution.
- **Immutable tasks**: Once approved, task definitions don't change mid-flight. Predictability enables parallelism.

### Crash-Safe, Restartable Execution

Workers fail. Networks drop. Containers timeout. ZERG assumes failure:

- **Idempotent tasks**: Running a task twice produces the same result. Workers can be interrupted and restarted.
- **Checkpoint state**: `.zerg/state/` captures progress. Resume picks up where we left off.
- **Verification commands**: Every task has a pass/fail check. No subjective "looks good"—either the test passes or it doesn't.

### Clear Task Boundaries

Ambiguity kills parallel execution. Each task must be:

- **Atomic**: One clear deliverable, achievable in one session
- **Verifiable**: Automated command confirms completion
- **Isolated**: File ownership prevents conflicts between workers

These values shape our contribution guidelines. When you understand the "why," the "how" makes sense.

---

## Mental Model for Contributors

### How ZERG is Structured

```
zerg/
├── data/commands/    # Slash command definitions (the "brain")
├── launcher.py       # Worker spawning (subprocess/Docker)
├── task_graph.py     # Dependency management
├── state.py          # Progress tracking
└── ...

.zerg/
├── specs/            # Feature specifications (human-reviewed)
├── state/            # Runtime state (crash-safe recovery)
└── config.yaml       # Project settings
```

**Commands define behavior**: When you run `/zerg:rush`, Claude reads `zerg/data/commands/rush.md`. That file tells Claude what to do. Changing behavior means changing command files.

**Python code enables commands**: The Python modules handle mechanics—spawning workers, tracking state, managing dependencies. Commands orchestrate; Python executes.

### Where Different Changes Belong

| Change Type | Location | Notes |
|-------------|----------|-------|
| New CLI flag | `cli.py` + relevant command `.md` | Flag parsing in Python, behavior in command |
| Worker behavior | `worker.md` (and `.core.md`/`.details.md`) | Workers read these instructions |
| State tracking | `state.py` | Must maintain crash-safe guarantees |
| New slash command | `zerg/data/commands/<name>.md` | Plus registration in command loader |

### What Makes a Good ZERG Contribution

**Good contributions understand the parallel context**: If your change introduces shared mutable state between workers, it will break. If your change requires conversation history, it won't work.

**Good contributions are verifiable**: Can you write a command that proves the feature works? If not, rethink the approach.

**Good contributions have clear boundaries**: "This PR adds X" not "This PR improves various things."

---

## Development Setup

### Prerequisites

| Requirement | Version | Why This Version |
|-------------|---------|------------------|
| Python | 3.12+ | ZERG uses `py312` features; we don't maintain backward compatibility because it simplifies the codebase |
| Git | Latest | Worktree support is used internally—older Git versions may have bugs |
| Docker | Latest | Optional, but required for `--mode container` (isolated worker execution) |

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

**Why editable install (`-e`)**: During development, you want code changes to take effect immediately without reinstalling. The `-e` flag creates a symlink instead of copying files.

**Why pre-commit hooks are required**: They catch issues before code leaves your machine. Fixing linting in CI is slower and more frustrating than fixing it locally.

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

ZERG enforces consistent style through pre-commit hooks and CI. This isn't about aesthetics—it's about reducing cognitive load during code review and eliminating style debates.

### Pre-commit Hooks (Required)

**Why pre-commit?** It catches problems before they enter the repository. Reviewers shouldn't waste time on formatting issues, and you shouldn't have CI failures for things your editor could have caught.

All commits must pass pre-commit hooks. Install once after cloning:

```bash
pre-commit install
```

Hooks run automatically on every commit. To run manually:

```bash
pre-commit run --all-files
```

### Ruff (Linting & Formatting)

**Why Ruff?** It's fast (written in Rust) and combines linting + formatting in one tool. Before Ruff, we needed Black + isort + Flake8. Now it's one command.

Configuration in `pyproject.toml`:

| Setting | Value | Reason |
|---------|-------|--------|
| Target | `py312` | We use modern Python features |
| Line length | 120 | 80 is too cramped for modern monitors; 120 balances readability with density |
| Selected rules | `E`, `F`, `I`, `UP` | Error, pyflakes, isort, pyupgrade—catches real bugs without excessive pedantry |
| Exclusions | `.zerg/`, `tests/fixtures/` | Generated/fixture files shouldn't trigger violations |

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

**Why strict mode?** Types are documentation that the compiler verifies. In a parallel execution system, type errors can cause subtle failures that are hard to debug. Strict mode ensures every function signature is explicit.

Mypy runs in **strict mode**. All function signatures require type annotations.

```bash
mypy zerg/
```

**Why type every function?** When you see `def process_task(task: Task) -> Result`, you know exactly what goes in and comes out. Without types, you're guessing from context—and in a codebase where workers are stateless, that context might not exist.

### Quick Style Check

Run all style checks at once:

```bash
ruff check . && ruff format --check . && mypy zerg/
```

---

## Test Requirements

### Why Testing Matters More in ZERG

In most projects, bugs surface during development. In ZERG, bugs might surface when the fifth worker hits an edge case at 2 AM during an unattended rush. Tests are our first line of defense against parallel chaos.

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

**Why 97%?** High coverage ensures most code paths are exercised. The 3% buffer accounts for defensive error handlers and platform-specific branches that are genuinely hard to test. But "hard to test" shouldn't be an excuse—if coverage drops, investigate.

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

**Why this split?** Unit tests run in milliseconds and catch logic errors. Integration tests catch wiring problems (module A calls module B incorrectly). E2E tests prove the system works end-to-end. Each layer serves a different purpose.

### Writing Tests

1. **Every new module must have unit tests** — Proves the module works in isolation
2. **Every new module must have at least one integration test with a production caller** — Proves the module works with its actual consumers (not just in isolation)
3. **Test files mirror source structure**: `zerg/foo.py` -> `tests/unit/test_foo.py`
4. **Use fixtures from `tests/conftest.py` where available** — Consistency and reduced boilerplate

**Why require integration tests?** A module can pass all unit tests but fail in production because it's called differently than tests expected. Integration tests catch this by testing the actual call sites.

---

## PR Process

### Why This Process Exists

Our PR process ensures changes are reviewable, reversible, and well-documented. Each step serves a purpose—skip steps and you skip their protections.

### 1. Create a Feature Branch

**Why feature branches?** Main is always deployable. Feature branches let you experiment without breaking what works. They also enable parallel development—multiple contributors can work simultaneously without stepping on each other.

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

**Why these prefixes?** They communicate intent at a glance. When you see `fix/state-recovery` in the branch list, you immediately know what that branch is about.

### 2. Update CHANGELOG.md (Required)

A CHANGELOG update is **required** and enforced by CI.

**Why require changelog updates?** Users need to know what changed. "See the git log" isn't helpful for someone deciding whether to upgrade. The changelog is the user-facing summary of changes.

Add your entry under `[Unreleased]`:

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

**Why Keep a Changelog format?** It's a standard. Users know where to find what they're looking for. Categories (Added, Changed, Fixed, Removed) answer different questions.

To skip the check (rare), apply the `skip-changelog` label to your PR. Use this only for changes that don't affect users (CI config, internal refactors, etc.).

### 3. Ensure CI Passes

All PRs must pass:
- `ruff check` — Linting
- `ruff format --check` — Formatting
- `mypy zerg/` — Type checking
- `pytest` — Test suite

**Why require all checks?** Each check catches a different class of problem. Passing tests but failing types means you have a latent bug. Passing types but failing lint means you might be using deprecated patterns.

### 4. PR Template Checklist

Your PR description should include:
- **Summary of changes** — What and why (the PR diff shows how)
- **Link to related issue** (if applicable) — Context for reviewers
- **Test plan** — How you verified the change works
- **Screenshots** (for UI changes) — Visual proof

**Why a checklist?** It prompts you to think about what reviewers need. A PR with no test plan makes reviewers worry about coverage. A PR with no summary forces reviewers to reverse-engineer intent from code.

### 5. Request Review

All PRs require review before merge. Tag maintainers if urgent.

**Why require reviews?** Two sets of eyes catch more issues. Reviews spread knowledge across the team. They also create accountability—someone else has verified this change makes sense.

---

## Commit Conventions

### Why Conventional Commits?

ZERG uses [Conventional Commits](https://www.conventionalcommits.org/) because they enable:

1. **Automatic changelog generation** — Tools can categorize commits into Added/Fixed/Changed
2. **Semantic versioning** — `feat:` triggers minor bump, `fix:` triggers patch
3. **Scannable git history** — You can find all bug fixes with `git log --grep="^fix:"`
4. **Clear intent** — `refactor:` vs `fix:` tells reviewers whether behavior should change

### Format

```
type(scope): description

[optional body]
```

### Prefixes and Their Meaning

| Prefix | Use Case | Version Impact | Changelog Section |
|--------|----------|----------------|-------------------|
| `feat:` | New features | Minor bump | Added |
| `fix:` | Bug fixes | Patch bump | Fixed |
| `docs:` | Documentation changes | None | — |
| `refactor:` | Code restructuring without behavior change | None | — |
| `test:` | Test additions or modifications | None | — |
| `chore:` | Maintenance, dependencies, tooling | None | — |
| `perf:` | Performance improvements | Patch bump | Changed |
| `style:` | Code style changes (formatting, whitespace) | None | — |

**Why distinguish `refactor` from `fix`?** A refactor shouldn't change behavior—if tests fail after a refactor, that's a bug in the refactor. A fix intentionally changes behavior—tests should change with it. The prefix sets reviewer expectations.

### Examples

```bash
# New feature—triggers minor version bump, appears in "Added"
feat(worker): add retry logic with exponential backoff

# Bug fix—triggers patch bump, appears in "Fixed"
fix(launcher): handle missing Docker daemon gracefully

# Documentation—no version impact, but documents improvement
docs(wiki): add troubleshooting page

# Multiple scopes (use sparingly)
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

**Why credit Claude?** Transparency. Reviewers should know which code had AI assistance. It's also useful for post-mortems—if AI-assisted code has different defect rates, we want to track that.

---

## Architecture Guidelines

### Module Structure Philosophy

Every new Python module in `zerg/` must:

1. **Have a production caller** — At least one other production file must import it
2. **Have unit tests** — In `tests/unit/test_<module>.py`
3. **Have integration tests** — Prove the module works with its callers

**Why require production callers?** Orphaned modules are dead code waiting to rot. If nothing imports your module, your module serves no purpose. This rule prevents "I might need this later" code that never gets used.

**Why require integration tests beyond unit tests?** Unit tests prove the module works in isolation. Integration tests prove it works when actually called. A module can have 100% unit test coverage and still fail in production because callers use it differently than tests expected.

Standalone entry points (`__main__.py`, files with `if __name__`) are exempt from the caller requirement.

### Consumer Matrix

During design phase, the `consumers` field in task specifications tracks who calls what. This prevents orphaned modules that pass unit tests but are never used.

**Why track consumers at design time?** It forces you to think about integration before writing code. If you can't name a consumer, you might be building something unnecessary.

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

**Why Task ecosystem integration?** Tasks are the coordination layer for parallel workers. Without Task calls, workers can't track progress, orchestrators can't monitor status, and resume can't work.

**Why split large commands?** Token budget is finite. Core instructions go to every worker; details are referenced on demand. Splitting reduces per-worker overhead.

**Why bracketed prefixes?** They enable filtering. `TaskList` can find all `[L1]` tasks to check level completion. Without prefixes, we'd need complex parsing.

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

**Why these details?** They let maintainers reproduce your bug. "It doesn't work" isn't actionable. "On Python 3.12.1, macOS 14.2, running `/zerg:rush` with 5 workers fails with error X after Y minutes" is.

### Feature Requests

Describe the **problem** you're solving, not just the solution. This helps maintainers evaluate alternatives.

**Why focus on problems?** "Add flag X" assumes flag X is the right solution. "Workers sometimes timeout and I have to restart manually" opens discussion—maybe the solution is better retry logic, not a flag.

### Security Vulnerabilities

Do **not** open public issues. See [Security](Security) for private reporting instructions.

**Why private reporting?** Public disclosure gives attackers a head start. Private reporting lets us fix vulnerabilities before they're exploited.

---

## Resources

- [Architecture](Architecture) — System design and module reference
- [Command-Reference](Command-Reference) — All 26 commands with usage examples
- [Context-Engineering](Context-Engineering) — Token optimization techniques
- [CLAUDE.md](https://github.com/rocklambros/zerg/blob/main/CLAUDE.md) — Anti-drift rules and Task ecosystem details

---

## License

By contributing to ZERG, you agree that your contributions will be licensed under the [MIT License](https://github.com/rocklambros/zerg/blob/main/LICENSE).

**Why MIT?** It's simple, permissive, and widely understood. Contributors know their code can be used commercially. Users know they can use ZERG without legal complexity.
