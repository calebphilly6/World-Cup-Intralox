from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo


POT_MULTIPLIERS = {
    1: 1.00,
    2: 1.25,
    3: 1.50,
    4: 2.00,
}

# Points for reaching the Round of 32 (qualifying out of the group), awarded to
# every team whose group run put them into the knockout bracket.
QUALIFY_BONUS = 3

KNOCKOUT_POINTS = {
    "won_round_of_32": 5,
    "won_round_of_16": 5,
    "won_quarterfinal": 5,
    "won_semifinal": 5,
    "won_final": 10,
}

APP_TIMEZONE = ZoneInfo("America/Chicago")
SCORE_REFRESH_TIME = time(4, 0)


@dataclass(frozen=True)
class TeamScore:
    team: str
    owner: str
    pot: int
    group_wins: int = 0
    group_draws: int = 0
    group_finish: int | None = None
    advanced: bool = False
    won_round_of_32: bool = False
    won_round_of_16: bool = False
    won_quarterfinal: bool = False
    won_semifinal: bool = False
    won_final: bool = False
    eliminated: bool = False

    @property
    def multiplier(self) -> float:
        return POT_MULTIPLIERS[self.pot]

    @property
    def group_result_points(self) -> int:
        return self.group_wins * 3 + self.group_draws

    @property
    def group_finish_bonus(self) -> int:
        if self.group_finish == 1:
            return 3
        if self.group_finish == 2:
            return 2
        if self.group_finish == 3 and self.advanced:
            return 1
        return 0

    @property
    def qualify_bonus(self) -> int:
        return QUALIFY_BONUS if self.advanced else 0

    @property
    def knockout_points(self) -> dict[str, int]:
        return {
            key: points if getattr(self, key) else 0
            for key, points in KNOCKOUT_POINTS.items()
        }

    @property
    def base_score(self) -> int:
        return (
            self.group_result_points
            + self.group_finish_bonus
            + self.qualify_bonus
            + sum(self.knockout_points.values())
        )

    @property
    def adjusted_score(self) -> float:
        return max(0.0, self.base_score * self.multiplier)

    @property
    def still_alive(self) -> bool:
        return not self.eliminated


def calculate_owner_leaderboard(team_scores: list[TeamScore], previous_ranks: dict[str, int] | None = None) -> list[dict]:
    previous_ranks = previous_ranks or {}
    owners: dict[str, dict] = {}
    for score in team_scores:
        row = owners.setdefault(
            score.owner,
            {
                "person": score.owner,
                "total_score": 0.0,
                "teams_left": 0,
                "teams": [],
                "pot_scores": {},
            },
        )
        row["total_score"] += score.adjusted_score
        row["teams_left"] += 1 if score.still_alive else 0
        row["teams"].append(score)
        row["pot_scores"][score.pot] = score

    leaderboard = sorted(
        owners.values(),
        key=lambda row: (-row["total_score"], -row["teams_left"], row["person"].lower()),
    )
    for index, row in enumerate(leaderboard, start=1):
        row["rank"] = index
        previous = previous_ranks.get(row["person"])
        row["movement"] = movement_label(previous, index)
    return leaderboard


def movement_label(previous_rank: int | None, current_rank: int) -> str:
    if previous_rank is None:
        return "New"
    delta = previous_rank - current_rank
    if delta > 0:
        return f"Up {delta}"
    if delta < 0:
        return f"Down {abs(delta)}"
    return "No change"


def validate_assignments(assignments: list[dict]) -> list[str]:
    errors: list[str] = []
    people: dict[str, list[dict]] = {}
    team_names: set[str] = set()
    duplicate_teams: set[str] = set()
    for row in assignments:
        person = str(row.get("person_name") or "").strip()
        team = str(row.get("team") or "").strip()
        try:
            pot = int(row.get("pot"))
        except (TypeError, ValueError):
            pot = 0
        if not person or not team:
            continue
        if pot not in POT_MULTIPLIERS:
            errors.append(f"{team}: pot must be 1, 2, 3, or 4.")
        if team in team_names:
            duplicate_teams.add(team)
        team_names.add(team)
        people.setdefault(person, []).append({**row, "pot": pot})

    if len(people) != 12:
        errors.append("Exactly 12 competitors are required.")
    for person, rows in sorted(people.items()):
        if len(rows) != 4:
            errors.append(f"{person} must have exactly 4 teams.")
        pots = sorted(row["pot"] for row in rows)
        if pots != [1, 2, 3, 4]:
            errors.append(f"{person} must have one team from each pot.")
    if duplicate_teams:
        errors.append("Each team can only be assigned once: " + ", ".join(sorted(duplicate_teams)))
    return errors


def daily_score_refresh_key(now: datetime | None = None) -> str:
    local_now = now.astimezone(APP_TIMEZONE) if now else datetime.now(APP_TIMEZONE)
    refresh_day = local_now.date()
    if local_now.time() < SCORE_REFRESH_TIME:
        refresh_day -= timedelta(days=1)
    return refresh_day.isoformat()
