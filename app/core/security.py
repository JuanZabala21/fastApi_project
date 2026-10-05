"""Password hashing and JWT creation/validation."""
from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

from app.core.config import settings

# Argon2 by default. We never store the plain password, only its hash.
_password_hash = PasswordHash.recommended()

# Verified when the email doesn't exist, so "unknown email" takes as long as "wrong password"
# and attackers can't enumerate accounts by timing the response.
DUMMY_HASH = _password_hash.hash("dummy-password-for-timing")


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return _password_hash.verify(password, hashed)


# "full" tokens can use the whole API. "todos" tokens (used by the MCP server) can only touch /todos,
# so a leaked MCP token can't read other users, change the password or delete the account.
SCOPE_FULL = "full"
SCOPE_TODOS = "todos"
VALID_SCOPES = {SCOPE_FULL, SCOPE_TODOS}


def create_access_token(subject: str, scope: str = SCOPE_FULL) -> str:
    """The token carries the user id ("sub"), its scope and an expiry ("exp"), signed with our secret."""
    minutes = settings.access_token_expire_minutes
    if scope == SCOPE_TODOS:
        minutes = min(minutes, settings.mcp_token_expire_minutes)  # restricted tokens live shorter
    expire = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    return jwt.encode(
        {"sub": subject, "scope": scope, "exp": expire}, settings.secret_key, algorithm=settings.algorithm
    )


def decode_access_token(token: str) -> tuple[str, str] | None:
    """Returns (user id, scope), or None if the token is invalid, expired or malformed."""
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm], options={"require": ["exp", "sub"]}
        )
    except jwt.InvalidTokenError:
        return None
    scope = payload.get("scope", SCOPE_FULL)
    if scope not in VALID_SCOPES:
        return None
    return payload["sub"], scope
