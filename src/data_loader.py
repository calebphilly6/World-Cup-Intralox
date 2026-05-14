from __future__ import annotations

from pathlib import Path
import unicodedata

import pandas as pd

from src.config import IMPORTS_DIR
from src.database import DB_PATH, get_connection
from src.analytics.odds_math import american_to_decimal, decimal_to_implied_probability
from src.utils.formatting import flag_for_code
from src.utils.validation import normalize_columns, validate_import


IMPORT_DIR = IMPORTS_DIR

TEAM_NAME_ALIASES = {
    "United States": "USA",
    "United States of America": "USA",
    "US": "USA",
    "Iran": "IR Iran",
    "Korea Republic": "South Korea",
    "Republic of Korea": "South Korea",
    "Turkiye": "Türkiye",
    "Turkey": "Türkiye",
    "Curacao": "Curaçao",
    "DR Congo": "Congo DR",
    "Congo DR": "Congo DR",
    "Bosnia & Herzegovina": "Bosnia and Herzegovina",
    "Cape Verde": "Cabo Verde",
    "Czech Republic": "Czechia",
    "Cote d'Ivoire": "Côte d'Ivoire",
    "Ivory Coast": "Côte d'Ivoire",
}
TEAM_NAME_ALIAS_LOOKUP = {}
for alias, canonical in TEAM_NAME_ALIASES.items():
    TEAM_NAME_ALIAS_LOOKUP[
        unicodedata.normalize("NFKD", alias)
        .encode("ascii", "ignore")
        .decode("ascii")
        .replace("’", "'")
        .lower()
    ] = canonical


def read_import_file(path_or_buffer) -> pd.DataFrame:
    name = getattr(path_or_buffer, "name", str(path_or_buffer))
    try:
        if str(name).lower().endswith(".json"):
            return normalize_columns(pd.read_json(path_or_buffer))
        return normalize_columns(pd.read_csv(path_or_buffer))
    except (pd.errors.EmptyDataError, ValueError):
        return pd.DataFrame()


def import_dataframe(kind: str, df: pd.DataFrame, db_path: Path = DB_PATH) -> tuple[int, list[str]]:
    clean = normalize_columns(df)
    if clean.empty:
        return 0, ["The uploaded file did not contain any rows."]
    if kind == "fifa_rankings" and "team" not in clean.columns and "team_name" in clean.columns:
        clean = clean.rename(columns={"team_name": "team"})
    errors = validate_import(kind, clean)
    if errors:
        return 0, errors

    if kind == "teams":
        return upsert_teams(clean, db_path), []
    if kind == "groups":
        return upsert_groups(clean, db_path), []
    if kind == "fixtures":
        return upsert_fixtures(clean, db_path), []
    if kind == "fifa_rankings":
        return upsert_rankings(clean, db_path), []
    if kind == "odds":
        return upsert_odds(clean, db_path), []
    return 0, [f"Unsupported import type: {kind}"]


def load_template(kind: str) -> pd.DataFrame:
    path = IMPORT_DIR / f"{kind}.csv"
    if not path.exists():
        return pd.DataFrame()
    return read_import_file(path)


def ensure_team(conn, name: str | None, country_code: str | None = None) -> int | None:
    if not name or str(name).strip().upper() == "TBD":
        return None
    team_name = canonical_team_name(name)
    code = None if pd.isna(country_code) else country_code
    conn.execute(
        """
        INSERT INTO teams (name, country_code, flag)
        VALUES (?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            country_code = COALESCE(excluded.country_code, teams.country_code),
            flag = COALESCE(excluded.flag, teams.flag),
            updated_at = CURRENT_TIMESTAMP
        """,
        (team_name, code, flag_for_code(code)),
    )
    row = conn.execute("SELECT id FROM teams WHERE name = ?", (team_name,)).fetchone()
    return int(row["id"])


