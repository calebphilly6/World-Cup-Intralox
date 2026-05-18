from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import requests

from src.analytics.odds_math import american_to_decimal, decimal_to_implied_probability
from src.config import get_secret, is_shared_core_read_only_mode
from src.database import DB_PATH, get_connection
from src.data_loader import canonical_team_name
from src.official_match_reference import normalize_team_key


API_HOST = "https://api.the-odds-api.com"


def is_configured(secrets: dict | None = None) -> bool:
    return bool(get_api_key(secrets))


def get_api_key(secrets: dict | None = None) -> str | None:
    if secrets is not None:
        try:
            api_keys = secrets.get("api_keys", {})
            return (
                secrets.get("THE_ODDS_API_KEY")
                or api_keys.get("the_odds_api")
                or api_keys.get("odds_provider")
            )
        except Exception:
            return None
    return get_secret("THE_ODDS_API_KEY")


def list_sports(api_key: str, include_all: bool = True) -> list[dict[str, Any]]:
    response = requests.get(
        f"{API_HOST}/v4/sports",
        params={"apiKey": api_key, "all": "true" if include_all else "false"},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def find_world_cup_sport_key(api_key: str) -> str | None:
    sports = list_sports(api_key)
    candidates = [
        sport for sport in sports
        if "soccer" in sport.get("key", "")
        and "world cup" in sport.get("title", "").lower()
        and sport.get("has_outrights")
    ]
    if candidates:
        return candidates[0]["key"]
    fallback = [
        sport for sport in sports
        if "world cup" in sport.get("title", "").lower() or "world_cup" in sport.get("key", "")
    ]
    return fallback[0]["key"] if fallback else None


def find_world_cup_sports(api_key: str) -> list[dict[str, Any]]:
    sports = list_sports(api_key, include_all=True)
    return [
        sport for sport in sports
        if "soccer" in sport.get("key", "").lower()
        and (
            "world cup" in sport.get("title", "").lower()
            or "world_cup" in sport.get("key", "").lower()
            or "fifa" in sport.get("key", "").lower()
            or "fifa" in sport.get("title", "").lower()
        )
    ]


def fetch_outrights(
    api_key: str,
    sport_key: str,
    regions: str = "us",
    odds_format: str = "american",
    bookmakers: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, str | None]]:
    params = {
        "apiKey": api_key,
        "regions": regions,
        "markets": "outrights",
        "oddsFormat": odds_format,
        "dateFormat": "iso",
    }
    if bookmakers:
        params["bookmakers"] = bookmakers
    response = requests.get(
        f"{API_HOST}/v4/sports/{sport_key}/odds",
        params=params,
        timeout=25,
    )
    if response.status_code >= 400:
        raise requests.HTTPError(
            f"{response.status_code} {response.reason}: {response.text}",
            response=response,
        )
    quota = {
        "remaining": response.headers.get("x-requests-remaining"),
        "used": response.headers.get("x-requests-used"),
        "last": response.headers.get("x-requests-last"),
    }
    return response.json(), quota


def fetch_match_odds(
    api_key: str,
    sport_key: str,
    regions: str = "us",
    markets: str = "h2h,spreads,totals",
    odds_format: str = "american",
    bookmakers: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, str | None]]:
    params = {
        "apiKey": api_key,
        "regions": regions,
        "markets": markets,
        "oddsFormat": odds_format,
        "dateFormat": "iso",
    }
    if bookmakers:
        params["bookmakers"] = bookmakers
    response = requests.get(
        f"{API_HOST}/v4/sports/{sport_key}/odds",
        params=params,
        timeout=25,
    )
    if response.status_code >= 400:
        raise requests.HTTPError(
            f"{response.status_code} {response.reason}: {response.text}",
            response=response,
        )
    quota = {
        "remaining": response.headers.get("x-requests-remaining"),
        "used": response.headers.get("x-requests-used"),
        "last": response.headers.get("x-requests-last"),
    }
    return response.json(), quota


def flatten_outrights(payload: list[dict[str, Any]], odds_format: str = "american") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    snapshot_ts = datetime.now(timezone.utc).isoformat()
    for event in payload:
        for bookmaker in event.get("bookmakers", []):
            for market in bookmaker.get("markets", []):
                if market.get("key") != "outrights":
                    continue
                market_ts = market.get("last_update") or bookmaker.get("last_update") or snapshot_ts
                for outcome in market.get("outcomes", []):
                    decimal_odds = None
                    american_odds = None
                    price = outcome.get("price")
                    if odds_format == "american":
                        american_odds = str(price)
                        decimal_odds = american_to_decimal(price)
                    else:
                        decimal_odds = float(price) if price is not None else None
                    rows.append(
                        {
                            "team_name": outcome.get("name"),
                            "market_type": "tournament_winner",
                            "odds_format": odds_format,
                            "american_odds": american_odds,
                            "decimal_odds": decimal_odds,
                            "implied_probability": decimal_to_implied_probability(decimal_odds),
                            "source": bookmaker.get("title") or bookmaker.get("key") or "the_odds_api",
                            "snapshot_ts": market_ts,
                            "notes": "Informational odds snapshot from The Odds API",
                        }
                    )
    return rows


