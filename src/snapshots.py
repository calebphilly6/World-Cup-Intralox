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
    "roster_players",
    "venues",
    "groups",
    "fixtures",
    "match_city_reference",
    "fifa_rankings",
    "global_fifa_rankings",
    "standings",
    "odds_snapshots",
    "fixture_odds_snapshots",
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
    """Load committed core CSV snapshots into the runtime SQLite database.

    Reboot-safe by design. The earlier version deleted every core table up front
    and then read each CSV, so a CSV that read back empty for any reason (a not
    yet hydrated OneDrive placeholder, a half written file, a parse error) wiped
    the table and left it empty. It also short-circuited whenever the stored
    snapshot id matched the CSV hash, so a database that was already empty but
    stamped (e.g. a persisted hosted container stamped during an earlier broken
    load) stayed empty on every subsequent reboot.

    This version reads and validates every CSV *before* touching the database,
    only replaces a table when its CSV actually parsed with rows, and reloads
    even on a hash match when an essential table is empty in the database while
    its CSV has data.
    """
    available = [table for table in CORE_SNAPSHOT_TABLES if (snapshot_dir / f"{table}.csv").exists()]
    if not available:
        return {}
    snapshot_id = _snapshot_id(snapshot_dir)

    # Read and validate everything up front so the database is never mutated on
    # the strength of a CSV that turned out to be empty or unreadable.
    frames: dict[str, pd.DataFrame] = {}
    read_error = False
    for table in available:
        path = snapshot_dir / f"{table}.csv"
        try:
            df = pd.read_csv(path)
        except pd.errors.EmptyDataError:
            df = pd.DataFrame()
        except Exception:
            # A genuinely unreadable file (e.g. an online-only placeholder). Leave
            # the existing table untouched and force a retry on the next launch by
            # not stamping the snapshot id.
            read_error = True
            continue
        if not df.empty:
            df = df.where(pd.notna(df), None)
            if table == "standings":
                df = _valid_standings_rows(df)
        frames[table] = df

    # Tables we are willing to actually swap: only those whose CSV parsed with
    # rows. Empty/unreadable CSVs never clear an existing populated table.
    loadable = [table for table in CORE_SNAPSHOT_TABLES if not frames.get(table, pd.DataFrame()).empty]

    loaded: dict[str, int] = {}
    with get_connection(db_path) as conn:
        current = conn.execute("SELECT value FROM app_metadata WHERE key = ?", (METADATA_KEY,)).fetchone()
        hash_matches = bool(current) and current["value"] == snapshot_id
        if hash_matches and not _essential_tables_need_reload(conn, loadable, frames):
            return {}

        conn.execute("PRAGMA foreign_keys = OFF")
        for table in reversed(CORE_SNAPSHOT_TABLES):
            if table in loadable:
                conn.execute(f"DELETE FROM {table}")

        for table in CORE_SNAPSHOT_TABLES:
            if table not in loadable:
                continue
            df = frames[table]
            df.to_sql(table, conn, if_exists="append", index=False)
            loaded[table] = len(df)

        try:
            for table in loadable:
                conn.execute("DELETE FROM sqlite_sequence WHERE name = ?", (table,))
        except Exception:
            pass

        # Only stamp the snapshot id once every CSV was readable. If any file
        # failed to read, leave the marker so the next launch retries the load.
        if not read_error:
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


# Tables that must hold data for the app to be usable. If one of these is empty
# in the database while its CSV snapshot has rows, reload even on a hash match so
# an already-empty (but stamped) database recovers on the next launch.
ESSENTIAL_SNAPSHOT_TABLES = ("teams", "fifa_rankings", "global_fifa_rankings", "fixtures", "groups")


def _essential_tables_need_reload(conn, loadable: list[str], frames: dict[str, pd.DataFrame]) -> bool:
    for table in ESSENTIAL_SNAPSHOT_TABLES:
        if table not in loadable:
            continue
        if frames.get(table, pd.DataFrame()).empty:
            continue
        try:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        except Exception:
            return True
        if not count:
            return True
    return False


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


def _valid_standings_rows(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "group_name" not in df.columns or "team_id" not in df.columns:
        return pd.DataFrame(columns=df.columns)
    clean = df.copy()
    clean["group_name"] = clean["group_name"].fillna("").astype(str).str.strip()
    clean = clean[(clean["group_name"] != "") & clean["team_id"].notna()]
    return clean
