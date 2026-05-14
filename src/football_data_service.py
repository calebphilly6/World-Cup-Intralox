from __future__ import annotations

from datetime import datetime, time, timedelta
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
# Free-tier scores may be delayed, so this app treats the feed as schedule/results
# data rather than true live scoring.
MATCHES_TTL_SECONDS = 60 * 60 * 6
TEAMS_TTL_SECONDS = 60 * 60 * 24
STANDINGS_TTL_SECONDS = 60 * 30
FIXTURE_REFRESH_TIME = time(3, 0)
APP_TIMEZONE = ZoneInfo("America/Chicago")


@st.cache_data(ttl=MATCHES_TTL_SECONDS)
def cached_connection_test() -> dict:
    return test_football_data_connection()


def cached_matches():
    return _cached_matches(_daily_fixture_refresh_key())


def daily_fixture_refresh_key() -> str:
    return _daily_fixture_refresh_key()


@st.cache_data(ttl=TEAMS_TTL_SECONDS)
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


def _daily_fixture_refresh_key(now: datetime | None = None) -> str:
    local_now = now.astimezone(APP_TIMEZONE) if now else datetime.now(APP_TIMEZONE)
    refresh_day = local_now.date()
    if local_now.time() < FIXTURE_REFRESH_TIME:
        refresh_day -= timedelta(days=1)
    return refresh_day.isoformat()