def flatten_match_odds(payload: list[dict[str, Any]], odds_format: str = "american") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    snapshot_ts = datetime.now(timezone.utc).isoformat()
    for event in payload:
        event_home = event.get("home_team")
        event_away = event.get("away_team")
        event_time = event.get("commence_time")
        for bookmaker in event.get("bookmakers", []):
            bookmaker_title = bookmaker.get("title") or bookmaker.get("key") or "the_odds_api"
            bookmaker_ts = bookmaker.get("last_update") or snapshot_ts
            for market in bookmaker.get("markets", []):
                market_key = market.get("key")
                if market_key not in {"h2h", "spreads", "totals"}:
                    continue
                market_ts = market.get("last_update") or bookmaker_ts
                for outcome in market.get("outcomes", []):
                    price = outcome.get("price")
                    decimal_odds = None
                    american_odds = None
                    if odds_format == "american":
                        american_odds = str(price) if price is not None else None
                        decimal_odds = american_to_decimal(price)
                    else:
                        decimal_odds = float(price) if price is not None else None
                    rows.append(
                        {
                            "external_event_id": event.get("id"),
                            "commence_time": event_time,
                            "home_team": event_home,
                            "away_team": event_away,
                            "bookmaker_key": bookmaker.get("key"),
                            "bookmaker_title": bookmaker_title,
                            "market_type": market_key,
                            "outcome_name": outcome.get("name"),
                            "odds_format": odds_format,
                            "american_odds": american_odds,
                            "decimal_odds": decimal_odds,
                            "implied_probability": decimal_to_implied_probability(decimal_odds),
                            "point": outcome.get("point"),
                            "source": bookmaker_title,
                            "snapshot_ts": market_ts,
                            "notes": "Informational match odds snapshot from The Odds API",
                        }
                    )
    return rows


def save_odds_rows(rows: list[dict[str, Any]], db_path=DB_PATH) -> int:
    if is_shared_core_read_only_mode():
        return 0
    saved = 0
    with get_connection(db_path) as conn:
        merge_duplicate_odds_teams(conn)
        for row in rows:
            team_name = canonical_team_name(_row_value(row, "team_name"))
            if not team_name:
                continue
            conn.execute(
                """
                INSERT INTO teams (name)
                VALUES (?)
                ON CONFLICT(name) DO NOTHING
                """,
                (team_name,),
            )
            team = conn.execute("SELECT id FROM teams WHERE name = ?", (team_name,)).fetchone()
            conn.execute(
                """
                INSERT INTO odds_snapshots (
                    team_id, market_type, odds_format, american_odds, decimal_odds,
                    implied_probability, source, snapshot_ts, notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    team["id"],
                    _row_value(row, "market_type"),
                    _row_value(row, "odds_format"),
                    _row_value(row, "american_odds"),
                    _row_value(row, "decimal_odds"),
                    _row_value(row, "implied_probability"),
                    _row_value(row, "source"),
                    _row_value(row, "snapshot_ts"),
                    _row_value(row, "notes"),
                ),
            )
            saved += 1
        merge_duplicate_odds_teams(conn)
        conn.commit()
    return saved


def save_fixture_odds_rows(rows: list[dict[str, Any]], db_path=DB_PATH) -> int:
    if is_shared_core_read_only_mode():
        return 0
    saved = 0
    with get_connection(db_path) as conn:
        fixture_lookup = _fixture_lookup(conn)
        for row in rows:
            outcome_name = str(_row_value(row, "outcome_name") or "").strip()
            if not outcome_name:
                continue
            fixture_id = _match_fixture_id(row, fixture_lookup)
            conn.execute(
                """
                INSERT INTO fixture_odds_snapshots (
                    fixture_id, external_event_id, commence_time, home_team, away_team,
                    bookmaker_key, bookmaker_title, market_type, outcome_name, odds_format,
                    american_odds, decimal_odds, implied_probability, point, source,
                    snapshot_ts, notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    fixture_id,
                    _row_value(row, "external_event_id"),
                    _row_value(row, "commence_time"),
                    canonical_team_name(_row_value(row, "home_team")) or _row_value(row, "home_team"),
                    canonical_team_name(_row_value(row, "away_team")) or _row_value(row, "away_team"),
                    _row_value(row, "bookmaker_key"),
                    _row_value(row, "bookmaker_title"),
                    _row_value(row, "market_type"),
                    outcome_name,
                    _row_value(row, "odds_format"),
                    _row_value(row, "american_odds"),
                    _row_value(row, "decimal_odds"),
                    _row_value(row, "implied_probability"),
                    _row_value(row, "point"),
                    _row_value(row, "source"),
                    _row_value(row, "snapshot_ts"),
                    _row_value(row, "notes"),
                ),
            )
            saved += 1
        conn.commit()
    return saved


