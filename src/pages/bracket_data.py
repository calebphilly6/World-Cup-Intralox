"""2026 FIFA World Cup knockout bracket data.

Update this file if FIFA changes the official match schedule, venues, dates, or
slot pairings. The renderer reads this data and should not need schedule edits.
"""

from __future__ import annotations


MATCHES = {
    73: {"round": "Round of 32", "date": "2026-06-28", "venue": "Los Angeles Stadium", "slots": ["2A", "2B"], "next": 90, "loser_next": None},
    74: {"round": "Round of 32", "date": "2026-06-29", "venue": "Boston Stadium", "slots": ["1E", "3ABCDF"], "next": 89, "loser_next": None},
    75: {"round": "Round of 32", "date": "2026-06-29", "venue": "Estadio Monterrey", "slots": ["1F", "2C"], "next": 90, "loser_next": None},
    76: {"round": "Round of 32", "date": "2026-06-29", "venue": "Houston Stadium", "slots": ["1C", "2F"], "next": 91, "loser_next": None},
    77: {"round": "Round of 32", "date": "2026-06-30", "venue": "New York New Jersey Stadium", "slots": ["1I", "3CDFGH"], "next": 89, "loser_next": None},
    78: {"round": "Round of 32", "date": "2026-06-30", "venue": "Dallas Stadium", "slots": ["2E", "2I"], "next": 91, "loser_next": None},
    79: {"round": "Round of 32", "date": "2026-06-30", "venue": "Mexico City Stadium", "slots": ["1A", "3CEFHI"], "next": 92, "loser_next": None},
    80: {"round": "Round of 32", "date": "2026-07-01", "venue": "Atlanta Stadium", "slots": ["1L", "3EHIJK"], "next": 92, "loser_next": None},
    81: {"round": "Round of 32", "date": "2026-07-01", "venue": "San Francisco Bay Area Stadium", "slots": ["1D", "3BEFIJ"], "next": 94, "loser_next": None},
    82: {"round": "Round of 32", "date": "2026-07-01", "venue": "Seattle Stadium", "slots": ["1G", "3AEHIJ"], "next": 94, "loser_next": None},
    83: {"round": "Round of 32", "date": "2026-07-02", "venue": "Toronto Stadium", "slots": ["2K", "2L"], "next": 93, "loser_next": None},
    84: {"round": "Round of 32", "date": "2026-07-02", "venue": "Los Angeles Stadium", "slots": ["1H", "2J"], "next": 93, "loser_next": None},
    85: {"round": "Round of 32", "date": "2026-07-02", "venue": "BC Place Vancouver", "slots": ["1B", "3EFGIJ"], "next": 96, "loser_next": None},
    86: {"round": "Round of 32", "date": "2026-07-03", "venue": "Miami Stadium", "slots": ["1J", "2H"], "next": 95, "loser_next": None},
    87: {"round": "Round of 32", "date": "2026-07-03", "venue": "Kansas City Stadium", "slots": ["1K", "3DEIJL"], "next": 96, "loser_next": None},
    88: {"round": "Round of 32", "date": "2026-07-03", "venue": "Dallas Stadium", "slots": ["2D", "2G"], "next": 95, "loser_next": None},
    89: {"round": "Round of 16", "date": "2026-07-04", "venue": "Philadelphia Stadium", "slots": ["W74", "W77"], "next": 97, "loser_next": None},
    90: {"round": "Round of 16", "date": "2026-07-04", "venue": "Houston Stadium", "slots": ["W73", "W75"], "next": 97, "loser_next": None},
    91: {"round": "Round of 16", "date": "2026-07-05", "venue": "New York New Jersey Stadium", "slots": ["W76", "W78"], "next": 99, "loser_next": None},
    92: {"round": "Round of 16", "date": "2026-07-05", "venue": "Mexico City Stadium", "slots": ["W79", "W80"], "next": 99, "loser_next": None},
    93: {"round": "Round of 16", "date": "2026-07-06", "venue": "Dallas Stadium", "slots": ["W83", "W84"], "next": 98, "loser_next": None},
    94: {"round": "Round of 16", "date": "2026-07-06", "venue": "Seattle Stadium", "slots": ["W81", "W82"], "next": 98, "loser_next": None},
    95: {"round": "Round of 16", "date": "2026-07-07", "venue": "Atlanta Stadium", "slots": ["W86", "W88"], "next": 100, "loser_next": None},
    96: {"round": "Round of 16", "date": "2026-07-07", "venue": "BC Place Vancouver", "slots": ["W85", "W87"], "next": 100, "loser_next": None},
    97: {"round": "Quarter-finals", "date": "2026-07-09", "venue": "Boston Stadium", "slots": ["W89", "W90"], "next": 101, "loser_next": None},
    98: {"round": "Quarter-finals", "date": "2026-07-10", "venue": "Los Angeles Stadium", "slots": ["W93", "W94"], "next": 101, "loser_next": None},
    99: {"round": "Quarter-finals", "date": "2026-07-11", "venue": "Miami Stadium", "slots": ["W91", "W92"], "next": 102, "loser_next": None},
    100: {"round": "Quarter-finals", "date": "2026-07-11", "venue": "Kansas City Stadium", "slots": ["W95", "W96"], "next": 102, "loser_next": None},
    101: {"round": "Semi-final", "date": "2026-07-14", "venue": "Dallas Stadium", "slots": ["W97", "W98"], "next": 104, "loser_next": 103},
    102: {"round": "Semi-final", "date": "2026-07-15", "venue": "Atlanta Stadium", "slots": ["W99", "W100"], "next": 104, "loser_next": 103},
    103: {"round": "Third Place Match", "date": "2026-07-18", "venue": "Miami Stadium", "slots": ["L101", "L102"], "next": None, "loser_next": None},
    104: {"round": "Final", "date": "2026-07-19", "venue": "New York New Jersey Stadium", "slots": ["W101", "W102"], "next": None, "loser_next": None},
}


