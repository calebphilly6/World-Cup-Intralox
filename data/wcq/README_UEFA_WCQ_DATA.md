# UEFA WCQ Data Pack — 2026 FIFA World Cup Qualification

This folder contains a Codex-ready UEFA data pack for the `WCQ` / `World Cup Qualification` feature.

## What this pack covers

UEFA had 16 spots at the 2026 FIFA World Cup.

Format:
- First Round: 12 groups total.
  - Groups A-F had 4 teams.
  - Groups G-L had 5 teams.
  - Each group winner qualified directly for the World Cup.
  - Each group runner-up advanced to the UEFA play-offs.
  - Four 2024-25 UEFA Nations League group winners outside the top two of their WCQ group also advanced to the play-offs.
- Second Round: 4 single-leg play-off paths.
  - Each path had two semi-finals and one final.
  - The four path winners qualified for the World Cup.

## Qualified UEFA teams

Direct group winners:
- Germany — Group A
- Switzerland — Group B
- Scotland — Group C
- France — Group D
- Spain — Group E
- Portugal — Group F
- Netherlands — Group G
- Austria — Group H
- Norway — Group I
- Belgium — Group J
- England — Group K
- Croatia — Group L

UEFA play-off winners:
- Bosnia and Herzegovina — Path A
- Sweden — Path B
- Turkey — Path C
- Czech Republic — Path D

## Files included

- `wcq_confederations.csv`
- `wcq_uefa_teams.csv`
- `wcq_rounds.csv`
- `wcq_groups.csv`
- `wcq_group_standings.csv`
- `wcq_matches.csv`
- `wcq_brackets.csv`
- `wcq_playoff_ties.csv`
- `wcq_eliminated_by_round.csv`
- `wcq_qualified_teams.csv`
- `wcq_sources.csv`
- `uefa_style.json`
- `uefa_wcq_data.json`
- `codex_import_prompt.txt`

## Notes for Codex

1. Treat `wcq_group_standings.csv` as the primary data source for the UEFA group-stage UI.
2. Treat `wcq_brackets.csv`, `wcq_playoff_ties.csv`, and UEFA_R2 rows in `wcq_matches.csv` as the primary data source for the UEFA play-off bracket.
3. The group-stage rows in `wcq_matches.csv` are generated from the standings matrix. They include scores but not exact match dates or venues.
4. FIFA rankings use the 28 November 2024 ranking snapshot used for the UEFA qualifying draw. Play-off seeding used a later November 2025 snapshot; if desired, add a separate playoff ranking field later.
5. Russia is included as a suspended / did-not-enter team because UEFA has 55 member associations but only 54 valid entries for the 2026 qualifying competition.
6. Do not crash if fields like exact dates, venues, or referee details are blank.

## Recommended UI behavior

- Load the UEFA tab with a hero section using `uefa_style.json`.
- Show First Round and Second Round as nested tabs.
- In First Round, show Groups A-L with standings tables/cards.
- Highlight:
  - `qualified` as a strong gold highlight.
  - `playoff` as blue/amber advancement highlight.
  - `eliminated` as muted slate/gray.
  - `suspended` as neutral gray.
- In Second Round, render four bracket paths: A, B, C, D.
- At the bottom of each round, list teams eliminated in that round.
- In the UEFA Qualified tab, show all 16 UEFA qualifiers grouped by qualification method.

## Source strategy

The pack uses official UEFA/FIFA sources where possible and a consolidated Wikipedia mirror for table data. All source references are listed in `wcq_sources.csv`.
