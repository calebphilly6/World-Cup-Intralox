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


@st.cache_data(show_spinner=False)
def latest_fixture_odds(match_number: int | None, home_team: str, away_team: str, kickoff_utc: str) -> pd.DataFrame:
    params: list = []
    filters: list[str] = []
    if match_number is not None:
        filters.append(
            """
            o.fixture_id IN (
                SELECT id FROM fixtures WHERE match_number = ?
            )
            """
        )
        params.append(match_number)

    event_day = str(kickoff_utc or "")[:10]
    if event_day and home_team and away_team:
        filters.append(
            """
            (
                substr(o.commence_time, 1, 10) = ?
                AND LOWER(o.home_team) = LOWER(?)
                AND LOWER(o.away_team) = LOWER(?)
            )
            """
        )
        params.extend([event_day, home_team, away_team])

    if not filters:
        return pd.DataFrame()

    return fetch_df(
        f"""
        WITH latest_rows AS (
            SELECT o.*,
                   ROW_NUMBER() OVER (
                       PARTITION BY
                           COALESCE(o.fixture_id, 0),
                           COALESCE(o.external_event_id, ''),
                           LOWER(COALESCE(o.bookmaker_key, o.bookmaker_title, '')),
                           o.market_type,
                           o.outcome_name,
                           COALESCE(o.point, -999999)
                       ORDER BY datetime(o.snapshot_ts) DESC, o.id DESC
                   ) AS row_num
            FROM fixture_odds_snapshots o
            WHERE {" OR ".join(filters)}
        )
        SELECT fixture_id, external_event_id, commence_time, home_team, away_team,
               bookmaker_key, bookmaker_title, market_type, outcome_name, odds_format,
               american_odds, decimal_odds, implied_probability, point, source,
               snapshot_ts, notes
        FROM latest_rows
        WHERE row_num = 1
        ORDER BY
            CASE market_type
                WHEN 'h2h' THEN 0
                WHEN 'spreads' THEN 1
                WHEN 'totals' THEN 2
                ELSE 9
            END,
            LOWER(COALESCE(bookmaker_title, bookmaker_key, source, '')),
            CASE outcome_name
                WHEN home_team THEN 0
                WHEN 'Draw' THEN 1
                WHEN away_team THEN 2
                WHEN 'Over' THEN 3
                WHEN 'Under' THEN 4
                ELSE 5
            END
        """,
        params,
    )
