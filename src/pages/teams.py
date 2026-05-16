from __future__ import annotations

import html
from datetime import datetime

import pandas as pd
import streamlit as st

from src.city_backgrounds import city_background_data_uri
from src.database import fetch_df
from src.fixture_display import enrich_fixture_participants, flag_code_for_team, flag_lookup_with_aliases
from src.football_data_service import cached_matches
from src.official_match_reference import apply_official_match_reference, normalize_team_key
from src.storage.storage import (
    load_favorite_teams,
    personal_preferences_use_browser_storage,
    preferences_are_session_only,
    save_favorite_teams,
)
from src.utils.formatting import format_local_time


FALLBACK_FLAGS = {
    "England": "gb-eng",
    "Scotland": "gb-sct",
}


def render() -> None:
    st.title("Teams")
    _styles()
    scope = "this session only" if preferences_are_session_only() else "this browser"
    st.caption(f"Favorite teams are personal and saved on {scope}.")

    teams = _teams()
    if teams.empty:
        st.info("Import teams to start building the field.")
        return

    selected_id = st.session_state.get("selected_team_id")
    if selected_id:
        selected = teams[teams["id"] == selected_id]
        if not selected.empty:
            _team_focus(selected.iloc[0])
            return
        st.session_state.pop("selected_team_id", None)

    sorted_teams = teams.sort_values(["favorite_sort", "team"], ascending=[False, True])
    for start in range(0, len(sorted_teams), 2):
        cols = st.columns(2)
        for col, (_, team) in zip(cols, sorted_teams.iloc[start:start + 2].iterrows()):
            with col:
                _team_card(team)


def _teams() -> pd.DataFrame:
    teams = fetch_df(
        """
        SELECT t.id, t.name AS team, t.name, t.country_code, t.flag, g.group_name,
               t.favorite, t.why_interested, t.key_players, t.notes,
               r.rank AS fifa_rank
        FROM teams t
        LEFT JOIN groups g ON g.team_id = t.id
        LEFT JOIN (
            SELECT team_id, rank
            FROM fifa_rankings r
            WHERE ranking_date = (
                SELECT MAX(r2.ranking_date) FROM fifa_rankings r2 WHERE r2.team_id = r.team_id
            )
        ) r ON r.team_id = t.id
        ORDER BY t.name
        """
    )
    if teams.empty:
        return teams
    if personal_preferences_use_browser_storage():
        favorite_ids = set(load_favorite_teams())
        teams["favorite"] = teams["id"].apply(lambda value: 1 if int(value) in favorite_ids else 0)
    teams["favorite_sort"] = teams["favorite"].fillna(0).astype(int)
    return teams