def ensure_venue(conn, stadium_name: str | None, city: str | None = None, country: str | None = None) -> int | None:
    if not stadium_name or pd.isna(stadium_name):
        return None
    name = str(stadium_name).strip()
    conn.execute(
        """
        INSERT INTO venues (stadium_name, city, country)
        VALUES (?, ?, ?)
        ON CONFLICT(stadium_name) DO UPDATE SET
            city = COALESCE(excluded.city, venues.city),
            country = COALESCE(excluded.country, venues.country),
            updated_at = CURRENT_TIMESTAMP
        """,
        (name, _clean(city), _clean(country)),
    )
    row = conn.execute("SELECT id FROM venues WHERE stadium_name = ?", (name,)).fetchone()
    return int(row["id"])


def upsert_teams(df: pd.DataFrame, db_path: Path = DB_PATH) -> int:
    count = 0
    with get_connection(db_path) as conn:
        for _, row in df.iterrows():
            code = _clean(row.get("country_code"))
            conn.execute(
                """
                INSERT INTO teams (
                    name, country_code, flag, confederation, favorite, personal_rating,
                    excitement_score, notes, why_interested, key_players
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    country_code = excluded.country_code,
                    flag = excluded.flag,
                    confederation = excluded.confederation,
                    favorite = excluded.favorite,
                    personal_rating = excluded.personal_rating,
                    excitement_score = excluded.excitement_score,
                    notes = excluded.notes,
                    why_interested = excluded.why_interested,
                    key_players = excluded.key_players,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    canonical_team_name(row["name"]),
                    code,
                    _clean(row.get("flag")) or flag_for_code(code),
                    _clean(row.get("confederation")),
                    _int(row.get("favorite"), 0),
                    _int(row.get("personal_rating")),
                    _int(row.get("excitement_score")),
                    _clean(row.get("notes")),
                    _clean(row.get("why_interested")),
                    _clean(row.get("key_players")),
                ),
            )
            count += 1
        conn.commit()
    return count


def upsert_groups(df: pd.DataFrame, db_path: Path = DB_PATH) -> int:
    count = 0
    with get_connection(db_path) as conn:
        for _, row in df.iterrows():
            team_id = ensure_team(conn, row.get("team_name"))
            if team_id is None:
                continue
            conn.execute(
                """
                INSERT INTO groups (group_name, team_id, qualification_status)
                VALUES (?, ?, ?)
                ON CONFLICT(group_name, team_id) DO UPDATE SET
                    qualification_status = excluded.qualification_status,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (str(row["group_name"]).strip(), team_id, _clean(row.get("qualification_status"))),
            )
            count += 1
        conn.commit()
    return count


