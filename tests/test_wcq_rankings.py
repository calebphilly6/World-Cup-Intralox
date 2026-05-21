import pandas as pd

from src.pages import wcq


def test_wcq_rankings_are_overlaid_from_latest_global_rankings(monkeypatch):
    def fake_fetch_df(query, params=None, db_path=None):
        return pd.DataFrame(
            [
                {"team_name": "Spain", "ranking_date": "2026-04-01", "rank": 2},
                {"team_name": "Czechia", "ranking_date": "2026-04-01", "rank": 38},
            ]
        )

    monkeypatch.setattr(wcq, "fetch_df", fake_fetch_df)
    payload = {
        "standings": pd.DataFrame(
            [
                {"team_name": "Spain", "fifa_rank": "3", "rank_snapshot_date": "2024-11-28"},
                {"team_name": "Czech Republic", "fifa_rank": "42", "rank_snapshot_date": "2024-11-28"},
            ]
        ),
        "runners_up_ranking": pd.DataFrame(columns=["team_name", "fifa_rank", "rank_snapshot_date"]),
        "eliminated": pd.DataFrame(columns=["team_name", "fifa_rank", "rank_snapshot_date"]),
        "qualified": pd.DataFrame(columns=["team_name", "fifa_rank", "rank_snapshot_date"]),
        "matches": pd.DataFrame(columns=["home_team_name", "home_fifa_rank", "away_team_name", "away_fifa_rank"]),
        "playoff_ties": pd.DataFrame(columns=["team1_name", "team1_fifa_rank", "team2_name", "team2_fifa_rank"]),
    }

    wcq._apply_global_fifa_rankings(payload)

    assert payload["standings"]["fifa_rank"].tolist() == ["2", "38"]
    assert payload["standings"]["rank_snapshot_date"].tolist() == ["2026-04-01", "2026-04-01"]


def test_wcq_identity_enrichment_does_not_restore_csv_rank(monkeypatch):
    monkeypatch.setattr(
        wcq,
        "_team_identity_lookup",
        lambda: {"ESP": {"team_name": "Spain", "fifa_code": "ESP", "flag_code": "ES", "fifa_rank": "3"}},
    )

    row = wcq._enrich_team_identity(pd.Series({"team_name": "Spain", "fifa_code": "ESP", "flag_code": "", "fifa_rank": ""}))

    assert row["flag_code"] == "ES"
    assert row["fifa_rank"] == ""


def test_wcq_rankings_are_cleared_when_global_rank_is_missing(monkeypatch):
    monkeypatch.setattr(wcq, "fetch_df", lambda query, params=None, db_path=None: pd.DataFrame(columns=["team_name", "ranking_date", "rank"]))
    payload = {
        "standings": pd.DataFrame([{"team_name": "Spain", "fifa_rank": "3", "rank_snapshot_date": "2024-11-28"}]),
        "runners_up_ranking": pd.DataFrame(columns=["team_name", "fifa_rank", "rank_snapshot_date"]),
        "eliminated": pd.DataFrame(columns=["team_name", "fifa_rank", "rank_snapshot_date"]),
        "qualified": pd.DataFrame(columns=["team_name", "fifa_rank", "rank_snapshot_date"]),
        "matches": pd.DataFrame(columns=["home_team_name", "home_fifa_rank", "away_team_name", "away_fifa_rank"]),
        "playoff_ties": pd.DataFrame(columns=["team1_name", "team1_fifa_rank", "team2_name", "team2_fifa_rank"]),
    }

    wcq._apply_global_fifa_rankings(payload)

    assert payload["standings"].iloc[0]["fifa_rank"] == ""
    assert payload["standings"].iloc[0]["rank_snapshot_date"] == ""
