from __future__ import annotations

from typing import Any

import streamlit as st


PAGE_SLUGS = {
    "Home": "home",
    "Teams": "teams",
    "Fixtures": "fixtures",
    "Groups": "groups",
    "History": "history",
    "WCQ": "wcq",
    "Bracket": "bracket",
    "FIFA Rankings": "fifa-rankings",
    "Odds": "odds",
    "Work Competition": "work-competition",
}


def remember_detail_origin(key: str) -> None:
    page_name = st.session_state.get("page_name")
    if not page_name:
        return
    st.session_state[key] = {
        "page_name": page_name,
        "selected_team_id": st.session_state.get("selected_team_id"),
        "selected_match_id": st.session_state.get("selected_match_id"),
    }


def return_to_detail_origin(key: str, fallback_page: str) -> None:
    # Session state only: the browser history bridge owns the URL/history, so
    # writing query params here would make Streamlit push a competing entry.
    origin = st.session_state.pop(key, {})
    page_name = _origin_value(origin, "page_name") or fallback_page
    st.session_state["page_name"] = page_name

    team_id = _origin_value(origin, "selected_team_id")
    if page_name == "Teams" and team_id:
        st.session_state["selected_team_id"] = int(team_id)
    else:
        st.session_state.pop("selected_team_id", None)

    match_id = _origin_value(origin, "selected_match_id")
    if page_name == "Teams" and match_id:
        st.session_state["selected_match_id"] = match_id
    else:
        st.session_state.pop("selected_match_id", None)


def clear_detail_origins() -> None:
    st.session_state.pop("fixture_return_origin", None)
    st.session_state.pop("team_return_origin", None)


def _origin_value(origin: Any, key: str):
    if isinstance(origin, dict):
        return origin.get(key)
    return None
