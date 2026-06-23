from __future__ import annotations

import html

from src.official_match_reference import normalize_team_key


COMMON_TEAM_NAMES = {
    "IR Iran": "Iran",
    "Türkiye": "Turkey",
    "TÃ¼rkiye": "Turkey",
    "Côte d'Ivoire": "Ivory Coast",
    "CÃ´te d'Ivoire": "Ivory Coast",
    "Congo DR": "DR Congo",
    "China PR": "China",
    "Kyrgyz Republic": "Kyrgyzstan",
    "The Gambia": "Gambia",
    "Korea DPR": "North Korea",
    "Hong Kong, China": "Hong Kong",
}

COMMON_FLAG_CODES = {
    "China": "cn",
    "China PR": "cn",
    "North Korea": "kp",
    "Korea DPR": "kp",
    "Iran": "ir",
    "IR Iran": "ir",
    "Turkey": "tr",
    "Türkiye": "tr",
    "TÃ¼rkiye": "tr",
    "Ivory Coast": "ci",
    "Côte d'Ivoire": "ci",
    "CÃ´te d'Ivoire": "ci",
    "DR Congo": "cd",
    "Congo DR": "cd",
    "Kyrgyzstan": "kg",
    "Kyrgyz Republic": "kg",
    "Gambia": "gm",
    "The Gambia": "gm",
    "Hong Kong": "hk",
    "Hong Kong, China": "hk",
    "Saint Kitts and Nevis": "kn",
    "St Kitts and Nevis": "kn",
    "Saint Lucia": "lc",
    "St Lucia": "lc",
    "Saint Vincent and the Grenadines": "vc",
    "St Vincent and the Grenadines": "vc",
}

TEAM_NAME_ALIASES = {
    "Cape Verde": "Cabo Verde",
    "Cabo Verde": "Cape Verde",
    "Czech Republic": "Czechia",
    "Czechia": "Czech Republic",
    "Democratic Republic of Congo": "DR Congo",
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


def display_team_name(team_name: object) -> str:
    text = str(team_name or "").strip()
    return COMMON_TEAM_NAMES.get(text, text)


def team_lookup_keys(team_name: object) -> set[str]:
    keys = {normalize_team_key(team_name)}
    for alias, official in TEAM_NAME_ALIASES.items():
        alias_key = normalize_team_key(alias)
        official_key = normalize_team_key(official)
        if keys & {alias_key, official_key}:
            keys.update({alias_key, official_key})
            keys.add(normalize_team_key(display_team_name(alias)))
            keys.add(normalize_team_key(display_team_name(official)))
    return {key for key in keys if key}


def team_link_attr(team_name: object) -> str:
    """Return a ``data-wc-team`` HTML attribute so the history bridge can open
    this team's profile on click. Empty for blank/TBD placeholders."""
    name = str(team_name or "").strip()
    if not name or name.upper() == "TBD":
        return ""
    return f' data-wc-team="{html.escape(name, quote=True)}"'


def flag_code_for_common_team(team_name: object) -> str:
    text = str(team_name or "").strip()
    for candidate in [text, display_team_name(text)]:
        code = COMMON_FLAG_CODES.get(candidate)
        if code:
            return code
    return ""
