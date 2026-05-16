from __future__ import annotations

from datetime import datetime, timezone
import html
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from src.database import fetch_df
from src.city_backgrounds import city_background_card_data_uri
from src.config import is_shared_core_read_only_mode
from src.fixture_display import enrich_fixture_participants
from src.football_data_service import cached_matches
from src.official_match_reference import apply_official_match_reference, normalize_team_key
from src.pages.rankings import FLAG_CODES
from src.storage.storage import load_favorite_teams
from src.utils.formatting import format_local_time
from src.world_cup_scoring import daily_score_refresh_key
from src.pages.work_competition import _daily_competition_state, _ensure_results_for_world_cup_teams


def render() -> None:
    st.title("Home")
    _styles()

    matches, header = _dashboard_matches()
    st.markdown(f'<div class="home-section-title">{html.escape(header)}</div>', unsafe_allow_html=True)
    if matches.empty:
        st.info("No fixtures imported yet.")
    else:
        _render_match_strip(matches)

    previous_matches, previous_header = _previous_dashboard_matches()
    st.markdown(f'<div class="home-section-title">{html.escape(previous_header)}</div>', unsafe_allow_html=True)
    if not previous_matches.empty:
        _render_match_strip(previous_matches)

    st.markdown('<div class="home-section-title">Favorite Teams</div>', unsafe_allow_html=True)
    favorites = _favorite_teams()
    if favorites.empty:
        st.info("Mark teams as favorites in the Teams tab.")
    else:
        _render_favorites(favorites)

    if not is_shared_core_read_only_mode():
        _ensure_results_for_world_cup_teams()
    _, intralox = _daily_competition_state(daily_score_refresh_key())
    _render_intralox_snapshot(intralox)


def _render_intralox_snapshot(leaderboard: list[dict]) -> None:
    st.markdown('<div class="home-section-title intralox-home-title">Intralox Scoreboard</div>', unsafe_allow_html=True)
    if not leaderboard:
        st.info("Intralox assignments are not ready yet.")
        return
    rows = "".join(
        '<div class="home-score-row">'
        f'<span>#{row["rank"]}</span><strong>{html.escape(row["person"])}</strong><em>{row["total_score"]:.1f}</em></div>'
        for row in leaderboard
    )
    st.markdown(f'<section class="home-scoreboard">{rows}</section>', unsafe_allow_html=True)


def _render_match_strip(matches: pd.DataFrame) -> None:
    for start in range(0, len(matches), 3):
        columns = st.columns(3)
        for column, (_, row) in zip(columns, matches.iloc[start:start + 3].iterrows()):
            with column:
                st.markdown(_home_fixture_card(row), unsafe_allow_html=True)
                if st.button("Open match", key=f"home_fixture_open_{_safe_key(_match_number_label(row.get('#')))}", use_container_width=True):
                    _open_fixture_from_home(row)


def _home_fixture_card(row) -> str:
    return (
        f'<article class="home-match-card" style="background-image: {_match_background(row)};">'
        '<div class="home-match-card-top">'
        f'<span>{html.escape(_match_number_label(row.get("#")))}</span><span>{html.escape(str(row["Stage"]))}</span>'
        '</div>'
        '<div class="home-match-card-body">'
        f'<div class="home-fixture-teams"><div>{html.escape(_team_text(row.get("Home")))}</div><strong>vs</strong><div>{html.escape(_team_text(row.get("Away")))}</div></div>'
        f'<div class="home-fixture-score">{html.escape(_match_center(row))}</div>'
        '</div>'
        '<div class="home-match-card-bottom">'
        f'<span>{html.escape(str(row["Stage"]))}</span><span>{html.escape(str(row.get("City") or "Host City TBD"))}</span>'
        '</div>'
        '</article>'
    )


def _open_fixture_from_home(row) -> None:
    st.session_state["page_name"] = "Fixtures"
    st.session_state["selected_fixture_id"] = _match_number_label(row.get("#"))
    st.session_state["selected_fixture_row"] = _fixture_focus_row(row)
    st.session_state.pop("selected_team_id", None)
    st.session_state.pop("selected_match_id", None)
    st.query_params["page"] = "fixtures"
    if "team_id" in st.query_params:
        del st.query_params["team_id"]
    if "fixture" in st.query_params:
        del st.query_params["fixture"]
    st.rerun()


