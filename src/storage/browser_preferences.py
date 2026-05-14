from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st
import streamlit.components.v1 as components


PREFERENCES_KEY = "wc2026_browser_preferences_v1"
SESSION_KEY = "_browser_preferences"
LOADED_KEY = "_browser_preferences_loaded"
STORAGE_FAILED_KEY = "_browser_preferences_storage_failed"
PENDING_SAVE_KEY = "_browser_preferences_pending_save"
PENDING_CLEAR_KEY = "_browser_preferences_pending_clear"
COMPONENT_DIR = Path(__file__).resolve().parent / "browser_preferences_component"
BROWSER_PREFERENCES_COMPONENT = components.declare_component("browser_preferences", path=str(COMPONENT_DIR))

DEFAULT_PREFERENCES: dict[str, Any] = {
    "favorite_teams": [],
    "watchlist": [],
    "bracket_picks": {},
    "predictions": [],
    "personal_notes": [],
    "dark_horses": [],
    "overrated_teams": [],
    "underrated_teams": [],
}


def load_browser_preferences() -> dict[str, Any]:
    if SESSION_KEY not in st.session_state:
        st.session_state[SESSION_KEY] = _default_preferences()
    return _merge_defaults(st.session_state[SESSION_KEY])


def save_browser_preferences(preferences: dict[str, Any]) -> None:
    st.session_state[SESSION_KEY] = _merge_defaults(preferences)
    st.session_state[LOADED_KEY] = True
    st.session_state[PENDING_SAVE_KEY] = True


def load_favorite_teams() -> list[int]:
    values = load_browser_preferences().get("favorite_teams", [])
    return sorted({team_id for team_id in (_safe_int(value) for value in values) if team_id is not None})


def save_favorite_teams(teams: list[int] | set[int]) -> None:
    preferences = load_browser_preferences()
    preferences["favorite_teams"] = sorted({int(team_id) for team_id in teams})
    save_browser_preferences(preferences)


def load_watchlist() -> list[dict[str, Any]]:
    return _as_list(load_browser_preferences().get("watchlist"))


def save_watchlist(watchlist: list[dict[str, Any]]) -> None:
    preferences = load_browser_preferences()
    preferences["watchlist"] = _as_list(watchlist)
    save_browser_preferences(preferences)


def load_bracket_picks() -> dict[str, Any]:
    value = load_browser_preferences().get("bracket_picks", {})
    return value if isinstance(value, dict) else {}


def save_bracket_picks(bracket: dict[str, Any]) -> None:
    preferences = load_browser_preferences()
    preferences["bracket_picks"] = dict(bracket)
    save_browser_preferences(preferences)


def load_predictions() -> list[dict[str, Any]]:
    return _as_list(load_browser_preferences().get("predictions"))


def save_predictions(predictions: list[dict[str, Any]]) -> None:
    preferences = load_browser_preferences()
    preferences["predictions"] = _as_list(predictions)
    save_browser_preferences(preferences)


def load_personal_notes() -> list[dict[str, Any]]:
    return _as_list(load_browser_preferences().get("personal_notes"))


def save_personal_notes(notes: list[dict[str, Any]]) -> None:
    preferences = load_browser_preferences()
    preferences["personal_notes"] = _as_list(notes)
    save_browser_preferences(preferences)


def clear_browser_preferences() -> None:
    st.session_state[SESSION_KEY] = _default_preferences()
    st.session_state[LOADED_KEY] = True
    st.session_state[PENDING_CLEAR_KEY] = True


def browser_preferences_are_session_only() -> bool:
    return bool(st.session_state.get(STORAGE_FAILED_KEY))


def render_browser_preferences_bridge() -> None:
    pending_save = bool(st.session_state.pop(PENDING_SAVE_KEY, False))
    pending_clear = bool(st.session_state.pop(PENDING_CLEAR_KEY, False))
    preferences = _merge_defaults(st.session_state.get(SESSION_KEY, _default_preferences()))
    action = "clear" if pending_clear else "save" if pending_save else "load"
    result = BROWSER_PREFERENCES_COMPONENT(
        storage_key=PREFERENCES_KEY,
        action=action,
        preferences=preferences,
        defaults=_default_preferences(),
        key="browser_preferences_component",
        default=None,
    )
    if not isinstance(result, dict):
        return

    if result.get("ok"):
        st.session_state[SESSION_KEY] = _merge_defaults(result.get("preferences") or {})
        st.session_state[LOADED_KEY] = True
        st.session_state[STORAGE_FAILED_KEY] = False
        return

    st.session_state[STORAGE_FAILED_KEY] = True


def _default_preferences() -> dict[str, Any]:
    return {key: list(value) if isinstance(value, list) else dict(value) if isinstance(value, dict) else value for key, value in DEFAULT_PREFERENCES.items()}


def _merge_defaults(preferences: dict[str, Any]) -> dict[str, Any]:
    merged = _default_preferences()
    if isinstance(preferences, dict):
        merged.update({key: value for key, value in preferences.items() if key in merged})
    return merged


def _as_list(value: Any) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
