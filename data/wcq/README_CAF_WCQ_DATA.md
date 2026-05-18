# CAF 2026 World Cup Qualification Data Pack

Generated: 2026-05-16

This pack is designed for the `WCQ` tab in the 2026 World Cup Streamlit app.
It contains the CAF qualification process in Codex-friendly CSV and JSON files.

## What is included

- All 54 CAF teams that entered the 2026 qualification draw
- FIFA code, flag code, and FIFA ranking snapshot from the 30 June 2023 draw pots
- Final team status: qualified, eliminated, or withdrew
- CAF first-round group standings for Groups A-I
- Runner-up ranking table used to choose the four CAF playoff teams
- CAF second-round playoff bracket and results
- DR Congo's inter-confederation playoff path
- Eliminated teams by round
- CAF qualified teams
- CAF-inspired UI style file
- Source tracking for every major row

## Format summary

CAF qualification format:

1. First round / Group stage
   - Nine groups.
   - Group winners qualified directly for the 2026 FIFA World Cup.
   - Four best runners-up advanced to the CAF second-round playoff.

2. CAF second round / Playoff tournament
   - Gabon, DR Congo, Cameroon, and Nigeria advanced as the four best runners-up.
   - DR Congo won the CAF playoff.

3. Inter-confederation playoff
   - DR Congo defeated Jamaica 1-0 after extra time and qualified for the World Cup.

## Important data notes

- `wcq_matches.csv` includes the group-stage score matrix with blank dates, plus dated playoff matches.
- Exact group-stage match dates/venues are not fully populated in this pack.
- `wcq_group_standings.csv` is complete for UI group tables.
- `wcq_runners_up_ranking.csv` is included because the second-place ranking used only selected results; matches against sixth-place teams were excluded.
- Group E has Eritrea listed as withdrew; Eritrea played zero matches.
- Congo and Equatorial Guinea have special notes because of suspensions/forfeits/cancellations.
- South Africa's group includes the awarded Lesotho result after South Africa fielded an ineligible player.

## Recommended Streamlit display

Inside WCQ > CAF:

- Overview
- First round / Group stage
- Runner-up ranking
- CAF playoff bracket
- Inter-confederation playoff
- Qualified
- Eliminated
- Sources

## Files

- `wcq_confederations.csv`
- `wcq_caf_teams.csv`
- `wcq_rounds.csv`
- `wcq_groups.csv`
- `wcq_group_standings.csv`
- `wcq_runners_up_ranking.csv`
- `wcq_matches.csv`
- `wcq_playoff_ties.csv`
- `wcq_brackets.csv`
- `wcq_eliminated_by_round.csv`
- `wcq_qualified_teams.csv`
- `wcq_sources.csv`
- `caf_style.json`
- `caf_wcq_data.json`
- `codex_import_prompt.txt`

## Main sources

- FIFA CAF standings: https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/qualifiers/caf/standings
- Wikipedia CAF qualification page: https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_qualification_(CAF)
- Sky Sports CAF qualifying table: https://www.skysports.com/fifa-world-cup-african-qualifying-table
- CAF Online: https://www.cafonline.com/
