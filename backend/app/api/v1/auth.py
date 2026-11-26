"""Signup, login, logout, password change, and session introspection."""
import logging
import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from backend.app.api.deps import SESSION_COOKIE, get_current_user, get_user_store
from backend.app.schemas.api_schemas import (
    AuthResponse,
    ChangePasswordRequest,
    LoginRequest,
    SignupRequest,
    UserPublic,
)
from backend.app.services.auth.rate_limit import check_rate_limit, reset_rate_limit
from backend.app.services.auth.security import ACCESS_TOKEN_EXPIRE_HOURS, create_access_token
from backend.app.services.auth.user_store import UserRecord, UserStore

logger = logging.getLogger("graphrag.api.auth")

router = APIRouter(prefix="/auth", tags=["Auth"])

_COOKIE_SECURE = os.getenv("COOKIE_SECURE", "").lower() in ("1", "true", "yes")


def _public_user(user: UserRecord) -> UserPublic:
    return UserPublic(id=user.id, email=user.email, display_name=user.display_name)


def _issue_session(response: Response, user: UserRecord) -> str:
    token = create_access_token(user.id, token_version=user.token_version)
    # HttpOnly session cookie: JS cannot read it (BUG-06). The bearer token
    # is still returned in the body for API clients.
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=ACCESS_TOKEN_EXPIRE_HOURS * 3600,
        httponly=True,
        samesite="lax",
        secure=_COOKIE_SECURE,
        path="/",
    )
    return token


def _client_key(request: Request, suffix: str) -> str:
    host = request.client.host if request.client else "unknown"
    return f"{suffix}:{host}"


def _enforce_limit(key: str, limit: int, window: float) -> None:
    wait = check_rate_limit(key, limit, window)
    if wait:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Please wait and try again.",
            headers={"Retry-After": str(int(wait))},
        )


@router.post("/signup", response_model=AuthResponse, summary="Create account")
async def signup(
    body: SignupRequest,
    request: Request,
    response: Response,
    store: Annotated[UserStore, Depends(get_user_store)],
) -> AuthResponse:
    _enforce_limit(_client_key(request, "signup"), limit=10, window=3600)
    try:
        user = store.create_user(body.email, body.password, body.display_name)
    except ValueError as e:
        message = str(e)
        if "already exists" in message:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=message)
    logger.info("New account registered: %s", user.id)
    token = _issue_session(response, user)
    return AuthResponse(access_token=token, user=_public_user(user))


@router.post("/login", response_model=AuthResponse, summary="Sign in")
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    store: Annotated[UserStore, Depends(get_user_store)],
) -> AuthResponse:
    # Throttle per IP+account: credential stuffing gets 429 (BUG-07).
    key = f"{_client_key(request, 'login')}:{body.email}"
    _enforce_limit(key, limit=5, window=300)
    user = store.authenticate(body.email, body.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    reset_rate_limit(key)
    token = _issue_session(response, user)
    return AuthResponse(access_token=token, user=_public_user(user))


@router.post("/logout", summary="Sign out (revokes all sessions server-side)")
async def logout(
    response: Response,
    current_user: Annotated[UserRecord, Depends(get_current_user)],
    store: Annotated[UserStore, Depends(get_user_store)],
) -> dict:
    # Bumping token_version revokes every outstanding token, not just the
    # local copies the browser deletes (BUG-06).
    store.bump_token_version(current_user.id)
    response.delete_cookie(key=SESSION_COOKIE, path="/")
    return {"status": "signed_out"}


@router.post("/change-password", response_model=AuthResponse, summary="Change password (revokes other sessions)")
async def change_password(
    body: ChangePasswordRequest,
    response: Response,
    current_user: Annotated[UserRecord, Depends(get_current_user)],
    store: Annotated[UserStore, Depends(get_user_store)],
) -> AuthResponse:
    verified = store.authenticate(current_user.email, body.current_password)
    if not verified:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Current password is incorrect")
    store.change_password(current_user.id, body.new_password)
    refreshed = store.get_by_id(current_user.id)
    assert refreshed is not None
    token = _issue_session(response, refreshed)
    return AuthResponse(access_token=token, user=_public_user(refreshed))


@router.get("/me", response_model=UserPublic, summary="Current user")
async def me(current_user: Annotated[UserRecord, Depends(get_current_user)]) -> UserPublic:
    return _public_user(current_user)
