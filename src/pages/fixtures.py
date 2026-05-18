from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from src.api_clients.odds_client import get_api_key
from data_sources.football_data_client import FootballDataError
from src.city_backgrounds import city_background_card_data_uri, city_background_data_uri
from src.database import fetch_df
from src.fixture_display import enrich_fixture_participants, flag_code_for_team, flag_lookup_with_aliases
from src.football_data_service import cached_matches, daily_fixture_refresh_key
from src.match_odds_service import refresh_match_odds_if_available
from src.navigation import remember_detail_origin, return_to_detail_origin
from src.odds_service import american_odds_text, latest_fixture_odds
from src.official_match_reference import apply_official_match_reference, normalize_team_key
from src.utils.formatting import format_local_time


STAGE_ORDER = {
    "groupstage": 0,
    "group": 0,
    "last32": 1,
    "roundof32": 1,
    "last16": 2,
    "roundof16": 2,
    "quarterfinals": 3,
    "quarterfinal": 3,
    "semifinals": 4,
    "semifinal": 4,
    "thirdplace": 5,
    "thirdplacematch": 5,
    "final": 6,
}

STAGE_LABELS = {
    "groupstage": "Group Stage",
    "group": "Group Stage",
    "last32": "Round of 32",
    "roundof32": "Round of 32",
    "last16": "Round of 16",
    "roundof16": "Round of 16",
    "quarterfinals": "Quarterfinals",
    "quarterfinal": "Quarterfinals",
    "semifinals": "Semifinals",
    "semifinal": "Semifinals",
    "thirdplace": "Third Place",
    "thirdplacematch": "Third Place",
    "final": "Final",
}

def render() -> None:
    st.title("Fixtures")
    _styles()

    selected_fixture_row = st.session_state.get("selected_fixture_row")
    if selected_fixture_row:
        _render_fixture_focus(pd.Series(selected_fixture_row))
        return

    with st.spinner("Loading all fixtures..."):
        fixtures, warning = _fixture_data(daily_fixture_refresh_key())
    if warning:
        st.warning(warning)

    if fixtures.empty:
        st.info("No fixtures available yet.")
        return

    fixtures = _normalize_fixture_labels(fixtures)
    selected_fixture = _selected_fixture_id()
    if selected_fixture:
        match = _fixture_by_id(fixtures, selected_fixture)
        if match is not None:
            _render_fixture_focus(match)
            return
        st.warning("That fixture could not be found. Close this view and choose another match.")

    filtered = _filter_fixtures(fixtures)
    if filtered.empty:
        st.info("No fixtures match the selected filters.")
        return

    _render_fixture_days(filtered, _fixture_backgrounds(filtered))


@st.cache_data(show_spinner=False)
def _fixture_data(refresh_key: str) -> tuple[pd.DataFrame, str]:
    try:
        return enrich_fixture_participants(apply_official_match_reference(cached_matches())), ""
    except FootballDataError as exc:
        return _local_fixture_fallback(), f"{exc} Using fallback fixture data. Scores and standings may not be current."
    except Exception as exc:
        return _local_fixture_fallback(), f"Could not load football-data.org fixtures: {exc}. Using fallback fixture data. Scores and standings may not be current."


def _local_fixture_fallback() -> pd.DataFrame:
    fixtures = fetch_df(
        """
        SELECT f.match_number, f.kickoff_utc, ht.name AS home_team, at.name AS away_team,
               f.stage, f.group_name, m.game_label,
               COALESCE(m.city, f.city) AS venue, COALESCE(m.city, f.city) AS city,
               f.host_country,
               f.status, f.home_score, f.away_score, f.watch_priority, f.notes
        FROM fixtures f
        LEFT JOIN teams ht ON ht.id = f.home_team_id
        LEFT JOIN teams at ON at.id = f.away_team_id
        LEFT JOIN match_city_reference m ON m.match_number = f.match_number
        ORDER BY datetime(f.kickoff_utc), f.match_number
        """
    )
    if fixtures.empty:
        return fixtures
    fixtures = enrich_fixture_participants(fixtures)
    fixtures["local_kickoff"] = fixtures["kickoff_utc"].apply(format_local_time)
    fixtures = fixtures.rename(
        columns={
            "match_number": "official_match_number",
            "kickoff_utc": "utc_date",
            "local_kickoff": "local_time",
            "group_name": "group",
        }
    )
    fixtures["match_id"] = fixtures["official_match_number"].map(lambda value: f"M{int(value)}" if pd.notna(value) else "")
    fixtures["local_date"] = pd.to_datetime(fixtures["utc_date"], utc=True, errors="coerce").dt.date.astype(str)
    return fixtures


