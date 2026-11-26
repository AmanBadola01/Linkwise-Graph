"""Content-hash dedupe for ingest (BUG-14).

Records successful ingests by (account_id, sha256). Re-uploading identical
bytes returns the stored result instead of re-running (and re-billing)
Gemini extraction. clear_existing removes the record so a forced re-ingest
really re-runs.
"""
import json
import os
import sqlite3
from typing import Optional

_DB = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "data", "ingest.db"
)


def _connect() -> sqlite3.Connection:
    path = os.path.abspath(_DB)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ingests (
            account_id TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            filename TEXT NOT NULL,
            result_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (account_id, sha256)
        )
        """
    )
    return conn


def get_ingest_result(account_id: str, sha256: str) -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT result_json FROM ingests WHERE account_id = ? AND sha256 = ?",
            (account_id, sha256),
        ).fetchone()
    return json.loads(row[0]) if row else None


def record_ingest(account_id: str, sha256: str, filename: str, result: dict) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO ingests (account_id, sha256, filename, result_json) VALUES (?, ?, ?, ?)",
            (account_id, sha256, filename, json.dumps(result)),
        )
        conn.commit()


def clear_ingests(account_id: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM ingests WHERE account_id = ?", (account_id,))
        conn.commit()
