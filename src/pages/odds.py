from __future__ import annotations

from datetime import datetime
import html

import pandas as pd
import streamlit as st

from src.api_clients.odds_client import get_api_key, merge_duplicate_odds_teams
from src.config import get_secret, get_section, is_shared_core_read_only_mode
from src.database import fetch_df, get_connection
from src.match_odds_service import refresh_match_odds_if_available
from src.odds_service import latest_tournament_winner_odds, odds_source_text
from src.odds_refresh import APP_TIMEZONE, daily_odds_refresh_key
from src.pages.rankings import FLAG_CODES
from src.tournament_odds_service import refresh_tournament_odds_if_available
from src.utils.team_names import display_team_name, team_link_attr


def render() -> None:
    st.title("Odds")
    _styles()

    read_only = is_shared_core_read_only_mode()
    if read_only:
        st.caption("Shared mode: live odds refresh is disabled. Showing stored odds only.")
    else:
        with get_connection() as conn:
            merge_duplicate_odds_teams(conn)
            conn.commit()

    _, api_key, _ = _odds_config()
    refresh_key = _daily_odds_refresh_key()
    refresh_result = (
        {"saved": 0}
        if read_only
        else refresh_tournament_odds_if_available(refresh_key)
    )
    match_refresh_result = {"saved": 0} if read_only else refresh_match_odds_if_available(refresh_key)

    if refresh_result.get("error"):
        st.warning(refresh_result["error"])
    if match_refresh_result.get("error"):
        st.warning(match_refresh_result["error"])
    elif not api_key and not read_only:
        st.info("Add an Odds API key to `.streamlit/secrets.toml` to refresh tournament odds automatically.")

    if refresh_result.get("saved"):
        latest_tournament_winner_odds.clear()
    latest = latest_tournament_winner_odds()
    if latest.empty:
        if read_only:
            st.info("No stored World Cup winner odds are available yet. Ask the app owner to refresh odds in local/admin mode.")
        else:
            st.info("No World Cup winner odds stored yet.")
        return

    _render_odds_board(latest)


def _odds_config() -> tuple[dict, str | None, dict]:
    secrets = {}
    api_key = get_secret("THE_ODDS_API_KEY") or get_api_key(None)
    odds_config = get_section("odds")
    return secrets, api_key, odds_config


def _latest_usage() -> pd.DataFrame:
    return fetch_df(
        """
        SELECT last_request_cost, requests_used, requests_remaining, updated_at
        FROM api_usage
        WHERE provider = 'the_odds_api'
        ORDER BY datetime(updated_at) DESC, id DESC
        LIMIT 1
        """
    )


def _render_odds_board(latest: pd.DataFrame) -> None:
    top = latest.head(4)
    rest = latest.iloc[4:]
    snapshot = _snapshot_text(latest["snapshot_ts"].dropna().max())
    st.markdown(
        f'<section class="odds-hero"><span>DraftKings</span>'
        f'<h2>Odds to win the World Cup</h2><div><small>Latest snapshot</small><strong>{snapshot}</strong></div></section>',
        unsafe_allow_html=True,
    )
    st.markdown(f'<section class="odds-favorites">{_odds_cards(top, featured=True)}</section>', unsafe_allow_html=True)
    if not rest.empty:
        st.markdown(f'<section class="odds-grid">{_odds_cards(rest)}</section>', unsafe_allow_html=True)


def _odds_cards(rows: pd.DataFrame, featured: bool = False) -> str:
    return "".join(_odds_card(row, featured) for _, row in rows.iterrows())


def _odds_card(row, featured: bool = False) -> str:
    team = str(row.get("Team") or "Unknown")
    display_name = display_team_name(team)
    probability = row.get("implied_probability")
    percent = f"{float(probability):.2%}" if pd.notna(probability) else "TBD"
    odds = html.escape(odds_source_text(row.get("american_odds"), row.get("source")))
    code = _flag_code(team, row.get("country_code"))
    class_name = "odds-card featured" if featured else "odds-card"
    return (
        f'<article class="{class_name}"{team_link_attr(team)}>'
        f'<div class="odds-flag">{_flag_img(code, display_name)}</div>'
        '<div class="odds-card-main">'
        f'<div class="odds-team">{html.escape(display_name)}</div>'
        f'<div class="odds-price">{odds}</div>'
        '</div>'
        f'<div class="odds-prob"><span>{percent}</span><small>Implied</small></div>'
        '</article>'
    )


def _flag_code(team: str, stored_code=None) -> str:
    stored_text = "" if pd.isna(stored_code) else str(stored_code).strip()
    code = FLAG_CODES.get(team) or stored_text
    return str(code).strip().lower()


def _flag_img(code: str, team: str) -> str:
    initials = "".join(part[0] for part in team.replace("-", " ").split()[:2]).upper() or "?"
    if not code:
        return f'<div class="odds-flag-fallback">{html.escape(initials)}</div>'
    return (
        f'<img src="https://flagcdn.com/w80/{html.escape(code)}.png" alt="{html.escape(team)} flag" '
        f'onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'grid\';">'
        f'<div class="odds-flag-fallback hidden">{html.escape(initials)}</div>'
    )


