"""
Example project registrations. Replace or extend with your own projects.

- default: No project memory; use only ADK memory (load_memory, preload_memory).
- femverse, wardrobe, al_siraat: Placeholders with optional in-memory fallback; replace
  memory_factory with Graphiti, Mem0, or your own BaseMemory implementation.
"""

from __future__ import annotations

from projects.registry import ProjectConfig, register_project


def _in_memory_factory():
    from abstractions.in_memory_memory import InMemoryMemory
    return InMemoryMemory(max_entries=200)


def register_example_projects() -> None:
    """Register example projects. Call from main or app startup so project ids are known."""

    # No project memory: agents use only ADK memory (add load_memory, preload_memory to tools in YAML)
    register_project(
        ProjectConfig(
            project_id="default",
            name="Default",
            memory_factory=None,
            extra_tool_names=[],
        )
    )

    # Femverse: add Graphiti (or Mem0) by replacing memory_factory with your implementation
    register_project(
        ProjectConfig(
            project_id="femverse",
            name="Femverse",
            memory_factory=_in_memory_factory,  # Replace with e.g. lambda: FemverseGraphitiMemory()
            extra_tool_names=[],
        )
    )

    # Wardrobe AI
    register_project(
        ProjectConfig(
            project_id="wardrobe",
            name="Wardrobe AI",
            memory_factory=_in_memory_factory,
            extra_tool_names=[],
        )
    )

    # Al-Siraat
    register_project(
        ProjectConfig(
            project_id="al_siraat",
            name="Al-Siraat",
            memory_factory=_in_memory_factory,
            extra_tool_names=[],
        )
    )
