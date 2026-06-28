from datetime import datetime, timezone

import pandas as pd

from src import team_status


NOW = datetime(2026, 6, 28, 12, tzinfo=timezone.utc)


def _fixture(**kwargs) -> dict:
    base = {
        "kickoff_utc": "2026-06-20T18:00:00Z",
        "stage": "GROUP_STAGE",
        "home_team": "Brazil",
        "away_team": "Serbia",
        "home_score": pd.NA,
        "away_score": pd.NA,
        "match_number": 1,
    }
    base.update(kwargs)
    return base


def test_round_label_handles_feed_stage_strings():
    assert team_status.round_label("LAST_32") == "Round of 32"
    assert team_status.round_label("LAST_16") == "Round of 16"
    assert team_status.round_label("QUARTER_FINALS") == "Quarterfinals"
    assert team_status.round_label("SEMI_FINALS") == "Semifinals"
    assert team_status.round_label("FINAL") == "Finals"
    assert team_status.round_label("GROUP_STAGE") == "Group Stage"


def test_current_round_uses_next_fixture_stage():
    fixtures = pd.DataFrame([_fixture(kickoff_utc="2026-07-03T18:00:00Z", stage="QUARTER_FINALS")])
    assert team_status.current_round(fixtures, NOW, "Brazil") == "Quarterfinals"


def test_is_eliminated_when_knockout_match_lost_and_nothing_left():
    fixtures = pd.DataFrame(
        [
            _fixture(
                kickoff_utc="2026-06-25T18:00:00Z",
                stage="LAST_16",
                home_team="Brazil",
                away_team="France",
                home_score=0,
                away_score=2,
            )
        ]
    )
    assert team_status.is_eliminated(fixtures, NOW, "Brazil") is True


def test_not_eliminated_when_an_upcoming_match_exists():
    fixtures = pd.DataFrame(
        [
            _fixture(
                kickoff_utc="2026-07-03T18:00:00Z",
                stage="QUARTER_FINALS",
                home_team="Brazil",
                away_team="Spain",
            )
        ]
    )
    assert team_status.is_eliminated(fixtures, NOW, "Brazil") is False


def test_group_stage_exit_only_counts_once_bracket_is_complete():
    fixtures = pd.DataFrame(
        [
            _fixture(home_team="Serbia", away_team="Brazil", home_score=0, away_score=1),
            _fixture(
                kickoff_utc="2026-06-24T18:00:00Z",
                home_team="Serbia",
                away_team="Switzerland",
                home_score=1,
                away_score=2,
            ),
        ]
    )
    # Bracket not yet resolved -> do not assert elimination from group results.
    assert team_status.is_eliminated(fixtures, NOW, "Serbia", bracket_complete=False) is False
    # Bracket resolved and Serbia is not in it -> eliminated.
    assert (
        team_status.is_eliminated(fixtures, NOW, "Serbia", bracket_complete=True, knockout_keys=frozenset())
        is True
    )


def test_group_qualifier_not_marked_eliminated_even_when_bracket_complete():
    fixtures = pd.DataFrame(
        [_fixture(home_team="Serbia", away_team="Brazil", home_score=0, away_score=3)]
    )
    keys = team_status.knockout_participant_keys({"1A": "Brazil"})
    assert (
        team_status.is_eliminated(
            fixtures, NOW, "Brazil", bracket_complete=True, knockout_keys=keys
        )
        is False
    )


def test_normalize_feed_renames_feed_columns():
    feed = pd.DataFrame(
        [{"utc_date": "2026-06-20T18:00:00Z", "official_match_number": 7, "home_team": "Brazil"}]
    )
    normalized = team_status.normalize_feed(feed)
    assert normalized.loc[0, "kickoff_utc"] == "2026-06-20T18:00:00Z"
    assert normalized.loc[0, "match_number"] == 7


def test_bracket_is_complete_threshold():
    assert team_status.bracket_is_complete({str(i): f"T{i}" for i in range(32)}) is True
    assert team_status.bracket_is_complete({str(i): f"T{i}" for i in range(20)}) is False