def _daily_odds_refresh_key(now: datetime | None = None) -> str:
    return daily_odds_refresh_key(now)


def _snapshot_text(value) -> str:
    parsed = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(parsed):
        return "Stored odds"
    local_time = parsed.tz_convert(APP_TIMEZONE)
    return f"{local_time.strftime('%b')} {local_time.day}, {local_time.strftime('%I:%M %p').lstrip('0')}"


def _styles() -> None:
    st.markdown(
        """
        <style>
        .odds-hero {
            align-items: baseline;
            border: 1px solid rgba(214,168,58,.32);
            border-radius: 8px;
            background:
                linear-gradient(135deg, rgba(5,5,5,.76), rgba(11,16,32,.62)),
                radial-gradient(circle at 82% 18%, rgba(157,255,0,.16), transparent 28%),
                radial-gradient(circle at 20% 86%, rgba(36,88,255,.20), transparent 32%);
            display: grid;
            grid-template-columns: 1fr auto 1fr;
            gap: 1.15rem;
            margin: .2rem 0 .8rem;
            min-height: 64px;
            padding: .62rem 1rem;
        }
        .odds-hero span, .odds-section-title {
            color: #D6A83A;
            font-size: .95rem;
            font-weight: 950;
            text-transform: uppercase;
            text-shadow: 0 4px 16px rgba(0,0,0,.45);
        }
        .odds-hero h2 {
            color: #FFFFFF;
            font-size: 2rem;
            font-weight: 950;
            line-height: .96;
            margin: 0;
            text-align: center;
            text-shadow: 0 8px 26px rgba(0,0,0,.46);
        }
        .odds-hero small, .odds-hero em {
            color: #CBD5E1;
            display: block;
            font-style: normal;
            font-weight: 750;
            text-align: right;
        }
        .odds-hero strong {
            color: #FFFFFF;
            display: block;
            font-size: .98rem;
            font-weight: 950;
            line-height: 1;
            margin: .08rem 0 0;
            text-align: right;
        }
        .odds-favorites {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: .8rem;
            margin-bottom: 1rem;
        }
        .odds-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: .65rem;
        }
        .odds-section-title {
            border-bottom: 1px solid rgba(214,168,58,.24);
            margin: .3rem 0 .75rem;
            padding-bottom: .5rem;
        }
        .odds-card {
            align-items: center;
            border: 1px solid rgba(214,168,58,.22);
            border-radius: 8px;
            background:
                linear-gradient(135deg, rgba(5,5,5,.60), rgba(11,16,32,.54)),
                radial-gradient(circle at 100% 0%, rgba(214,168,58,.14), transparent 32%);
            display: grid;
            grid-template-columns: 58px 1fr auto;
            gap: .72rem;
            min-height: 84px;
            padding: .68rem;
            box-shadow: 0 12px 30px rgba(0,0,0,.16);
        }
        .odds-card.featured {
            grid-template-columns: 68px 1fr;
            grid-template-rows: auto auto;
            min-height: 168px;
            align-content: space-between;
        }
        .odds-card.featured .odds-prob {
            grid-column: 1 / -1;
            justify-self: stretch;
            text-align: left;
        }
        .odds-flag img, .odds-flag-fallback {
            aspect-ratio: 3 / 2;
            border: 1px solid rgba(255,255,255,.52);
            border-radius: 6px;
            box-shadow: 0 8px 18px rgba(0,0,0,.34);
            display: block;
            object-fit: cover;
            object-position: center;
            width: 100%;
        }
        .odds-flag-fallback {
            align-items: center;
            background: linear-gradient(135deg, rgba(214,168,58,.35), rgba(36,88,255,.22));
            color: #FFFFFF;
            display: grid;
            font-weight: 950;
            justify-content: center;
        }
        .odds-flag-fallback.hidden {
            display: none;
        }
        .odds-team {
            color: #FFFFFF;
            font-size: 1.02rem;
            font-weight: 950;
            line-height: 1.05;
        }
        .odds-card.featured .odds-team {
            font-size: 1.35rem;
        }
        .odds-price {
            color: #D6A83A;
            font-weight: 950;
            margin-top: .22rem;
        }
        .odds-prob {
            color: #FFFFFF;
            text-align: right;
        }
        .odds-prob span {
            display: block;
            font-size: 1.05rem;
            font-weight: 950;
        }
        .odds-prob small {
            color: #CBD5E1;
            font-size: .72rem;
            font-weight: 850;
            text-transform: uppercase;
        }
        @media (max-width: 980px) {
            .odds-favorites, .odds-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }
        @media (max-width: 620px) {
            .odds-hero {
                flex-direction: column;
            }
            .odds-hero small, .odds-hero strong, .odds-hero em {
                text-align: left;
            }
            .odds-favorites, .odds-grid {
                grid-template-columns: 1fr;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