R32_LEFT = [74, 77, 73, 75, 83, 84, 81, 82]
R16_LEFT = [89, 90, 93, 94]
QF_LEFT = [97, 98]
SF_LEFT = [101]

R32_RIGHT = [76, 78, 79, 80, 86, 88, 85, 87]
R16_RIGHT = [91, 92, 95, 96]
QF_RIGHT = [99, 100]
SF_RIGHT = [102]

ROUND_ORDER = [R32_LEFT, R16_LEFT, QF_LEFT, SF_LEFT, [104], SF_RIGHT, QF_RIGHT, R16_RIGHT, R32_RIGHT]


SLOT_NOTES = {
    "1A": "Group A winner", "1B": "Group B winner", "1C": "Group C winner", "1D": "Group D winner",
    "1E": "Group E winner", "1F": "Group F winner", "1G": "Group G winner", "1H": "Group H winner",
    "1I": "Group I winner", "1J": "Group J winner", "1K": "Group K winner", "1L": "Group L winner",
    "2A": "Group A runner-up", "2B": "Group B runner-up", "2C": "Group C runner-up", "2D": "Group D runner-up",
    "2E": "Group E runner-up", "2F": "Group F runner-up", "2G": "Group G runner-up", "2H": "Group H runner-up",
    "2I": "Group I runner-up", "2J": "Group J runner-up", "2K": "Group K runner-up", "2L": "Group L runner-up",
    "3ABCDF": "3rd from A/B/C/D/F", "3CDFGH": "3rd from C/D/F/G/H", "3CEFHI": "3rd from C/E/F/H/I",
    "3EHIJK": "3rd from E/H/I/J/K", "3BEFIJ": "3rd from B/E/F/I/J", "3AEHIJ": "3rd from A/E/H/I/J",
    "3EFGIJ": "3rd from E/F/G/I/J", "3DEIJL": "3rd from D/E/I/J/L",
}
