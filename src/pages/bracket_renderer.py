from __future__ import annotations

from datetime import datetime
import html
import re

import pandas as pd

from src.pages.bracket_data import (
    MATCHES,
    QF_LEFT,
    QF_RIGHT,
    R16_LEFT,
    R16_RIGHT,
    R32_LEFT,
    R32_RIGHT,
    SF_LEFT,
    SF_RIGHT,
    SLOT_NOTES,
)
from src.pages.rankings import FLAG_CODES


CARD_W = 276
CARD_H = 142
FINAL_W = 350
FINAL_H = 180
THIRD_W = 350
THIRD_H = 126
CANVAS_W = 2790
CANVAS_H = 1420

COL_X = {
    "r32_left": 46,
    "r16_left": 336,
    "qf_left": 626,
    "sf_left": 916,
    "final": 1220,
    "sf_right": 1598,
    "qf_right": 1888,
    "r16_right": 2178,
    "r32_right": 2468,
}

R32_Y = [124, 274, 424, 574, 724, 874, 1024, 1174]
R16_Y = [199, 499, 799, 1099]
QF_Y = [349, 949]
SF_Y = [649]
FINAL_Y = 630
THIRD_PLACE_Y = 1250


def render_live_bracket_html(fixtures: pd.DataFrame, flag_lookup: dict[str, str], background_uri: str | None = None) -> str:
    match_models = _build_match_models(fixtures, flag_lookup)
    cards = []
    cards.extend(_cards_for(R32_LEFT, COL_X["r32_left"], R32_Y, match_models, "left"))
    cards.extend(_cards_for(R16_LEFT, COL_X["r16_left"], R16_Y, match_models, "left"))
    cards.extend(_cards_for(QF_LEFT, COL_X["qf_left"], QF_Y, match_models, "left"))
    cards.extend(_cards_for(SF_LEFT, COL_X["sf_left"], SF_Y, match_models, "left"))
    cards.append(_card_html(104, COL_X["final"], FINAL_Y, match_models[104], "final", final=True))
    cards.append(_card_html(103, COL_X["final"], THIRD_PLACE_Y, match_models[103], "third", third=True))
    cards.extend(_cards_for(SF_RIGHT, COL_X["sf_right"], SF_Y, match_models, "right"))
    cards.extend(_cards_for(QF_RIGHT, COL_X["qf_right"], QF_Y, match_models, "right"))
    cards.extend(_cards_for(R16_RIGHT, COL_X["r16_right"], R16_Y, match_models, "right"))
    cards.extend(_cards_for(R32_RIGHT, COL_X["r32_right"], R32_Y, match_models, "right"))

    return f"""
    <!doctype html>
    <html>
      <head>
        <meta charset="utf-8">
        <style>{_styles()}</style>
      </head>
      <body>
        <main class="bracket-shell">
          <section class="bracket-viewport">
            <div class="zoom-controls">
              <button id="zoom-fit" type="button">Fit</button>
              <button id="zoom-out" type="button">-</button>
              <span id="zoom-readout">100%</span>
              <button id="zoom-in" type="button">+</button>
            </div>
            <div id="bracket-zoom-space" class="bracket-zoom-space">
              <div id="bracket-canvas" class="bracket-canvas">
                {_background_layer(background_uri)}
                {_connector_svg()}
                {_column_headers()}
                {''.join(cards)}
                {_final_glow()}
              </div>
            </div>
          </section>
        </main>
        <script>
          const viewport = document.querySelector(".bracket-viewport");
          const space = document.getElementById("bracket-zoom-space");
          const canvas = document.getElementById("bracket-canvas");
          const readout = document.getElementById("zoom-readout");
          const baseWidth = {CANVAS_W};
          const baseHeight = {CANVAS_H};
          let zoom = 1;

          function fitZoom() {{
            const widthFit = (viewport.clientWidth - 36) / baseWidth;
            const heightFit = (viewport.clientHeight - 44) / baseHeight;
            return Math.min(widthFit, heightFit, 1);
          }}

          function setZoom(nextZoom, center = true) {{
            zoom = Math.max(0.28, Math.min(1.6, nextZoom));
            canvas.style.transform = `scale(${{zoom}})`;
            space.style.width = `${{baseWidth * zoom}}px`;
            space.style.height = `${{baseHeight * zoom}}px`;
            readout.textContent = `${{Math.round(zoom * 100)}}%`;
            if (center) {{
              const horizontalOverflow = Math.max(0, space.clientWidth - viewport.clientWidth);
              const verticalOverflow = Math.max(0, space.clientHeight - viewport.clientHeight);
              viewport.scrollLeft = horizontalOverflow / 2;
              viewport.scrollTop = verticalOverflow / 2;
            }}
          }}

          document.getElementById("zoom-fit").addEventListener("click", () => setZoom(fitZoom()));
          document.getElementById("zoom-out").addEventListener("click", () => setZoom(zoom - 0.12, false));
          document.getElementById("zoom-in").addEventListener("click", () => setZoom(zoom + 0.12, false));
          window.addEventListener("resize", () => setZoom(fitZoom()));
          window.requestAnimationFrame(() => setZoom(fitZoom()));
        </script>
      </body>
    </html>
    """


