from __future__ import annotations

import pandas as pd
import streamlit as st

from src.database import fetch_df


@st.cache_data(show_spinner=False)
def latest_tournament_winner_odds() -> pd.DataFrame:
    return fetch_df(
        """
        WITH latest_per_source AS (
            SELECT t.name AS Team,
                   t.country_code AS country_code,
                   o.american_odds AS american_odds,
                   o.implied_probability AS implied_probability,
                   o.source AS source,
                   o.snapshot_ts AS snapshot_ts,
                   ROW_NUMBER() OVER (
                       PARTITION BY o.team_id, o.market_type, LOWER(o.source)
                       ORDER BY datetime(o.snapshot_ts) DESC, o.id DESC
                   ) AS row_num
            FROM odds_snapshots o
            LEFT JOIN teams t ON t.id = o.team_id
            WHERE o.market_type = 'tournament_winner'
        ),
        preferred_odds AS (
            SELECT Team,
                   country_code,
                   american_odds,
                   implied_probability,
                   source,
                   snapshot_ts,
                   ROW_NUMBER() OVER (
                       PARTITION BY Team
                       ORDER BY
                           CASE WHEN LOWER(source) = 'draftkings' THEN 0 ELSE 1 END,
                           datetime(snapshot_ts) DESC,
                           implied_probability DESC
                   ) AS preferred_row
            FROM latest_per_source
            WHERE row_num = 1
              AND Team IS NOT NULL
        )
        SELECT Team, country_code, american_odds, implied_probability, source, snapshot_ts
        FROM preferred_odds
        WHERE preferred_row = 1
        ORDER BY implied_probability DESC
        """
    )


def latest_tournament_winner_odds_lookup() -> dict[str, dict]:
    rows = latest_tournament_winner_odds()
    if rows.empty:
        return {}
    return {
        str(row["Team"]): {
            "implied_probability": 0.0 if pd.isna(row["implied_probability"]) else float(row["implied_probability"]),
            "american_odds": row["american_odds"],
            "country_code": row["country_code"],
            "source": row["source"],
            "snapshot_ts": row["snapshot_ts"],
        }
        for _, row in rows.iterrows()
    }


def american_odds_text(value) -> str:
    if pd.isna(value) or str(value).strip() == "":
        return "TBD"
    text = str(value).strip()
    if text.startswith(("+", "-")):
        return text
    try:
        number = int(float(text))
    except ValueError:
        return text
    return f"+{number}" if number > 0 else str(number)


def odds_source_text(american_odds, source) -> str:
    odds = american_odds_text(american_odds)
    source_text = "" if pd.isna(source) else str(source).strip()
    if not source_text or source_text.lower() == "draftkings":
        return odds
    return f"{odds} {source_text}"
