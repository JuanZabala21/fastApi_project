from tests.helpers import auth_header, register


def test_todos_require_login(client):
    assert client.get("/todos").status_code == 401
    assert client.post("/todos", json={"title": "x"}).status_code == 401


def test_crud_flow(client):
    register(client)
    h = auth_header(client)

    r = client.post("/todos", json={"title": "learn fastapi"}, headers=h)
    assert r.status_code == 201
    todo = r.json()
    assert todo == {"id": 1, "title": "learn fastapi", "done": False, "due_date": None, "priority": "medium"}

    assert client.get("/todos/1", headers=h).json() == todo

    r = client.patch("/todos/1", json={"done": True}, headers=h)
    assert r.json()["done"] is True

    assert len(client.get("/todos", params={"done": True}, headers=h).json()) == 1
    assert client.get("/todos", params={"done": False}, headers=h).json() == []

    assert client.delete("/todos/1", headers=h).status_code == 204
    assert client.get("/todos/1", headers=h).status_code == 404


def test_validation_error(client):
    register(client)
    h = auth_header(client)
    assert client.post("/todos", json={"title": ""}, headers=h).status_code == 422
    assert client.get("/todos", params={"limit": 0}, headers=h).status_code == 422


def test_users_only_see_their_own_todos(client):
    register(client)
    register(client, email="bob@example.com")
    ana, bob = auth_header(client), auth_header(client, email="bob@example.com")

    client.post("/todos", json={"title": "ana's todo"}, headers=ana)

    assert client.get("/todos", headers=bob).json() == []
    assert client.get("/todos/1", headers=bob).status_code == 404
    assert client.patch("/todos/1", json={"done": True}, headers=bob).status_code == 404
    assert client.delete("/todos/1", headers=bob).status_code == 404
    # Ana's todo is untouched
    assert client.get("/todos/1", headers=ana).json()["done"] is False


def test_deleting_user_deletes_their_todos(client):
    register(client)
    h = auth_header(client)
    client.post("/todos", json={"title": "bye"}, headers=h)
    assert client.delete("/users/1", headers=h).status_code == 204

    # Same email again gets a new user id; the old todo must be gone
    register(client)
    assert client.get("/todos", headers=auth_header(client)).json() == []


def test_delete_all_needs_confirmation_and_only_removes_own_todos(client):
    register(client)
    register(client, email="bob@example.com")
    ana, bob = auth_header(client), auth_header(client, email="bob@example.com")
    for title in ("a", "b", "c"):
        client.post("/todos", json={"title": title}, headers=ana)
    client.post("/todos", json={"title": "bob's"}, headers=bob)

    assert client.delete("/todos", headers=ana).status_code == 400  # no confirm
    assert client.delete("/todos", params={"confirm": False}, headers=ana).status_code == 400
    assert len(client.get("/todos", headers=ana).json()) == 3
    assert client.delete("/todos", params={"confirm": True}).status_code == 401

    r = client.delete("/todos", params={"confirm": True}, headers=ana)
    assert r.status_code == 200 and r.json() == {"deleted": 3}
    assert client.get("/todos", headers=ana).json() == []
    assert len(client.get("/todos", headers=bob).json()) == 1  # bob untouched
    assert client.delete("/todos", params={"confirm": True}, headers=ana).json() == {"deleted": 0}


def test_restricted_token_cannot_delete_all(client):
    register(client)
    r = client.post("/auth/login", data={"username": "ana@example.com", "password": "supersecret", "scope": "todos"})
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    client.post("/todos", json={"title": "a"}, headers=h)
    assert client.delete("/todos", params={"confirm": True}, headers=h).status_code == 403
    assert len(client.get("/todos", headers=h).json()) == 1
