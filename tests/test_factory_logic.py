from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from google.adk.agents.parallel_agent import ParallelAgent
from google.adk.agents.sequential_agent import SequentialAgent
from pydantic import ValidationError

from dev import custom_tools
from src.schema_models import AgentDefinition, AgentsConfig, WorkflowDefinition
from src.workflow_factory import GenericDeveloperAgent, WorkflowFactory


@pytest_asyncio.fixture
async def complex_sequential_parallel_dummy_config() -> dict[str, Any]:
    """
    Sequential -> Parallel -> Sequential topology:
    Agent1 -> [Agent2, Agent3] -> Agent4
    """
    await asyncio.sleep(0)
    return {
        "default_model": "gemini-2.5-flash",
        "agents": [
            {
                "name": "Agent1",
                "role": "First step",
                "instruction": "Do step one. {user_query}",
                "tools": [],
                "output_key": "out1",
            },
            {
                "name": "Agent2",
                "role": "Parallel branch A",
                "instruction": "Branch A.",
                "tools": ["load_memory"],
                "output_key": "out2",
            },
            {
                "name": "Agent3",
                "role": "Parallel branch B",
                "instruction": "Branch B.",
                "tools": [],
                "output_key": "out3",
            },
            {
                "name": "Agent4",
                "role": "Final merge",
                "instruction": "Final step. Use branch_a={branch_a} and branch_b={branch_b}.",
                "tools": [],
                "output_key": "out4",
            },
        ],
        "workflow": {
            "type": "sequential",
            "name": "root_seq",
            "description": "Seq then parallel then seq",
            "steps": [
                "Agent1",
                {
                    "type": "parallel",
                    "name": "mid_parallel",
                    "description": "Two branches",
                    "steps": ["Agent2", "Agent3"],
                },
                "Agent4",
            ],
        },
        "connections": [
            {"from_agent": "Agent2", "to_agent": "Agent4", "to_key": "branch_a"},
            {"from_agent": "Agent3", "to_agent": "Agent4", "to_key": "branch_b"},
        ],
    }


@pytest.fixture
def workflow_factory_for_topology(complex_sequential_parallel_dummy_config: dict[str, Any]) -> WorkflowFactory:
    cfg = AgentsConfig.model_validate(complex_sequential_parallel_dummy_config)
    agents_by_name = {a.name: a for a in cfg.agents}
    return WorkflowFactory(
        agents_by_name=agents_by_name,
        connections=cfg.connections,
        default_model=cfg.default_model,
    )


############################################ Schema integrity ############################################


def test_tc_schema_missing_agent_name_raises_validation_error() -> None:
    """Bad agent rows must fail at AgentsConfig.model_validate (schema_models.py)."""
    bad = {
        "agents": [{"role": "x", "instruction": "y"}],
        "workflow": {"type": "sequential", "name": "w", "steps": []},
    }
    with pytest.raises(ValidationError) as exc_info:
        AgentsConfig.model_validate(bad)
    err = str(exc_info.value)
    assert "name" in err.lower(), (
        "FAILED: Expected Pydantic to report missing 'name' for AgentDefinition. "
        "Check field requirements in 'schema_models.py' (AgentDefinition.name)."
    )


def test_tc_schema_invalid_workflow_type_raises_validation_error() -> None:
    """Workflow type must be sequential | parallel | loop."""
    bad = {
        "agents": [],
        "workflow": {"type": "not_a_valid_type", "name": "w", "steps": []},
    }
    with pytest.raises(ValidationError) as exc_info:
        AgentsConfig.model_validate(bad)
    assert exc_info.value is not None, (
        "FAILED: Invalid workflow.type should raise ValidationError. "
        "Verify Literal['sequential','parallel','loop'] on WorkflowDefinition in 'schema_models.py'."
    )


def test_tc_schema_missing_workflow_raises_validation_error() -> None:
    """Root workflow is required on AgentsConfig."""
    bad: dict[str, Any] = {"agents": []}
    with pytest.raises(ValidationError) as exc_info:
        AgentsConfig.model_validate(bad)
    assert "workflow" in str(exc_info.value).lower(), (
        "FAILED: AgentsConfig requires 'workflow'. See AgentsConfig in 'schema_models.py'."
    )


############################################ Agent role / instruction matching ############################################


