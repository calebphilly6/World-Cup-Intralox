from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from src.database import DB_PATH, get_connection


def refresh_was_completed(provider: str, resource: str, refresh_key: str, db_path: Path = DB_PATH) -> bool:
    metadata_key = _metadata_key(provider, resource)
    with get_connection(db_path) as conn:
        row = conn.execute("SELECT value FROM app_metadata WHERE key = ?", (metadata_key,)).fetchone()
    return bool(row and row["value"] == refresh_key)


def mark_refresh_completed(provider: str, resource: str, refresh_key: str, db_path: Path = DB_PATH) -> None:
    metadata_key = _metadata_key(provider, resource)
    refreshed_at = datetime.now(timezone.utc).isoformat()
    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO app_metadata (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (metadata_key, refresh_key, refreshed_at),
        )
        conn.commit()


def _metadata_key(provider: str, resource: str) -> str:
    clean_provider = _clean_key_part(provider)
    clean_resource = _clean_key_part(resource)
    return f"api_refresh:{clean_provider}:{clean_resource}"


def _clean_key_part(value: str) -> str:
    return str(value).strip().lower().replace(" ", "_")