def _background_layer(background_uri: str | None) -> str:
    return '<div class="bracket-bg"></div>'


def _build_match_models(fixtures: pd.DataFrame, flag_lookup: dict[str, str]) -> dict[int, dict]:
    fixture_map = _fixture_map(fixtures)
    winners: dict[int, dict] = {}
    losers: dict[int, dict] = {}
    models: dict[int, dict] = {}

    for match_number in sorted(MATCHES):
        match = MATCHES[match_number]
        row = fixture_map.get(match_number)
        participants = []
        for index, slot in enumerate(match["slots"]):
            raw_value = _participant_from_row(row, index)
            if _is_real_team(raw_value):
                display = str(raw_value).strip()
            else:
                display = _resolve_slot(slot, winners, losers)
            participants.append(_participant_model(display, flag_lookup))

        scores = _score_pair(row)
        winner_index = _winner_index(row, scores)
        if winner_index is not None and participants[winner_index]["name"]:
            winners[match_number] = participants[winner_index]
            losers[match_number] = participants[1 - winner_index]

        models[match_number] = {
            "number": match_number,
            "round": match["round"],
            "date": _display_date(match["date"]),
            "venue": match["venue"],
            "participants": participants,
            "scores": scores,
            "winner_index": winner_index,
        }
    return models


def _fixture_map(fixtures: pd.DataFrame) -> dict[int, pd.Series]:
    if fixtures.empty:
        return {}
    rows = {}
    for _, row in fixtures.iterrows():
        number = row.get("official_match_number", row.get("match_number"))
        if pd.isna(number):
            continue
        rows[int(float(number))] = row
    return rows


def _participant_from_row(row: pd.Series | None, index: int):
    if row is None:
        return None
    return row.get("home_team") if index == 0 else row.get("away_team")


def _resolve_slot(slot: str, winners: dict[int, dict], losers: dict[int, dict]) -> str:
    if slot.startswith("W") and slot[1:].isdigit():
        return winners.get(int(slot[1:]), {}).get("name") or f"Winner M{slot[1:]}"
    if slot.startswith("L") and slot[1:].isdigit():
        return losers.get(int(slot[1:]), {}).get("name") or f"Loser M{slot[1:]}"
    return slot


def _participant_model(name: str, flag_lookup: dict[str, str]) -> dict:
    clean_name = str(name or "TBD").strip()
    placeholder = not _is_real_team(clean_name)
    return {
        "name": clean_name,
        "placeholder": placeholder,
        "note": SLOT_NOTES.get(clean_name, ""),
        "flag_code": "" if placeholder else _flag_code(clean_name, flag_lookup),
    }


def _is_real_team(value) -> bool:
    if pd.isna(value):
        return False
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "null", "tbd"}:
        return False
    if text in SLOT_NOTES:
        return False
    if re.match(r"^[WL]\d+$", text):
        return False
    if re.match(r"^(Winner|Loser)\s+M?\d+$", text, flags=re.IGNORECASE):
        return False
    if re.match(r"^[123][A-L]+$", text):
        return False
    return True


def _flag_code(team: str, flag_lookup: dict[str, str]) -> str:
    return str(flag_lookup.get(team) or FLAG_CODES.get(team) or "").strip().lower()


def _score_pair(row: pd.Series | None) -> tuple[int | None, int | None]:
    if row is None:
        return (None, None)
    home = row.get("home_score")
    away = row.get("away_score")
    if pd.isna(home) or pd.isna(away):
        return (None, None)
    return (int(home), int(away))


