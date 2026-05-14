from __future__ import annotations

from datetime import datetime, time, timedelta
import html
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from src.components.clickable_cards import clickable_cards
from src.database import fetch_df
from src.football_data_service import cached_matches
from src.official_match_reference import apply_official_match_reference, normalize_team_key

FALLBACK_FLAGS = {
    "England": "gb-eng",
    "Scotland": "gb-sct",
}
GROUP_REFRESH_TIME = time(4, 0)
APP_TIMEZONE = ZoneInfo("America/Chicago")


def render() -> None:
    st.title("Groups")
    _styles()

    groups = _groups_with_standings()
    if groups.empty:
        st.info("Import groups to see group cards and table shells.")
        return

    for group_name in sorted(groups["group_name"].dropna().unique()):
        subset = _sort_group_subset(groups[groups["group_name"] == group_name].copy())
        _group_banner(group_name, subset)
        clicked_team_id = clickable_cards(_group_cards(subset), variant="groups", key=f"group_cards_{group_name}")
        if clicked_team_id:
            _open_team(int(clicked_team_id))
        with st.expander(f"Open Group {group_name} details", expanded=False):
            _group_details(group_name, subset)


def _fmt_number(value) -> str:
    if pd.isna(value):
        return "TBD"
    return f"{value:.1f}"


def _groups_base() -> pd.DataFrame:
    return fetch_df(
        """
        SELECT t.id AS team_id, g.group_name, t.name AS team, t.name AS team_name,
               t.country_code, r.rank AS fifa_rank, r.points AS ranking_points, g.qualification_status,
               s.played, s.wins, s.draws, s.losses, s.goals_for, s.goals_against,
               s.points AS standing_points
        FROM groups g
        JOIN teams t ON t.id = g.team_id
        LEFT JOIN (
            SELECT team_id, rank, points
            FROM fifa_rankings r
            WHERE ranking_date = (
                SELECT MAX(r2.ranking_date) FROM fifa_rankings r2 WHERE r2.team_id = r.team_id
            )
        ) r ON r.team_id = t.id
        LEFT JOIN standings s ON s.group_name = g.group_name AND s.team_id = t.id
        ORDER BY g.group_name, COALESCE(r.rank, 999), t.name
        """
    )


def _groups_with_standings() -> pd.DataFrame:
    groups = _groups_base()
    if groups.empty:
        return groups
    live = _fixture_group_standings(_daily_group_refresh_key())
    if live.empty:
        return groups
    merged = groups.drop(
        columns=["played", "wins", "draws", "losses", "goals_for", "goals_against", "standing_points"],
        errors="ignore",
    ).merge(live, on=["team_id", "group_name"], how="left")
    for column in ["played", "wins", "draws", "losses", "goals_for", "goals_against", "standing_points"]:
        merged[column] = merged[column].fillna(0)
    return merged


@st.cache_data(show_spinner=False)
def _fixture_group_standings(refresh_key: str) -> pd.DataFrame:
    del refresh_key
    groups = _groups_base()
    if groups.empty:
        return pd.DataFrame()
    standings = {
        (int(row["team_id"]), str(row["group_name"])): {
            "team_id": int(row["team_id"]),
            "group_name": str(row["group_name"]),
            "played": 0,
            "wins": 0,
            "draws": 0,
            "losses": 0,
            "goals_for": 0,
            "goals_against": 0,
            "standing_points": 0,
        }
        for _, row in groups.iterrows()
    }
    team_lookup = {
        normalize_team_key(str(row["team"])): (int(row["team_id"]), str(row["group_name"]))
        for _, row in groups.iterrows()
    }

    try:
        fixtures = apply_official_match_reference(cached_matches())
    except Exception:
        return pd.DataFrame()
    if fixtures.empty:
        return pd.DataFrame()

    completed = fixtures[fixtures.apply(_is_completed_group_match, axis=1)].copy()
    for _, match in completed.iterrows():
        home_key = normalize_team_key(str(match.get("home_team") or ""))
        away_key = normalize_team_key(str(match.get("away_team") or ""))
        home_ref = team_lookup.get(home_key)
        away_ref = team_lookup.get(away_key)
        if not home_ref or not away_ref or home_ref[1] != away_ref[1]:
            continue
        home_score = int(match["home_score"])
        away_score = int(match["away_score"])
        _apply_group_result(standings[home_ref], home_score, away_score)
        _apply_group_result(standings[away_ref], away_score, home_score)

    rows = list(standings.values())
    if not any(row["played"] for row in rows):
        return pd.DataFrame()
    return pd.DataFrame(rows)


