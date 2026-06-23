"""Browser-history bridge so the back/forward buttons drive in-app navigation.

Streamlit reruns the whole script on every interaction and manages the URL with
``replaceState``, so the browser Back button never lands on the previous in-app
view. This module pairs a small front-end component (``history_nav_component``)
with the page state: each forward navigation becomes a real history entry, the
view scrolls to the top, and pressing Back restores the previous view *and* its
scroll position.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlencode

import streamlit as st
import streamlit.components.v1 as components

from src.database import fetch_df
from src.navigation import PAGE_SLUGS, remember_detail_origin
from src.utils.team_names import team_lookup_keys


SLUG_TO_PAGE = {slug: page_name for page_name, slug in PAGE_SLUGS.items()}

COMPONENT_DIR = Path(__file__).resolve().parent / "history_nav_component"
HISTORY_NAV_COMPONENT = components.declare_component("history_nav", path=str(COMPONENT_DIR))

_HANDLED_NONCE_KEY = "_history_nav_handled_nonce"


def current_nav_token() -> str:
    """Serialize the navigable view into a compact, parseable token.

    Examples: ``"teams"``, ``"teams|team=5"``, ``"teams|team=5|match=M50"``,
    ``"fixtures|fixture=M50"``.
    """
    page_name = st.session_state.get("page_name") or "Home"
    slug = PAGE_SLUGS.get(page_name, PAGE_SLUGS["Home"])
    parts = [slug]

    if page_name == "Teams":
        team_id = st.session_state.get("selected_team_id")
        if team_id:
            parts.append(f"team={int(team_id)}")
            match_id = st.session_state.get("selected_match_id")
            if match_id:
                parts.append(f"match={match_id}")
    elif page_name == "Fixtures":
        fixture_id = st.session_state.get("selected_fixture_id")
        if fixture_id:
            parts.append(f"fixture={fixture_id}")

    return "|".join(parts)


def current_nav_url() -> str:
    """Query string the bridge writes to the address bar for the current view.

    Set via the History API by the component (never ``st.query_params``), so the
    URL reflects the view and survives a refresh while Streamlit stays out of
    history management. Mirrors the deep-link params app.py reads on first load
    (page / team_id / fixture); a match focus within a team falls back to the
    team page on refresh.
    """
    page_name = st.session_state.get("page_name") or "Home"
    slug = PAGE_SLUGS.get(page_name, PAGE_SLUGS["Home"])
    params: list[tuple[str, str]] = [("page", slug)]

    if page_name == "Teams":
        team_id = st.session_state.get("selected_team_id")
        if team_id:
            params.append(("team_id", str(int(team_id))))
    elif page_name == "Fixtures":
        fixture_id = st.session_state.get("selected_fixture_id")
        if fixture_id:
            params.append(("fixture", str(fixture_id)))

    return "?" + urlencode(params)


def apply_nav_token(token: str) -> None:
    """Restore session state for a token sent back by Back/Forward.

    Deliberately does NOT touch ``st.query_params``. The browser already restores
    the matching URL on ``popstate``, and writing query params here would make
    Streamlit push its own history entry mid-rerun, truncating the forward stack
    and breaking repeated Back/Forward presses.
    """
    parts = token.split("|") if token else ["home"]
    slug = parts[0] or "home"
    page_name = SLUG_TO_PAGE.get(slug, "Home")

    st.session_state["page_name"] = page_name
    # Match the page we are restoring so app.py's "entered Teams from elsewhere"
    # guard does not wipe the selection we are about to set.
    st.session_state["_previous_page_name"] = page_name

    for key in ("selected_team_id", "selected_match_id", "selected_fixture_id", "selected_fixture_row"):
        st.session_state.pop(key, None)

    for extra in parts[1:]:
        key, _, value = extra.partition("=")
        if key == "team":
            try:
                st.session_state["selected_team_id"] = int(value)
            except ValueError:
                continue
        elif key == "match":
            st.session_state["selected_match_id"] = value
        elif key == "fixture":
            st.session_state["selected_fixture_id"] = value


@st.cache_data(show_spinner=False)
def _team_id_by_key() -> dict[str, int]:
    """Map every normalized team-name key (incl. aliases) to its team id."""
    rows = fetch_df("SELECT id, name FROM teams")
    lookup: dict[str, int] = {}
    for _, row in rows.iterrows():
        for key in team_lookup_keys(row["name"]):
            lookup.setdefault(key, int(row["id"]))
    return lookup


def open_team_by_name(name: str) -> bool:
    """Open a team's profile by display name. Returns True if the team was found."""
    lookup = _team_id_by_key()
    team_id = None
    for key in team_lookup_keys(name):
        if key in lookup:
            team_id = lookup[key]
            break
    if team_id is None:
        return False
    remember_detail_origin("team_return_origin")
    st.session_state["page_name"] = "Teams"
    st.session_state["selected_team_id"] = team_id
    st.session_state.pop("selected_match_id", None)
    st.session_state.pop("selected_fixture_id", None)
    st.session_state.pop("selected_fixture_row", None)
    return True


def open_fixture_by_match(match: str) -> bool:
    """Open the Fixtures focus card for an official match number (e.g. from the
    bracket). Works even when the knockout teams aren't filled in yet — the
    Fixtures page resolves the row from the feed by match number."""
    text = str(match or "").strip()
    if not text:
        return False
    match_id = text if text.upper().startswith("M") else f"M{text}"

    remember_detail_origin("fixture_return_origin")
    st.session_state["page_name"] = "Fixtures"
    st.session_state["selected_fixture_id"] = match_id
    st.session_state.pop("selected_fixture_row", None)
    st.session_state.pop("selected_team_id", None)
    st.session_state.pop("selected_match_id", None)
    return True


def render_history_bridge() -> None:
    """Render the bridge and, if Back/Forward was pressed, restore that view.

    Call this once per run after the page state is finalized but before the page
    body renders, so a Back press reruns with the right view from the start.
    """
    token = current_nav_token()
    result = HISTORY_NAV_COMPONENT(token=token, url=current_nav_url(), key="history_nav", default=None)
    if not isinstance(result, dict):
        return

    nonce = result.get("nonce")
    if not nonce or nonce == st.session_state.get(_HANDLED_NONCE_KEY):
        return
    st.session_state[_HANDLED_NONCE_KEY] = nonce

    kind = result.get("kind")
    if kind == "team":
        if open_team_by_name(str(result.get("team") or "")):
            st.rerun()
        return
    if kind == "fixture":
        if open_fixture_by_match(str(result.get("match") or "")):
            st.rerun()
        return

    target = result.get("token")
    if target and target != token:
        apply_nav_token(target)
        st.rerun()
