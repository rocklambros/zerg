"""Unit tests for zerg.token_counter module."""

from __future__ import annotations

import json
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
    """Tests for heuristic (non-API) token counting."""

    def test_heuristic_returns_estimated_mode(self, tmp_path) -> None:
        """Heuristic mode returns mode='estimated' and source='heuristic'."""
        counter = _make_counter(tmp_path, api_counting=False)
        result = counter.count("hello world")
        assert result.mode == "estimated"
        assert result.source == "heuristic"

    def test_heuristic_returns_reasonable_count(self, tmp_path) -> None:
        """Heuristic count is roughly len(text) / chars_per_token."""
        text = "a" * 100
        counter = _make_counter(tmp_path, api_counting=False, fallback_chars_per_token=4.0)
        result = counter.count(text)
        assert result.count == 25  # 100 / 4.0 = 25

    def test_heuristic_minimum_is_one(self, tmp_path) -> None:
        """Very short text still returns at least 1 token."""
        counter = _make_counter(tmp_path, api_counting=False, fallback_chars_per_token=10.0)
        result = counter.count("hi")
        assert result.count >= 1


class TestApiMode:
    """Tests for API-based token counting."""

    def test_api_mode_with_mock_anthropic(self, tmp_path) -> None:
        """Mock anthropic import and client; verify exact mode."""
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

    def test_api_mode_without_anthropic_falls_back(self, tmp_path) -> None:
        """When anthropic is not installed, falls back to heuristic."""
        counter = _make_counter(tmp_path, api_counting=True, cache_enabled=False)
        # Reset the class-level warning flag so the warning fires
        TokenCounter._warned_no_anthropic = False

        with patch.dict("sys.modules", {"anthropic": None}):
            result = counter.count("some text here")

        assert result.mode == "estimated"
        assert result.source == "heuristic"
        assert result.count >= 1

    def test_api_exception_falls_back_to_heuristic(self, tmp_path) -> None:
        """If the API call raises, falls back to heuristic."""
        counter = _make_counter(tmp_path, api_counting=True, cache_enabled=False)

        mock_anthropic = MagicMock()
        mock_anthropic.Anthropic.return_value.messages.count_tokens.side_effect = RuntimeError("boom")

        with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
            result = counter.count("fallback text")

        assert result.mode == "estimated"
        assert result.source == "heuristic"


class TestCaching:
    """Tests for the token count cache."""

    def test_cache_hit(self, tmp_path) -> None:
        """Second call for same text returns source='cache'."""
        counter = _make_counter(tmp_path, api_counting=False, cache_enabled=True)
        first = counter.count("repeated text")
        second = counter.count("repeated text")

        assert first.source == "heuristic"
        assert second.source == "cache"
        assert first.count == second.count

    def test_cache_miss_different_texts(self, tmp_path) -> None:
        """Different texts both compute fresh results."""
        counter = _make_counter(tmp_path, api_counting=False, cache_enabled=True)
        r1 = counter.count("text one")
        r2 = counter.count("text two")

        assert r1.source == "heuristic"
        assert r2.source == "heuristic"

    def test_cache_expiry(self, tmp_path) -> None:
        """Expired cache entries are not returned."""
        counter = _make_counter(
            tmp_path,
            api_counting=False,
            cache_enabled=True,
            cache_ttl_seconds=60,
        )
        counter.count("expiring text")

        # Manually set timestamp to the past in the cache file
        cache_data = json.loads(counter._cache_path.read_text())
        for key in cache_data:
            cache_data[key]["timestamp"] = time.time() - 120  # 2 minutes ago
        counter._cache_path.write_text(json.dumps(cache_data))

        result = counter.count("expiring text")
        assert result.source == "heuristic"  # cache expired, recomputed

    def test_cache_disabled(self, tmp_path) -> None:
        """With cache_enabled=False, no cache file is created."""
        counter = _make_counter(tmp_path, api_counting=False, cache_enabled=False)
        counter.count("no cache")
        counter.count("no cache")
        assert not counter._cache_path.exists()


class TestEmptyText:
    """Edge case: empty string input."""

    def test_empty_text_returns_count(self, tmp_path) -> None:
        """count('') returns a TokenResult (count may be 0 or 1 via max(1, ...))."""
        counter = _make_counter(tmp_path, api_counting=False, cache_enabled=False)
        result = counter.count("")
        # max(1, round(0 / 4.0)) = max(1, 0) = 1
        assert result.count >= 0
        assert isinstance(result, TokenResult)
