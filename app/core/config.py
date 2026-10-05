"""Settings loaded from environment variables / the .env file."""
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    database_url: str
    secret_key: str
    access_token_expire_minutes: int = 30
    algorithm: str = "HS256"
    mcp_token_expire_minutes: int = 15  # lifetime of the restricted "todos" tokens
    # Login throttling: max failed attempts per (client IP, email) inside the window
    login_max_attempts: int = 5
    login_window_seconds: int = 300
    # AI assistant. No key = the /assistant endpoint answers 503. Never hardcode the key: put it in .env.
    anthropic_api_key: SecretStr | None = None
    anthropic_model: str = "claude-sonnet-5-5"
    assistant_effort: Literal["low", "medium", "high"] = "medium"  # thinking depth: lower = cheaper/faster
    assistant_messages_per_hour: int = 30  # per user, caps spend
    # "mcp": the chat talks to our MCP server (FastAPI is the MCP client); "direct": tools run in-process.
    assistant_mode: Literal["mcp", "direct"] = "mcp"
    # Where the MCP server reaches this API (the MCP server calls the REST API over HTTP, like Claude Code would).
    assistant_api_url: str = "http://127.0.0.1:8000"
    assistant_allow_delete: bool = False  # the assistant can't delete todos unless you turn this on
    # Origins allowed to call the API from a browser (the bundled frontend is same-origin, so none needed)
    cors_origins: list[str] = []


settings = Settings()
