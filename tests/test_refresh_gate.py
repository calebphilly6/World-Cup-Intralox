from pathlib import Path
import tempfile
import unittest

from src.database import initialize_database
from src.refresh_gate import mark_refresh_completed, refresh_was_completed


class RefreshGateTests(unittest.TestCase):
    def test_refresh_marker_is_scoped_by_provider_resource_and_key(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "worldcup.db"
            initialize_database(db_path)

            self.assertFalse(refresh_was_completed("the_odds_api", "winner_odds", "2026-06-01", db_path))

            mark_refresh_completed("the_odds_api", "winner_odds", "2026-06-01", db_path)

            self.assertTrue(refresh_was_completed("the_odds_api", "winner_odds", "2026-06-01", db_path))
            self.assertFalse(refresh_was_completed("the_odds_api", "winner_odds", "2026-06-02", db_path))
            self.assertFalse(refresh_was_completed("football_data", "winner_odds", "2026-06-01", db_path))


if __name__ == "__main__":
    unittest.main()
