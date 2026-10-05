"""Shared dependencies (dependency injection)."""
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import SCOPE_FULL, SCOPE_TODOS, decode_access_token
from app.db.session import get_db
from app.models.user import User
from app.services import user_service

# --- Database + authentication ----------------------------------------------
DbDep = Annotated[Session, Depends(get_db)]

# Reads the "Authorization: Bearer <token>" header; tokenUrl powers the Authorize button in /docs
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def _authenticate(token: str, db: Session, allowed_scopes: set[str]) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    decoded = decode_access_token(token)
    if decoded is None:
        raise credentials_error
    user_id, scope = decoded
    if scope not in allowed_scopes:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This token is not allowed to use this endpoint")
    try:
        user = user_service.get_by_id(db, int(user_id))
    except ValueError:
        raise credentials_error
    if user is None or not user.is_active:
        raise credentials_error
    return user


def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: DbDep) -> User:
    """Full-access tokens only (users, /auth/me)."""
    return _authenticate(token, db, {SCOPE_FULL})


def get_todo_user(token: Annotated[str, Depends(oauth2_scheme)], db: DbDep) -> User:
    """Full tokens and restricted "todos" tokens (e.g. the MCP server) may manage todos."""
    return _authenticate(token, db, {SCOPE_FULL, SCOPE_TODOS})


CurrentUser = Annotated[User, Depends(get_current_user)]
TodoUser = Annotated[User, Depends(get_todo_user)]
