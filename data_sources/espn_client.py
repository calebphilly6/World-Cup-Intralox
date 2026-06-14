"""Free, unofficial ESPN endpoints for World Cup match details (goals + lineups).

ESPN exposes an undocumented JSON API at site.api.espn.com that requires no key.
We use it to fill the gap left by football-data.org's free tier, which does not
return scorers or lineups. This is a best-effort source: it can change or break
without notice, so every call degrades gracefully (returns empty, never raises
into the UI).
"""
from __future__ import annotations

from typing import Any

import pandas as pd
import requests

from src.utils.team_names import team_lookup_keys

ESPN_WC_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world"
TIMEOUT_SECONDS = 20


def _espn_get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    response = requests.get(
        f"{ESPN_WC_BASE}/{path.lstrip('/')}",
        params=params or {},
        timeout=TIMEOUT_SECONDS,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    response.raise_for_status()
    return response.json()


def _scoreboard_events(date_yyyymmdd: str) -> list[dict[str, Any]]:
    try:
        return _espn_get("scoreboard", {"dates": date_yyyymmdd}).get("events", []) or []
    except Exception:
        return []


def find_event_id(home_team: str, away_team: str, kickoff_utc: str | None) -> str | None:
    """Locate the ESPN event id for a fixture by team names near its kickoff date."""
    kickoff = pd.to_datetime(kickoff_utc, utc=True, errors="coerce")
    if pd.isna(kickoff):
        return None

    home_keys = team_lookup_keys(home_team)
    away_keys = team_lookup_keys(away_team)
    if not home_keys or not away_keys:
        return None

    base_date = kickoff.date()
    # ESPN buckets matches by US date, so check the kickoff day and its neighbours.
    candidate_dates = [base_date, base_date - pd.Timedelta(days=1), base_date + pd.Timedelta(days=1)]
    for date in candidate_dates:
        for event in _scoreboard_events(pd.Timestamp(date).strftime("%Y%m%d")):
            competitors = (event.get("competitions") or [{}])[0].get("competitors") or []
            names = {c.get("team", {}).get("displayName") for c in competitors}
            event_keys = set()
            for name in names:
                event_keys |= team_lookup_keys(name)
            if (home_keys & event_keys) and (away_keys & event_keys):
                return str(event.get("id"))
    return None


def fetch_summary(event_id: str) -> dict[str, Any] | None:
    try:
        return _espn_get("summary", {"event": event_id})
    except Exception:
        return None


def parse_goals(summary: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract scoring plays (excluding penalty shootouts) in chronological order."""
    goals: list[dict[str, Any]] = []
    for event in summary.get("keyEvents", []) or []:
        if not event.get("scoringPlay") or event.get("shootout"):
            continue
        participants = event.get("participants") or []
        scorer = (participants[0].get("athlete", {}).get("displayName") if participants else "") or ""
        assist = participants[1].get("athlete", {}).get("displayName") if len(participants) > 1 else ""
        detail = str(event.get("type", {}).get("text") or "Goal")
        goals.append(
            {
                "minute": str(event.get("clock", {}).get("displayValue") or "").strip(),
                "team": event.get("team", {}).get("displayName") or "",
                "scorer": scorer or str(event.get("shortText") or "").replace(" Goal", "").strip(),
                "assist": assist or "",
                "detail": detail,
                "is_penalty": "penalt" in detail.lower(),
                "is_own_goal": "own goal" in detail.lower(),
            }
        )
    return goals


def parse_substitutions(summary: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract substitutions as (player on, player off) pairs with minute."""
    subs: list[dict[str, Any]] = []
    for event in summary.get("keyEvents", []) or []:
        if str(event.get("type", {}).get("type") or "").lower() != "substitution":
            continue
        participants = event.get("participants") or []
        if len(participants) < 2:
            continue
        subs.append(
            {
                "minute": str(event.get("clock", {}).get("displayValue") or "").strip(),
                "team": event.get("team", {}).get("displayName") or "",
                "player_on": participants[0].get("athlete", {}).get("displayName") or "",
                "player_off": participants[1].get("athlete", {}).get("displayName") or "",
            }
        )
    return subs


def parse_lineups(summary: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract both teams' lineups: formation plus starters and substitutes."""
    lineups: list[dict[str, Any]] = []
    for team in summary.get("rosters", []) or []:
        players = []
        for entry in team.get("roster", []) or []:
            athlete = entry.get("athlete") or {}
            position = entry.get("position") or {}
            players.append(
                {
                    "name": athlete.get("displayName") or "",
                    "number": str(entry.get("jersey") or "").strip(),
                    "position": position.get("abbreviation") if isinstance(position, dict) else str(position or ""),
                    "is_starter": bool(entry.get("starter")),
                    "subbed_in": bool(entry.get("subbedIn")),
                    "subbed_out": bool(entry.get("subbedOut")),
                }
            )
        lineups.append(
            {
                "team": team.get("team", {}).get("displayName") or "",
                "home_away": team.get("homeAway") or "",
                "formation": team.get("formation") or "",
                "players": players,
            }
        )
    return lineups