def relink_fixture_odds_rows(db_path=DB_PATH) -> int:
    if is_shared_core_read_only_mode():
        return 0
    updated = 0
    with get_connection(db_path) as conn:
        fixture_lookup = _fixture_lookup(conn)
        rows = conn.execute(
            """
            SELECT id, commence_time, home_team, away_team
            FROM fixture_odds_snapshots
            WHERE fixture_id IS NULL
            """
        ).fetchall()
        for row in rows:
            fixture_id = _match_fixture_id(dict(row), fixture_lookup)
            if fixture_id is None:
                continue
            conn.execute("UPDATE fixture_odds_snapshots SET fixture_id = ? WHERE id = ?", (fixture_id, row["id"]))
            updated += 1
        conn.commit()
    return updated


def _fixture_lookup(conn) -> dict[tuple[str, str, str], int]:
    rows = conn.execute(
        """
        SELECT f.id, f.kickoff_utc, ht.name AS home_team, at.name AS away_team, m.game_label
        FROM fixtures f
        LEFT JOIN teams ht ON ht.id = f.home_team_id
        LEFT JOIN teams at ON at.id = f.away_team_id
        LEFT JOIN match_city_reference m ON m.match_number = f.match_number
        """
    ).fetchall()
    lookup: dict[tuple[str, str, str], int] = {}
    for row in rows:
        day = _event_day(row["kickoff_utc"])
        for home_team, away_team in _fixture_team_pairs(row):
            home_key = normalize_team_key(home_team)
            away_key = normalize_team_key(away_team)
            if not (day and home_key and away_key):
                continue
            lookup[(day, home_key, away_key)] = int(row["id"])
            lookup[(day, away_key, home_key)] = int(row["id"])
    return lookup


def _fixture_team_pairs(row) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    home_team = row["home_team"]
    away_team = row["away_team"]
    if home_team and away_team:
        pairs.append((home_team, away_team))
    label_home, label_away = _split_game_label(row["game_label"])
    if label_home and label_away:
        pairs.append((canonical_team_name(label_home), canonical_team_name(label_away)))
        pairs.append((label_home, label_away))
    return pairs


def _split_game_label(value) -> tuple[str, str]:
    label = str(value or "").strip()
    if " vs " not in label:
        return "", ""
    home, away = label.split(" vs ", 1)
    return home.strip(), away.strip()


def _match_fixture_id(row: dict[str, Any], fixture_lookup: dict[tuple[str, str, str], int]) -> int | None:
    key = (
        _event_day(_row_value(row, "commence_time")),
        normalize_team_key(_row_value(row, "home_team")),
        normalize_team_key(_row_value(row, "away_team")),
    )
    return fixture_lookup.get(key)


def _row_value(row, key: str):
    if row is None:
        return None
    if isinstance(row, dict):
        return row.get(key)
    try:
        return row.get(key)
    except AttributeError:
        return row[key]
    except (KeyError, IndexError):
        return None


def _event_day(value) -> str:
    text = str(value or "").strip()
    return text[:10] if len(text) >= 10 else ""


def merge_duplicate_odds_teams(conn) -> None:
    if is_shared_core_read_only_mode():
        return
    rows = conn.execute("SELECT id, name FROM teams").fetchall()
    for row in rows:
        canonical_name = canonical_team_name(row["name"])
        if not canonical_name or canonical_name == row["name"]:
            continue
        canonical = conn.execute("SELECT id FROM teams WHERE name = ?", (canonical_name,)).fetchone()
        if canonical is None:
            conn.execute(
                "UPDATE teams SET name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (canonical_name, row["id"]),
            )
            continue
        old_id = row["id"]
        new_id = canonical["id"]
        conn.execute("UPDATE odds_snapshots SET team_id = ? WHERE team_id = ?", (new_id, old_id))
        conn.execute("UPDATE fixtures SET home_team_id = ? WHERE home_team_id = ?", (new_id, old_id))
        conn.execute("UPDATE fixtures SET away_team_id = ? WHERE away_team_id = ?", (new_id, old_id))
        conn.execute(
            """
            INSERT OR IGNORE INTO groups (group_name, team_id, qualification_status)
            SELECT group_name, ?, qualification_status
            FROM groups
            WHERE team_id = ?
            """,
            (new_id, old_id),
        )
        conn.execute("DELETE FROM groups WHERE team_id = ?", (old_id,))
        conn.execute("DELETE FROM teams WHERE id = ?", (old_id,))


def save_api_usage(quota: dict[str, str | None], db_path=DB_PATH) -> None:
    if is_shared_core_read_only_mode():
        return
    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO api_usage (provider, last_request_cost, requests_used, requests_remaining)
            VALUES ('the_odds_api', ?, ?, ?)
            """,
            (quota.get("last"), quota.get("used"), quota.get("remaining")),
        )
        conn.commit()
