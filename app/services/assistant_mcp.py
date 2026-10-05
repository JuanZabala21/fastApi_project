"""AI assistant, MCP flavour: FastAPI acts as an MCP *client*.

    Claude (Anthropic API)  <->  this module (MCP client)  <->  mcp_server (MCP server)  ->  REST API

For each chat message we:
  1. mint a short-lived, restricted `todos` token for the logged-in user (no password involved),
  2. start the MCP server in memory with that token and connect to it as an MCP client,
  3. ask it which tools it offers and hand exactly those tools to Claude,
  4. run Claude's tool calls through the MCP server.

The same server (`mcp_server/`) is what Claude Code / Desktop use, so tools, validation, rate limiting and
audit logging live in ONE place. The REST API still enforces the user's identity: the MCP server can only
act with that restricted token.
"""
import asyncio
import logging
from typing import Any

import anthropic
import httpx
from mcp import Client

from app.core.config import settings
from app.core.security import SCOPE_TODOS, create_access_token
from app.services.assistant_service import (
    MAX_LOOP_STEPS,
    MAX_OUTPUT_TOKENS,
    MCP_BATCH_HINT,
    MESSAGES,
    AssistantUnavailable,
    ChatResult,
    _final_text,
    system_prompt,
)
from mcp_server.client import TodoApiClient
from mcp_server.security import McpConfig
from mcp_server.server import build_server

log = logging.getLogger("assistant.mcp")

MUTATING_TOOLS = {
    "create_todo", "create_todos", "set_todo_done", "rename_todo", "schedule_todo", "plan_todos", "delete_todo",
}
MAX_TOOL_RESULT_CHARS = 20_000  # keeps one huge tool result from flooding the model's context


def _api_http() -> httpx.Client:
    """HTTP client the MCP server uses to reach the REST API. A function so tests can swap it."""
    return httpx.Client(base_url=settings.assistant_api_url, timeout=15.0, follow_redirects=False)


def _result_text(result) -> str:
    text = "\n".join(c.text for c in result.content if getattr(c, "type", "") == "text") or "(no output)"
    return text[:MAX_TOOL_RESULT_CHARS]


async def _chat(client, user_id: int, history: list[dict[str, str]], lang: str) -> ChatResult:
    msg = MESSAGES.get(lang, MESSAGES["en"])
    config = McpConfig(
        api_url=settings.assistant_api_url,
        email="",
        password="",
        allow_delete=settings.assistant_allow_delete,
        rate_limit_per_minute=60,
        access_token=create_access_token(str(user_id), SCOPE_TODOS),  # restricted + short-lived
    )
    server = build_server(config, TodoApiClient(config, http=_api_http()))

    called: list[str] = []
    changed = False
    messages: list[Any] = [{"role": m["role"], "content": m["content"]} for m in history]

    async with Client(server) as mcp:
        # Whatever the MCP server offers is what Claude can use: discovery instead of a hardcoded list.
        tools = [
            {"name": t.name, "description": t.description or "", "input_schema": t.input_schema}
            for t in (await mcp.list_tools()).tools
        ]
        system = system_prompt(MCP_BATCH_HINT, lang)

        for _ in range(MAX_LOOP_STEPS):
            # The SDK call is blocking: run it in a thread so the event loop stays free for the MCP server.
            response = await asyncio.to_thread(
                client.messages.create,
                model=settings.anthropic_model,
                max_tokens=MAX_OUTPUT_TOKENS,
                system=system,
                tools=tools,
                output_config={"effort": settings.assistant_effort},
                messages=messages,
            )
            if response.stop_reason == "refusal":
                return ChatResult(msg["refusal"], changed, called)
            if response.stop_reason != "tool_use":
                reply = _final_text(response) or msg["done"]
                if response.stop_reason == "max_tokens":
                    reply += "\n\n" + msg["truncated"]
                return ChatResult(reply, changed, called)

            messages.append({"role": "assistant", "content": response.content})
            results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                try:
                    result = await mcp.call_tool(block.name, block.input if isinstance(block.input, dict) else {})
                    text, is_error = _result_text(result), bool(result.is_error)
                except Exception:  # protocol-level failure: tell the model, keep details in the server log
                    log.exception("MCP call failed: %s", block.name)
                    text, is_error = "The tool failed unexpectedly.", True
                called.append(block.name)
                changed = changed or (block.name in MUTATING_TOOLS and not is_error)
                log.info("user=%s mcp_tool=%s error=%s", user_id, block.name, is_error)
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": text, "is_error": is_error})
            messages.append({"role": "user", "content": results})

    return ChatResult(msg["steps"], changed, called)


def chat(client, user_id: int, history: list[dict[str, str]], lang: str = "en") -> ChatResult:
    """Sync entry point used by the route (it runs in FastAPI's threadpool, so asyncio.run is safe here)."""
    try:
        return asyncio.run(_chat(client, user_id, history, lang))
    except anthropic.APIError as exc:
        log.warning("Anthropic API error: %s", type(exc).__name__)  # never log request bodies or keys
        raise AssistantUnavailable("The assistant is unavailable right now, try again in a moment") from None

