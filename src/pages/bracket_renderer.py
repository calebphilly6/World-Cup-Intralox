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
from src.fixture_display import flag_code_for_team
from src.pages.rankings import FLAG_CODES


# Single-direction bracket: the tournament flows left -> right. The two halves of
# the official draw concatenate top-to-bottom into one continuous column order,
# so each later-round match sits centered between the two matches that feed it.
R32_ORDER = R32_LEFT + R32_RIGHT      # 16 first-round matches, top -> bottom
R16_ORDER = R16_LEFT + R16_RIGHT      # 8
QF_ORDER = QF_LEFT + QF_RIGHT         # 4
SF_ORDER = SF_LEFT + SF_RIGHT         # 2

CARD_W = 250
CARD_H = 132
FINAL_W = 330
FINAL_H = 168
THIRD_W = 330
THIRD_H = 120

PITCH = 156          # vertical distance between consecutive first-round cards
TOP = 14             # top padding inside the canvas
HEADER_H = 64        # sticky round-label strip height
COL_STEP = 360       # horizontal distance between rounds

COL_X = {
    "r32": 40,
    "r16": 40 + COL_STEP,
    "qf": 40 + COL_STEP * 2,
    "sf": 40 + COL_STEP * 3,
    "final": 40 + COL_STEP * 4,
}

R32_Y = [TOP + i * PITCH for i in range(16)]
R16_Y = [int(TOP + (2 * j + 0.5) * PITCH) for j in range(8)]
QF_Y = [int(TOP + (4 * k + 1.5) * PITCH) for k in range(4)]
SF_Y = [int(TOP + (8 * m + 3.5) * PITCH) for m in range(2)]
FINAL_Y = int(TOP + 7.5 * PITCH + (CARD_H - FINAL_H) / 2)
THIRD_Y = int(FINAL_Y + FINAL_H + 70)

CANVAS_W = COL_X["final"] + FINAL_W + 40
CANVAS_H = R32_Y[-1] + CARD_H + 40


