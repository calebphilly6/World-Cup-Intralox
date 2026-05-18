from pathlib import Path
import tempfile
import unittest

import pandas as pd

from src.data_loader import import_dataframe
from src.database import fetch_df, initialize_database


class RosterImportTests(unittest.TestCase):
    def test_roster_import_upserts_players_for_team(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "worldcup.db"
            initialize_database(db_path)

            rows = pd.DataFrame(
                [
                    {
                        "team_name": "USA",
                        "player_name": "Christian Pulisic",
                        "shirt_number": 10,
                        "position": "FW",
                        "club": "AC Milan",
                    },
                    {
                        "team_name": "USA",
                        "player_name": "Tyler Adams",
                        "shirt_number": 4,
                        "position": "MF",
                        "club": "Bournemouth",
                    },
                ]
            )

            imported, errors = import_dataframe("rosters", rows, db_path)

            self.assertEqual(errors, [])
            self.assertEqual(imported, 2)
            roster = fetch_df(
                """
                SELECT t.name AS team_name, r.player_name, r.shirt_number, r.position, r.club
                FROM roster_players r
                JOIN teams t ON t.id = r.team_id
                ORDER BY r.shirt_number
                """,
                db_path=db_path,
            )
            self.assertEqual(roster["player_name"].tolist(), ["Tyler Adams", "Christian Pulisic"])


if __name__ == "__main__":
    unittest.main()
