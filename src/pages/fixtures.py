from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from data_sources.football_data_client import FootballDataError
from src.city_backgrounds import city_background_card_data_uri, city_background_data_uri
from src.database import fetch_df
from src.fixture_display import enrich_fixture_participants, flag_code_for_team, flag_lookup_with_aliases
from src.football_data_service import cached_matches, daily_fixture_refresh_key
from src.official_match_reference import apply_official_match_reference
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
    "quarterfinals": "Quarter Finals",
    "quarterfinal": "Quarter Finals",
    "semifinals": "Semi Finals",
    "semifinal": "Semi Finals",
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
    home = html.escape(str(row.get("home_team") or "TBD"))
    away = html.escape(str(row.get("away_team") or "TBD"))
    match_number = _match_number(row)
    stage = _stage_label(row)
    time = html.escape(_kickoff_time(row.get("utc_date"), row.get("local_time")))
    center = _scoreline(row) if _has_score(row) else time
    return (
        f'<article class="fixture-card" style="background-image: {background_style};">'
        '<div class="fixture-card-top">'
        f'<span>{html.escape(match_number)}</span><span>{html.escape(stage)}</span>'
        '</div>'
        '<div class="fixture-card-body">'
        f'<div class="fixture-teams"><div>{home}</div><strong>vs</strong><div>{away}</div></div>'
        f'<div class="fixture-score">{html.escape(center)}</div>'
        '</div>'
        '<div class="fixture-card-bottom">'
        f'<span>{html.escape(stage)}</span><span>{html.escape(city)}</span>'
        '</div>'
        '</article>'
    )


def _render_fixture_focus(row) -> None:
    if st.button("Close Match View", key="close_fixture_focus"):
        st.session_state.pop("selected_fixture_id", None)
        st.session_state.pop("selected_fixture_row", None)
        st.query_params["page"] = "fixtures"
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
    stage = html.escape(_stage_label(row))
    time = html.escape(_kickoff_time(row.get("utc_date"), row.get("local_time")))
    center = html.escape(_scoreline(row) if _has_score(row) else time)
    markup = (
        f'<section class="fixture-focus" style="background-image: {background_style};">'
        f'<div class="fixture-focus-top"><span>{match_number}</span><span>{stage}</span></div>'
        '<div class="fixture-focus-body">'
        f'<div class="fixture-focus-team">{home_flag}<div>{home}</div></div>'
        f'<div class="fixture-focus-center"><div class="fixture-focus-vs">vs</div><div class="fixture-focus-time">{center}</div></div>'
        f'<div class="fixture-focus-team right">{away_flag}<div>{away}</div></div>'
        '</div>'
        f'<div class="fixture-focus-bottom"><span>{stage}</span><span>{html.escape(city)}</span></div>'
        '</section>'
    )
    st.markdown(markup, unsafe_allow_html=True)


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
        return group
    if stage == "Last 32":
        return "Round of 32"
    if stage == "Last 16":
        return "Round of 16"
    return stage if stage and stage.lower() != "nan" else "Stage TBD"


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
        }
        .fixture-focus-body {
            display: grid;
            grid-template-columns: 1fr auto 1fr;
            align-items: center;
            gap: 1.2rem;
            color: #FFFFFF;
            text-shadow: 0 5px 22px rgba(0,0,0,.92);
        }
        .fixture-focus-team {
            font-size: clamp(2rem, 5vw, 5.2rem);
            font-weight: 950;
            line-height: .95;
        }
        .fixture-focus-team.right {
            text-align: right;
        }
        .fixture-focus-flag {
            width: clamp(92px, 12vw, 170px);
            aspect-ratio: 3 / 2;
            object-fit: cover;
            border: 2px solid rgba(255,255,255,.78);
            border-radius: 8px;
            box-shadow: 0 14px 30px rgba(0,0,0,.46);
            margin-bottom: .8rem;
        }
        .fixture-focus-center {
            min-width: 120px;
            text-align: center;
        }
        .fixture-focus-vs {
            color: #D6A83A;
            font-size: 1rem;
            font-weight: 950;
            text-transform: uppercase;
        }
        .fixture-focus-time {
            color: #FFFFFF;
            font-size: clamp(1.25rem, 2.6vw, 2.4rem);
            font-weight: 950;
            margin-top: .3rem;
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
                text-align: center;
            }
            .fixture-focus-team,
            .fixture-focus-team.right {
                text-align: center;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
