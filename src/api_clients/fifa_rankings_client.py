from __future__ import annotations

from datetime import date
from typing import Any

import requests

from src.config import get_secret, is_shared_core_read_only_mode
from src.database import DB_PATH, get_connection


BASE_URL = "https://footballdata.io/api/v1"

TEAM_ALIASES = {
    "bosnia-herzegovina": "bosnia and herzegovina",
    "bosnia & herzegovina": "bosnia and herzegovina",
    "czech republic": "czechia",
    "cape verde": "cabo verde",
    "côte d'ivoire": "côte d'ivoire",
    "côte d’ivoire": "côte d'ivoire",
    "cote d'ivoire": "côte d'ivoire",
    "ivory coast": "côte d'ivoire",
    "curaçao": "curacao",
    "congo dr": "congo dr",
    "korea republic": "south korea",
    "republic of korea": "south korea",
    "turkey": "türkiye",
    "türkiye": "türkiye",
    "usa": "usa",
    "united states": "usa",
    "united states of america": "usa",
    "iran": "ir iran",
    "ir iran": "ir iran",
}


def is_configured(secrets: dict | None = None) -> bool:
    return bool(get_api_key(secrets))


def get_api_key(secrets: dict | None = None) -> str | None:
    if secrets is None:
        return get_secret("FIFA_RANKINGS_API_KEY", env_fallback=True)
    try:
        api_keys = secrets.get("api_keys", {})
        return secrets.get("FIFA_RANKINGS_API_KEY") or api_keys.get("fifa_rankings") or api_keys.get("footballdata")
    except Exception:
        return None


def fetch_current_rankings(api_key: str, limit: int = 100) -> list[dict[str, Any]]:
    response = requests.get(
        f"{BASE_URL}/fifa-rankings/current",
        params={"ranking_type": "men", "limit": limit},
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=25,
    )
    if response.status_code >= 400:
        raise requests.HTTPError(
            f"{response.status_code} {response.reason}: {response.text}",
            response=response,
        )
    return _extract_list(response.json())


def save_world_cup_rankings(rankings: list[dict[str, Any]], db_path=DB_PATH) -> tuple[int, int]:
    if is_shared_core_read_only_mode():
        return 0, len(rankings)
    with get_connection(db_path) as conn:
        teams = conn.execute("SELECT id, name FROM teams").fetchall()
        team_lookup = {_normalize(row["name"]): row for row in teams}
        saved = 0
        skipped = 0
        for ranking in rankings:
            parsed = _parse_ranking_row(ranking)
            if not parsed:
                skipped += 1
                continue
            team = team_lookup.get(_normalize(parsed["team_name"]))
            if team is None:
                skipped += 1
                continue
            conn.execute(
                """
                INSERT INTO fifa_rankings (team_id, ranking_date, rank, points, previous_rank, source, notes)
                VALUES (?, ?, ?, ?, ?, 'footballdata.io', 'Imported via FIFA Rankings API')
                ON CONFLICT(team_id, ranking_date) DO UPDATE SET
                    rank = excluded.rank,
                    points = excluded.points,
                    previous_rank = excluded.previous_rank,
                    source = excluded.source,
                    notes = excluded.notes
                """,
                (
                    team["id"],
                    parsed["ranking_date"],
                    parsed["rank"],
                    parsed["points"],
                    parsed["previous_rank"],
                ),
            )
            saved += 1
        conn.commit()
    return saved, skipped


def _extract_list(payload) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("data", "rankings", "results", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
        data = payload.get("data")
        if isinstance(data, dict):
            for key in ("rankings", "results", "items"):
                value = data.get(key)
                if isinstance(value, list):
                    return value
    return []


def _parse_ranking_row(row: dict[str, Any]) -> dict[str, Any] | None:
    team_name = _first(row, "team", "team_name", "country", "country_name", "name")
    if isinstance(team_name, dict):
        team_name = _first(team_name, "name", "country_name", "team_name")
    rank = _first(row, "rank", "ranking", "position", "current_rank")
    if team_name is None or rank is None:
        return None
    return {
        "team_name": str(team_name),
        "ranking_date": str(_first(row, "ranking_date", "date", "period_date", "published_at") or date.today().isoformat()),
        "rank": int(float(rank)),
        "points": _float(_first(row, "points", "total_points", "ranking_points", "score")),
        "previous_rank": _int(_first(row, "previous_rank", "previous", "last_rank", "rank_previous")),
    }


def _first(row: dict[str, Any], *keys: str):
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
    return None


def _normalize(value: str) -> str:
    text = str(value).strip().lower()
    return TEAM_ALIASES.get(text, text)


def _float(value) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _int(value) -> int | None:
    if value in (None, ""):
        return None
    return int(float(value))
