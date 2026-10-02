#!/usr/bin/env python3
"""
make-logo — turn any image into a fastfetch logo for kitty.

Does the three things that are easy to get wrong:

1. Converts to PNG. kitty's graphics protocol accepts only raw RGB (f=24),
   raw RGBA (f=32) and PNG (f=100). Hand it a JPEG and it will try to parse
   JPEG bytes as PNG, fail, and draw nothing at all — no error, no warning,
   just an empty space where the logo should be. This is the single most
   common reason an image logo "doesn't work".

2. Keys out the flat background to transparency, so the art floats on the
   terminal background instead of sitting in a visible rectangle. The colour
   is sampled from the image border rather than guessed.

3. Computes the width/height box in *character cells* that preserves the
   aspect ratio. Terminal cells are roughly 2.2x taller than they are wide,
   so a naive equal-cell box squashes the image badly.

Usage:
    ./make-logo.py photo.jpg
    ./make-logo.py photo.jpg --rows 30 --outdir ~/.config/fastfetch
    ./make-logo.py photo.jpg --keep-background      # skip the alpha key
"""

from __future__ import annotations

import argparse
import math
import sys
from collections import Counter
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    sys.exit("Pillow is required:  pip install --user Pillow")

# A character cell is taller than it is wide. Measured across common
# terminal fonts and DPI settings this lands between 2.0 and 2.3; 2.2 is a
# good middle. Override with --cell-ratio if your font is unusual.
DEFAULT_CELL_RATIO = 2.2


def sample_background(img: Image.Image) -> tuple[int, int, int]:
    """Most common colour around the border, which is background by construction."""
    rgb = img.convert("RGB")
    w, h = rgb.size
    px = rgb.load()
    edge: list[tuple[int, int, int]] = []
    for x in range(w):
        edge.append(px[x, 0])
        edge.append(px[x, h - 1])
    for y in range(h):
        edge.append(px[0, y])
        edge.append(px[w - 1, y])
    return Counter(edge).most_common(1)[0][0]


def key_background(img: Image.Image, bg: tuple[int, int, int], tol: float) -> tuple[Image.Image, float]:
    """Set alpha to 0 for pixels within `tol` of `bg`. Returns (image, fraction keyed)."""
    out = img.convert("RGBA")
    px = out.load()
    w, h = out.size
    keyed = 0
    for y in range(h):
        for x in range(w):
            r, g, b, _ = px[x, y]
            if math.dist((r, g, b), bg) <= tol:
                px[x, y] = (r, g, b, 0)
                keyed += 1
    return out, keyed / (w * h)


def cell_box(width: int, height: int, rows: int, cell_ratio: float) -> tuple[int, int]:
    """Columns needed for `rows` rows to preserve the image's aspect ratio."""
    cols = (width / height) * rows * cell_ratio
    return max(1, round(cols)), rows


def main() -> int:
    ap = argparse.ArgumentParser(description="Prepare an image for use as a fastfetch/kitty logo.")
    ap.add_argument("image", type=Path, help="source image (any format Pillow can read)")
    ap.add_argument("--outdir", type=Path, default=Path.cwd(), help="where to write the PNGs")
    ap.add_argument("--name", default=None, help="base name for output (default: source stem)")
    ap.add_argument("--rows", type=int, default=26, help="logo height in character cells (default: 26)")
    ap.add_argument("--cell-ratio", type=float, default=DEFAULT_CELL_RATIO,
                    help=f"cell height/width ratio (default: {DEFAULT_CELL_RATIO})")
    ap.add_argument("--tolerance", type=float, default=30.0,
                    help="RGB distance treated as background (default: 30)")
    ap.add_argument("--keep-background", action="store_true",
                    help="do not key the background to transparency")
    args = ap.parse_args()

    if not args.image.is_file():
        return f"no such file: {args.image}"  # type: ignore[return-value]

    src = Image.open(args.image)
    w, h = src.size
    stem = args.name or args.image.stem
    args.outdir.mkdir(parents=True, exist_ok=True)

    opaque = args.outdir / f"{stem}.png"
    src.convert("RGB").save(opaque, "PNG", optimize=True)
    print(f"wrote {opaque}   ({w}x{h}, aspect {w/h:.4f})")

    chosen = opaque
    if not args.keep_background:
        bg = sample_background(src)
        keyed_img, frac = key_background(src, bg, args.tolerance)
        transparent = args.outdir / f"{stem}-transparent.png"
        keyed_img.save(transparent, "PNG", optimize=True)
        print(f"wrote {transparent}")
        print(f"  background sampled as rgb{bg} (#{bg[0]:02x}{bg[1]:02x}{bg[2]:02x})")
        print(f"  {frac*100:.1f}% of pixels keyed transparent")
        if frac > 0.97:
            print("  WARNING: almost everything was keyed — lower --tolerance")
        elif frac < 0.05:
            print("  WARNING: almost nothing was keyed — the background may not be flat;"
                  " raise --tolerance or use --keep-background")
        chosen = transparent

    cols, rows = cell_box(w, h, args.rows, args.cell_ratio)
    print()
    print("Paste into ~/.config/fastfetch/config.jsonc:")
    print()
    print('  "logo": {')
    print('    "type": "kitty-direct",')
    print(f'    "source": "~/.config/fastfetch/{chosen.name}",')
    print(f'    "width": {cols},')
    print(f'    "height": {rows},')
    print('    "preserveAspectRatio": true,')
    print('    "padding": { "top": 1, "left": 2, "right": 4 }')
    print('  },')
    return 0


if __name__ == "__main__":
    sys.exit(main())