def upsert_fixtures(df: pd.DataFrame, db_path: Path = DB_PATH) -> int:
    count = 0
    with get_connection(db_path) as conn:
        for _, row in df.iterrows():
            home_id = ensure_team(conn, row.get("home_team"))
            away_id = ensure_team(conn, row.get("away_team"))
            venue_id = ensure_venue(conn, row.get("venue_name"), row.get("city"), row.get("host_country"))
            conn.execute(
                """
                INSERT INTO fixtures (
                    match_number, kickoff_utc, home_team_id, away_team_id, stage, group_name,
                    venue_id, city, host_country, status, home_score, away_score, watch_priority, notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(match_number) DO UPDATE SET
                    kickoff_utc = excluded.kickoff_utc,
                    home_team_id = excluded.home_team_id,
                    away_team_id = excluded.away_team_id,
                    stage = excluded.stage,
                    group_name = excluded.group_name,
                    venue_id = excluded.venue_id,
                    city = excluded.city,
                    host_country = excluded.host_country,
                    status = excluded.status,
                    home_score = excluded.home_score,
                    away_score = excluded.away_score,
                    watch_priority = excluded.watch_priority,
                    notes = excluded.notes,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    _int(row.get("match_number")),
                    str(row["kickoff_utc"]).strip(),
                    home_id,
                    away_id,
                    str(row["stage"]).strip(),
                    _clean(row.get("group_name")),
                    venue_id,
                    _clean(row.get("city")),
                    _clean(row.get("host_country")),
                    _clean(row.get("status")) or "Scheduled",
                    _int(row.get("home_score")),
                    _int(row.get("away_score")),
                    _clean(row.get("watch_priority")) or "Maybe",
                    _clean(row.get("notes")),
                ),
            )
            count += 1
        conn.commit()
    return count


def upsert_rankings(df: pd.DataFrame, db_path: Path = DB_PATH) -> int:
    count = 0
    with get_connection(db_path) as conn:
        for _, row in df.iterrows():
            team_name = canonical_team_name(row.get("team"))
            existing = conn.execute("SELECT id FROM teams WHERE name = ?", (team_name,)).fetchone()
            team_id = int(existing["id"]) if existing else None
            ranking_date = str(row["ranking_date"]).strip()
            rank = _int(row.get("rank"))
            points = _float(row.get("points"))
            previous_rank = _int(row.get("previous_rank"))
            source = _clean(row.get("source")) or "manual"
            notes = _clean(row.get("notes"))
            conn.execute(
                """
                INSERT INTO global_fifa_rankings (
                    team_name, ranking_date, rank, points, previous_rank, source, notes, is_world_cup_team
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(team_name, ranking_date) DO UPDATE SET
                    rank = excluded.rank,
                    points = excluded.points,
                    previous_rank = excluded.previous_rank,
                    source = excluded.source,
                    notes = excluded.notes,
                    is_world_cup_team = excluded.is_world_cup_team
                """,
                (team_name, ranking_date, rank, points, previous_rank, source, notes, int(team_id is not None)),
            )
            if team_id is None:
                count += 1
                continue
            conn.execute(
                """
                INSERT INTO fifa_rankings (team_id, ranking_date, rank, points, previous_rank, source, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(team_id, ranking_date) DO UPDATE SET
                    rank = excluded.rank,
                    points = excluded.points,
                    previous_rank = excluded.previous_rank,
                    source = excluded.source,
                    notes = excluded.notes
                """,
                (
                    team_id,
                    ranking_date,
                    rank,
                    points,
                    previous_rank,
                    source,
                    notes,
                ),
            )
            count += 1
        conn.commit()
    return count


def upsert_odds(df: pd.DataFrame, db_path: Path = DB_PATH) -> int:
    count = 0
    with get_connection(db_path) as conn:
        for _, row in df.iterrows():
            team_id = ensure_team(conn, row.get("team_name"))
            decimal_odds = _float(row.get("decimal_odds"))
            american_odds = _clean(row.get("american_odds"))
            if decimal_odds is None and american_odds:
                decimal_odds = american_to_decimal(american_odds)
            implied_probability = _float(row.get("implied_probability"))
            if implied_probability is None:
                implied_probability = decimal_to_implied_probability(decimal_odds)
            conn.execute(
                """
                INSERT INTO odds_snapshots (
                    team_id, market_type, odds_format, american_odds, decimal_odds,
                    implied_probability, source, snapshot_ts, notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    team_id,
                    str(row["market_type"]).strip(),
                    _clean(row.get("odds_format")) or "manual",
                    american_odds,
                    decimal_odds,
                    implied_probability,
                    _clean(row.get("source")) or "manual",
                    str(row["snapshot_ts"]).strip(),
                    _clean(row.get("notes")),
                ),
            )
            count += 1
        conn.commit()
    return count


def _clean(value) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def canonical_team_name(value) -> str:
    text = str(value).strip()
    if text in TEAM_NAME_ALIASES:
        return TEAM_NAME_ALIASES[text]
    normalized = (
        unicodedata.normalize("NFKD", text)
        .encode("ascii", "ignore")
        .decode("ascii")
        .replace("’", "'")
        .lower()
    )
    return TEAM_NAME_ALIAS_LOOKUP.get(normalized, text)


def _int(value, default=None) -> int | None:
    if value is None or pd.isna(value) or str(value).strip() == "":
        return default
    return int(float(value))


def _float(value) -> float | None:
    if value is None or pd.isna(value) or str(value).strip() == "":
        return None
    return float(value)
