"""Project registry (core). To add a project, edit dev/example_projects.py."""

from src.projects.registry import (
    ProjectConfig,
    ProjectRegistry,
    get_current_project,
    get_current_project_id,
    get_registry,
    register_project,
    set_current_project_id,
)

__all__ = [
    "ProjectConfig",
    "ProjectRegistry",
    "get_current_project",
    "get_current_project_id",
    "get_registry",
    "register_project",
    "set_current_project_id",
]
