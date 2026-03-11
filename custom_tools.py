from __future__ import annotations
import inspect
import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)

CUSTOM_TOOLS_REGISTRY: dict[str, Callable[..., Any]] = {}


def register_tool(name: str):
    """Decorator to register a function as a tool under the given name."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        if name in CUSTOM_TOOLS_REGISTRY:
            logger.warning("Overwriting existing tool registration: %s", name)
        CUSTOM_TOOLS_REGISTRY[name] = func
        return func

    return decorator


def _load_adk_builtin(name: str) -> Any | None:
    try:
        import google.adk.tools as adk_tools
    except ImportError:
        return None

    # ADK exposes built-ins via lazy __getattr__; __all__ lists valid names.
    if name not in getattr(adk_tools, "__all__", ()):
        return None

    try:
        obj = getattr(adk_tools, name)
    except AttributeError:
        return None
    except Exception as e:
        logger.warning("Failed to load ADK built-in tool %s: %s", name, e)
        return None

    # BaseTool subclasses often need instantiation; pre-built instances are returned as-is.
    if inspect.isclass(obj):
        try:
            return obj()
        except (TypeError, Exception) as e:
            # Class requires constructor args or is abstract — use dotted import in YAML.
            logger.debug(
                "ADK name %s is not usable as zero-arg tool (%s); skip or use import path.",
                name,
                e,
            )
            return None
    return obj


def list_adk_builtin_tool_names() -> list[str]:
    """
    Names of tools exposed by google.adk.tools that developers can list in agents_config
    (e.g. tools: [google_search, url_context]). Safe to call without importing every tool.
    """
    try:
        import google.adk.tools as adk_tools

        return list(getattr(adk_tools, "__all__", []))
    except ImportError:
        return []


def get_tool(name: str) -> Any | None:
    """
    Look up a tool by name: first custom registry, then ADK built-ins from google.adk.tools.
    Returns a callable (function tool) or BaseTool instance, or None.
    """
    if name in CUSTOM_TOOLS_REGISTRY:
        return CUSTOM_TOOLS_REGISTRY[name]
    return _load_adk_builtin(name)


def get_tools_by_names(names: list[str]) -> list[Any]:
    """
    Resolve a list of tool names to tools. Uses custom registry then ADK built-ins.
    Skips unknown names and logs a warning.
    """
    result = []
    for n in names:
        t = get_tool(n)
        if t is not None:
            result.append(t)
        else:
            logger.warning("Tool not found (custom or ADK built-in): %s", n)
    return result


############################## Example custom tools ##############################


@register_tool("echo")
def echo(message: str) -> dict[str, str]:
    """
    Echoes the given message back. Useful for testing the tool pipeline.
    """
    return {"status": "success", "result": message}


@register_tool("add_numbers")
def add_numbers(a: float, b: float) -> dict[str, Any]:
    """
    Adds two numbers.
    """
    return {"status": "success", "result": a + b}
