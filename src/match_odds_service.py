from __future__ import annotations

import streamlit as st

from src.api_clients.odds_client import (
    fetch_match_odds,
    flatten_match_odds,
    get_api_key,
    relink_fixture_odds_rows,
    save_api_usage,
    save_fixture_odds_rows,
)
from src.config import get_section, is_shared_core_read_only_mode
from src.odds_refresh import daily_odds_refresh_key
from src.refresh_gate import mark_refresh_completed, refresh_was_completed


ODDS_PROVIDER = "the_odds_api"
MATCH_ODDS_REFRESH_RESOURCE = "world_cup_match_odds"
DEFAULT_MATCH_ODDS_SPORT_KEY = "soccer_fifa_world_cup"
DEFAULT_MATCH_ODDS_MARKETS = "h2h,spreads,totals"


@st.cache_data(show_spinner=False)
def refresh_match_odds_if_available(refresh_key: str | None = None) -> dict:
    if is_shared_core_read_only_mode():
        return {"saved": 0, "read_only": True}
    api_key = get_api_key(None)
    if not api_key:
        return {"saved": 0}
    refresh_key = refresh_key or daily_odds_refresh_key()
    if refresh_was_completed(ODDS_PROVIDER, MATCH_ODDS_REFRESH_RESOURCE, refresh_key):
        return {"saved": 0, "skipped": True}

    odds_config = get_section("odds")
    sport_key = str(odds_config.get("match_sport_key") or DEFAULT_MATCH_ODDS_SPORT_KEY).strip()
    regions = str(odds_config.get("regions") or "us").strip()
    markets = str(odds_config.get("match_markets") or DEFAULT_MATCH_ODDS_MARKETS).strip()
    bookmakers = str(odds_config.get("bookmakers") or "").strip() or None
    try:
        payload, quota = fetch_match_odds(
            api_key=api_key,
            sport_key=sport_key,
            regions=regions,
            markets=markets,
            odds_format="american",
            bookmakers=bookmakers,
        )
        rows = flatten_match_odds(payload, odds_format="american")
        saved = save_fixture_odds_rows(rows)
        relink_fixture_odds_rows()
        save_api_usage(quota)
        mark_refresh_completed(ODDS_PROVIDER, MATCH_ODDS_REFRESH_RESOURCE, refresh_key)
        return {"saved": saved}
    except Exception as exc:
        return {"saved": 0, "error": f"Automatic match odds refresh failed: {exc}"}
