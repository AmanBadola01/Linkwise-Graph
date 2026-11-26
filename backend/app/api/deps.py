"""FastAPI dependencies."""
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.app.core.tenant import current_account_id
from backend.app.services.auth.security import decode_access_token
from backend.app.services.auth.user_store import UserRecord, UserStore

bearer_scheme = HTTPBearer(auto_error=False)
_user_store: UserStore | None = None

SESSION_COOKIE = "lw_session"


def get_user_store() -> UserStore:
    global _user_store
    if _user_store is None:
        _user_store = UserStore()
    return _user_store


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    store: Annotated[UserStore, Depends(get_user_store)],
) -> UserRecord:
    # Accept either an Authorization bearer token (API clients) or the
    # HttpOnly session cookie (browser, BUG-06).
    token: str | None = None
    if credentials is not None and credentials.scheme.lower() == "bearer":
        token = credentials.credentials
    if not token:
        token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user_id = payload.get("sub")
    if not user_id or not isinstance(user_id, str):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    user = store.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    # Revocation: tokens issued before a logout/password change carry an old
    # token_version and are rejected (BUG-06).
    if int(payload.get("tv", 0)) != user.token_version:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session revoked. Please sign in again")

    current_account_id.set(user.id)
    return user
