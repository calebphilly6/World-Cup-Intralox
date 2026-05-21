from __future__ import annotations

import base64
import html
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from src.database import fetch_df
from src.official_match_reference import normalize_team_key
from src.utils.team_names import display_team_name, team_lookup_keys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
WCQ_DATA_DIR = PROJECT_ROOT / "data" / "wcq"
WCQ_DATA_SCHEMA_VERSION = "2026-05-16-caf-runners-up"

CONFEDERATION_ORDER = ["AFC", "CAF", "CONCACAF", "CONMEBOL", "OFC", "UEFA"]
CONFEDERATION_LOGOS = {
    "AFC": PROJECT_ROOT / "assets" / "AFC.png",
    "CAF": PROJECT_ROOT / "assets" / "CAF.png",
    "CONCACAF": PROJECT_ROOT / "assets" / "Concacaf.png",
    "CONMEBOL": PROJECT_ROOT / "assets" / "CONMEBOL.png",
    "OFC": PROJECT_ROOT / "assets" / "OFC.png",
    "UEFA": PROJECT_ROOT / "assets" / "UEFA.png",
}

WCQ_FILES: dict[str, dict[str, Any]] = {
    "confederations": {
        "filename": "wcq_confederations.csv",
        "required": [
            "confederation_id",
            "confederation_name",
            "display_name",
            "region_description",
            "qualification_summary",
            "world_cup_slots",
            "playoff_slots",
            "style_key",
            "last_updated",
            "source_name",
            "source_url",
        ],
    },
    "rounds": {
        "filename": "wcq_rounds.csv",
        "required": [
            "round_id",
            "confederation_id",
            "round_order",
            "round_name",
            "round_type",
            "description",
            "start_date",
            "end_date",
            "teams_entered",
            "teams_advanced",
            "teams_eliminated",
            "teams_qualified",
            "source_name",
            "source_url",
        ],
    },
    "groups": {
        "filename": "wcq_groups.csv",
        "required": ["group_id", "round_id", "confederation_id", "group_name", "group_order", "notes"],
    },
    "standings": {
        "filename": "wcq_group_standings.csv",
        "required": [
            "standing_id",
            "group_id",
            "round_id",
            "confederation_id",
            "team_id",
            "team_name",
            "fifa_code",
            "flag_code",
            "fifa_rank",
            "rank_snapshot_date",
            "position",
            "played",
            "wins",
            "draws",
            "losses",
            "goals_for",
            "goals_against",
            "goal_difference",
            "points",
            "status",
            "advanced_to_round_id",
            "qualified_for_world_cup",
            "eliminated_in_this_round",
            "notes",
            "source_name",
            "source_url",
        ],
    },
    "matches": {
        "filename": "wcq_matches.csv",
        "required": [
            "match_id",
            "round_id",
            "confederation_id",
            "group_id",
            "bracket_id",
            "match_order",
            "date",
            "home_team_id",
            "home_team_name",
            "home_fifa_code",
            "home_flag_code",
            "home_fifa_rank",
            "away_team_id",
            "away_team_name",
            "away_fifa_code",
            "away_flag_code",
            "away_fifa_rank",
            "home_score",
            "away_score",
            "extra_time",
            "penalties",
            "winning_team_id",
            "result_notes",
            "source_name",
            "source_url",
        ],
    },
    "playoff_ties": {
        "filename": "wcq_playoff_ties.csv",
        "required": [
            "tie_id",
            "round_id",
            "confederation_id",
            "round_name",
            "team1_id",
            "team1_name",
            "team1_fifa_code",
            "team1_flag_code",
            "team1_fifa_rank",
            "team2_id",
            "team2_name",
            "team2_fifa_code",
            "team2_flag_code",
            "team2_fifa_rank",
            "aggregate_score",
            "leg1_score_team1_first",
            "leg2_score_team1_first",
            "winner_team_id",
            "loser_team_id",
            "notes",
            "source_name",
            "source_url",
        ],
    },
    "runners_up_ranking": {
        "filename": "wcq_runners_up_ranking.csv",
        "required": [
            "runner_up_rank",
            "group_name",
            "team_id",
            "team_name",
            "fifa_code",
            "flag_code",
            "fifa_rank",
            "rank_snapshot_date",
            "played_counting_results",
            "wins",
            "draws",
            "losses",
            "goals_for",
            "goals_against",
            "goal_difference",
            "points",
            "status",
            "advanced_to_round_id",
            "notes",
            "source_name",
            "source_url",
        ],
    },
    "brackets": {
        "filename": "wcq_brackets.csv",
        "required": [
            "bracket_id",
            "round_id",
            "confederation_id",
            "bracket_name",
            "bracket_stage",
            "match_id",
            "next_match_id",
            "slot_label",
            "winner_advances_to",
            "loser_eliminated",
            "notes",
        ],
    },
    "eliminated": {
        "filename": "wcq_eliminated_by_round.csv",
        "required": [
            "elimination_id",
            "confederation_id",
            "round_id",
            "team_id",
            "team_name",
            "fifa_code",
            "flag_code",
            "fifa_rank",
            "rank_snapshot_date",
            "elimination_reason",
            "final_position",
            "notes",
            "source_name",
            "source_url",
        ],
    },
    "qualified": {
        "filename": "wcq_qualified_teams.csv",
        "required": [
            "team_id",
            "team_name",
            "fifa_code",
            "flag_code",
            "confederation_id",
            "fifa_rank",
            "rank_snapshot_date",
            "qualification_method",
            "qualification_round",
            "qualification_date",
            "qualified_as",
            "notes",
            "source_name",
            "source_url",
        ],
    },
    "sources": {
        "filename": "wcq_sources.csv",
        "required": ["source_id", "confederation_id", "source_name", "source_url", "last_checked", "notes"],
    },
}

CONFEDERATION_STYLES = {
    "AFC": {
        "primary": "#002395",
        "secondary": "#FFC72C",
        "accent": "#FFC72C",
        "surface": "rgba(0,35,149,.20)",
        "glow": "rgba(255,199,44,.24)",
    },
    "CAF": {
        "primary": "#189E4B",
        "secondary": "#F8E825",
        "accent": "#F8E825",
        "surface": "rgba(24,158,75,.20)",
        "glow": "rgba(248,232,37,.22)",
    },
    "CONCACAF": {
        "primary": "#0B1220",
        "secondary": "#DABC73",
        "accent": "#DABC73",
        "surface": "rgba(11,18,32,.26)",
        "glow": "rgba(218,188,115,.20)",
    },
    "CONMEBOL": {
        "primary": "#005CA4",
        "secondary": "#FFFFFF",
        "accent": "#F6C453",
        "surface": "rgba(0,92,164,.18)",
        "glow": "rgba(255,255,255,.20)",
    },
    "OFC": {
        "primary": "#1A3374",
        "secondary": "#40B93C",
        "accent": "#D9E70C",
        "surface": "rgba(26,51,116,.20)",
        "glow": "rgba(64,185,60,.20)",
    },
    "UEFA": {
        "primary": "#00088E",
        "secondary": "#F61225",
        "accent": "#60A5FA",
        "surface": "rgba(0,8,142,.22)",
        "glow": "rgba(246,18,37,.18)",
    },
}

STATUS_LABELS = {
    "qualified": "Qualified",
    "advanced": "Advanced",
    "eliminated": "Eliminated",
    "playoff": "Playoff",
    "playoff_loss": "Playoff",
    "host": "Host",
    "withdrew": "Withdrew",
    "suspended": "Suspended",
    "did_not_enter": "Did not enter",
    "active": "Active",
    "unknown": "Unknown",
}


def render() -> None:
    st.title("WCQ")
    _styles()

    data = load_wcq_data(WCQ_DATA_SCHEMA_VERSION, _wcq_data_signature())
    _show_data_messages(data)

    sections = [*CONFEDERATION_ORDER, "Inter-Confederation Playoffs", "Qualified Teams"]
    selected_section = _render_wcq_section_selector(sections)
    if selected_section in CONFEDERATION_ORDER:
        render_confederation_tab(selected_section, data)
    elif selected_section == "Inter-Confederation Playoffs":
        render_inter_confederation_playoffs(data)
    else:
        render_qualified_teams(data)


def _render_wcq_section_selector(sections: list[str]) -> str:
    selected = st.session_state.get("wcq_section_selector", sections[0])
    if selected not in sections:
        selected = sections[0]
    columns = st.columns(len(sections), gap="small")
    for column, section in zip(columns, sections):
        selected_suffix = "_selected" if section == selected else ""
        with column:
            with st.container(key=f"wcq_section_tab_{_safe_key(section)}{selected_suffix}"):
                if st.button(section, key=f"wcq_section_button_{_safe_key(section)}", use_container_width=True):
                    st.session_state["wcq_section_selector"] = section
                    st.rerun()
    return selected


def load_wcq_data(_schema_version: str = WCQ_DATA_SCHEMA_VERSION, _data_signature: tuple[tuple[str, int, int], ...] = ()) -> dict[str, Any]:
    payload: dict[str, Any] = {"missing_files": [], "column_warnings": []}
    for key, spec in WCQ_FILES.items():
        path = WCQ_DATA_DIR / spec["filename"]
        required_columns = list(spec["required"])
        if not path.exists():
            payload[key] = pd.DataFrame(columns=required_columns)
            payload["missing_files"].append(spec["filename"])
            continue
        try:
            frame = pd.read_csv(path, dtype=str, keep_default_na=False)
        except Exception as exc:
            frame = pd.DataFrame(columns=required_columns)
            payload["column_warnings"].append(f"{spec['filename']}: could not be read ({exc})")
        missing_columns = [column for column in required_columns if column not in frame.columns]
        if missing_columns:
            payload["column_warnings"].append(f"{spec['filename']}: added missing columns {', '.join(missing_columns)}")
            for column in missing_columns:
                frame[column] = ""
        payload[key] = frame.fillna("")
    _apply_global_fifa_rankings(payload)
    _apply_common_team_names(payload)
    return payload


def _apply_global_fifa_rankings(payload: dict[str, Any]) -> None:
    rankings = _latest_global_fifa_ranking_lookup()
    for key in ["standings", "runners_up_ranking", "eliminated", "qualified"]:
        frame = _wcq_frame(payload, key)
        if frame.empty or "team_name" not in frame.columns:
            continue
        payload[key] = _with_canonical_rank_columns(frame, rankings, [("team_name", "fifa_rank", "rank_snapshot_date")])
    for key in ["matches"]:
        frame = _wcq_frame(payload, key)
        if frame.empty:
            continue
        payload[key] = _with_canonical_rank_columns(
            frame,
            rankings,
            [
                ("home_team_name", "home_fifa_rank", "home_rank_snapshot_date"),
                ("away_team_name", "away_fifa_rank", "away_rank_snapshot_date"),
            ],
        )
    for key in ["playoff_ties"]:
        frame = _wcq_frame(payload, key)
        if frame.empty:
            continue
        payload[key] = _with_canonical_rank_columns(
            frame,
            rankings,
            [
                ("team1_name", "team1_fifa_rank", "team1_rank_snapshot_date"),
                ("team2_name", "team2_fifa_rank", "team2_rank_snapshot_date"),
                ("team_1_name", "team_1_fifa_rank", "team_1_rank_snapshot_date"),
                ("team_2_name", "team_2_fifa_rank", "team_2_rank_snapshot_date"),
                ("home_team_name", "home_fifa_rank", "home_rank_snapshot_date"),
                ("away_team_name", "away_fifa_rank", "away_rank_snapshot_date"),
            ],
        )


def _with_canonical_rank_columns(
    frame: pd.DataFrame,
    rankings: dict[str, dict[str, str]],
    team_rank_columns: list[tuple[str, str, str]],
) -> pd.DataFrame:
    updated = frame.copy()
    for team_column, rank_column, date_column in team_rank_columns:
        if team_column not in updated.columns or rank_column not in updated.columns:
            continue
        updated[rank_column] = updated[team_column].apply(lambda value: rankings.get(_ranking_lookup_key(value), {}).get("rank", ""))
        if date_column in updated.columns:
            updated[date_column] = updated[team_column].apply(lambda value: rankings.get(_ranking_lookup_key(value), {}).get("ranking_date", ""))
    return updated


def _latest_global_fifa_ranking_lookup() -> dict[str, dict[str, str]]:
    try:
        rankings = fetch_df(
            """
            SELECT team_name, ranking_date, rank
            FROM global_fifa_rankings
            WHERE ranking_date = (SELECT MAX(ranking_date) FROM global_fifa_rankings)
            """
        )
    except Exception:
        return {}
    lookup: dict[str, dict[str, str]] = {}
    for _, row in rankings.fillna("").iterrows():
        rank = _clean_rank_value(row.get("rank", ""))
        if not rank:
            continue
        value = {
            "rank": rank,
            "ranking_date": str(row.get("ranking_date", "")).strip(),
        }
        team_name = str(row.get("team_name", "")).strip()
        for key in _ranking_lookup_keys(team_name):
            lookup[key] = value
    return lookup


