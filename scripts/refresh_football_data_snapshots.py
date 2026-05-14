from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_sources.football_data_client import (
    get_world_cup_2026_matches,
    get_world_cup_2026_standings,
    normalize_matches_to_dataframe,
    normalize_standings_to_dataframe,
)
from src.data_loader import import_dataframe
from src.database import fetch_df, get_connection
from src.official_match_reference import apply_official_match_reference
from src.snapshots import SNAPSHOT_DIR, export_core_snapshots


def main() -> None:
    print("Fetching football-data.org matches...")
    matches = apply_official_match_reference(normalize_matches_to_dataframe(get_world_cup_2026_matches()))
    fixture_rows = _fixtures_for_import(matches)
    imported_fixtures, fixture_errors = import_dataframe("fixtures", fixture_rows)
    if fixture_errors:
        raise RuntimeError("; ".join(fixture_errors))
    print(f"Saved fixtures: {imported_fixtures}")

    print("Fetching football-data.org standings...")
    standings = normalize_standings_to_dataframe(get_world_cup_2026_standings())
    saved_standings = _save_standings(standings)
    print(f"Saved standings rows: {saved_standings}")

    clean_non_world_cup_teams()
    repaired = repair_blank_standing_groups()
    if repaired:
        print(f"Repaired blank standing groups: {repaired}")
    counts = export_core_snapshots()
    print(f"Exported core data snapshots to {SNAPSHOT_DIR}")
    for table, count in counts.items():
        print(f"{table}: {count}")


def _fixtures_for_import(matches: pd.DataFrame) -> pd.DataFrame:
    if matches.empty:
        return pd.DataFrame()
    rows = matches.copy()
    team_lookup = _team_lookup()
    rows["home_team"] = rows["home_team"].map(lambda value: _snapshot_team_name(value, team_lookup))
    rows["away_team"] = rows["away_team"].map(lambda value: _snapshot_team_name(value, team_lookup))
    rows["match_number"] = rows.get("official_match_number", rows.get("match_id"))
    rows["kickoff_utc"] = rows["utc_date"]
    rows["group_name"] = rows.get("group", "").map(_group_name)
    rows["stage"] = rows.get("stage", "").map(_stage_name)
    rows["venue_name"] = rows.get("venue", "")
    rows["host_country"] = ""
    rows["watch_priority"] = "Maybe"
    rows["notes"] = ""
    return rows[
        [
            "match_number",
            "kickoff_utc",
            "home_team",
            "away_team",
            "stage",
            "group_name",
            "venue_name",
            "city",
            "host_country",
            "status",
            "home_score",
            "away_score",
            "watch_priority",
            "notes",
        ]
    ]


