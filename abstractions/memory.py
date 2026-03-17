from abc import ABC, abstractmethod
from typing import Any

class BaseMemory(ABC):
    """Abstract memory: ingest user messages and query for context."""

    @abstractmethod
    async def ingest(self, text: str, timestamp: str) -> None:
        """Store a piece of text with a timestamp."""
        pass

    @abstractmethod
    async def query(self, query: str, limit: int = 5) -> dict[str, Any]:
        """Return relevant context for the given query (e.g. recent or retrieved chunks)."""
        pass
