"""Security helpers for the MCP server: config, input cleaning and a call rate limiter."""
import os
import re
import time
from collections import deque
from dataclasses import dataclass
from datetime import date
from threading import Lock
from urllib.parse import urlparse

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f​-‏‪-‮⁦-⁩]")
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}

MAX_TITLE_LEN = 100  # same limit as the API schema
MAX_LIMIT = 100
MAX_ID = 2**31 - 1  # Postgres INTEGER


class ConfigError(RuntimeError):
    pass


class RateLimitExceeded(RuntimeError):
    """Safe to show to the model: it only says to wait."""


@dataclass(frozen=True)
class McpConfig:
    api_url: str
    email: str
    password: str
    allow_delete: bool
    rate_limit_per_minute: int
    # Alternative to email+password: a ready-made restricted ("todos") token. The FastAPI backend uses this
    # when it embeds the server for a logged-in user, so it never needs (or sees) that user's password.
    access_token: str = ""

    @classmethod
    def from_env(cls) -> "McpConfig":
        """Credentials come from the environment (set in the MCP client config), never from tool arguments,
        so the model can't read or change them."""
        api_url = os.environ.get("MCP_API_URL", "http://127.0.0.1:8000").rstrip("/")
        email = os.environ.get("MCP_EMAIL", "")
        password = os.environ.get("MCP_PASSWORD", "")
        access_token = os.environ.get("MCP_ACCESS_TOKEN", "")
        if not access_token and (not email or not password):
            raise ConfigError("Set MCP_EMAIL and MCP_PASSWORD (use a dedicated account for the MCP server)")
        parsed = urlparse(api_url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ConfigError("MCP_API_URL must be an http(s) URL")
        if parsed.scheme == "http" and parsed.hostname not in _LOCAL_HOSTS:
            raise ConfigError("MCP_API_URL must use https unless it points to localhost")
        return cls(
            api_url=api_url,
            email=email,
            password=password,
            allow_delete=os.environ.get("MCP_ALLOW_DELETE", "").lower() in ("1", "true", "yes"),
            rate_limit_per_minute=int(os.environ.get("MCP_RATE_LIMIT", "30")),
            access_token=access_token,
        )


def clean_title(title: str) -> str:
    """Strips control / invisible bidi characters (used to hide text from humans) and validates the length."""
    if not isinstance(title, str):
        raise ValueError("title must be text")
    cleaned = _CONTROL_CHARS.sub("", title).strip()
    if not cleaned:
        raise ValueError("title can't be empty")
    if len(cleaned) > MAX_TITLE_LEN:
        raise ValueError(f"title is too long (max {MAX_TITLE_LEN} characters)")
    return cleaned


PRIORITIES = ("low", "medium", "high")
SORTS = ("id", "due_date", "priority")
MAX_PLAN_ITEMS = 25
MIN_YEAR, MAX_YEAR = 2000, 2100


def check_date(value: str) -> str:
    """Accepts only real ISO dates (YYYY-MM-DD) in a sane range; returns the normalized string."""
    if not isinstance(value, str):
        raise ValueError("dates must be text in YYYY-MM-DD format")
    try:
        parsed = date.fromisoformat(value.strip())
    except ValueError:
        raise ValueError("dates must be valid and in YYYY-MM-DD format") from None
    if not MIN_YEAR <= parsed.year <= MAX_YEAR:
        raise ValueError(f"date year must be between {MIN_YEAR} and {MAX_YEAR}")
    return parsed.isoformat()


def check_priority(value: str) -> str:
    if value not in PRIORITIES:
        raise ValueError(f"priority must be one of: {', '.join(PRIORITIES)}")
    return value


def check_sort(value: str) -> str:
    if value not in SORTS:
        raise ValueError(f"sort_by must be one of: {', '.join(SORTS)}")
    return value


def check_id(todo_id: int) -> int:
    if isinstance(todo_id, bool) or not isinstance(todo_id, int) or not 1 <= todo_id <= MAX_ID:
        raise ValueError("todo_id must be a positive integer")
    return todo_id


def check_limit(limit: int) -> int:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_LIMIT:
        raise ValueError(f"limit must be between 1 and {MAX_LIMIT}")
    return limit


class RateLimiter:
    """Sliding window: at most `max_calls` tool calls per `window` seconds (stops runaway loops)."""

    def __init__(self, max_calls: int, window: float = 60.0) -> None:
        self.max_calls = max_calls
        self.window = window
        self._calls: deque[float] = deque()
        self._lock = Lock()

    def check(self) -> None:
        now = time.monotonic()
        with self._lock:
            while self._calls and self._calls[0] < now - self.window:
                self._calls.popleft()
            if len(self._calls) >= self.max_calls:
                raise RateLimitExceeded("Rate limit reached, wait a minute before trying again")
            self._calls.append(now)
