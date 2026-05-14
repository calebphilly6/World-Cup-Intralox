"""Optional football data API client placeholder."""

from src.config import get_secret


def is_configured(secrets: dict | None = None) -> bool:
    if secrets is not None:
        try:
            api_keys = secrets.get("api_keys", {})
            return bool(
                secrets.get("FOOTBALL_DATA_API_KEY")
                or secrets.get("FOOTBALL_DATA_TOKEN")
                or api_keys.get("football_data")
            )
        except Exception:
            return False
    return bool(get_secret("FOOTBALL_DATA_API_KEY"))
