from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pandas as pd


WORLD_CUP_START = datetime(2026, 6, 11, 0, 0, tzinfo=timezone.utc)


def flag_for_code(country_code: str | None) -> str:
    if not country_code or len(country_code.strip()) != 2:
        return ""
    code = country_code.strip().upper()
    return "".join(chr(127397 + ord(char)) for char in code)


def format_local_time(value: str | None, tz_name: str = "America/Chicago") -> str:
    if not value:
        return ""
    parsed = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(parsed):
        return str(value)
    return parsed.to_pydatetime().astimezone(ZoneInfo(tz_name)).strftime("%b %d, %Y %I:%M %p")


def countdown_parts(now: datetime | None = None) -> tuple[int, int, int]:
    current = now or datetime.now(timezone.utc)
    delta = WORLD_CUP_START - current
    total_seconds = max(0, int(delta.total_seconds()))
    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60
    return days, hours, minutes


def percent(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return ""
    return f"{float(value):.1%}"

