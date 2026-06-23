from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from src.components.clickable_cards import clickable_cards
from src.database import fetch_df
from src.football_data_service import cached_matches, hourly_fixture_refresh_key
from src.navigation import remember_detail_origin
from src.official_match_reference import apply_official_match_reference, normalize_team_key
from src.standings_order import rank_group
from src.utils.team_names import display_team_name, team_lookup_keys

FALLBACK_FLAGS = {
    "England": "gb-eng",
    "Scotland": "gb-sct",
}


def render() -> None:
    st.title("Groups")
    _styles()

    groups = _groups_with_standings()
    if groups.empty:
        st.info("Import groups to see group cards and table shells.")
        return

    groups_tab, third_place_tab = st.tabs(["Groups", "3rd-Place Race"])
    with groups_tab:
        for group_name in sorted(groups["group_name"].dropna().unique()):
            subset = _sort_group_subset(groups[groups["group_name"] == group_name].copy())
            clicked_team_id = clickable_cards(
                _group_cards(subset),
                variant="groups",
                key=f"group_cards_{group_name}",
                title=str(group_name),
                detail_html=_group_details_markup(group_name, subset),
            )
            if clicked_team_id:
                _open_team(int(clicked_team_id))
    with third_place_tab:
        _render_third_place_race(groups)


def _render_third_place_race(groups: pd.DataFrame) -> None:
    table = _third_place_table(groups)
    if table.empty:
        st.info("Third-place standings will appear once the groups are set.")
        return
    st.caption(
        "The eight best third-placed teams advance to the Round of 32. "
        "Ranked by points, then goal difference, then goals scored."
    )
    rows_html = "".join(
        _third_place_row(position, row)
        for position, (_, row) in enumerate(table.iterrows(), start=1)
    )
    st.markdown(
        '<div class="third-place-shell">'
        '<table class="group-table third-place-table"><thead><tr>'
        "<th>#</th><th>Team</th><th>Grp</th><th>Pld</th><th>W</th><th>D</th><th>L</th>"
        "<th>GF</th><th>GA</th><th>GD</th><th>Pts</th>"
        "</tr></thead>"
        f"<tbody>{rows_html}</tbody></table>"
        '<div class="third-legend"><span class="adv">Top 8 advance</span>'
        '<span class="out">Eliminated</span></div>'
        "</div>",
        unsafe_allow_html=True,
    )


def _third_place_table(groups: pd.DataFrame) -> pd.DataFrame:
    """The third-placed team from each group, ranked across all groups."""
    thirds = []
    for group_name in sorted(groups["group_name"].dropna().unique()):
        subset = _sort_group_subset(groups[groups["group_name"] == group_name].copy())
        if len(subset) < 3:
            continue
        thirds.append(subset.iloc[2])
    if not thirds:
        return pd.DataFrame()
    table = pd.DataFrame(thirds).copy()
    table["_pts"] = table["standing_points"].fillna(0)
    table["_gf"] = table["goals_for"].fillna(0)
    table["_gd"] = table["_gf"] - table["goals_against"].fillna(0)
    table["_rank"] = table["fifa_rank"].fillna(999)
    # Points, then goal difference, then goals scored; FIFA rank and name break
    # any remaining tie so the order stays deterministic before games are played.
    table = table.sort_values(
        ["_pts", "_gd", "_gf", "_rank", "team"],
        ascending=[False, False, False, True, True],
    ).reset_index(drop=True)
    return table.drop(columns=["_pts", "_gf", "_gd", "_rank"])


def _third_place_row(position: int, row) -> str:
    classes = ["third-advance" if position <= 8 else "third-out"]
    if position == 8:
        classes.append("third-cut")
    team = html.escape(display_team_name(row["team"]))
    group = html.escape(str(row["group_name"]))
    played = _standing_int(row, "played")
    wins = _standing_int(row, "wins")
    draws = _standing_int(row, "draws")
    losses = _standing_int(row, "losses")
    goals_for = _standing_int(row, "goals_for")
    goals_against = _standing_int(row, "goals_against")
    goal_difference = goals_for - goals_against
    points = _standing_int(row, "standing_points")
    return (
        f'<tr class="{" ".join(classes)}"><td>{position}</td>'
        f'<td><span class="table-team"><img src="{_flag_url(row)}" alt="">{team}</span></td>'
        f"<td>{group}</td><td>{played}</td><td>{wins}</td><td>{draws}</td><td>{losses}</td>"
        f"<td>{goals_for}</td><td>{goals_against}</td><td>{goal_difference}</td>"
        f"<td><strong>{points}</strong></td></tr>"
    )


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
    live = _fixture_group_standings(hourly_fixture_refresh_key())
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
    team_lookup = {}
    base_order: dict[str, tuple[float, str]] = {}
    for _, row in groups.iterrows():
        ref = (int(row["team_id"]), str(row["group_name"]))
        for key in team_lookup_keys(row["team"]):
            team_lookup[key] = ref
        rank = row.get("fifa_rank")
        base_order[int(row["team_id"])] = (
            999.0 if pd.isna(rank) else float(rank),
            str(row["team"]),
        )

    try:
        fixtures = apply_official_match_reference(cached_matches())
    except Exception:
        return pd.DataFrame()
    if fixtures.empty:
        return pd.DataFrame()

    # Completed matches per group, kept for the head-to-head tiebreaker.
    group_matches: dict[str, list[tuple[int, int, int, int]]] = {}
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
        group_matches.setdefault(home_ref[1], []).append(
            (home_ref[0], away_ref[0], home_score, away_score)
        )

    rows = list(standings.values())
    if not any(row["played"] for row in rows):
        return pd.DataFrame()
    _assign_group_positions(rows, group_matches, base_order)
    return pd.DataFrame(rows)


