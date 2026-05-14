from __future__ import annotations

from src.database import DB_PATH, get_connection
from src.match_city_reference import MATCH_CITY_REFERENCE
from src.utils.formatting import flag_for_code


WORLD_CUP_GROUPS_2026 = {
    "A": [
        ("Mexico", "MX", "CONCACAF"),
        ("South Africa", "ZA", "CAF"),
        ("South Korea", "KR", "AFC"),
        ("Czechia", "CZ", "UEFA"),
    ],
    "B": [
        ("Canada", "CA", "CONCACAF"),
        ("Switzerland", "CH", "UEFA"),
        ("Qatar", "QA", "AFC"),
        ("Bosnia and Herzegovina", "BA", "UEFA"),
    ],
    "C": [
        ("Brazil", "BR", "CONMEBOL"),
        ("Morocco", "MA", "CAF"),
        ("Haiti", "HT", "CONCACAF"),
        ("Scotland", None, "UEFA"),
    ],
    "D": [
        ("USA", "US", "CONCACAF"),
        ("Paraguay", "PY", "CONMEBOL"),
        ("Australia", "AU", "AFC"),
        ("Türkiye", "TR", "UEFA"),
    ],
    "E": [
        ("Germany", "DE", "UEFA"),
        ("Curaçao", "CW", "CONCACAF"),
        ("Côte d'Ivoire", "CI", "CAF"),
        ("Ecuador", "EC", "CONMEBOL"),
    ],
    "F": [
        ("Netherlands", "NL", "UEFA"),
        ("Japan", "JP", "AFC"),
        ("Sweden", "SE", "UEFA"),
        ("Tunisia", "TN", "CAF"),
    ],
    "G": [
        ("Belgium", "BE", "UEFA"),
        ("Egypt", "EG", "CAF"),
        ("IR Iran", "IR", "AFC"),
        ("New Zealand", "NZ", "OFC"),
    ],
    "H": [
        ("Spain", "ES", "UEFA"),
        ("Cabo Verde", "CV", "CAF"),
        ("Saudi Arabia", "SA", "AFC"),
        ("Uruguay", "UY", "CONMEBOL"),
    ],
    "I": [
        ("France", "FR", "UEFA"),
        ("Senegal", "SN", "CAF"),
        ("Norway", "NO", "UEFA"),
        ("Iraq", "IQ", "AFC"),
    ],
    "J": [
        ("Argentina", "AR", "CONMEBOL"),
        ("Algeria", "DZ", "CAF"),
        ("Austria", "AT", "UEFA"),
        ("Jordan", "JO", "AFC"),
    ],
    "K": [
        ("Portugal", "PT", "UEFA"),
        ("Congo DR", "CD", "CAF"),
        ("Uzbekistan", "UZ", "AFC"),
        ("Colombia", "CO", "CONMEBOL"),
    ],
    "L": [
        ("England", None, "UEFA"),
        ("Croatia", "HR", "UEFA"),
        ("Ghana", "GH", "CAF"),
        ("Panama", "PA", "CONCACAF"),
    ],
}


def seed_world_cup_2026_reference_data(db_path=DB_PATH) -> None:
    """Seed confirmed 2026 teams/groups while preserving personal fields."""
    with get_connection(db_path) as conn:
        _migrate_team_names(conn)
        expected_pairs = set()
        for group_name, teams in WORLD_CUP_GROUPS_2026.items():
            for team_name, country_code, confederation in teams:
                expected_pairs.add((group_name, team_name))
                conn.execute(
                    """
                    INSERT INTO teams (name, country_code, flag, confederation)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(name) DO UPDATE SET
                        country_code = COALESCE(teams.country_code, excluded.country_code),
                        flag = COALESCE(teams.flag, excluded.flag),
                        confederation = COALESCE(teams.confederation, excluded.confederation),
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (team_name, country_code, flag_for_code(country_code), confederation),
                )
                row = conn.execute("SELECT id FROM teams WHERE name = ?", (team_name,)).fetchone()
                conn.execute(
                    """
                    INSERT INTO groups (group_name, team_id, qualification_status)
                    VALUES (?, ?, COALESCE(
                        (SELECT qualification_status FROM groups WHERE group_name = ? AND team_id = ?),
                        'Pending'
                    ))
                    ON CONFLICT(group_name, team_id) DO UPDATE SET
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (group_name, row["id"], group_name, row["id"]),
                )
        _remove_unexpected_group_rows(conn, expected_pairs)
        _remove_old_team_names(conn)
        _seed_match_city_reference(conn)
        conn.commit()


def _seed_match_city_reference(conn) -> None:
    for match_number, round_name, game_label, city in MATCH_CITY_REFERENCE:
        conn.execute(
            """
            INSERT INTO match_city_reference (match_number, round_name, game_label, city)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(match_number) DO UPDATE SET
                round_name = excluded.round_name,
                game_label = excluded.game_label,
                city = excluded.city,
                updated_at = CURRENT_TIMESTAMP
            """,
            (match_number, round_name, game_label, city),
        )
        conn.execute(
            """
            UPDATE fixtures
            SET city = ?, updated_at = CURRENT_TIMESTAMP
            WHERE match_number = ?
            """,
            (city, match_number),
        )


