"""Reboot-safety regression tests for core snapshot loading.

These guard the two failure modes that blanked the FIFA rankings on the hosted
app: a stamped-but-empty database that never reloaded, and an empty/unreadable
CSV that wiped a populated table.
"""
from __future__ import annotations

import sqlite3

import pandas as pd

from src.database import initialize_database
from src import snapshots


def _write_snapshot(snapshot_dir, tables: dict[str, pd.DataFrame]) -> None:
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    for table, df in tables.items():
        df.to_csv(snapshot_dir / f"{table}.csv", index=False)


def _base_tables() -> dict[str, pd.DataFrame]:
    teams = pd.DataFrame([{"id": 1, "name": "Argentina", "country_code": "AR"}])
    fifa = pd.DataFrame([{"id": 1, "team_id": 1, "ranking_date": "2026-06-11", "rank": 1}])
    global_fifa = pd.DataFrame(
        [{"id": 1, "team_name": "Argentina", "ranking_date": "2026-06-11", "rank": 1, "is_world_cup_team": 1}]
    )
    return {"teams": teams, "fifa_rankings": fifa, "global_fifa_rankings": global_fifa}


def _counts(db_path):
    conn = sqlite3.connect(db_path)
    try:
        fifa = conn.execute("SELECT COUNT(*) FROM fifa_rankings").fetchone()[0]
        joined = conn.execute(
            "SELECT COUNT(*) FROM fifa_rankings r JOIN teams t ON t.id = r.team_id"
        ).fetchone()[0]
        return fifa, joined
    finally:
        conn.close()


def test_cold_start_loads_rankings(tmp_path):
    db_path = tmp_path / "wc.db"
    snapshot_dir = tmp_path / "snapshots"
    _write_snapshot(snapshot_dir, _base_tables())
    initialize_database(db_path)

    snapshots.load_core_snapshots(db_path=db_path, snapshot_dir=snapshot_dir)

    assert _counts(db_path) == (1, 1)


def test_stamped_but_empty_database_recovers(tmp_path):
    """A persisted hosted DB stamped with the current hash but holding no
    rankings must reload instead of staying empty forever."""
    db_path = tmp_path / "wc.db"
    snapshot_dir = tmp_path / "snapshots"
    _write_snapshot(snapshot_dir, _base_tables())
    initialize_database(db_path)

    # Stamp the matching hash on an empty database (the stuck state).
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO app_metadata(key, value) VALUES(?, ?)",
        (snapshots.METADATA_KEY, snapshots._snapshot_id(snapshot_dir)),
    )
    conn.commit()
    conn.close()

    snapshots.load_core_snapshots(db_path=db_path, snapshot_dir=snapshot_dir)

    assert _counts(db_path) == (1, 1)


def test_empty_csv_does_not_wipe_populated_table(tmp_path):
    """An empty/placeholder CSV (e.g. an un-hydrated OneDrive file) must not
    clear a table that already holds data."""
    db_path = tmp_path / "wc.db"
    snapshot_dir = tmp_path / "snapshots"
    _write_snapshot(snapshot_dir, _base_tables())
    initialize_database(db_path)
    snapshots.load_core_snapshots(db_path=db_path, snapshot_dir=snapshot_dir)
    assert _counts(db_path) == (1, 1)

    # Next launch: fifa_rankings.csv comes back as a 0-byte placeholder and the
    # hash changes, which would have triggered a delete-then-empty-reload before.
    (snapshot_dir / "fifa_rankings.csv").write_text("")

    snapshots.load_core_snapshots(db_path=db_path, snapshot_dir=snapshot_dir)

    assert _counts(db_path) == (1, 1)