def _filter_fixtures(fixtures: pd.DataFrame) -> pd.DataFrame:
    filtered = fixtures.copy()
    c1, c2, c3 = st.columns(3)

    teams = sorted(set(filtered.get("home_team", pd.Series(dtype=str)).dropna()) | set(filtered.get("away_team", pd.Series(dtype=str)).dropna()))
    selected_teams = c1.multiselect("Team", teams)
    group_options = sorted(filtered.get("group", pd.Series(dtype=str)).dropna().unique())
    stage_options = _ordered_stage_options(filtered.get("stage", pd.Series(dtype=str)).dropna().unique())
    selected_groups = c2.multiselect("Group", group_options, format_func=_clean_filter_label)
    selected_stages = c3.multiselect("Stage", stage_options, format_func=_stage_filter_label)

    if selected_teams:
        filtered = filtered[filtered["home_team"].isin(selected_teams) | filtered["away_team"].isin(selected_teams)]
    if selected_groups:
        filtered = filtered[filtered["group"].isin(selected_groups)]
    if selected_stages:
        filtered = filtered[filtered["stage"].isin(selected_stages)]

    return filtered.sort_values(["utc_date", "venue"])


def _normalize_fixture_labels(fixtures: pd.DataFrame) -> pd.DataFrame:
    normalized = fixtures.copy()
    if "status" in normalized:
        normalized["status"] = normalized["status"].map(_status_label)
    return normalized


def _clean_filter_label(value) -> str:
    text = str(value or "").replace("_", " ").strip()
    return text.title() if text else ""


def _ordered_stage_options(values) -> list:
    return sorted(values, key=lambda value: (STAGE_ORDER.get(_stage_key(value), 99), _stage_filter_label(value)))


def _stage_filter_label(value) -> str:
    key = _stage_key(value)
    if key in STAGE_LABELS:
        return STAGE_LABELS[key]
    return _clean_filter_label(value)


def _stage_key(value) -> str:
    return "".join(character for character in str(value or "").lower() if character.isalnum())


def _render_fixture_days(fixtures: pd.DataFrame, backgrounds: dict[str, str]) -> None:
    grouped = fixtures.copy()
    grouped["_day"] = pd.to_datetime(grouped["local_date"], errors="coerce")
    grouped = grouped.sort_values(["_day", "utc_date", "venue"])

    for day, day_matches in grouped.groupby(grouped["_day"].dt.date, sort=True):
        if pd.isna(day):
            continue
        day_ts = pd.Timestamp(day)
        day_label = f"{day_ts.strftime('%A, %B')} {day_ts.day}, {day_ts.year}"
        st.markdown(
            f'<section class="fixture-day"><h2>{html.escape(day_label)}</h2></section>',
            unsafe_allow_html=True,
        )
        for start in range(0, len(day_matches), 3):
            columns = st.columns(3)
            for column, (_, row) in zip(columns, day_matches.iloc[start:start + 3].iterrows()):
                with column:
                    st.markdown(_fixture_card(row, backgrounds), unsafe_allow_html=True)
                    match_number = _match_number(row)
                    if st.button("Open match", key=f"fixture_open_{_safe_key(match_number)}", use_container_width=True):
                        _open_fixture_from_row(row)


def _fixture_backgrounds(fixtures: pd.DataFrame) -> dict[str, str]:
    cities = sorted(
        {
            str(city).strip()
            for city in fixtures.get("city", pd.Series(dtype=str)).fillna("").tolist()
            + fixtures.get("venue", pd.Series(dtype=str)).fillna("").tolist()
            if str(city).strip()
        }
    )
    return {city: city_background_card_data_uri(city) for city in cities}


def _open_fixture_from_row(row) -> None:
    remember_detail_origin("fixture_return_origin")
    st.session_state["selected_fixture_id"] = _match_number(row)
    st.session_state["selected_fixture_row"] = row.to_dict()
    st.query_params["page"] = "fixtures"
    if "fixture" in st.query_params:
        del st.query_params["fixture"]
    st.rerun()


