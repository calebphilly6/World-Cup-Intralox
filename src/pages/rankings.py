from __future__ import annotations

import html
import re

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from src.components.clickable_cards import clickable_cards
from src.database import fetch_df
from src.navigation import remember_detail_origin
from src.official_match_reference import normalize_team_key
from src.pages.wcq import (
    WCQ_DATA_SCHEMA_VERSION,
    _canonical_inter_confederation_matches as _wcq_canonical_inter_confederation_matches,
    _has_bracket_shape as _wcq_has_bracket_shape,
    _inter_confederation_path_html as _wcq_inter_confederation_path_html,
    _is_two_leg_round as _wcq_is_two_leg_round,
    _round_rows as _wcq_round_rows,
    _styles as _wcq_styles,
    _wcq_data_signature,
    load_wcq_data,
    render_playoff_ties as _render_wcq_playoff_ties,
    render_tournament_bracket as _render_wcq_tournament_bracket,
)
from src.utils.team_names import display_team_name, flag_code_for_common_team, team_lookup_keys as shared_team_lookup_keys


FLAG_CODES = {
    "Afghanistan": "af", "Albania": "al", "Algeria": "dz", "American Samoa": "as", "Andorra": "ad",
    "Angola": "ao", "Anguilla": "ai", "Antigua and Barbuda": "ag", "Argentina": "ar", "Armenia": "am",
    "Aruba": "aw", "Australia": "au", "Austria": "at", "Azerbaijan": "az", "Bahamas": "bs",
    "Bahrain": "bh", "Bangladesh": "bd", "Barbados": "bb", "Belarus": "by", "Belgium": "be",
    "Belize": "bz", "Benin": "bj", "Bermuda": "bm", "Bhutan": "bt", "Bolivia": "bo",
    "Bosnia and Herzegovina": "ba", "Botswana": "bw", "Brazil": "br", "British Virgin Islands": "vg",
    "Brunei Darussalam": "bn", "Bulgaria": "bg", "Burkina Faso": "bf", "Burundi": "bi",
    "Cabo Verde": "cv", "Cambodia": "kh", "Cameroon": "cm", "Canada": "ca", "Cayman Islands": "ky",
    "Central African Republic": "cf", "Chad": "td", "Chile": "cl", "China PR": "cn", "Chinese Taipei": "tw",
    "Colombia": "co", "Comoros": "km", "Congo": "cg", "Congo DR": "cd", "Cook Islands": "ck",
    "Costa Rica": "cr", "Croatia": "hr", "Cuba": "cu", "Curacao": "cw", "Curaçao": "cw",
    "Cyprus": "cy", "Czechia": "cz", "Côte d'Ivoire": "ci", "Denmark": "dk", "Djibouti": "dj",
    "Dominica": "dm", "Dominican Republic": "do", "Ecuador": "ec", "Egypt": "eg", "El Salvador": "sv",
    "England": "gb-eng", "Equatorial Guinea": "gq", "Eritrea": "er", "Estonia": "ee", "Eswatini": "sz",
    "Ethiopia": "et", "Faroe Islands": "fo", "Fiji": "fj", "Finland": "fi", "France": "fr",
    "Gabon": "ga", "Georgia": "ge", "Germany": "de", "Ghana": "gh", "Gibraltar": "gi",
    "Greece": "gr", "Grenada": "gd", "Guam": "gu", "Guatemala": "gt", "Guinea": "gn",
    "Guinea-Bissau": "gw", "Guyana": "gy", "Haiti": "ht", "Honduras": "hn", "Hong Kong, China": "hk",
    "Hungary": "hu", "IR Iran": "ir", "Iceland": "is", "India": "in", "Indonesia": "id",
    "Iraq": "iq", "Israel": "il", "Italy": "it", "Jamaica": "jm", "Japan": "jp",
    "Jordan": "jo", "Kazakhstan": "kz", "Kenya": "ke", "Korea DPR": "kp", "Korea Republic": "kr",
    "Kosovo": "xk", "Kuwait": "kw", "Kyrgyz Republic": "kg", "Laos": "la", "Latvia": "lv",
    "Lebanon": "lb", "Lesotho": "ls", "Liberia": "lr", "Libya": "ly", "Liechtenstein": "li",
    "Lithuania": "lt", "Luxembourg": "lu", "Macau": "mo", "Madagascar": "mg", "Malawi": "mw",
    "Malaysia": "my", "Maldives": "mv", "Mali": "ml", "Malta": "mt", "Mauritania": "mr",
    "Mauritius": "mu", "Mexico": "mx", "Moldova": "md", "Mongolia": "mn", "Montenegro": "me",
    "Montserrat": "ms", "Morocco": "ma", "Mozambique": "mz", "Myanmar": "mm", "Namibia": "na",
    "Nepal": "np", "Netherlands": "nl", "New Caledonia": "nc", "New Zealand": "nz", "Nicaragua": "ni",
    "Niger": "ne", "Nigeria": "ng", "North Macedonia": "mk", "Northern Ireland": "gb-nir", "Norway": "no",
    "Oman": "om", "Pakistan": "pk", "Palestine": "ps", "Panama": "pa", "Papua New Guinea": "pg",
    "Paraguay": "py", "Peru": "pe", "Philippines": "ph", "Poland": "pl", "Portugal": "pt",
    "Puerto Rico": "pr", "Qatar": "qa", "Republic of Ireland": "ie", "Romania": "ro", "Russia": "ru",
    "Rwanda": "rw", "Samoa": "ws", "San Marino": "sm", "Saudi Arabia": "sa", "Scotland": "gb-sct",
    "Senegal": "sn", "Serbia": "rs", "Seychelles": "sc", "Sierra Leone": "sl", "Singapore": "sg",
    "Slovakia": "sk", "Slovenia": "si", "Solomon Islands": "sb", "Somalia": "so", "South Africa": "za",
    "South Korea": "kr", "South Sudan": "ss", "Spain": "es", "Sri Lanka": "lk", "St Kitts and Nevis": "kn",
    "St Lucia": "lc", "St Vincent and the Grenadines": "vc", "Sudan": "sd", "Suriname": "sr",
    "Sweden": "se", "Switzerland": "ch", "Syria": "sy", "São Tomé and Príncipe": "st", "Tahiti": "pf",
    "Tajikistan": "tj", "Tanzania": "tz", "Thailand": "th", "The Gambia": "gm", "Timor-Leste": "tl",
    "Togo": "tg", "Tonga": "to", "Trinidad and Tobago": "tt", "Tunisia": "tn", "Turkmenistan": "tm",
    "Turks and Caicos Islands": "tc", "Türkiye": "tr", "US Virgin Islands": "vi", "USA": "us",
    "Uganda": "ug", "Ukraine": "ua", "United Arab Emirates": "ae", "Uruguay": "uy", "Uzbekistan": "uz",
    "Vanuatu": "vu", "Venezuela": "ve", "Vietnam": "vn", "Wales": "gb-wls", "Yemen": "ye",
    "Zambia": "zm", "Zimbabwe": "zw",
    "China": "cn", "North Korea": "kp", "Iran": "ir", "Turkey": "tr", "Ivory Coast": "ci",
    "DR Congo": "cd", "Kyrgyzstan": "kg", "Gambia": "gm", "Hong Kong": "hk",
}

