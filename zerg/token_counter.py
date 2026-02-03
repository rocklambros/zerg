"""Token counting with caching and multiple counting modes."""

import hashlib
import json
import logging
import os
import tempfile
import time
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

    def _cache_lookup(self, text_hash: str) -> TokenResult | None:
        """Look up a cached token count by hash."""
        try:
            if not self._cache_path.exists():
                return None

            with open(self._cache_path) as f:
                cache = json.loads(f.read())

            entry = cache.get(text_hash)
            if entry is None:
                return None

            age = time.time() - entry.get("timestamp", 0)
            if age > self._config.cache_ttl_seconds:
                return None

            return TokenResult(
                count=entry["count"],
                mode=entry["mode"],
                source="cache",
            )
        except Exception:
            logger.debug("Cache lookup failed for hash %s", text_hash[:12])
            return None

    def _cache_store(self, text_hash: str, result: TokenResult) -> None:
        """Store a token count result in the cache file."""
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)

            cache: dict = {}
            if self._cache_path.exists():
                try:
                    with open(self._cache_path) as f:
                        cache = json.loads(f.read())
                except Exception:
                    cache = {}

            cache[text_hash] = {
                "count": result.count,
                "mode": result.mode,
                "timestamp": time.time(),
            }

            data = json.dumps(cache)
            dir_path = self._cache_path.parent

            fd, tmp_path = tempfile.mkstemp(dir=str(dir_path), suffix=".tmp")
            try:
                with os.fdopen(fd, "w") as f:
                    f.write(data)
                os.replace(tmp_path, str(self._cache_path))
            except Exception:
                # Clean up temp file on failure
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        except Exception:
            logger.debug("Cache store failed for hash %s", text_hash[:12])
