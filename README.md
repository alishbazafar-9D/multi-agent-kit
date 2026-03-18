# Config-driven ADK multi-agent workforce

A framework for running multi-agent pipelines driven by YAML config. Define agents, tools, and workflows in config; run via CLI or HTTP API. Uses Google ADK (Agent Development Kit) and Gemini.

---

## Quick start

1. **Clone and enter the repo**
  ```bash
   cd multi-agent-kit
  ```
2. **Create a virtual environment and install dependencies**
  ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
  ```
3. **Add your API key**
  - Create a file named `.env` in the repo root.
  - Add a line: `GOOGLE_API_KEY=your_key_here`
4. **Run**
  ```bash
   # One-shot run (CLI): sends a test prompt and prints the agent reply
   python main.py

   # Start the HTTP API (Swagger at http://localhost:8000/docs)
   python main.py --api
  ```

---

## Configuration

### Agents and workflow: `dev/agents_config.yaml`

This file defines your pipeline. The app loads `**dev/agents_config.yaml**` by default.

- `**default_model**` — e.g. `gemini-2.5-flash`
- `**agents**` — List of agents: `name`, `role`, `instruction`, `tools` (tool names from `dev/custom_tools.py` or ADK built-ins), optional `model`, `output_key`
- `**workflow**` — Root workflow: `type` (`sequential`, `parallel`, or `loop`), `name`, `steps` (agent names or nested workflows)
- `**connections**` — Optional: map one agent’s output to another’s input state
- `**project**` — Optional project id (e.g. `femverse`); selects which project memory/tools are used

Edit this file to add agents, change the model, or rearrange the workflow. You do not need to change code for that.

### Projects: `dev/example_projects.py`

Projects let you plug in different memory backends and tool sets. To add a project:

1. Open `**dev/example_projects.py**`.
2. Call `register_project(ProjectConfig(project_id="my_app", name="My App", memory_factory=..., extra_tool_names=[...]))`.
3. Use `project_id` in the YAML `project` field or in the API `project_id` form field.

The registry logic lives in `src/projects/`; you only edit `example_projects.py` to register projects.

### Tools: `dev/custom_tools.py`

Tools are functions agents can call. Names in `agents_config.yaml` are resolved in two ways:

**1. ADK built-in tools (no code changes)**  
The framework resolves tool names against Google ADK’s built-ins. You only add the name to an agent’s `tools` list in `**dev/agents_config.yaml`**. Examples:

- `**load_memory`**  : Load content from ADK’s memory bank into the conversation (e.g. for RAG).
- `**preload_memory`** : Preload memory into the session before the agent runs.

These are part of ADK’s own memory and session model. No edits in `custom_tools.py` are required.

**2. This repo’s registered tools (defined in** `dev/custom_tools.py`**)**  
The same config also resolves names from this project’s tool registry. Currently provided:

- `**add_numbers`** : Add two numbers.
- `**memory_ingest`** : Store text in the **project’s** memory (the one you plug in per project in `example_projects.py`). Shared per project.
- `**memory_query`** : Query that project memory for relevant context.  


**To add your own tool:**

1. In **`dev/custom_tools.py`**, define a function and decorate it with `@register_tool("tool_name")`.
2. Add `tool_name` to the agent’s `tools` list in **`dev/agents_config.yaml`**.

---

## Using the API

- **POST `/chat`** — Send a message and get the agent’s reply. Use the form fields:
  - `**message**` — User message.
  - `**project_id**` — Which project to use (default: `default`). Must be registered in `dev/example_projects.py`.
  - `**user_id**` — Identifies the user (e.g. from your auth). Use a stable, unique id per user so conversation history is isolated. Default: `api_user`.
  - `**session_id**` — Omit for a new conversation; send the `session_id` returned in the previous reply to continue the same thread.

The response includes `reply`, `session_id` (send this back for follow-ups), and `agent_name`.

- **GET `/projects`** — List registered `project_id`s.
- **GET `/health`** — Health check.

---

## Project layout

- **`dev/`** — Where you work:
  - **`agents_config.yaml`** — Pipeline config (agents, workflow, connections).
  - **`example_projects.py`** — Register projects here.
  - **`custom_tools.py`** — Register tools and add custom tools here.
  - **`main.py`** — CLI implementation (called by root `main.py`).
- **`src/`** — Core (no need to edit):
  - Orchestrator, workflow factory, schema models, project registry, FastAPI app, and abstractions (memory, LLM, chatbot).
- **Root:** `**main.py`** is the single entry point: `python main.py` for CLI, `python main.py --api` for the server.

