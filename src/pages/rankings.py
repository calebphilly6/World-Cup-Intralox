from __future__ import annotations

import html
import re

import pandas as pd
import streamlit as st

from src.database import fetch_df
from src.official_match_reference import normalize_team_key


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
}


def render() -> None:
    st.title("FIFA Rankings")
    _styles()

    rankings = _world_cup_rankings()
    global_rankings = _global_rankings()
    default_view = st.session_state.pop("rankings_default_view", "World Cup Teams")

    if default_view == "Full FIFA List":
        tab_full, tab_world_cup = st.tabs(["Full FIFA List", "World Cup Teams"])
    else:
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
    st.markdown(
        f'<div class="ranking-grid wc-grid">{_ranking_cards(latest, team_column="team", clickable=True)}</div>',
        unsafe_allow_html=True,
    )


def _render_full_rankings(global_rankings: pd.DataFrame) -> None:
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
    st.markdown(f'<div class="ranking-list">{_ranking_cards(global_latest, team_column="team_name", compact=True)}</div>', unsafe_allow_html=True)


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
        f'<div class="ranking-name">{html.escape(team)}</div>'
        f'<div class="ranking-meta">{group_badge}</div>'
        '</div>'
        '</article>'
    )
    team_id = row.get("team_id")
    if clickable and pd.notna(team_id):
        href = f"?page=teams&team_id={int(team_id)}"
        return f'<a class="ranking-card-link" href="{href}" target="_self" aria-label="Open {html.escape(team)} team page">{card}</a>'
    return card


def _flag_code(team: str, stored_code=None) -> str:
    code = FLAG_CODES.get(team) or stored_code or ""
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
        rows["team_name"].str.contains("|".join(re.escape(term) for term in direct_terms), case=False, na=False)
        if direct_terms
        else pd.Series(False, index=rows.index)
    )
    normalized_terms = {normalize_team_key(term) for term in terms if term}
    normalized = rows["team_name"].map(normalize_team_key).isin(normalized_terms)
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
            object-fit: cover;
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
        @media (max-width: 980px) {
            .ranking-grid, .ranking-list {
                grid-template-columns: 1fr;
            }
            .ranking-hero {
                flex-direction: column;
            }
        }
        @media (max-width: 560px) {
            .ranking-row, .ranking-row.compact {
                grid-template-columns: 52px 54px 1fr;
            }
            .ranking-position {
                font-size: 1.2rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