SEARCH_ALIASES = {
    "Cape Verde": "Cabo Verde",
    "Cabo Verde": "Cape Verde",
    "Czech Republic": "Czechia",
    "Czechia": "Czech Republic",
    "Democratic Republic of Congo": "Congo DR",
    "DR Congo": "Congo DR",
    "Congo DR": "DR Congo",
    "Iran": "IR Iran",
    "IR Iran": "Iran",
    "Ivory Coast": "Côte d'Ivoire",
    "Cote d'Ivoire": "Côte d'Ivoire",
    "Cote dIvoire": "Côte d'Ivoire",
    "Côte d'Ivoire": "Ivory Coast",
    "Korea Republic": "South Korea",
    "Republic of Korea": "South Korea",
    "South Korea": "Korea Republic",
    "Korea DPR": "North Korea",
    "North Korea": "Korea DPR",
    "Turkey": "Türkiye",
    "Turkiye": "Türkiye",
    "Türkiye": "Turkey",
    "USA": "United States",
    "US": "United States",
    "United States": "USA",
    "United States of America": "United States",
    "Curacao": "Curaçao",
    "Curaçao": "Curacao",
    "Bosnia & Herzegovina": "Bosnia and Herzegovina",
    "Bosnia-Herzegovina": "Bosnia and Herzegovina",
    "China PR": "China",
    "China": "China PR",
    "Kyrgyz Republic": "Kyrgyzstan",
    "Kyrgyzstan": "Kyrgyz Republic",
    "The Gambia": "Gambia",
    "Gambia": "The Gambia",
    "Hong Kong, China": "Hong Kong",
    "Hong Kong": "Hong Kong, China",
    "St Kitts and Nevis": "Saint Kitts and Nevis",
    "Saint Kitts and Nevis": "St Kitts and Nevis",
    "St Lucia": "Saint Lucia",
    "Saint Lucia": "St Lucia",
    "St Vincent and the Grenadines": "Saint Vincent and the Grenadines",
    "Saint Vincent and the Grenadines": "St Vincent and the Grenadines",
}


def render() -> None:
    st.title("FIFA Rankings")
    _styles()

    rankings = _world_cup_rankings()
    global_rankings = _global_rankings()
    if st.session_state.get("selected_ranking_wcq_team") or st.session_state.pop("activate_full_rankings_tab", False):
        _activate_full_rankings_tab()

    tab_world_cup, tab_full = st.tabs(["World Cup Teams", "Full FIFA List"])

    with tab_world_cup:
        _render_world_cup_rankings(rankings)

    with tab_full:
        _render_full_rankings(global_rankings)


def _render_world_cup_rankings(rankings: pd.DataFrame) -> None:
    if rankings.empty:
        st.info("Import FIFA rankings to see World Cup teams here.")
        return
    latest_date = rankings["ranking_date"].max()
    latest = rankings[rankings["ranking_date"] == latest_date].copy()
    latest = latest.sort_values(["rank", "team"], na_position="last")
    st.markdown(_section_title("World Cup Teams", latest_date), unsafe_allow_html=True)
    _render_clickable_world_cup_rankings(latest)


def _render_full_rankings(global_rankings: pd.DataFrame) -> None:
    selected_wcq_team = st.session_state.get("selected_ranking_wcq_team")
    if selected_wcq_team:
        _render_wcq_team_focus(str(selected_wcq_team))
        return

    if global_rankings.empty:
        st.info("Import a FIFA rankings CSV to see the full list here.")
        return
    latest_global_date = global_rankings["ranking_date"].max()
    global_latest = global_rankings[global_rankings["ranking_date"] == latest_global_date].copy()
    global_latest = global_latest.sort_values(["rank", "team_name"], na_position="last")

    target_team = st.session_state.pop("ranking_target_team", "")
    search = st.text_input("Search team", value=target_team)
    if search:
        global_latest = global_latest[_ranking_search_mask(global_latest, search)]

    st.markdown(_section_title("Full FIFA List", latest_global_date), unsafe_allow_html=True)
    clicked_team = clickable_cards(
        _full_ranking_click_cards(global_latest),
        variant="ranking-list",
        key=f"full_ranking_cards_{normalize_team_key(search or 'all')}_{st.session_state.get('ranking_cards_nonce', 0)}",
    )
    if clicked_team:
        _open_full_ranking_team(str(clicked_team), global_latest)


def _activate_full_rankings_tab() -> None:
    components.html(
        """
        <script>
        (() => {
          const doc = window.parent.document;
          const tabText = "Full FIFA List";

          function activate() {
            const tabs = Array.from(doc.querySelectorAll('[role="tab"]'));
            const target = tabs.find(tab => (tab.textContent || "").trim() === tabText);
            if (target && target.getAttribute("aria-selected") !== "true") {
              target.click();
              return true;
            }
            return Boolean(target);
          }

          let attempts = 0;
          const timer = setInterval(() => {
            attempts += 1;
            const found = activate();
            if (found && attempts >= 3) clearInterval(timer);
            if (attempts >= 20) clearInterval(timer);
          }, 100);
        })();
        </script>
        """,
        height=0,
    )


def _world_cup_rankings() -> pd.DataFrame:
    return fetch_df(
        """
        SELECT t.id AS team_id, t.name AS team, t.country_code, g.group_name, r.ranking_date,
               r.rank, r.points, r.previous_rank, r.source
        FROM fifa_rankings r
        JOIN teams t ON t.id = r.team_id
        LEFT JOIN groups g ON g.team_id = t.id
        ORDER BY r.ranking_date DESC, r.rank
        """
    )


def _global_rankings() -> pd.DataFrame:
    global_rankings = fetch_df(
        """
        SELECT gr.team_name, gr.ranking_date, gr.rank, gr.points, gr.previous_rank, gr.source,
               gr.is_world_cup_team, t.country_code
        FROM global_fifa_rankings gr
        LEFT JOIN teams t ON t.name = gr.team_name
        ORDER BY gr.ranking_date DESC, gr.rank
        """
    )
    if not global_rankings.empty:
        global_rankings = global_rankings[global_rankings["team_name"] != "Korea Republic"].copy()
        global_rankings["country_code"] = global_rankings.apply(
            lambda row: _flag_code(str(row["team_name"]), row.get("country_code")),
            axis=1,
        )
    return global_rankings


def _section_title(title: str, ranking_date: str | None) -> str:
    date_text = html.escape(str(ranking_date or "No date"))
    return f'<div class="ranking-section-title"><span>{html.escape(title)}</span><small>{date_text}</small></div>'


def _ranking_cards(rows: pd.DataFrame, team_column: str, compact: bool = False, clickable: bool = False) -> str:
    if rows.empty:
        return '<div class="ranking-empty">No teams match this view.</div>'
    return "".join(_ranking_card(row, team_column, compact, clickable) for _, row in rows.iterrows())


def _ranking_card(row, team_column: str, compact: bool, clickable: bool) -> str:
    team = str(row.get(team_column) or "")
    display_name = _common_team_name(team)
    rank = _rank_text(row.get("rank"))
    group = str(row.get("group_name") or "").strip()
    code = _flag_code(team, row.get("country_code"))
    flag = _flag_img(code, team)
    badge = '<span class="ranking-badge">World Cup</span>' if int(row.get("is_world_cup_team") or 0) == 1 else ""
    group_badge = f'<span class="ranking-badge blue">Group {html.escape(group)}</span>' if group and group.lower() != "nan" else badge
    classes = "ranking-row compact" if compact else "ranking-row"
    card = (
        f'<article class="{classes}">'
        f'<div class="ranking-position">#{rank}</div>'
        f'<div class="ranking-flag">{flag}</div>'
        '<div class="ranking-main">'
        f'<div class="ranking-name">{html.escape(display_name)}</div>'
        f'<div class="ranking-meta">{group_badge}</div>'
        '</div>'
        '</article>'
    )
    return card


def _render_clickable_world_cup_rankings(rows: pd.DataFrame) -> None:
    clicked_team_id = clickable_cards(_ranking_click_cards(rows), variant="rankings", key="world_cup_ranking_cards")
    if clicked_team_id:
        _open_team(int(clicked_team_id))


def _ranking_click_cards(rows: pd.DataFrame) -> list[dict]:
    cards = []
    for _, row in rows.iterrows():
        team = str(row.get("team") or "")
        display_name = _common_team_name(team)
        code = _flag_code(team, row.get("country_code"))
        cards.append(
            {
                "id": int(row["team_id"]),
                "name": display_name,
                "rank": _rank_text(row.get("rank")),
                "group": str(row.get("group_name") or "").strip(),
                "flag_url": f"https://flagcdn.com/w80/{code}.png" if code else "",
            }
        )
    return cards


def _full_ranking_click_cards(rows: pd.DataFrame) -> list[dict]:
    cards = []
    for _, row in rows.iterrows():
        team = str(row.get("team_name") or "")
        display_name = _common_team_name(team)
        code = _flag_code(team, row.get("country_code"))
        cards.append(
            {
                "id": team,
                "name": display_name,
                "rank": _rank_text(row.get("rank")),
                "badge": "World Cup" if int(row.get("is_world_cup_team") or 0) == 1 else "",
                "flag_url": f"https://flagcdn.com/w80/{code}.png" if code else "",
            }
        )
    return cards


