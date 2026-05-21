from datetime import datetime, timezone

import pandas as pd

from src.pages.dashboard import _favorite_stage_label, _next_game_label


def test_favorite_stage_label_shows_eliminated_when_team_is_out():
    label = _favorite_stage_label(
        True,
        "",
        pd.DataFrame(),
        datetime(2026, 7, 5, tzinfo=timezone.utc),
        1,
    )

    assert label == "Eliminated"


def test_favorite_stage_label_keeps_current_round_when_team_is_alive():
    fixtures = pd.DataFrame(
        [
            {
                "match_number": 1,
                "kickoff_utc": "2026-07-04T20:00:00Z",
                "stage": "Quarter-finals",
                "home_score": pd.NA,
                "away_score": pd.NA,
                "home_team_id": 1,
                "away_team_id": 2,
            }
        ]
    )

    label = _favorite_stage_label(
        False,
        "",
        fixtures,
        datetime(2026, 7, 4, 12, tzinfo=timezone.utc),
        1,
    )

    assert label == "Quarterfinals"


def test_next_game_label_uses_date_and_away_opponent_for_home_team():
    fixture = pd.Series(
        {
            "kickoff_utc": "2026-06-16T21:00:00Z",
            "home_team_id": 1,
            "away_team_id": 2,
            "home_team": "Canada",
            "away_team": "Brazil",
        }
    )

    assert _next_game_label(fixture, 1, "Canada") == "Next Game: June 16 vs Brazil"


def test_next_game_label_uses_date_and_home_opponent_for_away_team():
    fixture = pd.Series(
        {
            "kickoff_utc": "2026-06-17T01:00:00Z",
            "home_team_id": 1,
            "away_team_id": 2,
            "home_team": "Mexico",
            "away_team": "Japan",
        }
    )

    assert _next_game_label(fixture, 2, "Japan") == "Next Game: June 16 vs Mexico"
