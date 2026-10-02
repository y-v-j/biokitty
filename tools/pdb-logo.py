#!/usr/bin/env python3
"""
pdb-logo — render any PDB structure into a terminal logo, via PyMOL.

Why render instead of downloading a picture:

  * The alpha channel comes out of the ray tracer, so edges are properly
    anti-aliased. Colour-keying a render that was saved against a white
    background gives hard, stair-stepped edges — which looks visibly rough
    next to hard-edged pixel art.
  * The palette is chosen, not fought with, so the logo matches your theme.
  * PDB coordinate files are public domain, so there is no image licence to
    worry about when you publish your dotfiles.

Requires PyMOL on PATH (`pymol -cq` is used; no GUI or display needed).

Proteins are coloured blue -> pale along the chain; nucleic acids get a
blue -> cyan backbone with pale base-pair rungs, so DNA renders in the same
palette.

Usage:
    ./pdb-logo.py 1ema                       # GFP
    ./pdb-logo.py 1gzx --name hemoglobin
    ./pdb-logo.py 1aki --rows 20 --outdir ~/.config/fastfetch
    ./pdb-logo.py 1ema --upright             # rotate 90 deg (tall, narrow)

Bundled logos: 1bna (B-DNA, --upright --rows 26), 1kx5 (nucleosome,
--rows 21), 1ema (GFP), 2por (porin), 1aki (lysozyme, --rows 18).
Also worth trying: 1gzx (hemoglobin), 4ins (insulin), 1mbn (myoglobin),
6vxx (SARS-CoV-2 spike).

Note that dense structures turn to visual noise at terminal size. Bold,
simple silhouettes read best — a beta barrel survives the downscale far
better than a bundle of thin helices.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Deep blue -> bright cyan, matching the digital-helix theme.
PALETTE = {
    "bk_blue": "[0.15, 0.42, 0.85]",
    "bk_cyan": "[0.20, 0.85, 0.95]",
    "bk_pale": "[0.70, 0.93, 1.00]",
}

CELL_RATIO = 2.2  # terminal cells are ~2.2x taller than wide

SCRIPT = """
set ray_opaque_background, 0
set opaque_background, 0
set ray_shadows, 0
set antialias, 2
set cartoon_fancy_helices, 1
set cartoon_highlight_color, grey20
set ray_trace_mode, {trace_mode}
set ray_trace_gain, 0.15
set depth_cue, 0
set specular, 0.2
{colors}
fetch {pdb}, async=0
remove solvent
remove hydrogens
hide everything
show cartoon
spectrum count, bk_blue bk_cyan bk_pale, name CA
color bk_pale, polymer.nucleic
spectrum count, bk_blue bk_cyan, polymer.nucleic and name P
orient
{rotate}
zoom all, 1
ray {rw}, {rh}
png {out}, dpi=150
"""


def main() -> int:
    ap = argparse.ArgumentParser(description="Render a PDB structure as a terminal logo.")
    ap.add_argument("pdb", help="4-character PDB ID, e.g. 1ema")
    ap.add_argument("--outdir", type=Path, default=Path.cwd())
    ap.add_argument("--name", default=None, help="output base name (default: the PDB ID)")
    ap.add_argument("--rows", type=int, default=24, help="logo height in cells (default: 24)")
    ap.add_argument("--upright", action="store_true",
                    help="rotate 90 degrees; usually a better fit beside a text column")
    ap.add_argument("--flat", action="store_true",
                    help="smooth shading instead of the default cel shading")
    ap.add_argument("--ray", type=int, nargs=2, metavar=("W", "H"), default=(1200, 1648),
                    help="ray-trace resolution before cropping (default: 1200 1648)")
    ap.add_argument("--cell-width", type=float, default=8.05,
                    help="terminal cell width in px (default: 8.05, Fantasque 12pt)")
    ap.add_argument("--cell-height", type=float, default=17.18,
                    help="terminal cell height in px (default: 17.18, Fantasque 12pt)")
    args = ap.parse_args()

    if not shutil.which("pymol"):
        return "pymol not found on PATH — install PyMOL first"  # type: ignore[return-value]
    try:
        from PIL import Image
    except ImportError:
        return "Pillow is required:  pip install --user Pillow"  # type: ignore[return-value]

    name = args.name or args.pdb.lower()
    args.outdir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "raw.png"
        script = SCRIPT.format(
            pdb=args.pdb,
            colors="\n".join(f"set_color {k}, {v}" for k, v in PALETTE.items()),
            rotate="turn z, 90" if args.upright else "",
            trace_mode=0 if args.flat else 3,
            rw=args.ray[0], rh=args.ray[1],
            out=raw,
        )
        pml = Path(tmp) / "logo.pml"
        pml.write_text(script)

        print(f"rendering {args.pdb} with PyMOL (this takes a few seconds)...")
        proc = subprocess.run(["pymol", "-cq", str(pml)],
                              capture_output=True, text=True, cwd=tmp)
        if not raw.exists():
            sys.stderr.write(proc.stdout[-2000:] + proc.stderr[-2000:])
            return f"render failed — is '{args.pdb}' a valid PDB ID?"  # type: ignore[return-value]

        img = Image.open(raw).convert("RGBA")
        bbox = img.getbbox()
        if bbox is None:
            return "render produced an empty image"  # type: ignore[return-value]
        img = img.crop(bbox)

    # --- pre-scale to the size it will actually be displayed at -------------
    #
    # This is the step that decides whether the logo looks crisp or chewed.
    # kitty scales the image into the cell box itself, and a large reduction
    # (3x and up) shreds thin features — cel-shading outlines especially, which
    # are only a pixel or two wide. Downscaling here with Lanczos, from a
    # supersampled render, gives far cleaner edges than kitty's own reduction.
    #
    # The target is 2x the display size rather than 1x: the remaining 2:1
    # reduction is visually free, and the extra headroom means the logo still
    # looks sharp if you bump the font size instead of instantly going soft.
    src_w, src_h = img.size
    cols = round((src_w / src_h) * args.rows * CELL_RATIO)
    disp_w = cols * args.cell_width
    disp_h = args.rows * args.cell_height
    scale = min(disp_w / src_w, disp_h / src_h)          # aspect-fit, as kitty does
    target = (max(1, round(src_w * scale * 2)), max(1, round(src_h * scale * 2)))
    img = img.resize(target, Image.LANCZOS)

    dst = args.outdir / f"{name}.png"
    img.save(dst, "PNG", optimize=True)
    w, h = img.size

    alpha = img.getchannel("A")
    soft = sum(alpha.histogram()[1:255])

    print(f"wrote {dst}  ({w}x{h}, pre-scaled to 2x its {disp_w:.0f}x{disp_h:.0f} display size)")
    print(f"  {soft} anti-aliased edge pixels — a colour-keyed image would have 0")

    total = 2 + cols + 4 + 61  # padding + logo + gutter + typical info width
    print()
    print(f'  "logo": {{')
    print(f'    "type": "kitty-direct",')
    print(f'    "source": "~/.config/fastfetch/{dst.name}",')
    print(f'    "width": {cols},')
    print(f'    "height": {args.rows},')
    print(f'    "preserveAspectRatio": true,')
    print(f'    "padding": {{ "top": 1, "left": 2, "right": 4 }}')
    print(f'  }},')
    print()
    print(f"  estimated total line width: {total} columns", end="")
    if total > 110:
        print("  -- WIDER THAN THE DEFAULT WINDOW; use fewer --rows, or --upright")
    else:
        print("  (fits the default 110-column window)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
