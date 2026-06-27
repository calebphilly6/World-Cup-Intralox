import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from src.world_cup_scoring import (
    TeamScore,
    calculate_owner_leaderboard,
    daily_score_refresh_key,
    validate_assignments,
)


class WorldCupScoringTests(unittest.TestCase):
    def test_pot_one_champion_example_score(self):
        score = TeamScore(
            team="Example",
            owner="Owner",
            pot=1,
            group_wins=3,
            group_finish=1,
            won_round_of_32=True,
            won_round_of_16=True,
            won_quarterfinal=True,
            won_semifinal=True,
            won_final=True,
        )

        # group 9 + finish 3 + knockout (5+5+5+5+10) = 42
        self.assertEqual(score.base_score, 42)
        self.assertEqual(score.adjusted_score, 42)

    def test_pot_four_third_place_advance_example_score(self):
        score = TeamScore(
            team="Example",
            owner="Owner",
            pot=4,
            group_wins=1,
            group_draws=1,
            group_finish=3,
            advanced=True,
            won_round_of_32=True,
        )

        # group (3+1) + finish 1 + won R32 5 = 10, pot 4 doubles to 20
        self.assertEqual(score.base_score, 10)
        self.assertEqual(score.adjusted_score, 20)

    def test_leaderboard_orders_by_score_then_teams_left_then_name(self):
        scores = [
            TeamScore("A", "Jordan", 1, group_wins=1),
            TeamScore("B", "Alex", 4, group_wins=1, eliminated=True),
            TeamScore("C", "Alex", 1),
            TeamScore("D", "Casey", 2, group_draws=1),
        ]

        leaderboard = calculate_owner_leaderboard(scores, {"Alex": 2, "Jordan": 1})

        self.assertEqual([row["person"] for row in leaderboard], ["Alex", "Jordan", "Casey"])
        self.assertEqual(leaderboard[0]["rank"], 1)
        self.assertEqual(leaderboard[0]["movement"], "Up 1")

    def test_assignment_validation_requires_12_people_four_pots_and_unique_teams(self):
        assignments = []
        for person_index in range(12):
            for pot in (1, 2, 3, 4):
                assignments.append(
                    {
                        "person_name": f"Person {person_index + 1}",
                        "team": f"Team {person_index + 1}-{pot}",
                        "pot": pot,
                    }
                )

        self.assertEqual(validate_assignments(assignments), [])

        assignments[0]["team"] = assignments[1]["team"]
        errors = validate_assignments(assignments)
        self.assertTrue(any("Each team can only be assigned once" in error for error in errors))

    def test_daily_score_refresh_key_rolls_after_4am_central(self):
        zone = ZoneInfo("America/Chicago")

        before = datetime(2026, 6, 20, 3, 59, tzinfo=zone)
        after = datetime(2026, 6, 20, 4, 0, tzinfo=zone)

        self.assertEqual(daily_score_refresh_key(before), "2026-06-19")
        self.assertEqual(daily_score_refresh_key(after), "2026-06-20")


if __name__ == "__main__":
    unittest.main()
