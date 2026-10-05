"""Small helpers shared by the test files."""


def register(client, email="ana@example.com", password="supersecret"):
    return client.post("/users", json={"email": email, "password": password, "full_name": "Ana"})


def login(client, email="ana@example.com", password="supersecret"):
    return client.post("/auth/login", data={"username": email, "password": password})


def auth_header(client, **kw):
    return {"Authorization": f"Bearer {login(client, **kw).json()['access_token']}"}
