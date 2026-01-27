# DC-012 Integration Tests - ZERG Task Backlog

**Feature**: Container Flow Integration Tests
**Status**: PENDING
**Created**: 2026-01-27
**Total Tasks**: 9 | **Levels**: 4 | **Max Parallelization**: 4

---

## Execution Summary

| Metric | Value |
|--------|-------|
| Total Tasks | 9 |
| Completed | 0 |
| Critical Path | DC12-001 → DC12-002 → DC12-007 → DC12-009 |
| Estimated Sessions | 1-2 |

---

## Level 0: Foundation (Sequential: 1 task)

| ID | Task | Files Owned | Deps | Status | Verification |
|----|------|-------------|------|--------|--------------|
| **DC12-001** ⭐ | Create test infrastructure & conftest additions | `tests/integration/conftest_container.py` | - | ⬜ Pending | `python -c "from tests.integration.conftest_container import *"` |

**DC12-001 Details:**
- Create shared fixtures for container testing
- Add `docker_available()` helper function
- Add `mock_docker_run()` fixture
- Add `multi_lang_project()` fixture (creates marker files)
- Add `devcontainer_output_dir()` fixture

---

## Level 1: Core Test Classes (Parallel: 4 tasks)

| ID | Task | Files Owned | Deps | Status | Verification |
|----|------|-------------|------|--------|--------------|
| **DC12-002** ⭐ | TestMultiLanguageDetection (2 tests) | `tests/integration/test_container_detection.py` | DC12-001 | ⬜ Pending | `pytest tests/integration/test_container_detection.py -v` |
| **DC12-003** | TestDynamicDevcontainer (3 tests) | `tests/integration/test_container_devcontainer.py` | DC12-001 | ⬜ Pending | `pytest tests/integration/test_container_devcontainer.py -v` |
| **DC12-004** | TestContainerLauncher (3 tests) | `tests/integration/test_container_launcher_checks.py` | DC12-001 | ⬜ Pending | `pytest tests/integration/test_container_launcher_checks.py -v` |
| **DC12-005** | TestOrchestratorModeSelection (2 tests) | `tests/integration/test_container_orchestrator.py` | DC12-001 | ⬜ Pending | `pytest tests/integration/test_container_orchestrator.py -v` |

**DC12-002 Details (TestMultiLanguageDetection):**
```python
def test_detect_python_and_node(tmp_path):
    # Create requirements.txt + package.json
    # Call detect_project_stack()
    # Assert "python" in stack.languages and "javascript" in stack.languages

def test_detect_go_and_rust(tmp_path):
    # Create go.mod + Cargo.toml
    # Call detect_project_stack()
    # Assert "go" in stack.languages and "rust" in stack.languages
```

**DC12-003 Details (TestDynamicDevcontainer):**
```python
def test_multi_language_features():
    # get_features_for_languages({"python", "javascript"})
    # Assert python and node features in result

def test_custom_install_for_r():
    # get_post_create_commands({"r"})
    # Assert R installation command in result

def test_write_devcontainer_file(tmp_path):
    # generator.write_to_file(tmp_path)
    # Assert devcontainer.json exists and is valid JSON
```

**DC12-004 Details (TestContainerLauncher):**
```python
def test_docker_available_check():
    # ContainerLauncher.docker_available()
    # Assert returns bool without error

def test_image_exists_check():
    # launcher.image_exists("nonexistent-image")
    # Assert returns False

@patch("subprocess.run")
def test_spawn_requires_image(mock_run, tmp_path):
    # Mock docker image check to return "not found"
    # Attempt spawn
    # Assert graceful failure
```

**DC12-005 Details (TestOrchestratorModeSelection):**
```python
def test_auto_detect_without_devcontainer(tmp_path):
    # Create repo without .devcontainer/
    # Create Orchestrator with launcher_mode="auto"
    # Assert uses SubprocessLauncher

def test_container_mode_available_check(tmp_path):
    # Create Orchestrator
    # Call container_mode_available()
    # Assert returns (bool, str)
```

---

## Level 2: CLI & Command Tests (Parallel: 2 tasks)

| ID | Task | Files Owned | Deps | Status | Verification |
|----|------|-------------|------|--------|--------------|
| **DC12-006** | TestInitCommand (1 test) | `tests/integration/test_container_init_cmd.py` | DC12-003 | ⬜ Pending | `pytest tests/integration/test_container_init_cmd.py -v` |
| **DC12-007** ⭐ | TestRushCommand (1 test) | `tests/integration/test_container_rush_cmd.py` | DC12-005 | ⬜ Pending | `pytest tests/integration/test_container_rush_cmd.py -v` |

