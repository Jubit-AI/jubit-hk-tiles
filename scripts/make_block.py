#!/usr/bin/env python3
"""Generate a clean HK tong-lau building-block prop — the generic 'blocked' cell
identity sprite (replaces the broken bake'd prop-mongkok-block.png).

Deterministic (Pillow), transparent PNG, locked Yok-Iso palette. A soft plush HK
walk-up tenement in 3/4 view: warm-neutral concrete facade, a 3/4 shaded side,
stacked cream/jade-glass window rows, a cinnabar shop awning + shopfront, the
iconic protruding (blank, trademark-safe) signboard, and rooftop water tanks.
Sits on a 'blocked' cell as the impassable building. Pairs with the ding-ding
tram + Star Ferry vehicle keepsakes.

Why deterministic, not bake'd: the 3D bake can't isolate a single building from
HK's dense b3dm tiles (it yields loose block-chunks), so authored sprites are the
reliable route for clean identity props.

Usage:
  uv run python scripts/make_block.py --out game-tiles/props/prop-tonglau.png
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw

# Yok-Iso palette (aesthetic-spec §1)
CONC    = (198, 190, 174)   # warm-neutral concrete facade (lit, not tan-dune)
CONC_SH = (150, 142, 124)   # 3/4 shaded side
CREAM   = (240, 226, 201)   # window frames / shopfront
GLASS   = (170, 188, 184)   # jade-grey glass (harbour tie)
GOLD    = (199, 162, 91)    # C7A25B trim
INK     = (31, 26, 23)      # 1F1A17 contour
CINNABAR= (182, 71, 52)     # B64734 awning + signboard
JADE    = (46, 140, 125)    # 2E8C7D AC-unit accent

W, H = 208, 300


def block() -> Image.Image:
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    fx0, fy0, fx1, fy1 = 44, 58, 152, 276        # facade (front face)
    side = 20

    # ── 3/4 shaded side (behind the front face) ─────────────────────────────
    d.polygon([(fx1, fy0 + 6), (fx1 + side, fy0 + 18),
               (fx1 + side, fy1 - 6), (fx1, fy1)], fill=CONC_SH)
    d.line([(fx1 + side, fy0 + 18), (fx1 + side, fy1 - 6)], fill=INK, width=4)

    # ── rooftop: parapet + two water tanks + a thin antenna ─────────────────
    d.line([(fx0 - 2, fy0), (fx1 + 2, fy0)], fill=INK, width=4)        # parapet
    for tx in (fx0 + 16, fx0 + 64):
        d.rounded_rectangle([tx, fy0 - 22, tx + 30, fy0 - 2], radius=5, fill=CONC_SH, outline=INK, width=3)
        d.ellipse([tx + 4, fy0 - 26, tx + 26, fy0 - 14], fill=GOLD, outline=INK, width=2)
    d.line([(fx1 - 14, fy0), (fx1 - 14, fy0 - 30)], fill=INK, width=2)  # antenna

    # ── facade ──────────────────────────────────────────────────────────────
    d.rounded_rectangle([fx0, fy0, fx1, fy1], radius=6, fill=CONC, outline=INK, width=5)

    # stacked window rows (cream frame + jade-grey glass + ink mullions)
    def floor(y0, y1, ac=False):
        d.rounded_rectangle([fx0 + 10, y0, fx1 - 10, y1], radius=6, fill=CREAM, outline=INK, width=3)
        innerL, innerR, n = fx0 + 16, fx1 - 16, 3
        step = (innerR - innerL) / n
        for i in range(n):
            gx0 = innerL + i * step + 3
            gx1 = innerL + (i + 1) * step - 3
            d.rounded_rectangle([gx0, y0 + 6, gx1, y1 - 6], radius=3, fill=GLASS, outline=INK, width=2)
        if ac:  # a jade AC box hanging off one window (HK character)
            d.rectangle([innerL + step + 4, y1 - 2, innerL + step + 18, y1 + 8], fill=JADE, outline=INK, width=2)

    floor(fy0 + 12, fy0 + 50)
    floor(fy0 + 58, fy0 + 96, ac=True)
    floor(fy0 + 104, fy0 + 142, ac=True)

    # ── ground floor: cinnabar awning + shopfront ───────────────────────────
    ay = fy0 + 150
    d.polygon([(fx0 - 4, ay), (fx1 + 4, ay), (fx1 - 4, ay + 16), (fx0 + 4, ay + 16)], fill=CINNABAR, outline=INK)
    d.rounded_rectangle([fx0 + 8, ay + 20, fx1 - 8, fy1 - 6], radius=4, fill=CREAM, outline=INK, width=3)
    d.rounded_rectangle([fx0 + 16, ay + 28, fx0 + 50, fy1 - 10], radius=3, fill=CONC_SH, outline=INK, width=2)  # door
    d.rounded_rectangle([fx0 + 58, ay + 28, fx1 - 16, fy1 - 30], radius=3, fill=GLASS, outline=INK, width=2)    # shop window

    # ── iconic protruding signboard (blank — trademark-safe) ────────────────
    d.rectangle([fx0 - 18, fy0 + 36, fx0 + 2, fy0 + 96], fill=CINNABAR, outline=INK)
    d.rectangle([fx0 - 14, fy0 + 42, fx0 - 2, fy0 + 90], outline=GOLD, width=2)
    return img


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate the HK tong-lau block prop")
    ap.add_argument("--out", type=Path, default=Path("game-tiles/props/prop-tonglau.png"))
    args = ap.parse_args()
    out = (Path(__file__).resolve().parent.parent / args.out
           if not args.out.is_absolute() else args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    block().save(out)
    print(f"tong-lau block → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
