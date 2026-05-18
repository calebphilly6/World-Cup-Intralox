from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo


APP_TIMEZONE = ZoneInfo("America/Chicago")
ODDS_REFRESH_TIME = time(3, 0)


def daily_odds_refresh_key(now: datetime | None = None) -> str:
    local_now = now.astimezone(APP_TIMEZONE) if now else datetime.now(APP_TIMEZONE)
    refresh_day = local_now.date()
    if local_now.time() < ODDS_REFRESH_TIME:
        refresh_day -= timedelta(days=1)
    return refresh_day.isoformat()
