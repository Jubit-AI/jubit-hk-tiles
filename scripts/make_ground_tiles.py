#!/usr/bin/env python3
"""Generate the jubuddy-HK isometric GROUND tileset — the gameplay-legibility layer.

The plan's two-layer split (aesthetic-spec §7): the ground/gameplay tiles
(path/slot/blocked/spawn/goal) are HAND-AUTHORED and kept clean + instantly
readable — NOT produced by the city AI/bake pipeline (which is worst at repeated
game tiles). These are deterministic isometric diamonds in the locked Yok-Iso
palette: designed, total-control, on-brand, transparent PNGs that pair with the
HK identity PROP sprites (central_render_bake.py --transparent) dropped on top.

TileKind vocabulary matches jubuddy-game packages/buddy-core/src/maps/types.ts:
  empty | path | slot | blocked | spawn | goal
Emits PNGs + a tiles.json manifest ({name,w,h}) matching the jubuddy-game shape,
so jubuddy-HK can consume them like any other stage-tile kit.

Pure Pillow — no extra deps. 2:1 dimetric diamond, soft-graffiti ink contour.

Usage:
  uv run python scripts/make_ground_tiles.py --out game-tiles/iso
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw

# ── Palette anchor (aesthetic-spec §1, LOCKED 2026-06-14) ────────────────────
PARCHMENT = (243, 231, 207)   # F3E7CF rice paper (lightest)
OFFWHITE  = (243, 231, 207)   # alias → rice paper
CONC_LT   = (217, 197, 156)   # D9C59C parchment (mid base)
CONC_MD   = (163, 143, 97)    # ~A38F61 derived warm concrete mid
CONC_SH   = (94, 82, 56)      # ~5E5238 derived warm concrete shadow
INK       = (26, 26, 23)      # 1A1A17 contour
GOLD      = (199, 162, 91)    # C7A25B antique gold (slot ring)
TEAL      = (31, 111, 115)    # 1F6F73 harbour teal (goal)
DEEP_HARB = (13, 61, 70)      # 0D3D46 deep harbour
CINNABAR  = (182, 71, 52)     # B64734 (spawn)
JADE      = (46, 140, 125)    # 2E8C7D tram jade (goal gate)

TILE_W, TILE_H = 256, 160          # canvas; diamond is 256 wide × 128 tall
DIAMOND_H = 128
PAD_Y = (TILE_H - DIAMOND_H) // 2   # vertical centring (16px headroom each side)


def diamond_pts(cx, cy, w, h):
    """4 points of a 2:1 iso diamond centred at (cx,cy)."""
    return [(cx, cy - h / 2), (cx + w / 2, cy), (cx, cy + h / 2), (cx - w / 2, cy)]


def base_diamond(draw, fill, *, inset=0, edge=INK, edge_w=3):
    cx, cy = TILE_W / 2, PAD_Y + DIAMOND_H / 2
    w, h = TILE_W - inset * 2, DIAMOND_H - inset
    pts = diamond_pts(cx, cy, w, h)
    # one soft-graffiti ink contour per form (spec §2) + flat cel fill
    draw.polygon(pts, fill=fill, outline=edge)
    for k in range(edge_w):  # thicken the contour without anti-alias fuzz
        draw.line(pts + [pts[0]], fill=edge, width=1, joint="curve")
    return cx, cy


def top_sheen(draw, cx, cy, color):
    """A faint lighter band on the upper diamond faces (cel highlight)."""
    pts = [(cx, cy - DIAMOND_H / 2 + 6), (cx + TILE_W / 2 - 10, cy - 3),
           (cx, cy + 4), (cx - TILE_W / 2 + 10, cy - 3)]
    draw.polygon(pts, fill=color)


def make_tile(kind: str) -> Image.Image:
    img = Image.new("RGBA", (TILE_W, TILE_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    if kind == "empty":
        # neutral buildable-adjacent ground — calm concrete
        cx, cy = base_diamond(d, CONC_MD)
        top_sheen(d, cx, cy, CONC_LT)
    elif kind == "path":
        # the enemy lane — bright warm parchment so it reads as the route
        cx, cy = base_diamond(d, OFFWHITE)
        top_sheen(d, cx, cy, PARCHMENT)
    elif kind == "slot":
        # tower pad — concrete with an antique-gold ring (place here)
        cx, cy = base_diamond(d, CONC_LT)
        top_sheen(d, cx, cy, PARCHMENT)
        d.ellipse([cx - 34, cy - 17, cx + 34, cy + 17], outline=GOLD, width=4)
        d.ellipse([cx - 14, cy - 7, cx + 14, cy + 7], fill=GOLD)
    elif kind == "blocked":
        # impassable — heavy ink-dark stone
        base_diamond(d, CONC_SH)
        cx, cy = TILE_W / 2, PAD_Y + DIAMOND_H / 2
        d.polygon(diamond_pts(cx, cy, TILE_W - 70, DIAMOND_H - 36), fill=INK)
    elif kind == "spawn":
        # enemy entry — path-toned with a cinnabar inbound chevron
        cx, cy = base_diamond(d, OFFWHITE)
        top_sheen(d, cx, cy, PARCHMENT)
        d.polygon([(cx, cy - 22), (cx + 26, cy), (cx, cy + 22), (cx + 8, cy)],
                  fill=CINNABAR)
        d.polygon([(cx - 22, cy - 14), (cx - 4, cy), (cx - 22, cy + 14)], fill=CINNABAR)
    elif kind == "goal":
        # the objective — path-toned with a teal/jade gate marker
        cx, cy = base_diamond(d, OFFWHITE)
        top_sheen(d, cx, cy, PARCHMENT)
        d.ellipse([cx - 30, cy - 15, cx + 30, cy + 15], fill=JADE)
        d.ellipse([cx - 18, cy - 9, cx + 18, cy + 9], fill=TEAL)
    else:
        raise ValueError(f"unknown TileKind: {kind}")
    return img


TILE_KINDS = ["empty", "path", "slot", "blocked", "spawn", "goal"]


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate jubuddy-HK iso ground tiles")
    ap.add_argument("--out", type=Path, default=Path("game-tiles/iso"))
    args = ap.parse_args()
    out = (Path(__file__).resolve().parent.parent / args.out
           if not args.out.is_absolute() else args.out)
    out.mkdir(parents=True, exist_ok=True)

    manifest = {"source": "make_ground_tiles.py (Yok-Iso HK, deterministic)",
                "style": "yok_iso_hk_soft_pictorial", "tileKinds": TILE_KINDS,
                "sliced": []}
    for kind in TILE_KINDS:
        name = f"iso-{kind}"
        make_tile(kind).save(out / f"{name}.png")
        manifest["sliced"].append({"name": name, "w": TILE_W, "h": TILE_H})
    (out / "tiles.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"ground tiles → {out}  ({len(TILE_KINDS)} TileKinds + tiles.json)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
