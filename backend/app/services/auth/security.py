"""Password hashing and JWT issuance."""
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import jwt
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

_DEFAULT_SECRET = "change-me-in-production-linkwise-graph"
JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_ALGORITHM = "HS256"
JWT_ISSUER = "linkwise-graph"
JWT_AUDIENCE = "linkwise-web"
# Short-lived access tokens (hours, not the previous 14 days). Server-side
# revocation is via the per-user token_version claim (see UserStore).
ACCESS_TOKEN_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "12"))


def require_jwt_secret() -> str:
    """Fail fast: never run with a missing/default JWT secret (BUG-01).

    The previous fallback let anyone forge a token for any user from the
    public source code.
    """
    if not JWT_SECRET or JWT_SECRET == _DEFAULT_SECRET or len(JWT_SECRET) < 32:
        raise RuntimeError(
            "JWT_SECRET must be set to a private random value of at least 32 "
            "characters. Generate one and set it in the environment/.env; "
            "never use the old public default."
        )
    return JWT_SECRET


# Validate at import so the server refuses to start misconfigured.
require_jwt_secret()


def hash_password(password: str) -> str:
    if len(password.encode("utf-8")) > 72:
        raise ValueError("Password must be at most 72 bytes when UTF-8 encoded")
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# Pre-computed dummy hash so login timing does not reveal whether an
# account exists (BUG-08): unknown users still pay a bcrypt verify.
_DUMMY_HASH = pwd_context.hash("dummy-password-for-constant-time-login")


def verify_dummy(password: str) -> None:
    try:
        pwd_context.verify(password, _DUMMY_HASH)
    except Exception:  # noqa: BLE001 - timing only, result discarded
        pass


def create_access_token(subject: str, token_version: int = 0, extra: Dict[str, Any] | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload: Dict[str, Any] = {
        "sub": subject,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "tv": token_version,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Dict[str, Any]:
    return jwt.decode(
        token,
        JWT_SECRET,
        algorithms=[JWT_ALGORITHM],
        issuer=JWT_ISSUER,
        audience=JWT_AUDIENCE,
    )
