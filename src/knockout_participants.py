"""Sticky knockout-participant cache.

football-data.org fills bracket teams (e.g. "United States", "Germany",
"Mexico") into knockout slots intermittently and sometimes blanks them back to
nothing on a later pull. The app has no memory of its own, so whenever the feed
came back empty the teams vanished from the Bracket page.

This module remembers every *real* team the feed has shown for a knockout slot
and uses it to backfill that slot when a later feed pull (or the local DB
fallback) leaves it blank. A blank is never more correct than a team we have
already confirmed, so we only ever override placeholders with a remembered team
-- a different real team from the feed still wins and replaces the old one.
"""

from __future__ import annotations

import sqlite3

import pandas as pd

from src.config import is_shared_core_read_only_mode
from src.database import fetch_df, get_connection
from src.pages.bracket_renderer import is_real_team


KNOCKOUT_MIN = 73
KNOCKOUT_MAX = 104
_SLOT_COLUMNS = ("home_team", "away_team")


def apply_sticky_knockout_participants(fixtures: pd.DataFrame) -> pd.DataFrame:
    """Remember real knockout teams and backfill blank slots from memory.

    Works on either the live-feed fixtures or the local DB fallback; both carry an
    ``official_match_number`` column. Returns the fixtures with placeholder slots
    replaced by remembered teams where available.
    """
    if fixtures.empty or "official_match_number" not in fixtures:
        return fixtures

    store = _stored_participants()
    updated = fixtures.copy()
    for column in _SLOT_COLUMNS:
        if column in updated:
            updated[column] = updated[column].astype("object")

    new_records: list[tuple[int, int, str]] = []
    for index, row in updated.iterrows():
        number = row.get("official_match_number")
        if pd.isna(number):
            continue
        number = int(number)
        if not KNOCKOUT_MIN <= number <= KNOCKOUT_MAX:
            continue
        for slot_index, column in enumerate(_SLOT_COLUMNS):
            if column not in updated:
                continue
            value = row.get(column)
            if is_real_team(value):
                name = str(value).strip()
                if store.get((number, slot_index)) != name:
                    new_records.append((number, slot_index, name))
                    store[(number, slot_index)] = name
            else:
                remembered = store.get((number, slot_index))
                if remembered:
                    updated.at[index, column] = remembered

    _persist(new_records)
    return updated


def _stored_participants() -> dict[tuple[int, int], str]:
    try:
        rows = fetch_df(
            "SELECT match_number, slot_index, team_name FROM knockout_participants"
        )
    except Exception:
        # Table not created yet (older DB); behave as if nothing is remembered.
        return {}
    return {
        (int(row.match_number), int(row.slot_index)): str(row.team_name)
        for row in rows.itertuples()
    }


def _persist(records: list[tuple[int, int, str]]) -> None:
    if not records or is_shared_core_read_only_mode():
        return
    try:
        with get_connection() as conn:
            conn.executemany(
                """
                INSERT INTO knockout_participants (match_number, slot_index, team_name, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(match_number, slot_index) DO UPDATE SET
                    team_name = excluded.team_name,
                    updated_at = excluded.updated_at
                """,
                records,
            )
            conn.commit()
    except sqlite3.OperationalError:
        # Table missing on a not-yet-migrated DB; skip persistence this run.
        pass