def _open_full_ranking_team(team_name: str, rows: pd.DataFrame) -> None:
    key = normalize_team_key(team_name)
    team_rows = rows[
        rows["team_name"].astype(str).map(normalize_team_key).eq(key)
        | rows["team_name"].astype(str).map(_common_team_name).map(normalize_team_key).eq(key)
    ]
    if team_rows.empty:
        return
    row = team_rows.iloc[0]
    if int(row.get("is_world_cup_team") or 0) == 1:
        team_id = _world_cup_team_id(team_name)
        if team_id is not None:
            _open_team(team_id)
            return
    st.session_state["selected_ranking_wcq_team"] = team_name
    st.rerun()


def _world_cup_team_id(team_name: str) -> int | None:
    teams = fetch_df("SELECT id, name FROM teams")
    if teams.empty:
        return None
    key = normalize_team_key(team_name)
    direct = teams[teams["name"].astype(str).map(normalize_team_key).eq(key)]
    if direct.empty:
        alias_keys = {
            normalize_team_key(alias): normalize_team_key(official)
            for alias, official in SEARCH_ALIASES.items()
        }
        official_key = alias_keys.get(key)
        if official_key:
            direct = teams[teams["name"].astype(str).map(normalize_team_key).eq(official_key)]
    if direct.empty:
        return None
    return int(direct.iloc[0]["id"])


def _render_wcq_team_focus(team_name: str) -> None:
    _wcq_styles()
    st.markdown(_section_title("Full FIFA List", "Qualifying Results"), unsafe_allow_html=True)
    if st.button("Back to full rankings", key="close_ranking_wcq_team"):
        st.session_state.pop("selected_ranking_wcq_team", None)
        st.session_state["activate_full_rankings_tab"] = True
        st.session_state["ranking_cards_nonce"] = int(st.session_state.get("ranking_cards_nonce", 0)) + 1
        st.rerun()

    data = load_wcq_data(WCQ_DATA_SCHEMA_VERSION, _wcq_data_signature())
    profile = _wcq_team_profile(data, team_name)
    if not profile["team_name"]:
        st.info(f"No qualifying results are stored for {team_name} yet.")
        return
    _render_wcq_profile_hero(profile)
    _render_wcq_round_results(profile, data)


def _wcq_team_profile(data: dict, team_name: str) -> dict:
    keys = _team_lookup_keys(team_name)
    standings = _matching_team_rows(data.get("standings", pd.DataFrame()), keys)
    eliminated = _matching_team_rows(data.get("eliminated", pd.DataFrame()), keys)
    qualified = _matching_team_rows(data.get("qualified", pd.DataFrame()), keys)
    runner_up = _matching_team_rows(data.get("runners_up_ranking", pd.DataFrame()), keys)
    matches = _matching_match_rows(data.get("matches", pd.DataFrame()), keys)
    ties = _matching_tie_rows(data.get("playoff_ties", pd.DataFrame()), keys)
    round_names = _round_name_lookup(data.get("rounds", pd.DataFrame()))

    source_rows = [frame for frame in [eliminated, qualified, standings, runner_up] if not frame.empty]
    source = source_rows[0].iloc[0] if source_rows else None
    display_name = _row_value(source, "team_name", team_name) if source is not None else ""
    team_key = normalize_team_key(display_name or team_name)
    return {
        "team_name": display_name,
        "team_key": team_key,
        "standings": standings,
        "eliminated": eliminated,
        "qualified": qualified,
        "runner_up": runner_up,
        "matches": matches,
        "ties": ties,
        "rounds": data.get("rounds", pd.DataFrame()),
        "brackets": data.get("brackets", pd.DataFrame()),
        "summary": _wcq_summary_text(eliminated, qualified, standings, runner_up),
        "confederation": _row_value(source, "confederation_id", "") if source is not None else "",
        "flag_code": _row_value(source, "flag_code", "") if source is not None else "",
        "fifa_code": _row_value(source, "fifa_code", "") if source is not None else "",
        "rank": _row_value(source, "fifa_rank", "") if source is not None else "",
        "round_names": round_names,
        "stage": _wcq_stage_text(eliminated, qualified, standings, runner_up, round_names),
        "final_record": _wcq_final_record(standings, runner_up),
        "final_position": _wcq_final_position(eliminated, standings, runner_up),
    }


def _team_lookup_keys(team_name: str) -> set[str]:
    keys = set(shared_team_lookup_keys(team_name))
    for alias, official in SEARCH_ALIASES.items():
        alias_key = normalize_team_key(alias)
        official_key = normalize_team_key(official)
        if keys & {alias_key, official_key}:
            keys.update({alias_key, official_key})
    wcq_aliases = {
        "congo dr": "dr congo",
        "cabo verde": "cape verde",
        "cape verde": "cabo verde",
        "ir iran": "iran",
        "korea dpr": "north korea",
        "korea republic": "south korea",
        "hong kong china": "hong kong",
        "brunei darussalam": "brunei",
        "usa": "united states",
        "china pr": "china",
        "kyrgyz republic": "kyrgyzstan",
        "the gambia": "gambia",
        "hong kong china": "hong kong",
        "st kitts and nevis": "saint kitts and nevis",
        "st lucia": "saint lucia",
        "st vincent and the grenadines": "saint vincent and the grenadines",
    }
    for left, right in wcq_aliases.items():
        if keys & {normalize_team_key(left), normalize_team_key(right)}:
            keys.update({normalize_team_key(left), normalize_team_key(right)})
    return keys


def _matching_team_rows(frame: pd.DataFrame, keys: set[str]) -> pd.DataFrame:
    if frame.empty or "team_name" not in frame.columns:
        return pd.DataFrame()
    return frame[frame["team_name"].astype(str).map(normalize_team_key).isin(keys)].copy()


def _matching_match_rows(frame: pd.DataFrame, keys: set[str]) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    home = frame.get("home_team_name", pd.Series("", index=frame.index)).astype(str).map(normalize_team_key).isin(keys)
    away = frame.get("away_team_name", pd.Series("", index=frame.index)).astype(str).map(normalize_team_key).isin(keys)
    rows = frame[home | away].copy()
    if not rows.empty:
        rows["_date"] = pd.to_datetime(rows.get("date", ""), errors="coerce")
        rows["_order"] = pd.to_numeric(rows.get("match_order", ""), errors="coerce").fillna(999)
        rows = rows.sort_values(["_date", "_order", "match_id"], na_position="last")
    return rows


def _matching_tie_rows(frame: pd.DataFrame, keys: set[str]) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    mask = pd.Series(False, index=frame.index)
    for column in ["team1_name", "team2_name", "team_1_name", "team_2_name", "home_team_name", "away_team_name"]:
        if column in frame.columns:
            mask = mask | frame[column].astype(str).map(normalize_team_key).isin(keys)
    return frame[mask].copy()


def _wcq_summary_text(eliminated: pd.DataFrame, qualified: pd.DataFrame, standings: pd.DataFrame, runner_up: pd.DataFrame) -> str:
    if not eliminated.empty:
        row = eliminated.iloc[-1]
        reason = _row_value(row, "elimination_reason", _row_value(row, "notes", "Eliminated in qualifying."))
        final_position = _row_value(row, "final_position", "")
        return " | ".join(part for part in [reason, final_position] if part)
    if not qualified.empty:
        row = qualified.iloc[0]
        return _row_value(row, "qualification_method", "Qualified for the World Cup.")
    if not runner_up.empty:
        row = runner_up.iloc[-1]
        return _row_value(row, "notes", _row_value(row, "status", "Runner-up ranking result recorded."))
    if not standings.empty:
        row = standings.iloc[-1]
        return _row_value(row, "notes", _row_value(row, "status", "Qualifying standings are recorded."))
    return ""


def _round_name_lookup(rounds: pd.DataFrame) -> dict[str, str]:
    if rounds.empty or "round_id" not in rounds.columns:
        return {}
    return {
        str(row.get("round_id", "")): _row_value(row, "round_name", str(row.get("round_id", "")))
        for _, row in rounds.iterrows()
        if str(row.get("round_id", "")).strip()
    }


