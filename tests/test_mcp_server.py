"""MCP server: tools go through the API with a restricted token, inputs are validated."""
import asyncio

import pytest

from mcp_server.client import ApiError, TodoApiClient
from mcp_server.security import ConfigError, McpConfig, RateLimiter, clean_title
from mcp_server.server import build_server
from tests.helpers import register


def make_config(**kw):
    base = dict(api_url="http://testserver", email="ana@example.com", password="supersecret",
                allow_delete=False, rate_limit_per_minute=100)
    return McpConfig(**{**base, **kw})


@pytest.fixture
def make_server(client):
    register(client)

    def factory(**kw):
        config = make_config(**kw)
        return build_server(config, TodoApiClient(config, http=client))

    return factory


def call(server, name, **args):
    """Returns True if the tool call failed."""
    try:
        result = asyncio.run(server.call_tool(name, args))
    except Exception:
        return True
    return bool(getattr(result, "is_error", getattr(result, "isError", False)))


def _headers(client):
    r = client.post("/auth/login", data={"username": "ana@example.com", "password": "supersecret"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_tools_allowlist_hides_delete_by_default(make_server):
    names = {t.name for t in asyncio.run(make_server().list_tools())}
    assert names == {"get_today", "list_todos", "create_todo", "create_todos", "set_todo_done", "rename_todo", "schedule_todo", "plan_todos"}
    names = {t.name for t in asyncio.run(make_server(allow_delete=True).list_tools())}
    assert "delete_todo" in names


def test_create_list_and_update(make_server, client):
    server = make_server()
    assert not call(server, "create_todo", title="  buy milk‮ ")
    todos = client.get("/todos", headers=_headers(client)).json()
    assert todos == [{"id": 1, "title": "buy milk", "done": False, "due_date": None, "priority": "medium"}]  # invisible chars stripped
    assert not call(server, "set_todo_done", todo_id=1, done=True)
    assert not call(server, "rename_todo", todo_id=1, title="buy oat milk")
    assert not call(server, "list_todos", done=True)
    assert client.get("/todos/1", headers=_headers(client)).json()["title"] == "buy oat milk"


def test_validation_errors(make_server):
    server = make_server()
    assert call(server, "create_todo", title="   ")
    assert call(server, "create_todo", title="x" * 101)
    assert call(server, "set_todo_done", todo_id=0)
    assert call(server, "set_todo_done", todo_id=2**40)
    assert call(server, "list_todos", limit=1000)
    assert call(server, "set_todo_done", todo_id=999)  # 404 -> safe message


def test_mcp_token_cannot_reach_user_endpoints(client):
    register(client)
    api = TodoApiClient(make_config(), http=client)
    with pytest.raises(ApiError, match="Not allowed"):
        api.request("GET", "/users")


def test_delete_only_when_enabled(make_server, client):
    server = make_server(allow_delete=True)
    assert not call(server, "create_todo", title="tmp")
    assert not call(server, "delete_todo", todo_id=1)
    assert client.get("/todos/1", headers=_headers(client)).status_code == 404


def test_rate_limit(make_server):
    server = make_server(rate_limit_per_minute=2)
    assert not call(server, "list_todos")
    assert not call(server, "list_todos")
    assert call(server, "list_todos")


def test_errors_do_not_leak_credentials(client):
    register(client)
    api = TodoApiClient(make_config(password="wrong-password"), http=client)
    with pytest.raises(ApiError) as exc:
        api.request("GET", "/todos")
    assert "wrong-password" not in str(exc.value) and "supersecret" not in str(exc.value)


def test_config_from_env(monkeypatch):
    monkeypatch.delenv("MCP_EMAIL", raising=False)
    monkeypatch.delenv("MCP_PASSWORD", raising=False)
    with pytest.raises(ConfigError):
        McpConfig.from_env()
    monkeypatch.setenv("MCP_EMAIL", "a@b.co")
    monkeypatch.setenv("MCP_PASSWORD", "pw")
    monkeypatch.setenv("MCP_API_URL", "http://api.example.com")  # plain http to a remote host
    with pytest.raises(ConfigError):
        McpConfig.from_env()
    monkeypatch.setenv("MCP_API_URL", "https://api.example.com/")
    assert McpConfig.from_env().api_url == "https://api.example.com"


def test_helpers():
    assert clean_title("hi\x00 there") == "hi there"
    limiter = RateLimiter(1)
    limiter.check()
    with pytest.raises(RuntimeError):
        limiter.check()


def test_mcp_schedule_filter_and_plan(make_server, client):
    from datetime import date, timedelta

    server = make_server()
    soon = (date.today() + timedelta(days=1)).isoformat()
    assert not call(server, "create_todo", title="a", due_date=soon, priority="high")
    assert not call(server, "create_todo", title="b")
    assert not call(server, "schedule_todo", todo_id=2, due_date=soon, priority="low")
    assert not call(server, "schedule_todo", todo_id=2, clear_due_date=True)
    assert not call(server, "list_todos", priority="high", due_from=soon, sort_by="due_date", overdue=False)

    h = _headers(client)
    assert client.get("/todos/2", headers=h).json()["due_date"] is None
    assert not call(server, "plan_todos", plan=[{"todo_id": 1, "priority": "low"}, {"todo_id": 2, "due_date": soon}])
    assert client.get("/todos/1", headers=h).json()["priority"] == "low"
    assert client.get("/todos/2", headers=h).json()["due_date"] == soon
    assert not call(server, "get_today")


def test_mcp_schedule_validation(make_server):
    server = make_server()
    call(server, "create_todo", title="a")
    assert call(server, "create_todo", title="x", due_date="2026-02-30")
    assert call(server, "create_todo", title="x", due_date="3000-01-01")
    assert call(server, "create_todo", title="x", priority="urgent")
    assert call(server, "schedule_todo", todo_id=1)  # nothing to change
    assert call(server, "schedule_todo", todo_id=1, due_date="2026-01-01", clear_due_date=True)
    assert call(server, "list_todos", sort_by="title")
    assert call(server, "list_todos", due_from="yesterday")
    assert call(server, "plan_todos", plan=[])
    assert call(server, "plan_todos", plan=[{"todo_id": 1, "priority": "low"}] * 26)


def test_plan_is_validated_before_applying(make_server, client):
    server = make_server()
    call(server, "create_todo", title="a")
    bad = [{"todo_id": 1, "priority": "high"}, {"todo_id": 1, "due_date": "nope"}]
    assert call(server, "plan_todos", plan=bad)
    assert client.get("/todos/1", headers=_headers(client)).json()["priority"] == "medium"  # nothing applied