def _fixture_focus_row(row) -> dict:
    return {
        "official_match_number": row.get("#"),
        "match_id": _match_number_label(row.get("#")),
        "utc_date": row.get("kickoff_utc"),
        "local_time": row.get("Kickoff"),
        "home_team": row.get("Home"),
        "away_team": row.get("Away"),
        "stage": row.get("Stage"),
        "group": "",
        "venue": row.get("City"),
        "city": row.get("City"),
        "home_score": row.get("home_score"),
        "away_score": row.get("away_score"),
    }


def _match_background(row) -> str:
    city = str(row.get("City") or "Host City TBD")
    background = city_background_card_data_uri(city)
    if background:
        return f"linear-gradient(180deg, rgba(5,5,5,.18), rgba(5,5,5,.88)), url('{background}')"
    return "linear-gradient(135deg, #0B1020, #111111)"


def _match_number_label(value) -> str:
    if pd.isna(value):
        return "Match"
    try:
        return f"M{int(value)}"
    except (TypeError, ValueError):
        return f"M{value}"


def _match_center(row) -> str:
    score = row.get("Score")
    if pd.notna(score) and str(score).strip():
        return str(score)
    return str(row.get("Kickoff") or "")


def _team_text(value) -> str:
    if pd.isna(value) or not str(value).strip():
        return "TBD"
    return str(value)


def _safe_key(value: str) -> str:
    return "".join(character.lower() if character.isalnum() else "_" for character in str(value)).strip("_")


def _empty_label(value) -> str:
    if pd.isna(value) or not str(value).strip():
        return "TBD"
    return str(value)


def _render_favorites(favorites: pd.DataFrame) -> None:
    for start in range(0, len(favorites), 3):
        columns = st.columns(3)
        for column, (_, row) in zip(columns, favorites.iloc[start:start + 3].iterrows()):
            with column:
                st.markdown(_favorite_card(row), unsafe_allow_html=True)
                if st.button("Open team", key=f"home_favorite_open_{int(row['id'])}", use_container_width=True):
                    _open_team_from_home(int(row["id"]))


def _favorite_card(row) -> str:
    return (
        f'<article class="home-favorite{" out" if bool(row["_lost"]) else ""}">'
        f'<div class="home-favorite-head">{_flag_img(row["Team"], row.get("country_code"))}<strong>{html.escape(str(row["Team"]))}</strong></div>'
        '<div class="home-favorite-status">'
        f'<div><span>Group</span><strong>{html.escape(_empty_label(row["Group"]))}</strong></div>'
        f'<div><span>Stage</span><strong>{html.escape(_empty_label(row["Round"]))}</strong></div>'
        '</div>'
        f'<p>{html.escape(str(row["Next Game"]))}</p>'
        '</article>'
    )


def _open_team_from_home(team_id: int) -> None:
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


def _dashboard_matches() -> tuple[pd.DataFrame, str]:
    matches = _all_dashboard_fixtures()
    if matches.empty:
        return matches, "Today's Games"

    local_tz = ZoneInfo("America/Chicago")
    today = datetime.now(local_tz).date()
    matches = matches.copy()
    matches["_local_date"] = matches["kickoff_utc"].map(lambda value: _parse_dt(value).astimezone(local_tz).date())

    gameday = today if today in set(matches["_local_date"]) else None
    if gameday is None:
        future_dates = sorted(date for date in matches["_local_date"].unique() if date > today)
        if not future_dates:
            return pd.DataFrame(), "Today's Games"
        gameday = future_dates[0]

    gameday_matches = matches[matches["_local_date"] == gameday].copy()
    return _display_matches(gameday_matches), "Today's Games" if gameday == today else f"Next Gameday: {gameday.strftime('%B')} {gameday.day}"


