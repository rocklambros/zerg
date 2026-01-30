# Requirements: bug-fix-sweep

**Status: APPROVED**

## Summary

Systematic fix of 11 outstanding bugs across the ZERG codebase, ranging from HIGH (NotImplementedError stubs, bare except clauses) to LOW (stale state files, hardcoded paths).

## Bugs

1. **NotImplementedError stubs** — `analyze.py:BaseChecker.check()`, `refactor.py:BaseTransform.analyze()/apply()` raise NotImplementedError as abstract base classes but aren't using ABC
2. **Bare `except Exception: pass`** — 24 locations silently swallow errors without logging
3. **Missing .gitignore entries** — `.coverage`, `htmlcov/`, `.pytest_cache/` not ignored
4. **Stale STATE.md** — Contains error from a bug that was already fixed
5. **Flaky test** — `test_rebalance_multiple_failed_tasks` has isolation issues
6. **5 hanging tests** — `claim_next_task` / `start` tests in `tests/unit/test_worker_protocol.py` don't mock `time.sleep`
7. **E2E test timeout** — `test_launcher_spawn_creates_container` needs longer timeout
8. **E2E test borderline** — `test_recoverable_error_allows_resume` borderline 30s
9. **Hardcoded container paths** — `/home/worker`, `/tmp/.zerg-alive` in launcher.py
10. **Silent lock release** — `state.py` file lock unlock in bare except
11. **Debug print statements** — `status.py` uses `console.print` where `logger` would be appropriate
