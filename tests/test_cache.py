"""Unit tests for TTLCache — get, set, expiry, eviction, clear, len."""

import time

from cache import TTLCache


class TestTTLCache:
    # ── get ────────────────────────────────────────────────────────────────

    def test_get_hit(self):
        """Stored value is retrieved and key is promoted to MRU end."""
        cache = TTLCache(ttl=10, max_size=5)
        cache.set("abc", 42)
        assert cache.get("abc") == 42

    def test_get_miss(self):
        """Missing key returns None."""
        cache = TTLCache(ttl=10, max_size=5)
        assert cache.get("missing") is None

    # ── TTL expiry ─────────────────────────────────────────────────────────

    def test_ttl_expiry(self):
        """Entry older than ttl is evicted on get() and returns None."""
        cache = TTLCache(ttl=0.01, max_size=5)
        cache.set("ephemeral", 99)
        time.sleep(0.02)  # > 0.01s ttl
        assert cache.get("ephemeral") is None

    # ── LRU eviction ───────────────────────────────────────────────────────

    def test_max_size_eviction(self):
        """Oldest entry (first inserted) is evicted when max_size exceeded."""
        cache = TTLCache(ttl=60, max_size=2)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)  # triggers eviction of "a"
        assert len(cache) == 2
        assert cache.get("a") is None
        assert cache.get("b") == 2
        assert cache.get("c") == 3

    # ── clear / len ────────────────────────────────────────────────────────

    def test_clear(self):
        """clear() empties the cache entirely."""
        cache = TTLCache(ttl=60, max_size=5)
        cache.set("x", 1)
        cache.set("y", 2)
        cache.set("z", 3)
        cache.clear()
        assert len(cache) == 0

    def test_len(self):
        """len(cache) reflects current entry count."""
        cache = TTLCache(ttl=60, max_size=5)
        assert len(cache) == 0
        cache.set("a", 1)
        assert len(cache) == 1
        cache.set("b", 2)
        assert len(cache) == 2
