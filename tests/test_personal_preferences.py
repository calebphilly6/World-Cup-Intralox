from pathlib import Path

from src.storage.storage import personal_preferences_use_browser_storage


def test_personal_preferences_always_use_browser_storage() -> None:
    assert personal_preferences_use_browser_storage() is True


def test_favorite_toggle_does_not_update_teams_table() -> None:
    teams_page = Path("src/pages/teams.py").read_text(encoding="utf-8")

    assert "UPDATE teams SET favorite" not in teams_page
