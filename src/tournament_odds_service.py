from __future__ import annotations

import streamlit as st

from src.api_clients.odds_client import (
    fetch_outrights,
    find_world_cup_sport_key,
    flatten_outrights,
    get_api_key,
    save_api_usage,
    save_odds_rows,
)
from src.config import get_section
from src.odds_refresh import daily_odds_refresh_key
from src.refresh_gate import mark_refresh_completed, refresh_was_completed


ODDS_PROVIDER = "the_odds_api"
ODDS_REFRESH_RESOURCE = "world_cup_winner_odds"


@st.cache_data(show_spinner=False)
def refresh_tournament_odds_if_available(refresh_key: str | None = None) -> dict:
    api_key = get_api_key(None)
    if not api_key:
        return {"saved": 0}
    refresh_key = refresh_key or daily_odds_refresh_key()
    if refresh_was_completed(ODDS_PROVIDER, ODDS_REFRESH_RESOURCE, refresh_key):
        return {"saved": 0, "skipped": True}

    odds_config = get_section("odds")
    sport_key = str(odds_config.get("sport_key", "") or "").strip()
    regions = odds_config.get("regions", "us") or "us"
    try:
        resolved_key = sport_key or find_world_cup_sport_key(api_key)
        if not resolved_key:
            return {"saved": 0, "error": "Could not find a World Cup odds market. Set [odds].sport_key in secrets.toml."}
        try:
            payload, quota = fetch_outrights(
                api_key,
                resolved_key,
                regions=regions,
                odds_format="american",
                bookmakers="draftkings",
            )
        except Exception as first_exc:
            fallback_key = find_world_cup_sport_key(api_key)
            if not fallback_key or fallback_key == resolved_key:
                raise first_exc
            payload, quota = fetch_outrights(
                api_key,
                fallback_key,
                regions=regions,
                odds_format="american",
                bookmakers="draftkings",
            )
        rows = flatten_outrights(payload, odds_format="american")
        saved = save_odds_rows(rows)
        save_api_usage(quota)
        mark_refresh_completed(ODDS_PROVIDER, ODDS_REFRESH_RESOURCE, refresh_key)
        return {"saved": saved}
    except Exception as exc:
        return {"saved": 0, "error": f"Automatic odds refresh failed: {exc}"}
