"""Due dates, priorities, filters, sorting and the lightweight column migration."""
from datetime import date, timedelta

from sqlalchemy import create_engine, inspect, text

from app.db.session import ensure_columns
from tests.helpers import auth_header, register

TODAY = date.today()
D = lambda n: (TODAY + timedelta(days=n)).isoformat()  # noqa: E731


def _seed(client, h):
    rows = [
        {"title": "past high", "due_date": D(-2), "priority": "high"},
        {"title": "today low", "due_date": D(0), "priority": "low"},
        {"title": "next week med", "due_date": D(7)},
        {"title": "no date high", "priority": "high"},
        {"title": "past but done", "due_date": D(-5), "done": True},
    ]
    for row in rows:
        assert client.post("/todos", json=row, headers=h).status_code == 201


def _titles(client, h, **params):
    return [t["title"] for t in client.get("/todos", params=params, headers=h).json()]


def test_create_with_date_and_priority_and_clear_it(client):
    register(client)
    h = auth_header(client)
    todo = client.post("/todos", json={"title": "x", "due_date": D(3), "priority": "high"}, headers=h).json()
    assert todo["due_date"] == D(3) and todo["priority"] == "high"
    r = client.patch(f"/todos/{todo['id']}", json={"due_date": None}, headers=h)  # null clears the day
    assert r.json()["due_date"] is None and r.json()["priority"] == "high"
    r = client.patch(f"/todos/{todo['id']}", json={"title": "y"}, headers=h)  # leaving it out keeps things
    assert r.json()["title"] == "y"


def test_invalid_values_rejected(client):
    register(client)
    h = auth_header(client)
    assert client.post("/todos", json={"title": "x", "priority": "urgent"}, headers=h).status_code == 422
    assert client.post("/todos", json={"title": "x", "due_date": "2026-13-45"}, headers=h).status_code == 422
    client.post("/todos", json={"title": "x"}, headers=h)
    for body in ({"priority": None}, {"title": None}, {"done": None}):  # NOT NULL columns: 422, not 500
        assert client.patch("/todos/1", json=body, headers=h).status_code == 422


def test_filters(client):
    register(client)
    h = auth_header(client)
    _seed(client, h)
    assert _titles(client, h, priority="high") == ["past high", "no date high"]
    assert _titles(client, h, overdue=True) == ["past high"]  # done ones are not overdue
    assert _titles(client, h, due_from=D(0), due_to=D(7)) == ["today low", "next week med"]
    assert _titles(client, h, has_due_date=False) == ["no date high"]
    assert _titles(client, h, has_due_date=True, done=False) == ["past high", "today low", "next week med"]
    assert _titles(client, h, priority="high", overdue=True) == ["past high"]


def test_sorting(client):
    register(client)
    h = auth_header(client)
    _seed(client, h)
    assert _titles(client, h, sort_by="due_date") == [
        "past but done", "past high", "today low", "next week med", "no date high"
    ]  # undated last
    by_priority = _titles(client, h, sort_by="priority")
    assert by_priority[:2] == ["past high", "no date high"]  # high first, dated before undated
    assert by_priority[-1] == "today low"
    assert client.get("/todos", params={"sort_by": "title"}, headers=h).status_code == 422


def test_filters_only_see_own_todos(client):
    register(client)
    register(client, email="bob@example.com")
    client.post("/todos", json={"title": "ana's", "priority": "high"}, headers=auth_header(client))
    bob = auth_header(client, email="bob@example.com")
    assert _titles(client, bob, priority="high") == []


def test_ensure_columns_upgrades_an_old_table():
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE todos (id INTEGER PRIMARY KEY, title VARCHAR(100), done BOOLEAN, user_id INTEGER)"))
        conn.execute(text("INSERT INTO todos (title, done, user_id) VALUES ('old', 0, 1)"))
    ensure_columns(engine)
    ensure_columns(engine)  # idempotent
    assert {"due_date", "priority"} <= {c["name"] for c in inspect(engine).get_columns("todos")}
    with engine.connect() as conn:
        assert conn.execute(text("SELECT priority, due_date FROM todos")).one() == ("medium", None)