def _is_completed_group_match(row) -> bool:
    if pd.isna(row.get("home_score")) or pd.isna(row.get("away_score")):
        return False
    stage = str(row.get("stage") or "").lower()
    group = str(row.get("group") or "").strip().lower()
    has_group = bool(group) and group not in {"nan", "none"}
    return has_group or "group" in stage


def _apply_group_result(team_row: dict, goals_for: int, goals_against: int) -> None:
    team_row["played"] += 1
    team_row["goals_for"] += goals_for
    team_row["goals_against"] += goals_against
    if goals_for > goals_against:
        team_row["wins"] += 1
        team_row["standing_points"] += 3
    elif goals_for == goals_against:
        team_row["draws"] += 1
        team_row["standing_points"] += 1
    else:
        team_row["losses"] += 1


def _daily_group_refresh_key(now: datetime | None = None) -> str:
    local_now = now.astimezone(APP_TIMEZONE) if now else datetime.now(APP_TIMEZONE)
    refresh_day = local_now.date()
    if local_now.time() < GROUP_REFRESH_TIME:
        refresh_day -= timedelta(days=1)
    return refresh_day.isoformat()


def _group_banner(group_name: str, subset: pd.DataFrame) -> None:
    st.markdown(
        f"""
        <section class="group-banner">
            <div class="group-banner-copy">
                <div class="group-kicker">Group</div>
                <div class="group-title">{html.escape(str(group_name))}</div>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _group_details(group_name: str, subset: pd.DataFrame) -> None:
    table_rows = "".join(_table_row(row) for _, row in subset.iterrows())
    group = html.escape(str(group_name))
    avg_rank = _fmt_number(subset["fifa_rank"].mean())
    markup = (
        '<div class="group-detail-shell">'
        '<div class="group-detail-header">'
        f"<div><h3>Group {group}</h3></div>"
        f'<div class="group-detail-stat">Avg Rank {avg_rank}</div>'
        "</div>"
        '<table class="group-table"><thead><tr>'
        "<th>Team</th><th>Rank</th><th>W</th><th>D</th><th>L</th><th>GF</th><th>GA</th><th>GD</th><th>Pts</th>"
        "</tr></thead>"
        f"<tbody>{table_rows}</tbody></table>"
        "</div>"
    )
    st.markdown(markup, unsafe_allow_html=True)


def _group_cards(subset: pd.DataFrame) -> list[dict]:
    return [
        {
            "id": int(row["team_id"]),
            "name": str(row["team"]),
            "flag_url": _flag_url(row),
        }
        for _, row in subset.iterrows()
    ]


def _open_team(team_id: int) -> None:
    st.session_state["page_name"] = "Teams"
    st.session_state["selected_team_id"] = team_id
    st.session_state.pop("selected_match_id", None)
    st.session_state.pop("selected_fixture_id", None)
    st.session_state.pop("selected_fixture_row", None)
    st.query_params["page"] = "teams"
    st.query_params["team_id"] = str(team_id)
    if "fixture" in st.query_params:
        del st.query_params["fixture"]
    st.rerun()


def _team_card(row) -> str:
    team = html.escape(str(row["team"]))
    rank = "TBD" if pd.isna(row["fifa_rank"]) else str(int(row["fifa_rank"]))
    points = "" if pd.isna(row["ranking_points"]) else f"{float(row['ranking_points']):.1f} pts"
    meta = f"FIFA Rank {rank}{' | ' + points if points else ''}"
    return (
        f'<div class="group-team-card"><img src="{_flag_url(row)}" alt="">'
        f'<div><div class="group-team-name">{team}</div>'
        f'<div class="group-team-meta">{html.escape(meta)}</div></div></div>'
    )


def _table_row(row) -> str:
    team = html.escape(str(row["team"]))
    rank = "TBD" if pd.isna(row["fifa_rank"]) else str(int(row["fifa_rank"]))
    wins = _standing_int(row, "wins")
    draws = _standing_int(row, "draws")
    losses = _standing_int(row, "losses")
    goals_for = _standing_int(row, "goals_for")
    goals_against = _standing_int(row, "goals_against")
    goal_difference = goals_for - goals_against
    points = _standing_int(row, "standing_points")
    return (
        f'<tr><td><span class="table-team"><img src="{_flag_url(row)}" alt="">{team}</span></td>'
        f"<td>{rank}</td><td>{wins}</td><td>{draws}</td><td>{losses}</td>"
        f"<td>{goals_for}</td><td>{goals_against}</td><td>{goal_difference}</td>"
        f"<td><strong>{points}</strong></td></tr>"
    )


def _sort_group_subset(subset: pd.DataFrame) -> pd.DataFrame:
    sorted_subset = subset.copy()
    sorted_subset["_points_sort"] = sorted_subset["standing_points"].fillna(0)
    sorted_subset["_gd_sort"] = sorted_subset["goals_for"].fillna(0) - sorted_subset["goals_against"].fillna(0)
    sorted_subset["_rank_sort"] = sorted_subset["fifa_rank"].fillna(999)
    sorted_subset = sorted_subset.sort_values(
        ["_points_sort", "_gd_sort", "_rank_sort", "team"],
        ascending=[False, False, True, True],
    )
    return sorted_subset.drop(columns=["_points_sort", "_gd_sort", "_rank_sort"])


def _standing_int(row, column: str) -> int:
    value = row.get(column)
    return 0 if pd.isna(value) else int(value)


def _flag_url(row) -> str:
    team = str(row["team"])
    code = str(row.get("country_code") or "").strip().lower()
    code = FALLBACK_FLAGS.get(team, code)
    if not code:
        return "https://flagcdn.com/w160/un.png"
    return f"https://flagcdn.com/w160/{html.escape(code)}.png"


def _styles() -> None:
    st.markdown(
        """
        <style>
        [data-testid="stExpander"] details {
            border: 1px solid rgba(214,168,58,.28);
            border-radius: 8px;
            background: rgba(11,16,32,.72);
            overflow: hidden;
        }
        [data-testid="stExpander"] details,
        [data-testid="stExpander"] details[open] {
            background: rgba(11,16,32,.72) !important;
            border-color: rgba(214,168,58,.38) !important;
        }
        [data-testid="stExpander"] summary,
        [data-testid="stExpander"] details[open] summary {
            background: rgba(5,5,5,.46) !important;
            color: #D6A83A !important;
            border-radius: 8px 8px 0 0;
            font-weight: 900;
        }
        [data-testid="stExpander"] summary:hover,
        [data-testid="stExpander"] details[open] summary:hover {
            background: rgba(214,168,58,.13) !important;
            color: #D6A83A !important;
        }
        [data-testid="stExpander"] summary *,
        [data-testid="stExpander"] details[open] summary * {
            color: #D6A83A !important;
        }
        [data-testid="stExpander"] svg {
            color: #D6A83A !important;
            fill: #D6A83A !important;
        }
        .group-banner {
            min-height: 148px;
            margin: 1rem 0 .35rem;
            border: 1px solid rgba(214,168,58,.34);
            border-radius: 8px;
            background:
                linear-gradient(90deg, rgba(5,5,5,.78), rgba(11,16,32,.58)),
                radial-gradient(circle at 86% 18%, rgba(36,88,255,.22), transparent 28%);
            display: grid;
            grid-template-columns: minmax(130px, 190px) 1fr;
            align-items: center;
            gap: 1.25rem;
            padding: 1rem 1.25rem;
            box-shadow: 0 16px 38px rgba(0,0,0,.22);
        }
        .group-kicker {
            color: #D6A83A;
            font-size: .78rem;
            font-weight: 900;
            text-transform: uppercase;
        }
        .group-title {
            color: white;
            font-size: 4rem;
            font-weight: 950;
            line-height: .9;
        }
        .group-meta {
            color: #f8fafc;
            font-weight: 800;
            margin-top: .35rem;
        }
        .group-flags {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: .7rem;
        }
        .group-flag-link {
            color: inherit;
            display: block;
            text-decoration: none !important;
        }
        .group-flag-link:hover,
        .group-flag-link:focus,
        .group-flag-link:visited {
            color: inherit;
            text-decoration: none !important;
        }
        .group-flag-tile {
            min-height: 104px;
            border-radius: 8px;
            background: rgba(255,255,255,.08);
            border: 1px solid rgba(255,255,255,.14);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: .65rem;
            overflow: hidden;
        }
        .group-flag-tile img {
            width: 78px;
            height: 52px;
            object-fit: cover;
            border-radius: 5px;
            box-shadow: 0 8px 18px rgba(0,0,0,.32);
        }
        .group-flag-tile span {
            color: white;
            font-size: .82rem;
            font-weight: 850;
            margin-top: .45rem;
            text-align: center;
            line-height: 1.05;
        }
        .group-detail-shell {
            border: 1px solid rgba(214,168,58,.24);
            border-radius: 8px;
            background: rgba(5,5,5,.34);
            padding: 1rem;
            margin-bottom: 1.25rem;
        }
        .group-detail-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-end;
            gap: 1rem;
            margin-bottom: .85rem;
        }
        .group-detail-label, .group-detail-stat {
            color: #D6A83A;
            font-weight: 900;
            text-transform: uppercase;
            font-size: .78rem;
        }
        .group-detail-header h3 {
            margin: .1rem 0 0;
            font-size: 1.55rem;
        }
        .group-team-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: .75rem;
            margin-bottom: 1rem;
        }
        .group-team-card {
            display: flex;
            gap: .7rem;
            align-items: center;
            border: 1px solid rgba(255,255,255,.12);
            border-radius: 8px;
            background: rgba(255,255,255,.07);
            padding: .7rem;
        }
        .group-team-card img, .table-team img {
            width: 42px;
            height: 28px;
            object-fit: cover;
            border-radius: 4px;
        }
        .group-team-name {
            color: white;
            font-weight: 900;
            line-height: 1.05;
        }
        .group-team-meta {
            color: #D6A83A;
            font-size: .78rem;
            font-weight: 800;
            margin-top: .2rem;
        }
        .group-table {
            width: 100%;
            border-collapse: collapse;
            overflow: hidden;
            border-radius: 8px;
        }
        .group-table th {
            color: #050505;
            background: linear-gradient(135deg, #D6A83A, #9E7420);
            font-size: .78rem;
            text-transform: uppercase;
            padding: .65rem;
        }
        .group-table td {
            color: white;
            background: rgba(255,255,255,.055);
            border-bottom: 1px solid rgba(255,255,255,.09);
            padding: .62rem;
            text-align: center;
            font-weight: 750;
        }
        .group-table td:first-child {
            text-align: left;
        }
        .table-team {
            display: inline-flex;
            align-items: center;
            gap: .5rem;
            font-weight: 900;
        }
        @media (max-width: 860px) {
            .group-banner {
                grid-template-columns: 1fr;
            }
            .group-flags, .group-team-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