def _winner_index(row: pd.Series | None, scores: tuple[int | None, int | None]) -> int | None:
    home_score, away_score = scores
    winner = str(row.get("winner") if row is not None else "").upper()
    if home_score is not None and away_score is not None:
        if home_score > away_score:
            return 0
        if away_score > home_score:
            return 1
    if "HOME" in winner:
        return 0
    if "AWAY" in winner:
        return 1
    return None


def _cards_for(match_numbers: list[int], x: int, ys: list[int], models: dict[int, dict], side: str) -> list[str]:
    return [_card_html(number, x, y, models[number], side) for number, y in zip(match_numbers, ys)]


def _card_html(match_number: int, x: int, y: int, model: dict, side: str, final: bool = False, third: bool = False) -> str:
    size_class = " final-card" if final else " third-card" if third else ""
    style = f"left:{x}px;top:{y}px;"
    if final:
        style += f"width:{FINAL_W}px;"
    elif third:
        style += f"width:{THIRD_W}px;"
    badge = "Final" if final else "Third Place" if third else _round_badge(model["round"])
    rows = "".join(
        _team_row(participant, model["scores"][idx], model["winner_index"] == idx, model["winner_index"] is not None)
        for idx, participant in enumerate(model["participants"])
    )
    return (
        f'<article class="bracket-card {side}{size_class}" style="{style}">'
        '<div class="match-head">'
        f'<span>M{match_number}</span>'
        f'<strong>{html.escape(badge)}</strong>'
        '</div>'
        f'<div class="match-meta">{html.escape(model["date"])} | {html.escape(model["venue"])}</div>'
        f'<div class="team-stack">{rows}</div>'
        '</article>'
    )


def _team_row(participant: dict, score: int | None, winner: bool, has_winner: bool) -> str:
    classes = ["team-row"]
    if participant["placeholder"]:
        classes.append("placeholder")
    if winner:
        classes.append("winner")
    elif has_winner:
        classes.append("loser")
    score_text = "" if score is None else str(score)
    note = f'<small>{html.escape(participant["note"])}</small>' if participant["note"] else ""
    return (
        f'<div class="{" ".join(classes)}">'
        f'{_emblem(participant)}'
        f'<div class="team-copy"><span>{html.escape(participant["name"])}</span>{note}</div>'
        f'<strong class="team-score">{html.escape(score_text)}</strong>'
        '</div>'
    )


def _emblem(participant: dict) -> str:
    name = participant["name"]
    if participant["placeholder"]:
        return f'<div class="slot-emblem">{html.escape(_slot_abbrev(name))}</div>'
    code = participant["flag_code"]
    initials = "".join(part[0] for part in name.replace("-", " ").split()[:2]).upper() or "?"
    if not code:
        return f'<div class="team-flag flag-fallback">{html.escape(initials)}</div>'
    return (
        f'<img class="team-flag" src="https://flagcdn.com/w80/{html.escape(code)}.png" alt="{html.escape(name)} flag" '
        f'onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'grid\';">'
        f'<div class="team-flag flag-fallback hidden">{html.escape(initials)}</div>'
    )


def _slot_abbrev(value: str) -> str:
    text = str(value)
    if text.startswith("Winner M"):
        return "W" + text.replace("Winner M", "")
    if text.startswith("Loser M"):
        return "L" + text.replace("Loser M", "")
    return text[:6]


def _round_badge(value: str) -> str:
    text = str(value or "").strip().lower()
    if "round of 32" in text:
        return "R32"
    if "round of 16" in text:
        return "R16"
    if "quarter" in text:
        return "QF"
    if "semi" in text:
        return "SF"
    if "third" in text:
        return "3rd"
    if "final" in text:
        return "Final"
    return str(value or "")


def _connector_svg() -> str:
    paths = []
    paths.extend(_pair_connectors_left(COL_X["r32_left"] + CARD_W, COL_X["r16_left"], R32_Y, R16_Y, "left-blue"))
    paths.extend(_pair_connectors_left(COL_X["r16_left"] + CARD_W, COL_X["qf_left"], R16_Y, QF_Y, "left-blue"))
    paths.extend(_pair_connectors_left(COL_X["qf_left"] + CARD_W, COL_X["sf_left"], QF_Y, SF_Y, "gold"))
    paths.extend(_pair_connectors_right(COL_X["r32_right"], COL_X["r16_right"], R32_Y, R16_Y, "right-red"))
    paths.extend(_pair_connectors_right(COL_X["r16_right"], COL_X["qf_right"], R16_Y, QF_Y, "right-red"))
    paths.extend(_pair_connectors_right(COL_X["qf_right"], COL_X["sf_right"], QF_Y, SF_Y, "gold"))
    paths.append(_line(COL_X["sf_left"] + CARD_W, _center_y(SF_Y[0]), COL_X["final"], FINAL_Y + FINAL_H / 2, "gold strong"))
    paths.append(_line(COL_X["final"] + FINAL_W, FINAL_Y + FINAL_H / 2, COL_X["sf_right"], _center_y(SF_Y[0]), "gold strong"))
    return f'<svg class="connector-layer" viewBox="0 0 {CANVAS_W} {CANVAS_H}" aria-hidden="true">{"".join(paths)}</svg>'


