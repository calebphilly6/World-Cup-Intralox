from __future__ import annotations

from typing import Any

import pandas as pd

from src.config import is_deployed, is_shared_core_read_only_mode
from src.database import fetch_df
from src.odds_service import latest_tournament_winner_odds
from src.storage import browser_preferences


# Core World Cup data remains SQLite/API-backed. Personal preferences use
# browser/device storage in shared or deployed mode so no account, name, PIN, or
# hosted user database is required yet. TODO: if cross-device persistence becomes
# necessary, move preferences to a hosted database such as Supabase, Neon
# Postgres, Firebase, or similar.


def load_teams() -> pd.DataFrame:
    return fetch_df(
        """
        SELECT t.*, g.group_name
        FROM teams t
        LEFT JOIN groups g ON g.team_id = t.id
        ORDER BY t.name
        """
    )


def load_fixtures() -> pd.DataFrame:
    return fetch_df(
        """
        SELECT f.*, ht.name AS home_team, at.name AS away_team
        FROM fixtures f
        LEFT JOIN teams ht ON ht.id = f.home_team_id
        LEFT JOIN teams at ON at.id = f.away_team_id
        ORDER BY datetime(f.kickoff_utc), f.match_number
        """
    )


def load_rankings() -> pd.DataFrame:
    return fetch_df(
        """
        SELECT gr.*
        FROM global_fifa_rankings gr
        ORDER BY gr.ranking_date DESC, gr.rank
        """
    )


def load_odds() -> pd.DataFrame:
    return latest_tournament_winner_odds()


def personal_preferences_use_browser_storage() -> bool:
    return is_shared_core_read_only_mode() or is_deployed()


def load_user_preferences() -> dict[str, Any]:
    return browser_preferences.load_browser_preferences()


def save_user_preferences(preferences: dict[str, Any]) -> None:
    browser_preferences.save_browser_preferences(preferences)


def load_favorite_teams() -> list[int]:
    return browser_preferences.load_favorite_teams()


def save_favorite_teams(teams_or_legacy_arg, teams: list[int] | set[int] | None = None) -> None:
    values = teams_or_legacy_arg if teams is None else teams
    browser_preferences.save_favorite_teams(values)


def load_watchlist() -> list[dict[str, Any]]:
    return browser_preferences.load_watchlist()


def save_watchlist(watchlist_or_legacy_arg, watchlist: list[dict[str, Any]] | None = None) -> None:
    values = watchlist_or_legacy_arg if watchlist is None else watchlist
    browser_preferences.save_watchlist(values)


def load_user_brackets() -> list[dict[str, Any]]:
    bracket = browser_preferences.load_bracket_picks()
    return [bracket] if bracket else []


def save_user_bracket(bracket_or_legacy_arg, bracket: dict[str, Any] | None = None) -> None:
    values = bracket_or_legacy_arg if bracket is None else bracket
    browser_preferences.save_bracket_picks(values)


def load_user_notes() -> list[dict[str, Any]]:
    return browser_preferences.load_personal_notes()


def save_user_notes(notes_or_legacy_arg, notes: list[dict[str, Any]] | None = None) -> None:
    values = notes_or_legacy_arg if notes is None else notes
    browser_preferences.save_personal_notes(values)


def save_personal_picks(picks: Any, name: str = "default") -> None:
    predictions = browser_preferences.load_predictions()
    predictions = [item for item in predictions if str(item.get("name") or "") != name]
    predictions.append({"name": name, "picks": picks})
    browser_preferences.save_predictions(predictions)


def load_personal_picks(name: str | None = None) -> dict[str, Any]:
    predictions = browser_preferences.load_predictions()
    values = {str(item.get("name") or "default"): item.get("picks") for item in predictions}
    if name:
        return {name: values.get(name)}
    return values


def save_bracket(name: str, picks: Any, bracket_type: str = "personal") -> None:
    browser_preferences.save_bracket_picks({"name": name, "bracket_type": bracket_type, "picks": picks})


def load_brackets() -> list[dict[str, Any]]:
    bracket = browser_preferences.load_bracket_picks()
    return [bracket] if bracket else []


def preferences_are_session_only() -> bool:
    return browser_preferences.browser_preferences_are_session_only()
