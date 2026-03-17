from __future__ import annotations

import importlib
import inspect
import logging
from typing import Any, AsyncGenerator, Callable

from google.adk.agents.base_agent import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents.loop_agent import LoopAgent
from google.adk.agents.parallel_agent import ParallelAgent
from google.adk.agents.sequential_agent import SequentialAgent
from google.adk.events.event import Event
from typing_extensions import override
from custom_tools import get_tool
from schema_models import AgentDefinition, Connection, WorkflowDefinition

logger = logging.getLogger(__name__)


class GenericDeveloperAgent(BaseAgent):
    """
    A config-driven agent that inherits from BaseAgent and delegates to an internal
    LlmAgent.
    """

    # Pydantic field so it's preserved/validated.
    delegate: LlmAgent
    incoming_state_mappings: list[tuple[str, str]] = []

    # Ensure Pydantic accepts arbitrary ADK types.
    model_config = {"arbitrary_types_allowed": True}

    def __init__(
        self,
        *,
        name: str,
        description: str,
        instruction: str,
        tools: list[Any],
        output_key: str | None = None,
        model: str | None = None,
        default_model: str = "gemini-2.5-flash",
        incoming_state_mappings: list[tuple[str, str]] | None = None,
    ) -> None:
        resolved_model = model or default_model
        llm_agent = LlmAgent(
            name=name,
            description=description,
            instruction=instruction,
            tools=tools,
            output_key=output_key,
            model=resolved_model,
        )
        super().__init__(
            name=name,
            description=description,
            delegate=llm_agent,
            sub_agents=[llm_agent],
            incoming_state_mappings=incoming_state_mappings or [],
        )

    @override
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """Execute the dynamically configured LLM agent; yield all events."""
        # Apply connectivity mappings: copy outputs from prior agents into keys
        # this agent expects (typically referenced in instruction placeholders).
        for from_key, to_key in self.incoming_state_mappings:
            if from_key in ctx.session.state:
                ctx.session.state[to_key] = ctx.session.state.get(from_key)

        output_key = self.delegate.output_key
        accumulated: list[str] = []

        async for event in self.delegate.run_async(ctx):
            if output_key and getattr(event, "content", None) and event.content.parts and getattr(event, "author", None) == self.name:
                for part in event.content.parts:
                    if getattr(part, "text", None) and not getattr(part, "thought", None):
                        accumulated.append(part.text)
            yield event

        # Ensure session state is set for the next agent (runner may append
        # state_delta only for non-partial events; writing here guarantees it).
        if output_key and accumulated:
            ctx.session.state[output_key] = "".join(accumulated)


class WorkflowFactory:
    """
    Parses the agents_config schema and recursively builds the ADK agent tree.
    """

    def __init__(
        self,
        agents_by_name: dict[str, AgentDefinition],
        connections: list[Connection] | None = None,
        default_model: str = "gemini-2.5-flash",
    ) -> None:
        # Caller already provides a name -> AgentDefinition mapping.
        self._agents_by_name = dict(agents_by_name)
        self._incoming_mappings_by_agent = self._compile_incoming_mappings(
            connections or []
        )
        self._default_model = default_model
        self._built_agents: dict[str, BaseAgent] = {}

    def build(self, workflow: WorkflowDefinition) -> BaseAgent:
        """Build the root (or any) workflow node and its subtree"""
        return self._build_workflow(workflow)

    def _build_workflow(self, w: WorkflowDefinition) -> BaseAgent:
        """Recursively build a workflow node: either a composite (sequential/parallel/loop) or resolve to agent."""
        sub_agents: list[BaseAgent] = []
        for step in w.steps:
            if isinstance(step, str):
                agent = self._get_or_build_leaf_agent(step)
                if agent is not None:
                    sub_agents.append(agent)
                else:
                    logger.warning("Unknown agent name in workflow steps, skipping: %s", step)
            else:
                sub_agents.append(self._build_workflow(step))

        if w.type == "sequential":
            return SequentialAgent(
                name=w.name,
                description=w.description or f"Sequential workflow: {w.name}",
                sub_agents=sub_agents,
            )
        if w.type == "parallel":
            return ParallelAgent(
                name=w.name,
                description=w.description or f"Parallel workflow: {w.name}",
                sub_agents=sub_agents,
            )
        if w.type == "loop":
            return LoopAgent(
                name=w.name,
                description=w.description or f"Loop workflow: {w.name}",
                sub_agents=sub_agents,
                max_iterations=w.max_iterations,
            )
        raise ValueError(f"Unsupported workflow type: {w.type}")

    def _get_or_build_leaf_agent(self, agent_name: str) -> BaseAgent | None:
        """Build a GenericDeveloperAgent from AgentDefinition if not already built."""
        if agent_name in self._built_agents:
            return self._built_agents[agent_name]
        ad = self._agents_by_name.get(agent_name)
        if ad is None:
            return None
        tools = self._resolve_tools(ad.tools)
        agent = GenericDeveloperAgent(
            name=ad.name,
            description=ad.role,
            instruction=ad.instruction,
            tools=tools,
            output_key=ad.output_key,
            model=ad.model,
            default_model=self._default_model,
            incoming_state_mappings=self._incoming_mappings_by_agent.get(ad.name, []),
        )
        self._built_agents[agent_name] = agent
        return agent

    def _compile_incoming_mappings(
        self, connections: list[Connection]
    ) -> dict[str, list[tuple[str, str]]]:
        """
        Pre-resolve connection from_key defaults (from_agent.output_key) so agents
        can just copy state before running.
        """
        incoming: dict[str, list[tuple[str, str]]] = {}
        for c in connections:
            from_key = c.from_key
            if from_key is None:
                from_agent = self._agents_by_name.get(c.from_agent)
                from_key = from_agent.output_key if from_agent else None
            if not from_key:
                logger.warning(
                    "Skipping connection %s -> %s: could not resolve from_key",
                    c.from_agent,
                    c.to_agent,
                )
                continue
            incoming.setdefault(c.to_agent, []).append((from_key, c.to_key))
        return incoming

    def _resolve_tools(self, tool_names: list[str]) -> list[Callable[..., Any] | Any]:
        """
        Resolve tool names to ADK tool callables/objects.
        Priority:
          1) custom_tools.get_tool — custom registry then ADK built-ins (google.adk.tools)
          2) fully-qualified import path (function or class with zero-arg ctor)
        Unknown tools are ignored with a warning (placeholders allowed).
        """
        resolved: list[Callable[..., Any] | Any] = []
        for name in tool_names:
            # 1) Custom registry + ADK built-ins (see custom_tools.list_adk_builtin_tool_names())
            tool = get_tool(name)
            if tool is not None:
                resolved.append(tool)
                continue

            # 2) Fully-qualified import path (module:function or module.Class)
            if "." in name:
                try:
                    module_path, attr = name.rsplit(".", 1)
                    mod = importlib.import_module(module_path)
                    obj = getattr(mod, attr)
                    if inspect.isclass(obj):
                        resolved.append(obj())
                    else:
                        resolved.append(obj)
                    continue
                except Exception:
                    logger.warning("Could not import tool by path: %s", name)

            logger.warning("Unknown tool (placeholder ignored): %s", name)
        return resolved
