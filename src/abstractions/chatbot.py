from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Optional

from src.abstractions.llm import BaseLLM
from src.abstractions.memory import BaseMemory


class BaseChatbot(ABC):
    """Abstract chatbot: chat with optional memory ingest and context."""

    @abstractmethod
    async def chat(self, message: str, timestamp: Optional[str] = None) -> str:
        raise NotImplementedError


class Chatbot(BaseChatbot):
    """Chatbot that ingests messages into memory, queries for context, then calls the LLM."""

    def __init__(
        self,
        llm: BaseLLM,
        memory: BaseMemory,
        ingest_enabled: bool = True,
        default_limit: int = 5,
    ):
        self.llm = llm
        self.memory = memory
        self.ingest_enabled = ingest_enabled
        self.default_limit = default_limit

    async def chat(self, message: str, timestamp: Optional[str] = None) -> str:
        actual_timestamp = timestamp or datetime.now(timezone.utc).isoformat()

        if self.ingest_enabled:
            await self.memory.ingest(text=message, timestamp=actual_timestamp)

        context = await self.memory.query(query=message, limit=self.default_limit)
        return await self.llm.generate(user_input=message, context=context)