def _fixture_card(row, backgrounds: dict[str, str] | None = None) -> str:
    city = str(row.get("city") or row.get("venue") or "Host City TBD")
    background = (backgrounds or {}).get(city) or city_background_card_data_uri(city)
    background_style = (
        f"linear-gradient(180deg, rgba(5,5,5,.18), rgba(5,5,5,.88)), url('{background}')"
        if background
        else "linear-gradient(135deg, #0B1020, #111111)"
    )
    home = _card_team_label(str(row.get("home_team") or "TBD"))
    away = _card_team_label(str(row.get("away_team") or "TBD"))
    match_number = _match_number(row)
    stage = _stage_label(row)
    round_stage = _round_stage_label(row.get("stage") or stage)
    time = html.escape(_kickoff_time(row.get("utc_date"), row.get("local_time")))
    center = _scoreline(row) if _has_score(row) else time
    bottom_markup = _fixture_card_bottom_markup(round_stage, stage)
    return (
        f'<article class="fixture-card" style="background-image: {background_style};">'
        '<div class="fixture-card-top">'
        f'<span>{html.escape(match_number)}</span><span>{html.escape(city)}</span>'
        '</div>'
        '<div class="fixture-card-body">'
        f'<div class="fixture-teams"><div>{home}</div><strong>vs</strong><div>{away}</div></div>'
        f'<div class="fixture-score">{html.escape(center)}</div>'
        '</div>'
        f'{bottom_markup}'
        '</article>'
    )


def _render_fixture_focus(row) -> None:
    if st.button("Close Match View", key="close_fixture_focus"):
        st.session_state.pop("selected_fixture_id", None)
        st.session_state.pop("selected_fixture_row", None)
        return_to_detail_origin("fixture_return_origin", "Fixtures")
        if "fixture" in st.query_params:
            del st.query_params["fixture"]
        st.rerun()

    city = str(row.get("city") or row.get("venue") or "Host City TBD")
    background = city_background_data_uri(city)
    background_style = (
        f"linear-gradient(180deg, rgba(5,5,5,.12), rgba(5,5,5,.86)), url('{background}')"
        if background
        else "linear-gradient(135deg, #0B1020, #111111)"
    )
    background_style = html.escape(background_style, quote=True)
    home = html.escape(str(row.get("home_team") or "TBD"))
    away = html.escape(str(row.get("away_team") or "TBD"))
    home_flag = _flag_img(row.get("home_team"))
    away_flag = _flag_img(row.get("away_team"))
    match_number = html.escape(_match_number(row))
    stage_label = _stage_label(row)
    round_stage = _round_stage_label(row.get("stage") or stage_label)
    time = html.escape(_kickoff_time(row.get("utc_date"), row.get("local_time")))
    center = html.escape(_scoreline(row) if _has_score(row) else time)
    top_markup = _fixture_focus_top_markup(match_number, city, center, round_stage)
    bottom_markup = _fixture_focus_bottom_markup(round_stage, stage_label, center)
    markup = (
        f'<section class="fixture-focus" style="background-image: {background_style};">'
        f'{top_markup}'
        '<div class="fixture-focus-body">'
        f'<div class="fixture-focus-team">{home_flag}<div>{home}</div></div>'
        f'<div class="fixture-focus-team right">{away_flag}<div>{away}</div></div>'
        '</div>'
        f'{bottom_markup}'
        '</section>'
    )
    st.markdown(markup, unsafe_allow_html=True)
    _render_betting_odds(row)


def _render_betting_odds(row) -> None:
    refresh_result = refresh_match_odds_if_available()
    if refresh_result.get("saved"):
        latest_fixture_odds.clear()

    odds = latest_fixture_odds(
        _match_number_value(row),
        str(row.get("home_team") or ""),
        str(row.get("away_team") or ""),
        str(row.get("utc_date") or row.get("kickoff_utc") or ""),
    )

    if refresh_result.get("error"):
        st.warning(refresh_result["error"])
    if odds.empty:
        if not get_api_key(None):
            st.info("Add a The Odds API key to show game-level betting odds here.")
        else:
            st.info("No game-level betting odds are stored for this match yet.")
        return

    odds = _preferred_fixture_odds(odds)
    if odds.empty:
        st.info("No preferred game-level betting odds are stored for this match yet.")
        return

    st.markdown(_fixture_odds_panel_html(row, odds), unsafe_allow_html=True)


