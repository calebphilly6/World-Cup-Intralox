from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Team:
    team_id: Optional[int]
    name: str
    country_code: Optional[str] = None
    flag: Optional[str] = None
    group_name: Optional[str] = None
    confederation: Optional[str] = None


@dataclass(frozen=True)
class Fixture:
    fixture_id: Optional[int]
    match_number: Optional[int]
    kickoff_utc: str
    home_team: Optional[str]
    away_team: Optional[str]
    stage: str
    group_name: Optional[str] = None
    venue_name: Optional[str] = None

