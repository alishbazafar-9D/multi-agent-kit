"""
Tool registry and built-in tools. Add your own tools here with @register_tool("name").
Refer to tool names in dev/agents_config.yaml (agents[].tools).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable

logger = logging.getLogger(__name__)

CUSTOM_TOOLS_REGISTRY: dict[str, Callable[..., Any]] = {}

_fallback_memory: Any = None


def get_default_memory() -> Any:
    """
    Memory used by memory_ingest / memory_query tools.
    - If the current project (see src.projects.registry) has a registered memory, that is used.
    - Otherwise a fallback InMemoryMemory is used so tools still work without a project.
    ADK memory (load_memory, preload_memory) is separate and always available to agents via YAML.
    """
    global _fallback_memory
    try:
        from src.projects.registry import get_registry
        mem = get_registry().get_current_memory()
        if mem is not None:
            return mem
    except Exception:
        pass
    if _fallback_memory is None:
        from src.abstractions.in_memory_memory import InMemoryMemory
        _fallback_memory = InMemoryMemory(max_entries=100)
    return _fallback_memory


def register_tool(name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Register a function as a tool under the given name."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        CUSTOM_TOOLS_REGISTRY[name] = func
        return func

    return decorator


def get_tool(name: str) -> Any:
    """
    Resolve a tool by name. Checks custom registry first, then ADK built-ins (load_memory, preload_memory).
    Returns the callable or ADK tool instance, or None if not found.
    """
    if name in CUSTOM_TOOLS_REGISTRY:
        return CUSTOM_TOOLS_REGISTRY[name]
    try:
        from google.adk import tools as adk_tools
        if hasattr(adk_tools, name):
            return getattr(adk_tools, name)
    except Exception:
        pass
    return None


def list_adk_builtin_tool_names() -> list[str]:
    """Return known ADK built-in tool names (for reference in config)."""
    return ["load_memory", "preload_memory"]


@register_tool("add_numbers")
def add_numbers(a: float, b: float) -> dict[str, Any]:
    """
    Adds two numbers.
    """
    return {"status": "success", "result": a + b}


############################## Memory tools (abstract memory integration) ##############################


@register_tool("memory_ingest")
async def memory_ingest(text: str, timestamp: str | None = None) -> dict[str, Any]:
    """
    Store a message in the shared memory. Use before or after answering so future queries can use this context.
    """
    ts = timestamp or datetime.now(timezone.utc).isoformat()
    mem = get_default_memory()
    await mem.ingest(text=text, timestamp=ts)
    return {"status": "success", "message": "Ingested into memory."}


@register_tool("memory_query")
async def memory_query(query: str, limit: int = 5) -> dict[str, Any]:
    """
    Query the shared memory for relevant context. Returns recent or matching entries for the given query.
    """
    mem = get_default_memory()
    result = await mem.query(query=query, limit=limit)
    return {"status": "success", "context": result}
