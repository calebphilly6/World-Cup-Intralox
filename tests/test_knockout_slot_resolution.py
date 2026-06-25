import pandas as pd

from src.pages.bracket_renderer import _build_match_models


def _name(models, match_number, index):
    return models[match_number]["participants"][index]["name"]


def test_group_slots_resolve_from_standings_when_feed_blank():
    # Feed has the knockout fixtures but no teams yet (the pre-knockout reality).
    fixtures = pd.DataFrame(
        [
            {"official_match_number": 74, "home_team": None, "away_team": None},
            {"official_match_number": 73, "home_team": None, "away_team": None},
        ]
    )
    # M74 slots are ["1E", "3ABCDF"]; M73 slots are ["2A", "2B"].
    slot_teams = {"1E": "Germany", "2A": "USA", "2B": "Mexico"}

    models = _build_match_models(fixtures, {}, slot_teams)

    assert _name(models, 74, 0) == "Germany"
    assert models[74]["participants"][0]["placeholder"] is False
    assert _name(models, 73, 0) == "USA"
    assert _name(models, 73, 1) == "Mexico"
    # The third-place slot stays a placeholder (no allocation table yet).
    assert models[74]["participants"][1]["placeholder"] is True


def test_feed_team_wins_over_standings():
    fixtures = pd.DataFrame(
        [{"official_match_number": 73, "home_team": "Argentina", "away_team": None}]
    )
    # Standings would say USA, but the feed's official assignment must win.
    models = _build_match_models(fixtures, {}, {"2A": "USA", "2B": "Mexico"})

    assert _name(models, 73, 0) == "Argentina"
    assert _name(models, 73, 1) == "Mexico"


def test_standings_winner_propagates_to_next_round():
    # M73 (2A vs 2B) feeds the home slot of M90 ("W73"). Resolve teams from
    # standings, give M73 a score, and the winner should fill the next round.
    fixtures = pd.DataFrame(
        [{"official_match_number": 73, "home_team": None, "away_team": None,
          "home_score": 2, "away_score": 1}]
    )
    models = _build_match_models(fixtures, {}, {"2A": "USA", "2B": "Mexico"})

    assert models[73]["winner_index"] == 0
    assert _name(models, 90, 0) == "USA"  # W73 resolved to the standings winner