def _team_card(team) -> None:
    flag_url = _flag_url(team)
    rank = _display_rank(team["fifa_rank"])
    group = team["group_name"] or "Unassigned"
    star = "★" if int(team["favorite"] or 0) else "☆"
    favorite_label = "Remove favorite" if int(team["favorite"] or 0) else "Make favorite"

    st.markdown(
        f"""
        <div class="team-card" style="background-image: linear-gradient(90deg, rgba(3,7,18,.76), rgba(3,7,18,.45)), url('{flag_url}');">
          <div class="team-card-content">
            <div class="team-name">{team['team']}</div>
            <div class="team-meta">Group {group}</div>
            <div class="team-rank">FIFA Rank {rank}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    c1, c2 = st.columns([1, 4])
    with c1:
        with st.container(key=f"favorite_star_{team['id']}"):
            if st.button(star, key=f"fav_{team['id']}", help=favorite_label):
                _toggle_favorite(int(team["id"]), int(team["favorite"] or 0))
                st.rerun()
    if c2.button(f"Open {team['team']}", key=f"open_{team['id']}", use_container_width=True):
        st.session_state["selected_team_id"] = int(team["id"])
        st.rerun()


def _team_focus(team) -> None:
    fixtures = _fixtures_for_team(team)
    selected_match = st.session_state.get("selected_match_id")
    if selected_match:
        match = fixtures[fixtures["match_id"] == selected_match] if not fixtures.empty else pd.DataFrame()
        if not match.empty:
            _match_focus(match.iloc[0], team)
            return
        st.session_state.pop("selected_match_id", None)

    flag_url = _flag_url(team)
    st.markdown(
        f"""
        <div class="team-focus" style="background-image: linear-gradient(90deg, rgba(3,7,18,.88), rgba(3,7,18,.70)), url('{flag_url}');">
          <div class="team-focus-title">{team['team']}</div>
          <div class="team-focus-subtitle">Group {team['group_name'] or 'Unassigned'} | FIFA Rank {_display_rank(team['fifa_rank'])}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    c1, c2 = st.columns([1, 5])
    if c1.button("Close", key="close_team_focus"):
        st.session_state.pop("selected_team_id", None)
        st.session_state.pop("selected_match_id", None)
        if "team_id" in st.query_params:
            del st.query_params["team_id"]
        st.rerun()

    _ranking_context(team["team"])
    if fixtures.empty:
        st.info("No fixtures stored for this team yet.")
    else:
        st.subheader("Fixtures")
        for _, fixture in fixtures.iterrows():
            if st.button(_fixture_button_label(fixture, team["team"]), key=f"fixture_{team['id']}_{fixture['match_id']}", use_container_width=True):
                _open_fixture_in_fixtures_tab(fixture)


def _ranking_context(team_name: str) -> None:
    rankings = fetch_df(
        """
        SELECT team_name AS team, rank
        FROM global_fifa_rankings
        WHERE ranking_date = (
            SELECT MAX(ranking_date) FROM global_fifa_rankings
        )
        ORDER BY rank
        """
    )
    if rankings.empty:
        st.info("Import FIFA rankings to show ranking context.")
        return
    current = rankings[rankings["team"] == team_name]
    if current.empty:
        st.info("This team does not have a FIFA ranking yet.")
        return
    rank = int(current.iloc[0]["rank"])
    context = rankings[(rankings["rank"] >= rank - 2) & (rankings["rank"] <= rank + 2)].copy()
    rows = "".join(_ranking_context_row(row, team_name) for _, row in context.iterrows())
    st.markdown(
        f"""
        <section class="ranking-context-shell">
            <div class="ranking-context-header">
                <div>
                    <div class="ranking-context-kicker">FIFA Ranking Context</div>
                    <h3>{html.escape(team_name)}</h3>
                </div>
                <div class="ranking-context-rank">Rank #{rank}</div>
            </div>
            <table class="ranking-context-table">
                <thead><tr><th>Country</th><th>FIFA Rank</th></tr></thead>
                <tbody>{rows}</tbody>
            </table>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _ranking_context_row(row, focus_team: str) -> str:
    team = html.escape(str(row["team"]))
    rank = "" if pd.isna(row["rank"]) else str(int(row["rank"]))
    focus_class = " ranking-context-focus" if row["team"] == focus_team else ""
    return f'<tr class="{focus_class}"><td>{team}</td><td>#{rank}</td></tr>'


def _fixtures_for_team(team) -> pd.DataFrame:
    local_fixtures = fetch_df(
        """
        SELECT f.match_number AS match_id, f.kickoff_utc,
               f.home_team_id, f.away_team_id,
               ht.name AS home_team, at.name AS away_team,
               f.stage, f.group_name, m.game_label,
               COALESCE(m.city, f.city) AS venue, COALESCE(m.city, f.city) AS city,
               f.status,
               f.home_score, f.away_score
        FROM fixtures f
        LEFT JOIN teams ht ON ht.id = f.home_team_id
        LEFT JOIN teams at ON at.id = f.away_team_id
        LEFT JOIN match_city_reference m ON m.match_number = f.match_number
        ORDER BY datetime(f.kickoff_utc)
        """
    )
    local_fixtures = enrich_fixture_participants(local_fixtures)
    if not local_fixtures.empty:
        team_key = normalize_team_key(team["team"])
        local_fixtures = local_fixtures[
            local_fixtures["home_team"].map(normalize_team_key).eq(team_key)
            | local_fixtures["away_team"].map(normalize_team_key).eq(team_key)
        ].copy()
    if not local_fixtures.empty:
        return local_fixtures

    try:
        matches = cached_matches()
    except Exception:
        return local_fixtures
    if matches.empty:
        return local_fixtures
    matches = apply_official_match_reference(matches)
    team_name = normalize_team_key(team["team"])
    provider_matches = matches[
        matches["home_team"].map(normalize_team_key).eq(team_name)
        | matches["away_team"].map(normalize_team_key).eq(team_name)
    ].copy()
    if provider_matches.empty:
        return local_fixtures
    provider_matches = provider_matches.rename(
        columns={
            "utc_date": "kickoff_utc",
            "group": "group_name",
        }
    )
    provider_matches["match_id"] = provider_matches["official_match_number"]
    return provider_matches


def _fixture_button_label(fixture, team_name: str) -> str:
    opponent = fixture["away_team"] if fixture["home_team"] == team_name else fixture["home_team"]
    opponent = opponent if pd.notna(opponent) and str(opponent).strip() else "TBD"
    venue = fixture["venue"] or "Venue TBD"
    if pd.notna(fixture["home_score"]) and pd.notna(fixture["away_score"]):
        score = f"{fixture['home_team']} {int(fixture['home_score'])} - {int(fixture['away_score'])} {fixture['away_team']}"
        return f"{score} | {venue}"
    return f"{format_local_time(fixture['kickoff_utc'])} | vs {opponent} | {venue}"


def _open_fixture_in_fixtures_tab(fixture) -> None:
    match_id = _fixture_match_id(fixture)
    st.session_state["page_name"] = "Fixtures"
    st.session_state["selected_fixture_id"] = match_id
    st.session_state["selected_fixture_row"] = _fixture_focus_row(fixture, match_id)
    st.session_state.pop("selected_team_id", None)
    st.session_state.pop("selected_match_id", None)
    st.query_params["page"] = "fixtures"
    if "team_id" in st.query_params:
        del st.query_params["team_id"]
    if "fixture" in st.query_params:
        del st.query_params["fixture"]
    st.rerun()


def _fixture_focus_row(fixture, match_id: str) -> dict:
    return {
        "official_match_number": fixture.get("official_match_number", fixture.get("match_id")),
        "match_id": match_id,
        "utc_date": fixture.get("utc_date", fixture.get("kickoff_utc")),
        "local_time": fixture.get("local_time", format_local_time(fixture.get("kickoff_utc"))),
        "home_team": fixture.get("home_team"),
        "away_team": fixture.get("away_team"),
        "stage": fixture.get("stage"),
        "group": fixture.get("group", fixture.get("group_name")),
        "venue": fixture.get("venue"),
        "city": fixture.get("city", fixture.get("venue")),
        "home_score": fixture.get("home_score"),
        "away_score": fixture.get("away_score"),
    }


def _fixture_match_id(fixture) -> str:
    value = fixture.get("official_match_number", fixture.get("match_id"))
    if pd.isna(value) or value == "":
        return "Match"
    text = str(value)
    return text if text.startswith("M") else f"M{int(float(text))}"


def _match_focus(fixture, team) -> None:
    venue = fixture["venue"] or "Venue TBD"
    background = city_background_data_uri(venue)
    background_style = (
        f"linear-gradient(90deg, rgba(2,6,23,.58), rgba(2,6,23,.82)), url('{background}')"
        if background
        else "linear-gradient(135deg, #0b1220, #164e63)"
    )
    played = pd.notna(fixture["home_score"]) and pd.notna(fixture["away_score"])
    center = (
        f"{int(fixture['home_score'])} - {int(fixture['away_score'])}"
        if played
        else format_local_time(fixture["kickoff_utc"])
    )
    st.markdown(
        f"""
        <div class="match-focus" style="background-image: {background_style};">
          <div class="stadium-bg"></div>
          <div class="match-team">{_flag_image_for_team_name(fixture['home_team'])}<br>{html.escape(str(fixture['home_team'] or 'TBD'))}</div>
          <div class="match-center">
            <div class="match-time">{html.escape(str(center))}</div>
            <div class="match-venue">{html.escape(str(venue))}</div>
          </div>
          <div class="match-team right">{_flag_image_for_team_name(fixture['away_team'])}<br>{html.escape(str(fixture['away_team'] or 'TBD'))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Close Match View", key="close_match_focus"):
        st.session_state.pop("selected_match_id", None)
        st.rerun()


def _toggle_favorite(team_id: int, current: int) -> None:
    favorite_ids = set(load_favorite_teams())
    if current:
        favorite_ids.discard(team_id)
    else:
        favorite_ids.add(team_id)
    save_favorite_teams(favorite_ids)


def _flag_url(team) -> str:
    code = str(team.get("country_code") or "").strip().lower()
    code = FALLBACK_FLAGS.get(team["team"], code)
    if code:
        return f"https://flagcdn.com/w1280/{code}.png"
    return ""


def _flag_image_for_team_name(team_name: str | None) -> str:
    if not team_name:
        return ""
    code = flag_code_for_team(team_name, _team_flag_lookup())
    if not code:
        return ""
    return f'<img class="match-flag" src="https://flagcdn.com/w160/{html.escape(code)}.png" alt="">'


@st.cache_data(show_spinner=False)
def _team_flag_lookup() -> dict[str, str]:
    teams = fetch_df("SELECT name, country_code FROM teams")
    return flag_lookup_with_aliases(teams)


def _display_rank(value) -> str:
    return "TBD" if value is None or pd.isna(value) else str(int(value))


def _styles() -> None:
    st.markdown(
        """
        <style>
        .team-card {
            min-height: 190px;
            border-radius: 18px;
            background-size: cover;
            background-position: center;
            border: 1px solid rgba(255,255,255,.18);
            box-shadow: 0 12px 30px rgba(15,23,42,.22);
            display: flex;
            align-items: flex-end;
            margin-bottom: .45rem;
            overflow: hidden;
        }
        .team-card-content {
            padding: 1.25rem;
            text-shadow: 0 2px 9px rgba(0,0,0,.9);
        }
        .team-name {
            color: white;
            font-size: 2rem;
            font-weight: 900;
            line-height: 1.05;
        }
        .team-meta, .team-rank {
            color: #f8fafc;
            font-size: 1.05rem;
            font-weight: 800;
            margin-top: .25rem;
        }
        .team-focus {
            min-height: 420px;
            border-radius: 22px;
            background-size: cover;
            background-position: center;
            display: flex;
            flex-direction: column;
            justify-content: center;
            padding: 3rem;
            margin: 1rem 0 1.25rem;
            box-shadow: 0 16px 50px rgba(15,23,42,.28);
        }
        .team-focus-title {
            color: white;
            font-size: 4.25rem;
            font-weight: 900;
            text-shadow: 0 3px 18px rgba(0,0,0,.9);
        }
        .team-focus-subtitle {
            color: #f8fafc;
            font-size: 1.35rem;
            font-weight: 800;
            text-shadow: 0 2px 12px rgba(0,0,0,.9);
        }
        .ranking-context-shell {
            border: 1px solid rgba(214,168,58,.28);
            border-radius: 8px;
            background:
                linear-gradient(135deg, rgba(5,5,5,.48), rgba(11,16,32,.38)),
                radial-gradient(circle at 88% 12%, rgba(214,168,58,.16), transparent 30%);
            padding: 1rem;
            margin: 1rem 0 1.25rem;
            box-shadow: 0 14px 34px rgba(0,0,0,.20);
        }
        .ranking-context-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-end;
            gap: 1rem;
            margin-bottom: .8rem;
        }
        .ranking-context-kicker, .ranking-context-rank {
            color: #D6A83A;
            font-size: .78rem;
            font-weight: 950;
            text-transform: uppercase;
        }
        .ranking-context-header h3 {
            color: white;
            font-size: 1.55rem;
            margin: .1rem 0 0;
        }
        .ranking-context-table {
            width: 100%;
            border-collapse: collapse;
            border-radius: 8px;
            overflow: hidden;
        }
        .ranking-context-table th {
            color: #050505;
            background: linear-gradient(135deg, #D6A83A, #9E7420);
            text-transform: uppercase;
            font-size: .8rem;
            padding: .65rem .8rem;
            text-align: left;
        }
        .ranking-context-table td {
            color: white;
            background: rgba(255,255,255,.055);
            border-bottom: 1px solid rgba(255,255,255,.09);
            padding: .7rem .8rem;
            font-weight: 850;
        }
        .ranking-context-table td:last-child {
            text-align: right;
            color: #D6A83A;
        }
        .ranking-context-table .ranking-context-focus td {
            background: rgba(214,168,58,.20);
            color: white;
            font-weight: 950;
        }
        .ranking-context-table .ranking-context-focus td:last-child {
            color: #FFFFFF;
        }
        [class*="st-key-favorite_star_"] button {
            background: #050505;
            border: 2px solid #D6A83A;
            color: #D6A83A;
            font-size: 1.35rem;
            line-height: 1;
            min-height: 2.75rem;
            box-shadow: 0 8px 22px rgba(0,0,0,.34);
            text-shadow: none;
        }
        [class*="st-key-favorite_star_"] button:hover {
            background: #111111;
            color: #050505;
            border-color: #FFFFFF;
            transform: translateY(-1px);
        }
        [class*="st-key-favorite_star_"] button:hover p {
            color: #D6A83A;
        }
        [class*="st-key-favorite_star_"] button p {
            color: #D6A83A;
            font-weight: 950;
        }
        .match-focus {
            min-height: 520px;
            border-radius: 22px;
            background-size: cover;
            background-position: center;
            position: relative;
            overflow: hidden;
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            align-items: center;
            margin: 1rem 0;
            padding: 2rem;
        }
        .stadium-bg {
            position: absolute;
            inset: 0;
            background:
              radial-gradient(circle at center, rgba(255,255,255,.22), transparent 38%),
              repeating-linear-gradient(90deg, rgba(255,255,255,.08) 0 2px, transparent 2px 90px);
            opacity: .32;
        }
        .match-team, .match-center {
            position: relative;
            color: white;
            text-align: center;
            text-shadow: 0 3px 16px rgba(0,0,0,.9);
        }
        .match-team {
            font-size: 2.8rem;
            font-weight: 900;
        }
        .match-flag {
            width: 96px;
            height: 64px;
            object-fit: cover;
            border-radius: 6px;
            box-shadow: 0 8px 24px rgba(0,0,0,.36);
            margin-bottom: .75rem;
        }
        .match-time {
            font-size: 2rem;
            font-weight: 900;
        }
        .match-venue {
            font-size: 1.1rem;
            font-weight: 800;
            color: #dbeafe;
            margin-top: .75rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