def _pair_connectors_left(x_from: int, x_to: int, outer_ys: list[int], inner_ys: list[int], class_name: str) -> list[str]:
    paths = []
    mid = x_from + ((x_to - x_from) / 2)
    for index, inner_y in enumerate(inner_ys):
        for outer_y in (outer_ys[index * 2], outer_ys[(index * 2) + 1]):
            paths.append(_path(f"M{x_from},{_center_y(outer_y)} H{mid} V{_center_y(inner_y)} H{x_to}", class_name))
    return paths


def _pair_connectors_right(x_from: int, x_to: int, outer_ys: list[int], inner_ys: list[int], class_name: str) -> list[str]:
    paths = []
    inner_edge = x_to + CARD_W
    mid = inner_edge + ((x_from - inner_edge) / 2)
    for index, inner_y in enumerate(inner_ys):
        for outer_y in (outer_ys[index * 2], outer_ys[(index * 2) + 1]):
            paths.append(_path(f"M{x_from},{_center_y(outer_y)} H{mid} V{_center_y(inner_y)} H{inner_edge}", class_name))
    return paths


def _line(x1: float, y1: float, x2: float, y2: float, class_name: str) -> str:
    mid = x1 + ((x2 - x1) / 2)
    return _path(f"M{x1},{y1} H{mid} V{y2} H{x2}", class_name)


def _path(d: str, class_name: str) -> str:
    return f'<path class="connector {class_name}" d="{d}" fill="none"/>'


def _center_y(y: int) -> float:
    return y + (CARD_H / 2)


def _column_headers() -> str:
    headers = [
        (COL_X["r32_left"], "Round of 32"), (COL_X["r16_left"], "Round of 16"),
        (COL_X["qf_left"], "Quarterfinals"), (COL_X["sf_left"], "Semifinals"),
        (COL_X["final"], "Final"),
        (COL_X["sf_right"], "Semifinals"), (COL_X["qf_right"], "Quarterfinals"),
        (COL_X["r16_right"], "Round of 16"), (COL_X["r32_right"], "Round of 32"),
    ]
    return "".join(
        f'<div class="round-header" style="left:{x}px;top:80px;width:{FINAL_W if label == "Final" else CARD_W}px;">{html.escape(label)}</div>'
        for x, label in headers
    )


def _final_glow() -> str:
    return ""


def _display_date(value: str) -> str:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return value
    return f"{parsed.strftime('%b')} {parsed.day}"


