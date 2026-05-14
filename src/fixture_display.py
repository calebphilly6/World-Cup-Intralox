from __future__ import annotations

import pandas as pd


def enrich_fixture_participants(
    fixtures: pd.DataFrame,
    *,
    home_column: str = "home_team",
    away_column: str = "away_team",
    label_column: str = "game_label",
) -> pd.DataFrame:
    """Fill blank fixture participants from the official match label for display."""
    if fixtures.empty or label_column not in fixtures.columns:
        return fixtures

    enriched = fixtures.copy()
    if home_column not in enriched.columns:
        enriched[home_column] = ""
    if away_column not in enriched.columns:
        enriched[away_column] = ""

    for index, row in enriched.iterrows():
        home_label, away_label = _split_label(row.get(label_column))
        if home_label and _is_blank(row.get(home_column)):
            enriched.at[index, home_column] = home_label
        if away_label and _is_blank(row.get(away_column)):
            enriched.at[index, away_column] = away_label
    return enriched


def _split_label(value) -> tuple[str, str]:
    label = str(value or "").strip()
    if " vs " not in label:
        return "", ""
    home, away = label.split(" vs ", 1)
    return home.strip(), away.strip()


def _is_blank(value) -> bool:
    if pd.isna(value):
        return True
    text = str(value).strip().lower()
    return text in {"", "nan", "none", "null", "tbd"}