def _previous_dashboard_matches() -> tuple[pd.DataFrame, str]:
    matches = _all_dashboard_fixtures()
    if matches.empty:
        return pd.DataFrame(), "Previous Gameday"

    local_tz = ZoneInfo("America/Chicago")
    today = datetime.now(local_tz).date()
    matches = matches.copy()
    matches["_local_date"] = matches["kickoff_utc"].map(lambda value: _parse_dt(value).astimezone(local_tz).date())
    scored = matches[matches.apply(_has_score, axis=1)].copy()
    previous_dates = sorted(date for date in scored["_local_date"].unique() if date < today)
    if not previous_dates:
        return pd.DataFrame(), "Previous Gameday"
    gameday = previous_dates[-1]
    gameday_matches = scored[scored["_local_date"] == gameday].copy()
    return _display_matches(gameday_matches), f"Previous Gameday: {gameday.strftime('%B')} {gameday.day}"


def _all_dashboard_fixtures() -> pd.DataFrame:
    try:
        return _fixtures_from_api()
    except Exception:
        return _fixtures_from_database()


def _display_matches(matches: pd.DataFrame) -> pd.DataFrame:
    display = matches.copy()
    display["Kickoff"] = display["kickoff_utc"].apply(format_local_time)
    display["Score"] = display.apply(_score_text, axis=1)
    return display[["#", "kickoff_utc", "Kickoff", "Home", "Away", "Stage", "City", "Priority", "Score", "home_score", "away_score"]]


def _has_score(row) -> bool:
    return pd.notna(row.get("home_score")) and pd.notna(row.get("away_score"))


def _score_text(row) -> str:
    if not _has_score(row):
        return ""
    return f"{int(row['home_score'])} - {int(row['away_score'])}"


def _fixtures_from_api() -> pd.DataFrame:
    fixtures = apply_official_match_reference(cached_matches())
    if fixtures.empty:
        return fixtures
    mapped = fixtures.rename(
        columns={
            "official_match_number": "#",
            "utc_date": "kickoff_utc",
            "home_team": "Home",
            "away_team": "Away",
            "venue": "City",
        }
    )
    mapped["Stage"] = mapped.apply(lambda row: _stage_label(row.get("stage"), row.get("group")), axis=1)
    mapped["Priority"] = ""
    for column in ("home_score", "away_score"):
        if column not in mapped:
            mapped[column] = pd.NA
    return mapped[["#", "kickoff_utc", "Home", "Away", "Stage", "City", "Priority", "home_score", "away_score"]].sort_values(["kickoff_utc", "#"])


def _fixtures_from_database() -> pd.DataFrame:
    fixtures = fetch_df(
        """
            SELECT f.match_number AS "#", f.kickoff_utc, ht.name AS Home, at.name AS Away,
                   COALESCE(f.group_name, f.stage) AS Stage, COALESCE(m.city, f.city) AS City,
                   m.game_label,
                   f.watch_priority AS Priority, f.home_score, f.away_score
            FROM fixtures f
            LEFT JOIN teams ht ON ht.id = f.home_team_id
            LEFT JOIN teams at ON at.id = f.away_team_id
            LEFT JOIN match_city_reference m ON m.match_number = f.match_number
            ORDER BY datetime(f.kickoff_utc), f.match_number
        """
    )
    return enrich_fixture_participants(fixtures, home_column="Home", away_column="Away")


def _stage_label(stage, group) -> str:
    group_text = str(group or "").replace("_", " ").title()
    if group_text and group_text.lower() != "nan":
        return group_text
    stage_text = str(stage or "").replace("_", " ").title()
    if stage_text == "Last 32":
        return "Round of 32"
    if stage_text == "Last 16":
        return "Round of 16"
    return stage_text


