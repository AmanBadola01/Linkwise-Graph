"""SQLite-backed user accounts."""
import os
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from backend.app.services.auth.security import hash_password, verify_password, verify_dummy

DEFAULT_DB = os.getenv(
    "AUTH_DB_PATH",
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..",
        "..",
        "..",
        "..",
        "data",
        "auth.db",
    ),
)


@dataclass
class UserRecord:
    id: str
    email: str
    display_name: str
    created_at: str
    token_version: int = 0


class UserStore:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = os.path.abspath(db_path or DEFAULT_DB)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    display_name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            # Server-side token revocation (BUG-06): bumping token_version
            # invalidates every previously issued token for that user.
            cols = {row[1] for row in conn.execute("PRAGMA table_info(users)")}
            if "token_version" not in cols:
                conn.execute("ALTER TABLE users ADD COLUMN token_version INTEGER NOT NULL DEFAULT 0")
            conn.commit()

    def create_user(self, email: str, password: str, display_name: str) -> UserRecord:
        normalized = email.strip().lower()
        user_id = str(uuid.uuid4())
        created = datetime.now(timezone.utc).isoformat()
        password_hash = hash_password(password)
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO users (id, email, display_name, password_hash, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (user_id, normalized, display_name.strip(), password_hash, created),
                )
                conn.commit()
        except sqlite3.IntegrityError:
            raise ValueError("An account with this email already exists")
        return UserRecord(id=user_id, email=normalized, display_name=display_name.strip(), created_at=created)

    def authenticate(self, email: str, password: str) -> Optional[UserRecord]:
        normalized = email.strip().lower()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, email, display_name, password_hash, created_at, token_version FROM users WHERE email = ?",
                (normalized,),
            ).fetchone()
        if not row:
            # Constant-time-ish: always pay a bcrypt verify (BUG-08).
            verify_dummy(password)
            return None
        if not verify_password(password, row["password_hash"]):
            return None
        return UserRecord(
            id=row["id"],
            email=row["email"],
            display_name=row["display_name"],
            created_at=row["created_at"],
            token_version=int(row["token_version"] or 0),
        )

    def get_by_id(self, user_id: str) -> Optional[UserRecord]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, email, display_name, created_at, token_version FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
        if not row:
            return None
        return UserRecord(
            id=row["id"],
            email=row["email"],
            display_name=row["display_name"],
            created_at=row["created_at"],
            token_version=int(row["token_version"] or 0),
        )

    def bump_token_version(self, user_id: str) -> int:
        """Invalidate all existing tokens for a user (logout / pw change)."""
        with self._connect() as conn:
            conn.execute(
                "UPDATE users SET token_version = token_version + 1 WHERE id = ?",
                (user_id,),
            )
            conn.commit()
            row = conn.execute(
                "SELECT token_version FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        return int(row["token_version"]) if row else 0

    def change_password(self, user_id: str, new_password: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE users SET password_hash = ?, token_version = token_version + 1 WHERE id = ?",
                (hash_password(new_password), user_id),
            )
            conn.commit()