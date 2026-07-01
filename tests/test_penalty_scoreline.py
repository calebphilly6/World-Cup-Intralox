"""Penalty shootouts must show the regulation score with the shootout in
parentheses ("1 (4) - 1 (3)"), not the football-data.org fullTime total that
folds the shootout into the goals (which would read "5 - 4")."""
from data_sources.football_data_client import normalize_matches_to_dataframe
from src.fixture_display import format_scoreline


def _match(score: dict) -> dict:
    return {
        "matches": [
            {
                "id": 1,
                "utcDate": "2026-07-04T19:00:00Z",
                "homeTeam": {"name": "Germany"},
                "awayTeam": {"name": "Paraguay"},
                "score": score,
            }
        ]
    }


def test_shootout_folded_into_fulltime_is_peeled_back_out():
    row = normalize_matches_to_dataframe(
        _match(
            {
                "winner": "HOME_TEAM",
                "duration": "PENALTY_SHOOTOUT",
                "fullTime": {"home": 5, "away": 4},
                "penalties": {"home": 4, "away": 3},
            }
        )
    ).iloc[0]
    assert (row["home_score"], row["away_score"]) == (1, 1)
    assert (row["home_penalties"], row["away_penalties"]) == (4, 3)
    assert format_scoreline(row) == "1 (4) - 1 (3)"


def test_shootout_with_regulation_already_in_fulltime():
    # If the feed reports the level regulation score in fullTime and the shootout
    # separately, keep both rather than subtracting into a negative.
    row = normalize_matches_to_dataframe(
        _match(
            {
                "winner": "AWAY_TEAM",
                "duration": "PENALTY_SHOOTOUT",
                "fullTime": {"home": 1, "away": 1},
                "penalties": {"home": 4, "away": 5},
            }
        )
    ).iloc[0]
    assert (row["home_score"], row["away_score"]) == (1, 1)
    assert format_scoreline(row) == "1 (4) - 1 (5)"


def test_regular_match_is_unchanged():
    row = normalize_matches_to_dataframe(
        _match(
            {
                "winner": "HOME_TEAM",
                "duration": "REGULAR",
                "fullTime": {"home": 3, "away": 1},
            }
        )
    ).iloc[0]
    assert (row["home_score"], row["away_score"]) == (3, 1)
    assert row["home_penalties"] is None and row["away_penalties"] is None
    assert format_scoreline(row) == "3 - 1"