def _styles() -> str:
    return f"""
    * {{ box-sizing: border-box; }}
    html, body {{
        margin: 0;
        background: #050505;
        color: #FFFFFF;
        font-family: "Trebuchet MS", "Segoe UI", Arial, sans-serif;
    }}
    .bracket-shell {{
        min-height: 100vh;
        overflow: hidden;
        padding: 12px;
        position: relative;
        background:
            radial-gradient(circle at 50% 8%, rgba(214,168,58,.18), transparent 26%),
            radial-gradient(circle at 18% 40%, rgba(35,215,215,.09), transparent 22%),
            radial-gradient(circle at 82% 42%, rgba(255,59,31,.10), transparent 22%),
            linear-gradient(135deg, #030712, #0B1020 48%, #050505);
    }}
    .bracket-bg {{
        background:
            radial-gradient(circle at 50% 42%, rgba(214,168,58,.10), transparent 22%),
            radial-gradient(circle at 28% 36%, rgba(35,215,215,.08), transparent 24%),
            radial-gradient(circle at 72% 38%, rgba(255,59,31,.08), transparent 24%);
        inset: 0;
        position: absolute;
        z-index: 0;
    }}
    .bracket-viewport {{
        border: 1px solid rgba(214,168,58,.34);
        border-radius: 8px;
        height: calc(100vh - 24px);
        min-height: 780px;
        overflow: auto;
        background:
            linear-gradient(rgba(255,255,255,.025) 1px, transparent 1px),
            linear-gradient(90deg, rgba(255,255,255,.025) 1px, transparent 1px),
            linear-gradient(180deg, rgba(5,5,5,.42), rgba(5,5,5,.64));
        background-size: 92px 92px;
        box-shadow: inset 0 0 90px rgba(0,0,0,.54), 0 18px 40px rgba(0,0,0,.34);
        position: relative;
        z-index: 2;
    }}
    .zoom-controls {{
        align-items: center;
        border: 1px solid rgba(214,168,58,.28);
        border-radius: 999px;
        background: rgba(5,5,5,.84);
        box-shadow: 0 12px 28px rgba(0,0,0,.34);
        display: flex;
        gap: 6px;
        padding: 6px;
        position: sticky;
        top: 12px;
        left: 12px;
        width: max-content;
        z-index: 20;
    }}
    .zoom-controls button,
    .zoom-controls span {{
        border: 1px solid rgba(214,168,58,.30);
        border-radius: 999px;
        background: rgba(11,16,32,.88);
        color: #D6A83A;
        font-size: 12px;
        font-weight: 950;
        min-width: 34px;
        padding: 7px 10px;
    }}
    .zoom-controls button {{
        cursor: pointer;
    }}
    .zoom-controls button:hover {{
        background: rgba(214,168,58,.18);
    }}
    .bracket-zoom-space {{
        height: {CANVAS_H}px;
        margin-left: auto;
        margin-right: auto;
        min-height: 1px;
        position: relative;
        width: {CANVAS_W}px;
    }}
    .bracket-canvas {{
        height: {CANVAS_H}px;
        min-width: {CANVAS_W}px;
        position: relative;
        transform-origin: top left;
        width: {CANVAS_W}px;
    }}
    .connector-layer {{
        height: {CANVAS_H}px;
        inset: 0;
        pointer-events: none;
        position: absolute;
        width: {CANVAS_W}px;
        z-index: 1;
    }}
    .connector {{
        stroke-width: 2.5;
        stroke-linecap: round;
        stroke-linejoin: round;
        opacity: .44;
        filter: drop-shadow(0 0 8px rgba(214,168,58,.10));
    }}
    .connector.left-blue {{ stroke: #5CE8F0; }}
    .connector.right-red {{ stroke: #FF6652; }}
    .connector.gold {{ stroke: #D6A83A; }}
    .connector.strong {{ stroke-width: 4.5; opacity: .78; }}
    .round-header {{
        border: 1px solid rgba(214,168,58,.28);
        border-radius: 8px;
        background:
            linear-gradient(180deg, rgba(214,168,58,.16), rgba(5,5,5,.72)),
            rgba(5,5,5,.78);
        box-shadow: 0 12px 26px rgba(0,0,0,.28);
        color: #D6A83A;
        font-size: 15px;
        font-weight: 950;
        letter-spacing: .02em;
        padding: 10px 10px;
        position: absolute;
        text-align: center;
        text-shadow: 0 2px 10px rgba(0,0,0,.72);
        text-transform: uppercase;
        z-index: 3;
    }}
    .bracket-card {{
        border: 1px solid rgba(255,255,255,.20);
        border-radius: 8px;
        background:
            linear-gradient(180deg, rgba(8,13,25,.94), rgba(3,5,12,.91)),
            radial-gradient(circle at 100% 0%, rgba(36,88,255,.24), transparent 36%);
        box-shadow: 0 18px 36px rgba(0,0,0,.44), inset 0 1px 0 rgba(255,255,255,.06);
        min-height: {CARD_H}px;
        overflow: hidden;
        padding: 11px;
        position: absolute;
        width: {CARD_W}px;
        z-index: 4;
    }}
    .bracket-card::before {{
        background: linear-gradient(90deg, rgba(35,215,215,.92), rgba(214,168,58,.42));
        border-radius: 999px;
        content: "";
        height: 3px;
        left: 12px;
        position: absolute;
        right: 12px;
        top: 0;
    }}
    .bracket-card.right {{
        background:
            linear-gradient(180deg, rgba(8,13,25,.94), rgba(3,5,12,.91)),
            radial-gradient(circle at 0% 0%, rgba(255,59,31,.22), transparent 34%);
    }}
    .bracket-card.right::before {{
        background: linear-gradient(90deg, rgba(214,168,58,.42), rgba(255,59,31,.92));
    }}
    .bracket-card.final-card {{
        border-color: rgba(214,168,58,.74);
        background:
            linear-gradient(180deg, rgba(39,28,9,.96), rgba(5,5,5,.94)),
            radial-gradient(circle at 50% 0%, rgba(214,168,58,.30), transparent 52%);
        box-shadow: 0 24px 58px rgba(0,0,0,.54), 0 0 44px rgba(214,168,58,.14), inset 0 1px 0 rgba(255,255,255,.08);
        min-height: {FINAL_H}px;
        padding: 14px;
        z-index: 6;
    }}
    .bracket-card.final-card::before {{
        background: linear-gradient(90deg, transparent, #D6A83A, transparent);
        height: 4px;
    }}
    .bracket-card.third-card {{
        border-color: rgba(255,255,255,.20);
        background:
            linear-gradient(180deg, rgba(8,13,25,.88), rgba(5,5,5,.86)),
            radial-gradient(circle at 50% 0%, rgba(214,168,58,.12), transparent 44%);
        min-height: {THIRD_H}px;
        padding: 11px;
    }}
    .match-head {{
        align-items: center;
        display: flex;
        justify-content: space-between;
        gap: 10px;
    }}
    .match-head span {{
        color: #D6A83A;
        font-size: 13px;
        font-weight: 950;
    }}
    .match-head strong {{
        border: 1px solid rgba(214,168,58,.28);
        border-radius: 999px;
        color: #F8FAFC;
        font-size: 10px;
        font-weight: 950;
        letter-spacing: .04em;
        line-height: 1;
        padding: 4px 7px;
        text-transform: uppercase;
    }}
    .match-meta {{
        color: #CBD5E1;
        font-size: 11px;
        font-weight: 800;
        margin: 5px 0 8px;
        min-height: 14px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }}
    .team-stack {{
        display: grid;
        gap: 6px;
    }}
    .team-row {{
        align-items: center;
        border: 1px solid rgba(255,255,255,.15);
        border-radius: 7px;
        background: rgba(255,255,255,.065);
        display: grid;
        grid-template-columns: 38px 1fr 32px;
        gap: 9px;
        min-height: 40px;
        padding: 5px 7px;
    }}
    .team-row.winner {{
        border-color: rgba(214,168,58,.72);
        background: rgba(214,168,58,.17);
        box-shadow: inset 0 0 0 1px rgba(214,168,58,.10);
    }}
    .team-row.loser {{
        opacity: .58;
    }}
    .team-row.placeholder {{
        border-color: rgba(214,168,58,.20);
        background: rgba(5,5,5,.42);
    }}
    .team-flag, .slot-emblem {{
        align-items: center;
        aspect-ratio: 3 / 2;
        border-radius: 4px;
        display: grid;
        font-size: 10px;
        font-weight: 950;
        height: 25px;
        justify-content: center;
        object-fit: cover;
        object-position: center;
        width: 38px;
    }}
    .team-flag:not(.flag-fallback) {{
        border: 1px solid rgba(255,255,255,.52);
        display: block;
    }}
    .slot-emblem, .flag-fallback {{
        border: 1px solid rgba(214,168,58,.42);
        background: linear-gradient(135deg, rgba(214,168,58,.34), rgba(36,88,255,.18));
        color: #FFFFFF;
    }}
    .hidden {{ display: none; }}
    .team-copy {{
        min-width: 0;
    }}
    .team-copy span {{
        color: #FFFFFF;
        display: block;
        font-size: 14px;
        font-weight: 950;
        line-height: 1;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }}
    .team-copy small {{
        color: #D6A83A;
        display: block;
        font-size: 9.5px;
        font-weight: 850;
        line-height: 1.05;
        margin-top: 2px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }}
    .team-score {{
        color: #FFFFFF;
        font-size: 22px;
        font-weight: 950;
        text-align: right;
    }}
    .final-card .match-head span {{
        font-size: 15px;
    }}
    .final-card .match-head strong {{
        background: rgba(214,168,58,.18);
        color: #D6A83A;
        font-size: 11px;
    }}
    .final-card .match-meta {{
        font-size: 12px;
        margin-bottom: 10px;
    }}
    .final-card .team-row {{
        grid-template-columns: 44px 1fr 38px;
        min-height: 46px;
    }}
    .final-card .team-flag,
    .final-card .slot-emblem {{
        height: 29px;
        width: 44px;
    }}
    .final-card .team-copy span {{
        font-size: 15px;
    }}
    .final-card .team-score {{
        font-size: 25px;
    }}
    """
