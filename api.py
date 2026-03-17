from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from dotenv import load_dotenv
from fastapi import Form, FastAPI, HTTPException
from google.adk.errors.session_not_found_error import SessionNotFoundError
from google.adk.runners import InMemoryRunner
from google.genai import types
from pydantic import BaseModel, Field

from orchestrator import create_app, load_config
from projects.example_projects import register_example_projects
from projects.registry import get_registry, set_current_project_id

load_dotenv()
register_example_projects()

# ADK app and runner (created at startup)
_adk_app: Any = None
_runner: InMemoryRunner | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _adk_app, _runner
    config = load_config()
    _adk_app = create_app(config=config)
    _runner = InMemoryRunner(app=_adk_app)
    yield
    _runner = None
    _adk_app = None


app = FastAPI(
    title="Agents API",
    description="Send a message and get the pipeline reply. Use project_id to select project (memory/tools).",
    lifespan=lifespan,
)


class ChatResponse(BaseModel):
    reply: str = Field(..., description="Final agent reply text")
    session_id: str = Field(..., description="Session id; send this back for follow-up messages")
    agent_name: str | None = Field(default=None, description="Name of the agent that produced the reply")


@app.post("/chat", response_model=ChatResponse)
async def chat(
    message: str = Form(..., description="User message to send to the agents"),
    project_id: str = Form("default", description="Project id (e.g. femverse, wardrobe). Determines which project memory/tools are used."),
    user_id: str = Form("api_user", description="User id for session isolation (conversation history is per user)."),
    session_id: str | None = Form(None, description="Optional. Send this for follow-up messages in the same conversation. Leave empty to start a new session."),
) -> ChatResponse:
    """
    Send a message through the agent pipeline and get the reply.
    Fill in the form fields below and click Execute.
    """
    if _runner is None or _adk_app is None:
        raise HTTPException(status_code=503, detail="App not ready")

    set_current_project_id(project_id)

    if session_id and session_id.strip():
        session_id = session_id.strip()
    else:
        session = await _runner.session_service.create_session(
            app_name=_adk_app.name,
            user_id=user_id,
        )
        session_id = session.id

    content = types.Content(role="user", parts=[types.Part(text=message)])
    last_content_by_agent: dict[str, types.Content] = {}
    used_provided_session = bool(session_id and session_id.strip())

    try:
        async for event in _runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=content,
        ):
            if getattr(event, "content", None):
                last_content_by_agent[event.author] = event.content
    except SessionNotFoundError:
        if used_provided_session:
            session = await _runner.session_service.create_session(
                app_name=_adk_app.name,
                user_id=user_id,
            )
            session_id = session.id
            last_content_by_agent = {}
            async for event in _runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=content,
            ):
                if getattr(event, "content", None):
                    last_content_by_agent[event.author] = event.content
        else:
            raise

    reply = ""
    agent_name: str | None = None

    # Use the root workflow agent's reply if present; otherwise the last agent that produced content.
    for name, event_content in last_content_by_agent.items():
        text_parts = [
            getattr(part, "text", "")
            for part in getattr(event_content, "parts", [])
            if getattr(part, "text", "")
        ]
        text = " ".join(text_parts).strip()
        if text:
            reply = text
            agent_name = name

    return ChatResponse(
        reply=reply or "(no reply)",
        session_id=session_id,
        agent_name=agent_name,
    )


@app.get("/projects")
async def list_projects() -> dict[str, list[str]]:
    """List registered project ids (for use in /chat project_id)."""
    ids = get_registry().list_project_ids()
    return {"project_ids": ids}


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check."""
    return {"status": "ok"}
