# Requirements: Lockfile Hardening

## Metadata
- **Feature**: lockfile-hardening
- **Status**: APPROVED
- **Created**: 2026-02-11
- **Priority**: Medium — code quality findings from review, no production incidents
- **Source**: `/zerg:review` full two-stage review of multi-epic-isolation feature

---

## 1. Problem Statement

Code review of `zerg/commands/_utils.py` found 5 issues in lockfile and detect_feature code. All are hardening improvements — the code works but has edge-case vulnerabilities.

---

## 2. Findings to Fix

### F1: TOCTOU race in `acquire_feature_lock()` (lines 64-78)
- Gap between `lock_path.exists()` check and `lock_path.write_text()` create
- Two concurrent processes can both believe they acquired the lock
- Fix: use `os.open()` with `O_CREAT | O_EXCL` for atomic creation

### F2: Missing ownership check in `release_feature_lock()` (lines 81-90)
- Any process can delete another process's lock
- Fix: verify PID matches `os.getpid()` before `unlink()`

### F3: Unprotected `.read_text()` calls (lines 36, 66, 109)
- `PermissionError`, `UnicodeDecodeError`, `OSError` crash the caller
- Fix: wrap in `try/except (OSError, UnicodeDecodeError)` with fallback

### F4: Path traversal in feature name (lines 64, 88, 106)
- Feature name used directly in `Path(gsd_dir) / "specs" / feature / ".lock"`
- A name like `../../etc` could escape the intended directory
- Fix: validate feature name rejects `/`, `\`, `..`

### F5: Integer bounds on PID/timestamp parsing (lines 68, 111, 115)
- Extremely large values in lock content could cause issues
- Fix: validate PID range (1 to 4194304) and timestamp not in future

---

## 3. Functional Requirements

### FR1: Atomic lock creation
- `acquire_feature_lock()` uses `os.open(O_CREAT | O_EXCL)` for atomic file creation
- Falls back to `False` on `FileExistsError` (another process won the race)
- Stale lock cleanup remains before the atomic create attempt

### FR2: Ownership-validated release
- `release_feature_lock()` reads lock content and verifies PID == `os.getpid()`
- Skips deletion (with no error) if PID doesn't match
- Corrupt/unreadable locks can still be deleted (fallback)

### FR3: Resilient file reads
- `detect_feature()` wraps `.read_text()` at line 36 in try/except
- `acquire_feature_lock()` wraps `.read_text()` at line 66 in try/except
- `check_feature_lock()` wraps `.read_text()` at line 109 in try/except
- All fall through gracefully on error (return None or continue)

### FR4: Feature name validation
- New helper `_validate_feature_name(feature)` rejects names containing `/`, `\`, or `..`
- Called at entry of `acquire_feature_lock()`, `release_feature_lock()`, `check_feature_lock()`
- Raises `ValueError` on invalid input

### FR5: Bounds-checked parsing
- PID validated: 1 <= pid <= 4194304 (Linux kernel max PID)
- Timestamp validated: 0 < ts <= time.time() + 86400 (no future beyond 1 day)
- Out-of-bounds values treated as corrupt lock

---

## 4. Non-Functional Requirements

### NFR1: Backward compatibility
- No signature changes to public functions
- Lock file format unchanged (`pid:timestamp`)
- Existing valid locks continue to work

### NFR2: Test coverage
- Update existing tests in `test_lockfile.py` for new behaviors
- Add tests: atomic race simulation, ownership validation, path traversal rejection, bounds checking, read error resilience
- Update `test_commands_utils.py` for detect_feature read error handling

---

## 5. Scope

### In Scope
- `zerg/commands/_utils.py` — all 5 fixes
- `tests/unit/test_lockfile.py` — new tests for F1, F2, F4, F5
- `tests/unit/test_commands_utils.py` — new test for F3

### Out of Scope
- Command markdown files (no changes needed)
- Other Python modules (no callers of lockfile functions)
- CHANGELOG update (will add if requested)

---

## 6. Acceptance Criteria

- [ ] `acquire_feature_lock()` uses `O_CREAT | O_EXCL` for atomic creation
- [ ] `release_feature_lock()` only deletes lock owned by current PID
- [ ] `.read_text()` calls in detect_feature and lockfile functions don't crash on OSError/UnicodeDecodeError
- [ ] Feature names with `/`, `\`, `..` raise ValueError in all 3 lockfile functions
- [ ] PID > 4194304 or negative treated as corrupt
- [ ] All existing tests pass (no regressions)
- [ ] New tests cover each finding

---

## 7. Files to Modify

| File | Change |
|------|--------|
| `zerg/commands/_utils.py` | All 5 fixes |
| `tests/unit/test_lockfile.py` | New tests for F1, F2, F4, F5 |
| `tests/unit/test_commands_utils.py` | New test for F3 |

---

## 8. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Atomic create breaks on non-POSIX FS | Low | Low | `O_CREAT\|O_EXCL` is POSIX standard, works on macOS/Linux |
| Ownership check prevents cleanup of dead-PID locks | Low | Low | Stale expiry (2hr) handles dead processes |
| Feature name validation too strict | Low | Low | Only rejects path traversal chars, not alphanum/hyphens |

---

## 9. Implementation Priority

Single task — all 5 fixes in one commit since they're all in the same file.