def _ranking_lookup_keys(team_name: str) -> set[str]:
    key = _ranking_lookup_key(team_name)
    keys = {key} if key else set()
    keys.update(team_lookup_keys(team_name))
    aliases = {
        "cabo verde": "cape verde",
        "cape verde": "cabo verde",
        "congo dr": "dr congo",
        "dr congo": "congo dr",
        "democratic republic of the congo": "dr congo",
        "czechia": "czech republic",
        "czech republic": "czechia",
        "ir iran": "iran",
        "iran": "ir iran",
        "korea republic": "south korea",
        "south korea": "korea republic",
        "turkiye": "turkey",
        "turkey": "turkiye",
        "türkiye": "turkiye",
        "usa": "united states",
        "united states": "usa",
        "united states of america": "usa",
    }
    for left, right in aliases.items():
        left_key = _ranking_lookup_key(left)
        right_key = _ranking_lookup_key(right)
        if keys & {left_key, right_key}:
            keys.update({left_key, right_key})
    return keys


def _ranking_lookup_key(value: Any) -> str:
    return normalize_team_key(str(value or ""))


def _clean_rank_value(value: Any) -> str:
    if pd.isna(value) or str(value).strip() == "":
        return ""
    numeric = pd.to_numeric(value, errors="coerce")
    if not pd.isna(numeric):
        return str(int(numeric))
    return str(value).strip()


def _apply_common_team_names(payload: dict[str, Any]) -> None:
    for key, value in list(payload.items()):
        if not isinstance(value, pd.DataFrame) or value.empty:
            continue
        frame = value.copy()
        changed = False
        for column in [
            "team_name",
            "home_team_name",
            "away_team_name",
            "team1_name",
            "team2_name",
            "team_1_name",
            "team_2_name",
            "winner_team_name",
            "loser_team_name",
        ]:
            if column in frame.columns:
                frame[column] = frame[column].apply(display_team_name)
                changed = True
        if changed:
            payload[key] = frame


def _wcq_data_signature() -> tuple[tuple[str, int, int], ...]:
    if not WCQ_DATA_DIR.exists():
        return ()
    signature: list[tuple[str, int, int]] = []
    for path in sorted(WCQ_DATA_DIR.glob("*.csv")):
        try:
            stat = path.stat()
        except OSError:
            continue
        signature.append((path.name, stat.st_size, stat.st_mtime_ns))
    return tuple(signature)


def render_confederation_tab(confederation_id: str, data: dict[str, Any]) -> None:
    confed = _confederation_row(confederation_id, data)
    render_confederation_header(confederation_id, data, confed)

    rounds = _confederation_rows(data["rounds"], confederation_id)
    rounds = _without_inter_confederation_rounds(rounds)
    if rounds.empty:
        st.info(f"Add round data for {confederation_id} to build this qualification journey.")
        render_qualified_teams(data, confederation_id)
        return

    render_round_tabs(confederation_id, data, rounds)


