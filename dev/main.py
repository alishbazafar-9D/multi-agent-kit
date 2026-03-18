"""CLI entry: run the agent pipeline once. Run from repo root with PYTHONPATH=. (e.g. python dev/main.py)."""
import asyncio
from dotenv import load_dotenv
from google.adk.runners import InMemoryRunner
from google.genai import types

from dev.example_projects import register_example_projects
from src.orchestrator import create_app, load_config

load_dotenv()

# Register projects (Femverse, Wardrobe, Al-Siraat, etc.) so config.project selects memory/tools
register_example_projects()


def main() -> None:
    config = load_config()
    app = create_app(config=config)
    runner = InMemoryRunner(app=app)

    async def run() -> None:
        user_id = "cli_user"
        session = await runner.session_service.create_session(
            app_name=app.name,
            user_id=user_id,
        )

        prompt = "What is 3 + 5? Then write one sentence about addition."
        content = types.Content(role="user", parts=[types.Part(text=prompt)])

        # Track the last content event per agent name
        last_content_by_agent: dict[str, types.Content] = {}

        async for event in runner.run_async(
            user_id=user_id,
            session_id=session.id,
            new_message=content,
        ):
            if getattr(event, "content", None):
                last_content_by_agent[event.author] = event.content

        # Print only final text content per agent
        for agent_name, content in last_content_by_agent.items():
            text_parts = [
                getattr(part, "text", "")
                for part in getattr(content, "parts", [])
                if getattr(part, "text", "")
            ]
            if not text_parts:
                continue
            text = " ".join(text_parts).strip()
            if text:
                print(f"[{agent_name}] > {text}")

    asyncio.run(run())


if __name__ == "__main__":
    main()
