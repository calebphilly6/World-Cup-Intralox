# CONCACAF WCQ Data Pack — 2026 FIFA World Cup Qualification

Prepared for the Streamlit World Cup Program WCQ tab.

## What this includes

- All 35 FIFA-affiliated CONCACAF teams relevant to 2026 qualification: 32 qualification entrants plus Canada, Mexico, and the United States as automatic hosts.
- Team metadata: FIFA code, flag code, December 2023 FIFA ranking snapshot for qualification seeding, final status, qualification/elimination summary.
- Round definitions: Host qualification, First Round, Second Round, Third Round, Inter-confederation Play-offs.
- First Round two-leg playoff ties.
- Second Round standings for Groups A-F.
- Third Round standings for Groups A-C and runner-up ranking.
- Match matrix rows from group standings. Exact date/venue details can be expanded later from source pages.
- Eliminated teams by round.
- Qualified teams: Canada, Mexico, United States, Panama, Curaçao, Haiti.
- Style JSON for a CONCACAF-themed UI.

## Key qualification results

### Automatic hosts
- Canada
- Mexico
- United States

### Direct qualifiers from CONCACAF qualifying
- Panama — Third Round Group A winner
- Curaçao — Third Round Group B winner
- Haiti — Third Round Group C winner

### Inter-confederation playoff teams
- Suriname — lost 2-1 to Bolivia in playoff semifinal
- Jamaica — beat New Caledonia 1-0 in playoff semifinal, then lost 1-0 after extra time to DR Congo in playoff final

## Suggested install location

Copy these files into:

```
data/wcq/concacaf/
```

Or merge the generic files into your existing `data/wcq/` folder if the app expects all confederations in shared files.

## Important data notes

- FIFA rankings are stored with `rank_snapshot_date`. Most rankings are the December 2023 seeding rankings used for the CONCACAF qualification draw.
- Third-round seed rankings were based on June 2025 rankings, with April 2025 ranking values shown in the source; this pack keeps December 2023 ranks in the main team metadata for consistency and can be expanded with separate rank snapshots later.
- `wcq_matches.csv` includes match score rows reconstructed from standings matrices and key playoff results. Some exact dates are blank where not entered yet. The UI should still render tables, brackets, and team journeys.
- Use `wcq_group_standings.csv` as the primary source for group table UI.
- Use `wcq_playoff_ties.csv` for bracket/tie display.
- Use `wcq_eliminated_by_round.csv` for the eliminated-list cards at the bottom of each round tab.

## File list

- `wcq_confederations.csv`
- `wcq_concacaf_teams.csv`
- `wcq_rounds.csv`
- `wcq_groups.csv`
- `wcq_group_standings.csv`
- `wcq_playoff_ties.csv`
- `wcq_matches.csv`
- `wcq_eliminated_by_round.csv`
- `wcq_qualified_teams.csv`
- `wcq_sources.csv`
- `concacaf_style.json`
- `concacaf_wcq_data.json`
- `codex_import_prompt.txt`

## Sources

Sources are included row-by-row where useful and summarized in `wcq_sources.csv`.
