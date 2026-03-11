from __future__ import annotations
from typing import Literal, Union
from pydantic import BaseModel, Field


class AgentDefinition(BaseModel):
    name: str = Field(..., description="Unique agent name (must be a valid Python identifier)")
    role: str = Field(default="", description="Short description of the agent's capability")
    instruction: str = Field(
        default="",
        description="Instructions for the agent. Use {key} placeholders for state (e.g. {user_query}, {previous_result})",
    )
    tools: list[str] = Field(
        default_factory=list,
        description="List of tool names: ADK built-in names or custom names from custom_tools registry",
    )
    output_key: str | None = Field(
        default=None,
        description="Key in session state where this agent's output is stored (for connectivity to next agents)",
    )
    model: str | None = Field(
        default=None,
        description="Optional model override for this agent (e.g. gemini-2.5-flash)",
    )


class WorkflowDefinition(BaseModel):
    """
    A workflow node uses exactly one ADK composite pattern: sequential, parallel, or loop.
    Developers are not limited to a single pattern for the whole app. Combine patterns by
    nesting: any step may be an agent name (string) or another WorkflowDefinition. Examples:

    - Sequential A then B then parallel(C, D) then E:
        type: sequential
        steps:
          - AgentA
          - AgentB
          - type: parallel
            name: cd_parallel
            steps: [AgentC, AgentD]
          - AgentE

    """

    type: Literal["sequential", "parallel", "loop"] = Field(
        ...,
        description=(
            "Pattern for this node only: sequential, parallel, or loop. 
            "Combine patterns by nesting."
            "WorkflowDefinition objects inside steps."
        ),
    )
    name: str = Field(..., description="Unique name for this workflow node")
    description: str = Field(default="", description="Short description of this workflow")
    steps: list[Union[str, "WorkflowDefinition"]] = Field(
        default_factory=list,
        description=(
            "Each step is either an agent name (string) or a nested workflow object with its own type/steps."
        ),
    )
    max_iterations: int | None = Field(
        default=None,
        description="For type=loop only: maximum iterations before stopping",
    )


# Allow recursive WorkflowDefinition
WorkflowDefinition.model_rebuild()


class Connection(BaseModel):
    """Map output/state from one agent to a state key used by another agent."""

    from_agent: str = Field(..., description="Source agent name")
    from_key: str | None = Field(
        default=None,
        description="Source state key. If omitted, uses the source agent's output_key.",
    )
    to_agent: str = Field(..., description="Destination agent name")
    to_key: str = Field(
        ...,
        description="Destination state key to set before running to_agent.",
    )


class AgentsConfig(BaseModel):
    """Root schema for agents_config.yaml."""

    agents: list[AgentDefinition] = Field(
        default_factory=list,
        description="All leaf agents. Referenced by name in workflow steps.",
    )
    workflow: WorkflowDefinition = Field(
        ...,
        description="Root workflow: defines the execution tree (sequential/parallel/loop and steps).",
    )
    connections: list[Connection] = Field(
        default_factory=list,
        description="Optional connectivity mapping: copy state keys between agents before execution.",
    )
    default_model: str = Field(
        default="gemini-2.5-flash",
        description="Default LLM model for agents that do not specify model.",
    )