def render_confederation_header(confederation_id: str, data: dict[str, Any], confed: pd.Series | None = None) -> None:
    style = get_confederation_style(confederation_id)
    confed = confed if confed is not None else _confederation_row(confederation_id, data)
    name = _field(confed, "display_name", confederation_id)
    summary = _confederation_short_summary(confederation_id, data, confed)
    region = _field(confed, "region_description", "")
    if confederation_id.upper() == "CONMEBOL":
        name = "CONMEBOL"
        region = "South America"
    if confederation_id.upper() == "OFC":
        region = "Oceania and Pacific"
    kicker_markup = f'<div class="wcq-kicker">{html.escape(region)}</div>' if region else ""
    logo_markup = _confederation_logo_markup(confederation_id)
    st.markdown(
        f"""
        <section class="wcq-hero" style="{_style_vars(style)}">
          {logo_markup}
          <div>
            {kicker_markup}
            <h2>{html.escape(name)}</h2>
            <p>{html.escape(summary)}</p>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _confederation_logo_markup(confederation_id: str) -> str:
    confed = str(confederation_id).upper()
    logo_path = CONFEDERATION_LOGOS.get(confed)
    if not logo_path or not logo_path.exists():
        return f'<div class="wcq-hero-badge wcq-hero-badge-text">{html.escape(confed)}</div>'
    encoded = base64.b64encode(logo_path.read_bytes()).decode("ascii")
    mime_type = "image/jpeg" if logo_path.suffix.lower() in {".jpg", ".jpeg"} else "image/png"
    logo_class = f"wcq-logo-{_safe_key(confed)}"
    return (
        f'<div class="wcq-hero-badge wcq-hero-badge-logo {logo_class}">'
        f'<img src="data:{mime_type};base64,{encoded}" alt="{html.escape(confed)} logo">'
        "</div>"
    )


def render_round_tabs(
    confederation_id: str,
    data: dict[str, Any],
    rounds: pd.DataFrame,
    query: str = "",
    statuses: list[str] | None = None,
    round_filter: list[str] | None = None,
) -> None:
    rounds = rounds.copy()
    rounds["_order"] = pd.to_numeric(rounds["round_order"], errors="coerce").fillna(999)
    rounds = rounds.sort_values(["_order", "round_name"])
    if round_filter:
        rounds = rounds[rounds["round_id"].isin(round_filter)]
    round_rows = [row for _, row in rounds.iterrows()]
    options = [
        {
            "id": str(row["round_id"]),
            "label": _display_round_name(row),
        }
        for index, row in enumerate(round_rows)
    ]
    options.append({"id": "__qualified__", "label": "Qualified"})
    selected = _render_round_selector(confederation_id, options)
    if selected == "__qualified__":
        render_qualified_teams(data, confederation_id, query=query)
        return
    selected_rows = [row for row in round_rows if str(row["round_id"]) == selected]
    if selected_rows:
        render_round(confederation_id, data, selected_rows[0], query, statuses or [])


def _render_round_selector(confederation_id: str, options: list[dict[str, str]]) -> str:
    default = options[0]["id"] if options else ""
    state_key = f"wcq_round_selector_{_safe_key(confederation_id)}"
    selected = st.session_state.get(state_key, default)
    option_ids = {option["id"] for option in options}
    if selected not in option_ids:
        selected = default
    style = get_confederation_style(confederation_id)
    st.markdown(
        f"""
        <div class="wcq-round-tab-shell" style="{_style_vars(style)}">
          <div class="wcq-round-tab-line"></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    columns = st.columns(len(options), gap="small")
    for column, option in zip(columns, options):
        selected_suffix = "_selected" if option["id"] == selected else ""
        with column:
            with st.container(key=f"wcq_round_tab_{_safe_key(confederation_id)}_{_safe_key(option['id'])}{selected_suffix}"):
                if st.button(option["label"], key=f"wcq_round_button_{_safe_key(confederation_id)}_{_safe_key(option['id'])}", use_container_width=True):
                    st.session_state[state_key] = option["id"]
                    st.rerun()
    return selected


def render_round(
    confederation_id: str,
    data: dict[str, Any],
    round_row: pd.Series,
    query: str = "",
    statuses: list[str] | None = None,
) -> None:
    round_id = str(round_row["round_id"])
    round_type = str(round_row["round_type"] or "other").strip().lower()
    _round_intro(round_row)
    if round_type == "host_auto":
        render_qualified_teams(data, confederation_id, qualification_round=_field(round_row, "round_name", ""))
    elif round_type in {"group_stage", "league_table"}:
        render_group_stage(data, round_id, confederation_id, query, statuses or [])
    elif round_type in {"knockout_bracket", "two_leg_playoff", "single_match_playoff"}:
        render_bracket(data, round_id, confederation_id, query, statuses or [])
    else:
        render_flexible_round(data, round_id, confederation_id, query, statuses or [])
    render_eliminated_list(data, round_id, confederation_id, query=query)


def render_group_stage(
    data: dict[str, Any],
    round_id: str,
    confederation_id: str,
    query: str = "",
    statuses: list[str] | None = None,
) -> None:
    groups = data["groups"]
    standings = _filter_team_rows(_round_rows(data["standings"], round_id, confederation_id), query, statuses or [])
    round_groups = _round_rows(groups, round_id, confederation_id).copy()
    if confederation_id.upper() == "CONCACAF" and round_id == "CONCACAF_R3":
        round_groups = round_groups[~round_groups.get("group_id", pd.Series(dtype=str)).astype(str).eq("CONCACAF_R3_RUNNER_UPS")]
        standings = standings[~standings.get("group_id", pd.Series(dtype=str)).astype(str).eq("CONCACAF_R3_RUNNER_UPS")]
    if round_groups.empty and standings.empty:
        st.info("Add group and standings rows for this round to show tables.")
    else:
        if round_groups.empty:
            round_groups = pd.DataFrame(
                [{"group_id": group_id, "group_name": group_id, "group_order": index + 1} for index, group_id in enumerate(standings["group_id"].dropna().unique())]
            )
        round_groups["_order"] = pd.to_numeric(round_groups.get("group_order", ""), errors="coerce").fillna(999)
        for _, group in round_groups.sort_values(["_order", "group_name"]).iterrows():
            group_rows = standings[standings["group_id"].eq(group.get("group_id", ""))].copy()
            group_rows["_position"] = pd.to_numeric(group_rows.get("position", ""), errors="coerce").fillna(999)
            group_rows = group_rows.sort_values(["_position", "team_name"])
            st.markdown(f'<div class="wcq-section-title">{html.escape(str(group.get("group_name") or "Group"))}</div>', unsafe_allow_html=True)
            if group_rows.empty:
                st.info("No teams match the current filters for this group.")
                continue
            _render_standings_cards(group_rows, confederation_id)
    if not (confederation_id.upper() == "CONCACAF" and round_id == "CONCACAF_R3"):
        render_runners_up_ranking(data, round_id, confederation_id, query, statuses or [])


def render_league_table(data: dict[str, Any], round_id: str, confederation_id: str) -> None:
    render_group_stage(data, round_id, confederation_id)


def render_bracket(
    data: dict[str, Any],
    round_id: str,
    confederation_id: str,
    query: str = "",
    statuses: list[str] | None = None,
) -> None:
    matches = _filter_match_rows(_round_rows(_wcq_frame(data, "matches"), round_id, confederation_id), query)
    ties = _filter_tie_rows(_round_rows(_wcq_frame(data, "playoff_ties"), round_id, confederation_id), query)
    brackets = _round_rows(_wcq_frame(data, "brackets"), round_id, confederation_id)
    ties = _without_duplicate_ties(ties, matches)
    if not ties.empty and _is_two_leg_round(round_id, confederation_id, data):
        render_playoff_ties(ties, confederation_id)
        return
    if matches.empty and ties.empty:
        st.info("Add match or playoff-tie rows for this playoff or bracket round to show the matchup view.")
        return
    if not matches.empty and _has_bracket_shape(matches, brackets):
        render_tournament_bracket(matches, brackets, confederation_id)
        if not ties.empty:
            render_playoff_ties(ties, confederation_id)
        return
    if not ties.empty:
        render_playoff_ties(ties, confederation_id)
    if not matches.empty:
        matches["_order"] = pd.to_numeric(matches.get("match_order", ""), errors="coerce").fillna(999)
        for _, match in matches.sort_values(["_order", "date"]).iterrows():
            _render_match_card(match, confederation_id)


def render_playoff_ties(ties: pd.DataFrame, confederation_id: str) -> None:
    for _, tie in ties.sort_values(["tie_id"]).iterrows():
        _render_tie_card(tie, confederation_id)


def render_tournament_bracket(matches: pd.DataFrame, brackets: pd.DataFrame, confederation_id: str) -> None:
    bracket_matches = _matches_with_bracket_stage(matches, brackets)
    if bracket_matches.empty:
        return
    if "bracket_id" not in bracket_matches.columns:
        bracket_matches["bracket_id"] = ""
    bracket_matches["_bracket_id"] = bracket_matches["bracket_id"].replace("", "bracket").fillna("bracket")
    for bracket_id in _ordered_bracket_ids(bracket_matches):
        rows = bracket_matches[bracket_matches["_bracket_id"].eq(bracket_id)].copy()
        st.markdown(_tournament_bracket_html(rows, brackets, bracket_id, confederation_id), unsafe_allow_html=True)


def render_runners_up_ranking(
    data: dict[str, Any],
    round_id: str,
    confederation_id: str,
    query: str = "",
    statuses: list[str] | None = None,
) -> None:
    rows = _filter_team_rows(_confederation_rows(_wcq_frame(data, "runners_up_ranking"), confederation_id), query, statuses or [])
    if rows.empty:
        return
    rows["_rank"] = pd.to_numeric(rows.get("runner_up_rank", ""), errors="coerce").fillna(999)
    rows = rows.sort_values(["_rank", "team_name"])
    st.markdown('<div class="wcq-section-title">Runner-up Ranking</div>', unsafe_allow_html=True)
    _render_runners_up_table(rows, confederation_id)


def render_flexible_round(
    data: dict[str, Any],
    round_id: str,
    confederation_id: str,
    query: str = "",
    statuses: list[str] | None = None,
) -> None:
    standings = _filter_team_rows(_round_rows(data["standings"], round_id, confederation_id), query, statuses or [])
    matches = _filter_match_rows(_round_rows(_wcq_frame(data, "matches"), round_id, confederation_id), query)
    ties = _filter_tie_rows(_round_rows(_wcq_frame(data, "playoff_ties"), round_id, confederation_id), query)
    if not standings.empty:
        render_group_stage(data, round_id, confederation_id, query, statuses or [])
    if not matches.empty or not ties.empty:
        render_bracket(data, round_id, confederation_id, query, statuses or [])
    if standings.empty and matches.empty and ties.empty:
        st.info("This round can display standings, matches, bracket notes, or all three once local data is added.")


def render_eliminated_list(data: dict[str, Any], round_id: str, confederation_id: str, query: str = "") -> None:
    eliminated = _round_rows(data["eliminated"], round_id, confederation_id)
    eliminated = _filter_team_rows(eliminated, query, [])
    st.markdown('<div class="wcq-section-title eliminated">Eliminated in this round</div>', unsafe_allow_html=True)
    if eliminated.empty:
        st.info("No eliminated teams are recorded for this round yet.")
        return
    _team_card_grid(eliminated, confederation_id, mode="eliminated")


def render_qualified_teams(
    data: dict[str, Any],
    confederation_id: str | None = None,
    query: str = "",
    qualification_round: str = "",
) -> None:
    qualified = data["qualified"].copy()
    if confederation_id:
        qualified = _confederation_rows(qualified, confederation_id)
        if qualification_round:
            qualified = qualified[qualified["qualification_round"].astype(str).str.lower().eq(qualification_round.lower())]
        st.markdown('<div class="wcq-section-title">Qualified for the World Cup</div>', unsafe_allow_html=True)
    qualified = _filter_team_rows(qualified, query, [])
    if qualified.empty:
        st.info("No qualified teams are recorded yet.")
        return
    for confed, rows in _ordered_confederation_groups(qualified):
        if not confederation_id:
            st.markdown(f'<div class="wcq-section-title">{html.escape(confed)}</div>', unsafe_allow_html=True)
        _team_card_grid(rows, confed, mode="qualified")


def render_inter_confederation_playoffs(data: dict[str, Any]) -> None:
    st.subheader("Inter-Confederation Playoffs")

    matches = _canonical_inter_confederation_matches(data)
    if matches.empty:
        st.info("No inter-confederation playoff matches are recorded yet.")
        return

    for path_name in ["Path A", "Path B"]:
        path_matches = matches[matches["_icpo_path"].eq(path_name)].copy()
        if path_matches.empty:
            st.info(f"No matches recorded for {path_name} yet.")
            continue
        path_matches["_stage_order"] = path_matches["_icpo_stage"].map({"Semi-Final": 1, "Final": 2}).fillna(99)
        path_matches["_date"] = pd.to_datetime(path_matches.get("date", ""), errors="coerce")
        st.markdown(_inter_confederation_path_html(path_name, path_matches), unsafe_allow_html=True)

    eliminated = _inter_confederation_eliminated(data)
    if not eliminated.empty:
        st.markdown('<div class="wcq-section-title eliminated">Eliminated in this tournament</div>', unsafe_allow_html=True)
        _team_card_grid(eliminated, "CONCACAF", mode="eliminated")


def render_team_badge_or_card(team_row: pd.Series, confederation_id: str, mode: str = "default") -> str:
    status = _team_status(team_row, mode)
    style = get_status_style(status, confederation_id)
    name = _field(team_row, "team_name", "Team TBD")
    fifa_code = _field(team_row, "fifa_code", "TBD")
    rank = _rank_text(team_row)
    detail = _team_detail(team_row, mode)
    flag = _flag_markup(team_row, fifa_code)
    notes = _field(team_row, "notes", "")
    notes_markup = f"<p>{html.escape(notes)}</p>" if notes else ""
    status_markup = "" if mode == "eliminated" else f'<div class="wcq-status-pill">{html.escape(_status_label(team_row, status))}</div>'
    return (
        f'<article class="wcq-team-card {html.escape(status)}" style="{_status_vars(style)}">'
        f'<div class="wcq-team-top">{flag}</div>'
        f'<h4>{html.escape(name)}</h4>'
        f'<div class="wcq-rank">{html.escape(rank)}</div>'
        f'{status_markup}'
        '</article>'
    )


def get_status_style(status: str, confederation_id: str) -> dict[str, str]:
    confed = get_confederation_style(confederation_id)
    confederation_id = str(confederation_id).upper()
    status = str(status or "unknown").lower()
    if status in {"qualified", "host"}:
        return {"border": confed["secondary"], "background": confed["surface"], "accent": confed["secondary"], "shadow": confed["glow"]}
    if status == "advanced":
        if confederation_id == "AFC":
            return {"border": "#22C55E", "background": "rgba(22,101,52,.24)", "accent": "#86EFAC", "shadow": "rgba(34,197,94,.18)"}
        return {"border": confed["secondary"], "background": confed["surface"], "accent": confed["secondary"], "shadow": confed["glow"]}
    if status in {"playoff", "playoff_loss"}:
        return {"border": "#F59E0B", "background": "rgba(245,158,11,.16)", "accent": "#F59E0B", "shadow": "rgba(245,158,11,.18)"}
    if status == "eliminated":
        return {"border": "#EF4444", "background": "rgba(127,29,29,.20)", "accent": "#FCA5A5", "shadow": "rgba(239,68,68,.14)"}
    if status in {"withdrew", "suspended", "did_not_enter"}:
        return {"border": "#94A3B8", "background": "rgba(148,163,184,.13)", "accent": "#CBD5E1", "shadow": "rgba(148,163,184,.10)"}
    return {"border": confed["primary"], "background": "rgba(255,255,255,.075)", "accent": confed["secondary"], "shadow": confed["glow"]}


def get_confederation_style(confederation_id: str) -> dict[str, str]:
    return CONFEDERATION_STYLES.get(str(confederation_id).upper(), CONFEDERATION_STYLES["UEFA"])


def _round_intro(round_row: pd.Series) -> None:
    date_range = _format_round_date_range(_field(round_row, "start_date", ""), _field(round_row, "end_date", ""))
    date_markup = f'<div class="wcq-round-date">{html.escape(date_range)}</div>' if date_range else ""
    st.markdown(
        f"""
        <section class="wcq-round-intro">
          <div>
            <div class="wcq-kicker">{html.escape(_display_round_type(round_row))}</div>
            <h3>{html.escape(_display_round_name(round_row))}</h3>
            {date_markup}
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _render_standings_cards(rows: pd.DataFrame, confederation_id: str) -> None:
    header = """
        <div class="wcq-table-row wcq-table-head">
          <span>Pos</span><span>Team</span><span>FIFA Rank</span><span>P</span><span>W</span><span>D</span><span>L</span><span>GD</span><span>Pts</span><span>Status</span>
        </div>
    """
    body = "".join(_standings_row(row, confederation_id) for _, row in rows.iterrows())
    st.markdown(f'<div class="wcq-table">{header}{body}</div>', unsafe_allow_html=True)


def _standings_row(row: pd.Series, confederation_id: str) -> str:
    status = _team_status(row)
    style = get_status_style(status, confederation_id)
    status_label = _status_label(row, status)
    return (
        f'<div class="wcq-table-row" style="{_status_vars(style)}">'
        f'<span>{html.escape(_field(row, "position", "-"))}</span>'
        f'<span class="wcq-table-team">{_flag_markup(row, _field(row, "fifa_code", ""))}<strong>{html.escape(_field(row, "team_name", "Team TBD"))}</strong></span>'
        f'<span>{html.escape(_rank_number_text(row))}</span>'
        f'<span>{html.escape(_field(row, "played", "0"))}</span>'
        f'<span>{html.escape(_field(row, "wins", "0"))}</span>'
        f'<span>{html.escape(_field(row, "draws", "0"))}</span>'
        f'<span>{html.escape(_field(row, "losses", "0"))}</span>'
        f'<span>{html.escape(_field(row, "goal_difference", "0"))}</span>'
        f'<span>{html.escape(_field(row, "points", "0"))}</span>'
        f'<span class="wcq-status-text">{html.escape(status_label)}</span>'
        '</div>'
    )


def _render_runners_up_table(rows: pd.DataFrame, confederation_id: str) -> None:
    header = """
        <div class="wcq-runner-row wcq-table-head">
          <span>Rank</span><span>Team</span><span>FIFA Rank</span><span>P</span><span>W</span><span>D</span><span>L</span><span>GD</span><span>Pts</span><span>Status</span>
        </div>
    """
    body = "".join(_runner_up_row(row, confederation_id) for _, row in rows.iterrows())
    st.markdown(f'<div class="wcq-table wcq-runner-table">{header}{body}</div>', unsafe_allow_html=True)


def _runner_up_row(row: pd.Series, confederation_id: str) -> str:
    status = _team_status(row)
    style = get_status_style(status, confederation_id)
    status_label = _status_label(row, status)
    return (
        f'<div class="wcq-runner-row" style="{_status_vars(style)}">'
        f'<span>{html.escape(_field(row, "runner_up_rank", "-"))}</span>'
        f'<span class="wcq-table-team">{_flag_markup(row, _field(row, "fifa_code", ""))}<strong>{html.escape(_field(row, "team_name", "Team TBD"))}</strong></span>'
        f'<span>{html.escape(_rank_number_text(row))}</span>'
        f'<span>{html.escape(_field(row, "played_counting_results", "0"))}</span>'
        f'<span>{html.escape(_field(row, "wins", "0"))}</span>'
        f'<span>{html.escape(_field(row, "draws", "0"))}</span>'
        f'<span>{html.escape(_field(row, "losses", "0"))}</span>'
        f'<span>{html.escape(_field(row, "goal_difference", "0"))}</span>'
        f'<span>{html.escape(_field(row, "points", "0"))}</span>'
        f'<span class="wcq-status-text">{html.escape(status_label)}</span>'
        '</div>'
    )


def _status_label(row: pd.Series, status: str) -> str:
    status = str(status or "unknown").lower()
    next_round = _field(row, "advanced_to_round_id", "")
    notes = _field(row, "notes", "")
    if status == "playoff" and _field(row, "round_id", "") == "UEFA_R1" and next_round == "UEFA_R2":
        return "Advanced"
    if status in {"playoff", "playoff_loss"} and (
        "icpo" in next_round.lower()
        or "interconfed" in next_round.lower()
        or "inter-confederation" in notes.lower()
        or "inter confederation" in notes.lower()
    ):
        return "Inter-confederation playoff"
    return STATUS_LABELS.get(status, status.title())


def _render_match_card(match: pd.Series, confederation_id: str) -> None:
    winning_id = _field(match, "winning_team_id", "")
    result = _field(match, "result", "").lower()
    home_status = "advanced" if winning_id and winning_id == _field(match, "home_team_id", "") else "unknown"
    away_status = "advanced" if winning_id and winning_id == _field(match, "away_team_id", "") else "unknown"
    if not winning_id and result in {"home_win", "away_win"}:
        home_status = "advanced" if result == "home_win" else "unknown"
        away_status = "advanced" if result == "away_win" else "unknown"
    score = _scoreline(match)
    date = _field(match, "date", "")
    meta_markup = f'<div class="wcq-match-meta"><span>{html.escape(date)}</span></div>' if date else ""
    st.markdown(
        f"""
        <article class="wcq-match-card">
          {meta_markup}
          <div class="wcq-matchup">
            {_match_team(match, 'home', home_status, confederation_id)}
            <strong>{html.escape(score)}</strong>
            {_match_team(match, 'away', away_status, confederation_id)}
          </div>
        </article>
        """,
        unsafe_allow_html=True,
    )


def _bracket_match_card(match: pd.Series, confederation_id: str) -> str:
    home_status = _bracket_side_status(match, "home")
    away_status = _bracket_side_status(match, "away")
    penalties = _penalty_text(match)
    penalties_markup = f'<div class="wcq-bracket-score">{html.escape(penalties)}</div>' if penalties else ""
    advancement_markup = _bracket_advancement_markup(match)
    return (
        '<article class="wcq-bracket-card">'
        f'{_bracket_team_line(match, "home", home_status, confederation_id)}'
        f'{penalties_markup}'
        f'{_bracket_team_line(match, "away", away_status, confederation_id)}'
        f'{advancement_markup}'
        '</article>'
    )


def _bracket_advancement_markup(match: pd.Series) -> str:
    notes = _bracket_advancement_notes(match)
    if not notes:
        return ""
    return "".join(
        f'<div class="wcq-bracket-note {html.escape(kind)}">{html.escape(text)}</div>'
        for kind, text in notes
    )


def _bracket_side_status(match: pd.Series, side: str) -> str:
    winning_id = _field(match, "winning_team_id", "")
    side_id = _field(match, f"{side}_team_id", "")
    side_name = _field(match, f"{side}_team_name", "")
    notes = _field(match, "result_notes", _field(match, "notes", "")).lower()
    side_name_lower = side_name.lower()
    if winning_id and side_id and winning_id == side_id:
        if side_name_lower and side_name_lower in notes and "qualified directly" in notes:
            return "qualified"
        return "advanced"
    return "unknown"


def _bracket_advancement_note(match: pd.Series) -> str:
    notes = _bracket_advancement_notes(match)
    return " | ".join(text for _, text in notes)


def _bracket_advancement_notes(match: pd.Series) -> list[tuple[str, str]]:
    notes = _field(match, "result_notes", _field(match, "notes", "")).lower()
    match_id = _field(match, "match_id", "")
    if match_id == "caf_po_final":
        return [("playoff-note", "DR Congo advances to Inter-Confederation Playoffs")]
    if match_id == "ofc_r1_m3":
        return [("advanced-note", "Samoa advances to the Second Round")]
    if match_id == "ofc_r3_final":
        return [
            ("world-cup-note", "New Zealand advances to the World Cup"),
            ("playoff-note", "New Caledonia advances to Inter-Confederation Playoffs"),
        ]
    if match_id.startswith("UEFA_R2_PATH_") and match_id.endswith("_FINAL"):
        winner_name = _match_winner_name(match)
        if winner_name:
            return [("world-cup-note", f"{winner_name} advances to the World Cup")]
    if "advanced to the inter-confederation playoff" not in notes:
        return []
    for side in ("home", "away"):
        team_name = _field(match, f"{side}_team_name", "")
        if team_name and team_name.lower() in notes:
            return [("playoff-note", f"{team_name} advances to Inter-Confederation Playoffs")]
    return [("playoff-note", "Advances to Inter-Confederation Playoffs")]


def _match_winner_name(match: pd.Series) -> str:
    winning_id = _field(match, "winning_team_id", "")
    for side in ("home", "away"):
        if winning_id and winning_id.lower() == _field(match, f"{side}_team_id", "").lower():
            return _field(match, f"{side}_team_name", "")
    result = _field(match, "result", "").lower()
    if result == "home_win":
        return _field(match, "home_team_name", "")
    if result == "away_win":
        return _field(match, "away_team_name", "")
    return ""


def _tournament_bracket_html(rows: pd.DataFrame, brackets: pd.DataFrame, bracket_id: str, confederation_id: str) -> str:
    rows = rows.copy()
    rows["_order"] = pd.to_numeric(rows.get("match_order", ""), errors="coerce").fillna(999)
    stages = _bracket_stage_order(rows)
    bracket_name = _bracket_display_name(brackets, rows, bracket_id)
    if len(stages) == 2:
        return _two_stage_bracket_html(rows, stages, bracket_name, confederation_id)
    stage_markup = []
    for index, stage in enumerate(stages):
        stage_rows = rows[rows["_bracket_stage"].eq(stage)].sort_values(["_order", "date"])
        cards = "".join(_bracket_match_card(match, confederation_id) for _, match in stage_rows.iterrows())
        final_class = " final" if index == len(stages) - 1 and len(stages) > 1 else ""
        stage_markup.append(
            '<div class="wcq-real-bracket-stage">'
            f'<div class="wcq-bracket-stage-title">{html.escape(stage)}</div>'
            f'<div class="wcq-real-bracket-matches{final_class}">{cards}</div>'
            '</div>'
        )
        if index < len(stages) - 1:
            connector_class = " single" if len(stage_rows) <= 1 else ""
            stage_markup.append(f'<div class="wcq-bracket-connector{connector_class}"></div>')
    return (
        f'<section class="wcq-real-bracket" style="{_style_vars(get_confederation_style(confederation_id))}">'
        f'<h4>{html.escape(bracket_name)}</h4>'
        f'<div class="wcq-real-bracket-board" style="grid-template-columns: {_bracket_grid_template(len(stages))};">'
        f'{"".join(stage_markup)}'
        '</div>'
        '</section>'
    )


def _two_stage_bracket_html(rows: pd.DataFrame, stages: list[str], bracket_name: str, confederation_id: str) -> str:
    first_stage, final_stage = stages[0], stages[1]
    semifinals = rows[rows["_bracket_stage"].eq(first_stage)].sort_values(["_order", "date"])
    finals = rows[rows["_bracket_stage"].eq(final_stage)].sort_values(["_order", "date"])
    final_card = "".join(_bracket_match_card(match, confederation_id) for _, match in finals.iterrows())
    semifinal_cards = "".join(
        f'<div class="wcq-semifinal-slot">{_bracket_match_card(match, confederation_id)}</div>'
        for _, match in semifinals.iterrows()
    )
    return (
        f'<section class="wcq-real-bracket wcq-two-stage-bracket" style="{_style_vars(get_confederation_style(confederation_id))}">'
        '<div class="wcq-two-stage-labels">'
        f'<span>{html.escape(first_stage)}</span><span>{html.escape(final_stage)}</span>'
        '</div>'
        '<div class="wcq-two-stage-board">'
        f'<div class="wcq-semifinal-column">{semifinal_cards}</div>'
        '<div class="wcq-connector-column"><div class="wcq-clean-connector">'
        '<span class="wcq-arm wcq-arm-top"></span>'
        '<span class="wcq-arm wcq-arm-bottom"></span>'
        '<span class="wcq-arm wcq-arm-final"></span>'
        '</div></div>'
        f'<div class="wcq-final-column">{final_card}</div>'
        '</div>'
        '</section>'
    )


def _ordered_bracket_ids(matches: pd.DataFrame) -> list[str]:
    rows = matches.copy()
    rows["_order"] = pd.to_numeric(rows.get("match_order", ""), errors="coerce").fillna(999)
    order = rows.groupby("_bracket_id")["_order"].min().sort_values()
    return [str(value) for value in order.index]


def _bracket_display_name(brackets: pd.DataFrame, rows: pd.DataFrame, bracket_id: str) -> str:
    if not brackets.empty and "bracket_id" in brackets.columns and "bracket_name" in brackets.columns:
        match = brackets[brackets["bracket_id"].astype(str).eq(str(bracket_id))]
        names = [str(value).strip() for value in match["bracket_name"].dropna().unique() if str(value).strip()]
        if names:
            return names[0]
    text = str(bracket_id or "Bracket").replace("_", " ").strip()
    return text.title() if text else "Bracket"


def _bracket_grid_template(stage_count: int) -> str:
    if stage_count <= 1:
        return "minmax(0, 1fr)"
    tracks: list[str] = []
    for index in range(stage_count):
        tracks.append("minmax(220px, 1fr)")
        if index < stage_count - 1:
            tracks.append("72px")
    return " ".join(tracks)


def _inter_confederation_path_html(path_name: str, path_matches: pd.DataFrame) -> str:
    rows = path_matches.sort_values(["_stage_order", "_date", "match_id"])
    semifinal_rows = rows[rows["_icpo_stage"].eq("Semi-Final")]
    final_rows = rows[rows["_icpo_stage"].eq("Final")]
    semifinal = semifinal_rows.iloc[0] if not semifinal_rows.empty else None
    final = final_rows.iloc[0] if not final_rows.empty else None
    semifinal_card = _inter_confederation_match_card(semifinal, show_stage=False) if semifinal is not None else _empty_icpo_card("Semi-Final")
    final_card = _inter_confederation_match_card(final, show_stage=False) if final is not None else _empty_icpo_card("Final")
    qualifier = _icpo_qualified_team(final)
    qualifier_note = (
        f'<div class="wcq-icpo-qualifier-note">{html.escape(qualifier)} advanced to the World Cup</div>'
        if qualifier
        else ""
    )
    return (
        f'<section class="wcq-icpo-path" style="{_style_vars(get_confederation_style("CONCACAF"))}">'
        f'<div class="wcq-bracket-stage-title">{html.escape(path_name)}</div>'
        '<div class="wcq-icpo-path-board">'
        f'<div class="wcq-icpo-stage"><div class="wcq-icpo-stage-label">Semi-Final</div>{semifinal_card}</div>'
        '<div class="wcq-icpo-connector"></div>'
        f'<div class="wcq-icpo-stage"><div class="wcq-icpo-stage-label">Final</div>{final_card}</div>'
        '</div>'
        f'{qualifier_note}'
        '</section>'
    )


def _empty_icpo_card(stage: str) -> str:
    return (
        '<article class="wcq-bracket-card wcq-icpo-card">'
        f'<div class="wcq-bracket-date">{html.escape(stage)}</div>'
        '<div class="wcq-bracket-team"><span>TBD</span><strong></strong></div>'
        '</article>'
    )


def _icpo_qualified_team(match: pd.Series | None) -> str:
    if match is None:
        return ""
    winning_id = _field(match, "winning_team_id", "")
    for side in ("home", "away"):
        if winning_id and winning_id.lower() == _field(match, f"{side}_team_id", "").lower():
            return _field(match, f"{side}_team_name", "")
    result = _field(match, "result", "").lower()
    if result == "home_win":
        return _field(match, "home_team_name", "")
    if result == "away_win":
        return _field(match, "away_team_name", "")
    return ""


def _inter_confederation_match_card(match: pd.Series, show_stage: bool = True) -> str:
    stage = _field(match, "_icpo_stage", "Playoff")
    penalties = _penalty_text(match)
    penalties_markup = f'<div class="wcq-bracket-score">{html.escape(penalties)}</div>' if penalties else ""
    stage_markup = f'<div class="wcq-bracket-date">{html.escape(stage)}</div>' if show_stage else ""
    return (
        '<article class="wcq-bracket-card wcq-icpo-card">'
        f'{stage_markup}'
        f'{_bracket_team_line(match, "home", _icpo_side_status(match, "home"), "CONCACAF")}'
        f'{penalties_markup}'
        f'{_bracket_team_line(match, "away", _icpo_side_status(match, "away"), "CONCACAF")}'
        '</article>'
    )


def _icpo_side_status(match: pd.Series, side: str) -> str:
    winning_id = _field(match, "winning_team_id", "")
    side_id = _field(match, f"{side}_team_id", "")
    result = _field(match, "result", "").lower()
    if winning_id and side_id and winning_id.lower() == side_id.lower():
        return "qualified" if _truthy(match.get("_winner_qualified", "")) else "advanced"
    if not winning_id and result in {"home_win", "away_win"}:
        is_winner = (side == "home" and result == "home_win") or (side == "away" and result == "away_win")
        if is_winner:
            return "qualified" if _truthy(match.get("_winner_qualified", "")) else "advanced"
    return "eliminated"


def _bracket_team_line(match: pd.Series, side: str, status: str, confederation_id: str) -> str:
    row = pd.Series(
        {
            "team_name": _field(match, f"{side}_team_name", "TBD"),
            "fifa_code": _field(match, f"{side}_fifa_code", "TBD"),
            "flag_code": _field(match, f"{side}_flag_code", ""),
            "fifa_rank": _field(match, f"{side}_fifa_rank", ""),
        }
    )
    style = get_status_style(status, confederation_id)
    score = _field(match, f"{side}_score", "")
    winner = " winner" if status == "advanced" else ""
    return (
        f'<div class="wcq-bracket-team{winner}" style="{_status_vars(style)}">'
        f'{_flag_markup(row, _field(row, "fifa_code", ""))}'
        f'<span>{html.escape(_field(row, "team_name", "TBD"))}</span>'
        f'<strong>{html.escape(score)}</strong>'
        '</div>'
    )


def _render_tie_card(tie: pd.Series, confederation_id: str) -> None:
    winner_id = _field(tie, "winner_team_id", "")
    team1_id = _field(tie, "team1_id", _field(tie, "team_1_id", ""))
    team2_id = _field(tie, "team2_id", _field(tie, "team_2_id", ""))
    team1_status = "advanced" if winner_id and winner_id == team1_id else "eliminated"
    team2_status = "advanced" if winner_id and winner_id == team2_id else "eliminated"
    aggregate = _field(tie, "aggregate_score", _single_tie_score(tie))
    legs = " | ".join(
        part
        for part in [
            _field(tie, "leg1_score_team1_first", ""),
            _field(tie, "leg2_score_team1_first", ""),
        ]
        if part
    )
    legs_markup = f"<small>{html.escape(legs)}</small>" if legs else ""
    penalties = _field(tie, "penalty_score", _field(tie, "penalties", ""))
    penalties_markup = f"<small>PK {html.escape(penalties)}</small>" if penalties else ""
    date = _field(tie, "date", "")
    meta_markup = f'<div class="wcq-match-meta"><span>{html.escape(date)}</span></div>' if date else ""
    advancement_markup = _tie_advancement_badge(tie)
    st.markdown(
        f"""
        <article class="wcq-match-card">
          {meta_markup}
          <div class="wcq-matchup">
            {_tie_team(tie, 'team1', team1_status, confederation_id)}
            <strong>{html.escape(aggregate)}{legs_markup}{penalties_markup}</strong>
            {_tie_team(tie, 'team2', team2_status, confederation_id)}
          </div>
          {advancement_markup}
        </article>
        """,
        unsafe_allow_html=True,
    )


def _tie_advancement_badge(tie: pd.Series) -> str:
    note = _field(tie, "notes", _field(tie, "result_notes", ""))
    next_round = _field(tie, "winner_advances_to", "")
    winner_name = _tie_winner_name(tie)
    text = ""
    if "inter-confederation" in note.lower():
        text = note
    elif next_round and "inter" in next_round.lower() and winner_name:
        text = f"{winner_name} advanced to the inter-confederation playoffs"
    elif _field(tie, "round_id", "") == "AFC_R1" and winner_name:
        text = f"{winner_name} advanced to the Second Round"
    elif _field(tie, "round_id", "") == "CONCACAF_R1" and winner_name:
        text = f"{winner_name} advanced to the Second Round"
    elif _field(tie, "round_id", "") == "AFC_R5" and winner_name:
        text = f"{winner_name} advanced to the inter-confederation playoffs"
    if not text:
        return ""
    return f'<div class="wcq-advancement-badge">{html.escape(text)}</div>'


def _tie_winner_name(tie: pd.Series) -> str:
    winner_id = _field(tie, "winner_team_id", "")
    for side in ("team1", "team2"):
        numeric = "1" if side == "team1" else "2"
        side_id = _field(tie, f"{side}_id", _field(tie, f"team_{numeric}_id", ""))
        if winner_id and side_id and winner_id == side_id:
            return _field(tie, f"{side}_name", _field(tie, f"team_{numeric}_name", winner_id))
    return _field(tie, "winner_team_name", _field(tie, "winner_name", winner_id))


def _match_team(match: pd.Series, side: str, status: str, confederation_id: str) -> str:
    row = pd.Series(
        {
            "team_name": _field(match, f"{side}_team_name", "TBD"),
            "fifa_code": _field(match, f"{side}_fifa_code", "TBD"),
            "flag_code": _field(match, f"{side}_flag_code", ""),
            "fifa_rank": _field(match, f"{side}_fifa_rank", ""),
        }
    )
    style = get_status_style(status, confederation_id)
    return (
        f'<div class="wcq-match-team" style="{_status_vars(style)}">'
        f'{_flag_markup(row, _field(row, "fifa_code", ""))}'
        f'<span>{html.escape(_field(row, "team_name", "TBD"))}</span>'
        f'<small>{html.escape(_rank_text(row))}</small>'
        '</div>'
    )


def _tie_team(tie: pd.Series, side: str, status: str, confederation_id: str) -> str:
    prefix = side if side in tie.index and f"{side}_name" in tie.index else side
    if side in {"team1", "team2"}:
        numeric = "1" if side == "team1" else "2"
        name = _field(tie, f"{side}_name", _field(tie, f"team_{numeric}_name", "TBD"))
        fifa_code = _field(tie, f"{side}_fifa_code", _field(tie, f"team_{numeric}_fifa_code", _field(tie, f"{side}_id", _field(tie, f"team_{numeric}_id", "TBD"))))
        flag_code = _field(tie, f"{side}_flag_code", _field(tie, f"team_{numeric}_flag_code", ""))
        fifa_rank = _field(tie, f"{side}_fifa_rank", _field(tie, f"team_{numeric}_fifa_rank", ""))
    else:
        name = _field(tie, f"{prefix}_name", "TBD")
        fifa_code = _field(tie, f"{prefix}_fifa_code", "TBD")
        flag_code = _field(tie, f"{prefix}_flag_code", "")
        fifa_rank = _field(tie, f"{prefix}_fifa_rank", "")
    row = pd.Series(
        {
            "team_name": name,
            "fifa_code": fifa_code,
            "flag_code": flag_code,
            "fifa_rank": fifa_rank,
        }
    )
    row = _enrich_team_identity(row)
    style = get_status_style(status, confederation_id)
    return (
        f'<div class="wcq-match-team" style="{_status_vars(style)}">'
        f'{_flag_markup(row, _field(row, "fifa_code", ""))}'
        f'<span>{html.escape(_field(row, "team_name", "TBD"))}</span>'
        f'<small>{html.escape(_rank_text(row))}</small>'
        '</div>'
    )


def _enrich_team_identity(row: pd.Series) -> pd.Series:
    if _field(row, "flag_code", ""):
        return row
    lookup = _team_identity_lookup()
    candidates = [
        _field(row, "fifa_code", "").upper(),
        _normalize_team_label(_field(row, "team_name", "")),
    ]
    for candidate in candidates:
        identity = lookup.get(candidate)
        if not identity:
            continue
        enriched = row.copy()
        if not _field(enriched, "fifa_code", ""):
            enriched["fifa_code"] = identity.get("fifa_code", "")
        if not _field(enriched, "flag_code", ""):
            enriched["flag_code"] = identity.get("flag_code", "")
        return enriched
    return row


def _team_identity_lookup() -> dict[str, dict[str, str]]:
    lookup: dict[str, dict[str, str]] = {}
    for path in WCQ_DATA_DIR.glob("wcq_*_teams.csv"):
        try:
            rows = pd.read_csv(path, dtype=str, keep_default_na=False).fillna("")
        except Exception:
            continue
        for _, row in rows.iterrows():
            identity = {
                "team_name": str(row.get("team_name", "")).strip(),
                "fifa_code": str(row.get("fifa_code", "")).strip(),
                "flag_code": str(row.get("flag_code", "")).strip(),
            }
            for key in [identity["fifa_code"].upper(), _normalize_team_label(identity["team_name"])]:
                if key:
                    lookup[key] = identity
    return lookup


def _single_tie_score(tie: pd.Series) -> str:
    team1_score = _field(tie, "team_1_score", "")
    team2_score = _field(tie, "team_2_score", "")
    if team1_score and team2_score:
        return f"{team1_score} - {team2_score}"
    return "Score TBD"


def _team_card_grid(rows: pd.DataFrame, confederation_id: str, mode: str) -> None:
    cards = "".join(render_team_badge_or_card(row, confederation_id, mode) for _, row in rows.iterrows())
    st.markdown(f'<div class="wcq-card-grid">{cards}</div>', unsafe_allow_html=True)


def _show_data_messages(data: dict[str, Any]) -> None:
    if data["missing_files"]:
        with st.expander("WCQ data setup", expanded=False):
            st.warning("Some WCQ CSV files are missing. The page will keep working with empty placeholders.")
            st.write(", ".join(data["missing_files"]))
    if data["column_warnings"]:
        with st.expander("WCQ data validation", expanded=False):
            for warning in data["column_warnings"]:
                st.warning(warning)


def _confederation_short_summary(confederation_id: str, data: dict[str, Any], confed: pd.Series | None) -> str:
    rounds = _without_inter_confederation_rounds(_confederation_rows(_wcq_frame(data, "rounds"), confederation_id))
    qualified = _confederation_rows(_wcq_frame(data, "qualified"), confederation_id)
    parts = []
    if not rounds.empty:
        parts.append(f"{len(rounds)} rounds")
    if not qualified.empty:
        parts.append(f"{len(qualified)} qualified")
    if parts:
        return " | ".join(parts)
    return _field(confed, "region_description", "")


def _wcq_frame(data: dict[str, Any], key: str) -> pd.DataFrame:
    frame = data.get(key)
    if isinstance(frame, pd.DataFrame):
        return frame
    columns = WCQ_FILES.get(key, {}).get("required", [])
    return pd.DataFrame(columns=columns)


def _confederation_row(confederation_id: str, data: dict[str, Any]) -> pd.Series | None:
    rows = _confederation_rows(data["confederations"], confederation_id)
    if rows.empty:
        return None
    return rows.iloc[0]


def _confederation_rows(frame: pd.DataFrame, confederation_id: str) -> pd.DataFrame:
    if frame.empty or "confederation_id" not in frame.columns:
        return frame.iloc[0:0].copy()
    return frame[frame["confederation_id"].astype(str).str.upper().eq(str(confederation_id).upper())].copy()


def _round_rows(frame: pd.DataFrame, round_id: str, confederation_id: str) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    filtered = _confederation_rows(frame, confederation_id)
    if "round_id" not in filtered.columns:
        return filtered.iloc[0:0].copy()
    return filtered[filtered["round_id"].astype(str).eq(str(round_id))].copy()


def _inter_confederation_rounds(rounds: pd.DataFrame) -> pd.DataFrame:
    if rounds.empty:
        return rounds.copy()
    name = rounds.get("round_name", pd.Series(dtype=str)).astype(str).str.lower()
    round_id = rounds.get("round_id", pd.Series(dtype=str)).astype(str).str.lower()
    mask = (
        name.str.contains("inter-confederation|inter confederation", regex=True, na=False)
        | round_id.str.contains("icpo|inter", regex=True, na=False)
    )
    return rounds[mask].copy()


def _without_inter_confederation_rounds(rounds: pd.DataFrame) -> pd.DataFrame:
    if rounds.empty:
        return rounds.copy()
    inter_round_ids = set(_inter_confederation_rounds(rounds).get("round_id", pd.Series(dtype=str)).astype(str))
    if not inter_round_ids:
        return rounds
    return rounds[~rounds["round_id"].astype(str).isin(inter_round_ids)].copy()


def _inter_confederation_tab_label(round_row: pd.Series) -> str:
    confed = _field(round_row, "confederation_id", "")
    name = _field(round_row, "round_name", "Playoff")
    return f"{confed} - {name}" if confed else name


def _canonical_inter_confederation_matches(data: dict[str, Any]) -> pd.DataFrame:
    rounds = _inter_confederation_rounds(_wcq_frame(data, "rounds"))
    if rounds.empty:
        return pd.DataFrame()
    round_ids = set(rounds["round_id"].astype(str))
    matches = _wcq_frame(data, "matches")
    matches = matches[matches["round_id"].astype(str).isin(round_ids)].copy()
    ties = _wcq_frame(data, "playoff_ties")
    ties = ties[ties["round_id"].astype(str).isin(round_ids)].copy()

    candidates: list[pd.Series] = [row for _, row in matches.iterrows()]
    candidates.extend(_tie_as_match(row) for _, row in ties.iterrows())
    if not candidates:
        return pd.DataFrame()

    best_by_key: dict[tuple[str, str, str, str], pd.Series] = {}
    for row in candidates:
        row = row.copy()
        _normalize_icpo_match_row(row)
        path = _icpo_path(row)
        if not path:
            continue
        row["_icpo_path"] = path
        row["_icpo_stage"] = _icpo_stage(row)
        row["_winner_qualified"] = "true" if row["_icpo_stage"] == "Final" else ""
        key = _icpo_match_key(row)
        existing = best_by_key.get(key)
        if existing is None or _icpo_row_quality(row) > _icpo_row_quality(existing):
            best_by_key[key] = row

    if not best_by_key:
        return pd.DataFrame()
    return pd.DataFrame(best_by_key.values())


def _tie_as_match(tie: pd.Series) -> pd.Series:
    home_name = _field(tie, "home_team_name", _field(tie, "team1_name", _field(tie, "team_1_name", "")))
    away_name = _field(tie, "away_team_name", _field(tie, "team2_name", _field(tie, "team_2_name", "")))
    aggregate = _field(tie, "aggregate_score", "")
    home_score, away_score = _split_score(aggregate)
    if not home_score:
        home_score = _field(tie, "home_score", _field(tie, "team_1_score", ""))
    if not away_score:
        away_score = _field(tie, "away_score", _field(tie, "team_2_score", ""))
    return pd.Series(
        {
            "match_id": _field(tie, "tie_id", ""),
            "round_id": _field(tie, "round_id", ""),
            "confederation_id": _field(tie, "confederation_id", ""),
            "date": _field(tie, "date", ""),
            "home_team_id": _field(tie, "home_team_id", _field(tie, "team1_id", _field(tie, "team_1_id", ""))),
            "home_team_name": home_name,
            "home_fifa_code": _field(tie, "home_fifa_code", _field(tie, "team1_fifa_code", _field(tie, "team_1_fifa_code", ""))),
            "home_flag_code": _field(tie, "home_flag_code", _field(tie, "team1_flag_code", "")),
            "home_fifa_rank": _field(tie, "home_fifa_rank", _field(tie, "team1_fifa_rank", "")),
            "away_team_id": _field(tie, "away_team_id", _field(tie, "team2_id", _field(tie, "team_2_id", ""))),
            "away_team_name": away_name,
            "away_fifa_code": _field(tie, "away_fifa_code", _field(tie, "team2_fifa_code", _field(tie, "team_2_fifa_code", ""))),
            "away_flag_code": _field(tie, "away_flag_code", _field(tie, "team2_flag_code", "")),
            "away_fifa_rank": _field(tie, "away_fifa_rank", _field(tie, "team2_fifa_rank", "")),
            "home_score": home_score,
            "away_score": away_score,
            "extra_time": _field(tie, "extra_time", ""),
            "penalties": _field(tie, "penalties", _field(tie, "penalty_score", "")),
            "winning_team_id": _field(tie, "winner_team_id", ""),
            "result_notes": _field(tie, "notes", ""),
            "result": "",
        }
    )


def _split_score(score: str) -> tuple[str, str]:
    clean = str(score or "").lower().replace("aet", "").replace("a.e.t.", "").strip()
    if "-" not in clean:
        return "", ""
    first, second = clean.split("-", 1)
    return first.strip(), second.strip()


def _normalize_icpo_match_row(row: pd.Series) -> None:
    name_map = {
        "BOL": ("Bolivia", "BO"),
        "COD": ("DR Congo", "CD"),
        "IRQ": ("Iraq", "IQ"),
        "JAM": ("Jamaica", "JM"),
        "NCL": ("New Caledonia", "NC"),
        "SUR": ("Suriname", "SR"),
    }
    for side in ["home", "away"]:
        name_key = f"{side}_team_name"
        code_key = f"{side}_fifa_code"
        flag_key = f"{side}_flag_code"
        text = _field(row, name_key, "")
        code = _field(row, code_key, text).upper()
        if code in name_map and (not text or text.upper() == code):
            row[name_key] = name_map[code][0]
        if code in name_map and not _field(row, flag_key, ""):
            row[flag_key] = name_map[code][1]
        if not _field(row, code_key, "") and code in name_map:
            row[code_key] = code


def _icpo_path(row: pd.Series) -> str:
    teams = {_normalize_team_label(_field(row, "home_team_name", "")), _normalize_team_label(_field(row, "away_team_name", ""))}
    if teams & {"iraq", "bolivia", "suriname"}:
        return "Path A"
    if teams & {"dr congo", "jamaica", "new caledonia"}:
        return "Path B"
    return ""


def _icpo_stage(row: pd.Series) -> str:
    teams = {_normalize_team_label(_field(row, "home_team_name", "")), _normalize_team_label(_field(row, "away_team_name", ""))}
    if {"iraq", "bolivia"} <= teams or {"dr congo", "jamaica"} <= teams:
        return "Final"
    return "Semi-Final"


def _icpo_match_key(row: pd.Series) -> tuple[str, str, str, str]:
    teams = sorted([_normalize_team_label(_field(row, "home_team_name", "")), _normalize_team_label(_field(row, "away_team_name", ""))])
    return (_field(row, "_icpo_path", ""), teams[0], teams[1], _score_pair(row, "home", "away"))


def _icpo_row_quality(row: pd.Series) -> int:
    fields = [
        "home_team_name",
        "away_team_name",
        "home_flag_code",
        "away_flag_code",
        "home_fifa_rank",
        "away_fifa_rank",
        "winning_team_id",
        "result_notes",
        "bracket_id",
    ]
    quality = sum(1 for field in fields if _field(row, field, ""))
    quality -= sum(1 for side in ["home", "away"] if _field(row, f"{side}_team_name", "").upper() == _field(row, f"{side}_fifa_code", "").upper())
    return quality


def _normalize_team_label(value: str) -> str:
    text = str(value or "").strip().lower()
    aliases = {
        "bol": "bolivia",
        "cod": "dr congo",
        "congo dr": "dr congo",
        "democratic republic of the congo": "dr congo",
        "irq": "iraq",
        "jam": "jamaica",
        "ncl": "new caledonia",
        "sur": "suriname",
    }
    return aliases.get(text, text)


def _inter_confederation_eliminated(data: dict[str, Any]) -> pd.DataFrame:
    rounds = _inter_confederation_rounds(_wcq_frame(data, "rounds"))
    if rounds.empty:
        return pd.DataFrame()
    rows = _wcq_frame(data, "eliminated")
    rows = rows[rows["round_id"].astype(str).isin(set(rounds["round_id"].astype(str)))].copy()
    if rows.empty:
        return rows
    rows = rows.drop_duplicates(subset=["team_name"], keep="first")
    return rows


def _filter_team_rows(rows: pd.DataFrame, query: str, statuses: list[str]) -> pd.DataFrame:
    if rows.empty:
        return rows
    filtered = rows.copy()
    if query:
        haystack = filtered.get("team_name", "").astype(str) + " " + filtered.get("fifa_code", "").astype(str)
        filtered = filtered[haystack.str.contains(query, case=False, na=False)]
    if statuses and "status" in filtered:
        filtered = filtered[filtered["status"].astype(str).str.lower().isin(statuses)]
    return filtered


def _filter_match_rows(rows: pd.DataFrame, query: str) -> pd.DataFrame:
    if rows.empty or not query:
        return rows
    haystack = (
        rows.get("home_team_name", "").astype(str)
        + " "
        + rows.get("home_fifa_code", "").astype(str)
        + " "
        + rows.get("away_team_name", "").astype(str)
        + " "
        + rows.get("away_fifa_code", "").astype(str)
    )
    return rows[haystack.str.contains(query, case=False, na=False)]


def _filter_tie_rows(rows: pd.DataFrame, query: str) -> pd.DataFrame:
    if rows.empty or not query:
        return rows
    haystack = (
        rows.get("team1_name", "").astype(str)
        + " "
        + rows.get("team1_fifa_code", "").astype(str)
        + " "
        + rows.get("team2_name", "").astype(str)
        + " "
        + rows.get("team2_fifa_code", "").astype(str)
        + " "
        + rows.get("team_1_name", "").astype(str)
        + " "
        + rows.get("team_1_fifa_code", "").astype(str)
        + " "
        + rows.get("team_2_name", "").astype(str)
        + " "
        + rows.get("team_2_fifa_code", "").astype(str)
    )
    return rows[haystack.str.contains(query, case=False, na=False)]


def _without_duplicate_ties(ties: pd.DataFrame, matches: pd.DataFrame) -> pd.DataFrame:
    if ties.empty or matches.empty or "tie_id" not in ties.columns or "match_id" not in matches.columns:
        return ties
    match_ids = set(matches["match_id"].astype(str))
    match_keys = {_matchup_key(row) for _, row in matches.iterrows()}
    keep_rows = []
    for _, tie in ties.iterrows():
        if str(tie.get("tie_id", "")) in match_ids:
            continue
        if _tie_matchup_key(tie) in match_keys:
            continue
        keep_rows.append(tie)
    return pd.DataFrame(keep_rows, columns=ties.columns)


def _is_two_leg_round(round_id: str, confederation_id: str, data: dict[str, Any]) -> bool:
    rounds = _round_rows(_wcq_frame(data, "rounds"), round_id, confederation_id)
    if rounds.empty:
        return False
    return _field(rounds.iloc[0], "round_type", "").lower() == "two_leg_playoff"


def _matchup_key(row: pd.Series) -> tuple[str, str, str, str]:
    teams = sorted([_field(row, "home_team_name", "").lower(), _field(row, "away_team_name", "").lower()])
    return (str(row.get("round_id", "")), teams[0], teams[1], _score_pair(row, "home", "away"))


def _tie_matchup_key(row: pd.Series) -> tuple[str, str, str, str]:
    home = _field(row, "home_team_name", _field(row, "team1_name", _field(row, "team_1_name", ""))).lower()
    away = _field(row, "away_team_name", _field(row, "team2_name", _field(row, "team_2_name", ""))).lower()
    teams = sorted([home, away])
    return (str(row.get("round_id", "")), teams[0], teams[1], _score_pair(row, "home", "away"))


def _score_pair(row: pd.Series, first_prefix: str, second_prefix: str) -> str:
    first = _field(row, f"{first_prefix}_score", _field(row, "team_1_score", ""))
    second = _field(row, f"{second_prefix}_score", _field(row, "team_2_score", ""))
    scores = sorted([first, second])
    return "-".join(scores)


def _has_bracket_shape(matches: pd.DataFrame, brackets: pd.DataFrame) -> bool:
    if not brackets.empty:
        return True
    if "bracket_id" not in matches.columns:
        return False
    return matches["bracket_id"].astype(str).str.strip().ne("").any()


def _matches_with_bracket_stage(matches: pd.DataFrame, brackets: pd.DataFrame) -> pd.DataFrame:
    if matches.empty:
        return matches.copy()
    rows = matches.copy()
    if not brackets.empty and "match_id" in brackets.columns:
        stage_lookup = brackets[["match_id", "bracket_stage"]].drop_duplicates("match_id")
        rows = rows.merge(stage_lookup, on="match_id", how="left")
    if "bracket_stage" not in rows.columns:
        rows["bracket_stage"] = ""
    rows["_bracket_stage"] = rows["bracket_stage"].apply(_clean_bracket_stage)
    return rows


def _clean_bracket_stage(value) -> str:
    text = str(value or "").replace("_", " ").strip()
    return text.title() if text else "Playoff"


def _bracket_stage_order(matches: pd.DataFrame) -> list[str]:
    order = {"Preliminary": 0, "Semi-Final": 1, "Semi-Finals": 1, "Semifinal": 1, "Semifinals": 1, "Final": 2}
    stages = [stage for stage in matches["_bracket_stage"].dropna().unique() if str(stage).strip()]
    return sorted(stages, key=lambda stage: (order.get(str(stage), 99), str(stage)))


def _ordered_confederation_groups(qualified: pd.DataFrame):
    for confed in CONFEDERATION_ORDER:
        rows = _confederation_rows(qualified, confed)
        if not rows.empty:
            yield confed, rows
    remaining = qualified[~qualified["confederation_id"].isin(CONFEDERATION_ORDER)]
    if not remaining.empty:
        yield "Other", remaining


def _unique_team_count(*frames_and_confed) -> int:
    confederation_id = frames_and_confed[-1]
    frames = frames_and_confed[:-1]
    team_ids: set[str] = set()
    names: set[str] = set()
    for frame in frames:
        rows = _confederation_rows(frame, confederation_id)
        for column in ["team_id", "home_team_id", "away_team_id"]:
            if column in rows:
                team_ids.update(str(value) for value in rows[column] if str(value).strip())
        for column in ["team_name", "home_team_name", "away_team_name"]:
            if column in rows:
                names.update(str(value) for value in rows[column] if str(value).strip())
    return len(team_ids) if team_ids else len(names)


def _team_status(row: pd.Series, mode: str = "default") -> str:
    if mode == "qualified":
        method = _field(row, "qualification_method", "").lower()
        if method == "host":
            return "host"
        return "qualified"
    if mode == "eliminated":
        return "eliminated"
    if _truthy(row.get("qualified_for_world_cup", "")):
        return "qualified"
    return _field(row, "status", "unknown").lower()


def _team_detail(row: pd.Series, mode: str) -> str:
    if mode == "qualified":
        method = _field(row, "qualification_method", "Qualification method TBD")
        date = _field(row, "qualification_date", "")
        qualified_as = _field(row, "qualified_as", "")
        return " | ".join(part for part in [method.replace("_", " ").title(), date, qualified_as] if part)
    if mode == "eliminated":
        reason = _field(row, "elimination_reason", "Elimination details TBD")
        final_position = _field(row, "final_position", "")
        if not final_position or final_position.lower() in reason.lower():
            return reason
        return f"{reason} | {final_position}"
    return _field(row, "status", "Status TBD").replace("_", " ").title()


def _field(row: pd.Series | None, key: str, default: str = "") -> str:
    if row is None or key not in row:
        return default
    value = row.get(key, default)
    if pd.isna(value) or str(value).strip() == "":
        return default
    return str(value).strip()


def _format_round_date_range(start: str, end: str) -> str:
    start_ts = pd.to_datetime(start, errors="coerce")
    end_ts = pd.to_datetime(end, errors="coerce")
    if pd.isna(start_ts) and pd.isna(end_ts):
        return ""
    if pd.isna(end_ts) or start_ts == end_ts:
        return _format_date(start_ts)
    if pd.isna(start_ts):
        return _format_date(end_ts)
    if start_ts.year == end_ts.year and start_ts.month == end_ts.month:
        return f"{start_ts.strftime('%B')} {start_ts.day}-{end_ts.day}, {end_ts.year}"
    if start_ts.year == end_ts.year:
        return f"{start_ts.strftime('%B')} {start_ts.day} - {end_ts.strftime('%B')} {end_ts.day}, {end_ts.year}"
    return f"{_format_date(start_ts)} - {_format_date(end_ts)}"


def _format_date(value: pd.Timestamp) -> str:
    if pd.isna(value):
        return ""
    return f"{value.strftime('%B')} {value.day}, {value.year}"


def _safe_key(value: str) -> str:
    return "".join(character.lower() if character.isalnum() else "_" for character in str(value)).strip("_")


def _rank_text(row: pd.Series) -> str:
    rank = _field(row, "fifa_rank", "")
    if not rank:
        return "Rank unavailable"
    return f"FIFA rank {rank}"


def _rank_number_text(row: pd.Series) -> str:
    rank = _field(row, "fifa_rank", "")
    return rank if rank else "Unavailable"


def _flag_markup(row: pd.Series, fallback: str) -> str:
    code = _field(row, "flag_code", "").lower()
    fallback = fallback or _field(row, "fifa_code", "TBD")
    team_name = _field(row, "team_name", "Team")
    if not code:
        return f'<span class="wcq-flag fallback">{html.escape(fallback)}</span>'
    return (
        f'<img class="wcq-flag" src="https://flagcdn.com/w80/{html.escape(code)}.png" '
        f'alt="{html.escape(team_name)} flag" '
        "onerror=\"this.style.display='none';this.nextElementSibling.style.display='grid';\">"
        f'<span class="wcq-flag fallback hidden">{html.escape(fallback)}</span>'
    )


def _scoreline(match: pd.Series) -> str:
    home = _field(match, "home_score", "")
    away = _field(match, "away_score", "")
    if home and away:
        score = f"{home} - {away}"
    else:
        score = "vs"
    penalties = _field(match, "penalties", "")
    extra_time = _field(match, "extra_time", "")
    extra_label = "a.e.t." if str(extra_time).strip().lower() in {"true", "yes", "1", "aet", "a.e.t."} else ""
    penalties_label = f"{penalties} p" if penalties else ""
    extras = " | ".join(part for part in [extra_label, penalties_label] if part)
    return f"{score} ({extras})" if extras else score


def _penalty_text(match: pd.Series) -> str:
    penalties = _field(match, "penalties", "")
    if not penalties:
        return ""
    return f"{penalties} p"


def _round_label(rounds: pd.DataFrame, round_id: str) -> str:
    match = rounds[rounds["round_id"].eq(round_id)]
    if match.empty:
        return round_id
    return _display_round_name(match.iloc[0])


def _display_round_name(round_row: pd.Series) -> str:
    name = _field(round_row, "round_name", _field(round_row, "round_id", "Round"))
    replacements = {
        "First round / Group stage": "First Round",
        "Second round / CAF play-off tournament": "Second Round",
        "First Round - Group Stage": "First Round",
        "Second Round - UEFA Play-offs": "Second Round",
        "Round One": "First Round",
        "Round Two": "Second Round",
    }
    return replacements.get(name, name)


def _display_round_type(round_row: pd.Series) -> str:
    round_id = _field(round_row, "round_id", "")
    if round_id == "caf_2026_second_round":
        return "CAF Play-Off Tournament"
    if round_id == "UEFA_R2":
        return "UEFA Playoffs"
    return _field(round_row, "round_type", "Round").replace("_", " ").title()


def _truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _stat_tile(value: Any, label: str) -> str:
    return f'<div class="wcq-stat"><strong>{html.escape(str(value))}</strong><span>{html.escape(label)}</span></div>'


def _style_vars(style: dict[str, str]) -> str:
    return (
        f'--wcq-primary:{style["primary"]};'
        f'--wcq-secondary:{style["secondary"]};'
        f'--wcq-accent:{style["accent"]};'
        f'--wcq-surface:{style["surface"]};'
        f'--wcq-glow:{style["glow"]};'
    )


def _status_vars(style: dict[str, str]) -> str:
    return (
        f'--status-border:{style["border"]};'
        f'--status-bg:{style["background"]};'
        f'--status-accent:{style["accent"]};'
        f'--status-shadow:{style["shadow"]};'
    )


def _styles() -> None:
    st.markdown(
        """
        <style>
        .wcq-hero {
            background:
                radial-gradient(circle at 82% 18%, var(--wcq-glow), transparent 32%),
                linear-gradient(135deg, color-mix(in srgb, var(--wcq-primary) 34%, #050505), rgba(11,16,32,.86));
            border: 1px solid color-mix(in srgb, var(--wcq-secondary) 58%, transparent);
            border-radius: 8px;
            box-shadow: 0 18px 50px rgba(0,0,0,.28);
            display: grid;
            gap: 1.25rem;
            grid-template-columns: auto 1fr;
            margin: .8rem 0 1.2rem;
            overflow: hidden;
            padding: 1.35rem;
        }
        [class*="st-key-wcq_section_tab_"] {
            margin-bottom: .35rem;
        }
        [class*="st-key-wcq_section_tab_"] button {
            background: rgba(11,16,32,.92) !important;
            border: 1px solid rgba(214,168,58,.34) !important;
            border-radius: 8px !important;
            box-shadow: 0 10px 24px rgba(0,0,0,.16) !important;
            color: #FFFFFF !important;
            min-height: 46px;
            padding: .42rem .44rem !important;
            transition: transform .15s ease, border-color .15s ease, background .15s ease;
            width: 100%;
        }
        [class*="st-key-wcq_section_tab_"] button p {
            color: #FFFFFF !important;
            font-size: .82rem;
            font-weight: 950;
            line-height: 1.05;
            margin: 0;
            overflow-wrap: anywhere;
            text-align: center;
            text-transform: uppercase;
        }
        [class*="st-key-wcq_section_tab_"] button:hover {
            background: rgba(20,24,39,.98) !important;
            border-color: rgba(214,168,58,.82) !important;
            transform: translateY(-1px);
        }
        [class*="st-key-wcq_section_tab_"][class*="_selected"] button {
            background: linear-gradient(135deg, #D6A83A, #9E7420) !important;
            border-color: rgba(255,255,255,.38) !important;
            box-shadow: 0 12px 28px rgba(214,168,58,.22) !important;
            color: #050505 !important;
        }
        [class*="st-key-wcq_section_tab_"][class*="_selected"] button p {
            color: #050505 !important;
        }
        .wcq-round-tab-shell {
            margin: 1rem 0 .1rem;
            position: relative;
        }
        .wcq-round-tab-line {
            background: linear-gradient(90deg, transparent, var(--wcq-secondary), transparent);
            height: 2px;
            opacity: .72;
            width: 100%;
        }
        [class*="st-key-wcq_round_tab_"] {
            margin: .3rem 0 1rem;
            padding: 0;
        }
        [class*="st-key-wcq_round_tab_"] button {
            background: linear-gradient(135deg, rgba(11,16,32,.92), rgba(5,5,5,.72)) !important;
            border: 1px solid color-mix(in srgb, var(--wcq-primary, #D6A83A) 62%, rgba(255,255,255,.18)) !important;
            border-radius: 8px !important;
            box-shadow: 0 10px 22px rgba(0,0,0,.18) !important;
            color: #FFFFFF !important;
            min-height: 46px;
            padding: .42rem .38rem !important;
            width: 100%;
        }
        [class*="st-key-wcq_round_tab_"] button p {
            color: #FFFFFF !important;
            font-size: .82rem;
            font-weight: 950;
            line-height: 1.05;
            margin: 0;
            overflow-wrap: anywhere;
            text-align: center;
        }
        [class*="st-key-wcq_round_tab_"] button:hover {
            border-color: var(--wcq-secondary, #D6A83A) !important;
            transform: translateY(-1px);
        }
        [class*="st-key-wcq_round_tab_"][class*="_selected"] {
            background: transparent;
        }
        [class*="st-key-wcq_round_tab_"][class*="_selected"] button {
            background: linear-gradient(135deg, var(--wcq-secondary, #D6A83A), var(--wcq-primary, #9E7420)) !important;
            border-color: rgba(255,255,255,.40) !important;
            color: #050505 !important;
        }
        [class*="st-key-wcq_round_tab_"][class*="_selected"] button p {
            color: #050505 !important;
        }
        .wcq-hero-badge {
            align-items: center;
            background:
                radial-gradient(circle at 72% 12%, color-mix(in srgb, var(--wcq-secondary) 50%, transparent), transparent 42%),
                linear-gradient(135deg, color-mix(in srgb, var(--wcq-primary) 56%, #050505), rgba(255,255,255,.09));
            border: 1px solid color-mix(in srgb, var(--wcq-secondary) 58%, rgba(255,255,255,.22));
            border-radius: 8px;
            box-shadow: 0 18px 36px rgba(0,0,0,.24), inset 0 1px 0 rgba(255,255,255,.16);
            color: #050505;
            display: grid;
            font-size: 1.25rem;
            font-weight: 950;
            justify-content: center;
            min-height: 112px;
            overflow: hidden;
            padding: .72rem;
            text-shadow: none;
            width: 128px;
        }
        .wcq-hero-badge-text {
            background: linear-gradient(135deg, var(--wcq-secondary), var(--wcq-primary));
        }
        .wcq-hero-badge-logo {
            position: relative;
        }
        .wcq-hero-badge-logo::after {
            border: 1px solid rgba(255,255,255,.14);
            border-radius: 6px;
            content: "";
            inset: .45rem;
            pointer-events: none;
            position: absolute;
        }
        .wcq-hero-badge-logo img {
            display: block;
            filter: drop-shadow(0 8px 12px rgba(0,0,0,.30));
            max-height: 92px;
            object-fit: contain;
            position: relative;
            width: 104px;
            z-index: 1;
        }
        .wcq-logo-afc {
            background:
                radial-gradient(circle at 24% 18%, rgba(255,255,255,.12), transparent 32%),
                linear-gradient(135deg, #002395, color-mix(in srgb, #002395 72%, #050505));
        }
        .wcq-logo-afc img {
            border-radius: 6px;
            max-height: 88px;
            width: 88px;
        }
        .wcq-logo-caf img,
        .wcq-logo-uefa img {
            max-height: 98px;
            width: 98px;
        }
        .wcq-logo-ofc img {
            filter: drop-shadow(0 8px 12px rgba(0,0,0,.26));
            max-height: 86px;
            mix-blend-mode: screen;
            width: 108px;
        }
        .wcq-logo-concacaf img {
            filter:
                drop-shadow(0 0 10px rgba(218,188,115,.34))
                drop-shadow(0 8px 14px rgba(0,0,0,.30));
            max-height: 96px;
            width: 96px;
        }
        .wcq-logo-conmebol img {
            max-height: 100px;
            width: 112px;
        }
        .wcq-hero h2 {
            font-size: clamp(2rem, 4vw, 3.8rem);
            font-weight: 950;
            line-height: .95;
            margin: .15rem 0 .45rem;
        }
        .wcq-hero p,
        .wcq-round-intro p {
            color: rgba(255,255,255,.86);
            font-size: 1.02rem;
            font-weight: 700;
            margin: 0;
        }
        .wcq-kicker {
            color: var(--wcq-secondary, #D6A83A);
            font-size: .78rem;
            font-weight: 950;
            text-transform: uppercase;
        }
        .wcq-hero-stats,
        .wcq-round-stats {
            display: grid;
            gap: .65rem;
            grid-column: 1 / -1;
            grid-template-columns: repeat(6, minmax(0, 1fr));
        }
        .wcq-stat {
            background: rgba(5,5,5,.34);
            border: 1px solid rgba(255,255,255,.12);
            border-radius: 8px;
            padding: .72rem .78rem;
        }
        .wcq-stat strong {
            color: #FFFFFF;
            display: block;
            font-size: 1.35rem;
            font-weight: 950;
            overflow-wrap: anywhere;
        }
        .wcq-stat span {
            color: rgba(255,255,255,.72);
            display: block;
            font-size: .72rem;
            font-weight: 900;
            text-transform: uppercase;
        }
        .wcq-round-intro {
            background: rgba(5,5,5,.30);
            border: 1px solid rgba(214,168,58,.22);
            border-radius: 8px;
            display: block;
            margin: 1rem 0;
            padding: .75rem .9rem;
        }
        .wcq-round-intro h3 {
            font-size: 1.35rem;
            font-weight: 950;
            margin: .05rem 0 .1rem;
        }
        .wcq-round-date {
            background: rgba(214,168,58,.14);
            border: 1px solid rgba(214,168,58,.28);
            border-radius: 999px;
            color: #D6A83A;
            display: inline-block;
            font-size: .86rem;
            font-weight: 950;
            margin-top: .35rem;
            padding: .26rem .6rem;
        }
        .wcq-round-stats {
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }
        .wcq-section-title {
            border-top: 1px solid rgba(214,168,58,.24);
            color: #FFFFFF;
            font-size: 1.25rem;
            font-weight: 950;
            margin: 1.25rem 0 .65rem;
            padding-top: .85rem;
        }
        .wcq-section-title.eliminated {
            color: #FCA5A5;
        }
        .wcq-table {
            border: 1px solid rgba(255,255,255,.12);
            border-radius: 8px;
            margin-bottom: .9rem;
            overflow: hidden;
        }
        .wcq-table-row {
            align-items: center;
            background: var(--status-bg, rgba(255,255,255,.055));
            border-left: 4px solid var(--status-border, rgba(255,255,255,.15));
            border-bottom: 1px solid rgba(255,255,255,.08);
            color: #FFFFFF;
            display: grid;
            gap: .55rem;
            grid-template-columns: .35fr minmax(190px, 2.4fr) 1.15fr repeat(5, .45fr) .55fr 1fr;
            min-height: 58px;
            padding: .55rem .65rem;
        }
        .wcq-runner-row {
            align-items: center;
            background: var(--status-bg, rgba(255,255,255,.055));
            border-left: 4px solid var(--status-border, rgba(255,255,255,.15));
            border-bottom: 1px solid rgba(255,255,255,.08);
            color: #FFFFFF;
            display: grid;
            gap: .55rem;
            grid-template-columns: .55fr minmax(190px, 2.4fr) 1.15fr repeat(5, .45fr) .55fr 1fr;
            min-height: 58px;
            padding: .55rem .65rem;
        }
        .wcq-table-head {
            background: rgba(5,5,5,.54);
            border-left-color: #D6A83A;
            color: #D6A83A;
            font-size: .72rem;
            font-weight: 950;
            min-height: 40px;
            text-transform: uppercase;
        }
        .wcq-table-team {
            align-items: center;
            display: grid;
            gap: .55rem;
            grid-template-columns: auto 1fr;
            min-width: 0;
        }
        .wcq-table-team strong {
            overflow-wrap: anywhere;
        }
        .wcq-table-team em {
            color: rgba(255,255,255,.70);
            font-style: normal;
            font-weight: 900;
        }
        .wcq-status-text {
            color: var(--status-accent, #D6A83A);
            font-weight: 950;
        }
        .wcq-flag {
            aspect-ratio: 3 / 2;
            border: 1px solid rgba(255,255,255,.70);
            border-radius: 4px;
            box-shadow: 0 8px 16px rgba(0,0,0,.28);
            display: block;
            object-fit: cover;
            width: 52px;
        }
        .wcq-flag.fallback {
            align-items: center;
            background: rgba(214,168,58,.18);
            color: #FFFFFF;
            display: grid;
            font-size: .58rem;
            font-weight: 950;
            justify-content: center;
        }
        .wcq-flag.hidden {
            display: none;
        }
        .wcq-card-grid {
            display: grid;
            gap: .85rem;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            margin-bottom: .9rem;
        }
        .wcq-team-card,
        .wcq-match-card {
            background: var(--status-bg, rgba(255,255,255,.07));
            border: 1px solid var(--status-border, rgba(255,255,255,.18));
            border-radius: 8px;
            box-shadow: 0 14px 34px var(--status-shadow, rgba(0,0,0,.20));
            min-height: 188px;
            padding: .95rem;
        }
        .wcq-team-card h4 {
            color: #FFFFFF;
            font-size: 1.28rem;
            font-weight: 950;
            line-height: 1.05;
            margin: .75rem 0 .35rem;
            overflow-wrap: anywhere;
        }
        .wcq-team-top,
        .wcq-match-meta {
            align-items: center;
            display: flex;
            gap: .55rem;
            justify-content: flex-start;
        }
        .wcq-team-top span,
        .wcq-status-pill {
            background: rgba(5,5,5,.34);
            border: 1px solid rgba(255,255,255,.12);
            border-radius: 999px;
            color: var(--status-accent, #D6A83A);
            font-size: .72rem;
            font-weight: 950;
            padding: .22rem .48rem;
            text-transform: uppercase;
        }
        .wcq-rank,
        .wcq-team-card small,
        .wcq-team-card p {
            color: rgba(255,255,255,.76);
            display: block;
            font-weight: 800;
            margin-top: .35rem;
        }
        .wcq-status-pill {
            display: inline-block;
            margin-top: .55rem;
        }
        .wcq-match-card {
            margin-bottom: .85rem;
            min-height: 0;
        }
        .wcq-match-meta {
            color: #D6A83A;
            font-size: .78rem;
            font-weight: 900;
            margin-bottom: .85rem;
            text-transform: uppercase;
        }
        .wcq-matchup {
            align-items: center;
            display: grid;
            gap: .75rem;
            grid-template-columns: 1fr auto 1fr;
        }
        .wcq-matchup > strong {
            color: #FFFFFF;
            font-size: 1.4rem;
            font-weight: 950;
            text-align: center;
        }
        .wcq-matchup > strong small {
            color: rgba(255,255,255,.68);
            display: block;
            font-size: .72rem;
            font-weight: 850;
            margin-top: .25rem;
        }
        .wcq-advancement-badge {
            background: rgba(214,168,58,.14);
            border: 1px solid rgba(214,168,58,.42);
            border-radius: 999px;
            color: #FFE7A0;
            display: table;
            font-size: .82rem;
            font-weight: 950;
            letter-spacing: .01em;
            margin: .85rem auto 0;
            padding: .42rem .8rem;
            text-align: center;
        }
        .wcq-match-team {
            align-items: center;
            background: var(--status-bg, rgba(255,255,255,.06));
            border: 1px solid var(--status-border, rgba(255,255,255,.12));
            border-radius: 8px;
            display: grid;
            gap: .35rem;
            justify-items: center;
            min-height: 130px;
            padding: .85rem;
            text-align: center;
        }
        .wcq-match-team .wcq-flag,
        .wcq-team-card .wcq-flag {
            width: 68px;
        }
        .wcq-match-team span {
            color: #FFFFFF;
            font-size: 1.08rem;
            font-weight: 950;
        }
        .wcq-match-team small {
            color: rgba(255,255,255,.70);
            font-weight: 800;
        }
        .wcq-bracket-stage-title {
            color: #D6A83A;
            font-size: .86rem;
            font-weight: 950;
            margin: .35rem 0 .65rem;
            text-transform: uppercase;
        }
        .wcq-real-bracket {
            background:
                radial-gradient(circle at 85% 8%, var(--wcq-glow, rgba(214,168,58,.16)), transparent 34%),
                rgba(5,5,5,.26);
            border: 1px solid rgba(214,168,58,.24);
            border-radius: 8px;
            margin: 1rem 0 1.25rem;
            overflow-x: auto;
            padding: .9rem;
        }
        .wcq-real-bracket h4 {
            color: #FFFFFF;
            font-size: 1.05rem;
            font-weight: 950;
            margin: 0 0 .75rem;
        }
        .wcq-real-bracket-board {
            align-items: stretch;
            display: grid;
            gap: .55rem;
            min-width: min-content;
        }
        .wcq-real-bracket-stage {
            display: flex;
            flex-direction: column;
            min-width: 220px;
        }
        .wcq-real-bracket-matches {
            display: flex;
            flex: 1;
            flex-direction: column;
            gap: 1rem;
            justify-content: space-around;
        }
        .wcq-real-bracket-matches.final {
            justify-content: center;
        }
        .wcq-bracket-connector {
            background:
                linear-gradient(var(--wcq-secondary, #D6A83A), var(--wcq-secondary, #D6A83A)) center / 2px 54% no-repeat,
                linear-gradient(var(--wcq-secondary, #D6A83A), var(--wcq-secondary, #D6A83A)) left 27% / 100% 2px no-repeat,
                linear-gradient(var(--wcq-secondary, #D6A83A), var(--wcq-secondary, #D6A83A)) left 73% / 100% 2px no-repeat;
            min-width: 72px;
            opacity: .72;
        }
        .wcq-bracket-connector.single {
            background:
                linear-gradient(var(--wcq-secondary, #D6A83A), var(--wcq-secondary, #D6A83A)) center / 100% 2px no-repeat;
        }
        .wcq-icpo-path {
            background:
                radial-gradient(circle at 92% 8%, var(--wcq-glow, rgba(59,130,246,.16)), transparent 36%),
                rgba(5,5,5,.24);
            border: 1px solid rgba(214,168,58,.22);
            border-radius: 8px;
            margin-bottom: 1rem;
            overflow-x: auto;
            padding: .9rem;
        }
        .wcq-icpo-path-board {
            align-items: center;
            display: grid;
            gap: .6rem;
            grid-template-columns: minmax(230px, 1fr) 62px minmax(230px, 1fr);
            min-width: 540px;
        }
        .wcq-icpo-stage-label {
            color: rgba(255,255,255,.72);
            font-size: .72rem;
            font-weight: 950;
            margin-bottom: .5rem;
            text-transform: uppercase;
        }
        .wcq-icpo-connector {
            background:
                linear-gradient(var(--wcq-secondary, #D6A83A), var(--wcq-secondary, #D6A83A)) center / 100% 2px no-repeat;
            height: 100%;
            min-height: 150px;
            opacity: .78;
            position: relative;
        }
        .wcq-icpo-connector::after {
            border-right: 2px solid var(--wcq-secondary, #D6A83A);
            border-top: 2px solid var(--wcq-secondary, #D6A83A);
            content: "";
            height: 8px;
            position: absolute;
            right: 1px;
            top: calc(50% - 5px);
            transform: rotate(45deg);
            width: 8px;
        }
        .wcq-icpo-qualifier-note {
            background: rgba(250,204,21,.16);
            border: 1px solid rgba(250,204,21,.42);
            border-radius: 8px;
            color: #FEF3C7;
            font-size: .95rem;
            font-weight: 950;
            margin-top: .85rem;
            padding: .7rem .85rem;
            text-align: center;
        }
        .wcq-two-stage-labels {
            color: #D6A83A;
            display: grid;
            font-size: .86rem;
            font-weight: 950;
            grid-template-columns: 1fr 1fr;
            margin-bottom: .65rem;
            text-transform: uppercase;
        }
        .wcq-two-stage-labels span:last-child {
            text-align: center;
        }
        .wcq-two-stage-board {
            align-items: stretch;
            display: grid;
            gap: .65rem;
            grid-template-columns: minmax(240px, 1fr) 86px minmax(240px, 1fr);
        }
        .wcq-semifinal-column {
            display: grid;
            gap: 1.45rem;
            grid-template-rows: repeat(2, minmax(0, 1fr));
        }
        .wcq-semifinal-slot {
            align-items: center;
            display: flex;
            position: relative;
        }
        .wcq-semifinal-slot .wcq-bracket-card,
        .wcq-final-column .wcq-bracket-card {
            width: 100%;
        }
        .wcq-final-column {
            align-items: center;
            display: flex;
        }
        .wcq-connector-column {
            position: relative;
        }
        .wcq-clean-connector {
            height: 100%;
            min-height: 280px;
            position: relative;
        }
        .wcq-clean-connector::before {
            background: var(--wcq-secondary, #D6A83A);
            content: "";
            height: 50%;
            left: 38px;
            opacity: .75;
            position: absolute;
            top: 25%;
            width: 2px;
        }
        .wcq-arm {
            background: var(--wcq-secondary, #D6A83A);
            display: block;
            height: 2px;
            opacity: .75;
            position: absolute;
        }
        .wcq-arm-top,
        .wcq-arm-bottom {
            left: 0;
            width: 39px;
        }
        .wcq-arm-top {
            top: 25%;
        }
        .wcq-arm-bottom {
            top: 75%;
        }
        .wcq-arm-final {
            left: 38px;
            right: 0;
            top: 50%;
        }
        .wcq-bracket-card {
            background: rgba(5,5,5,.34);
            border: 1px solid rgba(214,168,58,.24);
            border-radius: 8px;
            box-shadow: 0 14px 34px rgba(0,0,0,.20);
            margin-bottom: .85rem;
            padding: .85rem;
            position: relative;
        }
        .wcq-bracket-date {
            color: rgba(255,255,255,.68);
            font-size: .72rem;
            font-weight: 850;
            margin-bottom: .55rem;
        }
        .wcq-bracket-team {
            align-items: center;
            background: var(--status-bg, rgba(255,255,255,.06));
            border: 1px solid var(--status-border, rgba(255,255,255,.12));
            border-radius: 8px;
            display: grid;
            gap: .55rem;
            grid-template-columns: auto 1fr auto;
            min-height: 54px;
            padding: .45rem .55rem;
        }
        .wcq-bracket-team + .wcq-bracket-score + .wcq-bracket-team {
            margin-top: .35rem;
        }
        .wcq-bracket-team span {
            color: #FFFFFF;
            font-weight: 950;
            overflow-wrap: anywhere;
        }
        .wcq-bracket-team strong {
            color: #FFFFFF;
            font-size: 1.15rem;
            font-weight: 950;
        }
        .wcq-bracket-team.winner {
            box-shadow: 0 0 0 1px var(--status-accent, #D6A83A);
        }
        .wcq-bracket-score {
            color: #D6A83A;
            font-size: .76rem;
            font-weight: 950;
            padding: .22rem 0;
            text-align: center;
            text-transform: uppercase;
        }
        .wcq-bracket-note {
            background: rgba(245,158,11,.13);
            border: 1px solid rgba(245,158,11,.34);
            border-radius: 8px;
            color: #FFE7A0;
            font-size: .78rem;
            font-weight: 950;
            margin-top: .65rem;
            padding: .45rem .55rem;
            text-align: center;
        }
        .wcq-bracket-note.world-cup-note {
            background: rgba(250,204,21,.18);
            border-color: rgba(250,204,21,.48);
            color: #FEF3C7;
        }
        .wcq-bracket-note.playoff-note {
            background: rgba(245,158,11,.14);
            border-color: rgba(245,158,11,.40);
            color: #FFEDD5;
        }
        .wcq-bracket-note.advanced-note {
            background: rgba(20,184,166,.14);
            border-color: rgba(20,184,166,.38);
            color: #CCFBF1;
        }
        .wcq-bracket-card small {
            color: rgba(255,255,255,.68);
            display: block;
            font-weight: 800;
            margin-top: .55rem;
        }
        .wcq-bracket-card .wcq-flag {
            width: 46px;
        }
        @media (max-width: 760px) {
            .wcq-real-bracket-board {
                display: flex;
                flex-direction: column;
                min-width: 0;
            }
            .wcq-bracket-connector {
                background:
                    linear-gradient(var(--wcq-secondary, #D6A83A), var(--wcq-secondary, #D6A83A)) center / 2px 100% no-repeat;
                height: 24px;
                min-width: 0;
            }
            .wcq-two-stage-labels {
                display: none;
            }
            .wcq-two-stage-board {
                display: flex;
                flex-direction: column;
            }
            .wcq-connector-column {
                height: 24px;
                width: 100%;
            }
            .wcq-clean-connector {
                height: 24px;
                min-height: 24px;
            }
            .wcq-clean-connector::before,
            .wcq-arm {
                background: linear-gradient(var(--wcq-secondary, #D6A83A), var(--wcq-secondary, #D6A83A)) center / 2px 100% no-repeat;
                height: 24px;
                inset: 0;
                left: auto;
                top: auto;
                width: 100%;
            }
            .wcq-arm-top,
            .wcq-arm-bottom {
                display: none;
            }
        }
        @media (max-width: 980px) {
            .wcq-hero,
            .wcq-round-intro {
                grid-template-columns: 1fr;
            }
            .wcq-hero-stats {
                grid-template-columns: repeat(3, minmax(0, 1fr));
            }
            .wcq-card-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
            .wcq-table-row {
                grid-template-columns: .35fr minmax(150px, 2.2fr) 1fr repeat(2, .45fr) 1fr;
            }
            .wcq-runner-row {
                grid-template-columns: .45fr minmax(150px, 2.2fr) 1fr repeat(2, .45fr) 1fr;
            }
            .wcq-table-row span:nth-child(5),
            .wcq-table-row span:nth-child(6),
            .wcq-table-row span:nth-child(7),
            .wcq-table-row span:nth-child(8),
            .wcq-runner-row span:nth-child(5),
            .wcq-runner-row span:nth-child(6),
            .wcq-runner-row span:nth-child(7),
            .wcq-runner-row span:nth-child(8) {
                display: none;
            }
        }
        @media (max-width: 680px) {
            .wcq-hero-stats,
            .wcq-round-stats,
            .wcq-card-grid,
            .wcq-matchup {
                grid-template-columns: 1fr;
            }
            .wcq-table {
                overflow-x: auto;
            }
            .wcq-table-row {
                min-width: 720px;
            }
            .wcq-runner-row {
                min-width: 720px;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