def _favorite_teams() -> pd.DataFrame:
    favorite_ids = load_favorite_teams()
    if not favorite_ids:
        return pd.DataFrame()
    placeholders = ",".join("?" for _ in favorite_ids)
    favorites = fetch_df(
        f"""
        SELECT t.id, t.name AS Team, COALESCE(g.group_name, '') AS "Group",
               t.country_code,
               COALESCE(g.qualification_status, '') AS qualification_status
        FROM teams t
        LEFT JOIN groups g ON g.team_id = t.id
        WHERE t.id IN ({placeholders})
        ORDER BY t.name
        """,
        favorite_ids,
    )
    if favorites.empty:
        return favorites

    fixtures = fetch_df(
        """
        SELECT f.match_number, f.kickoff_utc, f.stage, f.status,
               f.home_score, f.away_score, m.game_label,
               ht.id AS home_team_id, ht.name AS home_team,
               at.id AS away_team_id, at.name AS away_team
        FROM fixtures f
        LEFT JOIN teams ht ON ht.id = f.home_team_id
        LEFT JOIN teams at ON at.id = f.away_team_id
        LEFT JOIN match_city_reference m ON m.match_number = f.match_number
        ORDER BY datetime(f.kickoff_utc), f.match_number
        """
    )
    fixtures = enrich_fixture_participants(fixtures)
    now = datetime.now(timezone.utc)
    rows = []
    for _, team in favorites.iterrows():
        team_id = int(team["id"])
        team_fixtures = _team_fixtures(fixtures, team_id, str(team["Team"]))
        next_fixture = _next_fixture(team_fixtures, now)
        rows.append(
            {
                "id": team_id,
                "Team": team["Team"],
                "Group": team["Group"],
                "country_code": team["country_code"],
                "Next Game": _next_game_label(next_fixture, team_id, team["Team"]),
                "Round": _current_round(team["qualification_status"], team_fixtures, now, team_id),
                "_lost": _team_is_out_or_lost(team["qualification_status"], team_fixtures, now, team_id),
            }
        )
    return pd.DataFrame(rows).sort_values("Team")


def _flag_img(team: str, stored_code=None) -> str:
    code = "" if pd.isna(stored_code) else str(stored_code or "").strip().lower()
    code = code or FLAG_CODES.get(str(team), "")
    initials = "".join(part[0] for part in str(team).replace("-", " ").split()[:2]).upper() or "?"
    if not code:
        return f'<div class="home-favorite-flag flag-fallback">{html.escape(initials)}</div>'
    return (
        f'<img class="home-favorite-flag" src="https://flagcdn.com/w80/{html.escape(str(code).lower())}.png" alt="{html.escape(str(team))} flag" '
        f'onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'grid\';">'
        f'<div class="home-favorite-flag flag-fallback hidden">{html.escape(initials)}</div>'
    )


def _team_fixtures(fixtures: pd.DataFrame, team_id: int, team_name: str | None = None) -> pd.DataFrame:
    if fixtures.empty:
        return fixtures
    mask = (fixtures["home_team_id"] == team_id) | (fixtures["away_team_id"] == team_id)
    if team_name:
        team_key = normalize_team_key(team_name)
        mask = mask | fixtures["home_team"].map(normalize_team_key).eq(team_key) | fixtures["away_team"].map(normalize_team_key).eq(team_key)
    return fixtures[mask].copy()


def _next_fixture(fixtures: pd.DataFrame, now: datetime):
    if fixtures.empty:
        return None
    upcoming = fixtures[fixtures["kickoff_utc"].map(lambda value: _parse_dt(value) >= now)].copy()
    if upcoming.empty:
        return None
    upcoming["_dt"] = upcoming["kickoff_utc"].map(_parse_dt)
    return upcoming.sort_values(["_dt", "match_number"]).iloc[0]


def _next_game_label(fixture, team_id: int, team_name: str = "") -> str:
    if fixture is None:
        return ""
    if fixture["home_team_id"] == team_id or normalize_team_key(fixture["home_team"]) == normalize_team_key(team_name):
        opponent = fixture["away_team"]
    else:
        opponent = fixture["home_team"]
    kickoff = format_local_time(fixture["kickoff_utc"])
    return f"{kickoff} vs {opponent}"


def _current_round(status: str, fixtures: pd.DataFrame, now: datetime, team_id: int) -> str:
    text = str(status or "").lower()
    if "champion" in text:
        return "Champion"

    next_fixture = _next_fixture(fixtures, now)
    if next_fixture is not None:
        return _round_label(next_fixture["stage"])

    latest = _latest_fixture(fixtures)
    if latest is None:
        return "Group Stage"
    if _round_label(latest["stage"]) == "Finals" and _won_fixture(latest, team_id):
        return "Champion"
    return _round_label(latest["stage"])


def _team_is_out_or_lost(status: str, fixtures: pd.DataFrame, now: datetime, team_id: int) -> bool:
    text = str(status or "").lower()
    if any(word in text for word in ("out", "eliminated", "knocked")):
        return True
    if _next_fixture(fixtures, now) is not None:
        return False
    latest = _latest_fixture(fixtures)
    if latest is None:
        return False
    return _is_knockout_stage(latest["stage"]) and _lost_fixture(latest, team_id)


