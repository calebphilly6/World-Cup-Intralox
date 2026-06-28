from __future__ import annotations

from datetime import datetime, timezone
import html
import pandas as pd
import streamlit as st

from src import team_status
from src.city_backgrounds import city_background_card_data_uri, city_background_data_uri
from src.database import fetch_df
from src.fixture_display import enrich_fixture_participants, flag_code_for_team, flag_lookup_with_aliases
from src.football_data_service import hourly_fixture_refresh_key
from src.jersey_assets import team_jersey_data_uri, team_jersey_header_data_uri
from src.navigation import remember_detail_origin, return_to_detail_origin
from src.official_match_reference import normalize_team_key
from src.pages.fixtures import _fixture_data
from src.storage.storage import (
    load_favorite_teams,
    personal_preferences_use_browser_storage,
    save_favorite_teams,
)
from src.utils.formatting import format_local_time
from src.utils.team_names import display_team_name, team_lookup_keys


FALLBACK_FLAGS = {
    "England": "gb-eng",
    "Scotland": "gb-sct",
}


def render() -> None:
    st.title("Teams")
    _styles()

    teams = _teams()
    if teams.empty:
        st.info("Import teams to start building the field.")
        return

    eliminated_keys = _eliminated_team_keys(hourly_fixture_refresh_key())

    selected_id = st.session_state.get("selected_team_id")
    if selected_id:
        selected = teams[teams["id"] == selected_id]
        if not selected.empty:
            _team_focus(selected.iloc[0], eliminated_keys)
            return
        st.session_state.pop("selected_team_id", None)

    sorted_teams = teams.sort_values(["favorite_sort", "team"], ascending=[False, True])
    for start in range(0, len(sorted_teams), 2):
        cols = st.columns(2)
        for col, (_, team) in zip(cols, sorted_teams.iloc[start:start + 2].iterrows()):
            with col:
                _team_card(team, eliminated_keys)


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
    teams["team"] = teams["team"].apply(display_team_name)
    teams["name"] = teams["name"].apply(display_team_name)
    return teams


@st.cache_data(show_spinner=False)
def _eliminated_team_keys(refresh_key: str) -> frozenset[str]:
    """Normalized lookup keys for every team that is out of the tournament.

    Uses the same live, knockout-resolved fixtures feed and bracket resolution as
    the Home favorite cards (see :mod:`src.team_status`) so the two views agree on
    who is eliminated. Returns an empty set if the feed is unavailable.
    """
    try:
        fixtures, _warning = _fixture_data(refresh_key)
    except Exception:
        fixtures = pd.DataFrame()
    fixtures = team_status.normalize_feed(fixtures)
    if fixtures.empty:
        return frozenset()

    try:
        from src.knockout_slots import all_slot_teams

        slot_teams = dict(all_slot_teams())
    except Exception:
        slot_teams = {}
    knockout_keys = team_status.knockout_participant_keys(slot_teams)
    bracket_complete = team_status.bracket_is_complete(slot_teams)

    now = datetime.now(timezone.utc)
    names = fetch_df("SELECT name FROM teams").get("name", pd.Series(dtype=str)).dropna()
    eliminated: set[str] = set()
    for name in names:
        team_fixtures = team_status.fixtures_for_team(fixtures, str(name))
        if team_status.is_eliminated(
            team_fixtures,
            now,
            str(name),
            knockout_keys=knockout_keys,
            bracket_complete=bracket_complete,
        ):
            eliminated |= team_lookup_keys(str(name))
    return frozenset(eliminated)


def _team_is_eliminated(team_name, eliminated_keys: frozenset[str]) -> bool:
    return any(key in eliminated_keys for key in team_lookup_keys(team_name))


