"""Auth + users tests (the `client` fixture lives in conftest.py)."""
from tests.helpers import auth_header, login, register


def test_register_hides_password(client):
    r = register(client)
    assert r.status_code == 201
    assert r.json() == {"id": 1, "email": "ana@example.com", "full_name": "Ana", "is_active": True}


def test_duplicate_email_conflict(client):
    register(client)
    assert register(client).status_code == 409


def test_login_and_me(client):
    register(client)
    assert login(client, password="wrongpass1").status_code == 401
    assert login(client, email="nobody@example.com").status_code == 401
    r = client.get("/auth/me", headers=auth_header(client))
    assert r.status_code == 200 and r.json()["email"] == "ana@example.com"


def test_protected_routes_need_token(client):
    assert client.get("/users").status_code == 401
    assert client.get("/users", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_cannot_modify_other_users(client):
    register(client)
    register(client, email="bob@example.com")
    h = auth_header(client)
    assert client.patch("/users/2", json={"full_name": "x"}, headers=h).status_code == 403
    assert client.delete("/users/2", headers=h).status_code == 403


def test_update_and_delete_self(client):
    register(client)
    h = auth_header(client)
    r = client.patch("/users/1", json={"full_name": "Ana B", "password": "newpassword1"}, headers=h)
    assert r.json()["full_name"] == "Ana B"
    assert login(client, password="supersecret").status_code == 401
    assert login(client, password="newpassword1").status_code == 200
    assert client.delete("/users/1", headers=h).status_code == 204
    assert client.get("/users/1", headers=h).status_code == 401  # token's user no longer exists
