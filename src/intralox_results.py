"""Derive Intralox competition results directly from World Cup fixtures.

The Intralox scoreboard used to read a hand-maintained ``intralox_competition_results``
table that nobody updated, so every competitor stayed at 0.0 even after games were
played. This module computes each team's group and knockout results straight from the
same fixture feed that powers the Fixtures tab, so scores move whenever the fixtures do.
"""
from __future__ import annotations

from collections import defaultdict

import pandas as pd

from src.official_match_reference import normalize_team_key


# Maps a fixture stage to the TeamScore flag set when a team WINS at that stage.
KNOCKOUT_WIN_FIELD = {
    "R32": "won_round_of_32",
    "R16": "won_round_of_16",
    "QF": "won_quarterfinal",
    "SF": "won_semifinal",
    "FINAL": "won_final",
}


def _blank_result() -> dict:
    return {
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


def _stage_bucket(stage) -> str:
    key = "".join(character for character in str(stage or "").upper() if character.isalnum())
    if key in {"GROUPSTAGE", "GROUP"}:
        return "GROUP"
    if key in {"LAST32", "ROUNDOF32"}:
        return "R32"
    if key in {"LAST16", "ROUNDOF16"}:
        return "R16"
    if key in {"QUARTERFINALS", "QUARTERFINAL"}:
        return "QF"
    if key in {"SEMIFINALS", "SEMIFINAL"}:
        return "SF"
    if key == "FINAL":
        return "FINAL"
    if key in {"THIRDPLACE", "THIRDPLACEMATCH"}:
        return "THIRD"
    return ""


def _score(value):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def derive_intralox_results(fixtures: pd.DataFrame) -> dict[str, dict]:
    """Return per-team result fields keyed by :func:`normalize_team_key`.

    Group wins/draws accrue from every completed group match. Group finish and
    knockout flags fill in as those matches finish, so the scoreboard reflects the
    current state of the tournament without any manual data entry.
    """
    results: dict[str, dict] = {}

    def result_for(key: str) -> dict:
        return results.setdefault(key, _blank_result())

    # Per-group mini league used to assign final group positions once a group is done.
    group_stats: dict[str, dict[str, dict[str, int]]] = defaultdict(dict)
    group_total: dict[str, int] = defaultdict(int)
    group_completed: dict[str, int] = defaultdict(int)

    if fixtures is None or getattr(fixtures, "empty", True):
        return results

    for _, row in fixtures.iterrows():
        bucket = _stage_bucket(row.get("stage"))
        home = normalize_team_key(row.get("home_team"))
        away = normalize_team_key(row.get("away_team"))
        home_score = _score(row.get("home_score"))
        away_score = _score(row.get("away_score"))

        if bucket == "GROUP":
            if not home or not away:
                continue
            group = str(row.get("group") or "")
            group_total[group] += 1
            if home_score is None or away_score is None:
                continue
            group_completed[group] += 1
            home_result = result_for(home)
            away_result = result_for(away)
            if home_score > away_score:
                home_result["group_wins"] += 1
            elif away_score > home_score:
                away_result["group_wins"] += 1
            else:
                home_result["group_draws"] += 1
                away_result["group_draws"] += 1
            _accumulate_group_standing(group_stats[group], home, home_score, away_score)
            _accumulate_group_standing(group_stats[group], away, away_score, home_score)
        elif bucket in KNOCKOUT_WIN_FIELD:
            if not home or not away or home_score is None or away_score is None:
                continue
            # Both teams reached this round, so both advanced out of the group stage.
            result_for(home)["advanced"] = True
            result_for(away)["advanced"] = True
            winner, loser = _knockout_winner(home, away, home_score, away_score, row.get("winner"))
            if winner:
                result_for(winner)[KNOCKOUT_WIN_FIELD[bucket]] = True
                result_for(loser)["eliminated"] = True
        elif bucket == "THIRD":
            # The third-place match is unscored, but reaching it means both teams advanced.
            if home:
                result_for(home)["advanced"] = True
            if away:
                result_for(away)["advanced"] = True

    _finalize_group_positions(results, group_stats, group_total, group_completed)
    return results


def _accumulate_group_standing(table: dict[str, dict[str, int]], team: str, scored: int, conceded: int) -> None:
    stat = table.setdefault(team, {"points": 0, "goal_difference": 0, "goals_for": 0})
    if scored > conceded:
        stat["points"] += 3
    elif scored == conceded:
        stat["points"] += 1
    stat["goal_difference"] += scored - conceded
    stat["goals_for"] += scored


def _knockout_winner(home: str, away: str, home_score: int, away_score: int, winner_field) -> tuple[str | None, str | None]:
    if home_score > away_score:
        return home, away
    if away_score > home_score:
        return away, home
    # Level after full time: fall back to the feed's winner (penalty shootouts).
    decided = str(winner_field or "").upper()
    if decided == "HOME_TEAM":
        return home, away
    if decided == "AWAY_TEAM":
        return away, home
    return None, None


def _finalize_group_positions(
    results: dict[str, dict],
    group_stats: dict[str, dict[str, dict[str, int]]],
    group_total: dict[str, int],
    group_completed: dict[str, int],
) -> None:
    for group, total in group_total.items():
        if total == 0 or group_completed.get(group, 0) < total:
            continue  # Group still in progress, so positions are not final yet.
        ranked = sorted(
            group_stats.get(group, {}).items(),
            key=lambda item: (item[1]["points"], item[1]["goal_difference"], item[1]["goals_for"]),
            reverse=True,
        )
        last_position = len(ranked)
        for position, (team, _stat) in enumerate(ranked, start=1):
            result = results.setdefault(team, _blank_result())
            result["group_finish"] = position
            if position <= 2:
                result["advanced"] = True
            if position == last_position:
                # Bottom of the group can never advance.
                result["eliminated"] = True
