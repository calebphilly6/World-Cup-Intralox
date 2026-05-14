from __future__ import annotations

import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd

from src.config import DATA_DIR
from src.database import DB_PATH, fetch_df, get_connection


SNAPSHOT_DIR = DATA_DIR / "snapshots"
MANIFEST_NAME = "manifest.json"
METADATA_KEY = "core_snapshot_id"

# Tables that make up the shareable official/core data snapshot. Personal
# browser preferences are intentionally excluded.
CORE_SNAPSHOT_TABLES = (
    "teams",
    "venues",
    "groups",
    "fixtures",
    "match_city_reference",
    "fifa_rankings",
    "global_fifa_rankings",
    "standings",
    "odds_snapshots",
)


def export_core_snapshots(db_path: Path = DB_PATH, snapshot_dir: Path = SNAPSHOT_DIR) -> dict[str, int]:
    """Export API-refreshed core SQLite data to CSV files for hosted read loading."""
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    for table in CORE_SNAPSHOT_TABLES:
        df = fetch_df(f"SELECT * FROM {table}", db_path=db_path)
        df.to_csv(snapshot_dir / f"{table}.csv", index=False)
        counts[table] = len(df)
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "snapshot_id": _snapshot_id(snapshot_dir),
        "tables": counts,
    }
    (snapshot_dir / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return counts


def load_core_snapshots(db_path: Path = DB_PATH, snapshot_dir: Path = SNAPSHOT_DIR) -> dict[str, int]:
    """Load committed core CSV snapshots into the runtime SQLite database."""
    available = [table for table in CORE_SNAPSHOT_TABLES if (snapshot_dir / f"{table}.csv").exists()]
    if not available:
        return {}
    snapshot_id = _snapshot_id(snapshot_dir)

    loaded: dict[str, int] = {}
    with get_connection(db_path) as conn:
        current = conn.execute("SELECT value FROM app_metadata WHERE key = ?", (METADATA_KEY,)).fetchone()
        if current and current["value"] == snapshot_id:
            return {}

        conn.execute("PRAGMA foreign_keys = OFF")
        for table in reversed(CORE_SNAPSHOT_TABLES):
            if table in available:
                conn.execute(f"DELETE FROM {table}")

        for table in CORE_SNAPSHOT_TABLES:
            if table not in available:
                continue
            path = snapshot_dir / f"{table}.csv"
            try:
                df = pd.read_csv(path)
            except pd.errors.EmptyDataError:
                df = pd.DataFrame()
            if not df.empty:
                df = df.where(pd.notna(df), None)
                df.to_sql(table, conn, if_exists="append", index=False)
            loaded[table] = len(df)

        try:
            for table in available:
                conn.execute("DELETE FROM sqlite_sequence WHERE name = ?", (table,))
        except Exception:
            pass
        conn.execute(
            """
            INSERT INTO app_metadata (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
            """,
            (METADATA_KEY, snapshot_id),
        )
        conn.commit()
        conn.execute("PRAGMA foreign_keys = ON")
    return loaded


def core_snapshots_available(snapshot_dir: Path = SNAPSHOT_DIR) -> bool:
    return any((snapshot_dir / f"{table}.csv").exists() for table in CORE_SNAPSHOT_TABLES)


def _snapshot_id(snapshot_dir: Path) -> str:
    digest = hashlib.sha256()
    for table in CORE_SNAPSHOT_TABLES:
        path = snapshot_dir / f"{table}.csv"
        if not path.exists():
            continue
        digest.update(table.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()