def _wcq_stage_text(
    eliminated: pd.DataFrame,
    qualified: pd.DataFrame,
    standings: pd.DataFrame,
    runner_up: pd.DataFrame,
    round_names: dict[str, str],
) -> str:
    if not eliminated.empty:
        row = eliminated.iloc[-1]
        round_name = _display_round_name(_row_value(row, "round_id", ""), round_names) or "Qualifying"
        return f"Eliminated in {round_name}"
    if not qualified.empty:
        row = qualified.iloc[0]
        return _row_value(row, "qualification_round", "Qualified")
    if not runner_up.empty:
        return "Runner-up ranking"
    if not standings.empty:
        row = standings.iloc[-1]
        return _display_round_name(_row_value(row, "round_id", ""), round_names) or "Qualifying"
    return "Qualifying"


def _wcq_final_record(standings: pd.DataFrame, runner_up: pd.DataFrame) -> str:
    if not runner_up.empty:
        return _record_text(runner_up.iloc[-1])
    if not standings.empty:
        return _record_text(standings.iloc[-1])
    return ""


def _wcq_final_position(eliminated: pd.DataFrame, standings: pd.DataFrame, runner_up: pd.DataFrame) -> str:
    if not eliminated.empty:
        return _row_value(eliminated.iloc[-1], "final_position", "")
    if not runner_up.empty:
        row = runner_up.iloc[-1]
        rank = _row_value(row, "runner_up_rank", "")
        group = _row_value(row, "group_name", "")
        return " | ".join(part for part in [f"Runner-up rank {rank}" if rank else "", group] if part)
    if not standings.empty:
        row = standings.iloc[-1]
        position = _row_value(row, "position", "")
        group = _row_value(row, "group_id", _row_value(row, "group_name", ""))
        return " | ".join(part for part in [f"Position {position}" if position else "", group] if part)
    return ""


