from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import requests

from src.analytics.odds_math import american_to_decimal, decimal_to_implied_probability
from src.config import get_secret, is_shared_core_read_only_mode
from src.database import DB_PATH, get_connection
from src.data_loader import canonical_team_name


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


def save_odds_rows(rows: list[dict[str, Any]], db_path=DB_PATH) -> int:
    if is_shared_core_read_only_mode():
        return 0
    saved = 0
    with get_connection(db_path) as conn:
        merge_duplicate_odds_teams(conn)
        for row in rows:
            team_name = canonical_team_name(row.get("team_name"))
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
                    row["market_type"],
                    row["odds_format"],
                    row["american_odds"],
                    row["decimal_odds"],
                    row["implied_probability"],
                    row["source"],
                    row["snapshot_ts"],
                    row["notes"],
                ),
            )
            saved += 1
        merge_duplicate_odds_teams(conn)
        conn.commit()
    return saved


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
