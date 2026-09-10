"""Shared thread-safe cache for expensive Dummy OS planner dependency results."""
from __future__ import annotations

from threading import RLock
from typing import Any, Callable


class PlannerResultCache:
    """Cache planner results per material input key across entity workers."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._scopes: dict[str, tuple[tuple[Any, ...], dict[str, Any]]] = {}
        self.hits = 0
        self.misses = 0

    def get(self, scope: str, key: tuple[Any, ...], name: str, builder: Callable[[], Any]) -> Any:
        with self._lock:
            current = self._scopes.get(scope)
            if current is None or current[0] != key:
                current = (key, {})
                self._scopes[scope] = current
            values = current[1]
            if name in values:
                self.hits += 1
                return values[name]
            self.misses += 1
            value = builder()
            values[name] = value
            return value
