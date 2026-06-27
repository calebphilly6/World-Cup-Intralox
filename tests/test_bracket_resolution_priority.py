"""The bracket must fill Round-of-32 entry slots from our own resolution, not the
flaky football-data feed. The feed seeds these slots intermittently and sometimes
incorrectly (duplicating teams or placing them in the wrong tie), so a real team
the feed names must never override a slot we can resolve ourselves.
"""
from __future__ import annotations

import pandas as pd

from src.pages import bracket_renderer as br
from src.pages.bracket_data import MATCHES, R32_LEFT, R32_RIGHT


def _feed_with_ghost(match_numbers) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "official_match_number": n,
                "home_team": "FeedGhost",
                "away_team": "FeedGhost",
                "home_score": None,
                "away_score": None,
                "winner": None,
                "utc_date": None,
            }
            for n in match_numbers
        ]
    )


def test_own_resolution_wins_over_feed_for_r32_slots():
    r32 = R32_LEFT + R32_RIGHT
    # A correct, unique team for every R32 entry slot.
    slot_teams: dict[str, str] = {}
    for i, number in enumerate(r32):
        for j, slot in enumerate(MATCHES[number]["slots"]):
            slot_teams[slot] = f"Team{i}_{j}"

    feed = _feed_with_ghost(range(73, 105))
    models = br._build_match_models(feed, {}, slot_teams)

    names = [p["name"] for n in r32 for p in models[n]["participants"]]
    assert "FeedGhost" not in names, "feed value leaked into a resolvable R32 slot"
    assert len(names) == len(set(names)) == 32, "R32 slots must be 32 unique teams"


def test_feed_still_fills_unresolved_propagation_slots():
    # A later-round slot we cannot resolve (no slot_teams entry, not yet propagated)
    # should still accept a real team the feed names.
    feed = pd.DataFrame(
        [
            {
                "official_match_number": 89,  # an R16 match fed by Winner slots
                "home_team": "RealTeam",
                "away_team": None,
                "home_score": None,
                "away_score": None,
                "winner": None,
                "utc_date": None,
            }
        ]
    )
    models = br._build_match_models(feed, {}, {})
    assert models[89]["participants"][0]["name"] == "RealTeam"


def test_winner_propagation_unaffected():
    feed = pd.DataFrame(
        [
            {
                "official_match_number": 73,
                "home_team": None,
                "away_team": None,
                "home_score": 2,
                "away_score": 1,
                "winner": None,
                "utc_date": None,
            }
        ]
    )
    models = br._build_match_models(feed, {}, {"2A": "South Africa", "2B": "Canada"})
    winner_index = models[73]["winner_index"]
    assert winner_index == 0
    assert models[73]["participants"][winner_index]["name"] == "South Africa"