def _team_card(team, eliminated_keys: frozenset[str] = frozenset()) -> None:
    flag_url = _flag_url(team)
    rank = _display_rank(team["fifa_rank"])
    group = team["group_name"] or "Unassigned"
    star = "★" if int(team["favorite"] or 0) else "☆"
    favorite_label = "Remove favorite" if int(team["favorite"] or 0) else "Make favorite"
    eliminated = _team_is_eliminated(team["team"], eliminated_keys)
    card_class = "team-card eliminated" if eliminated else "team-card"
    badge = '<div class="team-elim-badge">Eliminated</div>' if eliminated else ""

    st.markdown(
        f"""
        <div class="{card_class}" style="background-image: linear-gradient(90deg, rgba(3,7,18,.76), rgba(3,7,18,.45)), url('{flag_url}');">
          {badge}
          <div class="team-card-content">
            <div class="team-name">{team['team']}</div>
            <div class="team-meta">Group {group}</div>
            <div class="team-rank">FIFA Rank {rank}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    c1, c2 = st.columns([0.14, 0.86], gap="small", vertical_alignment="center")
    with c1:
        with st.container(key=f"favorite_star_{team['id']}"):
            if st.button(star, key=f"fav_{team['id']}", help=favorite_label, use_container_width=True):
                _toggle_favorite(int(team["id"]), int(team["favorite"] or 0))
                st.rerun()
    with c2:
        with st.container(key=f"open_country_{team['id']}"):
            if st.button(f"Open {team['team']}", key=f"open_{team['id']}", use_container_width=True):
                st.session_state["selected_team_id"] = int(team["id"])
                st.rerun()


def _team_focus(team, eliminated_keys: frozenset[str] = frozenset()) -> None:
    fixtures = _fixtures_for_team(team)
    selected_match = st.session_state.get("selected_match_id")
    if selected_match:
        match = fixtures[fixtures["match_id"] == selected_match] if not fixtures.empty else pd.DataFrame()
        if not match.empty:
            _match_focus(match.iloc[0], team)
            return
        st.session_state.pop("selected_match_id", None)

    header_image = team_jersey_header_data_uri(team["team"]) or _flag_url(team)
    eliminated = _team_is_eliminated(team["team"], eliminated_keys)
    badge = '<div class="team-focus-elim">Eliminated</div>' if eliminated else ""
    st.markdown(
        f"""
        <div class="team-focus" style="background-image: linear-gradient(90deg, rgba(3,7,18,.92), rgba(3,7,18,.58)), url('{header_image}');">
          {badge}
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
        return_to_detail_origin("team_return_origin", "Teams")
        st.rerun()

    _ranking_context(team["team"])
    if fixtures.empty:
        st.info("No fixtures stored for this team yet.")
    else:
        st.subheader("Fixtures")
        _render_team_fixture_cards(team, fixtures)
    _roster_section(int(team["id"]), team["team"])


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
    lookup_keys = team_lookup_keys(team_name)
    current = rankings[rankings["team"].map(normalize_team_key).isin(lookup_keys)]
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
    display_name = display_team_name(row["team"])
    team = html.escape(display_name)
    rank = "" if pd.isna(row["rank"]) else str(int(row["rank"]))
    focus_class = " ranking-context-focus" if normalize_team_key(display_name) in team_lookup_keys(focus_team) else ""
    return f'<tr class="{focus_class}"><td>{team}</td><td>#{rank}</td></tr>'


def _roster_section(team_id: int, team_name: str = "") -> None:
    roster = fetch_df(
        """
        SELECT player_name, shirt_number, position, club, source, updated_at
        FROM roster_players
        WHERE team_id = ?
        ORDER BY
            CASE position
                WHEN 'GK' THEN 1
                WHEN 'Goalkeeper' THEN 1
                WHEN 'DF' THEN 2
                WHEN 'Defender' THEN 2
                WHEN 'Defence' THEN 2
                WHEN 'MF' THEN 3
                WHEN 'Midfielder' THEN 3
                WHEN 'Midfield' THEN 3
                WHEN 'FW' THEN 4
                WHEN 'Forward' THEN 4
                WHEN 'Attacker' THEN 4
                ELSE 5
            END,
            shirt_number IS NULL,
            shirt_number,
            player_name
        """,
        [team_id],
    )
    if roster.empty:
        st.markdown(
            """
            <section class="team-roster-shell team-roster-empty">
                <div class="team-roster-header">
                    <div>
                        <h3>Roster</h3>
                    </div>
                </div>
                <div class="team-roster-empty-message">No roster has been imported for this team yet.</div>
            </section>
            """,
            unsafe_allow_html=True,
        )
        return

    sort_key = "position"
    roster = _sort_roster(roster, sort_key)
    st.markdown(_roster_markup(roster, sort_key, team_jersey_data_uri(team_name)), unsafe_allow_html=True)
    _roster_sort_script()


def _roster_markup(roster: pd.DataFrame, sort_key: str, jersey_uri: str = "") -> str:
    rows = "".join(_roster_row(row) for _, row in roster.iterrows())
    shell_style = ""
    if jersey_uri:
        shell_style = (
            ' style="background-image: linear-gradient(rgba(8,10,18,.82), rgba(8,10,18,.88)), '
            f"url('{jersey_uri}'); background-size: cover; background-position: center 14%; "
            'background-repeat: no-repeat;"'
        )
    return f"""
    <section class="team-roster-shell"{shell_style}>
        <div class="team-roster-header">
            <div>
                <h3>Roster</h3>
            </div>
            <div class="team-roster-total">{len(roster)} players</div>
        </div>
        <div class="team-roster-table" role="table" aria-label="Team roster">
            <div class="team-roster-table-head" role="row">
                {_roster_header_cell("no", "No.", sort_key)}
                {_roster_header_cell("player", "Player", sort_key)}
                {_roster_header_cell("position", "Pos", sort_key)}
                {_roster_header_cell("club", "Club", sort_key)}
            </div>
            {rows}
        </div>
    </section>
    """


def _roster_header_cell(key: str, label: str, active_sort: str) -> str:
    active_class = " active" if key == active_sort else ""
    return (
        f'<button class="team-roster-sort{active_class}" type="button" data-roster-sort="{html.escape(key, quote=True)}" '
        f'aria-label="Sort roster by {html.escape(label)}">{html.escape(label)}</button>'
    )


def _sort_roster(roster: pd.DataFrame, sort_key: str) -> pd.DataFrame:
    sorted_roster = roster.copy()
    sorted_roster["_number_sort"] = sorted_roster["shirt_number"].map(_roster_number_sort_value)
    sorted_roster["_position_sort"] = sorted_roster["position"].map(_roster_position_sort_value)
    sorted_roster["_player_sort"] = sorted_roster["player_name"].map(lambda value: _clean_roster_value(value, "").casefold())
    sorted_roster["_club_sort"] = sorted_roster["club"].map(lambda value: _clean_roster_value(value, "").casefold())
    sort_columns = {
        "no": ["_number_sort", "_player_sort"],
        "player": ["_player_sort", "_number_sort"],
        "position": ["_position_sort", "_number_sort", "_player_sort"],
        "club": ["_club_sort", "_player_sort", "_number_sort"],
    }[sort_key]
    return sorted_roster.sort_values(sort_columns, na_position="last").drop(
        columns=["_number_sort", "_position_sort", "_player_sort", "_club_sort"]
    )


def _roster_row(row) -> str:
    number = _roster_number(row.get("shirt_number"))
    player = _clean_roster_value(row.get("player_name"), "Player TBD")
    position = _roster_position_label(row.get("position"))
    club = _clean_roster_value(row.get("club"), "Club TBD")
    number_sort = _roster_number_sort_value(row.get("shirt_number"))
    number_sort_text = "9999" if number_sort == float("inf") else str(number_sort)
    position_sort = str(_roster_position_sort_value(row.get("position")))
    player_sort = _clean_roster_value(row.get("player_name"), "").casefold()
    club_sort = _clean_roster_value(row.get("club"), "").casefold()
    return (
        '<div class="team-roster-row" role="row" '
        f'data-no="{html.escape(number_sort_text, quote=True)}" '
        f'data-player="{html.escape(player_sort, quote=True)}" '
        f'data-position="{html.escape(position_sort, quote=True)}" '
        f'data-club="{html.escape(club_sort, quote=True)}">'
        f'<span class="team-roster-number">{html.escape(number)}</span>'
        f'<span class="team-roster-player">{html.escape(player)}</span>'
        f'<span class="team-roster-position">{html.escape(position)}</span>'
        f'<span class="team-roster-club">{html.escape(club)}</span>'
        '</div>'
    )


def _roster_sort_script() -> None:
    st.iframe(
        """
        <script>
        (() => {
          const doc = window.parent.document;
          const numericSorts = new Set(["no", "position"]);

          function valueFor(row, key) {
            const value = row.dataset[key] || "";
            return numericSorts.has(key) ? Number(value || 9999) : value;
          }

          function compareRows(key, left, right) {
            const primaryLeft = valueFor(left, key);
            const primaryRight = valueFor(right, key);
            if (typeof primaryLeft === "number" || typeof primaryRight === "number") {
              const difference = Number(primaryLeft) - Number(primaryRight);
              if (difference !== 0) return difference;
            } else {
              const difference = String(primaryLeft).localeCompare(String(primaryRight));
              if (difference !== 0) return difference;
            }

            const numberDifference = Number(left.dataset.no || 9999) - Number(right.dataset.no || 9999);
            if (numberDifference !== 0) return numberDifference;
            return String(left.dataset.player || "").localeCompare(String(right.dataset.player || ""));
          }

          function sortTable(table, key) {
            const rows = Array.from(table.querySelectorAll(".team-roster-row"));
            rows.sort((left, right) => compareRows(key, left, right));
            rows.forEach(row => table.appendChild(row));
            table.querySelectorAll(".team-roster-sort").forEach(button => {
              button.classList.toggle("active", button.dataset.rosterSort === key);
            });
          }

          function bindRosterSorts() {
            doc.querySelectorAll(".team-roster-table").forEach(table => {
              if (table.dataset.rosterSortBound === "true") return;
              table.dataset.rosterSortBound = "true";
              table.querySelectorAll(".team-roster-sort").forEach(button => {
                button.addEventListener("click", event => {
                  event.preventDefault();
                  event.stopPropagation();
                  sortTable(table, button.dataset.rosterSort);
                });
              });
            });
          }

          bindRosterSorts();
          setTimeout(bindRosterSorts, 250);
        })();
        </script>
        """,
        height=1,  # st.iframe requires height >= 1; this iframe only runs JS
    )


def _roster_position_group(value) -> str:
    text = _clean_roster_value(value, "").lower()
    if text in {"gk", "goalkeeper"}:
        return "GK"
    if text in {"df", "defender", "defence", "defense"}:
        return "DF"
    if text in {"mf", "midfielder", "midfield"}:
        return "MF"
    if text in {"fw", "forward", "attacker"}:
        return "FW"
    return "Other"


def _roster_position_sort_value(value) -> int:
    return {
        "GK": 1,
        "DF": 2,
        "MF": 3,
        "FW": 4,
        "Other": 5,
    }[_roster_position_group(value)]


def _roster_number_sort_value(value) -> float:
    if value is None or pd.isna(value) or str(value).strip() == "":
        return float("inf")
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("inf")


def _roster_position_label(value) -> str:
    group = _roster_position_group(value)
    if group != "Other":
        return group
    return _clean_roster_value(value, "-")


def _roster_number(value) -> str:
    if value is None or pd.isna(value) or str(value).strip() == "":
        return "-"
    try:
        return str(int(float(value)))
    except (TypeError, ValueError):
        return str(value).strip()


def _clean_roster_value(value, fallback: str) -> str:
    if value is None or pd.isna(value) or str(value).strip() == "":
        return fallback
    return str(value).strip()


def _fixtures_for_team(team) -> pd.DataFrame:
    # Prefer the live fixtures feed (same source as the Fixtures tab) so scores stay
    # in sync. Fall back to the local schedule only when the feed is unavailable.
    provider_matches = _provider_fixtures_for_team(team)
    if not provider_matches.empty:
        return provider_matches
    return _local_fixtures_for_team(team)


def _provider_fixtures_for_team(team) -> pd.DataFrame:
    try:
        fixtures, _warning = _fixture_data(hourly_fixture_refresh_key())
    except Exception:
        return pd.DataFrame()
    if fixtures is None or fixtures.empty:
        return pd.DataFrame()
    team_key = normalize_team_key(team["team"])
    matched = fixtures[
        fixtures["home_team"].map(normalize_team_key).eq(team_key)
        | fixtures["away_team"].map(normalize_team_key).eq(team_key)
    ].copy()
    if matched.empty:
        return matched
    if "kickoff_utc" not in matched.columns and "utc_date" in matched.columns:
        matched["kickoff_utc"] = matched["utc_date"]
    if "group_name" not in matched.columns and "group" in matched.columns:
        matched["group_name"] = matched["group"]
    return matched


def _local_fixtures_for_team(team) -> pd.DataFrame:
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
    if local_fixtures.empty:
        return local_fixtures
    team_key = normalize_team_key(team["team"])
    return local_fixtures[
        local_fixtures["home_team"].map(normalize_team_key).eq(team_key)
        | local_fixtures["away_team"].map(normalize_team_key).eq(team_key)
    ].copy()


def _render_team_fixture_cards(team, fixtures: pd.DataFrame) -> None:
    for start in range(0, len(fixtures), 3):
        columns = st.columns(3)
        for column, (_, fixture) in zip(columns, fixtures.iloc[start:start + 3].iterrows()):
            with column:
                st.markdown(_team_fixture_card(fixture), unsafe_allow_html=True)
                key = f"team_fixture_open_{int(team['id'])}_{_safe_key(_fixture_match_id(fixture))}"
                if st.button("Open match", key=key, use_container_width=True):
                    _open_fixture_in_fixtures_tab(fixture)


def _team_fixture_card(fixture) -> str:
    match_id = _fixture_match_id(fixture)
    stage = _fixture_stage_label(fixture)
    round_stage = _fixture_round_label(stage)
    city = _fixture_city(fixture)
    bottom_markup = _team_fixture_bottom_markup(round_stage, stage)
    return (
        f'<article class="team-fixture-card" style="background-image: {_team_fixture_background(city)};">'
        '<div class="team-fixture-card-top">'
        f'<span>{html.escape(match_id)}</span><span>{html.escape(city)}</span>'
        '</div>'
        '<div class="team-fixture-card-body">'
        f'<div class="team-fixture-teams">{_team_fixture_team(fixture.get("home_team"))}<strong>vs</strong>{_team_fixture_team(fixture.get("away_team"))}</div>'
        f'<div class="team-fixture-score">{html.escape(_team_fixture_center(fixture))}</div>'
        '</div>'
        f'{bottom_markup}'
        '</article>'
    )


def _team_fixture_background(city: str) -> str:
    background = city_background_card_data_uri(city)
    if background:
        return f"linear-gradient(180deg, rgba(5,5,5,.18), rgba(5,5,5,.88)), url('{background}')"
    return "linear-gradient(135deg, #0B1020, #111111)"


def _team_fixture_team(value) -> str:
    team = _team_text(value)
    return (
        '<div class="team-fixture-team">'
        f'{_team_fixture_flag(team)}'
        f'<span>{html.escape(team)}</span>'
        '</div>'
    )


def _team_fixture_flag(team: str) -> str:
    code = flag_code_for_team(team, _team_flag_lookup())
    initials = "".join(part[0] for part in str(team).replace("-", " ").split()[:2]).upper() or "?"
    if not code:
        return f'<div class="team-fixture-flag flag-fallback">{html.escape(initials)}</div>'
    return (
        f'<img class="team-fixture-flag" src="https://flagcdn.com/w80/{html.escape(str(code).lower())}.png" alt="{html.escape(str(team))} flag" '
        f'onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'grid\';">'
        f'<div class="team-fixture-flag flag-fallback hidden">{html.escape(initials)}</div>'
    )


def _team_fixture_center(fixture) -> str:
    if pd.notna(fixture.get("home_score")) and pd.notna(fixture.get("away_score")):
        return f"{int(fixture['home_score'])} - {int(fixture['away_score'])}"
    return format_local_time(fixture.get("kickoff_utc"))


def _fixture_stage_label(fixture) -> str:
    group = str(fixture.get("group_name", fixture.get("group", "")) or "").strip().replace("_", " ").title()
    if group and group.lower() != "nan":
        if group.lower().startswith("group "):
            return group
        return f"Group {group}" if len(group) == 1 else group
    stage = str(fixture.get("stage") or "").replace("_", " ").strip().title()
    return stage or "Stage TBD"


def _fixture_round_label(stage: str) -> str:
    text = str(stage or "").replace("_", " ").strip()
    key = "".join(character for character in text.lower() if character.isalnum())
    labels = {
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
    if key in labels:
        return labels[key]
    if text.lower().startswith("group "):
        return "Group Stage"
    return text.title() if text else "Stage TBD"


def _team_fixture_bottom_markup(round_stage: str, stage: str) -> str:
    if _is_group_stage_label(round_stage) and stage != round_stage:
        return (
            '<div class="team-fixture-card-bottom">'
            f'<span>{html.escape(round_stage)}</span><span>{html.escape(stage)}</span>'
            '</div>'
        )
    return (
        '<div class="team-fixture-card-bottom is-centered">'
        f'<span>{html.escape(round_stage)}</span>'
        '</div>'
    )


def _is_group_stage_label(value: str) -> bool:
    return str(value or "").strip().lower() == "group stage"


def _fixture_city(fixture) -> str:
    value = fixture.get("city", fixture.get("venue"))
    if pd.isna(value) or not str(value).strip():
        return "Host City TBD"
    return str(value)


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
    remember_detail_origin("fixture_return_origin")
    st.session_state["page_name"] = "Fixtures"
    st.session_state["selected_fixture_id"] = match_id
    st.session_state["selected_fixture_row"] = _fixture_focus_row(fixture, match_id)
    st.session_state.pop("selected_team_id", None)
    st.session_state.pop("selected_match_id", None)
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


def _team_text(value) -> str:
    if pd.isna(value) or not str(value).strip():
        return "TBD"
    return str(value)


def _safe_key(value: str) -> str:
    return "".join(character.lower() if character.isalnum() else "_" for character in str(value)).strip("_")


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
    stage = _fixture_stage_label(fixture)
    st.markdown(
        f"""
        <div class="match-focus" style="background-image: {background_style};">
          <div class="stadium-bg"></div>
          <div class="match-stage-badge">{html.escape(stage)}</div>
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
            position: relative;
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
        .team-card.eliminated {
            border-color: rgba(220,38,38,.75);
            filter: grayscale(.55);
        }
        .team-elim-badge {
            position: absolute;
            top: .7rem;
            right: .7rem;
            z-index: 1;
            background: #b91c1c;
            color: #FFFFFF;
            font-size: .72rem;
            font-weight: 950;
            letter-spacing: .04em;
            text-transform: uppercase;
            padding: .28rem .6rem;
            border-radius: 999px;
            box-shadow: 0 6px 16px rgba(0,0,0,.45);
        }
        .team-focus-elim {
            align-self: flex-start;
            display: inline-block;
            background: #b91c1c;
            color: #FFFFFF;
            font-size: .9rem;
            font-weight: 950;
            letter-spacing: .05em;
            text-transform: uppercase;
            padding: .4rem .85rem;
            border-radius: 999px;
            margin-bottom: 1rem;
            box-shadow: 0 8px 22px rgba(0,0,0,.5);
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
            min-height: 520px;
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
        .team-roster-shell {
            background:
                linear-gradient(135deg, rgba(5,5,5,.50), rgba(11,16,32,.42)),
                radial-gradient(circle at 12% 0%, rgba(214,168,58,.14), transparent 30%);
            border: 1px solid rgba(214,168,58,.26);
            border-radius: 8px;
            box-shadow: 0 14px 34px rgba(0,0,0,.20);
            margin: 1.15rem 0 1.35rem;
            overflow: hidden;
            padding: 1rem;
        }
        .team-roster-header {
            align-items: flex-end;
            display: flex;
            gap: 1rem;
            justify-content: space-between;
            margin-bottom: .8rem;
        }
        .team-roster-header h3 {
            color: #D6A83A;
            font-size: 1.55rem;
            font-weight: 950;
            margin: .1rem 0 0;
        }
        .team-roster-total {
            background: rgba(214,168,58,.16);
            border: 1px solid rgba(214,168,58,.32);
            border-radius: 999px;
            color: #F8FAFC;
            flex: 0 0 auto;
            font-size: .82rem;
            font-weight: 900;
            padding: .42rem .7rem;
        }
        .team-roster-table {
            border: 1px solid rgba(255,255,255,.10);
            border-radius: 8px;
            overflow: hidden;
            margin-top: .8rem;
        }
        .team-roster-table-head,
        .team-roster-row {
            align-items: center;
            display: grid;
            gap: .75rem;
            grid-template-columns: 3.6rem minmax(9rem, 1.45fr) 4rem minmax(8rem, 1fr);
        }
        .team-roster-table-head {
            background: linear-gradient(135deg, #D6A83A, #9E7420);
            font-size: .78rem;
            font-weight: 950;
            padding: .54rem .68rem;
            text-transform: uppercase;
        }
        .team-roster-sort {
            appearance: none;
            align-items: center;
            background: rgba(5,5,5,.08);
            border: 1px solid rgba(5,5,5,.12);
            border-radius: 6px;
            color: #111827 !important;
            cursor: pointer;
            display: inline-flex;
            font-family: inherit;
            font-size: inherit;
            font-weight: 950;
            gap: .32rem;
            justify-content: space-between;
            letter-spacing: 0;
            line-height: 1;
            min-height: 1.75rem;
            min-width: 3.15rem;
            padding: .42rem .48rem;
            text-decoration: none !important;
            transition: background .15s ease, border-color .15s ease, box-shadow .15s ease, transform .15s ease;
            width: fit-content;
        }
        .team-roster-sort:hover {
            background: rgba(255,255,255,.20);
            border-color: rgba(5,5,5,.24);
            box-shadow: 0 5px 12px rgba(5,5,5,.12);
            color: #050505 !important;
            transform: translateY(-1px);
            text-decoration: none !important;
        }
        .team-roster-sort:focus-visible {
            outline: 2px solid rgba(255,255,255,.88);
            outline-offset: 2px;
        }
        .team-roster-sort.active {
            background: #050505;
            border-color: rgba(5,5,5,.72);
            box-shadow: 0 5px 14px rgba(5,5,5,.18);
            color: #D6A83A !important;
        }
        .team-roster-sort.active::after {
            content: "↑";
            align-items: center;
            background: rgba(214,168,58,.18);
            border-radius: 999px;
            color: #F8FAFC;
            display: inline-flex;
            font-size: .68rem;
            height: 1rem;
            justify-content: center;
            line-height: 1;
            width: 1rem;
        }
        .team-roster-row {
            background: rgba(255,255,255,.052);
            border-top: 1px solid rgba(255,255,255,.08);
            color: #F8FAFC;
            min-height: 3rem;
            padding: .64rem .8rem;
        }
        .team-roster-row:nth-child(odd) {
            background: rgba(255,255,255,.075);
        }
        .team-roster-number {
            color: #D6A83A;
            font-weight: 950;
        }
        .team-roster-player {
            color: #FFFFFF;
            font-weight: 900;
            overflow-wrap: anywhere;
        }
        .team-roster-position {
            background: rgba(214,168,58,.14);
            border: 1px solid rgba(214,168,58,.24);
            border-radius: 999px;
            color: #F8FAFC;
            font-size: .76rem;
            font-weight: 950;
            justify-self: start;
            min-width: 2.4rem;
            padding: .2rem .45rem;
            text-align: center;
        }
        .team-roster-club {
            color: #CBD5E1;
            font-weight: 800;
            overflow-wrap: anywhere;
        }
        .team-roster-empty-message {
            background: rgba(255,255,255,.06);
            border: 1px solid rgba(255,255,255,.10);
            border-radius: 8px;
            color: #CBD5E1;
            font-weight: 850;
            padding: .9rem 1rem;
        }
        @media (max-width: 760px) {
            .team-roster-header {
                align-items: flex-start;
                flex-direction: column;
            }
            .team-roster-table {
                border: 0;
            }
            .team-roster-table-head {
                display: none;
            }
            .team-roster-row {
                border: 1px solid rgba(255,255,255,.10);
                border-radius: 8px;
                grid-template-columns: 3.4rem 1fr auto;
                margin-bottom: .55rem;
            }
            .team-roster-club {
                grid-column: 2 / -1;
            }
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
        [class*="st-key-open_country_"] button {
            min-height: 2.75rem;
            width: 100%;
        }
        .team-fixture-card {
            border: 1px solid rgba(255,255,255,.18);
            border-radius: 8px;
            background-size: cover;
            background-position: center;
            box-shadow: 0 16px 38px rgba(0,0,0,.24);
            cursor: pointer;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            min-height: 245px;
            overflow: hidden;
            padding: .95rem;
            transition: border-color .15s ease, box-shadow .15s ease, transform .15s ease;
        }
        .team-fixture-card-top, .team-fixture-card-bottom {
            color: #D6A83A;
            display: flex;
            font-size: .78rem;
            font-weight: 900;
            gap: .75rem;
            justify-content: space-between;
            text-shadow: 0 2px 10px rgba(0,0,0,.75);
            text-transform: uppercase;
        }
        .team-fixture-card-bottom.is-centered {
            justify-content: center;
            text-align: center;
        }
        .team-fixture-card-body {
            color: #FFFFFF;
            text-shadow: 0 3px 16px rgba(0,0,0,.9);
        }
        .team-fixture-teams {
            align-items: center;
            display: grid;
            font-size: 1.28rem;
            font-weight: 950;
            gap: .55rem;
            grid-template-columns: 1fr auto 1fr;
            line-height: 1.05;
            text-align: center;
        }
        .team-fixture-team {
            align-items: center;
            display: flex;
            flex-direction: column;
            gap: .42rem;
            min-width: 0;
        }
        .team-fixture-team span {
            overflow-wrap: anywhere;
        }
        .team-fixture-flag {
            aspect-ratio: 3 / 2;
            border: 1px solid rgba(255,255,255,.70);
            border-radius: 4px;
            box-shadow: 0 8px 16px rgba(0,0,0,.34);
            display: block;
            object-fit: cover;
            object-position: center;
            width: 34px;
        }
        .team-fixture-flag.flag-fallback {
            align-items: center;
            background: linear-gradient(135deg, rgba(214,168,58,.50), rgba(36,88,255,.28));
            color: #FFFFFF;
            display: grid;
            font-size: .58rem;
            font-weight: 950;
            justify-content: center;
            line-height: 1;
        }
        .team-fixture-teams strong {
            color: #D6A83A;
            font-size: .82rem;
        }
        .team-fixture-score {
            color: #f8fafc;
            font-weight: 900;
            margin-top: .8rem;
            text-align: center;
        }
        [class*="st-key-team_fixture_open_"] {
            height: 245px;
            margin-bottom: .9rem;
            margin-top: -245px;
            position: relative;
            z-index: 2;
        }
        [class*="st-key-team_fixture_open_"] button {
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
        [class*="st-key-team_fixture_open_"] button p {
            color: transparent !important;
        }
        .flag-fallback.hidden {
            display: none;
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
        .match-stage-badge {
            position: absolute;
            right: 1.25rem;
            top: 1.15rem;
            z-index: 1;
            background: rgba(5,5,5,.62);
            border: 1px solid rgba(214,168,58,.58);
            border-radius: 999px;
            color: #D6A83A;
            font-size: .82rem;
            font-weight: 950;
            padding: .42rem .72rem;
            text-transform: uppercase;
            text-shadow: 0 2px 10px rgba(0,0,0,.75);
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
            display: block;
            object-fit: cover;
            object-position: center;
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
