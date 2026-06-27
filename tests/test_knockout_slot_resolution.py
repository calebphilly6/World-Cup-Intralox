import pandas as pd

from src.knockout_slots import fill_knockout_participants
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


def test_own_resolution_wins_over_feed_for_resolvable_slots():
    # The football-data feed seeds knockout slots intermittently and sometimes
    # incorrectly (e.g. "Argentina" in 2A when our standings say USA), which is
    # what duplicated/misplaced teams on the bracket. For any slot we can resolve
    # ourselves, our computed value must win over the feed's.
    fixtures = pd.DataFrame(
        [{"official_match_number": 73, "home_team": "Argentina", "away_team": None}]
    )
    models = _build_match_models(fixtures, {}, {"2A": "USA", "2B": "Mexico"})

    assert _name(models, 73, 0) == "USA"
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


def test_fill_knockout_participants_replaces_placeholder_labels(monkeypatch):
    # The Fixtures page passes enriched rows whose teams are the official slot
    # labels (e.g. "1C"/"2F"); fill_knockout_participants should upgrade them.
    import src.knockout_slots as ks
    monkeypatch.setattr(ks, "all_slot_teams", lambda: {"1C": "Brazil", "2F": "Croatia"})

    fixtures = pd.DataFrame(
        [
            {"official_match_number": 76, "home_team": "1C", "away_team": "2F"},
            {"official_match_number": 5, "home_team": "France", "away_team": "Senegal"},
        ]
    )
    out = fill_knockout_participants(fixtures)

    assert out.loc[0, "home_team"] == "Brazil"
    assert out.loc[0, "away_team"] == "Croatia"
    # Non-knockout group rows are untouched.
    assert out.loc[1, "home_team"] == "France"


def test_fill_keeps_placeholder_when_slot_unresolved(monkeypatch):
    import src.knockout_slots as ks
    monkeypatch.setattr(ks, "all_slot_teams", lambda: {})  # nothing resolvable yet

    fixtures = pd.DataFrame([{"official_match_number": 89, "home_team": "Winner M74", "away_team": "Winner M77"}])
    out = fill_knockout_participants(fixtures)

    assert out.loc[0, "home_team"] == "Winner M74"
    assert out.loc[0, "away_team"] == "Winner M77"
