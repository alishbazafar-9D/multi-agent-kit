from __future__ import annotations

from collections import deque
from typing import Any

from src.abstractions.memory import BaseMemory


class InMemoryMemory(BaseMemory):
    """
    Simple memory that keeps the last N entries in order.
    Query returns the most recent entries (optionally filtered by simple substring match).
    """

    def __init__(self, max_entries: int = 100):
        self._entries: deque[tuple[str, str]] = deque(maxlen=max_entries)

    async def ingest(self, text: str, timestamp: str) -> None:
        self._entries.append((text.strip(), timestamp))

    async def query(self, query: str, limit: int = 5) -> dict[str, Any]:
        # Return most recent entries; optional: filter by query substring
        query_lower = (query or "").strip().lower()
        if query_lower:
            matches = [
                {"text": t, "timestamp": ts}
                for t, ts in reversed(self._entries)
                if query_lower in t.lower()
            ][:limit]
        else:
            matches = [
                {"text": t, "timestamp": ts}
                for t, ts in list(reversed(self._entries))[:limit]
            ]
        return {"strategy": "in_memory", "context": matches}
