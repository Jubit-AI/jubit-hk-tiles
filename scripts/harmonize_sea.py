#!/usr/bin/env python3
"""Phase A polish — harmonize the f2 empty-sea fill with the real f2 water.

The f2 visualisation tileset has NO mesh over open sea, so those pixels fall
through to the renderer's clear colour (0x35655c). Graded, that clear colour pops
as a bright cyan that clashes with f2's own (darker, muted) textured water →
the harbour reads as a patchwork of bright rectangles next to real water.

This recolours ONLY those exact clear-colour pixels (a tiny, unambiguous ~5%
mask — never touches land, buildings, or textured water) to the measured f2
water tone plus a faint deterministic ripple, so the empties blend seamlessly
into the real water and the harbour reads uniform. Run on the RAW stitch, before
grade_viz.py. (A cuter all-teal harbour would require segmenting the muddy f2
water itself — deferred to the elevation-ramp / AI-restyle path; this detailed
map keeps real f2 colour, just without the clear-colour seam.)

Usage:
  uv run python scripts/harmonize_sea.py \
      --in scripts/out/territory-real/_stitched.png \
      --out scripts/out/territory-real/_stitched.png
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

CLEAR_RGB = np.array([53, 101, 92])      # main.js visualisation setClearColor(0x35655c)
WATER_RGB = np.array([36, 55, 49], np.float32)  # measured f2 textured-water mean (+faint teal)
TOL = 12                                  # |Δ| sum tolerance — the clear colour is exact


def harmonize(src: Path, out: Path) -> None:
    im = Image.open(src).convert("RGB")
    arr = np.asarray(im, np.float32)
    mask = np.abs(arr - CLEAR_RGB).sum(2) < TOL
    h, w = arr.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    # subtle, screen-space-deterministic ripple so the fill isn't dead-flat and
    # matches the gentle variance of real water (seamless across the one stitch).
    ripple = (np.sin(xx * 0.06) + np.cos(yy * 0.045) + np.sin((xx + yy) * 0.03)) * 2.2
    arr[mask] = WATER_RGB
    arr[mask, 1] += ripple[mask]
    arr[mask, 2] += ripple[mask] * 0.8
    out.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB").save(out)
    print(f"harmonized sea: recoloured {int(mask.sum())} px "
          f"({100 * mask.mean():.1f}%) → {out} ({w}x{h})")


def main() -> int:
    ap = argparse.ArgumentParser(description="Harmonize f2 empty-sea clear-colour with real water")
    ap.add_argument("--in", dest="src", required=True, type=Path)
    ap.add_argument("--out", dest="out", required=True, type=Path)
    args = ap.parse_args()
    harmonize(args.src, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
