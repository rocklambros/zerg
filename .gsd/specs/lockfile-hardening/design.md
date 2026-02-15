# Technical Design: lockfile-hardening

## Metadata
- **Feature**: lockfile-hardening
- **Status**: DRAFT
- **Created**: 2026-02-11
- **Author**: Factory Design Mode

---

## 1. Overview

### 1.1 Summary
Harden the advisory lockfile functions in `zerg/commands/_utils.py` against five edge-case vulnerabilities found during code review: TOCTOU race in lock creation, missing ownership check on release, unprotected `.read_text()` calls, path traversal via feature name, and unbounded PID/timestamp parsing. All fixes are localized to one source file plus two test files.

### 1.2 Goals
- Eliminate TOCTOU race in `acquire_feature_lock()` via atomic file creation
- Prevent cross-process lock deletion via PID ownership check
- Make all `.read_text()` calls resilient to OS/encoding errors
- Block path traversal through feature name validation
- Bounds-check PID and timestamp values from lock content

### 1.3 Non-Goals
- Changing lock file format (must remain `pid:timestamp`)
- Changing public function signatures
- Modifying any files outside `_utils.py` and its tests
- Adding new CLI commands or flags

---

## 2. Architecture

### 2.1 High-Level Design

```
┌──────────────────────────────────────────┐
│          zerg/commands/_utils.py          │
│                                          │
│  _validate_feature_name(feature)  ← NEW  │
│  _safe_read_text(path)            ← NEW  │
│  _parse_lock_content(content)     ← NEW  │
│                                          │
│  detect_feature()                 ← FIX  │
│  acquire_feature_lock()           ← FIX  │
│  release_feature_lock()           ← FIX  │
│  check_feature_lock()             ← FIX  │
└──────────────────────────────────────────┘
```

Three new private helpers + fixes to four existing functions.

### 2.2 Component Breakdown

| Component | Responsibility | Location |
|-----------|---------------|----------|
| `_validate_feature_name()` | Reject `/`, `\`, `..` in feature names | `_utils.py` (new) |
| `_safe_read_text()` | Wrap `Path.read_text()` with OSError/UnicodeDecodeError handling | `_utils.py` (new) |
| `_parse_lock_content()` | Parse `pid:timestamp`, validate bounds, return tuple or None | `_utils.py` (new) |
| `acquire_feature_lock()` | Atomic `O_CREAT|O_EXCL` creation, use helpers | `_utils.py` (modify) |
| `release_feature_lock()` | PID ownership check before unlink | `_utils.py` (modify) |
| `check_feature_lock()` | Use `_safe_read_text` + `_parse_lock_content` | `_utils.py` (modify) |
| `detect_feature()` | Use `_safe_read_text` for `.current-feature` read | `_utils.py` (modify) |

### 2.3 Data Flow

1. Caller invokes `acquire_feature_lock("my-feat")`
2. `_validate_feature_name("my-feat")` → passes (no `/`, `\`, `..`)
3. Check existing lock via `_safe_read_text(lock_path)` → content or None
4. If content, `_parse_lock_content(content)` → `(pid, ts)` or None
5. If stale or corrupt → remove old lock
6. Atomic create via `os.open(O_CREAT|O_EXCL|O_WRONLY)` → fd or FileExistsError
7. Write `pid:timestamp` to fd, close → return True

---

## 3. Detailed Design

### 3.1 `_validate_feature_name(feature: str) -> None`

```python
import re

_FEATURE_NAME_RE = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9._-]*$')

def _validate_feature_name(feature: str) -> None:
    """Raise ValueError if feature name contains path traversal characters."""
    if not feature or '..' in feature or '/' in feature or '\\' in feature:
        raise ValueError(f"Invalid feature name: {feature!r}")
    if not _FEATURE_NAME_RE.match(feature):
        raise ValueError(f"Invalid feature name: {feature!r}")
```

### 3.2 `_safe_read_text(path: Path) -> str | None`

```python
def _safe_read_text(path: Path) -> str | None:
    """Read text from path, returning None on any OS/encoding error."""
    try:
        return path.read_text().strip()
    except (OSError, UnicodeDecodeError):
        return None
```

### 3.3 `_parse_lock_content(content: str) -> tuple[int, float] | None`

```python
MAX_PID = 4_194_304  # Linux kernel max PID

def _parse_lock_content(content: str) -> tuple[int, float] | None:
    """Parse 'pid:timestamp' lock content with bounds checking."""
    try:
        pid_str, ts_str = content.split(":", 1)
        pid = int(pid_str)
        ts = float(ts_str)
    except (ValueError, TypeError):
        return None
    if pid < 1 or pid > MAX_PID:
        return None
    if ts <= 0 or ts > time.time() + 86400:
        return None
    return (pid, ts)
