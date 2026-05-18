from __future__ import annotations

import pandas as pd


REQUIRED_COLUMNS = {
    "teams": {"name"},
    "groups": {"group_name", "team_name"},
    "rosters": {"team_name", "player_name"},
    "fixtures": {"match_number", "kickoff_utc", "home_team", "away_team", "stage"},
    "fifa_rankings": {"team", "ranking_date", "rank"},
    "odds": {"team_name", "market_type", "source", "snapshot_ts"},
}


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    normalized = df.copy()
    normalized.columns = [
        str(col).strip().lower().replace(" ", "_").replace("-", "_") for col in normalized.columns
    ]
    return normalized


def validate_import(kind: str, df: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    required = REQUIRED_COLUMNS.get(kind, set())
    missing = sorted(required.difference(df.columns))
    if missing:
        errors.append(f"Missing required columns: {', '.join(missing)}")
    if df.empty:
        errors.append("Import file has no rows.")
    return errors
