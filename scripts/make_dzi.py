#!/usr/bin/env python3
"""Generate a Deep Zoom Image (DZI) pyramid from one image — pure Pillow.

OpenSeaDragon (the dseek.ai/data/life pixel-mode viewer) consumes:
  <name>.dzi                              the XML descriptor
  <name>_files/<level>/<col>_<row>.png    the tile pyramid

No libvips / pyvips / sharp dependency (none installed here) — just Pillow.
Level numbering is standard DZI: the highest level is full resolution, each
lower level halves the dimensions down to 1×1.

Usage:
  uv run python scripts/make_dzi.py --in scripts/out/viewmap-soft/_stitched.png \
      --out viewer/central
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image

DZI_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<Image TileSize="{ts}" Overlap="{ov}" Format="{fmt}" '
    'xmlns="http://schemas.microsoft.com/deepzoom/2008">\n'
    '  <Size Width="{w}" Height="{h}"/>\n'
    '</Image>\n'
)


def make_dzi(src: Path, out_base: Path, tile_size: int = 256,
             overlap: int = 1, fmt: str = "png") -> None:
    # Validate params — tile_size is a divisor (ZeroDivisionError if 0) and a
    # negative overlap would invert the crop math.
    if tile_size < 1:
        raise ValueError(f"tile_size must be >= 1 (got {tile_size})")
    if overlap < 0:
        raise ValueError(f"overlap must be >= 0 (got {overlap})")
    img = Image.open(src).convert("RGBA")
    w, h = img.size
    if w < 1 or h < 1:
        raise ValueError(f"source image has invalid size {w}×{h}")
    out_base.parent.mkdir(parents=True, exist_ok=True)
    files_dir = out_base.parent / (out_base.name + "_files")

    max_dim = max(w, h)
    max_level = math.ceil(math.log2(max_dim)) if max_dim > 1 else 0

    out_base.with_suffix(".dzi").write_text(
        DZI_XML.format(ts=tile_size, ov=overlap, fmt=fmt, w=w, h=h)
    )

    total = 0
    for level in range(max_level, -1, -1):
        scale = 2 ** (max_level - level)
        lw, lh = max(1, math.ceil(w / scale)), max(1, math.ceil(h / scale))
        level_img = img if scale == 1 else img.resize((lw, lh), Image.LANCZOS)
        lvl_dir = files_dir / str(level)
        lvl_dir.mkdir(parents=True, exist_ok=True)
        cols, rows = math.ceil(lw / tile_size), math.ceil(lh / tile_size)
        for r in range(rows):
            for c in range(cols):
                x = c * tile_size - (overlap if c > 0 else 0)
                y = r * tile_size - (overlap if r > 0 else 0)
                x2 = min(lw, c * tile_size + tile_size + overlap)
                y2 = min(lh, r * tile_size + tile_size + overlap)
                level_img.crop((max(0, x), max(0, y), x2, y2)).save(
                    lvl_dir / f"{c}_{r}.{fmt}"
                )
                total += 1
    print(f"DZI → {out_base.with_suffix('.dzi')}  ({w}×{h}, "
          f"levels 0..{max_level}, {total} tiles)")


def main() -> int:
    ap = argparse.ArgumentParser(description="Pure-Pillow DZI pyramid generator")
    ap.add_argument("--in", dest="src", required=True, type=Path)
    ap.add_argument("--out", dest="out", required=True, type=Path,
                    help="output base path (without .dzi), e.g. viewer/central")
    ap.add_argument("--tile-size", type=int, default=256)
    ap.add_argument("--overlap", type=int, default=1)
    args = ap.parse_args()
    make_dzi(args.src, args.out, args.tile_size, args.overlap)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
