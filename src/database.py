from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Iterator

import pandas as pd

from src.config import get_database_path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = get_database_path()


@contextmanager
def get_connection(db_path: Path = DB_PATH) -> Iterator[sqlite3.Connection]:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


def initialize_database(db_path: Path = DB_PATH) -> None:
    with get_connection(db_path) as conn:
        conn.executescript(SCHEMA)
        _sync_world_cup_rankings_to_global(conn)


def fetch_df(query: str, params: Iterable | None = None, db_path: Path = DB_PATH) -> pd.DataFrame:
    with get_connection(db_path) as conn:
        return pd.read_sql_query(query, conn, params=list(params or []))


def execute(query: str, params: Iterable | None = None, db_path: Path = DB_PATH) -> None:
    with get_connection(db_path) as conn:
        conn.execute(query, tuple(params or []))
        conn.commit()


def _sync_world_cup_rankings_to_global(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        INSERT INTO global_fifa_rankings (
            team_name, ranking_date, rank, points, previous_rank, source, notes, is_world_cup_team
        )
        SELECT t.name, r.ranking_date, r.rank, r.points, r.previous_rank, r.source, r.notes, 1
        FROM fifa_rankings r
        JOIN teams t ON t.id = r.team_id
        ON CONFLICT(team_name, ranking_date) DO UPDATE SET
            rank = excluded.rank,
            points = excluded.points,
            previous_rank = excluded.previous_rank,
            source = excluded.source,
            notes = excluded.notes,
            is_world_cup_team = 1
        """
    )


SCHEMA = """
CREATE TABLE IF NOT EXISTS teams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    country_code TEXT,
    flag TEXT,
    confederation TEXT,
    favorite INTEGER DEFAULT 0,
    personal_rating INTEGER,
    excitement_score INTEGER,
    notes TEXT,
    why_interested TEXT,
    key_players TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_name TEXT NOT NULL,
    team_id INTEGER NOT NULL,
    qualification_status TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(group_name, team_id),
    FOREIGN KEY(team_id) REFERENCES teams(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS roster_players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id INTEGER NOT NULL,
    player_name TEXT NOT NULL,
    shirt_number INTEGER,
    position TEXT,
    club TEXT,
    source TEXT DEFAULT 'manual',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(team_id, player_name),
    FOREIGN KEY(team_id) REFERENCES teams(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS venues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stadium_name TEXT NOT NULL UNIQUE,
    city TEXT,
    country TEXT,
    capacity INTEGER,
    latitude REAL,
    longitude REAL,
    map_link TEXT,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fixtures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_number INTEGER UNIQUE,
    kickoff_utc TEXT NOT NULL,
    home_team_id INTEGER,
    away_team_id INTEGER,
    stage TEXT NOT NULL,
    group_name TEXT,
    venue_id INTEGER,
    city TEXT,
    host_country TEXT,
    status TEXT DEFAULT 'Scheduled',
    home_score INTEGER,
    away_score INTEGER,
    watch_priority TEXT DEFAULT 'Maybe',
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(home_team_id) REFERENCES teams(id),
    FOREIGN KEY(away_team_id) REFERENCES teams(id),
    FOREIGN KEY(venue_id) REFERENCES venues(id)
);

CREATE TABLE IF NOT EXISTS match_city_reference (
    match_number INTEGER PRIMARY KEY,
    round_name TEXT NOT NULL,
    game_label TEXT NOT NULL,
    city TEXT NOT NULL,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Sticky cache of knockout participants. The football-data.org feed populates
-- bracket teams (e.g. "United States") intermittently and sometimes blanks them
-- back out. We remember each real team the feed has shown for a knockout slot so
-- the bracket keeps displaying it even when a later feed pull comes back empty.
CREATE TABLE IF NOT EXISTS knockout_participants (
    match_number INTEGER NOT NULL,
    slot_index INTEGER NOT NULL CHECK(slot_index IN (0, 1)),
    team_name TEXT NOT NULL,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (match_number, slot_index)
);

CREATE TABLE IF NOT EXISTS fifa_rankings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id INTEGER NOT NULL,
    ranking_date TEXT NOT NULL,
    rank INTEGER NOT NULL,
    points REAL,
    previous_rank INTEGER,
    source TEXT DEFAULT 'manual',
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(team_id, ranking_date),
    FOREIGN KEY(team_id) REFERENCES teams(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS global_fifa_rankings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_name TEXT NOT NULL,
    ranking_date TEXT NOT NULL,
    rank INTEGER NOT NULL,
    points REAL,
    previous_rank INTEGER,
    source TEXT DEFAULT 'manual',
    notes TEXT,
    is_world_cup_team INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(team_name, ranking_date)
);

CREATE TABLE IF NOT EXISTS odds_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id INTEGER,
    fixture_id INTEGER,
    market_type TEXT NOT NULL,
    odds_format TEXT,
    american_odds TEXT,
    decimal_odds REAL,
    implied_probability REAL,
    source TEXT DEFAULT 'manual',
    snapshot_ts TEXT NOT NULL,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(team_id) REFERENCES teams(id),
    FOREIGN KEY(fixture_id) REFERENCES fixtures(id)
);

CREATE TABLE IF NOT EXISTS fixture_odds_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fixture_id INTEGER,
    external_event_id TEXT,
    commence_time TEXT,
    home_team TEXT,
    away_team TEXT,
    bookmaker_key TEXT,
    bookmaker_title TEXT,
    market_type TEXT NOT NULL,
    outcome_name TEXT NOT NULL,
    odds_format TEXT,
    american_odds TEXT,
    decimal_odds REAL,
    implied_probability REAL,
    point REAL,
    source TEXT DEFAULT 'the_odds_api',
    snapshot_ts TEXT NOT NULL,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(fixture_id) REFERENCES fixtures(id)
);

CREATE TABLE IF NOT EXISTS standings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_name TEXT NOT NULL,
    team_id INTEGER NOT NULL,
    played INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0,
    draws INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    goals_for INTEGER DEFAULT 0,
    goals_against INTEGER DEFAULT 0,
    points INTEGER DEFAULT 0,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(group_name, team_id),
    FOREIGN KEY(team_id) REFERENCES teams(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_type TEXT NOT NULL,
    subject_id INTEGER,
    model_name TEXT DEFAULT 'personal_model',
    probability REAL,
    details_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS simulation_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_name TEXT NOT NULL,
    team_id INTEGER,
    result_type TEXT NOT NULL,
    probability REAL,
    details_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(team_id) REFERENCES teams(id)
);

CREATE TABLE IF NOT EXISTS brackets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    bracket_type TEXT,
    picks_json TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS personal_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_type TEXT NOT NULL,
    subject_id INTEGER,
    title TEXT,
    body TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS watchlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_type TEXT NOT NULL,
    item_id INTEGER,
    label TEXT NOT NULL,
    category TEXT,
    priority TEXT DEFAULT 'Maybe',
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(item_type, item_id, label, category)
);

