from __future__ import annotations

import os
from datetime import datetime
from typing import Any

import pandas as pd
import requests
from zoneinfo import ZoneInfo

from src.config import get_secret, is_shared_read_only_mode
from src.database import get_connection


BASE_URL = "https://api.football-data.org/v4"
COMPETITION_CODE = "WC"
SEASON = 2026
TIMEOUT_SECONDS = 25


class FootballDataError(RuntimeError):
    """Raised when football-data.org cannot be called cleanly."""


def get_football_data_token(secrets: dict | None = None) -> str | None:
    """Read the token from Streamlit secrets first, then environment variables."""
    if secrets is not None:
        try:
            api_keys = secrets.get("api_keys", {})
            token = (
                secrets.get("FOOTBALL_DATA_API_KEY")
                or secrets.get("FOOTBALL_DATA_TOKEN")
                or api_keys.get("football_data")
                or api_keys.get("football_data_api")
            )
            if token:
                return str(token)
        except Exception:
            pass

    return get_secret("FOOTBALL_DATA_API_KEY") or os.getenv("FOOTBALL_DATA_TOKEN")


def football_data_get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    token = get_football_data_token()
    if not token:
        raise FootballDataError(
            "Missing FOOTBALL_DATA_API_KEY. Add it to Streamlit secrets or .streamlit/secrets.toml."
        )

    response = requests.get(
        f"{BASE_URL}/{path.lstrip('/')}",
        headers={"X-Auth-Token": token},
        params=params or {},
        timeout=TIMEOUT_SECONDS,
    )

    if response.status_code == 403:
        raise FootballDataError("football-data.org returned 403. Check that your token is correct and has access to this competition.")
    if response.status_code == 429:
        raise FootballDataError("football-data.org rate limit exceeded. Wait for your quota to reset before refreshing again.")
    if response.status_code != 200:
        raise FootballDataError(f"football-data.org returned HTTP {response.status_code}. Check the request and try again later.")

    save_football_data_usage(response.headers)
    return response.json()


def save_football_data_usage(headers: requests.structures.CaseInsensitiveDict) -> None:
    if is_shared_read_only_mode():
        return
    remaining = (
        headers.get("X-Requests-Available-Minute")
        or headers.get("X-RequestsAvailable")
        or headers.get("X-RateLimit-Remaining")
    )
    reset = headers.get("X-RequestCounter-Reset") or headers.get("Retry-After")
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO api_usage (provider, last_request_cost, requests_used, requests_remaining)
            VALUES ('football_data_org', ?, ?, ?)
            """,
            ("1", reset, remaining),
        )
        conn.commit()


def test_football_data_connection() -> dict[str, Any]:
    return get_world_cup_2026_matches()


def get_world_cup_2026_matches() -> dict[str, Any]:
    return football_data_get(f"/competitions/{COMPETITION_CODE}/matches", {"season": SEASON})


def get_world_cup_2026_teams() -> dict[str, Any]:
    return football_data_get(f"/competitions/{COMPETITION_CODE}/teams", {"season": SEASON})


def get_world_cup_2026_standings() -> dict[str, Any]:
    return football_data_get(f"/competitions/{COMPETITION_CODE}/standings", {"season": SEASON})


def normalize_matches_to_dataframe(matches_json: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for match in matches_json.get("matches", []) or []:
        home = match.get("homeTeam") or {}
        away = match.get("awayTeam") or {}
        score = match.get("score") or {}
        full_time = score.get("fullTime") or {}
        local_dt = _local_datetime(match.get("utcDate"))
        rows.append(
            {
                "match_id": match.get("id"),
                "utc_date": match.get("utcDate"),
                "local_date": local_dt.date().isoformat() if local_dt else None,
                "local_time": local_dt.strftime("%I:%M %p") if local_dt else None,
                "status": match.get("status"),
                "stage": match.get("stage"),
                "group": match.get("group"),
                "matchday": match.get("matchday"),
                "venue": match.get("venue"),
                "home_team": home.get("name"),
                "home_team_short": home.get("shortName"),
                "home_team_tla": home.get("tla"),
                "away_team": away.get("name"),
                "away_team_short": away.get("shortName"),
                "away_team_tla": away.get("tla"),
                "home_score": full_time.get("home"),
                "away_score": full_time.get("away"),
                "winner": score.get("winner"),
                "last_updated": match.get("lastUpdated"),
            }
        )
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["_sort_date"] = pd.to_datetime(df["utc_date"], utc=True, errors="coerce")
    return df.sort_values("_sort_date").drop(columns=["_sort_date"])


def normalize_teams_to_dataframe(teams_json: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for team in teams_json.get("teams", []) or []:
        rows.append(
            {
                "team_id": team.get("id"),
                "name": team.get("name"),
                "short_name": team.get("shortName"),
                "tla": team.get("tla"),
                "crest": team.get("crest"),
                "country": team.get("area", {}).get("name") if isinstance(team.get("area"), dict) else None,
                "club_colors": team.get("clubColors"),
            }
        )
    return pd.DataFrame(rows)


def normalize_standings_to_dataframe(standings_json: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for standing in standings_json.get("standings", []) or []:
        for table_row in standing.get("table", []) or []:
            team = table_row.get("team") or {}
            rows.append(
                {
                    "stage": standing.get("stage"),
                    "type": standing.get("type"),
                    "group": standing.get("group"),
                    "position": table_row.get("position"),
                    "team": team.get("name"),
                    "short_name": team.get("shortName"),
                    "tla": team.get("tla"),
                    "played": table_row.get("playedGames"),
                    "won": table_row.get("won"),
                    "draw": table_row.get("draw"),
                    "lost": table_row.get("lost"),
                    "points": table_row.get("points"),
                    "goals_for": table_row.get("goalsFor"),
                    "goals_against": table_row.get("goalsAgainst"),
                    "goal_difference": table_row.get("goalDifference"),
                }
            )
    return pd.DataFrame(rows)


def _local_datetime(value: str | None):
    if not value:
        return None
    parsed = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.to_pydatetime().astimezone(ZoneInfo("America/Chicago"))