def _fixture_odds_panel_html(fixture_row, odds: pd.DataFrame) -> str:
    moneyline = odds[odds["market_type"].eq("h2h")]
    totals = odds[odds["market_type"].eq("totals")]
    home_team = str(fixture_row.get("home_team") or "Home")
    away_team = str(fixture_row.get("away_team") or "Away")
    moneyline_items = "".join(
        _fixture_odds_price_html(label, _odds_row_for_outcome(moneyline, label))
        for label in (home_team, "Draw", away_team)
    )
    total_items = "".join(
        _fixture_odds_price_html(_total_label(label, _odds_row_for_outcome(totals, label)), _odds_row_for_outcome(totals, label))
        for label in ("Under", "Over")
    )
    return (
        '<section class="fixture-odds-panel">'
        '<div class="fixture-odds-group">'
        '<h3>Moneyline</h3>'
        f'<div class="fixture-odds-prices moneyline">{moneyline_items}</div>'
        '</div>'
        '<div class="fixture-odds-group">'
        '<h3>Total Goals</h3>'
        f'<div class="fixture-odds-prices totals">{total_items}</div>'
        '</div>'
        '</section>'
    )


def _preferred_fixture_odds(odds: pd.DataFrame) -> pd.DataFrame:
    if odds.empty:
        return odds
    market = odds.get("market_type", pd.Series(dtype=str)).astype(str)
    selected = pd.concat(
        [
            _preferred_market_odds(odds[market == "h2h"], ["draftkings", "betrivers", "fanduel"]),
            _preferred_market_odds(odds[market == "totals"], ["betrivers", "draftkings", "fanduel"]),
        ],
        ignore_index=True,
    )
    if selected.empty:
        return selected
    selected["_market_order"] = selected["market_type"].map({"h2h": 0, "totals": 1}).fillna(9)
    selected["_outcome_order"] = selected["outcome_name"].map({"Draw": 1, "Over": 3, "Under": 4}).fillna(0)
    selected = selected.sort_values(["_market_order", "_outcome_order", "outcome_name"])
    return selected.drop(columns=["_market_order", "_outcome_order"])


def _preferred_market_odds(rows: pd.DataFrame, bookmaker_priority: list[str]) -> pd.DataFrame:
    if rows.empty:
        return rows
    book = rows.get("bookmaker_title", pd.Series(dtype=str)).fillna(rows.get("source", "")).astype(str).str.lower()
    for bookmaker in bookmaker_priority:
        selected = rows[book.eq(bookmaker)].copy()
        if not selected.empty:
            return selected
    return rows.iloc[0:0].copy()


def _odds_row_for_outcome(rows: pd.DataFrame, label: str):
    if rows.empty:
        return None
    label_key = normalize_team_key(label)
    matches = rows[rows["outcome_name"].map(normalize_team_key).eq(label_key)]
    if matches.empty:
        return None
    return matches.iloc[0]


def _fixture_odds_price_html(label: str, row) -> str:
    odds = "TBD" if row is None else american_odds_text(row.get("american_odds"))
    return (
        '<div class="fixture-odds-price">'
        f'<span>{html.escape(str(label))}</span>'
        f'<strong>{html.escape(odds)}</strong>'
        '</div>'
    )


def _total_label(label: str, row) -> str:
    point = "" if row is None else _point_text(row.get("point"))
    if not point:
        return label
    return f"{label} {point.replace('+', '')}"


def _point_text(value) -> str:
    if pd.isna(value) or str(value).strip() == "":
        return ""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number.is_integer():
        return f"{number:+.0f}"
    return f"{number:+.1f}"


def _match_number_value(row) -> int | None:
    text = _match_number(row).replace("M", "", 1)
    try:
        return int(float(text))
    except ValueError:
        return None


def _selected_fixture_id() -> str:
    state_value = st.session_state.get("selected_fixture_id")
    if state_value:
        return str(state_value).strip()
    value = st.query_params.get("fixture")
    if isinstance(value, list):
        value = value[0] if value else ""
    return str(value or "").strip()


def _fixture_by_id(fixtures: pd.DataFrame, fixture_id: str):
    for _, row in fixtures.iterrows():
        if _match_number(row) == fixture_id:
            return row
    return None


def _flag_img(team_name) -> str:
    code = flag_code_for_team(team_name, _team_flag_lookup())
    if not code:
        return ""
    return f'<img class="fixture-focus-flag" src="https://flagcdn.com/w160/{html.escape(code)}.png" alt="">'