```

### 3.4 `acquire_feature_lock()` changes

- Add `_validate_feature_name(feature)` at entry
- Replace `lock_path.read_text()` with `_safe_read_text(lock_path)`
- Replace inline parsing with `_parse_lock_content(content)`
- Replace `lock_path.write_text()` with `os.open(path, O_CREAT|O_EXCL|O_WRONLY)` + `os.write()` + `os.close()`
- Catch `FileExistsError` → return False (lost race)

### 3.5 `release_feature_lock()` changes

- Add `_validate_feature_name(feature)` at entry
- Read lock content, parse PID, verify `pid == os.getpid()`
- Only unlink if owned or unreadable/corrupt (fallback for cleanup)

### 3.6 `check_feature_lock()` changes

- Add `_validate_feature_name(feature)` at entry
- Replace `lock_path.read_text()` with `_safe_read_text(lock_path)`
- Replace inline parsing with `_parse_lock_content(content)`

### 3.7 `detect_feature()` changes

- Replace `current_feature.read_text()` at line 36 with `_safe_read_text(current_feature)`

---

## 4. Key Decisions

### Decision: Atomic file creation with `os.open(O_CREAT|O_EXCL)`

**Context**: TOCTOU race between `lock_path.exists()` and `lock_path.write_text()`.

**Options Considered**:
1. `os.open(O_CREAT|O_EXCL)`: Single atomic syscall, POSIX standard
2. `fcntl.flock()`: Advisory file locking, doesn't survive reboots cleanly
3. `filelock` library: Adds external dependency

**Decision**: Option 1 — `os.open(O_CREAT|O_EXCL)`

**Rationale**: Zero dependencies, single atomic syscall, works on macOS and Linux. The lock is advisory and already time-bounded (2hr stale), so full file locking is unnecessary.

**Consequences**: Slightly more verbose than `write_text()`, but eliminates the race entirely.

### Decision: PID ownership check with fallback deletion

**Context**: `release_feature_lock()` should only delete locks owned by the current process, but corrupt/unreadable locks must still be cleanable.

**Options Considered**:
1. Strict ownership only — refuse to delete unowned locks
2. Ownership check with fallback — delete if unreadable/corrupt
3. No ownership check — status quo

**Decision**: Option 2 — ownership with fallback

**Rationale**: Strict-only would leave corrupt lock files permanently. Fallback allows cleanup of broken locks while preventing cross-process deletion of valid ones.

---

## 5. Implementation Plan

### 5.1 Phase Summary

| Phase | Tasks | Parallel | Est. Time |
|-------|-------|----------|-----------|
| Foundation (L1) | 1 | N/A | 20 min |
| Testing (L2) | 2 | Yes | 25 min |
| Quality (L3) | 1 | N/A | 10 min |

### 5.2 File Ownership

| File | Task ID | Operation |
|------|---------|-----------|
| `zerg/commands/_utils.py` | TASK-001 | modify |
| `tests/unit/test_lockfile.py` | TASK-002 | modify |
| `tests/unit/test_commands_utils.py` | TASK-003 | modify |
| `CHANGELOG.md` | TASK-004 | modify |

### 5.3 Dependency Graph

```
TASK-001 [L1: Harden _utils.py]
    ├──→ TASK-002 [L2: Lockfile tests]
    └──→ TASK-003 [L2: detect_feature tests]
              └──→ TASK-004 [L3: CHANGELOG update]
```

---

## 6. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| `O_CREAT\|O_EXCL` unsupported on exotic FS | Very Low | Low | POSIX standard, works on all CI targets |
| Ownership check blocks stale lock cleanup | Low | Low | Fallback: delete corrupt/unreadable locks |
| Feature name regex too strict | Low | Low | Allows alphanum, dots, hyphens, underscores |
| Existing tests break | Low | Medium | Signatures unchanged, only behavioral hardening |

---

## 7. Testing Strategy

### 7.1 Unit Tests — test_lockfile.py additions

| Test | Covers |
|------|--------|
| `test_atomic_acquire_race_simulation` | F1: Two processes can't both acquire |
| `test_acquire_rejects_path_traversal` | F4: `../etc` raises ValueError |
| `test_acquire_rejects_slash_in_name` | F4: `foo/bar` raises ValueError |
| `test_acquire_rejects_backslash_in_name` | F4: `foo\bar` raises ValueError |
| `test_release_only_deletes_owned_lock` | F2: Different PID lock survives |
| `test_release_deletes_own_lock` | F2: Same PID lock is deleted |
| `test_release_deletes_corrupt_lock` | F2: Fallback for unreadable |
| `test_release_rejects_path_traversal` | F4: ValueError on bad name |
| `test_check_rejects_path_traversal` | F4: ValueError on bad name |
| `test_acquire_handles_read_error` | F3: OSError on read_text |
| `test_check_handles_read_error` | F3: OSError on read_text |
| `test_pid_out_of_bounds_treated_as_corrupt` | F5: PID > 4194304 |
| `test_negative_pid_treated_as_corrupt` | F5: PID < 1 |
| `test_future_timestamp_treated_as_corrupt` | F5: ts > now + 1 day |

### 7.2 Unit Tests — test_commands_utils.py additions

| Test | Covers |
|------|--------|
| `test_detect_feature_handles_read_error` | F3: OSError on .current-feature |
| `test_detect_feature_handles_unicode_error` | F3: UnicodeDecodeError |

### 7.3 Verification Commands

```bash
# Per-task verification
python -m pytest tests/unit/test_lockfile.py -v        # TASK-002
python -m pytest tests/unit/test_commands_utils.py -v   # TASK-003

# Full regression
python -m pytest tests/unit/ -v
```

---

## 8. Parallel Execution Notes

### 8.1 Safe Parallelization
- Level 1: Single task (TASK-001) — source code changes
- Level 2: TASK-002 and TASK-003 can run in parallel (different test files)
- Level 3: TASK-004 runs after tests pass

### 8.2 Recommended Workers
- Minimum: 1 worker (sequential)
- Optimal: 2 workers (parallelize Level 2)
- Maximum: 2 workers (only 2 tasks at widest level)

### 8.3 Estimated Duration
- Single worker: ~55 min
- With 2 workers: ~45 min
- Speedup: ~1.2x

---

## 9. Approval

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Architecture | | | PENDING |
| Engineering | | | PENDING |
