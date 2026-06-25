"""Re-validates the committed FIFA third-place allocation table and the resolver,
independently of the one-off fetch/parse script."""

import pandas as pd

import src.knockout_slots as ks
from src.pages.bracket_data import MATCHES

THIRD_MATCHES = (74, 77, 79, 80, 81, 82, 85, 87)


def _allowed_groups(match_number: int) -> set[str]:
    slot = next(s for s in MATCHES[match_number]["slots"] if s.startswith("3"))
    return set(slot[1:])


def test_allocation_table_has_495_valid_combinations():
    table = ks._allocation_table()
    assert len(table) == 495, f"expected 495 combinations, got {len(table)}"

    for key, allocation in table.items():
        qualifying = sorted(key)
        assert len(qualifying) == 8 and len(set(qualifying)) == 8
        assigned = sorted(allocation.values())
        # Every qualifying group's third is placed exactly once (a bijection).
        assert assigned == qualifying, f"{key}: {assigned} != {qualifying}"
        # And never against a same-group winner (FIFA rule, encoded in our labels).
        for match_number in THIRD_MATCHES:
            assert allocation[match_number] in _allowed_groups(match_number)


def test_known_combination_matches_source_row():
    # First row of FIFA's table: thirds advance from A-H.
    allocation = ks._allocation_table()["ABCDEFGH"]
    assert allocation == {74: "C", 77: "F", 79: "H", 80: "E", 81: "B", 82: "A", 85: "G", 87: "D"}


def test_third_place_slots_resolve_from_ranking(monkeypatch):
    # Synthetic best-eight thirds advancing from groups A-H.
    ranking = pd.DataFrame(
        [{"group_name": g, "team": f"Team {g}"} for g in "ABCDEFGH"]
    )
    monkeypatch.setattr(ks, "_third_place_ranking", lambda: ranking)

    slots = ks.third_place_slot_teams()

    # ABCDEFGH allocation -> M74 gets group C's third, M82 gets group A's third, etc.
    assert slots["3ABCDF"] == "Team C"   # M74
    assert slots["3AEHIJ"] == "Team A"   # M82
    assert slots["3DEIJL"] == "Team D"   # M87
    assert len(slots) == 8


def test_third_place_empty_before_eight_qualifiers(monkeypatch):
    ranking = pd.DataFrame([{"group_name": g, "team": f"Team {g}"} for g in "ABCDE"])
    monkeypatch.setattr(ks, "_third_place_ranking", lambda: ranking)
    assert ks.third_place_slot_teams() == {}
