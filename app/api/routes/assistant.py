from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, DbDep
from app.core.config import settings
from app.core.rate_limit import assistant_limiter
from app.services import assistant_mcp, assistant_service
from app.services.assistant_service import MAX_HISTORY, MAX_MESSAGE_CHARS, AssistantUnavailable

router = APIRouter(prefix="/assistant", tags=["assistant"])


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)


class ChatRequest(BaseModel):
    # The browser keeps the conversation and sends it back each time (the server stores nothing).
    messages: list[ChatMessage] = Field(min_length=1, max_length=MAX_HISTORY)
    lang: Literal["en", "es"] = "en"  # language for the reply and for the server's fixed messages


class ChatResponse(BaseModel):
    reply: str
    changed: bool  # true if todos were created / updated / deleted, so the UI should refresh
    actions: list[str]


def _client():
    try:
        return assistant_service.get_client()
    except AssistantUnavailable as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from None


@router.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest, db: DbDep, user: CurrentUser, client: Annotated[object, Depends(_client)]):
    if body.messages[-1].role != "user":
        raise HTTPException(422, "The last message must be from the user")
    wait = assistant_limiter.retry_after(user.id, settings.assistant_messages_per_hour)
    if wait:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Assistant message limit reached, try again later",
            headers={"Retry-After": str(wait)},
        )
    try:
        history = [m.model_dump() for m in body.messages]
        if settings.assistant_mode == "mcp":
            result = assistant_mcp.chat(client, user.id, history, body.lang)  # FastAPI as an MCP client
        else:
            result = assistant_service.chat(client, db, user.id, history, body.lang)  # tools run in-process
    except AssistantUnavailable as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from None
    return ChatResponse(reply=result.reply, changed=result.changed, actions=result.actions)
