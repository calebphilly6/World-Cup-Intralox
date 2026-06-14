from __future__ import annotations

import base64
import re
import unicodedata
from pathlib import Path

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
JERSEYS_DIR = PROJECT_ROOT / "assets" / "jerseys"
JERSEY_HEADERS_DIR = JERSEYS_DIR / "headers_norm"


def jersey_slug(team_name: str | None) -> str:
    """Slug used for jersey filenames (matches the asset build step)."""
    text = unicodedata.normalize("NFKD", str(team_name or "")).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


# Asset files use the raw FIFA team names, but several teams are shown under a
# different display name (e.g. "Congo DR" -> "DR Congo"). Map those display
# slugs back to the on-disk slug so the jersey still resolves either way.
SLUG_ALIASES = {
    "dr-congo": "congo-dr",
    "ivory-coast": "cote-d-ivoire",
    "iran": "ir-iran",
    "turkey": "turkiye",
}


def _candidate_slugs(team_name: str | None) -> list[str]:
    slug = jersey_slug(team_name)
    if not slug:
        return []
    aliased = SLUG_ALIASES.get(slug)
    return [slug, aliased] if aliased else [slug]


def jersey_path(team_name: str | None) -> Path | None:
    for slug in _candidate_slugs(team_name):
        path = JERSEYS_DIR / f"{slug}.webp"
        if path.exists():
            return path
    return None


def team_jersey_data_uri(team_name: str | None) -> str:
    """Return a browser-safe data URI for a team's home kit, or '' if missing."""
    path = jersey_path(team_name)
    if path is None:
        return ""
    return _jersey_data_uri(str(path), path.stat().st_mtime_ns)


def jersey_header_path(team_name: str | None) -> Path | None:
    for slug in _candidate_slugs(team_name):
        path = JERSEY_HEADERS_DIR / f"{slug}.webp"
        if path.exists():
            return path
    return None


def team_jersey_header_data_uri(team_name: str | None) -> str:
    """Return a data URI for a team's crest-centered kit header crop, or '' if missing."""
    path = jersey_header_path(team_name)
    if path is None:
        return ""
    return _jersey_data_uri(str(path), path.stat().st_mtime_ns)


@st.cache_data(show_spinner=False)
def _jersey_data_uri(path_text: str, cache_key: int) -> str:
    encoded = base64.b64encode(Path(path_text).read_bytes()).decode("ascii")
    return f"data:image/webp;base64,{encoded}"
