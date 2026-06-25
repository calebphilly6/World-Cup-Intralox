from __future__ import annotations

import base64
from pathlib import Path

import pandas as pd
import streamlit as st

from data_sources.football_data_client import FootballDataError
from src.database import fetch_df
from src.fixture_display import flag_lookup_with_aliases
from src.football_data_service import cached_matches
from src.knockout_participants import apply_sticky_knockout_participants
from src.knockout_slots import all_slot_teams
from src.official_match_reference import apply_official_match_reference
from src.pages.bracket_renderer import render_live_bracket_html


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ASSETS_DIR = PROJECT_ROOT / "assets"


def render() -> None:
    st.title("Bracket")

    fixtures, warning = _knockout_fixtures()
    if warning:
        st.warning(warning)

    st.iframe(
        render_live_bracket_html(fixtures, _flag_lookup(), _bracket_background_uri(), all_slot_teams()),
        height=1040,
    )


def _knockout_fixtures() -> tuple[pd.DataFrame, str]:
    try:
        fixtures = apply_official_match_reference(cached_matches())
    except FootballDataError as exc:
        return apply_sticky_knockout_participants(_local_fixture_fallback()), f"{exc} Showing the official bracket slots until fixture data is available."
    except Exception as exc:
        return apply_sticky_knockout_participants(_local_fixture_fallback()), f"Could not load football-data.org fixtures: {exc}. Showing the official bracket slots until fixture data is available."

    if fixtures.empty:
        return apply_sticky_knockout_participants(_local_fixture_fallback()), ""
    fixtures = fixtures.copy()
    fixtures["official_match_number"] = pd.to_numeric(fixtures["official_match_number"], errors="coerce")
    fixtures = fixtures[fixtures["official_match_number"].between(73, 104)].copy()
    return apply_sticky_knockout_participants(fixtures), ""


def _local_fixture_fallback() -> pd.DataFrame:
    fixtures = fetch_df(
        """
        SELECT f.match_number AS official_match_number, f.kickoff_utc AS utc_date,
               ht.name AS home_team, at.name AS away_team,
               f.stage, f.group_name AS "group", COALESCE(m.city, f.city) AS venue,
               COALESCE(m.city, f.city) AS city, f.status, f.home_score, f.away_score
        FROM fixtures f
        LEFT JOIN teams ht ON ht.id = f.home_team_id
        LEFT JOIN teams at ON at.id = f.away_team_id
        LEFT JOIN match_city_reference m ON m.match_number = f.match_number
        WHERE f.match_number BETWEEN 73 AND 104
        ORDER BY f.match_number
        """
    )
    if fixtures.empty:
        return fixtures
    fixtures["match_id"] = fixtures["official_match_number"].map(lambda value: f"M{int(value)}" if pd.notna(value) else "")
    return fixtures


@st.cache_data(show_spinner=False)
def _flag_lookup() -> dict[str, str]:
    # Alias-aware so feed names that differ from the teams table (e.g. the feed's
    # "United States" vs. our "USA") still resolve to a flag.
    return flag_lookup_with_aliases(fetch_df("SELECT name, country_code FROM teams"))


@st.cache_data(show_spinner=False)
def _bracket_background_uri() -> str | None:
    for path in ASSETS_DIR.glob("*"):
        if path.is_file() and path.stem.lower() == "world-cup-background" and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
            mime = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".webp": "image/webp",
            }[path.suffix.lower()]
            encoded = base64.b64encode(path.read_bytes()).decode("ascii")
            return f"data:{mime};base64,{encoded}"
    return None
