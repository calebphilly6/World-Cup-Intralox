"""Fetch-and-cache layer for finished-match scorers and lineups.

Finished matches never change, so once we successfully pull goals/lineups from
ESPN we store them permanently and never hit the network again. When a fetch
comes back empty (event not yet on ESPN, lineups not posted) we record the miss
and back off so Streamlit reruns don't hammer the endpoint.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from data_sources import espn_client
from src.config import is_shared_read_only_mode
from src.database import fetch_df, get_connection

RETRY_AFTER_MINUTES = 60
# Bump this when the stored shape changes so old cache entries are refetched once.
# v2 added substitution pairings (who replaced whom).
DATA_SOURCE_TAG = "espn-v2"


def get_match_details(
    match_number: int | None,
    home_team: str,
    away_team: str,
    kickoff_utc: str | None,
) -> dict:
    """Return {"found": bool, "goals": [...], "lineups": [...]} for a match."""
    if match_number is not None:
        cached = _load_cached(match_number)
        if cached is not None:
            return cached
        # A stale-version entry must refetch now, ignoring the empty-result back-off.
        if not _is_stale(match_number) and not _should_attempt_fetch(match_number):
            return {"found": False, "goals": [], "lineups": [], "substitutions": []}

    result = _fetch_live(home_team, away_team, kickoff_utc)

    if match_number is not None:
        _store(match_number, result)
    return result


def _fetch_live(home_team: str, away_team: str, kickoff_utc: str | None) -> dict:
    event_id = espn_client.find_event_id(home_team, away_team, kickoff_utc)
    if not event_id:
        return {"found": False, "goals": [], "lineups": [], "substitutions": [], "event_id": None}
    summary = espn_client.fetch_summary(event_id)
    if not summary:
        return {"found": False, "goals": [], "lineups": [], "substitutions": [], "event_id": event_id}
    goals = espn_client.parse_goals(summary)
    lineups = espn_client.parse_lineups(summary)
    substitutions = espn_client.parse_substitutions(summary)
    return {
        "found": bool(goals or lineups),
        "goals": goals,
        "lineups": lineups,
        "substitutions": substitutions,
        "event_id": event_id,
    }


def _is_stale(match_number: int) -> bool:
    fetch = fetch_df(
        "SELECT source FROM match_detail_fetch WHERE match_number = ?", [match_number]
    )
    if fetch.empty:
        return False
    return str(fetch.iloc[0]["source"] or "") != DATA_SOURCE_TAG


def _load_cached(match_number: int) -> dict | None:
    fetch = fetch_df(
        "SELECT found, source FROM match_detail_fetch WHERE match_number = ?", [match_number]
    )
    if fetch.empty or int(fetch.iloc[0]["found"]) != 1:
        return None
    if str(fetch.iloc[0]["source"] or "") != DATA_SOURCE_TAG:
        return None  # cached by an older version; force a refetch to backfill new fields

    goals = fetch_df(
        """
        SELECT minute, team_name, scorer, assist, detail, is_penalty, is_own_goal
        FROM match_goals WHERE match_number = ? ORDER BY sort_order
        """,
        [match_number],
    )
    lineups = fetch_df(
        """
        SELECT team_name, home_away, formation, player_name, shirt_number,
               position, is_starter, subbed_in, subbed_out
        FROM match_lineups WHERE match_number = ? ORDER BY sort_order
        """,
        [match_number],
    )
    subs = fetch_df(
        """
        SELECT team_name, minute, player_on, player_off
        FROM match_substitutions WHERE match_number = ? ORDER BY sort_order
        """,
        [match_number],
    )
    return {
        "found": True,
        "goals": _goals_from_frame(goals),
        "lineups": _lineups_from_frame(lineups),
        "substitutions": _subs_from_frame(subs),
    }


def _subs_from_frame(frame: pd.DataFrame) -> list[dict]:
    return [
        {
            "team": row["team_name"],
            "minute": row["minute"],
            "player_on": row["player_on"],
            "player_off": row["player_off"],
        }
        for _, row in frame.iterrows()
    ]


def _goals_from_frame(frame: pd.DataFrame) -> list[dict]:
    return [
        {
            "minute": row["minute"],
            "team": row["team_name"],
            "scorer": row["scorer"],
            "assist": row["assist"],
            "detail": row["detail"],
            "is_penalty": bool(row["is_penalty"]),
            "is_own_goal": bool(row["is_own_goal"]),
        }
        for _, row in frame.iterrows()
    ]


def _lineups_from_frame(frame: pd.DataFrame) -> list[dict]:
    teams: dict[str, dict] = {}
    order: list[str] = []
    for _, row in frame.iterrows():
        team = row["team_name"]
        if team not in teams:
            teams[team] = {
                "team": team,
                "home_away": row["home_away"],
                "formation": row["formation"],
                "players": [],
            }
            order.append(team)
        teams[team]["players"].append(
            {
                "name": row["player_name"],
                "number": row["shirt_number"],
                "position": row["position"],
                "is_starter": bool(row["is_starter"]),
                "subbed_in": bool(row["subbed_in"]),
                "subbed_out": bool(row["subbed_out"]),
            }
        )
    return [teams[name] for name in order]


def _should_attempt_fetch(match_number: int) -> bool:
    fetch = fetch_df(
        "SELECT fetched_at FROM match_detail_fetch WHERE match_number = ?", [match_number]
    )
    if fetch.empty:
        return True
    last = pd.to_datetime(fetch.iloc[0]["fetched_at"], utc=True, errors="coerce")
    if pd.isna(last):
        return True
    age_minutes = (datetime.now(timezone.utc) - last.to_pydatetime()).total_seconds() / 60
    return age_minutes >= RETRY_AFTER_MINUTES


def _store(match_number: int, result: dict) -> None:
    if is_shared_read_only_mode():
        return
    try:
        with get_connection() as conn:
            conn.execute("DELETE FROM match_goals WHERE match_number = ?", (match_number,))
            conn.execute("DELETE FROM match_lineups WHERE match_number = ?", (match_number,))
            conn.execute("DELETE FROM match_substitutions WHERE match_number = ?", (match_number,))
            for index, goal in enumerate(result.get("goals", [])):
                conn.execute(
                    """
                    INSERT INTO match_goals (match_number, sort_order, minute, team_name,
                        scorer, assist, detail, is_penalty, is_own_goal)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        match_number, index, goal["minute"], goal["team"], goal["scorer"],
                        goal["assist"], goal["detail"], int(goal["is_penalty"]),
                        int(goal["is_own_goal"]),
                    ),
                )
            order = 0
            for team in result.get("lineups", []):
                for player in team.get("players", []):
                    conn.execute(
                        """
                        INSERT INTO match_lineups (match_number, team_name, home_away, formation,
                            sort_order, player_name, shirt_number, position, is_starter,
                            subbed_in, subbed_out)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            match_number, team["team"], team["home_away"], team["formation"],
                            order, player["name"], player["number"], player["position"],
                            int(player["is_starter"]), int(player["subbed_in"]),
                            int(player["subbed_out"]),
                        ),
                    )
                    order += 1
            for index, sub in enumerate(result.get("substitutions", [])):
                conn.execute(
                    """
                    INSERT INTO match_substitutions (match_number, sort_order, team_name,
                        minute, player_on, player_off)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        match_number, index, sub["team"], sub["minute"],
                        sub["player_on"], sub["player_off"],
                    ),
                )
            conn.execute(
                """
                INSERT INTO match_detail_fetch (match_number, espn_event_id, found, source, fetched_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(match_number) DO UPDATE SET
                    espn_event_id = excluded.espn_event_id,
                    found = excluded.found,
                    source = excluded.source,
                    fetched_at = excluded.fetched_at
                """,
                (
                    match_number, result.get("event_id"), int(bool(result.get("found"))),
                    DATA_SOURCE_TAG, datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()
    except Exception:
        # Caching is best-effort; never break the page over a write failure.
        pass
