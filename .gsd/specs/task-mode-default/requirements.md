# Requirements: Task Mode Default

## Metadata
- **Feature**: task-mode-default
- **Status**: APPROVED
- **Created**: 2026-02-05
- **Author**: /zerg:plan

---

## 1. Problem Statement

Currently, `/zerg:rush` uses auto-detection logic that selects container mode when a devcontainer is configured and built. The user wants:

1. **Task mode as the default** — always use Task tool subagents unless explicitly overridden
2. **Container mode only when explicit** — `--mode container` must be passed; devcontainer presence is irrelevant

This simplifies the mental model: "task mode unless I say otherwise."

---

## 2. Current State Analysis

### Documentation (`rush.details.md` lines 163-167)
```
Auto-detection logic:
1. If `--mode` is explicitly set → use that mode
2. If `.devcontainer/devcontainer.json` exists AND worker image is built → container mode
3. If running as Claude Code slash command → task mode
4. Otherwise → subprocess mode
```

### Python Code (`launcher_configurator.py` lines 118-155)
```python
def _auto_detect_launcher_type(self) -> LauncherType:
    devcontainer_path = self._repo_path / ".devcontainer" / "devcontainer.json"
    if not devcontainer_path.exists():
        return LauncherType.SUBPROCESS
    # Check if image exists...
    if result.returncode == 0:
        return LauncherType.CONTAINER
    return LauncherType.SUBPROCESS
```

### Config (`.zerg/config.yaml` line 13)
```yaml
launcher_type: subprocess
```

---

## 3. Functional Requirements

### FR-1: Task Mode as Default in Documentation

Update `rush.details.md` auto-detection logic to:
```
Auto-detection logic:
1. If `--mode` is explicitly set → use that mode
2. Otherwise → **task mode** (default)
```

Remove rules 2-4 from current logic.

### FR-2: Update rush.core.md / rush.md Help Text

Change:
```
--mode MODE  Execution mode: container|subprocess
```
To:
```
--mode MODE  Execution mode: task|container|subprocess (default: task)
```

### FR-3: Update Python Auto-Detection

Modify `launcher_configurator.py:_auto_detect_launcher_type()` to always return `LauncherType.SUBPROCESS`. Remove the devcontainer existence check and Docker image check entirely.

```python
def _auto_detect_launcher_type(self) -> LauncherType:
    """Auto-detect launcher type. Always returns SUBPROCESS.

    Container mode requires explicit --mode container flag.
    """
    return LauncherType.SUBPROCESS
```

### FR-3.1: Update Unit Tests

Update `tests/unit/test_launcher_configurator.py`:
- `test_auto_detect_no_devcontainer` — keep as-is (already expects SUBPROCESS)
- `test_auto_detect_with_devcontainer_and_image` — change to expect SUBPROCESS (not CONTAINER)
- `test_auto_detect_docker_failure_falls_back` — remove or simplify (no longer relevant)
- `test_create_launcher_auto_falls_back_on_network_failure` — remove (no longer relevant)

### FR-3.2: Update Integration Tests

Update `tests/integration/test_container_launcher.py`:
- Remove or simplify `TestAutoDetectLauncherMode` class (devcontainer presence no longer matters for auto-detect)

### FR-4: Update Config Default

Change `.zerg/config.yaml`:
```yaml
launcher_type: task  # or remove this line since task is now implicit default
```

---

## 4. Files to Modify

| File | Change |
|------|--------|
| `zerg/data/commands/rush.details.md` | Simplify auto-detection to "task mode unless explicit" |
| `zerg/data/commands/rush.core.md` | Update help text, remove container-first language |
| `zerg/data/commands/rush.md` | Update help text (same as core) |
| `zerg/launcher_configurator.py` | Remove devcontainer auto-detection, always return SUBPROCESS for auto mode |
| `.zerg/config.yaml` | Update default launcher_type comment |
| `tests/unit/test_launcher_configurator.py` | Update TestAutoDetect tests to expect SUBPROCESS always |
| `tests/integration/test_container_launcher.py` | Remove/update TestAutoDetectLauncherMode tests |

---

## 5. Acceptance Criteria

- [x] `rush.details.md` shows task mode as default
- [x] Help text shows `--mode MODE  Execution mode: task|container|subprocess (default: task)`
- [x] Running `/zerg:rush --workers 4` uses task mode without checking devcontainer
- [x] Running `/zerg:rush --mode container` uses container mode
- [x] Running `/zerg:rush --mode subprocess` uses subprocess mode

---

## 6. Non-Functional Requirements

- Python code changes required to `launcher_configurator.py`
- Test updates required to match new behavior
- Changes should preserve container mode functionality when explicitly requested
- Backward compatible: explicit `--mode` flags still work

---

## 7. Out of Scope

- Removing container mode entirely (it still works with explicit `--mode container`)
- Changes to worker.md or other commands
- Adding "task" as a LauncherType enum in Python (task mode is prompt-only)
