from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

from data_sources.football_data_client import (
    get_world_cup_2026_matches,
    get_world_cup_2026_standings,
    get_world_cup_2026_teams,
    normalize_matches_to_dataframe,
    normalize_standings_to_dataframe,
    normalize_teams_to_dataframe,
    test_football_data_connection,
)


# football-data.org free plans have request limits. These caches keep normal page
# navigation from spending an API call every time Streamlit reruns the script.
# Scores (fixtures/results) refresh hourly: the matches feed is keyed on an hourly
# refresh key, so the first page load in each new hour spends one API call and every
# load within the hour is served from cache. Teams change rarely, so they stay daily.
MATCHES_TTL_SECONDS = 60 * 60
TEAMS_TTL_SECONDS = 60 * 60 * 24
STANDINGS_TTL_SECONDS = 60 * 60
APP_TIMEZONE = ZoneInfo("America/Chicago")


@st.cache_data(ttl=MATCHES_TTL_SECONDS)
def cached_connection_test() -> dict:
    return test_football_data_connection()


def cached_matches():
    return _cached_matches(_hourly_fixture_refresh_key())


def hourly_fixture_refresh_key() -> str:
    return _hourly_fixture_refresh_key()


@st.cache_data(ttl=MATCHES_TTL_SECONDS)
def _cached_matches(refresh_key: str):
    return normalize_matches_to_dataframe(get_world_cup_2026_matches())


@st.cache_data(ttl=TEAMS_TTL_SECONDS)
def cached_teams():
    return normalize_teams_to_dataframe(get_world_cup_2026_teams())


@st.cache_data(ttl=STANDINGS_TTL_SECONDS)
def cached_standings():
    return normalize_standings_to_dataframe(get_world_cup_2026_standings())


def clear_football_data_cache() -> None:
    cached_connection_test.clear()
    _cached_matches.clear()
    cached_teams.clear()
    cached_standings.clear()


def _hourly_fixture_refresh_key(now: datetime | None = None) -> str:
    # Changes value at the top of every local hour (e.g. "2026-06-18T14"), so the
    # cached matches feed pulls fresh scores from football-data.org once per hour.
    local_now = now.astimezone(APP_TIMEZONE) if now else datetime.now(APP_TIMEZONE)
    return local_now.strftime("%Y-%m-%dT%H")