def render_live_bracket_html(fixtures: pd.DataFrame, flag_lookup: dict[str, str], background_uri: str | None = None) -> str:
    match_models = _build_match_models(fixtures, flag_lookup)
    cards = []
    cards.extend(_cards_for(R32_ORDER, COL_X["r32"], R32_Y, match_models))
    cards.extend(_cards_for(R16_ORDER, COL_X["r16"], R16_Y, match_models))
    cards.extend(_cards_for(QF_ORDER, COL_X["qf"], QF_Y, match_models))
    cards.extend(_cards_for(SF_ORDER, COL_X["sf"], SF_Y, match_models))
    cards.append(_card_html(104, COL_X["final"], FINAL_Y, match_models[104], final=True))
    cards.append(_card_html(103, COL_X["final"], THIRD_Y, match_models[103], third=True))

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
            <div class="bracket-header-row">{_column_headers()}</div>
            <div class="bracket-canvas">
              {_connector_svg()}
              {''.join(cards)}
            </div>
          </section>
        </main>
        <script>{_click_script()}</script>
      </body>
    </html>
    """


def _click_script() -> str:
    # Clicking a card opens that fixture's card on the Fixtures tab (even before
    # the teams are filled in). The bracket renders in its own iframe, so we tag a
    # hidden trigger in the parent document and click it; the history bridge's
    # delegated click handler relays the match number to Python.
    return """
    (function () {
      try {
        var doc = window.parent.document;
        document.querySelectorAll('.bracket-card').forEach(function (card) {
          card.style.cursor = 'pointer';
          card.addEventListener('click', function () {
            var match = card.getAttribute('data-match');
            if (!match) { return; }
            var trigger = doc.getElementById('wc2026-fixture-trigger');
            if (!trigger) {
              trigger = doc.createElement('button');
              trigger.id = 'wc2026-fixture-trigger';
              trigger.style.display = 'none';
              doc.body.appendChild(trigger);
            }
            trigger.setAttribute('data-wc-fixture', match);
            trigger.click();
          });
        });
      } catch (error) {
        /* parent not reachable; leave the bracket non-clickable */
      }
    })();
    """


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
            "time": _kickoff_time(row),
            "venue": match["venue"],
            "participants": participants,
            "scores": scores,
            "winner_index": winner_index,
        }
    return models


def _kickoff_time(row: pd.Series | None) -> str:
    if row is None:
        return ""
    parsed = pd.to_datetime(row.get("utc_date"), utc=True, errors="coerce")
    if pd.isna(parsed):
        return ""
    return parsed.tz_convert("America/Chicago").strftime("%I:%M %p").lstrip("0")


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
    # Alias-aware lookup first (handles feed spellings like "United States"),
    # then the static FLAG_CODES table as a final fallback.
    code = flag_code_for_team(team, flag_lookup)
    return (code or str(FLAG_CODES.get(team) or "")).strip().lower()


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


def _cards_for(match_numbers: list[int], x: int, ys: list[int], models: dict[int, dict]) -> list[str]:
    return [_card_html(number, x, y, models[number]) for number, y in zip(match_numbers, ys)]


def _card_html(match_number: int, x: int, y: int, model: dict, final: bool = False, third: bool = False) -> str:
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
    meta_left = model["date"]
    if model.get("time"):
        meta_left += f' · {model["time"]}'
    return (
        f'<article class="bracket-card{size_class}" data-match="{match_number}" style="{style}">'
        '<div class="match-head">'
        f'<span>M{match_number}</span>'
        f'<strong>{html.escape(badge)}</strong>'
        '</div>'
        f'<div class="match-meta">{html.escape(meta_left)} | {html.escape(model["venue"])}</div>'
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
    paths.extend(_connect(COL_X["r32"] + CARD_W, COL_X["r16"], R32_Y, R16_Y, "line"))
    paths.extend(_connect(COL_X["r16"] + CARD_W, COL_X["qf"], R16_Y, QF_Y, "line"))
    paths.extend(_connect(COL_X["qf"] + CARD_W, COL_X["sf"], QF_Y, SF_Y, "line"))
    paths.extend(_connect_final(COL_X["sf"] + CARD_W, COL_X["final"], SF_Y, "line strong"))
    return f'<svg class="connector-layer" viewBox="0 0 {CANVAS_W} {CANVAS_H}" aria-hidden="true">{"".join(paths)}</svg>'


def _connect(x_from: int, x_to: int, feeder_ys: list[int], child_ys: list[int], class_name: str) -> list[str]:
    paths = []
    mid = x_from + ((x_to - x_from) / 2)
    for index, child_y in enumerate(child_ys):
        child_center = _center_y(child_y)
        for feeder_y in (feeder_ys[index * 2], feeder_ys[index * 2 + 1]):
            paths.append(_path(f"M{x_from},{_center_y(feeder_y)} H{mid} V{child_center} H{x_to}", class_name))
    return paths


def _connect_final(x_from: int, x_to: int, feeder_ys: list[int], class_name: str) -> list[str]:
    mid = x_from + ((x_to - x_from) / 2)
    child_center = FINAL_Y + FINAL_H / 2
    return [_path(f"M{x_from},{_center_y(feeder_y)} H{mid} V{child_center} H{x_to}", class_name) for feeder_y in feeder_ys]


def _path(d: str, class_name: str) -> str:
    return f'<path class="connector {class_name}" d="{d}" fill="none"/>'


def _center_y(y: int) -> float:
    return y + (CARD_H / 2)


def _column_headers() -> str:
    headers = [
        (COL_X["r32"], "Round of 32"),
        (COL_X["r16"], "Round of 16"),
        (COL_X["qf"], "Quarterfinals"),
        (COL_X["sf"], "Semifinals"),
        (COL_X["final"], "Final"),
    ]
    return "".join(
        f'<div class="round-header" style="left:{x}px;width:{FINAL_W if label == "Final" else CARD_W}px;">{html.escape(label)}</div>'
        for x, label in headers
    )


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
        background: #0B1120;
        color: #E8EDF6;
        font-family: "Segoe UI", "Trebuchet MS", Arial, sans-serif;
        -webkit-font-smoothing: antialiased;
    }}
    .bracket-shell {{
        height: 100vh;
        overflow: hidden;
        padding: 10px;
        position: relative;
        background: #0B1120;
    }}
    .bracket-viewport {{
        border: 1px solid rgba(148,163,184,.16);
        border-radius: 12px;
        height: calc(100vh - 20px);
        min-height: 740px;
        overflow: auto;
        background:
            linear-gradient(rgba(148,163,184,.05) 1px, transparent 1px),
            linear-gradient(90deg, rgba(148,163,184,.05) 1px, transparent 1px),
            #0E1626;
        background-size: 120px 120px;
        position: relative;
        z-index: 2;
    }}
    .bracket-header-row {{
        position: sticky;
        top: 0;
        left: 0;
        width: {CANVAS_W}px;
        height: {HEADER_H}px;
        z-index: 10;
        background: #0E1626;
        border-bottom: 1px solid rgba(148,163,184,.14);
    }}
    .round-header {{
        position: absolute;
        top: 50%;
        transform: translateY(-50%);
        border: 1px solid rgba(148,163,184,.18);
        border-radius: 8px;
        background: rgba(20,29,48,.92);
        color: #94A3B8;
        font-size: 13px;
        font-weight: 800;
        letter-spacing: .08em;
        padding: 9px 10px;
        text-align: center;
        text-transform: uppercase;
    }}
    .bracket-canvas {{
        height: {CANVAS_H}px;
        min-width: {CANVAS_W}px;
        position: relative;
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
        stroke: #33415C;
        stroke-width: 2;
        stroke-linecap: round;
        stroke-linejoin: round;
    }}
    .connector.strong {{ stroke: #D6A83A; stroke-width: 3; }}
    .bracket-card {{
        border: 1px solid rgba(148,163,184,.18);
        border-radius: 10px;
        background: #141D30;
        box-shadow: 0 6px 18px rgba(0,0,0,.30);
        min-height: {CARD_H}px;
        overflow: hidden;
        padding: 11px 12px;
        position: absolute;
        transition: border-color .15s ease, box-shadow .15s ease;
        width: {CARD_W}px;
        z-index: 4;
    }}
    .bracket-card:hover {{
        border-color: rgba(214,168,58,.50);
        box-shadow: 0 10px 26px rgba(0,0,0,.42);
        z-index: 7;
    }}
    .bracket-card.final-card {{
        border-color: rgba(214,168,58,.55);
        background:
            linear-gradient(180deg, rgba(214,168,58,.10), transparent 60%),
            #161F33;
        box-shadow: 0 14px 36px rgba(0,0,0,.48), 0 0 0 1px rgba(214,168,58,.12);
        min-height: {FINAL_H}px;
        padding: 14px 16px;
        z-index: 6;
    }}
    .bracket-card.third-card {{
        min-height: {THIRD_H}px;
    }}
    .match-head {{
        align-items: center;
        display: flex;
        justify-content: space-between;
        gap: 10px;
        margin-bottom: 2px;
    }}
    .match-head span {{
        color: #64748B;
        font-size: 11px;
        font-weight: 800;
        letter-spacing: .04em;
    }}
    .match-head strong {{
        border-radius: 5px;
        background: rgba(148,163,184,.14);
        color: #CBD5E1;
        font-size: 10px;
        font-weight: 800;
        letter-spacing: .05em;
        line-height: 1;
        padding: 4px 7px;
        text-transform: uppercase;
    }}
    .match-meta {{
        color: #7C8AA3;
        font-size: 10.5px;
        font-weight: 600;
        margin: 4px 0 9px;
        min-height: 13px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }}
    .team-stack {{
        display: grid;
        gap: 5px;
    }}
    .team-row {{
        align-items: center;
        border: 1px solid transparent;
        border-left: 3px solid transparent;
        border-radius: 6px;
        background: rgba(255,255,255,.04);
        display: grid;
        grid-template-columns: 34px 1fr 26px;
        gap: 10px;
        min-height: 40px;
        padding: 5px 9px 5px 7px;
        transition: background .15s ease;
    }}
    .team-row.winner {{
        border-left-color: #D6A83A;
        background: rgba(214,168,58,.14);
    }}
    .team-row.winner .team-copy span {{ color: #F4D789; }}
    .team-row.winner .team-score {{ color: #F4D789; }}
    .team-row.loser {{
        opacity: .50;
    }}
    .team-row.placeholder {{
        background: rgba(255,255,255,.02);
    }}
    .team-flag, .slot-emblem {{
        align-items: center;
        aspect-ratio: 3 / 2;
        border-radius: 3px;
        display: grid;
        font-size: 10px;
        font-weight: 800;
        height: 23px;
        justify-content: center;
        object-fit: cover;
        object-position: center;
        width: 34px;
    }}
    .team-flag:not(.flag-fallback) {{
        border: 1px solid rgba(255,255,255,.22);
        display: block;
    }}
    .slot-emblem, .flag-fallback {{
        border: 1px solid rgba(148,163,184,.24);
        background: rgba(148,163,184,.10);
        color: #94A3B8;
    }}
    .hidden {{ display: none; }}
    .team-copy {{
        min-width: 0;
    }}
    .team-copy span {{
        color: #EAF0FA;
        display: block;
        font-size: 13.5px;
        font-weight: 700;
        line-height: 1.1;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }}
    .team-row.placeholder .team-copy span {{
        color: #8C9AB3;
        font-weight: 600;
    }}
    .team-copy small {{
        color: #6B7A93;
        display: block;
        font-size: 9.5px;
        font-weight: 600;
        line-height: 1.05;
        margin-top: 2px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }}
    .team-score {{
        color: #EAF0FA;
        font-size: 20px;
        font-weight: 800;
        text-align: right;
    }}
    .final-card .match-head span {{
        color: #D6A83A;
        font-size: 12px;
    }}
    .final-card .match-head strong {{
        background: rgba(214,168,58,.18);
        color: #F4D789;
        font-size: 11px;
    }}
    .final-card .match-meta {{
        font-size: 11.5px;
        margin-bottom: 10px;
    }}
    .final-card .team-row {{
        grid-template-columns: 40px 1fr 34px;
        min-height: 46px;
    }}
    .final-card .team-flag,
    .final-card .slot-emblem {{
        height: 27px;
        width: 40px;
    }}
    .final-card .team-copy span {{
        font-size: 15px;
    }}
    .final-card .team-score {{
        font-size: 24px;
    }}
    """
