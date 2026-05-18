# OFC WCQ Data Pack - 2026 FIFA World Cup Qualification

This folder contains Codex-ready CSV/JSON data for the OFC portion of the 2026 FIFA World Cup qualification feature.

## Summary

- Confederation: OFC - Oceania Football Confederation
- Eligible FIFA teams: 11
- Direct World Cup places: 1
- Inter-confederation playoff places: 1
- Direct qualifier: New Zealand
- OFC playoff participant: New Caledonia
- Final OFC result: New Zealand 3-0 New Caledonia, 24 March 2025
- Playoff result: New Caledonia 0-1 Jamaica, 26 March 2026

## Format

1. Round One: Four lowest-ranked teams played a knockout mini-bracket in Samoa.
2. Round Two: Samoa joined seven seeded teams in two groups of four.
3. Third Round: Four-team knockout in New Zealand.
4. Inter-confederation playoff: New Caledonia represented OFC but lost to Jamaica.

## Files

- wcq_confederations.csv
- wcq_ofc_teams.csv
- wcq_rounds.csv
- wcq_groups.csv
- wcq_group_standings.csv
- wcq_matches.csv
- wcq_brackets.csv
- wcq_eliminated_by_round.csv
- wcq_qualified_teams.csv
- wcq_sources.csv
- ofc_style.json
- ofc_wcq_data.json
- codex_import_prompt.txt

## Implementation notes

- `wcq_matches.csv` includes all OFC qualifying matches plus New Caledonia's inter-confederation playoff semifinal.
- `wcq_group_standings.csv` only applies to Round Two because Round One and Round Three were knockout formats.
- `rank_snapshot_date` is set to 2024-07-18 because the seeding/ranking list used the July 2024 FIFA rankings.
- `flag_code` uses ISO-style country/territory codes for emoji flag rendering. Tahiti uses `PF` for French Polynesia.
- New Caledonia is marked `inter_confederation_playoff_loss`, not simply eliminated in the OFC final, because its qualification journey continued after the OFC final.

## Sources

- https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_qualification_(OFC)
- https://www.oceaniafootball.com/fifa-world-cup-2026-oceania-qualifiers/
- https://www.oceaniafootball.com/fifa-world-cup-2026-oceania-qualifiers-round-two/
- https://www.oceaniafootball.com/fifa-world-cup-26-oceania-qualifiers-round-three/
- https://www.oceaniafootball.com/brave-new-caledonia-fall-narrowly-in-historic-fifa-world-cup-play-off/