def _card_team_label(team_name: str) -> str:
    return (
        '<div class="fixture-team-label">'
        f'{_card_flag_img(team_name)}'
        f'<span>{html.escape(team_name)}</span>'
        '</div>'
    )


def _card_flag_img(team_name: str) -> str:
    code = flag_code_for_team(team_name, _team_flag_lookup())
    if not code:
        initials = "".join(part[0] for part in str(team_name).replace("-", " ").split()[:2]).upper() or "?"
        return f'<span class="fixture-card-flag flag-fallback">{html.escape(initials)}</span>'
    return (
        f'<img class="fixture-card-flag" src="https://flagcdn.com/w80/{html.escape(code)}.png" '
        f'alt="{html.escape(team_name)} flag">'
    )


@st.cache_data(show_spinner=False)
def _team_flag_lookup() -> dict[str, str]:
    teams = fetch_df("SELECT name, country_code FROM teams")
    return flag_lookup_with_aliases(teams)


def _match_number(row) -> str:
    value = row.get("official_match_number")
    if pd.isna(value):
        value = row.get("match_id")
    if pd.isna(value) or value == "":
        return "Match"
    text = str(value)
    return text if text.startswith("M") else f"M{int(float(text))}"


def _safe_key(value: str) -> str:
    return "".join(character.lower() if character.isalnum() else "_" for character in str(value)).strip("_")


def _stage_label(row) -> str:
    stage = str(row.get("stage") or "").replace("_", " ").title()
    group = str(row.get("group") or "").replace("_", " ").title()
    if group and group.lower() != "nan":
        return f"Group {group}" if len(group) == 1 else group
    if stage == "Last 32":
        return "Round of 32"
    if stage == "Last 16":
        return "Round of 16"
    return stage if stage and stage.lower() != "nan" else "Stage TBD"


def _fixture_card_bottom_markup(round_stage: str, stage: str) -> str:
    if _is_group_stage_label(round_stage) and stage != round_stage:
        return (
            '<div class="fixture-card-bottom">'
            f'<span>{html.escape(round_stage)}</span><span>{html.escape(stage)}</span>'
            '</div>'
        )
    return (
        '<div class="fixture-card-bottom is-centered">'
        f'<span>{html.escape(round_stage)}</span>'
        '</div>'
    )


def _fixture_focus_top_markup(match_number: str, city: str, center: str, round_stage: str) -> str:
    if _is_group_stage_label(round_stage):
        return f'<div class="fixture-focus-top"><span>{match_number}</span><span>{html.escape(city)}</span></div>'
    return (
        '<div class="fixture-focus-top has-center">'
        f'<span>{match_number}</span><strong>{center}</strong><span>{html.escape(city)}</span>'
        '</div>'
    )


def _fixture_focus_bottom_markup(round_stage: str, stage: str, center: str) -> str:
    if _is_group_stage_label(round_stage) and stage != round_stage:
        return (
            '<div class="fixture-focus-bottom">'
            f'<span>{html.escape(round_stage)}</span><strong>{center}</strong><span>{html.escape(stage)}</span>'
            '</div>'
        )
    return (
        '<div class="fixture-focus-bottom is-centered">'
        f'<span>{html.escape(round_stage)}</span>'
        '</div>'
    )


def _is_group_stage_label(value: str) -> bool:
    return str(value or "").strip().lower() == "group stage"


def _round_stage_label(value) -> str:
    key = _stage_key(value)
    if key in STAGE_LABELS:
        return STAGE_LABELS[key]
    text = str(value or "").replace("_", " ").strip()
    if text.lower().startswith("group "):
        return "Group Stage"
    return text.title() if text else "Stage TBD"


def _kickoff_time(utc_date, local_time) -> str:
    parsed = pd.to_datetime(utc_date, utc=True, errors="coerce")
    if not pd.isna(parsed):
        return parsed.tz_convert("America/Chicago").strftime("%I:%M %p").lstrip("0")
    return str(local_time or "")


def _scoreline(row) -> str:
    home_score = row.get("home_score")
    away_score = row.get("away_score")
    return f"{int(home_score)} - {int(away_score)}"


def _has_score(row) -> bool:
    return pd.notna(row.get("home_score")) and pd.notna(row.get("away_score"))


def _status_label(value) -> str:
    text = str(value or "Scheduled").replace("_", " ").strip()
    if text.upper() == "TIMED":
        return "Scheduled"
    return text.title()