def _migrate_team_names(conn) -> None:
    migrations = {
        "United States": "USA",
        "Turkey": "Türkiye",
        "Turkiye": "Türkiye",
        "Curacao": "Curaçao",
        "DR Congo": "Congo DR",
        "Iran": "IR Iran",
        "Bosnia & Herzegovina": "Bosnia and Herzegovina",
        "Cape Verde": "Cabo Verde",
        "Czech Republic": "Czechia",
        "Cote d'Ivoire": "Côte d'Ivoire",
        "Ivory Coast": "Côte d'Ivoire",
    }
    for old_name, new_name in migrations.items():
        old = conn.execute("SELECT id FROM teams WHERE name = ?", (old_name,)).fetchone()
        if old is None:
            continue
        new = conn.execute("SELECT id FROM teams WHERE name = ?", (new_name,)).fetchone()
        if new is None:
            conn.execute("UPDATE teams SET name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (new_name, old["id"]))
            conn.execute(
                "UPDATE global_fifa_rankings SET team_name = ? WHERE team_name = ?",
                (new_name, old_name),
            )
        else:
            _merge_team_ids(conn, old["id"], new["id"])
            conn.execute("DELETE FROM teams WHERE id = ?", (old["id"],))
            conn.execute(
                "UPDATE global_fifa_rankings SET team_name = ? WHERE team_name = ?",
                (new_name, old_name),
            )


def _merge_team_ids(conn, old_id: int, new_id: int) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO groups (group_name, team_id, qualification_status)
        SELECT group_name, ?, qualification_status
        FROM groups
        WHERE team_id = ?
        """,
        (new_id, old_id),
    )
    conn.execute("DELETE FROM groups WHERE team_id = ?", (old_id,))
    conn.execute("UPDATE fixtures SET home_team_id = ? WHERE home_team_id = ?", (new_id, old_id))
    conn.execute("UPDATE fixtures SET away_team_id = ? WHERE away_team_id = ?", (new_id, old_id))
    conn.execute("UPDATE odds_snapshots SET team_id = ? WHERE team_id = ?", (new_id, old_id))
    conn.execute("UPDATE predictions SET subject_id = ? WHERE subject_type = 'team' AND subject_id = ?", (new_id, old_id))
    conn.execute("UPDATE simulation_results SET team_id = ? WHERE team_id = ?", (new_id, old_id))
    conn.execute(
        """
        INSERT OR IGNORE INTO fifa_rankings (team_id, ranking_date, rank, points, previous_rank, source, notes)
        SELECT ?, ranking_date, rank, points, previous_rank, source, notes
        FROM fifa_rankings
        WHERE team_id = ?
        """,
        (new_id, old_id),
    )
    conn.execute("DELETE FROM fifa_rankings WHERE team_id = ?", (old_id,))
    conn.execute(
        """
        INSERT OR IGNORE INTO standings (group_name, team_id, played, wins, draws, losses, goals_for, goals_against, points)
        SELECT group_name, ?, played, wins, draws, losses, goals_for, goals_against, points
        FROM standings
        WHERE team_id = ?
        """,
        (new_id, old_id),
    )
    conn.execute("DELETE FROM standings WHERE team_id = ?", (old_id,))


def _remove_unexpected_group_rows(conn, expected_pairs: set[tuple[str, str]]) -> None:
    rows = conn.execute(
        """
        SELECT g.id, g.group_name, t.name AS team_name
        FROM groups g
        JOIN teams t ON t.id = g.team_id
        """
    ).fetchall()
    for row in rows:
        if (row["group_name"], row["team_name"]) not in expected_pairs:
            conn.execute("DELETE FROM groups WHERE id = ?", (row["id"],))


def _remove_old_team_names(conn) -> None:
    old_names = [
        "United States",
        "Turkey",
        "Turkiye",
        "Curacao",
        "DR Congo",
        "Iran",
        "Bosnia & Herzegovina",
        "Cape Verde",
        "Czech Republic",
        "Cote d'Ivoire",
        "Ivory Coast",
    ]
    for old_name in old_names:
        row = conn.execute("SELECT id FROM teams WHERE name = ?", (old_name,)).fetchone()
        if row is None:
            continue
        references = [
            conn.execute("SELECT COUNT(*) AS count FROM groups WHERE team_id = ?", (row["id"],)).fetchone()["count"],
            conn.execute("SELECT COUNT(*) AS count FROM fixtures WHERE home_team_id = ? OR away_team_id = ?", (row["id"], row["id"])).fetchone()["count"],
            conn.execute("SELECT COUNT(*) AS count FROM fifa_rankings WHERE team_id = ?", (row["id"],)).fetchone()["count"],
            conn.execute("SELECT COUNT(*) AS count FROM odds_snapshots WHERE team_id = ?", (row["id"],)).fetchone()["count"],
            conn.execute("SELECT COUNT(*) AS count FROM standings WHERE team_id = ?", (row["id"],)).fetchone()["count"],
        ]
        if sum(references) == 0:
            conn.execute("DELETE FROM teams WHERE id = ?", (row["id"],))
