"""Fetch and parse FIFA's third-place allocation table (Annexe C, 495 rows).

Sources the official Round-of-32 best-third-placed allocation from Wikipedia's
"2026 FIFA World Cup knockout stage" article and writes a deterministic CSV
reference file. Re-run if the source changes; the parse is verified by row count
(495) and structural assertions, so a malformed fetch fails loudly rather than
producing a silently-wrong bracket.

Output: data/reference/third_place_allocation.csv with columns:
    qualifying_groups : the 8 group letters whose thirds advance, sorted (e.g. "ABCDEFGH")
    one per group-winner slot: m74,m77,m79,m80,m81,m82,m85,m87 -> the 3rd-place
    group letter assigned to that match.
"""

from __future__ import annotations

import ssl
import sys
import urllib.request
from pathlib import Path

import pandas as pd

URL = "https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_knockout_stage"

# Each allocation column is keyed by the group winner; map that to our match number.
WINNER_TO_MATCH = {
    "1A": 79, "1B": 85, "1D": 81, "1E": 74,
    "1G": 82, "1I": 77, "1K": 87, "1L": 80,
}

OUT_PATH = Path(__file__).resolve().parents[1] / "data" / "reference" / "third_place_allocation.csv"


LOCAL_HTML = Path(__file__).resolve().parents[1] / "data" / "reference" / "_kostage.html"


def _fetch_html(url: str) -> str:
    # Prefer a locally-saved copy (the sandbox blocks outbound TLS; fetch the page
    # once with the browser/PowerShell and drop it at LOCAL_HTML).
    if LOCAL_HTML.exists():
        return LOCAL_HTML.read_text(encoding="utf-8", errors="replace")
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 bracket-tool"})
    return urllib.request.urlopen(req, timeout=60, context=ctx).read().decode("utf-8", "replace")


def _find_allocation_table(tables: list[pd.DataFrame]) -> pd.DataFrame:
    for table in tables:
        if 480 <= table.shape[0] <= 510:
            return table
    raise SystemExit(f"No ~495-row table found (sizes: {[t.shape[0] for t in tables]})")


def main() -> None:
    from io import StringIO

    html = _fetch_html(URL)
    table = _find_allocation_table(pd.read_html(StringIO(html)))
    print(f"Found allocation table: shape={table.shape}")
    if "--write" not in sys.argv:
        print("Columns:", list(table.columns))
        print(table.head(3).to_string())
        print("\nInspect-only run. Re-run with --write to validate and write the CSV.")
        return
    _parse_and_write(table)


# Allowed 3rd-place source groups per match, taken from the repo's own slot
# labels (bracket_data.MATCHES). Every parsed assignment must land inside these
# sets, which cross-checks the parse against our bracket and FIFA's "no same-group
# rematch" rule in one step.
def _allowed_groups_by_match() -> dict[int, set[str]]:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from src.pages.bracket_data import MATCHES

    allowed: dict[int, set[str]] = {}
    for number in WINNER_TO_MATCH.values():
        third_slot = next(s for s in MATCHES[number]["slots"] if s.startswith("3"))
        allowed[number] = set(third_slot[1:])  # "3ABCDF" -> {A,B,C,D,F}
    return allowed


def _winner_columns(table: pd.DataFrame) -> dict[int, str]:
    """Map each match number to the dataframe column that allocates its 3rd-place team."""
    columns: dict[int, str] = {}
    for col in table.columns:
        text = str(col).strip()
        if len(text) >= 2 and text[0] == "1" and text[1].upper() in "ABCDEFGHIJKL":
            winner = "1" + text[1].upper()
            if winner in WINNER_TO_MATCH:
                columns[WINNER_TO_MATCH[winner]] = col
    missing = set(WINNER_TO_MATCH.values()) - set(columns)
    if missing:
        raise SystemExit(f"Could not locate allocation columns for matches {sorted(missing)}")
    return columns


def _group_columns(table: pd.DataFrame) -> list:
    return [c for c in table.columns if str(c).startswith("Third-placed teams advance from groups")]


def _parse_and_write(table: pd.DataFrame) -> None:
    match_numbers = sorted(WINNER_TO_MATCH.values())
    winner_cols = _winner_columns(table)
    group_cols = _group_columns(table)
    allowed = _allowed_groups_by_match()
    if len(group_cols) != 12:
        raise SystemExit(f"Expected 12 group columns, found {len(group_cols)}")

    records: list[dict] = []
    seen_keys: set[str] = set()
    for _, row in table.iterrows():
        qualifying = sorted(
            str(row[c]).strip().upper()
            for c in group_cols
            if pd.notna(row[c]) and str(row[c]).strip()
        )
        qualifying = [g for g in qualifying if g in "ABCDEFGHIJKL"]
        if len(qualifying) != 8:
            raise SystemExit(f"Row has {len(qualifying)} qualifying groups, expected 8: {qualifying}")
        key = "".join(qualifying)

        assignment: dict[int, str] = {}
        for number in match_numbers:
            cell = str(row[winner_cols[number]]).strip().upper()
            group = cell[1:] if cell.startswith("3") else cell
            if group not in allowed[number]:
                raise SystemExit(
                    f"Combination {key}: match {number} assigned 3{group}, "
                    f"not in allowed {sorted(allowed[number])}"
                )
            assignment[number] = group

        assigned_groups = sorted(assignment.values())
        if assigned_groups != qualifying:
            raise SystemExit(
                f"Combination {key}: assigned thirds {assigned_groups} != qualifying {qualifying}"
            )
        if key in seen_keys:
            raise SystemExit(f"Duplicate combination {key}")
        seen_keys.add(key)
        records.append({"qualifying_groups": key, **{f"m{n}": assignment[n] for n in match_numbers}})

    if len(records) != 495:
        raise SystemExit(f"Expected 495 combinations, got {len(records)}")

    out = pd.DataFrame(records).sort_values("qualifying_groups").reset_index(drop=True)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_PATH, index=False)
    print(f"Wrote {len(out)} combinations to {OUT_PATH.relative_to(Path.cwd())}")
    print(out.head(3).to_string(index=False))


if __name__ == "__main__":
    main()
