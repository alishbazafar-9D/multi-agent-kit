from __future__ import annotations

import logging
from pathlib import Path

from google.adk.apps import App

from src.projects.registry import set_current_project_id
from src.schema_models import AgentsConfig
from src.workflow_factory import WorkflowFactory

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = "agents_config.yaml"


def load_config(path: str | Path | None = None) -> AgentsConfig:
    """Load and validate config from path. If path is None, looks for dev/agents_config.yaml."""
    path = Path(path) if path else None
    if path is None:
        # Default: dev/agents_config.yaml (repo root is parent of src/)
        repo_root = Path(__file__).resolve().parent.parent
        candidate = repo_root / "dev" / DEFAULT_CONFIG_PATH
        if not candidate.exists():
            raise FileNotFoundError(
                f"No config file found. Expected dev/{DEFAULT_CONFIG_PATH} in {repo_root}. "
                "Set path explicitly or create dev/agents_config.yaml."
            )
        path = candidate
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    suffix = path.suffix.lower()
    if suffix not in (".yaml", ".yml"):
        raise ValueError(
            f"Config must be a YAML file (.yaml or .yml), got: {path}. Use agents_config.yaml."
        )

    try:
        import yaml
    except ImportError:
        raise ImportError("PyYAML is required for YAML config. Install with: pip install pyyaml")

    raw = path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    return AgentsConfig.model_validate(data)


def create_app(config: AgentsConfig | None = None, config_path: str | Path | None = None) -> App:
    """
    Build the ADK App from config. Either pass a validated AgentsConfig or a path to the config file.
    """
    if config is None:
        config = load_config(config_path)

    # Set current project so memory_ingest / memory_query use project memory when registered
    set_current_project_id(config.project)

    agents_by_name = {a.name: a for a in config.agents}
    factory = WorkflowFactory(
        agents_by_name=agents_by_name,
        connections=config.connections,
        default_model=config.default_model,
    )
    root_agent = factory.build(config.workflow)

    app = App(
        name="config_driven_agents",
        root_agent=root_agent,
    )
    return app


# Single entry point: app suitable for Runner(app=app) or adk run
app = create_app()
