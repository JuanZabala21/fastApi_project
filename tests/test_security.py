"""Token scopes, login throttling, timing-safe login and security headers."""
import jwt

from app.core.config import settings
from tests.helpers import login, register


def _todos_token(client, email="ana@example.com"):
    r = client.post("/auth/login", data={"username": email, "password": "supersecret", "scope": "todos"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_todos_scope_can_only_use_todos(client):
    register(client)
    h = _todos_token(client)
    assert client.post("/todos", json={"title": "x"}, headers=h).status_code == 201
    assert client.get("/todos", headers=h).status_code == 200
    # but nothing else
    assert client.get("/auth/me", headers=h).status_code == 403
    assert client.get("/users", headers=h).status_code == 403
    assert client.delete("/users/1", headers=h).status_code == 403
    assert client.patch("/users/1", json={"full_name": "x"}, headers=h).status_code == 403


def test_invalid_scope_rejected(client):
    register(client)
    for scope in ("admin", "todos full"):
        r = client.post("/auth/login", data={"username": "ana@example.com", "password": "supersecret", "scope": scope})
        assert r.status_code == 400


def test_malformed_tokens_rejected(client):
    register(client)
    key, alg = settings.secret_key, settings.algorithm
    tokens = [
        jwt.encode({"sub": "1"}, key, algorithm=alg),  # no exp
        jwt.encode({"sub": "1", "scope": "root", "exp": 9999999999}, key, algorithm=alg),  # unknown scope
        jwt.encode({"sub": "abc", "exp": 9999999999}, key, algorithm=alg),  # non-numeric id
    ]
    for t in tokens:
        assert client.get("/todos", headers={"Authorization": f"Bearer {t}"}).status_code == 401


def test_login_is_throttled_after_repeated_failures(client):
    register(client)
    for _ in range(settings.login_max_attempts):
        assert login(client, password="wrong-password").status_code == 401
    r = login(client)  # even the right password is blocked while locked out
    assert r.status_code == 429
    assert int(r.headers["retry-after"]) > 0
    # another account is not affected
    register(client, email="bob@example.com")
    assert login(client, email="bob@example.com").status_code == 200


def test_successful_login_resets_counter(client):
    register(client)
    for _ in range(settings.login_max_attempts - 1):
        login(client, password="wrong-password")
    assert login(client).status_code == 200
    assert login(client, password="wrong-password").status_code == 401  # counter started again


def test_security_headers(client):
    r = client.get("/todos")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["cache-control"] == "no-store"
    app_page = client.get("/app/")
    assert app_page.status_code == 200
    assert "frame-ancestors 'none'" in app_page.headers["content-security-policy"]


def test_frontend_is_served(client):
    assert client.get("/app/app.js").status_code == 200
    assert client.get("/", follow_redirects=False).headers["location"] == "/app/"