def _save_standings(standings: pd.DataFrame) -> int:
    if standings.empty:
        return 0
    team_lookup = _team_lookup()
    count = 0
    with get_connection() as conn:
        for _, row in standings.iterrows():
            team_name = _snapshot_team_name(row.get("team"), team_lookup)
            if not team_name or team_name == "TBD":
                continue
            team = conn.execute("SELECT id FROM teams WHERE name = ?", (team_name,)).fetchone()
            if team is None:
                continue
            group_name = _group_name(row.get("group")) or _team_group(conn, int(team["id"]))
            if not group_name:
                continue
            conn.execute(
                """
                INSERT INTO standings (
                    group_name, team_id, played, wins, draws, losses,
                    goals_for, goals_against, points
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(group_name, team_id) DO UPDATE SET
                    played = excluded.played,
                    wins = excluded.wins,
                    draws = excluded.draws,
                    losses = excluded.losses,
                    goals_for = excluded.goals_for,
                    goals_against = excluded.goals_against,
                    points = excluded.points,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    group_name,
                    int(team["id"]),
                    _int(row.get("played")),
                    _int(row.get("won")),
                    _int(row.get("draw")),
                    _int(row.get("lost")),
                    _int(row.get("goals_for")),
                    _int(row.get("goals_against")),
                    _int(row.get("points")),
                ),
            )
            count += 1
        conn.commit()
    return count


def clean_non_world_cup_teams() -> None:
    allowed = set(_team_lookup().values())
    with get_connection() as conn:
        placeholders = [row["id"] for row in conn.execute("SELECT id, name FROM teams").fetchall() if row["name"] not in allowed]
        for team_id in placeholders:
            conn.execute("UPDATE fixtures SET home_team_id = NULL WHERE home_team_id = ?", (team_id,))
            conn.execute("UPDATE fixtures SET away_team_id = NULL WHERE away_team_id = ?", (team_id,))
            conn.execute("DELETE FROM standings WHERE team_id = ?", (team_id,))
            conn.execute("DELETE FROM fifa_rankings WHERE team_id = ?", (team_id,))
            conn.execute("DELETE FROM groups WHERE team_id = ?", (team_id,))
            conn.execute("DELETE FROM teams WHERE id = ?", (team_id,))
        conn.commit()


def repair_blank_standing_groups() -> int:
    count = 0
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT s.id, s.team_id, g.group_name
            FROM standings s
            LEFT JOIN groups g ON g.team_id = s.team_id
            WHERE s.group_name IS NULL OR TRIM(s.group_name) = ''
            """
        ).fetchall()
        for row in rows:
            group_name = str(row["group_name"] or "").strip()
            if not group_name:
                conn.execute("DELETE FROM standings WHERE id = ?", (row["id"],))
                continue
            conn.execute("UPDATE standings SET group_name = ? WHERE id = ?", (group_name, row["id"]))
            count += 1
        conn.commit()
    return count


def _team_group(conn, team_id: int) -> str:
    row = conn.execute("SELECT group_name FROM groups WHERE team_id = ? LIMIT 1", (team_id,)).fetchone()
    return str(row["group_name"] or "").strip() if row else ""


def _team_lookup() -> dict[str, str]:
    allowed_path = PROJECT_ROOT / "data" / "imports" / "teams.csv"
    allowed_names = set()
    if allowed_path.exists():
        allowed = pd.read_csv(allowed_path)
        if "name" in allowed.columns:
            allowed_names = {_normalize_team_name(name) for name in allowed["name"].dropna().tolist()}

    teams = fetch_df("SELECT name FROM teams")
    lookup = {}
    for name in teams["name"].dropna().tolist():
        normalized = _normalize_team_name(name)
        if not allowed_names or normalized in allowed_names:
            lookup[normalized] = str(name)
    return lookup


def _snapshot_team_name(value, team_lookup: dict[str, str]) -> str:
    text = str(value or "").strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return "TBD"
    lowered = text.lower()
    if lowered.startswith(("winner ", "loser ")) or text.upper() in {"TBD", "2A", "2B", "1A", "1B", "1C", "1D", "1E", "1F", "1G", "1H", "1I", "1J", "1K", "1L"}:
        return "TBD"
    normalized = _normalize_team_name(text)
    aliases = {
        "bosnia herzegovina": "bosnia and herzegovina",
        "cape verde islands": "cabo verde",
        "cape verde": "cabo verde",
        "curacao": "curacao",
        "turkiye": "turkiye",
        "united states": "usa",
        "united states of america": "usa",
        "korea republic": "south korea",
        "cote divoire": "cote divoire",
        "dr congo": "congo dr",
    }
    normalized = aliases.get(normalized, normalized)
    return team_lookup.get(normalized, "TBD")


def _normalize_team_name(value) -> str:
    import unicodedata

    text = str(value or "").strip()
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return " ".join(normalized.lower().replace("&", "and").replace("'", "").replace("-", " ").split())


def _group_name(value) -> str:
    text = str(value or "").strip()
    if text.upper().startswith("GROUP_"):
        return text.split("_", 1)[1].strip().upper()
    if text.lower().startswith("group "):
        return text.split(" ", 1)[1].strip().upper()
    return text


def _stage_name(value) -> str:
    text = str(value or "").replace("_", " ").strip().title()
    return text or "Group Stage"


def _int(value) -> int:
    try:
        if pd.isna(value):
            return 0
        return int(value)
    except (TypeError, ValueError):
        return 0


if __name__ == "__main__":
    main()
