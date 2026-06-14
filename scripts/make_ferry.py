#!/usr/bin/env python3
"""Generate the Star Ferry sprite — the harbour companion to the Ding Ding tram.

Deterministic (Pillow), transparent PNG, in the locked Yok-Iso palette. A soft
plush vehicle-keepsake per aesthetic-spec §6 (Tram/ferry): jade hull (jade is the
spec's water/ferry material), cream double-deck cabins, antique-gold beltline,
one cinnabar funnel (the charming punctuation), a soft ink contour, a hint of a
teal waterline. No real logos/text (trademark-safe — the "Star Ferry" livery is
evoked by form + palette only, never a wordmark).

Usage:
  uv run python scripts/make_ferry.py --out game-tiles/props/ferry-star.png
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw

# Yok-Iso palette (aesthetic-spec §1)
JADE     = (46, 140, 125)    # 2E8C7D tram-jade — the ferry/water material
JADE_SH  = (33, 104, 92)     # shaded 3/4 side
TEAL     = (31, 111, 115)    # 1F6F73 harbour teal (waterline)
CREAM    = (240, 226, 201)   # F0E2C9 cabin / window band
GLASS    = (201, 211, 196)   # soft jade-grey glass
GOLD     = (199, 162, 91)    # C7A25B beltline / trim
INK      = (31, 26, 23)      # 1F1A17 contour
CINNABAR = (182, 71, 52)     # B64734 funnel accent

W, H = 320, 220


def ferry() -> Image.Image:
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # ── waterline (soft teal dashes the hull sits on) ───────────────────────
    for wx in range(40, 290, 34):
        d.line([(wx, 196), (wx + 18, 196)], fill=TEAL, width=4)

    # ── hull (double-ended: tapered bow + stern), jade with a 3/4 side ──────
    deck_y = 126
    hull_front = [(28, deck_y), (292, deck_y), (264, 188), (56, 188)]
    side = 14
    # 3/4 shaded side behind the front face
    d.polygon([(292, deck_y), (292 + side, deck_y + 8),
               (264 + side, 188 - 4), (264, 188)], fill=JADE_SH)
    d.polygon(hull_front, fill=JADE, outline=INK)
    d.line([(28, deck_y), (292, deck_y)], fill=INK, width=5)   # deck line
    d.line([(56, 188), (264, 188)], fill=INK, width=5)         # keel
    d.line([(28, deck_y), (56, 188)], fill=INK, width=5)       # bow
    d.line([(292, deck_y), (264, 188)], fill=INK, width=5)     # stern

    # gold beltline along the hull top
    d.rectangle([34, deck_y + 6, 286, deck_y + 14], fill=GOLD)
    d.line([(34, deck_y + 6), (286, deck_y + 6)], fill=INK, width=2)

    # portholes (gold dots, ink-ringed) along the hull
    for px in range(70, 260, 34):
        d.ellipse([px, deck_y + 26, px + 14, deck_y + 40], fill=GOLD, outline=INK, width=2)

    # ── main deck cabin (cream, window row, ink contour) ────────────────────
    def cabin(x0, y0, x1, y1, n):
        d.rounded_rectangle([x0, y0, x1, y1], radius=8, fill=CREAM, outline=INK, width=4)
        innerL, innerR = x0 + 12, x1 - 12
        step = (innerR - innerL) / n
        for i in range(n):
            gx0 = innerL + i * step + 3
            gx1 = innerL + (i + 1) * step - 3
            d.rounded_rectangle([gx0, y0 + 9, gx1, y1 - 9], radius=4, fill=GLASS, outline=INK, width=2)

    cabin(52, 82, 268, deck_y, 7)          # main deck
    # gold beltline between decks
    d.rectangle([60, 76, 260, 84], fill=GOLD)
    d.line([(60, 76), (260, 76)], fill=INK, width=2)
    cabin(84, 44, 236, 76, 5)              # upper deck (shorter)

    # ── cinnabar funnel on the upper deck (the punctuation) ─────────────────
    d.rounded_rectangle([150, 14, 178, 48], radius=6, fill=CINNABAR, outline=INK, width=3)
    d.rectangle([150, 22, 178, 30], fill=GOLD)            # funnel band
    d.line([(150, 22), (178, 22)], fill=INK, width=2)
    d.line([(150, 30), (178, 30)], fill=INK, width=2)

    # ── bow flag on a little pole (gold pennant) ────────────────────────────
    d.line([(40, deck_y), (34, 96)], fill=INK, width=3)
    d.polygon([(34, 96), (34, 108), (54, 102)], fill=GOLD, outline=INK)

    return img


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate the Star Ferry sprite")
    ap.add_argument("--out", type=Path, default=Path("game-tiles/props/ferry-star.png"))
    args = ap.parse_args()
    out = (Path(__file__).resolve().parent.parent / args.out
           if not args.out.is_absolute() else args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    ferry().save(out)
    print(f"star ferry → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