def test_tc_agent_role_and_instruction_propagate_to_generic_developer_agent() -> None:
    """Role -> description; instruction -> LlmAgent.instruction."""
    ad = AgentDefinition(
        name="Leaf",
        role="Planner role text",
        instruction="You must plan: {user_query}",
        tools=[],
        output_key="plan_out",
    )
    factory = WorkflowFactory(agents_by_name={"Leaf": ad})
    root = factory.build(
        WorkflowDefinition(type="sequential", name="s", steps=["Leaf"])
    )
    assert isinstance(root, SequentialAgent), (
        "FAILED: Expected single-step sequential root. Verify _build_workflow in 'workflow_factory.py'."
    )
    leaf = root.sub_agents[0]
    assert isinstance(leaf, GenericDeveloperAgent), (
        "FAILED: Leaf should be GenericDeveloperAgent. Check _get_or_build_leaf_agent in 'workflow_factory.py'."
    )
    assert leaf.description == "Planner role text", (
        "FAILED: Agent 'role' from YAML/schema must map to GenericDeveloperAgent.description. "
        "See AgentDefinition.role and GenericDeveloperAgent.__init__ in 'workflow_factory.py'."
    )
    assert leaf.delegate.instruction == "You must plan: {user_query}", (
        "FAILED: instruction must flow to LlmAgent. Check instruction=ad.instruction in 'workflow_factory.py'."
    )


def test_tc_agent_dict_missing_role_uses_schema_default() -> None:
    """Role defaults to ''; if you require non-empty role, tighten AgentDefinition in schema_models.py."""
    agent_data = {"name": "A", "instruction": "x"}
    assert "role" not in agent_data, (
        "FAILED: This dummy omits 'role' on purpose to document defaulting. Adjust test data if schema changes."
    )
    m = AgentDefinition.model_validate(agent_data)
    assert m.role == "", (
        "FAILED: Missing 'role' in YAML should default to empty string per 'schema_models.py'. "
        "To fail fast on missing role, add Field(..., min_length=1) or a model_validator in 'schema_models.py'."
    )


############################################ Tool binding: built-in vs custom ############################################


def test_tc_builtin_tool_load_memory_bound_to_agent_toolbox() -> None:
    ad = AgentDefinition(
        name="WithBuiltin",
        role="r",
        instruction="i",
        tools=["load_memory"],
    )
    factory = WorkflowFactory(agents_by_name={"WithBuiltin": ad})
    root = factory.build(WorkflowDefinition(type="sequential", name="x", steps=["WithBuiltin"]))
    agent = root.sub_agents[0]
    assert isinstance(agent, GenericDeveloperAgent)
    assert len(agent.delegate.tools) >= 1, (
        "FAILED: load_memory should resolve via get_tool() in '_resolve_tools' (workflow_factory.py). "
        "Confirm ADK exposes load_memory in google.adk.tools (dev/custom_tools.get_tool)."
    )
    from dev.custom_tools import get_tool

    expected = get_tool("load_memory")
    assert expected is not None, (
        "FAILED: get_tool('load_memory') returned None. Check 'dev/custom_tools.py' and ADK builtins."
    )
    assert expected in agent.delegate.tools, (
        "FAILED: Built-in tool should appear on LlmAgent.tools. Trace _resolve_tools in 'workflow_factory.py'."
    )


@pytest.mark.asyncio  # agent/tool init path exercised after async registry patch
async def test_tc_custom_mock_tool_assigned_to_agent_toolbox(monkeypatch: pytest.MonkeyPatch) -> None:
    """Custom tools come from CUSTOM_TOOLS_REGISTRY (dev/custom_tools.py)."""
    mock_fn = MagicMock(__name__="mock_custom_tool_fn")
    monkeypatch.setitem(custom_tools.CUSTOM_TOOLS_REGISTRY, "mock_custom_xyz", mock_fn)

    await asyncio.sleep(0)

    ad = AgentDefinition(
        name="CustomToolAgent",
        role="r",
        instruction="i",
        tools=["mock_custom_xyz"],
    )
    factory = WorkflowFactory(agents_by_name={"CustomToolAgent": ad})
    root = factory.build(
        WorkflowDefinition(type="sequential", name="seq", steps=["CustomToolAgent"])
    )
    g = root.sub_agents[0]
    assert isinstance(g, GenericDeveloperAgent), (
        "FAILED: Expected GenericDeveloperAgent. See workflow_factory.py _get_or_build_leaf_agent."
    )
    assert mock_fn in g.delegate.tools, (
        "FAILED: Custom tool from registry must be in agent toolbox. "
        "Verify get_tool() and CUSTOM_TOOLS_REGISTRY in 'dev/custom_tools.py' and _resolve_tools in 'workflow_factory.py'."
    )


