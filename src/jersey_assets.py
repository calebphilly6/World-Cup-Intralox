from __future__ import annotations

import base64
import re
import unicodedata
from pathlib import Path

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
JERSEYS_DIR = PROJECT_ROOT / "assets" / "jerseys"
JERSEY_HEADERS_DIR = JERSEYS_DIR / "headers"


def jersey_slug(team_name: str | None) -> str:
    """Slug used for jersey filenames (matches the asset build step)."""
    text = unicodedata.normalize("NFKD", str(team_name or "")).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def jersey_path(team_name: str | None) -> Path | None:
    slug = jersey_slug(team_name)
    if not slug:
        return None
    path = JERSEYS_DIR / f"{slug}.webp"
    return path if path.exists() else None


def team_jersey_data_uri(team_name: str | None) -> str:
    """Return a browser-safe data URI for a team's home kit, or '' if missing."""
    path = jersey_path(team_name)
    if path is None:
        return ""
    return _jersey_data_uri(str(path), path.stat().st_mtime_ns)


def jersey_header_path(team_name: str | None) -> Path | None:
    slug = jersey_slug(team_name)
    if not slug:
        return None
    path = JERSEY_HEADERS_DIR / f"{slug}.webp"
    return path if path.exists() else None


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
