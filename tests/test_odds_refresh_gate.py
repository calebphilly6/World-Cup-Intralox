import unittest
from unittest.mock import patch

from src.pages.odds import _auto_refresh_odds


class OddsRefreshGateTests(unittest.TestCase):
    def test_completed_daily_marker_skips_odds_api_call(self):
        with (
            patch("src.pages.odds.refresh_was_completed", return_value=True),
            patch("src.pages.odds.fetch_outrights") as fetch_outrights,
        ):
            result = _auto_refresh_odds(
                api_key="test-key",
                sport_key="soccer_fifa_world_cup_winner",
                regions="us",
                odds_format="american",
                bookmakers="draftkings",
                refresh_key="2026-06-01",
            )

        self.assertEqual(result, {"saved": 0, "skipped": True})
        fetch_outrights.assert_not_called()


if __name__ == "__main__":
    unittest.main()
