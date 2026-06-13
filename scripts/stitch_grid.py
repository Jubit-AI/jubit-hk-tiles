#!/usr/bin/env python3
"""Montage a map_grid bake (r{row}_c{col}.png) into one image — the seam test.

Naive edge-to-edge montage: the deep-zoom MAP's tiles are baked so their ground
coverage abuts (see central_render_bake.map_grid), so a correct seamless render
montages cleanly. Visible seams here = the isometric building-overhang problem
(a tall building clipped at a tile's top edge), which would need an overlap-blend
pass. This script is the cheap decisive check before building the DZI pyramid.

Usage:
  uv run python scripts/stitch_grid.py --in scripts/out/map-test --out scripts/out/map-test/_stitched.png
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from PIL import Image

TILE_RE = re.compile(r"r(\d+)_c(\d+)\.png$")


def main() -> int:
    ap = argparse.ArgumentParser(description="Montage r{row}_c{col} map tiles")
    ap.add_argument("--in", dest="indir", required=True, type=Path)
    ap.add_argument("--out", dest="out", default=None, type=Path)
    args = ap.parse_args()

    tiles = {}
    max_r = max_c = -1
    for p in args.indir.glob("r*_c*.png"):
        m = TILE_RE.search(p.name)
        if not m:
            continue
        r, c = int(m.group(1)), int(m.group(2))
        tiles[(r, c)] = p
        max_r, max_c = max(max_r, r), max(max_c, c)
    if not tiles:
        print(f"no r*_c*.png tiles in {args.indir}")
        return 1

    # tile size from the first tile
    tw, th = Image.open(next(iter(tiles.values()))).size
    cols, rows = max_c + 1, max_r + 1
    canvas = Image.new("RGBA", (cols * tw, rows * th), (0, 0, 0, 0))
    placed = 0
    for (r, c), p in tiles.items():
        canvas.paste(Image.open(p).convert("RGBA"), (c * tw, r * th))
        placed += 1

    out = args.out or (args.indir / "_stitched.png")
    canvas.save(out)
    print(f"stitched {placed}/{rows*cols} tiles → {out} ({cols*tw}×{rows*th})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
