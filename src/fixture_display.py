from __future__ import annotations

import pandas as pd

from src.utils.team_names import display_team_name, flag_code_for_common_team


TEAM_NAME_ALIASES = {
    "bosnia herzegovina": "Bosnia and Herzegovina",
    "bosnia and herzegovina": "Bosnia and Herzegovina",
    "cape verde": "Cabo Verde",
    "cape verde islands": "Cabo Verde",
    "cabo verde": "Cabo Verde",
    "cote divoire": "Côte d'Ivoire",
    "cote d'ivoire": "Côte d'Ivoire",
    "ivory coast": "Côte d'Ivoire",
    "curacao": "Curaçao",
    "iran": "IR Iran",
    "ir iran": "IR Iran",
    "turkiye": "Türkiye",
    "turkey": "Türkiye",
    "united states": "USA",
    "united states of america": "USA",
    "us": "USA",
    "usa": "USA",
}


def _coerce_score(value):
    if value is None or pd.isna(value):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def format_scoreline(row, *, separator: str = " - ") -> str:
    """Render a finished match's score, showing a penalty shootout as
    "1 (4) - 1 (3)" rather than folding the shootout into the goals total."""
    home = _coerce_score(row.get("home_score"))
    away = _coerce_score(row.get("away_score"))
    if home is None or away is None:
        return ""
    home_pens = _coerce_score(row.get("home_penalties"))
    away_pens = _coerce_score(row.get("away_penalties"))
    if home_pens is not None and away_pens is not None:
        return f"{home} ({home_pens}){separator}{away} ({away_pens})"
    return f"{home}{separator}{away}"


def enrich_fixture_participants(
    fixtures: pd.DataFrame,
    *,
    home_column: str = "home_team",
    away_column: str = "away_team",
    label_column: str = "game_label",
    prefer_label: bool = True,
) -> pd.DataFrame:
    """Normalize fixture participants and optionally prefer official match labels."""
    if fixtures.empty:
        return fixtures

    enriched = fixtures.copy()
    if home_column not in enriched.columns:
        enriched[home_column] = ""
    if away_column not in enriched.columns:
        enriched[away_column] = ""

    for index, row in enriched.iterrows():
        home_label, away_label = _split_label(row.get(label_column)) if label_column in enriched.columns else ("", "")
        current_home = canonical_fixture_team_name(row.get(home_column))
        current_away = canonical_fixture_team_name(row.get(away_column))
        if home_label and (prefer_label or _is_blank(current_home)):
            current_home = canonical_fixture_team_name(home_label)
        if away_label and (prefer_label or _is_blank(current_away)):
            current_away = canonical_fixture_team_name(away_label)
        enriched.at[index, home_column] = current_home
        enriched.at[index, away_column] = current_away
    return enriched


def canonical_fixture_team_name(value) -> str:
    text = str(value or "").strip()
    if _is_blank(text):
        return ""
    key = _normalize_name(text)
    return display_team_name(TEAM_NAME_ALIASES.get(key, text))


def flag_code_for_team(team_name, flag_lookup: dict[str, str]) -> str:
    text = canonical_fixture_team_name(team_name)
    candidates = {text, str(team_name or "").strip(), _normalize_name(text), _normalize_name(team_name)}
    for candidate in candidates:
        code = flag_lookup.get(candidate)
        if code:
            return str(code).strip().lower()
    return flag_code_for_common_team(team_name)


def flag_lookup_with_aliases(rows: pd.DataFrame) -> dict[str, str]:
    flags: dict[str, str] = {}
    if rows.empty:
        return flags
    for _, row in rows.iterrows():
        raw_name = str(row.get("name") or "").strip()
        name = canonical_fixture_team_name(raw_name)
        code = str(row.get("country_code") or "").strip().lower()
        if name and code:
            flags[name] = code
            flags[_normalize_name(name)] = code
        if raw_name and code:
            flags[raw_name] = code
            flags[_normalize_name(raw_name)] = code
    for alias_key, canonical in TEAM_NAME_ALIASES.items():
        code = flags.get(canonical) or flags.get(_normalize_name(canonical))
        if code:
            flags[alias_key] = code
    for name in list(flags):
        display_name = display_team_name(name)
        if display_name and display_name not in flags:
            flags[display_name] = flags[name]
            flags[_normalize_name(display_name)] = flags[name]
    flags["England"] = "gb-eng"
    flags["england"] = "gb-eng"
    flags["Scotland"] = "gb-sct"
    flags["scotland"] = "gb-sct"
    return flags


def _split_label(value) -> tuple[str, str]:
    label = str(value or "").strip()
    if " vs " not in label:
        return "", ""
    home, away = label.split(" vs ", 1)
    return home.strip(), away.strip()


def _is_blank(value) -> bool:
    if pd.isna(value):
        return True
    text = str(value).strip().lower()
    return text in {"", "nan", "none", "null", "tbd"}


def _normalize_name(value) -> str:
    import unicodedata

    text = str(value or "").strip()
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    normalized = normalized.lower().replace("&", "and").replace("'", "").replace(".", "").replace("-", " ")
    return " ".join(normalized.split())
