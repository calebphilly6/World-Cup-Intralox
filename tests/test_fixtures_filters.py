import pandas as pd

from src.pages.fixtures import _team_filter_options_from_known


def test_team_filter_options_exclude_fixture_placeholders():
    fixtures = pd.DataFrame(
        [
            {"home_team": "Canada", "away_team": "1A"},
            {"home_team": "Winner M79", "away_team": "Brazil"},
            {"home_team": "2C", "away_team": "Mexico"},
        ]
    )

    options = _team_filter_options_from_known(fixtures, ["Brazil", "Canada", "Mexico"])

    assert options == ["Brazil", "Canada", "Mexico"]
