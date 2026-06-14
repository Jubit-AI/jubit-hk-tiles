#!/usr/bin/env python3
"""Generate the Ding Ding tram sprite — Output E's vintage double-decker keepsake.

Deterministic (Pillow), transparent PNG, in the locked Yok-Iso palette. A soft
plush vehicle-keepsake per aesthetic-spec §6 (Tram/ferry): ding-ding cinnabar
body, cream window bands, antique-gold beltline, one soft ink contour, a hint of
3/4 side. No real logos/text (the destination band is blank — trademark-safe).

Usage:
  uv run python scripts/make_tram.py --out game-tiles/props/tram-dingding.png
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw

# Yok-Iso palette (aesthetic-spec §1)
CINNABAR   = (182, 71, 52)    # B64734 ding-ding body
CINNABAR_SH= (150, 56, 40)    # shaded 3/4 side
CREAM      = (240, 226, 201)  # F0E2C9 window band
GLASS      = (201, 211, 196)  # soft jade-grey glass
GOLD       = (199, 162, 91)   # C7A25B beltline
INK        = (31, 26, 23)     # 1F1A17 contour
PAPER      = (246, 241, 232)  # F6F1E8

W, H = 256, 300


def tram() -> Image.Image:
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    bx0, by0, bx1, by1 = 44, 40, 196, 250          # body box (front face)
    side = 22                                        # 3/4 side depth
    R = 18

    # 3/4 shaded side (drawn first, behind the front face)
    d.polygon([(bx1, by0 + R), (bx1 + side, by0 + R + 8),
               (bx1 + side, by1 - 6), (bx1, by1)], fill=CINNABAR_SH)
    d.line([(bx1 + side, by0 + R + 8), (bx1 + side, by1 - 6)], fill=INK, width=4)

    # trolley pole (roof → up)
    d.line([(bx0 + 30, by0 + 6), (bx0 + 6, 8)], fill=INK, width=4)
    d.ellipse([bx0, 2, bx0 + 12, 14], fill=GOLD, outline=INK, width=2)

    # body (front face) — rounded, cinnabar, one soft ink contour
    d.rounded_rectangle([bx0, by0, bx1, by1], radius=R, fill=CINNABAR, outline=INK, width=5)

    # blank destination band (NO text — trademark-safe)
    d.rounded_rectangle([bx0 + 14, by0 + 10, bx1 - 14, by0 + 30], radius=6,
                        fill=CREAM, outline=INK, width=3)

    # upper deck windows (cream frame + glass + ink mullions)
    def window_row(y0, y1):
        d.rounded_rectangle([bx0 + 12, y0, bx1 - 12, y1], radius=8, fill=CREAM, outline=INK, width=3)
        n = 4
        innerL, innerR = bx0 + 20, bx1 - 20
        step = (innerR - innerL) / n
        for i in range(n):
            gx0 = innerL + i * step + 3
            gx1 = innerL + (i + 1) * step - 3
            d.rounded_rectangle([gx0, y0 + 7, gx1, y1 - 7], radius=4, fill=GLASS, outline=INK, width=2)

    window_row(by0 + 40, by0 + 86)                  # upper deck
    # gold beltline between decks
    d.rectangle([bx0 + 4, by0 + 92, bx1 - 4, by0 + 100], fill=GOLD)
    d.line([(bx0 + 4, by0 + 92), (bx1 - 4, by0 + 92)], fill=INK, width=2)
    d.line([(bx0 + 4, by0 + 100), (bx1 - 4, by0 + 100)], fill=INK, width=2)
    window_row(by0 + 108, by0 + 152)                # lower deck

    # door (right) + a panel
    d.rounded_rectangle([bx1 - 52, by0 + 158, bx1 - 16, by1 - 14], radius=6,
                        fill=CINNABAR_SH, outline=INK, width=3)
    d.line([((bx1 - 52 + bx1 - 16) / 2, by0 + 158), ((bx1 - 52 + bx1 - 16) / 2, by1 - 14)],
           fill=INK, width=2)

    # skirt + two wheels
    d.rectangle([bx0 + 8, by1 - 14, bx1 - 8, by1 + 4], fill=INK)
    for wx in (bx0 + 40, bx1 - 56):
        d.ellipse([wx, by1 - 6, wx + 28, by1 + 22], fill=(40, 34, 30), outline=INK, width=3)
        d.ellipse([wx + 9, by1 + 3, wx + 19, by1 + 13], fill=GOLD)

    # a single cinnabar "ding" headlamp dot (the charming punctuation)
    d.ellipse([bx0 + 16, by1 - 40, bx0 + 30, by1 - 26], fill=GOLD, outline=INK, width=2)
    return img


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate the Ding Ding tram sprite")
    ap.add_argument("--out", type=Path, default=Path("game-tiles/props/tram-dingding.png"))
    args = ap.parse_args()
    out = (Path(__file__).resolve().parent.parent / args.out
           if not args.out.is_absolute() else args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tram().save(out)
    print(f"ding ding tram → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
