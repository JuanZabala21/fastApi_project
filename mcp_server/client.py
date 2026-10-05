"""Thin HTTP client for the Todo API. Logs in with a restricted `todos` token and renews it when it expires."""
import httpx

from mcp_server.security import McpConfig

# Messages shown to the model. Raw API / network errors never reach it (they could leak internals).
_ERRORS = {
    400: "The API rejected the request",
    401: "Authentication with the API failed",
    403: "Not allowed",
    404: "Todo not found",
    422: "Invalid data",
    429: "The API is rate limiting us, try again later",
}


class ApiError(RuntimeError):
    pass


class TodoApiClient:
    def __init__(self, config: McpConfig, http: httpx.Client | None = None) -> None:
        self._config = config
        # Short timeout; no redirects (a redirect could send our token to another host).
        self._http = http or httpx.Client(base_url=config.api_url, timeout=10.0, follow_redirects=False)
        # With a ready-made token there is no password to log in again with, so it can't be renewed.
        self._token: str | None = config.access_token or None

    def _login(self) -> None:
        try:
            res = self._http.post(
                "/auth/login",
                data={"username": self._config.email, "password": self._config.password, "scope": "todos"},
            )
        except httpx.HTTPError:
            raise ApiError("Can't reach the API") from None
        if res.status_code != 200:
            raise ApiError(_ERRORS.get(res.status_code, "Login failed"))
        self._token = res.json()["access_token"]

    def request(self, method: str, path: str, **kwargs):
        for attempt in (1, 2):
            if self._token is None:
                self._login()
            try:
                res = self._http.request(
                    method, path, headers={"Authorization": f"Bearer {self._token}"}, **kwargs
                )
            except httpx.HTTPError:
                raise ApiError("Can't reach the API") from None
            if res.status_code == 401 and attempt == 1 and not self._config.access_token:
                self._token = None  # expired: log in again once
                continue
            break
        if res.status_code >= 400:
            raise ApiError(_ERRORS.get(res.status_code, f"API error ({res.status_code})"))
        return None if res.status_code == 204 else res.json()
