# Feature: performance-core

**Status: APPROVED**

**Created**: 2026-02-05
**Issues**: #133, #134, #144
**Priority**: P1 (HIGH)

---

## Problem Statement

ZERG orchestration suffers from significant I/O overhead due to:
1. **Config loading**: `ZergConfig.load()` reads disk on every call (14+ callsites)
2. **Log aggregation**: `LogAggregator._read_all_entries()` reads ALL log files per query
3. **Directory traversal**: Multiple `rglob()` calls traverse directory tree repeatedly
4. **Repository mapping**: `build_map()` parses AST on every call without caching

**Estimated current overhead**:
| Component | Current | Target |
|-----------|---------|--------|
| Config loading | 250ms+ per run | <5ms (cached) |
| Log aggregation | 500ms+ per status | <10ms (cached) |
| Directory traversal | 600ms-3s init | 100-500ms |
| Repo map building | 2-5s per call | <100ms (cached) |

---

## Functional Requirements

### FR-1: ZergConfig Singleton with mtime Invalidation

**Affected file**: `zerg/config.py`

Add caching to `ZergConfig.load()`:
- Use class-level `_cached_instance` and `_cache_mtime` variables
- On load, check file mtime against cached mtime
- Return cached instance if mtime unchanged
- Support `force_reload=True` parameter to bypass cache
- Thread-safe using `threading.Lock`
- Log cache hits/misses at DEBUG level

```python
# Signature change
@classmethod
def load(cls, config_path: str | Path | None = None, force_reload: bool = False) -> "ZergConfig":
```

### FR-2: LogAggregator Per-File Caching

**Affected file**: `zerg/log_aggregator.py`

Add per-file caching to `_read_all_entries()`:
- Track mtime per JSONL file
- Cache parsed entries per file
- Invalidate only files whose mtime changed
- Re-read only changed files on subsequent queries
- Thread-safe with lock protection
- Bounded cache size with LRU eviction (max 100 files)
- Log cache statistics at DEBUG level

### FR-3: Single-Pass Directory Traversal

**Affected files**:
- `zerg/security_rules.py` (`detect_project_stack()`)
- `zerg/repo_map.py` (`_collect_files()`)

Replace multiple `rglob()` calls with single traversal:
- Use `rglob("*")` once, classify files in memory
- Build extension → files mapping in single pass
- Eliminate redundant directory tree walks
- Pattern: collect-then-filter

### FR-4: TokenCounter In-Memory Cache

**Affected file**: `zerg/token_counter.py`

Replace file-based cache with in-memory:
- Load JSON file once on init
- Maintain in-memory dict for lookups
- Persist to file periodically (on store) with atomic writes
- O(1) lookup instead of file read per call
- LRU eviction to bound memory (max 10000 entries)
- Thread-safe with lock protection

### FR-5: RepoMap TTL-Based Caching

**Affected file**: `zerg/repo_map.py`

Add map-level caching to `build_map()`:
- Cache complete `SymbolGraph` result
- TTL of 30 seconds
- Invalidate on explicit `invalidate_cache()` call
- Return cached result if within TTL
- Thread-safe

---

## Non-Functional Requirements

### NFR-1: Thread Safety

All caches must be thread-safe for concurrent access:
- Use `threading.Lock` or `threading.RLock`
- Protect both read and write operations
- No deadlock potential

### NFR-2: Cache Size Limits

Prevent unbounded memory growth:
- LogAggregator: max 100 cached files (LRU eviction)
- TokenCounter: max 10000 cached entries (LRU eviction)
- RepoMap: single cached SymbolGraph (no eviction needed)
- ZergConfig: single cached instance (no eviction needed)

### NFR-3: Observability

Log cache behavior at DEBUG level:
- Cache hits: `"Cache hit for {key}"`
- Cache misses: `"Cache miss for {key}, loading from {source}"`
- Cache invalidations: `"Invalidating cache for {key}, reason: {reason}"`

### NFR-4: Backward Compatibility

All changes must be backward compatible:
- Existing function signatures preserved (new optional params only)
- No changes to public API behavior
- Existing tests must pass

---

## Acceptance Criteria

### From Issue #133
- [ ] ZergConfig uses singleton with mtime-based invalidation
- [ ] LogAggregator caches entries with file modification tracking
- [ ] TokenCounter maintains in-memory cache

### From Issue #134
- [ ] `detect_project_stack()` uses single `rglob("*")` traversal
- [ ] `_collect_files()` uses single traversal with suffix check
- [ ] No module performs multiple `rglob()` calls for different patterns

### From Issue #144
- [ ] Map cached with 30s TTL
- [ ] Cache invalidated on `invalidate_cache()` call
- [ ] `build_map()` returns in <100ms when cached

### Additional (from discovery)
- [ ] All caches are thread-safe
- [ ] LRU eviction for bounded memory usage
- [ ] Benchmark tests verify performance improvements
- [ ] DEBUG logging for cache hits/misses

---

## Testing Strategy

### Unit Tests
- `test_zergconfig_caching.py`: Verify singleton, mtime invalidation, force_reload
- `test_logaggregator_caching.py`: Verify per-file cache, LRU eviction
- `test_token_counter_memory.py`: Verify in-memory cache, persistence
- `test_repo_map_caching.py`: Verify TTL, invalidation
- `test_single_traversal.py`: Verify single rglob pattern

### Benchmark Tests
- `benchmark_config_load.py`: Measure before/after for ZergConfig
- `benchmark_log_query.py`: Measure before/after for LogAggregator
- `benchmark_directory_scan.py`: Measure before/after for rglob optimization
- `benchmark_repo_map.py`: Measure before/after for build_map

### Thread Safety Tests
- Concurrent access tests for each cache
- No race conditions under parallel load

---

## Out of Scope

- Watchdog-based file system events (future enhancement)
- Redis/external cache backends
- Configuration-driven TTL values (hardcoded 30s for now)
- Cache warming on startup

---

## Dependencies

- Python stdlib only: `threading`, `collections.OrderedDict` (for LRU), `time`, `json`
- No new external dependencies

---

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Stale config not reloaded | Low | Medium | mtime check on every access |
| Memory growth in large projects | Low | Medium | LRU eviction with size limits |
| Thread contention | Low | Low | Fine-grained locking |

---

## Notes

- All caches should be documented in CLAUDE.md under a "Performance" section
- Consider exposing cache stats via `/zerg:status` in future iteration
