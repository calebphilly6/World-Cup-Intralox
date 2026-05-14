from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
IMPORTS_DIR = DATA_DIR / "imports"
DEFAULT_DB_PATH = DATA_DIR / "worldcup.db"

_SECRET_ALIASES: dict[str, tuple[str | tuple[str, ...], ...]] = {
    "THE_ODDS_API_KEY": (
        ("api_keys", "the_odds_api"),
        ("api_keys", "odds_provider"),
    ),
    "BALLDONTLIE_API_KEY": (
        ("api_keys", "balldontlie"),
        ("api_keys", "ball_dont_lie"),
    ),
    "FOOTBALL_DATA_API_KEY": (
        "FOOTBALL_DATA_TOKEN",
        ("api_keys", "football_data"),
        ("api_keys", "football_data_api"),
        ("api_keys", "football_data_org"),
    ),
    "APP_PASSWORD": (),
    "SHARED_CORE_READ_ONLY_MODE": (
        "SHARED_READ_ONLY_MODE",
    ),
    "SHARED_READ_ONLY_MODE": (),
}


@dataclass(frozen=True)
class AppConfig:
    project_root: Path
    data_dir: Path
    imports_dir: Path
    database_path: Path
    is_deployed: bool
    shared_core_read_only_mode: bool
    api_keys_present: dict[str, bool]


def get_secret(name: str, default: str | None = None, *, env_fallback: bool = True) -> str | None:
    """Safely read Streamlit secrets without crashing when a key/file is missing."""
    candidates = (name, *_SECRET_ALIASES.get(name, ()))
    for candidate in candidates:
        value = _read_streamlit_secret(candidate)
        if _has_value(value):
            return str(value).strip()

    if env_fallback:
        for candidate in candidates:
            if isinstance(candidate, tuple):
                continue
            value = os.getenv(candidate)
            if _has_value(value):
                return str(value).strip()

    return default


def get_bool_secret(name: str, default: bool = False, *, env_fallback: bool = True) -> bool:
    value = get_secret(name, default=None, env_fallback=env_fallback)
    if value is None:
        return default
    return _parse_bool(value, default)


def get_section(name: str) -> dict[str, Any]:
    secrets = _streamlit_secrets()
    if secrets is None:
        return {}
    try:
        section = secrets.get(name, {})
    except Exception:
        return {}
    if hasattr(section, "to_dict"):
        try:
            return dict(section.to_dict())
        except Exception:
            return {}
    if isinstance(section, dict):
        return dict(section)
    try:
        return dict(section)
    except Exception:
        return {}


def get_database_path() -> Path:
    configured = get_secret("DATABASE_PATH", default=None)
    if not configured:
        return DEFAULT_DB_PATH
    path = Path(configured).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def is_shared_core_read_only_mode() -> bool:
    return get_bool_secret("SHARED_CORE_READ_ONLY_MODE", default=False)


def is_shared_read_only_mode() -> bool:
    """Backward-compatible alias for the old shared-mode setting name."""
    return is_shared_core_read_only_mode()


def is_deployed() -> bool:
    app_env = get_secret("APP_ENV", default=None)
    if app_env:
        normalized = app_env.strip().lower()
        if normalized in {"cloud", "deployed", "prod", "production"}:
            return True
        if normalized in {"dev", "development", "local"}:
            return False

    cloud_markers = (
        "STREAMLIT_CLOUD",
        "STREAMLIT_COMMUNITY_CLOUD",
        "STREAMLIT_SHARING_MODE",
    )
    return any(os.getenv(marker) for marker in cloud_markers)


def api_keys_present() -> dict[str, bool]:
    return {
        "THE_ODDS_API_KEY": bool(get_secret("THE_ODDS_API_KEY")),
        "BALLDONTLIE_API_KEY": bool(get_secret("BALLDONTLIE_API_KEY")),
        "FOOTBALL_DATA_API_KEY": bool(get_secret("FOOTBALL_DATA_API_KEY")),
    }


def get_app_config() -> AppConfig:
    return AppConfig(
        project_root=PROJECT_ROOT,
        data_dir=DATA_DIR,
        imports_dir=IMPORTS_DIR,
        database_path=get_database_path(),
        is_deployed=is_deployed(),
        shared_core_read_only_mode=is_shared_core_read_only_mode(),
        api_keys_present=api_keys_present(),
    )


def ensure_app_directories() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    IMPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _streamlit_secrets():
    try:
        import streamlit as st

        return st.secrets
    except Exception:
        return None


def _read_streamlit_secret(path: str | tuple[str, ...]) -> Any | None:
    secrets = _streamlit_secrets()
    if secrets is None:
        return None
    try:
        current: Any = secrets
        parts = (path,) if isinstance(path, str) else path
        for part in parts:
            if hasattr(current, "get"):
                current = current.get(part)
            else:
                current = current[part]
            if current is None:
                return None
        return current
    except Exception:
        return None


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    text = str(value).strip()
    if text == "":
        return False
    lowered = text.lower()
    return not (
        lowered.startswith("replace-with-")
        or lowered.startswith("paste-your-")
        or lowered.startswith("your-real-")
    )


def _parse_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default
