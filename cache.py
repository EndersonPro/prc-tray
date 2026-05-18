"""LRU cache with TTL for extraction results."""
import time
from collections import OrderedDict
from typing import Any

from config import CACHE_TTL, CACHE_MAX_SIZE


class TTLCache:
    def __init__(self, ttl: int = CACHE_TTL, max_size: int = CACHE_MAX_SIZE):
        self._store: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._ttl = ttl
        self._max_size = max_size

    def get(self, key: str) -> Any | None:
        if key not in self._store:
            return None
        ts, value = self._store[key]
        if time.time() - ts > self._ttl:
            del self._store[key]
            return None
        self._store.move_to_end(key)
        return value

    def set(self, key: str, value: Any) -> None:
        if key in self._store:
            self._store.move_to_end(key)
        self._store[key] = (time.time(), value)
        while len(self._store) > self._max_size:
            self._store.popitem(last=False)

    def clear(self) -> None:
        self._store.clear()

    def __len__(self) -> int:
        return len(self._store)


cache = TTLCache()
