import unittest
from unittest.mock import patch

from src.tournament_odds_service import refresh_tournament_odds_if_available


class OddsRefreshGateTests(unittest.TestCase):
    def test_completed_daily_marker_skips_odds_api_call(self):
        with (
            patch("src.tournament_odds_service.get_api_key", return_value="test-key"),
            patch("src.tournament_odds_service.refresh_was_completed", return_value=True),
            patch("src.tournament_odds_service.fetch_outrights") as fetch_outrights,
        ):
            result = refresh_tournament_odds_if_available(refresh_key="2026-06-01")

        self.assertEqual(result, {"saved": 0, "skipped": True})
        fetch_outrights.assert_not_called()


if __name__ == "__main__":
    unittest.main()