CREATE TABLE IF NOT EXISTS api_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    last_request_cost TEXT,
    requests_used TEXT,
    requests_remaining TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS work_competition_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_name TEXT NOT NULL,
    team_id INTEGER NOT NULL,
    pot INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(person_name, team_id),
    FOREIGN KEY(team_id) REFERENCES teams(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS intralox_competition_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_name TEXT NOT NULL,
    team_id INTEGER NOT NULL UNIQUE,
    pot INTEGER NOT NULL CHECK(pot IN (1, 2, 3, 4)),
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(team_id) REFERENCES teams(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS intralox_competition_results (
    team_id INTEGER PRIMARY KEY,
    group_wins INTEGER DEFAULT 0,
    group_draws INTEGER DEFAULT 0,
    group_finish INTEGER,
    advanced INTEGER DEFAULT 0,
    won_round_of_32 INTEGER DEFAULT 0,
    won_round_of_16 INTEGER DEFAULT 0,
    won_quarterfinal INTEGER DEFAULT 0,
    won_semifinal INTEGER DEFAULT 0,
    won_final INTEGER DEFAULT 0,
    eliminated INTEGER DEFAULT 0,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(team_id) REFERENCES teams(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS intralox_competition_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_key TEXT NOT NULL,
    person_name TEXT NOT NULL,
    rank INTEGER NOT NULL,
    total_score REAL NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(snapshot_key, person_name)
);

CREATE TABLE IF NOT EXISTS app_metadata (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS match_detail_fetch (
    match_number INTEGER PRIMARY KEY,
    espn_event_id TEXT,
    found INTEGER DEFAULT 0,
    source TEXT DEFAULT 'espn',
    fetched_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS match_goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_number INTEGER NOT NULL,
    sort_order INTEGER NOT NULL,
    minute TEXT,
    team_name TEXT,
    scorer TEXT,
    assist TEXT,
    detail TEXT,
    is_penalty INTEGER DEFAULT 0,
    is_own_goal INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS match_substitutions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_number INTEGER NOT NULL,
    sort_order INTEGER NOT NULL,
    team_name TEXT,
    minute TEXT,
    player_on TEXT,
    player_off TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS match_lineups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_number INTEGER NOT NULL,
    team_name TEXT,
    home_away TEXT,
    formation TEXT,
    sort_order INTEGER NOT NULL,
    player_name TEXT,
    shirt_number TEXT,
    position TEXT,
    is_starter INTEGER DEFAULT 0,
    subbed_in INTEGER DEFAULT 0,
    subbed_out INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""
