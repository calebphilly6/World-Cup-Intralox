from __future__ import annotations

import unicodedata

import pandas as pd

from src.database import fetch_df


def apply_official_match_reference(fixtures: pd.DataFrame) -> pd.DataFrame:
    if fixtures.empty:
        return fixtures

    reference = fetch_df(
        """
        SELECT match_number, round_name, game_label, city
        FROM match_city_reference
        ORDER BY match_number
        """
    )
    if reference.empty:
        return fixtures

    pair_lookup = _reference_pair_lookup(reference)
    kickoff_lookup = _kickoff_match_number_lookup()
    chronological_numbers = reference["match_number"].tolist()
    used_numbers: set[int] = set()
    official_numbers = []
    official_cities = []
    official_labels = []

    ordered = fixtures.sort_values("utc_date").copy()
    for _, row in ordered.iterrows():
        key = _fixture_pair_key(row.get("home_team"), row.get("away_team"))
        matched = pair_lookup.get(key)
        match_number = int(matched["match_number"]) if matched is not None else None
        if match_number is None or match_number in used_numbers:
            # Knockout matches have no teams yet, so they cannot be paired by name.
            # Map them to their official number by their unique kickoff time before
            # falling back to chronological order (which would shuffle times against
            # the numeric match/city labels).
            by_kickoff = kickoff_lookup.get(_normalize_kickoff(row.get("utc_date")))
            if by_kickoff is not None and by_kickoff not in used_numbers:
                match_number = by_kickoff
            else:
                match_number = _next_unused_match_number(chronological_numbers, used_numbers)
        used_numbers.add(match_number)
        official_numbers.append(match_number)
        city_row = reference[reference["match_number"] == match_number]
        official_cities.append("" if city_row.empty else city_row.iloc[0]["city"])
        official_labels.append("" if city_row.empty else city_row.iloc[0]["game_label"])

    ordered["official_match_number"] = official_numbers
    ordered["match_id"] = ordered["official_match_number"].map(lambda value: f"M{int(value)}")
    ordered["city"] = official_cities
    ordered["venue"] = ordered["city"]
    ordered = _fill_missing_participants_from_reference(ordered, official_labels)
    return ordered.sort_values("utc_date")


def _fill_missing_participants_from_reference(fixtures: pd.DataFrame, labels: list[str]) -> pd.DataFrame:
    updated = fixtures.copy()
    for column in ("home_team", "away_team"):
        if column in updated:
            updated[column] = updated[column].astype("object")
    for index, label in zip(updated.index, labels):
        if " vs " not in str(label):
            continue
        home_slot, away_slot = str(label).split(" vs ", 1)
        if _is_blank_participant(updated.at[index, "home_team"]):
            updated.at[index, "home_team"] = home_slot
        if _is_blank_participant(updated.at[index, "away_team"]):
            updated.at[index, "away_team"] = away_slot
    return updated


def _is_blank_participant(value) -> bool:
    if pd.isna(value):
        return True
    return str(value).strip().lower() in {"", "nan", "none", "null"}


def _reference_pair_lookup(reference: pd.DataFrame) -> dict[tuple[str, str], pd.Series]:
    lookup = {}
    for _, row in reference.iterrows():
        if " vs " not in row["game_label"]:
            continue
        home, away = row["game_label"].split(" vs ", 1)
        if home.startswith(("Winner ", "Loser ")) or away.startswith(("Winner ", "Loser ")):
            continue
        lookup[_fixture_pair_key(home, away)] = row
        lookup[_fixture_pair_key(away, home)] = row
    return lookup


def _fixture_pair_key(home_team, away_team) -> tuple[str, str]:
    return (normalize_team_key(home_team), normalize_team_key(away_team))


def normalize_team_key(value) -> str:
    text = str(value or "").strip()
    aliases = {
        "usa": "united states",
        "us": "united states",
        "united states of america": "united states",
        "czech republic": "czechia",
        "south korea": "korea republic",
        "bosnia & herzegovina": "bosnia and herzegovina",
        "bosnia-herzegovina": "bosnia and herzegovina",
        "bosnia herzegovina": "bosnia and herzegovina",
        "bosnia and hersegovina": "bosnia and herzegovina",
        "bosnia hersegovina": "bosnia and herzegovina",
        "turkey": "turkiye",
        "turkiye": "turkiye",
        "trkiye": "turkiye",
        "t?rkiye": "turkiye",
        "tÃ¼rkiye": "turkiye",
        "curacao": "curacao",
        "curaÃ§ao": "curacao",
        "cote d'ivoire": "cote divoire",
        "cÃ´te d'ivoire": "cote divoire",
        "ivory coast": "cote divoire",
        "cote divoire": "cote divoire",
        "c?te divoire": "cote divoire",
        "cte divoire": "cote divoire",
        "cape verde": "cabo verde",
        "cape verde islands": "cabo verde",
        "cabo verde islands": "cabo verde",
        "iran": "ir iran",
        "dr congo": "congo dr",
        "democratic republic of congo": "congo dr",
        "congo democratic republic": "congo dr",
    }
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    normalized = normalized.lower().replace("&", "and").replace("'", "").replace(".", "").replace("?", "")
    normalized = " ".join(normalized.split())
    return aliases.get(normalized, normalized)


def _kickoff_match_number_lookup() -> dict[str, int]:
    """Map a normalized kickoff time to its official match number.

    Built from the canonical fixtures schedule and limited to kickoff times that
    belong to a single match (knockout slots are unique; group-stage games share
    slots and are intentionally excluded so they keep matching by team pairing).
    """
    schedule = fetch_df("SELECT match_number, kickoff_utc FROM fixtures")
    if schedule.empty:
        return {}
    schedule = schedule.copy()
    schedule["_kickoff"] = schedule["kickoff_utc"].map(_normalize_kickoff)
    schedule = schedule[schedule["_kickoff"].notna()]
    counts = schedule["_kickoff"].value_counts()
    unique = schedule[schedule["_kickoff"].map(lambda value: counts.get(value, 0) == 1)]
    return {row["_kickoff"]: int(row["match_number"]) for _, row in unique.iterrows()}


def _normalize_kickoff(value) -> str | None:
    parsed = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.isoformat()


def _next_unused_match_number(match_numbers: list[int], used_numbers: set[int]) -> int:
    for match_number in match_numbers:
        if int(match_number) not in used_numbers:
            return int(match_number)
    return max(used_numbers or {0}) + 1
