from __future__ import annotations

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.snapshots import SNAPSHOT_DIR, export_core_snapshots


def main() -> None:
    counts = export_core_snapshots()
    print(f"Exported core data snapshots to {SNAPSHOT_DIR}")
    for table, count in counts.items():
        print(f"{table}: {count}")


if __name__ == "__main__":
    main()