**DC12-006 Details (TestInitCommand):**
```python
def test_init_creates_multi_lang_devcontainer(tmp_path):
    # Create multi-lang project (requirements.txt + package.json)
    # Run: runner.invoke(init, ["--detect"])
    # Assert .devcontainer/devcontainer.json created
    # Assert features contain python and node
```

**DC12-007 Details (TestRushCommand):**
```python
def test_rush_help_shows_mode_option():
    # runner.invoke(rush, ["--help"])
    # Assert "--mode" or "-m" in output
    # Assert "subprocess", "container", "auto" in output
```

---

## Level 3: End-to-End & Finalization (Sequential: 2 tasks)

| ID | Task | Files Owned | Deps | Status | Verification |
|----|------|-------------|------|--------|--------------|
| **DC12-008** ⭐ | TestEndToEndFlow (1 test) | `tests/integration/test_container_e2e.py` | DC12-006, DC12-007 | ⬜ Pending | `pytest tests/integration/test_container_e2e.py -v` |
| **DC12-009** | Update backlog & verify all tests | `.gsd/tasks/dynamic-devcontainer/BACKLOG.md` | DC12-008 | ⬜ Pending | `pytest tests/integration/test_container_*.py -v` (all pass) |

**DC12-008 Details (TestEndToEndFlow):**
```python
def test_full_init_to_dry_run(tmp_path):
    # 1. Create multi-lang project
    # 2. Run init --detect
    # 3. Verify devcontainer.json created
    # 4. Create minimal task-graph.json
    # 5. Run rush --mode auto --dry-run
    # 6. Assert execution plan shows mode selection
```

**DC12-009 Details (Update Backlog):**
- Mark DC-012 as COMPLETE in `.gsd/tasks/dynamic-devcontainer/BACKLOG.md`
- Update progress tracker to 12/12 (100%)
- Run full test suite to verify

---

## File Ownership Matrix

| File | Owner Task | Action |
|------|-----------|--------|
| `tests/integration/conftest_container.py` | DC12-001 | Create |
| `tests/integration/test_container_detection.py` | DC12-002 | Create |
| `tests/integration/test_container_devcontainer.py` | DC12-003 | Create |
| `tests/integration/test_container_launcher_checks.py` | DC12-004 | Create |
| `tests/integration/test_container_orchestrator.py` | DC12-005 | Create |
| `tests/integration/test_container_init_cmd.py` | DC12-006 | Create |
| `tests/integration/test_container_rush_cmd.py` | DC12-007 | Create |
| `tests/integration/test_container_e2e.py` | DC12-008 | Create |
| `.gsd/tasks/dynamic-devcontainer/BACKLOG.md` | DC12-009 | Modify |

---

## Critical Path ⭐

```
DC12-001 (Foundation)
    ↓
DC12-002 ─┬─ DC12-003 ─┬─ DC12-004 ─┬─ DC12-005  (Level 1: Parallel)
          │            │            │
          ↓            ↓            ↓
      DC12-006     DC12-007                       (Level 2: Parallel)
          │            │
          └─────┬──────┘
                ↓
            DC12-008 (E2E)
                ↓
            DC12-009 (Finalize)
```

**Critical path time**: DC12-001 → DC12-002 → DC12-007 → DC12-008 → DC12-009

---

## Test Coverage Targets

| Component | Tests | Coverage Target |
|-----------|-------|-----------------|
| `detect_project_stack()` | 2 | Multi-lang detection |
| `DynamicDevcontainerGenerator` | 3 | Feature generation, file writing |
| `ContainerLauncher` | 3 | Availability checks, graceful failure |
| `Orchestrator` mode selection | 2 | Auto-detect, availability check |
| `init` command | 1 | Multi-lang devcontainer creation |
| `rush` command | 1 | Mode flag in help |
| End-to-end | 1 | Full flow verification |
| **Total** | **13** | |

---

## Execution Commands

```bash
# Initialize ZERG for this feature
zerg plan dc-012-tests

# Run with parallelization
zerg rush --workers 4 --mode subprocess

# Monitor progress
zerg status

# Run all container tests after completion
pytest tests/integration/test_container_*.py -v --tb=short
```

---

## Progress Tracker

```
Last Updated: 2026-01-27

Level 0: ⬜ (0/1)
Level 1: ⬜⬜⬜⬜ (0/4)
Level 2: ⬜⬜ (0/2)
Level 3: ⬜⬜ (0/2)

Overall: 0/9 (0%)
```

---

## Notes

- All Docker operations mocked via `@patch("subprocess.run")`
- Tests skip gracefully if Docker unavailable
- File ownership ensures no merge conflicts during parallel execution
- Each test file is self-contained with its own imports
