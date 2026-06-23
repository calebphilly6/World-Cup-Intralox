"""Official FIFA group-stage ranking order, shared by the Groups view and the
Intralox scoring so they always agree on who finished 1st/2nd/3rd.

FIFA ranks group teams by, in order: points, goal difference, goals for. Teams
still equal after that are separated by a head-to-head mini-table among only the
tied teams (points, then goal difference, then goals scored in the matches they
played against each other). Anything still tied falls back to the caller's base
order (we don't have fair-play/drawing-of-lots data), which keeps results
deterministic.
"""

from __future__ import annotations

from typing import Hashable, Iterable, Mapping, Sequence


def _overall(stats: Mapping[Hashable, Mapping[str, int]], key: Hashable) -> tuple[int, int, int]:
    stat = stats.get(key, {})
    return (
        int(stat.get("points", 0) or 0),
        int(stat.get("goal_difference", 0) or 0),
        int(stat.get("goals_for", 0) or 0),
    )


def rank_group(
    keys: Iterable[Hashable],
    stats: Mapping[Hashable, Mapping[str, int]],
    matches: Sequence[tuple[Hashable, Hashable, int, int]],
) -> list[Hashable]:
    """Return ``keys`` ordered best-to-worst by the official group ranking.

    ``keys`` should already be in a deterministic base order (used as the final
    tiebreak via stable sorting). ``stats[key]`` carries overall ``points``,
    ``goal_difference`` and ``goals_for``. ``matches`` is the completed group
    matches as ``(home_key, away_key, home_score, away_score)``.
    """
    ordered = sorted(keys, key=lambda key: _overall(stats, key), reverse=True)

    result: list[Hashable] = []
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and _overall(stats, ordered[end]) == _overall(stats, ordered[index]):
            end += 1
        cluster = ordered[index:end]
        if len(cluster) > 1:
            cluster = _head_to_head_order(cluster, matches)
        result.extend(cluster)
        index = end
    return result


def _head_to_head_order(
    cluster: Sequence[Hashable],
    matches: Sequence[tuple[Hashable, Hashable, int, int]],
) -> list[Hashable]:
    members = set(cluster)
    mini = {key: {"points": 0, "gd": 0, "gf": 0} for key in cluster}
    for home, away, home_score, away_score in matches:
        if home not in members or away not in members:
            continue
        if home_score is None or away_score is None:
            continue
        mini[home]["gf"] += home_score
        mini[away]["gf"] += away_score
        mini[home]["gd"] += home_score - away_score
        mini[away]["gd"] += away_score - home_score
        if home_score > away_score:
            mini[home]["points"] += 3
        elif away_score > home_score:
            mini[away]["points"] += 3
        else:
            mini[home]["points"] += 1
            mini[away]["points"] += 1
    # Stable sort keeps the caller's base order for teams still fully tied.
    return sorted(
        cluster,
        key=lambda key: (mini[key]["points"], mini[key]["gd"], mini[key]["gf"]),
        reverse=True,
    )