############################################ Workflow ############################################


def test_tc_workflow_topology_agent1_parallel_agent2_agent3_then_agent4(
    workflow_factory_for_topology: WorkflowFactory,
    complex_sequential_parallel_dummy_config: dict[str, Any],
) -> None:
    cfg = AgentsConfig.model_validate(complex_sequential_parallel_dummy_config)
    root = workflow_factory_for_topology.build(cfg.workflow)

    assert isinstance(root, SequentialAgent), (
        "FAILED: Root workflow should be SequentialAgent. Verify type=='sequential' parsing in 'workflow_factory.py'."
    )
    assert len(root.sub_agents) == 3, (
        f"FAILED: Expected 3 sequential steps (Agent1, parallel block, Agent4). Got {len(root.sub_agents)}. "
        "Check nested steps in YAML vs _build_workflow in 'workflow_factory.py'."
    )

    a1 = root.sub_agents[0]
    mid = root.sub_agents[1]
    a4 = root.sub_agents[2]

    assert isinstance(a1, GenericDeveloperAgent) and a1.name == "Agent1", (
        "FAILED: First step should be Agent1 (GenericDeveloperAgent). See 'workflow_factory.py'."
    )

    assert isinstance(mid, ParallelAgent), (
        "FAILED: Workflow step 1 (index 1) should be the parallel composite (ADK ParallelAgent). "
        "Verify the parsing logic in 'workflow_factory.py' when step is a nested dict with type parallel."
    )

    assert len(mid.sub_agents) == 2, (
        f"FAILED: Parallel block should run Agent2 and Agent3. Got {len(mid.sub_agents)} children. "
        "Inspect nested WorkflowDefinition.steps in 'schema_models.py' / YAML."
    )
    assert mid.sub_agents[0].name == "Agent2" and mid.sub_agents[1].name == "Agent3", (
        "FAILED: Parallel order should be [Agent2, Agent3]. Check step order in dummy config and 'workflow_factory.py'."
    )

    assert isinstance(a4, GenericDeveloperAgent) and a4.name == "Agent4", (
        "FAILED: Final sequential step should be Agent4. Verify sequential steps list after parallel node in 'workflow_factory.py'."
    )
    assert getattr(a4, "incoming_state_mappings", None) == [
        ("out2", "branch_a"),
        ("out3", "branch_b"),
    ], (
        "FAILED: Expected connections[] to compile into A4 incoming_state_mappings "
        "(out2->branch_a, out3->branch_b). "
        "Check '_compile_incoming_mappings' + GenericDeveloperAgent wiring in 'src/workflow_factory.py'."
    )


@pytest.mark.asyncio
async def test_tc_async_fixture_warmup_then_topology(
    workflow_factory_for_topology: WorkflowFactory,
    complex_sequential_parallel_dummy_config: dict[str, Any],
) -> None:
    """Async-marked test: validate tree after async fixture warmup."""
    await asyncio.sleep(0)
    cfg = AgentsConfig.model_validate(complex_sequential_parallel_dummy_config)
    root = workflow_factory_for_topology.build(cfg.workflow)
    assert isinstance(root.sub_agents[1], ParallelAgent), (
        "FAILED: Middle step must be ParallelAgent. Verify 'workflow_factory.py' _build_workflow for nested parallel."
    )


def test_tc_unknown_agent_step_skipped_with_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Unknown string steps are skipped (workflow_factory logs warning)."""
    import logging

    caplog.set_level(logging.WARNING)
    agents = [
        AgentDefinition(name="Known", role="r", instruction="i"),
    ]
    factory = WorkflowFactory(agents_by_name={a.name: a for a in agents})
    w = WorkflowDefinition(
        type="sequential",
        name="s",
        steps=["Ghost", "Known"],
    )
    root = factory.build(w)
    assert isinstance(root, SequentialAgent)
    assert len(root.sub_agents) == 1, (
        "FAILED: Unknown agent 'Ghost' should be skipped; only Known built. See _build_workflow in 'workflow_factory.py'."
    )
    assert any("Unknown agent" in r.message for r in caplog.records), (
        "FAILED: Expect warning log for missing agent name. Check logger.warning in 'workflow_factory.py'."
    )
