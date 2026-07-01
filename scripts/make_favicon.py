"""Build the browser-tab favicon (assets/favicon.png) from a source headshot.

Crops a square focused on the face (upper-center of a typical portrait), masks
it into a circle with a transparent background, and saves a 256x256 PNG.

Usage:
    python scripts/make_favicon.py path/to/headshot.jpg
    python scripts/make_favicon.py path/to/headshot.jpg --shape square
    python scripts/make_favicon.py path/to/headshot.jpg --zoom 1.15 --top 0.06

--zoom  >1 crops in tighter on the face; <1 pulls back.
--top   fraction of the image height where the crop's top edge sits (0 = very
        top). Smaller keeps more forehead; larger cuts to just the face.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = PROJECT_ROOT / "assets" / "favicon.png"
SIZE = 256


def _face_square(image: Image.Image, zoom: float, top_fraction: float) -> Image.Image:
    """Return a square crop centered horizontally and biased toward the face,
    which sits in the upper-center of a standard portrait."""
    width, height = image.size
    side = int(min(width, height) / zoom)
    side = max(1, min(side, width, height))

    left = (width - side) // 2
    top = int(height * top_fraction)
    top = max(0, min(top, height - side))
    return image.crop((left, top, left + side, top + side))


def _circle_mask(size: int) -> Image.Image:
    mask = Image.new("L", (size * 4, size * 4), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size * 4, size * 4), fill=255)
    return mask.resize((size, size), Image.LANCZOS)


def build_favicon(source: Path, shape: str, zoom: float, top_fraction: float) -> Path:
    image = Image.open(source).convert("RGBA")
    square = _face_square(image, zoom, top_fraction).resize((SIZE, SIZE), Image.LANCZOS)

    if shape == "circle":
        square.putalpha(_circle_mask(SIZE))

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    square.save(OUTPUT_PATH, format="PNG")
    return OUTPUT_PATH


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate assets/favicon.png from a headshot.")
    parser.add_argument("source", type=Path, help="Path to the source headshot image.")
    parser.add_argument("--shape", choices=("circle", "square"), default="circle")
    parser.add_argument("--zoom", type=float, default=1.25, help="Crop tightness (>1 = tighter).")
    parser.add_argument("--top", type=float, default=0.04, help="Top edge as a fraction of height.")
    args = parser.parse_args()

    if not args.source.exists():
        raise SystemExit(f"Source image not found: {args.source}")

    output = build_favicon(args.source, args.shape, args.zoom, args.top)
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