def _styles() -> None:
    st.markdown(
        """
        <style>
        .fixtures-source, .fixtures-note {
            color: #D6A83A;
            font-weight: 850;
            margin: .2rem 0 1rem;
        }
        [data-testid="stWidgetLabel"] p {
            color: #D6A83A;
            font-weight: 900;
            text-transform: uppercase;
            font-size: .82rem;
        }
        [data-baseweb="select"] > div,
        [data-baseweb="input"] > div,
        [data-testid="stDateInput"] input {
            background-color: rgba(255,255,255,.10);
            border-color: rgba(214,168,58,.32);
            color: #FFFFFF;
        }
        [data-testid="stDateInput"] [data-baseweb="input"],
        [data-testid="stDateInput"] [data-baseweb="base-input"],
        [data-testid="stDateInput"] [data-baseweb="input"] > div,
        [data-testid="stDateInput"] [data-baseweb="base-input"] > div,
        [data-testid="stDateInput"] input {
            background: rgba(255,255,255,.10) !important;
            background-color: rgba(255,255,255,.10) !important;
            border-color: rgba(214,168,58,.32) !important;
            color: #FFFFFF !important;
        }
        [data-testid="stDateInput"] [data-baseweb="input"],
        [data-testid="stDateInput"] [data-baseweb="base-input"] {
            border: 1px solid rgba(214,168,58,.32) !important;
            border-radius: 8px !important;
        }
        [data-testid="stDateInput"] [data-baseweb="input"]:hover,
        [data-testid="stDateInput"] [data-baseweb="base-input"]:hover,
        [data-testid="stDateInput"] [data-baseweb="input"]:hover > div,
        [data-testid="stDateInput"] [data-baseweb="base-input"]:hover > div {
            background: rgba(255,255,255,.14) !important;
            background-color: rgba(255,255,255,.14) !important;
            border-color: rgba(214,168,58,.68) !important;
        }
        [data-testid="stDateInput"] [data-baseweb="input"]:focus-within,
        [data-testid="stDateInput"] [data-baseweb="base-input"]:focus-within {
            background: rgba(255,255,255,.14) !important;
            background-color: rgba(255,255,255,.14) !important;
            border-color: #D6A83A !important;
            box-shadow: 0 0 0 1px rgba(214,168,58,.30) !important;
        }
        [data-baseweb="select"] span,
        [data-baseweb="input"] input,
        [data-testid="stDateInput"] input {
            color: #FFFFFF !important;
            -webkit-text-fill-color: #FFFFFF !important;
        }
        [data-baseweb="select"] div {
            color: #F8FAFC;
        }
        [data-baseweb="select"] [aria-disabled="true"],
        [data-baseweb="select"] [class*="placeholder"] {
            color: #CBD5E1;
        }
        [data-baseweb="select"] svg {
            color: #D6A83A;
        }
        [data-testid="stDateInput"] svg {
            color: #D6A83A !important;
            fill: #D6A83A !important;
        }
        .fixture-stat {
            border: 1px solid rgba(214,168,58,.28);
            border-radius: 8px;
            background: rgba(5,5,5,.34);
            padding: .9rem 1rem;
            margin-bottom: .6rem;
        }
        .fixture-stat span {
            color: #FFFFFF;
            display: block;
            font-size: 2rem;
            font-weight: 950;
            line-height: 1;
        }
        .fixture-stat small {
            color: #D6A83A;
            font-weight: 850;
            text-transform: uppercase;
        }
        .fixture-day {
            display: flex;
            align-items: flex-end;
            justify-content: space-between;
            gap: 1rem;
            border-top: 1px solid rgba(214,168,58,.30);
            margin: 1.6rem 0 .8rem;
            padding-top: 1rem;
        }
        .fixture-day-kicker {
            color: #D6A83A;
            font-size: .75rem;
            font-weight: 950;
            text-transform: uppercase;
        }
        .fixture-day h2 {
            color: #FFFFFF;
            margin: .1rem 0 0;
            font-size: 1.75rem;
            font-weight: 950;
        }
        .fixture-day-meta {
            color: #D6A83A;
            font-weight: 850;
            padding-bottom: .15rem;
        }
        .fixture-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: .9rem;
        }
        .fixture-card-link,
        .fixture-card-link:hover,
        .fixture-card-link:focus,
        .fixture-card-link:visited {
            color: inherit;
            display: block;
            text-decoration: none !important;
        }
        [class*="st-key-fixture_open_"] {
            height: 245px;
            margin-top: -245px;
            margin-bottom: .9rem;
            position: relative;
            z-index: 2;
        }
        [class*="st-key-fixture_open_"] button {
            background: transparent !important;
            border: 0 !important;
            box-shadow: none !important;
            color: transparent !important;
            cursor: pointer;
            height: 245px;
            min-height: 245px;
            opacity: 0;
            padding: 0 !important;
        }
        [class*="st-key-fixture_open_"] button p {
            color: transparent !important;
        }
        .fixture-card {
            min-height: 245px;
            border: 1px solid rgba(255,255,255,.18);
            border-radius: 8px;
            background-size: cover;
            background-position: center;
            box-shadow: 0 16px 38px rgba(0,0,0,.24);
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            overflow: hidden;
            padding: .95rem;
            cursor: pointer;
            transition: border-color .15s ease, box-shadow .15s ease, transform .15s ease;
        }
        .fixture-card-top, .fixture-card-bottom {
            display: flex;
            justify-content: space-between;
            gap: .75rem;
            color: #D6A83A;
            font-size: .78rem;
            font-weight: 900;
            text-transform: uppercase;
            text-shadow: 0 2px 10px rgba(0,0,0,.75);
        }
        .fixture-card-bottom.is-centered {
            justify-content: center;
            text-align: center;
        }
        .fixture-card-body {
            color: #FFFFFF;
            text-shadow: 0 3px 16px rgba(0,0,0,.9);
        }
        .fixture-teams {
            display: grid;
            grid-template-columns: 1fr auto 1fr;
            align-items: center;
            gap: .55rem;
            font-size: 1.28rem;
            font-weight: 950;
            line-height: 1.05;
            text-align: center;
        }
        .fixture-teams strong {
            color: #D6A83A;
            font-size: .82rem;
        }
        .fixture-team-label {
            align-items: center;
            display: flex;
            flex-direction: column;
            gap: .42rem;
            min-width: 0;
        }
        .fixture-team-label span:last-child {
            overflow-wrap: anywhere;
        }
        .fixture-card-flag {
            aspect-ratio: 3 / 2;
            border: 1px solid rgba(255,255,255,.70);
            border-radius: 4px;
            box-shadow: 0 8px 16px rgba(0,0,0,.34);
            display: block;
            object-fit: cover;
            object-position: center;
            width: 34px;
        }
        .fixture-card-flag.flag-fallback {
            align-items: center;
            background: linear-gradient(135deg, rgba(214,168,58,.50), rgba(36,88,255,.28));
            color: #FFFFFF;
            display: grid;
            font-size: .58rem;
            font-weight: 950;
            justify-content: center;
            line-height: 1;
        }
        .fixture-score {
            margin-top: .8rem;
            text-align: center;
            color: #f8fafc;
            font-weight: 900;
        }
        .fixture-focus {
            min-height: calc(100vh - 190px);
            border: 1px solid rgba(214,168,58,.42);
            border-radius: 8px;
            background-size: cover;
            background-position: center;
            box-shadow: 0 22px 58px rgba(0,0,0,.34);
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            margin-top: .8rem;
            overflow: hidden;
            padding: 1.35rem;
            position: relative;
        }
        .fixture-focus::before {
            background:
                radial-gradient(circle at 50% 46%, rgba(0,0,0,.06), rgba(0,0,0,.34) 54%, rgba(0,0,0,.48) 100%),
                linear-gradient(90deg, rgba(0,0,0,.24), rgba(0,0,0,.02) 34%, rgba(0,0,0,.02) 66%, rgba(0,0,0,.24));
            content: "";
            inset: 0;
            pointer-events: none;
            position: absolute;
            z-index: 0;
        }
        .fixture-focus-top, .fixture-focus-bottom {
            display: flex;
            justify-content: space-between;
            gap: 1rem;
            color: #D6A83A;
            font-size: .95rem;
            font-weight: 950;
            text-transform: uppercase;
            text-shadow: 0 3px 14px rgba(0,0,0,.84);
            position: relative;
            z-index: 2;
        }
        .fixture-focus-top span,
        .fixture-focus-top strong,
        .fixture-focus-bottom span,
        .fixture-focus-bottom strong {
            background: rgba(5,5,5,.38);
            border: 1px solid rgba(255,255,255,.14);
            border-radius: 999px;
            padding: .36rem .62rem;
        }
        .fixture-focus-top.has-center strong {
            color: #FFFFFF;
            font-size: clamp(1.05rem, 2vw, 1.6rem);
            font-weight: 950;
            left: 50%;
            position: absolute;
            text-transform: none;
            top: 50%;
            transform: translate(-50%, -50%);
            white-space: nowrap;
        }
        .fixture-focus-bottom strong {
            color: #FFFFFF;
            font-size: clamp(1.05rem, 2vw, 1.6rem);
            font-weight: 950;
            left: 50%;
            position: absolute;
            text-transform: none;
            top: 50%;
            transform: translate(-50%, -50%);
            white-space: nowrap;
        }
        .fixture-focus-bottom {
            margin-top: auto;
        }
        .fixture-focus-bottom.is-centered {
            justify-content: center;
        }
        .fixture-focus-body {
            left: clamp(1.5rem, 5vw, 5rem);
            position: absolute;
            right: clamp(1.5rem, 5vw, 5rem);
            top: 50%;
            transform: translateY(-50%);
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            align-items: center;
            gap: clamp(2rem, 10vw, 12rem);
            color: #FFFFFF;
            text-shadow: 0 5px 22px rgba(0,0,0,.92);
            z-index: 1;
        }
        .fixture-focus-team {
            align-items: center;
            display: flex;
            flex-direction: column;
            gap: .9rem;
            min-width: 0;
            justify-self: center;
            font-size: clamp(2rem, 4.2vw, 4.8rem);
            font-weight: 950;
            line-height: .94;
            max-width: min(38vw, 540px);
            text-align: center;
        }
        .fixture-focus-team div {
            overflow-wrap: normal;
            text-wrap: balance;
        }
        .fixture-focus-team.right {
            align-items: center;
            text-align: center;
        }
        .fixture-focus-flag {
            width: clamp(98px, 12vw, 180px);
            aspect-ratio: 3 / 2;
            object-fit: cover;
            object-position: center;
            display: block;
            border: 2px solid rgba(255,255,255,.78);
            border-radius: 8px;
            box-shadow: 0 14px 30px rgba(0,0,0,.46);
        }
        .fixture-odds-panel {
            background: rgba(5,5,5,.42);
            border: 1px solid rgba(214,168,58,.28);
            border-radius: 8px;
            display: grid;
            gap: 1px;
            grid-template-columns: 1.35fr 1fr;
            margin: 1rem 0;
            overflow: hidden;
        }
        .fixture-odds-group {
            background: rgba(255,255,255,.055);
            padding: .85rem;
        }
        .fixture-odds-group h3 {
            color: #D6A83A;
            font-size: .95rem;
            font-weight: 950;
            letter-spacing: 0;
            margin: 0 0 .7rem;
            text-transform: uppercase;
        }
        .fixture-odds-prices {
            display: grid;
            gap: .55rem;
        }
        .fixture-odds-prices.moneyline {
            grid-template-columns: repeat(3, minmax(0, 1fr));
        }
        .fixture-odds-prices.totals {
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }
        .fixture-odds-price {
            align-items: center;
            background: rgba(5,5,5,.30);
            border: 1px solid rgba(255,255,255,.10);
            border-radius: 8px;
            display: grid;
            gap: .35rem;
            min-height: 76px;
            padding: .65rem .75rem;
            text-align: center;
        }
        .fixture-odds-price span {
            color: #FFFFFF;
            font-weight: 900;
            min-width: 0;
            overflow-wrap: anywhere;
        }
        .fixture-odds-price strong {
            color: #FFFFFF;
            font-size: 1.25rem;
            font-weight: 950;
        }
        @media (max-width: 980px) {
            .fixture-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }
        @media (max-width: 660px) {
            .fixture-grid {
                grid-template-columns: 1fr;
            }
            .fixture-day {
                align-items: flex-start;
                flex-direction: column;
            }
            .fixture-focus-body {
                grid-template-columns: 1fr;
                left: 1rem;
                right: 1rem;
                text-align: center;
                top: 52%;
            }
            .fixture-focus-team,
            .fixture-focus-team.right {
                align-items: center;
                text-align: center;
            }
            .fixture-odds-panel {
                grid-template-columns: 1fr;
            }
            .fixture-odds-prices.moneyline {
                grid-template-columns: 1fr;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
