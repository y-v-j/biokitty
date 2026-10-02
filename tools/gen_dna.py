#!/usr/bin/env python3
"""
Generate a binary-DNA double helix as monospace ASCII for use as a fastfetch logo.

Two backbone strands are sine waves 180 degrees out of phase, so they cross at
regular intervals the way a real double helix reads on the page. Between them,
base-pair rungs are filled with alternating binary digits, matching the
"digital DNA" look of the reference image.

Every row is padded to exactly `width` columns. That matters: fastfetch measures
the logo block by its widest line to decide where the info panel starts, so
ragged rows would skew the whole layout.
"""

from __future__ import annotations

import math

WIDTH = 34          # columns of the art block
HEIGHT = 24         # rows
PERIOD = 16.0       # rows per full 360-degree twist
AMPLITUDE = 13.0    # half-width of the helix swing
CENTER = WIDTH / 2.0

# fastfetch colour placeholders. $1 = backbone, $2..$4 = rung gradient.
BACKBONE = "$1"
RUNGS = ("$2", "$3", "$4")

BACKBONE_CH = "o"   # replaced per-row below with a binary digit


def strand_positions(row: int) -> tuple[int, int]:
    """Column indices of the two backbones on this row."""
    phase = row * (2 * math.pi / PERIOD)
    left = CENTER + AMPLITUDE * math.sin(phase)
    right = CENTER + AMPLITUDE * math.sin(phase + math.pi)
    return round(left), round(right)


def build() -> list[str]:
    rows: list[str] = []
    bit = 0
    for y in range(HEIGHT):
        a, b = strand_positions(y)
        lo, hi = min(a, b), max(a, b)
        cells = [" "] * WIDTH

        gap = hi - lo
        # Rungs only every other row, and only once the strands are far enough
        # apart to have something to span. Filling every row reads as a solid
        # blob rather than a helix.
        if gap >= 4 and y % 2 == 0:
            # Solid runs of digits, so each rung reads as one base pair of the
            # twisted ladder rather than a dotted line.
            for x in range(lo + 1, hi):
                cells[x] = str(bit & 1)
                bit += 1
        # Backbones sit on top of the rung so the strand always reads clearly.
        cells[lo] = str((y + 1) & 1)
        cells[hi] = str(y & 1)

        rows.append("".join(cells).rstrip().ljust(WIDTH))
        bit += 1  # shift the pattern each row so columns don't align vertically
    return rows


def colourise(rows: list[str]) -> list[str]:
    """Wrap each row in fastfetch colour placeholders.

    The rung colour cycles down the helix to fake the blue->cyan gradient of the
    reference image, while both backbones stay a single accent colour.
    """
    out: list[str] = []
    for y, row in enumerate(rows):
        a, b = strand_positions(y)
        lo, hi = min(a, b), max(a, b)
        rung = RUNGS[y % len(RUNGS)]

        # Emit one placeholder per contiguous run rather than per character.
        # Fewer escapes keeps the file readable and hand-editable, and leaves
        # less for fastfetch's width measurement to strip.
        line: list[str] = []
        current: str | None = None
        for x, ch in enumerate(row):
            if ch == " ":
                line.append(ch)
                current = None
                continue
            want = BACKBONE if x in (lo, hi) else rung
            if want != current:
                line.append(want)
                current = want
            line.append(ch)
        # Trailing spaces are preserved so every line is the same visual width.
        out.append("".join(line))
    return out


if __name__ == "__main__":
    plain = build()
    print("\n".join(plain))
    print()
    print("width check:", {len(r) for r in plain})
    with open("dna_plain.txt", "w", encoding="utf-8") as fh:
        fh.write("\n".join(plain) + "\n")
    with open("dna.txt", "w", encoding="utf-8") as fh:
        fh.write("\n".join(colourise(plain)) + "\n")