def _assign_group_positions(
    rows: list[dict],
    group_matches: dict[str, list[tuple[int, int, int, int]]],
    base_order: dict[int, tuple[float, str]],
) -> None:
    """Tag each standings row with its FIFA-ordered position within its group so
    the table, the 1st/2nd/3rd cut, and the 3rd-Place Race all use head-to-head
    the same way the Intralox scoreboard does."""
    by_group: dict[str, list[dict]] = {}
    for row in rows:
        by_group.setdefault(row["group_name"], []).append(row)
    for group_name, group_rows in by_group.items():
        stats = {
            row["team_id"]: {
                "points": row["standing_points"],
                "goal_difference": row["goals_for"] - row["goals_against"],
                "goals_for": row["goals_for"],
            }
            for row in group_rows
        }
        ordered_ids = sorted(stats.keys(), key=lambda tid: base_order.get(tid, (999.0, "")))
        ranking = rank_group(ordered_ids, stats, group_matches.get(group_name, []))
        position = {team_id: index for index, team_id in enumerate(ranking, start=1)}
        for row in group_rows:
            row["group_position"] = position.get(row["team_id"])


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


def _group_details_markup(group_name: str, subset: pd.DataFrame) -> str:
    table_rows = "".join(_table_row(row) for _, row in subset.iterrows())
    group = html.escape(str(group_name))
    avg_rank = _fmt_number(subset["fifa_rank"].mean())
    return (
        '<div class="group-detail-shell">'
        '<table class="group-table"><thead><tr>'
        "<th>Team</th><th>Rank</th><th>W</th><th>D</th><th>L</th><th>GF</th><th>GA</th><th>GD</th><th>Pts</th>"
        "</tr></thead>"
        f"<tbody>{table_rows}</tbody></table>"
        f'<div class="group-detail-stat">Avg Rank {avg_rank}</div>'
        "</div>"
    )


def _group_cards(subset: pd.DataFrame) -> list[dict]:
    return [
        {
            "id": int(row["team_id"]),
            "name": display_team_name(row["team"]),
            "flag_url": _flag_url(row),
        }
        for _, row in subset.iterrows()
    ]


def _open_team(team_id: int) -> None:
    remember_detail_origin("team_return_origin")
    st.session_state["page_name"] = "Teams"
    st.session_state["selected_team_id"] = team_id
    st.session_state.pop("selected_match_id", None)
    st.session_state.pop("selected_fixture_id", None)
    st.session_state.pop("selected_fixture_row", None)
    st.rerun()


def _team_card(row) -> str:
    team = html.escape(display_team_name(row["team"]))
    rank = "TBD" if pd.isna(row["fifa_rank"]) else str(int(row["fifa_rank"]))
    points = "" if pd.isna(row["ranking_points"]) else f"{float(row['ranking_points']):.1f} pts"
    meta = f"FIFA Rank {rank}{' | ' + points if points else ''}"
    return (
        f'<div class="group-team-card"><img src="{_flag_url(row)}" alt="">'
        f'<div><div class="group-team-name">{team}</div>'
        f'<div class="group-team-meta">{html.escape(meta)}</div></div></div>'
    )


def _table_row(row) -> str:
    team = html.escape(display_team_name(row["team"]))
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
    # Prefer the precomputed FIFA position (includes head-to-head) once any games
    # have been played; fall back to a rank-based order before kickoff.
    if "group_position" in sorted_subset.columns and sorted_subset["group_position"].notna().any():
        sorted_subset["_pos_sort"] = sorted_subset["group_position"].fillna(999)
        sorted_subset = sorted_subset.sort_values(["_pos_sort", "team"])
        return sorted_subset.drop(columns=["_pos_sort"])
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
            display: block;
            object-fit: cover;
            object-position: center;
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
            border-top: 0;
            border-radius: 0 0 8px 8px;
            background: rgba(5,5,5,.38);
            padding: 1rem;
            margin: -.35rem 0 1.25rem;
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
            display: block;
            object-fit: cover;
            object-position: center;
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
        .third-place-shell {
            border: 1px solid rgba(214,168,58,.24);
            border-radius: 8px;
            background: rgba(5,5,5,.38);
            padding: 1rem;
            margin: .75rem 0 1.25rem;
        }
        .third-place-table td:nth-child(2) {
            text-align: left;
        }
        .third-place-table tr.third-advance td {
            background: rgba(36,140,72,.18);
        }
        .third-place-table tr.third-out td {
            background: rgba(255,255,255,.03);
            color: #cbd5e1;
        }
        .third-place-table tr.third-cut td {
            border-bottom: 3px solid #D6A83A;
        }
        .third-legend {
            display: flex;
            gap: 1.25rem;
            margin-top: .75rem;
            font-size: .8rem;
            font-weight: 800;
        }
        .third-legend .adv::before,
        .third-legend .out::before {
            content: "";
            display: inline-block;
            width: .72rem;
            height: .72rem;
            border-radius: 3px;
            margin-right: .4rem;
            vertical-align: -1px;
        }
        .third-legend .adv {
            color: #7CE6A6;
        }
        .third-legend .adv::before {
            background: rgba(36,140,72,.6);
        }
        .third-legend .out {
            color: #94a3b8;
        }
        .third-legend .out::before {
            background: rgba(255,255,255,.14);
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
