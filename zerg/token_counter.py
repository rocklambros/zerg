"""Token counting with caching and multiple counting modes."""

import hashlib
import json
import logging
import os
import tempfile
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

from zerg.config import TokenMetricsConfig, ZergConfig
from zerg.constants import STATE_DIR

logger = logging.getLogger(__name__)


@dataclass
class TokenResult:
    count: int
    mode: str  # 'exact' or 'estimated'
    source: str  # 'api', 'heuristic', or 'cache'


class TokenCounter:
    """Count tokens with caching and heuristic/API modes."""

    MAX_CACHE_ENTRIES = 10000  # LRU limit

    _warned_no_anthropic: bool = False

    def __init__(self, config: TokenMetricsConfig | None = None) -> None:
        if config is not None:
            self._config = config
        else:
            try:
                zerg_config = ZergConfig.load()
                self._config = zerg_config.token_metrics
            except Exception:
                self._config = TokenMetricsConfig()

        self._cache_path = Path(STATE_DIR) / "token-cache.json"
        self._cache: OrderedDict[str, dict] = OrderedDict()
        self._cache_lock = threading.Lock()
        self._cache_dirty = False

        # Load existing cache file into memory
        self._load_cache_from_file()

    def count(self, text: str) -> TokenResult:
        """Count tokens in text. Never raises exceptions."""
        try:
            text_hash = hashlib.sha256(text.encode()).hexdigest()

            # Check cache first
            if self._config.cache_enabled:
                cached = self._cache_lookup(text_hash)
                if cached is not None:
                    return cached

            # Count tokens
            if self._config.api_counting:
                result = self._try_api_count(text)
            else:
                result = TokenResult(
                    count=self._count_heuristic(text),
                    mode="estimated",
                    source="heuristic",
                )

            # Store in cache
            if self._config.cache_enabled:
                self._cache_store(text_hash, result)

            return result
        except Exception:
            logger.warning("Token counting failed, using heuristic fallback")
            return TokenResult(
                count=max(1, round(len(text) / self._config.fallback_chars_per_token)),
                mode="estimated",
                source="heuristic",
            )

    def _try_api_count(self, text: str) -> TokenResult:
        """Attempt API-based counting, fall back to heuristic."""
        try:
            return self._count_api(text)
        except Exception:
            return TokenResult(
                count=self._count_heuristic(text),
                mode="estimated",
                source="heuristic",
            )

    def _count_api(self, text: str) -> TokenResult:
        """Count tokens via Anthropic API. Lazy imports anthropic."""
        try:
            import anthropic  # noqa: F811
        except ImportError:
            if not TokenCounter._warned_no_anthropic:
                logger.warning("anthropic package not installed, falling back to heuristic")
                TokenCounter._warned_no_anthropic = True
            raise

        client = anthropic.Anthropic()
        result = client.messages.count_tokens(
            model="claude-sonnet-4-20250514",
            messages=[{"role": "user", "content": text}],
        )
        return TokenResult(
            count=result.input_tokens,
            mode="exact",
            source="api",
        )

    def _count_heuristic(self, text: str) -> int:
        """Estimate token count from character length."""
        return max(1, round(len(text) / self._config.fallback_chars_per_token))

    def _load_cache_from_file(self) -> None:
        """Load cache from disk into memory on init."""
        try:
            if self._cache_path.exists():
                with open(self._cache_path) as f:
                    data = json.loads(f.read())
                    # Convert to OrderedDict for LRU
                    count = 0
                    for k, v in data.items():
                        self._cache[k] = v
                        count += 1
                        # Evict if over limit during load
                        if count >= self.MAX_CACHE_ENTRIES:
                            break
                logger.debug("Loaded %d entries from token cache file", count)
        except Exception:
            logger.debug("Failed to load token cache from file")

    def _cache_lookup(self, text_hash: str) -> TokenResult | None:
        """O(1) in-memory lookup."""
        with self._cache_lock:
            entry = self._cache.get(text_hash)
            if entry is None:
                return None

            age = time.time() - entry.get("timestamp", 0)
            if age > self._config.cache_ttl_seconds:
                return None

            # Move to end for LRU
            self._cache.move_to_end(text_hash)
            logger.debug("Cache hit for token hash %s", text_hash[:12])

            return TokenResult(
                count=entry["count"],
                mode=entry["mode"],
                source="cache",
            )

    def _cache_store(self, text_hash: str, result: TokenResult) -> None:
        """Store in memory with LRU eviction, persist periodically."""
        with self._cache_lock:
            self._cache[text_hash] = {
                "count": result.count,
                "mode": result.mode,
                "timestamp": time.time(),
            }
            self._cache.move_to_end(text_hash)

            # LRU eviction
            while len(self._cache) > self.MAX_CACHE_ENTRIES:
                oldest_key, _ = self._cache.popitem(last=False)
                logger.debug("Evicting token cache entry %s", oldest_key[:12])

            self._cache_dirty = True
            logger.debug("Cache miss for token hash %s, stored", text_hash[:12])

        # Persist to file (atomic write)
        self._persist_cache()

    def _persist_cache(self) -> None:
        """Atomically persist cache to file."""
        with self._cache_lock:
            if not self._cache_dirty:
                return

            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            data = json.dumps(dict(self._cache))

        # Write outside lock to minimize contention
        try:
            fd, tmp_path = tempfile.mkstemp(dir=str(self._cache_path.parent), suffix=".tmp")
            try:
                with os.fdopen(fd, "w") as f:
                    f.write(data)
                os.replace(tmp_path, str(self._cache_path))
                with self._cache_lock:
                    self._cache_dirty = False
            except Exception:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        except Exception:
            logger.debug("Failed to persist token cache to file")
