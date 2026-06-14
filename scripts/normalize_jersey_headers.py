"""Normalize team jersey hero headers so every crest sits at the vertical center.

Outputs to assets/jerseys/headers_norm/. The display crops are never padded or
shifted horizontally -- we only crop vertically, so there is no top/bottom
stretching and the image stays exactly centered horizontally.

- "Kept" teams already have the crest in the existing 1000x476 header crop, so we
  take a symmetric vertical window around the crest (cropping, never padding).
- "Regen" teams had crops where the crest was cut off / missing, so we rebuild
  the header from the full-kit image (assets/jerseys/<slug>.webp), which always
  contains the crest, then center-crop it vertically around the crest.

Crest vertical-center fractions below were determined by visual inspection.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
HEADERS = ROOT / "assets" / "jerseys" / "headers"
KITS = ROOT / "assets" / "jerseys"
OUT = ROOT / "assets" / "jerseys" / "headers_norm"
OUT.mkdir(exist_ok=True)

OUT_W = 1000
OUT_H = 476          # target output height / regen height
MIN_WIN = 400        # shortest kept window, bounds how much we zoom in

# Crest vertical center as a fraction of the existing 1000x476 header height.
KEPT = {
    "argentina": 0.50, "australia": 0.43, "austria": 0.46, "belgium": 0.46,
    "bosnia-and-herzegovina": 0.51, "brazil": 0.51, "cabo-verde": 0.50,
    "canada": 0.54, "colombia": 0.47, "congo-dr": 0.66, "cote-d-ivoire": 0.43,
    "curacao": 0.62, "czechia": 0.36, "ecuador": 0.36, "egypt": 0.46,
    "england": 0.48, "france": 0.53, "iraq": 0.50, "jordan": 0.50,
    "mexico": 0.50, "morocco": 0.58, "new-zealand": 0.40, "norway": 0.50,
    "panama": 0.50, "paraguay": 0.46, "portugal": 0.50, "qatar": 0.45,
    "saudi-arabia": 0.30, "senegal": 0.55, "south-africa": 0.37,
    "south-korea": 0.41, "spain": 0.50, "sweden": 0.50, "switzerland": 0.45,
    "tunisia": 0.50, "turkiye": 0.60, "uruguay": 0.50, "usa": 0.40,
    "uzbekistan": 0.46,
}

# Crest vertical center as a fraction of the full-kit image height.
REGEN = {
    "algeria": 0.72, "croatia": 0.40, "germany": 0.42, "ghana": 0.40,
    "haiti": 0.58, "ir-iran": 0.42, "japan": 0.60, "netherlands": 0.62,
    "scotland": 0.62,
}


def _clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


def build_kept(slug: str, cy: float) -> Image.Image:
    """Symmetric vertical crop of the existing header around the crest (no pad)."""
    src = Image.open(HEADERS / f"{slug}.webp").convert("RGB")
    if src.width != OUT_W:
        src = src.resize((OUT_W, round(src.height * OUT_W / src.width)))
    h = src.height
    crest = round(cy * h)
    win = _clamp(2 * min(crest, h - crest), MIN_WIN, h)
    top = _clamp(crest - win // 2, 0, h - win)
    return src.crop((0, top, OUT_W, top + win))


def build_regen(slug: str, cy: float) -> Image.Image:
    """Rebuild from the full kit: center-crop vertically around the crest (no pad,
    no horizontal shift)."""
    kit = Image.open(KITS / f"{slug}.webp").convert("RGB")
    kw, kh = kit.size
    band_h = round(0.42 * kh)                      # generous context around crest
    crest = round(cy * kh)
    top = _clamp(crest - band_h // 2, 0, kh - band_h)
    band = kit.crop((0, top, kw, top + band_h))
    big = band.resize((OUT_W, round(band_h * OUT_W / kw)))
    crest_big = round((crest - top) * OUT_W / kw)  # crest row in the upscaled band
    ctop = _clamp(crest_big - OUT_H // 2, 0, big.height - OUT_H)
    return big.crop((0, ctop, OUT_W, ctop + OUT_H))


def main() -> None:
    for slug, cy in KEPT.items():
        build_kept(slug, cy).save(OUT / f"{slug}.webp", quality=90, method=6)
    for slug, cy in REGEN.items():
        build_regen(slug, cy).save(OUT / f"{slug}.webp", quality=90, method=6)
    print(f"wrote {len(KEPT) + len(REGEN)} headers to {OUT}")


if __name__ == "__main__":
    main()
