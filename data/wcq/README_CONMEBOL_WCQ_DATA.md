# CONMEBOL 2026 World Cup Qualification Data Pack

This pack is intended for the Streamlit WCQ tab described in the project.

## Format Summary
CONMEBOL qualification used one 10-team home-and-away round-robin league table from 7 September 2023 to 9 September 2025. The top six qualified directly for the 2026 FIFA World Cup. The seventh-place team, Bolivia, advanced to the inter-confederation playoff and was eliminated after losing to Iraq in the playoff final.

## Direct CONMEBOL Qualifiers
1. Argentina — winners — qualified 2025-03-25
2. Ecuador — runners-up — qualified 2025-06-10
3. Colombia — third place — qualified 2025-09-04
4. Uruguay — fourth place — qualified date not populated in source table
5. Brazil — fifth place — qualified 2025-06-10
6. Paraguay — sixth place — qualified 2025-09-04

## Playoff Team
- Bolivia finished seventh, beat Suriname 2-1 in the inter-confederation playoff semi-final, then lost 2-1 to Iraq in the final.

## Eliminated Teams
- League table: Venezuela, Peru, Chile
- Inter-confederation playoff: Bolivia

## Files
- wcq_confederations.csv
- wcq_conmebol_teams.csv
- wcq_rounds.csv
- wcq_groups.csv
- wcq_group_standings.csv
- wcq_matches.csv
- wcq_brackets.csv
- wcq_eliminated_by_round.csv
- wcq_qualified_teams.csv
- wcq_sources.csv
- conmebol_style.json
- conmebol_wcq_data.json

## Data Notes
- FIFA ranks are July 2023 draw/entrant snapshot values.
- Ecuador's points reflect the three-point deduction applied before qualifying began.
- wcq_matches.csv includes all 90 league score rows using the final standings score matrix. Exact match dates and venues are not populated for every row, so the app should show score-first summaries and handle blank dates gracefully.
- The playoff matches are included with dates from the playoff path.

## Recommended UI Behavior
- Show CONMEBOL as a league-table-only confederation with a second tab for Bolivia's inter-confederation playoff path.
- Highlight positions 1-6 as World Cup qualified.
- Highlight position 7 as playoff / eliminated in playoff final.
- Highlight positions 8-10 as eliminated.

Sources are listed in wcq_sources.csv.
