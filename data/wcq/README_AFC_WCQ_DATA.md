# AFC World Cup Qualification Data Pack

Created: 2026-05-16

This folder contains CSV files for the AFC section of a 2026 World Cup Qualification (`WCQ`) tab.
It is designed for a Streamlit app with nested tabs: WCQ > AFC > rounds/groups/qualified.

## Scope

Included:
- All 46 AFC FIFA-affiliated entrants used in the 2026 AFC qualification process.
- July 2023 FIFA rankings used for AFC draw/seedings. These are not current live ranks.
- Round definitions for AFC Round 1 through AFC Round 5 plus Iraq's inter-confederation playoff final.
- Round 2, Round 3, and Round 4 group standings.
- First-round and fifth-round two-leg playoff ties.
- Round 4 individual matches and Iraq's inter-confederation playoff final.
- Eliminated teams by round.
- AFC qualified teams.
- Source tracking columns.

Not fully included:
- Every Round 2 and Round 3 match row/date/venue. The group standings are included and are enough for the UI you described. If you later want match-by-match timelines for every team, add full match rows to `wcq_matches.csv`.

## Important data note

The `fifa_rank` values are from the July 2023 FIFA rankings used for AFC qualification seeding, with `rank_snapshot_date = 2023-07-20`. FIFA ranks change over time, so do not label them as current ranks in the UI.

## Files

- `wcq_confederations.csv`: AFC metadata and qualification summary.
- `wcq_afc_teams.csv`: All 46 AFC teams, flags, FIFA codes, rank snapshot, final status.
- `wcq_rounds.csv`: AFC round metadata.
- `wcq_groups.csv`: Groups for Rounds 2, 3, and 4.
- `wcq_group_standings.csv`: Group standings for Rounds 2, 3, and 4.
- `wcq_playoff_ties.csv`: Two-leg ties for Round 1 and Round 5.
- `wcq_matches.csv`: Round 4 match rows plus Iraq vs Bolivia inter-confederation playoff final.
- `wcq_eliminated_by_round.csv`: Every eliminated AFC team by elimination round.
- `wcq_qualified_teams.csv`: AFC teams that reached the World Cup.
- `wcq_sources.csv`: Source list.
- `afc_style.json`: Suggested AFC UI theme.
- `codex_import_prompt.txt`: Prompt to give Codex with these files.

## Source strategy

Primary data is from FIFA/AFC-referenced standings summarized on the AFC qualification page and Reuters/FIFA for the Iraq-Bolivia inter-confederation playoff final.