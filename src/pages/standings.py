from __future__ import annotations

import streamlit as st

from data_sources.football_data_client import FootballDataError
from src.config import is_shared_core_read_only_mode
from src.football_data_service import cached_standings, clear_football_data_cache


def render() -> None:
    st.title("Standings")
    st.caption("World Cup 2026 standings from football-data.org. Free-tier scores and tables may be delayed.")

    if is_shared_core_read_only_mode():
        st.caption("Shared mode: manual API refresh is disabled.")
    elif st.button("Refresh football-data.org data"):
        clear_football_data_cache()
        st.success("football-data.org cache cleared. Fetching fresh standings data.")

    try:
        standings = cached_standings()
    except FootballDataError as exc:
        st.error(str(exc))
        return
    except Exception as exc:
        st.error(f"Could not load football-data.org standings: {exc}")
        return

    if standings.empty:
        st.info("Standings are not available yet. They should appear once the group stage begins.")
        return

    groups = sorted(standings["group"].dropna().unique())
    selected_groups = st.multiselect("Group", groups)
    filtered = standings
    if selected_groups:
        filtered = filtered[filtered["group"].isin(selected_groups)]

    st.dataframe(
        filtered[
            [
                "stage",
                "type",
                "group",
                "position",
                "team",
                "short_name",
                "tla",
                "played",
                "won",
                "draw",
                "lost",
                "points",
                "goals_for",
                "goals_against",
                "goal_difference",
            ]
        ],
        width="stretch",
        hide_index=True,
    )
