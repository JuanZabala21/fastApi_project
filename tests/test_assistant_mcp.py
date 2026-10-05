"""Chat in MCP mode: FastAPI is the MCP client of our MCP server, which calls the REST API.

The Anthropic client is scripted (no credits). The "network" hop MCP server -> REST API is the TestClient.
"""
import httpx
import pytest

from app.api.routes import assistant as assistant_route
from app.core.config import settings
from app.main import app
from app.services import assistant_mcp
from tests.helpers import auth_header, register
from tests.test_assistant import FakeClient, reply, text, tool


@pytest.fixture(autouse=True)
def _mcp_mode(client, monkeypatch):
    monkeypatch.setattr(settings, "assistant_mode", "mcp")
    monkeypatch.setattr(assistant_mcp, "_api_http", lambda: client)  # MCP server -> REST API


@pytest.fixture
def use_fake():
    def install(*responses):
        fake = FakeClient(*responses)
        app.dependency_overrides[assistant_route._client] = lambda: fake
        return fake

    yield install
    app.dependency_overrides.pop(assistant_route._client, None)


def chat(client, h, content="hi"):
    return client.post("/assistant/chat", json={"messages": [{"role": "user", "content": content}]}, headers=h)


def tool_results(fake, call_index):
    return fake.calls[call_index]["messages"][-1]["content"]


def test_tools_offered_to_claude_come_from_the_mcp_server(client, use_fake):
    register(client)
    fake = use_fake(reply(text("ok")))
    chat(client, auth_header(client))
    names = {t["name"] for t in fake.calls[0]["tools"]}
    assert {"get_today", "list_todos", "create_todos", "plan_todos", "schedule_todo"} <= names
    assert "delete_todo" not in names  # off by default, decided by the MCP server
    assert all(t["input_schema"]["type"] == "object" for t in fake.calls[0]["tools"])


def test_claude_creates_and_plans_todos_through_mcp(client, use_fake):
    register(client)
    h = auth_header(client)
    fake = use_fake(
        reply(tool("create_todos", {"items": [{"title": "buy milk", "priority": "high"}, {"title": "call mom"}]}),
              stop="tool_use"),
        reply(tool("plan_todos", {"plan": [{"todo_id": 2, "due_date": "2030-05-06"}]}), stop="tool_use"),
        reply(text("done")),
    )
    r = chat(client, h)
    assert r.status_code == 200 and r.json()["reply"] == "done" and r.json()["changed"] is True
    assert r.json()["actions"] == ["create_todos", "plan_todos"]
    todos = client.get("/todos", headers=h).json()
    assert [(t["title"], t["priority"], t["due_date"]) for t in todos] == [
        ("buy milk", "high", None),
        ("call mom", "medium", "2030-05-06"),
    ]
    assert not tool_results(fake, 1)[0]["is_error"]


def test_read_only_calls_do_not_report_changes(client, use_fake):
    register(client)
    h = auth_header(client)
    client.post("/todos", json={"title": "a"}, headers=h)
    use_fake(reply(tool("list_todos", {"sort_by": "due_date"}), stop="tool_use"), reply(text("1 task")))
    r = chat(client, h)
    assert r.json()["changed"] is False


def test_validation_errors_reach_the_model_with_their_reason(client, use_fake):
    register(client)
    fake = use_fake(
        reply(
            tool("create_todo", {"title": "x" * 200}, "a"),
            tool("list_todos", {"due_from": "tomorrow"}, "b"),
            tool("schedule_todo", {"todo_id": 999, "priority": "high"}, "c"),
            tool("no_such_tool", {}, "d"),
            stop="tool_use",
        ),
        reply(text("sorry")),
    )
    chat(client, auth_header(client))
    out = tool_results(fake, 1)
    assert out[0]["is_error"] and "too long" in out[0]["content"]  # the reason, not "Error executing tool"
    assert out[1]["is_error"] and "YYYY-MM-DD" in out[1]["content"]
    assert out[2]["is_error"] and "not found" in out[2]["content"].lower()
    assert out[3]["is_error"]


def test_it_acts_only_as_the_logged_in_user(client, use_fake):
    register(client)
    register(client, email="bob@example.com")
    bob = auth_header(client, email="bob@example.com")
    client.post("/todos", json={"title": "bob's"}, headers=bob)
    fake = use_fake(
        reply(tool("list_todos", {}, "a"), tool("schedule_todo", {"todo_id": 1, "priority": "low"}, "b"),
              stop="tool_use"),
        reply(text("ok")),
    )
    r = chat(client, auth_header(client))  # ana
    assert r.json()["changed"] is False
    out = tool_results(fake, 1)
    assert out[0]["content"].strip() in ("[]", '{\n  "result": []\n}') or '"bob' not in out[0]["content"]
    assert out[1]["is_error"]
    assert client.get("/todos", headers=bob).json()[0]["priority"] == "medium"


def test_delete_tool_only_when_enabled(client, use_fake, monkeypatch):
    register(client)
    h = auth_header(client)
    client.post("/todos", json={"title": "a"}, headers=h)
    monkeypatch.setattr(settings, "assistant_allow_delete", True)
    fake = use_fake(reply(tool("delete_todo", {"todo_id": 1}), stop="tool_use"), reply(text("deleted")))
    r = chat(client, h)
    assert "delete_todo" in {t["name"] for t in fake.calls[0]["tools"]}
    assert r.json()["changed"] is True and client.get("/todos", headers=h).json() == []


def test_unreachable_api_is_reported_without_details(client, use_fake, monkeypatch):
    register(client)
    monkeypatch.setattr(assistant_mcp, "_api_http", lambda: httpx.Client(base_url="http://127.0.0.1:1", timeout=2))
    fake = use_fake(reply(tool("list_todos", {}), stop="tool_use"), reply(text("can't")))
    r = chat(client, auth_header(client))
    assert r.status_code == 200
    out = tool_results(fake, 1)[0]
    assert out["is_error"] and "Can't reach the API" in out["content"] and "127.0.0.1" not in out["content"]


def test_loop_is_capped(client, use_fake):
    register(client)
    fake = use_fake(*[reply(tool("get_today", {}), stop="tool_use") for _ in range(8)])
    r = chat(client, auth_header(client))
    assert r.status_code == 200 and len(fake.calls) == 8


def test_language_reaches_the_prompt_in_mcp_mode(client, use_fake):
    register(client)
    fake = use_fake(reply(text("ok")), reply(text("ok")))
    h = auth_header(client)
    chat(client, h)
    client.post("/assistant/chat", json={"messages": [{"role": "user", "content": "hola"}], "lang": "es"}, headers=h)
    assert "Reply briefly in English" in fake.calls[0]["system"]
    assert "Reply briefly in Spanish" in fake.calls[1]["system"]