def _latest_fixture(fixtures: pd.DataFrame):
    if fixtures.empty:
        return None
    completed = fixtures.dropna(subset=["home_score", "away_score"]).copy()
    if completed.empty:
        return None
    completed["_dt"] = completed["kickoff_utc"].map(_parse_dt)
    return completed.sort_values(["_dt", "match_number"]).iloc[-1]


def _round_label(stage: str) -> str:
    text = str(stage or "").strip().lower()
    if "round of 32" in text:
        return "Round of 32"
    if "round of 16" in text:
        return "Round of 16"
    if "quarter" in text:
        return "Quarterfinals"
    if "semi" in text:
        return "Semifinals"
    if "final" in text:
        return "Finals"
    return "Group Stage"


def _is_knockout_stage(stage: str) -> bool:
    return _round_label(stage) != "Group Stage"


def _won_fixture(fixture, team_id: int) -> bool:
    home_score = fixture["home_score"]
    away_score = fixture["away_score"]
    if pd.isna(home_score) or pd.isna(away_score) or home_score == away_score:
        return False
    if fixture["home_team_id"] == team_id:
        return home_score > away_score
    return away_score > home_score


def _lost_fixture(fixture, team_id: int) -> bool:
    home_score = fixture["home_score"]
    away_score = fixture["away_score"]
    if pd.isna(home_score) or pd.isna(away_score) or home_score == away_score:
        return False
    if fixture["home_team_id"] == team_id:
        return home_score < away_score
    return away_score < home_score


def _parse_dt(value) -> datetime:
    text = str(value or "").replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _gray_out_lost_team(row, lost_flags: pd.Series) -> list[str]:
    if not bool(lost_flags.loc[row.name]):
        return [""] * len(row)
    return ["color: #9ca3af; background-color: #f3f4f6;"] * len(row)


