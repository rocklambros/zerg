"""Unit tests for zerg.token_counter module."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

from zerg.config import TokenMetricsConfig
from zerg.token_counter import TokenCounter, TokenResult


def _make_counter(tmp_path, **overrides):
    """Create a TokenCounter with tmp_path-based cache and given config overrides."""
    cfg = TokenMetricsConfig(**overrides)
    counter = TokenCounter(config=cfg)
    counter._cache_path = tmp_path / "token-cache.json"
    return counter


class TestHeuristicMode:
    def test_heuristic_returns_estimated_and_reasonable_count(self, tmp_path) -> None:
        counter = _make_counter(tmp_path, api_counting=False, fallback_chars_per_token=4.0)
        result = counter.count("a" * 100)
        assert result.mode == "estimated"
        assert result.source == "heuristic"
        assert result.count == 25

    def test_heuristic_minimum_is_one(self, tmp_path) -> None:
        counter = _make_counter(tmp_path, api_counting=False, fallback_chars_per_token=10.0)
        result = counter.count("hi")
        assert result.count >= 1


class TestApiMode:
    def test_api_mode_with_mock_anthropic(self, tmp_path) -> None:
        counter = _make_counter(tmp_path, api_counting=True, cache_enabled=False)
        mock_result = MagicMock()
        mock_result.input_tokens = 42
        mock_client = MagicMock()
        mock_client.messages.count_tokens.return_value = mock_result
        mock_anthropic = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
            result = counter.count("test text")
        assert result.count == 42
        assert result.mode == "exact"
        assert result.source == "api"

    def test_api_fallback_on_error(self, tmp_path) -> None:
        """Both missing anthropic and API exceptions fall back to heuristic."""
        counter = _make_counter(tmp_path, api_counting=True, cache_enabled=False)
        mock_anthropic = MagicMock()
        mock_anthropic.Anthropic.return_value.messages.count_tokens.side_effect = RuntimeError("boom")
        with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
            result = counter.count("fallback text")
        assert result.mode == "estimated"
        assert result.source == "heuristic"


class TestCaching:
    def test_cache_hit(self, tmp_path) -> None:
        counter = _make_counter(tmp_path, api_counting=False, cache_enabled=True)
        first = counter.count("repeated text")
        second = counter.count("repeated text")
        assert first.source == "heuristic"
        assert second.source == "cache"
        assert first.count == second.count

    def test_cache_expiry(self, tmp_path) -> None:
        counter = _make_counter(tmp_path, api_counting=False, cache_enabled=True, cache_ttl_seconds=60)
        counter.count("expiring text")
        with counter._cache_lock:
            for key in counter._cache:
                counter._cache[key]["timestamp"] = time.time() - 120
        result = counter.count("expiring text")
        assert result.source == "heuristic"

    def test_cache_disabled(self, tmp_path) -> None:
        counter = _make_counter(tmp_path, api_counting=False, cache_enabled=False)
        counter.count("no cache")
        counter.count("no cache")
        assert not counter._cache_path.exists()


class TestEmptyText:
    def test_empty_text_returns_token_result(self, tmp_path) -> None:
        counter = _make_counter(tmp_path, api_counting=False, cache_enabled=False)
        result = counter.count("")
        assert result.count >= 0
        assert isinstance(result, TokenResult)
