from abc import ABC, abstractmethod
from typing import Any

class BaseLLM(ABC):
    """Abstract LLM: generate a response from user input and context."""

    @abstractmethod
    async def generate(self, user_input: str, context: dict[str, Any]) -> str:
        """Generate a reply given the user message and context (e.g. from memory)."""
        raise NotImplementedError