def _styles() -> None:
    st.markdown(
        """
        <style>
        .home-hero {
            align-items: center;
            border: 1px solid rgba(214,168,58,.34);
            border-radius: 8px;
            background:
                linear-gradient(135deg, rgba(5,5,5,.72), rgba(11,16,32,.62)),
                radial-gradient(circle at 82% 18%, rgba(214,168,58,.20), transparent 30%),
                radial-gradient(circle at 18% 84%, rgba(35,215,215,.15), transparent 32%);
            display: flex;
            justify-content: space-between;
            gap: 1rem;
            margin: .25rem 0 .85rem;
            padding: 1rem 1.15rem;
        }
        .home-hero span, .home-section-title {
            color: #D6A83A;
            font-size: .82rem;
            font-weight: 950;
            text-transform: uppercase;
        }
        .home-hero h2 {
            color: #FFFFFF;
            font-size: 2.1rem;
            font-weight: 950;
            line-height: .96;
            margin: .1rem 0 0;
        }
        .home-hero p {
            color: #CBD5E1;
            font-weight: 800;
            margin: 0;
            text-align: right;
        }
        .home-scoreboard {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: .55rem;
            margin-bottom: 1.2rem;
        }
        .home-score-row {
            align-items: center;
            border: 1px solid rgba(214,168,58,.20);
            border-radius: 8px;
            background: rgba(5,5,5,.38);
            display: grid;
            grid-template-columns: 42px 1fr auto;
            gap: .45rem;
            min-height: 58px;
            padding: .55rem .65rem;
        }
        .home-score-row span, .home-score-row em {
            color: #D6A83A;
            font-style: normal;
            font-weight: 950;
        }
        .home-score-row strong {
            color: #FFFFFF;
            font-weight: 950;
            line-height: 1.05;
        }
        .home-score-row em {
            font-size: 1.3rem;
        }
        .home-section-title {
            border-bottom: 1px solid rgba(214,168,58,.24);
            margin: 1.1rem 0 .7rem;
            padding-bottom: .5rem;
        }
        .intralox-home-title {
            margin-top: 1.35rem;
        }
        .home-match-grid, .home-favorites {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: .65rem;
        }
        .home-match-card {
            border: 1px solid rgba(255,255,255,.13);
            border-radius: 8px;
            background-size: cover;
            background-position: center;
            box-shadow: 0 16px 38px rgba(0,0,0,.24);
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            min-height: 210px;
            overflow: hidden;
            padding: .85rem;
        }
        .home-match-card-top, .home-match-card-bottom {
            display: flex;
            justify-content: space-between;
            gap: .75rem;
            color: #D6A83A;
            font-size: .74rem;
            font-weight: 900;
            text-transform: uppercase;
            text-shadow: 0 2px 10px rgba(0,0,0,.75);
        }
        .home-match-card-body {
            color: #FFFFFF;
            text-shadow: 0 3px 16px rgba(0,0,0,.9);
        }
        .home-fixture-teams {
            align-items: center;
            display: grid;
            gap: .5rem;
            grid-template-columns: 1fr auto 1fr;
            font-size: 1.08rem;
            font-weight: 950;
            line-height: 1.05;
            text-align: center;
        }
        .home-fixture-teams strong {
            color: #D6A83A;
            font-size: .8rem;
        }
        .home-fixture-score {
            color: #f8fafc;
            font-weight: 950;
            margin-top: .72rem;
            text-align: center;
        }
        [class*="st-key-home_fixture_open_"] {
            height: 210px;
            margin-top: -210px;
            margin-bottom: .65rem;
            position: relative;
            z-index: 2;
        }
        [class*="st-key-home_fixture_open_"] button,
        [class*="st-key-home_favorite_open_"] button {
            background: transparent !important;
            border: 0 !important;
            box-shadow: none !important;
            color: transparent !important;
            cursor: pointer;
            opacity: 0;
            padding: 0 !important;
        }
        [class*="st-key-home_fixture_open_"] button {
            height: 210px;
            min-height: 210px;
        }
        [class*="st-key-home_fixture_open_"] button p,
        [class*="st-key-home_favorite_open_"] button p {
            color: transparent !important;
        }
        .home-favorite {
            border: 1px solid rgba(255,255,255,.13);
            border-radius: 8px;
            background:
                linear-gradient(135deg, rgba(5,5,5,.56), rgba(11,16,32,.52)),
                radial-gradient(circle at 100% 0%, rgba(36,88,255,.12), transparent 32%);
            min-height: 190px;
            padding: .75rem;
        }
        [class*="st-key-home_favorite_open_"] {
            height: 190px;
            margin-top: -190px;
            margin-bottom: .65rem;
            position: relative;
            z-index: 2;
        }
        [class*="st-key-home_favorite_open_"] button {
            height: 190px;
            min-height: 190px;
        }
        .home-favorite p {
            color: #CBD5E1;
            font-weight: 800;
            margin: .65rem 0 0;
        }
        .home-favorite strong {
            color: #FFFFFF;
            display: block;
            font-size: 1.05rem;
            font-weight: 950;
        }
        .home-favorite-head {
            align-items: center;
            display: flex;
            gap: .55rem;
            margin-bottom: .35rem;
        }
        .home-favorite-status {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: .45rem;
            margin-top: .7rem;
        }
        .home-favorite-status div {
            border: 1px solid rgba(214,168,58,.24);
            border-radius: 8px;
            background: rgba(5,5,5,.34);
            min-height: 64px;
            padding: .5rem .55rem;
        }
        .home-favorite-status span {
            color: #D6A83A;
            display: block;
            font-size: .66rem;
            font-weight: 950;
            letter-spacing: .04em;
            line-height: 1;
            text-transform: uppercase;
        }
        .home-favorite-status strong {
            color: #FFFFFF;
            font-size: .96rem;
            font-weight: 950;
            line-height: 1.05;
            margin-top: .32rem;
        }
        .home-favorite-flag {
            aspect-ratio: 3 / 2;
            border: 1px solid rgba(255,255,255,.52);
            border-radius: 5px;
            box-shadow: 0 7px 15px rgba(0,0,0,.30);
            flex: 0 0 42px;
            object-fit: cover;
            width: 42px;
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
        .home-favorite.out {
            opacity: .55;
        }
        @media (max-width: 980px) {
            .home-scoreboard, .home-match-grid, .home-favorites {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }
        @media (max-width: 620px) {
            .home-hero {
                flex-direction: column;
                align-items: flex-start;
            }
            .home-hero p {
                text-align: left;
            }
            .home-scoreboard, .home-match-grid, .home-favorites {
                grid-template-columns: 1fr;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
