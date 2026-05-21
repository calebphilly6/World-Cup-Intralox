from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit.components.v1 as components


COMPONENT_DIR = Path(__file__).resolve().parent / "clickable_cards_component"
_component = components.declare_component("clickable_cards", path=str(COMPONENT_DIR))


def clickable_cards(
    cards: list[dict[str, Any]],
    *,
    variant: str,
    key: str,
    title: str = "",
    detail_html: str = "",
):
    return _component(
        cards=cards,
        variant=variant,
        title=title,
        detail_html=detail_html,
        key=key,
        default=None,
    )
