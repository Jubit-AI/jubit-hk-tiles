#!/usr/bin/env python3
"""HK street-prop sprite batch — deterministic Yok-Iso identity props.

Adds 4 recognizable HK street props to the deterministic set (alongside the
ding-ding tram / Star Ferry / tong-lau block): MTR entrance, dai pai dong food
stall, red-sail junk boat, protruding neon sign. Pure Pillow, transparent PNGs,
locked palette, trademark-safe (form + palette only — no wordmarks/logos).

Usage:
  uv run python scripts/make_streetprops.py --out game-tiles/props
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw

# ── Yok-Iso palette (aesthetic-spec §1) ──────────────────────────────────────
CONC    = (198, 190, 174)
CONC_SH = (150, 142, 124)
CREAM   = (240, 226, 201)
GLASS   = (170, 188, 184)
GOLD    = (199, 162, 91)
INK     = (31, 26, 23)
CINNABAR= (182, 71, 52)
JADE    = (46, 140, 125)
TEAL    = (31, 111, 115)


def mtr_entrance() -> Image.Image:
    """Transit entrance: concrete kiosk, dark descending stairwell, gold canopy."""
    W, H = 200, 212
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    bx0, by0, bx1, by1 = 46, 98, 150, 190; side = 18
    d.polygon([(bx1, by0 + 10), (bx1 + side, by0 + 22), (bx1 + side, by1 - 6), (bx1, by1)], fill=CONC_SH)
    d.rounded_rectangle([bx0, by0, bx1, by1], radius=6, fill=CONC, outline=INK, width=5)
    # dark descending stairwell (narrower at the bottom) + step hints
    d.polygon([(bx0 + 18, by0 + 18), (bx1 - 18, by0 + 18), (bx1 - 30, by1 - 8), (bx0 + 30, by1 - 8)], fill=INK)
    for i in range(3):
        y = by0 + 36 + i * 16
        d.line([(bx0 + 24 + i * 4, y), (bx1 - 24 - i * 4, y)], fill=CONC_SH, width=3)
    # overhanging canopy + blank teal sign band (trademark-safe)
    d.rounded_rectangle([bx0 - 12, by0 - 16, bx1 + 12, by0 + 2], radius=4, fill=CONC, outline=INK, width=4)
    d.rounded_rectangle([bx0 + 6, by0 - 13, bx1 - 6, by0 - 2], radius=3, fill=TEAL, outline=INK, width=2)
    # railings flanking the stairs
    for rx in (bx0 + 14, bx1 - 14):
        d.line([(rx, by1 - 8), (rx, by0 + 22)], fill=GOLD, width=4)
        d.ellipse([rx - 4, by0 + 16, rx + 4, by0 + 24], fill=GOLD, outline=INK, width=2)
    return img


def dai_pai_dong() -> Image.Image:
    """Open-air food stall: cinnabar striped awning, counter, wok + steam, stools."""
    W, H = 212, 210
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    for px in (54, 158):                                   # awning support poles
        d.line([(px, 72), (px, 182)], fill=INK, width=4)
    d.polygon([(40, 58), (172, 58), (182, 84), (30, 84)], fill=CINNABAR, outline=INK)  # awning
    for sx in range(48, 176, 22):                          # cream stripes
        d.line([(sx, 60), (sx - 7, 82)], fill=CREAM, width=5)
    d.line([(30, 84), (182, 84)], fill=INK, width=3)
    d.rounded_rectangle([50, 98, 162, 170], radius=5, fill=CREAM, outline=INK, width=4)  # counter
    d.rectangle([50, 152, 162, 170], fill=CONC_SH); d.line([(50, 152), (162, 152)], fill=INK, width=2)
    d.ellipse([86, 92, 126, 110], fill=INK)               # wok
    d.ellipse([92, 90, 120, 104], fill=CONC_SH)
    for wx in (100, 108, 116):                             # steam wisps
        d.arc([wx - 6, 68, wx + 6, 92], 200, 340, fill=CREAM, width=3)
    d.rounded_rectangle([132, 100, 156, 132], radius=3, fill=GOLD, outline=INK, width=2)  # blank menu
    for sx in (76, 122):                                   # stools
        d.ellipse([sx - 10, 172, sx + 10, 182], fill=GOLD, outline=INK, width=2)
        d.line([(sx - 7, 182), (sx - 9, 198)], fill=INK, width=3)
        d.line([(sx + 7, 182), (sx + 9, 198)], fill=INK, width=3)
    return img


def junk_boat() -> Image.Image:
    """Red-sail HK junk: warm-wood hull, two masts, battened cinnabar sails."""
    W, H = 280, 232
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    for wx in range(30, 252, 32):                          # waterline
        d.line([(wx, 208), (wx + 16, 208)], fill=TEAL, width=4)
    d.polygon([(240, 170), (252, 178), (226, 204), (214, 202)], fill=CONC_SH)  # 3/4 stern
    d.polygon([(40, 170), (240, 170), (214, 202), (70, 202)], fill=GOLD, outline=INK)  # hull
    d.line([(40, 170), (240, 170)], fill=INK, width=5); d.line([(70, 202), (214, 202)], fill=INK, width=5)
    d.line([(40, 170), (70, 202)], fill=INK, width=5); d.line([(240, 170), (214, 202)], fill=INK, width=5)
    d.rectangle([46, 174, 234, 184], fill=CINNABAR)        # red beltline
    for mx in (98, 186):                                   # masts
        d.line([(mx, 168), (mx, 30)], fill=INK, width=5)

    def sail(mx, top, bot, w):                             # battened fan sail
        d.polygon([(mx, top), (mx + w, top + 12), (mx + w - 8, bot), (mx, bot)], fill=CINNABAR, outline=INK)
        for by in range(top + 18, bot - 4, 18):
            d.line([(mx, by), (mx + w - 6, by + 4)], fill=INK, width=2)
    sail(98, 40, 152, 60)
    sail(186, 32, 152, 66)
    return img


def neon_sign() -> Image.Image:
    """Protruding HK neon: dark panel on a wall bracket, abstract glowing tubes."""
    W, H = 152, 236
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    d.rectangle([6, 40, 22, 208], fill=CONC_SH, outline=INK)            # wall slice
    d.line([(22, 74), (58, 74)], fill=INK, width=6); d.line([(22, 152), (58, 152)], fill=INK, width=6)  # arms
    d.rounded_rectangle([54, 48, 132, 200], radius=8, fill=INK)         # sign back
    d.rounded_rectangle([58, 52, 128, 196], radius=6, outline=GOLD, width=2)
    cx = 93

    def glow_ellipse(box, color):                          # wide-faint + thin-bright = neon
        d.ellipse(box, outline=color + (70,), width=8); d.ellipse(box, outline=color + (255,), width=3)

    def glow_line(pts, color):
        d.line(pts, fill=color + (70,), width=9, joint="curve"); d.line(pts, fill=color + (255,), width=3, joint="curve")

    glow_ellipse([cx - 22, 68, cx + 22, 112], CINNABAR)                 # ring
    glow_line([(cx - 16, 130), (cx - 16, 182)], TEAL)                   # bars
    glow_line([(cx + 16, 130), (cx + 16, 182)], TEAL)
    glow_line([(cx - 12, 156), (cx, 142), (cx + 12, 156)], GOLD)        # zigzag
    return img


PROPS = {
    "mtr-entrance": mtr_entrance,
    "dai-pai-dong": dai_pai_dong,
    "junk-boat": junk_boat,
    "neon-sign": neon_sign,
}


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate the HK street-prop batch")
    ap.add_argument("--out", type=Path, default=Path("game-tiles/props"))
    args = ap.parse_args()
    out = (Path(__file__).resolve().parent.parent / args.out
           if not args.out.is_absolute() else args.out)
    out.mkdir(parents=True, exist_ok=True)
    for name, fn in PROPS.items():
        fn().save(out / f"{name}.png")
    print(f"street props → {out}  ({', '.join(PROPS)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