def _render_wcq_profile_hero(profile: dict) -> None:
    code = str(profile.get("flag_code") or "").lower()
    background = f"https://flagcdn.com/w1280/{html.escape(code)}.png" if code else ""
    background_style = (
        f"linear-gradient(90deg, rgba(3,7,18,.88), rgba(3,7,18,.70)), url('{background}')"
        if background
        else "linear-gradient(135deg, rgba(5,5,5,.82), rgba(11,16,32,.72))"
    )
    meta = " | ".join(
        part
        for part in [
            str(profile.get("confederation") or ""),
            f"FIFA rank {profile.get('rank')}" if profile.get("rank") else "",
        ]
        if part
    )
    st.markdown(
        f"""
        <section class="wcq-team-profile-hero" style="background-image: {background_style};">
          <div>
            <div class="wcq-team-profile-kicker">{html.escape(meta)}</div>
            <h2>{html.escape(profile["team_name"])}</h2>
            <p>{html.escape(profile["stage"])}</p>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _render_wcq_elimination_panel(profile: dict) -> None:
    stats = [
        ("Status", "Eliminated" if profile["eliminated"].empty is False else "Qualified" if profile["qualified"].empty is False else "Recorded"),
        ("Final stage", str(profile.get("stage") or "Qualifying")),
        ("Final position", str(profile.get("final_position") or "Not listed")),
        ("Record", str(profile.get("final_record") or "Not listed")),
    ]
    stat_markup = "".join(
        f'<div class="wcq-profile-stat"><span>{html.escape(label)}</span><strong>{html.escape(value)}</strong></div>'
        for label, value in stats
    )
    st.markdown(
        f"""
        <section class="wcq-profile-summary">
          <div>
            <div class="wcq-profile-summary-kicker">Qualifying outcome</div>
            <h3>{html.escape(profile["summary"] or "Qualifying outcome is recorded.")}</h3>
          </div>
          <div class="wcq-profile-stats">{stat_markup}</div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _render_wcq_path(profile: dict) -> None:
    rows = _important_path_rows(profile)
    if rows.empty:
        return
    body = "".join(
        "<tr>"
        f"<td>{html.escape(_row_value(row, 'stage'))}</td>"
        f"<td>{html.escape(_row_value(row, 'group'))}</td>"
        f"<td>{html.escape(_row_value(row, 'position', '-'))}</td>"
        f"<td>{html.escape(_record_text(row))}</td>"
        f"<td>{html.escape(_row_value(row, 'points', '0'))}</td>"
        f"<td>{html.escape(_clean_status(_row_value(row, 'status', '')))}</td>"
        "</tr>"
        for _, row in rows.iterrows()
    )
    _render_wcq_table("Qualifying Path", "<th>Stage</th><th>Group / Table</th><th>Place</th><th>W-D-L</th><th>Pts</th><th>Status</th>", body)


def _important_path_rows(profile: dict) -> pd.DataFrame:
    rows = []
    standings = profile["standings"].copy()
    if not standings.empty:
        standings["_position"] = pd.to_numeric(standings.get("position", ""), errors="coerce").fillna(999)
        standings = standings.sort_values(["confederation_id", "round_id", "group_id", "_position"])
        for _, row in standings.iterrows():
            item = row.copy()
            item["stage"] = _display_round_name(_row_value(row, "round_id", ""), profile["round_names"])
            item["group"] = _row_value(row, "group_name", _row_value(row, "group_id", ""))
            rows.append(item)
    runner_up = profile["runner_up"].copy()
    if not runner_up.empty:
        for _, row in runner_up.iterrows():
            item = row.copy()
            item["stage"] = "Runner-up ranking"
            item["group"] = _row_value(row, "group_name", "")
            item["position"] = _row_value(row, "runner_up_rank", "")
            item["played"] = _row_value(row, "played_counting_results", _row_value(row, "played", ""))
            rows.append(item)
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _render_wcq_round_results(profile: dict, data: dict) -> None:
    round_ids = _profile_round_ids(profile)
    if not round_ids:
        return
    st.markdown('<section class="wcq-profile-results"><h3>Qualifying Results</h3></section>', unsafe_allow_html=True)
    rendered_icpo_paths: set[str] = set()
    for round_id in round_ids:
        _render_wcq_round_result(profile, data, round_id, rendered_icpo_paths)


def _profile_round_ids(profile: dict) -> list[str]:
    round_ids: set[str] = set()
    for key in ["matches", "ties", "standings", "runner_up", "eliminated", "qualified"]:
        frame = profile.get(key, pd.DataFrame())
        if isinstance(frame, pd.DataFrame) and not frame.empty and "round_id" in frame.columns:
            round_ids.update(str(value) for value in frame["round_id"] if str(value).strip())
    return sorted(round_ids, key=lambda round_id: _round_sort_key(round_id, profile.get("rounds", pd.DataFrame())))


def _round_sort_key(round_id: str, rounds: pd.DataFrame) -> tuple[float, pd.Timestamp, str]:
    if rounds.empty or "round_id" not in rounds.columns:
        return (999, pd.NaT, round_id)
    match = rounds[rounds["round_id"].astype(str).eq(str(round_id))]
    if match.empty:
        return (999, pd.NaT, round_id)
    row = match.iloc[0]
    order = pd.to_numeric(_row_value(row, "round_order", ""), errors="coerce")
    start = pd.to_datetime(_row_value(row, "start_date", ""), errors="coerce")
    return (float(order) if not pd.isna(order) else 999, start, round_id)


def _render_wcq_round_result(profile: dict, data: dict, round_id: str, rendered_icpo_paths: set[str]) -> None:
    confederation_id = _profile_round_confederation(profile, data, round_id)
    round_name = _display_round_name(round_id, profile["round_names"])

    matches = _wcq_round_rows(data.get("matches", pd.DataFrame()), round_id, confederation_id)
    brackets = _wcq_round_rows(data.get("brackets", pd.DataFrame()), round_id, confederation_id)
    team_matches = _round_subset(profile.get("matches", pd.DataFrame()), round_id)
    team_ties = _round_subset(profile.get("ties", pd.DataFrame()), round_id)
    team_standings = _round_subset(profile.get("standings", pd.DataFrame()), round_id)
    team_runner_up = _round_subset(profile.get("runner_up", pd.DataFrame()), round_id)

    icpo_status = _render_inter_confederation_path_if_available(profile, data, round_id, round_name, rendered_icpo_paths)
    if icpo_status == "rendered":
        return
    if icpo_status == "already_rendered":
        return

    if not matches.empty and _wcq_has_bracket_shape(matches, brackets):
        bracket_matches, bracket_rows = _team_bracket_tournament(matches, brackets, team_matches)
        if bracket_matches.empty:
            bracket_matches = team_matches
        if bracket_matches.empty:
            return
        st.markdown(f'<div class="ranking-wcq-round-title">{html.escape(round_name)}</div>', unsafe_allow_html=True)
        _render_wcq_tournament_bracket(bracket_matches, bracket_rows, confederation_id)
        return

    if team_ties.empty and team_matches.empty and team_standings.empty and team_runner_up.empty:
        return
    st.markdown(f'<div class="ranking-wcq-round-title">{html.escape(round_name)}</div>', unsafe_allow_html=True)

    if not team_ties.empty and _wcq_is_two_leg_round(round_id, confederation_id, data):
        _render_wcq_playoff_ties(team_ties, confederation_id)
    elif not team_ties.empty:
        _render_wcq_ties(team_ties, profile["team_key"], profile["round_names"])

    if not team_matches.empty:
        _render_wcq_matches(team_matches, profile["team_key"], profile["round_names"], show_title=False)
    _render_round_group_details(data, round_id, confederation_id, team_standings, team_runner_up)


def _round_subset(frame: pd.DataFrame, round_id: str) -> pd.DataFrame:
    if frame.empty or "round_id" not in frame.columns:
        return pd.DataFrame()
    return frame[frame["round_id"].astype(str).eq(str(round_id))].copy()


def _round_confederation(data: dict, round_id: str) -> str:
    rounds = data.get("rounds", pd.DataFrame())
    if not isinstance(rounds, pd.DataFrame) or rounds.empty or "round_id" not in rounds.columns:
        return ""
    rows = rounds[rounds["round_id"].astype(str).eq(str(round_id))]
    if rows.empty:
        return ""
    return _row_value(rows.iloc[0], "confederation_id", "")


def _profile_round_confederation(profile: dict, data: dict, round_id: str) -> str:
    for key in ["matches", "ties", "standings", "runner_up", "eliminated", "qualified"]:
        rows = _round_subset(profile.get(key, pd.DataFrame()), round_id)
        if not rows.empty and "confederation_id" in rows.columns:
            confederation_id = _row_value(rows.iloc[0], "confederation_id", "")
            if confederation_id:
                return confederation_id
    return _round_confederation(data, round_id) or str(profile.get("confederation") or "")


def _team_bracket_tournament(matches: pd.DataFrame, brackets: pd.DataFrame, team_matches: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if team_matches.empty:
        return pd.DataFrame(columns=matches.columns), pd.DataFrame(columns=brackets.columns)
    bracket_ids = _nonempty_values(team_matches, "bracket_id")
    match_ids = _nonempty_values(team_matches, "match_id")
    if not bracket_ids and not brackets.empty and "match_id" in brackets.columns:
        team_bracket_rows = brackets[brackets["match_id"].astype(str).isin(match_ids)]
        bracket_ids = _nonempty_values(team_bracket_rows, "bracket_id")
    if bracket_ids:
        bracket_matches = matches[matches.get("bracket_id", pd.Series("", index=matches.index)).astype(str).isin(bracket_ids)].copy()
        bracket_rows = brackets[brackets.get("bracket_id", pd.Series("", index=brackets.index)).astype(str).isin(bracket_ids)].copy()
        return bracket_matches, bracket_rows
    return team_matches.copy(), pd.DataFrame(columns=brackets.columns)


def _nonempty_values(frame: pd.DataFrame, column: str) -> set[str]:
    if frame.empty or column not in frame.columns:
        return set()
    return {str(value).strip() for value in frame[column] if str(value).strip()}


def _render_inter_confederation_path_if_available(profile: dict, data: dict, round_id: str, round_name: str, rendered_paths: set[str]) -> str:
    if "icpo" not in str(round_id).lower() and "inter" not in str(round_id).lower():
        return ""
    matches = _wcq_canonical_inter_confederation_matches(data)
    if matches.empty or "_icpo_path" not in matches.columns:
        return ""
    team_key = str(profile.get("team_key") or "")
    team_mask = (
        matches.get("home_team_name", pd.Series("", index=matches.index)).astype(str).map(normalize_team_key).eq(team_key)
        | matches.get("away_team_name", pd.Series("", index=matches.index)).astype(str).map(normalize_team_key).eq(team_key)
    )
    team_rows = matches[team_mask]
    if team_rows.empty:
        return ""
    path_names = [str(path_name) for path_name in sorted(team_rows["_icpo_path"].dropna().unique())]
    rendered = False
    for path_name in path_names:
        path_name = str(path_name)
        if path_name in rendered_paths:
            continue
        path_matches = matches[matches["_icpo_path"].eq(path_name)].copy()
        if path_matches.empty:
            continue
        path_matches["_stage_order"] = path_matches["_icpo_stage"].map({"Semi-Final": 1, "Final": 2}).fillna(99)
        path_matches["_date"] = pd.to_datetime(path_matches.get("date", ""), errors="coerce")
        if not rendered:
            st.markdown(f'<div class="ranking-wcq-round-title">{html.escape(round_name)}</div>', unsafe_allow_html=True)
        st.markdown(_wcq_inter_confederation_path_html(path_name, path_matches), unsafe_allow_html=True)
        rendered_paths.add(path_name)
        rendered = True
    if rendered:
        return "rendered"
    return "already_rendered" if path_names else ""


def _render_wcq_matches(rows: pd.DataFrame, team_key: str, round_names: dict[str, str], show_title: bool = True) -> None:
    if rows.empty:
        return
    cards = "".join(_wcq_match_card(row, team_key, round_names) for _, row in rows.iterrows())
    title = "<h3>Qualifying Results</h3>" if show_title else ""
    st.markdown(
        f"""
        <section class="wcq-profile-results">
          {title}
          <div class="wcq-profile-result-grid">{cards}</div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _render_round_group_details(
    data: dict,
    round_id: str,
    confederation_id: str,
    team_standings: pd.DataFrame,
    runner_up: pd.DataFrame,
) -> None:
    if team_standings.empty and runner_up.empty:
        return
    if not team_standings.empty:
        all_standings = _wcq_round_rows(data.get("standings", pd.DataFrame()), round_id, confederation_id)
        group_ids = _nonempty_values(team_standings, "group_id")
        if group_ids:
            all_standings = all_standings[all_standings.get("group_id", pd.Series("", index=all_standings.index)).astype(str).isin(group_ids)].copy()
        else:
            team_names = _nonempty_values(team_standings, "team_name")
            all_standings = all_standings[all_standings.get("team_name", pd.Series("", index=all_standings.index)).astype(str).isin(team_names)].copy()
        if not all_standings.empty:
            all_standings["_position"] = pd.to_numeric(all_standings.get("position", ""), errors="coerce").fillna(999)
            all_standings = all_standings.sort_values(["_position", "team_name"])
            group_name = _display_group_name(_row_value(team_standings.iloc[0], "group_name", _row_value(team_standings.iloc[0], "group_id", "Group Table")))
            st.markdown(f'<div class="ranking-wcq-group-title">{html.escape(group_name)}</div>', unsafe_allow_html=True)
            _render_group_standings_table(all_standings)
    if not runner_up.empty:
        st.markdown('<div class="ranking-wcq-group-title">Runner-up Ranking</div>', unsafe_allow_html=True)
        _render_runner_up_detail_table(runner_up)


def _render_group_standings_table(rows: pd.DataFrame) -> None:
    header = """
        <div class="ranking-wcq-standings-row ranking-wcq-standings-head">
          <span>Pos</span><span>Team</span><span>P</span><span>W</span><span>D</span><span>L</span><span>GD</span><span>Pts</span><span>Status</span>
        </div>
    """
    body = "".join(_group_standings_row(row) for _, row in rows.iterrows())
    st.markdown(f'<div class="ranking-wcq-standings-table">{header}{body}</div>', unsafe_allow_html=True)


def _group_standings_row(row: pd.Series) -> str:
    return (
        '<div class="ranking-wcq-standings-row">'
        f'<span>{html.escape(_row_value(row, "position", "-"))}</span>'
        f'<span>{html.escape(_row_value(row, "team_name", "Team TBD"))}</span>'
        f'<span>{html.escape(_row_value(row, "played", "0"))}</span>'
        f'<span>{html.escape(_row_value(row, "wins", "0"))}</span>'
        f'<span>{html.escape(_row_value(row, "draws", "0"))}</span>'
        f'<span>{html.escape(_row_value(row, "losses", "0"))}</span>'
        f'<span>{html.escape(_row_value(row, "goal_difference", "0"))}</span>'
        f'<span>{html.escape(_row_value(row, "points", "0"))}</span>'
        f'<span class="ranking-wcq-status">{html.escape(_clean_status(_row_value(row, "status", "")))}</span>'
        '</div>'
    )


def _display_group_name(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return "Group Table"
    normalized = text.replace("-", "_").replace(" ", "_").upper()
    if "_GRP_" in normalized:
        suffix = normalized.rsplit("_GRP_", 1)[-1]
        if suffix:
            return f"Group {suffix}"
    if normalized.startswith("GROUP_"):
        suffix = normalized.rsplit("_", 1)[-1]
        if suffix:
            return f"Group {suffix}"
    return text.replace("_", " ").title()


def _render_runner_up_detail_table(rows: pd.DataFrame) -> None:
    header = """
        <div class="ranking-wcq-standings-row ranking-wcq-standings-head">
          <span>Rank</span><span>Team</span><span>P</span><span>W</span><span>D</span><span>L</span><span>GD</span><span>Pts</span><span>Status</span>
        </div>
    """
    body = "".join(
        '<div class="ranking-wcq-standings-row">'
        f'<span>{html.escape(_row_value(row, "runner_up_rank", "-"))}</span>'
        f'<span>{html.escape(_row_value(row, "team_name", "Team TBD"))}</span>'
        f'<span>{html.escape(_row_value(row, "played_counting_results", _row_value(row, "played", "0")))}</span>'
        f'<span>{html.escape(_row_value(row, "wins", "0"))}</span>'
        f'<span>{html.escape(_row_value(row, "draws", "0"))}</span>'
        f'<span>{html.escape(_row_value(row, "losses", "0"))}</span>'
        f'<span>{html.escape(_row_value(row, "goal_difference", "0"))}</span>'
        f'<span>{html.escape(_row_value(row, "points", "0"))}</span>'
        f'<span class="ranking-wcq-status">{html.escape(_clean_status(_row_value(row, "status", "")))}</span>'
        '</div>'
        for _, row in rows.iterrows()
    )
    st.markdown(f'<div class="ranking-wcq-standings-table">{header}{body}</div>', unsafe_allow_html=True)


def _render_wcq_ties(rows: pd.DataFrame, team_key: str, round_names: dict[str, str]) -> None:
    if rows.empty:
        return
    body = "".join(
        "<tr>"
        f"<td>{html.escape(_row_value(row, 'round_name', _display_round_name(_row_value(row, 'round_id'), round_names)))}</td>"
        f"<td>{html.escape(_row_value(row, 'team1_name'))} vs {html.escape(_row_value(row, 'team2_name'))}</td>"
        f"<td>{html.escape(_row_value(row, 'aggregate_score', '-'))}</td>"
        f"<td>{html.escape(_tie_result_text(row, team_key))}</td>"
        "</tr>"
        for _, row in rows.iterrows()
    )
    _render_wcq_table("Playoff Ties", "<th>Round</th><th>Tie</th><th>Aggregate</th><th>Result</th>", body)


def _render_wcq_table(title: str, header: str, body: str) -> None:
    st.markdown(
        f"""
        <section class="ranking-wcq-table-shell">
          <h3>{html.escape(title)}</h3>
          <div class="ranking-wcq-table-wrap">
            <table class="ranking-wcq-table">
              <thead><tr>{header}</tr></thead>
              <tbody>{body}</tbody>
            </table>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _wcq_match_card(row: pd.Series, team_key: str, round_names: dict[str, str]) -> str:
    home = _row_value(row, "home_team_name", "TBD")
    away = _row_value(row, "away_team_name", "TBD")
    result = _match_result_text(row, team_key)
    result_class = _safe_key(result or "scheduled")
    return (
        f'<article class="wcq-profile-result-card {html.escape(result_class)}">'
        f'<div class="wcq-profile-result-top"><span>{html.escape(_format_short_date(_row_value(row, "date", "")))}</span><span>{html.escape(_display_round_name(_row_value(row, "round_id", ""), round_names))}</span></div>'
        '<div class="wcq-profile-result-match">'
        f'{_wcq_result_team(row, "home", home)}'
        f'<strong>{html.escape(_match_score(row))}</strong>'
        f'{_wcq_result_team(row, "away", away)}'
        '</div>'
        f'<div class="wcq-profile-result-status">{html.escape(result or "Result TBD")}</div>'
        '</article>'
    )


def _wcq_result_team(row: pd.Series, side: str, name: str) -> str:
    code = _row_value(row, f"{side}_flag_code", "").lower()
    if not code:
        code = _flag_code(name, "")
    flag = _flag_img(code, name)
    return f'<span class="wcq-profile-result-team">{flag}<em>{html.escape(name)}</em></span>'


def _match_score(row: pd.Series) -> str:
    home = _row_value(row, "home_score", "")
    away = _row_value(row, "away_score", "")
    if not home or not away:
        return "vs"
    penalties = _row_value(row, "penalties", "")
    return f"{home}-{away}" + (f" ({penalties} pens)" if penalties else "")


def _display_round_name(round_id: str, round_names: dict[str, str]) -> str:
    value = str(round_id or "").strip()
    if not value:
        return ""
    return round_names.get(value, value.replace("_", " ").title())


def _clean_status(value: str) -> str:
    text = str(value or "").replace("_", " ").strip()
    return text.title() if text else "Recorded"


def _format_short_date(value: str) -> str:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return value
    return f"{parsed.strftime('%b')} {parsed.day}, {parsed.year}"


def _match_result_text(row: pd.Series, team_key: str) -> str:
    winner_id = _row_value(row, "winning_team_id", "")
    if winner_id:
        home_won = winner_id == _row_value(row, "home_team_id", "")
        away_won = winner_id == _row_value(row, "away_team_id", "")
        if home_won and normalize_team_key(_row_value(row, "home_team_name")) == team_key:
            return "Won"
        if away_won and normalize_team_key(_row_value(row, "away_team_name")) == team_key:
            return "Won"
        if home_won or away_won:
            return "Lost"
    home_score = pd.to_numeric(_row_value(row, "home_score", ""), errors="coerce")
    away_score = pd.to_numeric(_row_value(row, "away_score", ""), errors="coerce")
    if pd.isna(home_score) or pd.isna(away_score):
        return ""
    is_home = normalize_team_key(_row_value(row, "home_team_name")) == team_key
    team_score = home_score if is_home else away_score
    opponent_score = away_score if is_home else home_score
    if team_score > opponent_score:
        return "Won"
    if team_score < opponent_score:
        return "Lost"
    return "Drew"


def _tie_result_text(row: pd.Series, team_key: str) -> str:
    winner = _row_value(row, "winner_team_id", "")
    loser = _row_value(row, "loser_team_id", "")
    team1_is_team = normalize_team_key(_row_value(row, "team1_name")) == team_key
    team_id = _row_value(row, "team1_id" if team1_is_team else "team2_id", "")
    if winner and team_id == winner:
        return "Won tie"
    if loser and team_id == loser:
        return "Lost tie"
    return ""


def _record_text(row: pd.Series) -> str:
    return f"{_row_value(row, 'wins', '0')}-{_row_value(row, 'draws', '0')}-{_row_value(row, 'losses', '0')}"


def _safe_key(value: str) -> str:
    return "".join(character.lower() if character.isalnum() else "_" for character in str(value)).strip("_")


def _row_value(row: pd.Series | None, key: str, default: str = "") -> str:
    if row is None or key not in row:
        return default
    value = row.get(key, default)
    if pd.isna(value) or str(value).strip() == "":
        return default
    return str(value).strip()


def _open_team(team_id: int) -> None:
    remember_detail_origin("team_return_origin")
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


def _flag_code(team: str, stored_code=None) -> str:
    code = FLAG_CODES.get(team) or flag_code_for_common_team(team) or stored_code or ""
    return str(code).strip().lower()


def _flag_img(code: str, team: str) -> str:
    initials = "".join(part[0] for part in str(team).replace("-", " ").split()[:2]).upper() or "?"
    if not code:
        return f'<div class="ranking-flag-fallback">{html.escape(initials)}</div>'
    return (
        f'<img src="https://flagcdn.com/w80/{html.escape(code)}.png" alt="{html.escape(team)} flag" '
        f'onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'grid\';">'
        f'<div class="ranking-flag-fallback hidden">{html.escape(initials)}</div>'
    )


def _common_team_name(team_name: str) -> str:
    return display_team_name(team_name)


def _rank_text(value) -> str:
    if pd.isna(value):
        return "TBD"
    return str(int(value))


def _ranking_search_mask(rows: pd.DataFrame, search: str) -> pd.Series:
    terms = {search}
    normalized_search = normalize_team_key(search)
    for alias, official in SEARCH_ALIASES.items():
        if normalized_search in {normalize_team_key(alias), normalize_team_key(official)}:
            terms.update({alias, official})
    direct_terms = [term for term in terms if len(str(term).strip()) >= 3]
    direct = (
        (
            rows["team_name"].str.contains("|".join(re.escape(term) for term in direct_terms), case=False, na=False)
            | rows["team_name"].map(_common_team_name).str.contains("|".join(re.escape(term) for term in direct_terms), case=False, na=False)
        )
        if direct_terms
        else pd.Series(False, index=rows.index)
    )
    normalized_terms = {normalize_team_key(term) for term in terms if term}
    normalized = rows["team_name"].map(normalize_team_key).isin(normalized_terms) | rows["team_name"].map(_common_team_name).map(normalize_team_key).isin(normalized_terms)
    return direct | normalized


def _styles() -> None:
    st.markdown(
        """
        <style>
        [data-testid="stTextInput"] label,
        [data-testid="stTextInput"] label p {
            color: #FFFFFF !important;
            font-weight: 850;
        }
        [data-testid="stTabs"] [role="tab"] {
            min-width: 190px !important;
            width: 190px !important;
            padding-left: 1.15rem !important;
            padding-right: 1.15rem !important;
            justify-content: center !important;
            white-space: nowrap;
        }
        [data-testid="stTabs"] [role="tab"] p {
            min-width: max-content !important;
            white-space: nowrap;
        }
        .ranking-hero {
            border: 1px solid rgba(214,168,58,.32);
            border-radius: 8px;
            background:
                linear-gradient(135deg, rgba(5,5,5,.76), rgba(11,16,32,.64)),
                radial-gradient(circle at 82% 18%, rgba(36,88,255,.24), transparent 30%),
                radial-gradient(circle at 18% 82%, rgba(35,215,215,.16), transparent 30%);
            display: flex;
            justify-content: space-between;
            gap: 1.4rem;
            margin: .4rem 0 1.1rem;
            padding: 1.15rem 1.25rem;
        }
        .ranking-hero span, .ranking-section-title span {
            color: #D6A83A;
            font-size: .82rem;
            font-weight: 950;
            letter-spacing: .04em;
            text-transform: uppercase;
        }
        .ranking-hero h2 {
            color: #FFFFFF;
            font-size: 2.15rem;
            font-weight: 950;
            line-height: .95;
            margin: .15rem 0 0;
        }
        .ranking-hero p {
            color: #E5E7EB;
            font-weight: 750;
            max-width: 520px;
            margin: 0;
        }
        .ranking-section-title {
            align-items: baseline;
            border-bottom: 1px solid rgba(214,168,58,.24);
            display: flex;
            justify-content: space-between;
            margin: .85rem 0 .75rem;
            padding-bottom: .55rem;
        }
        .ranking-section-title small {
            color: #CBD5E1;
            font-weight: 800;
        }
        .ranking-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: .75rem;
        }
        .ranking-list {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: .55rem;
        }
        .ranking-card-link {
            color: inherit;
            display: block;
            text-decoration: none !important;
        }
        .ranking-card-link:hover,
        .ranking-card-link:focus {
            color: inherit;
            text-decoration: none !important;
        }
        .ranking-card-link:hover .ranking-row {
            border-color: rgba(214,168,58,.68);
            box-shadow: 0 16px 38px rgba(0,0,0,.24);
            transform: translateY(-1px);
        }
        .ranking-row {
            align-items: center;
            border: 1px solid rgba(214,168,58,.22);
            border-radius: 8px;
            background:
                linear-gradient(135deg, rgba(5,5,5,.58), rgba(11,16,32,.54)),
                radial-gradient(circle at 100% 0%, rgba(214,168,58,.14), transparent 34%);
            display: grid;
            grid-template-columns: 72px 74px 1fr;
            gap: .85rem;
            min-height: 104px;
            padding: .75rem;
            box-shadow: 0 12px 30px rgba(0,0,0,.16);
            transition: border-color .15s ease, box-shadow .15s ease, transform .15s ease;
        }
        .ranking-row.compact {
            grid-template-columns: 58px 58px 1fr;
            min-height: 76px;
            padding: .58rem;
        }
        .ranking-position {
            color: #D6A83A;
            font-size: 1.55rem;
            font-weight: 950;
            text-align: center;
        }
        .ranking-flag img, .ranking-flag-fallback {
            aspect-ratio: 3 / 2;
            border: 1px solid rgba(255,255,255,.52);
            border-radius: 6px;
            box-shadow: 0 8px 18px rgba(0,0,0,.34);
            display: block;
            object-fit: cover;
            object-position: center;
            width: 100%;
        }
        .ranking-flag-fallback {
            align-items: center;
            background: linear-gradient(135deg, rgba(214,168,58,.35), rgba(36,88,255,.22));
            color: #FFFFFF;
            display: grid;
            font-weight: 950;
            justify-content: center;
        }
        .ranking-flag-fallback.hidden {
            display: none;
        }
        .ranking-name {
            color: #FFFFFF;
            font-size: 1.08rem;
            font-weight: 950;
            line-height: 1.05;
        }
        .ranking-meta {
            align-items: center;
            color: #CBD5E1;
            display: flex;
            flex-wrap: wrap;
            gap: .35rem .55rem;
            font-size: .76rem;
            font-weight: 800;
            margin-top: .4rem;
            text-transform: uppercase;
        }
        .ranking-badge {
            border: 1px solid rgba(214,168,58,.42);
            border-radius: 999px;
            color: #D6A83A;
            padding: .1rem .45rem;
        }
        .ranking-badge.blue {
            border-color: rgba(35,215,215,.36);
            color: #23D7D7;
        }
        .ranking-empty {
            color: #D6A83A;
            font-weight: 850;
            padding: 1rem 0;
        }
        .wcq-team-profile-hero {
            align-items: center;
            background-position: center;
            background-size: cover;
            border: 1px solid rgba(255,255,255,.18);
            border-radius: 22px;
            box-shadow: 0 16px 50px rgba(15,23,42,.28);
            display: grid;
            gap: 1.35rem;
            grid-template-columns: 1fr;
            margin: 1rem 0 1.25rem;
            min-height: 360px;
            padding: 3rem;
        }
        .wcq-team-profile-kicker,
        .wcq-profile-summary-kicker {
            color: #D6A83A;
            font-size: .82rem;
            font-weight: 950;
            letter-spacing: .04em;
            text-transform: uppercase;
        }
        .wcq-team-profile-hero h2 {
            color: #FFFFFF;
            font-size: 4.25rem;
            font-weight: 950;
            line-height: .95;
            margin: .2rem 0 .3rem;
            text-shadow: 0 3px 18px rgba(0,0,0,.9);
        }
        .wcq-team-profile-hero p {
            color: #F8FAFC;
            font-size: 1.35rem;
            font-weight: 800;
            margin: 0;
            text-shadow: 0 2px 12px rgba(0,0,0,.9);
        }
        .wcq-profile-summary {
            background:
                linear-gradient(135deg, rgba(5,5,5,.50), rgba(11,16,32,.42)),
                radial-gradient(circle at 12% 0%, rgba(214,168,58,.14), transparent 30%);
            border: 1px solid rgba(214,168,58,.26);
            border-radius: 8px;
            box-shadow: 0 14px 34px rgba(0,0,0,.20);
            display: grid;
            gap: 1rem;
            grid-template-columns: minmax(0, 1.35fr) minmax(280px, .95fr);
            margin: 1rem 0 1.25rem;
            padding: 1rem;
        }
        .wcq-profile-summary h3 {
            color: #FFFFFF;
            font-size: 1.42rem;
            font-weight: 950;
            line-height: 1.12;
            margin: .2rem 0 0;
        }
        .wcq-profile-stats {
            display: grid;
            gap: .55rem;
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }
        .wcq-profile-stat {
            background: rgba(255,255,255,.06);
            border: 1px solid rgba(255,255,255,.10);
            border-radius: 8px;
            padding: .72rem;
        }
        .wcq-profile-stat span {
            color: #CBD5E1;
            display: block;
            font-size: .72rem;
            font-weight: 900;
            text-transform: uppercase;
        }
        .wcq-profile-stat strong {
            color: #FFFFFF;
            display: block;
            font-size: 1rem;
            font-weight: 950;
            margin-top: .18rem;
        }
        .ranking-wcq-table-shell {
            background: rgba(5,5,5,.24);
            border: 1px solid rgba(214,168,58,.22);
            border-radius: 8px;
            margin: 1rem 0;
            overflow: hidden;
        }
        .ranking-wcq-table-shell h3 {
            color: #D6A83A;
            font-size: 1.08rem;
            font-weight: 950;
            margin: 0;
            padding: .8rem .9rem;
        }
        .ranking-wcq-round-title {
            border-top: 1px solid rgba(214,168,58,.24);
            color: #FFFFFF;
            font-size: 1.18rem;
            font-weight: 950;
            margin: 1.15rem 0 .7rem;
            padding-top: .75rem;
        }
        .ranking-wcq-group-title {
            color: #FFFFFF;
            font-size: 1.02rem;
            font-weight: 950;
            margin: .9rem 0 .45rem;
        }
        .ranking-wcq-standings-table {
            border: 1px solid rgba(255,255,255,.12);
            border-radius: 8px;
            margin: .35rem 0 1rem;
            overflow: hidden;
        }
        .ranking-wcq-standings-row {
            align-items: center;
            background: rgba(255,255,255,.055);
            border-bottom: 1px solid rgba(255,255,255,.08);
            color: #FFFFFF;
            display: grid;
            gap: .55rem;
            grid-template-columns: .35fr minmax(190px, 2.4fr) repeat(5, .45fr) .55fr 1fr;
            min-height: 52px;
            padding: .5rem .65rem;
        }
        .ranking-wcq-standings-head {
            background: rgba(5,5,5,.54);
            border-left: 4px solid #D6A83A;
            color: #D6A83A;
            font-size: .72rem;
            font-weight: 950;
            min-height: 38px;
            text-transform: uppercase;
        }
        .ranking-wcq-standings-row span:nth-child(2) {
            font-weight: 950;
            overflow-wrap: anywhere;
        }
        .ranking-wcq-status {
            color: #D6A83A;
            font-weight: 950;
        }
        .ranking-wcq-table-wrap {
            overflow-x: auto;
        }
        .ranking-wcq-table {
            border-collapse: collapse;
            width: 100%;
        }
        .ranking-wcq-table th {
            background: rgba(214,168,58,.18);
            color: #D6A83A;
            font-size: .72rem;
            font-weight: 950;
            padding: .58rem .65rem;
            text-align: left;
            text-transform: uppercase;
            white-space: nowrap;
        }
        .ranking-wcq-table td {
            border-top: 1px solid rgba(255,255,255,.08);
            color: #F8FAFC;
            font-weight: 800;
            padding: .62rem .65rem;
            vertical-align: top;
        }
        .ranking-wcq-table tr:nth-child(even) td {
            background: rgba(255,255,255,.045);
        }
        .wcq-profile-results {
            margin: 1rem 0 1.25rem;
        }
        .wcq-profile-results h3 {
            color: #D6A83A;
            font-size: 1.18rem;
            font-weight: 950;
            margin: .2rem 0 .75rem;
        }
        .wcq-profile-result-grid {
            display: grid;
            gap: .75rem;
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }
        .wcq-profile-result-card {
            background:
                linear-gradient(135deg, rgba(5,5,5,.48), rgba(11,16,32,.38)),
                radial-gradient(circle at 88% 12%, rgba(214,168,58,.12), transparent 30%);
            border: 1px solid rgba(214,168,58,.24);
            border-radius: 8px;
            box-shadow: 0 14px 34px rgba(0,0,0,.20);
            min-height: 118px;
            padding: .9rem;
        }
        .wcq-profile-result-card.won {
            border-color: rgba(34,197,94,.46);
        }
        .wcq-profile-result-card.lost {
            border-color: rgba(239,68,68,.50);
        }
        .wcq-profile-result-card.drew {
            border-color: rgba(245,158,11,.50);
        }
        .wcq-profile-result-top {
            color: #CBD5E1;
            display: flex;
            font-size: .72rem;
            font-weight: 900;
            gap: .75rem;
            justify-content: space-between;
            text-transform: uppercase;
        }
        .wcq-profile-result-match {
            align-items: center;
            color: #FFFFFF;
            font-weight: 950;
            display: grid;
            gap: .65rem;
            grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
            line-height: 1.18;
            margin-top: .8rem;
            text-align: center;
        }
        .wcq-profile-result-match strong {
            color: #D6A83A;
            font-size: 1.05rem;
            white-space: nowrap;
        }
        .wcq-profile-result-team {
            align-items: center;
            display: flex;
            flex-direction: column;
            gap: .38rem;
            min-width: 0;
        }
        .wcq-profile-result-team img,
        .wcq-profile-result-team .ranking-flag-fallback {
            aspect-ratio: 3 / 2;
            border: 1px solid rgba(255,255,255,.62);
            border-radius: 4px;
            box-shadow: 0 8px 16px rgba(0,0,0,.32);
            display: block;
            object-fit: cover;
            object-position: center;
            width: 42px;
        }
        .wcq-profile-result-team .ranking-flag-fallback.hidden {
            display: none;
        }
        .wcq-profile-result-team em {
            color: #FFFFFF;
            font-style: normal;
            font-size: .95rem;
            font-weight: 950;
            overflow-wrap: anywhere;
        }
        .wcq-profile-result-status {
            color: #D6A83A;
            font-size: .78rem;
            font-weight: 950;
            margin-top: .55rem;
            text-transform: uppercase;
        }
        @media (max-width: 980px) {
            .ranking-grid, .ranking-list {
                grid-template-columns: 1fr;
            }
            .ranking-hero {
                flex-direction: column;
            }
            .wcq-team-profile-hero,
            .wcq-profile-summary,
            .wcq-profile-result-grid {
                grid-template-columns: 1fr;
            }
            .ranking-wcq-standings-row {
                grid-template-columns: .35fr minmax(150px, 2.2fr) repeat(2, .45fr) 1fr;
            }
            .ranking-wcq-standings-row span:nth-child(5),
            .ranking-wcq-standings-row span:nth-child(6),
            .ranking-wcq-standings-row span:nth-child(7),
            .ranking-wcq-standings-row span:nth-child(8) {
                display: none;
            }
            .wcq-team-profile-hero {
                min-height: 320px;
                padding: 2rem;
            }
        }
        @media (max-width: 560px) {
            .ranking-row, .ranking-row.compact {
                grid-template-columns: 52px 54px 1fr;
            }
            .ranking-position {
                font-size: 1.2rem;
            }
            .wcq-team-profile-hero h2 {
                font-size: 2.65rem;
            }
            .wcq-profile-stats {
                grid-template-columns: 1fr;
            }
            .wcq-profile-result-match {
                grid-template-columns: 1fr;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
