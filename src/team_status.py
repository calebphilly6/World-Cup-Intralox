"""Shared "where is this team in the tournament" logic.

The Home page favorite cards and the Teams page elimination badges both need to
answer the same two questions about a team -- what round are they in, and are
they out -- from the same live, knockout-resolved fixtures feed. Keeping the
logic here means the two views can't drift apart (e.g. Home saying "Round of 16"
while Teams shows an "Eliminated" badge for the same country).

Callers pass a fixtures frame that already carries resolved knockout
participants (see ``src.knockout_slots.fill_knockout_participants``) and has a
``kickoff_utc`` column. Group-stage elimination is only asserted once the full
Round-of-32 field is known, so a third-placed team waiting on the other groups
is never prematurely marked out.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from src.official_match_reference import normalize_team_key
from src.utils.team_names import team_lookup_keys


_ROUND_LABELS = {
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
    "final": "Finals",
}

# The Round of 32 has 32 entrants; once every slot resolves we can trust that a
# team absent from the bracket really did go out in the group stage.
_KNOCKOUT_FIELD_SIZE = 32


def round_label(stage) -> str:
    key = "".join(character for character in str(stage or "").lower() if character.isalnum())
    if key in _ROUND_LABELS:
        return _ROUND_LABELS[key]
    if "32" in key and ("last" in key or "round" in key):
        return "Round of 32"
    if "16" in key and ("last" in key or "round" in key):
        return "Round of 16"
    if "quarter" in key:
        return "Quarterfinals"
    if "semi" in key:
        return "Semifinals"
    if "final" in key:
        return "Finals"
    return "Group Stage"


def is_knockout_stage(stage) -> bool:
    return round_label(stage) != "Group Stage"


def normalize_feed(fixtures: pd.DataFrame) -> pd.DataFrame:
    """Give the Fixtures feed the column names this module expects.

    The live feed names its kickoff ``utc_date`` and its number
    ``official_match_number``; the helpers here read ``kickoff_utc`` and
    ``match_number``. Returns a copy so the caller's frame is untouched.
    """
    if fixtures is None or fixtures.empty:
        return pd.DataFrame()
    normalized = fixtures.copy()
    if "kickoff_utc" not in normalized.columns and "utc_date" in normalized.columns:
        normalized["kickoff_utc"] = normalized["utc_date"]
    if "match_number" not in normalized.columns and "official_match_number" in normalized.columns:
        normalized["match_number"] = normalized["official_match_number"]
    return normalized


def fixtures_for_team(fixtures: pd.DataFrame, team_name: str) -> pd.DataFrame:
    if fixtures is None or fixtures.empty:
        return pd.DataFrame()
    keys = team_lookup_keys(team_name)
    home = fixtures["home_team"].map(normalize_team_key).isin(keys)
    away = fixtures["away_team"].map(normalize_team_key).isin(keys)
    return fixtures[home | away].copy()


def next_fixture(team_fixtures: pd.DataFrame, now: datetime):
    if team_fixtures is None or team_fixtures.empty:
        return None
    upcoming = team_fixtures[team_fixtures["kickoff_utc"].map(lambda value: _parse_dt(value) >= now)].copy()
    if upcoming.empty:
        return None
    upcoming["_dt"] = upcoming["kickoff_utc"].map(_parse_dt)
    return upcoming.sort_values(_sort_columns(upcoming)).iloc[0]


def latest_completed(team_fixtures: pd.DataFrame):
    if team_fixtures is None or team_fixtures.empty:
        return None
    completed = team_fixtures.dropna(subset=["home_score", "away_score"]).copy()
    if completed.empty:
        return None
    completed["_dt"] = completed["kickoff_utc"].map(_parse_dt)
    return completed.sort_values(_sort_columns(completed)).iloc[-1]


def current_round(team_fixtures: pd.DataFrame, now: datetime, team_name: str, *, qualification_status: str = "") -> str:
    if "champion" in str(qualification_status or "").lower():
        return "Champion"
    upcoming = next_fixture(team_fixtures, now)
    if upcoming is not None:
        return round_label(upcoming["stage"])
    latest = latest_completed(team_fixtures)
    if latest is None:
        return "Group Stage"
    if round_label(latest["stage"]) == "Finals" and won(latest, team_name):
        return "Champion"
    return round_label(latest["stage"])


def is_eliminated(
    team_fixtures: pd.DataFrame,
    now: datetime,
    team_name: str,
    *,
    qualification_status: str = "",
    knockout_keys: frozenset[str] | set[str] = frozenset(),
    bracket_complete: bool = False,
) -> bool:
    if any(word in str(qualification_status or "").lower() for word in ("out", "eliminated", "knocked")):
        return True
    if "champion" in str(qualification_status or "").lower():
        return False
    if next_fixture(team_fixtures, now) is not None:
        return False
    latest = latest_completed(team_fixtures)
    if latest is None:
        return False
    # Lost their most recent knockout match with nothing left to play -> out.
    if is_knockout_stage(latest["stage"]) and lost(latest, team_name):
        return True
    # Group stage is over and the bracket is set, yet they're not in it -> out.
    if bracket_complete and not is_knockout_participant(team_name, knockout_keys):
        return True
    return False


def team_is_home(fixture, team_name: str) -> bool:
    home_name = fixture.get("home_team")
    if not team_name or pd.isna(home_name):
        return False
    return normalize_team_key(home_name) in team_lookup_keys(team_name)


def won(fixture, team_name: str) -> bool:
    home_score, away_score = fixture.get("home_score"), fixture.get("away_score")
    if pd.isna(home_score) or pd.isna(away_score) or home_score == away_score:
        return False
    return home_score > away_score if team_is_home(fixture, team_name) else away_score > home_score


def lost(fixture, team_name: str) -> bool:
    home_score, away_score = fixture.get("home_score"), fixture.get("away_score")
    if pd.isna(home_score) or pd.isna(away_score) or home_score == away_score:
        return False
    return home_score < away_score if team_is_home(fixture, team_name) else away_score < home_score


def knockout_participant_keys(slot_teams: dict[str, str]) -> frozenset[str]:
    keys: set[str] = set()
    for name in slot_teams.values():
        keys |= team_lookup_keys(name)
    return frozenset(keys)


def bracket_is_complete(slot_teams: dict[str, str]) -> bool:
    return len(slot_teams) >= _KNOCKOUT_FIELD_SIZE


def is_knockout_participant(team_name: str, knockout_keys: frozenset[str] | set[str]) -> bool:
    return any(key in knockout_keys for key in team_lookup_keys(team_name))


def _sort_columns(frame: pd.DataFrame) -> list[str]:
    return ["_dt", "match_number"] if "match_number" in frame.columns else ["_dt"]


def _parse_dt(value) -> datetime:
    text = str(value or "").replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
