from __future__ import annotations

import streamlit as st

from data_sources.football_data_client import FootballDataError, get_football_data_token
from src.config import is_shared_core_read_only_mode
from src.football_data_service import (
    cached_connection_test,
    cached_matches,
    cached_standings,
    cached_teams,
    clear_football_data_cache,
)


def render() -> None:
    st.title("football-data.org Setup")
    if is_shared_core_read_only_mode():
        st.info("Shared mode protects official World Cup data. API setup and manual refresh controls are disabled.")
        return

    st.write(
        "Store your football-data.org token in `.streamlit/secrets.toml` or in Streamlit Community Cloud secrets."
    )
    st.code('FOOTBALL_DATA_API_KEY = "paste-your-football-data-token-here"', language="toml")

    if get_football_data_token():
        st.success("football-data.org token found. It is hidden and will not be displayed.")
    else:
        st.warning("No football-data.org token found yet. Add `FOOTBALL_DATA_API_KEY` to Streamlit secrets, then restart Streamlit.")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Test football-data.org connection", type="primary"):
            try:
                payload = cached_connection_test()
                st.success("football-data.org connection worked.")
                st.json(
                    {
                        "competition": payload.get("competition", {}).get("name"),
                        "matches_returned": len(payload.get("matches", []) or []),
                    }
                )
            except FootballDataError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(f"Could not test football-data.org connection: {exc}")

    with c2:
        if st.button("Refresh football-data.org data"):
            clear_football_data_cache()
            st.success("football-data.org cache cleared. The next page load will refetch matches, teams, and standings.")

    st.divider()
    st.subheader("Cached Data Preview")
    st.caption(
        "Caching prevents wasting API calls on Streamlit reruns. The free tier may provide delayed scores rather than true live updates."
    )

    try:
        st.metric("Matches", len(cached_matches()))
        st.metric("Teams", len(cached_teams()))
        standings = cached_standings()
        st.metric("Standings Rows", len(standings))
    except FootballDataError as exc:
        st.error(str(exc))
    except Exception as exc:
        st.error(f"Could not load football-data.org preview: {exc}")
