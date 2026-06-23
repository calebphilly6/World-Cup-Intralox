import pandas as pd

from src.intralox_results import derive_intralox_results
from src.official_match_reference import normalize_team_key


def _key(name: str) -> str:
    return normalize_team_key(name)


def test_completed_group_match_awards_win_and_loss():
    fixtures = pd.DataFrame(
        [
            {
                "stage": "GROUP_STAGE",
                "group": "GROUP_A",
                "home_team": "Mexico",
                "away_team": "South Africa",
                "home_score": 2,
                "away_score": 0,
                "winner": "HOME_TEAM",
            }
        ]
    )

    derived = derive_intralox_results(fixtures)

    assert derived[_key("Mexico")]["group_wins"] == 1
    assert derived[_key("Mexico")]["group_draws"] == 0
    assert derived[_key("South Africa")]["group_wins"] == 0


def test_draw_awards_a_group_draw_to_both_teams():
    fixtures = pd.DataFrame(
        [
            {
                "stage": "GROUP_STAGE",
                "group": "GROUP_B",
                "home_team": "Canada",
                "away_team": "Bosnia and Herzegovina",
                "home_score": 1,
                "away_score": 1,
                "winner": "DRAW",
            }
        ]
    )

    derived = derive_intralox_results(fixtures)

    assert derived[_key("Canada")]["group_draws"] == 1
    assert derived[_key("Bosnia-Herzegovina")]["group_draws"] == 1


def test_unplayed_match_does_not_score():
    fixtures = pd.DataFrame(
        [
            {
                "stage": "GROUP_STAGE",
                "group": "GROUP_C",
                "home_team": "Brazil",
                "away_team": "Morocco",
                "home_score": None,
                "away_score": None,
                "winner": None,
            }
        ]
    )

    assert derive_intralox_results(fixtures) == {}


def test_knockout_win_sets_round_flag_and_eliminates_loser():
    fixtures = pd.DataFrame(
        [
            {
                "stage": "QUARTER_FINALS",
                "group": None,
                "home_team": "France",
                "away_team": "Germany",
                "home_score": 0,
                "away_score": 0,
                "winner": "AWAY_TEAM",  # decided on penalties
            }
        ]
    )

    derived = derive_intralox_results(fixtures)

    assert derived[_key("Germany")]["won_quarterfinal"] is True
    assert derived[_key("Germany")]["advanced"] is True
    assert derived[_key("Germany")]["eliminated"] is False
    assert derived[_key("France")]["won_quarterfinal"] is False
    assert derived[_key("France")]["advanced"] is True
    assert derived[_key("France")]["eliminated"] is True


def test_completed_group_assigns_finish_and_eliminates_bottom_team():
    rows = []
    teams = ["Spain", "Uruguay", "Norway", "Qatar"]
    # Spain wins all, Uruguay second, Norway third, Qatar last (loses all).
    scripted = [
        ("Spain", "Qatar", 3, 0),
        ("Spain", "Norway", 2, 0),
        ("Spain", "Uruguay", 1, 0),
        ("Uruguay", "Qatar", 2, 0),
        ("Uruguay", "Norway", 1, 0),
        ("Norway", "Qatar", 1, 0),
    ]
    for home, away, hs, as_ in scripted:
        rows.append(
            {
                "stage": "GROUP_STAGE",
                "group": "GROUP_E",
                "home_team": home,
                "away_team": away,
                "home_score": hs,
                "away_score": as_,
                "winner": "HOME_TEAM",
            }
        )

    derived = derive_intralox_results(pd.DataFrame(rows))

    assert derived[_key("Spain")]["group_finish"] == 1
    assert derived[_key("Spain")]["advanced"] is True
    assert derived[_key("Uruguay")]["group_finish"] == 2
    assert derived[_key("Qatar")]["group_finish"] == 4
    assert derived[_key("Qatar")]["eliminated"] is True


def _home_win_or_loss(home, away, hs, as_):
    return {
        "stage": "GROUP_STAGE",
        "group": "GROUP_HH",
        "home_team": home,
        "away_team": away,
        "home_score": hs,
        "away_score": as_,
        "winner": "HOME_TEAM" if hs > as_ else "AWAY_TEAM",
    }


def test_head_to_head_breaks_a_group_tie():
    # P and Q tie on points/GD/GF, but P beat Q; R and S tie, but S beat R.
    games = [
        ("P", "Q", 1, 0),
        ("P", "R", 0, 1),
        ("P", "S", 1, 0),
        ("Q", "R", 1, 0),
        ("Q", "S", 1, 0),
        ("R", "S", 0, 1),
    ]
    derived = derive_intralox_results(
        pd.DataFrame([_home_win_or_loss(h, a, hs, as_) for h, a, hs, as_ in games])
    )
    assert derived[_key("P")]["group_finish"] == 1
    assert derived[_key("Q")]["group_finish"] == 2
    # S won the head-to-head with R, so it finishes ahead despite the equal table.
    assert derived[_key("S")]["group_finish"] == 3
    assert derived[_key("R")]["group_finish"] == 4


def test_only_eight_best_third_place_teams_advance():
    rows = []
    for i in range(1, 13):
        a, b, c, d = f"A{i}", f"B{i}", f"C{i}", f"D{i}"
        group = f"GROUP_{i}"
        # A 1st, B 2nd, C 3rd, D last. C's goal difference grows with i, so the
        # higher-numbered groups own the better third-place teams.
        scripted = [(a, b, 1, 0), (a, c, 1, 0), (a, d, 1, 0), (b, c, 1, 0), (b, d, 1, 0), (c, d, i, 0)]
        for home, away, hs, as_ in scripted:
            rows.append(
                {
                    "stage": "GROUP_STAGE",
                    "group": group,
                    "home_team": home,
                    "away_team": away,
                    "home_score": hs,
                    "away_score": as_,
                    "winner": "HOME_TEAM",
                }
            )
    derived = derive_intralox_results(pd.DataFrame(rows))

    advanced = sorted(i for i in range(1, 13) if derived[_key(f"C{i}")]["advanced"])
    eliminated = sorted(i for i in range(1, 13) if derived[_key(f"C{i}")]["eliminated"])
    assert advanced == [5, 6, 7, 8, 9, 10, 11, 12]
    assert eliminated == [1, 2, 3, 4]

    # An eliminated third keeps its earned points; elimination only stops it
    # from earning more (still_alive turns False).
    out = derived[_key("C1")]
    assert out["group_wins"] == 1
    assert out["group_finish"] == 3
    assert out["advanced"] is False
    assert out["eliminated"] is True


def test_finish_not_assigned_until_group_is_complete():
    fixtures = pd.DataFrame(
        [
            {
                "stage": "GROUP_STAGE",
                "group": "GROUP_F",
                "home_team": "Netherlands",
                "away_team": "Japan",
                "home_score": 2,
                "away_score": 1,
                "winner": "HOME_TEAM",
            },
            {
                "stage": "GROUP_STAGE",
                "group": "GROUP_F",
                "home_team": "Sweden",
                "away_team": "Tunisia",
                "home_score": None,
                "away_score": None,
                "winner": None,
            },
        ]
    )

    derived = derive_intralox_results(fixtures)

    assert derived[_key("Netherlands")]["group_wins"] == 1
    assert derived[_key("Netherlands")]["group_finish"] is None
    assert derived[_key("Netherlands")]["eliminated"] is False
