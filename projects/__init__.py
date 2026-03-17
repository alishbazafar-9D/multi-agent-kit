"""
Project registry: make the framework adaptable per project (Femverse, Wardrobe, Al-Siraat, etc.).

Each project can plug in:
- Optional memory (BaseMemory): Graphiti, Mem0, or None to use only ADK memory.
- Optional extra tools (by name).
- Optional data/config.

ADK memory (load_memory, preload_memory, session state, memory bank) is available to all;
project memory is additive when a project registers it.
"""

from projects.registry import (
    ProjectConfig,
    ProjectRegistry,
    get_current_project,
    get_current_project_id,
    register_project,
    set_current_project_id,
)

__all__ = [
    "ProjectConfig",
    "ProjectRegistry",
    "get_current_project",
    "get_current_project_id",
    "register_project",
    "set_current_project_id",
]
