"""Update FIFA rankings from a CSV and regenerate the committed snapshots.

Usage:
    python scripts/update_fifa_rankings.py [path/to/rankings.csv]

If no path is given, it reads data/imports/fifa_rankings.csv. The CSV must have at
least: team, ranking_date, rank. Optional: points, previous_rank, source, notes.

This imports the rankings into the local SQLite database (populating both the full
``global_fifa_rankings`` list and the World Cup ``fifa_rankings`` table) and then
re-exports data/snapshots/*.csv so the change can be committed and picked up by the
hosted (read-only) version on its next load.
"""
from __future__ import annotations

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data_loader import import_dataframe, read_import_file
from src.snapshots import SNAPSHOT_DIR, export_core_snapshots

DEFAULT_CSV = PROJECT_ROOT / "data" / "imports" / "fifa_rankings.csv"


def main() -> int:
    csv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CSV
    if not csv_path.exists():
        print(f"CSV not found: {csv_path}")
        return 1

    df = read_import_file(csv_path)
    if df.empty:
        print(f"No rows found in {csv_path}.")
        return 1

    rows, errors = import_dataframe("fifa_rankings", df)
    if errors:
        print("Import failed:")
        for error in errors:
            print(f"  - {error}")
        return 1
    print(f"Imported {rows} ranking rows from {csv_path.name} into the full list; "
          "rows matching a World Cup team also update the tournament rankings table.")

    counts = export_core_snapshots()
    print(f"Regenerated core snapshots in {SNAPSHOT_DIR}:")
    for table in ("global_fifa_rankings", "fifa_rankings"):
        print(f"  {table}: {counts.get(table, 0)} rows")
    print("\nNext: commit data/imports/fifa_rankings.csv and data/snapshots/*.csv, then push.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
