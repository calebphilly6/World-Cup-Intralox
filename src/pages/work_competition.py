from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from src.config import is_shared_core_read_only_mode
from src.database import fetch_df, get_connection
from src.football_data_service import hourly_fixture_refresh_key
from src.intralox_results import derive_intralox_results
from src.odds_service import latest_tournament_winner_odds_lookup, odds_source_text
from src.official_match_reference import normalize_team_key
from src.pages.fixtures import _fixture_data
from src.pages.rankings import FLAG_CODES
from src.utils.team_names import display_team_name, team_link_attr
from src.world_cup_scoring import (
    POT_MULTIPLIERS,
    TeamScore,
    calculate_owner_leaderboard,
    daily_score_refresh_key,
    validate_assignments,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOCKED_ASSIGNMENTS_PATH = PROJECT_ROOT / "data" / "intralox_assignments_locked.csv"


def render() -> None:
    st.title("Intralox")
    _styles()
    if not is_shared_core_read_only_mode():
        _ensure_results_for_world_cup_teams()

    assignments = _assignment_rows()
    _todays_games_line(assignments, hourly_fixture_refresh_key())
    scores, leaderboard = _daily_competition_state(daily_score_refresh_key(), hourly_fixture_refresh_key())

    validation_errors = validate_assignments(assignments.to_dict("records")) if not assignments.empty else ["Exactly 12 competitors are required."]
    if validation_errors:
        with st.expander("Setup validation", expanded=True):
            for error in validation_errors:
                st.warning(error)

    odds_lookup = latest_tournament_winner_odds_lookup()
    _leaderboard(leaderboard)
    _owned_team_breakdowns(scores, odds_lookup)
    _championship_odds_scoreboard(scores, odds_lookup)


@st.cache_data(show_spinner=False)
def _daily_competition_state(score_refresh_key: str, fixture_refresh_key: str) -> tuple[list[TeamScore], list[dict]]:
    # ``fixture_refresh_key`` busts this cache whenever the Fixtures feed refreshes,
    # so the scoreboard tracks the same results the Fixtures tab shows.
    assignments = _assignment_rows()
    derived = _derived_team_results(fixture_refresh_key)
    scores = _team_scores(assignments, derived)
    leaderboard = calculate_owner_leaderboard(scores, _previous_ranks())
    _save_snapshot(leaderboard, score_refresh_key)
    return scores, leaderboard


def _derived_team_results(fixture_refresh_key: str) -> dict[str, dict]:
    """Compute each team's results from the live fixtures, keyed by team-name key."""
    try:
        fixtures, _warning = _fixture_data(fixture_refresh_key)
    except Exception:
        return {}
    return derive_intralox_results(fixtures)


def _todays_games_line(assignments: pd.DataFrame, fixture_refresh_key: str) -> None:
    """Show today's World Cup games and which competitor owns each team."""
    try:
        fixtures, _warning = _fixture_data(fixture_refresh_key)
    except Exception:
        return

    games = _todays_games(fixtures)
    owners = _team_owner_lookup(assignments)
    if not games:
        st.markdown(
            '<section class="intralox-today empty">'
            '<span class="intralox-today-head">Today\'s Games</span>'
            '<span class="intralox-today-none">No World Cup games today.</span>'
            '</section>',
            unsafe_allow_html=True,
        )
        return

    rows = "".join(_todays_game_markup(game, owners) for game in games)
    st.markdown(
        '<section class="intralox-today">'
        '<span class="intralox-today-head">Today\'s Games</span>'
        f'<div class="intralox-today-list">{rows}</div>'
        '</section>',
        unsafe_allow_html=True,
    )


def _todays_games(fixtures: pd.DataFrame) -> list[dict]:
    if fixtures is None or fixtures.empty or "local_date" not in fixtures:
        return []
    today = datetime.now(ZoneInfo("America/Chicago")).date().isoformat()
    todays = fixtures[fixtures["local_date"].astype(str) == today].copy()
    if todays.empty:
        return []
    todays = todays.sort_values("utc_date")
    games = []
    for _, row in todays.iterrows():
        games.append(
            {
                "home": str(row.get("home_team") or "TBD"),
                "away": str(row.get("away_team") or "TBD"),
                "time": _short_kickoff(row.get("local_time")),
            }
        )
    return games


def _short_kickoff(local_time) -> str:
    text = str(local_time or "").strip()
    if not text:
        return ""
    return text.lstrip("0")


def _team_owner_lookup(assignments: pd.DataFrame) -> dict[str, str]:
    if assignments is None or assignments.empty:
        return {}
    owners: dict[str, str] = {}
    for _, row in assignments.iterrows():
        team = str(row.get("team") or "").strip()
        person = str(row.get("person_name") or "").strip()
        if team and person:
            owners[normalize_team_key(team)] = person
    return owners


def _todays_game_markup(game: dict, owners: dict[str, str]) -> str:
    time_markup = f'<span class="intralox-today-time">{html.escape(game["time"])}</span>' if game["time"] else ""
    return (
        '<div class="intralox-today-game">'
        f'{time_markup}'
        f'{_todays_team_markup(game["home"], owners)}'
        '<span class="intralox-today-vs">v</span>'
        f'{_todays_team_markup(game["away"], owners)}'
        '</div>'
    )


def _todays_team_markup(team: str, owners: dict[str, str]) -> str:
    owner = owners.get(normalize_team_key(team), "")
    owner_markup = f'<em>{html.escape(owner)}</em>' if owner else ""
    return (
        f'<span class="intralox-today-team"{team_link_attr(team)}>'
        f'<strong>{html.escape(display_team_name(team))}</strong>{owner_markup}'
        '</span>'
    )


def _assignment_rows() -> pd.DataFrame:
    if LOCKED_ASSIGNMENTS_PATH.exists():
        return pd.read_csv(LOCKED_ASSIGNMENTS_PATH)
    return fetch_df(
        """
        SELECT e.person_name, t.name AS team, e.pot
        FROM intralox_competition_entries e
        JOIN teams t ON t.id = e.team_id
        ORDER BY e.person_name, e.pot, t.name
        """
    )


def _result_rows() -> pd.DataFrame:
    return fetch_df(
        """
        SELECT t.name AS team, r.group_wins, r.group_draws, r.group_finish, r.advanced,
               r.won_round_of_32, r.won_round_of_16, r.won_quarterfinal,
               r.won_semifinal, r.won_final, r.eliminated
        FROM intralox_competition_results r
        JOIN teams t ON t.id = r.team_id
        ORDER BY t.name
        """
    )


def _team_scores(assignments: pd.DataFrame, derived: dict[str, dict]) -> list[TeamScore]:
    if assignments.empty:
        return []
    scores: list[TeamScore] = []
    for _, row in assignments.iterrows():
        team = str(row["team"])
        data = derived.get(normalize_team_key(team), {})
        finish = data.get("group_finish")
        scores.append(
            TeamScore(
                team=team,
                owner=str(row["person_name"]),
                pot=int(row["pot"]),
                group_wins=int(data.get("group_wins", 0) or 0),
                group_draws=int(data.get("group_draws", 0) or 0),
                group_finish=None if finish is None else int(finish),
                advanced=bool(data.get("advanced", False)),
                won_round_of_32=bool(data.get("won_round_of_32", False)),
                won_round_of_16=bool(data.get("won_round_of_16", False)),
                won_quarterfinal=bool(data.get("won_quarterfinal", False)),
                won_semifinal=bool(data.get("won_semifinal", False)),
                won_final=bool(data.get("won_final", False)),
                eliminated=bool(data.get("eliminated", False)),
            )
        )
    return scores


def _previous_ranks() -> dict[str, int]:
    rows = fetch_df(
        """
        SELECT person_name, rank
        FROM intralox_competition_snapshots
        WHERE created_at = (
            SELECT MAX(created_at) FROM intralox_competition_snapshots
        )
        """
    )
    if rows.empty:
        return {}
    return {str(row["person_name"]): int(row["rank"]) for _, row in rows.iterrows()}


def _save_snapshot(leaderboard: list[dict], snapshot_key: str) -> None:
    if not leaderboard or is_shared_core_read_only_mode():
        return
    with get_connection() as conn:
        for row in leaderboard:
            conn.execute(
                """
                INSERT INTO intralox_competition_snapshots (snapshot_key, person_name, rank, total_score)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(snapshot_key, person_name) DO UPDATE SET
                    rank = excluded.rank,
                    total_score = excluded.total_score,
                    created_at = CURRENT_TIMESTAMP
                """,
                (snapshot_key, row["person"], row["rank"], row["total_score"]),
            )
        conn.commit()


def _leaderboard(leaderboard: list[dict]) -> None:
    if not leaderboard:
        st.info("Add 12 competitors and 48 assigned teams to build the leaderboard.")
        return
    cards = "".join(_leaderboard_card(row) for row in leaderboard)
    st.markdown(f'<section class="intralox-board">{cards}</section>', unsafe_allow_html=True)


def _leaderboard_card(row: dict) -> str:
    leader_class = " leader" if row["rank"] == 1 else ""
    pot_cells = "".join(_pot_cell(row["pot_scores"].get(pot), pot) for pot in (1, 2, 3, 4))
    return (
        f'<article class="intralox-card{leader_class}">'
        f'<div class="intralox-rank">#{row["rank"]}</div>'
        '<div class="intralox-main">'
        '<div class="intralox-title-row">'
        f'<div class="intralox-name">{html.escape(row["person"])}</div>'
        f'<div class="intralox-score">{row["total_score"]:.1f}</div>'
        '</div>'
        f'<div class="intralox-pots">{pot_cells}</div>'
        '</div>'
        f'<div class="intralox-total"><small>{row["teams_left"]} alive</small></div>'
        '</article>'
    )


def _pot_cell(score: TeamScore | None, pot: int) -> str:
    if score is None:
        return f'<div class="intralox-pot"><small>Pot {pot}</small><strong>Unassigned</strong><span>0.0</span></div>'
    flag = _flag_img(score.team, "intralox-pot-flag")
    return (
        f'<div class="intralox-pot"><small>Pot {pot}</small>'
        f'<div class="intralox-pot-team"{team_link_attr(score.team)}>{flag}<strong>{html.escape(display_team_name(score.team))}</strong></div>'
        f'<span>{score.adjusted_score:.1f}</span></div>'
    )


def _owned_team_breakdowns(scores: list[TeamScore], odds_lookup: dict[str, dict]) -> None:
    if not scores:
        return
    st.markdown('<div class="intralox-section-title">Team scoring breakdown</div>', unsafe_allow_html=True)
    for owner in sorted({score.owner for score in scores}):
        owner_scores = [score for score in scores if score.owner == owner]
        total = sum(score.adjusted_score for score in owner_scores)
        champion_odds = _owner_champion_odds(owner_scores, odds_lookup)
        with st.expander(f"{owner} - {total:.1f} points | Odds of Champion: {_percent_text(champion_odds)}", expanded=False):
            st.markdown(
                f'<div class="team-score-grid">{"".join(_score_breakdown_card(score) for score in owner_scores)}</div>',
                unsafe_allow_html=True,
            )
            st.markdown(_owner_odds_panel(owner, owner_scores, odds_lookup, champion_odds), unsafe_allow_html=True)


def _score_breakdown_card(score: TeamScore) -> str:
    knockout = score.knockout_points
    flag = _flag_img(score.team, "team-score-flag")
    return (
        '<article class="team-score-card">'
        f'<div class="team-score-head"><div{team_link_attr(score.team)}>{flag}<span>{html.escape(display_team_name(score.team))}</span></div><small>Pot {score.pot} x{score.multiplier:.2f}</small></div>'
        '<div class="score-lines">'
        f'<div><span>Group wins</span><strong>{score.group_wins} x 3 = {score.group_wins * 3}</strong></div>'
        f'<div><span>Group draws</span><strong>{score.group_draws} x 1 = {score.group_draws}</strong></div>'
        f'<div><span>Finish bonus</span><strong>{score.group_finish_bonus}</strong></div>'
        f'<div><span>Qualified (R32)</span><strong>{score.qualify_bonus}</strong></div>'
        f'<div><span>Win Round of 32</span><strong>{knockout["won_round_of_32"]}</strong></div>'
        f'<div><span>Win Round of 16</span><strong>{knockout["won_round_of_16"]}</strong></div>'
        f'<div><span>Win Quarterfinal</span><strong>{knockout["won_quarterfinal"]}</strong></div>'
        f'<div><span>Win Semifinal</span><strong>{knockout["won_semifinal"]}</strong></div>'
        f'<div><span>Win Final</span><strong>{knockout["won_final"]}</strong></div>'
        '</div>'
        f'<div class="score-total"><span>Base {score.base_score}</span><strong>{score.adjusted_score:.1f}</strong></div>'
        '</article>'
    )


def _owner_champion_odds(scores: list[TeamScore], odds_lookup: dict[str, dict]) -> float:
    return sum(float(odds_lookup.get(score.team, {}).get("implied_probability") or 0.0) for score in scores)


def _owner_odds_panel(owner: str, scores: list[TeamScore], odds_lookup: dict[str, dict], total_probability: float) -> str:
    rows = "".join(_owner_odds_team(score, odds_lookup.get(score.team, {})) for score in scores)
    return (
        '<section class="owner-odds-panel">'
        '<div class="owner-odds-head">'
        f'<div><span>Champion Odds</span><strong>{html.escape(owner)}</strong></div>'
        f'<em>{_percent_text(total_probability)}</em>'
        '</div>'
        f'<div class="owner-odds-grid">{rows}</div>'
        '</section>'
    )


def _owner_odds_team(score: TeamScore, odds: dict) -> str:
    probability = float(odds.get("implied_probability") or 0.0)
    odds_text = _odds_source_text(odds)
    flag = _flag_img(score.team, "owner-odds-flag")
    missing_class = " missing" if not odds else ""
    return (
        f'<article class="owner-odds-team{missing_class}"{team_link_attr(score.team)}>'
        f'<div>{flag}<strong>{html.escape(display_team_name(score.team))}</strong></div>'
        f'<span>{_percent_text(probability)}</span>'
        f'<small>{html.escape(odds_text)}</small>'
        '</article>'
    )


def _championship_odds_scoreboard(scores: list[TeamScore], odds_lookup: dict[str, dict]) -> None:
    if not scores:
        return
    owners = []
    for owner in sorted({score.owner for score in scores}):
        owner_scores = [score for score in scores if score.owner == owner]
        owners.append((owner, owner_scores, _owner_champion_odds(owner_scores, odds_lookup)))
    rows = sorted(owners, key=lambda row: row[2], reverse=True)
    st.markdown('<div class="intralox-section-title">Championship odds board</div>', unsafe_allow_html=True)
    board = "".join(_championship_odds_row(rank, owner, owner_scores, probability) for rank, (owner, owner_scores, probability) in enumerate(rows, start=1))
    st.markdown(f'<section class="championship-odds-board">{board}</section>', unsafe_allow_html=True)


def _championship_odds_row(rank: int, owner: str, scores: list[TeamScore], probability: float) -> str:
    return (
        '<article class="championship-odds-row">'
        f'<span class="championship-odds-rank">#{rank}</span>'
        '<div class="championship-odds-team">'
        f'<div><strong>{html.escape(owner)}</strong></div></div>'
        f'<span class="championship-odds-percent">{_percent_text(probability)}</span>'
        f'<span class="championship-odds-price">{len(scores)} teams</span>'
        '</article>'
    )


def _percent_text(value: float) -> str:
    return f"{float(value):.2%}"


def _odds_source_text(odds: dict) -> str:
    if not odds:
        return "No odds"
    return odds_source_text(odds.get("american_odds"), odds.get("source"))


def _flag_img(team: str, class_name: str) -> str:
    code = _team_flag_lookup().get(team) or FLAG_CODES.get(team) or ""
    initials = "".join(part[0] for part in str(team).replace("-", " ").split()[:2]).upper() or "?"
    if not code:
        return f'<div class="{class_name} flag-fallback">{html.escape(initials)}</div>'
    return (
        f'<img class="{class_name}" src="https://flagcdn.com/w80/{html.escape(str(code).lower())}.png" alt="{html.escape(team)} flag" '
        f'onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'grid\';">'
        f'<div class="{class_name} flag-fallback hidden">{html.escape(initials)}</div>'
    )


@st.cache_data(show_spinner=False)
def _team_flag_lookup() -> dict[str, str]:
    rows = fetch_df("SELECT name, country_code FROM teams")
    flags: dict[str, str] = {}
    for _, row in rows.iterrows():
        code = "" if pd.isna(row.get("country_code")) else str(row.get("country_code")).strip().lower()
        if code:
            flags[str(row["name"])] = code
    flags["England"] = "gb-eng"
    flags["Scotland"] = "gb-sct"
    return flags


def _data_entry(assignments: pd.DataFrame, results: pd.DataFrame) -> None:
    with st.expander("Edit competition data", expanded=False):
        if is_shared_core_read_only_mode():
            st.info("Shared mode protects official and competition data. Competition data editing is disabled.")
            return
        if LOCKED_ASSIGNMENTS_PATH.exists():
            st.caption("Assignments are locked in data/intralox_assignments_locked.csv and are not editable in the app.")
        else:
            st.caption("Edit assignments and results here, or use the CSV templates in the data folder.")
        teams = fetch_df("SELECT name FROM teams ORDER BY name")["name"].tolist()
        if LOCKED_ASSIGNMENTS_PATH.exists():
            st.markdown('<div class="intralox-editor-title">Locked assignments</div>', unsafe_allow_html=True)
            st.dataframe(assignments, width="stretch", hide_index=True)
        else:
            assignment_template = assignments.copy()
            if assignment_template.empty:
                assignment_template = pd.DataFrame(
                    [{"person_name": "", "team": "", "pot": pot} for _ in range(12) for pot in (1, 2, 3, 4)]
                )
            edited_assignments = st.data_editor(
                assignment_template,
                width="stretch",
                hide_index=True,
                num_rows="dynamic",
                column_config={
                    "person_name": st.column_config.TextColumn("Person"),
                    "team": st.column_config.SelectboxColumn("Team", options=teams),
                    "pot": st.column_config.SelectboxColumn("Pot", options=[1, 2, 3, 4]),
                },
                key="intralox_assignment_editor",
            )
            if st.button("Save assignments", key="save_intralox_assignments"):
                errors = validate_assignments(edited_assignments.to_dict("records"))
                if errors:
                    for error in errors:
                        st.error(error)
                else:
                    _save_assignments(edited_assignments)
                    st.success("Assignments saved. Standings will update after the next 4:00 AM refresh.")
                    st.rerun()

        result_template = results.copy()
        if result_template.empty:
            result_template = pd.DataFrame(
                {
                    "team": teams,
                    "group_wins": 0,
                    "group_draws": 0,
                    "group_finish": None,
                    "advanced": False,
                    "won_round_of_32": False,
                    "won_round_of_16": False,
                    "won_quarterfinal": False,
                    "won_semifinal": False,
                    "won_final": False,
                    "eliminated": False,
                }
            )
        st.markdown('<div class="intralox-editor-title">Results</div>', unsafe_allow_html=True)
        edited_results = st.data_editor(
            result_template,
            width="stretch",
            hide_index=True,
            num_rows="fixed",
            column_config={
                "team": st.column_config.SelectboxColumn("Team", options=teams),
                "group_wins": st.column_config.NumberColumn("Group Wins", min_value=0, max_value=3, step=1),
                "group_draws": st.column_config.NumberColumn("Group Draws", min_value=0, max_value=3, step=1),
                "group_finish": st.column_config.NumberColumn("Group Finish", min_value=1, max_value=4, step=1),
            },
            key="intralox_results_editor",
        )
        if st.button("Save results", key="save_intralox_results"):
            _save_results(edited_results)
            st.success("Results saved. Standings will update after the next 4:00 AM refresh.")
            st.rerun()


def _save_assignments(assignments: pd.DataFrame) -> None:
    if is_shared_core_read_only_mode():
        return
    clean = assignments.dropna(subset=["person_name", "team", "pot"]).copy()
    clean["person_name"] = clean["person_name"].astype(str).str.strip()
    clean["team"] = clean["team"].astype(str).str.strip()
    clean = clean[(clean["person_name"] != "") & (clean["team"] != "")]
    with get_connection() as conn:
        conn.execute("DELETE FROM intralox_competition_entries")
        for _, row in clean.iterrows():
            team = conn.execute("SELECT id FROM teams WHERE name = ?", (row["team"],)).fetchone()
            if team:
                conn.execute(
                    """
                    INSERT INTO intralox_competition_entries (person_name, team_id, pot)
                    VALUES (?, ?, ?)
                    """,
                    (row["person_name"], team["id"], int(row["pot"])),
                )
        conn.commit()


def _save_results(results: pd.DataFrame) -> None:
    if is_shared_core_read_only_mode():
        return
    with get_connection() as conn:
        for _, row in results.iterrows():
            team_name = str(row.get("team") or "").strip()
            if not team_name:
                continue
            team = conn.execute("SELECT id FROM teams WHERE name = ?", (team_name,)).fetchone()
            if not team:
                continue
            conn.execute(
                """
                INSERT INTO intralox_competition_results (
                    team_id, group_wins, group_draws, group_finish, advanced,
                    won_round_of_32, won_round_of_16, won_quarterfinal,
                    won_semifinal, won_final, eliminated, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(team_id) DO UPDATE SET
                    group_wins = excluded.group_wins,
                    group_draws = excluded.group_draws,
                    group_finish = excluded.group_finish,
                    advanced = excluded.advanced,
                    won_round_of_32 = excluded.won_round_of_32,
                    won_round_of_16 = excluded.won_round_of_16,
                    won_quarterfinal = excluded.won_quarterfinal,
                    won_semifinal = excluded.won_semifinal,
                    won_final = excluded.won_final,
                    eliminated = excluded.eliminated,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    team["id"],
                    _safe_int(row.get("group_wins")),
                    _safe_int(row.get("group_draws")),
                    None if pd.isna(row.get("group_finish")) else _safe_int(row.get("group_finish")),
                    _safe_bool(row.get("advanced")),
                    _safe_bool(row.get("won_round_of_32")),
                    _safe_bool(row.get("won_round_of_16")),
                    _safe_bool(row.get("won_quarterfinal")),
                    _safe_bool(row.get("won_semifinal")),
                    _safe_bool(row.get("won_final")),
                    _safe_bool(row.get("eliminated")),
                ),
            )
        conn.commit()


def _ensure_results_for_world_cup_teams() -> None:
    if is_shared_core_read_only_mode():
        return
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO intralox_competition_results (team_id)
            SELECT id FROM teams
            """
        )
        conn.commit()


def _safe_int(value) -> int:
    if pd.isna(value):
        return 0
    return max(0, int(value))


def _safe_bool(value) -> int:
    if pd.isna(value):
        return 0
    if isinstance(value, str):
        return 1 if value.strip().lower() in {"1", "true", "yes", "y"} else 0
    return 1 if bool(value) else 0


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
        .intralox-today {
            border: 1px solid rgba(214,168,58,.24);
            border-radius: 8px;
            background: rgba(5,5,5,.34);
            display: flex;
            flex-direction: column;
            gap: .4rem;
            margin: .2rem 0 1rem;
            padding: .6rem .8rem;
        }
        .intralox-today.empty {
            flex-direction: row;
            flex-wrap: wrap;
            align-items: baseline;
            gap: .45rem .9rem;
        }
        .intralox-today-head {
            color: #D6A83A;
            font-size: .72rem;
            font-weight: 950;
            letter-spacing: .04em;
            text-transform: uppercase;
            white-space: nowrap;
        }
        .intralox-today-none {
            color: #CBD5E1;
            font-weight: 800;
        }
        .intralox-today-list {
            display: flex;
            flex-direction: column;
            gap: .3rem;
        }
        .intralox-today-game {
            align-items: baseline;
            border-top: 1px solid rgba(255,255,255,.08);
            display: flex;
            flex-wrap: wrap;
            gap: .3rem .45rem;
            padding-top: .3rem;
        }
        .intralox-today-game:first-child {
            border-top: 0;
            padding-top: 0;
        }
        .intralox-today-time {
            color: #23D7D7;
            font-size: .72rem;
            font-weight: 900;
            white-space: nowrap;
        }
        .intralox-today-team {
            color: #FFFFFF;
            white-space: nowrap;
        }
        .intralox-today-team strong {
            color: #FFFFFF;
            font-weight: 900;
        }
        .intralox-today-team em {
            color: #D6A83A;
            font-style: normal;
            font-weight: 850;
            margin-left: .3rem;
        }
        .intralox-today-team em::before {
            content: "(";
        }
        .intralox-today-team em::after {
            content: ")";
        }
        .intralox-today-vs {
            color: #94A3B8;
            font-size: .78rem;
            font-weight: 800;
        }
        .intralox-board {
            display: grid;
            grid-template-columns: 1fr;
            gap: .7rem;
            margin: .7rem 0 1.1rem;
        }
        .intralox-card {
            align-items: center;
            border: 1px solid rgba(214,168,58,.24);
            border-radius: 8px;
            background:
                linear-gradient(135deg, rgba(5,5,5,.62), rgba(11,16,32,.56)),
                radial-gradient(circle at 98% 10%, rgba(36,88,255,.16), transparent 32%);
            display: grid;
            grid-template-columns: 74px 1fr 76px;
            gap: .65rem;
            padding: .8rem;
            box-shadow: 0 14px 32px rgba(0,0,0,.18);
        }
        .intralox-card.leader {
            border-color: rgba(214,168,58,.72);
            background:
                linear-gradient(135deg, rgba(5,5,5,.70), rgba(11,16,32,.60)),
                radial-gradient(circle at 98% 10%, rgba(214,168,58,.24), transparent 34%);
        }
        .intralox-rank, .intralox-total span {
            color: #D6A83A;
            font-size: 1.8rem;
            font-weight: 950;
            text-align: center;
        }
        .intralox-name {
            color: #FFFFFF;
            font-size: 1.25rem;
            font-weight: 950;
        }
        .intralox-title-row {
            align-items: flex-start;
            display: flex;
            justify-content: space-between;
            gap: 1rem;
        }
        .intralox-score {
            color: #D6A83A;
            font-size: 2.45rem;
            font-weight: 950;
            line-height: .82;
            margin-top: .18rem;
            text-shadow: 0 6px 20px rgba(0,0,0,.32);
        }
        .intralox-move, .intralox-total small {
            color: #CBD5E1;
            font-size: .78rem;
            font-weight: 850;
            text-transform: uppercase;
        }
        .intralox-pots {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: .45rem;
            margin-top: .55rem;
        }
        .intralox-pot {
            border: 1px solid rgba(255,255,255,.12);
            border-radius: 8px;
            background: rgba(255,255,255,.07);
            padding: .5rem;
        }
        .intralox-pot small {
            color: #D6A83A;
            display: block;
            font-weight: 900;
            text-transform: uppercase;
        }
        .intralox-pot strong {
            color: #FFFFFF;
            display: block;
            font-size: .86rem;
            line-height: 1.05;
        }
        .intralox-pot-team {
            align-items: center;
            display: flex;
            gap: .45rem;
            min-height: 2.15rem;
        }
        .intralox-pot-flag, .team-score-flag {
            aspect-ratio: 3 / 2;
            border: 1px solid rgba(255,255,255,.52);
            border-radius: 5px;
            box-shadow: 0 7px 15px rgba(0,0,0,.30);
            display: block;
            object-fit: cover;
            object-position: center;
        }
        .intralox-pot-flag {
            width: 34px;
            flex: 0 0 34px;
        }
        .team-score-flag {
            width: 48px;
            flex: 0 0 48px;
        }
        .flag-fallback {
            align-items: center;
            background: linear-gradient(135deg, rgba(214,168,58,.35), rgba(36,88,255,.22));
            color: #FFFFFF;
            display: grid;
            font-size: .7rem;
            font-weight: 950;
            justify-content: center;
        }
        .flag-fallback.hidden {
            display: none;
        }
        .intralox-pot span {
            color: #23D7D7;
            font-weight: 950;
        }
        .intralox-total {
            justify-self: start;
            text-align: left;
        }
        .intralox-section-title, .intralox-editor-title {
            border-bottom: 1px solid rgba(214,168,58,.24);
            color: #D6A83A;
            font-size: .82rem;
            font-weight: 950;
            margin: 1.1rem 0 .7rem;
            padding-bottom: .5rem;
            text-transform: uppercase;
        }
        .team-score-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: .7rem;
        }
        .team-score-card {
            border: 1px solid rgba(214,168,58,.22);
            border-radius: 8px;
            background: rgba(5,5,5,.34);
            padding: .8rem;
        }
        .team-score-head {
            align-items: center;
            display: flex;
            justify-content: space-between;
            gap: .7rem;
            margin-bottom: .65rem;
        }
        .team-score-head > div {
            align-items: center;
            display: flex;
            gap: .6rem;
        }
        .team-score-head span, .score-total strong {
            color: #FFFFFF;
            font-weight: 950;
        }
        .team-score-head small, .score-total span {
            color: #D6A83A;
            font-weight: 900;
        }
        .score-lines div, .score-total {
            display: flex;
            justify-content: space-between;
            border-top: 1px solid rgba(255,255,255,.08);
            padding: .35rem 0;
        }
        .score-lines span {
            color: #CBD5E1;
            font-weight: 750;
        }
        .score-lines strong {
            color: #FFFFFF;
        }
        .owner-odds-panel {
            border: 1px solid rgba(214,168,58,.24);
            border-radius: 8px;
            background:
                linear-gradient(135deg, rgba(5,5,5,.42), rgba(11,16,32,.38)),
                radial-gradient(circle at 98% 0%, rgba(157,255,0,.11), transparent 30%);
            margin-top: .8rem;
            padding: .85rem;
        }
        .owner-odds-head {
            align-items: flex-end;
            border-bottom: 1px solid rgba(214,168,58,.18);
            display: flex;
            justify-content: space-between;
            gap: 1rem;
            margin-bottom: .7rem;
            padding-bottom: .65rem;
        }
        .owner-odds-head span {
            color: #D6A83A;
            display: block;
            font-size: .72rem;
            font-weight: 950;
            text-transform: uppercase;
        }
        .owner-odds-head strong {
            color: #FFFFFF;
            display: block;
            font-size: 1.15rem;
            font-weight: 950;
            line-height: 1;
            margin-top: .15rem;
        }
        .owner-odds-head em {
            color: #9DFF00;
            font-size: 1.65rem;
            font-style: normal;
            font-weight: 950;
            line-height: 1;
            text-shadow: 0 0 18px rgba(157,255,0,.20);
        }
        .owner-odds-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: .55rem;
        }
        .owner-odds-team {
            border: 1px solid rgba(255,255,255,.12);
            border-radius: 8px;
            background: rgba(255,255,255,.055);
            padding: .55rem;
        }
        .owner-odds-team.missing {
            opacity: .72;
        }
        .owner-odds-team > div {
            align-items: center;
            display: flex;
            gap: .45rem;
            min-height: 28px;
        }
        .owner-odds-team strong {
            color: #FFFFFF;
            font-size: .82rem;
            font-weight: 950;
            line-height: 1.05;
        }
        .owner-odds-team span {
            color: #9DFF00;
            display: block;
            font-size: 1.2rem;
            font-weight: 950;
            margin-top: .45rem;
        }
        .owner-odds-team small {
            color: #CBD5E1;
            font-weight: 850;
        }
        .owner-odds-flag {
            aspect-ratio: 3 / 2;
            border: 1px solid rgba(255,255,255,.46);
            border-radius: 4px;
            display: block;
            flex: 0 0 34px;
            object-fit: cover;
            object-position: center;
            width: 34px;
        }
        .championship-odds-board {
            border: 1px solid rgba(214,168,58,.22);
            border-radius: 8px;
            background:
                linear-gradient(135deg, rgba(5,5,5,.48), rgba(11,16,32,.48)),
                radial-gradient(circle at 100% 0%, rgba(36,88,255,.16), transparent 32%);
            display: grid;
            gap: .36rem;
            margin: .6rem 0 .2rem;
            padding: .65rem;
        }
        .championship-odds-row {
            align-items: center;
            border: 1px solid rgba(255,255,255,.10);
            border-radius: 8px;
            background: rgba(255,255,255,.055);
            display: grid;
            grid-template-columns: 54px minmax(0, 1fr) 92px 76px;
            gap: .65rem;
            min-height: 58px;
            padding: .48rem .6rem;
        }
        .championship-odds-row.missing {
            opacity: .66;
        }
        .championship-odds-rank {
            color: #D6A83A;
            font-size: 1rem;
            font-weight: 950;
            text-align: center;
        }
        .championship-odds-team {
            align-items: center;
            display: flex;
            gap: .55rem;
            min-width: 0;
        }
        .championship-odds-team strong {
            color: #FFFFFF;
            display: block;
            font-size: .98rem;
            font-weight: 950;
            line-height: 1.05;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .championship-odds-team small {
            color: #CBD5E1;
            display: block;
            font-size: .72rem;
            font-weight: 850;
            margin-top: .12rem;
            overflow: hidden;
            text-overflow: ellipsis;
            text-transform: uppercase;
            white-space: nowrap;
        }
        .championship-odds-flag {
            aspect-ratio: 3 / 2;
            border: 1px solid rgba(255,255,255,.48);
            border-radius: 4px;
            box-shadow: 0 7px 16px rgba(0,0,0,.28);
            display: block;
            flex: 0 0 38px;
            object-fit: cover;
            object-position: center;
            width: 38px;
        }
        .championship-odds-percent {
            color: #9DFF00;
            font-size: 1.08rem;
            font-weight: 950;
            text-align: right;
        }
        .championship-odds-price {
            color: #D6A83A;
            font-size: .88rem;
            font-weight: 900;
            text-align: right;
        }
        @media (max-width: 980px) {
            .intralox-card {
                grid-template-columns: 58px 1fr;
            }
            .intralox-total {
                grid-column: 1 / -1;
                text-align: left;
            }
            .intralox-pots, .team-score-grid, .owner-odds-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
            .championship-odds-row {
                grid-template-columns: 42px minmax(0, 1fr) 72px;
            }
            .championship-odds-price {
                display: none;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
