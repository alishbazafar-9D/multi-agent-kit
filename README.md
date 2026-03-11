# Config-driven ADK multi-agent workforce

This project lets developers define an entire agentic workforce (agents + nested workflows) in **one** file: `agents_config.yaml`. No Python code is required to add new agents or change the workflow shape.

## Files

- `schema_models.py`: Pydantic config schema (agents, nested workflows, connections).
- `custom_tools.py`: place to register tool functions by string name.
- `workflow_factory.py`: `WorkflowFactory` + `GenericDeveloperAgent` (a `BaseAgent` that dynamically configures an internal `LlmAgent`).
- `orchestrator.py`: loads config and creates an ADK `App`.
- `agents_config.yaml`: example workforce config (Code Development Pipeline from [ADK Sequential agents](https://google.github.io/adk-docs/agents/workflow-agents/sequential-agents/): CodeWriterAgent, CodeReviewerAgent, CodeRefactorerAgent, CodePipelineAgent).
- `main.py`: runs the app with `InMemoryRunner`.

## Install

```bash
python -m pip install -r requirements.txt
```

## Required credentials (LLM)

ADK’s `LlmAgent` needs model credentials.

Option A (Gemini API):
- set `GOOGLE_API_KEY` (recommended via a `.env` file)

Option B (Vertex AI):
- configure Vertex AI credentials (project + location) per your environment.

If you don’t set credentials, you’ll see an error like:
`ValueError: Missing key inputs argument! ... provide (api_key) ... or (vertexai, project & location)`.

## Run

```bash
python main.py
```

## Config concepts

### 1) Agents (leaf nodes)

Each agent has:
- `name`
- `role` (mapped to ADK `description`)
- `instruction`
- `tools`: list of tool names (strings)
- `output_key`: where its output is stored in `ctx.session.state`

### 2) Workflows (nested at any level)

Each workflow node has **one** type: `sequential`, `parallel`, or `loop`. You are **not** limited to one type for the whole pipeline—**combine them by nesting**.

- **Sequential** runs its `steps` in order. A step can be an agent name or a **nested** workflow (parallel/loop/sequential).
- **Parallel** runs its `steps` concurrently (same shared session state).
- **Loop** repeats its sub-workflow up to `max_iterations`.

Example: run Agent1 then Agent2 sequentially, then Agent3 and Agent4 in parallel, then Agent5:

```yaml
workflow:
  type: sequential
  name: mixed_pipeline
  description: Sequential segments with a parallel block in the middle
  steps:
    - Agent1
    - Agent2
    - type: parallel
      name: parallel_research
      description: Run two researchers at once
      steps:
        - Agent3
        - Agent4
    - Agent5
```

Workflows can be nested arbitrarily using:
- `type: sequential`
- `type: parallel`
- `type: loop` (+ optional `max_iterations`)

Each workflow has `steps`, which are either:
- a string (agent name), or
- an inline nested workflow object (with its own `type`, `name`, and `steps`)

### 3) Connectivity (`connections`)

`connections` let you map state between agents without changing agent instructions.

Example: copy the output from `researcher` into `context` before running `writer`:

```yaml
connections:
  - from_agent: researcher
    to_agent: writer
    to_key: context
```

If `from_key` is omitted, it uses `from_agent.output_key`.

### 4) Tools

Tool names are resolved in this order:
1. **`custom_tools.py` registry** — your `@register_tool("name")` functions (e.g. `echo`, `add_numbers`)
2. **ADK built-in tools** — names from `google.adk.tools` (lazy-loaded). Common agent tools in YAML:
   `google_search`, `url_context`, `google_maps_grounding`, `enterprise_web_search`,
   `exit_loop`, `get_user_choice`, `load_artifacts`, `load_memory`, `preload_memory`,
   `transfer_to_agent`. Some entries in ADK’s public list are classes or helpers—if a name
   doesn’t load with zero-arg construction, use a fully-qualified import path instead.
   Discover names in code: `from custom_tools import list_adk_builtin_tool_names`.
3. **Fully-qualified import path** (function or zero-arg class), e.g. `my_pkg.my_tools.some_tool`

Unknown tool names are treated as placeholders and ignored with a warning.

