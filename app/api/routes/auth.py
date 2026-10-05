from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import CurrentUser, DbDep
from app.core.config import settings
from app.core.rate_limit import login_throttle
from app.core.security import SCOPE_FULL, VALID_SCOPES, create_access_token
from app.schemas.user import Token, UserRead
from app.services import user_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(request: Request, form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DbDep):
    """Send `scope=todos` to get a restricted token that can only use /todos (what the MCP server does)."""
    # OAuth2 sends scopes as one space-separated string; none requested = full access.
    if len(form.scopes) > 1 or not set(form.scopes) <= VALID_SCOPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid scope")
    scope = form.scopes[0] if form.scopes else SCOPE_FULL

    key = f"{request.client.host if request.client else '?'}|{form.username.lower()}"
    wait = login_throttle.retry_after(key, settings.login_max_attempts, settings.login_window_seconds)
    if wait:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many failed attempts, try again later",
            headers={"Retry-After": str(wait)},
        )

    # The OAuth2 standard calls the field "username"; we use the email there.
    user = user_service.authenticate(db, form.username, form.password)
    if user is None or not user.is_active:
        login_throttle.record_failure(key)
        # Same message for "unknown email" and "wrong password" so attackers can't tell which
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    login_throttle.reset(key)
    return Token(access_token=create_access_token(str(user.id), scope))


@router.get("/me", response_model=UserRead)
def me(current_user: CurrentUser):
    return current_user
