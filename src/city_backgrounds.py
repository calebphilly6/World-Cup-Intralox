from __future__ import annotations

import base64
import re
from pathlib import Path

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
UPDATED_CITY_ASSETS_DIR = PROJECT_ROOT / "assets"
CITY_BACKGROUNDS_DIR = PROJECT_ROOT / "data" / "assets" / "city_backgrounds"
GENERATED_BACKGROUNDS_DIR = UPDATED_CITY_ASSETS_DIR / "_generated_backgrounds"

UPDATED_CITY_IMAGES = {
    "atlanta": "Atlanta.jpg",
    "boston": "Boston.jpg",
    "dallas": "Dallas.jpg",
    "guadalajara": "Guadalajara.jpeg",
    "houston": "Houston.jpg",
    "kansas_city": "Kansas-City.jpeg",
    "los_angeles": "Los-Angeles.jpg",
    "mexico_city": "Mexico-City.jpeg",
    "miami": "Miami.jpg",
    "monterrey": "Monterrey.png",
    "new_york_new_jersey": "New-York-New-Jersey.jpg",
    "philadelphia": "Philadelphia.jpg",
    "san_francisco_bay_area": "San-Francisco-Bay-Area.jpg",
    "seattle": "Seattle.jpg",
    "toronto": "Toronto.jpg",
    "vancouver": "Vancouver.jpg",
}


def city_background_data_uri(city: str | None) -> str:
    """Return a browser-safe data URI for a host city background image."""
    path = city_background_path(city)
    if path is None:
        return ""
    return _image_data_uri(str(path), path.stat().st_mtime_ns)


def city_background_card_data_uri(city: str | None) -> str:
    """Return a lighter background image for repeated fixture cards."""
    path = city_background_path(city)
    if path is None:
        return ""
    thumbnail = _thumbnail_path(str(path), path.stat().st_mtime_ns)
    return _image_data_uri(str(thumbnail), thumbnail.stat().st_mtime_ns)


def city_background_path(city: str | None) -> Path | None:
    slug = city_slug(city)
    if not slug:
        return None
    updated_path = UPDATED_CITY_ASSETS_DIR / UPDATED_CITY_IMAGES.get(slug, "")
    if updated_path.exists():
        return updated_path
    path = CITY_BACKGROUNDS_DIR / f"{slug}_crisper_1920x1080.png"
    return path if path.exists() else None


def city_slug(city: str | None) -> str:
    text = str(city or "").strip().lower()
    if not text:
        return ""
    text = text.replace("/", " ")
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


@st.cache_data(show_spinner=False)
def _image_data_uri(path_text: str, cache_key: int) -> str:
    path = Path(path_text)
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    mime_type = "image/jpeg" if path.suffix.lower() in {".jpg", ".jpeg"} else "image/png"
    return f"data:{mime_type};base64,{encoded}"


@st.cache_data(show_spinner=False)
def _thumbnail_path(path_text: str, cache_key: int) -> Path:
    path = Path(path_text)
    GENERATED_BACKGROUNDS_DIR.mkdir(parents=True, exist_ok=True)
    thumbnail_path = GENERATED_BACKGROUNDS_DIR / f"{path.stem}_card.jpg"
    if thumbnail_path.exists() and thumbnail_path.stat().st_mtime_ns >= cache_key:
        return thumbnail_path
    try:
        from PIL import Image

        with Image.open(path) as image:
            image = image.convert("RGB")
            image.thumbnail((720, 405))
            image.save(thumbnail_path, "JPEG", quality=72, optimize=True)
        return thumbnail_path
    except Exception:
        return path
